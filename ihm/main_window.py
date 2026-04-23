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
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen, QPolygon, QKeySequence, QShortcut, QBrush
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
    MAX_NO_PASS_ZONES,
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

_MAX_PIN_ATTEMPTS = 3
_LOCKOUT_SECONDS = 30


# Enum simple des droits pour piloter les restrictions d'acces IHM.
class AccessLevel:
    """Niveaux d'accès utilisateur."""
    NONE       = 0  # Machine verrouillée
    OPERATEUR  = 1  # Opérateur — production (lecture seule)
    TECHNICIEN = 2  # Technicien — PM, RAZ, réglages (sauf Extras)
    ADMIN      = 3  # Admin — accès total

# ---------------------------------------------------------------------------
# Palette de couleurs — thème clair minimaliste
# ---------------------------------------------------------------------------
COLORS = {
    "bg_main":       "#F0EDE6",
    "panel_bg":      "#E8E4DC",
    "bg_button":     "#FAFAF8",
    "text_primary":  "#1A1A18",
    "text_secondary": "#4A4844",
    "border":        "#C8C4BC",
    "separator":     "#C8C4BC",
    "blue":          "#C49A3C",
    "nav_active":    "#8B6520",
    "settings_btn":  "#A07830",
    "export_btn":    "#F1F8E9",
    "ok_bg":         "#E8F5E9",
    "ok_text":       "#2E7D32",
    "ok_border":     "#2E7D32",
    "nok_bg":        "#FFEBEE",
    "nok_text":      "#C62828",
    "nok_border":    "#C62828",
    "running_bg":    "#F7E8CC",
    "running_border": "#C49A3C",
    "curve_ok":      "#2E7D32",
    "curve_nok":     "#C62828",
    "alarm":         "#C62828",
    "idle_bg":       "#FAFAF8",
    "idle_text":     "#1A1A18",
    "win_idle":      "#F0EDE6",
    "win_running":   "#E8E4DC",
    "win_ok":        "#F1F8E9",
    "win_nok":       "#FFF3F3",
    "raz_btn":       "#FFF3F3",
    "bg_graph":      "#FFFFFF",
    "nopass_border": "#C62828",
    # Clés graphique (fallbacks si set_theme non appelé)
    "grid":          "#E0DDD6",
    "axis_text":     "#4A4844",
    "curve_live":    "#C49A3C",
    "curve_history": "#9C9890",
    "unibox_border": "#1565C0",
    "envelope_border": "#1565C0",
    "tool_no_pass":  "#C62828",
    "tool_unibox":   "#1565C0",
    "tool_envelope": "#1565C0",
}


# Retourne le dictionnaire de couleurs actif partage par toute l'IHM.
def get_colors() -> dict[str, str]:
    """Retourne la palette active."""
    return COLORS


# Convertit une valeur de force interne en Newton vers l'affichage en daN.
def n_to_dan(force_n: float) -> float:
    """Convertit une force interne en N vers daN pour l'affichage UI."""
    return force_n / 10.0


# Formate directement une force (N) en texte daN avec la precision voulue.
def fmt_force_dan(force_n: float, decimals: int = 1) -> str:
    """Formate une force interne en N au format daN."""
    return f"{n_to_dan(force_n):.{decimals}f}"


_PIN_CODE = "1234"
_MAX_PIN_ATTEMPTS = 3
_LOCKOUT_SECONDS = 30

# ---------------------------------------------------------------------------
# Feuille de style globale QSS
# ---------------------------------------------------------------------------
STYLESHEET = f"""
/* Fenetre principale + widget central de l'application. */

QMainWindow, QWidget#central {{
    background-color: {COLORS['bg_main']};
    color: {COLORS['text_primary']};
    font-family: 'Segoe UI', Arial, sans-serif;
}}
/* Style de base applique a tous les textes QLabel de l'IHM (hors labels specialises). */

QLabel {{
    background-color: transparent;
    font-size: 14px;
    font-weight: 500;
}}
/* Badge central PASS/NOK/EN COURS dans le panneau droit. */

QLabel#result_label {{
    font-size: 44px;
    font-weight: bold;
    border-radius: 10px;
    padding: 8px;
}}
/* Compteurs OK/NOK/TOTAL juste sous le badge resultat. */

QLabel#counter_ok   {{ color: {COLORS['ok_text']}; font-size: 22px; font-weight: bold; }}
QLabel#counter_nok  {{ color: {COLORS['nok_text']}; font-size: 22px; font-weight: bold; }}
QLabel#counter_tot  {{ color: {COLORS['text_primary']}; font-size: 22px; font-weight: bold; }}
/* Date/heure en bas du panneau droit. */
QLabel#datetime_label {{ font-size: 13px; color: {COLORS['text_secondary']}; }}
/* Titre PM + valeur PM cliquable dans la zone PM. */
QLabel#pm_section_title {{ font-size: 15px; font-weight: bold; color: {COLORS['blue']}; }}
QLabel#pm_btn_label {{ font-size: 17px; font-weight: bold; color: {COLORS['text_primary']}; }}
/* Labels mesures live (force/position) et pics Fmax/Xmax. */
QLabel#live_label   {{ font-size: 13px; font-weight: 600; color: {COLORS['text_secondary']}; }}
QLabel#live_value   {{ font-size: 38px; font-weight: bold; color: {COLORS['text_primary']}; }}
QLabel#peak_label   {{ font-size: 13px; font-weight: 600; color: {COLORS['text_secondary']}; }}
QLabel#peak_value   {{ font-size: 24px; font-weight: bold; color: {COLORS['blue']}; }}

/* Barres de progression live force/position dans le panneau droit. */
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

/* Style de base de tous les boutons de l'IHM. */
QPushButton {{
    transition: none;
    border: 1.5px solid #1A1A18;
}}
QPushButton:pressed {{
    padding-top: 2px;
    padding-left: 2px;
}}
/* Bouton PM dans la ligne date/heure (selection programme). */
QPushButton#btn_pm {{
    background-color: {COLORS['bg_button']};
    color: {COLORS['text_primary']};
    font-size: 15px;
    font-weight: bold;
    border-top: 2px solid #1A1A18;
    border-right: 2px solid #1A1A18;
    border-bottom: 2px solid #1A1A18;
    border-left: 2px solid #1A1A18;
    border-radius: 0px;
    padding: 4px 8px;
    text-align: left;
}}
QPushButton#btn_pm:pressed {{ background-color: {COLORS['nav_active']}; }}

/* Bouton Reglages en bas du panneau droit. */
QPushButton#btn_settings {{
    background-color: #A07830;
    color: #1A1A18;
    font-size: 13px;
    font-weight: bold;
    border-top: 2px solid #1A1A18;
    border-right: 2px solid #1A1A18;
    border-bottom: 2px solid #1A1A18;
    border-left: 2px solid #1A1A18;
    border-radius: 0px;
    min-height: 36px;
    padding: 0 8px;
}}
QPushButton#btn_settings:hover {{
    background-color: #8B6520;
    color: #1A1A18;
}}
QPushButton#btn_settings:pressed {{
    background-color: #6B4A10;
    color: #1A1A18;
    padding-top: 2px;
}}

/* Boutons navigation bas (courbe, historique, donnees, stats, etc.). */
QPushButton#nav_btn {{
    background-color: #FAFAF8;
    color: #1A1A18;
    font-size: 14px;
    font-weight: 600;
    border: 1px solid #888480;
    border-radius: 4px;
    min-height: 48px;
    padding: 0 4px;
}}
QPushButton#nav_btn:checked {{
    background-color: #7A5A20;
    color: #FFFFFF;
    border: 1px solid #A07830;
}}
QPushButton#nav_btn:pressed {{
    background-color: #E8E4DC;
    padding-top: 2px;
}}
QPushButton#nav_btn:checked:pressed {{
    background-color: #7A5A20;
}}

/* Bouton navigation rouge (RAZ compteurs). */
QPushButton#nav_btn_red {{
    background-color: #FFF3F3;
    color: #C62828;
    font-size: 14px;
    font-weight: 600;
    border: 1px solid #C62828;
    border-radius: 4px;
    min-height: 48px;
    padding: 0 4px;
}}
QPushButton#nav_btn_red:pressed {{
    background-color: #FFEBEE;
    padding-top: 2px;
}}
"""

