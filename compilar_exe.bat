@echo off
cls

echo ============================================================
echo CRIAR EXECUTAVEL DA FERRAMENTA DE BACKUP
echo ============================================================
echo.

python --version >nul 2>&1
if "%ERRORLEVEL%" NEQ "0" (
    echo ERRO: Python nao encontrado ou nao esta no PATH!
    echo Instale Python e marque: Add python.exe to PATH
    pause
    exit /b 1
)

echo Instalando PyInstaller e Pillow...
pip install pyinstaller pillow --quiet
echo.

echo Processando Icone...
if exist logo.png (
    python -c "from PIL import Image; Image.open('logo.png').save('logo.ico')"
)

set CMD=python -m PyInstaller --onefile --windowed --name BackupTool

if exist logo.ico (
    set CMD=%CMD% --icon=logo.ico --add-data "logo.ico;."
) else (
    set CMD=%CMD% --icon=NONE
)

if exist logo.png (
    set CMD=%CMD% --add-data "logo.png;."
)

if exist loading.gif (
    set CMD=%CMD% --add-data "loading.gif;."
)

set CMD=%CMD% backup_tool.py

echo.
echo ============================================================
echo COMPILANDO EXECUTAVEL... (Pode demorar um pouco)
echo ============================================================
echo.

%CMD%

if "%ERRORLEVEL%" NEQ "0" (
    echo.
    echo [ERRO] Falha ao criar o arquivo executavel!
    pause
    exit /b 1
)

echo.
echo ============================================================
echo SUCESSO!
echo ============================================================
echo O seu arquivo BackupTool.exe foi criado na pasta "dist".
echo.
pause
