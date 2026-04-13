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
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QPoint, QRect, QTimer, Slot
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygon, QKeySequence, QShortcut, QBrush
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
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
from ihm.translations import set_language, t
from ihm.ui_utils import (
    RIGHT_PANEL_WIDTH,
    load_config,
    make_hseparator,
    make_vseparator,
)

# ---------------------------------------------------------------------------
# Constantes de couleur — thème industriel sombre (maXYmos style)
# ---------------------------------------------------------------------------
COLORS: dict[str, str] = {
    # Fonds
    "bg_main":        "#2E2E2E",
    "bg_panel":       "#3A3A3A",
    "bg_button":      "#444444",
    "bg_graph":       "#2E2E2E",

    # Textes
    "text_primary":   "#F0F0F0",
    "text_secondary": "#AAAAAA",

    # Séparateurs
    "border":         "#555555",
    "separator":      "#555555",
    "grid":           "#3A3A3A",
    "axis_text":      "#888888",

    # Accent ACM Or
    "nav_active":     "#A07830",
    "blue":           "#C49A3C",

    # États machine (IEC 60073 — inchangés)
    "ok_bg":          "#1a3a1a",
    "ok_border":      "#2d7a2d",
    "ok_text":        "#4caf50",
    "nok_bg":         "#3a1a1a",
    "nok_border":     "#c62828",
    "nok_text":       "#ef5350",

    # Running — or ACM au lieu de bleu
    "running_bg":     "#2a2010",
    "running_border": "#C49A3C",

    # Idle
    "idle_bg":        "#2E2E2E",
    "idle_text":      "#AAAAAA",

    # Fond fenêtre dynamique
    "win_idle":       "#2E2E2E",
    "win_running":    "#2a2010",
    "win_ok":         "#1a2a1a",
    "win_nok":        "#2a1a1a",

    # Alarme (jaune ambre IEC 60073 — inchangé)
    "alarm":          "#f57f17",
    "alarm_bg":       "#2a2a1a",

    # Courbes
    "curve_running":  "#C49A3C",
    "curve_ok":       "#4caf50",
    "curve_nok":      "#ef5350",
    "curve_history":  "#777777",
    "curve_live":     "#C49A3C",

    # Outils graphique
    "nopass_fill":    "#c62828",
    "nopass_border":  "#ef5350",
    "unibox_border":  "#C49A3C",
    "envelope_border":"#A07830",
    "envelope_fill":  "#A07830",

    # Boutons navigation
    "settings_btn":   "#A07830",
    "export_btn":     "#1a3a1a",
    "raz_btn":        "#3a1a1a",

    # Résultat
    "result_ok":      "#1a3a1a",
    "result_nok":     "#3a1a1a",
    "result_idle":    "#3A3A3A",

    # Aliases
    "panel_bg":       "#3A3A3A",
    "progress_ok":    "#4caf50",
    "progress_warn":  "#ef5350",

    # Compatibilité outils graphique
    "tool_no_pass":   "#c62828",
    "tool_unibox":    "#C49A3C",
    "tool_envelope":  "#A07830",
}

COLORS_LIGHT: dict[str, str] = {
    # Fonds
    "bg_main":        "#F5F5F5",
    "bg_panel":       "#EEEEEE",
    "bg_button":      "#E0E0E0",
    "bg_graph":       "#FFFFFF",

    # Textes
    "text_primary":   "#212121",
    "text_secondary": "#757575",

    # Séparateurs
    "border":         "#BDBDBD",
    "separator":      "#BDBDBD",
    "grid":           "#E0E0E0",
    "axis_text":      "#9E9E9E",

    # Accent ACM Or — identique aux deux thèmes
    "nav_active":     "#A07830",
    "blue":           "#C49A3C",

    # États machine — inchangés (IEC 60073)
    "ok_bg":          "#E8F5E9",
    "ok_border":      "#2d7a2d",
    "ok_text":        "#2E7D32",
    "nok_bg":         "#FFEBEE",
    "nok_border":     "#c62828",
    "nok_text":       "#C62828",

    # Running — or ACM
    "running_bg":     "#FFF8E1",
    "running_border": "#C49A3C",

    # Idle
    "idle_bg":        "#F5F5F5",
    "idle_text":      "#757575",

    # Fond fenêtre dynamique
    "win_idle":       "#F5F5F5",
    "win_running":    "#FFFDE7",
    "win_ok":         "#F1F8E9",
    "win_nok":        "#FFEBEE",

    # Alarme
    "alarm":          "#E65100",
    "alarm_bg":       "#FFF3E0",

    # Courbes
    "curve_running":  "#C49A3C",
    "curve_ok":       "#2E7D32",
    "curve_nok":      "#C62828",
    "curve_history":  "#9E9E9E",
    "curve_live":     "#C49A3C",

    # Outils graphique
    "nopass_fill":    "#c62828",
    "nopass_border":  "#ef5350",
    "unibox_border":  "#C49A3C",
    "envelope_border":"#A07830",
    "envelope_fill":  "#A07830",

    # Boutons navigation
    "settings_btn":   "#A07830",
    "export_btn":     "#E8F5E9",
    "raz_btn":        "#FFEBEE",

    # Résultat
    "result_ok":      "#E8F5E9",
    "result_nok":     "#FFEBEE",
    "result_idle":    "#F5F5F5",

    # Aliases
    "panel_bg":       "#EEEEEE",
    "progress_ok":    "#4caf50",
    "progress_warn":  "#ef5350",

    # Compatibilité outils graphique
    "tool_no_pass":   "#c62828",
    "tool_unibox":    "#C49A3C",
    "tool_envelope":  "#A07830",
}

_current_theme: str = "dark"  # "dark" ou "light"


def get_colors() -> dict[str, str]:
    """Retourne la palette active selon le thème courant."""
    return COLORS_LIGHT if _current_theme == "light" else COLORS


_PIN_CODE = "1234"
_MAX_PIN_ATTEMPTS = 3
_LOCKOUT_SECONDS = 30


class AccessLevel:
    """Niveaux d'accès utilisateur."""
    NONE       = 0  # Machine verrouillée
    OPERATEUR  = 1  # Opérateur — production (lecture seule)
    TECHNICIEN = 2  # Technicien — PM, RAZ, réglages (sauf Extras)
    ADMIN      = 3  # Admin — accès total

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
    font-size: 44px;
    font-weight: bold;
    border-radius: 10px;
    padding: 8px;
}}
QLabel#counter_ok   {{ color: {COLORS['ok_text']}; font-size: 22px; font-weight: bold; }}
QLabel#counter_nok  {{ color: {COLORS['nok_text']}; font-size: 22px; font-weight: bold; }}
QLabel#counter_tot  {{ color: {COLORS['text_primary']}; font-size: 22px; font-weight: bold; }}
QLabel#datetime_label {{ font-size: 12px; color: {COLORS['text_secondary']}; }}
QLabel#pm_section_title {{ font-size: 13px; font-weight: bold; color: {COLORS['blue']}; }}
QLabel#pm_btn_label {{ font-size: 17px; font-weight: bold; color: {COLORS['text_primary']}; }}
QLabel#live_label   {{ font-size: 15px; font-weight: 600; color: {COLORS['text_secondary']}; }}
QLabel#live_value   {{ font-size: 26px; font-weight: bold; color: {COLORS['text_primary']}; }}
QLabel#peak_label   {{ font-size: 15px; font-weight: 600; color: {COLORS['text_secondary']}; }}
QLabel#peak_value   {{ font-size: 22px; font-weight: bold; color: {COLORS['blue']}; }}

