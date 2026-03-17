#!/bin/bash
# Lanceur ACM Riveteuse
cd /home/acmfrance/Documents/logiciel_mesure/code
source .venv/bin/activate
python3 main.py --sim
# Remplacer --sim par rien quand le hardware est branché