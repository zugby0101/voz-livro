#!/usr/bin/env bash
# Gera o executável para Linux/macOS em dist/
set -e
cd "$(dirname "$0")"
python3 -m pip install -r requirements.txt pyinstaller
python3 -m PyInstaller --noconfirm --clean audiolivro.spec
echo "Pronto: dist/Narra-Audiolivro"
