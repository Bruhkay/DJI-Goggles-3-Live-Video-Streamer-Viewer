@echo off
REM Gozlugun USB ag arayuzune WinUSB surucusu kurar - Zadig ile, tek seferlik
cd /d "%~dp0"
if not exist tools mkdir tools
if exist tools\zadig.exe goto run
echo Zadig indiriliyor...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\get_zadig.ps1"
if exist tools\zadig.exe goto run
echo Zadig otomatik indirilemedi. Tarayicida zadig.akeo.ie aciliyor.
echo Indirdigin exe dosyasini bu klasorde tools\zadig.exe adiyla kaydet, sonra bu dosyayi tekrar calistir.
start "" https://zadig.akeo.ie
pause
exit /b 1

:run
echo.
echo ================= ZADIG ADIMLARI =================
echo  1. Zadig acilinca: Options menusu, "List All Devices" isaretle.
echo  2. Acilir listeden gozlugu sec. USB ID kutusunda 2CA3 0020 yazmali
echo     ve yaninda MI 00 olmali. Adi RNDIS veya DJI olabilir.
echo  3. Yesil okun sagindaki surucu WinUSB olsun, "Replace Driver" bas.
echo  4. Listede 2CA3 0020 MI 01 ayrica gorunuyorsa onu da WinUSB yap.
echo  5. Zadig'i kapat. Bitti.
echo  Geri almak icin: Aygit Yoneticisi, cihaz, Surucuyu kaldir, gozlugu cikar-tak.
echo ==================================================
echo.
start "" /wait tools\zadig.exe
