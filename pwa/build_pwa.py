"""Gera a versão PWA (app instalável no iPhone/Android pelo navegador) em pwa/dist/.

Uso: python3 pwa/build_pwa.py   (requer npm e Pillow)
Depois publique a pasta dist/ em qualquer hospedagem HTTPS (GitHub Pages, Netlify, Vercel...).
"""
import hashlib
import math
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
WEB = ROOT.parent / "web" / "index.html"
DIST = ROOT / "dist"
LIBS = {"pdfjs-dist@3.11.174": ["build/pdf.min.js", "build/pdf.worker.min.js"],
        "mammoth@1.6.0": ["mammoth.browser.min.js"]}


def icon(size, maskable=False):
    big = size * 4
    im = Image.new("RGBA", (big, big), (26, 35, 51, 255) if maskable else (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    k = big / 1024
    if not maskable:
        d.rounded_rectangle((0, 0, big, big), radius=0, fill=(26, 35, 51, 255))
    s = 0.78 if maskable else 1.0  # área segura do ícone "maskable"
    c = 512 * k
    r = 300 * k * s
    d.ellipse((c - r, c - r, c + r, c + r), outline=(238, 241, 244, 255), width=int(36 * k * s))
    r2 = 62 * k * s
    d.ellipse((c - r2, c - r2, c + r2, c + r2), fill=(238, 241, 244, 255))
    for ang in (90, 210, 330):
        x = c + 170 * k * s * math.cos(math.radians(ang))
        y = c - 170 * k * s * math.sin(math.radians(ang))
        d.ellipse((x - r2, y - r2, x + r2, y + r2), fill=(224, 164, 60, 255))
    return im.resize((size, size), Image.LANCZOS).convert("RGB")


def main():
    shutil.rmtree(DIST, ignore_errors=True)
    (DIST / "lib").mkdir(parents=True)
    (DIST / "icons").mkdir()

    with tempfile.TemporaryDirectory() as tmp:
        for pkg, files in LIBS.items():
            out = subprocess.run(["npm", "pack", "-s", pkg], cwd=tmp, capture_output=True, text=True,
                                 check=True).stdout.strip().splitlines()[-1]
            with tarfile.open(Path(tmp) / out) as t:
                for f in files:
                    data = t.extractfile("package/" + f).read()
                    (DIST / "lib" / Path(f).name).write_bytes(data)

    for size in (180, 192, 512):
        icon(size).save(DIST / "icons" / f"icon-{size}.png")
    icon(512, maskable=True).save(DIST / "icons" / "maskable-512.png")

    html = WEB.read_text(encoding="utf-8")
    html = html.replace("https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/", "lib/")
    html = html.replace("https://cdnjs.cloudflare.com/ajax/libs/mammoth/1.6.0/", "lib/")
    assert "cdnjs" not in html
    head = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#1a2333">
<meta name="description" content="Transforme DOC, DOCX e PDF em audiolivro com vozes de IA em português, inglês e espanhol.">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Narra">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<link rel="manifest" href="manifest.webmanifest">
<link rel="apple-touch-icon" href="icons/icon-180.png">
<link rel="icon" type="image/png" sizes="192x192" href="icons/icon-192.png">
<style>:root{padding-top:env(safe-area-inset-top,0px)}body{margin:0;-webkit-text-size-adjust:100%}</style>
"""
    html = head + html.replace('<meta name="claude:viewport-fit-sides" content="cover">\n', "")
    assert html.count('<div class="wrap">') == 1
    html = html.replace('<div class="wrap">', '</head>\n<body>\n<div class="wrap">')
    html += """
<script>
if ("serviceWorker" in navigator) {
  addEventListener("load", () => navigator.serviceWorker.register("sw.js").catch(() => {}));
}
</script>
</body>
</html>
"""
    (DIST / "index.html").write_text(html, encoding="utf-8")

    (DIST / "manifest.webmanifest").write_text("""{
  "name": "Narra Audiolivros",
  "short_name": "Narra",
  "description": "Transforme DOC, DOCX e PDF em audiolivro com vozes de IA em português, inglês e espanhol.",
  "lang": "pt-BR",
  "start_url": "./",
  "scope": "./",
  "display": "standalone",
  "orientation": "any",
  "background_color": "#eef1f4",
  "theme_color": "#1a2333",
  "icons": [
    {"src": "icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
    {"src": "icons/icon-512.png", "sizes": "512x512", "type": "image/png"},
    {"src": "icons/maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}
  ]
}
""", encoding="utf-8")

    files = sorted(str(p.relative_to(DIST)) for p in DIST.rglob("*")
                   if p.is_file() and not p.name.startswith("."))
    version = hashlib.sha256(b"".join((DIST / f).read_bytes() for f in files)).hexdigest()[:10]
    precache = ",\n  ".join(f'"./{f}"' for f in files)
    (DIST / "sw.js").write_text(f"""// Service worker do Narra: guarda o app no aparelho para funcionar offline.
const CACHE = "narra-{version}";
const FILES = [
  "./",
  {precache}
];
self.addEventListener("install", e => {{
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(FILES)).then(() => self.skipWaiting()));
}});
self.addEventListener("activate", e => {{
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
}});
self.addEventListener("fetch", e => {{
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin === location.origin) {{
    // app: cache primeiro, rede como reserva
    e.respondWith(caches.match(req, {{ignoreSearch: true}}).then(r => r || fetch(req)));
  }} else if (url.hostname.endsWith("fonts.googleapis.com") || url.hostname.endsWith("fonts.gstatic.com")) {{
    // fontes: usa a rede e guarda uma cópia para uso offline
    e.respondWith(caches.open(CACHE).then(c => c.match(req).then(hit => hit || fetch(req).then(res => {{
      c.put(req, res.clone()); return res;
    }}))));
  }}
}});
""", encoding="utf-8")
    (DIST / ".nojekyll").write_text("")
    print(f"PWA gerado em {DIST} (versão {version}, {len(files) + 1} arquivos)")


if __name__ == "__main__":
    main()
