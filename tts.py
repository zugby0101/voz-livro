"""Conversão de texto em áudio com vozes neurais (Microsoft Edge TTS)."""
from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Callable

import edge_tts

# Vozes neurais selecionadas por idioma
VOICES: dict[str, list[dict]] = {
    "pt": [
        {"id": "pt-BR-FranciscaNeural", "name": "Francisca", "gender": "F", "locale": "pt-BR"},
        {"id": "pt-BR-AntonioNeural", "name": "Antônio", "gender": "M", "locale": "pt-BR"},
        {"id": "pt-BR-ThalitaMultilingualNeural", "name": "Thalita", "gender": "F", "locale": "pt-BR"},
        {"id": "pt-PT-RaquelNeural", "name": "Raquel", "gender": "F", "locale": "pt-PT"},
        {"id": "pt-PT-DuarteNeural", "name": "Duarte", "gender": "M", "locale": "pt-PT"},
    ],
    "en": [
        {"id": "en-US-AriaNeural", "name": "Aria", "gender": "F", "locale": "en-US"},
        {"id": "en-US-GuyNeural", "name": "Guy", "gender": "M", "locale": "en-US"},
        {"id": "en-US-JennyNeural", "name": "Jenny", "gender": "F", "locale": "en-US"},
        {"id": "en-US-AndrewNeural", "name": "Andrew", "gender": "M", "locale": "en-US"},
        {"id": "en-US-EmmaNeural", "name": "Emma", "gender": "F", "locale": "en-US"},
        {"id": "en-GB-SoniaNeural", "name": "Sonia", "gender": "F", "locale": "en-GB"},
        {"id": "en-GB-RyanNeural", "name": "Ryan", "gender": "M", "locale": "en-GB"},
    ],
    "es": [
        {"id": "es-ES-ElviraNeural", "name": "Elvira", "gender": "F", "locale": "es-ES"},
        {"id": "es-ES-AlvaroNeural", "name": "Álvaro", "gender": "M", "locale": "es-ES"},
        {"id": "es-MX-DaliaNeural", "name": "Dalia", "gender": "F", "locale": "es-MX"},
        {"id": "es-MX-JorgeNeural", "name": "Jorge", "gender": "M", "locale": "es-MX"},
        {"id": "es-AR-ElenaNeural", "name": "Elena", "gender": "F", "locale": "es-AR"},
    ],
}
DEFAULT_VOICE = {lang: v[0]["id"] for lang, v in VOICES.items()}

MAX_CHUNK = 2500  # caracteres por requisição


def split_text(text: str, max_len: int = MAX_CHUNK) -> list[str]:
    """Divide o texto em blocos respeitando parágrafos e frases."""
    chunks, cur = [], ""
    for para in re.split(r"\n\s*\n", text):
        para = " ".join(para.split())
        if not para:
            continue
        pieces = [para] if len(para) <= max_len else _split_sentences(para, max_len)
        for piece in pieces:
            if len(cur) + len(piece) + 2 <= max_len:
                cur = f"{cur}\n\n{piece}" if cur else piece
            else:
                if cur:
                    chunks.append(cur)
                cur = piece
    if cur:
        chunks.append(cur)
    return chunks


def _split_sentences(para: str, max_len: int) -> list[str]:
    sentences = re.split(r"(?<=[.!?…;])\s+", para)
    out, cur = [], ""
    for s in sentences:
        while len(s) > max_len:  # frase gigante: corta em espaço
            cut = s.rfind(" ", 0, max_len) or max_len
            out.append(s[:cut])
            s = s[cut:].strip()
        if len(cur) + len(s) + 1 <= max_len:
            cur = f"{cur} {s}" if cur else s
        else:
            if cur:
                out.append(cur)
            cur = s
    if cur:
        out.append(cur)
    return out


def _pct(v: int) -> str:
    return f"{'+' if v >= 0 else ''}{int(v)}%"


async def _synth_chunk(text: str, voice: str, rate: int, volume: int, pitch: int,
                       retries: int = 4) -> bytes:
    last = None
    for attempt in range(retries):
        try:
            com = edge_tts.Communicate(text, voice, rate=_pct(rate), volume=_pct(volume),
                                       pitch=f"{'+' if pitch >= 0 else ''}{int(pitch)}Hz")
            buf = bytearray()
            async for msg in com.stream():
                if msg["type"] == "audio":
                    buf.extend(msg["data"])
            if buf:
                return bytes(buf)
            last = RuntimeError("resposta de áudio vazia")
        except Exception as e:  # rede instável: tenta novamente
            last = e
        await asyncio.sleep(1.5 * (attempt + 1))
    if "connect" in str(last).lower() or "resolve" in str(last).lower():
        raise RuntimeError("Sem conexão com o serviço de voz. Verifique sua internet e tente de novo.")
    raise RuntimeError(f"Falha ao sintetizar trecho: {last}")


async def synthesize(text: str, out_path: str | Path, voice: str, rate: int = 0,
                     volume: int = 0, pitch: int = 0, concurrency: int = 4,
                     progress: Callable[[int, int], None] | None = None,
                     synth=None) -> Path:
    """Gera um MP3 único a partir do texto. `progress(feitos, total)` é chamado a cada bloco."""
    synth = synth or _synth_chunk
    chunks = split_text(text)
    if not chunks:
        raise ValueError("Texto vazio.")
    total, done = len(chunks), 0
    results: list[bytes | None] = [None] * total
    sem = asyncio.Semaphore(concurrency)

    async def work(i: int, chunk: str):
        nonlocal done
        async with sem:
            results[i] = await synth(chunk, voice, rate, volume, pitch)
        done += 1
        if progress:
            progress(done, total)

    if progress:
        progress(0, total)
    await asyncio.gather(*(work(i, c) for i, c in enumerate(chunks)))
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:  # MP3 de mesmo formato pode ser concatenado quadro a quadro
        for r in results:
            f.write(r)
    return out_path


def estimate_minutes(text: str, rate: int = 0) -> float:
    words = len(text.split())
    return words / (150 * (1 + rate / 100))
