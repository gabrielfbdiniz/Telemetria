@echo off
title Telemetria Formula ITA - V0
cd /d "%~dp0"

echo ==============================================================================
echo        TELEMETRIA VEICULAR - FORMULA ITA (FORMULA SAE ELECTRIC)
echo ==============================================================================
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERRO] Python nao encontrado no sistema!
    echo Por favor, instale o Python 3.10 ou superior e marque a opcao "Add Python to PATH".
    pause
    exit /b 1
)

echo [1/2] Verificando dependencias essenciais...
python -m pip install -r requirements.txt --quiet --disable-pip-version-check

echo [2/2] Iniciando o Dashboard de Telemetria...
echo.
python main.py

if %errorlevel% neq 0 (
    echo.
    echo [AVISO] A aplicacao encerrou com codigo de erro %errorlevel%.
    pause
)
