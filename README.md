# Narra — Audiolivros com vozes de IA

Transforma documentos **.doc, .docx e .pdf** em audiolivros narrados por vozes de IA em
**português, inglês e espanhol**. Há duas versões:

| | Versão web (`web/index.html`) | Aplicativo executável |
|---|---|---|
| Instalação | Nenhuma: abra no navegador | Um arquivo executável |
| Vozes | Vozes do navegador/sistema (no Microsoft Edge aparecem vozes neurais de IA, marcadas com ★) | 17 vozes neurais da Microsoft (Francisca, Antônio, Raquel, Aria, Guy, Elvira, Álvaro…) |
| Resultado | Ouve na hora, com texto destacado frase a frase | Gera um **arquivo MP3** do livro inteiro |
| Funciona offline | Depois de carregada, sim (se o sistema tiver vozes locais) | Não, a síntese usa a internet |

## Versão web
Abra `web/index.html` em qualquer navegador moderno (Edge e Chrome recomendados).
Arraste o arquivo, escolha idioma e voz, e aperte play. Recursos:
- leitura de DOCX, DOC (Word 97‑2003), PDF com texto e TXT, tudo dentro do navegador;
- detecção automática do idioma e dos capítulos;
- destaque da frase sendo lida, clique em qualquer frase para pular até ela;
- velocidade e tom ajustáveis; lembra onde você parou em cada livro;
- atalho: barra de espaço para play/pausa.

## Aplicativo executável

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
Em um Mac, também dá para gerar com PyInstaller via `./build.sh`.

### Android (Narra.apk — Android 5.0 ou mais novo)
1. Copie `Narra.apk` para o celular e toque nele. Autorize "instalar apps desconhecidos" quando pedido.
2. A narração usa o motor de voz do Android (Google Text-to-Speech, com vozes neurais).
   Se faltar a voz de um idioma, toque em "Instalar vozes" no app.
3. Abra documentos pelo botão do app ou pelo "Abrir com" do gerenciador de arquivos.
4. "Salvar audiolivro (M4A)" grava o livro inteiro em um arquivo de áudio.
5. A narração continua com a tela apagada ou com o app em segundo plano.

Para recompilar: `android/build-apk.sh` (Ubuntu/Debian; requisitos no início do script).
A chave de assinatura fica em `android/narra-release.jks` (senha padrão `narra123`):
guarde-a, porque atualizações do app precisam ser assinadas com a mesma chave.

### iPhone / iPad
- **PWA (sem instalar nada):** publique a pasta `pwa/dist` numa hospedagem HTTPS (GitHub Pages,
  Netlify, Vercel), abra no Safari e toque em Compartilhar › Adicionar à Tela de Início.
  Funciona offline e usa as vozes Aprimoradas/Premium do iOS. Para regerar: `python3 pwa/build_pwa.py`.
- **App nativo (`ios/`):** narra com a tela bloqueada e grava M4A. Compile no Mac com Xcode ou pelo
  workflow `.github/workflows/ios.yml` e instale com Sideloadly/AltStore. Veja `ios/LEIA-ME.md`.

### Gerar o executável
- Windows: dê dois cliques em `build.bat` → `dist\Narra-Audiolivro.exe`
- Linux/macOS: `./build.sh` → `dist/Narra-Audiolivro`
- Ou envie o projeto ao GitHub: o workflow `.github/workflows/build.yml` gera os
  executáveis de Windows, macOS e Linux automaticamente (aba *Actions* → *Artifacts*).

Executáveis do PyInstaller só rodam no sistema em que foram gerados: o `.exe` do Windows precisa ser gerado no Windows (ou pelo workflow).

### Linha de comando
```bash
python cli.py livro.pdf                         # detecta idioma e usa a voz padrão
python cli.py book.docx -l en -v en-US-GuyNeural --velocidade 10 -o book.mp3
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
tts.py          vozes neurais, divisão do texto e geração do MP3
cli.py          linha de comando
static/         interface do aplicativo
web/index.html  versão web independente
pwa/            app web instalável (PWA) para iPhone e Android
ios/            app nativo para iPhone/iPad (Swift)
android/        app Android (Java + interface web embutida)
mac/            lançador, Info.plist e ícone do Narra.app
```
