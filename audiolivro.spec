# PyInstaller: pyinstaller audiolivro.spec
from PyInstaller.utils.hooks import collect_all

datas = [("static", "static")]
binaries = []
hiddenimports = ["uvicorn.logging", "uvicorn.loops.auto", "uvicorn.protocols.http.auto",
                 "uvicorn.protocols.websockets.auto", "uvicorn.lifespan.on", "multipart"]
# Kokoro: modelo ONNX, espeak-ng (fonemas) e dados de idiomas
for pkg in ("kokoro_onnx", "espeakng_loader", "phonemizer", "onnxruntime", "lameenc",
            "language_tags", "segments", "csvw"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

a = Analysis(["desktop.py"], datas=datas, binaries=binaries, hiddenimports=hiddenimports)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, name="Narra-Audiolivro", console=True, upx=False)
