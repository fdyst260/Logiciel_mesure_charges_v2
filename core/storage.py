"""Persistance des cycles en CSV sur SSD."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from config import DATA_DIR


def build_cycle_filename(pm_id: int, result: str, now: datetime | None = None) -> Path:
    now = now or datetime.now()
    stamp = now.strftime("%Y%m%d_%H%M%S")
    return Path(DATA_DIR) / f"{stamp}_PM{pm_id:02d}_{result}.csv"


def save_cycle_csv(
    pm_id: int,
    result: str,
    points: list[tuple[float, float, float]],
) -> Path:
    """Enregistre la liste des points [t, force_n, pos_mm]."""
    path = build_cycle_filename(pm_id=pm_id, result=result)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["time_s", "force_n", "position_mm"])
        writer.writerows(points)

    return path
