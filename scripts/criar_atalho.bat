@echo off
REM Cria um atalho "Organizador de Arquivos" na Area de Trabalho com icone.
REM Basta dar duplo clique neste arquivo.

title Criar atalho - Organizador de Arquivos

set "SCRIPT_DIR=%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%create_shortcut.ps1"

echo.
pause
