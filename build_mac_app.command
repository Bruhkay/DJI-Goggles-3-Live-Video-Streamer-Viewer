#!/bin/bash
# SkyFeed Studio - Mac uygulamasi (.app) ve kurulum dosyasi (.dmg) uretir.
# Cift tikla; bitince dist klasoru acilir.
cd "$(dirname "$0")" || exit 1

fail() { echo; echo "HATA: $1"; echo "Bu pencerenin ciktisini Claude'a at."; read -r -p "Kapatmak icin Enter'a bas..."; exit 1; }

echo "== SkyFeed Studio: uygulama derleniyor =="
export HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_NO_INSTALLED_DEPENDENTS_CHECK=1
export HOMEBREW_NO_INSTALL_UPGRADE=1 HOMEBREW_NO_INSTALL_CLEANUP=1

BREW=""
for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do [ -x "$b" ] && BREW="$b"; done
if [ -n "$BREW" ]; then
  eval "$("$BREW" shellenv)"
  PREFIX="$(brew --prefix)"
  brew list --formula libusb >/dev/null 2>&1 || brew install libusb || true
fi

# PySide6 en sorunsuz 3.12 / 3.13 ile calisir
PY=""
for v in 3.12 3.13 3.11 3.14; do
  for d in "$PREFIX/bin" /Library/Frameworks/Python.framework/Versions/$v/bin /usr/local/bin; do
    [ -x "$d/python$v" ] && { PY="$d/python$v"; break 2; }
  done
done
if [ -z "$PY" ] && [ -n "$BREW" ]; then
  brew install python@3.12 || true
  [ -x "$PREFIX/bin/python3.12" ] && PY="$PREFIX/bin/python3.12"
fi
[ -n "$PY" ] || fail "Python 3.11-3.14 bulunamadi. Once setup_mac.command calistir."
echo "Python: $PY"

rm -rf .build-venv
"$PY" -m venv .build-venv || fail "Sanal ortam olusturulamadi."
.build-venv/bin/python -m pip install --upgrade pip -q || true
echo "Paketler indiriliyor (PySide6 ve OpenCV buyuk, birkac dakika surebilir)..."
.build-venv/bin/python -m pip install -q -r requirements-app.txt pyinstaller pillow || fail "Paketler kurulamadi."

rm -rf build dist
.build-venv/bin/pyinstaller --noconfirm --clean --log-level WARN goggles3live.spec || fail "PyInstaller derlemesi basarisiz."

APP="dist/SkyFeed Studio.app"
[ -d "$APP" ] || fail "Uygulama olusmadi."
"$APP/Contents/MacOS/SkyFeedStudio" --helper --selftest || fail "Uygulama ici test basarisiz (libusb yuklenemedi)."

VER="$(.build-venv/bin/python -c 'import g3; print(g3.__version__)')"
DMG="dist/SkyFeed-Studio-$VER.dmg"
mkdir -p dist/dmg
cp -R "$APP" dist/dmg/
ln -s /Applications dist/dmg/Applications
hdiutil create -volname "SkyFeed Studio" -srcfolder dist/dmg -ov -format UDZO "$DMG" >/dev/null || fail "DMG olusturulamadi."
rm -rf dist/dmg

echo
echo "Hazir: $DMG"
echo "DMG'yi ac, SkyFeed Studio'yu Applications klasorune surukle."
open dist
read -r -p "Kapatmak icin Enter'a bas..."
