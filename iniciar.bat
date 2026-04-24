@echo off
title Organizador de Arquivos
python run.py
if errorlevel 1 (
    echo.
    echo Erro ao iniciar. Verifique se o Python esta instalado.
    echo Instale em: https://www.python.org/downloads/
    pause
)
