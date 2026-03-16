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
# Constantes de couleur — thème industriel sombre
# ---------------------------------------------------------------------------
COLORS: dict[str, str] = {
    # Arrière-plan fenêtre selon état
    "bg_idle":        "#1a1a1a",
    "bg_acquiring":   "#0a1628",
    "bg_ok":          "#051a12",
    "bg_nok":         "#1a0505",
    # Graphique
    "bg_graph":       "#111111",
    "grid":           "#2a2a2a",
    "axis_text":      "#666666",
    "curve_live":     "#378ADD",
    "curve_ok":       "#1D9E75",
    "curve_nok":      "#E24B4A",
    "curve_history":  "#5F5E5A",
    # Outils d'évaluation
    "tool_no_pass":   "#A32D2D",
    "tool_unibox":    "#EF9F27",
    "tool_envelope":  "#1D9E75",
    # Badges résultat
    "result_ok":      "#085041",
    "result_nok":     "#791F1F",
    "result_idle":    "#2a2a2a",
    # UI générale
    "text_primary":   "#e0e0e0",
    "text_secondary": "#888888",
    "btn_nav":        "#2a2a2a",
    "btn_settings":   "#854F0B",
    "panel_bg":       "#1a1a1a",
    "separator":      "#333333",
    "progress_ok":    "#1D9E75",
    "progress_warn":  "#E24B4A",
}

_PIN_CODE = "1234"
_MAX_PIN_ATTEMPTS = 3
_LOCKOUT_SECONDS = 30

# ---------------------------------------------------------------------------
# Feuille de style globale QSS
# ---------------------------------------------------------------------------
STYLESHEET = """
QMainWindow, QWidget#central {
    background-color: #1a1a1a;
    color: #e0e0e0;
    font-family: 'Segoe UI', Arial, sans-serif;
}

QLabel#result_label {
    font-size: 48px;
    font-weight: bold;
    border-radius: 12px;
    padding: 10px;
}

QLabel#counters_label {
    font-size: 16px;
    color: #b0b0b0;
    padding: 4px 8px;
    border-top: 1px solid #333;
    border-bottom: 1px solid #333;
}

QLabel#live_label {
    font-size: 13px;
    color: #888;
    margin-top: 8px;
}
QLabel#live_value {
    font-size: 22px;
    font-weight: bold;
    color: #e0e0e0;
}

QProgressBar {
    border: none;
    border-radius: 4px;
    background-color: #2a2a2a;
    max-height: 10px;
}
QProgressBar::chunk {
    border-radius: 4px;
    background-color: #1D9E75;
}
QProgressBar[alarm="true"]::chunk {
    background-color: #E24B4A;
}

QLabel#pm_title {
    font-size: 15px;
    font-weight: bold;
    color: #ffffff;
    padding: 6px;
    background-color: #2a2a2a;
    border-radius: 6px;
}
QLabel#pm_peak {
    font-size: 13px;
    color: #888;
}
QLabel#pm_peak_value {
    font-size: 20px;
    font-weight: bold;
    color: #378ADD;
}

QPushButton#btn_settings {
    background-color: #854F0B;
    color: #ffffff;
    font-size: 14px;
    font-weight: bold;
    border-radius: 8px;
    padding: 12px;
    min-height: 55px;
}
QPushButton#btn_settings:pressed {
    background-color: #6B3F09;
}

QPushButton#nav_btn {
    background-color: #2a2a2a;
    color: #cccccc;
    font-size: 13px;
    border-radius: 6px;
    border: 1px solid #3a3a3a;
    min-height: 52px;
    padding: 0 12px;
}
QPushButton#nav_btn:checked, QPushButton#nav_btn:pressed {
    background-color: #185FA5;
    color: #ffffff;
    border-color: #378ADD;
}
QPushButton#nav_btn_green {
    background-color: #085041;
    color: #9FE1CB;
    font-size: 13px;
    border-radius: 6px;
    border: 1px solid #0F6E56;
    min-height: 52px;
    padding: 0 12px;
}
QPushButton#nav_btn_red {
    background-color: #3d1515;
    color: #F7C1C1;
    font-size: 13px;
    border-radius: 6px;
    border: 1px solid #791F1F;
    min-height: 52px;
    padding: 0 12px;
}

QFrame#separator {
    background-color: #333;
    max-height: 1px;
}
"""