# ---------------------------------------------------------------------------
# Style du dialogue PIN
# ---------------------------------------------------------------------------
PINSTYLE = """
/* Boite de dialogue PIN globale. */
QDialog { background-color: #FAFAF8; }
/* Libelles du dialogue PIN. */
QLabel  { color: #2C2C2A; font-size: 15px; }
/* Champ de saisie PIN masque. */
QLineEdit {
    background-color: #FFFFFF;
    color: #2C2C2A;
    border: 2px solid #E8E4DC;
    border-radius: 8px;
    font-size: 28px;
    padding: 8px;
    letter-spacing: 12px;
}
QLineEdit:focus { border-color: #C49A3C; }
/* Boutons du dialogue PIN (valider/annuler/ouvrir clavier). */
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

# Widget de rendu graphique live + historique avec overlays des zones outils.
class GraphWidget(QWidget):
    """Tracé temps réel Force=f(Position) ou f(t), rendu par QPainter."""

    _GRID_DIVS = 5
    # Marges internes (pixels)
    _MIN_LEFT_MARGIN = 56
    _ML, _MR, _MT, _MB = _MIN_LEFT_MARGIN, 15, 15, 35

    # Initialise l'etat du widget de trace et ses buffers de cycle.
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(400, 300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAutoFillBackground(False)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)

        self._current_points: list[tuple[float, float, float]] = []
        self._history: collections.deque[tuple[list, str]] = collections.deque(maxlen=20)
        self._display_mode: DisplayMode = DisplayMode.FORCE_POSITION
        self._history_mode: bool = False
        self._tools: list[EvaluationTool] = []
        self._tools_config: dict = {}
        self._current_result: str | None = None
        self._auto_scale: bool = False
        self._manual_axis_bounds: bool = False
        self._x_min: float = 0.0
        self._x_max: float = float(POSITION_MM_MAX)
        self._y_min: float = 0.0
        self._y_max: float = float(FORCE_NEWTON_MAX)
        self._edit_mode: bool = False
        self._edit_handles: list[dict] = []
        self._dragging_handle: dict | None = None
        self._drag_start_px: tuple[int, int] = (0, 0)
        self._tools_config_backup = None

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    # Injecte la liste des outils d'evaluation a dessiner sur le graphe.
    def set_tools(self, tools: list[EvaluationTool]) -> None:
        self._tools = tools
        self.update()

    # Charge la configuration YAML des zones et recalcule les poignees si besoin.
    def set_tools_config(self, tools_config: dict) -> None:
        """Charge la configuration des outils depuis config.yaml (dict brut)."""
        self._tools_config = tools_config
        if self._edit_mode:
            self._compute_handles()
        self.update()

    # Change le mode d'affichage (F-X, F-t, X-t) et vide la courbe courante.
    def set_display_mode(self, mode: DisplayMode) -> None:
        self._display_mode = mode
        self.reset_axis_bounds(redraw=False)
        self._current_points.clear()
        self.update()

    # Active/desactive le rendu historique des cycles precedents.
    def set_history_mode(self, enabled: bool) -> None:
        self._history_mode = enabled
        self.update()

    # Bascule l'auto-echelle pour adapter dynamiquement les axes.
    def toggle_auto_scale(self) -> None:
        self._auto_scale = not self._auto_scale
        if self._auto_scale:
            self._manual_axis_bounds = False
        self.update()

    # Recale manuellement les axes sur la courbe actuellement visible.
    def auto_scale_current_curve(self) -> None:
        self._auto_scale = False
        points: list[tuple[float, float, float]] = []
        if self._current_points:
            points = self._current_points
        elif self._history_mode and self._history:
            for pts, _ in self._history:
                points.extend(pts)

        if not points:
            self.reset_axis_bounds()
            return

        positions: list[float] = []
        forces: list[float] = []
        for point in points:
            try:
                if len(point) != 3:
                    continue
                _t, f, x = float(point[0]), float(point[1]), float(point[2])
                positions.append(x)
                forces.append(f)
            except (TypeError, ValueError):
                continue

        if not positions or not forces:
            self.reset_axis_bounds()
            return

        self._x_min = min(positions)
        self._x_max = max(positions)
        if self._x_max <= self._x_min:
            self._x_max = self._x_min + 1.0

        self._y_min = 0.0
        self._y_max = max(max(forces) * 1.10, 1.0)
        self._manual_axis_bounds = True
        self._auto_scale = False
        self.update()

    # Restaure les bornes d'axes par defaut.
    def reset_axis_bounds(self, redraw: bool = True) -> None:
        self._manual_axis_bounds = False
        self._x_min = 0.0
        self._x_max = float(POSITION_MM_MAX)
        self._y_min = 0.0
        self._y_max = float(FORCE_NEWTON_MAX)
        if redraw:
            self.update()

    # Active/desactive le mode edition des zones et prepare les poignees.
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

    # Detecte la prise d'une poignee quand l'utilisateur clique en mode edition.
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

    # Deplace la poignee selectionnee et propage la mise a jour des coords.
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
        x_min, x_max, y_min, y_max = self._get_axis_bounds()
        xr = max(x_max - x_min, 1.0)
        yr = max(y_max - y_min, 1.0)

        px = max(rect.left(), min(px, rect.right()))
        py = max(rect.top(), min(py, rect.bottom()))

        new_x = x_min + (px - rect.left()) / rect.width() * xr
        new_y = y_max - (py - rect.top()) / rect.height() * yr
        new_x = max(0.0, round(new_x, 1))
        new_y = max(0.0, round(new_y, 0))

        h = self._dragging_handle
        self._apply_handle_drag(h, new_x, new_y)

        self._compute_handles()
        self.update()
        main_win = self.window()
        if hasattr(main_win, '_refresh_edit_panel'):
            main_win._refresh_edit_panel()

    # Termine le glisser-deposer de poignee sur relachement du clic gauche.
    def mouseReleaseEvent(self, event) -> None:
        if not self._edit_mode:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging_handle = None
            self.setCursor(Qt.CursorShape.ArrowCursor)

    # Ajoute un lot de points recus depuis le buffer de rafraichissement.
    def add_points(self, points: list[tuple[float, float, float]]) -> None:
        """Ajoute les points du buffer (appelé par le timer 30 fps)."""
        self._current_points.extend(points)
        self.update()

    # Cloture le cycle courant, l'archive en historique et nettoie la courbe live.
    def finish_cycle(self, result: str) -> None:
        """Clôture le cycle courant dans l'historique."""
        if self._current_points:
            self._history.append((list(self._current_points), result))
        self._current_result = result
        self._current_points.clear()
        self.update()

    # Reinitialise l'etat graphique pour demarrer un nouveau cycle propre.
    def start_new_cycle(self) -> None:
        self._current_points.clear()
        self._current_result = None
        self.update()

    # ------------------------------------------------------------------
    # Géométrie
    # ------------------------------------------------------------------

    # Retourne la zone de trace utile en retirant les marges d'axes.
    def _plot_rect(self) -> QRect:
        w = max(1, self.width()  - self._ML - self._MR)
        h = max(1, self.height() - self._MT - self._MB)
        return QRect(self._ML, self._MT, w, h)

    # Recalcule la marge gauche selon la largeur maximale des labels Y.
    def _update_left_margin(self) -> None:
        """Ajuste la marge gauche selon le label Y le plus large."""
        axis_font = QFont("Arial", 9)
        fm = QFontMetrics(axis_font)

        _x_min, _x_max, y_min, y_max = self._get_axis_bounds()
        yr = y_max - y_min
        if self._display_mode == DisplayMode.POSITION_TIME:
            y_labels = [
                f"{(y_min + i * yr / self._GRID_DIVS):.0f}"
                for i in range(self._GRID_DIVS + 1)
            ]
        else:
            y_labels = [
                fmt_force_dan(y_min + i * yr / self._GRID_DIVS)
                for i in range(self._GRID_DIVS + 1)
            ]
            # Garantit qu'un label de référence large reste visible en mode force.
            y_labels.append(fmt_force_dan(10000.0))

        max_label_width = max((fm.horizontalAdvance(lbl) for lbl in y_labels), default=0)
        self._ML = max(self._MIN_LEFT_MARGIN, max_label_width + 8)

    # Donne les bornes X/Y actives selon le mode, l'auto-echelle et le recalage manuel.
    def _get_axis_bounds(self) -> tuple[float, float, float, float]:
        if self._display_mode == DisplayMode.FORCE_POSITION:
            x_min, x_max = 0.0, float(POSITION_MM_MAX)
            y_min, y_max = 0.0, float(FORCE_NEWTON_MAX)

            if self._manual_axis_bounds:
                x_min, x_max = self._x_min, self._x_max
                y_min, y_max = self._y_min, self._y_max
            elif self._auto_scale and self._current_points:
                max_f = max(f for _, f, _ in self._current_points)
                max_x = max(x for _, _, x in self._current_points)
                y_max = max(max_f * 1.15, 100.0)
                x_max = max(max_x * 1.15, 1.0)
        elif self._display_mode == DisplayMode.FORCE_TIME:
            x_min, x_max = 0.0, 2.0
            y_min, y_max = 0.0, float(FORCE_NEWTON_MAX)

            if self._auto_scale and self._current_points:
                max_f = max(f for _, f, _ in self._current_points)
                y_max = max(max_f * 1.15, 100.0)
        else:
            x_min, x_max = 0.0, 2.0
            y_min, y_max = 0.0, float(POSITION_MM_MAX)

            if self._auto_scale and self._current_points:
                max_x = max(x for _, _, x in self._current_points)
                y_max = max(max_x * 1.15, 1.0)

        if x_max <= x_min:
            x_max = x_min + 1.0
        if y_max <= y_min:
            y_max = y_min + 1.0

        return x_min, x_max, y_min, y_max

    # Donne les bornes max X/Y actives pour la logique existante (zones, presets).
    def _get_ranges(self) -> tuple[float, float]:
        _x_min, x_max, _y_min, y_max = self._get_axis_bounds()
        return x_max, y_max

    # Convertit un point brut (t, F, X) vers les coordonnees du mode courant.
    def _pt_to_data(self, t: float, f: float, x: float) -> tuple[float, float]:
        if self._display_mode == DisplayMode.FORCE_POSITION:
            return x, f
        if self._display_mode == DisplayMode.FORCE_TIME:
            return t, f
        return t, x

    # Convertit une coordonnee metier (X/Y) en pixel dans le rectangle de trace.
    def _to_px(self, xd: float, yd: float, rect: QRect) -> tuple[int, int]:
        x_min, x_max, y_min, y_max = self._get_axis_bounds()
        xr = max(x_max - x_min, 1.0)
        yr = max(y_max - y_min, 1.0)
        px = rect.left() + (xd - x_min) / xr * rect.width()
        py = rect.bottom() - (yd - y_min) / yr * rect.height()
        return int(px), int(py)

    # Applique la palette de theme au graphe puis force un redraw.
    def set_theme(self, colors: dict) -> None:
        """Met à jour les couleurs du graphique."""
        self._colors = colors
        self.update()

    # Lit une couleur du theme actif avec fallback sur la palette par defaut.
    def _get_color(self, key: str) -> str:
        if hasattr(self, "_colors") and self._colors:
            return self._colors.get(key, COLORS.get(key, "#FFFFFF"))
        return COLORS.get(key, "#FFFFFF")

    # ------------------------------------------------------------------
    # paintEvent
    # ------------------------------------------------------------------

    # Orchestre tout le rendu: fond, axes, grille, zones et courbes.
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            self._update_left_margin()

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
                    c_hist = self._get_color("curve_history")
                    if not c_hist or c_hist in ("#FFFFFF", ""):
                        c_hist = "#9C9890"
                    self._draw_curve(painter, pts, QColor(c_hist), rect)
                if self._history:
                    pts, res = self._history[-1]
                    if res == "PASS":
                        c = self._get_color("curve_ok")
                        if not c or c in ("#FFFFFF", ""):
                            c = "#2E7D32"
                    else:
                        c = self._get_color("curve_nok")
                        if not c or c in ("#FFFFFF", ""):
                            c = "#C62828"
                    self._draw_curve(painter, pts, QColor(c), rect)
            elif self._current_points:
                if self._current_result == "PASS":
                    c_ok = self._get_color("curve_ok")
                    if not c_ok or c_ok in ("#FFFFFF", ""):
                        c_ok = "#2E7D32"
                    color = QColor(c_ok)
                elif self._current_result == "NOK":
                    c_nok = self._get_color("curve_nok")
                    if not c_nok or c_nok in ("#FFFFFF", ""):
                        c_nok = "#C62828"
                    color = QColor(c_nok)
                else:
                    c_live = self._get_color("curve_live")
                    if not c_live or c_live in ("#FFFFFF", ""):
                        c_live = "#C49A3C"
                    color = QColor(c_live)
                self._draw_curve(painter, self._current_points, color, rect)

            painter.restore()

            # Labels axes (hors clip)
            self._draw_axes(painter, rect)
        except Exception as e:
            print(f"[GRAPH] paintEvent error: {e}")
        finally:
            painter.end()

    # Dessine les deux axes principaux du repere (Y puis X).
    def _draw_axis_lines(self, painter: QPainter, rect: QRect) -> None:
        pen = QPen(QColor("#9C9890"), 1, Qt.PenStyle.SolidLine)
        painter.setPen(pen)
        painter.drawLine(rect.left(), rect.top(), rect.left(), rect.bottom())
        painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())

    # Trace la grille interieure pour faciliter la lecture des valeurs.
    def _draw_grid(self, painter: QPainter, rect: QRect) -> None:
        grid_color = self._get_color("grid")
        if not grid_color or grid_color in ("#FFFFFF", ""):
            grid_color = "#E0DDD6"
        pen = QPen(QColor(grid_color), 1, Qt.PenStyle.SolidLine)
        painter.setPen(pen)
        for i in range(1, self._GRID_DIVS):
            x = rect.left() + int(i * rect.width() / self._GRID_DIVS)
            painter.drawLine(x, rect.top(), x, rect.bottom())
            y = rect.top() + int(i * rect.height() / self._GRID_DIVS)
            painter.drawLine(rect.left(), y, rect.right(), y)

    # Dessine la polyline d'une courbe de points (live ou historique).
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

    # Dessine les zones d'evaluation (No-Pass/Uni-Box/Envelope) et les poignees d'edition.
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
            # NO-PASS : lm=1  tm=2  rm=3  (pas de bm)
            _NP_MID_NUMS = {"lm": 1, "tm": 2, "rm": 3}
            # UNI-BOX : lm=1  tm=2  rm=3  bm=4
            _UB_MID_NUMS = {"lm": 1, "tm": 2, "rm": 3, "bm": 4}
            _CORNERS = {"tl", "tr", "bl", "br"}
            font_num  = QFont("Arial", 10, QFont.Weight.Bold)
            font_zone = QFont("Arial", 11, QFont.Weight.Bold)

            # Label Zn (NO-PASS) dans le coin supérieur gauche de chaque zone active
            np_zones = self._tools_config.get("no_pass_zones", [])
            for zone_idx, zone in enumerate(np_zones):
                if not zone.get("enabled"):
                    continue
                try:
                    zx1, zy1 = self._to_px(float(zone["x_min"]), float(zone["y_limit"]), rect)
                except (KeyError, TypeError, ValueError):
                    continue
                painter.setPen(QColor("#C62828"))
                painter.setFont(font_zone)
                painter.drawText(zx1 + 4, zy1 - 4, f"Z{zone_idx + 1}")

            # Label UBn (UNI-BOX) dans le coin supérieur gauche de chaque zone active
            ub_zones_edit = self._tools_config.get("uni_box_zones", [])
            for zone_idx, zone in enumerate(ub_zones_edit):
                if not zone.get("enabled"):
                    continue
                try:
                    ux1, uy1 = self._to_px(float(zone["box_x_min"]), float(zone["box_y_max"]), rect)
                except (KeyError, TypeError, ValueError):
                    continue
                painter.setPen(QColor("#FF9800"))
                painter.setFont(font_zone)
                painter.drawText(ux1 + 4, uy1 - 4, f"UB{zone_idx + 1}")

            # Poignées
            for handle in self._edit_handles:
                px, py = self._to_px(handle["x_data"], handle["y_data"], rect)
                handle["px"] = px
                handle["py"] = py
                hid = handle["handle_id"]
                zone_type = handle["zone_type"]
                is_corner = hid in _CORNERS

                # Cercle : rayon 5 pour coins, rayon 7 pour milieux
                painter.setPen(QPen(QColor("#C49A3C"), 2))
                painter.setBrush(QBrush(QColor("#FFFFFF")))
                if is_corner:
                    painter.drawEllipse(px - 5, py - 5, 10, 10)
                else:
                    painter.drawEllipse(px - 7, py - 7, 14, 14)

                # Numéro positionné hors de la forme (milieux seulement)
                if not is_corner:
                    mid_nums = _NP_MID_NUMS if zone_type == "no_pass" else _UB_MID_NUMS
                    num = mid_nums.get(hid, 0)
                    if num > 0:
                        if hid == "lm":
                            px_num, py_num = px - 18, py + 4
                        elif hid == "tm":
                            px_num, py_num = px - 4,  py - 14
                        elif hid == "rm":
                            px_num, py_num = px + 10, py + 4
                        else:  # bm
                            px_num, py_num = px - 4,  py + 16
                        # Fond blanc lisible
                        painter.fillRect(px_num - 2, py_num - 12, 14, 14,
                                         QColor(255, 255, 255, 200))
                        painter.setPen(QColor("#C49A3C"))
                        painter.setFont(font_num)
                        painter.drawText(px_num, py_num, str(num))

    # Recalcule toutes les poignees manipulables depuis la config des zones.
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
                ("tm", (x1 + x2) / 2.0, y1),
                ("lm", x1, y2),
                ("rm", x2, y2),
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

        ub_zones = self._tools_config.get("uni_box_zones", [])
        # Compatibilité ancien format
        if not ub_zones and self._tools_config.get("uni_box", {}).get("enabled"):
            ub_zones = [self._tools_config["uni_box"]]

        for zone_idx, zone in enumerate(ub_zones):
            if not zone.get("enabled"):
                continue
            x1 = float(zone.get("box_x_min", 0))
            x2 = float(zone.get("box_x_max", 0))
            y1 = float(zone.get("box_y_max", 0))
            y2 = float(zone.get("box_y_min", 0))

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
                        "zone_idx": zone_idx,
                        "handle_id": handle_id,
                        "x_data": x_data,
                        "y_data": y_data,
                        "px": 0,
                        "py": 0,
                    }
                )

    # Applique le deplacement d'une poignee en mettant a jour la zone correspondante.
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
            zones = self._tools_config.get("uni_box_zones", [])
            if zone_idx >= len(zones):
                return
            ub = zones[zone_idx]

            if hid in ("tl", "bl", "lm"):
                ub["box_x_min"] = min(new_x, ub["box_x_max"] - 1.0)
            if hid in ("tr", "br", "rm"):
                ub["box_x_max"] = max(new_x, ub["box_x_min"] + 1.0)
            if hid in ("tl", "tr", "tm"):
                ub["box_y_max"] = max(new_y, ub["box_y_min"] + 1.0)
            if hid in ("bl", "br", "bm"):
                ub["box_y_min"] = min(new_y, ub["box_y_max"] - 1.0)

    # Dessine les overlays a partir du dictionnaire tools lu depuis config.yaml.
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

        ub_zones = self._tools_config.get("uni_box_zones", [])
        # Compatibilité ancien format
        if not ub_zones and self._tools_config.get("uni_box", {}).get("enabled"):
            ub_zones = [self._tools_config["uni_box"]]

        font_ub = QFont("Arial", 11, QFont.Weight.Bold)
        for zone_idx, ub_d in enumerate(ub_zones):
            if not ub_d.get("enabled"):
                continue
            x1, y1 = self._to_px(ub_d["box_x_min"], ub_d["box_y_max"], rect)
            x2, y2 = self._to_px(ub_d["box_x_max"], ub_d["box_y_min"], rect)
            fill_ub = QColor(255, 152, 0, 40)
            painter.fillRect(x1, y1, x2 - x1, y2 - y1, fill_ub)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(self._get_color("unibox_border")), 2, Qt.PenStyle.DashLine))
            painter.drawRect(x1, y1, x2 - x1, y2 - y1)
            painter.setPen(QColor("#FF9800"))
            painter.setFont(font_ub)
            painter.drawText(x1 + 4, y1 - 4, f"UB{zone_idx + 1}")

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

    # Dessine la zone d'exclusion NO-PASS (surface rouge semi-transparente).
    def _draw_no_pass(self, painter: QPainter, tool: EvaluationTool, rect: QRect) -> None:
        if None in (tool.x_min, tool.x_max, tool.y_limit):
            return
        _xr, yr = self._get_ranges()
        x1, y1 = self._to_px(tool.x_min, yr, rect)
        x2, y2 = self._to_px(tool.x_max, tool.y_limit, rect)
        color = QColor(self._get_color("tool_no_pass"))
        color.setAlpha(80)
        painter.fillRect(x1, y1, x2 - x1, y2 - y1, color)

    # Dessine le rectangle UNI-BOX (contour pointille).
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

    # Dessine les deux courbes de l'enveloppe de tolerance.
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

    # Dessine les labels des axes et les unites affichees une seule fois.
    def _draw_axes(self, painter: QPainter, rect: QRect) -> None:
        x_min, x_max, y_min, y_max = self._get_axis_bounds()
        xr = x_max - x_min
        yr = y_max - y_min
        x_unit = "mm" if self._display_mode == DisplayMode.FORCE_POSITION else "s"
        y_unit = "mm" if self._display_mode == DisplayMode.POSITION_TIME else "daN"

        _axis_font = QFont("Arial", 9)
        painter.setFont(_axis_font)
        axis_color = self._get_color("axis_text")
        if not axis_color or axis_color in ("#FFFFFF", ""):
            axis_color = "#4A4844"
        painter.setPen(QColor(axis_color))

        # 6 valeurs (GRID_DIVS + 1)
        for i in range(self._GRID_DIVS + 1):
            # Labels Y — alignés à droite dans la marge gauche
            val_y = y_min + i * yr / self._GRID_DIVS
            py = rect.bottom() - int(i * rect.height() / self._GRID_DIVS)
            lbl_y = f"{val_y:.0f}" if y_unit == "mm" else fmt_force_dan(val_y)
            painter.drawText(QRect(0, py - 10, self._ML - 4, 20), Qt.AlignmentFlag.AlignRight, lbl_y)

            # Labels X — centrés sous chaque graduation
            val_x = x_min + i * xr / self._GRID_DIVS
            px = rect.left() + int(i * rect.width() / self._GRID_DIVS)
            lbl_x = f"{val_x:.0f}"
            painter.drawText(QRect(px - 20, rect.bottom() + 4, 40, 16), Qt.AlignmentFlag.AlignCenter, lbl_x)

        # Unités affichées une seule fois près des axes.
        painter.drawText(
            QRect(rect.left() + 4, max(0, rect.top() - 14), 60, 14),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            f"({y_unit})",
        )
        painter.drawText(
            QRect(rect.right() - 48, rect.bottom() + 18, 48, 14),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            f"({x_unit})",
        )


# ===========================================================================
# NumpadDialog — pavé numérique tactile modal
# ===========================================================================

