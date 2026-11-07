#!/usr/bin/env bash
# Teste do Narra.app num Mac: tests/test_mac_app.sh <caminho/Narra.app> <abrir|ler|mp3|kokoro> [x86_64]
set -euo pipefail
APP="$1"; WHAT="$2"; ARCH="${3:-}"
URL=http://127.0.0.1:8765
LAUNCH=("$APP/Contents/MacOS/Narra" --no-browser)
[ "$ARCH" = "x86_64" ] && LAUNCH=(arch -x86_64 /bin/bash "$APP/Contents/MacOS/Narra" --no-browser)
WORK=$(mktemp -d)

cleanup() { curl -s -X POST $URL/api/quit >/dev/null 2>&1 || true; sleep 1; }
fail() {
  # anotação visível na API do GitHub (o log completo exige login)
  msg=$(tail -c 900 ~/Library/Logs/Narra.log 2>/dev/null | tr '\n' ' ' | tr -d '\r')
  echo "::error title=Narra ${WHAT} ${ARCH:-arm64} (linha $1)::${msg:-sem log}"
}
trap 'fail $LINENO' ERR
trap cleanup EXIT
rm -f ~/Library/Logs/Narra.log
"${LAUNCH[@]}" &
for i in $(seq 1 45); do curl -sf $URL/api/voices >/dev/null && break; sleep 2; done
curl -sf $URL/api/voices >/dev/null || { echo "app não abriu"; tail -50 ~/Library/Logs/Narra.log || true; false; }
if [ -n "$ARCH" ]; then
  pid=$(pgrep -f "py-x86_64/bin/python3" | head -1) || { echo "::error title=Intel::Python Intel não está rodando"; exit 1; }
  echo "Python Intel rodando (pid $pid)"
fi

case "$WHAT" in
abrir)
  page=$(curl -sf $URL/); voices=$(curl -sf $URL/api/voices)
  grep -q "<title>Narra" <<<"$page"
  grep -q "pt-BR-FranciscaNeural" <<<"$voices"
  grep -q '"pf_dora"' <<<"$voices"
  ;;
ler)
  printf 'Capítulo 1\n\nEra uma vez uma menina que morava perto do rio. Ela não tinha medo da água e todos os dias ia nadar com seus amigos.\n' > "$WORK/teste.txt"
  textutil -convert docx "$WORK/teste.txt" -output "$WORK/teste.docx"
  textutil -convert doc  "$WORK/teste.txt" -output "$WORK/teste.doc"
  cupsfilter "$WORK/teste.txt" > "$WORK/teste.pdf" 2>/dev/null
  for f in docx doc pdf; do
    r=$(curl -sf -F file=@"$WORK/teste.$f" $URL/api/extract)
    echo "$f: ${r:0:120}"
    grep -q '"language":"pt"' <<<"$r"
    grep -q 'menina que morava' <<<"$r"
  done
  ;;
mp3|kokoro)
  VOICE=pt-BR-FranciscaNeural; [ "$WHAT" = kokoro ] && VOICE=pf_dora
  job=$(curl -sf -H 'Content-Type: application/json' \
    -d '{"text":"Olá! Este é um teste do Narra, o seu audiolivro com vozes de inteligência artificial.","voice":"'"$VOICE"'","title":"teste-mac"}' \
    $URL/api/convert | python3 -c "import json,sys;print(json.load(sys.stdin)['job'])")
  for i in $(seq 1 450); do
    st=$(curl -sf $URL/api/jobs/$job | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['status'],d.get('error') or '')")
    case "$st" in done*) break;; error*) echo "erro: $st"; exit 1;; esac
    sleep 2
  done
  curl -sf -o "$WORK/teste.mp3" "$URL/api/jobs/$job/audio"
  afinfo "$WORK/teste.mp3" | tee "$WORK/info.txt"
  dur=$(awk '/estimated duration/ {print $3}' "$WORK/info.txt")
  python3 -c "import sys; d=float('$dur'); print('$VOICE duração:', d, 's'); sys.exit(0 if d > 2 else 1)"
  ;;
esac
echo "OK: $WHAT ${ARCH:-arm64}"
