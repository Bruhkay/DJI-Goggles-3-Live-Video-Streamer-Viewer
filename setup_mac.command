#!/bin/bash
# Goggles 3 Live - macOS kurulum (bir kere calistir)
cd "$(dirname "$0")" || exit 1

fail() { echo; echo "HATA: $1"; echo "Bu pencerenin ciktisini Claude'a at."; read -r -p "Kapatmak icin Enter'a bas..."; exit 1; }

echo "== Goggles 3 Live: macOS kurulumu =="

# Kurulu paketlere dokunma: guncelleme yok, bagimli paketleri (opencv vb.) yeniden kurma yok
export HOMEBREW_NO_AUTO_UPDATE=1
export HOMEBREW_NO_INSTALLED_DEPENDENTS_CHECK=1
export HOMEBREW_NO_INSTALL_UPGRADE=1
export HOMEBREW_NO_INSTALL_CLEANUP=1

BREW=""
for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do [ -x "$b" ] && BREW="$b"; done
if [ -z "$BREW" ]; then
  echo "Homebrew bulunamadi, kuruluyor (sifren istenebilir)..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do [ -x "$b" ] && BREW="$b"; done
fi
[ -n "$BREW" ] || fail "Homebrew kurulamadi."
eval "$("$BREW" shellenv)"
PREFIX="$(brew --prefix)"

# Sadece eksik olani kur. Baska paketlerden gelen link uyarilari bizi durdurmasin.
for f in libusb ffmpeg; do
  if brew list --formula "$f" >/dev/null 2>&1; then
    echo "$f zaten kurulu, atlaniyor."
  else
    echo "$f kuruluyor..."
    brew install "$f" || echo "(uyari: brew $f kurulumunda hata bildirdi, devam ediliyor)"
  fi
done

# ffplay (canli pencere) yeni Homebrew'da ffmpeg-full icinde olabilir
find_ffplay() {
  for p in "$PREFIX/bin/ffplay" "$PREFIX/opt/ffmpeg/bin/ffplay" "$PREFIX/opt/ffmpeg-full/bin/ffplay"; do
    [ -x "$p" ] && { echo "$p"; return 0; }
  done
  command -v ffplay
}
if [ -z "$(find_ffplay)" ]; then
  echo "ffplay bulunamadi, ffmpeg-full kuruluyor..."
  brew install ffmpeg-full || echo "(uyari: ffmpeg-full kurulumunda hata bildirildi, kontrol ediliyor)"
fi
[ -n "$(find_ffplay)" ] || fail "ffplay bulunamadi (ffmpeg kurulumu eksik)."
echo "ffplay: $(find_ffplay)"

[ -f "$PREFIX/lib/libusb-1.0.dylib" ] || [ -f "$PREFIX/opt/libusb/lib/libusb-1.0.dylib" ] || fail "libusb bulunamadi."

# Python: kurulu olani kullan, yoksa kur
PY=""
for v in 3.12 3.13 3.14 3.11; do
  [ -x "$PREFIX/bin/python$v" ] && { PY="$PREFIX/bin/python$v"; break; }
done
if [ -z "$PY" ]; then
  brew install python@3.12 || true
  [ -x "$PREFIX/bin/python3.12" ] && PY="$PREFIX/bin/python3.12"
fi
[ -z "$PY" ] && [ -x /usr/bin/python3 ] && PY=/usr/bin/python3
[ -n "$PY" ] || fail "Python bulunamadi."
echo "Python: $PY"

rm -rf .venv
"$PY" -m venv .venv || fail "Python sanal ortami olusturulamadi."
.venv/bin/python -m pip install --upgrade pip -q || true
.venv/bin/python -m pip install -r requirements.txt -q || fail "Python paketleri kurulamadi."

chmod +x run_mac.command
echo
echo "Kurulum tamam."
