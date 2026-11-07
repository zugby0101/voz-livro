"""Testa o executável do Narra: python tests/test_exe.py <executavel> <abrir|ler|doc|mp3|kokoro>

Abre o app sem navegador, faz as verificações e encerra. Em caso de falha imprime uma
anotação ::error (visível na API do GitHub) e sai com código 1.
"""
import io
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

import socket

with socket.socket() as _s:  # porta livre só para este teste
    _s.bind(("127.0.0.1", 0))
    PORT = _s.getsockname()[1]
URL = f"http://127.0.0.1:{PORT}"


def req(path, data=None, headers=None, method=None, timeout=60):
    r = urllib.request.Request(URL + path, data=data, headers=headers or {}, method=method)
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return resp.status, resp.read()


def upload(name, content):
    boundary = uuid.uuid4().hex
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{name}\"\r\n"
            f"Content-Type: application/octet-stream\r\n\r\n").encode() + content + f"\r\n--{boundary}--\r\n".encode()
    try:
        return req("/api/extract", body, {"Content-Type": f"multipart/form-data; boundary={boundary}"})
    except urllib.error.HTTPError as e:
        return e.code, e.read()


TEXTO = "Era uma vez uma menina que morava perto do rio. Ela não tinha medo da água e todos os dias ia nadar."


def make_docx():
    import docx
    d = docx.Document()
    d.add_heading("Capítulo 1", 1)
    d.add_paragraph(TEXTO)
    b = io.BytesIO()
    d.save(b)
    return b.getvalue()


def make_pdf():
    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", size=12)
    pdf.multi_cell(0, 8, "Capítulo 1\n\n" + TEXTO)
    return bytes(pdf.output())


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)


def run(what):
    if what == "abrir":
        _, html = req("/")
        check(b"<title>Narra" in html, "página inicial sem o título do Narra")
        _, v = req("/api/voices")
        check(b"pt-BR-FranciscaNeural" in v, "lista de vozes incompleta")
    elif what == "ler":
        for name, content in (("teste.docx", make_docx()), ("teste.pdf", make_pdf())):
            code, body = upload(name, content)
            check(code == 200, f"{name}: HTTP {code} {body[:200]!r}")
            d = json.loads(body)
            print(f"{name}: idioma={d['language']} palavras={d['words']}")
            check(d["language"] == "pt", f"{name}: idioma detectado {d['language']}")
            check("menina que morava" in d["text"], f"{name}: texto não encontrado")
    elif what == "doc":
        # sem LibreOffice/antiword o app deve explicar o que fazer, sem travar
        fake_doc = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 4096
        code, body = upload("teste.doc", fake_doc)
        print(f".doc sem LibreOffice: HTTP {code} {body[:200].decode('utf-8', 'replace')}")
        check(code == 422, f"esperado 422, veio {code}")
        check("LibreOffice" in body.decode("utf-8", "replace"), "mensagem não orienta a instalar o LibreOffice")
        _, v = req("/api/voices")  # o app continua respondendo
    elif what in ("mp3", "kokoro"):
        voice = "pf_dora" if what == "kokoro" else "pt-BR-FranciscaNeural"
        payload = json.dumps({"text": "Olá! Este é um teste do Narra, o seu audiolivro com vozes de "
                                      "inteligência artificial. Era uma vez uma menina que morava perto do rio.",
                              "voice": voice, "title": f"teste-{what}"}).encode()
        _, body = req("/api/convert", payload, {"Content-Type": "application/json"})
        job = json.loads(body)["job"]
        msgs = set()
        for _ in range(450):  # inclui o download do modelo Kokoro na primeira vez
            _, s = req(f"/api/jobs/{job}")
            s = json.loads(s)
            if s.get("message") and s["message"].split(":")[0] not in msgs:
                msgs.add(s["message"].split(":")[0])
                print("  ", s["message"])
            if s["status"] == "done":
                break
            check(s["status"] != "error", f"erro na síntese: {s.get('error')}")
            time.sleep(2)
        check(s["status"] == "done", "a geração do MP3 não terminou a tempo")
        _, mp3 = req(f"/api/jobs/{job}/audio?download=true")
        from mutagen.mp3 import MP3
        dur = MP3(io.BytesIO(mp3)).info.length
        print(f"MP3 ({voice}): {len(mp3)} bytes, {dur:.1f} s, arquivo salvo como {s['name']}")
        check(dur > 2, f"áudio curto demais ({dur:.1f}s)")
    else:
        raise SystemExit(f"teste desconhecido: {what}")


def main():
    exe, what = sys.argv[1], sys.argv[2]
    proc = subprocess.Popen([exe, "--no-browser", "--port", str(PORT)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(90):  # o .exe de arquivo único se descompacta na primeira execução
            try:
                req("/api/voices", timeout=3)
                break
            except Exception:
                if proc.poll() is not None:
                    break
                time.sleep(2)
        else:
            raise AssertionError("o app não respondeu em 3 minutos")
        check(proc.poll() is None, f"o app fechou sozinho (código {proc.returncode})")
        run(what)
        print(f"OK: {what}")
    except Exception as e:
        msg = f"{type(e).__name__}: {e}".replace("\n", " ")
        print(f"::error title=Narra {what}::{msg}")
        sys.exit(1)
    finally:
        try:
            req("/api/quit", b"", method="POST", timeout=5)
        except Exception:
            pass
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    main()
