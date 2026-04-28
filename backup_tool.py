# -*- coding: utf-8 -*-
"""
Backup Tool
Sicoob Credinter
"""

import os
import sys
import json
import shutil
import zipfile
import threading
import subprocess
import ctypes
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

# Paleta de Cores
COLORS = {
    'primary': '#004050',    # Azul Escuro Profundo
    'accent': '#c1d831',     # Verde Lima
    'bg': '#F5F8F7',         # Cinza Suave
    'white': '#FFFFFF',
    'sidebar': '#004050',
    'text_dark': '#004050',
    'text_muted': '#64748b',
    'success': '#10b981',
    'error': '#ef4444',
    'terminal': '#004050'
}

class BrowserProfile:
    def __init__(self, name, folder_name, browser_type):
        self.name = name
        self.folder_name = folder_name
        self.browser_type = browser_type

class EnhancedBackupEngine:
    def __init__(self, log_callback, progress_callback):
        self.log_callback = log_callback
        self.progress_callback = progress_callback
        self.is_cancelled = False
        self.total_files = 0
        self.processed_files = 0

    def log(self, msg, level="INFO"):
        self.log_callback(f"{msg}", level)

    def get_browser_profiles(self, username):
        profiles = []
        user_home = Path(f'C:/Users/{username}')
        
        # Chrome
        chrome_path = user_home / 'AppData/Local/Google/Chrome/User Data'
        if chrome_path.exists():
            local_state_path = chrome_path / 'Local State'
            if local_state_path.exists():
                try:
                    with open(local_state_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        info_cache = data.get('profile', {}).get('info_cache', {})
                        for folder, info in info_cache.items():
                            name = info.get('name', folder)
                            profiles.append(BrowserProfile(f"Chrome: {name}", folder, "Chrome"))
                except:
                    profiles.append(BrowserProfile("Chrome: Perfil Padrão", "Default", "Chrome"))

        # Edge
        edge_path = user_home / 'AppData/Local/Microsoft/Edge/User Data'
        if edge_path.exists():
            local_state_path = edge_path / 'Local State'
            if local_state_path.exists():
                try:
                    with open(local_state_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        info_cache = data.get('profile', {}).get('info_cache', {})
                        for folder, info in info_cache.items():
                            name = info.get('name', folder)
                            profiles.append(BrowserProfile(f"Edge: {name}", folder, "Edge"))
                except:
                    profiles.append(BrowserProfile("Edge: Perfil Padrão", "Default", "Edge"))

        # Firefox
        ff_path = user_home / 'AppData/Roaming/Mozilla/Firefox/Profiles'
        if ff_path.exists():
            for folder in os.listdir(ff_path):
                if os.path.isdir(ff_path / folder):
                    profiles.append(BrowserProfile(f"Firefox: {folder}", folder, "Firefox"))
        
        return profiles

    def get_size_info(self, paths):
        total_size = 0
        file_count = 0
        for p in paths:
            if p.exists():
                if p.is_file():
                    total_size += p.stat().st_size
                    file_count += 1
                else:
                    for item in p.rglob('*'):
                        if item.is_file():
                            try:
                                total_size += item.stat().st_size
                                file_count += 1
                            except:
                                continue
        return total_size, file_count

    def format_size(self, size_bytes):
        if size_bytes == 0: return "0 B"
        import math
        size_name = ("B", "KB", "MB", "GB", "TB")
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_name[i]}"

    def count_files(self, paths):
        _, count = self.get_size_info(paths)
        return count

    def start_backup(self, username, source_folders, dest_root, use_zip=False):
        self.is_cancelled = False
        self.processed_files = 0
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        import socket
        machine_name = socket.gethostname()
        base_name = f"Backup_{machine_name}_{username}_{timestamp}"
        
        info_content = (
            "========== INFORMACOES DO BACKUP ==========\n"
            f"Maquina de Origem: {machine_name}\n"
            f"Usuario de Origem: {username}\n"
            f"Data/Hora do Backup: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
            "===========================================\n"
        )
        
        try:
            if not use_zip:
                backup_dir = Path(dest_root) / base_name
                backup_dir.mkdir(parents=True, exist_ok=True)
                
                info_file_path = backup_dir / "info_restauracao.txt"
                with open(info_file_path, "w", encoding="utf-8") as f:
                    f.write(info_content)

            user_home = Path(f'C:/Users/{username}')
            
            std_mapping = {
                'Desktop': user_home / 'Desktop',
                'Documentos': user_home / 'Documents',
                'Downloads': user_home / 'Downloads',
                'Imagens': user_home / 'Pictures',
                'Videos': user_home / 'Videos'
            }

            self.log(f"Analizando arquivos do usuário {username}...")
            
            paths_to_process = []
            for folder_name in source_folders:
                if folder_name in std_mapping:
                    paths_to_process.append((std_mapping[folder_name], folder_name))
                elif folder_name.startswith("Browser:"):
                    parts = folder_name.split('|')
                    b_type = parts[1]
                    p_folder = parts[2]
                    if b_type == "Firefox":
                        b_path = user_home / 'AppData/Roaming/Mozilla/Firefox/Profiles' / p_folder
                    else:
                        base = "Google/Chrome" if b_type=="Chrome" else "Microsoft/Edge"
                        b_path = user_home / 'AppData/Local' / base / 'User Data' / p_folder
                    paths_to_process.append((b_path, f"Navegador_{b_type}_{p_folder}"))

            self.total_files = self.count_files([p[0] for p in paths_to_process])
            self.log(f"Total de arquivos localizados: {self.total_files}")

            if self.total_files == 0:
                self.log("Nenhum arquivo encontrado para as pastas selecionadas.", "ERROR")
                return False

            if use_zip:
                zip_path = Path(dest_root) / f"{base_name}.zip"
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    zipf.writestr("info_restauracao.txt", info_content)
                    for src, name in paths_to_process:
                        if self.is_cancelled: break
                        self.log(f"Compactando: {name}")
                        self._zip_folder(src, name, zipf)
            else:
                for src, name in paths_to_process:
                    if self.is_cancelled: break
                    target = backup_dir / name
                    self.log(f"Copiando: {name}")
                    self._copy_folder(src, target)

            if self.is_cancelled:
                self.log("Backup CANCELADO pelo usuário.", "ERROR")
                return False
            else:
                self.log("Backup CONCLUÍDO com sucesso!", "SUCCESS")
                return True

        except Exception as e:
            self.log(f"Erro fatal no backup: {str(e)}", "ERROR")
            return False

    def _copy_folder(self, src, dst):
        if not src.exists(): return
        dst.mkdir(parents=True, exist_ok=True)
        for item in src.rglob('*'):
            if self.is_cancelled: return
            if item.is_file():
                try:
                    rel = item.relative_to(src)
                    target = dst / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, target)
                    self.processed_files += 1
                    self.progress_callback(self.processed_files, self.total_files, item.name)
                except: continue

    def _zip_folder(self, src, arcname, zipf):
        if not src.exists(): return
        for item in src.rglob('*'):
            if self.is_cancelled: return
            if item.is_file():
                try:
                    rel = item.relative_to(src)
                    zipf.write(item, Path(arcname) / rel)
                    self.processed_files += 1
                    self.progress_callback(self.processed_files, self.total_files, item.name)
                except: continue

