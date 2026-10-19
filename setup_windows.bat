@echo off
REM Goggles 3 Live - Windows kurulum (bir kere calistir)
cd /d "%~dp0"
echo == Goggles 3 Live: Windows kurulumu ==

set PY=
where py >nul 2>nul && set PY=py -3
if not defined PY python -c "import sys" >nul 2>nul && set PY=python
if not defined PY (
  echo Python bulunamadi, winget ile kuruluyor...
  winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
  if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set PY="%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
)
if not defined PY (
  echo Python kurulamadi. python.org adresinden Python 3 kurup bu dosyayi tekrar calistir.
  pause
  exit /b 1
)

echo ffmpeg kuruluyor - zaten kuruluysa atlanir...
winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements

%PY% -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip -q
.venv\Scripts\python.exe -m pip install -r requirements.txt -q
if errorlevel 1 (
  echo Python paketleri kurulamadi.
  pause
  exit /b 1
)

echo.
echo Simdi tek seferlik USB surucusu adimi. Gozlugu USB-C ile bagla ve ac.
call "%~dp0install_driver_windows.bat"
echo.
echo Kurulum tamam. Bundan sonra sadece run_windows.bat dosyasina cift tikla.
pause
