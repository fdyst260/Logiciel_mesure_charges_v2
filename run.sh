#!/bin/bash
# Lanceur ACM Riveteuse
LOG=/tmp/acm_launch.log
exec > "$LOG" 2>&1

echo "=== ACM démarrage $(date) ==="

cd /home/acmfrance/Documents/logiciel_mesure/code || { echo "ERREUR: dossier introuvable"; exit 1; }

# Chemin absolu vers le Python du venv — évite les problèmes avec "source activate"
PYTHON=/home/acmfrance/Documents/logiciel_mesure/code/.venv/bin/python3

if [ ! -f "$PYTHON" ]; then
    echo "ERREUR: Python venv introuvable : $PYTHON"
    exit 1
fi

echo "Python: $PYTHON"
echo "Lancement main.py --sim ..."

"$PYTHON" main.py --sim
echo "=== ACM terminé (code $?) ==="