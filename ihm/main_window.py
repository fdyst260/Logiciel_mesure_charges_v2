"""Fenêtre principale IHM riveteuse — 1280×720 paysage, plein écran sans barre.

Architecture Qt :
  MainWindow
  └── Widget central
      └── self.stack (QStackedWidget)
          ├── Page 0 : Production (graphique | panneau droit | barre nav)
          └── Page 1 : SettingsPage (réglages)

Données : on_new_point() accumule dans buffer ; timer 30 FPS vide le buffer.
"""

from __future__ import annotations

import collections
import csv
from datetime import datetime
from pathlib import Path

import yaml

from PySide6.QtCore import Qt, QRect, QTimer, Slot
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config import (
    FORCE_NEWTON_MAX,
    FORCE_THRESHOLD_N,
    PM_DEFINITIONS,
    POSITION_MM_MAX,
    POSITION_THRESHOLD_MM,
)
from core.analysis import DisplayMode
from core.models import EvaluationTool, EvaluationType

# ---------------------------------------------------------------------------
# Constantes de couleur — thème industriel sombre (maXYmos style)
# ---------------------------------------------------------------------------
COLORS: dict[str, str] = {
    # États machine (IEC 60073)
    "ok_bg":          "#1a3a1a",
    "ok_border":      "#2d7a2d",
    "ok_text":        "#4caf50",
    "nok_bg":         "#3a1a1a",
    "nok_border":     "#c62828",
    "nok_text":       "#ef5350",
    "running_bg":     "#1a2a3a",
    "running_border": "#1565c0",
    "idle_bg":        "#1e1e1e",
    "idle_text":      "#9e9e9e",
    # Fond fenêtre dynamique selon état
    "win_idle":       "#121212",
    "win_running":    "#0d1a26",
    "win_ok":         "#0d1a0d",
    "win_nok":        "#1a0d0d",
    # Alarme seuil (jaune ambre IEC 60073)
    "alarm":          "#f57f17",
    "alarm_bg":       "#2a2a1a",
    # Courbe
    "curve_running":  "#1976D2",
    "curve_ok":       "#388E3C",
    "curve_nok":      "#D32F2F",
    "curve_history":  "#616161",
    # Outils graphique
    "nopass_fill":    "#c62828",
    "nopass_border":  "#ef5350",
    "unibox_border":  "#f57f17",
    "envelope_border":"#1565c0",
    "envelope_fill":  "#1565c0",
    # Interface générale
    "bg_main":        "#121212",
    "bg_panel":       "#1e1e1e",
    "bg_button":      "#252525",
    "text_primary":   "#e0e0e0",
    "text_secondary": "#9e9e9e",
    "border":         "#333333",
    "settings_btn":   "#b45309",
    "nav_active":     "#1565c0",
    "export_btn":     "#1a3a1a",
    "raz_btn":        "#3a1a1a",
    # Aliases pour compatibilité avec l'existant
    "bg_graph":       "#121212",
    "grid":           "#222222",
    "axis_text":      "#556677",
    "curve_live":     "#1976D2",
    "tool_no_pass":   "#c62828",
    "tool_unibox":    "#f57f17",
    "tool_envelope":  "#1565c0",
    "result_ok":      "#1a3a1a",
    "result_nok":     "#3a1a1a",
    "result_idle":    "#1e1e1e",
    "panel_bg":       "#1e1e1e",
    "separator":      "#333333",
    "progress_ok":    "#4caf50",
    "progress_warn":  "#ef5350",
}

_PIN_CODE = "1234"
_MAX_PIN_ATTEMPTS = 3
_LOCKOUT_SECONDS = 30

