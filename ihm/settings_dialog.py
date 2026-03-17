"""Dialogue des réglages — système complet multi-onglets.

Structure inspirée du design industriel ACM :
  Réglage: Accueil
  ├── Réglage général  (grille d'icônes, 2 pages)
  ├── Réglage PM       (sélection PM → détail PM)
  └── Gestion PM       (gestionnaire : copier/coller/RAZ)
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config import PM_DEFINITIONS

# ---------------------------------------------------------------------------
# Palette de couleurs — thème chaud industriel (orange / doré / crème)
# ---------------------------------------------------------------------------
_C = {
    "header_bg":     "#D4942A",
    "header_text":   "#FFFFFF",
    "body_bg":       "#F5E1B8",
    "body_bg_alt":   "#EDD9A8",
    "btn_bg":        "#FAF0DA",
    "btn_border":    "#C8A96E",
    "btn_pressed":   "#E8CF9A",
    "btn_text":      "#3A2A10",
    "tab_active":    "#E8A630",
    "tab_inactive":  "#C8880E",
    "tab_text":      "#FFFFFF",
    "input_bg":      "#FFFFFF",
    "input_border":  "#B89850",
    "table_header":  "#D4942A",
    "table_row_alt": "#F0DAB0",
    "table_row":     "#FAF0DA",
    "accent_green":  "#4CAF50",
    "accent_red":    "#D32F2F",
    "separator":     "#C8A96E",
    "text_dark":     "#3A2A10",
    "text_muted":    "#7A6A4A",
    "nav_arrow_bg":  "#D4942A",
    "nav_arrow_text": "#FFFFFF",
    "icon_bg":       "#FAF0DA",
}

_FONT_FAMILY = "'Segoe UI', Arial, sans-serif"

# ---------------------------------------------------------------------------
# Feuille de style globale pour le dialogue
# ---------------------------------------------------------------------------
_DIALOG_STYLE = f"""
QDialog {{
    background-color: {_C['body_bg']};
    font-family: {_FONT_FAMILY};
}}
QLabel {{
    color: {_C['text_dark']};
    background: transparent;
}}
QLineEdit {{
    background-color: {_C['input_bg']};
    border: 1px solid {_C['input_border']};
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 14px;
    color: {_C['text_dark']};
}}
QLineEdit:focus {{
    border-color: {_C['tab_active']};
    border-width: 2px;
}}
QTableWidget {{
    background-color: {_C['btn_bg']};
    gridline-color: {_C['separator']};
    color: {_C['text_dark']};
    border: 1px solid {_C['separator']};
    font-size: 13px;
}}
QTableWidget::item {{
    padding: 4px 8px;
}}
QHeaderView::section {{
    background-color: {_C['table_header']};
    color: {_C['header_text']};
    font-weight: bold;
    padding: 6px;
    border: none;
    border-right: 1px solid {_C['separator']};
}}
"""


# ===========================================================================
# Widgets réutilisables
# ===========================================================================

class _HeaderBar(QWidget):
    """Barre de titre orange en haut d'un écran."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(42)
        self.setStyleSheet(
            f"background-color: {_C['header_bg']}; "
            f"border-top-left-radius: 6px; border-top-right-radius: 6px;"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)
        lbl = QLabel(title)
        lbl.setStyleSheet(
            f"color: {_C['header_text']}; font-size: 15px; font-weight: bold; background: transparent;"
        )
        layout.addWidget(lbl)


