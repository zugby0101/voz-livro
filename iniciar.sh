#!/usr/bin/env bash
# Executa sem empacotar (requer Python 3.9+)
cd "$(dirname "$0")"
python3 -m pip install -q -r requirements.txt
python3 desktop.py
