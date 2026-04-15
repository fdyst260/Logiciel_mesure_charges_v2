"""Persistance des cycles en CSV sur SSD."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from config import DATA_DIR

_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


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
        writer = csv.writer(csvfile, delimiter=';')
        writer.writerow(["t", "force_n", "position_mm"])
        writer.writerows(points)

    _auto_export_if_enabled(path)
    return path


def _auto_export_if_enabled(csv_path: Path) -> None:
    """Exporte vers clé USB si auto_export est activé dans config.yaml."""
    try:
        import yaml
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    except Exception:
        return

    export_cfg = cfg.get("export", {})
    if not export_cfg.get("auto_export", False):
        return

    dest = export_cfg.get("destination_auto", "Dossier local")
    if dest != "Clé USB si présente":
        return

    try:
        from core.export_manager import export_csv_to_usb, find_usb_drives
        drives = find_usb_drives()
        if drives:
            export_csv_to_usb(
                source_dir=csv_path.parent,
                usb_path=drives[0],
                filter_result=export_cfg.get("filtre", "OK+NOK"),
            )
    except Exception as e:
        print(f"[STORAGE] Auto-export échoué : {e}")
