"""Simulateur d'acquisition sans hardware (remplace acquisition_loop).

Genere UN seul cycle de rivetage realiste en 3 phases sans aucune carte MCC 118 :
  - Phase 1 "approche"   (position  0 -> 20 mm) : force faible ~50 N
  - Phase 2 "sertissage" (position 20 -> 80 mm) : force montante 0 -> 3800 N
                                                   avec bruit gaussien (sigma=80 N)
  - Phase 3 "retour"     (position 80 -> 100 mm): force chute rapide vers 0 N

Apres le cycle, la fonction se termine. Le bouton "NOUVEAU CYCLE" dans l'IHM
permet de relancer manuellement un nouveau cycle.

Meme signature exacte que acquisition_loop() pour etre interchangeable dans main.py.
"""

from __future__ import annotations

import queue
import threading
import time

import numpy as np

from config import CHUNK_SIZE, SAMPLE_RATE_HZ

# Duree totale d'un cycle simule : ~2 secondes
_TOTAL_SAMPLES = int(SAMPLE_RATE_HZ * 2.0)


def fake_acquisition_loop(
    data_queue: queue.Queue,
    stop_event: threading.Event,
    calibrator=None,
    inject_fault: bool = False,
) -> None:
    """Boucle producteur simulee — UN seul cycle puis termine.

    Parametres
    ----------
    data_queue   : queue partagee avec DataProcessor
    stop_event   : evenement d'arret global
    calibrator   : ignore (valeurs generees directement en unites physiques)
    inject_fault : si True, injecte un pic a 5200 N a position 55 mm (NOK)
    """
    # Attente avant trigger simule (~1 seconde, interruptible)
    print("[SIM] Attente trigger simule (1 s)...")
    for _ in range(100):
        if stop_event.is_set():
            return
        time.sleep(0.01)
    print("[SIM] Trigger simule")

    t_start = time.perf_counter()
    samples_sent = 0

    while samples_sent < _TOTAL_SAMPLES and not stop_event.is_set():
        chunk_end = min(samples_sent + CHUNK_SIZE, _TOTAL_SAMPLES)
        block: list[tuple[float, float, float]] = []
        for i in range(samples_sent, chunk_end):
            t = t_start + i / SAMPLE_RATE_HZ
            pos_mm = i * 100.0 / _TOTAL_SAMPLES
            force_n = _compute_force(pos_mm, inject_fault)
            block.append((t, force_n, pos_mm))
        try:
            data_queue.put(block, timeout=0.2)
        except queue.Full:
            break
        samples_sent = chunk_end
        time.sleep(CHUNK_SIZE / SAMPLE_RATE_HZ)

    # Sentinelle fin de cycle
    try:
        data_queue.put(None, timeout=0.5)
    except queue.Full:
        pass

    print("[SIM] Cycle simule termine.")


def _compute_force(pos_mm: float, inject_fault: bool) -> float:
    """Calcule la force simulee en Newton selon la position."""
    noise = float(np.random.normal(0.0, 80.0))

    if pos_mm < 20.0:
        # Phase 1 : approche — force faible avec bruit reduit
        return max(0.0, 50.0 + noise * 0.2)

    if pos_mm <= 80.0:
        # Phase 2 : sertissage
        if inject_fault and 53.0 <= pos_mm <= 57.0:
            # Pic de defaut a 5200 N (doit declencher NOK)
            return 5200.0 + noise

        if pos_mm <= 60.0:
            # Montee lineaire 0 -> 3800 N entre 20 et 60 mm
            force = (pos_mm - 20.0) / 40.0 * 3800.0
        else:
            # Descente lineaire 3800 -> 2000 N entre 60 et 80 mm
            force = 3800.0 - (pos_mm - 60.0) / 20.0 * 1800.0

        return max(0.0, force + noise)

    # Phase 3 : retour (80 -> 100 mm) — chute rapide vers 0 N
    force = 2000.0 * (1.0 - (pos_mm - 80.0) / 20.0)
    return max(0.0, force + noise * 0.5)