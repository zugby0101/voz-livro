"""Extração de texto de arquivos .doc, .docx e .pdf."""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

SUPPORTED = {".doc", ".docx", ".pdf", ".txt"}


class ExtractionError(Exception):
    pass


def extract_text(path: str | Path) -> str:
    path = Path(path)
    ext = path.suffix.lower()
    if ext == ".docx":
        text = _docx(path)
    elif ext == ".pdf":
        text = _pdf(path)
    elif ext == ".doc":
        text = _doc(path)
    elif ext == ".txt":
        text = path.read_text(encoding="utf-8", errors="replace")
    else:
        raise ExtractionError(f"Formato não suportado: {ext}. Use .doc, .docx ou .pdf.")
    text = clean_text(text)
    if not text.strip():
        raise ExtractionError(
            "Nenhum texto encontrado. Se o PDF for digitalizado (imagem), é preciso OCR antes."
        )
    return text


def _docx(path: Path) -> str:
    try:
        import docx
    except ImportError as e:
        raise ExtractionError("Instale python-docx: pip install python-docx") from e
    from docx.oxml.ns import qn

    document = docx.Document(str(path))
    parts: list[str] = []
    # Percorre o corpo na ordem original (parágrafos e tabelas intercalados)
    for block in document.element.body.iterchildren():
        if block.tag == qn("w:p"):
            t = "".join(n.text or "" for n in block.iter(qn("w:t"))).strip()
            if t:
                parts.append(t)
        elif block.tag == qn("w:tbl"):
            for row in block.iter(qn("w:tr")):
                cells = []
                for cell in row.iter(qn("w:tc")):
                    ct = " ".join(
                        "".join(n.text or "" for n in p.iter(qn("w:t")))
                        for p in cell.iter(qn("w:p"))
                    ).strip()
                    if ct:
                        cells.append(ct)
                if cells:
                    parts.append(". ".join(cells) + ".")
    return "\n\n".join(parts)


def _pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise ExtractionError("Instale pypdf: pip install pypdf") from e
    reader = PdfReader(str(path))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as e:
            raise ExtractionError("PDF protegido por senha.") from e
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    pages = _strip_headers_footers(pages)
    return "\n\n".join(_reflow(p) for p in pages)


def _strip_headers_footers(pages: list[str]) -> list[str]:
    """Remove linhas repetidas no topo/rodapé (cabeçalhos) e números de página."""
    if len(pages) < 3:
        return [_drop_page_numbers(p) for p in pages]
    from collections import Counter

    first, last = Counter(), Counter()
    for p in pages:
        lines = [l.strip() for l in p.splitlines() if l.strip()]
        if lines:
            first[_norm(lines[0])] += 1
            last[_norm(lines[-1])] += 1
    threshold = max(3, len(pages) // 2)
    rep_first = {k for k, v in first.items() if v >= threshold and k}
    rep_last = {k for k, v in last.items() if v >= threshold and k}
    out = []
    for p in pages:
        lines = [l for l in p.splitlines() if l.strip()]
        if lines and _norm(lines[0].strip()) in rep_first:
            lines = lines[1:]
        if lines and _norm(lines[-1].strip()) in rep_last:
            lines = lines[:-1]
        out.append(_drop_page_numbers("\n".join(lines)))
    return out


def _norm(s: str) -> str:
    return re.sub(r"\d+", "#", s.lower())


def _drop_page_numbers(p: str) -> str:
    return re.sub(r"(?m)^\s*(p[áa]gina\s+|page\s+)?\d{1,4}(\s*(/|de|of)\s*\d{1,4})?\s*$", "", p,
                  flags=re.IGNORECASE)


_CHAPTER = re.compile(
    r"^(cap[ií]tulo|chapter|parte|part|libro|livro|book|pr[óo]logo|prologue|ep[íi]logo|epilogue)\b",
    re.IGNORECASE)


def _reflow(text: str) -> str:
    """Junta linhas quebradas do PDF em parágrafos contínuos."""
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)  # hifenização no fim da linha
    lines = [l.rstrip() for l in text.splitlines()]
    paras, cur = [], []
    for line in lines:
        if not line.strip():
            if cur:
                paras.append(" ".join(cur))
                cur = []
            continue
        if len(line) < 80 and _CHAPTER.match(line.strip()):
            if cur:
                paras.append(" ".join(cur))
                cur = []
            paras.append(line.strip())
            continue
        cur.append(line.strip())
        # Linha curta terminando em pontuação final -> provável fim de parágrafo
        if re.search(r"[.!?:»\"”]$", line) and len(line) < 60:
            paras.append(" ".join(cur))
            cur = []
    if cur:
        paras.append(" ".join(cur))
    return "\n\n".join(paras)


