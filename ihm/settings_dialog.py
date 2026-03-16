"""Dialogue des réglages — stub (à implémenter).

Sera complété ultérieurement avec :
  - Sélection du mode d'affichage (F=f(x), F=f(t), X=f(t))
  - Configuration des seuils d'alarme
  - Sélection du programme de mesure actif
  - Étalonnage capteurs
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout, QWidget


class SettingsDialog(QDialog):
    """Dialogue des réglages (stub — à implémenter)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Paramètres")
        self.setMinimumSize(500, 300)
        self.setModal(True)

        layout = QVBoxLayout(self)

        lbl = QLabel("Paramètres — à implémenter")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setFont(QFont("sans-serif", 16))
        layout.addWidget(lbl)

        layout.addStretch()

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)
