"""Page de réglages — intégrée dans self.stack de MainWindow (index 1).

Structure inspirée du maXYmos BL, thème sombre industriel :
  ┌─────────────────────────────────────────────────────┬────────┐
  │  ⚙  Réglages                                        │ Retour │
  ├──────────────────┬──────────────────┬───────────────┴────────┤
  │ Paramètres gén.  │   Réglage PM     │   Gestionnaire PM      │
  │  [Langue]        │  PM-01 Standard  │  N° | Nom    | Actif   │
  │  [Date/Heure]    │  PM-02 Souple    │  01 | STD    |  ✓      │
  │  [Voie X]  ...   │  ...             │  02 | SOUPLE |         │
  ├──────────────────┴──────────────────┴────────────────────────┤
  │  ACM Riveteuse v1.0  |  Raspberry Pi 5  |  MCC 118  |  5 kHz │
  └──────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config import PM_DEFINITIONS

# ---------------------------------------------------------------------------
# Palette de couleurs — thème sombre identique à main_window
# ---------------------------------------------------------------------------
_C = {
    "bg":          "#111111",
    "panel":       "#181818",
    "card":        "#1e1e1e",
    "border":      "#333333",
    "header_bg":   "#1e1e1e",
    "title_bg":    "#854F0B",   # orange — titres colonnes
    "text":        "#e0e0e0",
    "text_dim":    "#888888",
    "btn_bg":      "#252525",
    "btn_border":  "#383838",
    "btn_active":  "#185FA5",
    "ok_green":    "#1D9E75",
    "nok_red":     "#E24B4A",
    "blue":        "#378ADD",
}

_STYLESHEET = f"""
QWidget {{
    background-color: {_C['bg']};
    color: {_C['text']};
    font-family: 'Segoe UI', Arial, sans-serif;
}}
QLabel {{ background-color: transparent; }}

/* Boutons grille paramètres */
QPushButton#grid_btn {{
    background-color: {_C['btn_bg']};
    color: {_C['text']};
    font-size: 13px;
    border: 1px solid {_C['btn_border']};
    border-radius: 8px;
    padding: 6px;
}}
QPushButton#grid_btn:pressed {{ background-color: {_C['btn_active']}; }}

/* Boutons génériques */
QPushButton#action_btn {{
    background-color: {_C['btn_bg']};
    color: {_C['text']};
    font-size: 13px;
    border: 1px solid {_C['btn_border']};
    border-radius: 6px;
    min-height: 38px;
    padding: 0 12px;
}}
QPushButton#action_btn:pressed {{ background-color: {_C['btn_active']}; }}

/* Bouton Retour */
QPushButton#btn_back {{
    background-color: {_C['btn_bg']};
    color: {_C['text']};
    font-size: 13px;
    border: 1px solid {_C['btn_border']};
    border-radius: 0px;
    padding: 0 20px;
    min-height: 50px;
}}
QPushButton#btn_back:pressed {{ background-color: {_C['btn_active']}; }}

