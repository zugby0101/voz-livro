"""Vozes Kokoro: modelo de voz de IA aberto (Kokoro-82M) que roda no próprio computador.

O modelo (~350 MB) é baixado uma única vez e guardado na pasta de dados do usuário.
Depois disso a narração funciona sem internet.
"""
from __future__ import annotations

import os
import ssl
import sys
import threading
import urllib.request
from pathlib import Path
from typing import Callable

SAMPLE_RATE = 24000
_BASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
MODEL_FILES = [
    ("kokoro-v1.0.onnx", 325_532_387),
    ("voices-v1.0.bin", 28_214_398),
]
TOTAL_BYTES = sum(size for _, size in MODEL_FILES)

# id, nome, gênero, idioma exibido
VOICES = {
    "pt": [("pf_dora", "Dora", "F", "pt-BR"), ("pm_alex", "Alex", "M", "pt-BR"),
           ("pm_santa", "Santa", "M", "pt-BR")],
    "en": [("af_heart", "Heart", "F", "en-US"), ("af_bella", "Bella", "F", "en-US"),
           ("af_nicole", "Nicole", "F", "en-US"), ("am_michael", "Michael", "M", "en-US"),
           ("am_fenrir", "Fenrir", "M", "en-US"), ("bf_emma", "Emma", "F", "en-GB"),
           ("bm_george", "George", "M", "en-GB")],
    "es": [("ef_dora", "Dora", "F", "es-ES"), ("em_alex", "Alex", "M", "es-ES"),
           ("em_santa", "Santa", "M", "es-ES")],
}
VOICE_IDS = {v[0] for vs in VOICES.values() for v in vs}
_LANG_BY_PREFIX = {"a": "en-us", "b": "en-gb", "e": "es", "p": "pt-br"}


def model_dir() -> Path:
    if os.environ.get("NARRA_MODEL_DIR"):
        return Path(os.environ["NARRA_MODEL_DIR"])
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        return base / "Narra" / "modelos"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Narra" / "modelos"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "narra" / "modelos"


def availability() -> tuple[bool, str]:
    """O motor ONNX precisa de macOS 13 (Intel) / 14 (Apple Silicon) ou mais novo."""
    try:
        import kokoro_onnx  # noqa: F401
        import lameenc  # noqa: F401
        import onnxruntime  # noqa: F401
    except Exception as e:  # pragma: no cover - depende da plataforma
        return False, f"Kokoro indisponível neste computador ({e.__class__.__name__}: {e})"
    return True, ""


def is_installed() -> bool:
    d = model_dir()
    return all((d / name).exists() and (d / name).stat().st_size == size for name, size in MODEL_FILES)


class _Download:
    lock = threading.Lock()
    running = False
    done = 0
    error: str | None = None


def download_state() -> dict:
    return {"installed": is_installed(), "downloading": _Download.running,
            "done": _Download.done, "total": TOTAL_BYTES, "error": _Download.error,
            "size_mb": round(TOTAL_BYTES / 1e6), "folder": str(model_dir())}


def _ssl_context():
    if os.environ.get("SSL_CERT_FILE"):  # redes corporativas com certificado próprio
        return ssl.create_default_context(cafile=os.environ["SSL_CERT_FILE"])
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def ensure_model(progress: Callable[[int, int], None] | None = None) -> Path:
    """Baixa o modelo se ainda não estiver no computador. Seguro para várias threads."""
    d = model_dir()
    if is_installed():
        return d
    with _Download.lock:
        if is_installed():
            return d
        _Download.running, _Download.done, _Download.error = True, 0, None
        try:
            d.mkdir(parents=True, exist_ok=True)
            ctx = _ssl_context()
            before = 0
            for name, size in MODEL_FILES:
                target = d / name
                if target.exists() and target.stat().st_size == size:
                    before += size
                    _Download.done = before
                    continue
                part = target.with_suffix(target.suffix + ".part")
                req = urllib.request.Request(_BASE + name, headers={"User-Agent": "Narra-Audiolivros"})
                with urllib.request.urlopen(req, context=ctx, timeout=60) as resp, open(part, "wb") as f:
                    got = 0
                    while True:
                        buf = resp.read(1 << 20)
                        if not buf:
                            break
                        f.write(buf)
                        got += len(buf)
                        _Download.done = before + got
                        if progress:
                            progress(_Download.done, TOTAL_BYTES)
                if part.stat().st_size != size:
                    part.unlink(missing_ok=True)
                    raise IOError(f"download incompleto de {name}; tente de novo")
                part.replace(target)
                before += size
            return d
        except Exception as e:
            _Download.error = str(e)
            raise RuntimeError(f"Não foi possível baixar o modelo Kokoro: {e}") from e
        finally:
            _Download.running = False


_engine = None
_engine_lock = threading.Lock()


def _get_engine():
    global _engine
    with _engine_lock:
        if _engine is None:
            from kokoro_onnx import Kokoro
            d = ensure_model()
            _engine = Kokoro(str(d / MODEL_FILES[0][0]), str(d / MODEL_FILES[1][0]))
        return _engine


def synth(text: str, voice: str, speed: float = 1.0):
    """Gera áudio (numpy float32, 24 kHz, mono)."""
    lang = _LANG_BY_PREFIX.get(voice[:1], "en-us")
    speed = min(max(speed, 0.5), 2.0)
    samples, _sr = _get_engine().create(text, voice=voice, speed=speed, lang=lang)
    return samples


class Mp3Writer:
    """Codifica PCM em MP3 aos poucos, sem precisar do ffmpeg."""

    def __init__(self, path, bitrate=64):
        import lameenc
        self._enc = lameenc.Encoder()
        self._enc.set_bit_rate(bitrate)
        self._enc.set_in_sample_rate(SAMPLE_RATE)
        self._enc.set_channels(1)
        self._enc.set_quality(2)
        self._f = open(path, "wb")

    def write(self, samples):
        import numpy as np
        pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2").tobytes()
        self._f.write(self._enc.encode(pcm))

    def silence(self, seconds: float):
        import numpy as np
        self.write(np.zeros(int(SAMPLE_RATE * seconds), dtype="float32"))

    def close(self):
        self._f.write(self._enc.flush())
        self._f.close()