QProgressBar {{
    border: none;
    border-radius: 4px;
    background-color: {COLORS['bg_button']};
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
    border-color: {COLORS['blue']};
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
QDialog { background-color: #3A3A3A; }
QLabel  { color: #F0F0F0; font-size: 15px; }
QLineEdit {
    background-color: #444444;
    color: #ffffff;
    border: 2px solid #555555;
    border-radius: 8px;
    font-size: 28px;
    padding: 8px;
    letter-spacing: 12px;
}
QLineEdit:focus { border-color: #C49A3C; }
QPushButton {
    background-color: #C49A3C;
    color: white;
    border-radius: 8px;
    padding: 10px 24px;
    font-size: 14px;
    font-weight: bold;
    border: none;
}
QPushButton:pressed { background-color: #A07830; }
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
        self._auto_scale: bool = False
        self._edit_mode: bool = False
        self._edit_handles: list[dict] = []
        self._dragging_handle: dict | None = None
        self._drag_start_px: tuple[int, int] = (0, 0)
        self._tools_config_backup = None

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    def set_tools(self, tools: list[EvaluationTool]) -> None:
        self._tools = tools
        self.update()

    def set_tools_config(self, tools_config: dict) -> None:
        """Charge la configuration des outils depuis config.yaml (dict brut)."""
        self._tools_config = tools_config
        if self._edit_mode:
            self._compute_handles()
        self.update()

    def set_display_mode(self, mode: DisplayMode) -> None:
        self._display_mode = mode
        self._current_points.clear()
        self.update()

    def set_history_mode(self, enabled: bool) -> None:
        self._history_mode = enabled
        self.update()

    def toggle_auto_scale(self) -> None:
        self._auto_scale = not self._auto_scale
        self.update()

    def set_edit_mode(self, enabled: bool) -> None:
        self._edit_mode = enabled
        self.setMouseTracking(enabled)
        if enabled:
            import copy
            self._tools_config_backup = copy.deepcopy(self._tools_config)
            self._compute_handles()
        else:
            self._edit_handles.clear()
            self._dragging_handle = None
            self._tools_config_backup = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()

    def mousePressEvent(self, event) -> None:
        if not self._edit_mode:
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return

        px = event.position().x()
        py = event.position().y()

        handle_radius = 12
        for handle in self._edit_handles:
            dist = ((handle["px"] - px) ** 2 + (handle["py"] - py) ** 2) ** 0.5
            if dist <= handle_radius:
                self._dragging_handle = handle
                self._drag_start_px = (int(px), int(py))
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                break

    def mouseMoveEvent(self, event) -> None:
        if not self._edit_mode:
            return

        px = int(event.position().x())
        py = int(event.position().y())

        if self._dragging_handle is None:
            for handle in self._edit_handles:
                dist = ((handle["px"] - px) ** 2 + (handle["py"] - py) ** 2) ** 0.5
                if dist <= 12:
                    self.setCursor(Qt.CursorShape.OpenHandCursor)
                    return
            self.setCursor(Qt.CursorShape.ArrowCursor)
            return

        rect = self._plot_rect()
        xr, yr = self._get_ranges()

        px = max(rect.left(), min(px, rect.right()))
        py = max(rect.top(), min(py, rect.bottom()))

        new_x = (px - rect.left()) / rect.width() * xr
        new_y = yr - (py - rect.top()) / rect.height() * yr
        new_x = max(0.0, round(new_x, 1))
        new_y = max(0.0, round(new_y, 0))

        h = self._dragging_handle
        self._apply_handle_drag(h, new_x, new_y)

        self._compute_handles()
        self.update()
        main_win = self.window()
        if hasattr(main_win, '_refresh_edit_panel'):
            main_win._refresh_edit_panel()

    def mouseReleaseEvent(self, event) -> None:
        if not self._edit_mode:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging_handle = None
            self.setCursor(Qt.CursorShape.ArrowCursor)

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
            xr, yr = POSITION_MM_MAX, FORCE_NEWTON_MAX
        elif self._display_mode == DisplayMode.FORCE_TIME:
            xr, yr = 2.0, FORCE_NEWTON_MAX
        else:
            xr, yr = 2.0, POSITION_MM_MAX

        if self._auto_scale and self._current_points:
            max_f = max(f for _, f, _ in self._current_points)
            max_x = max(x for _, _, x in self._current_points)
            if self._display_mode == DisplayMode.FORCE_POSITION:
                yr = max(max_f * 1.15, 100.0)
                xr = max(max_x * 1.15, 1.0)
            elif self._display_mode == DisplayMode.FORCE_TIME:
                yr = max(max_f * 1.15, 100.0)
            else:
                yr = max(max_x * 1.15, 1.0)

        return xr, yr

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

    def set_theme(self, colors: dict) -> None:
        """Met à jour les couleurs du graphique."""
        self._colors = colors
        self.update()

    def _get_color(self, key: str) -> str:
        if hasattr(self, "_colors") and self._colors:
            return self._colors.get(key, COLORS.get(key, "#000000"))
        return COLORS.get(key, "#000000")

    # ------------------------------------------------------------------
    # paintEvent
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            # Fond global
            painter.fillRect(self.rect(), QColor(self._get_color("bg_graph")))

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
                    self._draw_curve(painter, pts, QColor(self._get_color("curve_history")), rect)
                if self._history:
                    pts, res = self._history[-1]
                    c = self._get_color("curve_ok") if res == "PASS" else self._get_color("curve_nok")
                    self._draw_curve(painter, pts, QColor(c), rect)
            elif self._current_points:
                if self._current_result == "PASS":
                    color = QColor(self._get_color("curve_ok"))
                elif self._current_result == "NOK":
                    color = QColor(self._get_color("curve_nok"))
                else:
                    color = QColor(self._get_color("curve_live"))
                self._draw_curve(painter, self._current_points, color, rect)

            painter.restore()

            # Labels axes (hors clip)
            self._draw_axes(painter, rect)
        except Exception as e:
            print(f"[GRAPH] paintEvent error: {e}")
        finally:
            painter.end()

    def _draw_axis_lines(self, painter: QPainter, rect: QRect) -> None:
        pen = QPen(QColor("#445566"))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawLine(rect.left(), rect.top(), rect.left(), rect.bottom())
        painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())

    def _draw_grid(self, painter: QPainter, rect: QRect) -> None:
        pen = QPen(QColor(self._get_color("grid")))
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
        for point in points:
            try:
                if len(point) != 3:
                    continue
                t, f, x = float(point[0]), float(point[1]), float(point[2])
                xd, yd = self._pt_to_data(t, f, x)
                px, py = self._to_px(xd, yd, rect)
                if prev is not None:
                    painter.drawLine(prev[0], prev[1], px, py)
                prev = (px, py)
            except (TypeError, ValueError, ZeroDivisionError):
                continue

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

        if self._edit_mode:
            _HANDLE_NUMS = {
                "tl": 1, "tm": 2, "tr": 3, "rm": 4,
                "br": 5, "bm": 6, "bl": 7, "lm": 8,
            }
            font_num = QFont("Arial", 9, QFont.Weight.Bold)
            for handle in self._edit_handles:
                px, py = self._to_px(handle["x_data"], handle["y_data"], rect)
                handle["px"] = px
                handle["py"] = py
                painter.setPen(QPen(QColor("#C49A3C"), 2))
                painter.setBrush(QBrush(QColor("#FFFFFF")))
                painter.drawEllipse(px - 6, py - 6, 12, 12)
                num = _HANDLE_NUMS.get(handle["handle_id"], 0)
                painter.setPen(QColor("#C49A3C"))
                painter.setFont(font_num)
                painter.drawText(px + 8, py - 8, str(num))

    def _compute_handles(self) -> None:
        self._edit_handles.clear()

        no_pass_zones = self._tools_config.get("no_pass_zones", [])
        if not no_pass_zones:
            old_no_pass = self._tools_config.get("no_pass", {})
            if old_no_pass.get("enabled"):
                no_pass_zones = [old_no_pass]

        for zone_idx, zone in enumerate(no_pass_zones):
            if not zone.get("enabled"):
                continue

            x1, x2 = float(zone["x_min"]), float(zone["x_max"])
            y1 = float(zone["y_limit"])
            y2 = 0.0

            for handle_id, x_data, y_data in [
                ("tl", x1, y1),
                ("tr", x2, y1),
                ("bl", x1, y2),
                ("br", x2, y2),
                ("tm", (x1 + x2) / 2.0, y1),
                ("bm", (x1 + x2) / 2.0, y2),
                ("lm", x1, y1 / 2.0),
                ("rm", x2, y1 / 2.0),
            ]:
                self._edit_handles.append(
                    {
                        "zone_type": "no_pass",
                        "zone_idx": zone_idx,
                        "handle_id": handle_id,
                        "x_data": x_data,
                        "y_data": y_data,
                        "px": 0,
                        "py": 0,
                    }
                )

        uni_box = self._tools_config.get("uni_box", {})
        if uni_box.get("enabled"):
            x1, x2 = float(uni_box["box_x_min"]), float(uni_box["box_x_max"])
            y1, y2 = float(uni_box["box_y_max"]), float(uni_box["box_y_min"])

            for handle_id, x_data, y_data in [
                ("tl", x1, y1),
                ("tr", x2, y1),
                ("bl", x1, y2),
                ("br", x2, y2),
                ("tm", (x1 + x2) / 2.0, y1),
                ("bm", (x1 + x2) / 2.0, y2),
                ("lm", x1, (y1 + y2) / 2.0),
                ("rm", x2, (y1 + y2) / 2.0),
            ]:
                self._edit_handles.append(
                    {
                        "zone_type": "uni_box",
                        "zone_idx": 0,
                        "handle_id": handle_id,
                        "x_data": x_data,
                        "y_data": y_data,
                        "px": 0,
                        "py": 0,
                    }
                )

    def _apply_handle_drag(self, handle: dict, new_x: float, new_y: float) -> None:
        """Met à jour _tools_config selon la poignée draguée."""
        zone_type = handle["zone_type"]
        zone_idx = handle["zone_idx"]
        hid = handle["handle_id"]

        if zone_type == "no_pass":
            zones = self._tools_config.get("no_pass_zones", [])
            if zone_idx >= len(zones):
                return
            z = zones[zone_idx]

            if hid in ("tl", "bl", "lm"):
                z["x_min"] = min(new_x, z["x_max"] - 1.0)
            if hid in ("tr", "br", "rm"):
                z["x_max"] = max(new_x, z["x_min"] + 1.0)
            if hid in ("tl", "tr", "tm"):
                z["y_limit"] = max(new_y, 1.0)

        elif zone_type == "uni_box":
            ub = self._tools_config.get("uni_box", {})
            if not ub:
                return

            if hid in ("tl", "bl", "lm"):
                ub["box_x_min"] = min(new_x, ub["box_x_max"] - 1.0)
            if hid in ("tr", "br", "rm"):
                ub["box_x_max"] = max(new_x, ub["box_x_min"] + 1.0)
            if hid in ("tl", "tr", "tm"):
                ub["box_y_max"] = max(new_y, ub["box_y_min"] + 1.0)
            if hid in ("bl", "br", "bm"):
                ub["box_y_min"] = min(new_y, ub["box_y_max"] - 1.0)

    def _draw_overlays_from_config(self, painter: QPainter, rect: QRect) -> None:
        """Dessine les outils depuis le dict config.yaml (couleurs IEC 60073)."""
        _xr, yr = self._get_ranges()

        # NO-PASS multi-zones
        np_zones = self._tools_config.get("no_pass_zones", [])
        # Compatibilité ancien format
        if not np_zones:
            old = self._tools_config.get("no_pass", {})
            if old.get("enabled"):
                np_zones = [old]

        for zone in np_zones:
            if not zone.get("enabled"):
                continue
            x1, y1 = self._to_px(zone["x_min"], yr, rect)
            x2, y2 = self._to_px(zone["x_max"], zone["y_limit"], rect)
            fill = QColor(198, 40, 40, 60)
            painter.fillRect(x1, y1, x2 - x1, y2 - y1, fill)
            painter.setPen(QPen(QColor(self._get_color("nopass_border")), 1.5, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(x1, y1, x2 - x1, y2 - y1)

        ub_d = self._tools_config.get("uni_box", {})
        if ub_d.get("enabled"):
            x1, y1 = self._to_px(ub_d["box_x_min"], ub_d["box_y_max"], rect)
            x2, y2 = self._to_px(ub_d["box_x_max"], ub_d["box_y_min"], rect)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(self._get_color("unibox_border")), 2, Qt.PenStyle.DashLine))
            painter.drawRect(x1, y1, x2 - x1, y2 - y1)

        env_d = self._tools_config.get("envelope", {})
        if env_d.get("enabled"):
            lower = env_d.get("lower_curve", [])
            upper = env_d.get("upper_curve", [])
            if len(lower) >= 2 and len(upper) >= 2:
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
                pen_env = QPen(QColor(self._get_color("envelope_border")), 1.5, Qt.PenStyle.DashLine)
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
        color = QColor(self._get_color("tool_no_pass"))
        color.setAlpha(80)
        painter.fillRect(x1, y1, x2 - x1, y2 - y1, color)

    def _draw_unibox(self, painter: QPainter, tool: EvaluationTool, rect: QRect) -> None:
        if None in (tool.box_x_min, tool.box_x_max, tool.box_y_min, tool.box_y_max):
            return
        pen = QPen(QColor(self._get_color("tool_unibox")))
        pen.setWidth(2)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        x1, y1 = self._to_px(tool.box_x_min, tool.box_y_max, rect)
        x2, y2 = self._to_px(tool.box_x_max, tool.box_y_min, rect)
        painter.drawRect(x1, y1, x2 - x1, y2 - y1)

    def _draw_envelope(self, painter: QPainter, tool: EvaluationTool, rect: QRect) -> None:
        pen = QPen(QColor(self._get_color("tool_envelope")))
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
        painter.setPen(QColor(self._get_color("axis_text")))

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
# NumpadDialog — pavé numérique tactile modal
# ===========================================================================

class NumpadDialog(QDialog):
    """Pavé numérique tactile modal — retourne une valeur float ou str.

    Usage :
        dlg = NumpadDialog(title="Seuil force", unit="N", value="4200.0", parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            val = dlg.value()  # str
    """

    def __init__(
        self,
        title: str = "Saisie",
        unit: str = "",
        value: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setFixedSize(360, 460)
        self.setStyleSheet("""
            QDialog { background-color: #3A3A3A; }
            QLabel#numpad_title {
                color: #AAAAAA; font-size: 13px; font-weight: 600;
            }
            QLabel#numpad_unit {
                color: #AAAAAA; font-size: 13px;
            }
            QLineEdit#numpad_display {
                background-color: #444444;
                color: #ffffff;
                border: 2px solid #C49A3C;
                border-radius: 8px;
                font-size: 28px;
                font-weight: bold;
                padding: 8px 12px;
                min-height: 52px;
            }
            QPushButton#numpad_key {
                background-color: #444444;
                color: #F0F0F0;
                font-size: 20px;
                font-weight: bold;
                border: 1px solid #555555;
                border-radius: 8px;
                min-height: 56px;
            }
            QPushButton#numpad_key:pressed { background-color: #A07830; }
            QPushButton#numpad_backspace {
                background-color: #444444;
                color: #ef9a9a;
                font-size: 18px;
                font-weight: bold;
                border: 1px solid #c62828;
                border-radius: 8px;
                min-height: 56px;
            }
            QPushButton#numpad_backspace:pressed { background-color: #3a1a1a; }
            QPushButton#numpad_ok {
                background-color: #1a3a1a;
                color: #4caf50;
                font-size: 18px;
                font-weight: bold;
                border: 2px solid #2d7a2d;
                border-radius: 8px;
                min-height: 56px;
            }
            QPushButton#numpad_ok:pressed { background-color: #2d7a2d; }
            QPushButton#numpad_cancel {
                background-color: #3a1a1a;
                color: #ef9a9a;
                font-size: 18px;
                font-weight: bold;
                border: 1px solid #c62828;
                border-radius: 8px;
                min-height: 56px;
            }
            QPushButton#numpad_cancel:pressed { background-color: #c62828; }
        """)
        self._build_ui(title, unit, value)

    def _build_ui(self, title: str, unit: str, value: str) -> None:
        from PySide6.QtWidgets import QGridLayout

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        lbl_title = QLabel(title)
        lbl_title.setObjectName("numpad_title")
        layout.addWidget(lbl_title)

        display_row = QHBoxLayout()
        self._display = QLineEdit(value)
        self._display.setObjectName("numpad_display")
        self._display.setReadOnly(True)
        self._display.setAlignment(Qt.AlignmentFlag.AlignRight)
        display_row.addWidget(self._display)
        if unit:
            lbl_unit = QLabel(unit)
            lbl_unit.setObjectName("numpad_unit")
            lbl_unit.setFixedWidth(36)
            display_row.addWidget(lbl_unit)
        layout.addLayout(display_row)

        grid = QGridLayout()
        grid.setSpacing(8)

        keys = [
            ("7", 0, 0), ("8", 0, 1), ("9", 0, 2),
            ("4", 1, 0), ("5", 1, 1), ("6", 1, 2),
            ("1", 2, 0), ("2", 2, 1), ("3", 2, 2),
            ("0", 3, 0), (".", 3, 1),
        ]
        for label, row, col in keys:
            btn = QPushButton(label)
            btn.setObjectName("numpad_key")
            btn.clicked.connect(lambda _, c=label: self._key_press(c))
            grid.addWidget(btn, row, col)

        btn_back = QPushButton(t("btn_backspace"))
        btn_back.setObjectName("numpad_backspace")
        btn_back.clicked.connect(self._backspace)
        grid.addWidget(btn_back, 3, 2)

        layout.addLayout(grid)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_cancel = QPushButton(t("btn_cancel_x"))
        btn_cancel.setObjectName("numpad_cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton(t("btn_ok_check"))
        btn_ok.setObjectName("numpad_ok")
        btn_ok.clicked.connect(self.accept)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_ok)
        layout.addLayout(btn_row)

    def _key_press(self, char: str) -> None:
        current = self._display.text()
        if char == "." and "." in current:
            return
        self._display.setText(current + char)

    def _backspace(self) -> None:
        self._display.setText(self._display.text()[:-1])

    def value(self) -> str:
        return self._display.text()


# ===========================================================================
# AlphaNumpadDialog — clavier alphanumérique tactile modal
# ===========================================================================

class AlphaNumpadDialog(QDialog):
    """Clavier alphanumérique tactile modal pour saisir un nom (ex: nom PM).

    Usage :
        dlg = AlphaNumpadDialog(title="Nom du PM", value="GTD14", parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            name = dlg.value()
    """

    _ROWS = [
        list("AZERTYUIOP"),
        list("QSDFGHJKLM"),
        list("WXCVBN_-. "),
    ]

    def __init__(
        self,
        title: str = "Saisie texte",
        value: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setFixedSize(660, 400)
        self.setStyleSheet("""
            QDialog { background-color: #3A3A3A; }
            QLabel { color: #AAAAAA; font-size: 13px; font-weight: 600; }
            QLineEdit#alpha_display {
                background-color: #444444;
                color: #ffffff;
                border: 2px solid #C49A3C;
                border-radius: 8px;
                font-size: 22px;
                font-weight: bold;
                padding: 8px 12px;
                min-height: 48px;
            }
            QPushButton#alpha_key {
                background-color: #444444;
                color: #F0F0F0;
                font-size: 16px;
                font-weight: bold;
                border: 1px solid #555555;
                border-radius: 6px;
                min-height: 48px;
                min-width: 48px;
            }
            QPushButton#alpha_key:pressed { background-color: #A07830; }
            QPushButton#alpha_special {
                background-color: #444444;
                color: #ef9a9a;
                font-size: 14px;
                font-weight: bold;
                border: 1px solid #c62828;
                border-radius: 6px;
                min-height: 48px;
            }
            QPushButton#alpha_special:pressed { background-color: #3a1a1a; }
            QPushButton#alpha_ok {
                background-color: #1a3a1a;
                color: #4caf50;
                font-size: 16px;
                font-weight: bold;
                border: 2px solid #2d7a2d;
                border-radius: 6px;
                min-height: 48px;
            }
            QPushButton#alpha_ok:pressed { background-color: #2d7a2d; }
            QPushButton#alpha_cancel {
                background-color: #3a1a1a;
                color: #ef9a9a;
                font-size: 16px;
                font-weight: bold;
                border: 1px solid #c62828;
                border-radius: 6px;
                min-height: 48px;
            }
        """)
        self._build_ui(title, value)

    def _build_ui(self, title: str, value: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        layout.addWidget(QLabel(title))

        self._display = QLineEdit(value)
        self._display.setObjectName("alpha_display")
        self._display.setReadOnly(True)
        layout.addWidget(self._display)

        for row_chars in self._ROWS:
            row = QHBoxLayout()
            row.setSpacing(5)
            for ch in row_chars:
                label = "ESP" if ch == " " else ch
                btn = QPushButton(label)
                btn.setObjectName("alpha_key")
                btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                btn.clicked.connect(lambda _, c=ch: self._key_press(c))
                row.addWidget(btn)
            layout.addLayout(row)

        num_row = QHBoxLayout()
        num_row.setSpacing(5)
        for ch in "0123456789":
            btn = QPushButton(ch)
            btn.setObjectName("alpha_key")
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.clicked.connect(lambda _, c=ch: self._key_press(c))
            num_row.addWidget(btn)
        btn_back = QPushButton(t("btn_backspace"))
        btn_back.setObjectName("alpha_special")
        btn_back.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        btn_back.clicked.connect(self._backspace)
        num_row.addWidget(btn_back)
        layout.addLayout(num_row)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_cancel = QPushButton(t("btn_cancel_x"))
        btn_cancel.setObjectName("alpha_cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton(t("btn_ok_check"))
        btn_ok.setObjectName("alpha_ok")
        btn_ok.clicked.connect(self.accept)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_ok)
        layout.addLayout(btn_row)

    def _key_press(self, char: str) -> None:
        self._display.setText(self._display.text() + char)

    def _backspace(self) -> None:
        self._display.setText(self._display.text()[:-1])

    def value(self) -> str:
        return self._display.text()


# ===========================================================================
# PmSelectorDialog — sélecteur de Programme de Mesure
# ===========================================================================

_PM_SELECTOR_STYLE = f"""
QDialog {{
    background-color: {COLORS['panel_bg']};
    color: {COLORS['text_primary']};
}}
QLabel#title {{
    font-size: 18px;
    font-weight: bold;
    color: {COLORS['text_primary']};
    padding: 4px 0 12px 0;
}}
QPushButton#pm_item {{
    background-color: {COLORS['bg_button']};
    color: {COLORS['text_primary']};
    border: 2px solid {COLORS['border']};
    border-radius: 8px;
    font-size: 15px;
    font-weight: bold;
    padding: 8px;
}}
QPushButton#pm_item:hover {{
    background-color: #4e4e4e;
    border-color: #777777;
}}
QPushButton#pm_item_active {{
    background-color: {COLORS['ok_bg']};
    color: {COLORS['ok_text']};
    border: 2px solid {COLORS['ok_border']};
    border-radius: 8px;
    font-size: 15px;
    font-weight: bold;
    padding: 8px;
}}
QPushButton#pm_item_active:hover {{
    background-color: #1f4a1f;
}}
QPushButton#btn_cancel {{
    background-color: {COLORS['border']};
    color: {COLORS['text_primary']};
    border: 1px solid #777777;
    border-radius: 6px;
    font-size: 14px;
    padding: 6px;
}}
QPushButton#btn_cancel:hover {{
    background-color: #444;
}}
"""


class PmSelectorDialog(QDialog):
    """Sélecteur PM — grille de tuiles colorées."""

    _PM_COLORS = [
        ("#1a3a4a", "#2196F3"),  # bleu
        ("#1a3a1a", "#4CAF50"),  # vert
        ("#3a2a1a", "#FF9800"),  # orange
        ("#2a1a3a", "#9C27B0"),  # violet
        ("#3a1a1a", "#F44336"),  # rouge
        ("#1a3a3a", "#00BCD4"),  # cyan
        ("#3a3a1a", "#FFEB3B"),  # jaune
        ("#2a2a1a", "#C49A3C"),  # or ACM
    ]

    def __init__(self, current_pm_id: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog
        )
        self.setModal(True)
        self.setFixedSize(700, 500)
        self.setStyleSheet("""
            QDialog {
                background-color: #2E2E2E;
                border: 2px solid #C49A3C;
                border-radius: 12px;
            }
        """)
        self.selected_pm_id: int | None = None
        self._current_pm_id = current_pm_id
        self._build_ui()

    def _build_ui(self) -> None:
        from PySide6.QtWidgets import QGridLayout

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        # Header
        header_row = QHBoxLayout()
        title = QLabel(t("dlg_pm_selection_title"))
        title.setStyleSheet(
            "color: #C49A3C; font-size: 18px; font-weight: bold; background: transparent;"
        )
        header_row.addWidget(title)
        header_row.addStretch()

        current_pm = PM_DEFINITIONS.get(self._current_pm_id)
        current_name = current_pm.name if current_pm else "—"
        active_lbl = QLabel(f"Actif : PM-{self._current_pm_id:02d} · {current_name}")
        active_lbl.setStyleSheet(
            "color: #4caf50; font-size: 13px;"
            " background: #1a3a1a; border-radius: 4px; padding: 4px 8px;"
        )
        header_row.addWidget(active_lbl)
        root.addLayout(header_row)

        # Séparateur doré
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background-color: #C49A3C; max-height: 1px;")
        root.addWidget(sep)

        # Grille de PM — 3 colonnes
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setSpacing(10)

        pm_ids = sorted(PM_DEFINITIONS.keys())
        for idx, pm_id in enumerate(pm_ids):
            pm = PM_DEFINITIONS[pm_id]
            row, col = divmod(idx, 3)
            bg, accent = self._PM_COLORS[idx % len(self._PM_COLORS)]
            is_active = (pm_id == self._current_pm_id)
            border_width = "3px" if is_active else "1px"
            border_color = "#4caf50" if is_active else accent
            bg_hover = bg.replace("1a", "2a")

            tile = QFrame()
            tile.setFixedHeight(90)
            tile.setCursor(Qt.CursorShape.PointingHandCursor)
            tile.setStyleSheet(f"""
                QFrame {{
                    background-color: {bg};
                    border: {border_width} solid {border_color};
                    border-radius: 8px;
                }}
                QFrame:hover {{
                    border: 2px solid {accent};
                    background-color: {bg_hover};
                }}
            """)

            tile_layout = QVBoxLayout(tile)
            tile_layout.setContentsMargins(12, 8, 12, 8)
            tile_layout.setSpacing(4)

            top_row = QHBoxLayout()
            pm_num = QLabel(f"PM-{pm_id:02d}")
            pm_num.setStyleSheet(
                f"color: {accent}; font-size: 16px;"
                f" font-weight: bold; background: transparent;"
            )
            top_row.addWidget(pm_num)
            top_row.addStretch()
            if is_active:
                badge = QLabel(t("badge_active"))
                badge.setStyleSheet(
                    "color: #4caf50; font-size: 11px;"
                    " background: transparent; font-weight: bold;"
                )
                top_row.addWidget(badge)
            tile_layout.addLayout(top_row)

            pm_name_lbl = QLabel(pm.name)
            pm_name_lbl.setStyleSheet(
                "color: #F0F0F0; font-size: 13px; background: transparent;"
            )
            pm_name_lbl.setWordWrap(True)
            tile_layout.addWidget(pm_name_lbl)

            tile.mousePressEvent = lambda e, pid=pm_id: self._select(pid)
            grid.addWidget(tile, row, col)

        scroll.setWidget(grid_widget)
        root.addWidget(scroll, stretch=1)

        # Footer
        btn_cancel = QPushButton(t("btn_cancel_x_wide"))
        btn_cancel.setFixedHeight(44)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #3a1a1a;
                color: #ef9a9a;
                font-size: 14px;
                font-weight: bold;
                border: 1px solid #c62828;
                border-radius: 6px;
            }
            QPushButton:pressed { background-color: #c62828; }
        """)
        btn_cancel.clicked.connect(self.reject)
        root.addWidget(btn_cancel)

    def _select(self, pm_id: int) -> None:
        self.selected_pm_id = pm_id
        self.accept()


# ===========================================================================
# _TendanceWidget — mini tracé Fmax via QPainter (page stable, pas de transition)
# ===========================================================================

class _TendanceWidget(QWidget):
    """Graphe Fmax par cycle (QPainter autorisé : widget stable, hors transition stack)."""

    _ML, _MR, _MT, _MB = 45, 12, 15, 28

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._data: list[float] = []
        self.setFixedHeight(200)
        self.setStyleSheet("background-color: #1a1a1a;")

    def set_data(self, fmax_values: list[float]) -> None:
        self._data = fmax_values
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            w, h = self.width(), self.height()
            ml, mr, mt, mb = self._ML, self._MR, self._MT, self._MB
            pw, ph = w - ml - mr, h - mt - mb

            if len(self._data) < 2:
                p.setPen(QPen(QColor("#9e9e9e")))
                p.drawText(QRect(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, t("lbl_not_enough_data"))
                return

            # Grille horizontale
            p.setPen(QPen(QColor("#222222"), 1))
            for i in range(5):
                y = mt + int(ph * i / 4)
                p.drawLine(ml, y, w - mr, y)

            # Labels Y
            font = QFont()
            font.setPointSize(8)
            p.setFont(font)
            p.setPen(QPen(QColor("#556677")))
            p.drawText(2, mt + 8, f"{FORCE_NEWTON_MAX:.0f}N")
            p.drawText(2, h - mb + 5, "0N")

            # Axes
            p.setPen(QPen(QColor("#444444"), 1))
            p.drawLine(ml, mt, ml, h - mb)
            p.drawLine(ml, h - mb, w - mr, h - mb)

            # Points
            n = len(self._data)
            pts = []
            for i, fmax in enumerate(self._data):
                x = ml + int(i * pw / max(n - 1, 1))
                raw_y = mt + ph - int(min(fmax, FORCE_NEWTON_MAX) / FORCE_NEWTON_MAX * ph)
                pts.append((x, max(mt, min(mt + ph, raw_y))))

            # Moyenne
            avg = sum(self._data) / n
            avg_y = mt + ph - int(min(avg, FORCE_NEWTON_MAX) / FORCE_NEWTON_MAX * ph)
            avg_y = max(mt, min(mt + ph, avg_y))
            p.setPen(QPen(QColor("#ef5350"), 1, Qt.PenStyle.DashLine))
            p.drawLine(ml, avg_y, w - mr, avg_y)

            # Courbe Fmax
            p.setPen(QPen(QColor("#42a5f5"), 2))
            for i in range(len(pts) - 1):
                p.drawLine(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])

            # Labels X (premier et dernier cycle)
            p.setPen(QPen(QColor("#556677")))
            p.drawText(ml, h - 4, "1")
            last_x = pts[-1][0]
            p.drawText(max(ml, last_x - 20), h - 4, str(n))
        finally:
            p.end()


# ===========================================================================
# _StatsWidget — page statistiques production
# ===========================================================================

class _StatsWidget(QWidget):
    """Affiche les statistiques de production en scroll vertical."""

    _N_OPTIONS = [20, 50, 100]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._n_histo = 50
        self._last_log: list[tuple] = []
        self._build_ui()

    # ------------------------------------------------------------------
    # Construction UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        existing = self.layout()
        if existing is not None:
            while existing.count():
                item = existing.takeAt(0)
                w = item.widget()
                if w is not None:
                    w.deleteLater()

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background-color: #121212; border: none;")

        content = QWidget()
        content.setStyleSheet("background-color: #121212;")
        v = QVBoxLayout(content)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(14)

        v.addWidget(self._build_summary_section())
        v.addWidget(self._build_histogram_section())
        v.addWidget(self._build_tendance_section())
        v.addWidget(self._build_rebut_section())
        v.addWidget(self._build_nok_table_section())
        v.addStretch()

        scroll.setWidget(content)
        outer = existing if existing is not None else QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _card_section(self, title: str, inner: QWidget) -> tuple[QWidget, QLabel]:
        box = QWidget()
        box.setStyleSheet("background-color: #1e1e1e; border-radius: 8px;")
        v = QVBoxLayout(box)
        v.setContentsMargins(10, 8, 10, 10)
        v.setSpacing(6)
        lbl = QLabel(title)
        lbl.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #9e9e9e; background: transparent;"
        )
        sep = QFrame()
        sep.setObjectName("separator")
        v.addWidget(lbl)
        v.addWidget(sep)
        v.addWidget(inner)
        return box, lbl

    def _build_summary_section(self) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        specs = [
            ("total", t("stats_total"),   "#1e1e1e", "#e0e0e0", "📊"),
            ("ok",    t("status_ok"),   "#1a3a1a", "#4caf50", "✅"),
            ("nok",   t("status_nok"),  "#3a1a1a", "#ef5350", "❌"),
            ("taux",  t("stats_ok_rate"), "#1a2a3a", "#42a5f5", "📈"),
        ]
        self._card_lbls: dict[str, QLabel] = {}
        for key, name, bg, fg, icon in specs:
            frame = QFrame()
            frame.setFixedSize(140, 100)
            frame.setStyleSheet(
                f"QFrame {{ background-color: {bg}; border-radius: 8px;"
                f" border-top: none; border-left: none; border-right: none;"
                f" border-bottom: 4px solid {fg}; }}"
            )
            fv = QVBoxLayout(frame)
            fv.setContentsMargins(6, 6, 6, 6)
            fv.setSpacing(2)
            ico = QLabel(icon)
            ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ico.setStyleSheet("font-size: 20px; background: transparent; border: none;")
            val = QLabel("—")
            val.setAlignment(Qt.AlignmentFlag.AlignCenter)
            val.setStyleSheet(
                f"font-size: 32px; font-weight: bold; color: {fg};"
                " background: transparent; border: none;"
            )
            sub = QLabel(name)
            sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sub.setStyleSheet("font-size: 13px; color: #9e9e9e; background: transparent; border: none;")
            fv.addWidget(ico)
            fv.addWidget(val)
            fv.addWidget(sub)
            self._card_lbls[key] = val
            h.addWidget(frame)
        h.addStretch()
        section, _ = self._card_section(t("stats_summary_title"), w)
        return section

    def _build_histogram_section(self) -> QWidget:
        wrapper = QWidget()
        v = QVBoxLayout(wrapper)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)

        self._bar_container = QWidget()
        self._bar_container.setFixedHeight(120)
        self._bar_container.setStyleSheet(
            "background-color: #1a1a1a; border: 1px solid #333; border-radius: 4px;"
        )
        self._bar_layout = QHBoxLayout(self._bar_container)
        self._bar_layout.setContentsMargins(4, 4, 4, 4)
        self._bar_layout.setSpacing(2)
        self._bar_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        v.addWidget(self._bar_container)

        row = QWidget()
        rh = QHBoxLayout(row)
        rh.setContentsMargins(0, 0, 0, 0)
        self._histo_info = QLabel(t("lbl_cycles_shown_zero"))
        self._histo_info.setStyleSheet("font-size: 12px; color: #9e9e9e;")
        rh.addWidget(self._histo_info)
        rh.addStretch()
        self._n_btn = QPushButton(t("lbl_cycles_count").format(n=self._n_histo))
        self._n_btn.setObjectName("nav_btn")
        self._n_btn.setFixedSize(120, 32)
        self._n_btn.clicked.connect(self._cycle_n_histo)
        rh.addWidget(self._n_btn)
        v.addWidget(row)

        section, self._histo_title_lbl = self._card_section(
            t("stats_history_title").format(n=self._n_histo), wrapper
        )
        return section

    def _build_tendance_section(self) -> QWidget:
        self._tendance = _TendanceWidget()
        section, self._tendance_title_lbl = self._card_section(t("stats_trend_title"), self._tendance)
        return section

    def _build_rebut_section(self) -> QWidget:
        self._rebut_inner = QWidget()
        self._rebut_layout = QVBoxLayout(self._rebut_inner)
        self._rebut_layout.setContentsMargins(0, 0, 0, 0)
        self._rebut_layout.setSpacing(4)
        section, _ = self._card_section(t("stats_scrap_hour_title"), self._rebut_inner)
        return section

    def _build_nok_table_section(self) -> QWidget:
        self._nok_table = QTableWidget(0, 5)
        self._nok_table.setHorizontalHeaderLabels(
            [
                t("table_col_cycle"),
                t("lbl_time"),
                t("table_col_fmax_n"),
                t("table_col_xmax_mm"),
                t("table_col_pm"),
            ]
        )
        self._nok_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._nok_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._nok_table.setStyleSheet(
            "QTableWidget { background-color: #1a0808; color: #e0e0e0;"
            " gridline-color: #333; }"
            "QHeaderView::section { background-color: #2a0a0a; color: #e0e0e0;"
            " border: none; padding: 4px; }"
        )
        self._nok_table.horizontalHeader().setDefaultSectionSize(110)
        section, self._nok_title_lbl = self._card_section(t("stats_nok_details_title"), self._nok_table)
        return section

    def apply_language(self) -> None:
        self._build_ui()
        self.refresh(self._last_log)

    # ------------------------------------------------------------------
    # Interactions
    # ------------------------------------------------------------------

    def _cycle_n_histo(self) -> None:
        idx = self._N_OPTIONS.index(self._n_histo) if self._n_histo in self._N_OPTIONS else 1
        self._n_histo = self._N_OPTIONS[(idx + 1) % len(self._N_OPTIONS)]
        self._n_btn.setText(t("lbl_cycles_count").format(n=self._n_histo))
        n_displayed = len(self._last_log[-self._n_histo:])
        self._histo_title_lbl.setText(
            t("stats_history_title_count").format(n=self._n_histo, shown=n_displayed)
        )
        self._update_histogram(self._last_log)

    # ------------------------------------------------------------------
    # Refresh principal
    # ------------------------------------------------------------------

    def refresh(self, production_log: list[tuple]) -> None:
        """
        production_log : liste de tuples (cycle_num, fmax, xmax, result, heure)
        """
        self._last_log = production_log
        n_displayed = len(production_log[-self._n_histo:])
        nb_nok = sum(1 for e in production_log if e[3] != "PASS")
        self._histo_title_lbl.setText(
            t("stats_history_title_count").format(n=self._n_histo, shown=n_displayed)
        )
        self._tendance_title_lbl.setText(t("stats_trend_title_points").format(n=n_displayed))
        self._nok_title_lbl.setText(t("stats_nok_details_title_count").format(n=nb_nok))
        self._update_summary(production_log)
        self._update_histogram(production_log)
        self._update_tendance(production_log)
        self._update_rebut_par_heure(production_log)
        self._update_nok_table(production_log)

    def _update_summary(self, log: list[tuple]) -> None:
        total = len(log)
        nb_ok = sum(1 for r in log if r[3] == "PASS")
        nb_nok = total - nb_ok
        taux = (nb_ok / total * 100) if total else 0.0

        self._card_lbls["total"].setText(str(total))
        self._card_lbls["ok"].setText(str(nb_ok))
        self._card_lbls["nok"].setText(str(nb_nok))
        self._card_lbls["taux"].setText(f"{taux:.1f} %")

        # Couleur dynamique Taux OK
        if taux >= 95:
            taux_color = "#4caf50"
        elif taux >= 90:
            taux_color = "#42a5f5"
        else:
            taux_color = "#ef5350"
        self._card_lbls["taux"].setStyleSheet(
            f"font-size: 32px; font-weight: bold; color: {taux_color};"
            " background: transparent; border: none;"
        )

    def _update_histogram(self, log: list[tuple]) -> None:
        # Vider le container
        while self._bar_layout.count():
            item = self._bar_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        subset = log[-self._n_histo:]
        self._histo_info.setText(t("lbl_cycles_shown").format(n=len(subset)))

        bar_h = self._bar_container.height() - 8  # marges

        for entry in subset:
            cycle_num, fmax, _, result, _ = entry
            color = "#4caf50" if result == "PASS" else "#ef5350"
            height = max(4, int(min(fmax, FORCE_NEWTON_MAX) / FORCE_NEWTON_MAX * bar_h))

            slot = QWidget()
            slot.setFixedWidth(12)
            sv = QVBoxLayout(slot)
            sv.setContentsMargins(0, 0, 0, 0)
            sv.setSpacing(0)
            sv.addStretch()

            bar = QFrame(slot)
            bar.setFixedSize(12, height)
            bar.setStyleSheet(
                f"QFrame {{ background-color: {color}; border-radius: 2px; border: none; }}"
            )
            bar.setToolTip(f"Cycle {cycle_num}\n{result}\nFmax: {fmax:.0f} N")
            sv.addWidget(bar)
            self._bar_layout.addWidget(slot)

        self._bar_layout.addStretch()

    def _update_tendance(self, log: list[tuple]) -> None:
        fmax_values = [r[1] for r in log[-self._n_histo:]]
        self._tendance.set_data(fmax_values)

    def _update_rebut_par_heure(self, log: list[tuple]) -> None:
        # Nettoyer
        while self._rebut_layout.count():
            item = self._rebut_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Grouper par heure (HH:MM:SS → clé HH)
        hours: dict[str, list[tuple]] = {}
        for entry in log:
            heure = entry[4]  # format HH:MM:SS
            key = heure[:5] if len(heure) >= 5 else heure  # HH:MM
            hours.setdefault(key, []).append(entry)

        if not hours:
            lbl = QLabel(t("lbl_no_data"))
            lbl.setStyleSheet("color: #9e9e9e;")
            self._rebut_layout.addWidget(lbl)
            return

        for key in sorted(hours.keys()):
            entries = hours[key]
            nb_total = len(entries)
            nb_nok = sum(1 for e in entries if e[3] != "PASS")
            pct = (nb_nok / nb_total * 100) if nb_total else 0.0

            row = QWidget()
            rh = QHBoxLayout(row)
            rh.setContentsMargins(0, 2, 0, 2)
            rh.setSpacing(8)

            lbl = QLabel(f"{key}")
            lbl.setFixedWidth(40)
            lbl.setStyleSheet("font-size: 14px; color: #FFFFFF; font-weight: bold;")
            rh.addWidget(lbl)

            pb = QProgressBar()
            pb.setMaximum(nb_total)
            pb.setValue(nb_nok)
            pb.setFixedHeight(18)
            pb.setTextVisible(False)
            if pct > 10:
                chunk_color = "#ef5350"
            elif pct > 5:
                chunk_color = "#f57f17"
            else:
                chunk_color = "#4caf50"
            pb.setStyleSheet(
                "QProgressBar { background-color: #2a2a2a; border-radius: 3px; border: none; }"
                f"QProgressBar::chunk {{ background-color: {chunk_color}; border-radius: 3px; }}"
            )
            rh.addWidget(pb, stretch=1)

            info = QLabel(t("stats_hour_row_info").format(nok=nb_nok, total=nb_total))
            info.setFixedWidth(170)
            info.setStyleSheet("font-size: 12px; color: #9e9e9e;")
            rh.addWidget(info)

            self._rebut_layout.addWidget(row)

    def _update_nok_table(self, log: list[tuple]) -> None:
        self._nok_table.setRowCount(0)
        nok_entries = [(i, e) for i, e in enumerate(log) if e[3] != "PASS"]
        # Plus récent en haut
        nok_entries = sorted(nok_entries, key=lambda x: x[1][4], reverse=True)[:50]

        for _, (cycle_num, fmax, xmax, result, heure) in nok_entries:
            row = self._nok_table.rowCount()
            self._nok_table.insertRow(row)
            if fmax > FORCE_THRESHOLD_N:
                fmax_color = "#ef5350"
            elif fmax > FORCE_THRESHOLD_N * 0.8:
                fmax_color = "#FF9800"
            else:
                fmax_color = "#F0F0F0"
            for col, text in enumerate(
                [str(cycle_num), heure, f"{fmax:.0f}", f"{xmax:.1f}", "—"]
            ):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setBackground(QColor("#1a0808"))
                if col == 2:
                    item.setForeground(QColor(fmax_color))
                self._nok_table.setItem(row, col, item)


# ===========================================================================
# LevelSelectorDialog — choix du niveau avant saisie PIN
# ===========================================================================

class LevelSelectorDialog(QDialog):
    """Dialog de sélection du niveau d'accès avant saisie PIN."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog
        )
        self.setModal(True)
        self.setFixedSize(400, 320)
        self.setStyleSheet("""
            QDialog {
                background-color: #2E2E2E;
                border: 2px solid #C49A3C;
                border-radius: 12px;
            }
        """)
        self.selected_level: int = AccessLevel.NONE
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        title = QLabel(t("dlg_level_select_title"))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            "color: #C49A3C; font-size: 16px; font-weight: bold; background: transparent;"
        )
        layout.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background-color: #C49A3C; max-height: 1px;")
        layout.addWidget(sep)

        levels = [
            (AccessLevel.OPERATEUR,  "🟢", t("level_operator"),
               t("level_desc_operator"),               "#4caf50", "#1a3a1a"),
            (AccessLevel.TECHNICIEN, "🟡", t("level_tech"),
               t("level_desc_tech"),                   "#FF9800", "#2a1a00"),
            (AccessLevel.ADMIN,      "🔴", t("level_admin"),
               t("level_desc_admin"),                  "#C49A3C", "#2a1500"),
        ]

        for level, icon, name, desc, color, bg in levels:
            btn = QPushButton()
            btn.setFixedHeight(64)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg};
                    border: 1px solid {color};
                    border-radius: 8px;
                    text-align: left;
                    padding: 0 16px;
                }}
                QPushButton:pressed {{
                    border: 2px solid {color};
                    background-color: #3A3A3A;
                }}
            """)
            btn_layout = QHBoxLayout(btn)
            btn_layout.setContentsMargins(12, 8, 12, 8)

            icon_lbl = QLabel(f"{icon}  {name}")
            icon_lbl.setStyleSheet(
                f"color: {color}; font-size: 16px; font-weight: bold; "
                "background: transparent; border: none;"
            )
            desc_lbl = QLabel(desc)
            desc_lbl.setStyleSheet(
                "color: #AAAAAA; font-size: 12px; background: transparent; border: none;"
            )

            col = QVBoxLayout()
            col.addWidget(icon_lbl)
            col.addWidget(desc_lbl)
            btn_layout.addLayout(col)
            btn_layout.addStretch()

            btn.clicked.connect(lambda _, lv=level: self._select(lv))
            layout.addWidget(btn)

        btn_cancel = QPushButton(t("btn_cancel_x"))
        btn_cancel.setFixedHeight(40)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #3a1a1a;
                color: #ef9a9a;
                font-size: 13px;
                font-weight: bold;
                border: 1px solid #c62828;
                border-radius: 6px;
            }
            QPushButton:pressed { background-color: #c62828; }
        """)
        btn_cancel.clicked.connect(self.reject)
        layout.addWidget(btn_cancel)

    def _select(self, level: int) -> None:
        self.selected_level = level
        self.accept()


# ===========================================================================
# PinDialog — saisie PIN avec verrouillage
# ===========================================================================

class PinDialog(QDialog):
    """Dialogue PIN 4 chiffres, 3 tentatives, verrouillage 30 s."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("dlg_access_settings_title"))
        self.setModal(True)
        self.setFixedSize(360, 300)
        self.setStyleSheet(PINSTYLE)

        self._attempts = 0
        self._locked = False
        self._lockout_remaining = _LOCKOUT_SECONDS
        self._pin_value: str = ""
        self._lockout_timer = QTimer(self)
        self._lockout_timer.setInterval(1000)
        self._lockout_timer.timeout.connect(self._on_lockout_tick)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)

        self._label = QLabel(t("lbl_enter_pin"))
        layout.addWidget(self._label)

        self._pin_edit = QLineEdit()
        self._pin_edit.setReadOnly(True)
        self._pin_edit.setPlaceholderText(t("pin_placeholder"))
        self._pin_edit.setMinimumHeight(56)
        self._pin_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._pin_edit)

        btn_kbd = QPushButton(t("btn_enter_code"))
        btn_kbd.setMinimumHeight(52)
        btn_kbd.clicked.connect(self._open_numpad)
        layout.addWidget(btn_kbd)

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

    def _open_numpad(self) -> None:
        dlg = NumpadDialog(title="Code PIN", unit="", value="", parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            val = dlg.value()
            self._pin_value = val
            self._pin_edit.setText("•" * len(val))

    def _validate(self) -> None:
        if self._locked:
            return
        import hashlib
        cfg = load_config(Path(__file__).parent.parent / "config.yaml")
        # Initialiser les PIN par défaut si la section est absente
        ac = cfg.setdefault("access_control", {})
        _defaults = {
            "pin_operateur":  "0000",
            "pin_technicien": "2222",
            "pin_admin":      "1111",
        }
        for k, plain in _defaults.items():
            ac.setdefault(k, hashlib.sha256(plain.encode()).hexdigest())
        stored = ac.get("pin_admin", "")
        if not stored:
            stored = hashlib.sha256("1111".encode()).hexdigest()
        entered_hash = hashlib.sha256(self._pin_value.encode()).hexdigest()
        print(f"[PIN] pin_admin stocké : {stored[:12]}...")
        print(f"[PIN] PIN saisi hash   : {entered_hash[:12]}...")
        # Compatibilité plain text hérité
        valid = (
            entered_hash == stored
            if len(stored) == 64
            else self._pin_value == stored
        )
        if valid:
            self.accept()
        else:
            self._attempts += 1
            remaining = _MAX_PIN_ATTEMPTS - self._attempts
            if remaining > 0:
                self._error_label.setText(f"PIN incorrect — {remaining} tentative(s).")
            else:
                self._start_lockout()
            self._pin_value = ""
            self._pin_edit.clear()

    def _start_lockout(self) -> None:
        self._locked = True
        self._lockout_remaining = _LOCKOUT_SECONDS
        self._lockout_timer.start()
        self._update_lockout_label()

    def _on_lockout_tick(self) -> None:
        self._lockout_remaining -= 1
        if self._lockout_remaining <= 0:
            self._lockout_timer.stop()
            self._locked = False
            self._attempts = 0
            self._error_label.setText(t("lbl_pin_retry"))
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
        self.setWindowTitle(t("app_title"))

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

        # Mode simulateur + callback relance/arrêt
        self._sim_mode: bool = False
        self._restart_callback = None
        self._stop_callback = None
        self._restart_btn = None
        self._manual_cycle_enabled: bool = False
        self._modbus_connected: bool = False

        # Droits d'accès
        self._access_level: int = AccessLevel.OPERATEUR
        self._access_enabled: bool = False

        # Préférences d'affichage
        self._badge_style: str = "Texte"
        self._histogramme_mode: str = "OK-NOK en %"

        self.setStyleSheet(STYLESHEET)
        self._build_ui()

        self._edit_bar = QWidget(self._graph)
        edit_layout = QHBoxLayout(self._edit_bar)
        edit_layout.setContentsMargins(10, 6, 10, 6)
        edit_layout.setSpacing(10)

        self._btn_apply_zones = QPushButton("✓  Appliquer")
        self._btn_apply_zones.setFixedHeight(44)
        self._btn_apply_zones.setStyleSheet("""
            QPushButton {
                background-color: #1a3a1a;
                color: #4caf50;
                font-size: 15px;
                font-weight: bold;
                border: 2px solid #2d7a2d;
                border-radius: 8px;
                padding: 0 20px;
            }
            QPushButton:pressed { background-color: #2d7a2d; }
        """)
        self._btn_apply_zones.clicked.connect(self._apply_zone_edits)

        self._btn_cancel_zones = QPushButton("✗  Annuler")
        self._btn_cancel_zones.setFixedHeight(44)
        self._btn_cancel_zones.setStyleSheet("""
            QPushButton {
                background-color: #3a1a1a;
                color: #ef9a9a;
                font-size: 15px;
                font-weight: bold;
                border: 1px solid #c62828;
                border-radius: 8px;
                padding: 0 20px;
            }
            QPushButton:pressed { background-color: #c62828; }
        """)
        self._btn_cancel_zones.clicked.connect(self._cancel_zone_edits)

        self._edit_coords_label = QLabel("")
        self._edit_coords_label.setStyleSheet(
            "color: #C49A3C; font-size: 12px; background: transparent;"
        )
        edit_layout.addWidget(self._edit_coords_label)
        edit_layout.addStretch()
        edit_layout.addWidget(self._btn_cancel_zones)
        edit_layout.addWidget(self._btn_apply_zones)

        self._edit_bar.setVisible(False)

        # Bouton Auto-scale flottant sur le graphique
        self._auto_scale_btn = QPushButton("⤢ Auto", self._graph)
        self._auto_scale_btn.setCheckable(True)
        self._auto_scale_btn.setFixedSize(70, 28)
        self._auto_scale_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(40, 40, 40, 180);
                color: #aaaaaa;
                font-size: 12px;
                border: 1px solid #555555;
                border-radius: 4px;
            }
            QPushButton:checked {
                background-color: rgba(30, 80, 160, 200);
                color: #ffffff;
                border: 1px solid #42a5f5;
            }
        """)
        self._auto_scale_btn.clicked.connect(self._on_auto_scale_toggled)
        self._position_auto_scale_btn()

        self._apply_state_style("idle")
        self.apply_display_settings()
        self._load_access_settings()

        # Langue
        set_language(load_config(
            Path(__file__).parent.parent / "config.yaml"
        ).get("language", "fr"))
        self.apply_language()

        # Thème
        global _current_theme
        _theme_cfg = load_config(Path(__file__).parent.parent / "config.yaml")
        _current_theme = _theme_cfg.get("theme", "dark")
        if _current_theme == "light":
            self._theme_btn.setText("🌙  Thème sombre")
        self.apply_theme()

        # Charger les outils depuis config.yaml
        cfg_path = Path(__file__).parent.parent / "config.yaml"
        cfg = load_config(cfg_path)
        pm_tools = cfg.get("programmes", {}).get(self._pm_id, {}).get("tools", {})
        if pm_tools:
            self._graph.set_tools_config(pm_tools)

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
        self._stats_widget = _StatsWidget()
        self._content_stack.addWidget(self._graph)        # index 0
        self._content_stack.addWidget(self._data_table)   # index 1
        self._content_stack.addWidget(self._stats_widget) # index 2
        self._graph.setMinimumWidth(860)
        h.addWidget(self._content_stack, stretch=1)

        # Panneau droit — 420px fixe (normal + édition)
        self._right_stack = QStackedWidget()
        self._right_stack.setFixedWidth(420)
        right = self._build_right_panel()
        self._right_stack.addWidget(right)           # index 0 : normal
        self._edit_panel = self._build_edit_panel()
        self._right_stack.addWidget(self._edit_panel) # index 1 : édition
        h.addWidget(self._right_stack)

        v.addWidget(content, stretch=1)
        v.addWidget(self._build_nav_bar())
        return page

    # ------------------------------------------------------------------
    # Panneau droit — résultat + compteurs + PM + peaks + live + réglages
    # ------------------------------------------------------------------

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(
            f"background-color: {get_colors()['panel_bg']}; "
            f"border-left: 1px solid {get_colors()['separator']};"
        )
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(3)



        self._level_indicator = QLabel(t("level_free_icon"))
        self._level_indicator.setObjectName("level_indicator")
        self._level_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._level_indicator.setFixedHeight(20)
        self._level_indicator.setStyleSheet(
            "color: #AAAAAA; font-size: 12px; font-weight: bold; "
            "background: #3A3A3A; border-radius: 4px; padding: 2px 8px;"
        )
        layout.addWidget(self._level_indicator)

        self._login_btn = QPushButton(t("btn_login_unlock"))
        self._login_btn.setObjectName("login_btn")
        self._login_btn.setFixedHeight(24)
        self._login_btn.setStyleSheet("""
            QPushButton#login_btn {
                background-color: #444444;
                color: #C49A3C;
                font-size: 12px;
                font-weight: bold;
                border: 1px solid #C49A3C;
                border-radius: 4px;
            }
            QPushButton#login_btn:pressed {
                background-color: #A07830;
                color: #ffffff;
            }
        """)
        self._login_btn.setVisible(False)
        self._login_btn.clicked.connect(self._on_login_clicked)
        layout.addWidget(self._login_btn)

        layout.addWidget(self._build_result_badge())
        layout.addWidget(self._build_counters_section())
        layout.addWidget(self._build_datetime_section())
        layout.addWidget(make_hseparator(get_colors()["separator"]))
        layout.addWidget(self._build_pm_section())
        layout.addWidget(make_hseparator(get_colors()["separator"]))
        layout.addWidget(self._build_peaks_section())
        layout.addWidget(make_hseparator(get_colors()["separator"]))
        self._build_live_section(layout)
        layout.addStretch()
        layout.addWidget(self._build_modbus_indicator())
        self._theme_btn = QPushButton("☀  Thème clair")
        self._theme_btn.setObjectName("theme_btn")
        self._theme_btn.setFixedHeight(24)
        self._theme_btn.setStyleSheet("""
            QPushButton#theme_btn {
                background-color: #444444;
                color: #F0F0F0;
                font-size: 12px;
                font-weight: bold;
                border: 1px solid #666666;
                border-radius: 4px;
            }
            QPushButton#theme_btn:pressed {
                background-color: #C49A3C;
                color: #ffffff;
            }
        """)
        self._theme_btn.clicked.connect(self._toggle_theme)
        layout.addWidget(self._theme_btn)
        layout.addWidget(self._build_settings_button())
        return panel

    def _build_edit_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(
            f"background-color: {get_colors()['panel_bg']}; "
            f"border-left: 1px solid {get_colors()['separator']};"
        )
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("✏  Édition des zones")
        title.setStyleSheet("color: #C49A3C; font-size: 14px; font-weight: bold; background: transparent;")
        layout.addWidget(title)
        layout.addWidget(make_hseparator())

        self._edit_panel_content = QVBoxLayout()
        self._edit_panel_content.setSpacing(4)
        layout.addLayout(self._edit_panel_content)

        layout.addStretch()
        layout.addWidget(make_hseparator())

        reset_zoom_btn = QPushButton("↺  Réinitialiser zoom")
        reset_zoom_btn.setStyleSheet(
            "background-color: #444; color: #C49A3C; font-size: 13px; "
            "border: 1px solid #C49A3C; border-radius: 6px; padding: 6px;"
        )
        reset_zoom_btn.clicked.connect(lambda: (
            setattr(self._graph, '_auto_scale', False),
            self._graph.update(),
        ))
        layout.addWidget(reset_zoom_btn)

        hint = QLabel("Cliquez sur ✏ pour modifier\nune coordonnée précisément")
        hint.setStyleSheet("color: #888; font-size: 11px; font-style: italic; background: transparent;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        self._handle_coord_labels: dict[str, QLabel] = {}
        return panel

    _HANDLE_ORDER = [
        ("tl", 1), ("tm", 2), ("tr", 3), ("rm", 4),
        ("br", 5), ("bm", 6), ("bl", 7), ("lm", 8),
    ]

    def _get_handle_text(self, zone_type: str, zone_idx: int, hid: str) -> str:
        tools_cfg = self._graph._tools_config
        if zone_type == "no_pass":
            zones = tools_cfg.get("no_pass_zones", [])
            if not zones:
                old = tools_cfg.get("no_pass", {})
                if old.get("enabled"):
                    zones = [old]
            if zone_idx >= len(zones):
                return "—"
            z = zones[zone_idx]
            x = float(z.get("x_min", 0)) if hid in ("tl", "bl", "lm") else float(z.get("x_max", 0))
            y = float(z.get("y_limit", 0)) if hid in ("tl", "tr", "tm") else 0.0
        elif zone_type == "uni_box":
            ub = tools_cfg.get("uni_box", {})
            x = float(ub.get("box_x_min", 0)) if hid in ("tl", "bl", "lm") else float(ub.get("box_x_max", 0))
            y = float(ub.get("box_y_max", 0)) if hid in ("tl", "tr", "tm") else float(ub.get("box_y_min", 0))
        else:
            return "—"
        if hid in ("lm", "rm"):
            return f"X: {x:.1f} mm"
        elif hid in ("tm", "bm"):
            return f"Y: {y:.0f} N"
        else:
            return f"X: {x:.1f} mm  Y: {y:.0f} N"

    def _update_handle_coord_labels(self) -> None:
        for key, lbl in self._handle_coord_labels.items():
            zone_type, zone_idx_str, hid = key.split("|")
            lbl.setText(self._get_handle_text(zone_type, int(zone_idx_str), hid))

    def _build_edit_panel_content(self) -> None:
        while self._edit_panel_content.count():
            item = self._edit_panel_content.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._handle_coord_labels = {}
        tools_cfg = self._graph._tools_config

        no_pass_zones = tools_cfg.get("no_pass_zones", [])
        if not no_pass_zones:
            old = tools_cfg.get("no_pass", {})
            if old.get("enabled"):
                no_pass_zones = [old]

        for zone_idx, z in enumerate(no_pass_zones):
            if not z.get("enabled"):
                continue
            lbl_title = QLabel(f"Zone {zone_idx + 1} — NO-PASS")
            lbl_title.setStyleSheet(
                "color: #ef5350; font-weight: bold; font-size: 13px; background: transparent;"
            )
            self._edit_panel_content.addWidget(lbl_title)
            self._add_handle_rows("no_pass", zone_idx)
            self._edit_panel_content.addWidget(make_hseparator())

        ub = tools_cfg.get("uni_box", {})
        if ub.get("enabled"):
            lbl_title = QLabel("UNI-BOX")
            lbl_title.setStyleSheet(
                "color: #FF9800; font-weight: bold; font-size: 13px; background: transparent;"
            )
            self._edit_panel_content.addWidget(lbl_title)
            self._add_handle_rows("uni_box", 0)
            self._edit_panel_content.addWidget(make_hseparator())

    def _add_handle_rows(self, zone_type: str, zone_idx: int) -> None:
        for hid, num in self._HANDLE_ORDER:
            key = f"{zone_type}|{zone_idx}|{hid}"
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 1, 0, 1)
            row_layout.setSpacing(4)

            lbl_num = QLabel(f"{num}—{hid}")
            lbl_num.setStyleSheet(
                "color: #C49A3C; font-size: 11px; background: transparent; min-width: 45px;"
            )

            lbl_coord = QLabel(self._get_handle_text(zone_type, zone_idx, hid))
            lbl_coord.setStyleSheet(
                "color: #F0F0F0; font-size: 11px; background: transparent;"
            )
            self._handle_coord_labels[key] = lbl_coord

            btn_edit = QPushButton("✏")
            btn_edit.setFixedSize(26, 24)
            btn_edit.setStyleSheet(
                "background: #444; color: #C49A3C; border: 1px solid #C49A3C; "
                "border-radius: 4px; font-size: 12px; padding: 0;"
            )
            btn_edit.clicked.connect(
                lambda _checked, zt=zone_type, zi=zone_idx, h=hid:
                    self._edit_handle_from_panel(zt, zi, h)
            )

            row_layout.addWidget(lbl_num)
            row_layout.addWidget(lbl_coord, stretch=1)
            row_layout.addWidget(btn_edit)
            self._edit_panel_content.addWidget(row)

    def _edit_handle_from_panel(self, zone_type: str, zone_idx: int, hid: str) -> None:
        handle = next(
            (h for h in self._graph._edit_handles
             if h["zone_type"] == zone_type and h["zone_idx"] == zone_idx and h["handle_id"] == hid),
            None,
        )
        if handle is None:
            return

        if hid in ("lm", "rm"):
            dlg = NumpadDialog(
                title="Position (mm)", unit=" mm",
                value=str(round(handle["x_data"], 1)), parent=self
            )
            if dlg.exec():
                try:
                    self._graph._apply_handle_drag(dict(handle), float(dlg.value()), handle["y_data"])
                except ValueError:
                    return
        elif hid in ("tm", "bm"):
            dlg = NumpadDialog(
                title="Force (N)", unit=" N",
                value=str(round(handle["y_data"], 0)), parent=self
            )
            if dlg.exec():
                try:
                    self._graph._apply_handle_drag(dict(handle), handle["x_data"], float(dlg.value()))
                except ValueError:
                    return
        else:
            dlg_x = NumpadDialog(
                title="Position (mm)", unit=" mm",
                value=str(round(handle["x_data"], 1)), parent=self
            )
            if not dlg_x.exec():
                return
            dlg_y = NumpadDialog(
                title="Force (N)", unit=" N",
                value=str(round(handle["y_data"], 0)), parent=self
            )
            if not dlg_y.exec():
                return
            try:
                self._graph._apply_handle_drag(dict(handle), float(dlg_x.value()), float(dlg_y.value()))
            except ValueError:
                return

        self._graph._compute_handles()
        self._graph.update()
        self._update_handle_coord_labels()

    def _refresh_edit_panel(self) -> None:
        if not hasattr(self, '_handle_coord_labels'):
            self._handle_coord_labels = {}
        if self._handle_coord_labels:
            self._update_handle_coord_labels()
        else:
            self._build_edit_panel_content()

    def _build_result_badge(self) -> QLabel:
        self._result_badge = QLabel(t("status_idle"))
        self._result_badge.setObjectName("result_label")
        self._result_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._result_badge.setFixedHeight(110)
        self._result_badge.setStyleSheet(
            f"background-color: {get_colors()['idle_bg']}; color: {get_colors()['idle_text']}; "
            "border: 2px solid #333; border-radius: 10px; "
            "font-size: 36px; font-weight: bold; padding: 10px;"
        )
        return self._result_badge

    def _build_counters_section(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(55)
        w.setStyleSheet(
            "background-color: #1e1e1e; border: 1px solid #333; border-radius: 6px;"
        )
        h = QHBoxLayout(w)
        h.setContentsMargins(10, 4, 10, 4)
        h.setSpacing(0)
        self._ok_count_label = QLabel(t("counter_ok_zero"))
        self._ok_count_label.setObjectName("counter_ok")
        self._ok_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._nok_count_label = QLabel(t("counter_nok_zero"))
        self._nok_count_label.setObjectName("counter_nok")
        self._nok_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._total_count_label = QLabel(t("counter_total_zero"))
        self._total_count_label.setObjectName("counter_tot")
        self._total_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h.addWidget(self._ok_count_label, stretch=1)
        h.addWidget(make_vseparator(get_colors()["separator"]))
        h.addWidget(self._nok_count_label, stretch=1)
        h.addWidget(make_vseparator(get_colors()["separator"]))
        h.addWidget(self._total_count_label, stretch=1)
        return w

    def _build_datetime_section(self) -> QLabel:
        self._datetime_label = QLabel(datetime.now().strftime("%d/%m/%y   %H:%M:%S"))
        self._datetime_label.setObjectName("datetime_label")
        self._datetime_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._datetime_label.setFixedHeight(40)
        self._dt_timer = QTimer(self)
        self._dt_timer.setInterval(1000)
        self._dt_timer.timeout.connect(self._update_datetime)
        self._dt_timer.start()
        return self._datetime_label

    def _build_pm_section(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(4)
        self._pm_title_label = QLabel(t("app_title"))
        self._pm_title_label.setObjectName("pm_section_title")
        self._pm_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._pm_title_label.setFixedHeight(30)
        v.addWidget(self._pm_title_label)
        pm = PM_DEFINITIONS.get(self._pm_id)
        self._pm_btn = QPushButton(f"PM-{self._pm_id:02d}  ·  {pm.name if pm else '—'}")
        self._pm_btn.setObjectName("btn_pm")
        self._pm_btn.setFixedHeight(45)
        self._pm_btn.clicked.connect(self._on_pm_clicked)
        v.addWidget(self._pm_btn)
        return w

    def _build_peaks_section(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        self._peak_name_labels: list[QLabel] = []
        for attr, lbl_text, init_text in [
            ("_fmax_label", t("fmax_label"), "0 N"),
            ("_xmax_label", t("xmax_label"), "0.0 mm"),
        ]:
            row = QHBoxLayout()
            lbl = QLabel(lbl_text)
            lbl.setObjectName("peak_label")
            self._peak_name_labels.append(lbl)
            val = QLabel(init_text)
            val.setObjectName("peak_value")
            val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            setattr(self, attr, val)
            row.addWidget(lbl)
            row.addWidget(val)
            row_w = QWidget()
            row_w.setFixedHeight(50)
            row_w.setLayout(row)
            v.addWidget(row_w)
        return w

    def _build_live_section(self, layout: QVBoxLayout) -> None:
        self._live_name_labels: list[QLabel] = []
        for attr_val, attr_bar, lbl_text, max_val in [
            ("_force_value", "_force_bar", t("force_label"),    int(FORCE_NEWTON_MAX)),
            ("_pos_value",   "_pos_bar",   t("position_label"), int(POSITION_MM_MAX)),
        ]:
            lbl = QLabel(lbl_text)
            lbl.setObjectName("live_label")
            self._live_name_labels.append(lbl)
            layout.addWidget(lbl)
            row = QHBoxLayout()
            val_lbl = QLabel("0 N" if "force" in attr_val else "0.0 mm")
            val_lbl.setObjectName("live_value")
            bar = QProgressBar()
            bar.setRange(0, max_val)
            bar.setValue(0)
            bar.setTextVisible(False)
            bar.setProperty("alarm", "false")
            setattr(self, attr_val, val_lbl)
            setattr(self, attr_bar, bar)
            row.addWidget(val_lbl)
            row.addWidget(bar, stretch=1)
            layout.addLayout(row)

    def _build_modbus_indicator(self) -> QLabel:
        self._modbus_indicator = QLabel(t("modbus_unknown"))
        self._modbus_indicator.setStyleSheet("color: #9e9e9e; font-size: 12px; padding: 4px;")
        self._modbus_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return self._modbus_indicator

    def _build_settings_button(self) -> QPushButton:
        self._settings_btn = QPushButton(t("btn_settings_icon_upper"))
        self._settings_btn.setObjectName("btn_settings")
        self._settings_btn.setMinimumHeight(60)
        self._settings_btn.clicked.connect(self._on_settings_clicked)
        return self._settings_btn

    # ------------------------------------------------------------------
    # Barre de navigation bas
    # ------------------------------------------------------------------

    def _build_nav_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(70)
        bar.setStyleSheet(
            f"background-color: {get_colors()['panel_bg']}; "
            f"border-top: 1px solid {get_colors()['separator']};"
        )
        h = QHBoxLayout(bar)
        h.setContentsMargins(6, 6, 6, 6)
        h.setSpacing(6)

        btn_group = QButtonGroup(bar)
        btn_group.setExclusive(True)

        self._nav_buttons: dict[str, QPushButton] = {}
        specs = [
            ("current", f"📈  {t('nav_current')}", "nav_btn",    self._show_current_curve, True),
            ("history", f"🕐  {t('nav_history')}", "nav_btn",    self._show_history,       False),
            ("data",    f"📊  {t('nav_data')}",    "nav_btn",    self._show_data_table,    False),
            ("stats",   f"📊  {t('nav_stats')}",   "nav_btn",    self._show_stats,         False),
            ("zones",   "✏  Zones",               "nav_btn",    self._toggle_edit_mode,   False),
            ("manual",  "▶  Démarrer cycle",      "nav_btn",    self._start_manual_cycle, False),
            ("raz",     f"🔄  {t('nav_raz')}",     "nav_btn_red", self._reset_counters,     False),
        ]

        for key, label, obj_name, callback, checked in specs:
            btn = QPushButton(label)
            btn.setObjectName(obj_name)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            btn.clicked.connect(callback)
            btn.clicked.connect(lambda checked=False, b=btn: self._flash_nav_button(b))
            self._nav_buttons[key] = btn
            if obj_name == "nav_btn" and key not in ("zones", "manual"):
                btn.setCheckable(True)
                btn.setChecked(checked)
                btn_group.addButton(btn)
            h.addWidget(btn, stretch=1)

        manual_btn = self._nav_buttons.get("manual")
        if manual_btn is not None:
            manual_btn.setVisible(False)

        return bar

    def _flash_nav_button(self, btn: QPushButton) -> None:
        """Flash doré bref sur le bouton nav cliqué."""
        original = btn.styleSheet()
        btn.setStyleSheet(original + "background-color: #A07830; color: #ffffff;")
        QTimer.singleShot(150, lambda: btn.setStyleSheet(original))

    def _build_data_table(self) -> QTableWidget:
        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels([
            t("table_col_cycle"),
            t("table_col_fmax_n"),
            t("table_col_xmax_mm"),
            t("table_col_result"),
            t("lbl_time"),
        ])
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
        return make_hseparator(get_colors()["separator"])

    @staticmethod
    def _make_vsep() -> QFrame:
        return make_vseparator(get_colors()["separator"])

    # ------------------------------------------------------------------
    # Fond de fenêtre dynamique
    # ------------------------------------------------------------------

    def _apply_state_style(self, state: str) -> None:
        """Modifie le fond de la page production sans écraser STYLESHEET."""
        color_map = {
            "idle":      get_colors()["win_idle"],
            "acquiring": get_colors()["win_running"],
            "ok":        get_colors()["win_ok"],
            "nok":       get_colors()["win_nok"],
        }
        bg = color_map.get(state, get_colors()["win_idle"])
        self.centralWidget().setStyleSheet(f"background-color: {bg};")

    @staticmethod
    def _badge_content() -> dict[str, dict[str, str]]:
        return {
            "Smiley": {"ok": "😊", "nok": "😞", "running": "⏳", "idle": "—"},
            "Coche":  {"ok": "✓",  "nok": "✗",  "running": "⏳", "idle": "—"},
            "Pouce":  {"ok": "👍", "nok": "👎", "running": "⏳", "idle": "—"},
            "Texte":  {
                "ok": t("status_ok"),
                "nok": t("status_nok"),
                "running": t("status_running"),
                "idle": t("status_idle"),
            },
            "Vide":   {"ok": "",   "nok": "",    "running": "",  "idle": ""},
        }

    def _update_result_display(self, status: str) -> None:
        """Met à jour badge résultat + fond fenêtre selon l'état."""
        badge_content = self._badge_content()
        content = badge_content.get(
            self._badge_style, badge_content["Texte"]
        )
        self._result_badge.setText(content[status])

        if status == "ok":
            self._result_badge.setStyleSheet(
                f"background-color: {get_colors()['ok_bg']}; color: {get_colors()['ok_text']}; "
                f"border: 2px solid {get_colors()['ok_border']}; border-radius: 10px; "
                "font-size: 36px; font-weight: bold; padding: 8px;"
            )
            self._apply_state_style("ok")
            self._flash_badge()
        elif status == "nok":
            self._result_badge.setStyleSheet(
                f"background-color: {get_colors()['nok_bg']}; color: {get_colors()['nok_text']}; "
                f"border: 2px solid {get_colors()['nok_border']}; border-radius: 10px; "
                "font-size: 36px; font-weight: bold; padding: 8px;"
            )
            self._apply_state_style("nok")
            self._flash_badge()
        elif status == "running":
            self._result_badge.setStyleSheet(
                f"background-color: {get_colors()['running_bg']}; color: {get_colors()['blue']}; "
                f"border: 2px solid {get_colors()['running_border']}; border-radius: 10px; "
                "font-size: 36px; font-weight: bold; padding: 10px;"
            )
            self._apply_state_style("acquiring")
        else:  # idle
            self._result_badge.setStyleSheet(
                f"background-color: {get_colors()['idle_bg']}; color: {get_colors()['idle_text']}; "
                f"border: 2px solid {get_colors()['border']}; border-radius: 10px; "
                "font-size: 36px; font-weight: bold; padding: 10px;"
            )
            self._apply_state_style("idle")

    def _flash_badge(self) -> None:
        """Clignote 2 fois rapidement pour attirer l'attention."""
        original_style = self._result_badge.styleSheet()

        def _step1() -> None:
            self._result_badge.setStyleSheet(original_style + "opacity: 0.3;")

        def _step2() -> None:
            self._result_badge.setStyleSheet(original_style)

        def _step3() -> None:
            self._result_badge.setStyleSheet(original_style + "opacity: 0.3;")

        def _step4() -> None:
            self._result_badge.setStyleSheet(original_style)

        QTimer.singleShot(0,   _step1)
        QTimer.singleShot(100, _step2)
        QTimer.singleShot(200, _step3)
        QTimer.singleShot(300, _step4)

    # ------------------------------------------------------------------
    # Slots de données (connectés depuis main.py via AcquisitionBridge)
    # ------------------------------------------------------------------

    @Slot(float, float, float)
    def on_new_point(self, t: float, force_n: float, pos_mm: float) -> None:
        """Accumule un point dans le buffer — pas de redessin immédiat."""
        if not self._cycle_started:
            self._cycle_started = True
            self._update_result_display("running")
            print(f"[DEBUG] on_new_point: cycle_started=True, premier point")
        self._point_buffer.append((t, force_n, pos_mm))
        if len(self._point_buffer) % 50 == 1:
            print(f"[DEBUG] on_new_point: force={force_n:.1f} pos={pos_mm:.1f} buffer={len(self._point_buffer)}")
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

        if self._content_stack.currentIndex() == 2:
            self._stats_widget.refresh(self._production_log)

        # Remettre le bouton en mode "Démarrer"
        manual_btn = self._nav_buttons.get("manual")
        if manual_btn is not None:
            manual_btn.setText("▶  Démarrer cycle")

        if self._sim_mode:
            self._show_restart_button()

    def _show_restart_button(self) -> None:
        """Affiche un bouton flottant 'NOUVEAU CYCLE' au centre du graphique."""
        if self._restart_btn is not None:
            self._restart_btn.show()
            self._center_restart_btn()
            return
        self._restart_btn = QPushButton(f"▶   {t('btn_new_cycle')}", self._graph)
        self._restart_btn.setStyleSheet("""
            QPushButton {
                background-color: #1565c0;
                color: #ffffff;
                font-size: 18px;
                font-weight: bold;
                border-radius: 10px;
                border: 2px solid #42a5f5;
                padding: 14px 30px;
            }
            QPushButton:pressed { background-color: #0d47a1; }
        """)
        self._restart_btn.adjustSize()
        self._center_restart_btn()
        self._restart_btn.clicked.connect(self._on_restart_clicked)
        self._restart_btn.show()

    def _center_restart_btn(self) -> None:
        if self._restart_btn is None:
            return
        gw = self._graph
        bw = self._restart_btn.width()
        bh = self._restart_btn.height()
        self._restart_btn.move((gw.width() - bw) // 2, (gw.height() - bh) // 2)

    def _on_restart_clicked(self) -> None:
        if self._restart_btn is not None:
            self._restart_btn.hide()
        self._graph.start_new_cycle()
        self._update_result_display("idle")
        if self._restart_callback:
            self._restart_callback()

    def on_cycle_started(self) -> None:
        """Appelé quand un nouveau cycle commence."""
        self._cycle_started = False
        self._cycle_fmax = 0.0
        self._cycle_xmax = 0.0
        self._last_force = 0.0
        self._last_pos = 0.0
        self._graph.start_new_cycle()
        self._update_result_display("idle")

        # Basculer le bouton en mode "Arrêter"
        manual_btn = self._nav_buttons.get("manual")
        if manual_btn is not None:
            manual_btn.setText("⏹  Arrêter cycle")

    # ------------------------------------------------------------------
    # Timer 30 FPS
    # ------------------------------------------------------------------

    def _flush_buffer(self) -> None:
        if self._point_buffer:
            n = len(self._point_buffer)
            print(f"[DEBUG] flush_buffer: {n} points -> graph")
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
        if not self._cycle_started:
            self._graph.start_new_cycle()

    def _show_history(self) -> None:
        self._graph.set_history_mode(True)
        self._content_stack.setCurrentIndex(0)

    def _show_data_table(self) -> None:
        self._content_stack.setCurrentIndex(1)

    def _show_stats(self) -> None:
        self._graph.set_history_mode(False)
        self._content_stack.setCurrentIndex(2)
        self._stats_widget.refresh(self._production_log)

    def _start_manual_cycle(self) -> None:
        if not self._manual_cycle_enabled:
            return
        # Si cycle en cours → arrêter
        if self._cycle_started:
            self._stop_manual_cycle()
            return
        self.on_cycle_started()
        if self._restart_callback:
            self._restart_callback()

    def _stop_manual_cycle(self) -> None:
        """Arrête manuellement le cycle en cours."""
        if self._stop_callback:
            self._stop_callback()

    def _toggle_edit_mode(self) -> None:
        new_mode = not self._graph._edit_mode
        self._graph.set_edit_mode(new_mode)
        if new_mode:
            self._edit_bar.setVisible(True)
            gw = self._graph
            bar_h = 60
            self._edit_bar.setGeometry(0, gw.height() - bar_h, gw.width(), bar_h)
            self._right_stack.setCurrentIndex(1)
            self._handle_coord_labels = {}
            self._refresh_edit_panel()
        else:
            self._edit_bar.setVisible(False)
            self._right_stack.setCurrentIndex(0)
        for btn in self.findChildren(QPushButton):
            if "Zones" in btn.text():
                if new_mode:
                    btn.setText("✏  Zones ●")
                    btn.setStyleSheet(
                        btn.styleSheet() +
                        "background-color: #A07830;"
                    )
                else:
                    btn.setText("✏  Zones")
                    btn.setStyleSheet("")
                break

    def _apply_zone_edits(self) -> None:
        from ihm.ui_utils import load_config, save_config
        from pathlib import Path

        cfg_path = Path(__file__).parent.parent / "config.yaml"
        cfg = load_config(cfg_path)
        pm_id = self._pm_id

        tools_cfg = self._graph._tools_config
        cfg.setdefault("programmes", {}).setdefault(pm_id, {}).setdefault("tools", {})
        pm_tools = cfg["programmes"][pm_id]["tools"]

        if "no_pass_zones" in tools_cfg:
            pm_tools["no_pass_zones"] = tools_cfg["no_pass_zones"]

        if "uni_box" in tools_cfg:
            pm_tools["uni_box"] = tools_cfg["uni_box"]

        save_config(cfg_path, cfg)

        from config import build_tools_from_yaml
        new_tools = build_tools_from_yaml(pm_id)
        self._tools = new_tools
        self._graph.set_tools(new_tools)

        self._graph.set_edit_mode(False)
        self._edit_bar.setVisible(False)
        self._graph._tools_config_backup = None
        self._right_stack.setCurrentIndex(0)

        for btn in self.findChildren(QPushButton):
            if "Zones" in btn.text():
                btn.setText("✏  Zones")
                btn.setStyleSheet("")
                break

        QMessageBox.information(
            self, "Zones sauvegardées",
            f"✓ Zones du PM-{pm_id:02d} sauvegardées."
        )

    def _cancel_zone_edits(self) -> None:
        if self._graph._tools_config_backup is not None:
            import copy
            self._graph._tools_config = copy.deepcopy(
                self._graph._tools_config_backup
            )

        self._graph.set_edit_mode(False)
        self._edit_bar.setVisible(False)
        self._right_stack.setCurrentIndex(0)

        for btn in self.findChildren(QPushButton):
            if "Zones" in btn.text():
                btn.setText("✏  Zones")
                btn.setStyleSheet("")
                break

        self._graph.update()

    def _update_edit_coords(self, tools_cfg: dict) -> None:
        self._refresh_edit_panel()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, '_edit_bar') and self._edit_bar.isVisible():
            gw = self._graph
            self._edit_bar.setGeometry(
                0, gw.height() - 60,
                gw.width(), 60
            )
        if hasattr(self, '_auto_scale_btn'):
            self._position_auto_scale_btn()

    def _animate_counter(self, label: QLabel) -> None:
        """Grossit brièvement le compteur pour signaler l'incrémentation."""
        obj = label.objectName()
        if obj == "counter_ok":
            color = get_colors()["ok_text"]
        elif obj == "counter_nok":
            color = get_colors()["nok_text"]
        else:
            color = get_colors()["text_primary"]
        original_style = label.styleSheet()
        label.setStyleSheet(f"font-size: 28px; font-weight: bold; color: {color};")
        QTimer.singleShot(200, lambda: label.setStyleSheet(original_style))

    def _update_counters(self) -> None:
        total = self._count_ok + self._count_nok
        self._ok_count_label.setText(f"✓  {self._count_ok}")
        self._nok_count_label.setText(f"✗  {self._count_nok}")
        self._total_count_label.setText(f"Σ  {total}")
        if self._count_ok > 0:
            self._animate_counter(self._ok_count_label)
        if self._count_nok > 0:
            self._animate_counter(self._nok_count_label)

    def _update_datetime(self) -> None:
        self._datetime_label.setText(datetime.now().strftime("%d/%m/%y   %H:%M:%S"))

    def _reset_counters(self) -> None:
        reply = QMessageBox.question(
            self,
            t("dlg_raz_counters_title"),
            t("dlg_raz_counters_msg"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._count_ok = 0
            self._count_nok = 0
            self._update_counters()

    def set_sim_mode(self, enabled: bool) -> None:
        self._sim_mode = enabled

    def _position_auto_scale_btn(self) -> None:
        gw = self._graph
        self._auto_scale_btn.move(gw.width() - 80, 10)

    def _on_auto_scale_toggled(self) -> None:
        self._graph.toggle_auto_scale()
        if self._graph._auto_scale:
            self._auto_scale_btn.setText("⤢ Fixe")
        else:
            self._auto_scale_btn.setText("⤢ Auto")

    def set_restart_callback(self, callback) -> None:
        self._restart_callback = callback

    def set_stop_callback(self, callback) -> None:
        self._stop_callback = callback

    def set_manual_cycle_enabled(self, enabled: bool) -> None:
        self._manual_cycle_enabled = enabled
        manual_btn = self._nav_buttons.get("manual") if hasattr(self, "_nav_buttons") else None
        if manual_btn is not None:
            manual_btn.setVisible(enabled and not self._modbus_connected and not self._sim_mode)

    def set_modbus_status(self, connected: bool) -> None:
        self._modbus_connected = connected
        if connected:
            self._modbus_indicator.setText(f"⬤  {t('modbus_connected')}")
            self._modbus_indicator.setStyleSheet(
                "color: #4caf50; font-size: 12px; padding: 4px;"
            )
        else:
            self._modbus_indicator.setText(f"⬤  {t('modbus_disconnected')}")
            self._modbus_indicator.setStyleSheet(
                "color: #ef5350; font-size: 12px; padding: 4px;"
            )
        manual_btn = self._nav_buttons.get("manual") if hasattr(self, "_nav_buttons") else None
        if manual_btn is not None:
            manual_btn.setVisible(self._manual_cycle_enabled and not connected and not self._sim_mode)

    def _on_pm_clicked(self) -> None:
        """Ouvre le sélecteur de PM."""
        dlg = PmSelectorDialog(current_pm_id=self._pm_id, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        new_pm_id = dlg.selected_pm_id
        if new_pm_id is None or new_pm_id == self._pm_id:
            return
        self._apply_pm(new_pm_id)

    def _apply_pm(self, pm_id: int) -> None:
        """Applique le nouveau PM : met à jour l'affichage et recharge les outils."""
        self._pm_id = pm_id
        pm = PM_DEFINITIONS.get(pm_id)
        pm_name = pm.name if pm else f"PM-{pm_id:02d}"
        self._pm_btn.setText(f"PM-{pm_id:02d}  ·  {pm_name}")

        # Recharger les overlays visuels depuis config.yaml
        cfg_path = Path(__file__).parent.parent / "config.yaml"
        cfg = load_config(cfg_path)
        pm_tools = cfg.get("programmes", {}).get(pm_id, {}).get("tools", {})
        self._graph.set_tools_config(pm_tools)

        # Réinitialiser l'affichage du cycle
        self._cycle_fmax = 0.0
        self._cycle_xmax = 0.0
        self._fmax_label.setText("0 N")
        self._xmax_label.setText("0.0 mm")
        self._update_result_display("idle")

    def apply_theme(self) -> None:
        """Régénère et applique le stylesheet selon le thème."""
        global _current_theme
        c = get_colors()

        new_stylesheet = f"""
QMainWindow, QWidget#central {{
    background-color: {c['bg_main']};
    color: {c['text_primary']};
    font-family: 'Segoe UI', Arial, sans-serif;
}}
QLabel {{
    background-color: transparent;
    font-size: 15px;
    font-weight: 500;
}}
QLabel#result_label {{
    font-size: 44px;
    font-weight: bold;
    border-radius: 10px;
    padding: 8px;
}}
QLabel#counter_ok   {{ color: {c['ok_text']}; font-size: 22px; font-weight: bold; }}
QLabel#counter_nok  {{ color: {c['nok_text']}; font-size: 22px; font-weight: bold; }}
QLabel#counter_tot  {{ color: {c['text_primary']}; font-size: 22px; font-weight: bold; }}
QLabel#datetime_label {{ font-size: 12px; color: {c['text_secondary']}; }}
QLabel#pm_section_title {{ font-size: 13px; font-weight: bold; color: {c['blue']}; }}
QLabel#pm_btn_label {{ font-size: 17px; font-weight: bold; color: {c['text_primary']}; }}
QLabel#live_label   {{ font-size: 15px; font-weight: 600; color: {c['text_secondary']}; }}
QLabel#live_value   {{ font-size: 26px; font-weight: bold; color: {c['text_primary']}; }}
QLabel#peak_label   {{ font-size: 15px; font-weight: 600; color: {c['text_secondary']}; }}
QLabel#peak_value   {{ font-size: 22px; font-weight: bold; color: {c['blue']}; }}
QProgressBar {{
    border: none; border-radius: 4px;
    background-color: {c['bg_button']};
    max-height: 10px;
}}
QProgressBar::chunk {{
    border-radius: 4px;
    background-color: {c['ok_text']};
}}
QPushButton#btn_pm {{
    background-color: {c['bg_button']};
    color: {c['text_primary']};
    font-size: 14px; font-weight: bold;
    border: 1px solid {c['border']};
    border-radius: 6px; padding: 6px;
}}
QPushButton#btn_settings {{
    background-color: {c['settings_btn']};
    color: #ffffff; font-size: 16px; font-weight: bold;
    border-radius: 8px; border: 1px solid #d97706;
    min-height: 60px;
}}
QPushButton#nav_btn {{
    background-color: {c['bg_button']};
    color: {c['text_secondary']};
    font-size: 15px; font-weight: 600;
    border-radius: 8px;
    border: 1px solid {c['border']};
    min-height: 58px;
}}
QPushButton#nav_btn:checked {{
    background-color: {c['nav_active']};
    color: #ffffff;
    border-color: #E0B554;
}}
QPushButton#nav_btn_green {{
    background-color: {c['export_btn']};
    color: {c['ok_text']};
    font-size: 15px; font-weight: 600;
    border-radius: 8px;
    border: 1px solid {c['ok_border']};
    min-height: 58px;
}}
QPushButton#nav_btn_red {{
    background-color: {c['raz_btn']};
    color: {c['nok_text']};
    font-size: 15px; font-weight: 600;
    border-radius: 8px;
    border: 1px solid {c['nok_border']};
    min-height: 58px;
}}
QFrame#separator {{
    background-color: {c['border']};
    max-height: 1px;
}}
"""
        self.setStyleSheet(new_stylesheet)

        right_panel = self.findChild(QWidget, "right_panel")
        if right_panel:
            right_panel.setStyleSheet(
                f"background-color: {c['panel_bg']}; "
                f"border-left: 1px solid {c['separator']};"
            )

        self._graph.set_theme(c)

        self._update_result_display(
            "ok" if hasattr(self, "_count_ok") and self._count_ok > 0 else "idle"
        )

    def _toggle_theme(self) -> None:
        global _current_theme
        from pathlib import Path

        if _current_theme == "dark":
            _current_theme = "light"
            self._theme_btn.setText("🌙  Thème sombre")
        else:
            _current_theme = "dark"
            self._theme_btn.setText("☀  Thème clair")

        cfg_path = Path(__file__).parent.parent / "config.yaml"
        cfg = load_config(cfg_path)
        cfg["theme"] = _current_theme
        from ihm.ui_utils import save_config
        save_config(cfg_path, cfg)

        self.apply_theme()

    def apply_display_settings(self) -> None:
        """Recharge les préférences d'affichage depuis config.yaml."""
        cfg = load_config(Path(__file__).parent.parent / "config.yaml")
        dp = cfg.get("affichage_prod", {})
        self._badge_style      = dp.get("feu_bicolore",  "Texte")
        self._histogramme_mode = dp.get("histogramme",   "OK-NOK en %")

    def apply_language(self) -> None:
        """Applique la langue courante aux chaînes traduisibles de l'IHM."""
        # Bouton Réglages
        self._settings_btn.setText(f"⚙   {t('btn_settings')}")
        # Bouton login
        if hasattr(self, "_login_btn"):
            if self._access_level == AccessLevel.NONE:
                self._login_btn.setText(f"🔓  {t('btn_login')}")
        # Indicateur Modbus
        if hasattr(self, "_modbus_indicator"):
            text = self._modbus_indicator.text()
            connected_words = ("Connecté", "Connected", "Connesso",
                               "Conectado", "Conectat")
            if any(w in text for w in connected_words):
                self._modbus_indicator.setText(f"⬤  {t('modbus_connected')}")
            else:
                self._modbus_indicator.setText(f"⬤  {t('modbus_disconnected')}")

        if hasattr(self, "_pm_title_label"):
            self._pm_title_label.setText(t("app_title"))

        if hasattr(self, "_peak_name_labels") and len(self._peak_name_labels) >= 2:
            self._peak_name_labels[0].setText(t("fmax_label"))
            self._peak_name_labels[1].setText(t("xmax_label"))

        if hasattr(self, "_live_name_labels") and len(self._live_name_labels) >= 2:
            self._live_name_labels[0].setText(t("force_label"))
            self._live_name_labels[1].setText(t("position_label"))

        if hasattr(self, "_data_table"):
            self._data_table.setHorizontalHeaderLabels([
                t("table_col_cycle"),
                t("table_col_fmax_n"),
                t("table_col_xmax_mm"),
                t("table_col_result"),
                t("lbl_time"),
            ])

        if hasattr(self, "_nav_buttons"):
            self._nav_buttons.get("current") and self._nav_buttons["current"].setText(f"📈  {t('nav_current')}")
            self._nav_buttons.get("history") and self._nav_buttons["history"].setText(f"🕐  {t('nav_history')}")
            self._nav_buttons.get("data") and self._nav_buttons["data"].setText(f"📊  {t('nav_data')}")
            self._nav_buttons.get("stats") and self._nav_buttons["stats"].setText(f"📊  {t('nav_stats')}")
            self._nav_buttons.get("raz") and self._nav_buttons["raz"].setText(f"🔄  {t('nav_raz')}")

        if hasattr(self, "_restart_btn") and self._restart_btn is not None:
            self._restart_btn.setText(f"▶   {t('btn_new_cycle')}")

        if hasattr(self, "_stats_widget"):
            self._stats_widget.apply_language()

        settings_page = self.stack.widget(1) if hasattr(self, "stack") else None
        if settings_page is not None and hasattr(settings_page, "apply_language"):
            settings_page.apply_language()
            self._apply_settings_restrictions()

        self._update_level_indicator()

        self._result_badge.setText(t("status_idle"))

    def set_access_level(self, level: int) -> None:
        """Définit le niveau d'accès courant."""
        self._access_level = level
        self._update_level_indicator()
        self._update_ui_for_access_level()

    def _update_level_indicator(self) -> None:
        """Met à jour le label indicateur de niveau visible."""
        if not self._access_enabled:
            self._level_indicator.setText(t("level_free_icon"))
            self._level_indicator.setStyleSheet(
                "color: #AAAAAA; font-size: 12px; font-weight: bold; "
                "background: #3A3A3A; border-radius: 4px; padding: 2px 8px;"
            )
            return
        configs = {
            AccessLevel.NONE:       (f"🔒  {t('level_locked')}",   "#ef5350", "#3a1a1a"),
            AccessLevel.OPERATEUR:  (f"🟢  {t('level_operator')}", "#4caf50", "#1a3a1a"),
            AccessLevel.TECHNICIEN: (f"🟡  {t('level_tech')}",     "#FF9800", "#2a1a00"),
            AccessLevel.ADMIN:      (f"🔴  {t('level_admin')}",    "#C49A3C", "#2a1500"),
        }
        text, color, bg = configs.get(
            self._access_level, (f"👤  {t('level_free')}", "#AAAAAA", "#3A3A3A")
        )
        self._level_indicator.setText(text)
        self._level_indicator.setStyleSheet(
            f"color: {color}; font-size: 12px; font-weight: bold; "
            f"background: {bg}; border-radius: 4px; padding: 2px 8px;"
        )

    def _update_ui_for_access_level(self) -> None:
        """Active/désactive les boutons selon le niveau d'accès courant."""
        if not self._access_enabled:
            self._pm_btn.setEnabled(True)
            self._settings_btn.setEnabled(True)
            for btn in self.findChildren(QPushButton):
                if btn.objectName() == "nav_btn_red":
                    btn.setEnabled(True)
            return

        level = self._access_level
        # PM et RAZ : Technicien et Admin uniquement
        self._pm_btn.setEnabled(level >= AccessLevel.TECHNICIEN)
        for btn in self.findChildren(QPushButton):
            if btn.objectName() == "nav_btn_red":
                btn.setEnabled(level >= AccessLevel.TECHNICIEN)
        # Bouton Réglages : Opérateur et au-dessus
        self._settings_btn.setEnabled(level >= AccessLevel.OPERATEUR)
        # Restrictions interne aux réglages
        self._apply_settings_restrictions()

    def _apply_settings_restrictions(self) -> None:
        """Grise/active les boutons dans Paramètres généraux selon le niveau."""
        settings_page = self.stack.widget(1)
        if settings_page is None:
            return

        level = self._access_level

        restricted_op = {
            "voie_x", "voie_y", "cycle",
            "date_heure", "affichage", "exportation", "extras",
        }
        restricted_tech = {"extras"}

        for btn in settings_page.findChildren(QPushButton):
            action = btn.property("settings_action")
            if not action:
                continue
            if level == AccessLevel.OPERATEUR:
                blocked = action in restricted_op
                btn.setEnabled(not blocked)
            elif level == AccessLevel.TECHNICIEN:
                blocked = action in restricted_tech
                btn.setEnabled(not blocked)
            else:
                btn.setEnabled(True)

    def _on_login_clicked(self) -> None:
        """Connexion / déconnexion depuis le panneau droit."""
        import hashlib

        # Si déjà connecté → déconnexion
        if self._access_level > AccessLevel.NONE:
            self.set_access_level(AccessLevel.NONE)
            self._login_btn.setText(f"🔓  {t('btn_login')}")
            return

        # Étape 1 — Choisir le niveau
        level_dlg = LevelSelectorDialog(self)
        if level_dlg.exec() != QDialog.DialogCode.Accepted:
            return
        chosen_level = level_dlg.selected_level

        # Étape 2 — Saisir le PIN
        level_names = {
            AccessLevel.OPERATEUR:  t("level_operator"),
            AccessLevel.TECHNICIEN: t("level_tech"),
            AccessLevel.ADMIN:      t("level_admin"),
        }
        dlg = NumpadDialog(
            title=f"PIN — {level_names.get(chosen_level, '')}",
            unit="", value="", parent=self,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        # Étape 3 — Vérifier le PIN
        cfg = load_config(Path(__file__).parent.parent / "config.yaml")
        ac = cfg.get("access_control", {})
        pin_hash = hashlib.sha256(dlg.value().encode()).hexdigest()

        pin_keys = {
            AccessLevel.OPERATEUR:  ("pin_operateur",  "0000"),
            AccessLevel.TECHNICIEN: ("pin_technicien", "2222"),
            AccessLevel.ADMIN:      ("pin_admin",       "1234"),
        }
        key, default = pin_keys[chosen_level]
        stored = ac.get(key, hashlib.sha256(default.encode()).hexdigest())

        if pin_hash == stored:
            self.set_access_level(chosen_level)
            labels = {
                AccessLevel.OPERATEUR:  f"🟢  {t('level_operator')}",
                AccessLevel.TECHNICIEN: f"🟡  {t('level_tech')}",
                AccessLevel.ADMIN:      f"🔴  {t('level_admin')}",
            }
            self._login_btn.setText(f"🔒  {labels.get(chosen_level, t('level_locked'))}")
        else:
            QMessageBox.warning(
                self,
                t("dlg_access_denied_title"),
                t("dlg_pin_incorrect_msg").format(
                    level=level_names.get(chosen_level, "")
                ) + ".",
            )

    def _load_access_settings(self) -> None:
        """Charge et applique les préférences de droits depuis config.yaml."""
        cfg = load_config(Path(__file__).parent.parent / "config.yaml")
        ac = cfg.get("access_control", {})
        self._access_enabled = bool(ac.get("enabled", False))
        if not self._access_enabled:
            self._login_btn.setVisible(False)
            self._level_indicator.setVisible(False)
        else:
            self._login_btn.setVisible(True)
            self._level_indicator.setVisible(True)
            self.set_access_level(AccessLevel.NONE)

    def _on_settings_clicked(self) -> None:
        """Navigue vers la page Réglages (droits vérifiés dans _update_ui_for_access_level)."""
        if not self._access_enabled:
            self.stack.setCurrentIndex(1)
            return
        if self._access_level >= AccessLevel.OPERATEUR:
            self._apply_settings_restrictions()
            self.stack.setCurrentIndex(1)
            return
        QMessageBox.information(
            self,
            t("dlg_access_restricted_title"),
            t("dlg_access_restricted_msg"),
        )

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
                    QColor(get_colors()["curve_ok"] if result == "PASS" else get_colors()["curve_nok"])
                )
            self._data_table.setItem(row, col, item)
        self._data_table.scrollToBottom()
