@echo off
REM Goggles 3 Live - Windows calistir
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe call setup_windows.bat
.venv\Scripts\python.exe -m g3 %*
pause
