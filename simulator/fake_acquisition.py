"""Simulateur d'acquisition sans hardware (remplace acquisition_loop).

Genere UN seul cycle de rivetage plausible avec course 0 -> 20 mm :
    - Approche libre : force faible et peu bruitee
    - Prise de contact : montee progressive
    - Sertissage plastique : montee rapide
    - Fin de course : pic puis leger tassement

Un cycle nominal reste autour de 1300 kgf max (~12750 N).
Si inject_fault=True, un pic local depasse la zone nominale pour forcer un NOK.

Apres le cycle, la fonction se termine. Le bouton "NOUVEAU CYCLE" dans l'IHM
permet de relancer manuellement un nouveau cycle.

Meme signature exacte que acquisition_loop() pour etre interchangeable dans main.py.
"""

from __future__ import annotations

import queue
import threading
import time

import numpy as np

from config import CHUNK_SIZE, POSITION_MM_MAX, SAMPLE_RATE_HZ

# Duree totale d'un cycle simule : ~2 secondes
_TOTAL_SAMPLES = int(SAMPLE_RATE_HZ * 2.0)
_NOMINAL_MAX_FORCE_N = 12750.0  # ~1300 kgf


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
    inject_fault : si True, injecte un pic de force hors nominal (NOK)
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
            pos_mm = i * POSITION_MM_MAX / max(_TOTAL_SAMPLES - 1, 1)
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
    """Calcule la force simulee (N) en fonction de la position (mm)."""
    pos = float(np.clip(pos_mm, 0.0, POSITION_MM_MAX))

    # Profil nominal multi-phases pour reproduire une courbe de rivetage réaliste.
    if pos < 6.0:
        # Approche libre : quasi pas d'effort.
        base = 20.0 + 35.0 * pos
    elif pos < 14.0:
        # Prise de contact : montée progressive, non linéaire.
        u = (pos - 6.0) / 8.0
        base = 230.0 + 4200.0 * (u ** 1.45)
    elif pos < 18.2:
        # Sertissage plastique : raideur apparente plus forte.
        u = (pos - 14.0) / 4.2
        base = 4450.0 + 7000.0 * (u ** 1.2)
    elif pos < 19.4:
        # Fin de course : pic proche de 1300 kgf.
        u = (pos - 18.2) / 1.2
        base = 11450.0 + 1300.0 * u
    else:
        # Tassement final : légère détente sans retomber à 0 pendant l'avance.
        u = (pos - 19.4) / 0.6
        base = 12750.0 - 1100.0 * u

    # Bruit proportionnel au niveau de force + petite composante périodique.
    sigma = 18.0 + 0.010 * base
    noise = float(np.random.normal(0.0, sigma))
    ripple = 85.0 * np.sin(2.0 * np.pi * pos / 1.7)
    force = base + noise + ripple

    if inject_fault and 18.8 <= pos <= 19.2:
        # Défaut : sur-effort local qui dépasse le seuil NOK.
        force += 2200.0

    if not inject_fault:
        force = min(force, _NOMINAL_MAX_FORCE_N)

    return max(0.0, force)
