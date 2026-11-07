"""Linha de comando: python cli.py livro.pdf -l pt -v pt-BR-AntonioNeural -o livro.mp3"""
import argparse
import asyncio
import sys
from pathlib import Path

from extractor import detect_language, extract_text
from tts import DEFAULT_VOICE, VOICES, estimate_minutes, synthesize


def main():
    p = argparse.ArgumentParser(description="Converte .doc/.docx/.pdf em audiolivro MP3.")
    p.add_argument("arquivo", nargs="?")
    p.add_argument("-o", "--saida")
    p.add_argument("-l", "--idioma", choices=["pt", "en", "es"], help="padrão: detecção automática")
    p.add_argument("-v", "--voz")
    p.add_argument("--velocidade", type=int, default=0, help="-50 a +100 (%%)")
    p.add_argument("--tom", type=int, default=0, help="-50 a +50 (Hz)")
    p.add_argument("--listar-vozes", action="store_true")
    a = p.parse_args()

    if a.listar_vozes:
        for lang, vs in VOICES.items():
            print(f"[{lang}]")
            for v in vs:
                print(f"  {v['id']:36} {v['name']} ({v['gender']}, {v['locale']})")
        return
    if not a.arquivo:
        p.error("informe o arquivo")

    text = extract_text(a.arquivo)
    lang = a.idioma or detect_language(text)
    voice = a.voz or DEFAULT_VOICE[lang]
    out = a.saida or str(Path(a.arquivo).with_suffix(".mp3"))
    print(f"Idioma: {lang} | Voz: {voice} | {len(text.split())} palavras "
          f"(~{estimate_minutes(text, a.velocidade):.0f} min de áudio)")

    def prog(d, t):
        bar = "#" * int(30 * d / t)
        sys.stdout.write(f"\r[{bar:<30}] {d}/{t}")
        sys.stdout.flush()

    asyncio.run(synthesize(text, out, voice, rate=a.velocidade, pitch=a.tom, progress=prog))
    print(f"\nPronto: {out}")


if __name__ == "__main__":
    main()
