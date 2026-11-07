@echo off
REM Executa sem empacotar (requer Python instalado)
cd /d "%~dp0"
py -m pip install -q -r requirements.txt
py desktop.py
