#!/usr/bin/env bash
# Copia a interface (versão web com bibliotecas embutidas) para dentro do app iOS.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 pwa/build_pwa.py
rm -rf ios/Narra/www && mkdir -p ios/Narra/www
cp pwa/dist/index.html ios/Narra/www/ && cp -r pwa/dist/lib ios/Narra/www/
echo "Interface copiada para ios/Narra/www"
