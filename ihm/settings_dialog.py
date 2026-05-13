"""Page de réglages — intégrée dans self.stack de MainWindow (index 1).

Architecture QStackedWidget interne (self._settings_stack) :
    Page 0 : Accueil Réglages    (2 grandes tuiles de navigation)
  Page 1 : Paramètres généraux (grille 3×3 de boutons)
    Page 2 : Gestion PM          (tableau + actions)

Chaque page enfant a son propre header avec titre + bouton ← Retour.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QPointF, Signal, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF, QPixmap, QIcon
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
from ihm.translations import t, get_language
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
            background-color: #FAFAF8;
            color: #1A1A18;
            border: 1.5px solid #C8C4BC;
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
            background-color: #FAFAF8;
            color: #1A1A18;
            border: 1.5px solid #C8C4BC;
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
    "bg":         "#F0EDE6",
    "panel":      "#E8E4DC",
    "card":       "#FAFAF8",
    "border":     "#C8C4BC",
    "header_bg":  "#E8E4DC",
    "text":       "#1A1A18",
    "text_dim":   "#4A4844",
    "btn_bg":     "#FAFAF8",
    "btn_border": "#C8C4BC",
    "btn_active": "#A07830",
    "ok_green":   "#2E7D32",
    "nok_red":    "#C62828",
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
    font-size: 30px;
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
QListWidget::item:selected {{ background-color: {_C['btn_active']}; color: #1A1A18; }}

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
# Feuille de style — dialogues Coordonnée X / Coordonnée Y
# ---------------------------------------------------------------------------
_DIALOG_STYLE = """
QDialog, QWidget {
    background-color: #FAFAF8;
    color: #1A1A18;
    font-family: 'Segoe UI', Arial, sans-serif;
}
QLabel {
    background-color: transparent;
    font-size: 15px;
    color: #1A1A18;
}
QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox {
    background-color: #FAFAF8;
    color: #1A1A18;
    border: 1.5px solid #C8C4BC;
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
    background-color: #FAFAF8;
    color: #1A1A18;
    selection-background-color: #A07830;
}
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button,
QSpinBox::up-button,       QSpinBox::down-button {
    background-color: #C8C4BC;
    border: none;
    width: 20px;
}
QPushButton#btn_save {
    background-color: #C49A3C;
    color: #ffffff;
    font-size: 18px;
    font-weight: bold;
    border: none;
    border-radius: 8px;
    min-height: 54px;
    min-width: 160px;
}
QPushButton#btn_save:pressed { background-color: #A07830; }
QPushButton#btn_cancel {
    background-color: #FAFAF8;
    color: #4A4844;
    font-size: 14px;
    font-weight: bold;
    border: 1px solid #C8C4BC;
    border-radius: 8px;
    min-height: 44px;
    min-width: 160px;
}
QPushButton#btn_cancel:pressed { background-color: #E8E4DC; }
QPushButton#btn_nav {
    background-color: #A07830;
    color: #1A1A18;
    font-size: 30px;
    font-weight: bold;
    border: none;
    border-radius: 8px;
    min-height: 44px;
    min-width: 120px;
}
QPushButton#btn_nav:pressed { background-color: #7a5c24; }
QPushButton#btn_nav:disabled { background-color: #C8C4BC; color: #7A7870; }
QCheckBox {
    font-size: 15px; color: #1A1A18; spacing: 8px;
    min-height: 42px; background: transparent;
}
QCheckBox::indicator {
    width: 22px; height: 22px; background-color: #FAFAF8;
    border: 1.5px solid #C8C4BC; border-radius: 4px;
}
QCheckBox::indicator:checked { background-color: #F1F8E9; border-color: #2d7a2d; }
"""


# ---------------------------------------------------------------------------
# Style QTabWidget pour PMEditDialog
# ---------------------------------------------------------------------------
_PM_EDIT_STYLE = _DIALOG_STYLE + """
QTabWidget::pane { background-color: #FAFAF8; border: none; }
QTabBar::tab {
    background: #E8E4DC; color: #4A4844; padding: 10px 20px;
    font-size: 14px; border-radius: 6px 6px 0 0; margin-right: 2px;
}
QTabBar::tab:selected { background: #FAFAF8; color: #1A1A18; border-bottom: 2px solid #C49A3C; }
QCheckBox {
    font-size: 15px; color: #1A1A18; spacing: 8px;
    min-height: 42px; background: transparent;
}
QCheckBox::indicator {
    width: 22px; height: 22px; background-color: #FAFAF8;
    border: 1.5px solid #C8C4BC; border-radius: 4px;
}
QCheckBox::indicator:checked { background-color: #F1F8E9; border-color: #2d7a2d; }
"""


# ===========================================================================
# Barre de titre commune — utilisée par toutes les pages de réglages
# ===========================================================================

def _make_header(
    titre: str,
    callback_retour,
    *,
    label_ref: list | None = None,
) -> QWidget:
    """Barre titre unifiée 56px : ← Retour + label titre."""
    barre = QWidget()
    barre.setFixedHeight(56)
    barre.setStyleSheet("background:#f5f4f0; border-bottom:2px solid #dddddd;")
    layout = QHBoxLayout(barre)
    layout.setContentsMargins(8, 0, 8, 0)
    layout.setSpacing(12)

    btn = QPushButton("← Retour")
    btn.setFixedSize(130, 40)
    btn.setStyleSheet(
        "QPushButton {"
        "background:#ffffff; border:1.5px solid #dddddd;"
        "border-radius:8px; color:#333333; font-size:14px; font-weight:bold;}"
        "QPushButton:pressed { background:#eeeeee; }"
    )
    btn.clicked.connect(callback_retour)
    layout.addWidget(btn)

    lbl = QLabel(titre)
    lbl.setStyleSheet(
        "font-size:20px; font-weight:bold; color:#333333; border:none; background:transparent;"
    )
    lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
    layout.addWidget(lbl, stretch=1)

    if label_ref is not None:
        label_ref.append(lbl)
    return barre


def _make_voie_footer(
    left_text: str,
    left_callback,
    right_text: str,
    right_callback,
    *,
    primary: bool,
) -> QWidget:
    """Footer commun VoieX/VoieY : bouton gauche stretch=1, bouton droit stretch=2."""
    w = QWidget()
    w.setStyleSheet("background-color: #F0EDE6;")
    h = QHBoxLayout(w)
    h.setContentsMargins(10, 6, 10, 6)
    h.setSpacing(10)

    btn_l = QPushButton(left_text)
    btn_l.setFixedHeight(60)
    btn_l.setStyleSheet(
        "QPushButton { background:#ffffff; border:1.5px solid #dddddd;"
        " border-radius:8px; color:#333333; font-size:16px; font-weight:bold; }"
        "QPushButton:pressed { background:#eeeeee; }"
    )
    btn_l.clicked.connect(left_callback)
    h.addWidget(btn_l, stretch=1)

    btn_r = QPushButton(right_text)
    btn_r.setFixedHeight(60)
    if primary:
        btn_r.setStyleSheet(
            "QPushButton { background:#C49A3C; border:none; border-radius:0px;"
            " color:#ffffff; font-size:16px; font-weight:bold; }"
            "QPushButton:pressed { background:#A07830; }"
        )
    else:
        btn_r.setStyleSheet(
            "QPushButton { background:#A07830; border:none; border-radius:8px;"
            " color:#ffffff; font-size:16px; font-weight:bold; }"
            "QPushButton:pressed { background:#7a5c24; }"
        )
    btn_r.clicked.connect(right_callback)
    h.addWidget(btn_r, stretch=2)
    return w


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
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            w, h = self.width(), self.height()
            mx, my = 24, 8
            ws_x, ws_y, ws_w, ws_h = mx, my, w - 2 * mx, h - 2 * my - 16
            p.fillRect(ws_x, ws_y, ws_w, ws_h, QColor("#FAFAF8"))
            p.setPen(QPen(QColor("#C8C4BC"), 1))
            p.drawRect(ws_x, ws_y, ws_w, ws_h)
            X_MAX, Y_MAX = 500.0, 6000.0

            def fx(v):
                return ws_x + (v / X_MAX) * ws_w

            def fy(v):
                return ws_y + ws_h - (v / Y_MAX) * ws_h

            rx1, rx2 = int(fx(self._x_min.value())), int(fx(self._x_max.value()))
            ry_top, ry_bot = ws_y, int(fy(self._y_limit.value()))
            if rx2 > rx1 and ry_bot > ry_top:
                p.fillRect(rx1, ry_top, rx2 - rx1, ry_bot - ry_top, QColor(226, 75, 74, 80))
                p.setPen(QPen(QColor("#E24B4A"), 1.5))
                p.drawRect(rx1, ry_top, rx2 - rx1, ry_bot - ry_top)
            p.setPen(QPen(QColor("#7A7870"), 1))
            p.setFont(QFont("Arial", 9))
            p.drawText(ws_x, ws_y + ws_h + 13, "Aperçu NO-PASS  (X = position mm, Y = force N)")
        finally:
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
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            w, h = self.width(), self.height()
            mx, my = 24, 8
            ws_x, ws_y, ws_w, ws_h = mx, my, w - 2 * mx, h - 2 * my - 16
            p.fillRect(ws_x, ws_y, ws_w, ws_h, QColor("#FAFAF8"))
            p.setPen(QPen(QColor("#C8C4BC"), 1))
            p.drawRect(ws_x, ws_y, ws_w, ws_h)
            X_MAX, Y_MAX = 500.0, 6000.0

            def fx(v):
                return ws_x + (v / X_MAX) * ws_w

            def fy(v):
                return ws_y + ws_h - (v / Y_MAX) * ws_h

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
            p.setPen(QPen(QColor("#7A7870"), 1))
            p.setFont(QFont("Arial", 9))
            p.drawText(ws_x, ws_y + ws_h + 13, "Aperçu UNI-BOX  (vert = entrée, rouge = sortie)")
        finally:
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
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            w, h = self.width(), self.height()
            mx, my = 24, 8
            ws_x, ws_y, ws_w, ws_h = mx, my, w - 2 * mx, h - 2 * my - 16
            p.fillRect(ws_x, ws_y, ws_w, ws_h, QColor("#FAFAF8"))
            p.setPen(QPen(QColor("#C8C4BC"), 1))
            p.drawRect(ws_x, ws_y, ws_w, ws_h)
            lower, upper = self._read(self._lower), self._read(self._upper)
            if len(lower) < 2 or len(upper) < 2:
                p.setPen(QPen(QColor("#666"), 1))
                p.setFont(QFont("Arial", 10))
                p.drawText(ws_x + 10, ws_y + ws_h // 2 + 4, "≥ 2 points requis dans chaque courbe")
                return
            all_pts = lower + upper
            x0, x1 = min(pt[0] for pt in all_pts), max(pt[0] for pt in all_pts)
            y0, y1 = min(0.0, min(pt[1] for pt in all_pts)), max(pt[1] for pt in all_pts)
            if x1 == x0:
                x1 += 1
            if y1 == y0:
                y1 += 1

            def fx(v):
                return ws_x + (v - x0) / (x1 - x0) * ws_w

            def fy(v):
                return ws_y + ws_h - (v - y0) / (y1 - y0) * ws_h

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
            p.setPen(QPen(QColor("#7A7870"), 1))
            p.setFont(QFont("Arial", 9))
            p.drawText(ws_x, ws_y + ws_h + 13, "Aperçu ENVELOPPE  (vert = basse, rouge = haute)")
        finally:
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
        _lbl_ref: list = []
        root.addWidget(_make_header(
            f"{t('table_col_pm')}-{self._pm_id:02d} — {self._pm_name}",
            lambda: self._main_stack.setCurrentIndex(1),
            label_ref=_lbl_ref,
        ))
        self._title_lbl = _lbl_ref[0]
        # Onglets
        tabs = QTabWidget()
        tabs.addTab(self._build_tab_general(),  t("tab_general"))
        tabs.addTab(self._build_tab_no_pass(),  t("tab_nopass"))
        tabs.addTab(self._build_tab_uni_box(),  t("tab_unibox"))
        tabs.addTab(self._build_tab_envelope(), t("tab_enveloppe"))
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
            "background-color: #FAFAF8; border: 1px solid #C8C4BC; border-radius: 6px; "
            "padding: 10px; font-size: 13px; color: #4A4844;"
        )
        lbl.setWordWrap(True)
        return lbl

    @staticmethod
    def _make_curve_table() -> QTableWidget:
        table = QTableWidget(6, 2)
        table.setHorizontalHeaderLabels([t("table_col_position_mm"), t("table_col_force_n")])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)
        return table

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
        return pts

    # ---- Onglet 1 — Général -----------------------------------------------

    def _build_tab_general(self) -> QWidget:
        w = QWidget()
        form = self._make_form(w)
        self._gen_name = _make_alpha_btn("", title=t("table_col_name"), parent=self)
        form.addRow(t("lbl_pm_name"), self._gen_name)
        self._gen_desc = _make_alpha_btn("", title="Description", parent=self)
        form.addRow(t("lbl_description"), self._gen_desc)
        self._gen_mode = QComboBox()
        self._gen_mode.addItem("Force = f(Position)", "FORCE_POSITION")
        self._gen_mode.addItem("Force = f(Temps)",    "FORCE_TIME")
        self._gen_mode.addItem("Position = f(Temps)", "POSITION_TIME")
        form.addRow(t("lbl_display_mode"), self._gen_mode)
        return w

    # ---- Onglet 2 — NO-PASS -----------------------------------------------

    def _build_tab_no_pass(self) -> QWidget:
        from config import MAX_NO_PASS_ZONES
        outer = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(10)
        v.addWidget(self._make_desc(
            "Zones interdites : si la courbe pénètre dans une zone active, le cycle est NOK.\n"
            "Jusqu'à 5 zones indépendantes. Cocher 'Actif' pour activer une zone."
        ))

        # En-tête colonnes
        hdr = QWidget()
        hdr_h = QHBoxLayout(hdr)
        hdr_h.setContentsMargins(0, 0, 0, 0)
        hdr_h.setSpacing(8)
        for txt, w_fixed in [("Zone", 60), ("Actif", 50), ("Pos min (mm)", 110),
                               ("Pos max (mm)", 110), ("Force max (daN)", 110), ("", 28), ("", 28)]:
            lbl = QLabel(txt)
            lbl.setStyleSheet("color: #4A4844; font-size: 11px; font-weight: bold;")
            if w_fixed:
                lbl.setFixedWidth(w_fixed)
            hdr_h.addWidget(lbl)
        v.addWidget(hdr)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {_C['border']}; max-height:1px;")
        v.addWidget(sep)

        self._np_enabled: list[QCheckBox]    = []
        self._np_x_min:   list[QPushButton]  = []
        self._np_x_max:   list[QPushButton]  = []
        self._np_y_limit: list[QPushButton]  = []
        self._np_preview: list[QLabel]       = []

        for i in range(MAX_NO_PASS_ZONES):
            row_w = QWidget()
            row_h = QHBoxLayout(row_w)
            row_h.setContentsMargins(0, 2, 0, 2)
            row_h.setSpacing(8)

            lbl_zone = QLabel(f"Zone {i + 1}")
            lbl_zone.setFixedWidth(60)
            lbl_zone.setStyleSheet("color: #1A1A18; font-size: 13px;")
            row_h.addWidget(lbl_zone)

            chk = QCheckBox()
            chk.setFixedWidth(50)
            self._np_enabled.append(chk)
            row_h.addWidget(chk)

            btn_xmin = _make_numpad_btn("0.0", suffix=" mm",
                                        title=f"Zone {i+1} — {t('position_label')} min", parent=self)
            btn_xmin.setFixedWidth(110)
            self._np_x_min.append(btn_xmin)
            row_h.addWidget(btn_xmin)

            btn_xmax = _make_numpad_btn("0.0", suffix=" mm",
                                        title=f"Zone {i+1} — {t('position_label')} max", parent=self)
            btn_xmax.setFixedWidth(110)
            self._np_x_max.append(btn_xmax)
            row_h.addWidget(btn_xmax)

            btn_ylim = _make_numpad_btn("0", suffix=" N",
                                        title=f"Zone {i+1} — {t('force_label')} limite", parent=self)
            btn_ylim.setFixedWidth(110)
            self._np_y_limit.append(btn_ylim)
            row_h.addWidget(btn_ylim)

            preview = QLabel()
            preview.setFixedSize(24, 24)
            preview.setStyleSheet("background-color: #C8C4BC; border-radius: 3px;")
            self._np_preview.append(preview)
            row_h.addWidget(preview)

            # Connecter checkbox → activer/désactiver la ligne
            chk.toggled.connect(lambda checked, idx=i: self._on_np_zone_toggled(idx, checked))

            v.addWidget(row_w)

        v.addStretch()
        scroll.setWidget(w)
        out_v = QVBoxLayout(outer)
        out_v.setContentsMargins(0, 0, 0, 0)
        out_v.addWidget(scroll)
        return outer

    def _on_np_zone_toggled(self, i: int, checked: bool) -> None:
        self._np_x_min[i].setEnabled(checked)
        self._np_x_max[i].setEnabled(checked)
        self._np_y_limit[i].setEnabled(checked)
        color = "#c62828" if checked else "#7A7870"
        self._np_preview[i].setStyleSheet(
            f"background-color: {color}; border-radius: 3px;"
        )

    # ---- Onglet 3 — UNI-BOX (multi-zones) -----------------------------------

    def _build_tab_uni_box(self) -> QWidget:
        from config import MAX_UNI_BOX_ZONES
        outer = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(10)
        v.addWidget(self._make_desc(
            "Boîtes de passage obligatoire : la courbe doit passer dans chaque zone active.\n"
            "Jusqu'à 5 zones indépendantes. Cocher 'Actif' pour activer une zone."
        ))

        # En-tête colonnes
        hdr = QWidget()
        hdr_h = QHBoxLayout(hdr)
        hdr_h.setContentsMargins(0, 0, 0, 0)
        hdr_h.setSpacing(8)
        for txt, w_fixed in [("Zone", 60), ("Actif", 50), ("Pos min (mm)", 110),
                               ("Pos max (mm)", 110), ("F min (daN)", 110),
                               ("F max (daN)", 110), ("", 28)]:
            lbl = QLabel(txt)
            lbl.setStyleSheet("color: #4A4844; font-size: 11px; font-weight: bold;")
            if w_fixed:
                lbl.setFixedWidth(w_fixed)
            hdr_h.addWidget(lbl)
        v.addWidget(hdr)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {_C['border']}; max-height:1px;")
        v.addWidget(sep)

        self._ub_enabled: list[QCheckBox]   = []
        self._ub_x_min:   list[QPushButton] = []
        self._ub_x_max:   list[QPushButton] = []
        self._ub_y_min:   list[QPushButton] = []
        self._ub_y_max:   list[QPushButton] = []
        self._ub_preview: list[QLabel]      = []

        for i in range(MAX_UNI_BOX_ZONES):
            row_w = QWidget()
            row_h = QHBoxLayout(row_w)
            row_h.setContentsMargins(0, 2, 0, 2)
            row_h.setSpacing(8)

            lbl_zone = QLabel(f"Zone {i + 1}")
            lbl_zone.setFixedWidth(60)
            lbl_zone.setStyleSheet("color: #1A1A18; font-size: 13px;")
            row_h.addWidget(lbl_zone)

            chk = QCheckBox()
            chk.setFixedWidth(50)
            self._ub_enabled.append(chk)
            row_h.addWidget(chk)

            btn_xmin = _make_numpad_btn("0.0", suffix=" mm",
                                        title=f"Zone {i+1} — {t('position_label')} min", parent=self)
            btn_xmin.setFixedWidth(110)
            self._ub_x_min.append(btn_xmin)
            row_h.addWidget(btn_xmin)

            btn_xmax = _make_numpad_btn("0.0", suffix=" mm",
                                        title=f"Zone {i+1} — {t('position_label')} max", parent=self)
            btn_xmax.setFixedWidth(110)
            self._ub_x_max.append(btn_xmax)
            row_h.addWidget(btn_xmax)

            btn_ymin = _make_numpad_btn("0", suffix=" N",
                                        title=f"Zone {i+1} — {t('force_label')} min", parent=self)
            btn_ymin.setFixedWidth(110)
            self._ub_y_min.append(btn_ymin)
            row_h.addWidget(btn_ymin)

            btn_ymax = _make_numpad_btn("0", suffix=" N",
                                        title=f"Zone {i+1} — {t('force_label')} max", parent=self)
            btn_ymax.setFixedWidth(110)
            self._ub_y_max.append(btn_ymax)
            row_h.addWidget(btn_ymax)

            preview = QLabel()
            preview.setFixedSize(24, 24)
            preview.setStyleSheet("background-color: #C8C4BC; border-radius: 3px;")
            self._ub_preview.append(preview)
            row_h.addWidget(preview)

            chk.toggled.connect(lambda checked, idx=i: self._on_ub_zone_toggled(idx, checked))

            v.addWidget(row_w)

        v.addStretch()
        scroll.setWidget(w)
        out_v = QVBoxLayout(outer)
        out_v.setContentsMargins(0, 0, 0, 0)
        out_v.addWidget(scroll)
        return outer

    def _on_ub_zone_toggled(self, i: int, checked: bool) -> None:
        self._ub_x_min[i].setEnabled(checked)
        self._ub_x_max[i].setEnabled(checked)
        self._ub_y_min[i].setEnabled(checked)
        self._ub_y_max[i].setEnabled(checked)
        color = "#FF9800" if checked else "#7A7870"
        self._ub_preview[i].setStyleSheet(
            f"background-color: {color}; border-radius: 3px;"
        )

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
            btn_add = QPushButton(t("btn_add_point"))
            btn_add.setObjectName("action_btn")
            btn_del = QPushButton(t("btn_delete"))
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

        # NO-PASS multi-zones
        np_zones = tools.get("no_pass_zones", [])
        # Compatibilité ancien format
        if not np_zones and tools.get("no_pass", {}).get("enabled"):
            old = tools["no_pass"]
            np_zones = [{"enabled": True, "x_min": old.get("x_min", 0.0),
                         "x_max": old.get("x_max", 0.0), "y_limit": old.get("y_limit", 0.0)}]
        for i in range(5):
            z = np_zones[i] if i < len(np_zones) else {}
            checked = bool(z.get("enabled", False))
            self._np_enabled[i].setChecked(checked)
            for btn, key, suffix in [
                (self._np_x_min[i],   "x_min",   " mm"),
                (self._np_x_max[i],   "x_max",   " mm"),
                (self._np_y_limit[i], "y_limit",  " N"),
            ]:
                val = str(z.get(key, 0.0))
                btn.setProperty("numpad_value", val)
                btn.setText(f"{val}{suffix}")
            self._on_np_zone_toggled(i, checked)
        # UNI-BOX multi-zones
        ub_zones = tools.get("uni_box_zones", [])
        # Compatibilité ancien format
        if not ub_zones and tools.get("uni_box", {}):
            old_ub = tools["uni_box"]
            if old_ub.get("enabled"):
                ub_zones = [{"enabled": True,
                             "box_x_min": old_ub.get("box_x_min", 0.0),
                             "box_x_max": old_ub.get("box_x_max", 0.0),
                             "box_y_min": old_ub.get("box_y_min", 0.0),
                             "box_y_max": old_ub.get("box_y_max", 0.0)}]
        for i in range(5):
            z = ub_zones[i] if i < len(ub_zones) else {}
            checked = bool(z.get("enabled", False))
            self._ub_enabled[i].setChecked(checked)
            for btn, key, suffix in [
                (self._ub_x_min[i], "box_x_min", " mm"),
                (self._ub_x_max[i], "box_x_max", " mm"),
                (self._ub_y_min[i], "box_y_min", " N"),
                (self._ub_y_max[i], "box_y_max", " N"),
            ]:
                val = str(z.get(key, 0.0))
                btn.setProperty("numpad_value", val)
                btn.setText(f"{val}{suffix}")
            self._on_ub_zone_toggled(i, checked)
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
                "no_pass_zones": [
                    {
                        "enabled": self._np_enabled[i].isChecked(),
                        "x_min":   _get_numpad_value(self._np_x_min[i]),
                        "x_max":   _get_numpad_value(self._np_x_max[i]),
                        "y_limit": _get_numpad_value(self._np_y_limit[i]),
                    }
                    for i in range(5)
                ],
                "uni_box_zones": [
                    {
                        "enabled":   self._ub_enabled[i].isChecked(),
                        "box_x_min": _get_numpad_value(self._ub_x_min[i]),
                        "box_x_max": _get_numpad_value(self._ub_x_max[i]),
                        "box_y_min": _get_numpad_value(self._ub_y_min[i]),
                        "box_y_max": _get_numpad_value(self._ub_y_max[i]),
                        "entry_side": "left",
                        "exit_side":  "left",
                    }
                    for i in range(5)
                ],
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
        QMessageBox.information(
            self,
            t("dlg_pm_saved_title"),
            t("dlg_pm_saved_msg").format(id=f"{self._pm_id:02d}"),
        )
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

        lbl_icon = QLabel()
        lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_icon.setStyleSheet("background: transparent; border: none;")
        pixmap = QPixmap(icon)
        if not pixmap.isNull():
            pixmap = pixmap.scaled(350, 350, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            lbl_icon.setPixmap(pixmap)
        else:
            lbl_icon.setText(icon)
            lbl_icon.setFont(QFont("", 40))
        lbl_icon.setStyleSheet("background: transparent; border: none;")
        v.addWidget(lbl_icon)

        lbl_text = QLabel(label)
        lbl_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_text.setFont(QFont("Segoe UI", 32, QFont.Weight.Bold))
        lbl_text.setStyleSheet(
            "font-size: 32px; font-weight: 700; "
            "background: transparent; border: none; color: #1A1A18;"
        )
        v.addWidget(lbl_text)

    def _update_style(self) -> None:
        bg = "#F5EDD6" if self._hovered else "#FAFAF8"
        border = "#C49A3C" if self._hovered else self._border_color
        self.setStyleSheet(
            f"QFrame {{ background-color: {bg}; "
            f"border: 2px solid {border}; "
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
# Constantes de choix — dialogues Coordonnée X / Coordonnée Y
# ===========================================================================

_DECIMAL_CHOICES  = ["0", "1", "2", "3", "4"]
_SENSOR_TYPES_X   = ["Linéaire", "Rotatif", "Angulaire", "Impulsion"]
_UNITS_X          = ["mm", "cm", "°", "pulse", "µm", "in"]
_UNITS_Y          = ["daN", "kN", "kg"]
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
        title_font_size: int | None = None,
        item_font_size: int | None = None,
        item_min_height: int | None = None,
    ) -> None:
        super().__init__(parent)
        title_font_size = title_font_size or 15
        item_font_size = item_font_size or 15
        item_min_height = item_min_height or 48
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
        hdr.setStyleSheet("background-color: #E8E4DC;")
        hh = QHBoxLayout(hdr)
        hh.setContentsMargins(8, 0, 8, 0)
        lbl = QLabel(title)
        lbl.setStyleSheet(
            f"font-size: {title_font_size}px; font-weight: bold; color: #1A1A18;"
        )
        hh.addWidget(lbl)
        root.addWidget(hdr)

        # Boutons de choix
        for c in choices:
            b = QPushButton(c)
            b.setMinimumHeight(item_min_height)
            bg = "#A07830" if c == current else "#E8E4DC"
            b.setStyleSheet(
                f"background-color: {bg}; color: #1A1A18; font-size: {item_font_size}px;"
                " border: none; border-bottom: 1px solid #333;"
                " text-align: left; padding-left: 16px;"
            )
            b.clicked.connect(lambda _chk, v=c: self._pick(v))
            root.addWidget(b)

        # Annuler
        btn_x = QPushButton(t("btn_close_x"))
        btn_x.setObjectName("btn_cancel")
        btn_x.clicked.connect(self.reject)
        root.addWidget(btn_x)

        self.setFixedSize(320, 46 + len(choices) * item_min_height + 54)

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
    display_map: dict[str, str] | None = None,
    dialog_width: int | None = None,
    dialog_title_font_size: int | None = None,
    dialog_item_font_size: int | None = None,
    dialog_item_height: int | None = None,
) -> QPushButton:
    """Retourne un QPushButton qui ouvre _ChoiceDialog au clic."""
    reverse_display_map = {v: k for k, v in (display_map or {}).items()}

    def _display(v: str) -> str:
        return display_map.get(v, v) if display_map else v

    btn = QPushButton(_display(current))
    btn.setProperty("choice_value", current)
    btn.setMinimumHeight(42)

    def _open(_chk: bool = False) -> None:
        current_value = btn.property("choice_value") or current
        shown_choices = [_display(c) for c in choices]
        dlg = _ChoiceDialog(
            shown_choices,
            _display(current_value),
            title,
            parent,
            title_font_size=dialog_title_font_size,
            item_font_size=dialog_item_font_size,
            item_min_height=dialog_item_height,
        )
        if dialog_width is not None:
            dlg.setFixedWidth(dialog_width)
        if dlg.exec():
            picked = dlg.value()
            v = reverse_display_map.get(picked, picked)
            btn.setProperty("choice_value", v)
            btn.setText(_display(v))

    btn.clicked.connect(_open)
    return btn


# ===========================================================================
# VoieXDialog — configuration Coordonnée X (Position)
# ===========================================================================

class _VoieXPage(QWidget):
    """Page 2 pages — configuration Coordonnée X (intégrée dans _settings_stack).

    Page 0 : Déclaration capteur (nom, type, unité, canal, décimales)
    Page 1 : Mise à l'échelle 2 points (table affichage / signal%)
    """

    def __init__(self, stack: QStackedWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._main_stack = stack
        self._back_callback = None  # type: ignore[assignment]
        self.setStyleSheet(_DIALOG_STYLE)
        self._build_ui()
        self._load_config()

    def showEvent(self, event) -> None:
        self._load_config()
        super().showEvent(event)

    def _cancel(self) -> None:
        if self._back_callback is not None:
            self._back_callback()
        else:
            self._main_stack.setCurrentIndex(13)

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Page combinée (déclaration + mise à l'échelle) dans un seul scroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setMaximumWidth(720)
        v = QVBoxLayout(inner)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addWidget(self._build_page0())
        v.addWidget(self._build_page1())
        v.addStretch(1)
        scroll.setWidget(inner)
        root.addWidget(scroll, stretch=1)

    def _build_page0(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(
            "QLabel { font-size:20px; color:#555555; background:transparent; }"
        )
        form = QFormLayout(w)
        form.setContentsMargins(20, 20, 20, 20)
        form.setSpacing(22)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self._name_btn = _make_alpha_btn("", title=t("table_col_name"), parent=self)
        form.addRow(t("lbl_sensor_name"), self._name_btn)

        self._sensor_type_btn = _make_choice_btn(
            _SENSOR_TYPES_X, "Linéaire", "Type de capteur", self
        )
        form.addRow(t("lbl_sensor_type"), self._sensor_type_btn)

        self._unit_btn = _make_choice_btn(_UNITS_X, "mm", "Unité", self)
        form.addRow(t("lbl_unit"), self._unit_btn)

        self._channel_btn = _make_numpad_btn(
            "1", suffix="", title="Canal MCC 118 (0-7)", parent=self
        )
        form.addRow(t("lbl_mcc_channel"), self._channel_btn)

        self._decimal_btn = _make_choice_btn(_DECIMAL_CHOICES, "2", "Décimales", self)
        form.addRow(t("lbl_decimals"), self._decimal_btn)

        for fld in (self._name_btn, self._sensor_type_btn, self._unit_btn,
                    self._channel_btn, self._decimal_btn):
            fld.setFixedHeight(64)
            fld.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            fld.setStyleSheet((fld.styleSheet() or "") +
                              "QPushButton { font-size:20px; font-weight:bold; min-height:64px; }")
        return w

    def _build_page1(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(20, 16, 20, 16)
        v.setSpacing(16)

        lbl = QLabel(t("hdr_scale_2pts"))
        lbl.setStyleSheet("font-size: 16px; color: #555555; font-weight: bold;")
        v.addWidget(lbl)

        grid = QGridLayout()
        grid.setSpacing(8)

        # En-têtes colonnes
        for col, txt in enumerate(["", t("col_display"), t("col_signal_pct"), ""], start=0):
            lc = QLabel(txt)
            lc.setStyleSheet("font-size: 13px; color: #4A4844;")
            lc.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(lc, 0, col)

        # Point 1
        grid.addWidget(QLabel(t("lbl_point1")), 1, 0)
        self._p1_display = _make_numpad_btn(
            "0.0", suffix="", title=t("lbl_point1"), parent=self
        )
        grid.addWidget(self._p1_display, 1, 1)
        self._p1_signal = _make_numpad_btn(
            "0.0", suffix=" %", title=t("lbl_point1"), parent=self
        )
        grid.addWidget(self._p1_signal, 1, 2)
        self._btn_teach1 = QPushButton(t("btn_teach"))
        self._btn_teach1.setObjectName("btn_nav")
        self._btn_teach1.clicked.connect(lambda: self._teach_point(1))
        grid.addWidget(self._btn_teach1, 1, 3)

        # Point 2
        grid.addWidget(QLabel(t("lbl_point2")), 2, 0)
        self._p2_display = _make_numpad_btn(
            "100.0", suffix="", title=t("lbl_point2"), parent=self
        )
        grid.addWidget(self._p2_display, 2, 1)
        self._p2_signal = _make_numpad_btn(
            "100.0", suffix=" %", title=t("lbl_point2"), parent=self
        )
        grid.addWidget(self._p2_signal, 2, 2)
        self._btn_teach2 = QPushButton(t("btn_teach"))
        self._btn_teach2.setObjectName("btn_nav")
        self._btn_teach2.clicked.connect(lambda: self._teach_point(2))
        grid.addWidget(self._btn_teach2, 2, 3)

        v.addLayout(grid)
        v.addStretch()
        return w

    # ------------------------------------------------------------------
    def _teach_point(self, point: int) -> None:
        """Lit la tension instantanee CH1 et injecte le % dans le champ Signal % correspondant."""
        try:
            from core.acquisition import read_single_voltage_ch1
            voltage = read_single_voltage_ch1()
        except Exception as exc:
            QMessageBox.warning(self, "TEACH", str(exc))
            return

        signal_pct = round((voltage / 10.0) * 100.0, 1)
        val_str = str(signal_pct)
        btn = self._p1_signal if point == 1 else self._p2_signal
        sfx = btn.property("numpad_suffix") or ""
        btn.setProperty("numpad_value", val_str)
        btn.setText(f"{val_str}{sfx}")

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
        QMessageBox.information(self, t("dlg_voie_x_title"), t("dlg_voie_x_saved_msg"))
        self._main_stack.setCurrentIndex(1)


# ===========================================================================
# VoieYDialog — configuration Coordonnée Y (Force)
# ===========================================================================

class _VoieYPage(QWidget):
    """Page 2 pages — configuration Coordonnée Y (intégrée dans _settings_stack).

    Page 0 : Déclaration capteur (nom, unité, force max, canal, décimales)
    Page 1 : Sensibilité piézo (méthode, sensibilité, alarme, Avancé ▼)
    """

    def __init__(self, stack: QStackedWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._main_stack = stack
        self._back_callback = None  # type: ignore[assignment]
        self.setStyleSheet(_DIALOG_STYLE)
        self._build_ui()
        self._load_config()

    def showEvent(self, event) -> None:
        self._load_config()
        super().showEvent(event)

    def _scale_method_display_map(self) -> dict[str, str]:
        return {
            "Sensibilité": t("scale_method_sensitivity"),
            "2 points": t("scale_method_2points"),
        }

    def _filter_display_map(self) -> dict[str, str]:
        return {
            "Aucun": t("choice_none"),
            "50 Hz": "50 Hz",
            "100 Hz": "100 Hz",
            "200 Hz": "200 Hz",
            "500 Hz": "500 Hz",
        }

    def _cancel(self) -> None:
        if self._back_callback is not None:
            self._back_callback()
        else:
            self._main_stack.setCurrentIndex(13)

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Page combinée (déclaration + sensibilité) dans un seul scroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setMaximumWidth(720)
        v = QVBoxLayout(inner)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addWidget(self._build_page0())
        v.addWidget(self._build_page1())
        v.addStretch(1)
        scroll.setWidget(inner)
        root.addWidget(scroll, stretch=1)

    def _build_page0(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(
            "QLabel { font-size:20px; color:#555555; background:transparent; }"
        )
        form = QFormLayout(w)
        form.setContentsMargins(20, 20, 20, 20)
        form.setSpacing(22)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self._name_btn = _make_alpha_btn("", title=t("table_col_name"), parent=self)
        form.addRow(t("lbl_sensor_name"), self._name_btn)

        # Type fixe piézo
        btn_piezo = QPushButton(t("btn_piezo"))
        btn_piezo.setObjectName("btn_nav")
        btn_piezo.setEnabled(False)
        form.addRow(t("lbl_sensor_type"), btn_piezo)

        self._unit_btn = _make_choice_btn(_UNITS_Y, "daN", "Unité", self)
        form.addRow(t("lbl_unit"), self._unit_btn)

        self._max_btn = _make_numpad_btn(
            "5000.0", suffix="", title=t("force_label"), parent=self
        )
        form.addRow(t("lbl_force_max"), self._max_btn)

        self._channel_btn = _make_numpad_btn(
            "0", suffix="", title="Canal MCC 118 (0-7)", parent=self
        )
        form.addRow(t("lbl_mcc_channel"), self._channel_btn)

        self._decimal_btn = _make_choice_btn(_DECIMAL_CHOICES, "1", "Décimales", self)
        form.addRow(t("lbl_decimals"), self._decimal_btn)

        for fld in (self._name_btn, btn_piezo, self._unit_btn, self._max_btn,
                    self._channel_btn, self._decimal_btn):
            fld.setFixedHeight(64)
            fld.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            fld.setStyleSheet((fld.styleSheet() or "") +
                              "QPushButton { font-size:20px; font-weight:bold; min-height:64px; }")
        return w

    def _build_page1(self) -> QWidget:
        inner = QWidget()
        inner.setStyleSheet(
            "QLabel { font-size:20px; color:#555555; background:transparent; }"
        )
        v = QVBoxLayout(inner)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(16)

        form = QFormLayout()
        form.setSpacing(22)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self._scale_method_btn = _make_choice_btn(
            _SCALE_METHODS,
            "Sensibilité",
            t("title_scale_method"),
            self,
            display_map=self._scale_method_display_map(),
        )
        form.addRow(t("lbl_scale_method"), self._scale_method_btn)

        self._sensitivity_btn = _make_numpad_btn(
            "-10.0", suffix=" pC/N", title=t("title_sensitivity_pcn"), parent=self
        )
        form.addRow(t("lbl_sensitivity"), self._sensitivity_btn)

        self._alarm_btn = _make_numpad_btn(
            "4500.0", suffix="", title=t("title_alarm_threshold"), parent=self
        )
        form.addRow(t("lbl_alarm_threshold"), self._alarm_btn)

        self._invert_chk = QCheckBox(t("lbl_invert_signal"))
        form.addRow("", self._invert_chk)

        v.addLayout(form)

        # Section Avancé (collapsible)
        self._avance_toggle = QPushButton(t("btn_advanced_collapsed"))
        self._avance_toggle.setStyleSheet(
            "background: transparent; color: #A07830; font-size: 14px;"
            " font-weight: bold; border: none; text-align: left; padding: 4px 0;"
        )
        self._avance_toggle.clicked.connect(self._toggle_avance)
        v.addWidget(self._avance_toggle)

        self._avance_w = QWidget()
        av = QFormLayout(self._avance_w)
        av.setContentsMargins(0, 4, 0, 4)
        av.setSpacing(12)
        av.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._filter_btn = _make_choice_btn(
            _FILTER_CHOICES,
            "Aucun",
            t("title_filter"),
            self,
            display_map=self._filter_display_map(),
        )
        av.addRow(t("lbl_filter"), self._filter_btn)

        self._couple_dcy_chk = QCheckBox(t("lbl_couple_dcy"))
        av.addRow("", self._couple_dcy_chk)

        self._test_point_btn = _make_numpad_btn(
            "0.0", suffix="", title=t("title_test_point"), parent=self
        )
        av.addRow(t("lbl_test_point"), self._test_point_btn)

        self._tolerance_btn = _make_numpad_btn(
            "5.0", suffix=" %", title=t("title_tolerance_pct"), parent=self
        )
        av.addRow(t("lbl_tolerance"), self._tolerance_btn)

        self._test_tor_chk = QCheckBox("Test TOR")
        av.addRow("", self._test_tor_chk)

        self._avance_w.setVisible(False)
        v.addWidget(self._avance_w)
        v.addStretch()

        for fld in (self._scale_method_btn, self._sensitivity_btn, self._alarm_btn,
                    self._filter_btn, self._test_point_btn, self._tolerance_btn):
            fld.setFixedHeight(54)
            fld.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            fld.setStyleSheet((fld.styleSheet() or "") +
                              "QPushButton { font-size:16px; min-height:54px; }")

        return inner

    def _toggle_avance(self) -> None:
        vis = self._avance_w.isVisible()
        self._avance_w.setVisible(not vis)
        self._avance_toggle.setText(
            t("btn_advanced_expanded") if not vis else t("btn_advanced_collapsed")
        )

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
            (self._unit_btn,         scaling.get("force_unit"),          "daN"),
            (self._decimal_btn,      str(scaling.get("force_decimal", 1)), "1"),
        ]:
            v = val or default
            btn.setProperty("choice_value", v)
            btn.setText(v)

        scale_method = cal.get("scale_method") or "Sensibilité"
        self._scale_method_btn.setProperty("choice_value", scale_method)
        self._scale_method_btn.setText(self._scale_method_display_map().get(scale_method, scale_method))

        filt = cal.get("filter") or "Aucun"
        self._filter_btn.setProperty("choice_value", filt)
        self._filter_btn.setText(self._filter_display_map().get(filt, filt))

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
        cfg["scaling"]["force_unit"] = self._unit_btn.property("choice_value") or "daN"
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
        QMessageBox.information(self, t("dlg_voie_y_title"), t("dlg_voie_y_saved_msg"))
        self._main_stack.setCurrentIndex(1)


# ===========================================================================
# _CycleGraphWidget — mini-graphique ALLER / RETOUR (QPainter)
# ===========================================================================

# ===========================================================================
# _ControleCyclePage — configuration du contrôle de cycle (2 pages)
# ===========================================================================

class _ControleCyclePage(QWidget):
    """Page unique — Mode mesure + Conditions + ALLER/RETOUR + Traçage
    (intégrée dans _settings_stack)."""

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

        root.addWidget(_make_header("Contrôle cycle", self._cancel))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background:transparent;")

        inner = QWidget()
        inner.setMaximumWidth(720)
        v = QVBoxLayout(inner)
        v.setContentsMargins(16, 16, 16, 16)
        v.setSpacing(8)

        self._build_page0_content(v)
        self._build_page1_content(v)

        v.addStretch(1)
        scroll.setWidget(inner)
        root.addWidget(scroll, stretch=1)

        root.addWidget(self._build_single_footer())

    def _build_single_footer(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(76)
        w.setStyleSheet("background:#f5f4f0; border-top:1px solid #dddddd;")
        h = QHBoxLayout(w)
        h.setContentsMargins(12, 8, 12, 8)
        h.setSpacing(12)

        btn_cancel = QPushButton(t("btn_cancel_cross"))
        btn_cancel.setFixedHeight(60)
        btn_cancel.setStyleSheet(
            "QPushButton { background:#ffffff; border:1.5px solid #dddddd;"
            " border-radius:8px; color:#333333; font-size:18px; font-weight:bold; }"
            "QPushButton:pressed { background:#eeeeee; }"
        )
        btn_cancel.clicked.connect(self._cancel)
        h.addWidget(btn_cancel, stretch=1)

        btn_save = QPushButton(t("btn_save_check"))
        btn_save.setFixedHeight(60)
        btn_save.setStyleSheet(
            "QPushButton { background:#C49A3C; border:none; border-radius:8px;"
            " color:#ffffff; font-size:18px; font-weight:bold; }"
            "QPushButton:pressed { background:#A07830; }"
        )
        btn_save.clicked.connect(self._save)
        h.addWidget(btn_save, stretch=2)
        return w

    # ------------------------------------------------------------------
    # Page 0 — Mode mesure + Conditions début / fin
    # ------------------------------------------------------------------

    def _build_page0_content(self, v: QVBoxLayout) -> None:

        def _section_header(text: str) -> QWidget:
            hdr = QWidget()
            hdr.setFixedHeight(48)
            hdr.setStyleSheet(
                "background:#f5f0e8; border-left:6px solid #C49A3C;"
                " border-radius:6px; margin-bottom:8px;"
            )
            hl = QHBoxLayout(hdr)
            hl.setContentsMargins(14, 0, 14, 0)
            hl.setSpacing(0)
            lbl = QLabel(text)
            lbl.setStyleSheet(
                "font-size:22px; font-weight:bold; color:#8B6520;"
                " border:none; background:transparent;"
            )
            hl.addWidget(lbl)
            return hdr

        def _field_btn_style(btn: QPushButton) -> None:
            btn.setFixedHeight(62)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setStyleSheet(
                (btn.styleSheet() or "") +
                "QPushButton { font-size:20px; font-weight:bold; }"
            )

        def _make_form() -> QFormLayout:
            f = QFormLayout()
            f.setSpacing(16)
            f.setContentsMargins(0, 8, 0, 8)
            f.setLabelAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            f.setFormAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
            )
            f.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
            return f

        # ── Section 1 : Mode mesure ──────────────────────────────────
        v.addSpacing(12)
        v.addWidget(_section_header("Mode mesure"))
        v.addSpacing(8)

        form0 = _make_form()

        self._mode_btn = _make_choice_btn(
            ["Y (x)", "Y (t)", "X (t)", "Y (x, t)"], "Y (x)", "Mode mesure", self
        )
        _field_btn_style(self._mode_btn)
        form0.addRow(t("lbl_measure_mode"), self._mode_btn)

        self._nb_samples_btn = _make_numpad_btn(
            "1000", suffix="", title="Nombre d'échantillons", parent=self
        )
        _field_btn_style(self._nb_samples_btn)
        form0.addRow(t("lbl_samples_count"), self._nb_samples_btn)

        self._delta_x_btn = _make_choice_btn(
            ["Automatique", "Manuel"], "Automatique", "Delta X", self
        )
        _field_btn_style(self._delta_x_btn)
        form0.addRow(t("lbl_delta_x"), self._delta_x_btn)

        v.addLayout(form0)

        self._mode_indicator = QLabel()
        self._mode_indicator.setStyleSheet(
            "background-color: #E8E4DC; color: #A07830; font-size: 18px;"
            " padding: 10px 16px; border-radius: 6px; border: 1px solid #C8C4BC;"
        )
        self._mode_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._mode_indicator.setFixedHeight(50)
        v.addWidget(self._mode_indicator)

        # ── Section 2 : Conditions début / fin ──────────────────────
        v.addSpacing(12)
        v.addWidget(_section_header("Conditions début / fin"))
        v.addSpacing(8)

        cond_hdr = QHBoxLayout()
        for txt in ["  Début", "", "  Fin"]:
            lbl2 = QLabel(txt)
            if txt:
                lbl2.setStyleSheet("font-size:20px; font-weight:bold; color:#1A1A18;")
            cond_hdr.addWidget(lbl2, 0 if not txt else 1)
        v.addLayout(cond_hdr)
        v.addSpacing(6)

        cols = QHBoxLayout()
        cols.setSpacing(10)

        self._condition_debut_btn = _make_choice_btn(
            ["E-TOR 1 / Bus", "Seuil-X", "Seuil-Y", "Manuel"],
            "E-TOR 1 / Bus", "Condition début", self,
        )
        _field_btn_style(self._condition_debut_btn)
        cols.addWidget(self._condition_debut_btn, stretch=1)

        arrow = QLabel(t("symbol_arrow_right"))
        arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        arrow.setStyleSheet("color: #4A4844; font-size: 20px;")
        arrow.setFixedWidth(24)
        cols.addWidget(arrow)

        self._condition_fin_btn = _make_choice_btn(
            ["E-TOR 1 / Bus", "Manuel", "Seuil-X", "Seuil-Y", "Retour-X", "Temps"],
            "E-TOR 1 / Bus", "Condition fin", self,
        )
        _field_btn_style(self._condition_fin_btn)
        cols.addWidget(self._condition_fin_btn, stretch=1)

        v.addLayout(cols)

        form1 = _make_form()
        self._duree_btn = _make_numpad_btn(
            "20.0", suffix=" s", title="Durée du cycle (s)", parent=self
        )
        _field_btn_style(self._duree_btn)
        form1.addRow(t("lbl_cycle_duration"), self._duree_btn)
        v.addLayout(form1)

    # ------------------------------------------------------------------
    # Page 1 — Parties ALLER / RETOUR + Traçage
    # ------------------------------------------------------------------

    def _build_page1_content(self, v: QVBoxLayout) -> None:

        def _section_header(text: str) -> QWidget:
            hdr = QWidget()
            hdr.setFixedHeight(48)
            hdr.setStyleSheet(
                "background:#f5f0e8; border-left:6px solid #C49A3C;"
                " border-radius:6px; margin-bottom:8px;"
            )
            hl = QHBoxLayout(hdr)
            hl.setContentsMargins(14, 0, 14, 0)
            hl.setSpacing(0)
            lbl = QLabel(text)
            lbl.setStyleSheet(
                "font-size:22px; font-weight:bold; color:#8B6520;"
                " border:none; background:transparent;"
            )
            hl.addWidget(lbl)
            return hdr

        def _field_btn_style(btn: QPushButton) -> None:
            btn.setFixedHeight(62)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setStyleSheet(
                (btn.styleSheet() or "") +
                "QPushButton { font-size:20px; font-weight:bold; }"
            )

        def _make_form() -> QFormLayout:
            f = QFormLayout()
            f.setSpacing(16)
            f.setContentsMargins(0, 8, 0, 8)
            f.setLabelAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            f.setFormAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
            )
            f.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
            return f

        # ── Section 3 : Parties ALLER / RETOUR ──────────────────────
        v.addSpacing(12)
        v.addWidget(_section_header("Parties ALLER / RETOUR"))
        v.addSpacing(8)

        form2 = _make_form()

        self._aller_btn = _make_choice_btn(
            ["Non défini", "Xmax", "Ymax", "Ymin"], "Xmax",
            "Partie ALLER jusqu'à", self,
        )
        _field_btn_style(self._aller_btn)
        form2.addRow(t("lbl_part_forward_until"), self._aller_btn)

        self._retour_btn = _make_choice_btn(
            ["Non défini", "Xmin", "Ymax", "Ymin"], "Non défini",
            "Partie RETOUR jusqu'à", self,
        )
        _field_btn_style(self._retour_btn)
        form2.addRow(t("lbl_part_return_until"), self._retour_btn)

        v.addLayout(form2)

        ind_row = QHBoxLayout()
        ind_row.setSpacing(32)
        ind_row.addStretch()
        for txt, color in [("↗  ALLER", "#E24B4A"), ("↘  RETOUR", "#A07830")]:
            lbl3 = QLabel(txt)
            lbl3.setStyleSheet(
                f"color: {color}; font-size: 20px; font-weight: bold; background: transparent;"
            )
            lbl3.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ind_row.addWidget(lbl3)
        ind_row.addStretch()
        v.addLayout(ind_row)

        # ── Section 4 : Traçage ──────────────────────────────────────
        v.addSpacing(12)
        v.addWidget(_section_header("Traçage de la courbe"))
        v.addSpacing(8)

        form3 = _make_form()

        self._tracage_btn = _make_choice_btn(
            ["ALLER-RETOUR", "ALLER", "RETOUR"], "ALLER",
            "Traçage de la courbe", self,
        )
        _field_btn_style(self._tracage_btn)
        form3.addRow(t("lbl_curve_tracing"), self._tracage_btn)
        v.addLayout(form3)

        ind_row2 = QHBoxLayout()
        ind_row2.setSpacing(32)
        ind_row2.addStretch()
        self._tracage_lbl_aller = QLabel(t("lbl_stroke_forward"))
        self._tracage_lbl_aller.setStyleSheet(
            "font-size:20px; font-weight:bold; background:transparent;"
        )
        self._tracage_lbl_aller.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ind_row2.addWidget(self._tracage_lbl_aller)
        self._tracage_lbl_retour = QLabel(t("lbl_stroke_return"))
        self._tracage_lbl_retour.setStyleSheet(
            "font-size:20px; font-weight:bold; background:transparent;"
        )
        self._tracage_lbl_retour.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ind_row2.addWidget(self._tracage_lbl_retour)
        ind_row2.addStretch()
        v.addLayout(ind_row2)

    # ------------------------------------------------------------------
    # Refresh helpers
    # ------------------------------------------------------------------

    def _refresh_mode_indicator(self) -> None:
        _desc = {
            "Y (x)":    "Force en fonction de la position",
            "Y (t)":    "Force en fonction du temps",
            "X (t)":    "Position en fonction du temps",
            "Y (x, t)": "Force en fonction de la position et du temps",
        }
        mode = self._mode_btn.property("choice_value") or "Y (x)"
        self._mode_indicator.setText(f"~  {_desc.get(mode, mode)}")

    def _refresh_duree_visibility(self) -> None:
        is_temps = (self._condition_fin_btn.property("choice_value") == "Temps")
        self._duree_btn.setEnabled(is_temps)

    def _refresh_tracage_graph(self) -> None:
        mode = self._tracage_btn.property("choice_value") or "ALLER"
        aller_active  = (mode != "RETOUR")
        retour_active = (mode != "ALLER")
        self._tracage_lbl_aller.setStyleSheet(
            f"color: {'#E24B4A' if aller_active else '#7A7870'};"
            " font-size: 18px; font-weight: bold; background: transparent;"
        )
        self._tracage_lbl_aller.setText(
            t("lbl_stroke_forward") + ("" if aller_active else "  (ignoré)")
        )
        self._tracage_lbl_retour.setStyleSheet(
            f"color: {'#A07830' if retour_active else '#7A7870'};"
            " font-size: 18px; font-weight: bold; background: transparent;"
        )
        self._tracage_lbl_retour.setText(
            t("lbl_stroke_return") + ("" if retour_active else "  (ignoré)")
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
        QMessageBox.information(self, t("dlg_cycle_ctrl_title"), t("dlg_config_saved_restart_msg"))
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
    """Page droits d'accès — page unique fusionnée."""

    _LEVELS = [
        ("pin_operateur",  "", "level_operator", "#2E7D32"),
        ("pin_technicien", "", "level_tech",     "#FF9800"),
        ("pin_admin",      "", "level_admin",    "#C62828"),
    ]
    _AUTO_LOGOUT_CHOICES = ["Jamais", "5 minutes", "15 minutes", "1 heure"]
    _AUTO_LOGOUT_DEFAULT = "Jamais"

    def __init__(self, stack: QStackedWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._main_stack = stack
        self.setStyleSheet(_DIALOG_STYLE)
        self._build_ui()

    def showEvent(self, event) -> None:
        self._load_config()
        super().showEvent(event)

    def _auto_logout_display_map(self) -> dict[str, str]:
        return {
            "Jamais": t("auto_logout_never"),
            "5 minutes": t("auto_logout_5_min"),
            "15 minutes": t("auto_logout_15_min"),
            "1 heure": t("auto_logout_1_hour"),
        }

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        root.addWidget(_make_header(
            t("hdr_access_rights"),
            lambda: self._main_stack.setCurrentIndex(1),
        ))

        # Contenu unique scrollable
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        inner = QWidget()
        inner.setMaximumWidth(720)
        inner.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        v = QVBoxLayout(inner)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(16)

        # Activation des droits
        self._enabled_chk = QCheckBox(t("lbl_access_rights_enable"))
        self._enabled_chk.setStyleSheet(
            "QCheckBox { font-size:17px; color:#1A1A18; }"
            "QCheckBox::indicator { width:26px; height:26px; }"
        )
        v.addWidget(self._enabled_chk)

        # Déconnexion auto
        row_logout = QHBoxLayout()
        row_logout.setSpacing(12)
        lbl_logout = QLabel(t("lbl_auto_logout"))
        lbl_logout.setStyleSheet("color: #1A1A18; font-size:17px;")
        self._auto_logout_btn = _make_choice_btn(
            self._AUTO_LOGOUT_CHOICES,
            self._AUTO_LOGOUT_DEFAULT,
            t("auto_logout_title"),
            self,
            display_map=self._auto_logout_display_map(),
            dialog_width=520,
            dialog_title_font_size=24,
            dialog_item_font_size=24,
            dialog_item_height=70,
        )
        self._auto_logout_btn.setFixedHeight(52)
        self._auto_logout_btn.setMinimumWidth(200)
        auto_logout_font = self._auto_logout_btn.font()
        auto_logout_font.setPixelSize(17)
        self._auto_logout_btn.setFont(auto_logout_font)
        row_logout.addWidget(lbl_logout)
        row_logout.addWidget(self._auto_logout_btn)
        v.addLayout(row_logout)

        # Séparateur + titre PIN
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setStyleSheet("color: #C8C4BC;")
        v.addWidget(sep1)
        lbl_pin_title = QLabel(t("lbl_modify_pin"))
        lbl_pin_title.setStyleSheet("color: #4A4844; font-size:17px; font-weight: bold;")
        v.addWidget(lbl_pin_title)

        # 3 lignes PIN
        _ROW_STYLE = "background-color: #E8E4DC; border-radius: 8px; padding: 8px;"
        _BTN_MOD_STYLE = (
            "QPushButton {"
            "  background-color: #A07830; color: #1A1A18;"
            "  font-size: 22px; font-weight: bold;"
            "  border: none; border-radius: 8px;"
            "  min-height: 58px; min-width: 190px; padding: 0 16px;"
            "}"
            "QPushButton:pressed { background-color: #7a5c24; }"
        )
        for key, icon, name_key, color in self._LEVELS:
            name = t(name_key)
            row_w = QWidget()
            row_w.setStyleSheet(_ROW_STYLE)
            rh = QHBoxLayout(row_w)
            rh.setContentsMargins(12, 6, 12, 6)
            rh.setSpacing(12)
            lbl_name = QLabel(f"{icon}  {name}")
            lbl_name.setStyleSheet(
                f"color: {color}; font-size: 24px; font-weight: bold; min-width: 260px;"
            )
            rh.addWidget(lbl_name)
            rh.addStretch()
            pin_lbl = QLabel(t("lbl_pin_masked"))
            pin_lbl.setStyleSheet("color: #666666; font-size: 22px;")
            rh.addWidget(pin_lbl)
            btn_mod = QPushButton(t("btn_edit"))
            btn_mod.setStyleSheet(_BTN_MOD_STYLE)
            btn_mod.clicked.connect(
                lambda _c=False, k=key, n=name: self._change_pin(k, n)
            )
            rh.addWidget(btn_mod)
            v.addWidget(row_w)

        # Séparateur + tableau des niveaux (page1 intégrée)
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color: #C8C4BC;")
        v.addWidget(sep2)
        lbl_table = QLabel(t("lbl_access_levels_table"))
        lbl_table.setStyleSheet("color: #4A4844; font-size:17px; font-weight: bold;")
        v.addWidget(lbl_table)

        table = QTableWidget(3, 3)
        table.setHorizontalHeaderLabels([
            t("table_col_level"), t("table_col_name"), t("table_col_rights")
        ])
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setDefaultSectionSize(120)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        table.setStyleSheet(
            "QTableWidget { font-size:16px; border:1.5px solid #dddddd; }"
            "QHeaderView::section { font-size:16px; font-weight:bold;"
            " padding:10px; background:#f5f4f0; border-bottom:2px solid #dddddd; }"
        )
        table.horizontalHeader().setFixedHeight(52)
        table.verticalHeader().setDefaultSectionSize(90)
        table.setMinimumHeight(400)
        table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        table.setMaximumWidth(700)
        table.horizontalHeader().setStretchLastSection(True)

        _ROWS = [
            ("1", t('level_operator'), t("access_rights_row_operator"),   "#2e7d32"),
            ("2", t('level_tech'),     t("access_rights_row_technician"), "#e65100"),
            ("3", t('level_admin'),    t("access_rights_row_admin"),      "#c62828"),
        ]
        for row, (niv, nom, droits, color) in enumerate(_ROWS):
            item0 = QTableWidgetItem(niv)
            item0.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter)
            table.setItem(row, 0, item0)
            item1 = QTableWidgetItem(nom)
            item1.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            item1.setForeground(QColor(color))
            table.setItem(row, 1, item1)
            item2 = QTableWidgetItem(droits)
            item2.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            table.setItem(row, 2, item2)

        v.addWidget(table)
        scroll.setWidget(inner)
        root.addWidget(scroll, stretch=1)

        # Footer unique — pleine largeur
        footer = QWidget()
        footer.setFixedHeight(64)
        footer.setStyleSheet("background-color: #F0EDE6;")
        h = QHBoxLayout(footer)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        btn_save = QPushButton(t("btn_save_check"))
        btn_save.setFixedHeight(64)
        btn_save.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        btn_save.setStyleSheet(
            "QPushButton { background:#C49A3C; border:none; border-radius:0px;"
            " color:#ffffff; font-size:18px; font-weight:bold; }"
            "QPushButton:pressed { background:#A07830; }"
        )
        btn_save.clicked.connect(self._save)
        h.addWidget(btn_save)
        root.addWidget(footer)

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
            QMessageBox.warning(self, t("dlg_pin_incorrect_title"), t("dlg_old_pin_wrong_msg"))
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
            QMessageBox.warning(self, t("dlg_pin_different_title"), t("dlg_pin_mismatch_msg"))
            return

        # 4. Sauvegarder
        ac[level_key] = _hash_pin(new_pin)
        cfg["access_control"] = ac
        save_config(_CONFIG_PATH, cfg)
        QMessageBox.information(
            self,
            t("dlg_pin_updated_title"),
            t("dlg_pin_updated_msg").format(level_name=level_name),
        )

    # ------------------------------------------------------------------
    def _load_config(self) -> None:
        cfg = load_config(_CONFIG_PATH)
        ac = cfg.get("access_control", {})
        self._enabled_chk.setChecked(bool(ac.get("enabled", False)))
        v = ac.get("auto_logout", self._AUTO_LOGOUT_DEFAULT)
        if v not in self._AUTO_LOGOUT_CHOICES:
            v = self._AUTO_LOGOUT_DEFAULT
        self._auto_logout_btn.setProperty("choice_value", v)
        self._auto_logout_btn.setText(self._auto_logout_display_map().get(v, v))

    def _save(self) -> None:
        cfg = load_config(_CONFIG_PATH)
        ac = cfg.setdefault("access_control", {})
        ac["enabled"]     = self._enabled_chk.isChecked()
        ac["auto_logout"] = self._auto_logout_btn.property("choice_value") or self._AUTO_LOGOUT_DEFAULT
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
            self,
            t("dlg_access_rights_saved_title"),
            t("dlg_config_saved_restart_msg"),
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
        root.addWidget(_make_header(
            t("hdr_datetime"),
            lambda: self._main_stack.setCurrentIndex(1),
        ))

        # Corps
        body = QWidget()
        form_v = QVBoxLayout(body)
        form_v.setContentsMargins(20, 20, 20, 20)
        form_v.setSpacing(24)

        # ---- NTP ----
        self._ntp_check = QCheckBox("Utiliser l'horloge serveur pour horodatage auto.")
        self._ntp_check.setStyleSheet(
            "QCheckBox { font-size:22px; color:#1A1A18; }"
            "QCheckBox::indicator { width:30px; height:30px; }"
        )
        self._ntp_check.setFixedHeight(50)
        form_v.addWidget(self._ntp_check)

        ntp_lbl = QLabel(t("lbl_ntp_server"))
        ntp_lbl.setStyleSheet("color:#4A4844; font-size:22px;")
        ntp_lbl.setFixedHeight(40)
        form_v.addWidget(ntp_lbl)

        self._btn_ntp = _make_alpha_btn("pool.ntp.org", title="Serveur NTP", parent=self)
        self._btn_ntp.setFixedHeight(64)
        self._btn_ntp.setStyleSheet(
            (self._btn_ntp.styleSheet() or "") +
            "QPushButton { border:1.5px solid #dddddd; border-radius:8px;"
            " padding:0 12px; font-size:22px; }"
        )
        form_v.addWidget(self._btn_ntp)

        self._ntp_check.stateChanged.connect(
            lambda state: self._btn_ntp.setEnabled(bool(state))
        )
        self._btn_ntp.setEnabled(False)

        form_v.addSpacing(10)

        # Séparateur
        sep = QFrame()
        sep.setFixedHeight(2)
        sep.setStyleSheet("background:#dddddd; border:none;")
        form_v.addWidget(sep)

        # ---- Date ----
        date_lbl = QLabel(t("lbl_date"))
        date_lbl.setStyleSheet("font-size:24px; font-weight:bold; color:#1A1A18;")
        date_lbl.setFixedHeight(50)
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
            lbl_u.setStyleSheet("color:#888888; font-size:18px;")
            lbl_u.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_u.setFixedHeight(36)
            col.addWidget(lbl_u)
            btn = _make_numpad_btn(default, suffix="", title=title, parent=self)
            btn.setFixedHeight(110)
            btn.setStyleSheet(
                "QPushButton { background:#ffffff; border:1.5px solid #dddddd;"
                " border-radius:10px; color:#333333;"
                " font-size:36px; font-weight:bold; }"
                "QPushButton:pressed { background:#eeeeee; }"
            )
            setattr(self, attr, btn)
            col.addWidget(btn)
            date_row.addLayout(col)
        form_v.addLayout(date_row)

        form_v.addSpacing(20)

        # ---- Heure ----
        heure_lbl = QLabel(t("lbl_time"))
        heure_lbl.setStyleSheet("font-size:24px; font-weight:bold; color:#1A1A18;")
        heure_lbl.setFixedHeight(50)
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
            lbl_u.setStyleSheet("color:#888888; font-size:18px;")
            lbl_u.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_u.setFixedHeight(36)
            col.addWidget(lbl_u)
            btn = _make_numpad_btn(default, suffix="", title=title, parent=self)
            btn.setFixedHeight(110)
            btn.setStyleSheet(
                "QPushButton { background:#ffffff; border:1.5px solid #dddddd;"
                " border-radius:10px; color:#333333;"
                " font-size:36px; font-weight:bold; }"
                "QPushButton:pressed { background:#eeeeee; }"
            )
            setattr(self, attr, btn)
            col.addWidget(btn)
            heure_row.addLayout(col)
        form_v.addLayout(heure_row)

        form_v.addStretch(1)
        root.addWidget(body, stretch=1)

        # Bouton Appliquer
        btn_apply = QPushButton(t("btn_apply"))
        btn_apply.setObjectName("btn_save")
        btn_apply.setFixedHeight(64)
        btn_apply.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        btn_apply.setStyleSheet(
            "QPushButton { background:#C49A3C; border:none; border-radius:0px;"
            " color:#ffffff; font-size:20px; font-weight:bold; }"
            "QPushButton:pressed { background:#A07830; }"
        )
        btn_apply.clicked.connect(self._apply)
        root.addWidget(btn_apply)

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
                self, t("dlg_datetime_title"),
                f"✓ Date et heure appliquées :\n{date_str}",
            )
        except subprocess.CalledProcessError as e:
            QMessageBox.warning(
                self, t("dlg_error_title"),
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

        root.addWidget(_make_header(
            t("hdr_display"),
            lambda: self._main_stack.setCurrentIndex(1),
        ))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background:transparent;")

        inner = QWidget()
        inner.setMaximumWidth(720)
        v = QVBoxLayout(inner)
        v.setContentsMargins(16, 16, 16, 16)
        v.setSpacing(16)

        self._build_section_histo(v)
        self._build_section_outil(v)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(2)
        sep.setStyleSheet("background:#dddddd; border:none;")
        v.addWidget(sep)

        self._build_section_feu(v)

        v.addStretch(1)
        scroll.setWidget(inner)
        root.addWidget(scroll, stretch=1)
        root.addWidget(self._build_single_footer())

    # ------------------------------------------------------------------
    def _build_section_histo(self, v: QVBoxLayout) -> None:
        hdr = QWidget()
        hdr.setFixedHeight(60)
        hdr.setStyleSheet(
            "background:#f5f0e8; border-left:6px solid #C49A3C; border-radius:6px;"
        )
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(14, 0, 14, 0)
        lbl_hdr = QLabel(t("lbl_histogram"))
        lbl_hdr.setStyleSheet(
            "font-size:26px; font-weight:bold; color:#8B6520;"
            " border:none; background:transparent;"
        )
        hl.addWidget(lbl_hdr)
        v.addWidget(hdr)

        _PB_STYLE = (
            "QProgressBar { border: 1px solid #444; border-radius: 6px;"
            " background: #FAFAF8; }"
            "QProgressBar::chunk { background-color: #E24B4A; border-radius: 6px; }"
        )
        self._histo_group = QButtonGroup(self)
        self._histo_btns: list = []

        for idx, (val, suffix) in enumerate(
            [("OK-NOK en %", " %"), ("Nb de pièce NOK", " pcs")]
        ):
            row_w = QWidget()
            row_w.setFixedHeight(72)
            row_h = QHBoxLayout(row_w)
            row_h.setContentsMargins(4, 0, 4, 0)
            row_h.setSpacing(12)
            rb = QRadioButton(val)
            rb.setStyleSheet(
                "QRadioButton { color:#1A1A18; font-size:22px; }"
                "QRadioButton::indicator { width:28px; height:28px; }"
            )
            self._histo_group.addButton(rb, idx)
            self._histo_btns.append(rb)
            row_h.addWidget(rb)
            pb = QProgressBar()
            pb.setRange(0, 100)
            pb.setValue(65)
            pb.setTextVisible(False)
            pb.setFixedHeight(36)
            pb.setStyleSheet(_PB_STYLE)
            row_h.addWidget(pb, stretch=1)
            lbl_val = QLabel(f"65{suffix}")
            lbl_val.setStyleSheet("color:#4A4844; font-size:20px; min-width:65px;")
            row_h.addWidget(lbl_val)
            v.addWidget(row_w)

        self._histo_btns[0].setChecked(True)

    # ------------------------------------------------------------------
    def _build_section_outil(self, v: QVBoxLayout) -> None:
        hdr = QWidget()
        hdr.setFixedHeight(60)
        hdr.setStyleSheet(
            "background:#f5f0e8; border-left:6px solid #C49A3C; border-radius:6px;"
        )
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(14, 0, 14, 0)
        lbl_hdr = QLabel(t("lbl_eval_tool"))
        lbl_hdr.setStyleSheet(
            "font-size:26px; font-weight:bold; color:#8B6520;"
            " border:none; background:transparent;"
        )
        hl.addWidget(lbl_hdr)
        v.addWidget(hdr)

        _CHK_STYLE = (
            "QCheckBox { font-size:22px; color:#1A1A18; }"
            "QCheckBox::indicator { width:30px; height:30px; }"
        )
        _APE_STYLE = (
            "background:#FAFAF8; border:2px solid #C49A3C;"
            " border-radius:4px; padding:4px 12px;"
        )

        for chk_text, preview_key, chk_attr in [
            ("Fenêtre pleine",  "preview_full_block", "_fenetre_pleine_chk"),
            ("Indication E/S",  "preview_io_arrow",   "_indication_es_chk"),
        ]:
            row_w = QWidget()
            row_w.setFixedHeight(64)
            row_h = QHBoxLayout(row_w)
            row_h.setContentsMargins(4, 0, 4, 0)
            row_h.setSpacing(14)
            chk = QCheckBox(chk_text)
            chk.setStyleSheet(_CHK_STYLE)
            chk.setChecked(True)
            setattr(self, chk_attr, chk)
            row_h.addWidget(chk)
            row_h.addStretch()
            lbl = QLabel(t(preview_key))
            lbl.setStyleSheet(f"color:#A07830; font-size:18px; {_APE_STYLE}")
            row_h.addWidget(lbl)
            v.addWidget(row_w)

    # ------------------------------------------------------------------
    def _build_section_feu(self, v: QVBoxLayout) -> None:
        hdr = QWidget()
        hdr.setFixedHeight(60)
        hdr.setStyleSheet(
            "background:#f5f0e8; border-left:6px solid #C49A3C; border-radius:6px;"
        )
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(14, 0, 14, 0)
        lbl_hdr = QLabel(t("hdr_led_style"))
        lbl_hdr.setStyleSheet(
            "font-size:26px; font-weight:bold; color:#8B6520;"
            " border:none; background:transparent;"
        )
        hl.addWidget(lbl_hdr)
        v.addWidget(hdr)

        self._feu_group = QButtonGroup(self)
        self._feu_btns: list = []

        _OK_STYLE = (
            "background-color:#F1F8E9; color:#2E7D32; border:1px solid #2E7D32;"
            " border-radius:6px; font-size:26px; font-weight:bold;"
        )
        _NOK_STYLE = (
            "background-color:#FDECEC; color:#C62828; border:1px solid #C62828;"
            " border-radius:6px; font-size:26px; font-weight:bold;"
        )

        for idx, val in enumerate(self._FEU_VALS):
            ok_txt, nok_txt = self._FEU_CONTENT[val]
            row_w = QWidget()
            row_w.setFixedHeight(80)
            row_h = QHBoxLayout(row_w)
            row_h.setContentsMargins(4, 0, 4, 0)
            row_h.setSpacing(12)
            rb = QRadioButton(val)
            rb.setStyleSheet(
                "QRadioButton { color:#1A1A18; font-size:22px; min-width:160px; }"
                "QRadioButton::indicator { width:28px; height:28px; }"
            )
            self._feu_group.addButton(rb, idx)
            self._feu_btns.append(rb)
            row_h.addWidget(rb)
            row_h.addStretch()
            for txt, style in [(ok_txt, _OK_STYLE), (nok_txt, _NOK_STYLE)]:
                lbl_ap = QLabel(txt)
                lbl_ap.setFixedSize(110, 62)
                lbl_ap.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl_ap.setStyleSheet(style)
                row_h.addWidget(lbl_ap)
            v.addWidget(row_w)

        self._feu_btns[0].setChecked(True)

    # ------------------------------------------------------------------
    def _build_single_footer(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(76)
        w.setStyleSheet("background:#f5f4f0; border-top:1px solid #dddddd;")
        h = QHBoxLayout(w)
        h.setContentsMargins(16, 10, 16, 10)
        h.setSpacing(12)

        btn_cancel = QPushButton(t("btn_cancel_cross"))
        btn_cancel.setFixedHeight(54)
        btn_cancel.setStyleSheet(
            "QPushButton { background:#ffffff; border:1.5px solid #dddddd;"
            " border-radius:8px; color:#333333; font-size:17px; font-weight:bold; }"
            "QPushButton:pressed { background:#eeeeee; }"
        )
        btn_cancel.clicked.connect(lambda: self._main_stack.setCurrentIndex(1))
        h.addWidget(btn_cancel, stretch=1)

        btn_save = QPushButton(t("btn_save_check"))
        btn_save.setFixedHeight(54)
        btn_save.setStyleSheet(
            "QPushButton { background:#C49A3C; border:none; border-radius:8px;"
            " color:#ffffff; font-size:17px; font-weight:bold; }"
            "QPushButton:pressed { background:#A07830; }"
        )
        btn_save.clicked.connect(self._save)
        h.addWidget(btn_save, stretch=2)
        return w

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

        QMessageBox.information(self, t("dlg_display_title"), t("dlg_display_saved_msg"))
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
            self._btn_export.setText(t("btn_export_usb"))
        if not (self._worker_pdf is not None and self._worker_pdf.isRunning()):
            self._btn_pdf.setEnabled(True)
            self._btn_pdf.setText(t("btn_generate_pdf"))
        if not (self._worker_detect is not None and self._worker_detect.isRunning()):
            self._btn_detect.setEnabled(True)
            self._btn_detect.setText(t("btn_detect_usb"))

    def _cancel(self) -> None:
        self._main_stack.setCurrentIndex(1)

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(_make_header(t("hdr_export"), self._cancel))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background:transparent;")

        inner = QWidget()
        inner.setMaximumWidth(720)
        v = QVBoxLayout(inner)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(16)

        self._build_section_folder(v)
        self._add_section_sep(v)
        self._build_section_usb(v)
        self._add_section_sep(v)
        self._build_section_pdf(v)
        self._add_section_sep(v)
        self._build_section_advanced(v)

        v.addStretch(1)
        scroll.setWidget(inner)
        root.addWidget(scroll, stretch=1)
        root.addWidget(self._build_single_footer())

    def _add_section_sep(self, v: QVBoxLayout) -> None:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(2)
        sep.setStyleSheet("background:#dddddd; border:none;")
        v.addWidget(sep)

    def _section_header(self, text: str) -> QWidget:
        w = QWidget()
        w.setFixedHeight(48)
        w.setStyleSheet(
            "background:#f5f0e8; border-left:6px solid #C49A3C; border-radius:6px;"
        )
        h = QHBoxLayout(w)
        h.setContentsMargins(14, 0, 14, 0)
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "font-size:22px; font-weight:bold; color:#8B6520;"
            " border:none; background:transparent;"
        )
        h.addWidget(lbl)
        return w

    def _make_field_form(self) -> QFormLayout:
        f = QFormLayout()
        f.setSpacing(16)
        f.setContentsMargins(0, 8, 0, 8)
        f.setLabelAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        f.setFormAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        f.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        return f

    def _style_field_btn(self, btn: QPushButton, height: int = 58) -> None:
        btn.setFixedHeight(height)
        btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        btn.setStyleSheet(
            (btn.styleSheet() or "") +
            f"QPushButton {{ font-size:18px; font-weight:bold; }}"
        )

    # ------------------------------------------------------------------
    def _build_section_folder(self, v: QVBoxLayout) -> None:
        v.addWidget(self._section_header(t("lbl_local_folder")))

        cfg = _load_cfg_safe()
        data_dir = cfg.get("storage", {}).get("data_dir", "./data")
        self._data_dir_lbl = QLabel(str(Path(data_dir).resolve()))
        self._data_dir_lbl.setStyleSheet(
            "background-color:#E8E4DC; color:#4A4844; border:1px solid #C8C4BC;"
            " border-radius:6px; padding:10px 14px; font-size:18px;"
        )
        self._data_dir_lbl.setWordWrap(True)
        v.addWidget(self._data_dir_lbl)

    # ------------------------------------------------------------------
    def _build_section_usb(self, v: QVBoxLayout) -> None:
        v.addWidget(self._section_header(t("lbl_usb_key")))

        self._btn_detect = QPushButton(t("btn_detect_usb"))
        self._style_field_btn(self._btn_detect, height=60)
        self._btn_detect.clicked.connect(self._detect_usb)
        v.addWidget(self._btn_detect)

        self._usb_status_lbl = QLabel(t("lbl_no_usb"))
        self._usb_status_lbl.setStyleSheet("color:#4A4844; font-size:18px;")
        v.addWidget(self._usb_status_lbl)

        form_usb = self._make_field_form()

        self._filtre_btn = _make_choice_btn(
            ["OK+NOK", "OK uniquement", "NOK uniquement"],
            "OK+NOK", "Filtre export", self,
        )
        self._style_field_btn(self._filtre_btn)
        form_usb.addRow("Filtre export :", self._filtre_btn)

        self._periode_export_btn = _make_choice_btn(
            ["Aujourd'hui", "7 derniers jours", "30 derniers jours", "Tout l'historique"],
            "Aujourd'hui", "Période export", self,
        )
        self._style_field_btn(self._periode_export_btn)
        form_usb.addRow("Période :", self._periode_export_btn)

        v.addLayout(form_usb)

        self._btn_export = QPushButton(t("btn_export_usb"))
        self._style_field_btn(self._btn_export, height=62)
        self._btn_export.clicked.connect(self._do_export_usb)
        v.addWidget(self._btn_export)

    # ------------------------------------------------------------------
    def _build_section_pdf(self, v: QVBoxLayout) -> None:
        v.addWidget(self._section_header(t("lbl_pdf_report")))

        form_pdf = self._make_field_form()

        self._contenu_btn = _make_choice_btn(
            ["Tous les cycles", "Cycles NOK uniquement", "Session courante"],
            "Tous les cycles", "Contenu rapport", self,
        )
        self._style_field_btn(self._contenu_btn)
        form_pdf.addRow("Contenu rapport :", self._contenu_btn)

        self._periode_btn = _make_choice_btn(
            ["Aujourd'hui", "7 derniers jours", "30 derniers jours", "Tout l'historique"],
            "Aujourd'hui", "Période", self,
        )
        self._style_field_btn(self._periode_btn)
        form_pdf.addRow("Période :", self._periode_btn)

        v.addLayout(form_pdf)

        self._btn_pdf = QPushButton(t("btn_generate_pdf"))
        self._style_field_btn(self._btn_pdf, height=62)
        self._btn_pdf.clicked.connect(self._do_generate_pdf)
        v.addWidget(self._btn_pdf)

    # ------------------------------------------------------------------
    def _build_section_advanced(self, v: QVBoxLayout) -> None:
        v.addWidget(self._section_header("⚙  Paramètres avancés"))

        form = self._make_field_form()

        self._nommage_btn = _make_choice_btn(
            ["PM_date_heure_résultat", "Numéro séquentiel", "PM_numéro_résultat"],
            "PM_date_heure_résultat", "Nommage fichier", self,
        )
        self._style_field_btn(self._nommage_btn)
        form.addRow(t("lbl_file_naming"), self._nommage_btn)

        self._auto_export_chk = QCheckBox("Exporter automatiquement à chaque cycle")
        self._auto_export_chk.setStyleSheet(
            "QCheckBox { font-size:18px; color:#1A1A18; }"
            "QCheckBox::indicator { width:26px; height:26px; }"
        )
        form.addRow(t("lbl_auto_export"), self._auto_export_chk)

        self._dest_auto_btn = _make_choice_btn(
            ["Dossier local", "Clé USB si présente"],
            "Dossier local", "Destination auto", self,
        )
        self._style_field_btn(self._dest_auto_btn)
        form.addRow(t("lbl_auto_destination"), self._dest_auto_btn)

        v.addLayout(form)

    # ------------------------------------------------------------------
    def _build_single_footer(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(76)
        w.setStyleSheet("background:#f5f4f0; border-top:1px solid #dddddd;")
        h = QHBoxLayout(w)
        h.setContentsMargins(16, 10, 16, 10)
        h.setSpacing(12)

        btn_cancel = QPushButton(t("btn_cancel_cross"))
        btn_cancel.setFixedHeight(54)
        btn_cancel.setStyleSheet(
            "QPushButton { background:#ffffff; border:1.5px solid #dddddd;"
            " border-radius:8px; color:#333333; font-size:17px; font-weight:bold; }"
            "QPushButton:pressed { background:#eeeeee; }"
        )
        btn_cancel.clicked.connect(self._cancel)
        h.addWidget(btn_cancel, stretch=1)

        btn_save = QPushButton(t("btn_save_check"))
        btn_save.setFixedHeight(54)
        btn_save.setStyleSheet(
            "QPushButton { background:#C49A3C; border:none; border-radius:8px;"
            " color:#ffffff; font-size:17px; font-weight:bold; }"
            "QPushButton:pressed { background:#A07830; }"
        )
        btn_save.clicked.connect(self._save)
        h.addWidget(btn_save, stretch=2)
        return w

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

        periode_export = exp.get("periode_export", "Aujourd'hui")
        self._periode_export_btn.setProperty("choice_value", periode_export)
        self._periode_export_btn.setText(periode_export)

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
        cfg["export"]["periode_export"] = (
            self._periode_export_btn.property("choice_value") or "Aujourd'hui"
        )
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
        self._btn_detect.setText(t("btn_searching"))
        self._worker_detect = ExportWorker(task="detect")
        self._worker_detect.drives_detected.connect(self._on_drives_detected)
        self._worker_detect.task_done.connect(self._on_detect_done)
        self._worker_detect.start()

    def _on_drives_detected(self, drives: list) -> None:
        self._detected_drives = drives

    def _on_detect_done(self, success: bool, message: str) -> None:
        self._btn_detect.setEnabled(True)
        self._btn_detect.setText(t("btn_detect_usb"))
        self._worker_detect = None
        self._usb_status_lbl.setText(message)
        if success:
            self._usb_status_lbl.setStyleSheet("color: #1D9E75; font-size: 14px;")
        else:
            self._usb_status_lbl.setStyleSheet("color: #4A4844; font-size: 14px;")

    def _do_export_usb(self) -> None:
        if not self._detected_drives:
            QMessageBox.warning(
                self,
                t("dlg_export_usb_title"),
                t("dlg_no_usb_detected_msg"),
            )
            return

        self._btn_export.setEnabled(False)
        self._btn_export.setText(t("btn_exporting"))

        from core.export_manager import ExportWorker

        cfg = _load_cfg_safe()
        data_dir = Path(cfg.get("storage", {}).get("data_dir", "./data"))
        filtre = self._filtre_btn.property("choice_value") or "OK+NOK"
        periode = self._periode_export_btn.property("choice_value") or "Aujourd'hui"

        _PERIODE_TO_FILTER = {
            "Aujourd'hui":       "today",
            "7 derniers jours":  "last7",
            "30 derniers jours": "last30",
            "Tout l'historique": None,
        }
        date_filter = _PERIODE_TO_FILTER.get(periode, "today")

        self._worker_usb = ExportWorker(
            task="usb",
            source_dir=data_dir,
            usb_path=self._detected_drives[0],
            filter_result=filtre,
            date_filter=date_filter,
        )
        self._worker_usb.task_done.connect(self._on_export_done)
        self._worker_usb.start()

    def _on_export_done(self, success: bool, message: str) -> None:
        print(f"[DEBUG] _on_export_done: success={success}, msg={message}")
        self._btn_export.setEnabled(True)
        self._btn_export.setText(t("btn_export_usb"))
        self._worker_usb = None  # nettoyage manuel
        print("[DEBUG] Bouton export réactivé")
        if success:
            QMessageBox.information(self, t("dlg_export_usb_title"), message)
        else:
            QMessageBox.warning(self, t("dlg_export_usb_title"), f"Erreur : {message}")

    def _do_generate_pdf(self) -> None:
        self._btn_pdf.setEnabled(False)
        self._btn_pdf.setText(t("btn_generating"))

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
        self._btn_pdf.setText(t("btn_generate_pdf"))
        self._worker_pdf = None  # nettoyage manuel
        if success:
            QMessageBox.information(self, t("lbl_pdf_report"), message)
        else:
            QMessageBox.warning(self, t("lbl_pdf_report"), f"Erreur : {message}")


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
        "background-color: #FAFAF8; color: #C49A3C; font-size: 14px; "
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

        # Header
        root.addWidget(_make_header(
            t("hdr_extras"),
            lambda: self._main_stack.setCurrentIndex(1),
        ))

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
            title=t("dlg_modbus_title"),
            parent=self,
        )
        self._mb_poll_btn = _make_numpad_btn(
            str(mb.get("poll_interval_ms", 50)),
            suffix=" ms",
            title="Intervalle poll",
            parent=self,
        )

        form_mb.addRow(QLabel(t("lbl_plc_ip")), self._mb_host_btn)
        form_mb.addRow(QLabel(t("lbl_modbus_port")), self._mb_port_btn)
        form_mb.addRow(QLabel(t("lbl_poll_interval")), self._mb_poll_btn)

        btn_apply_mb = QPushButton(t("btn_apply"))
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
        lbl_eth0 = QLabel(t("hdr_eth0"))
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
        _gw_default, _dns_default = self._read_current_eth0_gw_dns()
        self._eth0_gw_btn = _make_alpha_btn(
            net.get("eth0_gw", _gw_default),
            title=t("lbl_gateway"),
            parent=self,
        )
        self._eth0_dns_btn = _make_alpha_btn(
            net.get("eth0_dns", _dns_default),
            title=t("lbl_dns"),
            parent=self,
        )
        form_net.addRow(QLabel(t("lbl_eth0_ip")), self._eth0_ip_btn)
        form_net.addRow(QLabel(t("lbl_netmask")), self._eth0_mask_btn)
        form_net.addRow(QLabel(t("lbl_gateway")), self._eth0_gw_btn)
        form_net.addRow(QLabel(t("lbl_dns")), self._eth0_dns_btn)

        btn_apply_eth0 = QPushButton(t("btn_apply_eth0"))
        btn_apply_eth0.setObjectName("btn_save")
        btn_apply_eth0.clicked.connect(self._apply_eth0)
        form_net.addRow("", btn_apply_eth0)

        # WiFi (lecture seule)
        lbl_wifi = QLabel(t("hdr_wifi"))
        lbl_wifi.setStyleSheet("color: #C49A3C; font-weight: bold; margin-top: 6px;")
        form_net.addRow(lbl_wifi)

        self._wifi_ip_lbl = QLabel("—")
        self._wifi_ssid_lbl = QLabel("—")
        form_net.addRow(QLabel(t("lbl_wifi_ip")), self._wifi_ip_lbl)
        form_net.addRow(QLabel(t("lbl_wifi_ssid")), self._wifi_ssid_lbl)

        note_wifi = QLabel(
            "ℹ La config WiFi se fait via raspi-config ou l'interface graphique du Pi."
        )
        note_wifi.setWordWrap(True)
        note_wifi.setStyleSheet("color: #4A4844; font-size: 12px;")
        form_net.addRow(note_wifi)

        btn_refresh_net = QPushButton(t("btn_refresh_network"))
        btn_refresh_net.setObjectName("btn_nav")
        btn_refresh_net.clicked.connect(self._refresh_network)
        form_net.addRow("", btn_refresh_net)

        v.addWidget(fw_net)
        v.addStretch()

        scroll.setWidget(content)
        root.addWidget(scroll, stretch=1)

        # Footer supprimé : retour déplacé dans l'en-tête.

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
        gw = net.get("eth0_gw", "")
        dns = net.get("eth0_dns", "")
        if not gw or not dns:
            sys_gw, sys_dns = self._read_current_eth0_gw_dns()
            gw = gw or sys_gw
            dns = dns or sys_dns
        _btn_set_alpha(self._eth0_gw_btn, gw)
        _btn_set_alpha(self._eth0_dns_btn, dns)
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
            QMessageBox.warning(self, t("dlg_modbus_title"), t("dlg_modbus_int_error_msg"))
            return
        cfg = _load_cfg_safe()
        cfg.setdefault("modbus", {})
        cfg["modbus"]["host"] = host
        cfg["modbus"]["port"] = port
        cfg["modbus"]["poll_interval_ms"] = poll
        save_config(_CONFIG_PATH, cfg)
        QMessageBox.information(self, t("dlg_modbus_title"), t("dlg_config_saved_restart_plain_msg"))

    # ------------------------------------------------------------------
    def _apply_eth0(self) -> None:
        import subprocess
        ip        = self._eth0_ip_btn.property("alpha_value")  or "10.0.0.2"
        mask_full = self._eth0_mask_btn.property("choice_value") or "/24 (255.255.255.0)"
        gw        = (self._eth0_gw_btn.property("alpha_value")  or "").strip()
        dns       = (self._eth0_dns_btn.property("alpha_value") or "").strip()

        # Extraire juste le préfixe "/24" depuis "/24 (255.255.255.0)"
        prefix  = mask_full.split()[0]
        address = f"{ip}{prefix}"

        # Sous-réseau machine 10.0.0.x : passerelle et DNS facultatifs
        is_machine_net = ip.startswith("10.0.0.")

        if not is_machine_net and not gw:
            QMessageBox.warning(
                self, t("dlg_network_title"),
                "Veuillez saisir une passerelle (ex : 192.168.1.1)."
            )
            return

        def _run_modify(conn: str) -> "subprocess.CompletedProcess[str]":
            args = [
                "sudo", "nmcli", "connection", "modify", conn,
                "ipv4.method",    "manual",
                "ipv4.addresses", address,
            ]
            if gw:
                args += ["ipv4.gateway", gw]
            else:
                args += ["ipv4.gateway", ""]   # effacer la passerelle précédente
            if dns:
                args += ["ipv4.dns", dns]
            else:
                args += ["ipv4.dns", ""]       # effacer le DNS précédent
            return subprocess.run(args, capture_output=True, text=True)

        def _run_up(conn: str) -> "subprocess.CompletedProcess[str]":
            return subprocess.run(
                ["sudo", "nmcli", "connection", "up", conn],
                capture_output=True, text=True,
            )

        try:
            conn = "Wired connection 1"
            res = _run_modify(conn)
            if res.returncode != 0:
                conn = "eth0"
                res = _run_modify(conn)

            if res.returncode != 0:
                QMessageBox.warning(
                    self, t("dlg_network_title"),
                    f"Erreur nmcli modify :\n{res.stderr.strip()}"
                )
                return

            res_up = _run_up(conn)
            if res_up.returncode != 0:
                QMessageBox.warning(
                    self, t("dlg_network_title"),
                    f"Erreur nmcli up :\n{res_up.stderr.strip()}"
                )
                return

            cfg = _load_cfg_safe()
            cfg.setdefault("network", {})
            cfg["network"]["eth0_ip"]   = ip
            cfg["network"]["eth0_mask"] = mask_full
            cfg["network"]["eth0_gw"]   = gw
            cfg["network"]["eth0_dns"]  = dns
            save_config(_CONFIG_PATH, cfg)

            detail = f"IP : {address}"
            if gw:
                detail += f"\nPasserelle : {gw}"
            if dns:
                detail += f"\nDNS : {dns}"
            QMessageBox.information(
                self, t("dlg_network_title"),
                f"eth0 configurée :\n{detail}"
            )
        except Exception as e:
            QMessageBox.warning(self, t("dlg_network_title"), f"Erreur : {e}")

    # ------------------------------------------------------------------
    @staticmethod
    def _read_current_eth0_gw_dns() -> tuple[str, str]:
        """Lit la passerelle et le DNS actifs sur eth0 depuis le système."""
        import subprocess
        gw  = ""
        dns = "8.8.8.8"
        try:
            res = subprocess.run(
                ["ip", "route", "show", "default", "dev", "eth0"],
                capture_output=True, text=True, timeout=3,
            )
            for line in res.stdout.splitlines():
                if "via" in line:
                    parts = line.split()
                    gw = parts[parts.index("via") + 1]
                    break
        except Exception:
            pass
        try:
            res = subprocess.run(
                ["nmcli", "dev", "show", "eth0"],
                capture_output=True, text=True, timeout=3,
            )
            for line in res.stdout.splitlines():
                if "IP4.DNS" in line:
                    dns = line.split(":", 1)[-1].strip()
                    break
        except Exception:
            pass
        return gw, dns

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

class _InfoSystemePage(QWidget):
    """Page Informations système (index 15) — extraite de Extras."""

    def __init__(self, stack: QStackedWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._main_stack = stack
        self.setStyleSheet(_DIALOG_STYLE)
        self._build_ui()

    def showEvent(self, event) -> None:
        self._refresh_sysinfo()
        super().showEvent(event)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(_make_header(
            "  Informations système",
            lambda: self._main_stack.setCurrentIndex(1),
        ))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background:transparent;")

        content = QWidget()
        content.setMaximumWidth(720)
        v = QVBoxLayout(content)
        v.setContentsMargins(16, 16, 16, 16)
        v.setSpacing(16)

        # ── Carte info système ───────────────────────────────────────
        card = QWidget()
        card.setStyleSheet(
            "background:#ffffff; border:1.5px solid #dddddd; border-radius:10px;"
        )
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 16, 20, 16)
        card_layout.setSpacing(20)

        _LBL_STYLE = (
            "font-size:20px; font-weight:bold; color:#888888; background:transparent;"
        )
        _VAL_STYLE = "font-size:20px; color:#333333; background:transparent;"

        self._sys_labels: dict[str, QLabel] = {}
        rows = [
            ("version", t("lbl_sw_version")),
            ("modele",  t("lbl_pi_model")),
            ("os",      t("lbl_os")),
            ("uptime",  t("lbl_uptime")),
            ("disque",  t("lbl_disk_space")),
            ("ram",     t("lbl_ram_used")),
            ("temp",    t("lbl_cpu_temp")),
        ]
        for key, label_txt in rows:
            row_w = QWidget()
            row_w.setStyleSheet("background:transparent; border:none;")
            row_h = QHBoxLayout(row_w)
            row_h.setContentsMargins(0, 0, 0, 0)
            row_h.setSpacing(12)

            lbl_key = QLabel(label_txt)
            lbl_key.setStyleSheet(_LBL_STYLE)
            lbl_key.setFixedWidth(200)
            lbl_key.setWordWrap(False)
            row_h.addWidget(lbl_key)

            lbl_val = QLabel("—")
            lbl_val.setStyleSheet(_VAL_STYLE)
            lbl_val.setWordWrap(True)
            self._sys_labels[key] = lbl_val
            row_h.addWidget(lbl_val, stretch=1)

            card_layout.addWidget(row_w)

        v.addWidget(card)

        # ── Bouton Actualiser ────────────────────────────────────────
        btn_refresh = QPushButton("↺  Actualiser")
        btn_refresh.setFixedHeight(64)
        btn_refresh.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        btn_refresh.setStyleSheet(
            "QPushButton { background:#ffffff; border:1.5px solid #C49A3C;"
            " border-radius:8px; color:#C49A3C;"
            " font-size:20px; font-weight:bold; }"
            "QPushButton:pressed { background:#fff8ee; }"
        )
        btn_refresh.clicked.connect(self._refresh_sysinfo)
        v.addWidget(btn_refresh)

        v.addStretch(1)
        scroll.setWidget(content)
        root.addWidget(scroll, stretch=1)

    def _refresh_sysinfo(self) -> None:
        import shutil

        version_file = _CONFIG_PATH.parent / "VERSION.txt"
        try:
            self._sys_labels["version"].setText(
                version_file.read_text(encoding="utf-8").strip()
            )
        except Exception:
            self._sys_labels["version"].setText("1.0.0")

        try:
            model = Path("/proc/device-tree/model").read_bytes().rstrip(b"\x00").decode()
            self._sys_labels["modele"].setText(model)
        except Exception:
            self._sys_labels["modele"].setText("—")

        try:
            os_info = "—"
            for line in Path("/etc/os-release").read_text().splitlines():
                if line.startswith("PRETTY_NAME="):
                    os_info = line.split("=", 1)[1].strip('"')
                    break
            self._sys_labels["os"].setText(os_info)
        except Exception:
            self._sys_labels["os"].setText("—")

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

        try:
            raw = int(Path("/sys/class/thermal/thermal_zone0/temp").read_text())
            temp = raw / 1000.0
            color = "#2E7D32" if temp < 60 else ("#A07830" if temp < 70 else "#C62828")
            self._sys_labels["temp"].setText(f"{temp:.1f} °C")
            self._sys_labels["temp"].setStyleSheet(
                f"font-size:20px; color:{color}; background:transparent;"
            )
        except Exception:
            self._sys_labels["temp"].setText("—")


def _btn_set_alpha(btn: QPushButton, value: str) -> None:
    btn.setProperty("alpha_value", value)
    btn.setText(value or "—")


def _btn_set_numpad(btn: QPushButton, value: str, suffix: str) -> None:
    btn.setProperty("numpad_value", value)
    btn.setText(f"{value}{suffix}")


# ===========================================================================
# _CopyDestDialog — sélection du PM destination pour la copie
# ===========================================================================

class _CopyDestDialog(QDialog):
    """Sélection du PM destination pour la copie."""

    def __init__(self, source_pm_id: int, parent=None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog
        )
        self.setModal(True)
        self.setFixedSize(340, 500)
        self.setStyleSheet(
            "QDialog { background-color: #F0EDE6; "
            "border: 2px solid #C49A3C; border-radius: 10px; }"
        )
        self.dest_pm_id: int | None = None
        self._source = source_pm_id
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        title = QLabel(f"{t('btn_copy_to').replace('📋  ', '').replace('...', '')} PM-{self._source:02d} vers :")
        title.setStyleSheet(
            "color: #C49A3C; font-size: 15px; font-weight: bold; background: transparent;"
        )
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setSpacing(6)

        for pm_id in sorted(PM_DEFINITIONS.keys()):
            if pm_id == self._source:
                continue
            pm = PM_DEFINITIONS[pm_id]
            btn = QPushButton(f"PM-{pm_id:02d}  ·  {pm.name}")
            btn.setFixedHeight(44)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #FAFAF8;
                    color: #1A1A18;
                    border: 1px solid #C8C4BC;
                    border-radius: 6px;
                    font-size: 13px;
                    text-align: left;
                    padding: 0 12px;
                }
                QPushButton:pressed {
                    background-color: #A07830;
                    color: #1A1A18;
                }
            """)
            btn.clicked.connect(lambda _, pid=pm_id: self._select(pid))
            inner_layout.addWidget(btn)

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll, stretch=1)

        btn_cancel = QPushButton(t("btn_cancel_x"))
        btn_cancel.setFixedHeight(40)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #FAFAF8;
                color: #C62828;
                border: 1px solid #c62828;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:pressed { background-color: #c62828; }
        """)
        btn_cancel.clicked.connect(self.reject)
        layout.addWidget(btn_cancel)

    def _select(self, pm_id: int) -> None:
        self.dest_pm_id = pm_id
        self.accept()


# ===========================================================================
# _FlagTile — tuile langue avec fond drapeau peint + overlay + texte centré
# ===========================================================================

class _FlagTile(QWidget):
    """Tuile cliquable : fond drapeau (QPixmap), overlay semi-transparent, nom centré."""

    clicked = Signal(str)  # émet le code langue

    def __init__(self, code: str, name: str, pixmap: QPixmap, parent=None) -> None:
        super().__init__(parent)
        self._code = code
        self._name = name
        self._flag_pixmap = pixmap
        self._selected = False
        self._pressed = False
        self.setMinimumSize(180, 110)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # Texte centré par-dessus le drapeau
        self._lbl = QLabel(name, self)
        self._lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._lbl.setStyleSheet(
            "color: white; font-size: 14pt; font-weight: bold; background: transparent;"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._lbl)

    def set_selected(self, selected: bool) -> None:
        if self._selected != selected:
            self._selected = selected
            self.update()

    def paintEvent(self, event) -> None:  # noqa: ANN001
        from PySide6.QtGui import QPainterPath
        from PySide6.QtCore import QRectF

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        radius = 12.0
        pen_width = 3 if self._selected else 1

        # Clip arrondi
        path = QPainterPath()
        path.addRoundedRect(QRectF(rect), radius, radius)
        painter.setClipPath(path)

        # Fond : drapeau étiré aux dimensions exactes de la tuile (sans rognage)
        if not self._flag_pixmap.isNull():
            painter.drawPixmap(self.rect(), self._flag_pixmap)
        else:
            painter.fillRect(rect, QColor("#C8C4BC"))

        # Overlay semi-transparent (plus léger si sélectionné)
        if self._pressed:
            overlay_alpha = 110
        else:
            overlay_alpha = 38 if self._selected else 89   # ~0.15 / ~0.35
        painter.fillRect(rect, QColor(0, 0, 0, overlay_alpha))

        painter.setClipping(False)

        # Bordure
        if self._pressed:
            pen_color = QColor("#444444")
            pen_width = max(4, pen_width)
        else:
            pen_color = QColor("#C49A3C") if self._selected else QColor("#888888")
        painter.setPen(QPen(pen_color, pen_width))
        border_rect = QRectF(rect).adjusted(
            pen_width / 2, pen_width / 2, -pen_width / 2, -pen_width / 2
        )
        painter.drawRoundedRect(border_rect, radius, radius)

        painter.end()

    def mousePressEvent(self, event) -> None:  # noqa: ANN001
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            # visual nudge: push contents 2px down
            if self.layout() is not None:
                self.layout().setContentsMargins(0, 2, 0, 0)
            self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: ANN001
        if event.button() == Qt.MouseButton.LeftButton:
            was_pressed = self._pressed
            self._pressed = False
            # restore layout margins
            if self.layout() is not None:
                self.layout().setContentsMargins(0, 0, 0, 0)
            self.update()
            if was_pressed:
                # emit on release to match button behaviour
                self.clicked.emit(self._code)
        super().mouseReleaseEvent(event)


# ===========================================================================
# _LanguePage — sélection de la langue (index 12)
# ===========================================================================

class _LanguePage(QWidget):
    """Page de sélection de la langue — grille 1×6 (une colonne) de tuiles drapeau."""

    def __init__(self, stack: QStackedWidget, parent=None) -> None:
        super().__init__(parent)
        self._main_stack = stack
        self._current = "fr"
        self._tiles: dict[str, _FlagTile] = {}
        self._build_ui()
        self._load_config()

    def _build_ui(self) -> None:
        from ihm.translations import LANGUAGES

        FLAG_PATHS = {
            "fr": "assets/icon/flags/drapeau_francais.png",
            "en": "assets/icon/flags/drapeau_anglais.png",
            "it": "assets/icon/flags/drapeau_italien.png",
            "es": "assets/icon/flags/drapeau_espagnol.png",
            "pt": "assets/icon/flags/drapeau_portugais.png",
            "ro": "assets/icon/flags/drapeau_roumain.png",
        }

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        layout.addWidget(_make_header(
            t("hdr_language"),
            lambda: self._main_stack.setCurrentIndex(1),
        ))

        # Grille 1×6 (une colonne) de tuiles
        body = QWidget()
        body.setStyleSheet(f"background-color: {_C['bg']};")
        grid = QGridLayout(body)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setSpacing(12)

        for idx, (code, name) in enumerate(LANGUAGES.items()):
            row = idx
            col = 0
            pixmap = QPixmap(FLAG_PATHS.get(code, ""))
            tile = _FlagTile(code, name, pixmap, self)
            tile.clicked.connect(self._select_lang)
            grid.addWidget(tile, row, col)
            grid.setRowStretch(row, 1)
            self._tiles[code] = tile

        # Single column stretch
        grid.setColumnStretch(0, 1)

        layout.addWidget(body, stretch=1)

    def _load_config(self) -> None:
        cfg = load_config(_CONFIG_PATH)
        lang = cfg.get("language", "fr")
        self._current = lang
        self._update_tiles(lang)

    def showEvent(self, event) -> None:  # noqa: ANN001
        self._load_config()
        super().showEvent(event)

    def _update_tiles(self, lang: str) -> None:
        for code, tile in self._tiles.items():
            tile.set_selected(code == lang)

    def _select_lang(self, lang: str) -> None:
        from ihm.translations import set_language
        self._current = lang
        self._update_tiles(lang)

        cfg = load_config(_CONFIG_PATH)
        cfg["language"] = lang
        save_config(_CONFIG_PATH, cfg)
        set_language(lang)

        main_win = self._main_stack.window()
        if hasattr(main_win, "apply_language"):
            main_win.apply_language()

        QMessageBox.information(self, t("dlg_language_title"), t("dlg_language_applied_msg"))
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
        root = self.layout()
        if root is None:
            root = QVBoxLayout(self)
            root.setContentsMargins(0, 0, 0, 0)
            root.setSpacing(0)
        else:
            while root.count():
                item = root.takeAt(0)
                w = item.widget()
                if w is not None:
                    w.deleteLater()

        self._settings_stack = QStackedWidget()
        self._settings_stack.addWidget(self._build_page0_home())        # 0
        self._settings_stack.addWidget(self._build_page1_general())     # 1
        self._settings_stack.addWidget(self._build_page2_pm_management())  # 2

        self._cycle_page = _ControleCyclePage(self._settings_stack, self)
        self._settings_stack.addWidget(self._cycle_page)                # 3
        # Voie X / Voie Y : instances créées mais pas ajoutées au stack.
        # Elles sont intégrées côte-à-côte dans la page 13 (Coordonnées).
        # Placeholders aux indices 4 et 5 pour garder les indices stables.
        self._voie_x_page = _VoieXPage(self._settings_stack, self)
        self._settings_stack.addWidget(QWidget())                       # 4 (placeholder)
        self._voie_y_page = _VoieYPage(self._settings_stack, self)
        self._settings_stack.addWidget(QWidget())                       # 5 (placeholder)
        self._pm_edit_page = _PMEditPage(
            self._settings_stack, self._on_pm_saved, self
        )
        self._settings_stack.addWidget(self._pm_edit_page)              # 6
        self._date_heure_page = _DateHeurePage(self._settings_stack, self)
        self._settings_stack.addWidget(self._date_heure_page)           # 7
        self._droits_page = _DroitsAccesPage(self._settings_stack, self)
        self._settings_stack.addWidget(self._droits_page)               # 8
        self._affichage_page = _AffichageProdPage(self._settings_stack, self)
        self._settings_stack.addWidget(self._affichage_page)            # 9
        self._export_page = _ExportationPage(self._settings_stack, self)
        self._settings_stack.addWidget(self._export_page)               # 10
        self._extras_page = _ExtrasPage(self._settings_stack, self)
        self._settings_stack.addWidget(self._extras_page)               # 11
        self._langue_page = _LanguePage(self._settings_stack, self)
        self._settings_stack.addWidget(self._langue_page)               # 12
        self._settings_stack.addWidget(self._build_page13_coordonnees())  # 13
        self._info_sys_page = _InfoSystemePage(self._settings_stack, self)
        self._settings_stack.addWidget(self._info_sys_page)               # 14

        root.addWidget(self._settings_stack)

    def apply_language(self) -> None:
        current_idx = self._settings_stack.currentIndex() if hasattr(self, "_settings_stack") else 0
        self._build_ui()
        self._settings_stack.setCurrentIndex(max(0, min(current_idx, self._settings_stack.count() - 1)))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_header(self, title: str, back_to_home: bool = True) -> QWidget:
        """Délègue à la fonction module-level _make_header."""
        cb = (
            (lambda: self._settings_stack.setCurrentIndex(0))
            if back_to_home
            else self._go_to_production
        )
        return _make_header(title, cb)

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

        v.addWidget(_make_header(t("settings_home_title_icon"), self._go_to_production))

        # Corps — 2 tuiles en grille plein écran
        body = QWidget()
        body.setStyleSheet(f"background-color: {_C['bg']};")
        grid_layout = QVBoxLayout(body)
        grid_layout.setContentsMargins(20, 20, 20, 20)
        grid_layout.setSpacing(16)

        tiles_def = [
            ("assets/icon/settings/Image_kistler/parametre_généraux .png", t("settings_tile_general"),    "#A07830", 1),
            ("assets/icon/settings/Image_kistler/Getion_pm.png", "Gestion PM", "#1565C0", 2),
        ]
        for (icon, label, border, page_idx) in tiles_def:
            tile = _Tile(icon, label, border)
            tile.setFixedSize(680, 560)
            tile.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            tile.clicked.connect(lambda idx=page_idx: self._settings_stack.setCurrentIndex(idx))
            grid_layout.addWidget(tile, alignment=Qt.AlignmentFlag.AlignHCenter)

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

        v.addWidget(self._make_header(t("settings_general_title_icon")))

        grid_w = QWidget()
        grid_w.setStyleSheet(f"background-color: {_C['bg']};")
        grid = QGridLayout(grid_w)
        grid.setContentsMargins(10, 10, 10, 10)
        grid.setSpacing(10)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        grid_w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        _BTN_STYLE = f"""
            QPushButton {{
                background-color: #FAFAF8;
                color: #1A1A18;
                font-size: 16px;
                font-weight: 500;
                border: 1.5px solid #C8C4BC;
                border-radius: 12px;
                padding: 8px;
            }}
            QPushButton:hover {{
                background-color: #F5EDD6;
                border-color: #C49A3C;
                color: #A07830;
            }}
            QPushButton:pressed {{ background-color: {_C['btn_active']}; color: #1A1A18; }}
        """

        coord_label = "Coordonnées" if get_language() == "fr" else "Coordinates"
        info_label = "Informations système" if get_language() == "fr" else "System information"
        buttons = [
            ("assets/icon/settings/Image_kistler/langages.png", t("dlg_language_title"), "langue"),
            ("assets/icon/settings/Image_kistler/Droit_acces.png", t("dlg_access_rights_saved_title"), "droits"),
            ("assets/icon/settings/Image_kistler/date_heure.png", t("dlg_datetime_title"), "date_heure"),
            ("assets/icon/settings/Image_kistler/graphe_x_y.png",  coord_label, "coordonnees"),
            ("assets/icon/settings/Image_kistler/Controle_cycle.png",  t("dlg_cycle_ctrl_title"), "cycle"),
            ("assets/icon/settings/Image_kistler/pinceau.png", t("dlg_display_title"), "affichage"),
            ("assets/icon/settings/Image_kistler/Exportation.png", t("hdr_export"), "exportation"),
            ("assets/icon/settings/Image_kistler/Point_acces.png",  t("hdr_extras"), "extras"),
            ("assets/icon/settings/Image_kistler/System_info.png",  info_label, "info_systeme"),
        ]
        for index, (icon, label, action) in enumerate(buttons):
            row = index // 2
            col = index % 2
            btn = QPushButton()
            btn.setProperty("settings_action", action)
            btn.setObjectName(f"settings_btn_{action}")
            btn.setMinimumHeight(160)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            btn.setStyleSheet(_BTN_STYLE)
            tile_layout = QVBoxLayout(btn)
            tile_layout.setContentsMargins(8, 8, 8, 8)
            tile_layout.setSpacing(6)
            tile_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_lbl = QLabel(icon)
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_lbl.setStyleSheet("font-size: 28px; background: transparent; border: none;")
            pixmap = QPixmap(icon)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(140, 140, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                icon_lbl.setPixmap(pixmap)
            else:
                icon_lbl.setText(icon)
                icon_lbl.setStyleSheet("font-size: 28px; background: transparent; border: none;")
            icon_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            text_lbl = QLabel(label)
            text_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            text_lbl.setWordWrap(True)
            text_lbl.setStyleSheet("font-size: 22px; font-weight: 700; background: transparent; border: none;")
            text_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            tile_layout.addWidget(icon_lbl)
            tile_layout.addWidget(text_lbl)
            if action == "coordonnees":
                btn.clicked.connect(
                    lambda checked=False: self._settings_stack.setCurrentIndex(13)
                )
            elif action == "info_systeme":
                btn.clicked.connect(
                    lambda checked=False: self._settings_stack.setCurrentIndex(14)
                )
            elif action == "cycle":
                btn.clicked.connect(
                    lambda checked=False: self._settings_stack.setCurrentIndex(3)
                )
            elif action == "date_heure":
                btn.clicked.connect(
                    lambda checked=False: self._settings_stack.setCurrentIndex(7)
                )
            elif action == "droits":
                btn.clicked.connect(
                    lambda checked=False: self._settings_stack.setCurrentIndex(8)
                )
            elif action == "affichage":
                btn.clicked.connect(
                    lambda checked=False: self._settings_stack.setCurrentIndex(9)
                )
            elif action == "exportation":
                btn.clicked.connect(
                    lambda checked=False: self._settings_stack.setCurrentIndex(10)
                )
            elif action == "extras":
                btn.clicked.connect(
                    lambda checked=False: self._settings_stack.setCurrentIndex(11)
                )
            elif action == "langue":
                btn.clicked.connect(
                    lambda checked=False: self._settings_stack.setCurrentIndex(12)
                )
            else:
                btn.clicked.connect(
                    lambda checked=False, lbl=label: QMessageBox.information(
                        self, "Réglages", f"{lbl} — À implémenter."
                    )
                )
            # If it's the last tile (Informations système), span two columns
            if action == "info_systeme":
                grid.addWidget(btn, 4, 0, 1, 2)
                btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                btn.setMinimumHeight(160)
            else:
                grid.addWidget(btn, row, col)

        for c in range(2):
            grid.setColumnStretch(c, 1)
        # Ensure rows stretch evenly (5 rows for 9 tiles)
        for r in range(5):
            grid.setRowStretch(r, 1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")
        scroll.setWidget(grid_w)
        v.addWidget(scroll, stretch=1)
        return page

    # ------------------------------------------------------------------
    # Page 13 — Coordonnées (intermédiaire vers Voie X / Voie Y)
    # ------------------------------------------------------------------

    def _build_page13_coordonnees(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        coord_label = "Coordonnées" if get_language() == "fr" else "Coordinates"

        # Barre titre principale
        v.addWidget(_make_header(
            f"⇄  {coord_label}",
            lambda: self._settings_stack.setCurrentIndex(1),
        ))

        # QStackedWidget interne : 0=Voie X, 1=Voie Y
        self._coord_pages = QStackedWidget()

        # Page Voie X : titre section bleu + contenu voie X
        page_x = QWidget()
        px_v = QVBoxLayout(page_x)
        px_v.setContentsMargins(0, 0, 0, 0)
        px_v.setSpacing(0)
        sec_x = QLabel(" Voie X — Capteur de position")
        sec_x.setFixedHeight(54)
        sec_x.setStyleSheet(
            "background:#e8f0fe; border-bottom:1px solid #c5d5f5;"
            " color:#1a56a0; font-size:22px; font-weight:bold;"
            " padding-left:12px;"
        )
        px_v.addWidget(sec_x)
        px_v.addWidget(self._voie_x_page, stretch=1)
        self._coord_pages.addWidget(page_x)

        # Page Voie Y : titre section orange + contenu voie Y
        page_y = QWidget()
        py_v = QVBoxLayout(page_y)
        py_v.setContentsMargins(0, 0, 0, 0)
        py_v.setSpacing(0)
        sec_y = QLabel(" Voie Y — Capteur de force")
        sec_y.setFixedHeight(54)
        sec_y.setStyleSheet(
            "background:#fff3f3; border-bottom:1px solid #ffe0b2;"
            " color:#c62828; font-size:22px; font-weight:bold;"
            " padding-left:12px;"
        )
        py_v.addWidget(sec_y)
        py_v.addWidget(self._voie_y_page, stretch=1)
        self._coord_pages.addWidget(page_y)

        v.addWidget(self._coord_pages, stretch=1)

        # Boutons globaux Annuler / Sauvegarder
        save_bar = QWidget()
        save_bar.setFixedHeight(64)
        save_bar.setStyleSheet("background:#F0EDE6;")
        sh = QHBoxLayout(save_bar)
        sh.setContentsMargins(10, 6, 10, 6)
        sh.setSpacing(10)
        btn_cancel = QPushButton("✗ Annuler")
        btn_cancel.setFixedHeight(64)
        btn_cancel.setStyleSheet(
            "QPushButton { background:#ffffff; border:1.5px solid #dddddd;"
            " border-radius:8px; color:#333333; font-size:20px; font-weight:bold; }"
            "QPushButton:pressed { background:#eeeeee; }"
        )
        btn_cancel.clicked.connect(lambda: self._settings_stack.setCurrentIndex(1))
        sh.addWidget(btn_cancel, stretch=1)
        btn_save = QPushButton("✓ Sauvegarder")
        btn_save.setFixedHeight(64)
        btn_save.setStyleSheet(
            "QPushButton { background:#ffffff; border:1.5px solid #dddddd; border-radius:8px;"
            " color:#333333; font-size:20px; font-weight:bold; }"
            "QPushButton:pressed { background:#A07830; }"
        )
        btn_save.clicked.connect(self._coord_save_current)
        sh.addWidget(btn_save, stretch=2)
        v.addWidget(save_bar)

        # Barre navigation Voie X / Voie Y
        nav_bar = QWidget()
        nav_bar.setFixedHeight(70)
        nav_bar.setStyleSheet("background:#F0EDE6;")
        nh = QHBoxLayout(nav_bar)
        nh.setContentsMargins(10, 8, 10, 8)
        nh.setSpacing(10)
        self._btn_coord_prev = QPushButton("← Voie X")
        self._btn_coord_prev.setFixedHeight(60)
        self._btn_coord_prev.setStyleSheet(
            "QPushButton { background:#ffffff; border:1.5px solid #dddddd;"
            " border-radius:8px; color:#333333; font-size:18px; font-weight:bold; }"
            "QPushButton:pressed { background:#A07830; }"
        )
        self._btn_coord_prev.clicked.connect(self._coord_go_prev)
        self._btn_coord_prev.setVisible(False)
        nh.addWidget(self._btn_coord_prev, stretch=1)
        self._btn_coord_next = QPushButton("Voie Y →")
        self._btn_coord_next.setFixedHeight(60)
        self._btn_coord_next.setStyleSheet(
            "QPushButton { background:#FFFFFF; border:none; border-radius:8px;"
            " color:#333333; font-size:18px; font-weight:bold; }"
            "QPushButton:pressed { background:#A07830; }"
        )
        self._btn_coord_next.clicked.connect(self._coord_go_next)
        nh.addWidget(self._btn_coord_next, stretch=1)
        v.addWidget(nav_bar)

        # État initial : Voie X
        self._coord_pages.setCurrentIndex(0)
        return page

    def _coord_go_next(self) -> None:
        self._coord_pages.setCurrentIndex(1)
        self._btn_coord_prev.setVisible(True)
        self._btn_coord_next.setVisible(False)

    def _coord_go_prev(self) -> None:
        self._coord_pages.setCurrentIndex(0)
        self._btn_coord_prev.setVisible(False)
        self._btn_coord_next.setVisible(True)

    def _coord_save_current(self) -> None:
        if self._coord_pages.currentIndex() == 0:
            self._voie_x_page._save()
        else:
            self._voie_y_page._save()

    # ------------------------------------------------------------------
    # Page 2 — Gestion PM
    # ------------------------------------------------------------------

    def _build_page2_pm_management(self) -> QWidget:
        page = QWidget()
        page.showEvent = self._pm_management_show_event  # type: ignore[method-assign]
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        v.addWidget(self._make_header("Gestion PM"))

        # ── Tableau PM pleine largeur ────────────────────────────────
        self._pm_table = QTableWidget(0, 3)
        self._pm_table.setHorizontalHeaderLabels(["N°", "Nom", "Outils actifs"])

        self._pm_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Fixed)
        self._pm_table.setColumnWidth(0, 52)
        self._pm_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch)
        self._pm_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Fixed)
        self._pm_table.setColumnWidth(2, 200)

        self._pm_table.verticalHeader().setDefaultSectionSize(64)
        self._pm_table.verticalHeader().setVisible(False)
        self._pm_table.horizontalHeader().setFixedHeight(52)
        self._pm_table.horizontalHeader().setStretchLastSection(True)

        self._pm_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._pm_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._pm_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._pm_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._pm_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._pm_table.setStyleSheet(
            "QTableWidget {"
            "  font-size:18px; border:none;"
            "}"
            "QTableWidget::item {"
            "  padding:8px; border-bottom:1px solid #eeeeee;"
            "}"
            "QTableWidget::item:selected {"
            "  background:#fff3e0; color:#333333;"
            "}"
            "QHeaderView::section {"
            "  font-size:18px; font-weight:bold;"
            "  background:#f5f4f0;"
            "  border-bottom:2px solid #dddddd;"
            "  padding:10px;"
            "}"
        )
        self._pm_table.itemSelectionChanged.connect(self._on_pm_table_selection)
        self._pm_table.itemDoubleClicked.connect(self._on_pm_table_double_click)
        v.addWidget(self._pm_table, stretch=1)

        # ── Barre d'actions en bas ───────────────────────────────────
        v.addWidget(self._build_pm_action_bar())

        self._load_pm_table()
        return page

    def _build_pm_action_bar(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(150)
        w.setStyleSheet("background:#f5f4f0; border-top:2px solid #dddddd;")
        vl = QVBoxLayout(w)
        vl.setContentsMargins(12, 10, 12, 10)
        vl.setSpacing(8)

        _STYLE_ENABLED = (
            "QPushButton { background:#ffffff; border:1.5px solid #dddddd;"
            " border-radius:8px; color:#333333; font-size:17px; font-weight:bold; }"
            "QPushButton:pressed { background:#eeeeee; }"
        )
        _STYLE_DISABLED = (
            "QPushButton { background:#f0f0f0; border:1.5px solid #dddddd;"
            " border-radius:8px; color:#bbbbbb; font-size:17px; font-weight:bold; }"
        )
        _STYLE_RAZ = (
            "QPushButton { background:#fff5f5; border:1.5px solid #ef9a9a;"
            " border-radius:8px; color:#c62828; font-size:17px; font-weight:bold; }"
            "QPushButton:pressed { background:#ffebee; }"
            "QPushButton:disabled { background:#f5f5f5; border-color:#dddddd; color:#bbbbbb; }"
        )

        row1 = QHBoxLayout()
        row1.setSpacing(10)
        self._btn_rename = QPushButton("✏  Renommer")
        self._btn_rename.setFixedHeight(56)
        self._btn_rename.setStyleSheet(_STYLE_DISABLED)
        self._btn_rename.setEnabled(False)
        self._btn_rename.clicked.connect(self._pm_manager_rename)
        row1.addWidget(self._btn_rename, stretch=1)

        self._btn_copy = QPushButton("⎘  Copier vers...")
        self._btn_copy.setFixedHeight(56)
        self._btn_copy.setStyleSheet(_STYLE_DISABLED)
        self._btn_copy.setEnabled(False)
        self._btn_copy.clicked.connect(self._pm_manager_copy)
        row1.addWidget(self._btn_copy, stretch=1)
        vl.addLayout(row1)

        self._btn_raz = QPushButton("⚠  RAZ")
        self._btn_raz.setFixedHeight(56)
        self._btn_raz.setStyleSheet(_STYLE_RAZ)
        self._btn_raz.setEnabled(False)
        self._btn_raz.clicked.connect(self._pm_manager_raz)
        vl.addWidget(self._btn_raz)

        # Stocker les styles pour _on_pm_table_selection
        self._pm_btn_style_enabled  = _STYLE_ENABLED
        self._pm_btn_style_disabled = _STYLE_DISABLED

        return w

    def _on_pm_saved(self, pm_id: int) -> None:
        self._load_pm_table()
        for row in range(self._pm_table.rowCount()):
            item = self._pm_table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == pm_id:
                self._pm_table.selectRow(row)
                self._on_pm_table_selection()
                break

    def _on_pm_table_double_click(self, item) -> None:  # noqa: ANN001
        row = self._pm_table.row(item)
        id_item = self._pm_table.item(row, 0)
        pm_id = id_item.data(Qt.ItemDataRole.UserRole) if id_item else None
        if pm_id is None:
            return
        self._pm_edit_page.load_pm(pm_id)
        self._settings_stack.setCurrentIndex(6)

    def _pm_management_show_event(self, event) -> None:  # noqa: ANN001
        self._load_pm_table()

    def _load_pm_table(self) -> None:
        self._pm_table.setRowCount(0)
        cfg = load_config(_CONFIG_PATH)
        programmes = cfg.get("programmes", {})

        for pm_id in sorted(PM_DEFINITIONS.keys()):
            pm = PM_DEFINITIONS[pm_id]
            tools = programmes.get(pm_id, {}).get("tools", {})

            active: list[str] = []
            if any(z.get("enabled") for z in tools.get("no_pass_zones", [tools.get("no_pass", {})])):
                active.append("NO-PASS")
            if any(z.get("enabled") for z in tools.get("uni_box_zones", [tools.get("uni_box", {})])):
                active.append("UNI-BOX")
            if tools.get("envelope", {}).get("enabled"):
                active.append("ENV")
            outils_str = ", ".join(active) if active else "—"

            row = self._pm_table.rowCount()
            self._pm_table.insertRow(row)

            n_item = QTableWidgetItem(f"{pm_id:02d}")
            n_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            n_item.setData(Qt.ItemDataRole.UserRole, pm_id)
            self._pm_table.setItem(row, 0, n_item)
            self._pm_table.setItem(row, 1, QTableWidgetItem(pm.name))

            outils_item = QTableWidgetItem(outils_str)
            outils_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if active:
                outils_item.setForeground(QColor(_C["blue"]))
            self._pm_table.setItem(row, 2, outils_item)

        self._pm_table.clearSelection()
        self._on_pm_table_selection()

    def _pm_manager_selected_id(self) -> int | None:
        rows = self._pm_table.selectedItems()
        if not rows:
            return None
        row = self._pm_table.row(rows[0])
        item = self._pm_table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _on_pm_table_selection(self) -> None:
        enabled = self._pm_manager_selected_id() is not None
        for btn in (self._btn_rename, self._btn_copy):
            btn.setEnabled(enabled)
            btn.setStyleSheet(
                self._pm_btn_style_enabled if enabled else self._pm_btn_style_disabled
            )
        self._btn_raz.setEnabled(enabled)

    def _pm_manager_rename(self) -> None:
        pm_id = self._pm_manager_selected_id()
        if pm_id is None:
            return
        from ihm.main_window import AlphaNumpadDialog
        current_name = PM_DEFINITIONS[pm_id].name
        dlg = AlphaNumpadDialog(
            title=f"{t('btn_rename').replace('✏  ', '')} PM-{pm_id:02d}",
            value=current_name,
            parent=self,
        )
        if not dlg.exec():
            return
        new_name = dlg.value().strip()
        if not new_name:
            return
        # Mettre à jour PM_DEFINITIONS
        from config import ProgramMeasure
        pm = PM_DEFINITIONS[pm_id]
        PM_DEFINITIONS[pm_id] = ProgramMeasure(
            pm_id=pm_id, name=new_name,
            description=pm.description, view_mode=pm.view_mode,
        )
        # Mettre à jour config.yaml
        cfg = load_config(_CONFIG_PATH)
        cfg.setdefault("programmes", {}).setdefault(pm_id, {})["name"] = new_name
        save_config(_CONFIG_PATH, cfg)
        self._load_pm_table()
        self._on_pm_saved(pm_id)

    def _pm_manager_copy(self) -> None:
        pm_id = self._pm_manager_selected_id()
        if pm_id is None:
            return
        dlg = _CopyDestDialog(source_pm_id=pm_id, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted or dlg.dest_pm_id is None:
            return
        dest_id = dlg.dest_pm_id
        cfg = load_config(_CONFIG_PATH)
        progs = cfg.setdefault("programmes", {})
        src_tools = progs.get(pm_id, {}).get("tools", {})
        import copy
        progs.setdefault(dest_id, {})["tools"] = copy.deepcopy(src_tools)
        progs[dest_id]["name"] = f"Copie de {PM_DEFINITIONS[pm_id].name}"
        save_config(_CONFIG_PATH, cfg)
        # Mettre à jour PM_DEFINITIONS pour le nom
        from config import ProgramMeasure
        pm_dest = PM_DEFINITIONS[dest_id]
        PM_DEFINITIONS[dest_id] = ProgramMeasure(
            pm_id=dest_id,
            name=progs[dest_id]["name"],
            description=pm_dest.description,
            view_mode=pm_dest.view_mode,
        )
        self._load_pm_table()
        self._on_pm_saved(dest_id)
        QMessageBox.information(
            self, "Copie effectuée",
            f"PM-{pm_id:02d} copié vers PM-{dest_id:02d}.",
        )

    def _pm_manager_raz(self) -> None:
        pm_id = self._pm_manager_selected_id()
        if pm_id is None:
            return
        reply = QMessageBox.question(
            self, "Remise à zéro",
            f"Remettre PM-{pm_id:02d} à zéro ?\n"
            "Tous les outils seront désactivés et les\n"
            "valeurs remises à 0.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        _default_ub_zone = {
            "enabled": False, "box_x_min": 0.0, "box_x_max": 0.0,
            "box_y_min": 0.0, "box_y_max": 0.0,
            "entry_side": "left", "exit_side": "left",
        }
        _default_np_zone = {"enabled": False, "x_min": 0.0, "x_max": 0.0, "y_limit": 0.0}
        default_tools = {
            "no_pass_zones": [dict(_default_np_zone) for _ in range(5)],
            "uni_box_zones": [dict(_default_ub_zone) for _ in range(5)],
            "envelope": {
                "enabled": False,
                "lower_curve": [[0.0, 0.0], [100.0, 0.0]],
                "upper_curve": [[0.0, 0.0], [100.0, 0.0]],
            },
        }
        cfg = load_config(_CONFIG_PATH)
        cfg.setdefault("programmes", {}).setdefault(pm_id, {})["tools"] = default_tools
        save_config(_CONFIG_PATH, cfg)
        self._load_pm_table()

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