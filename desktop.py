"""Inicia o Audiolivro IA como aplicativo local e abre o navegador."""
import socket
import sys
import threading
import time
import webbrowser

import uvicorn

import kokoro_engine
from app import OUTPUT_DIR, app


def free_port(start=8765):
    for port in range(start, start + 50):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("Nenhuma porta livre")


def main():
    port = None
    if "--port" in sys.argv:
        port = int(sys.argv[sys.argv.index("--port") + 1])
    port = port or free_port()
    url = f"http://127.0.0.1:{port}"
    print("=" * 52)
    print("  Audiolivro IA")
    print(f"  Abrindo {url}")
    print(f"  Áudios salvos em: {OUTPUT_DIR}")
    print(f"  Modelo de voz Kokoro em: {kokoro_engine.model_dir()}")
    print("  Feche esta janela para encerrar.")
    print("=" * 52)
    if "--no-browser" not in sys.argv:
        threading.Thread(target=lambda: (time.sleep(1.2), webbrowser.open(url)), daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