# Dialogue clavier numerique pour saisir une valeur sans clavier physique.
class NumpadDialog(QDialog):
    """Pavé numérique tactile modal — retourne une valeur float ou str.

    Usage :
        dlg = NumpadDialog(title="Seuil force", unit="N", value="4200.0", parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            val = dlg.value()  # str
    """

    # Construit la fenetre de saisie numerique et applique son style local.
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
            /* Fond du dialogue numpad. */
            QDialog { background-color: #FAFAF8; }
            /* Libelle de titre en haut du numpad. */
            QLabel#numpad_title {
                color: #6B6860; font-size: 13px; font-weight: 600;
            }
            /* Libelle unite a droite du champ de saisie. */
            QLabel#numpad_unit {
                color: #6B6860; font-size: 13px;
            }
            /* Afficheur principal de la valeur numerique. */
            QLineEdit#numpad_display {
                background-color: #FFFFFF;
                color: #2C2C2A;
                border: 2px solid #C49A3C;
                border-radius: 8px;
                font-size: 28px;
                font-weight: bold;
                padding: 8px 12px;
                min-height: 52px;
            }
            /* Touches numeriques standard. */
            QPushButton#numpad_key {
                background-color: #FFFFFF;
                color: #2C2C2A;
                font-size: 20px;
                font-weight: bold;
                border: 1px solid #E8E4DC;
                border-radius: 8px;
                min-height: 56px;
            }
            QPushButton#numpad_key:pressed { background-color: #A07830; color: #ffffff; }
            /* Touche retour arriere du numpad. */
            QPushButton#numpad_backspace {
                background-color: #FFF3F3;
                color: #C62828;
                font-size: 18px;
                font-weight: bold;
                border: 1px solid #C62828;
                border-radius: 8px;
                min-height: 56px;
            }
            QPushButton#numpad_backspace:pressed { background-color: #C62828; color: #ffffff; }
            /* Bouton de validation de la saisie. */
            QPushButton#numpad_ok {
                background-color: #F1F8E9;
                color: #2E7D32;
                font-size: 18px;
                font-weight: bold;
                border: 2px solid #2d7a2d;
                border-radius: 8px;
                min-height: 56px;
            }
            QPushButton#numpad_ok:pressed { background-color: #2d7a2d; color: #ffffff; }
            /* Bouton d'annulation du dialogue. */
            QPushButton#numpad_cancel {
                background-color: #FFF3F3;
                color: #C62828;
                font-size: 18px;
                font-weight: bold;
                border: 1px solid #C62828;
                border-radius: 8px;
                min-height: 56px;
            }
            QPushButton#numpad_cancel:pressed { background-color: #C62828; color: #ffffff; }
        """)
        self._build_ui(title, unit, value)

    # Construit toute la grille des touches et le champ d'affichage.
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

    # Ajoute un caractere saisi dans l'afficheur (en evitant les doubles points).
    def _key_press(self, char: str) -> None:
        current = self._display.text()
        if char == "." and "." in current:
            return
        self._display.setText(current + char)

    # Supprime le dernier caractere de la valeur courante.
    def _backspace(self) -> None:
        self._display.setText(self._display.text()[:-1])

    # Retourne la valeur finale saisie dans le numpad.
    def value(self) -> str:
        return self._display.text()


# ===========================================================================
# AlphaNumpadDialog — clavier alphanumérique tactile modal
# ===========================================================================

# Dialogue clavier alphanumerique tactile pour saisir des noms/codes texte.
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
            /* Fond principal du dialogue alphanumerique. */
            QDialog { background-color: #FAFAF8; }
            /* Libelles du dialogue (titre/infos). */
            QLabel { color: #6B6860; font-size: 13px; font-weight: 600; }
            /* Champ d'affichage du texte saisi. */
            QLineEdit#alpha_display {
                background-color: #FFFFFF;
                color: #2C2C2A;
                border: 2px solid #C49A3C;
                border-radius: 8px;
                font-size: 22px;
                font-weight: bold;
                padding: 8px 12px;
                min-height: 48px;
            }
            /* Touches alpha et numeriques standard. */
            QPushButton#alpha_key {
                background-color: #FFFFFF;
                color: #2C2C2A;
                font-size: 16px;
                font-weight: bold;
                border: 1px solid #E8E4DC;
                border-radius: 6px;
                min-height: 48px;
                min-width: 48px;
            }
            QPushButton#alpha_key:pressed { background-color: #A07830; color: #ffffff; }
            /* Touches speciales (retour arriere). */
            QPushButton#alpha_special {
                background-color: #FFF3F3;
                color: #C62828;
                font-size: 14px;
                font-weight: bold;
                border: 1px solid #C62828;
                border-radius: 6px;
                min-height: 48px;
            }
            QPushButton#alpha_special:pressed { background-color: #C62828; color: #ffffff; }
            /* Bouton OK pour valider la saisie. */
            QPushButton#alpha_ok {
                background-color: #F1F8E9;
                color: #2E7D32;
                font-size: 16px;
                font-weight: bold;
                border: 2px solid #2d7a2d;
                border-radius: 6px;
                min-height: 48px;
            }
            QPushButton#alpha_ok:pressed { background-color: #2d7a2d; color: #ffffff; }
            /* Bouton annuler du dialogue. */
            QPushButton#alpha_cancel {
                background-color: #FFF3F3;
                color: #C62828;
                font-size: 16px;
                font-weight: bold;
                border: 1px solid #C62828;
                border-radius: 6px;
                min-height: 48px;
            }
        """)
        self._build_ui(title, value)

    # Construit la disposition complete des rangées alpha + numeriques.
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

    # Ajoute un caractere dans le champ texte courant.
    def _key_press(self, char: str) -> None:
        self._display.setText(self._display.text() + char)

    # Retire le dernier caractere saisi.
    def _backspace(self) -> None:
        self._display.setText(self._display.text()[:-1])

    # Retourne le texte final saisi par l'utilisateur.
    def value(self) -> str:
        return self._display.text()


# ===========================================================================
# PmSelectorDialog — sélecteur de Programme de Mesure
# ===========================================================================

_PM_SELECTOR_STYLE = f"""
/* Fenetre du selecteur de programme de mesure (PM). */
QDialog {{
    background-color: {COLORS['panel_bg']};
    color: {COLORS['text_primary']};
}}
/* Titre principal du dialogue PM. */
QLabel#title {{
    font-size: 18px;
    font-weight: bold;
    color: {COLORS['text_primary']};
    padding: 4px 0 12px 0;
}}
/* Tuile PM standard (non active). */
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
    background-color: #F5EDD6;
    border-color: #C49A3C;
}}
/* Tuile PM active (programme actuellement selectionne). */
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
    background-color: #F1F8E9;
}}
/* Bouton annuler en bas du selecteur PM. */
QPushButton#btn_cancel {{
    background-color: {COLORS['border']};
    color: {COLORS['text_primary']};
    border: 1px solid #C8C4BC;
    border-radius: 6px;
    font-size: 14px;
    padding: 6px;
}}
QPushButton#btn_cancel:hover {{
    background-color: #E8E4DC;
}}
"""


# Dialogue de selection du programme PM via grille de tuiles.
class PmSelectorDialog(QDialog):
    """Sélecteur PM — grille de tuiles colorées."""

    _PM_COLORS = [
        ("#FAFAF8", "#A07830"),  # or ACM
        ("#FAFAF8", "#1565C0"),  # bleu
        ("#FAFAF8", "#2E7D32"),  # vert
        ("#FAFAF8", "#C62828"),  # rouge
        ("#FAFAF8", "#7A7870"),  # neutre
        ("#FAFAF8", "#A07830"),  # or ACM
        ("#FAFAF8", "#1565C0"),  # bleu
        ("#FAFAF8", "#2E7D32"),  # vert
    ]

    # Initialise le dialogue PM frameless et charge son contenu.
    def __init__(self, current_pm_id: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog
        )
        self.setModal(True)
        self.setFixedSize(700, 500)
        self.setStyleSheet("""
            /* Cadre global du dialogue PM en plein ecran partiel. */
            QDialog {
                background-color: #FAFAF8;
                border: 2px solid #C49A3C;
                border-radius: 12px;
            }
        """)
        self.selected_pm_id: int | None = None
        self._current_pm_id = current_pm_id
        self._build_ui()

    # Construit l'entete, la grille des PM et le bouton d'annulation.
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
            "color: #2E7D32; font-size: 13px;"
            " background: #F1F8E9; border: 1px solid #2E7D32; border-radius: 4px; padding: 4px 8px;"
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
            border_color = "#2E7D32" if is_active else accent
            bg_hover = "#F5EDD6"

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
                    "color: #2E7D32; font-size: 11px;"
                    " background: transparent; font-weight: bold;"
                )
                top_row.addWidget(badge)
            tile_layout.addLayout(top_row)

            pm_name_lbl = QLabel(pm.name)
            pm_name_lbl.setStyleSheet(
                "color: #1A1A18; font-size: 13px; background: transparent;"
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
            /* Style du bouton annuler dans le footer PM selector. */
            QPushButton {
                background-color: #FAFAF8;
                color: #C62828;
                font-size: 14px;
                font-weight: bold;
                border: 1px solid #c62828;
                border-radius: 6px;
            }
            QPushButton:pressed { background-color: #c62828; }
        """)
        btn_cancel.clicked.connect(self.reject)
        root.addWidget(btn_cancel)

    # Définition : sélectionne le PM cliqué puis ferme la fenêtre.
    def _select(self, pm_id: int) -> None:
        self.selected_pm_id = pm_id
        self.accept()


# ===========================================================================
# _TendanceWidget — mini tracé Fmax via QPainter (page stable, pas de transition)
# ===========================================================================

class _TendanceWidget(QWidget):
    """Graphe Fmax par cycle (QPainter autorisé : widget stable, hors transition stack)."""

    _ML, _MR, _MT, _MB = 45, 12, 15, 28

    # Définition : initialise le widget de tendance et son style d'affichage.
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._data: list[float] = []
        self.setFixedHeight(200)
        self.setStyleSheet("background-color: #FAFAF8;")

    # Définition : injecte les données Fmax puis redessine le graphe.
    def set_data(self, fmax_values: list[float]) -> None:
        self._data = fmax_values
        self.update()

    # Définition : dessine la courbe, la grille et les axes de tendance.
    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            w, h = self.width(), self.height()
            ml, mr, mt, mb = self._ML, self._MR, self._MT, self._MB
            pw, ph = w - ml - mr, h - mt - mb

            if len(self._data) < 2:
                p.setPen(QPen(QColor("#7A7870")))
                p.drawText(QRect(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, t("lbl_not_enough_data"))
                return

            # Grille horizontale
            p.setPen(QPen(QColor("#E8E4DC"), 1))
            for i in range(5):
                y = mt + int(ph * i / 4)
                p.drawLine(ml, y, w - mr, y)

            # Labels Y
            font = QFont()
            font.setPointSize(8)
            p.setFont(font)
            p.setPen(QPen(QColor("#4A4844")))
            p.drawText(2, mt + 8, f"{fmt_force_dan(FORCE_NEWTON_MAX)} daN")
            p.drawText(2, h - mb + 5, "0.0 daN")

            # Axes
            p.setPen(QPen(QColor("#C8C4BC"), 1))
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
            p.setPen(QPen(QColor("#C62828"), 1, Qt.PenStyle.DashLine))
            p.drawLine(ml, avg_y, w - mr, avg_y)

            # Courbe Fmax
            p.setPen(QPen(QColor("#1565C0"), 2))
            for i in range(len(pts) - 1):
                p.drawLine(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])

            # Labels X (premier et dernier cycle)
            p.setPen(QPen(QColor("#4A4844")))
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

    # Définition : initialise l'état des statistiques et construit l'UI.
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._n_histo = 50
        self._last_log: list[tuple] = []
        self._build_ui()

    # ------------------------------------------------------------------
    # Construction UI
    # ------------------------------------------------------------------

    # Définition : (re)construit la page statistiques complète.
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
        scroll.setStyleSheet("background-color: #F0EDE6; border: none;")

        content = QWidget()
        content.setStyleSheet("background-color: #F0EDE6;")
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

    # Définition : crée une section "carte" avec titre, séparateur et contenu.
    def _card_section(self, title: str, inner: QWidget) -> tuple[QWidget, QLabel]:
        box = QWidget()
        box.setStyleSheet("background-color: #FAFAF8; border: 1px solid #C8C4BC; border-radius: 8px;")
        v = QVBoxLayout(box)
        v.setContentsMargins(10, 8, 10, 10)
        v.setSpacing(6)
        # QLabel : titre principal de la section.
        lbl = QLabel(title)
        lbl.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #1A1A18; background: transparent;"
        )
        sep = QFrame()
        sep.setObjectName("separator")
        v.addWidget(lbl)
        v.addWidget(sep)
        v.addWidget(inner)
        return box, lbl

    # Définition : construit la section de synthèse (total/OK/NOK/taux).
    def _build_summary_section(self) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        specs = [
            ("total", t("stats_total"),   "#FAFAF8", "#1A1A18", "📊"),
            ("ok",    t("status_ok"),   "#FAFAF8", "#2E7D32", "✅"),
            ("nok",   t("status_nok"),  "#FAFAF8", "#C62828", "❌"),
            ("taux",  t("stats_ok_rate"), "#FAFAF8", "#C49A3C", "📈"),
        ]
        self._card_lbls: dict[str, QLabel] = {}
        for key, name, bg, fg, icon in specs:
            # QFrame : carte visuelle pour un indicateur de synthèse.
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
            # QLabel : icône de l'indicateur (emoji).
            ico = QLabel(icon)
            ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ico.setStyleSheet("font-size: 20px; background: transparent; border: none;")
            # QLabel : valeur numérique de l'indicateur.
            val = QLabel("—")
            val.setAlignment(Qt.AlignmentFlag.AlignCenter)
            val.setStyleSheet(
                f"font-size: 32px; font-weight: bold; color: {fg};"
                " background: transparent; border: none;"
            )
            # QLabel : libellé de l'indicateur.
            sub = QLabel(name)
            sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sub.setStyleSheet("font-size: 13px; color: #4A4844; background: transparent; border: none;")
            fv.addWidget(ico)
            fv.addWidget(val)
            fv.addWidget(sub)
            self._card_lbls[key] = val
            h.addWidget(frame)
        h.addStretch()
        section, _ = self._card_section(t("stats_summary_title"), w)
        return section

    # Définition : construit la section histogramme des cycles.
    def _build_histogram_section(self) -> QWidget:
        wrapper = QWidget()
        v = QVBoxLayout(wrapper)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)

        # QWidget : conteneur des barres de l'histogramme.
        self._bar_container = QWidget()
        self._bar_container.setFixedHeight(120)
        self._bar_container.setStyleSheet(
            "background-color: #FAFAF8; border: 1px solid #C8C4BC; border-radius: 4px;"
        )
        self._bar_layout = QHBoxLayout(self._bar_container)
        self._bar_layout.setContentsMargins(4, 4, 4, 4)
        self._bar_layout.setSpacing(2)
        self._bar_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        v.addWidget(self._bar_container)

        # QWidget : ligne d'actions (infos + bouton de taille d'historique).
        row = QWidget()
        rh = QHBoxLayout(row)
        rh.setContentsMargins(0, 0, 0, 0)
        # QLabel : texte indiquant le nombre de cycles affichés.
        self._histo_info = QLabel(t("lbl_cycles_shown_zero"))
        self._histo_info.setStyleSheet("font-size: 12px; color: #7A7870;")
        rh.addWidget(self._histo_info)
        rh.addStretch()
        # QPushButton : bouton pour faire défiler les tailles d'historique.
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

    # Définition : construit la section de tendance Fmax.
    def _build_tendance_section(self) -> QWidget:
        self._tendance = _TendanceWidget()
        section, self._tendance_title_lbl = self._card_section(t("stats_trend_title"), self._tendance)
        return section

    # Définition : construit la section rebut par plage horaire.
    def _build_rebut_section(self) -> QWidget:
        # QWidget : conteneur interne des lignes de rebut horaire.
        self._rebut_inner = QWidget()
        self._rebut_layout = QVBoxLayout(self._rebut_inner)
        self._rebut_layout.setContentsMargins(0, 0, 0, 0)
        self._rebut_layout.setSpacing(4)
        section, _ = self._card_section(t("stats_scrap_hour_title"), self._rebut_inner)
        return section

    # Définition : construit la table de détail des cycles NOK.
    def _build_nok_table_section(self) -> QWidget:
        # QTableWidget : tableau des entrées NOK (5 colonnes).
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
            "QTableWidget { background-color: #FAFAF8; color: #1A1A18;"
            " gridline-color: #C8C4BC; alternate-background-color: #F0EDE6; }"
            "QHeaderView::section { background-color: #E8E4DC; color: #4A4844;"
            " border: 1px solid #C8C4BC; padding: 4px; }"
        )
        self._nok_table.horizontalHeader().setDefaultSectionSize(110)
        section, self._nok_title_lbl = self._card_section(t("stats_nok_details_title"), self._nok_table)
        return section

    # Définition : reconstruit la vue pour appliquer les traductions.
    def apply_language(self) -> None:
        self._build_ui()
        self.refresh(self._last_log)

    # ------------------------------------------------------------------
    # Interactions
    # ------------------------------------------------------------------

    # Définition : passe à la prochaine valeur de fenêtre d'historique.
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

    # Définition : met à jour toutes les sous-sections avec le log courant.
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

    # Définition : recalcule et affiche les compteurs de synthèse.
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
            taux_color = "#2E7D32"
        elif taux >= 90:
            taux_color = "#C49A3C"
        else:
            taux_color = "#C62828"
        self._card_lbls["taux"].setStyleSheet(
            f"font-size: 32px; font-weight: bold; color: {taux_color};"
            " background: transparent; border: none;"
        )

    # Définition : régénère dynamiquement les barres de l'histogramme.
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
            color = "#2E7D32" if result == "PASS" else "#C62828"
            height = max(4, int(min(fmax, FORCE_NEWTON_MAX) / FORCE_NEWTON_MAX * bar_h))

            # QWidget : emplacement vertical pour ancrer une barre.
            slot = QWidget()
            slot.setFixedWidth(12)
            sv = QVBoxLayout(slot)
            sv.setContentsMargins(0, 0, 0, 0)
            sv.setSpacing(0)
            sv.addStretch()

            # QFrame : barre colorée représentant un cycle.
            bar = QFrame(slot)
            bar.setFixedSize(12, height)
            bar.setStyleSheet(
                f"QFrame {{ background-color: {color}; border-radius: 2px; border: none; }}"
            )
            bar.setToolTip(f"Cycle {cycle_num}\n{result}\nFmax: {fmt_force_dan(fmax)} daN")
            sv.addWidget(bar)
            self._bar_layout.addWidget(slot)

        self._bar_layout.addStretch()

    # Définition : envoie les Fmax au widget de tendance.
    def _update_tendance(self, log: list[tuple]) -> None:
        fmax_values = [r[1] for r in log[-self._n_histo:]]
        self._tendance.set_data(fmax_values)

    # Définition : calcule et affiche le rebut par tranche horaire.
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
            # QLabel : message affiché lorsqu'aucune donnée n'est disponible.
            lbl = QLabel(t("lbl_no_data"))
            lbl.setStyleSheet("color: #7A7870;")
            self._rebut_layout.addWidget(lbl)
            return

        for key in sorted(hours.keys()):
            entries = hours[key]
            nb_total = len(entries)
            nb_nok = sum(1 for e in entries if e[3] != "PASS")
            pct = (nb_nok / nb_total * 100) if nb_total else 0.0

            # QWidget : ligne d'affichage d'une heure de production.
            row = QWidget()
            rh = QHBoxLayout(row)
            rh.setContentsMargins(0, 2, 0, 2)
            rh.setSpacing(8)

            # QLabel : heure (HH:MM) de la ligne courante.
            lbl = QLabel(f"{key}")
            lbl.setFixedWidth(40)
            lbl.setStyleSheet("font-size: 14px; color: #1A1A18; font-weight: bold;")
            rh.addWidget(lbl)

            # QProgressBar : visualise le nombre de NOK sur l'heure.
            pb = QProgressBar()
            pb.setMaximum(nb_total)
            pb.setValue(nb_nok)
            pb.setFixedHeight(18)
            pb.setTextVisible(False)
            if pct > 10:
                chunk_color = "#C62828"
            elif pct > 5:
                chunk_color = "#C49A3C"
            else:
                chunk_color = "#2E7D32"
            pb.setStyleSheet(
                "QProgressBar { background-color: #E8E4DC; border-radius: 3px; border: none; }"
                f"QProgressBar::chunk {{ background-color: {chunk_color}; border-radius: 3px; }}"
            )
            rh.addWidget(pb, stretch=1)

            # QLabel : résumé texte NOK/total pour l'heure.
            info = QLabel(t("stats_hour_row_info").format(nok=nb_nok, total=nb_total))
            info.setFixedWidth(170)
            info.setStyleSheet("font-size: 12px; color: #7A7870;")
            rh.addWidget(info)

            self._rebut_layout.addWidget(row)

    # Définition : rafraîchit la table des cycles NOK les plus récents.
    def _update_nok_table(self, log: list[tuple]) -> None:
        self._nok_table.setRowCount(0)
        nok_entries = [(i, e) for i, e in enumerate(log) if e[3] != "PASS"]
        # Plus récent en haut
        nok_entries = sorted(nok_entries, key=lambda x: x[1][4], reverse=True)[:50]

        for _, (cycle_num, fmax, xmax, result, heure) in nok_entries:
            row = self._nok_table.rowCount()
            self._nok_table.insertRow(row)
            if fmax > FORCE_THRESHOLD_N:
                fmax_color = "#C62828"
            elif fmax > FORCE_THRESHOLD_N * 0.8:
                fmax_color = "#C49A3C"
            else:
                fmax_color = "#1A1A18"
            for col, text in enumerate(
                [str(cycle_num), heure, fmt_force_dan(fmax), f"{xmax:.1f}", "—"]
            ):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setBackground(QColor("#FAFAF8"))
                if col == 2:
                    item.setForeground(QColor(fmax_color))
                self._nok_table.setItem(row, col, item)


# ===========================================================================
# LevelSelectorDialog — choix du niveau avant saisie PIN
# ===========================================================================

class LevelSelectorDialog(QDialog):
    """Dialog de sélection du niveau d'accès avant saisie PIN."""

    # Définition : initialise le dialogue de choix du niveau d'accès.
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog
        )
        self.setModal(True)
        self.setFixedSize(400, 320)
        self.setStyleSheet("""
            QDialog {
                background-color: #FAFAF8;
                border: 2px solid #C49A3C;
                border-radius: 12px;
            }
        """)
        self.selected_level: int = AccessLevel.NONE
        self._build_ui()

    # Définition : construit l'interface de sélection des niveaux.
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # QLabel : titre du dialogue de sélection.
        title = QLabel(t("dlg_level_select_title"))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            "color: #C49A3C; font-size: 16px; font-weight: bold; background: transparent;"
        )
        layout.addWidget(title)

        # QFrame : séparateur visuel sous le titre.
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background-color: #C49A3C; max-height: 1px;")
        layout.addWidget(sep)

        levels = [
            (AccessLevel.OPERATEUR,  "🟢", t("level_operator"),
               t("level_desc_operator"),               "#2E7D32", "#F1F8E9"),
            (AccessLevel.TECHNICIEN, "🟡", t("level_tech"),
               t("level_desc_tech"),                   "#C49A3C", "#FFF8E1"),
            (AccessLevel.ADMIN,      "🔴", t("level_admin"),
               t("level_desc_admin"),                  "#A07830", "#FFF3E0"),
        ]

        for level, icon, name, desc, color, bg in levels:
            # QPushButton : bouton de sélection d'un niveau d'accès.
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
                    background-color: #E8E4DC;
                }}
            """)
            btn_layout = QHBoxLayout(btn)
            btn_layout.setContentsMargins(12, 8, 12, 8)

            # QLabel : icône + nom du niveau.
            icon_lbl = QLabel(f"{icon}  {name}")
            icon_lbl.setStyleSheet(
                f"color: {color}; font-size: 16px; font-weight: bold; "
                "background: transparent; border: none;"
            )
            # QLabel : description du niveau d'accès.
            desc_lbl = QLabel(desc)
            desc_lbl.setStyleSheet(
                "color: #6B6860; font-size: 12px; background: transparent; border: none;"
            )

            col = QVBoxLayout()
            col.addWidget(icon_lbl)
            col.addWidget(desc_lbl)
            btn_layout.addLayout(col)
            btn_layout.addStretch()

            btn.clicked.connect(lambda _, lv=level: self._select(lv))
            layout.addWidget(btn)

        # QPushButton : annule et ferme le dialogue.
        btn_cancel = QPushButton(t("btn_cancel_x"))
        btn_cancel.setFixedHeight(40)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #FFF3F3;
                color: #C62828;
                font-size: 13px;
                font-weight: bold;
                border: 1px solid #C62828;
                border-radius: 6px;
            }
            QPushButton:pressed { background-color: #C62828; color: #ffffff; }
        """)
        btn_cancel.clicked.connect(self.reject)
        layout.addWidget(btn_cancel)

    # Définition : enregistre le niveau choisi puis valide le dialogue.
    def _select(self, level: int) -> None:
        self.selected_level = level
        self.accept()


