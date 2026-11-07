#!/usr/bin/env bash
# Monta Narra.app (macOS 11+, Apple Silicon e Intel) a partir de Linux ou Mac,
# sem precisar de um Mac: usa o Python portátil python-build-standalone + wheels de macOS.
set -euo pipefail
cd "$(dirname "$0")"
OUT="${1:-dist-mac}"
PBS=https://github.com/astral-sh/python-build-standalone/releases/download/20241206
VER=3.12.8+20241206
APP="$OUT/Narra.app/Contents"; R="$APP/Resources"
rm -rf "$OUT" && mkdir -p "$APP/MacOS" "$R/app"
# O motor do Kokoro (onnxruntime) exige macOS 14 no Apple Silicon e 13 no Intel.
for pair in "aarch64 macosx_14_0_arm64" "x86_64 macosx_13_0_x86_64"; do
  set -- $pair
  mkdir -p "$R/py-$1"
  curl -fsSL "$PBS/cpython-$VER-$1-apple-darwin-install_only_stripped.tar.gz" | tar xz -C "$R/py-$1" --strip-components=1
  python3 -m pip install -q --target "$R/site-$1" --platform "$2" --platform macosx_10_9_universal2 \
    --platform macosx_10_9_x86_64 --platform macosx_11_0_universal2 --only-binary=:all: \
    --python-version 3.12 --implementation cp -r requirements.txt
  rm -rf "$R/py-$1"/lib/python3.12/{tkinter,idlelib,turtledemo,ensurepip,test,lib2to3} \
         "$R/py-$1"/lib/python3.12/site-packages/pip* "$R/py-$1"/lib/{tcl*,tk*,itcl*,thread*} "$R/site-$1/bin"
  find "$R/py-$1" "$R/site-$1" -name __pycache__ -prune -exec rm -rf {} +
done
cp app.py desktop.py extractor.py tts.py cli.py kokoro_engine.py "$R/app/" && cp -r static "$R/app/"
cp mac/Narra "$APP/MacOS/Narra" && chmod +x "$APP/MacOS/Narra"
cp mac/Info.plist "$APP/Info.plist" && cp mac/Narra.icns "$R/Narra.icns"
printf 'APPL????' > "$APP/PkgInfo"
cat > "$OUT/LEIA-ME.txt" <<'TXT'
NARRA AUDIOLIVROS PARA macOS (11 Big Sur ou mais novo; Apple Silicon M1/M2/M3/M4 e Intel)

1. Arraste o Narra.app para a pasta Aplicativos.
2. Como o app não tem assinatura da Apple, na primeira vez abra o Terminal e rode:
     xattr -cr /Applications/Narra.app
   (ou: tente abrir, depois vá em Ajustes do Sistema > Privacidade e Segurança > "Abrir Mesmo Assim")
3. Abra o Narra. O navegador abre sozinho com o aplicativo.
4. Para fechar, use o botão "Encerrar" no canto superior direito da página.

Os MP3 são salvos na pasta Audiolivros, dentro da sua pasta de usuário.
É preciso internet para gerar as vozes. Registro de erros: ~/Library/Logs/Narra.log
TXT
(cd "$OUT" && zip -qry Narra-macOS.zip Narra.app LEIA-ME.txt)
echo "Pronto: $OUT/Narra-macOS.zip"
