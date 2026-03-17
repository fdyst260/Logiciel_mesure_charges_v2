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

from PySide6.QtCore import Qt, QPointF, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QCheckBox,
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
    QTabWidget,
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


# ---------------------------------------------------------------------------
# Style QTabWidget pour PMEditDialog
# ---------------------------------------------------------------------------
_PM_EDIT_STYLE = _DIALOG_STYLE + """
QTabWidget::pane { background-color: #1e1e1e; border: none; }
QTabBar::tab {
    background: #252525; color: #888888; padding: 10px 20px;
    font-size: 14px; border-radius: 6px 6px 0 0; margin-right: 2px;
}
QTabBar::tab:selected { background: #1e1e1e; color: #ffffff; border-bottom: 2px solid #378ADD; }
QCheckBox {
    font-size: 15px; color: #e0e0e0; spacing: 8px;
    min-height: 42px; background: transparent;
}
QCheckBox::indicator {
    width: 22px; height: 22px; background-color: #2a2a2a;
    border: 1.5px solid #444; border-radius: 4px;
}
QCheckBox::indicator:checked { background-color: #085041; border-color: #1D9E75; }
"""


# ===========================================================================
# Aperçus visuels (NO-PASS, UNI-BOX, ENVELOPPE)
# ===========================================================================