# ---------------------------------------------------------------------------
# Style du dialogue PIN
# ---------------------------------------------------------------------------
PINSTYLE = """
QDialog {
    background-color: #1e1e1e;
    border-radius: 12px;
}
QLabel {
    color: #e0e0e0;
    font-size: 16px;
}
QLineEdit {
    background-color: #2a2a2a;
    color: #ffffff;
    border: 2px solid #444;
    border-radius: 8px;
    font-size: 28px;
    padding: 8px;
    letter-spacing: 12px;
}
QLineEdit:focus {
    border-color: #378ADD;
}
QPushButton {
    background-color: #378ADD;
    color: white;
    border-radius: 8px;
    padding: 10px 24px;
    font-size: 14px;
    font-weight: bold;
}
QPushButton:pressed { background-color: #185FA5; }
"""


# ===========================================================================
# GraphWidget — tracé temps réel QPainter (sans matplotlib)
# ===========================================================================

class GraphWidget(QWidget):
    """Tracé temps réel de la courbe Force=f(Position) ou f(t) par QPainter."""

    _GRID_DIVS = 5

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
        """Rectangle de tracé (hors marges axes)."""
        return QRect(50, 10, self.width() - 60, self.height() - 40)

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

        # Fond graphique
        painter.fillRect(self.rect(), QColor(COLORS["bg_graph"]))

        # Bordure du widget : 1px #333333, coins arrondis 8px
        border_pen = QPen(QColor("#333333"))
        border_pen.setWidth(1)
        painter.setPen(border_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 8, 8)

        rect = self._plot_rect()
        self._draw_grid(painter, rect)
        self._draw_tool_overlays(painter, rect)

        if self._history_mode:
            # Toutes les courbes sauf la dernière en gris
            history_list = list(self._history)
            for pts, _res in history_list[:-1]:
                self._draw_curve(painter, pts, QColor(COLORS["curve_history"]), rect)
            # Dernière courbe en couleur
            if history_list:
                pts, res = history_list[-1]
                c = COLORS["curve_ok"] if res == "PASS" else COLORS["curve_nok"]
                self._draw_curve(painter, pts, QColor(c), rect)
        else:
            # Courbe courante
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
        pen = QPen(QColor(COLORS["grid"]))  # #2a2a2a — grille subtile
        pen.setWidth(1)
        painter.setPen(pen)
        for i in range(self._GRID_DIVS + 1):
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
        painter.setPen(QColor(COLORS["axis_text"]))  # #666666
        painter.setFont(QFont("monospace", 11))
        x_range, y_range = self._get_ranges()
        x_unit = "mm" if self._display_mode == DisplayMode.FORCE_POSITION else "s"
        y_unit = "mm" if self._display_mode == DisplayMode.POSITION_TIME else "N"

        for i in range(self._GRID_DIVS + 1):
            # Labels X (bas)
            val_x = i * x_range / self._GRID_DIVS
            px = rect.left() + int(i * rect.width() / self._GRID_DIVS)
            painter.drawText(px - 12, rect.bottom() + 20, f"{val_x:.0f}")
            # Labels Y (gauche)
            val_y = i * y_range / self._GRID_DIVS
            py = rect.bottom() - int(i * rect.height() / self._GRID_DIVS)
            painter.drawText(2, py + 4, f"{val_y:.0f}")

        # Unités axes
        painter.drawText(rect.left() + rect.width() // 2 - 8, rect.bottom() + 34, x_unit)
        painter.save()
        painter.translate(10, rect.top() + rect.height() // 2 + 8)
        painter.rotate(-90)
        painter.drawText(0, 0, y_unit)
        painter.restore()


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

        # Badge résultat — 110px de haut, objectName pour le CSS
        self._result_badge = QLabel("EN ATTENTE")
        self._result_badge.setObjectName("result_label")
        self._result_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._result_badge.setFixedHeight(110)
        self._result_badge.setWordWrap(True)
        self._result_badge.setStyleSheet(
            f"background-color: {COLORS['result_idle']}; color: {COLORS['text_primary']}; "
            "border-radius: 12px; font-size: 28px; font-weight: bold;"
        )
        layout.addWidget(self._result_badge)

        # Compteurs ✓ / ✗ / Σ — 45px de haut
        self._counter_label = QLabel("✓ 0   ✗ 0   Σ 0")
        self._counter_label.setObjectName("counters_label")
        self._counter_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._counter_label.setFixedHeight(45)
        layout.addWidget(self._counter_label)

        layout.addWidget(self._make_separator())

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
        layout.setContentsMargins(12, 14, 12, 14)
        layout.setSpacing(8)

        # Nom du PM actif
        pm = PM_DEFINITIONS.get(self._pm_id)
        pm_text = f"PM-{self._pm_id:02d}\n{pm.name if pm else '—'}"
        pm_label = QLabel(pm_text)
        pm_label.setObjectName("pm_title")
        pm_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pm_label.setWordWrap(True)
        layout.addWidget(pm_label)

        layout.addWidget(self._make_separator())

        # Fmax
        lbl_fmax = QLabel("Fmax")
        lbl_fmax.setObjectName("pm_peak")
        lbl_fmax.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_fmax)

        self._fmax_label = QLabel("0 N")
        self._fmax_label.setObjectName("pm_peak_value")
        self._fmax_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._fmax_label)

        layout.addWidget(self._make_separator())

        # Xmax
        lbl_xmax = QLabel("Xmax")
        lbl_xmax.setObjectName("pm_peak")
        lbl_xmax.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_xmax)

        self._xmax_label = QLabel("0.0 mm")
        self._xmax_label.setObjectName("pm_peak_value")
        self._xmax_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._xmax_label)

        layout.addStretch()

        # Bouton réglages (PIN requis)
        self._settings_btn = QPushButton("⚙  RÉGLAGES  🔒")
        self._settings_btn.setObjectName("btn_settings")
        self._settings_btn.setMinimumHeight(55)
        self._settings_btn.clicked.connect(self._on_settings_clicked)
        layout.addWidget(self._settings_btn)

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
            f"background-color: {COLORS['bg_graph']}; color: {COLORS['text_primary']}; "
            f"gridline-color: {COLORS['separator']};"
        )
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
            "idle":      "#1a1a1a",
            "acquiring": "#0a1628",
            "ok":        "#051a12",
            "nok":       "#1a0505",
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
            self._result_badge.setText("OK  ✓")
            self._result_badge.setStyleSheet(
                f"background-color: {COLORS['result_ok']}; color: white; "
                "border-radius: 12px; font-size: 28px; font-weight: bold;"
            )
            self._apply_state_style("ok")
        else:
            self._count_nok += 1
            self._result_badge.setText("NOK  ✗")
            self._result_badge.setStyleSheet(
                f"background-color: {COLORS['result_nok']}; color: white; "
                "border-radius: 12px; font-size: 28px; font-weight: bold;"
            )
            self._apply_state_style("nok")

        self._counter_label.setText(
            f"✓ {self._count_ok}   ✗ {self._count_nok}   Σ {self._count_ok + self._count_nok}"
        )
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
        self._result_badge.setText("EN COURS...")
        self._result_badge.setStyleSheet(
            f"background-color: {COLORS['result_idle']}; color: {COLORS['text_primary']}; "
            "border-radius: 12px; font-size: 22px; font-weight: bold;"
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
            self._counter_label.setText("✓ 0   ✗ 0   Σ 0")

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
