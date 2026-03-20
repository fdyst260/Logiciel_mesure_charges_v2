"""Point d'entree du systeme d'acquisition bi-canal de rivetage.

Modes de lancement :
    python main.py           -> acquisition reelle (MCC 118)
    python main.py --sim     -> simulateur sans hardware
    python main.py --sim --fault -> simulateur avec defaut injecte (NOK attendu)
"""

from __future__ import annotations

import os
os.environ.setdefault("QT_IM_MODULE", "none")

import queue
import sys
import threading

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from config import (
    ACQ_THREAD_TIMEOUT,
    MODBUS_THREAD_TIMEOUT,
    PM_DEFINITIONS,
    QUEUE_MAXSIZE,
    THREAD_JOIN_TIMEOUT,
    build_tools_from_yaml,
    load_pm_from_yaml,
)
from core.acquisition import AcquisitionError, acquisition_loop
from core.analysis import CycleManager, DisplayMode
from core.processing import DataProcessor
from ihm.main_window import MainWindow
from simulator.fake_acquisition import fake_acquisition_loop


# ---------------------------------------------------------------------------
# Pont thread-safe entre DataProcessor (thread Python) et MainWindow (Qt)
# ---------------------------------------------------------------------------

class AcquisitionBridge(QObject):
    """Relaie les evenements du thread d'acquisition vers le thread UI Qt.

    Les signaux Qt garantissent la thread-safety : l'emission depuis un thread
    Python non-Qt est automatiquement mise en file vers le thread principal Qt
    (connexion QueuedConnection par defaut entre threads differents).
    """

    new_point: Signal = Signal(float, float, float)  # t, force_n, pos_mm
    cycle_finished: Signal = Signal(str)             # "PASS" ou "NOK"
    cycle_started: Signal = Signal()
    cycle_stop_requested: Signal = Signal()

    def emit_point(self, t: float, force_n: float, pos_mm: float) -> None:
        """Appele depuis le thread DataProcessor — thread-safe via Qt."""
        self.new_point.emit(t, force_n, pos_mm)

    def emit_cycle_finished(self, result: str) -> None:
        """Appele depuis le thread DataProcessor — thread-safe via Qt."""
        self.cycle_finished.emit(result)

    def emit_cycle_started(self) -> None:
        """Appele depuis le thread DataProcessor — thread-safe via Qt."""
        self.cycle_started.emit()

    def emit_cycle_stop(self) -> None:
        """Appele depuis le thread Modbus — thread-safe via Qt."""
        self.cycle_stop_requested.emit()


# ---------------------------------------------------------------------------
# Fonction principale
# ---------------------------------------------------------------------------