# ---------------------------------------------------------------------------
# Feuille de style globale QSS
# ---------------------------------------------------------------------------
STYLESHEET = f"""
QMainWindow, QWidget#central {{
    background-color: {COLORS['bg_main']};
    color: {COLORS['text_primary']};
    font-family: 'Segoe UI', Arial, sans-serif;
}}
QLabel {{
    background-color: transparent;
    font-size: 15px;
    font-weight: 500;
}}
QLabel#result_label {{
    font-size: 52px;
    font-weight: bold;
    border-radius: 10px;
    padding: 10px;
}}
QLabel#counter_ok   {{ color: {COLORS['ok_text']}; font-size: 22px; font-weight: bold; }}
QLabel#counter_nok  {{ color: {COLORS['nok_text']}; font-size: 22px; font-weight: bold; }}
QLabel#counter_tot  {{ color: {COLORS['text_primary']}; font-size: 22px; font-weight: bold; }}
QLabel#datetime_label {{ font-size: 12px; color: {COLORS['text_secondary']}; }}
QLabel#pm_section_title {{ font-size: 13px; font-weight: bold; color: #378ADD; }}
QLabel#pm_btn_label {{ font-size: 17px; font-weight: bold; color: {COLORS['text_primary']}; }}
QLabel#live_label   {{ font-size: 15px; font-weight: 600; color: {COLORS['text_secondary']}; }}
QLabel#live_value   {{ font-size: 26px; font-weight: bold; color: {COLORS['text_primary']}; }}
QLabel#peak_label   {{ font-size: 15px; font-weight: 600; color: {COLORS['text_secondary']}; }}
QLabel#peak_value   {{ font-size: 22px; font-weight: bold; color: #378ADD; }}

QProgressBar {{
    border: none;
    border-radius: 4px;
    background-color: #2a2a2a;
    max-height: 10px;
}}
QProgressBar::chunk {{
    border-radius: 4px;
    background-color: {COLORS['ok_text']};
}}
QProgressBar[alarm="true"]::chunk {{
    background-color: {COLORS['alarm']};
}}

QPushButton#btn_pm {{
    background-color: {COLORS['bg_button']};
    color: {COLORS['text_primary']};
    font-size: 14px;
    font-weight: bold;
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    padding: 6px;
}}
QPushButton#btn_pm:pressed {{ background-color: {COLORS['nav_active']}; }}

QPushButton#btn_settings {{
    background-color: {COLORS['settings_btn']};
    color: #ffffff;
    font-size: 16px;
    font-weight: bold;
    border-radius: 8px;
    border: 1px solid #d97706;
    min-height: 60px;
}}
QPushButton#btn_settings:pressed {{ background-color: #92400e; }}

QPushButton#nav_btn {{
    background-color: {COLORS['bg_button']};
    color: {COLORS['text_secondary']};
    font-size: 15px;
    font-weight: 600;
    border-radius: 8px;
    border: 1px solid {COLORS['border']};
    min-height: 58px;
}}
QPushButton#nav_btn:checked, QPushButton#nav_btn:pressed {{
    background-color: {COLORS['nav_active']};
    color: #ffffff;
    border-color: #42a5f5;
}}
QPushButton#nav_btn_green {{
    background-color: {COLORS['export_btn']};
    color: #81c784;
    font-size: 15px;
    font-weight: 600;
    border-radius: 8px;
    border: 1px solid {COLORS['ok_border']};
    min-height: 58px;
}}
QPushButton#nav_btn_red {{
    background-color: {COLORS['raz_btn']};
    color: #ef9a9a;
    font-size: 15px;
    font-weight: 600;
    border-radius: 8px;
    border: 1px solid {COLORS['nok_border']};
    min-height: 58px;
}}
QFrame#separator {{
    background-color: {COLORS['border']};
    max-height: 1px;
}}
"""

# ---------------------------------------------------------------------------
# Style du dialogue PIN
# ---------------------------------------------------------------------------
PINSTYLE = """
QDialog { background-color: #1e1e1e; }
QLabel  { color: #e0e0e0; font-size: 15px; }
QLineEdit {
    background-color: #2a2a2a;
    color: #ffffff;
    border: 2px solid #444;
    border-radius: 8px;
    font-size: 28px;
    padding: 8px;
    letter-spacing: 12px;
}
QLineEdit:focus { border-color: #378ADD; }
QPushButton {
    background-color: #378ADD;
    color: white;
    border-radius: 8px;
    padding: 10px 24px;
    font-size: 14px;
    font-weight: bold;
    border: none;
}
QPushButton:pressed { background-color: #185FA5; }
"""


# ===========================================================================
# GraphWidget — tracé temps réel QPainter (sans matplotlib)
# ===========================================================================

