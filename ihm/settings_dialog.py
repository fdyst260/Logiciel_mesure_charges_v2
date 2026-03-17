"""Page de réglages — intégrée dans self.stack de MainWindow (index 1).

Architecture QStackedWidget interne (self._settings_stack) :
  Page 0 : Accueil Réglages   (3 grandes tuiles de navigation)
  Page 1 : Paramètres généraux (grille 3×3 de boutons)
  Page 2 : Réglage PM          (liste des 16 PM)
  Page 3 : Gestionnaire PM     (tableau + actions)

Chaque page enfant a son propre header avec titre + bouton ← Retour.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config import PM_DEFINITIONS

_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"

# ---------------------------------------------------------------------------
# Palette de couleurs — thème sombre identique à main_window
# ---------------------------------------------------------------------------
_C = {
    "bg":         "#111111",
    "panel":      "#181818",
    "card":       "#1e1e1e",
    "border":     "#333333",
    "header_bg":  "#1e1e1e",
    "text":       "#e0e0e0",
    "text_dim":   "#888888",
    "btn_bg":     "#252525",
    "btn_border": "#383838",
    "btn_active": "#185FA5",
    "ok_green":   "#1D9E75",
    "nok_red":    "#E24B4A",
    "blue":       "#378ADD",
}

# ---------------------------------------------------------------------------
# Feuille de style — page réglages
# ---------------------------------------------------------------------------
_STYLESHEET = f"""
QWidget {{
    background-color: {_C['bg']};
    color: {_C['text']};
    font-family: 'Segoe UI', Arial, sans-serif;
}}
QLabel {{ background-color: transparent; font-size: 15px; }}

QPushButton#btn_back {{
    background-color: {_C['btn_bg']};
    color: {_C['text']};
    font-size: 14px;
    font-weight: 600;
    border: 1px solid {_C['btn_border']};
    border-radius: 0px;
    padding: 0 20px;
    min-height: 50px;
}}
QPushButton#btn_back:pressed {{ background-color: {_C['btn_active']}; }}

QPushButton#action_btn {{
    background-color: {_C['btn_bg']};
    color: {_C['text']};
    font-size: 14px;
    border: 1px solid {_C['btn_border']};
    border-radius: 6px;
    min-height: 38px;
    padding: 0 12px;
}}
QPushButton#action_btn:pressed {{ background-color: {_C['btn_active']}; }}