/* Liste PM */
QListWidget {{
    background-color: {_C['card']};
    color: {_C['text']};
    border: none;
    font-size: 13px;
    outline: none;
}}
QListWidget::item {{ padding: 8px 12px; border-bottom: 1px solid {_C['border']}; }}
QListWidget::item:selected {{ background-color: {_C['btn_active']}; color: #ffffff; }}

/* Table PM */
QTableWidget {{
    background-color: {_C['card']};
    color: {_C['text']};
    gridline-color: {_C['border']};
    border: none;
    font-size: 12px;
    outline: none;
}}
QTableWidget::item:selected {{ background-color: {_C['btn_active']}; }}
QHeaderView::section {{
    background-color: #2a2a2a;
    color: {_C['text_dim']};
    padding: 5px;
    border: 1px solid {_C['border']};
    font-size: 12px;
}}

QFrame#separator {{
    background-color: {_C['border']};
    max-height: 1px;
}}
"""


class SettingsPage(QWidget):
    """Page de réglages embarquée dans self.stack (index 1) de MainWindow."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(_STYLESHEET)
        self._build_ui()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())

        # Corps : 3 colonnes égales
        body = QWidget()
        body.setStyleSheet(f"background-color: {_C['bg']};")
        bh = QHBoxLayout(body)
        bh.setContentsMargins(10, 10, 10, 10)
        bh.setSpacing(10)
        bh.addWidget(self._build_col_general(),    stretch=1)
        bh.addWidget(self._build_col_pm_list(),     stretch=1)
        bh.addWidget(self._build_col_pm_manager(), stretch=1)
        root.addWidget(body, stretch=1)

        root.addWidget(self._build_footer())

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setFixedHeight(50)
        header.setStyleSheet(
            f"background-color: {_C['header_bg']}; "
            f"border-bottom: 1px solid {_C['border']};"
        )
        h = QHBoxLayout(header)
        h.setContentsMargins(14, 0, 0, 0)
        h.setSpacing(0)

        lbl = QLabel("⚙   Réglages")
        lbl.setStyleSheet(f"color: {_C['text']}; font-size: 18px; font-weight: bold;")
        h.addWidget(lbl)
        h.addStretch()

        btn_back = QPushButton("←  Retour")
        btn_back.setObjectName("btn_back")
        btn_back.clicked.connect(self._go_back)
        h.addWidget(btn_back)
        return header

    def _go_back(self) -> None:
        """Retourne à la page Production (index 0 du stack principal)."""
        self.window().stack.setCurrentIndex(0)

    # ------------------------------------------------------------------
    # Helpers colonnes
    # ------------------------------------------------------------------

    @staticmethod
    def _col_title(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"background-color: {_C['title_bg']}; color: #ffffff; "
            "font-size: 14px; font-weight: bold; padding: 8px; border-radius: 0px;"
        )
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setFixedHeight(36)
        return lbl

    @staticmethod
    def _make_card() -> QWidget:
        """Conteneur carte avec fond sombre et coin arrondi."""
        card = QWidget()
        card.setStyleSheet(
            f"background-color: {_C['card']}; border-radius: 8px; "
            f"border: 1px solid {_C['border']};"
        )
        return card

    # ------------------------------------------------------------------
    # Colonne 1 — Paramètres généraux
    # ------------------------------------------------------------------

    def _build_col_general(self) -> QWidget:
        col = QWidget()
        col.setStyleSheet(f"background-color: {_C['panel']}; border-radius: 8px;")
        v = QVBoxLayout(col)
        v.setContentsMargins(0, 0, 0, 8)
        v.setSpacing(8)

        v.addWidget(self._col_title("Paramètres généraux"))

        # Grille 2×3 de boutons stub
        grid_w = QWidget()
        grid_w.setStyleSheet(f"background-color: {_C['panel']};")
        grid = QGridLayout(grid_w)
        grid.setContentsMargins(10, 4, 10, 4)
        grid.setSpacing(8)

        buttons = [
            ("🌐\nLangue",           0, 0),
            ("🔒\nDroits d'accès",   0, 1),
            ("📅\nDate / Heure",     1, 0),
            ("📊\nVoie X",           1, 1),
            ("📡\nVoie Y",           2, 0),
            ("⏱\nContrôle cycle",    2, 1),
        ]
        for text, row, col_idx in buttons:
            btn = QPushButton(text)
            btn.setObjectName("grid_btn")
            btn.setFixedHeight(90)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            label = text.replace("\n", " ")
            btn.clicked.connect(
                lambda _checked=False, t=label: QMessageBox.information(
                    self, "Réglages", f"{t} — À implémenter."
                )
            )
            grid.addWidget(btn, row, col_idx)

        v.addWidget(grid_w)
        v.addStretch()
        return col

    # ------------------------------------------------------------------
    # Colonne 2 — Réglage PM (liste scrollable)
    # ------------------------------------------------------------------

    def _build_col_pm_list(self) -> QWidget:
        col = QWidget()
        col.setStyleSheet(f"background-color: {_C['panel']}; border-radius: 8px;")
        v = QVBoxLayout(col)
        v.setContentsMargins(0, 0, 0, 8)
        v.setSpacing(0)

        v.addWidget(self._col_title("Réglage PM"))

        pm_list = QListWidget()
        pm_list.setStyleSheet("")  # utilise le _STYLESHEET global
        for pm_id, pm in PM_DEFINITIONS.items():
            pm_list.addItem(f"PM-{pm_id:02d}   ·   {pm.name}")

        pm_list.itemDoubleClicked.connect(
            lambda item: QMessageBox.information(
                self,
                "Réglage PM",
                f"Édition {item.text().split('·')[0].strip()} — À implémenter.",
            )
        )
        v.addWidget(pm_list, stretch=1)
        return col

    # ------------------------------------------------------------------
    # Colonne 3 — Gestionnaire PM (table + boutons)
    # ------------------------------------------------------------------

    def _build_col_pm_manager(self) -> QWidget:
        col = QWidget()
        col.setStyleSheet(f"background-color: {_C['panel']}; border-radius: 8px;")
        v = QVBoxLayout(col)
        v.setContentsMargins(0, 0, 0, 8)
        v.setSpacing(6)

        v.addWidget(self._col_title("Gestionnaire PM"))

        table = QTableWidget(len(PM_DEFINITIONS), 3)
        table.setHorizontalHeaderLabels(["N°", "Nom", "Actif"])
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setDefaultSectionSize(50)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        for row, (pm_id, pm) in enumerate(PM_DEFINITIONS.items()):
            n_item = QTableWidgetItem(f"{pm_id:02d}")
            n_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, 0, n_item)

            table.setItem(row, 1, QTableWidgetItem(pm.name))

            actif_item = QTableWidgetItem("✓" if row == 0 else "")
            actif_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            actif_item.setForeground(QColor(_C["ok_green"]))
            table.setItem(row, 2, actif_item)

        v.addWidget(table, stretch=1)

        # Boutons Valider / Annuler
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        for label in ["✓  Valider", "✗  Annuler"]:
            btn = QPushButton(label)
            btn.setObjectName("action_btn")
            btn_row.addWidget(btn)
        v.addLayout(btn_row)

        return col

    # ------------------------------------------------------------------
    # Footer
    # ------------------------------------------------------------------

    def _build_footer(self) -> QWidget:
        footer = QWidget()
        footer.setFixedHeight(40)
        footer.setStyleSheet(
            f"background-color: {_C['header_bg']}; "
            f"border-top: 1px solid {_C['border']};"
        )
        h = QHBoxLayout(footer)
        lbl = QLabel(
            "ACM Riveteuse v1.0   |   Raspberry Pi 5   |   MCC 118   |   5 kHz"
        )
        lbl.setStyleSheet(f"color: {_C['text_dim']}; font-size: 11px;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h.addWidget(lbl)
        return footer


# Alias de rétrocompatibilité (anciens imports depuis main_window.py)
SettingsDialog = SettingsPage