# ===========================================================================
# LoginDialog — sélection niveau + saisie PIN en une seule page
# ===========================================================================

class LoginDialog(QDialog):
    """Dialogue unique combinant choix du niveau d'accès et saisie PIN."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.setFixedSize(640, 480)
        self.setStyleSheet("""
            QDialog {
                background-color: #FAFAF8;
                border: 2px solid #C49A3C;
                border-radius: 14px;
            }
        """)
        self.selected_level: int = AccessLevel.NONE
        self._pin_value: str = ""
        self._level_btns: dict[int, QPushButton] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        # Titre
        title = QLabel(f"🔐  {t('btn_login')}")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            "color: #C49A3C; font-size: 22px; font-weight: bold; background: transparent;"
        )
        root.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background-color: #C49A3C; max-height: 1px;")
        root.addWidget(sep)

        # Corps : colonne gauche (niveaux) + colonne droite (PIN)
        body = QHBoxLayout()
        body.setSpacing(16)

        # --- Colonne gauche : boutons niveau ---
        left_col = QVBoxLayout()
        left_col.setSpacing(8)

        lbl_choose = QLabel(t("dlg_level_select_title"))
        lbl_choose.setStyleSheet(
            "color: #6B6860; font-size: 16px; font-weight: bold; background: transparent;"
        )
        lbl_choose.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_col.addWidget(lbl_choose)

        levels = [
            (AccessLevel.OPERATEUR,  "🟢", t("level_operator"),  t("level_desc_operator"),  "#2E7D32", "#F1F8E9"),
            (AccessLevel.TECHNICIEN, "🟡", t("level_tech"),       t("level_desc_tech"),       "#C49A3C", "#FFF8E1"),
            (AccessLevel.ADMIN,      "🔴", t("level_admin"),      t("level_desc_admin"),      "#A07830", "#FFF3E0"),
        ]
        for level, icon, name, desc, color, bg in levels:
            btn = QPushButton()
            btn.setFixedHeight(76)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg};
                    border: 2px solid transparent;
                    border-radius: 10px;
                    text-align: left;
                    padding: 0 12px;
                }}
                QPushButton:pressed {{ border: 2px solid {color}; background-color: #E8E4DC; }}
            """)
            btn_layout = QHBoxLayout(btn)
            btn_layout.setContentsMargins(10, 6, 10, 6)
            name_lbl = QLabel(f"{icon}  {name}")
            name_lbl.setStyleSheet(
                f"color: {color}; font-size: 18px; font-weight: bold; "
                "background: transparent; border: none;"
            )
            desc_lbl = QLabel(desc)
            desc_lbl.setStyleSheet(
                "color: #6B6860; font-size: 13px; background: transparent; border: none;"
            )
            col = QVBoxLayout()
            col.setSpacing(2)
            col.addWidget(name_lbl)
            col.addWidget(desc_lbl)
            btn_layout.addLayout(col)
            btn_layout.addStretch()
            btn.clicked.connect(lambda _, lv=level, c=color, b=bg: self._select_level(lv, c, b))
            left_col.addWidget(btn)
            self._level_btns[level] = btn

        left_col.addStretch()
        body.addLayout(left_col, stretch=4)

        # Séparateur vertical
        vsep = QFrame()
        vsep.setFrameShape(QFrame.Shape.VLine)
        vsep.setStyleSheet("background-color: #E0DCD4; max-width: 1px;")
        body.addWidget(vsep)

        # --- Colonne droite : afficheur PIN + pavé ---
        right_col = QVBoxLayout()
        right_col.setSpacing(8)

        lbl_pin = QLabel(t("dlg_pin_title") if "dlg_pin_title" in (t("dlg_pin_title"),) else "Code PIN")
        lbl_pin.setStyleSheet(
            "color: #6B6860; font-size: 16px; font-weight: bold; background: transparent;"
        )
        lbl_pin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_col.addWidget(lbl_pin)

        # Afficheur PIN masqué
        self._pin_display = QLineEdit()
        self._pin_display.setReadOnly(True)
        self._pin_display.setEchoMode(QLineEdit.EchoMode.Password)
        self._pin_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._pin_display.setStyleSheet("""
            QLineEdit {
                background-color: #FFFFFF;
                color: #2C2C2A;
                border: 2px solid #C49A3C;
                border-radius: 8px;
                font-size: 30px;
                font-weight: bold;
                min-height: 52px;
                padding: 4px 12px;
            }
        """)
        right_col.addWidget(self._pin_display)

        # Grille de touches
        from PySide6.QtWidgets import QGridLayout
        grid = QGridLayout()
        grid.setSpacing(6)

        key_style = """
            QPushButton {
                background-color: #FFFFFF;
                color: #2C2C2A;
                font-size: 22px;
                font-weight: bold;
                border: 1px solid #E8E4DC;
                border-radius: 8px;
                min-height: 52px;
            }
            QPushButton:pressed { background-color: #A07830; color: #ffffff; }
        """
        back_style = """
            QPushButton {
                background-color: #FFF3F3;
                color: #C62828;
                font-size: 20px;
                font-weight: bold;
                border: 1px solid #C62828;
                border-radius: 8px;
                min-height: 52px;
            }
            QPushButton:pressed { background-color: #C62828; color: #ffffff; }
        """

        for label, row, col in [
            ("7", 0, 0), ("8", 0, 1), ("9", 0, 2),
            ("4", 1, 0), ("5", 1, 1), ("6", 1, 2),
            ("1", 2, 0), ("2", 2, 1), ("3", 2, 2),
            ("0", 3, 0), (".", 3, 1),
        ]:
            btn_k = QPushButton(label)
            btn_k.setStyleSheet(key_style)
            btn_k.clicked.connect(lambda _, c=label: self._key_press(c))
            grid.addWidget(btn_k, row, col)

        btn_back = QPushButton(t("btn_backspace"))
        btn_back.setStyleSheet(back_style)
        btn_back.clicked.connect(self._backspace)
        grid.addWidget(btn_back, 3, 2)

        right_col.addLayout(grid)
        body.addLayout(right_col, stretch=5)
        root.addLayout(body, stretch=1)

        # --- Ligne de boutons Annuler / Valider ---
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        btn_cancel = QPushButton(t("btn_cancel_x"))
        btn_cancel.setFixedHeight(48)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #FFF3F3; color: #C62828;
                font-size: 18px; font-weight: bold;
                border: 1px solid #C62828; border-radius: 8px;
            }
            QPushButton:pressed { background-color: #C62828; color: #ffffff; }
        """)
        btn_cancel.clicked.connect(self.reject)

        btn_ok = QPushButton(t("btn_ok_check"))
        btn_ok.setFixedHeight(48)
        btn_ok.setStyleSheet("""
            QPushButton {
                background-color: #F1F8E9; color: #2E7D32;
                font-size: 18px; font-weight: bold;
                border: 2px solid #2d7a2d; border-radius: 8px;
            }
            QPushButton:pressed { background-color: #2d7a2d; color: #ffffff; }
        """)
        btn_ok.clicked.connect(self.accept)

        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_ok)
        root.addLayout(btn_row)

    def _select_level(self, level: int, color: str, bg: str) -> None:
        self.selected_level = level
        # Réinitialise tous les boutons puis met en évidence le sélectionné
        _borders = {
            AccessLevel.OPERATEUR:  ("#2E7D32", "#F1F8E9"),
            AccessLevel.TECHNICIEN: ("#C49A3C", "#FFF8E1"),
            AccessLevel.ADMIN:      ("#A07830", "#FFF3E0"),
        }
        for lv, btn in self._level_btns.items():
            c, b = _borders[lv]
            selected = lv == level
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {b if not selected else c};
                    border: 2px solid {c if selected else 'transparent'};
                    border-radius: 10px; text-align: left; padding: 0 12px;
                }}
                QPushButton:pressed {{ border: 2px solid {c}; background-color: #E8E4DC; }}
            """)
            # Recolore les labels internes selon sélection
            for child in btn.findChildren(QLabel):
                if child.styleSheet().startswith(f"color: {c}"):
                    child.setStyleSheet(
                        f"color: {'#FFFFFF' if selected else c}; font-size: 18px; "
                        "font-weight: bold; background: transparent; border: none;"
                    )
                else:
                    child.setStyleSheet(
                        f"color: {'#E0E0D8' if selected else '#6B6860'}; "
                        "font-size: 13px; background: transparent; border: none;"
                    )

    def _key_press(self, char: str) -> None:
        if char == "." and "." in self._pin_value:
            return
        self._pin_value += char
        self._pin_display.setText(self._pin_value)

    def _backspace(self) -> None:
        self._pin_value = self._pin_value[:-1]
        self._pin_display.setText(self._pin_value)

    def pin(self) -> str:
        return self._pin_value


# ===========================================================================
# PinDialog — saisie PIN avec verrouillage
# ===========================================================================

class PinDialog(QDialog):
    """Dialogue PIN 4 chiffres, 3 tentatives, verrouillage 30 s."""

    # Définition : initialise le dialogue PIN et la logique de verrouillage.
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

        # QLabel : invite utilisateur pour saisir le PIN.
        self._label = QLabel(t("lbl_enter_pin"))
        layout.addWidget(self._label)

        # QLineEdit : affichage masqué du PIN saisi.
        self._pin_edit = QLineEdit()
        self._pin_edit.setReadOnly(True)
        self._pin_edit.setPlaceholderText(t("pin_placeholder"))
        self._pin_edit.setMinimumHeight(56)
        self._pin_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._pin_edit)

        # QPushButton : ouvre le pavé numérique.
        btn_kbd = QPushButton(t("btn_enter_code"))
        btn_kbd.setMinimumHeight(52)
        btn_kbd.clicked.connect(self._open_numpad)
        layout.addWidget(btn_kbd)

        # QLabel : message d'erreur ou état du verrouillage.
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

    # Définition : ouvre le pavé numérique et récupère la valeur saisie.
    def _open_numpad(self) -> None:
        dlg = NumpadDialog(title="Code PIN", unit="", value="", parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            val = dlg.value()
            self._pin_value = val
            self._pin_edit.setText("•" * len(val))

    # Définition : valide le PIN saisi et gère les tentatives.
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

    # Définition : active la période de verrouillage après trop d'échecs.
    def _start_lockout(self) -> None:
        self._locked = True
        self._lockout_remaining = _LOCKOUT_SECONDS
        self._lockout_timer.start()
        self._update_lockout_label()

    # Définition : décrémente le verrouillage chaque seconde.
    def _on_lockout_tick(self) -> None:
        self._lockout_remaining -= 1
        if self._lockout_remaining <= 0:
            self._lockout_timer.stop()
            self._locked = False
            self._attempts = 0
            self._error_label.setText(t("lbl_pin_retry"))
        else:
            self._update_lockout_label()

    # Définition : met à jour le texte d'information de verrouillage.
    def _update_lockout_label(self) -> None:
        self._error_label.setText(
            f"Trop de tentatives — réessayez dans {self._lockout_remaining} s."
        )


# ===========================================================================
# MainWindow — fenêtre principale 1280×720
# ===========================================================================

class MainWindow(QMainWindow):
    """Fenêtre principale IHM riveteuse (1280×720, plein écran sans barre)."""

    # Définition : initialise l'état global de la fenêtre principale.
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
        self._stop_cycle_btn = None
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

        # QWidget : barre d'actions dédiée à l'édition des zones.
        self._edit_bar = QWidget(self._graph)
        edit_layout = QHBoxLayout(self._edit_bar)
        edit_layout.setContentsMargins(10, 6, 10, 6)
        edit_layout.setSpacing(10)

        # QPushButton : applique les modifications de zones.
        self._btn_apply_zones = QPushButton(t("btn_apply"))
        self._btn_apply_zones.setFixedHeight(44)
        self._btn_apply_zones.setStyleSheet("""
            QPushButton {
                background-color: #F1F8E9;
                color: #2E7D32;
                font-size: 15px;
                font-weight: bold;
                border: 2px solid #2d7a2d;
                border-radius: 8px;
                padding: 0 20px;
            }
            QPushButton:pressed { background-color: #2d7a2d; color: #ffffff; }
        """)
        self._btn_apply_zones.clicked.connect(self._apply_zone_edits)

        # QPushButton : annule les modifications de zones.
        self._btn_cancel_zones = QPushButton(t("btn_cancel_cross"))
        self._btn_cancel_zones.setFixedHeight(44)
        self._btn_cancel_zones.setStyleSheet("""
            QPushButton {
                background-color: #FFF3F3;
                color: #C62828;
                font-size: 15px;
                font-weight: bold;
                border: 1px solid #C62828;
                border-radius: 8px;
                padding: 0 20px;
            }
            QPushButton:pressed { background-color: #C62828; color: #ffffff; }
        """)
        self._btn_cancel_zones.clicked.connect(self._cancel_zone_edits)

        # QLabel : affiche des infos de coordonnées en mode édition.
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
        # QPushButton : bascule auto-scale/fixe du graphique.
        self._auto_scale_btn = QPushButton("⤢ Auto", self._graph)
        self._auto_scale_btn.setCheckable(True)
        self._auto_scale_btn.setFixedSize(70, 28)
        self._auto_scale_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(242, 240, 235, 200);
                color: #6B6860;
                font-size: 12px;
                border: 1px solid #E8E4DC;
                border-radius: 4px;
            }
            QPushButton:checked {
                background-color: rgba(160, 120, 48, 200);
                color: #ffffff;
                border: 1px solid #C49A3C;
            }
        """)
        self._auto_scale_btn.clicked.connect(self._on_auto_scale_toggled)

        # QPushButton : recalage ponctuel des axes sur la courbe affichée.
        self._auto_scale_once_btn = QPushButton("⊡ Auto-scale", self._graph)
        self._auto_scale_once_btn.setMinimumHeight(36)
        self._auto_scale_once_btn.setFixedWidth(118)
        self._auto_scale_once_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(242, 240, 235, 200);
                color: #6B6860;
                font-size: 12px;
                font-weight: bold;
                border: 1px solid #E8E4DC;
                border-radius: 4px;
                padding: 0 10px;
            }
            QPushButton:pressed {
                background-color: rgba(218, 213, 204, 220);
            }
        """)
        self._auto_scale_once_btn.clicked.connect(self._on_auto_scale_once_clicked)
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

    # Définition : adapte la fenêtre à la résolution de l'écran.
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

    # Définition : construit l'UI principale (stack production/réglages).
    def _build_ui(self) -> None:
        # QWidget : conteneur central de l'application.
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Stack principal : Page 0 = Production | Page 1 = Réglages
        # QStackedWidget : navigation entre page production et page réglages.
        self.stack = QStackedWidget()
        root.addWidget(self.stack)

        # Page 0 — Production
        self.stack.addWidget(self._build_production_page())

        # Page 1 — Réglages (import différé pour éviter les imports circulaires)
        from ihm.settings_dialog import SettingsPage
        self.stack.addWidget(SettingsPage(parent=self))

    # Définition : construit la page de production complète.
    def _build_production_page(self) -> QWidget:
        # QWidget : racine de la page production.
        page = QWidget()
        page.setObjectName("production_page")
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # Ligne contenu : graphique | panneau droit
        # QWidget : zone horizontale graphique + panneau droit.
        content = QWidget()
        h = QHBoxLayout(content)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        # Graphique (QStackedWidget : courbe ou table données)
        # QStackedWidget : bascule courbe / table / stats.
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

        # Panneau droit — 330px fixe (normal + édition)
        # QStackedWidget : bascule panneau droit normal / édition.
        self._right_stack = QStackedWidget()
        self._right_stack.setFixedWidth(330)
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

    # Définition : construit le panneau droit de supervision.
    def _build_right_panel(self) -> QWidget:
        # QWidget : conteneur du panneau droit.
        panel = QWidget()
        self._right_panel = panel
        self._right_panel.setFixedWidth(330)
        panel.setStyleSheet(
            f"background-color: {get_colors()['panel_bg']}; "
            f"border-left: 1px solid {get_colors()['separator']};"
        )
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(2)



        # QPushButton : connexion/déconnexion utilisateur.
        self._access_btn = QPushButton(f"👤  {t('btn_login')}")
        self._access_btn.setFixedHeight(32)
        self._access_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._access_btn.clicked.connect(self._on_login_clicked)
        layout.addWidget(self._access_btn)

        layout.addWidget(self._build_result_badge())
        layout.addWidget(self._build_counters_section())
        layout.addSpacing(1)
        layout.addWidget(self._build_datetime_section())
        sep_pm = make_hseparator(get_colors()["separator"])
        sep_pm.setFixedHeight(1)
        layout.addWidget(sep_pm)
        layout.addWidget(self._build_peaks_section())
        sep_peaks = make_hseparator(get_colors()["separator"])
        sep_peaks.setFixedHeight(1)
        layout.addWidget(sep_peaks)
        layout.addStretch()
        self._build_live_section(layout)
        layout.addStretch()
        # QWidget : ligne basse horloge + bouton réglages.
        bottom_row = QWidget()
        bottom_row.setFixedHeight(48)
        bottom_h = QHBoxLayout(bottom_row)
        bottom_h.setContentsMargins(6, 4, 6, 4)
        bottom_h.setSpacing(6)
        # QLabel : horloge temps réel.
        self._clock_label = QLabel(datetime.now().strftime("%d/%m/%Y  %H:%M:%S"))
        self._clock_label.setObjectName("datetime_label")
        self._clock_label.setFixedHeight(24)
        self._clock_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._clock_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        bottom_h.addWidget(self._clock_label, stretch=1)
        bottom_h.addWidget(self._build_settings_button(), stretch=0)
        layout.addWidget(bottom_row)
        return panel

    # Définition : construit le panneau d'édition des zones.
    def _build_edit_panel(self) -> QWidget:
        # QWidget : conteneur du panneau d'édition.
        panel = QWidget()
        panel.setStyleSheet(
            f"background-color: {get_colors()['panel_bg']}; "
            f"border-left: 1px solid {get_colors()['separator']};"
        )
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # QLabel : titre de section du mode édition.
        self._edit_panel_title_label = QLabel(t("edit_zones_title"))
        self._edit_panel_title_label.setStyleSheet("color: #C49A3C; font-size: 14px; font-weight: bold; background: transparent;")  # titre section
        layout.addWidget(self._edit_panel_title_label)

        # --- Ligne de boutons Z1-Z5 ---
        zone_btn_row = QHBoxLayout()
        zone_btn_row.setSpacing(4)
        self._zone_btns: list[QPushButton] = []
        for i in range(MAX_NO_PASS_ZONES):
            # QPushButton : active/désactive une zone NO-PASS.
            btn = QPushButton(f"Z{i + 1}")
            btn.setFixedSize(44, 36)
            btn.setCheckable(True)
            btn.setStyleSheet(
                "background-color: #FAFAF8; color: #4A4844; "
                "border: 1px solid #C8C4BC; border-radius: 6px; "
                "font-size: 13px; font-weight: bold;"
            )
            btn.clicked.connect(
                lambda checked, idx=i: self._on_zone_btn_clicked(idx, checked)
            )
            zone_btn_row.addWidget(btn)
            self._zone_btns.append(btn)
        zone_btn_row.addStretch()
        layout.addLayout(zone_btn_row)

        # --- Ligne de boutons UB1-UB5 ---
        ub_btn_row = QHBoxLayout()
        ub_btn_row.setSpacing(4)
        self._ub_btns: list[QPushButton] = []
        for i in range(MAX_NO_PASS_ZONES):  # MAX_UNI_BOX_ZONES = 5 = MAX_NO_PASS_ZONES
            # QPushButton : active/désactive une zone UNI-BOX.
            btn = QPushButton(f"UB{i + 1}")
            btn.setFixedSize(44, 36)
            btn.setCheckable(True)
            btn.setStyleSheet(
                "background-color: #FAFAF8; color: #4A4844; "
                "border: 1px solid #C8C4BC; border-radius: 6px; "
                "font-size: 11px; font-weight: bold;"
            )
            btn.clicked.connect(
                lambda checked, idx=i: self._on_ub_btn_clicked(idx, checked)
            )
            ub_btn_row.addWidget(btn)
            self._ub_btns.append(btn)
        ub_btn_row.addStretch()
        layout.addLayout(ub_btn_row)

        layout.addWidget(make_hseparator())

        # Zone scrollable pour les coordonnées
        # QScrollArea : zone scrollable des coordonnées éditables.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; } "
            "QWidget#scroll_inner { background: transparent; }"
        )
        # QWidget : contenu interne de la zone scrollable.
        inner = QWidget()
        inner.setObjectName("scroll_inner")
        inner.setStyleSheet("background: transparent;")
        self._edit_panel_content = QVBoxLayout(inner)
        self._edit_panel_content.setSpacing(4)
        self._edit_panel_content.setContentsMargins(0, 2, 0, 2)
        self._edit_panel_content.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll, stretch=1)

        layout.addWidget(make_hseparator())

        # QPushButton : réinitialise le zoom du graphique.
        self._reset_zoom_btn = QPushButton(t("btn_reset_zoom"))
        self._reset_zoom_btn.setStyleSheet(
            "background-color: #FAFAF8; color: #A07830; font-size: 19px; "
            "border: 1px solid #C49A3C; border-radius: 6px; padding: 6px;"
        )
        self._reset_zoom_btn.clicked.connect(self._reset_graph_zoom)
        layout.addWidget(self._reset_zoom_btn)

        # QLabel : aide rapide pour l'édition des poignées.
        self._edit_panel_hint_label = QLabel(t("hint_edit_precise_coord"))
        self._edit_panel_hint_label.setStyleSheet("color: #888; font-size: 15px; font-style: italic; background: transparent;")
        self._edit_panel_hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._edit_panel_hint_label)

        self._handle_coord_labels: dict[str, QLabel] = {}
        return panel

    # Définition : active/désactive une zone NO-PASS.
    def _on_zone_btn_clicked(self, idx: int, checked: bool) -> None:
        """Active/désactive la zone NO-PASS idx dans _tools_config."""
        zones = self._graph._tools_config.get("no_pass_zones", [])
        # S'assurer que la liste a au moins idx+1 éléments
        while len(zones) <= idx:
            zones.append({"enabled": False, "x_min": 0, "x_max": 0, "y_limit": 0})
        self._graph._tools_config["no_pass_zones"] = zones
        zones[idx]["enabled"] = checked
        if checked:
            z = zones[idx]
            if z.get("x_max", 0) == 0:
                xr, yr = self._graph._get_ranges()
                z["x_min"] = round(xr * 0.2, 1)
                z["x_max"] = round(xr * 0.6, 1)
                z["y_limit"] = round(yr * 0.7, 0)
        self._graph._compute_handles()
        self._graph.update()
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()
        self._refresh_edit_panel()
        self._update_zone_buttons()

    # Définition : rafraîchit l'état visuel des boutons de zones.
    def _update_zone_buttons(self) -> None:
        """Met à jour l'apparence des boutons Z1-Z5 (NO-PASS) et UB1-UB5 (UNI-BOX)."""
        if not hasattr(self, "_zone_btns"):
            return
        zones = self._graph._tools_config.get("no_pass_zones", [])
        for i, btn in enumerate(self._zone_btns):
            active = i < len(zones) and bool(zones[i].get("enabled"))
            btn.setChecked(active)
            if active:
                btn.setStyleSheet(
                    "background-color: #C62828; color: #FFFFFF; "
                    "border: 1px solid #8B1A1A; border-radius: 6px; "
                    "font-size: 13px; font-weight: bold;"
                )
            else:
                btn.setStyleSheet(
                    "background-color: #FAFAF8; color: #4A4844; "
                    "border: 1px solid #C8C4BC; border-radius: 6px; "
                    "font-size: 13px; font-weight: bold;"
                )
        self._update_ub_buttons()

    # Définition : active/désactive une zone UNI-BOX.
    def _on_ub_btn_clicked(self, idx: int, checked: bool) -> None:
        """Active/désactive la zone UNI-BOX idx dans _tools_config."""
        zones = self._graph._tools_config.get("uni_box_zones", [])
        while len(zones) <= idx:
            zones.append({
                "enabled": False, "box_x_min": 0, "box_x_max": 0,
                "box_y_min": 0, "box_y_max": 0,
                "entry_side": "left", "exit_side": "left",
            })
        self._graph._tools_config["uni_box_zones"] = zones
        zones[idx]["enabled"] = checked
        if checked:
            z = zones[idx]
            if z.get("box_x_max", 0) == 0:
                xr, yr = self._graph._get_ranges()
                z["box_x_min"] = round(xr * 0.2, 1)
                z["box_x_max"] = round(xr * 0.6, 1)
                z["box_y_min"] = round(yr * 0.3, 0)
                z["box_y_max"] = round(yr * 0.7, 0)
        self._graph._compute_handles()
        self._graph.update()
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()
        self._refresh_edit_panel()
        self._update_zone_buttons()

    # Définition : rafraîchit l'état visuel des boutons UNI-BOX.
    def _update_ub_buttons(self) -> None:
        """Met à jour l'apparence des boutons UB1-UB5 selon l'état des zones."""
        if not hasattr(self, "_ub_btns"):
            return
        zones = self._graph._tools_config.get("uni_box_zones", [])
        for i, btn in enumerate(self._ub_btns):
            active = i < len(zones) and bool(zones[i].get("enabled"))
            btn.setChecked(active)
            if active:
                btn.setStyleSheet(
                    "background-color: #FF9800; color: #FFFFFF; "
                    "border: 1px solid #E65100; border-radius: 6px; "
                    "font-size: 11px; font-weight: bold;"
                )
            else:
                btn.setStyleSheet(
                    "background-color: #FAFAF8; color: #4A4844; "
                    "border: 1px solid #C8C4BC; border-radius: 6px; "
                    "font-size: 11px; font-weight: bold;"
                )

    # NO-PASS : 3 lignes — lm=1 Pos.min  tm=2 Haut.max  rm=3 Pos.max
    _COORD_ROWS_NO_PASS = [
        ("coord_pos_min",   "lm", "mm",  False),
        ("coord_haut_max",  "tm", "daN", False),
        ("coord_pos_max",   "rm", "mm",  False),
    ]
    # UNI-BOX : 4 lignes — lm=1 Pos.min  tm=2 Haut.max  rm=3 Pos.max  bm=4 Haut.min
    _COORD_ROWS_UNIBOX = [
        ("coord_pos_min",   "lm", "mm",  False),
        ("coord_haut_max",  "tm", "daN", False),
        ("coord_pos_max",   "rm", "mm",  False),
        ("coord_haut_min",  "bm", "daN", False),
    ]

    # Définition : formate le texte affiché pour une poignée de zone.
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
            if hid == "lm":
                return f"{float(z.get('x_min', 0)):.1f} mm"
            elif hid == "rm":
                return f"{float(z.get('x_max', 0)):.1f} mm"
            elif hid == "tm":
                return f"{fmt_force_dan(float(z.get('y_limit', 0)))} daN"
            elif hid == "bm":
                return "0.0 daN"
            return "—"
        elif zone_type == "uni_box":
            ub_zones = tools_cfg.get("uni_box_zones", [])
            if not ub_zones and tools_cfg.get("uni_box", {}).get("enabled"):
                ub_zones = [tools_cfg["uni_box"]]
            if zone_idx >= len(ub_zones):
                return "—"
            ub = ub_zones[zone_idx]
            if hid == "lm":
                return f"{float(ub.get('box_x_min', 0)):.1f} mm"
            elif hid == "rm":
                return f"{float(ub.get('box_x_max', 0)):.1f} mm"
            elif hid == "tm":
                return f"{fmt_force_dan(float(ub.get('box_y_max', 0)))} daN"
            elif hid == "bm":
                return f"{fmt_force_dan(float(ub.get('box_y_min', 0)))} daN"
            return "—"
        return "—"

    # Définition : met à jour toutes les valeurs de coordonnées affichées.
    def _update_handle_coord_labels(self) -> None:
        for key, lbl in self._handle_coord_labels.items():
            zone_type, zone_idx_str, hid = key.split("|")
            lbl.setText(self._get_handle_text(zone_type, int(zone_idx_str), hid))

    # Définition : reconstruit le contenu dynamique du panneau d'édition.
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
            # QLabel : en-tête de bloc pour une zone NO-PASS active.
            lbl_title = QLabel(f"Z{zone_idx + 1} — NO-PASS")
            lbl_title.setStyleSheet(
                "color: #C62828; font-weight: bold; font-size: 22px; background: transparent;"
            )
            self._edit_panel_content.addWidget(lbl_title)
            self._add_handle_rows("no_pass", zone_idx)
            self._edit_panel_content.addWidget(make_hseparator())

        ub_zones_panel = tools_cfg.get("uni_box_zones", [])
        if not ub_zones_panel and tools_cfg.get("uni_box", {}).get("enabled"):
            ub_zones_panel = [tools_cfg["uni_box"]]
        for zone_idx, ub in enumerate(ub_zones_panel):
            if not ub.get("enabled"):
                continue
            # QLabel : en-tête de bloc pour une zone UNI-BOX active.
            lbl_title = QLabel(f"UB{zone_idx + 1} — UNI-BOX")
            lbl_title.setStyleSheet(
                "color: #FF9800; font-weight: bold; font-size: 22px; background: transparent;"
            )
            self._edit_panel_content.addWidget(lbl_title)
            self._add_handle_rows("uni_box", zone_idx)
            self._edit_panel_content.addWidget(make_hseparator())

    # Définition : ajoute les lignes de coordonnées éditables d'une zone.
    def _add_handle_rows(self, zone_type: str, zone_idx: int) -> None:
        coord_rows = (
            self._COORD_ROWS_NO_PASS
            if zone_type == "no_pass"
            else self._COORD_ROWS_UNIBOX
        )
        for label_key, hid, unit, disabled in coord_rows:
            key = f"{zone_type}|{zone_idx}|{hid}"
            # QWidget : ligne d'édition d'une coordonnée.
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 1, 0, 1)
            row_layout.setSpacing(4)

            # QLabel : nom du paramètre de coordonnée.
            lbl_num = QLabel(f"{t(label_key)} :")
            lbl_num.setStyleSheet(
                "color: #C49A3C; font-size: 19px; background: transparent; min-width: 80px;"
            )

            # QLabel : valeur courante de la coordonnée.
            lbl_coord = QLabel(self._get_handle_text(zone_type, zone_idx, hid))
            lbl_coord.setStyleSheet(
                "color: #1A1A18; font-size: 19px; font-weight: bold; background: transparent;"
            )
            self._handle_coord_labels[key] = lbl_coord

            # QPushButton : ouvre la saisie numérique de la coordonnée.
            btn_edit = QPushButton("✏")
            btn_edit.setFixedSize(44, 44)
            if disabled:
                btn_edit.setEnabled(False)
                btn_edit.setStyleSheet(
                    "background: #E8E4DC; color: #9C9890; border: 1px solid #C8C4BC; "
                    "border-radius: 4px; font-size: 20px; padding: 0;"
                )
            else:
                btn_edit.setStyleSheet(
                    "background: #FAFAF8; color: #A07830; border: 1px solid #C49A3C; "
                    "border-radius: 4px; font-size: 20px; padding: 0;"
                )
                btn_edit.clicked.connect(
                    lambda _checked, zt=zone_type, zi=zone_idx, h=hid:
                        self._edit_handle_from_panel(zt, zi, h)
                )

            row_layout.addWidget(lbl_num)
            row_layout.addWidget(lbl_coord, stretch=1)
            row_layout.addWidget(btn_edit)
            self._edit_panel_content.addWidget(row)

    # Définition : édite une poignée depuis le panneau via NumpadDialog.
    def _edit_handle_from_panel(self, zone_type: str, zone_idx: int, hid: str) -> None:
        # Chercher la poignée correspondante (lm/rm/tm/bm sur la zone)
        handle = next(
            (h for h in self._graph._edit_handles
             if h["zone_type"] == zone_type and h["zone_idx"] == zone_idx and h["handle_id"] == hid),
            None,
        )
        if handle is None:
            # Construire un handle factice depuis _tools_config
            tools_cfg = self._graph._tools_config
            if zone_type == "no_pass":
                zones = tools_cfg.get("no_pass_zones", [])
                if zone_idx < len(zones):
                    z = zones[zone_idx]
                    x_data = float(z.get("x_min" if hid == "lm" else "x_max", 0))
                    y_data = float(z.get("y_limit", 0)) if hid == "tm" else 0.0
                    handle = {
                        "zone_type": zone_type, "zone_idx": zone_idx,
                        "handle_id": hid, "x_data": x_data, "y_data": y_data,
                        "px": 0, "py": 0,
                    }
            elif zone_type == "uni_box":
                ub_zones_list = tools_cfg.get("uni_box_zones", [])
                if not ub_zones_list and tools_cfg.get("uni_box", {}).get("enabled"):
                    ub_zones_list = [tools_cfg["uni_box"]]
                if zone_idx < len(ub_zones_list):
                    ub = ub_zones_list[zone_idx]
                    x_data = float(ub.get("box_x_min" if hid == "lm" else "box_x_max", 0))
                    y_data = float(ub.get("box_y_max" if hid == "tm" else "box_y_min", 0))
                    handle = {
                        "zone_type": zone_type, "zone_idx": zone_idx,
                        "handle_id": hid, "x_data": x_data, "y_data": y_data,
                        "px": 0, "py": 0,
                    }
            if handle is None:
                return

        if hid == "lm":
            dlg = NumpadDialog(
                title="Position min", unit=" mm",
                value=str(round(handle["x_data"], 1)), parent=self
            )
            if dlg.exec():
                try:
                    self._graph._apply_handle_drag(dict(handle), float(dlg.value()), handle["y_data"])
                except ValueError:
                    return
        elif hid == "rm":
            dlg = NumpadDialog(
                title="Position max", unit=" mm",
                value=str(round(handle["x_data"], 1)), parent=self
            )
            if dlg.exec():
                try:
                    self._graph._apply_handle_drag(dict(handle), float(dlg.value()), handle["y_data"])
                except ValueError:
                    return
        elif hid == "tm":
            dlg = NumpadDialog(
                title="Hauteur max", unit=" daN",
                value=str(round(n_to_dan(handle["y_data"]), 1)), parent=self
            )
            if dlg.exec():
                try:
                    self._graph._apply_handle_drag(dict(handle), handle["x_data"], float(dlg.value()) * 10.0)
                except ValueError:
                    return
        # bm (Hauteur min) est désactivé pour NO-PASS ; pour UNI-BOX :
        elif hid == "bm" and zone_type == "uni_box":
            dlg = NumpadDialog(
                title="Hauteur min", unit=" daN",
                value=str(round(n_to_dan(handle["y_data"]), 1)), parent=self
            )
            if dlg.exec():
                try:
                    self._graph._apply_handle_drag(dict(handle), handle["x_data"], float(dlg.value()) * 10.0)
                except ValueError:
                    return

        self._graph._compute_handles()
        self._graph.update()
        self._update_handle_coord_labels()

    # Définition : rafraîchit le panneau d'édition et ses boutons.
    def _refresh_edit_panel(self) -> None:
        if not hasattr(self, '_handle_coord_labels'):
            self._handle_coord_labels = {}
        if self._handle_coord_labels:
            self._update_handle_coord_labels()
        else:
            self._build_edit_panel_content()
        self._update_zone_buttons()

    # Définition : construit le badge central de résultat cycle.
    def _build_result_badge(self) -> QLabel:
        # QLabel : badge principal affichant l'état PASS/NOK/IDLE.
        self._result_badge = QLabel(t("status_idle"))
        self._result_badge.setObjectName("result_label")
        self._result_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._result_badge.setFixedHeight(110)
        self._result_badge.setStyleSheet(
            f"background-color: {get_colors()['idle_bg']}; color: {get_colors()['idle_text']}; "
            "border: 2px solid #C8C4BC; border-radius: 10px; "
            "font-size: 36px; font-weight: bold; padding: 10px;"
        )
        return self._result_badge

    # Définition : construit les compteurs OK/NOK/TOTAL.
    def _build_counters_section(self) -> QWidget:
        # QWidget : conteneur des compteurs.
        w = QWidget()
        w.setFixedHeight(55)
        w.setStyleSheet(
            "background-color: #FAFAF8; border: 1px solid #C8C4BC; border-radius: 6px;"
        )
        h = QHBoxLayout(w)
        h.setContentsMargins(10, 4, 10, 4)
        h.setSpacing(0)
        # QLabel : compteur des cycles OK.
        self._ok_count_label = QLabel(t("counter_ok_zero"))
        self._ok_count_label.setObjectName("counter_ok")
        self._ok_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # QLabel : compteur des cycles NOK.
        self._nok_count_label = QLabel(t("counter_nok_zero"))
        self._nok_count_label.setObjectName("counter_nok")
        self._nok_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # QLabel : compteur total des cycles.
        self._total_count_label = QLabel(t("counter_total_zero"))
        self._total_count_label.setObjectName("counter_tot")
        self._total_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h.addWidget(self._ok_count_label, stretch=1)
        h.addWidget(make_vseparator(get_colors()["separator"]))
        h.addWidget(self._nok_count_label, stretch=1)
        h.addWidget(make_vseparator(get_colors()["separator"]))
        h.addWidget(self._total_count_label, stretch=1)
        return w

    # Définition : construit la ligne PM/date-heure dynamique.
    def _build_datetime_section(self) -> QWidget:
        # QWidget : conteneur de la ligne PM/date.
        row_w = QWidget()
        row_w.setMinimumHeight(64)
        row_w.setFixedHeight(64)
        row = QHBoxLayout(row_w)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        # QPushButton : bouton PM cliquable avec libellé tronqué.
        self._pm_label = QPushButton()
        self._pm_label.setObjectName("btn_pm")
        self._pm_label.setMinimumWidth(140)
        self._pm_label.setMinimumHeight(60)
        self._pm_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._pm_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pm_label.setStyleSheet(self._PM_BTN_STYLE)
        self._pm_label.clicked.connect(
            lambda: self._flash_simple_button(self._pm_label, self._PM_BTN_STYLE)
        )
        self._pm_label.clicked.connect(self._on_pm_clicked)
        self._pm_btn = self._pm_label

        row.addWidget(self._pm_label, stretch=1)

        self._dt_timer = QTimer(self)
        self._dt_timer.setInterval(1000)
        self._dt_timer.timeout.connect(self._update_datetime)
        self._dt_timer.start()
        self._refresh_datetime_line()
        return row_w

    # Définition : construit la section PM dans le panneau droit.
    def _build_pm_section(self) -> QWidget:
        # QWidget : conteneur section PM.
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(4)
        # QLabel : titre de la section PM.
        self._pm_title_label = QLabel(t("app_title"))
        self._pm_title_label.setObjectName("pm_section_title")
        self._pm_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._pm_title_label.setFixedHeight(30)
        v.addWidget(self._pm_title_label)
        pm = PM_DEFINITIONS.get(self._pm_id)
        # QPushButton : bouton de sélection/changement de PM.
        self._pm_btn = QPushButton(f"PM-{self._pm_id:02d}  ·  {pm.name if pm else '—'}")
        self._pm_btn.setObjectName("btn_pm")
        self._pm_btn.setFixedHeight(45)
        self._pm_btn.setStyleSheet(self._PM_BTN_STYLE)
        self._pm_btn.clicked.connect(
            lambda: self._flash_simple_button(self._pm_btn, self._PM_BTN_STYLE)
        )
        self._pm_btn.clicked.connect(self._on_pm_clicked)
        v.addWidget(self._pm_btn)
        return w

    # Définition : construit l'affichage des pics Fmax/Xmax.
    def _build_peaks_section(self) -> QWidget:
        # QWidget : conteneur des pics de cycle.
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        self._peak_name_labels: list[QLabel] = []
        for attr, lbl_text, init_text in [
            ("_fmax_label", t("fmax_label"), "0.0 daN"),
            ("_xmax_label", t("xmax_label"), "0.0 mm"),
        ]:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(4)
            # QLabel : libellé du pic (Fmax/Xmax).
            lbl = QLabel(lbl_text)
            lbl.setObjectName("peak_label")
            self._peak_name_labels.append(lbl)
            # QLabel : valeur dynamique du pic.
            val = QLabel(init_text)
            val.setObjectName("peak_value")
            val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            setattr(self, attr, val)
            row.addWidget(lbl)
            row.addWidget(val)
            # QWidget : conteneur de ligne pour un couple label/valeur.
            row_w = QWidget()
            row_w.setFixedHeight(44)
            row_w.setLayout(row)
            v.addWidget(row_w)
        return w

    # Définition : construit les jauges live force/position.
    def _build_live_section(self, layout: QVBoxLayout) -> None:
        self._live_name_labels: list[QLabel] = []
        specs = [
            ("_force_value", "_force_bar", t("force_label"),    int(FORCE_NEWTON_MAX)),
            ("_pos_value",   "_pos_bar",   t("position_label"), int(POSITION_MM_MAX)),
        ]
        for idx, (attr_val, attr_bar, lbl_text, max_val) in enumerate(specs):
            if idx > 0:
                layout.addStretch()
            # QLabel : nom de la mesure live.
            lbl = QLabel(lbl_text)
            lbl.setObjectName("live_label")
            self._live_name_labels.append(lbl)
            layout.addWidget(lbl)
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(6)
            # QLabel : valeur live affichée.
            val_lbl = QLabel("0.0 daN" if "force" in attr_val else "0.0 mm")
            val_lbl.setObjectName("live_value")
            # QProgressBar : barre de progression live de la mesure.
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

    _SETTINGS_BTN_STYLE = (
        "background-color: #FAFAF8; color: #1A1A18;"
        " font-size: 13px; font-weight: 600;"
        " border: 1px solid #888480; border-radius: 4px;"
        " padding: 0 8px; outline: none;"
    )
    _PM_BTN_STYLE = (
        "background-color: #FAFAF8; color: #1A1A18;"
        " font-size: 15px; font-weight: bold;"
        " border: 2px solid #1A1A18; border-radius: 0px;"
        " padding: 4px 8px; text-align: left; outline: none;"
    )

    # Définition : construit le bouton d'accès aux réglages.
    def _build_settings_button(self) -> QWidget:
        # QPushButton : ouvre la page des paramètres.
        self._settings_btn = QPushButton(t("btn_settings_icon_upper"))
        self._settings_btn.setObjectName("btn_settings")
        self._settings_btn.setFixedWidth(110)
        self._settings_btn.setFixedHeight(40)
        self._settings_btn.setStyleSheet(self._SETTINGS_BTN_STYLE)
        self._settings_btn.clicked.connect(
            lambda: self._flash_simple_button(self._settings_btn, self._SETTINGS_BTN_STYLE)
        )
        self._settings_btn.clicked.connect(self._on_settings_clicked)
        return self._settings_btn

    # Définition : applique un flash visuel bref sur un bouton simple.
    def _flash_simple_button(self, btn: QPushButton, base_style: str) -> None:
        """Flash doré bref sur un bouton non-checkable."""
        btn.setStyleSheet(
            base_style
            + " background-color: #A07830; color: #FFFFFF;"
        )
        QTimer.singleShot(150, lambda: btn.setStyleSheet(base_style))

    # ------------------------------------------------------------------
    # Barre de navigation bas
    # ------------------------------------------------------------------

    # Définition : construit la barre de navigation inférieure.
    def _build_nav_bar(self) -> QWidget:
        # QWidget : conteneur de la barre de navigation.
        bar = QWidget()
        bar.setFixedHeight(70)
        bar.setStyleSheet(
            f"background-color: {get_colors()['panel_bg']}; "
            f"border-top: 1px solid {get_colors()['separator']};"
        )
        h = QHBoxLayout(bar)
        h.setContentsMargins(6, 6, 6, 6)
        h.setSpacing(6)

        self._nav_btn_group = QButtonGroup(self)
        self._nav_btn_group.setExclusive(True)

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
            # QPushButton : bouton de navigation/action.
            btn = QPushButton(label)
            btn.setObjectName(obj_name)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            btn.clicked.connect(callback)
            btn.clicked.connect(lambda checked=False, b=btn: self._flash_nav_button(b))
            self._nav_buttons[key] = btn
            if obj_name == "nav_btn" and key not in ("zones", "manual"):
                btn.setCheckable(True)
                btn.setChecked(checked)
                self._nav_btn_group.addButton(btn)
            h.addWidget(btn, stretch=1)

        manual_btn = self._nav_buttons.get("manual")
        if manual_btn is not None:
            manual_btn.setVisible(False)

        self._nav_btn_group.buttonClicked.connect(lambda _: self._update_tab_buttons())
        self._update_tab_buttons()

        return bar

    # Définition : applique le style actif/inactif des onglets nav.
    def _update_tab_buttons(self) -> None:
        """Applique le style actif/inactif sur les boutons de navigation cochables."""
        for btn in self._nav_btn_group.buttons():
            if btn.isChecked():
                btn.setStyleSheet(
                    "background-color: #7A5A20; color: #FFFFFF;"
                    " border: 1px solid #A07830; border-radius: 6px;"
                )
            else:
                btn.setStyleSheet("")

    # Définition : applique un flash visuel sur le bouton de nav cliqué.
    def _flash_nav_button(self, btn: QPushButton) -> None:
        """Flash doré bref sur le bouton nav cliqué."""
        btn.setStyleSheet(
            "background-color: #A07830; color: #ffffff;"
            " border: 1px solid #A07830; border-radius: 6px;"
        )

        # Définition : restaure le style normal après le flash.
        def _restore() -> None:
            # Conserve le style de sélection sur les onglets checkables.
            if btn in self._nav_btn_group.buttons() and btn.isChecked():
                self._update_tab_buttons()
                return

            # Conserve le style actif du bouton Zones pendant l'édition.
            zones_btn = self._nav_buttons.get("zones") if hasattr(self, "_nav_buttons") else None
            if zones_btn is btn and self._graph._edit_mode:
                btn.setStyleSheet(
                    "background-color: #7A5A20; color: #FFFFFF;"
                    " border: 1px solid #A07830; border-radius: 6px;"
                )
                return

            btn.setStyleSheet("")

        QTimer.singleShot(150, _restore)

    # Définition : construit la table des cycles de production.
    def _build_data_table(self) -> QTableWidget:
        # QTableWidget : tableau des cycles enregistrés.
        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels([
            t("table_col_cycle"),
            t("table_col_fmax_n"),
            t("table_col_xmax_mm"),
            t("table_col_result"),
            t("lbl_time"),
        ])
        table.setStyleSheet(
            "background-color: #FAFAF8; color: #1A1A18; "
            "gridline-color: #C8C4BC; alternate-background-color: #F0EDE6;"
        )
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setDefaultSectionSize(140)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        return table

    # ------------------------------------------------------------------
    # Helpers UI
    # ------------------------------------------------------------------

    # Définition : retourne un séparateur horizontal thémé.
    @staticmethod
    def _make_separator() -> QFrame:
        return make_hseparator(get_colors()["separator"])

    # Définition : retourne un séparateur vertical thémé.
    @staticmethod
    def _make_vsep() -> QFrame:
        return make_vseparator(get_colors()["separator"])

    # ------------------------------------------------------------------
    # Fond de fenêtre dynamique
    # ------------------------------------------------------------------

    # Définition : applique le fond selon l'état machine.
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

    # Définition : fournit le mapping de contenu du badge résultat.
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

    # Définition : met à jour le badge et le fond selon le statut.
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
                f"background-color: {get_colors()['running_bg']}; color: {get_colors()['nav_active']}; "
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

    # Définition : déclenche une animation de clignotement du badge.
    def _flash_badge(self) -> None:
        """Clignote 2 fois rapidement pour attirer l'attention."""
        original_style = self._result_badge.styleSheet()

        # Définition : étape 1 du clignotement du badge.
        def _step1() -> None:
            self._result_badge.setStyleSheet(original_style + "opacity: 0.3;")

        # Définition : étape 2 du clignotement du badge.
        def _step2() -> None:
            self._result_badge.setStyleSheet(original_style)

        # Définition : étape 3 du clignotement du badge.
        def _step3() -> None:
            self._result_badge.setStyleSheet(original_style + "opacity: 0.3;")

        # Définition : étape 4 du clignotement du badge.
        def _step4() -> None:
            self._result_badge.setStyleSheet(original_style)

        QTimer.singleShot(0,   _step1)
        QTimer.singleShot(100, _step2)
        QTimer.singleShot(200, _step3)
        QTimer.singleShot(300, _step4)

    # ------------------------------------------------------------------
    # Slots de données (connectés depuis main.py via AcquisitionBridge)
    # ------------------------------------------------------------------

    # Définition : reçoit un point d'acquisition et met à jour le buffer.
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

    # Définition : traite la fin de cycle et met à jour les vues.
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
        self._fmax_label.setText(f"{fmt_force_dan(self._cycle_fmax)} daN")
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

        if self._stop_cycle_btn is not None:
            self._stop_cycle_btn.setVisible(False)
            self._stop_cycle_btn.setEnabled(True)

        if self._sim_mode:
            self._show_restart_button()

    # Définition : affiche le bouton flottant de redémarrage de cycle.
    def _show_restart_button(self) -> None:
        """Affiche un bouton flottant 'NOUVEAU CYCLE' au centre du graphique."""
        self._ensure_cycle_action_buttons()
        self._restart_btn.setVisible(True)
        self._stop_cycle_btn.setVisible(False)
        self._center_restart_btn()

    # Définition : affiche le bouton flottant d'arrêt du cycle en cours.
    def _show_stop_cycle_button(self) -> None:
        self._ensure_cycle_action_buttons()
        self._restart_btn.setVisible(False)
        self._stop_cycle_btn.setEnabled(True)
        self._stop_cycle_btn.setVisible(True)
        self._center_restart_btn()

    # Définition : crée (si nécessaire) les boutons flottants NOUVEAU/ARRÊTER CYCLE.
    def _ensure_cycle_action_buttons(self) -> None:
        if self._restart_btn is None:
            # QPushButton : lance un nouveau cycle depuis le graphique.
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
            self._restart_btn.clicked.connect(self._on_restart_clicked)

        if self._stop_cycle_btn is None:
            # QPushButton : arrête proprement le cycle en cours.
            self._stop_cycle_btn = QPushButton(t("btn_stop_cycle"), self._graph)
            self._stop_cycle_btn.setStyleSheet("""
                QPushButton {
                    background-color: #C62828;
                    color: #ffffff;
                    font-size: 18px;
                    font-weight: bold;
                    border-radius: 10px;
                    border: 2px solid #8E0000;
                    padding: 14px 30px;
                }
                QPushButton:pressed { background-color: #8E0000; }
            """)
            self._stop_cycle_btn.clicked.connect(self._on_stop_cycle_clicked)

        self._sync_cycle_action_btn_sizes()

    # Définition : impose une taille identique aux boutons NOUVEAU/ARRÊTER CYCLE.
    def _sync_cycle_action_btn_sizes(self) -> None:
        if self._restart_btn is None or self._stop_cycle_btn is None:
            return
        self._restart_btn.adjustSize()
        self._stop_cycle_btn.adjustSize()
        width = max(self._restart_btn.sizeHint().width(), self._stop_cycle_btn.sizeHint().width())
        height = max(self._restart_btn.sizeHint().height(), self._stop_cycle_btn.sizeHint().height())
        self._restart_btn.setFixedSize(width, height)
        self._stop_cycle_btn.setFixedSize(width, height)

    # Définition : centre le bouton de redémarrage sur le graphique.
    def _center_restart_btn(self) -> None:
        if self._restart_btn is None and self._stop_cycle_btn is None:
            return
        gw = self._graph
        if self._restart_btn is not None:
            bw = self._restart_btn.width()
            bh = self._restart_btn.height()
            self._restart_btn.move((gw.width() - bw) // 2, (gw.height() - bh) // 2)
        if self._stop_cycle_btn is not None:
            bw = self._stop_cycle_btn.width()
            bh = self._stop_cycle_btn.height()
            self._stop_cycle_btn.move((gw.width() - bw) // 2, (gw.height() - bh) // 2)

    # Définition : gère le clic sur redémarrage de cycle.
    def _on_restart_clicked(self) -> None:
        if self._restart_btn is not None:
            self._restart_btn.setVisible(False)
        if self._stop_cycle_btn is not None:
            self._stop_cycle_btn.setVisible(True)
            self._stop_cycle_btn.setEnabled(True)
        self._graph.start_new_cycle()
        self._update_result_display("idle")
        if self._restart_callback:
            self._restart_callback()

    # Définition : gère le clic sur arrêt manuel de cycle.
    def _on_stop_cycle_clicked(self) -> None:
        if self._stop_cycle_btn is not None:
            self._stop_cycle_btn.setEnabled(False)
        if self._stop_callback:
            self._stop_callback()

    # Définition : initialise l'état lors du démarrage d'un cycle.
    def on_cycle_started(self) -> None:
        """Appelé quand un nouveau cycle commence."""
        self._cycle_started = False
        self._cycle_fmax = 0.0
        self._cycle_xmax = 0.0
        self._last_force = 0.0
        self._last_pos = 0.0
        self._graph.start_new_cycle()
        self._update_result_display("idle")

        if self._sim_mode:
            self._show_stop_cycle_button()

        # Basculer le bouton en mode "Arrêter"
        manual_btn = self._nav_buttons.get("manual")
        if manual_btn is not None:
            manual_btn.setText(f"⏹  {t('btn_stop_cycle')}")

    # ------------------------------------------------------------------
    # Timer 30 FPS
    # ------------------------------------------------------------------

    # Définition : vide le buffer de points vers le graphique.
    def _flush_buffer(self) -> None:
        if self._point_buffer:
            self._graph.add_points(self._point_buffer)
            self._point_buffer.clear()
            self._update_live_values(self._last_force, self._last_pos)

    # Définition : met à jour les valeurs live et alarmes visuelles.
    def _update_live_values(self, force_n: float, pos_mm: float) -> None:
        self._force_value.setText(f"{fmt_force_dan(force_n)} daN")
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

        self._fmax_label.setText(f"{fmt_force_dan(self._cycle_fmax)} daN")
        self._xmax_label.setText(f"{self._cycle_xmax:.1f} mm")

    # ------------------------------------------------------------------
    # Actions barre de navigation
    # ------------------------------------------------------------------

    # Définition : affiche la vue courbe cycle courant.
    def _show_current_curve(self) -> None:
        self._graph.set_history_mode(False)
        self._content_stack.setCurrentIndex(0)
        if not self._cycle_started:
            self._graph.start_new_cycle()

    # Définition : affiche la vue historique des cycles.
    def _show_history(self) -> None:
        self._graph.set_history_mode(True)
        self._content_stack.setCurrentIndex(0)

    # Définition : affiche la table de données production.
    def _show_data_table(self) -> None:
        self._content_stack.setCurrentIndex(1)

    # Définition : affiche la page de statistiques.
    def _show_stats(self) -> None:
        self._graph.set_history_mode(False)
        self._content_stack.setCurrentIndex(2)
        self._stats_widget.refresh(self._production_log)

    # Définition : lance/arrête un cycle manuel selon l'état.
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

    # Définition : stoppe manuellement le cycle en cours.
    def _stop_manual_cycle(self) -> None:
        """Arrête manuellement le cycle en cours."""
        if self._sim_mode and self._stop_cycle_btn is not None:
            self._stop_cycle_btn.setEnabled(False)
        if self._stop_callback:
            self._stop_callback()

    # Définition : active/désactive le mode d'édition des zones.
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
            self._update_zone_buttons()
        else:
            self._edit_bar.setVisible(False)
            self._right_stack.setCurrentIndex(0)
        for btn in self.findChildren(QPushButton):
            if "Zones" in btn.text():
                if new_mode:
                    btn.setText("✏  Zones ●")
                    btn.setStyleSheet(
                        "background-color: #7A5A20; color: #FFFFFF;"
                        " border: 1px solid #A07830; border-radius: 6px;"
                    )
                else:
                    btn.setText("✏  Zones")
                    btn.setStyleSheet("")
                break

    # Définition : sauvegarde les zones éditées dans la configuration.
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

        if "uni_box_zones" in tools_cfg:
            pm_tools["uni_box_zones"] = tools_cfg["uni_box_zones"]
            pm_tools.pop("uni_box", None)
        elif "uni_box" in tools_cfg:
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

    # Définition : annule les modifications de zones non sauvegardées.
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

    # Définition : met à jour le contenu des coordonnées d'édition.
    def _update_edit_coords(self, tools_cfg: dict) -> None:
        self._refresh_edit_panel()

    # Définition : repositionne les éléments flottants au redimensionnement.
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
        if (hasattr(self, "_restart_btn") and self._restart_btn is not None) or (
            hasattr(self, "_stop_cycle_btn") and self._stop_cycle_btn is not None
        ):
            self._center_restart_btn()
        if hasattr(self, "_pm_label"):
            self._refresh_datetime_line()

    # Définition : anime brièvement un compteur incrémenté.
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

    # Définition : met à jour les compteurs OK/NOK/TOTAL.
    def _update_counters(self) -> None:
        total = self._count_ok + self._count_nok
        self._ok_count_label.setText(f"✓  {self._count_ok}")
        self._nok_count_label.setText(f"✗  {self._count_nok}")
        self._total_count_label.setText(f"Σ  {total}")
        if self._count_ok > 0:
            self._animate_counter(self._ok_count_label)
        if self._count_nok > 0:
            self._animate_counter(self._nok_count_label)

    # Définition : met à jour l'horloge de l'interface.
    def _update_datetime(self) -> None:
        now_str = datetime.now().strftime("%d/%m/%Y  %H:%M:%S")
        if hasattr(self, "_clock_label"):
            self._clock_label.setText(now_str)
        self._refresh_datetime_line()

    # Définition : rafraîchit la ligne PM affichée.
    def _refresh_datetime_line(self) -> None:
        if not hasattr(self, "_pm_label"):
            return
        pm = PM_DEFINITIONS.get(self._pm_id)
        pm_text = f"PM-{self._pm_id:02d}  ·  {pm.name if pm else '—'}"
        pm_metrics = QFontMetrics(self._pm_label.font())
        pm_width = max(140, self._pm_label.width() - 12)
        self._pm_label.setText(pm_metrics.elidedText(pm_text, Qt.TextElideMode.ElideRight, pm_width))
        self._pm_label.setToolTip(pm_text)

    # Définition : réinitialise les compteurs après confirmation.
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

    # Définition : active/désactive le mode simulateur.
    def set_sim_mode(self, enabled: bool) -> None:
        self._sim_mode = enabled

    # Définition : positionne le bouton auto-scale sur le graphique.
    def _position_auto_scale_btn(self) -> None:
        gw = self._graph
        right_margin = 10
        top_margin = 10
        gap = 8

        x = gw.width() - right_margin
        if hasattr(self, "_auto_scale_btn"):
            x -= self._auto_scale_btn.width()
            self._auto_scale_btn.move(x, top_margin)
            x -= gap
        if hasattr(self, "_auto_scale_once_btn"):
            x -= self._auto_scale_once_btn.width()
            self._auto_scale_once_btn.move(x, top_margin)

    # Définition : bascule l'auto-scale et son libellé.
    def _on_auto_scale_toggled(self) -> None:
        self._graph.toggle_auto_scale()
        if self._graph._auto_scale:
            self._auto_scale_btn.setText("⤢ Fixe")
        else:
            self._auto_scale_btn.setText("⤢ Auto")

    # Définition : applique un auto-scale ponctuel sur la courbe affichée.
    def _on_auto_scale_once_clicked(self) -> None:
        self._graph.auto_scale_current_curve()
        self._auto_scale_btn.setChecked(False)
        self._auto_scale_btn.setText("⤢ Auto")

    # Définition : réinitialise le zoom/échelle du graphique aux valeurs par défaut.
    def _reset_graph_zoom(self) -> None:
        self._graph._auto_scale = False
        self._graph.reset_axis_bounds()
        self._auto_scale_btn.setChecked(False)
        self._auto_scale_btn.setText("⤢ Auto")

    # Définition : enregistre le callback de redémarrage de cycle.
    def set_restart_callback(self, callback) -> None:
        self._restart_callback = callback

    # Définition : enregistre le callback d'arrêt de cycle.
    def set_stop_callback(self, callback) -> None:
        self._stop_callback = callback

    # Définition : active l'option cycle manuel selon le contexte.
    def set_manual_cycle_enabled(self, enabled: bool) -> None:
        self._manual_cycle_enabled = enabled
        manual_btn = self._nav_buttons.get("manual") if hasattr(self, "_nav_buttons") else None
        if manual_btn is not None:
            manual_btn.setVisible(enabled and not self._modbus_connected and not self._sim_mode)

    # Définition : met à jour l'état Modbus et la visibilité du cycle manuel.
    def set_modbus_status(self, connected: bool) -> None:
        self._modbus_connected = connected
        manual_btn = self._nav_buttons.get("manual") if hasattr(self, "_nav_buttons") else None
        if manual_btn is not None:
            manual_btn.setVisible(self._manual_cycle_enabled and not connected and not self._sim_mode)

    # Définition : ouvre le sélecteur de PM puis applique le choix.
    def _on_pm_clicked(self) -> None:
        """Ouvre le sélecteur de PM."""
        dlg = PmSelectorDialog(current_pm_id=self._pm_id, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        new_pm_id = dlg.selected_pm_id
        if new_pm_id is None or new_pm_id == self._pm_id:
            return
        self._apply_pm(new_pm_id)

    # Définition : applique un nouveau PM et recharge ses outils.
    def _apply_pm(self, pm_id: int) -> None:
        """Applique le nouveau PM : met à jour l'affichage et recharge les outils."""
        self._pm_id = pm_id
        pm = PM_DEFINITIONS.get(pm_id)
        pm_name = pm.name if pm else f"PM-{pm_id:02d}"
        if hasattr(self, "_pm_btn"):
            self._pm_btn.setToolTip(f"PM-{pm_id:02d}  ·  {pm_name}")
        self._refresh_datetime_line()

        # Recharger les overlays visuels depuis config.yaml
        cfg_path = Path(__file__).parent.parent / "config.yaml"
        cfg = load_config(cfg_path)
        pm_tools = cfg.get("programmes", {}).get(pm_id, {}).get("tools", {})
        self._graph.set_tools_config(pm_tools)

        # Réinitialiser l'affichage du cycle
        self._cycle_fmax = 0.0
        self._cycle_xmax = 0.0
        self._fmax_label.setText("0.0 daN")
        self._xmax_label.setText("0.0 mm")
        self._update_result_display("idle")

    # Définition : applique le thème graphique de l'IHM.
    def apply_theme(self) -> None:
        """Applique le stylesheet du thème clair."""
        c = get_colors()

        new_stylesheet = f"""
QMainWindow, QWidget#central {{
    background-color: {c['bg_main']};
    color: {c['text_primary']};
    font-family: 'Segoe UI', Arial, sans-serif;
}}
/* Style de base applique a tous les textes QLabel de l'IHM (hors labels specialises). */
QLabel {{
    background-color: transparent;
    font-size: 14px;
    font-weight: 500;
}}
/* Badge central PASS/NOK/EN COURS dans le panneau droit. */
QLabel#result_label {{
    font-size: 44px;
    font-weight: bold;
    border-radius: 10px;
    padding: 8px;
}}
/* Compteurs OK/NOK/TOTAL juste sous le badge resultat. */
QLabel#counter_ok   {{ color: {c['ok_text']}; font-size: 22px; font-weight: bold; }}
QLabel#counter_nok  {{ color: {c['nok_text']}; font-size: 22px; font-weight: bold; }}
QLabel#counter_tot  {{ color: {c['text_primary']}; font-size: 22px; font-weight: bold; }}
/* Date/heure en bas du panneau droit. */
QLabel#datetime_label {{ font-size: 13px; color: {c['text_secondary']}; }}
/* Titre PM + valeur PM cliquable dans la zone PM. */
QLabel#pm_section_title {{ font-size: 15px; font-weight: bold; color: {c['blue']}; }}
QLabel#pm_btn_label {{ font-size: 17px; font-weight: bold; color: {c['text_primary']}; }}
/* Labels mesures live (force/position) et pics Fmax/Xmax. */
QLabel#live_label   {{ font-size: 13px; font-weight: 600; color: {c['text_secondary']}; }}
QLabel#live_value   {{ font-size: 38px; font-weight: bold; color: {c['text_primary']}; }}
QLabel#peak_label   {{ font-size: 13px; font-weight: 600; color: {c['text_secondary']}; }}
QLabel#peak_value   {{ font-size: 24px; font-weight: bold; color: {c['blue']}; }}
QProgressBar {{
    border: none; border-radius: 4px;
    background-color: {c['bg_button']};
    max-height: 10px;
}}
QProgressBar::chunk {{
    border-radius: 4px;
    background-color: {c['ok_text']};
}}
QPushButton {{
    transition: none;
    border: 1.5px solid #1A1A18;
}}
QPushButton:pressed {{
    padding-top: 2px;
    padding-left: 2px;
}}
QPushButton#btn_pm {{
    background-color: {COLORS['bg_button']};
    color: {COLORS['text_primary']};
    font-size: 15px;
    font-weight: bold;
    border-top: 2px solid #1A1A18;
    border-right: 2px solid #1A1A18;
    border-bottom: 2px solid #1A1A18;
    border-left: 2px solid #1A1A18;
    border-radius: 0px;
    padding: 4px 8px;
    text-align: left;
}}
QPushButton#btn_settings {{
    background-color: #A07830;
    color: #1A1A18;
    font-size: 13px;
    font-weight: bold;
    border-top: 2px solid #1A1A18;
    border-right: 2px solid #1A1A18;
    border-bottom: 2px solid #1A1A18;
    border-left: 2px solid #1A1A18;
    border-radius: 0px;
    min-height: 36px;
    padding: 0 8px;
}}
QPushButton#btn_settings:hover {{
    background-color: #8B6520;
    color: #1A1A18;
}}
QPushButton#btn_settings:pressed {{
    background-color: #6B4A10;
    color: #1A1A18;
    padding-top: 2px;
}}

QPushButton#nav_btn {{
    background-color: #FAFAF8;
    color: #1A1A18;
    font-size: 14px;
    font-weight: 600;
    border: 1px solid #888480;
    border-radius: 6px;
    min-height: 48px;
    padding: 0 4px;
}}
QPushButton#nav_btn:checked {{
    background-color: #7A5A20;
    color: #FFFFFF;
    border: 1px solid #A07830;
}}
QPushButton#nav_btn:pressed {{
    background-color: #E8E4DC;
    padding-top: 2px;
}}
QPushButton#nav_btn:checked:pressed {{
    background-color: #7A5A20;
}}

QPushButton#nav_btn_red {{
    background-color: #FFF3F3;
    color: #C62828;
    font-size: 14px;
    font-weight: 600;
    border: 1px solid #C62828;
    border-radius: 4px;
    min-height: 48px;
    padding: 0 4px;
}}
QPushButton#nav_btn_red:pressed {{
    background-color: #FFEBEE;
    padding-top: 2px;
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

    # Définition : recharge les préférences d'affichage utilisateur.
    def apply_display_settings(self) -> None:
        """Recharge les préférences d'affichage depuis config.yaml."""
        cfg = load_config(Path(__file__).parent.parent / "config.yaml")
        dp = cfg.get("affichage_prod", {})
        self._badge_style      = dp.get("feu_bicolore",  "Texte")
        self._histogramme_mode = dp.get("histogramme",   "OK-NOK en %")

    # Définition : applique les traductions à l'interface courante.
    def apply_language(self) -> None:
        """Applique la langue courante aux chaînes traduisibles de l'IHM."""
        # Bouton Réglages
        self._settings_btn.setText(f"⚙   {t('btn_settings')}")
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
            self._sync_cycle_action_btn_sizes()

        if hasattr(self, "_stop_cycle_btn") and self._stop_cycle_btn is not None:
            self._stop_cycle_btn.setText(t("btn_stop_cycle"))
            self._sync_cycle_action_btn_sizes()

        if hasattr(self, "_stats_widget"):
            self._stats_widget.apply_language()

        if hasattr(self, "_btn_apply_zones"):
            self._btn_apply_zones.setText(t("btn_apply"))
        if hasattr(self, "_btn_cancel_zones"):
            self._btn_cancel_zones.setText(t("btn_cancel_cross"))
        if hasattr(self, "_edit_panel_title_label"):
            self._edit_panel_title_label.setText(t("edit_zones_title"))
        if hasattr(self, "_reset_zoom_btn"):
            self._reset_zoom_btn.setText(t("btn_reset_zoom"))
        if hasattr(self, "_edit_panel_hint_label"):
            self._edit_panel_hint_label.setText(t("hint_edit_precise_coord"))
        if hasattr(self, "_edit_panel_content"):
            self._build_edit_panel_content()

        settings_page = self.stack.widget(1) if hasattr(self, "stack") else None
        if settings_page is not None and hasattr(settings_page, "apply_language"):
            settings_page.apply_language()
            self._apply_settings_restrictions()

        self._update_level_indicator()

        self._result_badge.setText(t("status_idle"))

    # Définition : définit le niveau d'accès actif.
    def set_access_level(self, level: int) -> None:
        """Définit le niveau d'accès courant."""
        self._access_level = level
        self._update_level_indicator()
        self._update_ui_for_access_level()

    # Définition : met à jour l'indicateur visuel de niveau d'accès.
    def _update_level_indicator(self) -> None:
        """Met à jour le bouton d'accès (état + action de connexion)."""
        if not hasattr(self, "_access_btn"):
            return
        if not self._access_enabled:
            text, fg, bg, border = (t("level_free_icon"), "#6B6860", "#F2F0EB", "#E8E4DC")
        else:
            configs = {
                AccessLevel.NONE:       (f"👤  {t('btn_login')}",   "#4A4844", "#F2F0EB", "#C8C4BC"),
                AccessLevel.OPERATEUR:  (f"🟢  {t('level_operator')}", "#2E7D32", "#F1F8E9", "#2E7D32"),
                AccessLevel.TECHNICIEN: (f"🟡  {t('level_tech')}",     "#A07830", "#FFF8E1", "#C49A3C"),
                AccessLevel.ADMIN:      (f"🔴  {t('level_admin')}",    "#A07830", "#FFF8E1", "#C49A3C"),
            }
            text, fg, bg, border = configs.get(
                self._access_level, (f"👤  {t('btn_login')}", "#4A4844", "#F2F0EB", "#C8C4BC")
            )
        self._access_btn.setText(text)
        self._access_btn.setStyleSheet(
            f"background-color: {bg}; color: {fg}; "
            "font-size: 13px; font-weight: bold; border-radius: 6px; padding: 0 10px; "
            f"border: 1px solid {border};"
        )

    # Définition : applique les droits d'accès sur les contrôles UI.
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

    # Définition : applique les restrictions de la page Réglages.
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

    # Définition : gère le flux connexion/déconnexion par PIN.
    def _on_login_clicked(self) -> None:
        """Connexion / déconnexion depuis le panneau droit."""
        import hashlib

        # Si déjà connecté → déconnexion
        if self._access_level > AccessLevel.NONE:
            self.set_access_level(AccessLevel.NONE)
            return

        # Dialog unique : choix niveau + saisie PIN en une seule page
        dlg = LoginDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        chosen_level = dlg.selected_level
        if chosen_level == AccessLevel.NONE:
            QMessageBox.warning(
                self,
                t("dlg_access_denied_title"),
                t("dlg_level_select_title") + ".",
            )
            return

        # Vérifier le PIN
        cfg = load_config(Path(__file__).parent.parent / "config.yaml")
        ac = cfg.get("access_control", {})
        pin_hash = hashlib.sha256(dlg.pin().encode()).hexdigest()

        level_names = {
            AccessLevel.OPERATEUR:  t("level_operator"),
            AccessLevel.TECHNICIEN: t("level_tech"),
            AccessLevel.ADMIN:      t("level_admin"),
        }
        pin_keys = {
            AccessLevel.OPERATEUR:  ("pin_operateur",  "0000"),
            AccessLevel.TECHNICIEN: ("pin_technicien", "2222"),
            AccessLevel.ADMIN:      ("pin_admin",       "1234"),
        }
        key, default = pin_keys[chosen_level]
        stored = ac.get(key, hashlib.sha256(default.encode()).hexdigest())

        if pin_hash == stored:
            self.set_access_level(chosen_level)
        else:
            QMessageBox.warning(
                self,
                t("dlg_access_denied_title"),
                t("dlg_pin_incorrect_msg").format(
                    level=level_names.get(chosen_level, "")
                ) + ".",
            )

    # Définition : charge la politique de contrôle d'accès depuis la config.
    def _load_access_settings(self) -> None:
        """Charge et applique les préférences de droits depuis config.yaml."""
        cfg = load_config(Path(__file__).parent.parent / "config.yaml")
        ac = cfg.get("access_control", {})
        self._access_enabled = bool(ac.get("enabled", False))
        if self._access_enabled:
            self.set_access_level(AccessLevel.NONE)
        else:
            self._update_level_indicator()

    # Définition : ouvre les réglages si les droits le permettent.
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

    # Définition : ajoute une ligne de cycle dans la table production.
    def _add_production_row(
        self, cycle: int, fmax: float, xmax: float, result: str, hour: str
    ) -> None:
        row = self._data_table.rowCount()
        self._data_table.insertRow(row)
        for col, text in enumerate([str(cycle), fmt_force_dan(fmax), f"{xmax:.1f}", result, hour]):
            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if col == 3:
                item.setForeground(
                    QColor(get_colors()["curve_ok"] if result == "PASS" else get_colors()["curve_nok"])
                )
            self._data_table.setItem(row, col, item)
        self._data_table.scrollToBottom()
