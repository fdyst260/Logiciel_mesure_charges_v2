"""Fenêtre principale IHM riveteuse — 1280×720 paysage tactile.

Architecture Qt :
  MainWindow
  ├── Widget central
  │   ├── Zone gauche+centre (graphique | panneau central | barre nav)
  │   └── Panneau droit PM / réglages (pleine hauteur)
  └── Slots : on_new_point(), on_cycle_finished(), on_cycle_started()

Points reçus accumulés dans un buffer ; timer 30 FPS vide le buffer et redessine.
"""

from __future__ import annotations

import collections
import csv
from datetime import datetime

from PySide6.QtCore import Qt, QRect, QTimer, Slot
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QKeySequence, QShortcut
from PySide6.QtWidgets import (
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
# Constantes de couleur — thème industriel clair/sombre
# ---------------------------------------------------------------------------
COLORS: dict[str, str] = {
    # Arrière-plan fenêtre selon état
    "bg_idle":        "#e8ecf0",
    "bg_acquiring":   "#dce6f0",
    "bg_ok":          "#d4eddf",
    "bg_nok":         "#f5d5d5",
    # Graphique (fond clair moderne)
    "bg_graph":       "#f0f4f8",
    "graph_title_bg": "#4a90d9",
    "graph_title_fg": "#ffffff",
    "grid":           "#c8d4e0",
    "axis_text":      "#556677",
    "curve_live":     "#2e7d32",
    "curve_ok":       "#2e7d32",
    "curve_nok":      "#d32f2f",
    "curve_history":  "#90a4ae",
    # Outils d'évaluation
    "tool_no_pass":   "#d32f2f",
    "tool_unibox":    "#2e7d32",
    "tool_envelope":  "#1565c0",
    # Badges résultat
    "result_ok":      "#2e7d32",
    "result_nok":     "#d32f2f",
    "result_idle":    "#78909c",
    # UI générale
    "text_primary":   "#263238",
    "text_secondary": "#607d8b",
    "btn_nav":        "#eceff1",
    "btn_settings":   "#5c6bc0",
    "panel_bg":       "#f5f7fa",
    "separator":      "#cfd8dc",
    "progress_ok":    "#2e7d32",
    "progress_warn":  "#d32f2f",
}

_PIN_CODE = "1234"
_MAX_PIN_ATTEMPTS = 3
_LOCKOUT_SECONDS = 30

# ---------------------------------------------------------------------------
# Feuille de style globale QSS
# ---------------------------------------------------------------------------
STYLESHEET = """
QMainWindow, QWidget#central {
    background-color: #e8ecf0;
    color: #263238;
    font-family: 'Segoe UI', Arial, sans-serif;
}

QLabel#result_label {
    font-size: 36px;
    font-weight: bold;
    border-radius: 8px;
    padding: 10px;
}

QLabel#counter_row {
    font-size: 18px;
    font-weight: bold;
    padding: 2px 8px;
    background-color: #ffffff;
    border: 1px solid #cfd8dc;
}

QLabel#datetime_label {
    font-size: 13px;
    color: #455a64;
    padding: 4px 8px;
    background-color: #ffffff;
    border: 1px solid #cfd8dc;
    border-radius: 4px;
}

QLabel#live_label {
    font-size: 13px;
    color: #607d8b;
    margin-top: 8px;
}
QLabel#live_value {
    font-size: 22px;
    font-weight: bold;
    color: #263238;
}

QProgressBar {
    border: none;
    border-radius: 4px;
    background-color: #cfd8dc;
    max-height: 10px;
}
QProgressBar::chunk {
    border-radius: 4px;
    background-color: #2e7d32;
}
QProgressBar[alarm="true"]::chunk {
    background-color: #d32f2f;
}

QLabel#pm_title {
    font-size: 15px;
    font-weight: bold;
    color: #ffffff;
    padding: 6px;
    background-color: #5c6bc0;
    border-radius: 6px;
}
QLabel#pm_peak {
    font-size: 13px;
    color: #607d8b;
}
QLabel#pm_peak_value {
    font-size: 20px;
    font-weight: bold;
    color: #1565c0;
}

QPushButton#btn_settings {
    background-color: #5c6bc0;
    color: #ffffff;
    font-size: 14px;
    font-weight: bold;
    border-radius: 8px;
    padding: 10px;
    min-height: 48px;
    border: none;
}
QPushButton#btn_settings:pressed {
    background-color: #3949ab;
}

QPushButton#btn_service {
    background-color: #78909c;
    color: #ffffff;
    font-size: 14px;
    font-weight: bold;
    border-radius: 8px;
    padding: 10px;
    min-height: 48px;
    border: none;
}
QPushButton#btn_service:pressed {
    background-color: #546e7a;
}

QPushButton#nav_btn {
    background-color: #eceff1;
    color: #455a64;
    font-size: 13px;
    border-radius: 6px;
    border: 1px solid #b0bec5;
    min-height: 52px;
    padding: 0 12px;
}
QPushButton#nav_btn:checked, QPushButton#nav_btn:pressed {
    background-color: #4a90d9;
    color: #ffffff;
    border-color: #3578c4;
}
QPushButton#nav_btn_green {
    background-color: #e8f5e9;
    color: #2e7d32;
    font-size: 13px;
    border-radius: 6px;
    border: 1px solid #a5d6a7;
    min-height: 52px;
    padding: 0 12px;
}
QPushButton#nav_btn_red {
    background-color: #ffebee;
    color: #c62828;
    font-size: 13px;
    border-radius: 6px;
    border: 1px solid #ef9a9a;
    min-height: 52px;
    padding: 0 12px;
}

QFrame#separator {
    background-color: #cfd8dc;
    max-height: 1px;
}
"""

# ---------------------------------------------------------------------------
# Style du dialogue PIN
# ---------------------------------------------------------------------------
PINSTYLE = """
QDialog {
    background-color: #f5f7fa;
    border-radius: 12px;
}
QLabel {
    color: #263238;
    font-size: 16px;
}
QLineEdit {
    background-color: #ffffff;
    color: #263238;
    border: 2px solid #b0bec5;
    border-radius: 8px;
    font-size: 28px;
    padding: 8px;
    letter-spacing: 12px;
}
QLineEdit:focus {
    border-color: #4a90d9;
}
QPushButton {
    background-color: #4a90d9;
    color: white;
    border-radius: 8px;
    padding: 10px 24px;
    font-size: 14px;
    font-weight: bold;
}
QPushButton:pressed { background-color: #3578c4; }
"""


# ===========================================================================
# GraphWidget — tracé temps réel QPainter (sans matplotlib)
# ===========================================================================

class GraphWidget(QWidget):
    """Tracé temps réel de la courbe Force=f(Position) ou f(t) par QPainter."""

    _GRID_DIVS = 5
    _TITLE_HEIGHT = 32

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(400, 300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Points du cycle courant
        self._current_points: list[tuple[float, float, float]] = []
        # Historique (points, résultat "PASS"/"NOK")
        self._history: collections.deque[tuple[list, str]] = collections.deque(maxlen=20)

        self._display_mode: DisplayMode = DisplayMode.FORCE_POSITION
        self._history_mode: bool = False
        self._tools: list[EvaluationTool] = []
        self._current_result: str | None = None  # résultat cycle terminé
        self._title: str = "Production: Courbe actuelle"

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    def set_tools(self, tools: list[EvaluationTool]) -> None:
        self._tools = tools
        self.update()

    def set_display_mode(self, mode: DisplayMode) -> None:
        self._display_mode = mode
        self._current_points.clear()
        self.update()

    def set_history_mode(self, enabled: bool) -> None:
        self._history_mode = enabled
        self._title = "Production: Historique" if enabled else "Production: Courbe actuelle"
        self.update()

    def add_points(self, points: list[tuple[float, float, float]]) -> None:
        """Ajoute les points vidés du buffer (appelé par le timer 30 fps)."""
        self._current_points.extend(points)
        self.update()

    def finish_cycle(self, result: str) -> None:
        """Clôture le cycle courant et le verse dans l'historique."""
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
    # Géométrie — marges : gauche 50px, haut 10px, droite 10px, bas 30px
    # ------------------------------------------------------------------

    def _plot_rect(self) -> QRect:
        """Rectangle de tracé (hors marges axes et barre titre)."""
        top = self._TITLE_HEIGHT + 10
        return QRect(55, top, self.width() - 70, self.height() - top - 35)

    def _get_ranges(self) -> tuple[float, float]:
        """Retourne (x_max, y_max) selon le mode."""
        if self._display_mode == DisplayMode.FORCE_POSITION:
            return POSITION_MM_MAX, FORCE_NEWTON_MAX
        if self._display_mode == DisplayMode.FORCE_TIME:
            return 2.0, FORCE_NEWTON_MAX
        return 2.0, POSITION_MM_MAX  # POSITION_TIME

    def _pt_to_data(self, t: float, force_n: float, pos_mm: float) -> tuple[float, float]:
        """Extrait (x_data, y_data) selon le mode d'affichage."""
        if self._display_mode == DisplayMode.FORCE_POSITION:
            return pos_mm, force_n
        if self._display_mode == DisplayMode.FORCE_TIME:
            return t, force_n
        return t, pos_mm  # POSITION_TIME

    def _to_px(self, x_data: float, y_data: float, rect: QRect) -> tuple[int, int]:
        x_range, y_range = self._get_ranges()
        px = rect.left() + x_data / x_range * rect.width()
        py = rect.bottom() - y_data / y_range * rect.height()
        return int(px), int(py)

    # ------------------------------------------------------------------
    # paintEvent
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()

        # Fond graphique clair
        painter.fillRect(self.rect(), QColor(COLORS["bg_graph"]))

        # Bordure arrondie
        border_pen = QPen(QColor("#b0bec5"))
        border_pen.setWidth(1)
        painter.setPen(border_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 8, 8)

        # Barre de titre
        title_rect = QRect(1, 1, w - 2, self._TITLE_HEIGHT)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(COLORS["graph_title_bg"]))
        painter.drawRoundedRect(QRect(1, 1, w - 2, self._TITLE_HEIGHT + 8), 8, 8)
        painter.fillRect(QRect(1, self._TITLE_HEIGHT - 4, w - 2, 12), QColor(COLORS["graph_title_bg"]))

        painter.setPen(QColor(COLORS["graph_title_fg"]))
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, self._title)

        rect = self._plot_rect()

        # Fond zone de tracé blanc
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#ffffff"))
        painter.drawRect(rect)

        self._draw_grid(painter, rect)
        self._draw_tool_overlays(painter, rect)

        if self._history_mode:
            history_list = list(self._history)
            for pts, _res in history_list[:-1]:
                self._draw_curve(painter, pts, QColor(COLORS["curve_history"]), rect)
            if history_list:
                pts, res = history_list[-1]
                c = COLORS["curve_ok"] if res == "PASS" else COLORS["curve_nok"]
                self._draw_curve(painter, pts, QColor(c), rect)
        else:
            if self._current_points:
                if self._current_result == "PASS":
                    color = QColor(COLORS["curve_ok"])
                elif self._current_result == "NOK":
                    color = QColor(COLORS["curve_nok"])
                else:
                    color = QColor(COLORS["curve_live"])
                self._draw_curve(painter, self._current_points, color, rect)

        self._draw_axes(painter, rect)
        painter.end()

    def _draw_grid(self, painter: QPainter, rect: QRect) -> None:
        pen = QPen(QColor(COLORS["grid"]))
        pen.setWidth(1)
        pen.setStyle(Qt.PenStyle.DotLine)
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
        pen.setWidthF(2.5)  # épaisseur légèrement plus visible
        painter.setPen(pen)
        prev: tuple[int, int] | None = None
        for t, force_n, pos_mm in points:
            xd, yd = self._pt_to_data(t, force_n, pos_mm)
            px, py = self._to_px(xd, yd, rect)
            if prev is not None:
                painter.drawLine(prev[0], prev[1], px, py)
            prev = (px, py)

    def _draw_tool_overlays(self, painter: QPainter, rect: QRect) -> None:
        """Superpose les outils (uniquement en mode FORCE_POSITION)."""
        if self._display_mode != DisplayMode.FORCE_POSITION:
            return
        for tool in self._tools:
            if tool.tool_type == EvaluationType.NO_PASS:
                self._draw_no_pass(painter, tool, rect)
            elif tool.tool_type == EvaluationType.UNI_BOX:
                self._draw_unibox(painter, tool, rect)
            elif tool.tool_type == EvaluationType.ENVELOPE:
                self._draw_envelope(painter, tool, rect)

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
        x_range, y_range = self._get_ranges()
        x_unit = "mm" if self._display_mode == DisplayMode.FORCE_POSITION else "s"
        y_unit = "mm" if self._display_mode == DisplayMode.POSITION_TIME else "N"

        # Axes lines
        axis_pen = QPen(QColor("#78909c"))
        axis_pen.setWidth(2)
        painter.setPen(axis_pen)
        painter.drawLine(rect.left(), rect.top(), rect.left(), rect.bottom())
        painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())

        # Labels
        painter.setPen(QColor(COLORS["axis_text"]))
        painter.setFont(QFont("Segoe UI", 10))

        for i in range(self._GRID_DIVS + 1):
            val_x = i * x_range / self._GRID_DIVS
            px = rect.left() + int(i * rect.width() / self._GRID_DIVS)
            painter.drawText(px - 12, rect.bottom() + 18, f"{val_x:.0f}")

            val_y = i * y_range / self._GRID_DIVS
            py = rect.bottom() - int(i * rect.height() / self._GRID_DIVS)
            label = f"{val_y:.0f}{y_unit}" if i == self._GRID_DIVS else f"{val_y:.0f}"
            painter.drawText(2, py + 4, label)

        # Unit label on X axis
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        painter.drawText(rect.right() - 20, rect.bottom() + 18, x_unit)


