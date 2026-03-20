"""Utilitaires partagés pour l'IHM — thème, séparateurs, config YAML.

Ce module ne doit pas importer depuis ihm/main_window.py ou
ihm/settings_dialog.py (risque de circular imports).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from PySide6.QtWidgets import QFrame

# ---------------------------------------------------------------------------
# Constantes UI (dimensions standards)
# ---------------------------------------------------------------------------

HEADER_HEIGHT      = 50
NAV_BAR_HEIGHT     = 70
RIGHT_PANEL_WIDTH  = 420
BUTTON_HEIGHT_SM   = 44
BUTTON_HEIGHT_MD   = 52
BUTTON_HEIGHT_LG   = 60

# ---------------------------------------------------------------------------
# Config YAML
# ---------------------------------------------------------------------------

def load_config(config_path: Path) -> dict:
    """Charge un fichier YAML, retourne {} si absent ou invalide."""
    try:
        with open(config_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def save_config(config_path: Path, cfg: dict) -> bool:
    """Sauvegarde un dict dans un fichier YAML. Retourne True si succès."""
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Séparateurs QFrame
# ---------------------------------------------------------------------------

def make_hseparator(color: str = "#333333") -> QFrame:
    """Séparateur horizontal 1px."""
    sep = QFrame()
    sep.setObjectName("separator")
    sep.setFrameShape(QFrame.Shape.HLine)
    sep.setFixedHeight(1)
    sep.setStyleSheet(f"background-color: {color};")
    return sep


def make_vseparator(color: str = "#333333") -> QFrame:
    """Séparateur vertical 1px."""
    sep = QFrame()
    sep.setFrameShape(QFrame.Shape.VLine)
    sep.setFixedWidth(1)
    sep.setStyleSheet(f"background-color: {color};")
    return sep