QListWidget {{
    background-color: {_C['card']};
    color: {_C['text']};
    border: none;
    font-size: 15px;
    outline: none;
}}
QListWidget::item {{ padding: 10px 12px; border-bottom: 1px solid {_C['border']}; }}
QListWidget::item:selected {{ background-color: {_C['btn_active']}; color: #ffffff; }}

QTableWidget {{
    background-color: {_C['card']};
    color: {_C['text']};
    gridline-color: {_C['border']};
    border: none;
    font-size: 14px;
    outline: none;
}}
QTableWidget::item:selected {{ background-color: {_C['btn_active']}; }}
QHeaderView::section {{
    background-color: #2a2a2a;
    color: {_C['text_dim']};
    padding: 5px;
    border: 1px solid {_C['border']};
    font-size: 13px;
}}
QFrame#separator {{ background-color: {_C['border']}; max-height: 1px; }}
"""

# ---------------------------------------------------------------------------
# Feuille de style — dialogues Voie X / Voie Y
# ---------------------------------------------------------------------------
_DIALOG_STYLE = """
QDialog, QWidget {
    background-color: #1e1e1e;
    color: #e0e0e0;
    font-family: 'Segoe UI', Arial, sans-serif;
}
QLabel {
    background-color: transparent;
    font-size: 15px;
    color: #e0e0e0;
}
QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox {
    background-color: #2a2a2a;
    color: #e0e0e0;
    border: 1.5px solid #444;
    border-radius: 6px;
    padding: 6px;
    font-size: 15px;
    min-height: 42px;
}
QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus {
    border-color: #378ADD;
}
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView {
    background-color: #2a2a2a;
    color: #e0e0e0;
    selection-background-color: #185FA5;
}
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button,
QSpinBox::up-button,       QSpinBox::down-button {
    background-color: #333;
    border: none;
    width: 20px;
}
QPushButton#btn_save {
    background-color: #085041;
    color: #9FE1CB;
    font-size: 14px;
    font-weight: bold;
    border: none;
    border-radius: 8px;
    min-height: 44px;
    min-width: 160px;
}
QPushButton#btn_save:pressed { background-color: #063d31; }
QPushButton#btn_cancel {
    background-color: #3d1515;
    color: #F7C1C1;
    font-size: 14px;
    font-weight: bold;
    border: none;
    border-radius: 8px;
    min-height: 44px;
    min-width: 160px;
}
QPushButton#btn_cancel:pressed { background-color: #2a0e0e; }
"""


# ===========================================================================
# _Tile — tuile de navigation 220×200
# ===========================================================================

class _Tile(QFrame):
    """Tuile cliquable avec icône emoji (grand) et libellé (petit)."""

    clicked = Signal()

    def __init__(
        self,
        icon: str,
        label: str,
        border_color: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._border_color = border_color
        self._hovered = False
        self.setFixedSize(220, 200)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_style()

        v = QVBoxLayout(self)
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.setSpacing(12)
        v.setContentsMargins(12, 16, 12, 16)

        lbl_icon = QLabel(icon)
        lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_icon.setFont(QFont("", 40))
        lbl_icon.setStyleSheet("background: transparent; border: none;")
        v.addWidget(lbl_icon)

        lbl_text = QLabel(label)
        lbl_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_text.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        lbl_text.setStyleSheet("background: transparent; border: none; color: #e0e0e0;")
        v.addWidget(lbl_text)

    def _update_style(self) -> None:
        bg = "#2a2a2a" if self._hovered else "#1e1e1e"
        self.setStyleSheet(
            f"QFrame {{ background-color: {bg}; "
            f"border: 2px solid {self._border_color}; "
            f"border-radius: 16px; }}"
            "QLabel { background: transparent; border: none; }"
        )

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def enterEvent(self, event) -> None:
        self._hovered = True
        self._update_style()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self._update_style()
        super().leaveEvent(event)


# ===========================================================================
# VoieXDialog — configuration Voie X (Position)
# ===========================================================================

class VoieXDialog(QDialog):
    """Dialog de configuration du capteur Position (Voie X)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.setFixedSize(500, 380)
        self.setStyleSheet(_DIALOG_STYLE)
        self._build_ui()
        self._load_config()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        header = QWidget()
        header.setFixedHeight(50)
        header.setStyleSheet("background-color: #252525;")
        hh = QHBoxLayout(header)
        hh.setContentsMargins(16, 0, 16, 0)
        title = QLabel("📊   Configuration Voie X — Position")
        title.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: #e0e0e0; background: transparent;"
        )
        hh.addWidget(title)
        root.addWidget(header)

        # Formulaire
        form_w = QWidget()
        form = QFormLayout(form_w)
        form.setContentsMargins(24, 20, 24, 20)
        form.setSpacing(16)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("ex: Capteur déplacement")
        form.addRow("Nom du capteur :", self._name_edit)

        self._unit_combo = QComboBox()
        self._unit_combo.addItems(["mm", "cm", "°", "pulse"])
        form.addRow("Unité :", self._unit_combo)

        self._min_spin = QDoubleSpinBox()
        self._min_spin.setRange(-9999, 9999)
        self._min_spin.setDecimals(2)
        form.addRow("Valeur minimum :", self._min_spin)

        self._max_spin = QDoubleSpinBox()
        self._max_spin.setRange(0, 9999)
        self._max_spin.setDecimals(2)
        form.addRow("Valeur maximum :", self._max_spin)

        self._channel_spin = QSpinBox()
        self._channel_spin.setRange(0, 7)
        form.addRow("Canal MCC 118 :", self._channel_spin)

        root.addWidget(form_w, stretch=1)

        # Footer boutons
        footer = QWidget()
        footer.setFixedHeight(60)
        footer.setStyleSheet("background-color: #181818;")
        fh = QHBoxLayout(footer)
        fh.setContentsMargins(24, 8, 24, 8)
        fh.setSpacing(16)
        fh.addStretch()

        btn_save = QPushButton("✓  Sauvegarder")
        btn_save.setObjectName("btn_save")
        btn_save.clicked.connect(self._save)
        fh.addWidget(btn_save)

        btn_cancel = QPushButton("✗  Annuler")
        btn_cancel.setObjectName("btn_cancel")
        btn_cancel.clicked.connect(self.reject)
        fh.addWidget(btn_cancel)

        root.addWidget(footer)

    def _load_config(self) -> None:
        try:
            with open(_CONFIG_PATH) as f:
                cfg = yaml.safe_load(f) or {}
        except (FileNotFoundError, yaml.YAMLError):
            return

        scaling = cfg.get("scaling", {})
        acquisition = cfg.get("acquisition", {})

        self._name_edit.setText(scaling.get("position_name", ""))
        idx = self._unit_combo.findText(scaling.get("position_unit", "mm"))
        if idx >= 0:
            self._unit_combo.setCurrentIndex(idx)
        self._min_spin.setValue(0.0)
        self._max_spin.setValue(float(scaling.get("position_mm_max", 100.0)))
        self._channel_spin.setValue(int(acquisition.get("position_channel", 1)))

    def _save(self) -> None:
        try:
            with open(_CONFIG_PATH) as f:
                cfg = yaml.safe_load(f) or {}
        except (FileNotFoundError, yaml.YAMLError):
            cfg = {}

        cfg.setdefault("scaling", {})
        cfg.setdefault("acquisition", {})
        cfg["scaling"]["position_mm_max"] = self._max_spin.value()
        cfg["scaling"]["position_unit"] = self._unit_combo.currentText()
        cfg["scaling"]["position_name"] = self._name_edit.text()
        cfg["acquisition"]["position_channel"] = self._channel_spin.value()

        with open(_CONFIG_PATH, "w") as f:
            yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)

        QMessageBox.information(
            self,
            "Voie X",
            "✓ Configuration Voie X sauvegardée.\nRedémarrez pour appliquer.",
        )
        self.accept()