class _NoPassPreview(QWidget):
    def __init__(self, x_min_sp: QDoubleSpinBox, x_max_sp: QDoubleSpinBox,
                 y_limit_sp: QDoubleSpinBox, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(200)
        self._x_min, self._x_max, self._y_limit = x_min_sp, x_max_sp, y_limit_sp
        for sp in (x_min_sp, x_max_sp, y_limit_sp):
            sp.valueChanged.connect(self.update)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        mx, my = 24, 8
        ws_x, ws_y, ws_w, ws_h = mx, my, w - 2 * mx, h - 2 * my - 16
        p.fillRect(ws_x, ws_y, ws_w, ws_h, QColor("#1a1a1a"))
        p.setPen(QPen(QColor("#444444"), 1))
        p.drawRect(ws_x, ws_y, ws_w, ws_h)
        X_MAX, Y_MAX = 500.0, 6000.0
        def fx(v): return ws_x + (v / X_MAX) * ws_w
        def fy(v): return ws_y + ws_h - (v / Y_MAX) * ws_h
        rx1, rx2 = int(fx(self._x_min.value())), int(fx(self._x_max.value()))
        ry_top, ry_bot = ws_y, int(fy(self._y_limit.value()))
        if rx2 > rx1 and ry_bot > ry_top:
            p.fillRect(rx1, ry_top, rx2 - rx1, ry_bot - ry_top, QColor(226, 75, 74, 80))
            p.setPen(QPen(QColor("#E24B4A"), 1.5))
            p.drawRect(rx1, ry_top, rx2 - rx1, ry_bot - ry_top)
        p.setPen(QPen(QColor("#666666"), 1))
        p.setFont(QFont("Arial", 9))
        p.drawText(ws_x, ws_y + ws_h + 13, "Aperçu NO-PASS  (X = position mm, Y = force N)")
        p.end()


class _UniBoxPreview(QWidget):
    def __init__(self, x_min_sp, x_max_sp, y_min_sp, y_max_sp,
                 entry_combo, exit_combo, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(200)
        self._x_min, self._x_max = x_min_sp, x_max_sp
        self._y_min, self._y_max = y_min_sp, y_max_sp
        self._entry, self._exit = entry_combo, exit_combo
        for sp in (x_min_sp, x_max_sp, y_min_sp, y_max_sp):
            sp.valueChanged.connect(self.update)
        entry_combo.currentIndexChanged.connect(self.update)
        exit_combo.currentIndexChanged.connect(self.update)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        mx, my = 24, 8
        ws_x, ws_y, ws_w, ws_h = mx, my, w - 2 * mx, h - 2 * my - 16
        p.fillRect(ws_x, ws_y, ws_w, ws_h, QColor("#1a1a1a"))
        p.setPen(QPen(QColor("#444444"), 1))
        p.drawRect(ws_x, ws_y, ws_w, ws_h)
        X_MAX, Y_MAX = 500.0, 6000.0
        def fx(v): return ws_x + (v / X_MAX) * ws_w
        def fy(v): return ws_y + ws_h - (v / Y_MAX) * ws_h
        bx1, bx2 = int(fx(self._x_min.value())), int(fx(self._x_max.value()))
        by1, by2 = int(fy(self._y_max.value())), int(fy(self._y_min.value()))
        if bx2 > bx1 and by2 > by1:
            p.fillRect(bx1, by1, bx2 - bx1, by2 - by1, QColor(133, 79, 11, 60))
            p.setPen(QPen(QColor("#E8891B"), 1.5, Qt.PenStyle.DashLine))
            p.drawRect(bx1, by1, bx2 - bx1, by2 - by1)
            cx, cy = (bx1 + bx2) // 2, (by1 + by2) // 2
            self._arrow(p, bx1, bx2, by1, by2, cx, cy,
                        self._entry.currentData(), QColor("#1D9E75"), True)
            self._arrow(p, bx1, bx2, by1, by2, cx, cy,
                        self._exit.currentData(), QColor("#E24B4A"), False)
        p.setPen(QPen(QColor("#666666"), 1))
        p.setFont(QFont("Arial", 9))
        p.drawText(ws_x, ws_y + ws_h + 13, "Aperçu UNI-BOX  (vert = entrée, rouge = sortie)")
        p.end()

    @staticmethod
    def _arrow(p, bx1, bx2, by1, by2, cx, cy, side, color, inward):
        p.setPen(QPen(color, 2))
        L = 18
        if side == "left":
            p.drawLine(bx1 - L, cy, bx1, cy) if inward else p.drawLine(bx1, cy, bx1 - L, cy)
        elif side == "right":
            p.drawLine(bx2 + L, cy, bx2, cy) if inward else p.drawLine(bx2, cy, bx2 + L, cy)
        elif side == "bottom":
            p.drawLine(cx, by2 + L, cx, by2) if inward else p.drawLine(cx, by2, cx, by2 + L)
        elif side == "top":
            p.drawLine(cx, by1 - L, cx, by1) if inward else p.drawLine(cx, by1, cx, by1 - L)


class _EnvelopePreview(QWidget):
    def __init__(self, lower_table: QTableWidget, upper_table: QTableWidget,
                 parent=None) -> None:
        super().__init__(parent)
        self._lower, self._upper = lower_table, upper_table

    @staticmethod
    def _read(table: QTableWidget) -> list[tuple[float, float]]:
        pts = []
        for row in range(table.rowCount()):
            xi, yi = table.item(row, 0), table.item(row, 1)
            if xi and yi and xi.text() and yi.text():
                try:
                    pts.append((float(xi.text()), float(yi.text())))
                except ValueError:
                    pass
        return sorted(pts, key=lambda pt: pt[0])

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        mx, my = 24, 8
        ws_x, ws_y, ws_w, ws_h = mx, my, w - 2 * mx, h - 2 * my - 16
        p.fillRect(ws_x, ws_y, ws_w, ws_h, QColor("#1a1a1a"))
        p.setPen(QPen(QColor("#444444"), 1))
        p.drawRect(ws_x, ws_y, ws_w, ws_h)
        lower, upper = self._read(self._lower), self._read(self._upper)
        if len(lower) < 2 or len(upper) < 2:
            p.setPen(QPen(QColor("#666"), 1))
            p.setFont(QFont("Arial", 10))
            p.drawText(ws_x + 10, ws_y + ws_h // 2 + 4, "≥ 2 points requis dans chaque courbe")
            p.end()
            return
        all_pts = lower + upper
        x0, x1 = min(pt[0] for pt in all_pts), max(pt[0] for pt in all_pts)
        y0, y1 = min(0.0, min(pt[1] for pt in all_pts)), max(pt[1] for pt in all_pts)
        if x1 == x0: x1 += 1
        if y1 == y0: y1 += 1
        def fx(v): return ws_x + (v - x0) / (x1 - x0) * ws_w
        def fy(v): return ws_y + ws_h - (v - y0) / (y1 - y0) * ws_h
        poly = QPolygonF()
        for x, y in lower:
            poly.append(QPointF(fx(x), fy(y)))
        for x, y in reversed(upper):
            poly.append(QPointF(fx(x), fy(y)))
        p.setPen(QPen(Qt.PenStyle.NoPen))
        p.setBrush(QColor(29, 158, 117, 50))
        p.drawPolygon(poly)
        p.setBrush(Qt.BrushStyle.NoBrush)
        for pts, color in [(lower, "#1D9E75"), (upper, "#E24B4A")]:
            p.setPen(QPen(QColor(color), 2))
            for i in range(len(pts) - 1):
                p.drawLine(int(fx(pts[i][0])), int(fy(pts[i][1])),
                           int(fx(pts[i + 1][0])), int(fy(pts[i + 1][1])))
        p.setPen(QPen(QColor("#666666"), 1))
        p.setFont(QFont("Arial", 9))
        p.drawText(ws_x, ws_y + ws_h + 13, "Aperçu ENVELOPPE  (vert = basse, rouge = haute)")
        p.end()


# ===========================================================================
# PMEditDialog — éditeur complet d'un Programme de Mesure
# ===========================================================================

class PMEditDialog(QDialog):
    """Dialog 900×620 avec 4 onglets : Général / NO-PASS / UNI-BOX / ENVELOPPE."""

    def __init__(self, pm_id: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pm_id = pm_id
        pm = PM_DEFINITIONS.get(pm_id)
        self._pm_name = pm.name if pm else f"PM-{pm_id:02d}"
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.setFixedSize(900, 620)
        self.setStyleSheet(_PM_EDIT_STYLE)
        self._build_ui()
        self._load_from_yaml()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        # Header
        header = QWidget()
        header.setFixedHeight(55)
        header.setStyleSheet("background-color: #252525;")
        hh = QHBoxLayout(header)
        hh.setContentsMargins(16, 0, 16, 0)
        hh.setSpacing(12)
        title = QLabel(f"📋  PM-{self._pm_id:02d} — {self._pm_name}")
        title.setStyleSheet(
            "font-size: 17px; font-weight: bold; color: #e0e0e0; background: transparent;"
        )
        hh.addWidget(title)
        hh.addStretch()
        btn_save = QPushButton("✓  Sauvegarder")
        btn_save.setObjectName("btn_save")
        btn_save.clicked.connect(self._save)
        hh.addWidget(btn_save)
        btn_cancel = QPushButton("✗  Annuler")
        btn_cancel.setObjectName("btn_cancel")
        btn_cancel.clicked.connect(self.reject)
        hh.addWidget(btn_cancel)
        root.addWidget(header)
        # Onglets
        tabs = QTabWidget()
        tabs.addTab(self._build_tab_general(),  "Général")
        tabs.addTab(self._build_tab_no_pass(),  "Outil NO-PASS")
        tabs.addTab(self._build_tab_uni_box(),  "Outil UNI-BOX")
        tabs.addTab(self._build_tab_envelope(), "Outil ENVELOPPE")
        root.addWidget(tabs, stretch=1)

    # ---- helpers ----------------------------------------------------------

    def _make_form(self, parent: QWidget) -> QFormLayout:
        f = QFormLayout(parent)
        f.setContentsMargins(24, 20, 24, 20)
        f.setSpacing(16)
        f.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        return f

    @staticmethod
    def _make_desc(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "background-color: #1a1a1a; border: 1px solid #333; border-radius: 6px; "
            "padding: 10px; font-size: 13px; color: #888888;"
        )
        lbl.setWordWrap(True)
        return lbl

    @staticmethod
    def _make_curve_table() -> QTableWidget:
        t = QTableWidget(6, 2)
        t.setHorizontalHeaderLabels(["Position mm", "Force N"])
        t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        t.verticalHeader().setVisible(False)
        return t

    @staticmethod
    def _add_row(table: QTableWidget) -> None:
        table.insertRow(table.rowCount())

    @staticmethod
    def _del_row(table: QTableWidget) -> None:
        row = table.currentRow()
        if row >= 0 and table.rowCount() > 1:
            table.removeRow(row)

    @staticmethod
    def _read_table(table: QTableWidget) -> list[list[float]]:
        pts: list[list[float]] = []
        for row in range(table.rowCount()):
            xi, yi = table.item(row, 0), table.item(row, 1)
            if xi and yi and xi.text() and yi.text():
                try:
                    pts.append([float(xi.text()), float(yi.text())])
                except ValueError:
                    pass
        return sorted(pts, key=lambda pt: pt[0])

    # ---- Onglet 1 — Général -----------------------------------------------

    def _build_tab_general(self) -> QWidget:
        w = QWidget()
        form = self._make_form(w)
        self._gen_name = QLineEdit()
        self._gen_name.setPlaceholderText("ex: PM01_STANDARD")
        form.addRow("Nom du PM :", self._gen_name)
        self._gen_desc = QLineEdit()
        self._gen_desc.setPlaceholderText("ex: Rivetage standard")
        form.addRow("Description :", self._gen_desc)
        self._gen_mode = QComboBox()
        self._gen_mode.addItem("Force = f(Position)", "FORCE_POSITION")
        self._gen_mode.addItem("Force = f(Temps)",    "FORCE_TIME")
        self._gen_mode.addItem("Position = f(Temps)", "POSITION_TIME")
        form.addRow("Mode d'affichage :", self._gen_mode)
        return w

    # ---- Onglet 2 — NO-PASS -----------------------------------------------

    def _build_tab_no_pass(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(20, 14, 20, 14)
        v.setSpacing(14)
        v.addWidget(self._make_desc(
            "Zone interdite : si la courbe passe dans cette zone, le cycle est NOK.\n"
            "Définir la plage de position (X) et la limite de force (Y) à ne pas dépasser."
        ))
        fw = QWidget()
        form = QFormLayout(fw)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._np_enabled = QCheckBox("Activer")
        form.addRow("Activer NO-PASS :", self._np_enabled)
        self._np_x_min = QDoubleSpinBox()
        self._np_x_min.setRange(0, 500); self._np_x_min.setDecimals(1); self._np_x_min.setSuffix(" mm")
        form.addRow("Position min (X) :", self._np_x_min)
        self._np_x_max = QDoubleSpinBox()
        self._np_x_max.setRange(0, 500); self._np_x_max.setDecimals(1); self._np_x_max.setSuffix(" mm")
        form.addRow("Position max (X) :", self._np_x_max)
        self._np_y_limit = QDoubleSpinBox()
        self._np_y_limit.setRange(0, 99999); self._np_y_limit.setDecimals(0); self._np_y_limit.setSuffix(" N")
        form.addRow("Force limite (Y) :", self._np_y_limit)
        v.addWidget(fw)
        v.addWidget(_NoPassPreview(self._np_x_min, self._np_x_max, self._np_y_limit))
        v.addStretch()
        return w

    # ---- Onglet 3 — UNI-BOX -----------------------------------------------

    def _build_tab_uni_box(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(20, 14, 20, 14)
        v.setSpacing(14)
        v.addWidget(self._make_desc(
            "Boîte de passage obligatoire : la courbe doit entrer et sortir par les côtés définis.\n"
            "Utile pour vérifier un point de force à une position donnée."
        ))
        fw = QWidget()
        form = QFormLayout(fw)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._ub_enabled = QCheckBox("Activer")
        form.addRow("Activer UNI-BOX :", self._ub_enabled)
        self._ub_x_min = QDoubleSpinBox()
        self._ub_x_min.setRange(0, 500); self._ub_x_min.setDecimals(1); self._ub_x_min.setSuffix(" mm")
        form.addRow("Position min boîte :", self._ub_x_min)
        self._ub_x_max = QDoubleSpinBox()
        self._ub_x_max.setRange(0, 500); self._ub_x_max.setDecimals(1); self._ub_x_max.setSuffix(" mm")
        form.addRow("Position max boîte :", self._ub_x_max)
        self._ub_y_min = QDoubleSpinBox()
        self._ub_y_min.setRange(0, 99999); self._ub_y_min.setDecimals(0); self._ub_y_min.setSuffix(" N")
        form.addRow("Force min boîte :", self._ub_y_min)
        self._ub_y_max = QDoubleSpinBox()
        self._ub_y_max.setRange(0, 99999); self._ub_y_max.setDecimals(0); self._ub_y_max.setSuffix(" N")
        form.addRow("Force max boîte :", self._ub_y_max)
        _SIDES = [("Gauche (left)", "left"), ("Droite (right)", "right"),
                  ("Bas (bottom)", "bottom"), ("Haut (top)", "top")]
        self._ub_entry = QComboBox()
        self._ub_exit = QComboBox()
        for lbl, val in _SIDES:
            self._ub_entry.addItem(lbl, val)
            self._ub_exit.addItem(lbl, val)
        form.addRow("Côté d'entrée :", self._ub_entry)
        form.addRow("Côté de sortie :", self._ub_exit)
        v.addWidget(fw)
        v.addWidget(_UniBoxPreview(
            self._ub_x_min, self._ub_x_max, self._ub_y_min, self._ub_y_max,
            self._ub_entry, self._ub_exit,
        ))
        v.addStretch()
        return w

    # ---- Onglet 4 — ENVELOPPE ---------------------------------------------

    def _build_tab_envelope(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(10)
        self._env_enabled = QCheckBox("Activer l'outil ENVELOPPE")
        v.addWidget(self._env_enabled)
        v.addWidget(self._make_desc(
            "La courbe doit rester entre la limite basse et la limite haute "
            "sur toute la plage de position."
        ))
        cols = QHBoxLayout()
        cols.setSpacing(16)
        for attr, label_text, color, defaults in [
            ("_env_lower_table", "Limite basse", "#1D9E75", [("0","0"),("100","3000")]),
            ("_env_upper_table", "Limite haute", "#E24B4A", [("0","500"),("100","5000")]),
        ]:
            col_w = QWidget()
            col_v = QVBoxLayout(col_w)
            col_v.setContentsMargins(0, 0, 0, 0)
            col_v.setSpacing(6)
            lbl = QLabel(label_text)
            lbl.setStyleSheet(
                f"font-size: 14px; font-weight: bold; color: {color}; background: transparent;"
            )
            col_v.addWidget(lbl)
            table = self._make_curve_table()
            for row, (xv, yv) in enumerate(defaults):
                table.setItem(row, 0, QTableWidgetItem(xv))
                table.setItem(row, 1, QTableWidgetItem(yv))
            setattr(self, attr, table)
            col_v.addWidget(table, stretch=1)
            btn_add = QPushButton("+ Ajouter point")
            btn_add.setObjectName("action_btn")
            btn_del = QPushButton("- Supprimer")
            btn_del.setObjectName("action_btn")
            btn_add.clicked.connect(lambda _, t=table: self._add_row(t))
            btn_del.clicked.connect(lambda _, t=table: self._del_row(t))
            br = QHBoxLayout()
            br.addWidget(btn_add)
            br.addWidget(btn_del)
            col_v.addLayout(br)
            cols.addWidget(col_w)
        v.addLayout(cols, stretch=1)
        env_preview = _EnvelopePreview(self._env_lower_table, self._env_upper_table)
        env_preview.setFixedHeight(180)
        self._env_lower_table.cellChanged.connect(env_preview.update)
        self._env_upper_table.cellChanged.connect(env_preview.update)
        v.addWidget(env_preview)
        return w

    # ---- Chargement -------------------------------------------------------

    def _load_from_yaml(self) -> None:
        pm = PM_DEFINITIONS.get(self._pm_id)
        if pm:
            self._gen_name.setText(pm.name)
            self._gen_desc.setText(pm.description)
            idx = self._gen_mode.findData(pm.view_mode)
            if idx >= 0:
                self._gen_mode.setCurrentIndex(idx)
        try:
            with open(_CONFIG_PATH, encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
        except (FileNotFoundError, yaml.YAMLError):
            return
        tools = cfg.get("programmes", {}).get(self._pm_id, {}).get("tools", {})
        np_d = tools.get("no_pass", {})
        if np_d:
            self._np_enabled.setChecked(bool(np_d.get("enabled", False)))
            self._np_x_min.setValue(float(np_d.get("x_min", 0.0)))
            self._np_x_max.setValue(float(np_d.get("x_max", 0.0)))
            self._np_y_limit.setValue(float(np_d.get("y_limit", 0.0)))
        ub_d = tools.get("uni_box", {})
        if ub_d:
            self._ub_enabled.setChecked(bool(ub_d.get("enabled", False)))
            self._ub_x_min.setValue(float(ub_d.get("box_x_min", 0.0)))
            self._ub_x_max.setValue(float(ub_d.get("box_x_max", 0.0)))
            self._ub_y_min.setValue(float(ub_d.get("box_y_min", 0.0)))
            self._ub_y_max.setValue(float(ub_d.get("box_y_max", 0.0)))
            for combo, key in [(self._ub_entry, "entry_side"), (self._ub_exit, "exit_side")]:
                idx = combo.findData(ub_d.get(key, "left"))
                if idx >= 0:
                    combo.setCurrentIndex(idx)
        env_d = tools.get("envelope", {})
        if env_d:
            self._env_enabled.setChecked(bool(env_d.get("enabled", False)))
            for table, key in [(self._env_lower_table, "lower_curve"),
                               (self._env_upper_table, "upper_curve")]:
                pts = env_d.get(key, [])
                if pts:
                    table.blockSignals(True)
                    table.setRowCount(max(len(pts), 6))
                    for i, pt in enumerate(pts):
                        table.setItem(i, 0, QTableWidgetItem(str(pt[0])))
                        table.setItem(i, 1, QTableWidgetItem(str(pt[1])))
                    table.blockSignals(False)

    # ---- Sauvegarde -------------------------------------------------------

    def _save(self) -> None:
        try:
            with open(_CONFIG_PATH, encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
        except (FileNotFoundError, yaml.YAMLError):
            cfg = {}
        cfg.setdefault("programmes", {})
        cfg["programmes"][self._pm_id] = {
            "name":        self._gen_name.text(),
            "description": self._gen_desc.text(),
            "view_mode":   self._gen_mode.currentData(),
            "tools": {
                "no_pass": {
                    "enabled": self._np_enabled.isChecked(),
                    "x_min":   self._np_x_min.value(),
                    "x_max":   self._np_x_max.value(),
                    "y_limit": self._np_y_limit.value(),
                },
                "uni_box": {
                    "enabled":    self._ub_enabled.isChecked(),
                    "box_x_min":  self._ub_x_min.value(),
                    "box_x_max":  self._ub_x_max.value(),
                    "box_y_min":  self._ub_y_min.value(),
                    "box_y_max":  self._ub_y_max.value(),
                    "entry_side": self._ub_entry.currentData(),
                    "exit_side":  self._ub_exit.currentData(),
                },
                "envelope": {
                    "enabled":     self._env_enabled.isChecked(),
                    "lower_curve": self._read_table(self._env_lower_table),
                    "upper_curve": self._read_table(self._env_upper_table),
                },
            },
        }
        with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)
        from config import ProgramMeasure
        PM_DEFINITIONS[self._pm_id] = ProgramMeasure(
            pm_id=self._pm_id,
            name=self._gen_name.text(),
            description=self._gen_desc.text(),
            view_mode=self._gen_mode.currentData(),
        )
        QMessageBox.information(self, "PM sauvegardé", f"✓ PM-{self._pm_id:02d} sauvegardé.")
        self.accept()


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

        self._pm_list = QListWidget()
        for pm_id, pm in PM_DEFINITIONS.items():
            self._pm_list.addItem(f"PM-{pm_id:02d}   ·   {pm.name}")
        self._pm_list.itemDoubleClicked.connect(self._on_pm_double_click)
        v.addWidget(self._pm_list, stretch=1)
        return page

    def _on_pm_double_click(self, item) -> None:
        row = self._pm_list.row(item)
        pm_id = row + 1
        dlg = PMEditDialog(pm_id, self)
        dlg.exec()
        item.setText(f"PM-{pm_id:02d}   ·   {PM_DEFINITIONS[pm_id].name}")

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