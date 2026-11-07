# PyInstaller: pyinstaller audiolivro.spec
a = Analysis(
    ["desktop.py"],
    datas=[("static", "static")],
    hiddenimports=["uvicorn.logging", "uvicorn.loops.auto", "uvicorn.protocols.http.auto",
                   "uvicorn.protocols.websockets.auto", "uvicorn.lifespan.on", "multipart"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, name="Narra-Audiolivro", console=True, upx=False)