# ===========================================================================
# VoieYDialog — configuration Voie Y (Force)
# ===========================================================================

class VoieYDialog(QDialog):
    """Dialog de configuration du capteur Force (Voie Y)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.setFixedSize(500, 430)
        self.setStyleSheet(_DIALOG_STYLE)
        self._build_ui()
        self._load_config()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        header = QWidget()
        header.setFixedHeight(50)
        header.setStyleSheet("background-color: #252525;")
        hh = QHBoxLayout(header)
        hh.setContentsMargins(16, 0, 16, 0)
        title = QLabel("📡   Configuration Voie Y — Force")
        title.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: #e0e0e0; background: transparent;"
        )
        hh.addWidget(title)
        root.addWidget(header)

        # Formulaire
        form_w = QWidget()
        form = QFormLayout(form_w)
        form.setContentsMargins(24, 20, 24, 20)
        form.setSpacing(16)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("ex: Capteur piézoélectrique")
        form.addRow("Nom du capteur :", self._name_edit)

        self._unit_combo = QComboBox()
        self._unit_combo.addItems(["N", "kN", "kg", "lbf"])
        form.addRow("Unité :", self._unit_combo)

        self._min_spin = QDoubleSpinBox()
        self._min_spin.setRange(-9999, 9999)
        self._min_spin.setDecimals(2)
        form.addRow("Valeur minimum :", self._min_spin)

        self._max_spin = QDoubleSpinBox()
        self._max_spin.setRange(0, 9999)
        self._max_spin.setDecimals(2)
        form.addRow("Valeur maximum :", self._max_spin)

        self._channel_spin = QSpinBox()
        self._channel_spin.setRange(0, 7)
        form.addRow("Canal MCC 118 :", self._channel_spin)

        self._alarm_spin = QDoubleSpinBox()
        self._alarm_spin.setRange(0, 9999)
        self._alarm_spin.setDecimals(2)
        self._alarm_spin.setSuffix(" N")
        form.addRow("Seuil d'alarme :", self._alarm_spin)

        root.addWidget(form_w, stretch=1)

        # Footer boutons
        footer = QWidget()
        footer.setFixedHeight(60)
        footer.setStyleSheet("background-color: #181818;")
        fh = QHBoxLayout(footer)
        fh.setContentsMargins(24, 8, 24, 8)
        fh.setSpacing(16)
        fh.addStretch()

        btn_save = QPushButton("✓  Sauvegarder")
        btn_save.setObjectName("btn_save")
        btn_save.clicked.connect(self._save)
        fh.addWidget(btn_save)

        btn_cancel = QPushButton("✗  Annuler")
        btn_cancel.setObjectName("btn_cancel")
        btn_cancel.clicked.connect(self.reject)
        fh.addWidget(btn_cancel)

        root.addWidget(footer)

    def _load_config(self) -> None:
        try:
            with open(_CONFIG_PATH) as f:
                cfg = yaml.safe_load(f) or {}
        except (FileNotFoundError, yaml.YAMLError):
            return

        scaling = cfg.get("scaling", {})
        acquisition = cfg.get("acquisition", {})
        thresholds = cfg.get("thresholds", {})

        self._name_edit.setText(scaling.get("force_name", ""))
        idx = self._unit_combo.findText(scaling.get("force_unit", "N"))
        if idx >= 0:
            self._unit_combo.setCurrentIndex(idx)
        self._min_spin.setValue(0.0)
        self._max_spin.setValue(float(scaling.get("force_newton_max", 5000.0)))
        self._channel_spin.setValue(int(acquisition.get("force_channel", 0)))
        self._alarm_spin.setValue(float(thresholds.get("force_max_n", 4500.0)))

    def _save(self) -> None:
        try:
            with open(_CONFIG_PATH) as f:
                cfg = yaml.safe_load(f) or {}
        except (FileNotFoundError, yaml.YAMLError):
            cfg = {}

        cfg.setdefault("scaling", {})
        cfg.setdefault("acquisition", {})
        cfg.setdefault("thresholds", {})
        cfg["scaling"]["force_newton_max"] = self._max_spin.value()
        cfg["scaling"]["force_unit"] = self._unit_combo.currentText()
        cfg["scaling"]["force_name"] = self._name_edit.text()
        cfg["acquisition"]["force_channel"] = self._channel_spin.value()
        cfg["thresholds"]["force_max_n"] = self._alarm_spin.value()

        with open(_CONFIG_PATH, "w") as f:
            yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)

        QMessageBox.information(
            self,
            "Voie Y",
            "✓ Configuration Voie Y sauvegardée.\nRedémarrez pour appliquer.",
        )
        self.accept()


# ===========================================================================
# SettingsPage — fenêtre de réglages principale
# ===========================================================================

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

        self._settings_stack = QStackedWidget()
        self._settings_stack.addWidget(self._build_page0_home())        # 0
        self._settings_stack.addWidget(self._build_page1_general())     # 1
        self._settings_stack.addWidget(self._build_page2_pm_list())     # 2
        self._settings_stack.addWidget(self._build_page3_pm_manager())  # 3

        root.addWidget(self._settings_stack)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_header(self, title: str, back_to_home: bool = True) -> QWidget:
        """Header 50px : titre à gauche + bouton ← Retour à droite."""
        header = QWidget()
        header.setFixedHeight(50)
        header.setStyleSheet(
            f"background-color: {_C['header_bg']}; "
            f"border-bottom: 1px solid {_C['border']};"
        )
        h = QHBoxLayout(header)
        h.setContentsMargins(16, 0, 0, 0)
        h.setSpacing(0)

        lbl = QLabel(title)
        lbl.setStyleSheet(
            f"color: {_C['text']}; font-size: 18px; font-weight: bold;"
        )
        h.addWidget(lbl)
        h.addStretch()

        btn = QPushButton("←  Retour" if back_to_home else "←  Retour Production")
        btn.setObjectName("btn_back")
        if back_to_home:
            btn.clicked.connect(lambda: self._settings_stack.setCurrentIndex(0))
        else:
            btn.clicked.connect(self._go_to_production)
        h.addWidget(btn)
        return header

    def _go_to_production(self) -> None:
        """Retourne à la page Production (index 0 du stack principal)."""
        self.window().stack.setCurrentIndex(0)

    # ------------------------------------------------------------------
    # Page 0 — Accueil Réglages
    # ------------------------------------------------------------------

    def _build_page0_home(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        v.addWidget(self._make_header("⚙   Réglages", back_to_home=False))

        # Corps — 3 tuiles centrées
        body = QWidget()
        body.setStyleSheet(f"background-color: {_C['bg']};")
        bh = QHBoxLayout(body)
        bh.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bh.setSpacing(40)
        bh.setContentsMargins(40, 0, 40, 0)

        tiles_def = [
            ("🔧", "Paramètres\ngénéraux", "#854F0B", 1),
            ("📋", "Réglage PM",           "#185FA5", 2),
            ("📁", "Gestionnaire\nPM",     "#0F6E56", 3),
        ]
        for icon, label, border, page_idx in tiles_def:
            tile = _Tile(icon, label, border)
            tile.clicked.connect(
                lambda idx=page_idx: self._settings_stack.setCurrentIndex(idx)
            )
            bh.addWidget(tile)

        v.addWidget(body, stretch=1)
        v.addWidget(self._build_footer())
        return page

    # ------------------------------------------------------------------
    # Page 1 — Paramètres généraux
    # ------------------------------------------------------------------

    def _build_page1_general(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        v.addWidget(self._make_header("🔧   Paramètres généraux"))

        grid_w = QWidget()
        grid_w.setStyleSheet(f"background-color: {_C['bg']};")
        grid = QGridLayout(grid_w)
        grid.setContentsMargins(20, 20, 20, 20)
        grid.setSpacing(16)

        _BTN_STYLE = f"""
            QPushButton {{
                background-color: {_C['card']};
                color: #cccccc;
                font-size: 15px;
                font-weight: 600;
                border: 1px solid {_C['border']};
                border-radius: 10px;
            }}
            QPushButton:hover {{ background-color: #2a2a2a; border-color: #555; }}
            QPushButton:pressed {{ background-color: {_C['btn_active']}; color: #fff; }}
        """

        buttons = [
            ("🌐", "Langue",          0, 0, None),
            ("🔒", "Droits d'accès",  0, 1, None),
            ("📅", "Date / Heure",    0, 2, None),
            ("📊", "Voie X",          1, 0, "voie_x"),
            ("📡", "Voie Y",          1, 1, "voie_y"),
            ("⏱",  "Contrôle cycle", 1, 2, None),
            ("🖥",  "Affichage prod.",2, 0, None),
            ("💾", "Exportation",     2, 1, None),
            ("⚙",  "Extras",         2, 2, None),
        ]
        for icon, label, row, col, action in buttons:
            btn = QPushButton(f"{icon}\n{label}")
            btn.setFixedSize(180, 120)
            btn.setStyleSheet(_BTN_STYLE)
            if action == "voie_x":
                btn.clicked.connect(lambda checked=False: VoieXDialog(self).exec())
            elif action == "voie_y":
                btn.clicked.connect(lambda checked=False: VoieYDialog(self).exec())
            else:
                btn.clicked.connect(
                    lambda checked=False, t=label: QMessageBox.information(
                        self, "Réglages", f"{t} — À implémenter."
                    )
                )
            grid.addWidget(btn, row, col)

        v.addWidget(grid_w, stretch=1)
        return page

    # ------------------------------------------------------------------
    # Page 2 — Réglage PM
    # ------------------------------------------------------------------

    def _build_page2_pm_list(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        v.addWidget(self._make_header("📋   Réglage PM"))

        pm_list = QListWidget()
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
        return page

    # ------------------------------------------------------------------
    # Page 3 — Gestionnaire PM
    # ------------------------------------------------------------------

    def _build_page3_pm_manager(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        v.addWidget(self._make_header("📁   Gestionnaire PM"))

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

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(10, 6, 10, 6)
        btn_row.setSpacing(6)
        for lbl in ["✓  Valider", "✗  Annuler"]:
            btn = QPushButton(lbl)
            btn.setObjectName("action_btn")
            btn_row.addWidget(btn)
        v.addLayout(btn_row)
        return page

    # ------------------------------------------------------------------
    # Footer (page 0 uniquement)
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
        lbl.setStyleSheet("color: #555; font-size: 12px;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h.addWidget(lbl)
        return footer


# Alias de rétrocompatibilité (anciens imports depuis main_window.py)
SettingsDialog = SettingsPage