"""Page de réglages — intégrée dans self.stack de MainWindow (index 1).

Architecture QStackedWidget interne (self._settings_stack) :
  Page 0 : Accueil Réglages   (3 grandes tuiles de navigation)
  Page 1 : Paramètres généraux (grille 3×3 de boutons)
  Page 2 : Réglage PM          (liste des 16 PM)
  Page 3 : Gestionnaire PM     (tableau + actions)

Chaque page enfant a son propre header avec titre + bouton ← Retour.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QPointF, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QButtonGroup,
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
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config import PM_DEFINITIONS, ProgramMeasure
from ihm.ui_utils import load_config, save_config

_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


# ---------------------------------------------------------------------------
# Helpers clavier virtuel (NumpadDialog / AlphaNumpadDialog)
# ---------------------------------------------------------------------------

def _make_numpad_btn(
    value: str,
    suffix: str = "",
    title: str = "Saisie",
    parent=None,
) -> QPushButton:
    """Crée un QPushButton qui ouvre NumpadDialog au clic."""
    from ihm.main_window import NumpadDialog

    btn = QPushButton(f"{value}{suffix}")
    btn.setProperty("numpad_value", value)
    btn.setProperty("numpad_suffix", suffix)
    btn.setStyleSheet("""
        QPushButton {
            background-color: #444444;
            color: #ffffff;
            border: 1.5px solid #555555;
            border-radius: 6px;
            padding: 6px 12px;
            font-size: 15px;
            min-height: 42px;
            text-align: right;
        }
        QPushButton:pressed { border-color: #C49A3C; }
    """)

    def _open_numpad():
        dlg = NumpadDialog(
            title=title,
            unit=suffix.strip(),
            value=btn.property("numpad_value") or "",
            parent=parent,
        )
        if dlg.exec():
            v = dlg.value()
            btn.setProperty("numpad_value", v)
            btn.setText(f"{v}{suffix}")

    btn.clicked.connect(_open_numpad)
    return btn


def _get_numpad_value(btn: QPushButton, default: float = 0.0) -> float:
    """Lit la valeur float stockée dans un bouton numpad."""
    try:
        return float(btn.property("numpad_value") or default)
    except (ValueError, TypeError):
        return default


def _make_alpha_btn(
    value: str,
    title: str = "Saisie texte",
    parent=None,
) -> QPushButton:
    """Crée un QPushButton qui ouvre AlphaNumpadDialog au clic."""
    from ihm.main_window import AlphaNumpadDialog

    btn = QPushButton(value or "—")
    btn.setProperty("alpha_value", value)
    btn.setStyleSheet("""
        QPushButton {
            background-color: #444444;
            color: #ffffff;
            border: 1.5px solid #555555;
            border-radius: 6px;
            padding: 6px 12px;
            font-size: 15px;
            min-height: 42px;
            text-align: left;
        }
        QPushButton:pressed { border-color: #C49A3C; }
    """)

    def _open_alpha():
        dlg = AlphaNumpadDialog(
            title=title,
            value=btn.property("alpha_value") or "",
            parent=parent,
        )
        if dlg.exec():
            v = dlg.value()
            btn.setProperty("alpha_value", v)
            btn.setText(v or "—")

    btn.clicked.connect(_open_alpha)
    return btn


def _get_alpha_value(btn: QPushButton) -> str:
    return btn.property("alpha_value") or ""


# ---------------------------------------------------------------------------
# Palette de couleurs — thème sombre identique à main_window
# ---------------------------------------------------------------------------
_C = {
    "bg":         "#2E2E2E",
    "panel":      "#3A3A3A",
    "card":       "#444444",
    "border":     "#555555",
    "header_bg":  "#3A3A3A",
    "text":       "#F0F0F0",
    "text_dim":   "#AAAAAA",
    "btn_bg":     "#444444",
    "btn_border": "#555555",
    "btn_active": "#A07830",
    "ok_green":   "#4caf50",
    "nok_red":    "#ef5350",
    "blue":       "#C49A3C",
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
    background-color: {_C['card']};
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
    background-color: #3A3A3A;
    color: #F0F0F0;
    font-family: 'Segoe UI', Arial, sans-serif;
}
QLabel {
    background-color: transparent;
    font-size: 15px;
    color: #F0F0F0;
}
QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox {
    background-color: #444444;
    color: #F0F0F0;
    border: 1.5px solid #555555;
    border-radius: 6px;
    padding: 6px;
    font-size: 15px;
    min-height: 42px;
}
QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus {
    border-color: #C49A3C;
}
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView {
    background-color: #444444;
    color: #F0F0F0;
    selection-background-color: #A07830;
}
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button,
QSpinBox::up-button,       QSpinBox::down-button {
    background-color: #555555;
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
QPushButton#btn_nav {
    background-color: #A07830;
    color: #ffffff;
    font-size: 14px;
    font-weight: bold;
    border: none;
    border-radius: 8px;
    min-height: 44px;
    min-width: 120px;
}
QPushButton#btn_nav:pressed { background-color: #7a5c24; }
QPushButton#btn_nav:disabled { background-color: #444444; color: #777777; }
QCheckBox {
    font-size: 15px; color: #F0F0F0; spacing: 8px;
    min-height: 42px; background: transparent;
}
QCheckBox::indicator {
    width: 22px; height: 22px; background-color: #444444;
    border: 1.5px solid #555555; border-radius: 4px;
}
QCheckBox::indicator:checked { background-color: #085041; border-color: #1D9E75; }
"""


# ---------------------------------------------------------------------------
# Style QTabWidget pour PMEditDialog
# ---------------------------------------------------------------------------
_PM_EDIT_STYLE = _DIALOG_STYLE + """
QTabWidget::pane { background-color: #3A3A3A; border: none; }
QTabBar::tab {
    background: #444444; color: #AAAAAA; padding: 10px 20px;
    font-size: 14px; border-radius: 6px 6px 0 0; margin-right: 2px;
}
QTabBar::tab:selected { background: #3A3A3A; color: #ffffff; border-bottom: 2px solid #C49A3C; }
QCheckBox {
    font-size: 15px; color: #F0F0F0; spacing: 8px;
    min-height: 42px; background: transparent;
}
QCheckBox::indicator {
    width: 22px; height: 22px; background-color: #444444;
    border: 1.5px solid #555555; border-radius: 4px;
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

class _PMEditPage(QWidget):
    """Page 4 onglets : Général / NO-PASS / UNI-BOX / ENVELOPPE (intégrée dans _settings_stack)."""

    def __init__(
        self,
        stack: QStackedWidget,
        on_after_save=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._main_stack = stack
        self._on_after_save_cb = on_after_save or (lambda pm_id: None)
        self._pm_id = 1
        self._pm_name = "PM-01"
        self.setStyleSheet(_PM_EDIT_STYLE)
        self._build_ui()

    def load_pm(self, pm_id: int) -> None:
        """Charge les données du PM pm_id et prépare la page avant navigation."""
        self._pm_id = pm_id
        pm = PM_DEFINITIONS.get(pm_id)
        self._pm_name = pm.name if pm else f"PM-{pm_id:02d}"
        self._title_lbl.setText(f"📋  PM-{pm_id:02d} — {self._pm_name}")
        self._load_from_yaml()

    def _cancel(self) -> None:
        self._main_stack.setCurrentIndex(2)

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
        self._title_lbl = QLabel(f"📋  PM-{self._pm_id:02d} — {self._pm_name}")
        self._title_lbl.setStyleSheet(
            "font-size: 17px; font-weight: bold; color: #e0e0e0; background: transparent;"
        )
        hh.addWidget(self._title_lbl)
        hh.addStretch()
        btn_save = QPushButton("✓  Sauvegarder")
        btn_save.setObjectName("btn_save")
        btn_save.clicked.connect(self._save)
        hh.addWidget(btn_save)
        btn_cancel = QPushButton("✗  Annuler")
        btn_cancel.setObjectName("btn_cancel")
        btn_cancel.clicked.connect(self._cancel)
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
        self._gen_name = _make_alpha_btn("", title="Nom du PM", parent=self)
        form.addRow("Nom du PM :", self._gen_name)
        self._gen_desc = _make_alpha_btn("", title="Description", parent=self)
        form.addRow("Description :", self._gen_desc)
        self._gen_mode = QComboBox()
        self._gen_mode.addItem("Force = f(Position)", "FORCE_POSITION")
        self._gen_mode.addItem("Force = f(Temps)",    "FORCE_TIME")
        self._gen_mode.addItem("Position = f(Temps)", "POSITION_TIME")
        form.addRow("Mode d'affichage :", self._gen_mode)
        return w

    # ---- Onglet 2 — NO-PASS -----------------------------------------------

    def _build_tab_no_pass(self) -> QWidget:
        outer = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
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
        self._np_x_min = _make_numpad_btn("0.0", suffix=" mm", title="Position min (X)", parent=self)
        form.addRow("Position min (X) :", self._np_x_min)
        self._np_x_max = _make_numpad_btn("0.0", suffix=" mm", title="Position max (X)", parent=self)
        form.addRow("Position max (X) :", self._np_x_max)
        self._np_y_limit = _make_numpad_btn("0", suffix=" N", title="Force limite (Y)", parent=self)
        form.addRow("Force limite (Y) :", self._np_y_limit)
        v.addWidget(fw)
        v.addStretch()
        scroll.setWidget(w)
        out_v = QVBoxLayout(outer)
        out_v.setContentsMargins(0, 0, 0, 0)
        out_v.addWidget(scroll)
        return outer

    # ---- Onglet 3 — UNI-BOX -----------------------------------------------

    def _build_tab_uni_box(self) -> QWidget:
        outer = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
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
        self._ub_x_min = _make_numpad_btn("0.0", suffix=" mm", title="Position min boîte", parent=self)
        form.addRow("Position min boîte :", self._ub_x_min)
        self._ub_x_max = _make_numpad_btn("0.0", suffix=" mm", title="Position max boîte", parent=self)
        form.addRow("Position max boîte :", self._ub_x_max)
        self._ub_y_min = _make_numpad_btn("0", suffix=" N", title="Force min boîte", parent=self)
        form.addRow("Force min boîte :", self._ub_y_min)
        self._ub_y_max = _make_numpad_btn("0", suffix=" N", title="Force max boîte", parent=self)
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
        v.addStretch()
        scroll.setWidget(w)
        out_v = QVBoxLayout(outer)
        out_v.setContentsMargins(0, 0, 0, 0)
        out_v.addWidget(scroll)
        return outer

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
            self._gen_name.setProperty("alpha_value", pm.name)
            self._gen_name.setText(pm.name or "—")
            self._gen_desc.setProperty("alpha_value", pm.description)
            self._gen_desc.setText(pm.description or "—")
            idx = self._gen_mode.findData(pm.view_mode)
            if idx >= 0:
                self._gen_mode.setCurrentIndex(idx)
        cfg = load_config(_CONFIG_PATH)
        if not cfg:
            return
        tools = cfg.get("programmes", {}).get(self._pm_id, {}).get("tools", {})
        np_d = tools.get("no_pass", {})
        if np_d:
            self._np_enabled.setChecked(bool(np_d.get("enabled", False)))
            for btn, key in [
                (self._np_x_min, "x_min"),
                (self._np_x_max, "x_max"),
                (self._np_y_limit, "y_limit"),
            ]:
                v = str(np_d.get(key, 0.0))
                suffix = btn.property("numpad_suffix") or ""
                btn.setProperty("numpad_value", v)
                btn.setText(f"{v}{suffix}")
        ub_d = tools.get("uni_box", {})
        if ub_d:
            self._ub_enabled.setChecked(bool(ub_d.get("enabled", False)))
            for btn, key in [
                (self._ub_x_min, "box_x_min"),
                (self._ub_x_max, "box_x_max"),
                (self._ub_y_min, "box_y_min"),
                (self._ub_y_max, "box_y_max"),
            ]:
                v = str(ub_d.get(key, 0.0))
                suffix = btn.property("numpad_suffix") or ""
                btn.setProperty("numpad_value", v)
                btn.setText(f"{v}{suffix}")
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
        cfg = load_config(_CONFIG_PATH)
        cfg.setdefault("programmes", {})
        cfg["programmes"][self._pm_id] = {
            "name":        _get_alpha_value(self._gen_name),
            "description": _get_alpha_value(self._gen_desc),
            "view_mode":   self._gen_mode.currentData(),
            "tools": {
                "no_pass": {
                    "enabled": self._np_enabled.isChecked(),
                    "x_min":   _get_numpad_value(self._np_x_min),
                    "x_max":   _get_numpad_value(self._np_x_max),
                    "y_limit": _get_numpad_value(self._np_y_limit),
                },
                "uni_box": {
                    "enabled":    self._ub_enabled.isChecked(),
                    "box_x_min":  _get_numpad_value(self._ub_x_min),
                    "box_x_max":  _get_numpad_value(self._ub_x_max),
                    "box_y_min":  _get_numpad_value(self._ub_y_min),
                    "box_y_max":  _get_numpad_value(self._ub_y_max),
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
        save_config(_CONFIG_PATH, cfg)
        PM_DEFINITIONS[self._pm_id] = ProgramMeasure(
            pm_id=self._pm_id,
            name=_get_alpha_value(self._gen_name),
            description=_get_alpha_value(self._gen_desc),
            view_mode=self._gen_mode.currentData(),
        )
        QMessageBox.information(self, "PM sauvegardé", f"✓ PM-{self._pm_id:02d} sauvegardé.")
        self._main_stack.setCurrentIndex(2)
        self._on_after_save_cb(self._pm_id)


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
# Constantes de choix — dialogues Voie X / Voie Y
# ===========================================================================

_DECIMAL_CHOICES  = ["0", "1", "2", "3", "4"]
_SENSOR_TYPES_X   = ["Linéaire", "Rotatif", "Angulaire", "Impulsion"]
_UNITS_X          = ["mm", "cm", "°", "pulse", "µm", "in"]
_UNITS_Y          = ["N", "kN", "kg", "lbf"]
_FILTER_CHOICES   = ["Aucun", "50 Hz", "100 Hz", "200 Hz", "500 Hz"]
_SCALE_METHODS    = ["Sensibilité", "2 points"]


# ---------------------------------------------------------------------------
# _ChoiceDialog — sélecteur tactile (liste de boutons)
# ---------------------------------------------------------------------------

class _ChoiceDialog(QDialog):
    """Sélecteur plein-écran tactile : affiche une liste de boutons."""

    def __init__(
        self,
        choices: list[str],
        current: str,
        title: str = "Choisir",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.setStyleSheet(_DIALOG_STYLE)
        self._value = current

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        hdr = QWidget()
        hdr.setFixedHeight(46)
        hdr.setStyleSheet("background-color: #252525;")
        hh = QHBoxLayout(hdr)
        hh.setContentsMargins(16, 0, 16, 0)
        lbl = QLabel(title)
        lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #e0e0e0;")
        hh.addWidget(lbl)
        root.addWidget(hdr)

        # Boutons de choix
        for c in choices:
            b = QPushButton(c)
            b.setMinimumHeight(48)
            bg = "#185FA5" if c == current else "#2a2a2a"
            b.setStyleSheet(
                f"background-color: {bg}; color: #e0e0e0; font-size: 15px;"
                " border: none; border-bottom: 1px solid #333;"
                " text-align: left; padding-left: 16px;"
            )
            b.clicked.connect(lambda _chk, v=c: self._pick(v))
            root.addWidget(b)

        # Annuler
        btn_x = QPushButton("✗  Fermer")
        btn_x.setObjectName("btn_cancel")
        btn_x.clicked.connect(self.reject)
        root.addWidget(btn_x)

        self.setFixedSize(320, 46 + len(choices) * 48 + 54)

    def _pick(self, v: str) -> None:
        self._value = v
        self.accept()

    def value(self) -> str:
        return self._value


# ---------------------------------------------------------------------------
# _make_choice_btn — bouton tactile ouvrant _ChoiceDialog
# ---------------------------------------------------------------------------

def _make_choice_btn(
    choices: list[str],
    current: str,
    title: str,
    parent: QWidget | None = None,
) -> QPushButton:
    """Retourne un QPushButton qui ouvre _ChoiceDialog au clic."""
    btn = QPushButton(current)
    btn.setProperty("choice_value", current)
    btn.setMinimumHeight(42)

    def _open(_chk: bool = False) -> None:
        dlg = _ChoiceDialog(choices, btn.property("choice_value") or current, title, parent)
        if dlg.exec():
            v = dlg.value()
            btn.setProperty("choice_value", v)
            btn.setText(v)

    btn.clicked.connect(_open)
    return btn


# ===========================================================================
# VoieXDialog — configuration Voie X (Position)
# ===========================================================================

class _VoieXPage(QWidget):
    """Page 2 pages — configuration Voie X (intégrée dans _settings_stack).

    Page 0 : Déclaration capteur (nom, type, unité, canal, décimales)
    Page 1 : Mise à l'échelle 2 points (table affichage / signal%)
    """

    def __init__(self, stack: QStackedWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._main_stack = stack
        self.setStyleSheet(_DIALOG_STYLE)
        self._build_ui()
        self._load_config()

    def showEvent(self, event) -> None:
        self._load_config()
        super().showEvent(event)

    def _cancel(self) -> None:
        self._main_stack.setCurrentIndex(1)

    # ------------------------------------------------------------------
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
        self._header_lbl = QLabel("Voie X — Déclaration capteur")
        self._header_lbl.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: #e0e0e0; background: transparent;"
        )
        hh.addWidget(self._header_lbl)
        root.addWidget(header)

        # Contenu (2 pages)
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_page0())
        self._stack.addWidget(self._build_page1())
        root.addWidget(self._stack, stretch=1)

        # Footer (2 états)
        self._footer = QStackedWidget()
        self._footer.setFixedHeight(64)
        self._footer.addWidget(self._build_footer0())
        self._footer.addWidget(self._build_footer1())
        root.addWidget(self._footer)

    def _build_page0(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(24, 18, 24, 18)
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._name_btn = _make_alpha_btn("", title="Nom du capteur", parent=self)
        form.addRow("Nom du capteur :", self._name_btn)

        self._sensor_type_btn = _make_choice_btn(
            _SENSOR_TYPES_X, "Linéaire", "Type de capteur", self
        )
        form.addRow("Type de capteur :", self._sensor_type_btn)

        self._unit_btn = _make_choice_btn(_UNITS_X, "mm", "Unité", self)
        form.addRow("Unité :", self._unit_btn)

        self._channel_btn = _make_numpad_btn(
            "1", suffix="", title="Canal MCC 118 (0-7)", parent=self
        )
        form.addRow("Canal MCC 118 :", self._channel_btn)

        self._decimal_btn = _make_choice_btn(_DECIMAL_CHOICES, "2", "Décimales", self)
        form.addRow("Décimales :", self._decimal_btn)

        return w

    def _build_page1(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(24, 16, 24, 16)
        v.setSpacing(12)

        lbl = QLabel("Mise à l'échelle — 2 points")
        lbl.setStyleSheet("font-size: 14px; color: #888888; font-weight: bold;")
        v.addWidget(lbl)

        grid = QGridLayout()
        grid.setSpacing(8)

        # En-têtes colonnes
        for col, txt in enumerate(["", "Affichage", "Signal  %", ""], start=0):
            lc = QLabel(txt)
            lc.setStyleSheet("font-size: 13px; color: #888888;")
            lc.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(lc, 0, col)

        # Point 1
        grid.addWidget(QLabel("Point 1"), 1, 0)
        self._p1_display = _make_numpad_btn(
            "0.0", suffix="", title="Point 1 — Affichage", parent=self
        )
        grid.addWidget(self._p1_display, 1, 1)
        self._p1_signal = _make_numpad_btn(
            "0.0", suffix=" %", title="Point 1 — Signal %", parent=self
        )
        grid.addWidget(self._p1_signal, 1, 2)
        btn_t1 = QPushButton("TEACH")
        btn_t1.setObjectName("btn_nav")
        btn_t1.setEnabled(False)
        grid.addWidget(btn_t1, 1, 3)

        # Point 2
        grid.addWidget(QLabel("Point 2"), 2, 0)
        self._p2_display = _make_numpad_btn(
            "100.0", suffix="", title="Point 2 — Affichage", parent=self
        )
        grid.addWidget(self._p2_display, 2, 1)
        self._p2_signal = _make_numpad_btn(
            "100.0", suffix=" %", title="Point 2 — Signal %", parent=self
        )
        grid.addWidget(self._p2_signal, 2, 2)
        btn_t2 = QPushButton("TEACH")
        btn_t2.setObjectName("btn_nav")
        btn_t2.setEnabled(False)
        grid.addWidget(btn_t2, 2, 3)

        v.addLayout(grid)
        v.addStretch()
        return w

    def _build_footer0(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background-color: #181818;")
        h = QHBoxLayout(w)
        h.setContentsMargins(24, 10, 24, 10)
        h.setSpacing(16)
        btn_cancel = QPushButton("✗  Annuler")
        btn_cancel.setObjectName("btn_cancel")
        btn_cancel.clicked.connect(self._cancel)
        h.addWidget(btn_cancel)
        h.addStretch()
        btn_next = QPushButton("Suivant  →")
        btn_next.setObjectName("btn_nav")
        btn_next.clicked.connect(self._go_page1)
        h.addWidget(btn_next)
        return w

    def _build_footer1(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background-color: #181818;")
        h = QHBoxLayout(w)
        h.setContentsMargins(24, 10, 24, 10)
        h.setSpacing(16)
        btn_back = QPushButton("←  Retour")
        btn_back.setObjectName("btn_cancel")
        btn_back.clicked.connect(self._go_page0)
        h.addWidget(btn_back)
        h.addStretch()
        btn_save = QPushButton("✓  Sauvegarder")
        btn_save.setObjectName("btn_save")
        btn_save.clicked.connect(self._save)
        h.addWidget(btn_save)
        return w

    def _go_page0(self) -> None:
        self._stack.setCurrentIndex(0)
        self._footer.setCurrentIndex(0)
        self._header_lbl.setText("Voie X — Déclaration capteur")

    def _go_page1(self) -> None:
        self._stack.setCurrentIndex(1)
        self._footer.setCurrentIndex(1)
        self._header_lbl.setText("Voie X — Mise à l'échelle")

    # ------------------------------------------------------------------
    def _load_config(self) -> None:
        cfg = load_config(_CONFIG_PATH)
        if not cfg:
            return

        scaling = cfg.get("scaling", {})
        acq = cfg.get("acquisition", {})
        cal = cfg.get("calibration", {}).get("voie_x", {})

        name = scaling.get("position_name", "")
        self._name_btn.setProperty("alpha_value", name)
        self._name_btn.setText(name or "—")

        for btn, val, default in [
            (self._sensor_type_btn, scaling.get("position_sensor_type"), "Linéaire"),
            (self._unit_btn,        scaling.get("position_unit"),        "mm"),
            (self._decimal_btn,     str(scaling.get("position_decimal", 2)), "2"),
        ]:
            v = val or default
            btn.setProperty("choice_value", v)
            btn.setText(v)

        ch = str(acq.get("position_channel", 1))
        self._channel_btn.setProperty("numpad_value", ch)
        self._channel_btn.setText(ch)

        for btn, key, default in [
            (self._p1_display, "p1_display", "0.0"),
            (self._p1_signal,  "p1_signal",  "0.0"),
            (self._p2_display, "p2_display", "100.0"),
            (self._p2_signal,  "p2_signal",  "100.0"),
        ]:
            val = str(cal.get(key, default))
            sfx = btn.property("numpad_suffix") or ""
            btn.setProperty("numpad_value", val)
            btn.setText(f"{val}{sfx}")

    def _save(self) -> None:
        cfg = load_config(_CONFIG_PATH)
        cfg.setdefault("scaling", {})
        cfg.setdefault("acquisition", {})
        cfg.setdefault("calibration", {})
        cfg["calibration"].setdefault("voie_x", {})

        cfg["scaling"]["position_name"] = _get_alpha_value(self._name_btn)
        cfg["scaling"]["position_sensor_type"] = (
            self._sensor_type_btn.property("choice_value") or "Linéaire"
        )
        cfg["scaling"]["position_unit"] = self._unit_btn.property("choice_value") or "mm"
        cfg["scaling"]["position_decimal"] = int(
            self._decimal_btn.property("choice_value") or "2"
        )
        cfg["scaling"]["position_mm_max"] = _get_numpad_value(self._p2_display)
        cfg["acquisition"]["position_channel"] = int(_get_numpad_value(self._channel_btn))

        cal = cfg["calibration"]["voie_x"]
        cal["p1_display"] = _get_numpad_value(self._p1_display)
        cal["p1_signal"]  = _get_numpad_value(self._p1_signal)
        cal["p2_display"] = _get_numpad_value(self._p2_display)
        cal["p2_signal"]  = _get_numpad_value(self._p2_signal)

        save_config(_CONFIG_PATH, cfg)
        QMessageBox.information(
            self, "Voie X",
            "✓ Configuration Voie X sauvegardée.\nRedémarrez pour appliquer.",
        )
        self._main_stack.setCurrentIndex(1)


# ===========================================================================
# VoieYDialog — configuration Voie Y (Force)
# ===========================================================================

class _VoieYPage(QWidget):
    """Page 2 pages — configuration Voie Y (intégrée dans _settings_stack).

    Page 0 : Déclaration capteur (nom, unité, force max, canal, décimales)
    Page 1 : Sensibilité piézo (méthode, sensibilité, alarme, Avancé ▼)
    """

    def __init__(self, stack: QStackedWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._main_stack = stack
        self.setStyleSheet(_DIALOG_STYLE)
        self._build_ui()
        self._load_config()

    def showEvent(self, event) -> None:
        self._load_config()
        super().showEvent(event)

    def _cancel(self) -> None:
        self._main_stack.setCurrentIndex(1)

    # ------------------------------------------------------------------
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
        self._header_lbl = QLabel("Voie Y — Déclaration capteur")
        self._header_lbl.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: #e0e0e0; background: transparent;"
        )
        hh.addWidget(self._header_lbl)
        root.addWidget(header)

        # Contenu (2 pages)
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_page0())
        self._stack.addWidget(self._build_page1())
        root.addWidget(self._stack, stretch=1)

        # Footer (2 états)
        self._footer = QStackedWidget()
        self._footer.setFixedHeight(64)
        self._footer.addWidget(self._build_footer0())
        self._footer.addWidget(self._build_footer1())
        root.addWidget(self._footer)

    def _build_page0(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(24, 18, 24, 18)
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._name_btn = _make_alpha_btn("", title="Nom du capteur", parent=self)
        form.addRow("Nom du capteur :", self._name_btn)

        # Type fixe piézo
        btn_piezo = QPushButton("Piézoélectrique")
        btn_piezo.setObjectName("btn_nav")
        btn_piezo.setEnabled(False)
        form.addRow("Type de capteur :", btn_piezo)

        self._unit_btn = _make_choice_btn(_UNITS_Y, "N", "Unité", self)
        form.addRow("Unité :", self._unit_btn)

        self._max_btn = _make_numpad_btn(
            "5000.0", suffix="", title="Force max (pleine échelle)", parent=self
        )
        form.addRow("Force max :", self._max_btn)

        self._channel_btn = _make_numpad_btn(
            "0", suffix="", title="Canal MCC 118 (0-7)", parent=self
        )
        form.addRow("Canal MCC 118 :", self._channel_btn)

        self._decimal_btn = _make_choice_btn(_DECIMAL_CHOICES, "1", "Décimales", self)
        form.addRow("Décimales :", self._decimal_btn)

        return w

    def _build_page1(self) -> QWidget:
        inner = QWidget()
        v = QVBoxLayout(inner)
        v.setContentsMargins(24, 16, 24, 16)
        v.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._scale_method_btn = _make_choice_btn(
            _SCALE_METHODS, "Sensibilité", "Méthode d'échelle", self
        )
        form.addRow("Méthode d'échelle :", self._scale_method_btn)

        self._sensitivity_btn = _make_numpad_btn(
            "-10.0", suffix=" pC/N", title="Sensibilité (pC/N)", parent=self
        )
        form.addRow("Sensibilité :", self._sensitivity_btn)

        self._alarm_btn = _make_numpad_btn(
            "4500.0", suffix="", title="Seuil d'alarme", parent=self
        )
        form.addRow("Seuil d'alarme :", self._alarm_btn)

        self._invert_chk = QCheckBox("Inverser le signal")
        form.addRow("", self._invert_chk)

        v.addLayout(form)

        # Section Avancé (collapsible)
        self._avance_toggle = QPushButton("Avancé  ▼")
        self._avance_toggle.setStyleSheet(
            "background: transparent; color: #378ADD; font-size: 14px;"
            " font-weight: bold; border: none; text-align: left; padding: 4px 0;"
        )
        self._avance_toggle.clicked.connect(self._toggle_avance)
        v.addWidget(self._avance_toggle)

        self._avance_w = QWidget()
        av = QFormLayout(self._avance_w)
        av.setContentsMargins(0, 4, 0, 4)
        av.setSpacing(12)
        av.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._filter_btn = _make_choice_btn(_FILTER_CHOICES, "Aucun", "Filtre", self)
        av.addRow("Filtre :", self._filter_btn)

        self._couple_dcy_chk = QCheckBox("Couple DCY")
        av.addRow("", self._couple_dcy_chk)

        self._test_point_btn = _make_numpad_btn(
            "0.0", suffix="", title="Point de test", parent=self
        )
        av.addRow("Point de test :", self._test_point_btn)

        self._tolerance_btn = _make_numpad_btn(
            "5.0", suffix=" %", title="Tolérance (%)", parent=self
        )
        av.addRow("Tolérance :", self._tolerance_btn)

        self._test_tor_chk = QCheckBox("Test TOR")
        av.addRow("", self._test_tor_chk)

        self._avance_w.setVisible(False)
        v.addWidget(self._avance_w)
        v.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(inner)
        return scroll

    def _toggle_avance(self) -> None:
        vis = self._avance_w.isVisible()
        self._avance_w.setVisible(not vis)
        self._avance_toggle.setText("Avancé  ▲" if not vis else "Avancé  ▼")

    def _build_footer0(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background-color: #181818;")
        h = QHBoxLayout(w)
        h.setContentsMargins(24, 10, 24, 10)
        h.setSpacing(16)
        btn_cancel = QPushButton("✗  Annuler")
        btn_cancel.setObjectName("btn_cancel")
        btn_cancel.clicked.connect(self._cancel)
        h.addWidget(btn_cancel)
        h.addStretch()
        btn_next = QPushButton("Suivant  →")
        btn_next.setObjectName("btn_nav")
        btn_next.clicked.connect(self._go_page1)
        h.addWidget(btn_next)
        return w

    def _build_footer1(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background-color: #181818;")
        h = QHBoxLayout(w)
        h.setContentsMargins(24, 10, 24, 10)
        h.setSpacing(16)
        btn_back = QPushButton("←  Retour")
        btn_back.setObjectName("btn_cancel")
        btn_back.clicked.connect(self._go_page0)
        h.addWidget(btn_back)
        h.addStretch()
        btn_save = QPushButton("✓  Sauvegarder")
        btn_save.setObjectName("btn_save")
        btn_save.clicked.connect(self._save)
        h.addWidget(btn_save)
        return w

    def _go_page0(self) -> None:
        self._stack.setCurrentIndex(0)
        self._footer.setCurrentIndex(0)
        self._header_lbl.setText("Voie Y — Déclaration capteur")

    def _go_page1(self) -> None:
        self._stack.setCurrentIndex(1)
        self._footer.setCurrentIndex(1)
        self._header_lbl.setText("Voie Y — Sensibilité piézo")

    # ------------------------------------------------------------------
    def _load_config(self) -> None:
        cfg = load_config(_CONFIG_PATH)
        if not cfg:
            return

        scaling = cfg.get("scaling", {})
        acq = cfg.get("acquisition", {})
        thr = cfg.get("thresholds", {})
        cal = cfg.get("calibration", {}).get("voie_y", {})

        name = scaling.get("force_name", "")
        self._name_btn.setProperty("alpha_value", name)
        self._name_btn.setText(name or "—")

        for btn, val, default in [
            (self._unit_btn,         scaling.get("force_unit"),          "N"),
            (self._decimal_btn,      str(scaling.get("force_decimal", 1)), "1"),
            (self._scale_method_btn, cal.get("scale_method"),             "Sensibilité"),
            (self._filter_btn,       cal.get("filter"),                   "Aucun"),
        ]:
            v = val or default
            btn.setProperty("choice_value", v)
            btn.setText(v)

        for btn, val, default in [
            (self._max_btn,         str(scaling.get("force_newton_max", 5000.0)), "5000.0"),
            (self._channel_btn,     str(acq.get("force_channel", 0)),             "0"),
            (self._sensitivity_btn, str(cal.get("sensitivity", -10.0)),           "-10.0"),
            (self._alarm_btn,       str(thr.get("force_max_n", 4500.0)),          "4500.0"),
            (self._test_point_btn,  str(cal.get("test_point", 0.0)),              "0.0"),
            (self._tolerance_btn,   str(cal.get("tolerance_pct", 5.0)),           "5.0"),
        ]:
            sfx = btn.property("numpad_suffix") or ""
            btn.setProperty("numpad_value", val)
            btn.setText(f"{val}{sfx}")

        self._invert_chk.setChecked(bool(cal.get("invert_signal", False)))
        self._couple_dcy_chk.setChecked(bool(cal.get("couple_dcy", False)))
        self._test_tor_chk.setChecked(bool(cal.get("test_tor", False)))

    def _save(self) -> None:
        cfg = load_config(_CONFIG_PATH)
        cfg.setdefault("scaling", {})
        cfg.setdefault("acquisition", {})
        cfg.setdefault("thresholds", {})
        cfg.setdefault("calibration", {})
        cfg["calibration"].setdefault("voie_y", {})

        cfg["scaling"]["force_name"] = _get_alpha_value(self._name_btn)
        cfg["scaling"]["force_unit"] = self._unit_btn.property("choice_value") or "N"
        cfg["scaling"]["force_newton_max"] = _get_numpad_value(self._max_btn)
        cfg["scaling"]["force_decimal"] = int(
            self._decimal_btn.property("choice_value") or "1"
        )
        cfg["acquisition"]["force_channel"] = int(_get_numpad_value(self._channel_btn))
        cfg["thresholds"]["force_max_n"] = _get_numpad_value(self._alarm_btn)

        cal = cfg["calibration"]["voie_y"]
        cal["scale_method"]  = self._scale_method_btn.property("choice_value") or "Sensibilité"
        cal["sensitivity"]   = _get_numpad_value(self._sensitivity_btn)
        cal["invert_signal"] = self._invert_chk.isChecked()
        cal["filter"]        = self._filter_btn.property("choice_value") or "Aucun"
        cal["couple_dcy"]    = self._couple_dcy_chk.isChecked()
        cal["test_point"]    = _get_numpad_value(self._test_point_btn)
        cal["tolerance_pct"] = _get_numpad_value(self._tolerance_btn)
        cal["test_tor"]      = self._test_tor_chk.isChecked()

        save_config(_CONFIG_PATH, cfg)
        QMessageBox.information(
            self, "Voie Y",
            "✓ Configuration Voie Y sauvegardée.\nRedémarrez pour appliquer.",
        )
        self._main_stack.setCurrentIndex(1)


# ===========================================================================
# _CycleGraphWidget — mini-graphique ALLER / RETOUR (QPainter)
# ===========================================================================

# ===========================================================================
# _ControleCyclePage — configuration du contrôle de cycle (4 pages)
# ===========================================================================

class _ControleCyclePage(QWidget):
    """Page 4 pages — Mode mesure, Conditions, Parties aller/retour, Traçage
    (intégrée dans _settings_stack)."""

    _TITLES = [
        "Contrôle cycle — Mode mesure",
        "Contrôle cycle — Conditions début / fin",
        "Contrôle cycle — Parties aller / retour",
        "Contrôle cycle — Traçage de la courbe",
    ]

    def __init__(self, stack: QStackedWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._main_stack = stack
        self.setStyleSheet(_DIALOG_STYLE)
        self._build_ui()
        self._load_config()

    def showEvent(self, event) -> None:
        self._load_config()
        super().showEvent(event)

    def _cancel(self) -> None:
        self._main_stack.setCurrentIndex(1)

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        hdr = QWidget()
        hdr.setFixedHeight(50)
        hdr.setStyleSheet("background-color: #252525;")
        hh = QHBoxLayout(hdr)
        hh.setContentsMargins(16, 0, 16, 0)
        self._header_lbl = QLabel(self._TITLES[0])
        self._header_lbl.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #e0e0e0; background: transparent;"
        )
        hh.addWidget(self._header_lbl)
        root.addWidget(hdr)

        # Contenu (4 pages)
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_page0())
        self._stack.addWidget(self._build_page1())
        self._stack.addWidget(self._build_page2())
        self._stack.addWidget(self._build_page3())
        root.addWidget(self._stack, stretch=1)

        # Footer (4 états)
        self._footer = QStackedWidget()
        self._footer.setFixedHeight(64)
        for i in range(4):
            self._footer.addWidget(self._build_footer_nav(i))
        root.addWidget(self._footer)

    def _build_footer_nav(self, page_idx: int) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background-color: #181818;")
        h = QHBoxLayout(w)
        h.setContentsMargins(24, 10, 24, 10)
        h.setSpacing(12)

        if page_idx > 0:
            btn_back = QPushButton("←  Retour")
            btn_back.setObjectName("btn_cancel")
            btn_back.clicked.connect(
                lambda _c=False, i=page_idx: self._go_page(i - 1)
            )
            h.addWidget(btn_back)

        btn_cancel = QPushButton("✗  Annuler")
        btn_cancel.setObjectName("btn_cancel")
        btn_cancel.clicked.connect(self._cancel)
        h.addWidget(btn_cancel)
        h.addStretch()

        if page_idx < 3:
            btn_next = QPushButton("Suivant  →")
            btn_next.setObjectName("btn_nav")
            btn_next.clicked.connect(
                lambda _c=False, i=page_idx: self._go_page(i + 1)
            )
            h.addWidget(btn_next)
        else:
            btn_save = QPushButton("✓  Sauvegarder")
            btn_save.setObjectName("btn_save")
            btn_save.clicked.connect(self._save)
            h.addWidget(btn_save)

        return w

    def _go_page(self, idx: int) -> None:
        self._stack.setCurrentIndex(idx)
        self._footer.setCurrentIndex(idx)
        self._header_lbl.setText(self._TITLES[idx])
        if idx == 0:
            self._refresh_mode_indicator()
        elif idx == 1:
            self._refresh_duree_visibility()
        elif idx == 3:
            self._refresh_tracage_graph()

    # ------------------------------------------------------------------
    # Page 0 — Mode mesure + acquisition
    # ------------------------------------------------------------------

    def _build_page0(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(24, 18, 24, 18)
        v.setSpacing(14)

        form = QFormLayout()
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._mode_btn = _make_choice_btn(
            ["Y (x)", "Y (t)", "X (t)", "Y (x, t)"], "Y (x)", "Mode mesure", self
        )
        form.addRow("Mode mesure :", self._mode_btn)

        self._nb_samples_btn = _make_numpad_btn(
            "1000", suffix="", title="Nombre d'échantillons", parent=self
        )
        form.addRow("Nb d'échantillons :", self._nb_samples_btn)

        self._delta_x_btn = _make_choice_btn(
            ["Automatique", "Manuel"], "Automatique", "Delta X", self
        )
        form.addRow("Delta X :", self._delta_x_btn)

        v.addLayout(form)

        # Indicateur mode (texte dynamique)
        self._mode_indicator = QLabel()
        self._mode_indicator.setStyleSheet(
            "background-color: #252525; color: #378ADD; font-size: 13px;"
            " padding: 10px 16px; border-radius: 6px; border: 1px solid #333333;"
        )
        self._mode_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._mode_indicator.setFixedHeight(50)
        v.addWidget(self._mode_indicator)
        v.addStretch()
        return w

    def _refresh_mode_indicator(self) -> None:
        _desc = {
            "Y (x)":    "Force en fonction de la position",
            "Y (t)":    "Force en fonction du temps",
            "X (t)":    "Position en fonction du temps",
            "Y (x, t)": "Force en fonction de la position et du temps",
        }
        mode = self._mode_btn.property("choice_value") or "Y (x)"
        self._mode_indicator.setText(f"~  {_desc.get(mode, mode)}")

    # ------------------------------------------------------------------
    # Page 1 — Conditions début / fin
    # ------------------------------------------------------------------

    def _build_page1(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(24, 18, 24, 18)
        v.setSpacing(16)

        # En-têtes colonnes
        hdr_row = QHBoxLayout()
        for txt in ["  Début", "", "  Fin"]:
            lbl = QLabel(txt)
            if txt:
                lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #e0e0e0;")
            hdr_row.addWidget(lbl, 0 if not txt else 1)
        v.addLayout(hdr_row)

        # Deux colonnes
        cols = QHBoxLayout()
        cols.setSpacing(10)

        self._condition_debut_btn = _make_choice_btn(
            ["E-TOR 1 / Bus", "Seuil-X", "Seuil-Y", "Manuel"],
            "E-TOR 1 / Bus",
            "Condition début",
            self,
        )
        self._condition_debut_btn.setMinimumHeight(54)
        cols.addWidget(self._condition_debut_btn, stretch=1)

        arrow = QLabel("→")
        arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        arrow.setStyleSheet("color: #888888; font-size: 20px;")
        arrow.setFixedWidth(24)
        cols.addWidget(arrow)

        self._condition_fin_btn = _make_choice_btn(
            ["E-TOR 1 / Bus", "Manuel", "Seuil-X", "Seuil-Y", "Retour-X", "Temps"],
            "E-TOR 1 / Bus",
            "Condition fin",
            self,
        )
        self._condition_fin_btn.setMinimumHeight(54)
        cols.addWidget(self._condition_fin_btn, stretch=1)

        v.addLayout(cols)

        # Durée du cycle (pleine largeur, grisée si condition fin ≠ "Temps")
        form_duree = QFormLayout()
        form_duree.setSpacing(14)
        form_duree.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._duree_btn = _make_numpad_btn(
            "20.0", suffix=" s", title="Durée du cycle (s)", parent=self
        )
        form_duree.addRow("Durée du cycle :", self._duree_btn)
        v.addLayout(form_duree)
        v.addStretch()
        return w

    def _refresh_duree_visibility(self) -> None:
        is_temps = (self._condition_fin_btn.property("choice_value") == "Temps")
        self._duree_btn.setEnabled(is_temps)

    # ------------------------------------------------------------------
    # Page 2 — Parties ALLER / RETOUR
    # ------------------------------------------------------------------

    def _build_page2(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(24, 18, 24, 18)
        v.setSpacing(16)

        form = QFormLayout()
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._aller_btn = _make_choice_btn(
            ["Non défini", "Xmax", "Ymax", "Ymin"], "Xmax",
            "Partie ALLER jusqu'à", self,
        )
        form.addRow("Partie ALLER jusqu'à :", self._aller_btn)

        self._retour_btn = _make_choice_btn(
            ["Non défini", "Xmin", "Ymax", "Ymin"], "Non défini",
            "Partie RETOUR jusqu'à", self,
        )
        form.addRow("Partie RETOUR jusqu'à :", self._retour_btn)

        v.addLayout(form)

        # Indicateur visuel statique (ALLER + RETOUR toujours affichés)
        ind_row = QHBoxLayout()
        ind_row.setSpacing(32)
        ind_row.addStretch()
        for txt, color in [("↗  ALLER", "#E24B4A"), ("↘  RETOUR", "#378ADD")]:
            lbl = QLabel(txt)
            lbl.setStyleSheet(
                f"color: {color}; font-size: 18px; font-weight: bold; background: transparent;"
            )
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ind_row.addWidget(lbl)
        ind_row.addStretch()
        v.addLayout(ind_row)

        v.addStretch()
        return w

    # ------------------------------------------------------------------
    # Page 3 — Traçage de la courbe
    # ------------------------------------------------------------------

    def _build_page3(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(24, 18, 24, 18)
        v.setSpacing(16)

        form = QFormLayout()
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._tracage_btn = _make_choice_btn(
            ["ALLER-RETOUR", "ALLER", "RETOUR"], "ALLER",
            "Traçage de la courbe", self,
        )
        form.addRow("Traçage de la courbe :", self._tracage_btn)

        v.addLayout(form)

        # Indicateur visuel dynamique (mis à jour dans _refresh_tracage_graph)
        ind_row = QHBoxLayout()
        ind_row.setSpacing(32)
        ind_row.addStretch()
        self._tracage_lbl_aller = QLabel("↗  ALLER")
        self._tracage_lbl_aller.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ind_row.addWidget(self._tracage_lbl_aller)
        self._tracage_lbl_retour = QLabel("↘  RETOUR")
        self._tracage_lbl_retour.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ind_row.addWidget(self._tracage_lbl_retour)
        ind_row.addStretch()
        v.addLayout(ind_row)

        v.addStretch()
        return w

    def _refresh_tracage_graph(self) -> None:
        mode = self._tracage_btn.property("choice_value") or "ALLER"
        aller_active  = (mode != "RETOUR")
        retour_active = (mode != "ALLER")
        self._tracage_lbl_aller.setStyleSheet(
            f"color: {'#E24B4A' if aller_active else '#555555'};"
            " font-size: 18px; font-weight: bold; background: transparent;"
        )
        self._tracage_lbl_aller.setText(
            "↗  ALLER" + ("" if aller_active else "  (ignoré)")
        )
        self._tracage_lbl_retour.setStyleSheet(
            f"color: {'#378ADD' if retour_active else '#555555'};"
            " font-size: 18px; font-weight: bold; background: transparent;"
        )
        self._tracage_lbl_retour.setText(
            "↘  RETOUR" + ("" if retour_active else "  (ignoré)")
        )

    # ------------------------------------------------------------------
    # Load / Save
    # ------------------------------------------------------------------

    def _load_config(self) -> None:
        cfg = load_config(_CONFIG_PATH)
        cc = cfg.get("cycle_control", {})

        for btn, val, default in [
            (self._mode_btn,            cc.get("mode_mesure"),       "Y (x)"),
            (self._delta_x_btn,         cc.get("delta_x"),           "Automatique"),
            (self._condition_debut_btn, cc.get("condition_debut"),    "E-TOR 1 / Bus"),
            (self._condition_fin_btn,   cc.get("condition_fin"),      "E-TOR 1 / Bus"),
            (self._aller_btn,           cc.get("partie_aller"),       "Xmax"),
            (self._retour_btn,          cc.get("partie_retour"),      "Non défini"),
            (self._tracage_btn,         cc.get("tracage"),            "ALLER"),
        ]:
            v = val or default
            btn.setProperty("choice_value", v)
            btn.setText(v)

        for btn, val, default in [
            (self._nb_samples_btn, str(cc.get("nb_echantillons", 1000)), "1000"),
            (self._duree_btn,      str(cc.get("duree_cycle_s", 20.0)),   "20.0"),
        ]:
            sfx = btn.property("numpad_suffix") or ""
            btn.setProperty("numpad_value", val)
            btn.setText(f"{val}{sfx}")

        self._refresh_mode_indicator()
        self._refresh_duree_visibility()
        self._refresh_tracage_graph()

    def _save(self) -> None:
        cfg = load_config(_CONFIG_PATH)
        cc = cfg.setdefault("cycle_control", {})

        cc["mode_mesure"]     = self._mode_btn.property("choice_value") or "Y (x)"
        cc["nb_echantillons"] = int(_get_numpad_value(self._nb_samples_btn))
        cc["delta_x"]         = self._delta_x_btn.property("choice_value") or "Automatique"
        cc["condition_debut"] = self._condition_debut_btn.property("choice_value") or "E-TOR 1 / Bus"
        cc["condition_fin"]   = self._condition_fin_btn.property("choice_value") or "E-TOR 1 / Bus"
        cc["duree_cycle_s"]   = _get_numpad_value(self._duree_btn)
        cc["partie_aller"]    = self._aller_btn.property("choice_value") or "Xmax"
        cc["partie_retour"]   = self._retour_btn.property("choice_value") or "Non défini"
        cc["tracage"]         = self._tracage_btn.property("choice_value") or "ALLER"

        save_config(_CONFIG_PATH, cfg)
        QMessageBox.information(
            self, "Contrôle cycle",
            "✓ Configuration sauvegardée.\nRedémarrez pour appliquer.",
        )
        self._main_stack.setCurrentIndex(1)


# ===========================================================================
# _DroitsAccesPage — gestion des droits d'accès et codes PIN (index 9)
# ===========================================================================

def _hash_pin(pin: str) -> str:
    import hashlib
    return hashlib.sha256(pin.encode()).hexdigest()


def _check_pin(entered: str, stored: str) -> bool:
    """Vérifie un PIN saisi contre la valeur stockée (hash ou fallback plain)."""
    if len(stored) == 64:   # sha256 hexdigest
        return _hash_pin(entered) == stored
    return entered == stored  # fallback plain text (migration)


class _DroitsAccesPage(QWidget):
    """Page droits d'accès — 2 pages internes (QStackedWidget)."""

    _LEVELS = [
        ("🟢", "Opérateur",     "pin_operateur",  "0000"),
        ("🟡", "Technicien",    "pin_technicien", "2222"),
        ("🔴", "Administrateur","pin_admin",       "1234"),
    ]

    def __init__(self, stack: QStackedWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._main_stack = stack
        self.setStyleSheet(_DIALOG_STYLE)
        self._build_ui()

    def showEvent(self, event) -> None:
        self._load_config()
        super().showEvent(event)

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        hdr = QWidget()
        hdr.setFixedHeight(50)
        hdr.setStyleSheet("background-color: #252525;")
        hh = QHBoxLayout(hdr)
        hh.setContentsMargins(16, 0, 16, 0)
        lbl = QLabel("🔒   Droits d'accès")
        lbl.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #e0e0e0; background: transparent;"
        )
        hh.addWidget(lbl)
        root.addWidget(hdr)

        # Contenu (2 pages)
        self._inner_stack = QStackedWidget()
        self._inner_stack.addWidget(self._build_page0())
        self._inner_stack.addWidget(self._build_page1())
        root.addWidget(self._inner_stack, stretch=1)

        # Footer (2 états)
        self._footer_stack = QStackedWidget()
        self._footer_stack.setFixedHeight(64)
        self._footer_stack.addWidget(self._build_footer0())
        self._footer_stack.addWidget(self._build_footer1())
        root.addWidget(self._footer_stack)

    def _build_page0(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(24, 18, 24, 14)
        v.setSpacing(14)

        # Activation des droits
        self._enabled_chk = QCheckBox("Activer les droits d'accès")
        self._enabled_chk.setStyleSheet("color: #cccccc; font-size: 14px;")
        v.addWidget(self._enabled_chk)

        # Déconnexion auto
        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._auto_logout_btn = _make_choice_btn(
            ["Jamais", "5 minutes", "15 minutes", "1 heure"],
            "Jamais", "Déconnexion auto", self,
        )
        form.addRow("Déconnexion auto :", self._auto_logout_btn)
        v.addLayout(form)

        # Séparateur + titre
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #333333;")
        v.addWidget(sep)
        lbl_pin = QLabel("Modifier les codes PIN")
        lbl_pin.setStyleSheet("color: #888888; font-size: 13px; font-weight: bold;")
        v.addWidget(lbl_pin)

        # 3 lignes PIN
        _ROW_STYLE = (
            "background-color: #252525; border-radius: 8px; padding: 6px;"
        )
        for icon, name, key, _ in self._LEVELS:
            row_w = QWidget()
            row_w.setStyleSheet(_ROW_STYLE)
            rh = QHBoxLayout(row_w)
            rh.setContentsMargins(10, 4, 10, 4)
            rh.setSpacing(12)
            lbl = QLabel(f"{icon}  {name}")
            lbl.setStyleSheet("color: #cccccc; font-size: 14px; min-width: 160px;")
            rh.addWidget(lbl)
            rh.addStretch()
            pin_lbl = QLabel("PIN : ••••")
            pin_lbl.setStyleSheet("color: #666666; font-size: 13px;")
            rh.addWidget(pin_lbl)
            btn_mod = QPushButton("✏  Modifier")
            btn_mod.setObjectName("btn_nav")
            btn_mod.setFixedWidth(120)
            btn_mod.clicked.connect(
                lambda _c=False, k=key, n=name: self._change_pin(k, n)
            )
            rh.addWidget(btn_mod)
            v.addWidget(row_w)

        v.addStretch()
        return w

    def _build_page1(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(24, 18, 24, 18)
        v.setSpacing(14)

        lbl = QLabel("Tableau des niveaux d'accès")
        lbl.setStyleSheet("color: #888888; font-size: 13px; font-weight: bold;")
        v.addWidget(lbl)

        table = QTableWidget(3, 3)
        table.setHorizontalHeaderLabels(["Niveau", "Nom", "Droits"])
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setDefaultSectionSize(90)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)

        _ROWS = [
            ("1", "🟢 Opérateur",     "Voir courbes, compteurs, export CSV"),
            ("2", "🟡 Technicien",    "+ Changer PM, RAZ compteurs"),
            ("3", "🔴 Administrateur","+ Réglages complets, PM, date/heure"),
        ]
        for row, (niv, nom, droits) in enumerate(_ROWS):
            for col, txt in enumerate([niv, nom, droits]):
                item = QTableWidgetItem(txt)
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                table.setItem(row, col, item)

        v.addWidget(table, stretch=1)
        return w

    def _build_footer0(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background-color: #181818;")
        h = QHBoxLayout(w)
        h.setContentsMargins(24, 10, 24, 10)
        h.setSpacing(12)
        btn_back = QPushButton("←  Retour")
        btn_back.setObjectName("btn_cancel")
        btn_back.clicked.connect(lambda: self._main_stack.setCurrentIndex(1))
        h.addWidget(btn_back)
        btn_save = QPushButton("✓  Sauvegarder")
        btn_save.setObjectName("btn_save")
        btn_save.clicked.connect(self._save)
        h.addWidget(btn_save)
        h.addStretch()
        btn_niveaux = QPushButton("Voir niveaux  →")
        btn_niveaux.setObjectName("btn_nav")
        btn_niveaux.clicked.connect(self._go_page1)
        h.addWidget(btn_niveaux)
        return w

    def _build_footer1(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background-color: #181818;")
        h = QHBoxLayout(w)
        h.setContentsMargins(24, 10, 24, 10)
        h.setSpacing(12)
        btn_back = QPushButton("←  Retour")
        btn_back.setObjectName("btn_cancel")
        btn_back.clicked.connect(self._go_page0)
        h.addWidget(btn_back)
        h.addStretch()
        return w

    def _go_page0(self) -> None:
        self._inner_stack.setCurrentIndex(0)
        self._footer_stack.setCurrentIndex(0)

    def _go_page1(self) -> None:
        self._inner_stack.setCurrentIndex(1)
        self._footer_stack.setCurrentIndex(1)

    # ------------------------------------------------------------------
    def _change_pin(self, level_key: str, level_name: str) -> None:
        """Flux changement PIN : vérification ancien → nouveau × 2."""
        from ihm.main_window import NumpadDialog

        # 1. Vérifier l'ancien PIN
        dlg_old = NumpadDialog(
            title=f"Ancien PIN — {level_name}", unit="", value="", parent=self
        )
        if not dlg_old.exec():
            return
        entered_old = dlg_old.value()
        cfg = load_config(_CONFIG_PATH)
        ac = cfg.get("access_control", {})
        default_plain = dict(
            pin_operateur="0000", pin_technicien="2222", pin_admin="1234"
        )
        stored = ac.get(level_key, _hash_pin(default_plain[level_key]))
        if not _check_pin(entered_old, stored):
            QMessageBox.warning(self, "PIN incorrect", "L'ancien PIN est incorrect.")
            return

        # 2. Nouveau PIN
        dlg_new = NumpadDialog(
            title=f"Nouveau PIN — {level_name}", unit="", value="", parent=self
        )
        if not dlg_new.exec():
            return
        new_pin = dlg_new.value()

        # 3. Confirmation
        dlg_conf = NumpadDialog(
            title=f"Confirmer nouveau PIN — {level_name}", unit="", value="", parent=self
        )
        if not dlg_conf.exec():
            return
        if dlg_conf.value() != new_pin:
            QMessageBox.warning(self, "PIN différent", "Les deux PIN ne correspondent pas.")
            return

        # 4. Sauvegarder
        ac[level_key] = _hash_pin(new_pin)
        cfg["access_control"] = ac
        save_config(_CONFIG_PATH, cfg)
        QMessageBox.information(self, "PIN modifié", f"✓ PIN {level_name} mis à jour.")

    # ------------------------------------------------------------------
    def _load_config(self) -> None:
        cfg = load_config(_CONFIG_PATH)
        ac = cfg.get("access_control", {})
        self._enabled_chk.setChecked(bool(ac.get("enabled", False)))
        v = ac.get("auto_logout", "Jamais")
        self._auto_logout_btn.setProperty("choice_value", v)
        self._auto_logout_btn.setText(v)

    def _save(self) -> None:
        cfg = load_config(_CONFIG_PATH)
        ac = cfg.setdefault("access_control", {})
        ac["enabled"]     = self._enabled_chk.isChecked()
        ac["auto_logout"] = self._auto_logout_btn.property("choice_value") or "Jamais"
        # Initialiser les PIN par défaut hashés s'ils n'existent pas encore
        _defaults = {
            "pin_operateur":  "0000",
            "pin_technicien": "2222",
            "pin_admin":      "1234",
        }
        for key, plain in _defaults.items():
            ac.setdefault(key, _hash_pin(plain))
        save_config(_CONFIG_PATH, cfg)
        QMessageBox.information(
            self, "Droits d'accès",
            "✓ Configuration sauvegardée.\nRedémarrez pour appliquer.",
        )
        self._main_stack.setCurrentIndex(1)


# ===========================================================================
# _DateHeurePage — réglage date / heure système (index 8)
# ===========================================================================

class _DateHeurePage(QWidget):
    """Page unique — réglage de la date et de l'heure système du Raspberry Pi."""

    def __init__(self, stack: QStackedWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._main_stack = stack
        self.setStyleSheet(_DIALOG_STYLE)
        self._build_ui()

    def showEvent(self, event) -> None:
        self._load_current_datetime()
        super().showEvent(event)

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        from datetime import datetime
        now = datetime.now()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        hdr = QWidget()
        hdr.setFixedHeight(50)
        hdr.setStyleSheet("background-color: #252525;")
        hh = QHBoxLayout(hdr)
        hh.setContentsMargins(16, 0, 16, 0)
        lbl = QLabel("📅   Date / Heure")
        lbl.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #e0e0e0; background: transparent;"
        )
        hh.addWidget(lbl)
        root.addWidget(hdr)

        # Corps
        body = QWidget()
        form_v = QVBoxLayout(body)
        form_v.setContentsMargins(28, 22, 28, 22)
        form_v.setSpacing(22)

        # ---- NTP ----
        ntp_grp = QWidget()
        ntp_v = QVBoxLayout(ntp_grp)
        ntp_v.setContentsMargins(0, 0, 0, 0)
        ntp_v.setSpacing(10)

        self._ntp_check = QCheckBox("Utiliser l'horloge serveur pour horodatage auto.")
        self._ntp_check.setStyleSheet("color: #cccccc; font-size: 14px;")
        ntp_v.addWidget(self._ntp_check)

        ntp_row = QHBoxLayout()
        ntp_lbl = QLabel("Serveur NTP :")
        ntp_lbl.setStyleSheet("color: #888888; font-size: 13px;")
        ntp_row.addWidget(ntp_lbl)
        self._btn_ntp = _make_alpha_btn("pool.ntp.org", title="Serveur NTP", parent=self)
        ntp_row.addWidget(self._btn_ntp, stretch=1)
        ntp_v.addLayout(ntp_row)

        self._ntp_check.stateChanged.connect(
            lambda state: self._btn_ntp.setEnabled(bool(state))
        )
        # état initial : chargé depuis config dans showEvent
        self._btn_ntp.setEnabled(False)

        form_v.addWidget(ntp_grp)

        # Séparateur
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #333333;")
        form_v.addWidget(sep)

        # ---- Date ----
        date_lbl = QLabel("Date")
        date_lbl.setStyleSheet("color: #888888; font-size: 13px; font-weight: bold;")
        form_v.addWidget(date_lbl)

        date_row = QHBoxLayout()
        date_row.setSpacing(12)
        for unit_lbl, attr, title, default in [
            ("AAAA", "_btn_annee", "Année [AAAA]",  f"{now.year:04d}"),
            ("MM",   "_btn_mois",  "Mois [MM]",     f"{now.month:02d}"),
            ("JJ",   "_btn_jour",  "Jour [JJ]",     f"{now.day:02d}"),
        ]:
            col = QVBoxLayout()
            col.setSpacing(4)
            lbl_u = QLabel(unit_lbl)
            lbl_u.setStyleSheet("color: #888888; font-size: 12px;")
            lbl_u.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col.addWidget(lbl_u)
            btn = _make_numpad_btn(default, suffix="", title=title, parent=self)
            setattr(self, attr, btn)
            col.addWidget(btn)
            date_row.addLayout(col)
        form_v.addLayout(date_row)

        # ---- Heure ----
        heure_lbl = QLabel("Heure")
        heure_lbl.setStyleSheet("color: #888888; font-size: 13px; font-weight: bold;")
        form_v.addWidget(heure_lbl)

        heure_row = QHBoxLayout()
        heure_row.setSpacing(12)
        for unit_lbl, attr, title, default in [
            ("HH", "_btn_heure",  "Heure [HH]",     f"{now.hour:02d}"),
            ("MM", "_btn_minute", "Minutes [MM]",    f"{now.minute:02d}"),
            ("SS", "_btn_sec",    "Secondes [SS]",   f"{now.second:02d}"),
        ]:
            col = QVBoxLayout()
            col.setSpacing(4)
            lbl_u = QLabel(unit_lbl)
            lbl_u.setStyleSheet("color: #888888; font-size: 12px;")
            lbl_u.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col.addWidget(lbl_u)
            btn = _make_numpad_btn(default, suffix="", title=title, parent=self)
            setattr(self, attr, btn)
            col.addWidget(btn)
            heure_row.addLayout(col)
        form_v.addLayout(heure_row)

        form_v.addStretch()
        root.addWidget(body, stretch=1)

        # Footer
        footer = QWidget()
        footer.setFixedHeight(64)
        footer.setStyleSheet("background-color: #181818;")
        fh = QHBoxLayout(footer)
        fh.setContentsMargins(24, 10, 24, 10)
        fh.setSpacing(12)

        btn_back = QPushButton("←  Retour")
        btn_back.setObjectName("btn_cancel")
        btn_back.clicked.connect(lambda: self._main_stack.setCurrentIndex(1))
        fh.addWidget(btn_back)
        fh.addStretch()

        btn_apply = QPushButton("✓  Appliquer")
        btn_apply.setObjectName("btn_save")
        btn_apply.clicked.connect(self._apply)
        fh.addWidget(btn_apply)

        root.addWidget(footer)

    # ------------------------------------------------------------------
    def _load_current_datetime(self) -> None:
        from datetime import datetime
        now = datetime.now()
        for btn, val in [
            (self._btn_annee,  f"{now.year:04d}"),
            (self._btn_mois,   f"{now.month:02d}"),
            (self._btn_jour,   f"{now.day:02d}"),
            (self._btn_heure,  f"{now.hour:02d}"),
            (self._btn_minute, f"{now.minute:02d}"),
            (self._btn_sec,    f"{now.second:02d}"),
        ]:
            btn.setProperty("numpad_value", val)
            btn.setText(val)

        cfg = load_config(_CONFIG_PATH)
        sys_cfg = cfg.get("system", {})
        ntp_enabled = bool(sys_cfg.get("ntp_enabled", False))
        ntp_server  = sys_cfg.get("ntp_server", "pool.ntp.org")

        self._ntp_check.setChecked(ntp_enabled)
        self._btn_ntp.setProperty("alpha_value", ntp_server)
        self._btn_ntp.setText(ntp_server or "pool.ntp.org")
        self._btn_ntp.setEnabled(ntp_enabled)

    # ------------------------------------------------------------------
    def _apply(self) -> None:
        import subprocess
        from datetime import datetime

        annee   = _get_numpad_value(self._btn_annee,  2024)
        mois    = _get_numpad_value(self._btn_mois,   1)
        jour    = _get_numpad_value(self._btn_jour,   1)
        heure   = _get_numpad_value(self._btn_heure,  0)
        minute  = _get_numpad_value(self._btn_minute, 0)
        seconde = _get_numpad_value(self._btn_sec,    0)

        date_str = (
            f"{int(annee):04d}-{int(mois):02d}-{int(jour):02d} "
            f"{int(heure):02d}:{int(minute):02d}:{int(seconde):02d}"
        )

        try:
            subprocess.run(
                ["sudo", "date", "-s", date_str],
                check=True, capture_output=True,
            )
            subprocess.run(
                ["sudo", "hwclock", "--systohc"],
                capture_output=True,
            )
            QMessageBox.information(
                self, "Date / Heure",
                f"✓ Date et heure appliquées :\n{date_str}",
            )
        except subprocess.CalledProcessError as e:
            QMessageBox.warning(
                self, "Erreur",
                f"Impossible d'appliquer la date :\n{e.stderr.decode()}\n\n"
                "Vérifiez que le Pi a les droits sudo sans mot de passe.",
            )

        if self._ntp_check.isChecked():
            try:
                subprocess.run(
                    ["sudo", "timedatectl", "set-ntp", "true"],
                    capture_output=True,
                )
            except Exception:
                pass

        cfg = load_config(_CONFIG_PATH)
        cfg.setdefault("system", {})
        cfg["system"]["ntp_enabled"] = self._ntp_check.isChecked()
        cfg["system"]["ntp_server"]  = _get_alpha_value(self._btn_ntp)
        save_config(_CONFIG_PATH, cfg)

        self._main_stack.setCurrentIndex(1)


# ===========================================================================
# _AffichageProdPage — préférences d'affichage production (index 10)
# ===========================================================================

class _AffichageProdPage(QWidget):
    """Page 2 pages internes — histogramme, outil, feu bicolore."""

    _HISTO_VALS = ["OK-NOK en %", "Nb de pièce NOK"]
    _FEU_VALS   = ["Smiley", "Coche", "Pouce", "Texte", "Vide"]

    # Contenu texte pour chaque style de feu
    _FEU_CONTENT = {
        "Smiley": ("😊", "😞"),
        "Coche":  ("✓",  "✗"),
        "Pouce":  ("👍", "👎"),
        "Texte":  ("OK", "NOK"),
        "Vide":   ("",   ""),
    }

    def __init__(self, stack: QStackedWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._main_stack = stack
        self.setStyleSheet(_DIALOG_STYLE)
        self._build_ui()

    def showEvent(self, event) -> None:
        self._load_config()
        super().showEvent(event)

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        hdr = QWidget()
        hdr.setFixedHeight(50)
        hdr.setStyleSheet("background-color: #252525;")
        hh = QHBoxLayout(hdr)
        hh.setContentsMargins(16, 0, 16, 0)
        lbl = QLabel("🖥   Affichage production")
        lbl.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #e0e0e0; background: transparent;"
        )
        hh.addWidget(lbl)
        root.addWidget(hdr)

        # Contenu (2 pages)
        self._inner_stack = QStackedWidget()
        self._inner_stack.addWidget(self._build_page0())
        self._inner_stack.addWidget(self._build_page1())
        root.addWidget(self._inner_stack, stretch=1)

        # Footer (2 états)
        self._footer_stack = QStackedWidget()
        self._footer_stack.setFixedHeight(64)
        self._footer_stack.addWidget(self._build_footer0())
        self._footer_stack.addWidget(self._build_footer1())
        root.addWidget(self._footer_stack)

    # ------------------------------------------------------------------
    def _build_page0(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(24, 18, 24, 14)
        v.setSpacing(16)

        # ---- Histogramme ----
        lbl_h = QLabel("Histogramme")
        lbl_h.setStyleSheet("color: #888888; font-size: 13px; font-weight: bold;")
        v.addWidget(lbl_h)

        _PB_STYLE = (
            "QProgressBar { border: 1px solid #444; border-radius: 4px;"
            " background: #1a1a1a; height: 22px; }"
            "QProgressBar::chunk { background-color: #E24B4A; border-radius: 4px; }"
        )
        self._histo_group = QButtonGroup(self)
        self._histo_btns: list = []

        for idx, (val, suffix) in enumerate(
            [("OK-NOK en %", " %"), ("Nb de pièce NOK", " pcs")]
        ):
            row = QHBoxLayout()
            row.setSpacing(10)
            rb = QRadioButton(val)
            rb.setStyleSheet("color: #cccccc; font-size: 13px; min-width: 160px;")
            self._histo_group.addButton(rb, idx)
            self._histo_btns.append(rb)
            row.addWidget(rb)
            pb = QProgressBar()
            pb.setRange(0, 100)
            pb.setValue(65)
            pb.setTextVisible(False)
            pb.setFixedHeight(22)
            pb.setStyleSheet(_PB_STYLE)
            row.addWidget(pb, stretch=1)
            lbl_val = QLabel(f"65{suffix}")
            lbl_val.setStyleSheet("color: #888888; font-size: 12px; min-width: 50px;")
            row.addWidget(lbl_val)
            v.addLayout(row)

        self._histo_btns[0].setChecked(True)

        # ---- Séparateur ----
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #333333;")
        v.addWidget(sep)

        # ---- Outil d'évaluation ----
        lbl_outil = QLabel("Outil d'évaluation")
        lbl_outil.setStyleSheet("color: #888888; font-size: 13px; font-weight: bold;")
        v.addWidget(lbl_outil)

        _APE_STYLE = (
            "background: #1e1e1e; border: 2px solid #378ADD;"
            " border-radius: 4px; padding: 2px 8px;"
        )

        # Fenêtre pleine
        row_fp = QHBoxLayout()
        row_fp.setSpacing(14)
        self._fenetre_pleine_chk = QCheckBox("Fenêtre pleine")
        self._fenetre_pleine_chk.setStyleSheet("color: #cccccc; font-size: 13px;")
        self._fenetre_pleine_chk.setChecked(True)
        row_fp.addWidget(self._fenetre_pleine_chk)
        row_fp.addStretch()
        lbl_fp = QLabel("█████")
        lbl_fp.setStyleSheet(f"color: #378ADD; font-size: 16px; {_APE_STYLE}")
        row_fp.addWidget(lbl_fp)
        v.addLayout(row_fp)

        # Indication E/S
        row_es = QHBoxLayout()
        row_es.setSpacing(14)
        self._indication_es_chk = QCheckBox("Indication E/S")
        self._indication_es_chk.setStyleSheet("color: #cccccc; font-size: 13px;")
        self._indication_es_chk.setChecked(True)
        row_es.addWidget(self._indication_es_chk)
        row_es.addStretch()
        lbl_es = QLabel("→ □ →")
        lbl_es.setStyleSheet(f"color: #378ADD; font-size: 14px; {_APE_STYLE}")
        row_es.addWidget(lbl_es)
        v.addLayout(row_es)

        v.addStretch()
        return w

    # ------------------------------------------------------------------
    def _build_page1(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(24, 18, 24, 14)
        v.setSpacing(10)

        lbl = QLabel("Feu bicolore — style badge résultat")
        lbl.setStyleSheet("color: #888888; font-size: 13px; font-weight: bold;")
        v.addWidget(lbl)

        self._feu_group = QButtonGroup(self)
        self._feu_btns: list = []

        _OK_STYLE  = (
            "background-color: #1a3a1a; color: #4caf50; border-radius: 6px;"
            " font-size: 18px; font-weight: bold;"
        )
        _NOK_STYLE = (
            "background-color: #3a1a1a; color: #ef5350; border-radius: 6px;"
            " font-size: 18px; font-weight: bold;"
        )

        for idx, val in enumerate(self._FEU_VALS):
            ok_txt, nok_txt = self._FEU_CONTENT[val]
            row = QHBoxLayout()
            row.setSpacing(12)
            rb = QRadioButton(val)
            rb.setStyleSheet("color: #cccccc; font-size: 13px; min-width: 120px;")
            self._feu_group.addButton(rb, idx)
            self._feu_btns.append(rb)
            row.addWidget(rb)
            row.addStretch()
            for txt, style in [(ok_txt, _OK_STYLE), (nok_txt, _NOK_STYLE)]:
                lbl_ap = QLabel(txt)
                lbl_ap.setFixedSize(80, 40)
                lbl_ap.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl_ap.setStyleSheet(style)
                row.addWidget(lbl_ap)
            v.addLayout(row)

        self._feu_btns[0].setChecked(True)
        v.addStretch()
        return w

    # ------------------------------------------------------------------
    def _build_footer0(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background-color: #181818;")
        h = QHBoxLayout(w)
        h.setContentsMargins(24, 10, 24, 10)
        h.setSpacing(12)
        btn_back = QPushButton("←  Retour")
        btn_back.setObjectName("btn_cancel")
        btn_back.clicked.connect(lambda: self._main_stack.setCurrentIndex(1))
        h.addWidget(btn_back)
        btn_save = QPushButton("✓  Sauvegarder")
        btn_save.setObjectName("btn_save")
        btn_save.clicked.connect(self._save)
        h.addWidget(btn_save)
        h.addStretch()
        btn_feu = QPushButton("Feu bicolore  →")
        btn_feu.setObjectName("btn_nav")
        btn_feu.clicked.connect(self._go_page1)
        h.addWidget(btn_feu)
        return w

    def _build_footer1(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background-color: #181818;")
        h = QHBoxLayout(w)
        h.setContentsMargins(24, 10, 24, 10)
        h.setSpacing(12)
        btn_back = QPushButton("←  Retour")
        btn_back.setObjectName("btn_cancel")
        btn_back.clicked.connect(self._go_page0)
        h.addWidget(btn_back)
        h.addStretch()
        btn_save = QPushButton("✓  Sauvegarder")
        btn_save.setObjectName("btn_save")
        btn_save.clicked.connect(self._save)
        h.addWidget(btn_save)
        return w

    def _go_page0(self) -> None:
        self._inner_stack.setCurrentIndex(0)
        self._footer_stack.setCurrentIndex(0)

    def _go_page1(self) -> None:
        self._inner_stack.setCurrentIndex(1)
        self._footer_stack.setCurrentIndex(1)

    # ------------------------------------------------------------------
    def _load_config(self) -> None:
        cfg = load_config(_CONFIG_PATH)
        dp = cfg.get("affichage_prod", {})

        histo = dp.get("histogramme", "OK-NOK en %")
        for i, val in enumerate(self._HISTO_VALS):
            self._histo_btns[i].setChecked(val == histo)

        self._fenetre_pleine_chk.setChecked(bool(dp.get("fenetre_pleine", True)))
        self._indication_es_chk.setChecked(bool(dp.get("indication_es", True)))

        feu = dp.get("feu_bicolore", "Texte")
        for i, val in enumerate(self._FEU_VALS):
            self._feu_btns[i].setChecked(val == feu)

    def _save(self) -> None:
        cfg = load_config(_CONFIG_PATH)
        dp = cfg.setdefault("affichage_prod", {})

        checked_histo = self._histo_group.checkedId()
        dp["histogramme"] = (
            self._HISTO_VALS[checked_histo]
            if 0 <= checked_histo < len(self._HISTO_VALS)
            else "OK-NOK en %"
        )

        dp["fenetre_pleine"] = self._fenetre_pleine_chk.isChecked()
        dp["indication_es"]  = self._indication_es_chk.isChecked()

        checked_feu = self._feu_group.checkedId()
        dp["feu_bicolore"] = (
            self._FEU_VALS[checked_feu]
            if 0 <= checked_feu < len(self._FEU_VALS)
            else "Texte"
        )

        save_config(_CONFIG_PATH, cfg)

        # Notifier MainWindow pour appliquer immédiatement
        main_win = self._main_stack.window()
        if hasattr(main_win, "apply_display_settings"):
            main_win.apply_display_settings()

        QMessageBox.information(
            self, "Affichage production",
            "✓ Préférences d'affichage sauvegardées.",
        )
        self._main_stack.setCurrentIndex(1)


# ===========================================================================
# _ExportationPage — export CSV/PDF vers clé USB (index 11)
# ===========================================================================

class _ExportationPage(QWidget):
    """Page 2 pages — export CSV et rapport PDF.

    Page 0 : Configuration export (dossier, clé USB, filtre, PDF)
    Page 1 : Paramètres avancés (nommage, export auto)
    """

    def __init__(self, stack: QStackedWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._main_stack = stack
        self._detected_drives: list[str] = []
        self._worker_usb: object | None = None
        self._worker_pdf: object | None = None
        self._worker_detect: object | None = None
        self.setStyleSheet(_DIALOG_STYLE)
        self._build_ui()

    def showEvent(self, event) -> None:
        self._load_config()
        self._reset_buttons_if_idle()
        super().showEvent(event)

    def _reset_buttons_if_idle(self) -> None:
        """Remet les boutons à leur état initial si aucun worker ne tourne."""
        if not (self._worker_usb is not None and self._worker_usb.isRunning()):
            self._btn_export.setEnabled(True)
            self._btn_export.setText("💾  Exporter vers la clé USB")
        if not (self._worker_pdf is not None and self._worker_pdf.isRunning()):
            self._btn_pdf.setEnabled(True)
            self._btn_pdf.setText("📄  Générer rapport PDF")
        if not (self._worker_detect is not None and self._worker_detect.isRunning()):
            self._btn_detect.setEnabled(True)
            self._btn_detect.setText("🔍  Détecter les clés USB")

    def _cancel(self) -> None:
        self._main_stack.setCurrentIndex(1)

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header commun
        header = QWidget()
        header.setFixedHeight(50)
        header.setStyleSheet("background-color: #252525;")
        hh = QHBoxLayout(header)
        hh.setContentsMargins(16, 0, 16, 0)
        lbl = QLabel("💾  Exportation")
        lbl.setStyleSheet(
            "font-size: 17px; font-weight: bold; color: #e0e0e0; background: transparent;"
        )
        hh.addWidget(lbl)
        root.addWidget(header)

        # Stack interne (2 pages)
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_page0())
        self._stack.addWidget(self._build_page1())
        root.addWidget(self._stack, stretch=1)

        # Footer (2 états)
        self._footer = QStackedWidget()
        self._footer.setFixedHeight(64)
        self._footer.addWidget(self._build_footer0())
        self._footer.addWidget(self._build_footer1())
        root.addWidget(self._footer)

    # ------------------------------------------------------------------
    def _build_page0(self) -> QWidget:
        outer = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(24, 18, 24, 18)
        v.setSpacing(18)

        # ---- Section : Dossier local ----
        sec0 = QLabel("📁  Dossier local")
        sec0.setStyleSheet("font-size: 14px; font-weight: bold; color: #888888;")
        v.addWidget(sec0)

        cfg = _load_cfg_safe()
        data_dir = cfg.get("storage", {}).get("data_dir", "./data")
        self._data_dir_lbl = QLabel(str(Path(data_dir).resolve()))
        self._data_dir_lbl.setStyleSheet(
            "background-color: #2a2a2a; color: #aaaaaa; border: 1px solid #444;"
            " border-radius: 6px; padding: 8px 12px; font-size: 14px;"
        )
        self._data_dir_lbl.setWordWrap(True)
        v.addWidget(self._data_dir_lbl)

        sep0 = QFrame()
        sep0.setObjectName("separator")
        sep0.setFrameShape(QFrame.Shape.HLine)
        v.addWidget(sep0)

        # ---- Section : Clé USB ----
        sec1 = QLabel("🔌  Clé USB")
        sec1.setStyleSheet("font-size: 14px; font-weight: bold; color: #888888;")
        v.addWidget(sec1)

        self._btn_detect = QPushButton("🔍  Détecter les clés USB")
        self._btn_detect.setObjectName("btn_nav")
        self._btn_detect.clicked.connect(self._detect_usb)
        v.addWidget(self._btn_detect)

        self._usb_status_lbl = QLabel("Aucune clé USB détectée")
        self._usb_status_lbl.setStyleSheet("color: #888888; font-size: 14px;")
        v.addWidget(self._usb_status_lbl)

        form_usb = QFormLayout()
        form_usb.setSpacing(10)
        form_usb.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._filtre_btn = _make_choice_btn(
            ["OK+NOK", "OK uniquement", "NOK uniquement"],
            "OK+NOK",
            "Filtre export",
            self,
        )
        form_usb.addRow("Filtre export :", self._filtre_btn)
        fw_usb = QWidget()
        fw_usb.setLayout(form_usb)
        v.addWidget(fw_usb)

        self._btn_export = QPushButton("💾  Exporter vers la clé USB")
        self._btn_export.setObjectName("btn_save")
        self._btn_export.clicked.connect(self._do_export_usb)
        v.addWidget(self._btn_export)

        sep1 = QFrame()
        sep1.setObjectName("separator")
        sep1.setFrameShape(QFrame.Shape.HLine)
        v.addWidget(sep1)

        # ---- Section : Rapport PDF ----
        sec2 = QLabel("📄  Rapport PDF")
        sec2.setStyleSheet("font-size: 14px; font-weight: bold; color: #888888;")
        v.addWidget(sec2)

        form_pdf = QFormLayout()
        form_pdf.setSpacing(10)
        form_pdf.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._contenu_btn = _make_choice_btn(
            ["Tous les cycles", "Cycles NOK uniquement", "Session courante"],
            "Tous les cycles",
            "Contenu rapport",
            self,
        )
        self._periode_btn = _make_choice_btn(
            ["Aujourd'hui", "7 derniers jours", "30 derniers jours", "Tout l'historique"],
            "Aujourd'hui",
            "Période",
            self,
        )
        form_pdf.addRow("Contenu rapport :", self._contenu_btn)
        form_pdf.addRow("Période :", self._periode_btn)
        fw_pdf = QWidget()
        fw_pdf.setLayout(form_pdf)
        v.addWidget(fw_pdf)

        self._btn_pdf = QPushButton("📄  Générer rapport PDF")
        self._btn_pdf.setObjectName("btn_nav")
        self._btn_pdf.clicked.connect(self._do_generate_pdf)
        v.addWidget(self._btn_pdf)

        v.addStretch()
        scroll.setWidget(w)
        out_v = QVBoxLayout(outer)
        out_v.setContentsMargins(0, 0, 0, 0)
        out_v.addWidget(scroll)
        return outer

    # ------------------------------------------------------------------
    def _build_page1(self) -> QWidget:
        outer = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(24, 18, 24, 18)
        v.setSpacing(18)

        form = QFormLayout()
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._nommage_btn = _make_choice_btn(
            [
                "PM_date_heure_résultat",
                "Numéro séquentiel",
                "PM_numéro_résultat",
            ],
            "PM_date_heure_résultat",
            "Nommage fichier",
            self,
        )
        form.addRow("Nommage fichier :", self._nommage_btn)

        self._auto_export_chk = QCheckBox("Exporter automatiquement à chaque cycle")
        form.addRow("Export automatique :", self._auto_export_chk)

        self._dest_auto_btn = _make_choice_btn(
            ["Dossier local", "Clé USB si présente"],
            "Dossier local",
            "Destination auto",
            self,
        )
        form.addRow("Destination auto :", self._dest_auto_btn)

        fw = QWidget()
        fw.setLayout(form)
        v.addWidget(fw)
        v.addStretch()
        scroll.setWidget(w)

        out_v = QVBoxLayout(outer)
        out_v.setContentsMargins(0, 0, 0, 0)
        out_v.addWidget(scroll)
        return outer

    # ------------------------------------------------------------------
    def _build_footer0(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background-color: #1a1a1a; border-top: 1px solid #333;")
        h = QHBoxLayout(w)
        h.setContentsMargins(16, 8, 16, 8)
        h.setSpacing(12)

        btn_cancel = QPushButton("←  Retour")
        btn_cancel.setObjectName("btn_cancel")
        btn_cancel.clicked.connect(self._cancel)
        h.addWidget(btn_cancel)

        h.addStretch()

        btn_save = QPushButton("✓  Sauvegarder")
        btn_save.setObjectName("btn_save")
        btn_save.clicked.connect(self._save)
        h.addWidget(btn_save)

        btn_next = QPushButton("Avancé  →")
        btn_next.setObjectName("btn_nav")
        btn_next.clicked.connect(self._go_page1)
        h.addWidget(btn_next)

        return w

    def _build_footer1(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background-color: #1a1a1a; border-top: 1px solid #333;")
        h = QHBoxLayout(w)
        h.setContentsMargins(16, 8, 16, 8)
        h.setSpacing(12)

        btn_back = QPushButton("←  Retour")
        btn_back.setObjectName("btn_cancel")
        btn_back.clicked.connect(self._go_page0)
        h.addWidget(btn_back)

        h.addStretch()

        btn_save = QPushButton("✓  Sauvegarder")
        btn_save.setObjectName("btn_save")
        btn_save.clicked.connect(self._save)
        h.addWidget(btn_save)

        return w

    # ------------------------------------------------------------------
    def _go_page0(self) -> None:
        self._stack.setCurrentIndex(0)
        self._footer.setCurrentIndex(0)

    def _go_page1(self) -> None:
        self._stack.setCurrentIndex(1)
        self._footer.setCurrentIndex(1)

    # ------------------------------------------------------------------
    def _load_config(self) -> None:
        cfg = _load_cfg_safe()
        exp = cfg.get("export", {})

        # Page 0
        data_dir = cfg.get("storage", {}).get("data_dir", "./data")
        self._data_dir_lbl.setText(str(Path(data_dir).resolve()))

        filtre = exp.get("filtre", "OK+NOK")
        self._filtre_btn.setProperty("choice_value", filtre)
        self._filtre_btn.setText(filtre)

        contenu = exp.get("contenu_rapport", "Tous les cycles")
        self._contenu_btn.setProperty("choice_value", contenu)
        self._contenu_btn.setText(contenu)

        # Page 1
        nommage = exp.get("nommage", "PM_date_heure_résultat")
        self._nommage_btn.setProperty("choice_value", nommage)
        self._nommage_btn.setText(nommage)

        self._auto_export_chk.setChecked(exp.get("auto_export", False))

        dest_auto = exp.get("destination_auto", "Dossier local")
        self._dest_auto_btn.setProperty("choice_value", dest_auto)
        self._dest_auto_btn.setText(dest_auto)

    def _save(self) -> None:
        cfg = _load_cfg_safe()
        cfg.setdefault("export", {})
        cfg["export"]["filtre"] = self._filtre_btn.property("choice_value") or "OK+NOK"
        cfg["export"]["contenu_rapport"] = (
            self._contenu_btn.property("choice_value") or "Tous les cycles"
        )
        cfg["export"]["nommage"] = (
            self._nommage_btn.property("choice_value") or "PM_date_heure_résultat"
        )
        cfg["export"]["auto_export"] = self._auto_export_chk.isChecked()
        cfg["export"]["destination_auto"] = (
            self._dest_auto_btn.property("choice_value") or "Dossier local"
        )
        save_config(_CONFIG_PATH, cfg)
        self._main_stack.setCurrentIndex(1)

    # ------------------------------------------------------------------
    def _detect_usb(self) -> None:
        from core.export_manager import ExportWorker

        self._btn_detect.setEnabled(False)
        self._btn_detect.setText("⏳  Recherche...")
        self._worker_detect = ExportWorker(task="detect")
        self._worker_detect.drives_detected.connect(self._on_drives_detected)
        self._worker_detect.task_done.connect(self._on_detect_done)
        self._worker_detect.start()

    def _on_drives_detected(self, drives: list) -> None:
        self._detected_drives = drives

    def _on_detect_done(self, success: bool, message: str) -> None:
        self._btn_detect.setEnabled(True)
        self._btn_detect.setText("🔍  Détecter les clés USB")
        self._worker_detect = None
        self._usb_status_lbl.setText(message)
        if success:
            self._usb_status_lbl.setStyleSheet("color: #1D9E75; font-size: 14px;")
        else:
            self._usb_status_lbl.setStyleSheet("color: #888888; font-size: 14px;")

    def _do_export_usb(self) -> None:
        if not self._detected_drives:
            QMessageBox.warning(
                self,
                "Export USB",
                "Aucune clé USB détectée.\nBranchez une clé USB et cliquez sur Détecter.",
            )
            return

        self._btn_export.setEnabled(False)
        self._btn_export.setText("⏳  Export en cours...")

        from core.export_manager import ExportWorker

        cfg = _load_cfg_safe()
        data_dir = Path(cfg.get("storage", {}).get("data_dir", "./data"))
        filtre = self._filtre_btn.property("choice_value") or "OK+NOK"

        self._worker_usb = ExportWorker(
            task="usb",
            source_dir=data_dir,
            usb_path=self._detected_drives[0],
            filter_result=filtre,
        )
        self._worker_usb.task_done.connect(self._on_export_done)
        self._worker_usb.start()

    def _on_export_done(self, success: bool, message: str) -> None:
        print(f"[DEBUG] _on_export_done: success={success}, msg={message}")
        self._btn_export.setEnabled(True)
        self._btn_export.setText("💾  Exporter vers la clé USB")
        self._worker_usb = None  # nettoyage manuel
        print("[DEBUG] Bouton export réactivé")
        if success:
            QMessageBox.information(self, "Export USB terminé", message)
        else:
            QMessageBox.warning(self, "Export USB", f"Erreur : {message}")

    def _do_generate_pdf(self) -> None:
        self._btn_pdf.setEnabled(False)
        self._btn_pdf.setText("⏳  Génération en cours...")

        from core.export_manager import ExportWorker

        cfg = _load_cfg_safe()
        data_dir = Path(cfg.get("storage", {}).get("data_dir", "./data"))
        contenu = self._contenu_btn.property("choice_value") or "Tous les cycles"
        periode = self._periode_btn.property("choice_value") or "Aujourd'hui"

        _PERIODE_TO_FILTER = {
            "Aujourd'hui":       "today",
            "7 derniers jours":  "last7",
            "30 derniers jours": "last30",
            "Tout l'historique": None,
        }
        date_filter = _PERIODE_TO_FILTER.get(periode, "today")

        cycles_data = _build_cycles_from_csv(data_dir, contenu, date_filter)

        if self._detected_drives:
            output_dir = Path(self._detected_drives[0]) / "ACM_Export"
        else:
            output_dir = data_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = output_dir / f"rapport_{timestamp}.pdf"

        self._worker_pdf = ExportWorker(
            task="pdf",
            cycles_data=cycles_data,
            output_path=output_path,
            machine_name="ACM Riveteuse",
            periode=periode,
        )
        self._worker_pdf.task_done.connect(self._on_pdf_done)
        self._worker_pdf.start()

    def _on_pdf_done(self, success: bool, message: str) -> None:
        self._btn_pdf.setEnabled(True)
        self._btn_pdf.setText("📄  Générer rapport PDF")
        self._worker_pdf = None  # nettoyage manuel
        if success:
            QMessageBox.information(self, "Rapport PDF", message)
        else:
            QMessageBox.warning(self, "Rapport PDF", f"Erreur : {message}")


def _load_cfg_safe() -> dict:
    """Charge config.yaml sans lever d'exception."""
    try:
        return load_config(_CONFIG_PATH)
    except Exception:
        return {}


def _build_cycles_from_csv(
    data_dir: Path,
    contenu: str,
    date_filter: str | None = None,
) -> list[dict]:
    """Reconstruit une liste de dicts cycles depuis les fichiers CSV.

    Format nom : YYYYMMDD_HHMMSS_PMxx_RESULT.csv
    Colonnes CSV : time_s, force_n, position_mm  (cf. core/storage.py)

    date_filter : "today" | "last7" | "last30" | None (tout l'historique)
    """
    import csv as _csv
    from datetime import timedelta

    # Calculer la date de coupure
    today_str = datetime.now().strftime("%Y%m%d")
    if date_filter == "today":
        cutoff = today_str
        exact = True
    elif date_filter == "last7":
        cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")
        exact = False
    elif date_filter == "last30":
        cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
        exact = False
    else:
        cutoff = None
        exact = False

    cycles: list[dict] = []
    if not data_dir.exists():
        return cycles

    for i, csv_file in enumerate(sorted(data_dir.glob("*.csv")), start=1):
        name = csv_file.stem.upper()
        result = "PASS" if "PASS" in name else "NOK"

        if contenu == "Cycles NOK uniquement" and result == "PASS":
            continue

        # Extraire timestamp depuis le nom (YYYYMMDD_HHMMSS_...)
        parts = csv_file.stem.split("_")
        timestamp_str = ""
        date_str = ""
        if len(parts) >= 2:
            try:
                dt = datetime.strptime(f"{parts[0]}_{parts[1]}", "%Y%m%d_%H%M%S")
                timestamp_str = dt.strftime("%d/%m/%Y %H:%M:%S")
                date_str = parts[0]
            except ValueError:
                timestamp_str = csv_file.stem[:15]

        # Appliquer le filtre de date
        if cutoff and date_str:
            if exact and date_str != cutoff:
                continue
            if not exact and date_str < cutoff:
                continue

        # Lire le contenu CSV pour extraire Fmax et Xmax réels
        fmax, xmax = 0.0, 0.0
        try:
            with open(csv_file, newline="", encoding="utf-8") as f:
                reader = _csv.DictReader(f)
                for row in reader:
                    try:
                        force = float(row.get("force_n", 0) or 0)
                        pos   = float(row.get("position_mm", 0) or 0)
                        if force > fmax:
                            fmax = force
                        if pos > xmax:
                            xmax = pos
                    except (ValueError, TypeError):
                        continue
        except Exception as e:
            print(f"[EXPORT] Erreur lecture {csv_file.name}: {e}")

        cycles.append(
            {
                "cycle_num": i,
                "result":    result,
                "timestamp": timestamp_str,
                "fmax":      fmax,
                "xmax":      xmax,
                "points":    [],
            }
        )
    return cycles


# ===========================================================================
# _ExtrasPage — Modbus / Réseau / Infos système  (index 12)
# ===========================================================================

def _extras_section_header(title: str) -> QLabel:
    lbl = QLabel(title)
    lbl.setStyleSheet(
        "background-color: #444444; color: #C49A3C; font-size: 14px; "
        "font-weight: bold; padding: 8px; border-radius: 6px; "
        "margin-top: 10px;"
    )
    return lbl


class _ExtrasPage(QWidget):
    """Page Extras : Modbus TCP · Réseau · Informations système (index 12)."""

    def __init__(self, stack: QStackedWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._main_stack = stack
        self.setStyleSheet(_DIALOG_STYLE)
        self._build_ui()

    # ------------------------------------------------------------------
    def showEvent(self, event) -> None:
        self._load_all()
        super().showEvent(event)

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ──────────────────────────────────────────────────
        hdr = QLabel("⚙   Extras")
        hdr.setStyleSheet(
            f"background-color: {_C['header_bg']}; color: {_C['text']}; "
            "font-size: 20px; font-weight: bold; padding: 14px 20px;"
        )
        root.addWidget(hdr)

        # ── Scroll ───────────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background-color: transparent;")

        content = QWidget()
        content.setStyleSheet(f"background-color: {_C['bg']};")
        v = QVBoxLayout(content)
        v.setContentsMargins(20, 10, 20, 20)
        v.setSpacing(8)

        # ── Section 1 : Modbus ───────────────────────────────────────
        v.addWidget(_extras_section_header("🔌 Connexion Modbus TCP"))

        cfg = _load_cfg_safe()
        mb = cfg.get("modbus", {})

        fw_mb = QFrame()
        fw_mb.setStyleSheet(
            f"background-color: {_C['panel']}; border-radius: 8px; padding: 4px;"
        )
        form_mb = QFormLayout(fw_mb)
        form_mb.setContentsMargins(12, 10, 12, 10)
        form_mb.setSpacing(10)
        form_mb.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._mb_host_btn = _make_alpha_btn(
            mb.get("host", "10.0.0.1"),
            title="IP Automate",
            parent=self,
        )
        self._mb_port_btn = _make_numpad_btn(
            str(mb.get("port", 502)),
            suffix="",
            title="Port Modbus",
            parent=self,
        )
        self._mb_poll_btn = _make_numpad_btn(
            str(mb.get("poll_interval_ms", 50)),
            suffix=" ms",
            title="Intervalle poll",
            parent=self,
        )

        form_mb.addRow(QLabel("IP Automate :"), self._mb_host_btn)
        form_mb.addRow(QLabel("Port Modbus :"), self._mb_port_btn)
        form_mb.addRow(QLabel("Intervalle poll :"), self._mb_poll_btn)

        btn_apply_mb = QPushButton("✓  Appliquer")
        btn_apply_mb.setObjectName("btn_save")
        btn_apply_mb.clicked.connect(self._apply_modbus)
        form_mb.addRow("", btn_apply_mb)

        v.addWidget(fw_mb)

        # ── Section 2 : Réseau ───────────────────────────────────────
        v.addWidget(_extras_section_header("🌐 Réseau Raspberry Pi"))

        fw_net = QFrame()
        fw_net.setStyleSheet(
            f"background-color: {_C['panel']}; border-radius: 8px; padding: 4px;"
        )
        form_net = QFormLayout(fw_net)
        form_net.setContentsMargins(12, 10, 12, 10)
        form_net.setSpacing(10)
        form_net.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        net = cfg.get("network", {})

        # eth0
        lbl_eth0 = QLabel("── eth0 (automate) ──")
        lbl_eth0.setStyleSheet("color: #C49A3C; font-weight: bold;")
        form_net.addRow(lbl_eth0)

        self._eth0_ip_btn = _make_alpha_btn(
            net.get("eth0_ip", "10.0.0.2"),
            title="IP fixe eth0",
            parent=self,
        )
        self._eth0_mask_btn = _make_choice_btn(
            ["/24 (255.255.255.0)", "/16 (255.255.0.0)", "/8 (255.0.0.0)"],
            net.get("eth0_mask", "/24 (255.255.255.0)"),
            "Masque réseau",
            self,
        )
        form_net.addRow(QLabel("IP fixe eth0 :"), self._eth0_ip_btn)
        form_net.addRow(QLabel("Masque réseau :"), self._eth0_mask_btn)

        btn_apply_eth0 = QPushButton("✓  Appliquer eth0")
        btn_apply_eth0.setObjectName("btn_save")
        btn_apply_eth0.clicked.connect(self._apply_eth0)
        form_net.addRow("", btn_apply_eth0)

        # WiFi (lecture seule)
        lbl_wifi = QLabel("── WiFi (réseau entreprise) ──")
        lbl_wifi.setStyleSheet("color: #C49A3C; font-weight: bold; margin-top: 6px;")
        form_net.addRow(lbl_wifi)

        self._wifi_ip_lbl = QLabel("—")
        self._wifi_ssid_lbl = QLabel("—")
        form_net.addRow(QLabel("IP WiFi :"), self._wifi_ip_lbl)
        form_net.addRow(QLabel("SSID :"), self._wifi_ssid_lbl)

        note_wifi = QLabel(
            "ℹ La config WiFi se fait via raspi-config ou l'interface graphique du Pi."
        )
        note_wifi.setWordWrap(True)
        note_wifi.setStyleSheet("color: #AAAAAA; font-size: 12px;")
        form_net.addRow(note_wifi)

        btn_refresh_net = QPushButton("🔄  Rafraîchir réseau")
        btn_refresh_net.setObjectName("btn_nav")
        btn_refresh_net.clicked.connect(self._refresh_network)
        form_net.addRow("", btn_refresh_net)

        v.addWidget(fw_net)

        # ── Section 3 : Infos système ────────────────────────────────
        v.addWidget(_extras_section_header("ℹ️ Informations système"))

        fw_sys = QFrame()
        fw_sys.setStyleSheet(
            f"background-color: {_C['panel']}; border-radius: 8px; padding: 4px;"
        )
        form_sys = QFormLayout(fw_sys)
        form_sys.setContentsMargins(12, 10, 12, 10)
        form_sys.setSpacing(10)
        form_sys.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._sys_labels: dict[str, QLabel] = {}
        for key in ("version", "modele", "os", "uptime", "disque", "ram", "temp"):
            lbl = QLabel("—")
            lbl.setWordWrap(True)
            self._sys_labels[key] = lbl

        form_sys.addRow(QLabel("Version logiciel :"), self._sys_labels["version"])
        form_sys.addRow(QLabel("Modèle Pi :"), self._sys_labels["modele"])
        form_sys.addRow(QLabel("OS :"), self._sys_labels["os"])
        form_sys.addRow(QLabel("Uptime :"), self._sys_labels["uptime"])
        form_sys.addRow(QLabel("Espace disque :"), self._sys_labels["disque"])
        form_sys.addRow(QLabel("RAM utilisée :"), self._sys_labels["ram"])
        form_sys.addRow(QLabel("Température CPU :"), self._sys_labels["temp"])

        btn_refresh_sys = QPushButton("🔄  Rafraîchir infos")
        btn_refresh_sys.setObjectName("btn_nav")
        btn_refresh_sys.clicked.connect(self._refresh_sysinfo)
        form_sys.addRow("", btn_refresh_sys)

        v.addWidget(fw_sys)
        v.addStretch()

        scroll.setWidget(content)
        root.addWidget(scroll, stretch=1)

        # ── Footer ───────────────────────────────────────────────────
        footer = QFrame()
        footer.setObjectName("footer_bar")
        footer.setStyleSheet(
            f"background-color: {_C['header_bg']}; border-top: 1px solid {_C['border']};"
        )
        fh = QHBoxLayout(footer)
        fh.setContentsMargins(16, 8, 16, 8)
        btn_back = QPushButton("←  Retour")
        btn_back.setObjectName("btn_cancel")
        btn_back.clicked.connect(
            lambda: self._main_stack.setCurrentIndex(1)
        )
        fh.addWidget(btn_back)
        fh.addStretch()
        root.addWidget(footer)

    # ------------------------------------------------------------------
    def _load_all(self) -> None:
        cfg = _load_cfg_safe()
        mb = cfg.get("modbus", {})
        # Recharger les valeurs Modbus dans les boutons
        _btn_set_alpha(self._mb_host_btn, mb.get("host", "10.0.0.1"))
        _btn_set_numpad(self._mb_port_btn, str(mb.get("port", 502)), "")
        _btn_set_numpad(self._mb_poll_btn, str(mb.get("poll_interval_ms", 50)), " ms")
        # Réseau
        net = cfg.get("network", {})
        _btn_set_alpha(self._eth0_ip_btn, net.get("eth0_ip", "10.0.0.2"))
        mask = net.get("eth0_mask", "/24 (255.255.255.0)")
        self._eth0_mask_btn.setProperty("choice_value", mask)
        self._eth0_mask_btn.setText(mask)
        # Sys info + réseau
        self._refresh_sysinfo()
        self._refresh_network()

    # ------------------------------------------------------------------
    def _apply_modbus(self) -> None:
        host = self._mb_host_btn.property("alpha_value") or "10.0.0.1"
        port_str = self._mb_port_btn.property("numpad_value") or "502"
        poll_str = self._mb_poll_btn.property("numpad_value") or "50"
        try:
            port = int(port_str)
            poll = int(poll_str)
        except ValueError:
            QMessageBox.warning(self, "Modbus", "Port et intervalle doivent être des entiers.")
            return
        cfg = _load_cfg_safe()
        cfg.setdefault("modbus", {})
        cfg["modbus"]["host"] = host
        cfg["modbus"]["port"] = port
        cfg["modbus"]["poll_interval_ms"] = poll
        save_config(_CONFIG_PATH, cfg)
        QMessageBox.information(self, "Modbus", "Configuration sauvegardée.\nRedémarrez pour appliquer.")

    # ------------------------------------------------------------------
    def _apply_eth0(self) -> None:
        import subprocess
        ip = self._eth0_ip_btn.property("alpha_value") or "10.0.0.2"
        mask_full = self._eth0_mask_btn.property("choice_value") or "/24 (255.255.255.0)"
        # Extraire juste le préfixe "/24" depuis "/24 (255.255.255.0)"
        prefix = mask_full.split()[0]  # "/24"
        address = f"{ip}{prefix}"

        nmcli_args = [
            "sudo", "nmcli", "connection", "modify", "Wired connection 1",
            "ipv4.addresses", address,
            "ipv4.method", "manual",
        ]
        try:
            result = subprocess.run(nmcli_args, capture_output=True, text=True)
            if result.returncode != 0:
                # Réessai avec "eth0"
                nmcli_args[4] = "eth0"
                result = subprocess.run(nmcli_args, capture_output=True, text=True)
            if result.returncode == 0:
                cfg = _load_cfg_safe()
                cfg.setdefault("network", {})
                cfg["network"]["eth0_ip"] = ip
                cfg["network"]["eth0_mask"] = mask_full
                save_config(_CONFIG_PATH, cfg)
                QMessageBox.information(
                    self, "Réseau", f"eth0 configurée : {address}\nRedémarrez pour appliquer."
                )
            else:
                QMessageBox.warning(
                    self, "Réseau", f"Erreur nmcli :\n{result.stderr.strip()}"
                )
        except Exception as e:
            QMessageBox.warning(self, "Réseau", f"Erreur : {e}")

    # ------------------------------------------------------------------
    def _refresh_network(self) -> None:
        import socket
        import subprocess

        # IP WiFi
        try:
            ip = socket.gethostbyname(socket.gethostname())
            self._wifi_ip_lbl.setText(ip)
        except Exception:
            self._wifi_ip_lbl.setText("—")

        # SSID
        try:
            res = subprocess.run(
                ["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"],
                capture_output=True, text=True, timeout=3,
            )
            ssid = "—"
            for line in res.stdout.splitlines():
                if line.startswith("yes:"):
                    ssid = line.split(":", 1)[1]
                    break
            self._wifi_ssid_lbl.setText(ssid)
        except Exception:
            self._wifi_ssid_lbl.setText("—")

    # ------------------------------------------------------------------
    def _refresh_sysinfo(self) -> None:
        import shutil

        # Version logiciel
        version_file = _CONFIG_PATH.parent / "VERSION.txt"
        try:
            self._sys_labels["version"].setText(
                version_file.read_text(encoding="utf-8").strip()
            )
        except Exception:
            self._sys_labels["version"].setText("1.0.0")

        # Modèle Pi
        try:
            model = Path("/proc/device-tree/model").read_bytes().rstrip(b"\x00").decode()
            self._sys_labels["modele"].setText(model)
        except Exception:
            self._sys_labels["modele"].setText("—")

        # OS
        try:
            os_info = "—"
            for line in Path("/etc/os-release").read_text().splitlines():
                if line.startswith("PRETTY_NAME="):
                    os_info = line.split("=", 1)[1].strip('"')
                    break
            self._sys_labels["os"].setText(os_info)
        except Exception:
            self._sys_labels["os"].setText("—")

        # Uptime
        try:
            up_secs = int(float(Path("/proc/uptime").read_text().split()[0]))
            jours = up_secs // 86400
            heures = (up_secs % 86400) // 3600
            minutes = (up_secs % 3600) // 60
            self._sys_labels["uptime"].setText(
                f"{jours} j  {heures} h  {minutes} min"
            )
        except Exception:
            self._sys_labels["uptime"].setText("—")

        # Espace disque
        try:
            du = shutil.disk_usage("/")
            used_go = du.used / 1e9
            total_go = du.total / 1e9
            pct = du.used / du.total * 100
            self._sys_labels["disque"].setText(
                f"{used_go:.1f} Go utilisés / {total_go:.1f} Go total ({pct:.0f}%)"
            )
        except Exception:
            self._sys_labels["disque"].setText("—")

        # RAM
        try:
            mem_total = mem_avail = 0
            for line in Path("/proc/meminfo").read_text().splitlines():
                if line.startswith("MemTotal:"):
                    mem_total = int(line.split()[1]) // 1024
                elif line.startswith("MemAvailable:"):
                    mem_avail = int(line.split()[1]) // 1024
            mem_used = mem_total - mem_avail
            self._sys_labels["ram"].setText(
                f"{mem_used} Mo utilisés / {mem_total} Mo total"
            )
        except Exception:
            self._sys_labels["ram"].setText("—")

        # Température CPU
        try:
            raw = int(Path("/sys/class/thermal/thermal_zone0/temp").read_text())
            temp = raw / 1000.0
            color = "#4caf50" if temp < 60 else ("#f57f17" if temp < 70 else "#ef5350")
            self._sys_labels["temp"].setText(f"{temp:.1f} °C")
            self._sys_labels["temp"].setStyleSheet(f"color: {color};")
        except Exception:
            self._sys_labels["temp"].setText("—")


def _btn_set_alpha(btn: QPushButton, value: str) -> None:
    btn.setProperty("alpha_value", value)
    btn.setText(value or "—")


def _btn_set_numpad(btn: QPushButton, value: str, suffix: str) -> None:
    btn.setProperty("numpad_value", value)
    btn.setText(f"{value}{suffix}")


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

        self._cycle_page = _ControleCyclePage(self._settings_stack, self)
        self._settings_stack.addWidget(self._cycle_page)                # 4
        self._voie_x_page = _VoieXPage(self._settings_stack, self)
        self._settings_stack.addWidget(self._voie_x_page)               # 5
        self._voie_y_page = _VoieYPage(self._settings_stack, self)
        self._settings_stack.addWidget(self._voie_y_page)               # 6
        self._pm_edit_page = _PMEditPage(
            self._settings_stack, self._on_pm_saved, self
        )
        self._settings_stack.addWidget(self._pm_edit_page)              # 7
        self._date_heure_page = _DateHeurePage(self._settings_stack, self)
        self._settings_stack.addWidget(self._date_heure_page)           # 8
        self._droits_page = _DroitsAccesPage(self._settings_stack, self)
        self._settings_stack.addWidget(self._droits_page)               # 9
        self._affichage_page = _AffichageProdPage(self._settings_stack, self)
        self._settings_stack.addWidget(self._affichage_page)            # 10
        self._export_page = _ExportationPage(self._settings_stack, self)
        self._settings_stack.addWidget(self._export_page)               # 11
        self._extras_page = _ExtrasPage(self._settings_stack, self)
        self._settings_stack.addWidget(self._extras_page)               # 12

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
            ("🔒", "Droits d'accès",  0, 1, "droits"),
            ("📅", "Date / Heure",    0, 2, "date_heure"),
            ("📊", "Voie X",          1, 0, "voie_x"),
            ("📡", "Voie Y",          1, 1, "voie_y"),
            ("⏱",  "Contrôle cycle", 1, 2, "cycle"),
            ("🖥",  "Affichage prod.",2, 0, "affichage"),
            ("💾", "Exportation",     2, 1, "exportation"),
            ("⚙",  "Extras",         2, 2, "extras"),
        ]
        for icon, label, row, col, action in buttons:
            btn = QPushButton(f"{icon}\n{label}")
            btn.setFixedSize(180, 120)
            btn.setStyleSheet(_BTN_STYLE)
            if action == "voie_x":
                btn.clicked.connect(
                    lambda checked=False: self._settings_stack.setCurrentIndex(5)
                )
            elif action == "voie_y":
                btn.clicked.connect(
                    lambda checked=False: self._settings_stack.setCurrentIndex(6)
                )
            elif action == "cycle":
                btn.clicked.connect(
                    lambda checked=False: self._settings_stack.setCurrentIndex(4)
                )
            elif action == "date_heure":
                btn.clicked.connect(
                    lambda checked=False: self._settings_stack.setCurrentIndex(8)
                )
            elif action == "droits":
                btn.clicked.connect(
                    lambda checked=False: self._settings_stack.setCurrentIndex(9)
                )
            elif action == "affichage":
                btn.clicked.connect(
                    lambda checked=False: self._settings_stack.setCurrentIndex(10)
                )
            elif action == "exportation":
                btn.clicked.connect(
                    lambda checked=False: self._settings_stack.setCurrentIndex(11)
                )
            elif action == "extras":
                btn.clicked.connect(
                    lambda checked=False: self._settings_stack.setCurrentIndex(12)
                )
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
        self._pm_edit_page.load_pm(pm_id)
        self._settings_stack.setCurrentIndex(7)

    def _on_pm_saved(self, pm_id: int) -> None:
        row = pm_id - 1
        item = self._pm_list.item(row)
        if item:
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