def main(use_simulator: bool = False, inject_fault: bool = False, fullscreen: bool = True) -> None:
    app = QApplication(sys.argv)
    load_pm_from_yaml()

    # 1. Pont AVANT les threads (doit vivre dans le thread Qt)
    bridge = AcquisitionBridge()

    # 2. Fenêtre principale
    tools = build_tools_from_yaml(pm_id=1)
    window = MainWindow(pm_id=1, tools=tools, fullscreen=fullscreen)
    bridge.new_point.connect(window.on_new_point)
    bridge.cycle_finished.connect(window.on_cycle_finished)
    bridge.cycle_started.connect(window.on_cycle_started)
    window.set_sim_mode(use_simulator)

    # 3. Infrastructure d'acquisition initiale
    data_queue: queue.Queue = queue.Queue(maxsize=QUEUE_MAXSIZE)
    stop_event = threading.Event()

    cycle_manager = CycleManager(tools=tools, mode=DisplayMode.FORCE_POSITION)
    processor = DataProcessor(
        data_queue=data_queue,
        stop_event=stop_event,
        cycle_manager=cycle_manager,
        pm_id=1,
        point_callback=bridge.emit_point,
        cycle_callback=bridge.emit_cycle_finished,
        cycle_started_callback=bridge.emit_cycle_started,
        sim_mode=use_simulator,
    )
    processor.start()

    acq_fn = fake_acquisition_loop if use_simulator else acquisition_loop
    acq_kwargs: dict = {"inject_fault": inject_fault} if use_simulator else {}
    acq_thread = threading.Thread(
        target=acq_fn,
        kwargs={"data_queue": data_queue, "stop_event": stop_event, **acq_kwargs},
        name="AcquisitionThread",
        daemon=True,
    )
    acq_thread.start()

    # 4. Helper — recrée DataProcessor + acq_thread (réutilisé par sim et Modbus)
    def _start_cycle(fn, kwargs: dict, sim_mode: bool) -> None:
        nonlocal data_queue, stop_event, processor, acq_thread
        stop_event.set()
        stop_event = threading.Event()
        data_queue = queue.Queue(maxsize=QUEUE_MAXSIZE)
        new_manager = CycleManager(
            tools=build_tools_from_yaml(pm_id=window._pm_id),
            mode=DisplayMode.FORCE_POSITION,
        )
        new_proc = DataProcessor(
            data_queue=data_queue,
            stop_event=stop_event,
            cycle_manager=new_manager,
            pm_id=window._pm_id,
            point_callback=bridge.emit_point,
            cycle_callback=bridge.emit_cycle_finished,
            cycle_started_callback=bridge.emit_cycle_started,
            sim_mode=sim_mode,
        )
        new_proc.start()
        new_thread = threading.Thread(
            target=fn,
            kwargs={"data_queue": data_queue, "stop_event": stop_event, **kwargs},
            name="AcquisitionThread",
            daemon=True,
        )
        new_thread.start()
        processor = new_proc
        acq_thread = new_thread

    # 5. Modbus (mode réel) ou bouton relance (mode sim)
    modbus_controller = None
    if not use_simulator:
        from core.modbus_controller import ModbusController
        from pathlib import Path as _Path

        def _on_modbus_cycle_start() -> None:
            _start_cycle(acquisition_loop, {}, sim_mode=False)
            bridge.emit_cycle_started()

        def _on_modbus_cycle_stop() -> None:
            try:
                data_queue.put_nowait(None)
            except Exception:
                pass

        modbus_controller = ModbusController(
            config_path=_Path(__file__).parent / "config.yaml",
            on_cycle_start=_on_modbus_cycle_start,
            on_cycle_stop=_on_modbus_cycle_stop,
        )
        modbus_controller.set_status_callback(window.set_modbus_status)
        modbus_controller.start()
        bridge.cycle_finished.connect(
            lambda result: modbus_controller.write_result(result)
        )
    else:
        def _restart_sim_cycle() -> None:
            _start_cycle(
                fake_acquisition_loop,
                {"inject_fault": inject_fault},
                sim_mode=True,
            )
        window.set_restart_callback(_restart_sim_cycle)

    # 6. Boucle événements Qt
    exit_code = app.exec()

    # 7. Arrêt propre des threads
    stop_event.set()
    try:
        data_queue.put_nowait(None)
    except queue.Full:
        pass
    processor.join(timeout=THREAD_JOIN_TIMEOUT)
    acq_thread.join(timeout=ACQ_THREAD_TIMEOUT)
    if modbus_controller:
        modbus_controller._stop_event.set()
        modbus_controller.join(timeout=MODBUS_THREAD_TIMEOUT)

    sys.exit(exit_code)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="IHM Riveteuse ACM")
    parser.add_argument(
        "--sim",
        action="store_true",
        help="Utiliser le simulateur (sans hardware MCC 118)",
    )
    parser.add_argument(
        "--fault",
        action="store_true",
        help="Injecter un defaut dans le simulateur (force 5200 N -> NOK)",
    )
    parser.add_argument(
        "--windowed",
        action="store_true",
        help="Lancer en mode fenetre (sans plein ecran)",
    )
    args = parser.parse_args()
    main(use_simulator=args.sim, inject_fault=args.fault, fullscreen=not args.windowed)