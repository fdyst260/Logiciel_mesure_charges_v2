"""Point d'entree du systeme d'acquisition bi-canal de rivetage.

Modes de lancement :
    python main.py           -> acquisition reelle (MCC 118)
    python main.py --sim     -> simulateur sans hardware
    python main.py --sim --fault -> simulateur avec defaut injecte (NOK attendu)
"""

from __future__ import annotations

import queue
import sys
import threading

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from config import PM_DEFINITIONS, QUEUE_MAXSIZE
from core.acquisition import AcquisitionError, acquisition_loop
from core.analysis import CycleManager, DisplayMode
from core.models import EvaluationTool, EvaluationType, Point2D
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

    def emit_point(self, t: float, force_n: float, pos_mm: float) -> None:
        """Appele depuis le thread DataProcessor — thread-safe via Qt."""
        self.new_point.emit(t, force_n, pos_mm)

    def emit_cycle_finished(self, result: str) -> None:
        """Appele depuis le thread DataProcessor — thread-safe via Qt."""
        self.cycle_finished.emit(result)


# ---------------------------------------------------------------------------
# Outils d'evaluation par defaut
# ---------------------------------------------------------------------------

def build_default_tools() -> list[EvaluationTool]:
    """Jeu d'outils d'evaluation type pour Force=f(Position)."""
    return [
        EvaluationTool(
            name="no_pass_overload",
            tool_type=EvaluationType.NO_PASS,
            x_min=20.0,
            x_max=80.0,
            y_limit=4200.0,
        ),
        EvaluationTool(
            name="uni_box_fitting",
            tool_type=EvaluationType.UNI_BOX,
            box_x_min=10.0,
            box_x_max=40.0,
            box_y_min=500.0,
            box_y_max=2500.0,
            entry_side="left",
            exit_side="right",
        ),
        EvaluationTool(
            name="envelope_signature",
            tool_type=EvaluationType.ENVELOPE,
            lower_curve=[Point2D(0.0, 0.0), Point2D(100.0, 3000.0)],
            upper_curve=[Point2D(0.0, 500.0), Point2D(100.0, 5000.0)],
        ),
    ]


# ---------------------------------------------------------------------------
# Fonction principale
# ---------------------------------------------------------------------------

def main(use_simulator: bool = False, inject_fault: bool = False) -> None:
    app = QApplication(sys.argv)

    # 1. Pont AVANT les threads (doit vivre dans le thread Qt)
    bridge = AcquisitionBridge()

    # 2. Fenetre principale + connexion des signaux (QueuedConnection auto)
    tools = build_default_tools()
    window = MainWindow(pm_id=1, tools=tools)
    bridge.new_point.connect(window.on_new_point)
    bridge.cycle_finished.connect(window.on_cycle_finished)

    # 3. Infrastructure d'acquisition
    data_queue: queue.Queue = queue.Queue(maxsize=QUEUE_MAXSIZE)
    stop_event = threading.Event()
    pm_id = 1

    cycle_manager = CycleManager(
        tools=tools,
        mode=DisplayMode.FORCE_POSITION,
    )
    processor = DataProcessor(
        data_queue=data_queue,
        stop_event=stop_event,
        cycle_manager=cycle_manager,
        pm_id=pm_id,
        point_callback=bridge.emit_point,
        cycle_callback=bridge.emit_cycle_finished,
    )

    # 4. Demarrage du thread DataProcessor
    processor.start()
    window.on_cycle_started()

    # 5. Demarrage du thread d'acquisition (simulateur ou reel)
    acq_fn = fake_acquisition_loop if use_simulator else acquisition_loop
    acq_kwargs: dict = {"inject_fault": inject_fault} if use_simulator else {}

    acq_thread = threading.Thread(
        target=acq_fn,
        kwargs={"data_queue": data_queue, "stop_event": stop_event, **acq_kwargs},
        name="AcquisitionThread",
        daemon=True,
    )
    acq_thread.start()

    # 6. Boucle evenements Qt (bloquant jusqu'a fermeture de la fenetre)
    exit_code = app.exec()

    # 7. Arret propre des threads d'acquisition
    stop_event.set()
    try:
        data_queue.put_nowait(None)
    except queue.Full:
        pass
    processor.join(timeout=4.0)
    acq_thread.join(timeout=2.0)

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
    args = parser.parse_args()
    main(use_simulator=args.sim, inject_fault=args.fault)
