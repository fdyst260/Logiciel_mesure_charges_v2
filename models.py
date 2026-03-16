"""Modeles metier d'evaluation de cycle rivetage."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class EvaluationType(str, Enum):
    NO_PASS = "NO_PASS"
    UNI_BOX = "UNI_BOX"
    ENVELOPE = "ENVELOPE"


class EvalStatus(str, Enum):
    RUNNING = "RUNNING"
    PASS = "PASS"
    NOK = "NOK"


@dataclass(frozen=True)
class Point2D:
    x: float
    y: float


@dataclass
class EvaluationResult:
    status: EvalStatus
    triggered: bool = False
    message: str = ""


@dataclass
class EvaluationTool:
    """Outil d'evaluation generique pour courbes Y=f(X)."""

    name: str
    tool_type: EvaluationType

    # NO_PASS
    x_min: float | None = None
    x_max: float | None = None
    y_limit: float | None = None

    # UNI_BOX
    box_x_min: float | None = None
    box_x_max: float | None = None
    box_y_min: float | None = None
    box_y_max: float | None = None
    entry_side: str | None = None  # left/right/top/bottom
    exit_side: str | None = None

    # ENVELOPE (x croissant)
    lower_curve: list[Point2D] = field(default_factory=list)
    upper_curve: list[Point2D] = field(default_factory=list)

    # Etat interne UNI_BOX
    _entered: bool = field(default=False, init=False)
    _entry_side_seen: str | None = field(default=None, init=False)
    _exit_validated: bool = field(default=False, init=False)

    def reset(self) -> None:
        """Remet a zero l'etat interne UNI_BOX entre deux cycles consecutifs."""
        self._entered = False
        self._entry_side_seen = None
        self._exit_validated = False

    def evaluate(self, x: float, y: float, previous: Point2D | None = None) -> EvaluationResult:
        if self.tool_type == EvaluationType.NO_PASS:
            return self._eval_no_pass(x, y)
        if self.tool_type == EvaluationType.UNI_BOX:
            return self._eval_uni_box(x, y, previous)
        if self.tool_type == EvaluationType.ENVELOPE:
            return self._eval_envelope(x, y)
        return EvaluationResult(EvalStatus.RUNNING)

    def _eval_no_pass(self, x: float, y: float) -> EvaluationResult:
        if None in (self.x_min, self.x_max, self.y_limit):
            return EvaluationResult(EvalStatus.RUNNING)

        if self.x_min < x < self.x_max and y > self.y_limit:
            return EvaluationResult(
                status=EvalStatus.NOK,
                triggered=True,
                message=f"NO-PASS: zone interdite atteinte ({x:.3f}, {y:.3f})",
            )
        return EvaluationResult(EvalStatus.RUNNING)

    def _eval_uni_box(self, x: float, y: float, previous: Point2D | None) -> EvaluationResult:
        if None in (self.box_x_min, self.box_x_max, self.box_y_min, self.box_y_max):
            return EvaluationResult(EvalStatus.RUNNING)

        inside = self._is_inside_box(x, y)
        previous_inside = self._is_inside_box(previous.x, previous.y) if previous else False

        if not self._entered and inside and not previous_inside and previous is not None:
            side = self._crossed_side(previous, Point2D(x, y))
            self._entered = True
            self._entry_side_seen = side
            if self.entry_side and side != self.entry_side:
                return EvaluationResult(
                    status=EvalStatus.NOK,
                    triggered=True,
                    message=f"UNI-BOX: entree invalide ({side})",
                )

        if self._entered and previous_inside and not inside and previous is not None:
            side = self._crossed_side(previous, Point2D(x, y))
            if self.exit_side and side != self.exit_side:
                return EvaluationResult(
                    status=EvalStatus.NOK,
                    triggered=True,
                    message=f"UNI-BOX: sortie invalide ({side})",
                )
            self._exit_validated = True
            return EvaluationResult(EvalStatus.PASS, triggered=True, message="UNI-BOX valide")

        return EvaluationResult(EvalStatus.RUNNING)

    def _eval_envelope(self, x: float, y: float) -> EvaluationResult:
        if not self.lower_curve or not self.upper_curve:
            return EvaluationResult(EvalStatus.RUNNING)

        lower = self._interpolate(self.lower_curve, x)
        upper = self._interpolate(self.upper_curve, x)
        if lower is None or upper is None:
            return EvaluationResult(EvalStatus.RUNNING)

        if not (lower <= y <= upper):
            return EvaluationResult(
                status=EvalStatus.NOK,
                triggered=True,
                message=f"ENVELOPE: hors limites ({lower:.2f} <= {y:.2f} <= {upper:.2f})",
            )
        return EvaluationResult(EvalStatus.RUNNING)

    def _is_inside_box(self, x: float, y: float) -> bool:
        assert self.box_x_min is not None
        assert self.box_x_max is not None
        assert self.box_y_min is not None
        assert self.box_y_max is not None
        return self.box_x_min <= x <= self.box_x_max and self.box_y_min <= y <= self.box_y_max

    def _crossed_side(self, p1: Point2D, p2: Point2D) -> str:
        assert self.box_x_min is not None
        assert self.box_x_max is not None
        assert self.box_y_min is not None
        assert self.box_y_max is not None

        if p1.x < self.box_x_min <= p2.x or p2.x < self.box_x_min <= p1.x:
            return "left"
        if p1.x > self.box_x_max >= p2.x or p2.x > self.box_x_max >= p1.x:
            return "right"
        if p1.y < self.box_y_min <= p2.y or p2.y < self.box_y_min <= p1.y:
            return "bottom"
        if p1.y > self.box_y_max >= p2.y or p2.y > self.box_y_max >= p1.y:
            return "top"
        return "unknown"

    @staticmethod
    def _interpolate(curve: Iterable[Point2D], x: float) -> float | None:
        points = list(curve)
        if len(points) < 2:
            return None
        if x < points[0].x or x > points[-1].x:
            return None

        for idx in range(len(points) - 1):
            p1, p2 = points[idx], points[idx + 1]
            if p1.x <= x <= p2.x:
                if p2.x == p1.x:
                    return p1.y
                ratio = (x - p1.x) / (p2.x - p1.x)
                return p1.y + ratio * (p2.y - p1.y)
        return None
