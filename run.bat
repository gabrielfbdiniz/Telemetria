@echo off
title Telemetria Formula ITA - Pit Station
cd /d "%~dp0"

echo [FORMULA ITA] Iniciando Telemetria de Pista...
python pit_software\main.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERRO] Ocorreu uma falha ao executar o software de pista.
    echo Verifique se as dependencias foram instaladas via: pip install -r pit_software\requirements.txt
    pause
)