def _doc(path: Path) -> str:
    """Arquivos .doc (Word 97-2003): tenta antiword, catdoc e por fim LibreOffice."""
    textutil = shutil.which("textutil")  # já vem instalado no macOS
    if textutil:
        r = subprocess.run([textutil, "-convert", "txt", "-stdout", str(path)],
                           capture_output=True, timeout=120)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.decode("utf-8", errors="replace")
    for tool, args in (("antiword", ["-w", "0"]), ("catdoc", ["-w"])):
        exe = shutil.which(tool)
        if exe:
            r = subprocess.run([exe, *args, str(path)], capture_output=True, timeout=120)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.decode("utf-8", errors="replace")
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice:
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run(
                [soffice, "--headless", "--convert-to", "docx", "--outdir", tmp, str(path)],
                capture_output=True, timeout=300,
            )
            out = Path(tmp) / (path.stem + ".docx")
            if out.exists():
                return _docx(out)
    raise ExtractionError(
        "Para ler arquivos .doc instale o LibreOffice, antiword ou catdoc "
        "(ex.: sudo apt install antiword)."
    )


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x0c", "\n\n")
    text = re.sub(r"[­​﻿]", "", text)  # hífen suave, zero-width
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ---------------------------------------------------------------- idioma
_STOP = {
    "pt": "de a o que e do da em um para é com não uma os no se na por mais as dos como mas foi ao ele das tem à seu sua ou ser quando muito há nos já está eu também só pelo pela até isso ela entre era depois sem mesmo aos ter seus quem nas me esse eles estão você tinha foram essa num nem suas meu às minha têm numa pelos elas havia seja qual será nós tenho lhe deles essas esses pelas este fosse dele tu te vocês vos lhes meus minhas teu tua nosso nossa então ainda são".split(),
    "es": "de la que el en y a los se del las un por con no una su para es al lo como más pero sus le ya o este sí porque esta entre cuando muy sin sobre también me hasta hay donde quien desde todo nos durante todos uno les ni contra otros ese eso ante ellos e esto mí antes algunos qué unos yo otro otras otra él tanto esa estos mucho quienes nada muchos cual poco ella estar estas algunas algo nosotros mi mis tú te ti tu tus ellas era fue son está había".split(),
    "en": "the of and to in a is that for it as was with be by on not he i this are or his from at which but have an they you were her she there been one all we their has would when if so no will more out up into do any your what can who them some could him than then its only other my about our these over very".split(),
}
_ACCENT_HINTS = {"pt": "ãõçâêô", "es": "ñ¿¡"}


def detect_language(text: str) -> str:
    """Detecta pt, en ou es por frequência de palavras comuns."""
    sample = text[:20000].lower()
    words = re.findall(r"[a-zà-ÿ]+", sample)
    if not words:
        return "pt"
    scores = {}
    for lang, stops in _STOP.items():
        s = set(stops)
        scores[lang] = sum(1 for w in words if w in s) / len(words)
    for lang, chars in _ACCENT_HINTS.items():
        scores[lang] += sum(sample.count(c) for c in chars) / max(len(words), 1) * 2
    return max(scores, key=scores.get)
