@echo off
REM Iniciador do Organizador de Arquivos.
REM Instala dependencias no primeiro uso e abre a GUI sem janela de console.

title Organizador de Arquivos

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

REM Verifica se customtkinter esta disponivel; se nao, instala requirements.txt
python -c "import customtkinter" >nul 2>&1
if errorlevel 1 (
    echo Instalando dependencias pela primeira vez...
    python -m pip install --user --quiet -r requirements.txt
    if errorlevel 1 (
        echo.
        echo Nao foi possivel instalar as dependencias.
        echo Instale manualmente: pip install -r requirements.txt
        pause
        exit /b 1
    )
)

REM Usa pythonw para abrir a GUI sem console preto junto
where pythonw >nul 2>&1
if errorlevel 1 (
    python run.py
) else (
    start "" pythonw run.py
)

if errorlevel 1 (
    echo.
    echo Erro ao iniciar. Verifique se o Python 3.8+ esta instalado.
    echo Baixe em: https://www.python.org/downloads/
    pause
)
