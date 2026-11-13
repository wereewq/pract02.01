@echo off
chcp 65001 >nul
title ИС «КнигоГрад: Система учёта продаж и поставок»
cd /d "%~dp0"

if exist "dist\KnigoGrad_Setup.exe" (
    echo Запуск автономного исполняемого файла KnigoGrad_Setup.exe...
    start "" "dist\KnigoGrad_Setup.exe"
    exit /b
)

echo Проверка виртуального окружения Python...
if not exist ".venv" (
    python -m venv .venv
)
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt
echo Запуск ИС «КнигоГрад»...
python backend\app\main.py
pause
