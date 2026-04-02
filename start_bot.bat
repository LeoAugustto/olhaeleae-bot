@echo off
cd /d "%~dp0"
:loop
".venv\Scripts\python.exe" bot.py
if %errorlevel% neq 0 (
  echo Bot caiu. Reiniciando em 5 segundos...
  timeout /t 5 /nobreak >nul
  goto loop
)