class EnhancedRestoreEngine(EnhancedBackupEngine):
    def get_backup_info(self, source_path):
        import zipfile
        info = {}
        path = Path(source_path)
        if path.is_file() and path.suffix == '.zip':
            try:
                with zipfile.ZipFile(path, 'r') as zipf:
                    if "info_restauracao.txt" in zipf.namelist():
                        with zipf.open("info_restauracao.txt") as f:
                            content = f.read().decode('utf-8')
                            for line in content.split('\n'):
                                if ":" in line:
                                    k, v = line.split(':', 1)
                                    info[k.strip()] = v.strip()
            except: pass
        elif path.is_dir():
            info_file = path / "info_restauracao.txt"
            if info_file.exists():
                with open(info_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    for line in content.split('\n'):
                        if ":" in line:
                            k, v = line.split(':', 1)
                            info[k.strip()] = v.strip()
        return info

    def start_restore(self, backup_source, target_username):
        import shutil
        import zipfile
        self.is_cancelled = False
        self.processed_files = 0
        try:
            target_home = Path(f"C:/Users/{target_username}")
            if not target_home.exists():
                self.log(f"Usuário alvo {target_username} não encontrado.", "ERROR")
                return False

            backup_path = Path(backup_source)
            self.log("Iniciando restauração...")

            if backup_path.is_dir():
                return self._restore_from_dir(backup_path, target_home)
            elif backup_path.is_file() and backup_path.suffix == '.zip':
                return self._restore_from_zip(backup_path, target_home)
            else:
                self.log("Origem de backup inválida.", "ERROR")
                return False

        except Exception as e:
            self.log(f"Erro fatal na restauração: {str(e)}", "ERROR")
            return False

    def _restore_from_dir(self, cwd, target_home):
        self.total_files = self.count_files([cwd])
        self._kill_browsers()
        for item in cwd.iterdir():
            if item.is_file(): continue
            target_path = self._map_folder_to_target(item.name, target_home)
            if not target_path: continue
            self.log(f"Restaurando pasta: {item.name}")
            self._copy_folder(item, target_path)
        if self.is_cancelled: return False
        self.log("Restauração CONCLUÍDA!", "SUCCESS")
        return True

    def _restore_from_zip(self, zip_file, target_home):
        import zipfile
        import shutil
        self._kill_browsers()
        with zipfile.ZipFile(zip_file, 'r') as zipf:
            namelist = zipf.namelist()
            self.total_files = len(namelist)
            
            for file_path in namelist:
                if self.is_cancelled: break
                parts = Path(file_path).parts
                if len(parts) == 0: continue
                top_folder = parts[0]
                if top_folder == "info_restauracao.txt": continue
                
                target_base = self._map_folder_to_target(top_folder, target_home)
                if not target_base: continue
                
                rel_path = Path(*parts[1:])
                target_file = target_base / rel_path
                
                if file_path.endswith('/'): 
                    target_file.mkdir(parents=True, exist_ok=True)
                    continue

                target_file.parent.mkdir(parents=True, exist_ok=True)
                try:
                    with zipf.open(file_path) as source, open(target_file, "wb") as target:
                        shutil.copyfileobj(source, target)
                except: pass
                
                self.processed_files += 1
                if self.processed_files % 15 == 0:
                    self.progress_callback(self.processed_files, self.total_files, Path(file_path).name)
        if self.is_cancelled: return False
        self.log("Restauração CONCLUÍDA!", "SUCCESS")
        return True

    def _map_folder_to_target(self, folder_name, target_home):
        std_mapping = {
            'Desktop': target_home / 'Desktop',
            'Documentos': target_home / 'Documents',
            'Downloads': target_home / 'Downloads',
            'Imagens': target_home / 'Pictures',
            'Videos': target_home / 'Videos'
        }
        if folder_name in std_mapping: return std_mapping[folder_name]
        try:
            if folder_name.startswith("Navegador_"):
                parts = folder_name.split('_')
                if len(parts) < 3: return None
                b_type = parts[1]
                p_folder = "_".join(parts[2:])
                if b_type == "Chrome": return target_home / 'AppData/Local/Google/Chrome/User Data' / p_folder
                elif b_type == "Edge": return target_home / 'AppData/Local/Microsoft/Edge/User Data' / p_folder
                elif b_type == "Firefox": return target_home / 'AppData/Roaming/Mozilla/Firefox/Profiles' / p_folder
        except: pass
        return None

    def _kill_browsers(self):
        import subprocess
        self.log("Fechando navegadores antes da restauração...")
        try:
            subprocess.run(['taskkill', '/F', '/IM', 'chrome.exe'], creationflags=subprocess.CREATE_NO_WINDOW, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(['taskkill', '/F', '/IM', 'msedge.exe'], creationflags=subprocess.CREATE_NO_WINDOW, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(['taskkill', '/F', '/IM', 'firefox.exe'], creationflags=subprocess.CREATE_NO_WINDOW, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except: pass

class ProfessionalBackupGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Backup Tool | Sicoob Credinter")
        self.root.geometry("1100x950")
        self.root.state('zoomed')
        self.root.configure(bg=COLORS['primary'])
        
        self.engine = EnhancedBackupEngine(self.add_log, self.update_progress)
        self.selected_user = tk.StringVar()
        self.dest_path = tk.StringVar()
        self.use_zip = tk.BooleanVar(value=False)
        self.is_admin_validated = True
        self.loading_frames = []

        # Tenta carregar o loading.gif
        try:
            def resource_path(relative_path):
                import sys
                import os
                try:
                    base_path = sys._MEIPASS
                except Exception:
                    base_path = os.path.dirname(os.path.abspath(__file__))
                return os.path.join(base_path, relative_path)
            
            gif_path = resource_path("loading.gif")
            if os.path.exists(gif_path):
                try:
                    from PIL import Image, ImageTk
                    pil_img = Image.open(gif_path)
                    try:
                        while True:
                            # Use LANCZOS se disponível, senão padrão
                            resample_filter = getattr(Image, 'Resampling', Image).LANCZOS
                            frame = pil_img.copy().convert('RGBA').resize((15, 15), resample_filter)
                            self.loading_frames.append(ImageTk.PhotoImage(frame))
                            pil_img.seek(len(self.loading_frames))
                    except EOFError:
                        pass
                except ImportError:
                    # Fallback padrão Tkinter
                    img = tk.PhotoImage(file=gif_path, format="gif -index 0")
                    while True:
                        w = img.width()
                        if w > 15:
                            r = w // 15
                            img = img.subsample(r, r)
                        self.loading_frames.append(img)
                        img = tk.PhotoImage(file=gif_path, format=f"gif -index {len(self.loading_frames)}")
        except Exception:
            pass

        self._setup_styles()
        self._create_widgets()
        self.load_users()

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        # Estilos Globais
        style.configure("TFrame", background=COLORS['bg'])
        style.configure("Sidebar.TFrame", background=COLORS['sidebar'])
        
        # Labels
        style.configure("TLabel", background=COLORS['bg'], foreground=COLORS['text_dark'], font=('Segoe UI', 10))
        style.configure("Header.TLabel", background=COLORS['white'], foreground=COLORS['primary'], font=('Segoe UI', 14, 'bold'))
        style.configure("Sidebar.TLabel", background=COLORS['sidebar'], foreground=COLORS['white'], font=('Segoe UI', 10, 'bold'))
        style.configure("Step.TLabel", background=COLORS['primary'], foreground=COLORS['white'], font=('Segoe UI', 9, 'bold'), padding=5)
        
        # Cards
        style.configure("Card.TLabelframe", background=COLORS['white'], borderwidth=1, relief="solid", padding=20)
        style.configure("Card.TLabelframe.Label", font=('Segoe UI', 10, 'bold'), foreground=COLORS['primary'])
        
        # Botões
        style.configure("Primary.TButton", font=('Segoe UI', 11, 'bold'), padding=15, background=COLORS['accent'], foreground=COLORS['primary'])
        style.map("Primary.TButton", background=[('active', '#9cb800')])
        
        style.configure("Action.TButton", font=('Segoe UI', 9, 'bold'), padding=8, background=COLORS['white'], foreground=COLORS['primary'])
        
        # Progress Bar
        style.configure("Modern.Horizontal.TProgressbar", thickness=10, background=COLORS['accent'], troughcolor='#e5e7eb', bordercolor='#e5e7eb')

    def _create_widgets(self):
        # Sidebar
        sidebar = tk.Frame(self.root, bg=COLORS['sidebar'], width=70)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)

        logo_container = tk.Frame(sidebar, bg=COLORS['sidebar'])
        logo_container.pack(pady=30)

        # Tenta carregar a imagem logo.png
        self.logo_img = None
        logo_loaded = False
        
        # Helper para PyInstaller extrair arquivos na pasta temporária (_MEIPASS)
        def resource_path(relative_path):
            try:
                base_path = sys._MEIPASS
            except Exception:
                base_path = os.path.dirname(os.path.abspath(__file__))
            return os.path.join(base_path, relative_path)

        logo_path = resource_path("logo.png")
        if os.path.exists(logo_path):
            try:
                # Carregar imagem em tamanho original para o ícone da janela
                self.icon_img = tk.PhotoImage(file=logo_path)
                self.root.iconphoto(True, self.icon_img)

                # Redimensionar para o uso lateral (subsample)
                self.logo_img = tk.PhotoImage(file=logo_path)
                width = self.logo_img.width()
                if width > 60:
                    ratio = width // 45
                    if ratio > 1:
                        self.logo_img = self.logo_img.subsample(ratio, ratio)
                
                tk.Label(logo_container, image=self.logo_img, bg=COLORS['sidebar']).pack()
                logo_loaded = True
            except Exception as e:
                print(f"Erro ao carregar logo.png: {e}")

        if not logo_loaded:
            # Fallback para o logo de texto "BP" (Backup)
            logo_box = tk.Frame(logo_container, bg=COLORS['accent'], width=45, height=45)
            logo_box.pack()
            tk.Label(logo_box, text="BP", bg=COLORS['accent'], fg=COLORS['primary'], font=('Segoe UI', 14, 'bold')).place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        # Tenta carregar ícone para a barra de título caso o iconphoto falhe em alguma versão
        ico_path = resource_path("logo.ico")
        if os.path.exists(ico_path):
            try:
                self.root.iconbitmap(ico_path)
            except Exception:
                pass

        # Main Layout
        content_area = tk.Frame(self.root, bg=COLORS['bg'])
        content_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Header
        header = tk.Frame(content_area, bg=COLORS['white'], height=70, bd=0, highlightthickness=1, highlightbackground='#e2e8f0')
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(header, text="BACKUP ", bg=COLORS['white'], fg=COLORS['primary'], font=('Segoe UI', 12, 'bold')).pack(side=tk.LEFT, padx=(30, 0))
        tk.Label(header, text="TOOL", bg=COLORS['white'], fg=COLORS['accent'], font=('Segoe UI', 12, 'bold')).pack(side=tk.LEFT)
        
        self.auth_status = tk.Label(header, text="ADMINISTRADOR: ATIVO", bg='#ecfdf5', fg='#047857', font=('Segoe UI', 8, 'bold'), padx=10, pady=2)
        self.auth_status.pack(side=tk.RIGHT, padx=30)

        # Configurar Notebook (Abas) para alternar Backup e Restore
        style = ttk.Style()
        style.configure("TNotebook", background=COLORS['bg'], borderwidth=0)
        style.configure("TNotebook.Tab", background=COLORS['primary'], foreground=COLORS['white'], padding=[20, 8], font=('Segoe UI', 10, 'bold'))
        style.map("TNotebook.Tab", background=[('selected', COLORS['primary'])], foreground=[('selected', COLORS['accent'])])

        self.notebook = ttk.Notebook(content_area)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=(10, 20))

        # ABA 1: BACKUP
        self.tab_backup = tk.Frame(self.notebook, bg=COLORS['bg'])
        self.notebook.add(self.tab_backup, text="   📤 FAZER BACKUP   ")

        main_scrollable = tk.Frame(self.tab_backup, bg=COLORS['bg'])
        main_scrollable.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # ABA 2: RESTAURACAO
        self.tab_restore = tk.Frame(self.notebook, bg=COLORS['bg'])
        self.notebook.add(self.tab_restore, text="   📥 RESTAURAR BACKUP   ")
        self._build_restore_tab()

        # Terminal Global
        terminal_frame = tk.Frame(content_area, bg=COLORS['terminal'], height=130)
        terminal_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=20, pady=(0, 20))
        terminal_frame.pack_propagate(False)
        tk.Label(terminal_frame, text="TERMINAL DE LOG E PROGRESSO", bg=COLORS['terminal'], fg='#c1d831', font=('Segoe UI', 7, 'bold')).pack(anchor=tk.W, padx=10, pady=5)
        
        loader_frame = tk.Frame(terminal_frame, bg=COLORS['terminal'])
        loader_frame.pack(fill=tk.X, padx=10)
        self.lbl_gif = tk.Label(loader_frame, bg=COLORS['terminal'])
        self.lbl_gif.pack(side=tk.LEFT, padx=5)
        
        style.configure("Custom.Horizontal.TProgressbar", thickness=3, background=COLORS['accent'], troughcolor='#4b767c', bordercolor=COLORS['terminal'])
        self.progress_bar = ttk.Progressbar(loader_frame, style="Custom.Horizontal.TProgressbar", orient=tk.HORIZONTAL, mode='determinate')
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=2)
        
        self.status_lbl = tk.Label(loader_frame, text="Standby", bg=COLORS['terminal'], fg='#c2e0a4', font=('Segoe UI', 8))
        self.status_lbl.pack(side=tk.RIGHT, padx=10)

        self.log_widget = tk.Text(terminal_frame, bg=COLORS['terminal'], fg='#10b981', font=('Consolas', 8), bd=0, insertbackground='white')
        self.log_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 5))
        
        self.gif_job = None
        self.gif_frame_idx = 0
        
        # Container Principal Backup
        left_grid = tk.Frame(main_scrollable, bg=COLORS['bg'])
        left_grid.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # --- Passo 1: Usuário ---
        user_section = ttk.LabelFrame(left_grid, text="  1. SELEÇÃO DE USUÁRIO LOCAL  ", style="Card.TLabelframe")
        user_section.pack(fill=tk.X, pady=(0, 20))
        
        tk.Label(user_section, text="Identifique o perfil de origem no sistema:", bg='white', fg=COLORS['text_muted'], font=('Segoe UI', 9)).pack(anchor=tk.W, pady=(0, 10))
        
        combo_frame = tk.Frame(user_section, bg='white')
        combo_frame.pack(fill=tk.X)
        
        self.user_combo = ttk.Combobox(combo_frame, textvariable=self.selected_user, state="readonly", width=50)
        self.user_combo.pack(side=tk.LEFT, ipady=3)
        self.user_combo.bind("<<ComboboxSelected>>", self.on_user_switch)
        
        ttk.Button(combo_frame, text="ATUALIZAR", style="Action.TButton", command=self.load_users).pack(side=tk.LEFT, padx=15)

        import socket
        info_frame = tk.Frame(user_section, bg='#f8fafc', bd=1, relief="solid")
        info_frame.config(highlightbackground='#e2e8f0', highlightcolor='#e2e8f0', highlightthickness=1)
        info_frame.pack(fill=tk.X, pady=(15, 0))
        tk.Label(info_frame, text=f"💻 Máquina de Origem: {socket.gethostname().upper()}", bg='#f8fafc', fg=COLORS['primary'], font=('Segoe UI', 9, 'bold')).pack(side=tk.LEFT, padx=10, pady=8)

        # --- Passo 2: Privilégios de Sistema ---
        auth_section = ttk.LabelFrame(left_grid, text="  2. PRIVILÉGIOS DE SISTEMA  ", style="Card.TLabelframe")
        auth_section.pack(fill=tk.X, pady=(0, 20))

        auth_frame = tk.Frame(auth_section, bg='#ecfdf5', bd=1, relief="solid", highlightthickness=1, highlightbackground='#a7f3d0')
        auth_frame.pack(fill=tk.X, ipady=10, pady=5)
        
        tk.Label(auth_frame, text="✓ ACESSO TOTAL CONCEDIDO", bg='#ecfdf5', fg='#047857', font=('Segoe UI', 10, 'bold')).pack(anchor=tk.W, padx=15, pady=(5, 0))
        tk.Label(auth_frame, text="Sessão iniciada como Administrador via UAC. Permissão garantida aos perfis locais.", bg='#ecfdf5', fg='#065f46', font=('Segoe UI', 9)).pack(anchor=tk.W, padx=15, pady=(2, 5))

        # --- Passo 3: Destino ---
        dest_section = ttk.LabelFrame(left_grid, text="  3. PASTA DE DESTINO  ", style="Card.TLabelframe")
        dest_section.pack(fill=tk.X)
        
        dest_box = tk.Frame(dest_section, bg='#f8fafc', bd=1, relief="solid")
        dest_box.pack(fill=tk.X, ipady=10)
        
        tk.Entry(dest_box, textvariable=self.dest_path, bg='#f8fafc', bd=0, font=('Consolas', 9)).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=15)
        tk.Button(dest_box, text="PROCURAR...", bg='white', relief="flat", fg=COLORS['text_dark'], font=('Segoe UI', 8, 'bold'), command=self.browse_dest).pack(side=tk.RIGHT, padx=10)

        zip_box = tk.Frame(dest_section, bg='white')
        zip_box.pack(fill=tk.X, anchor=tk.W, pady=(5, 10))
        tk.Checkbutton(zip_box, text="Compactar backup em formato .zip", variable=self.use_zip, bg='white', activebackground='white', fg=COLORS['text_dark'], font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5)

        # Coluna Direita (Status e Ações)
        right_panel = tk.Frame(main_scrollable, bg=COLORS['bg'], width=300)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(30, 0))
        right_panel.pack_propagate(False)

        # Módulos
        module_card = tk.Frame(right_panel, bg='white', bd=1, relief="solid", highlightthickness=0)
        module_card.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
        tk.Label(module_card, text="MÓDULOS DE BACKUP", bg='white', fg=COLORS['text_muted'], font=('Segoe UI', 8, 'bold')).pack(pady=15)
        
        self.tasks_container = tk.Frame(module_card, bg='white')
        self.tasks_container.pack(fill=tk.BOTH, expand=True, padx=20)

        # Execution Card
        exec_card = tk.Frame(right_panel, bg=COLORS['primary'], bd=0)
        exec_card.pack(fill=tk.X, ipady=20)
        
        tk.Label(exec_card, text="PRONTO?", bg=COLORS['primary'], fg='white', font=('Segoe UI', 14, 'bold')).pack(pady=(20, 5))
        self.est_label = tk.Label(exec_card, text="Aguardando seleção...", bg=COLORS['primary'], fg='#cbd5e1', font=('Segoe UI', 8))
        self.est_label.pack(pady=(0, 20))

        self.btn_start = tk.Button(exec_card, text="INICIAR BACKUP", bg=COLORS['accent'], fg=COLORS['primary'], font=('Segoe UI', 11, 'bold'), relief="flat", cursor="hand2", command=self.run_backup)
        self.btn_start.pack(fill=tk.X, padx=30, ipady=12)
        
        self.btn_cancel = tk.Button(exec_card, text="CANCELAR", bg=COLORS['accent'], fg=COLORS['error'], font=('Segoe UI', 10, 'bold'), relief="flat", cursor="hand2", command=self.cancel_operation, state=tk.DISABLED)
        self.btn_cancel.pack(fill=tk.X, padx=30, pady=(10, 20), ipady=8)

    def _build_restore_tab(self):
        self.restore_source_path = tk.StringVar()
        self.restore_target_user = tk.StringVar()

        res_grid = tk.Frame(self.tab_restore, bg=COLORS['bg'])
        res_grid.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        left_restore = tk.Frame(res_grid, bg=COLORS['bg'])
        left_restore.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 20))

        # Card: Origem Backup
        src_section = ttk.LabelFrame(left_restore, text="  1. SELECIONAR BACKUP (ORIGEM)  ", style="Card.TLabelframe")
        src_section.pack(fill=tk.X, pady=(0, 20))
        tk.Label(src_section, text="Selecione a pasta do backup ou o arquivo .zip gerado:", bg='white', fg=COLORS['text_muted'], font=('Segoe UI', 9)).pack(anchor=tk.W, pady=(0, 10))
        
        src_box = tk.Frame(src_section, bg='#f8fafc', bd=1, relief="solid")
        src_box.pack(fill=tk.X, ipady=10)
        tk.Entry(src_box, textvariable=self.restore_source_path, bg='#f8fafc', bd=0, font=('Consolas', 9)).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=15)
        
        btn_box = tk.Frame(src_box, bg='#f8fafc')
        btn_box.pack(side=tk.RIGHT, padx=10)
        tk.Button(btn_box, text="SELECIONAR PASTA", bg='white', relief="flat", fg=COLORS['text_dark'], font=('Segoe UI', 8, 'bold'), command=lambda: self.restore_source_path.set(filedialog.askdirectory() or "") or self.check_backup_info()).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_box, text="SELECIONAR ZIP", bg='white', relief="flat", fg=COLORS['text_dark'], font=('Segoe UI', 8, 'bold'), command=lambda: self.restore_source_path.set(filedialog.askopenfilename(filetypes=[("Zip Files", "*.zip")]) or "") or self.check_backup_info()).pack(side=tk.LEFT)

        self.info_lbl = tk.Label(src_section, text="Nenhum backup selecionado.", bg='white', fg=COLORS['accent'], font=('Segoe UI', 9, 'bold'))
        self.info_lbl.pack(anchor=tk.W, pady=(15, 0))

        # Card: Destino
        tgt_section = ttk.LabelFrame(left_restore, text="  2. USUÁRIO DE DESTINO (LOCAL)  ", style="Card.TLabelframe")
        tgt_section.pack(fill=tk.X)
        tk.Label(tgt_section, text="Para qual usuário do sistema atual os arquivos devem ser restaurados?", bg='white', fg=COLORS['text_muted'], font=('Segoe UI', 9)).pack(anchor=tk.W, pady=(0, 10))
        
        tgt_box = tk.Frame(tgt_section, bg='white')
        tgt_box.pack(fill=tk.X)
        self.res_user_combo = ttk.Combobox(tgt_box, textvariable=self.restore_target_user, state="readonly", width=50)
        self.res_user_combo.pack(side=tk.LEFT, ipady=3)
        ttk.Button(tgt_box, text="ATUALIZAR LISTA", style="Action.TButton", command=self.load_users).pack(side=tk.LEFT, padx=15)

        # Right Restore
        right_res = tk.Frame(res_grid, bg=COLORS['bg'], width=300)
        right_res.pack(side=tk.RIGHT, fill=tk.BOTH)
        right_res.pack_propagate(False)

        exec_res_card = tk.Frame(right_res, bg=COLORS['primary'], bd=0)
        exec_res_card.pack(fill=tk.X, ipady=20)
        tk.Label(exec_res_card, text="ATENÇÃO AOS DADOS!", bg=COLORS['primary'], fg=COLORS['accent'], font=('Segoe UI', 12, 'bold')).pack(pady=(20, 5))
        tk.Label(exec_res_card, text="Dados de navegadores como\nSenhas (DPAPI) não serão\nrecuperados por conta da\ncriptografia do Windows.\nApenas Favoritos e Histórico.", bg=COLORS['primary'], fg=COLORS['white'], font=('Segoe UI', 9)).pack(pady=(0,20))
        
        self.btn_restore = tk.Button(exec_res_card, text="INICIAR RESTAURAÇÃO", bg=COLORS['accent'], fg=COLORS['primary'], font=('Segoe UI', 11, 'bold'), relief="flat", cursor="hand2", command=self.run_restore)
        self.btn_restore.pack(fill=tk.X, padx=30, ipady=12)
        
        self.btn_cancel_restore = tk.Button(exec_res_card, text="CANCELAR", bg=COLORS['accent'], fg=COLORS['error'], font=('Segoe UI', 10, 'bold'), relief="flat", cursor="hand2", command=self.cancel_operation, state=tk.DISABLED)
        self.btn_cancel_restore.pack(fill=tk.X, padx=30, pady=(10, 20), ipady=8)

    def check_backup_info(self):
        engine = EnhancedRestoreEngine(self.add_log, self.update_progress)
        info = engine.get_backup_info(self.restore_source_path.get())
        if info:
            self.info_lbl.configure(text=f"📂 Origem: MÁQUINA: {info.get('Maquina de Origem', '?')} | USUÁRIO: {info.get('Usuario de Origem', '?')} | {info.get('Data/Hora do Backup', '?')}")
            self.info_lbl.configure(fg=COLORS['success'])
        else:
            self.info_lbl.configure(text="⚠️ Cuidado: O arquivo 'info_restauracao.txt' não foi encontrado. Apenas a estrutura será restaurada.", fg='orange')

    def run_restore(self):
        if not self.is_admin_validated:
            messagebox.showwarning("Admin", "Requer privilégios.")
            return
        if not self.restore_source_path.get() or not self.restore_target_user.get():
            messagebox.showwarning("Campos", "Selecione o backup e o usuário destino.")
            return

        self.btn_restore.configure(state=tk.DISABLED, text="PROCESSANDO...")
        self.btn_cancel_restore.configure(state=tk.NORMAL)
        
        def _thread_run():
            self.restore_engine = EnhancedRestoreEngine(self.add_log, self.update_progress)
            success = self.restore_engine.start_restore(self.restore_source_path.get(), self.restore_target_user.get())
            self.root.after(0, lambda: self._on_finish_restore(success))

        import threading
        self.animate_gif()
        threading.Thread(target=_thread_run, daemon=True).start()
        
    def _on_finish_restore(self, success):
        self.btn_restore.configure(state=tk.NORMAL, text="INICIAR RESTAURAÇÃO")
        self.btn_cancel_restore.configure(state=tk.DISABLED)
        if self.gif_job:
            self.root.after_cancel(self.gif_job)
            self.gif_job = None
        if success:
            self.progress_bar['value'] = 100
            self.status_lbl.configure(text="Restauração concluída!")
            messagebox.showinfo("Restauração", "Processo concluído com sucesso!")
        elif hasattr(self, 'restore_engine') and self.restore_engine and self.restore_engine.is_cancelled:
            self.status_lbl.configure(text="Restauração cancelada.")
            messagebox.showinfo("Restauração", "A restauração foi cancelada pelo usuário.")
        else: messagebox.showerror("Restauração", "O processo terminou com erros. Verifique o terminal.")

    def cancel_operation(self):
        if hasattr(self, 'engine') and self.engine:
            self.engine.is_cancelled = True
        if hasattr(self, 'restore_engine') and self.restore_engine:
            self.restore_engine.is_cancelled = True
        self.add_log("Cancelamento solicitado pelo usuário...", "WARNING")
        if hasattr(self, 'btn_cancel'):
            self.btn_cancel.configure(state=tk.DISABLED)
        if hasattr(self, 'btn_cancel_restore'):
            self.btn_cancel_restore.configure(state=tk.DISABLED)

    def load_users(self):
        users = []
        try:
            cmd = [
            'powershell',
            '-Command',
            "Get-CimInstance Win32_UserProfile | Select-Object -ExpandProperty LocalPath"
        ]
        output = subprocess.check_output(cmd, text=True, creationflags=subprocess.CREATE_NO_WINDOW)

        for line in output.split('\n'):
            if "C:\\Users\\" in line:
                username = line.strip().split("\\")[-1]
                if username:
                    users.append(username)

        exclude = ['Administrator', 'Public', 'Default', 'Default User', 'All Users']
        users = [u for u in users if u not in exclude]

    except Exception:
        users = [p.name for p in Path('C:/Users').iterdir() if p.is_dir()]

    self.user_combo['values'] = users
    if hasattr(self, 'res_user_combo'):
        self.res_user_combo['values'] = users

    if users:
        self.user_combo.current(0)
        if hasattr(self, 'res_user_combo'):
            self.res_user_combo.current(0)
        self.on_user_switch()

    def on_user_switch(self, event=None):
        user = self.selected_user.get()
        for widget in self.tasks_container.winfo_children(): widget.destroy()
        self.task_vars = {}
        self.module_labels = {}

        user_home = Path(f'C:/Users/{user}')
        std_mapping = {
            'Desktop': user_home / 'Desktop',
            'Documentos': user_home / 'Documents',
            'Downloads': user_home / 'Downloads',
            'Imagens': user_home / 'Pictures',
            'Videos': user_home / 'Videos'
        }

        def start_size_calc(key, path, label_widget):
            def _task():
                size, _ = self.engine.get_size_info([path])
                formatted = self.engine.format_size(size)
                self.root.after(0, lambda: label_widget.config(text=formatted))
                self.root.after(0, self.update_total_estimate)
            threading.Thread(target=_task, daemon=True).start()

        # Configurações dos Módulos Padrão com Ícones
        module_config = [
            ('Desktop', '🖥️ Desktop'),
            ('Documentos', '📂 Documentos'),
            ('Downloads', '📥 Downloads'),
            ('Imagens', '🖼️ Imagens'),
            ('Videos', '🎬 Vídeos')
        ]

        for internal_name, display_name in module_config:
            frame = tk.Frame(self.tasks_container, bg='white')
            frame.pack(fill=tk.X, pady=1)
            
            # Todos desmarcados por padrão (value=False)
            var = tk.BooleanVar(value=False)
            cb = tk.Checkbutton(frame, text=display_name, variable=var, bg='white', activebackground='white', 
                              fg=COLORS['text_dark'], font=('Segoe UI', 9), command=self.update_total_estimate)
            cb.pack(side=tk.LEFT)
            self.task_vars[internal_name] = var
            
            size_lbl = tk.Label(frame, text="calculando...", bg='white', fg=COLORS['text_muted'], font=('Segoe UI', 8))
            size_lbl.pack(side=tk.RIGHT)
            self.module_labels[internal_name] = size_lbl
            
            if internal_name in std_mapping:
                start_size_calc(internal_name, std_mapping[internal_name], size_lbl)
        
        tk.Frame(self.tasks_container, bg='#f1f5f9', height=1).pack(fill=tk.X, pady=10)

        profiles = self.engine.get_browser_profiles(user)
        for p in profiles:
            frame = tk.Frame(self.tasks_container, bg='white')
            frame.pack(fill=tk.X, pady=1)
            
            # Navegadores também desmarcados por padrão
            var = tk.BooleanVar(value=False)
            key = f"Browser:|{p.browser_type}|{p.folder_name}"
            display_text = f"🌐 {p.name}"
            cb = tk.Checkbutton(frame, text=display_text, variable=var, bg='white', activebackground='white', 
                              fg='#0891b2', font=('Segoe UI', 8), command=self.update_total_estimate)
            cb.pack(side=tk.LEFT)
            self.task_vars[key] = var
            
            size_lbl = tk.Label(frame, text="calculando...", bg='white', fg=COLORS['text_muted'], font=('Segoe UI', 8))
            size_lbl.pack(side=tk.RIGHT)
            self.module_labels[key] = size_lbl
            
            if p.browser_type == "Firefox":
                b_path = user_home / 'AppData/Roaming/Mozilla/Firefox/Profiles' / p.folder_name
            else:
                base = "Google/Chrome" if p.browser_type=="Chrome" else "Microsoft/Edge"
                b_path = user_home / 'AppData/Local' / base / 'User Data' / p.folder_name
            start_size_calc(key, b_path, size_lbl)

    def update_total_estimate(self):
        total_bytes = 0
        for key, var in self.task_vars.items():
            if var.get():
                lbl_text = self.module_labels[key].cget("text")
                if "calculando" not in lbl_text and " B" in lbl_text or "KB" in lbl_text or "MB" in lbl_text or "GB" in lbl_text:
                    # Parse approximate back to bytes for estimation
                    val = float(lbl_text.split()[0])
                    unit = lbl_text.split()[1]
                    mult = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}.get(unit, 1)
                    total_bytes += val * mult
        
        self.est_label.configure(text=f"Total estimado: {self.engine.format_size(total_bytes)}")

    def add_log(self, msg, level="INFO"):
        def _log():
            prefix = f"[{datetime.now().strftime('%H:%M:%S')}] "
            self.log_widget.insert(tk.END, f"{prefix}{msg}\n")
            self.log_widget.see(tk.END)
        self.root.after(0, _log)

    def update_progress(self, current, total, filename):
        perc = int((current/total)*100) if total > 0 else 0
        if perc > 100: perc = 100
        if not hasattr(self, '_last_perc'): self._last_perc = -1
        if not hasattr(self, '_last_update'): self._last_update = 0
        
        import time
        now = time.time()
        # Atualiza a GUI apenas se a porcentagem mudou ou se passou 0.1s
        if perc != self._last_perc or (now - self._last_update) > 0.1:
            self._last_perc = perc
            self._last_update = now
            def _progress(c=current, t=total, f=filename, p=perc):
                self.progress_bar['value'] = p
                self.status_lbl.configure(text=f"Processando: {f[:30]}...")
            self.root.after(0, _progress)

    def browse_dest(self):
        path = filedialog.askdirectory()
        if path: self.dest_path.set(path)

    def animate_gif(self):
        if not self.loading_frames: return
        self.gif_frame_idx = (self.gif_frame_idx + 1) % len(self.loading_frames)
        self.lbl_gif.configure(image=self.loading_frames[self.gif_frame_idx])
        self.gif_job = self.root.after(100, self.animate_gif)

    def run_backup(self):
        if not self.is_admin_validated:
            messagebox.showwarning("Admin", "Valide as credenciais administrativa primeiro.")
            return
        
        if not self.dest_path.get():
            messagebox.showwarning("Destino", "Selecione a pasta de destino.")
            return

        selected = [k for k, v in self.task_vars.items() if v.get()]
        if not selected:
            messagebox.showwarning("Módulos", "Selecione ao menos um módulo.")
            return

        self.btn_start.configure(state=tk.DISABLED, text="PROCESSANDO...")
        self.btn_cancel.configure(state=tk.NORMAL)
        self.animate_gif()
        
        def _thread_run():
            try:
                success = self.engine.start_backup(
                    self.selected_user.get(),
                    selected,
                    self.dest_path.get(),
                    self.use_zip.get()
                )
                self.root.after(0, lambda: self._on_finish(success))
            except Exception as e:
                self.root.after(0, lambda e=e: self.add_log(f"Exception na Thread de Backup: {e}", "ERROR"))
                self.root.after(0, lambda: self._on_finish(False))

        threading.Thread(target=_thread_run, daemon=True).start()

    def _on_finish(self, success):
        self.btn_start.configure(state=tk.NORMAL, text="INICIAR BACKUP")
        self.btn_cancel.configure(state=tk.DISABLED)
        if self.gif_job:
            self.root.after_cancel(self.gif_job)
            self.gif_job = None
        
        if success:
            self.progress_bar['value'] = 100
            self.status_lbl.configure(text="Backup concluído!")
            messagebox.showinfo("Backup", "Processo concluído com sucesso!")
        elif self.engine and self.engine.is_cancelled:
            self.status_lbl.configure(text="Backup cancelado.")
            messagebox.showinfo("Backup", "O backup foi cancelado pelo usuário.")
        else:
            messagebox.showerror("Backup", "O processo terminou com erros. Verifique o terminal.")

if __name__ == "__main__":
    try:
        if os.name != 'nt': sys.exit()
        
        try: is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
        except: is_admin = False

        if not is_admin:
            res = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
            if res > 32: sys.exit()
            else: sys.exit()

        root = tk.Tk()
        # Remove os estilos padrão do sistema para um look flat
        try: root.tk.call('tk_setPalette', COLORS['bg'])
        except: pass
        
        app = ProfessionalBackupGUI(root)
        root.mainloop()
        
    except Exception as e:
        import traceback
        with open("CRITICAL_ERROR.txt", "w") as f: f.write(traceback.format_exc())
