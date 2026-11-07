# Narra — Audiolivros com vozes de IA

Transforma documentos **.doc, .docx e .pdf** em audiolivros narrados por vozes de IA em
**português, inglês e espanhol**. Há duas versões:

| | Versão web (`web/index.html`) | Aplicativo para PC (Windows, macOS, Linux) |
|---|---|---|
| Instalação | Nenhuma: abra no navegador | Um arquivo executável |
| Vozes | Vozes do navegador/sistema | **Kokoro** (IA que roda no seu computador) + vozes neurais da Microsoft (online) |
| Resultado | Ouve na hora, com texto destacado frase a frase | Gera um **arquivo MP3** do livro inteiro |
| Funciona offline | Depois de carregada, se o sistema tiver vozes locais | **Sim, com as vozes Kokoro** |

## Versão web
Abra `web/index.html` em qualquer navegador moderno (Edge e Chrome recomendados).
Arraste o arquivo, escolha idioma e voz, e aperte play. Recursos:
- leitura de DOCX, DOC (Word 97‑2003), PDF com texto e TXT, tudo dentro do navegador;
- detecção automática do idioma e dos capítulos;
- destaque da frase sendo lida, clique em qualquer frase para pular até ela;
- velocidade e tom ajustáveis; lembra onde você parou em cada livro;
- atalho: barra de espaço para play/pausa.

## Aplicativo executável

### Vozes Kokoro (padrão)
O [Kokoro](https://huggingface.co/hexgrad/Kokoro-82M) é um modelo de voz de IA aberto (licença
Apache 2.0) que roda no próprio computador, sem internet e sem custo. Vozes disponíveis:

- **Português (Brasil):** Dora (feminina), Alex e Santa (masculinas)
- **Inglês:** Heart, Bella, Nicole, Michael, Fenrir (EUA); Emma, George (Reino Unido)
- **Espanhol:** Dora (feminina), Alex e Santa (masculinas)

Na primeira vez, o app baixa o modelo de voz (~350 MB, uma única vez) para a pasta de dados
do usuário (Windows: `%LOCALAPPDATA%\Narra\modelos`; macOS: `~/Library/Application Support/Narra/modelos`;
Linux: `~/.local/share/narra/modelos`). Depois disso tudo funciona offline.
No macOS, o Kokoro exige macOS 14+ (Apple Silicon) ou 13+ (Intel); em versões mais antigas o app
usa as vozes Microsoft.

As vozes da Microsoft (Francisca, Antônio, Aria, Elvira…) continuam disponíveis como opção online.

### Usar sem empacotar (precisa de Python 3.9+)
- Windows: dê dois cliques em `iniciar.bat`
- Linux/macOS: `./iniciar.sh`

O navegador abre sozinho em `http://127.0.0.1:8765`. Os MP3 ficam na pasta `~/Audiolivros`.

### macOS (Narra.app — Apple Silicon e Intel, macOS 11+)
1. Extraia `Narra-macOS.zip` e arraste o `Narra.app` para Aplicativos.
2. Como o app não é assinado pela Apple, na primeira vez rode no Terminal:
   `xattr -cr /Applications/Narra.app`
   (ou Ajustes do Sistema → Privacidade e Segurança → "Abrir Mesmo Assim").
3. Para fechar, use o botão **Encerrar** na página. Erros ficam em `~/Library/Logs/Narra.log`.

Para remontar o app (funciona em Linux ou Mac): `./build-mac-from-linux.sh`.
O download pronto fica na página de Releases do GitHub (`Narra-macOS.zip`).
Em um Mac, também dá para gerar com PyInstaller via `./build.sh`.

### Gerar o executável
- Windows: dê dois cliques em `build.bat` → `dist\Narra-Audiolivro.exe`
- Linux/macOS: `./build.sh` → `dist/Narra-Audiolivro`
- Ou envie o projeto ao GitHub: o workflow `.github/workflows/build.yml` gera os
  executáveis de Windows, macOS e Linux automaticamente (aba *Actions* → *Artifacts*).

Executáveis do PyInstaller só rodam no sistema em que foram gerados: o `.exe` do Windows precisa ser gerado no Windows (ou pelo workflow).

### Linha de comando
```bash
python cli.py livro.pdf                         # detecta idioma e usa a voz Kokoro padrão
python cli.py book.docx -l en -v am_michael --velocidade 10 -o book.mp3
python cli.py --listar-vozes
```

## Observações
- Arquivos `.doc` antigos: no Mac o app usa o `textutil` do sistema; no Windows/Linux usa antiword, catdoc ou LibreOffice se estiverem instalados.
  A versão web lê `.doc` direto, mas se o resultado sair incompleto salve o arquivo como `.docx`.
- PDFs digitalizados (só imagem) precisam de OCR antes.
- Cabeçalhos, rodapés e números de página repetidos do PDF são removidos automaticamente.

## Estrutura
```
app.py          servidor local (FastAPI)
desktop.py      inicia o servidor e abre o navegador (ponto de entrada do executável)
extractor.py    extração de texto DOC/DOCX/PDF e detecção de idioma
tts.py          vozes, divisão do texto e geração do MP3
kokoro_engine.py  vozes Kokoro (IA local): download do modelo, síntese e MP3
tests/          testes do executável e do app de Mac (rodam no GitHub Actions)
cli.py          linha de comando
static/         interface do aplicativo
web/index.html  versão web independente
mac/            lançador, Info.plist e ícone do Narra.app
```
