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
            background-color: #2a2a2a;
            color: #ffffff;
            border: 1.5px solid #444;
            border-radius: 6px;
            padding: 6px 12px;
            font-size: 15px;
            min-height: 42px;
            text-align: right;
        }
        QPushButton:pressed { border-color: #378ADD; }
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
            background-color: #2a2a2a;
            color: #ffffff;
            border: 1.5px solid #444;
            border-radius: 6px;
            padding: 6px 12px;
            font-size: 15px;
            min-height: 42px;
            text-align: left;
        }
        QPushButton:pressed { border-color: #378ADD; }
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
QPushButton#btn_nav {
    background-color: #185FA5;
    color: #ffffff;
    font-size: 14px;
    font-weight: bold;
    border: none;
    border-radius: 8px;
    min-height: 44px;
    min-width: 120px;
}
QPushButton#btn_nav:pressed { background-color: #0d4a80; }
QPushButton#btn_nav:disabled { background-color: #2a2a2a; color: #555555; }
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
            ("⏱",  "Contrôle cycle", 1, 2, "cycle"),
            ("🖥",  "Affichage prod.",2, 0, None),
            ("💾", "Exportation",     2, 1, None),
            ("⚙",  "Extras",         2, 2, None),
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