@echo off
chcp 65001 >nul
title Сборка автономного EXE-файла ИС «КнигоГрад»
cd /d "%~dp0"

if not exist ".venv" (
    python -m venv .venv
)
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt

echo Сборка единого исполняемого файла KnigoGrad.exe...
pyinstaller --noconfirm --onefile --windowed --name "KnigoGrad" ^
  --add-data "frontend;frontend" ^
  --paths "backend" ^
  backend\app\main.py

echo.
echo Готово! Автономный файл для запуска на компьютере преподавателя находится в папке:
echo %~dp0dist\KnigoGrad.exe
pause
