"""Consommateur: conversion physique, evaluation et stockage cycle."""

from __future__ import annotations

import queue
import threading
from collections.abc import Callable

from core.analysis import CycleManager
from config import PM_DEFINITIONS


class DataProcessor(threading.Thread):
    def __init__(
        self,
        data_queue: queue.Queue,
        stop_event: threading.Event,
        cycle_manager: CycleManager,
        pm_id: int,
        point_callback: Callable[[float, float, float], None] | None = None,
        cycle_callback: Callable[[str], None] | None = None,
        cycle_started_callback: Callable[[], None] | None = None,
        sim_mode: bool = False,
    ) -> None:
        super().__init__(name="DataProcessor", daemon=True)
        self._data_queue = data_queue
        self._stop_event = stop_event
        self._cycle_manager = cycle_manager
        self._pm_id = pm_id
        self._point_callback = point_callback
        self._cycle_callback = cycle_callback
        self._cycle_started_callback = cycle_started_callback
        self._sim_mode = sim_mode
        self._points_for_csv: list[tuple[float, float, float]] = []
        self.saved_csv_path: str | None = None

        if pm_id not in PM_DEFINITIONS:
            raise ValueError(f"PM inconnu: {pm_id}")

    def run(self) -> None:
        first_point = True

        while not (self._stop_event.is_set() and self._data_queue.empty()):
            try:
                block = self._data_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if block is None:
                self._data_queue.task_done()
                final_result = self._cycle_manager.finalize_cycle().value
                if self._cycle_callback:
                    self._cycle_callback(final_result)
                print(f"[PROCESSING] Resultat cycle: {final_result}")
                from core.storage import save_cycle_csv
                csv_path = save_cycle_csv(
                    pm_id=self._pm_id,
                    result=final_result,
                    points=self._points_for_csv,
                )
                self.saved_csv_path = str(csv_path)
                print(f"[PROCESSING] CSV: {csv_path}")
                return  # Un seul cycle en mode sim ; en mode reel idem (1 cycle/thread)

            if first_point:
                if self._cycle_started_callback:
                    self._cycle_started_callback()
                first_point = False

            for t, force_n, pos_mm in block:
                state = self._cycle_manager.add_sample(
                    t=t, force_n=force_n, pos_mm=pos_mm
                )
                self._points_for_csv.append((t, force_n, pos_mm))
                if self._point_callback:
                    self._point_callback(t, force_n, pos_mm)
                if state["result"].value == "NOK":
                    break

            self._data_queue.task_done()