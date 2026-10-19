@echo off
REM SkyFeed Studio - Windows uygulamasi derler (dist\SkyFeedStudio klasoru + zip)
cd /d "%~dp0"
set PY=
where py >nul 2>nul && set PY=py -3
if not defined PY python -c "import sys" >nul 2>nul && set PY=python
if not defined PY (
  echo Python bulunamadi. Once setup_windows.bat calistir.
  pause
  exit /b 1
)
if exist .build-venv rmdir /s /q .build-venv
%PY% -m venv .build-venv
.build-venv\Scripts\python.exe -m pip install --upgrade pip -q
.build-venv\Scripts\python.exe -m pip install -q -r requirements-app.txt pyinstaller pillow
if errorlevel 1 (
  echo Paketler kurulamadi.
  pause
  exit /b 1
)
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
.build-venv\Scripts\pyinstaller.exe --noconfirm --clean --log-level WARN goggles3live.spec
if errorlevel 1 (
  echo Derleme basarisiz.
  pause
  exit /b 1
)
dist\SkyFeedStudio\SkyFeedStudio.exe --helper --selftest
powershell -NoProfile -Command "Compress-Archive -Force -Path dist\SkyFeedStudio -DestinationPath dist\SkyFeedStudio-windows.zip"
echo.
echo Hazir: dist\SkyFeedStudio\SkyFeedStudio.exe  (ve dist\SkyFeedStudio-windows.zip)
echo Not: gozluk icin tek seferlik Zadig surucu adimi gerekir (install_driver_windows.bat).
start "" dist
pause