class GraphWidget(QWidget):
    """Tracé temps réel Force=f(Position) ou f(t), rendu par QPainter."""

    _GRID_DIVS = 5
    # Marges internes (pixels)
    _ML, _MR, _MT, _MB = 55, 15, 15, 35

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(400, 300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._current_points: list[tuple[float, float, float]] = []
        self._history: collections.deque[tuple[list, str]] = collections.deque(maxlen=20)
        self._display_mode: DisplayMode = DisplayMode.FORCE_POSITION
        self._history_mode: bool = False
        self._tools: list[EvaluationTool] = []
        self._tools_config: dict = {}
        self._current_result: str | None = None

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    def set_tools(self, tools: list[EvaluationTool]) -> None:
        self._tools = tools
        self.update()

    def set_tools_config(self, tools_config: dict) -> None:
        """Charge la configuration des outils depuis config.yaml (dict brut)."""
        self._tools_config = tools_config
        self.update()

    def set_display_mode(self, mode: DisplayMode) -> None:
        self._display_mode = mode
        self._current_points.clear()
        self.update()

    def set_history_mode(self, enabled: bool) -> None:
        self._history_mode = enabled
        self.update()

    def add_points(self, points: list[tuple[float, float, float]]) -> None:
        """Ajoute les points du buffer (appelé par le timer 30 fps)."""
        self._current_points.extend(points)
        self.update()

    def finish_cycle(self, result: str) -> None:
        """Clôture le cycle courant dans l'historique."""
        if self._current_points:
            self._history.append((list(self._current_points), result))
        self._current_result = result
        self._current_points.clear()
        self.update()

    def start_new_cycle(self) -> None:
        self._current_points.clear()
        self._current_result = None
        self.update()

    # ------------------------------------------------------------------
    # Géométrie
    # ------------------------------------------------------------------

    def _plot_rect(self) -> QRect:
        w = self.width() - self._ML - self._MR
        h = self.height() - self._MT - self._MB
        return QRect(self._ML, self._MT, w, h)

    def _get_ranges(self) -> tuple[float, float]:
        if self._display_mode == DisplayMode.FORCE_POSITION:
            return POSITION_MM_MAX, FORCE_NEWTON_MAX
        if self._display_mode == DisplayMode.FORCE_TIME:
            return 2.0, FORCE_NEWTON_MAX
        return 2.0, POSITION_MM_MAX

    def _pt_to_data(self, t: float, f: float, x: float) -> tuple[float, float]:
        if self._display_mode == DisplayMode.FORCE_POSITION:
            return x, f
        if self._display_mode == DisplayMode.FORCE_TIME:
            return t, f
        return t, x

    def _to_px(self, xd: float, yd: float, rect: QRect) -> tuple[int, int]:
        xr, yr = self._get_ranges()
        px = rect.left() + xd / xr * rect.width()
        py = rect.bottom() - yd / yr * rect.height()
        return int(px), int(py)

    # ------------------------------------------------------------------
    # paintEvent
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Fond global
        painter.fillRect(self.rect(), QColor(COLORS["bg_graph"]))

        rect = self._plot_rect()

        # Lignes d'axes (hors clip)
        self._draw_axis_lines(painter, rect)

        # Grille + outils + courbes (clippés dans rect)
        painter.save()
        painter.setClipRect(rect)
        self._draw_grid(painter, rect)
        self._draw_tool_overlays(painter, rect)

        if self._history_mode:
            for pts, _ in list(self._history)[:-1]:
                self._draw_curve(painter, pts, QColor(COLORS["curve_history"]), rect)
            if self._history:
                pts, res = self._history[-1]
                c = COLORS["curve_ok"] if res == "PASS" else COLORS["curve_nok"]
                self._draw_curve(painter, pts, QColor(c), rect)
        elif self._current_points:
            if self._current_result == "PASS":
                color = QColor(COLORS["curve_ok"])
            elif self._current_result == "NOK":
                color = QColor(COLORS["curve_nok"])
            else:
                color = QColor(COLORS["curve_live"])
            self._draw_curve(painter, self._current_points, color, rect)

        painter.restore()

        # Labels axes (hors clip)
        self._draw_axes(painter, rect)
        painter.end()

    def _draw_axis_lines(self, painter: QPainter, rect: QRect) -> None:
        pen = QPen(QColor("#445566"))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawLine(rect.left(), rect.top(), rect.left(), rect.bottom())
        painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())

    def _draw_grid(self, painter: QPainter, rect: QRect) -> None:
        pen = QPen(QColor(COLORS["grid"]))
        pen.setWidth(1)
        painter.setPen(pen)
        for i in range(1, self._GRID_DIVS):
            x = rect.left() + int(i * rect.width() / self._GRID_DIVS)
            painter.drawLine(x, rect.top(), x, rect.bottom())
            y = rect.top() + int(i * rect.height() / self._GRID_DIVS)
            painter.drawLine(rect.left(), y, rect.right(), y)

    def _draw_curve(
        self,
        painter: QPainter,
        points: list[tuple[float, float, float]],
        color: QColor,
        rect: QRect,
    ) -> None:
        if len(points) < 2:
            return
        pen = QPen(color)
        pen.setWidthF(2.5)
        painter.setPen(pen)
        prev: tuple[int, int] | None = None
        for t, f, x in points:
            xd, yd = self._pt_to_data(t, f, x)
            px, py = self._to_px(xd, yd, rect)
            if prev is not None:
                painter.drawLine(prev[0], prev[1], px, py)
            prev = (px, py)

    def _draw_tool_overlays(self, painter: QPainter, rect: QRect) -> None:
        if self._display_mode != DisplayMode.FORCE_POSITION:
            return
        # Priorité : config YAML si disponible, sinon EvaluationTool
        if self._tools_config:
            self._draw_overlays_from_config(painter, rect)
        else:
            for tool in self._tools:
                if tool.tool_type == EvaluationType.NO_PASS:
                    self._draw_no_pass(painter, tool, rect)
                elif tool.tool_type == EvaluationType.UNI_BOX:
                    self._draw_unibox(painter, tool, rect)
                elif tool.tool_type == EvaluationType.ENVELOPE:
                    self._draw_envelope(painter, tool, rect)

    def _draw_overlays_from_config(self, painter: QPainter, rect: QRect) -> None:
        """Dessine les outils depuis le dict config.yaml (couleurs IEC 60073)."""
        _xr, yr = self._get_ranges()

        np_d = self._tools_config.get("no_pass", {})
        if np_d.get("enabled"):
            x1, y1 = self._to_px(np_d["x_min"], yr, rect)
            x2, y2 = self._to_px(np_d["x_max"], np_d["y_limit"], rect)
            fill = QColor(198, 40, 40, 60)
            painter.fillRect(x1, y1, x2 - x1, y2 - y1, fill)
            painter.setPen(QPen(QColor(COLORS["nopass_border"]), 1.5, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(x1, y1, x2 - x1, y2 - y1)

        ub_d = self._tools_config.get("uni_box", {})
        if ub_d.get("enabled"):
            x1, y1 = self._to_px(ub_d["box_x_min"], ub_d["box_y_max"], rect)
            x2, y2 = self._to_px(ub_d["box_x_max"], ub_d["box_y_min"], rect)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(COLORS["unibox_border"]), 2, Qt.PenStyle.DashLine))
            painter.drawRect(x1, y1, x2 - x1, y2 - y1)

        env_d = self._tools_config.get("envelope", {})
        if env_d.get("enabled"):
            lower = env_d.get("lower_curve", [])
            upper = env_d.get("upper_curve", [])
            if len(lower) >= 2 and len(upper) >= 2:
                from PySide6.QtGui import QPolygon
                from PySide6.QtCore import QPoint
                poly = QPolygon()
                for x, y in lower:
                    px, py = self._to_px(x, y, rect)
                    poly.append(QPoint(px, py))
                for x, y in reversed(upper):
                    px, py = self._to_px(x, y, rect)
                    poly.append(QPoint(px, py))
                fill_env = QColor(21, 101, 192, 20)
                painter.setBrush(fill_env)
                painter.setPen(QPen(Qt.PenStyle.NoPen))
                painter.drawPolygon(poly)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                pen_env = QPen(QColor(COLORS["envelope_border"]), 1.5, Qt.PenStyle.DashLine)
                painter.setPen(pen_env)
                for curve in (lower, upper):
                    for i in range(len(curve) - 1):
                        px1, py1 = self._to_px(curve[i][0], curve[i][1], rect)
                        px2, py2 = self._to_px(curve[i + 1][0], curve[i + 1][1], rect)
                        painter.drawLine(px1, py1, px2, py2)

    def _draw_no_pass(self, painter: QPainter, tool: EvaluationTool, rect: QRect) -> None:
        if None in (tool.x_min, tool.x_max, tool.y_limit):
            return
        _xr, yr = self._get_ranges()
        x1, y1 = self._to_px(tool.x_min, yr, rect)
        x2, y2 = self._to_px(tool.x_max, tool.y_limit, rect)
        color = QColor(COLORS["tool_no_pass"])
        color.setAlpha(80)
        painter.fillRect(x1, y1, x2 - x1, y2 - y1, color)

    def _draw_unibox(self, painter: QPainter, tool: EvaluationTool, rect: QRect) -> None:
        if None in (tool.box_x_min, tool.box_x_max, tool.box_y_min, tool.box_y_max):
            return
        pen = QPen(QColor(COLORS["tool_unibox"]))
        pen.setWidth(2)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        x1, y1 = self._to_px(tool.box_x_min, tool.box_y_max, rect)
        x2, y2 = self._to_px(tool.box_x_max, tool.box_y_min, rect)
        painter.drawRect(x1, y1, x2 - x1, y2 - y1)

    def _draw_envelope(self, painter: QPainter, tool: EvaluationTool, rect: QRect) -> None:
        pen = QPen(QColor(COLORS["tool_envelope"]))
        pen.setWidth(2)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        for curve in (tool.lower_curve, tool.upper_curve):
            pts = list(curve)
            for i in range(len(pts) - 1):
                px1, py1 = self._to_px(pts[i].x, pts[i].y, rect)
                px2, py2 = self._to_px(pts[i + 1].x, pts[i + 1].y, rect)
                painter.drawLine(px1, py1, px2, py2)

    def _draw_axes(self, painter: QPainter, rect: QRect) -> None:
        xr, yr = self._get_ranges()
        x_unit = "mm" if self._display_mode == DisplayMode.FORCE_POSITION else "s"
        y_unit = "mm" if self._display_mode == DisplayMode.POSITION_TIME else "N"

        _axis_font = QFont("monospace", 11)
        _axis_font.setBold(True)
        painter.setFont(_axis_font)
        painter.setPen(QColor(COLORS["axis_text"]))

        # 6 valeurs (GRID_DIVS + 1)
        for i in range(self._GRID_DIVS + 1):
            # Labels Y — alignés à droite dans la marge gauche
            val_y = i * yr / self._GRID_DIVS
            py = rect.bottom() - int(i * rect.height() / self._GRID_DIVS)
            lbl_y = f"{val_y:.0f}{y_unit}"
            painter.drawText(QRect(0, py - 8, self._ML - 4, 16), Qt.AlignmentFlag.AlignRight, lbl_y)

            # Labels X — centrés sous chaque graduation
            val_x = i * xr / self._GRID_DIVS
            px = rect.left() + int(i * rect.width() / self._GRID_DIVS)
            lbl_x = f"{val_x:.0f}{x_unit}"
            painter.drawText(QRect(px - 20, rect.bottom() + 4, 40, 20), Qt.AlignmentFlag.AlignCenter, lbl_x)


