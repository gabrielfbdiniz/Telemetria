@echo off
title Telemetria Formula ITA - Pit Station
cd /d "%~dp0"

echo [FORMULA ITA] Iniciando Software de Telemetria de Pista...
python main.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERRO] Ocorreu uma falha ao executar o software de pista.
    echo Verifique se as dependencias foram instaladas via: pip install -r requirements.txt
    pause
)
