#!/usr/bin/env bash
# Compila o Narra para Android (APK) sem Android Studio/Gradle.
# Requisitos (Ubuntu/Debian): sudo apt install openjdk-17-jdk aapt apksigner zipalign dalvik-exchange android-sdk-platform-23 npm
set -euo pipefail
cd "$(dirname "$0")"
SDK_JAR="${ANDROID_JAR:-/usr/lib/android-sdk/platforms/android-23/android.jar}"
B=build
rm -rf "$B" && mkdir -p "$B"/{gen,classes,assets/www/lib,npm}

# 1) interface web + bibliotecas embutidas (funciona offline)
( cd "$B/npm" && npm pack -s pdfjs-dist@3.11.174 mammoth@1.6.0 >/dev/null && for f in *.tgz; do mkdir -p "${f%.tgz}" && tar xzf "$f" -C "${f%.tgz}"; done )
cp "$B"/npm/pdfjs-dist-3.11.174/package/build/pdf.min.js "$B"/npm/pdfjs-dist-3.11.174/package/build/pdf.worker.min.js "$B/assets/www/lib/"
cp "$B"/npm/mammoth-1.6.0/package/mammoth.browser.min.js "$B/assets/www/lib/"
sed -e 's#https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/#lib/#g' \
    -e 's#https://cdnjs.cloudflare.com/ajax/libs/mammoth/1.6.0/#lib/#g' \
    -e 's#<title>#<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><title>#' \
    ../web/index.html > "$B/assets/www/index.html"
grep -q "cdnjs" "$B/assets/www/index.html" && { echo "ainda há referências ao CDN"; exit 1; }

# 2) recursos -> R.java
aapt package -f -m -J "$B/gen" -M AndroidManifest.xml -S res -I "$SDK_JAR"

# 3) Java -> .class -> classes.dex
javac -nowarn -encoding UTF-8 -source 8 -target 8 -bootclasspath "$SDK_JAR" -d "$B/classes" \
      $(find src "$B/gen" -name '*.java') 2>&1 | grep -v "warning:\|^Note:\|^1 warning\|^[0-9]* warnings" || true
dalvik-exchange --dex --min-sdk-version=21 --output="$B/classes.dex" "$B/classes"

# 4) empacota, alinha e assina
aapt package -f -M AndroidManifest.xml -S res -A "$B/assets" -I "$SDK_JAR" -F "$B/unsigned.apk"
( cd "$B" && aapt add unsigned.apk classes.dex >/dev/null )
zipalign -f -p 4 "$B/unsigned.apk" "$B/aligned.apk"
KS="${NARRA_KEYSTORE:-narra-release.jks}"
if [ ! -f "$KS" ]; then
  keytool -genkeypair -keystore "$KS" -alias narra -keyalg RSA -keysize 2048 -validity 10000 \
    -storepass narra123 -keypass narra123 -dname "CN=Narra Audiolivros, O=Narra, C=BR" >/dev/null 2>&1
fi
apksigner sign --ks "$KS" --ks-key-alias narra --ks-pass pass:${NARRA_KS_PASS:-narra123} \
  --key-pass pass:${NARRA_KS_PASS:-narra123} --out Narra.apk "$B/aligned.apk"
apksigner verify Narra.apk
echo "Pronto: $(pwd)/Narra.apk"
