# Narra para iPhone/iPad (app nativo)

Recursos: mesma interface da versão web; narração com o motor de voz do iOS (inclui vozes
Aprimoradas/Premium), **continua com a tela bloqueada**, e **"Salvar audiolivro (M4A)"** grava o livro
inteiro e abre a folha de compartilhamento (Salvar em Arquivos, AirDrop…). Também aparece no
"Compartilhar" do app Arquivos para PDF, DOCX, DOC e TXT. Requer iOS 15 ou mais novo.

## Opção A — tenho um Mac
1. Instale o Xcode (App Store) e o XcodeGen: `brew install xcodegen`
2. `./ios/prepare-www.sh` (copia a interface) e `cd ios && xcodegen generate`
3. Abra `ios/Narra.xcodeproj`, em *Signing & Capabilities* escolha seu Apple ID como *Team*
4. Conecte o iPhone e clique em ▶︎ (Run). No iPhone: Ajustes › Geral › VPN e Gerenciamento de
   Dispositivo › confie no seu Apple ID. Com Apple ID gratuito o app vale por 7 dias.

## Opção B — não tenho Mac (Windows)
1. Envie o projeto para um repositório no GitHub. O workflow `.github/workflows/ios.yml` compila
   num Mac da nuvem e gera `Narra-iPhone-sem-assinatura.ipa` (aba *Actions* › *Artifacts*).
2. Instale com o **Sideloadly** (Windows/Mac) ou **AltStore**, que assinam com seu Apple ID gratuito
   (validade de 7 dias; renove reinstalando).

## Sem instalar nada: PWA
Publique `pwa/dist` em uma hospedagem HTTPS, abra no Safari e toque em
Compartilhar › **Adicionar à Tela de Início**. Funciona offline; o iOS não permite gravar o áudio
nem narrar com a tela bloqueada nesse modo.