class _IconButton(QPushButton):
    """Bouton carré avec icône (emoji) + libellé en dessous, style crème."""

    def __init__(self, icon_text: str, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(120, 100)
        self.setText(f"{icon_text}\n{label}")
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {_C['btn_bg']};
                border: 1px solid {_C['btn_border']};
                border-radius: 8px;
                color: {_C['btn_text']};
                font-size: 12px;
                font-weight: bold;
                padding: 8px 4px;
            }}
            QPushButton:pressed {{
                background-color: {_C['btn_pressed']};
            }}
            QPushButton:hover {{
                border-color: {_C['tab_active']};
                border-width: 2px;
            }}
        """)


class _NavArrowButton(QPushButton):
    """Bouton flèche de navigation (← →) en bas d'écran."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setFixedSize(60, 40)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {_C['nav_arrow_bg']};
                color: {_C['nav_arrow_text']};
                border: none;
                border-radius: 6px;
                font-size: 18px;
                font-weight: bold;
            }}
            QPushButton:pressed {{
                background-color: {_C['tab_inactive']};
            }}
        """)


class _ActionButton(QPushButton):
    """Bouton d'action (Copier, Coller, Raz, etc.)."""

    def __init__(self, text: str, color: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        bg = color or _C['btn_bg']
        self.setMinimumHeight(38)
        self.setMinimumWidth(90)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                border: 1px solid {_C['btn_border']};
                border-radius: 6px;
                color: {_C['btn_text']};
                font-size: 13px;
                font-weight: bold;
                padding: 6px 14px;
            }}
            QPushButton:pressed {{
                background-color: {_C['btn_pressed']};
            }}
        """)


def _make_tab_button(text: str, active: bool = False) -> QPushButton:
    """Crée un bouton onglet (style tab en haut)."""
    btn = QPushButton(text)
    btn.setCheckable(True)
    btn.setChecked(active)
    btn.setMinimumHeight(48)
    btn.setMinimumWidth(140)
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {_C['tab_inactive']};
            color: {_C['tab_text']};
            border: 1px solid {_C['separator']};
            border-bottom: none;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
            font-size: 14px;
            font-weight: bold;
            padding: 8px 20px;
        }}
        QPushButton:checked {{
            background-color: {_C['tab_active']};
            border-bottom: 3px solid {_C['header_text']};
        }}
        QPushButton:hover {{
            background-color: {_C['tab_active']};
        }}
    """)
    return btn


def _make_separator() -> QFrame:
    sep = QFrame()
    sep.setFrameShape(QFrame.Shape.HLine)
    sep.setFixedHeight(1)
    sep.setStyleSheet(f"background-color: {_C['separator']};")
    return sep


# ===========================================================================
# Page 1 — Réglage général (grille d'icônes, 2 pages)
# ===========================================================================

