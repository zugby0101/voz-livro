@echo off
REM Gera o executavel para Windows em dist\Narra-Audiolivro.exe
cd /d "%~dp0"
py -m pip install -r requirements.txt pyinstaller || python -m pip install -r requirements.txt pyinstaller
py -m PyInstaller --noconfirm --clean audiolivro.spec || python -m PyInstaller --noconfirm --clean audiolivro.spec
echo Pronto: dist\Narra-Audiolivro.exe
pause
