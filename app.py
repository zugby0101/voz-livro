"""Servidor local do Audiolivro IA (FastAPI)."""
from __future__ import annotations

import asyncio
import re
import sys
import tempfile
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from extractor import SUPPORTED, ExtractionError, detect_language, extract_text
import kokoro_engine
from tts import DEFAULT_VOICE, VOICES, engine_of, estimate_minutes, synthesize

BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
OUTPUT_DIR = Path.home() / "Audiolivros"
OUTPUT_DIR.mkdir(exist_ok=True)

app = FastAPI(title="Audiolivro IA")
JOBS: dict[str, dict] = {}


@app.get("/", response_class=HTMLResponse)
def index():
    return (BASE / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/api/voices")
def voices():
    ok, why = kokoro_engine.availability()
    return {"voices": VOICES, "default": DEFAULT_VOICE,
            "kokoro": dict(kokoro_engine.download_state(), available=ok, reason=why)}


@app.get("/api/kokoro")
def kokoro_state():
    ok, why = kokoro_engine.availability()
    return dict(kokoro_engine.download_state(), available=ok, reason=why)


@app.post("/api/kokoro/download")
async def kokoro_download():
    ok, why = kokoro_engine.availability()
    if not ok:
        raise HTTPException(400, why)
    if not kokoro_engine.is_installed() and not kokoro_engine.download_state()["downloading"]:
        async def run():
            try:
                await asyncio.to_thread(kokoro_engine.ensure_model)
            except Exception:
                pass  # o erro fica em download_state()["error"]
        asyncio.get_running_loop().create_task(run())
    return kokoro_engine.download_state()


@app.post("/api/extract")
async def extract(file: UploadFile = File(...)):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in SUPPORTED:
        raise HTTPException(400, f"Formato não suportado ({ext}). Use .doc, .docx ou .pdf.")
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / f"entrada{ext}"
        p.write_bytes(await file.read())
        try:
            text = await asyncio.to_thread(extract_text, p)
        except ExtractionError as e:
            raise HTTPException(422, str(e))
        except Exception as e:
            raise HTTPException(422, f"Não foi possível ler o arquivo: {e}")
    return {
        "text": text,
        "language": detect_language(text),
        "words": len(text.split()),
        "minutes": round(estimate_minutes(text), 1),
        "title": Path(file.filename).stem,
    }


class ConvertRequest(BaseModel):
    text: str
    voice: str
    title: str = "audiolivro"
    rate: int = 0
    pitch: int = 0
    volume: int = 0


@app.post("/api/convert")
async def convert(req: ConvertRequest):
    if not req.text.strip():
        raise HTTPException(400, "Texto vazio.")
    job_id = uuid.uuid4().hex[:12]
    safe = re.sub(r"[^\w\-. ]+", "", req.title).strip() or "audiolivro"
    out = OUTPUT_DIR / f"{safe} - {time.strftime('%Y%m%d-%H%M%S')}.mp3"
    job = JOBS[job_id] = {"status": "running", "done": 0, "total": 0, "file": str(out),
                          "name": out.name, "error": None, "message": ""}

    def prog(d, t):
        job["done"], job["total"] = d, t

    def status(msg):
        job["message"] = msg

    async def run():
        try:
            await synthesize(req.text, out, req.voice, rate=req.rate, pitch=req.pitch,
                             volume=req.volume, progress=prog, status=status)
            job["status"] = "done"
        except Exception as e:
            job["status"], job["error"] = "error", str(e)

    job["task"] = asyncio.create_task(run())
    return {"job": job_id}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Tarefa não encontrada")
    return {k: v for k, v in job.items() if k != "task"}


@app.get("/api/jobs/{job_id}/audio")
def job_audio(job_id: str, download: bool = False):
    job = JOBS.get(job_id)
    if not job or job["status"] != "done":
        raise HTTPException(404, "Áudio indisponível")
    return FileResponse(job["file"], media_type="audio/mpeg",
                        filename=job["name"] if download else None)


@app.post("/api/quit")
async def quit_app():
    """Encerra o aplicativo (usado pelo botão "Encerrar")."""
    import os
    import threading
    threading.Timer(0.5, lambda: os._exit(0)).start()
    return {"ok": True}


@app.post("/api/preview")
async def preview(voice: str = Form(...), text: str = Form(...), rate: int = Form(0),
                  pitch: int = Form(0)):
    if engine_of(voice) == "kokoro" and not kokoro_engine.is_installed():
        raise HTTPException(409, "Baixe o modelo Kokoro primeiro (botão \"Baixar vozes Kokoro\").")
    out = Path(tempfile.gettempdir()) / f"preview-{uuid.uuid4().hex[:8]}.mp3"
    try:
        await synthesize(text[:300], out, voice, rate=rate, pitch=pitch)
    except Exception as e:
        raise HTTPException(502, str(e))
    return FileResponse(out, media_type="audio/mpeg")