class _GeneralSettingsPage(QWidget):
    """Grille d'icônes des paramètres généraux avec pagination."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(_HeaderBar("Réglage général: Accueil"))

        # Pages empilées
        self._pages = QStackedWidget()

        # --- Page 1 ---
        page1 = QWidget()
        page1.setStyleSheet(f"background-color: {_C['body_bg']};")
        g1 = QGridLayout(page1)
        g1.setSpacing(12)
        g1.setContentsMargins(20, 20, 20, 10)

        icons_p1 = [
            ("🏳️", "Langue"),
            ("🔒", "Droits d'accès"),
            ("📅", "Date+Heure"),
            ("📈", "Voie X"),
            ("📉", "Voie Y"),
            ("🔄", "Contrôle cycle"),
            ("📋", "Affichage prod."),
            ("💾", "Exportation"),
            ("⚙️", "Extras"),
        ]
        for i, (icon, label) in enumerate(icons_p1):
            btn = _IconButton(icon, label)
            btn.clicked.connect(lambda checked, n=label: self._on_item_clicked(n))
            g1.addWidget(btn, i // 3, i % 3, Qt.AlignmentFlag.AlignCenter)

        self._pages.addWidget(page1)

        # --- Page 2 ---
        page2 = QWidget()
        page2.setStyleSheet(f"background-color: {_C['body_bg']};")
        g2 = QGridLayout(page2)
        g2.setSpacing(12)
        g2.setContentsMargins(20, 20, 20, 10)

        icons_p2 = [
            ("🔌", "E/S TOR"),
            ("🖧", "Bus de terrain"),
            ("⚠️", "Avertissement"),
            ("🖥️", "Ecran+Audio"),
            ("🏷️", "Appellation"),
            ("🌐", "Réseau"),
        ]
        for i, (icon, label) in enumerate(icons_p2):
            btn = _IconButton(icon, label)
            btn.clicked.connect(lambda checked, n=label: self._on_item_clicked(n))
            g2.addWidget(btn, i // 3, i % 3, Qt.AlignmentFlag.AlignCenter)

        self._pages.addWidget(page2)

        layout.addWidget(self._pages, stretch=1)

        # Barre de navigation bas
        nav = QWidget()
        nav.setStyleSheet(f"background-color: {_C['body_bg_alt']};")
        nav_layout = QHBoxLayout(nav)
        nav_layout.setContentsMargins(16, 8, 16, 8)

        self._btn_prev = _NavArrowButton("◀")
        self._btn_prev.clicked.connect(self._prev_page)
        self._btn_prev.setEnabled(False)

        self._btn_next = _NavArrowButton("▶")
        self._btn_next.clicked.connect(self._next_page)

        nav_layout.addWidget(self._btn_prev)
        nav_layout.addStretch()
        nav_layout.addWidget(self._btn_next)

        layout.addWidget(nav)

    def _prev_page(self) -> None:
        idx = max(0, self._pages.currentIndex() - 1)
        self._pages.setCurrentIndex(idx)
        self._btn_prev.setEnabled(idx > 0)
        self._btn_next.setEnabled(idx < self._pages.count() - 1)

    def _next_page(self) -> None:
        idx = min(self._pages.count() - 1, self._pages.currentIndex() + 1)
        self._pages.setCurrentIndex(idx)
        self._btn_prev.setEnabled(idx > 0)
        self._btn_next.setEnabled(idx < self._pages.count() - 1)

    def _on_item_clicked(self, name: str) -> None:
        QMessageBox.information(self, "Réglage", f"Paramètre « {name} » — à implémenter.")


# ===========================================================================
# Page 2 — Réglage PM (choix PM → détail)
# ===========================================================================

class _PMSettingsPage(QWidget):
    """Sélection d'un PM dans une grille, puis écran de détail."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._header = _HeaderBar("Réglage: choix du PM à paramétrer")
        layout.addWidget(self._header)

        self._stack = QStackedWidget()

        # --- Écran sélection PM ---
        self._selection = QWidget()
        self._selection.setStyleSheet(f"background-color: {_C['body_bg']};")
        sel_layout = QVBoxLayout(self._selection)
        sel_layout.setContentsMargins(16, 16, 16, 8)
        sel_layout.setSpacing(8)

        grid = QGridLayout()
        grid.setSpacing(8)

        # PM-00 à PM-09 (2 colonnes × 5 lignes)
        pm_ids = sorted(PM_DEFINITIONS.keys())[:10]
        for i, pm_id in enumerate(pm_ids):
            pm = PM_DEFINITIONS[pm_id]
            btn = QPushButton(f"PM-{pm_id:02d}:{pm.name}")
            btn.setMinimumHeight(44)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {_C['btn_bg']};
                    border: 1px solid {_C['btn_border']};
                    border-radius: 6px;
                    color: {_C['btn_text']};
                    font-size: 13px;
                    font-weight: bold;
                    padding: 6px 12px;
                    text-align: left;
                }}
                QPushButton:pressed {{
                    background-color: {_C['btn_pressed']};
                }}
                QPushButton:hover {{
                    border-color: {_C['tab_active']};
                    border-width: 2px;
                }}
            """)
            btn.clicked.connect(lambda checked, pid=pm_id: self._open_pm_detail(pid))
            grid.addWidget(btn, i % 5, i // 5)

        sel_layout.addLayout(grid)
        sel_layout.addStretch()

        # Nav bas
        nav = QWidget()
        nav.setStyleSheet(f"background-color: {_C['body_bg_alt']};")
        nav_l = QHBoxLayout(nav)
        nav_l.setContentsMargins(16, 8, 16, 8)
        btn_prev = _NavArrowButton("◀")
        btn_prev.setEnabled(False)
        btn_next = _NavArrowButton("▶")
        btn_next.setEnabled(False)
        nav_l.addWidget(btn_prev)
        nav_l.addStretch()
        nav_l.addWidget(btn_next)
        sel_layout.addWidget(nav)

        self._stack.addWidget(self._selection)

        # --- Écran détail PM ---
        self._detail = QWidget()
        self._detail.setStyleSheet(f"background-color: {_C['body_bg']};")
        det_layout = QVBoxLayout(self._detail)
        det_layout.setContentsMargins(16, 16, 16, 8)
        det_layout.setSpacing(12)

        # Nom PM
        row_name = QHBoxLayout()
        row_name.addWidget(QLabel("Nom PM"))
        self._pm_name_edit = QLineEdit()
        self._pm_name_edit.setMinimumHeight(36)
        row_name.addWidget(self._pm_name_edit, stretch=1)
        det_layout.addLayout(row_name)

        det_layout.addWidget(_make_separator())

        # Grille d'icônes de sous-réglages PM
        det_grid = QGridLayout()
        det_grid.setSpacing(12)

        pm_icons = [
            ("📊", "Evaluation"),
            ("📐", "Sorties seuils"),
            ("📋", "Données prod."),
            ("🔢", "N° pièce"),
            ("⏱️", "Séquenceur"),
        ]
        for i, (icon, label) in enumerate(pm_icons):
            btn = _IconButton(icon, label)
            btn.clicked.connect(lambda checked, n=label: self._on_pm_sub_clicked(n))
            det_grid.addWidget(btn, i // 3, i % 3, Qt.AlignmentFlag.AlignCenter)

        det_layout.addLayout(det_grid)
        det_layout.addStretch()

        # Bouton retour
        back_row = QHBoxLayout()
        btn_back = _NavArrowButton("◀")
        btn_back.clicked.connect(self._back_to_selection)
        back_row.addWidget(btn_back)
        back_row.addStretch()
        det_layout.addLayout(back_row)

        self._stack.addWidget(self._detail)

        layout.addWidget(self._stack, stretch=1)

        self._current_pm_id: int | None = None

    def _open_pm_detail(self, pm_id: int) -> None:
        self._current_pm_id = pm_id
        pm = PM_DEFINITIONS.get(pm_id)
        self._header.findChild(QLabel).setText(f"PM-{pm_id:02d} Réglage: Accueil")
        self._pm_name_edit.setText(pm.name if pm else "")
        self._stack.setCurrentIndex(1)

    def _back_to_selection(self) -> None:
        self._header.findChild(QLabel).setText("Réglage: choix du PM à paramétrer")
        self._stack.setCurrentIndex(0)

    def _on_pm_sub_clicked(self, name: str) -> None:
        QMessageBox.information(
            self, "Réglage PM",
            f"PM-{self._current_pm_id:02d} → « {name} » — à implémenter."
        )


# ===========================================================================
# Page 3 — Gestionnaire PM (table, copier, coller, RAZ)
# ===========================================================================

class _PMManagerPage(QWidget):
    """Gestionnaire de programmes de mesure avec table et actions."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(_HeaderBar("Réglage: Gestionnaire Programme de Mesure"))

        body = QWidget()
        body.setStyleSheet(f"background-color: {_C['body_bg']};")
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(12, 12, 12, 12)
        body_layout.setSpacing(12)

        # --- Table PM ---
        self._table = QTableWidget()
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["PM", "Nom", "Actif"])
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(0, 50)
        self._table.setColumnWidth(2, 60)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)

        self._populate_table()
        body_layout.addWidget(self._table, stretch=1)

        # --- Colonne d'actions ---
        actions = QWidget()
        actions_layout = QVBoxLayout(actions)
        actions_layout.setSpacing(10)
        actions_layout.setContentsMargins(0, 0, 0, 0)

        btn_copy = _ActionButton("📋 Copier")
        btn_copy.clicked.connect(self._copy_pm)
        actions_layout.addWidget(btn_copy)

        btn_paste = _ActionButton("📌 Coller")
        btn_paste.clicked.connect(self._paste_pm)
        actions_layout.addWidget(btn_paste)

        # Indicateur mémoire
        self._mem_label = QLabel("En mémoire:\n—")
        self._mem_label.setStyleSheet(
            f"color: {_C['text_muted']}; font-size: 12px; padding: 8px;"
        )
        self._mem_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        actions_layout.addWidget(self._mem_label)

        actions_layout.addStretch()

        # Boutons haut/bas
        btn_up = _ActionButton("▲")
        btn_up.clicked.connect(self._move_up)
        actions_layout.addWidget(btn_up)

        btn_down = _ActionButton("▼")
        btn_down.clicked.connect(self._move_down)
        actions_layout.addWidget(btn_down)

        actions_layout.addStretch()

        btn_raz = _ActionButton("🔄 Raz", _C['body_bg_alt'])
        btn_raz.clicked.connect(self._raz_pm)
        actions_layout.addWidget(btn_raz)

        body_layout.addWidget(actions)

        layout.addWidget(body, stretch=1)

        # Barre validation bas
        bottom = QWidget()
        bottom.setStyleSheet(f"background-color: {_C['body_bg_alt']};")
        bottom_l = QHBoxLayout(bottom)
        bottom_l.setContentsMargins(16, 8, 16, 8)
        bottom_l.addStretch()

        btn_ok = _ActionButton("✓", _C['accent_green'])
        btn_ok.setStyleSheet(btn_ok.styleSheet().replace(
            f"color: {_C['btn_text']}", "color: #FFFFFF"
        ))
        btn_ok.setFixedSize(50, 40)
        bottom_l.addWidget(btn_ok)

        btn_cancel = _ActionButton("✗", _C['accent_red'])
        btn_cancel.setStyleSheet(btn_cancel.styleSheet().replace(
            f"color: {_C['btn_text']}", "color: #FFFFFF"
        ))
        btn_cancel.setFixedSize(50, 40)
        bottom_l.addWidget(btn_cancel)

        layout.addWidget(bottom)

        self._clipboard_pm: int | None = None

    def _populate_table(self) -> None:
        pm_ids = sorted(PM_DEFINITIONS.keys())
        self._table.setRowCount(len(pm_ids))
        for row, pm_id in enumerate(pm_ids):
            pm = PM_DEFINITIONS[pm_id]
            item_id = QTableWidgetItem(f"{pm_id:02d}")
            item_id.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 0, item_id)

            item_name = QTableWidgetItem(pm.name)
            self._table.setItem(row, 1, item_name)

            item_active = QTableWidgetItem("✓")
            item_active.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 2, item_active)

    def _copy_pm(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            return
        pm_id_text = self._table.item(row, 0).text()
        pm_name = self._table.item(row, 1).text()
        self._clipboard_pm = int(pm_id_text)
        self._mem_label.setText(f"En mémoire:\nPM-{pm_id_text}\n{pm_name}")

    def _paste_pm(self) -> None:
        if self._clipboard_pm is None:
            QMessageBox.information(self, "Coller", "Aucun PM en mémoire.")
            return
        row = self._table.currentRow()
        if row < 0:
            return
        source = PM_DEFINITIONS.get(self._clipboard_pm)
        if source:
            self._table.item(row, 1).setText(source.name)

    def _move_up(self) -> None:
        row = self._table.currentRow()
        if row <= 0:
            return
        self._swap_rows(row, row - 1)
        self._table.setCurrentCell(row - 1, 0)

    def _move_down(self) -> None:
        row = self._table.currentRow()
        if row < 0 or row >= self._table.rowCount() - 1:
            return
        self._swap_rows(row, row + 1)
        self._table.setCurrentCell(row + 1, 0)

    def _swap_rows(self, r1: int, r2: int) -> None:
        for col in range(self._table.columnCount()):
            t1 = self._table.item(r1, col).text()
            t2 = self._table.item(r2, col).text()
            self._table.item(r1, col).setText(t2)
            self._table.item(r2, col).setText(t1)

    def _raz_pm(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            return
        reply = QMessageBox.question(
            self, "RAZ",
            f"Remettre à zéro le PM ligne {row} ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._table.item(row, 1).setText("------")


# ===========================================================================
# SettingsDialog — dialogue principal avec onglets
# ===========================================================================

class SettingsDialog(QDialog):
    """Dialogue des réglages complet — 3 onglets, thème industriel chaud."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Réglage: Accueil")
        self.setMinimumSize(900, 600)
        self.setModal(True)
        self.setStyleSheet(_DIALOG_STYLE)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # --- Barre titre ---
        title_bar = QWidget()
        title_bar.setFixedHeight(44)
        title_bar.setStyleSheet(
            f"background-color: {_C['header_bg']}; "
            f"border-top-left-radius: 8px; border-top-right-radius: 8px;"
        )
        tb_layout = QHBoxLayout(title_bar)
        tb_layout.setContentsMargins(16, 0, 16, 0)
        title_lbl = QLabel("Réglage: Accueil")
        title_lbl.setStyleSheet(
            f"color: {_C['header_text']}; font-size: 16px; font-weight: bold; background: transparent;"
        )
        tb_layout.addWidget(title_lbl)
        tb_layout.addStretch()

        # Bouton fermer
        btn_close = QPushButton("✕")
        btn_close.setFixedSize(36, 36)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {_C['header_text']};
                font-size: 18px;
                font-weight: bold;
                border: none;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {_C['accent_red']};
            }}
        """)
        btn_close.clicked.connect(self.reject)
        tb_layout.addWidget(btn_close)

        root.addWidget(title_bar)

        # --- Onglets ---
        tabs_bar = QWidget()
        tabs_bar.setFixedHeight(54)
        tabs_bar.setStyleSheet(f"background-color: {_C['body_bg_alt']};")
        tabs_layout = QHBoxLayout(tabs_bar)
        tabs_layout.setContentsMargins(12, 4, 12, 0)
        tabs_layout.setSpacing(6)

        self._tab_general = _make_tab_button("Réglage général", active=True)
        self._tab_pm = _make_tab_button("Réglage PM")
        self._tab_gestion = _make_tab_button("Gestion PM")

        self._tab_general.clicked.connect(lambda: self._switch_tab(0))
        self._tab_pm.clicked.connect(lambda: self._switch_tab(1))
        self._tab_gestion.clicked.connect(lambda: self._switch_tab(2))

        tabs_layout.addWidget(self._tab_general)
        tabs_layout.addWidget(self._tab_pm)
        tabs_layout.addWidget(self._tab_gestion)
        tabs_layout.addStretch()

        root.addWidget(tabs_bar)

        # --- Contenu empilé ---
        self._content = QStackedWidget()

        self._page_general = _GeneralSettingsPage()
        self._page_pm = _PMSettingsPage()
        self._page_manager = _PMManagerPage()

        self._content.addWidget(self._page_general)
        self._content.addWidget(self._page_pm)
        self._content.addWidget(self._page_manager)

        root.addWidget(self._content, stretch=1)

        # --- Barre bas avec bouton Fermer ---
        bottom = QWidget()
        bottom.setFixedHeight(50)
        bottom.setStyleSheet(f"background-color: {_C['body_bg_alt']};")
        bot_layout = QHBoxLayout(bottom)
        bot_layout.setContentsMargins(16, 6, 16, 6)
        bot_layout.addStretch()

        btn_fermer = _ActionButton("Fermer")
        btn_fermer.clicked.connect(self.reject)
        bot_layout.addWidget(btn_fermer)

        root.addWidget(bottom)

    def _switch_tab(self, index: int) -> None:
        self._content.setCurrentIndex(index)
        tabs = [self._tab_general, self._tab_pm, self._tab_gestion]
        for i, tab in enumerate(tabs):
            tab.setChecked(i == index)
