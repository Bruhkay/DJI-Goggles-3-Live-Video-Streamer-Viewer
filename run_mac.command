#!/bin/bash
# Goggles 3 Live - macOS calistir
cd "$(dirname "$0")" || exit 1
if [ ! -x .venv/bin/python ]; then
  bash ./setup_mac.command || exit 1
fi
echo
echo "USB arayuzunu acmak icin macOS yonetici izni gerekiyor; Mac sifreni gir."
sudo .venv/bin/python -m g3 "$@"
echo
read -r -p "Kapatmak icin Enter'a bas..."
