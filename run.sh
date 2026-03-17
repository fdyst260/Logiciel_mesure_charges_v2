#!/bin/bash
# Lanceur ACM Riveteuse
cd /home/acmfrance/Documents/logiciel_mesure/code

# Chemin absolu vers le Python du venv — évite les problèmes avec "source activate"
PYTHON=/home/acmfrance/Documents/logiciel_mesure/code/.venv/bin/python3

exec "$PYTHON" main.py --sim
# Remplacer --sim par rien quand le hardware MCC 118 est branché