# ===========================================================================
# PinDialog — saisie PIN avec verrouillage après 3 échecs
# ===========================================================================

class PinDialog(QDialog):
    """Dialogue de saisie PIN (4 chiffres) pour accéder aux réglages."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Accès réglages")
        self.setModal(True)
        self.setFixedSize(360, 240)
        self.setStyleSheet(PINSTYLE)

        self._attempts = 0
        self._locked = False
        self._lockout_remaining = _LOCKOUT_SECONDS

        self._lockout_timer = QTimer(self)
        self._lockout_timer.setInterval(1000)
        self._lockout_timer.timeout.connect(self._on_lockout_tick)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

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
                self._error_label.setText(f"PIN incorrect — {remaining} tentative(s) restante(s).")
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
    """Fenêtre principale IHM riveteuse (1280×720, paysage, tactile)."""

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

        # Compteurs de cycles
        self._count_ok = 0
        self._count_nok = 0

        # Buffer de points reçus entre deux rafraîchissements (30 fps)
        self._point_buffer: list[tuple[float, float, float]] = []
        self._last_force: float = 0.0
        self._last_pos: float = 0.0

        # Valeurs peak du cycle courant
        self._cycle_fmax: float = 0.0
        self._cycle_xmax: float = 0.0

        # Historique de production (cycle#, fmax, xmax, résultat, heure)
        self._production_log: list[tuple[int, float, float, str, str]] = []

        # Feuille de style globale (appliquée une fois, jamais écrasée)
        self.setStyleSheet(STYLESHEET)

        self._build_ui()
        self._apply_state_style("idle")

        # Timer de rafraîchissement graphique : ~30 FPS
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(33)
        self._refresh_timer.timeout.connect(self._flush_buffer)
        self._refresh_timer.start()

        # Raccourci Échap → quitter (développement)
        shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        shortcut.activated.connect(self.close)

        if fullscreen:
            # setFixedSize + showMaximized : compatible X11/VNC
            self.setFixedSize(1280, 720)
            self.showMaximized()
        else:
            self.resize(1280, 720)
            self.show()

    # ------------------------------------------------------------------
    # Construction de l'interface
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)

        # Disposition principale : zone gauche+centre | panneau droit fixe 240px
        main_h = QHBoxLayout(central)
        main_h.setSpacing(0)
        main_h.setContentsMargins(0, 0, 0, 0)

        # ------ Colonne gauche + centre (graphique 780px + statut 260px + nav 70px) ------
        left_center = QWidget()
        lc_v = QVBoxLayout(left_center)
        lc_v.setSpacing(0)
        lc_v.setContentsMargins(0, 0, 0, 0)

        # Ligne principale : graphique | panneau central
        content_row = QWidget()
        content_h = QHBoxLayout(content_row)
        content_h.setSpacing(0)
        content_h.setContentsMargins(0, 0, 0, 0)

        # Graphique (QStackedWidget pour alterner avec la table données)
        self._stack = QStackedWidget()
        self._graph = GraphWidget()
        self._graph.set_tools(self._tools)
        self._data_table = self._build_data_table()
        self._stack.addWidget(self._graph)       # index 0 : courbe
        self._stack.addWidget(self._data_table)  # index 1 : données production
        content_h.addWidget(self._stack, stretch=1)  # prend l'espace restant (~780px)

        # Panneau central : largeur fixe 260px
        center = self._build_center_panel()
        center.setFixedWidth(260)
        content_h.addWidget(center)

        lc_v.addWidget(content_row, stretch=1)
        lc_v.addWidget(self._build_nav_bar())

        main_h.addWidget(left_center, stretch=1)

        # ------ Panneau droit PM + réglages : largeur fixe 240px ------
        right = self._build_right_panel()
        right.setFixedWidth(240)
        main_h.addWidget(right)

    def _build_center_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(f"background-color: {COLORS['panel_bg']}; border-left: 1px solid {COLORS['separator']};")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        # Force live
        lbl_force = QLabel("Force")
        lbl_force.setObjectName("live_label")
        layout.addWidget(lbl_force)

        self._force_value = QLabel("0 N")
        self._force_value.setObjectName("live_value")
        self._force_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._force_value)

        self._force_bar = QProgressBar()
        self._force_bar.setRange(0, int(FORCE_NEWTON_MAX))
        self._force_bar.setValue(0)
        self._force_bar.setTextVisible(False)
        self._force_bar.setProperty("alarm", "false")
        layout.addWidget(self._force_bar)

        layout.addWidget(self._make_separator())

        # Position live
        lbl_pos = QLabel("Position")
        lbl_pos.setObjectName("live_label")
        layout.addWidget(lbl_pos)

        self._pos_value = QLabel("0.0 mm")
        self._pos_value.setObjectName("live_value")
        self._pos_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._pos_value)

        self._pos_bar = QProgressBar()
        self._pos_bar.setRange(0, int(POSITION_MM_MAX))
        self._pos_bar.setValue(0)
        self._pos_bar.setTextVisible(False)
        self._pos_bar.setProperty("alarm", "false")
        layout.addWidget(self._pos_bar)

        layout.addStretch()
        return panel

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(
            f"background-color: {COLORS['panel_bg']}; "
            f"border-left: 1px solid {COLORS['separator']};"
        )
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        # Badge résultat OK/NOK — gros et visible comme sur la photo
        self._result_badge = QLabel("EN ATTENTE")
        self._result_badge.setObjectName("result_label")
        self._result_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._result_badge.setFixedHeight(70)
        self._result_badge.setWordWrap(True)
        self._result_badge.setStyleSheet(
            f"background-color: {COLORS['result_idle']}; color: #ffffff; "
            "border-radius: 8px; font-size: 32px; font-weight: bold;"
        )
        layout.addWidget(self._result_badge)

        # Compteurs (✓ / ✗ / Σ) en tableau structuré
        counters_frame = QWidget()
        counters_frame.setStyleSheet(
            "background-color: #ffffff; border: 1px solid #cfd8dc; border-radius: 6px;"
        )
        cl = QVBoxLayout(counters_frame)
        cl.setContentsMargins(8, 4, 8, 4)
        cl.setSpacing(0)

        self._ok_count_label = QLabel("✓          0")
        self._ok_count_label.setObjectName("counter_row")
        self._ok_count_label.setStyleSheet("color: #2e7d32; font-size: 18px; font-weight: bold; border: none;")
        cl.addWidget(self._ok_count_label)

        self._nok_count_label = QLabel("✗          0")
        self._nok_count_label.setObjectName("counter_row")
        self._nok_count_label.setStyleSheet("color: #d32f2f; font-size: 18px; font-weight: bold; border: none;")
        cl.addWidget(self._nok_count_label)

        self._total_count_label = QLabel("Σ          0")
        self._total_count_label.setObjectName("counter_row")
        self._total_count_label.setStyleSheet("color: #263238; font-size: 18px; font-weight: bold; border: none;")
        cl.addWidget(self._total_count_label)

        layout.addWidget(counters_frame)

        # Date / Heure
        self._datetime_label = QLabel(datetime.now().strftime("%d/%m/%y\n%H:%M:%S"))
        self._datetime_label.setObjectName("datetime_label")
        self._datetime_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._datetime_label)

        # Timer pour mettre à jour la date/heure
        self._dt_timer = QTimer(self)
        self._dt_timer.setInterval(1000)
        self._dt_timer.timeout.connect(self._update_datetime)
        self._dt_timer.start()

        layout.addWidget(self._make_separator())

        # PM actif
        pm = PM_DEFINITIONS.get(self._pm_id)
        pm_text = f"PM-{self._pm_id:02d}"
        pm_label = QLabel(pm_text)
        pm_label.setObjectName("pm_title")
        pm_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(pm_label)

        layout.addWidget(self._make_separator())

        # Fmax / Xmax en ligne compacte
        peaks_frame = QWidget()
        peaks_frame.setStyleSheet(
            "background-color: #ffffff; border: 1px solid #cfd8dc; border-radius: 6px;"
        )
        pl = QVBoxLayout(peaks_frame)
        pl.setContentsMargins(8, 4, 8, 4)
        pl.setSpacing(2)

        fmax_row = QHBoxLayout()
        lbl_fmax = QLabel("Fmax")
        lbl_fmax.setObjectName("pm_peak")
        self._fmax_label = QLabel("0 N")
        self._fmax_label.setObjectName("pm_peak_value")
        self._fmax_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        fmax_row.addWidget(lbl_fmax)
        fmax_row.addWidget(self._fmax_label)
        pl.addLayout(fmax_row)

        xmax_row = QHBoxLayout()
        lbl_xmax = QLabel("Xmax")
        lbl_xmax.setObjectName("pm_peak")
        self._xmax_label = QLabel("0.0 mm")
        self._xmax_label.setObjectName("pm_peak_value")
        self._xmax_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        xmax_row.addWidget(lbl_xmax)
        xmax_row.addWidget(self._xmax_label)
        pl.addLayout(xmax_row)

        layout.addWidget(peaks_frame)

        layout.addStretch()

        # Bouton Réglages
        self._settings_btn = QPushButton("Réglage")
        self._settings_btn.setObjectName("btn_settings")
        self._settings_btn.clicked.connect(self._on_settings_clicked)
        layout.addWidget(self._settings_btn)

        # Bouton Service
        service_btn = QPushButton("Service")
        service_btn.setObjectName("btn_service")
        service_btn.clicked.connect(lambda: QMessageBox.information(self, "Service", "Mode service non disponible."))
        layout.addWidget(service_btn)

        return panel

    def _build_nav_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(70)
        bar.setStyleSheet(
            f"background-color: {COLORS['panel_bg']}; "
            f"border-top: 1px solid {COLORS['separator']};"
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 9, 8, 9)
        layout.setSpacing(6)

        # Groupe exclusif pour les boutons de vue
        btn_group = QButtonGroup(bar)
        btn_group.setExclusive(True)

        btn_specs = [
            ("📈  Courbe",        "nav_btn",       self._show_current_curve, True),
            ("🕐  Historique",    "nav_btn",        self._show_history,       False),
            ("📊  Données",       "nav_btn",        self._show_data_table,    False),
            ("💾  Export CSV",    "nav_btn_green",  self._export_csv,         False),
            ("🔄  RAZ compteurs", "nav_btn_red",    self._reset_counters,     False),
        ]

        for label, obj_name, callback, checked in btn_specs:
            btn = QPushButton(label)
            btn.setObjectName(obj_name)
            btn.setMinimumHeight(52)
            btn.clicked.connect(callback)
            # Les 3 premiers boutons sont checkables (sélection de vue)
            if obj_name == "nav_btn":
                btn.setCheckable(True)
                btn.setChecked(checked)
                btn_group.addButton(btn)
            layout.addWidget(btn, stretch=1)

        return bar

    def _build_data_table(self) -> QTableWidget:
        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels(["Cycle", "Fmax (N)", "Xmax (mm)", "Résultat", "Heure"])
        table.setStyleSheet(
            "background-color: #ffffff; color: #263238; "
            "gridline-color: #cfd8dc; alternate-background-color: #f5f7fa;"
        )
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setDefaultSectionSize(130)
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

    # ------------------------------------------------------------------
    # Fond de fenêtre dynamique selon état du cycle
    # ------------------------------------------------------------------

    def _apply_state_style(self, state: str) -> None:
        """Change la couleur de fond selon l'état — sans écraser le STYLESHEET global."""
        color_map = {
            "idle":      "#e8ecf0",
            "acquiring": "#dce6f0",
            "ok":        "#d4eddf",
            "nok":       "#f5d5d5",
        }
        bg = color_map.get(state, "#1a1a1a")
        # On cible uniquement le widget central pour ne pas écraser STYLESHEET
        self.centralWidget().setStyleSheet(f"background-color: {bg};")

    # ------------------------------------------------------------------
    # Slots de données
    # ------------------------------------------------------------------

    @Slot(float, float, float)
    def on_new_point(self, t: float, force_n: float, pos_mm: float) -> None:
        """Reçoit un point et l'accumule dans le buffer — ne redessine pas."""
        self._point_buffer.append((t, force_n, pos_mm))
        # Mémorisation pour mise à jour live à 30 FPS
        self._last_force = force_n
        self._last_pos = pos_mm
        # Peak
        if force_n > self._cycle_fmax:
            self._cycle_fmax = force_n
        if pos_mm > self._cycle_xmax:
            self._cycle_xmax = pos_mm

    @Slot(str)
    def on_cycle_finished(self, result: str) -> None:
        """Reçoit le résultat final du cycle (PASS ou NOK)."""
        if result == "PASS":
            self._count_ok += 1
            self._result_badge.setText("OK")
            self._result_badge.setStyleSheet(
                f"background-color: {COLORS['result_ok']}; color: white; "
                "border-radius: 8px; font-size: 32px; font-weight: bold;"
            )
            self._apply_state_style("ok")
        else:
            self._count_nok += 1
            self._result_badge.setText("NOK")
            self._result_badge.setStyleSheet(
                f"background-color: {COLORS['result_nok']}; color: white; "
                "border-radius: 8px; font-size: 32px; font-weight: bold;"
            )
            self._apply_state_style("nok")

        self._update_counters()
        self._fmax_label.setText(f"{self._cycle_fmax:.0f} N")
        self._xmax_label.setText(f"{self._cycle_xmax:.1f} mm")

        # Enregistrement dans la table production
        now = datetime.now().strftime("%H:%M:%S")
        cycle_num = self._count_ok + self._count_nok
        self._production_log.append(
            (cycle_num, self._cycle_fmax, self._cycle_xmax, result, now)
        )
        self._add_production_row(cycle_num, self._cycle_fmax, self._cycle_xmax, result, now)
        self._graph.finish_cycle(result)

    def on_cycle_started(self) -> None:
        """Appelé quand un nouveau cycle commence."""
        self._cycle_fmax = 0.0
        self._cycle_xmax = 0.0
        self._last_force = 0.0
        self._last_pos = 0.0
        self._graph.start_new_cycle()
        self._result_badge.setText("...")
        self._result_badge.setStyleSheet(
            f"background-color: {COLORS['result_idle']}; color: #ffffff; "
            "border-radius: 8px; font-size: 28px; font-weight: bold;"
        )
        self._apply_state_style("acquiring")

    # ------------------------------------------------------------------
    # Timer 30 FPS : flush buffer + mise à jour labels live
    # ------------------------------------------------------------------

    def _flush_buffer(self) -> None:
        if self._point_buffer:
            self._graph.add_points(self._point_buffer)
            self._point_buffer.clear()
            self._update_live_values(self._last_force, self._last_pos)

    def _update_live_values(self, force_n: float, pos_mm: float) -> None:
        self._force_value.setText(f"{force_n:.0f} N")
        self._force_bar.setValue(int(min(force_n, FORCE_NEWTON_MAX)))
        # Alarme force : setProperty + unpolish/polish pour forcer le rechargement CSS
        alarm_f = "true" if force_n >= FORCE_THRESHOLD_N else "false"
        if self._force_bar.property("alarm") != alarm_f:
            self._force_bar.setProperty("alarm", alarm_f)
            self._force_bar.style().unpolish(self._force_bar)
            self._force_bar.style().polish(self._force_bar)

        self._pos_value.setText(f"{pos_mm:.1f} mm")
        self._pos_bar.setValue(int(min(pos_mm, POSITION_MM_MAX)))
        # Alarme position
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
        self._stack.setCurrentIndex(0)

    def _show_history(self) -> None:
        self._graph.set_history_mode(True)
        self._stack.setCurrentIndex(0)

    def _show_data_table(self) -> None:
        self._stack.setCurrentIndex(1)

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
        self._ok_count_label.setText(f"✓          {self._count_ok}")
        self._nok_count_label.setText(f"✗          {self._count_nok}")
        self._total_count_label.setText(f"Σ          {total}")

    def _update_datetime(self) -> None:
        self._datetime_label.setText(datetime.now().strftime("%d/%m/%y\n%H:%M:%S"))

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

    def _on_settings_clicked(self) -> None:
        dlg = PinDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            from ihm.settings_dialog import SettingsDialog
            SettingsDialog(self).exec()

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
