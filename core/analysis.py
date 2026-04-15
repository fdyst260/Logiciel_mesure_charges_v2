"""Analyse temps reel de cycle et pilotage des sorties."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from config import (
    FORCE_THRESHOLD_N,
    GPIO_OUT_ALARM,
    GPIO_OUT_NOK,
    GPIO_OUT_OK,
    POSITION_THRESHOLD_MM,
)
from core.models import EvalStatus, EvaluationResult, EvaluationTool, Point2D


class DisplayMode(str, Enum):
    FORCE_TIME = "A"
    FORCE_POSITION = "B"
    POSITION_TIME = "C"


@dataclass(frozen=True)
class Sample:
    t: float
    force_n: float
    pos_mm: float


class GpioOutputController:
    """Pilote 3 sorties GPIO: OK, NOK, Alarme Seuil."""

    def __init__(
        self,
        ok_pin: int = GPIO_OUT_OK,
        nok_pin: int = GPIO_OUT_NOK,
        alarm_pin: int = GPIO_OUT_ALARM,
    ) -> None:
        self.ok_pin = ok_pin
        self.nok_pin = nok_pin
        self.alarm_pin = alarm_pin
        self._ready = False
        self._pins: dict[str, object] = {}

        try:
            from gpiozero import DigitalOutputDevice

            self._pins["ok"] = DigitalOutputDevice(ok_pin)
            self._pins["nok"] = DigitalOutputDevice(nok_pin)
            self._pins["alarm"] = DigitalOutputDevice(alarm_pin)
            self._ready = True
        except Exception:
            # En dev hors Pi/GPIO, on fonctionne en mode degrade (sans exception).
            self._ready = False

    def drive_outputs(self, ok: bool, nok: bool, alarm: bool) -> None:
        if not self._ready:
            return
        self._write("ok", ok)
        self._write("nok", nok)
        self._write("alarm", alarm)

    def _write(self, key: str, state: bool) -> None:
        pin = self._pins[key]
        if state:
            pin.on()
        else:
            pin.off()


class CycleManager:
    """Supervise le cycle: stockage points, evaluation et alarmes temps reel."""

    def __init__(
        self,
        tools: list[EvaluationTool] | None = None,
        mode: DisplayMode = DisplayMode.FORCE_POSITION,
        force_threshold_n: float = FORCE_THRESHOLD_N,
        position_threshold_mm: float = POSITION_THRESHOLD_MM,
        gpio: GpioOutputController | None = None,
    ) -> None:
        self.mode = mode
        self.tools = tools or []
        self.force_threshold_n = force_threshold_n
        self.position_threshold_mm = position_threshold_mm
        self.gpio = gpio or GpioOutputController()

        self.points: list[Sample] = []
        self.result: EvalStatus = EvalStatus.RUNNING
        self.messages: list[str] = []

    def add_sample(self, t: float, force_n: float, pos_mm: float) -> dict[str, object]:
        sample = Sample(t=t, force_n=force_n, pos_mm=pos_mm)
        prev = self.points[-1] if self.points else None
        self.points.append(sample)

        alarm_force = force_n >= self.force_threshold_n
        alarm_position = pos_mm >= self.position_threshold_mm
        alarm_threshold = alarm_force or alarm_position

        _xy_sample = self._xy(sample)
        x, y = _xy_sample.x, _xy_sample.y
        previous_xy = self._xy(prev) if prev else None

        tool_results: list[EvaluationResult] = []
        if self.result != EvalStatus.NOK:
            for tool in self.tools:
                res = tool.evaluate(x=x, y=y, previous=previous_xy)
                tool_results.append(res)
                if res.triggered and res.message:
                    self.messages.append(res.message)
                if res.status == EvalStatus.NOK:
                    self.result = EvalStatus.NOK
                    break

        ok = self.result == EvalStatus.PASS
        nok = self.result == EvalStatus.NOK
        self.gpio.drive_outputs(ok=ok, nok=nok, alarm=alarm_threshold)

        return {
            "sample": sample,
            "alarm_force": alarm_force,
            "alarm_position": alarm_position,
            "alarm_threshold": alarm_threshold,
            "result": self.result,
            "tool_results": tool_results,
        }

    def finalize_cycle(self) -> EvalStatus:
        for tool in self.tools:
            res = tool.finalize()
            if res.status == EvalStatus.NOK:
                self.result = EvalStatus.NOK
                if res.message:
                    self.messages.append(res.message)
                break

        if self.result == EvalStatus.RUNNING:
            self.result = EvalStatus.PASS
        self.gpio.drive_outputs(
            ok=self.result == EvalStatus.PASS,
            nok=self.result == EvalStatus.NOK,
            alarm=False,
        )
        return self.result

    def _xy(self, sample: Sample | None) -> Point2D | None:
        if sample is None:
            return None
        if self.mode == DisplayMode.FORCE_TIME:
            return Point2D(sample.t, sample.force_n)
        if self.mode == DisplayMode.POSITION_TIME:
            return Point2D(sample.t, sample.pos_mm)
        return Point2D(sample.pos_mm, sample.force_n)