# ===========================================================================
# PinDialog — saisie PIN avec verrouillage
# ===========================================================================

class PinDialog(QDialog):
    """Dialogue PIN 4 chiffres, 3 tentatives, verrouillage 30 s."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Accès réglages")
        self.setModal(True)
        self.setFixedSize(360, 250)
        self.setStyleSheet(PINSTYLE)

        self._attempts = 0
        self._locked = False
        self._lockout_remaining = _LOCKOUT_SECONDS
        self._lockout_timer = QTimer(self)
        self._lockout_timer.setInterval(1000)
        self._lockout_timer.timeout.connect(self._on_lockout_tick)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)

        self._label = QLabel("Entrez le code PIN (4 chiffres) :")
        layout.addWidget(self._label)

        self._pin_edit = QLineEdit()
        self._pin_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._pin_edit.setMaxLength(4)
        self._pin_edit.setPlaceholderText("••••")
        self._pin_edit.setMinimumHeight(56)
        self._pin_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._pin_edit.returnPressed.connect(self._validate)
        layout.addWidget(self._pin_edit)

        self._error_label = QLabel("")
        self._error_label.setStyleSheet("color: #E24B4A; font-size: 12px;")
        layout.addWidget(self._error_label)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.button(QDialogButtonBox.StandardButton.Ok).setMinimumHeight(48)
        btn_box.button(QDialogButtonBox.StandardButton.Cancel).setMinimumHeight(48)
        btn_box.accepted.connect(self._validate)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _validate(self) -> None:
        if self._locked:
            return
        if self._pin_edit.text() == _PIN_CODE:
            self.accept()
        else:
            self._attempts += 1
            remaining = _MAX_PIN_ATTEMPTS - self._attempts
            if remaining > 0:
                self._error_label.setText(f"PIN incorrect — {remaining} tentative(s).")
            else:
                self._start_lockout()
            self._pin_edit.clear()

    def _start_lockout(self) -> None:
        self._locked = True
        self._lockout_remaining = _LOCKOUT_SECONDS
        self._pin_edit.setEnabled(False)
        self._lockout_timer.start()
        self._update_lockout_label()

    def _on_lockout_tick(self) -> None:
        self._lockout_remaining -= 1
        if self._lockout_remaining <= 0:
            self._lockout_timer.stop()
            self._locked = False
            self._attempts = 0
            self._pin_edit.setEnabled(True)
            self._error_label.setText("Vous pouvez réessayer.")
        else:
            self._update_lockout_label()

    def _update_lockout_label(self) -> None:
        self._error_label.setText(
            f"Trop de tentatives — réessayez dans {self._lockout_remaining} s."
        )


# ===========================================================================
# MainWindow — fenêtre principale 1280×720
# ===========================================================================

class MainWindow(QMainWindow):
    """Fenêtre principale IHM riveteuse (1280×720, plein écran sans barre)."""

    def __init__(
        self,
        pm_id: int = 1,
        tools: list[EvaluationTool] | None = None,
        fullscreen: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("ACM — Riveteuse")

        self._pm_id = pm_id
        self._tools = tools or []
        self._display_mode = DisplayMode.FORCE_POSITION

        # Compteurs cycles
        self._count_ok = 0
        self._count_nok = 0

        # Buffer 30 FPS
        self._point_buffer: list[tuple[float, float, float]] = []
        self._last_force: float = 0.0
        self._last_pos: float = 0.0

        # Peaks cycle courant
        self._cycle_fmax: float = 0.0
        self._cycle_xmax: float = 0.0

        # Log production
        self._production_log: list[tuple[int, float, float, str, str]] = []

        # Flag premier point du cycle courant
        self._cycle_started: bool = False

        self.setStyleSheet(STYLESHEET)
        self._build_ui()
        self._apply_state_style("idle")

        # Charger les outils depuis config.yaml
        try:
            cfg_path = Path(__file__).parent.parent / "config.yaml"
            cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
            pm_tools = cfg.get("programmes", {}).get(self._pm_id, {}).get("tools", {})
            self._graph.set_tools_config(pm_tools)
        except Exception:
            pass

        # Timer 30 FPS
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(33)
        self._refresh_timer.timeout.connect(self._flush_buffer)
        self._refresh_timer.start()

        # Échap → quitter (dev)
        shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        shortcut.activated.connect(self.close)

        self._setup_window()

    # ------------------------------------------------------------------
    # Setup fenêtre
    # ------------------------------------------------------------------

    def _setup_window(self) -> None:
        """Adapte la taille à la résolution réelle de l'écran."""
        screen = QApplication.primaryScreen()
        screen_size = screen.size()
        screen_w = screen_size.width()
        screen_h = screen_size.height()

        print(f"[IHM] Résolution détectée : {screen_w}×{screen_h}")

        # Plein écran sans barre de titre
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setGeometry(0, 0, screen_w, screen_h)
        self.showFullScreen()

    # ------------------------------------------------------------------
    # Construction de l'interface
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Stack principal : Page 0 = Production | Page 1 = Réglages
        self.stack = QStackedWidget()
        root.addWidget(self.stack)

        # Page 0 — Production
        self.stack.addWidget(self._build_production_page())

        # Page 1 — Réglages (import différé pour éviter les imports circulaires)
        from ihm.settings_dialog import SettingsPage
        self.stack.addWidget(SettingsPage(parent=self))

    def _build_production_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("production_page")
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # Ligne contenu : graphique | panneau droit
        content = QWidget()
        h = QHBoxLayout(content)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        # Graphique (QStackedWidget : courbe ou table données)
        self._content_stack = QStackedWidget()
        self._graph = GraphWidget()
        self._graph.set_tools(self._tools)
        self._data_table = self._build_data_table()
        self._content_stack.addWidget(self._graph)       # index 0
        self._content_stack.addWidget(self._data_table)  # index 1
        self._graph.setMinimumWidth(860)
        h.addWidget(self._content_stack, stretch=1)

        # Panneau droit — 420px fixe
        right = self._build_right_panel()
        right.setFixedWidth(420)
        h.addWidget(right)

        v.addWidget(content, stretch=1)
        v.addWidget(self._build_nav_bar())
        return page

    # ------------------------------------------------------------------
    # Panneau droit — résultat + compteurs + PM + peaks + live + réglages
    # ------------------------------------------------------------------

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(
            f"background-color: {COLORS['panel_bg']}; "
            f"border-left: 1px solid {COLORS['separator']};"
        )
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        # 1. Badge résultat — 140px
        self._result_badge = QLabel("ATTENTE")
        self._result_badge.setObjectName("result_label")
        self._result_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._result_badge.setFixedHeight(140)
        self._result_badge.setStyleSheet(
            f"background-color: {COLORS['idle_bg']}; color: {COLORS['idle_text']}; "
            "border: 2px solid #333; border-radius: 10px; "
            "font-size: 36px; font-weight: bold; padding: 10px;"
        )
        layout.addWidget(self._result_badge)

        # 2. Compteurs ✓ / ✗ / Σ — 55px, 3 colonnes
        counters_w = QWidget()
        counters_w.setFixedHeight(55)
        counters_w.setStyleSheet(
            "background-color: #1e1e1e; border: 1px solid #333; border-radius: 6px;"
        )
        ch = QHBoxLayout(counters_w)
        ch.setContentsMargins(10, 4, 10, 4)
        ch.setSpacing(0)

        self._ok_count_label = QLabel("✓  0")
        self._ok_count_label.setObjectName("counter_ok")
        self._ok_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._nok_count_label = QLabel("✗  0")
        self._nok_count_label.setObjectName("counter_nok")
        self._nok_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._total_count_label = QLabel("Σ  0")
        self._total_count_label.setObjectName("counter_tot")
        self._total_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        ch.addWidget(self._ok_count_label, stretch=1)
        ch.addWidget(self._make_vsep())
        ch.addWidget(self._nok_count_label, stretch=1)
        ch.addWidget(self._make_vsep())
        ch.addWidget(self._total_count_label, stretch=1)
        layout.addWidget(counters_w)

        # 3. Horodatage — 40px
        self._datetime_label = QLabel(datetime.now().strftime("%d/%m/%y   %H:%M:%S"))
        self._datetime_label.setObjectName("datetime_label")
        self._datetime_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._datetime_label.setFixedHeight(40)
        layout.addWidget(self._datetime_label)

        self._dt_timer = QTimer(self)
        self._dt_timer.setInterval(1000)
        self._dt_timer.timeout.connect(self._update_datetime)
        self._dt_timer.start()

        layout.addWidget(self._make_separator())

        # 4. Label PM — 30px
        pm_section = QLabel("ACM — Riveteuse")
        pm_section.setObjectName("pm_section_title")
        pm_section.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pm_section.setFixedHeight(30)
        layout.addWidget(pm_section)

        # 5. Bouton PM actif — 45px
        pm = PM_DEFINITIONS.get(self._pm_id)
        pm_name = pm.name if pm else "—"
        self._pm_btn = QPushButton(f"PM-{self._pm_id:02d}  ·  {pm_name}")
        self._pm_btn.setObjectName("btn_pm")
        self._pm_btn.setFixedHeight(45)
        self._pm_btn.clicked.connect(self._on_pm_clicked)
        layout.addWidget(self._pm_btn)

        layout.addWidget(self._make_separator())

        # 6. Fmax — 50px
        fmax_row = QHBoxLayout()
        lbl_fmax = QLabel("Fmax")
        lbl_fmax.setObjectName("peak_label")
        self._fmax_label = QLabel("0 N")
        self._fmax_label.setObjectName("peak_value")
        self._fmax_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        fmax_row.addWidget(lbl_fmax)
        fmax_row.addWidget(self._fmax_label)
        fmax_w = QWidget()
        fmax_w.setFixedHeight(50)
        fmax_w.setLayout(fmax_row)
        layout.addWidget(fmax_w)

        # 7. Xmax — 50px
        xmax_row = QHBoxLayout()
        lbl_xmax = QLabel("Xmax")
        lbl_xmax.setObjectName("peak_label")
        self._xmax_label = QLabel("0.0 mm")
        self._xmax_label.setObjectName("peak_value")
        self._xmax_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        xmax_row.addWidget(lbl_xmax)
        xmax_row.addWidget(self._xmax_label)
        xmax_w = QWidget()
        xmax_w.setFixedHeight(50)
        xmax_w.setLayout(xmax_row)
        layout.addWidget(xmax_w)

        layout.addWidget(self._make_separator())

        # 8. Force live (compact)
        lbl_f = QLabel("Force")
        lbl_f.setObjectName("live_label")
        layout.addWidget(lbl_f)
        live_f_row = QHBoxLayout()
        self._force_value = QLabel("0 N")
        self._force_value.setObjectName("live_value")
        self._force_bar = QProgressBar()
        self._force_bar.setRange(0, int(FORCE_NEWTON_MAX))
        self._force_bar.setValue(0)
        self._force_bar.setTextVisible(False)
        self._force_bar.setProperty("alarm", "false")
        live_f_row.addWidget(self._force_value)
        live_f_row.addWidget(self._force_bar, stretch=1)
        layout.addLayout(live_f_row)

        # 9. Position live (compact)
        lbl_p = QLabel("Position")
        lbl_p.setObjectName("live_label")
        layout.addWidget(lbl_p)
        live_p_row = QHBoxLayout()
        self._pos_value = QLabel("0.0 mm")
        self._pos_value.setObjectName("live_value")
        self._pos_bar = QProgressBar()
        self._pos_bar.setRange(0, int(POSITION_MM_MAX))
        self._pos_bar.setValue(0)
        self._pos_bar.setTextVisible(False)
        self._pos_bar.setProperty("alarm", "false")
        live_p_row.addWidget(self._pos_value)
        live_p_row.addWidget(self._pos_bar, stretch=1)
        layout.addLayout(live_p_row)

        # 10. Stretch
        layout.addStretch()

        # 11. Bouton RÉGLAGES — 60px
        self._settings_btn = QPushButton("⚙   RÉGLAGES")
        self._settings_btn.setObjectName("btn_settings")
        self._settings_btn.setMinimumHeight(60)
        self._settings_btn.clicked.connect(self._on_settings_clicked)
        layout.addWidget(self._settings_btn)

        return panel

    # ------------------------------------------------------------------
    # Barre de navigation bas
    # ------------------------------------------------------------------

    def _build_nav_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(70)
        bar.setStyleSheet(
            f"background-color: {COLORS['panel_bg']}; "
            f"border-top: 1px solid {COLORS['separator']};"
        )
        h = QHBoxLayout(bar)
        h.setContentsMargins(6, 6, 6, 6)
        h.setSpacing(6)

        btn_group = QButtonGroup(bar)
        btn_group.setExclusive(True)

        specs = [
            ("📈  Courbe actuelle", "nav_btn",       self._show_current_curve, True),
            ("🕐  Historique",      "nav_btn",        self._show_history,       False),
            ("📊  Données",         "nav_btn",        self._show_data_table,    False),
            ("💾  Export CSV",      "nav_btn_green",  self._export_csv,         False),
            ("🔄  RAZ",             "nav_btn_red",    self._reset_counters,     False),
        ]

        for label, obj_name, callback, checked in specs:
            btn = QPushButton(label)
            btn.setObjectName(obj_name)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            btn.clicked.connect(callback)
            if obj_name == "nav_btn":
                btn.setCheckable(True)
                btn.setChecked(checked)
                btn_group.addButton(btn)
            h.addWidget(btn, stretch=1)

        return bar

    def _build_data_table(self) -> QTableWidget:
        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels(["Cycle", "Fmax (N)", "Xmax (mm)", "Résultat", "Heure"])
        table.setStyleSheet(
            "background-color: #181818; color: #e0e0e0; "
            "gridline-color: #333; alternate-background-color: #1e1e1e;"
        )
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setDefaultSectionSize(140)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        return table

    # ------------------------------------------------------------------
    # Helpers UI
    # ------------------------------------------------------------------

    @staticmethod
    def _make_separator() -> QFrame:
        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {COLORS['separator']};")
        return sep

    @staticmethod
    def _make_vsep() -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedWidth(1)
        sep.setStyleSheet(f"background-color: {COLORS['separator']};")
        return sep

    # ------------------------------------------------------------------
    # Fond de fenêtre dynamique
    # ------------------------------------------------------------------

    def _apply_state_style(self, state: str) -> None:
        """Modifie le fond de la page production sans écraser STYLESHEET."""
        color_map = {
            "idle":      COLORS["win_idle"],
            "acquiring": COLORS["win_running"],
            "ok":        COLORS["win_ok"],
            "nok":       COLORS["win_nok"],
        }
        bg = color_map.get(state, COLORS["win_idle"])
        self.centralWidget().setStyleSheet(f"background-color: {bg};")

    def _update_result_display(self, status: str) -> None:
        """Met à jour badge résultat + fond fenêtre selon l'état."""
        if status == "ok":
            self._result_badge.setText("OK")
            self._result_badge.setStyleSheet(
                f"background-color: {COLORS['ok_bg']}; color: {COLORS['ok_text']}; "
                f"border: 2px solid {COLORS['ok_border']}; border-radius: 10px; "
                "font-size: 52px; font-weight: bold; padding: 10px;"
            )
            self._apply_state_style("ok")
        elif status == "nok":
            self._result_badge.setText("NOK")
            self._result_badge.setStyleSheet(
                f"background-color: {COLORS['nok_bg']}; color: {COLORS['nok_text']}; "
                f"border: 2px solid {COLORS['nok_border']}; border-radius: 10px; "
                "font-size: 52px; font-weight: bold; padding: 10px;"
            )
            self._apply_state_style("nok")
        elif status == "running":
            self._result_badge.setText("EN COURS")
            self._result_badge.setStyleSheet(
                f"background-color: {COLORS['running_bg']}; color: #42a5f5; "
                f"border: 2px solid {COLORS['running_border']}; border-radius: 10px; "
                "font-size: 36px; font-weight: bold; padding: 10px;"
            )
            self._apply_state_style("acquiring")
        else:  # idle
            self._result_badge.setText("ATTENTE")
            self._result_badge.setStyleSheet(
                f"background-color: {COLORS['idle_bg']}; color: {COLORS['idle_text']}; "
                "border: 2px solid #333; border-radius: 10px; "
                "font-size: 36px; font-weight: bold; padding: 10px;"
            )
            self._apply_state_style("idle")

    # ------------------------------------------------------------------
    # Slots de données (connectés depuis main.py via AcquisitionBridge)
    # ------------------------------------------------------------------

    @Slot(float, float, float)
    def on_new_point(self, t: float, force_n: float, pos_mm: float) -> None:
        """Accumule un point dans le buffer — pas de redessin immédiat."""
        if not self._cycle_started:
            self._cycle_started = True
            self._update_result_display("running")
        self._point_buffer.append((t, force_n, pos_mm))
        self._last_force = force_n
        self._last_pos = pos_mm
        if force_n > self._cycle_fmax:
            self._cycle_fmax = force_n
        if pos_mm > self._cycle_xmax:
            self._cycle_xmax = pos_mm

    @Slot(str)
    def on_cycle_finished(self, result: str) -> None:
        """Reçoit le résultat final du cycle (PASS ou NOK)."""
        self._cycle_started = False
        if result == "PASS":
            self._count_ok += 1
            self._update_result_display("ok")
        else:
            self._count_nok += 1
            self._update_result_display("nok")

        self._update_counters()
        self._fmax_label.setText(f"{self._cycle_fmax:.0f} N")
        self._xmax_label.setText(f"{self._cycle_xmax:.1f} mm")

        now = datetime.now().strftime("%H:%M:%S")
        cycle_num = self._count_ok + self._count_nok
        self._production_log.append(
            (cycle_num, self._cycle_fmax, self._cycle_xmax, result, now)
        )
        self._add_production_row(cycle_num, self._cycle_fmax, self._cycle_xmax, result, now)
        self._graph.finish_cycle(result)

    def on_cycle_started(self) -> None:
        """Appelé quand un nouveau cycle commence."""
        self._cycle_started = False
        self._cycle_fmax = 0.0
        self._cycle_xmax = 0.0
        self._last_force = 0.0
        self._last_pos = 0.0
        self._graph.start_new_cycle()
        self._update_result_display("idle")

    # ------------------------------------------------------------------
    # Timer 30 FPS
    # ------------------------------------------------------------------

    def _flush_buffer(self) -> None:
        if self._point_buffer:
            self._graph.add_points(self._point_buffer)
            self._point_buffer.clear()
            self._update_live_values(self._last_force, self._last_pos)

    def _update_live_values(self, force_n: float, pos_mm: float) -> None:
        self._force_value.setText(f"{force_n:.0f} N")
        self._force_bar.setValue(int(min(force_n, FORCE_NEWTON_MAX)))
        alarm_f = "true" if force_n >= FORCE_THRESHOLD_N else "false"
        if self._force_bar.property("alarm") != alarm_f:
            self._force_bar.setProperty("alarm", alarm_f)
            self._force_bar.style().unpolish(self._force_bar)
            self._force_bar.style().polish(self._force_bar)

        self._pos_value.setText(f"{pos_mm:.1f} mm")
        self._pos_bar.setValue(int(min(pos_mm, POSITION_MM_MAX)))
        alarm_p = "true" if pos_mm >= POSITION_THRESHOLD_MM else "false"
        if self._pos_bar.property("alarm") != alarm_p:
            self._pos_bar.setProperty("alarm", alarm_p)
            self._pos_bar.style().unpolish(self._pos_bar)
            self._pos_bar.style().polish(self._pos_bar)

        self._fmax_label.setText(f"{self._cycle_fmax:.0f} N")
        self._xmax_label.setText(f"{self._cycle_xmax:.1f} mm")

    # ------------------------------------------------------------------
    # Actions barre de navigation
    # ------------------------------------------------------------------

    def _show_current_curve(self) -> None:
        self._graph.set_history_mode(False)
        self._content_stack.setCurrentIndex(0)

    def _show_history(self) -> None:
        self._graph.set_history_mode(True)
        self._content_stack.setCurrentIndex(0)

    def _show_data_table(self) -> None:
        self._content_stack.setCurrentIndex(1)

    def _export_csv(self) -> None:
        if not self._production_log:
            QMessageBox.information(self, "Export", "Aucune donnée à exporter.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Exporter les données de production",
            f"production_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "CSV (*.csv)",
        )
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Cycle", "Fmax_N", "Xmax_mm", "Resultat", "Heure"])
            writer.writerows(self._production_log)
        QMessageBox.information(self, "Export", f"Données exportées :\n{path}")

    def _update_counters(self) -> None:
        total = self._count_ok + self._count_nok
        self._ok_count_label.setText(f"✓  {self._count_ok}")
        self._nok_count_label.setText(f"✗  {self._count_nok}")
        self._total_count_label.setText(f"Σ  {total}")

    def _update_datetime(self) -> None:
        self._datetime_label.setText(datetime.now().strftime("%d/%m/%y   %H:%M:%S"))

    def _reset_counters(self) -> None:
        reply = QMessageBox.question(
            self,
            "RAZ compteurs",
            "Remettre les compteurs OK/NOK à zéro ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._count_ok = 0
            self._count_nok = 0
            self._update_counters()

    def _on_pm_clicked(self) -> None:
        """Ouvre un sélecteur de PM (liste des PM disponibles)."""
        QMessageBox.information(self, "Sélection PM", "Sélection du programme — À implémenter.")

    def _on_settings_clicked(self) -> None:
        """Vérifie le PIN puis navigue vers la page Réglages."""
        dlg = PinDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.stack.setCurrentIndex(1)

    # ------------------------------------------------------------------
    # Table de production
    # ------------------------------------------------------------------

    def _add_production_row(
        self, cycle: int, fmax: float, xmax: float, result: str, hour: str
    ) -> None:
        row = self._data_table.rowCount()
        self._data_table.insertRow(row)
        for col, text in enumerate([str(cycle), f"{fmax:.0f}", f"{xmax:.1f}", result, hour]):
            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if col == 3:
                item.setForeground(
                    QColor(COLORS["curve_ok"] if result == "PASS" else COLORS["curve_nok"])
                )
            self._data_table.setItem(row, col, item)
        self._data_table.scrollToBottom()
