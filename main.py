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

from config import PM_DEFINITIONS, QUEUE_MAXSIZE, load_pm_from_yaml
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
    cycle_started: Signal = Signal()

    def emit_point(self, t: float, force_n: float, pos_mm: float) -> None:
        """Appele depuis le thread DataProcessor — thread-safe via Qt."""
        self.new_point.emit(t, force_n, pos_mm)

    def emit_cycle_finished(self, result: str) -> None:
        """Appele depuis le thread DataProcessor — thread-safe via Qt."""
        self.cycle_finished.emit(result)

    def emit_cycle_started(self) -> None:
        """Appele depuis le thread DataProcessor — thread-safe via Qt."""
        self.cycle_started.emit()


# ---------------------------------------------------------------------------
# Outils d'evaluation par defaut
# ---------------------------------------------------------------------------

def build_tools_from_yaml(pm_id: int) -> list[EvaluationTool]:
    """Charge les outils d'évaluation depuis config.yaml pour un PM donné.
    Retourne les outils par défaut si le PM n'est pas configuré."""
    import yaml
    from pathlib import Path

    cfg_path = Path(__file__).parent / "config.yaml"
    try:
        with open(cfg_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        tools_data = cfg.get("programmes", {}).get(pm_id, {}).get("tools", {})
    except Exception:
        return build_default_tools()

    tools: list[EvaluationTool] = []

    np_d = tools_data.get("no_pass", {})
    if np_d.get("enabled", False):
        tools.append(EvaluationTool(
            name="no_pass",
            tool_type=EvaluationType.NO_PASS,
            x_min=np_d["x_min"], x_max=np_d["x_max"], y_limit=np_d["y_limit"],
        ))

    ub_d = tools_data.get("uni_box", {})
    if ub_d.get("enabled", False):
        tools.append(EvaluationTool(
            name="uni_box",
            tool_type=EvaluationType.UNI_BOX,
            box_x_min=ub_d["box_x_min"], box_x_max=ub_d["box_x_max"],
            box_y_min=ub_d["box_y_min"], box_y_max=ub_d["box_y_max"],
            entry_side=ub_d["entry_side"], exit_side=ub_d["exit_side"],
        ))

    env_d = tools_data.get("envelope", {})
    if env_d.get("enabled", False):
        tools.append(EvaluationTool(
            name="envelope",
            tool_type=EvaluationType.ENVELOPE,
            lower_curve=[Point2D(p[0], p[1]) for p in env_d["lower_curve"]],
            upper_curve=[Point2D(p[0], p[1]) for p in env_d["upper_curve"]],
        ))

    return tools if tools else build_default_tools()


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

def main(use_simulator: bool = False, inject_fault: bool = False, fullscreen: bool = True) -> None:
    app = QApplication(sys.argv)

    # Charger les PM personnalisés depuis config.yaml
    load_pm_from_yaml()

    # 1. Pont AVANT les threads (doit vivre dans le thread Qt)
    bridge = AcquisitionBridge()

    # 2. Fenetre principale + connexion des signaux (QueuedConnection auto)
    tools = build_tools_from_yaml(pm_id=1)
    window = MainWindow(pm_id=1, tools=tools, fullscreen=fullscreen)
    bridge.new_point.connect(window.on_new_point)
    bridge.cycle_finished.connect(window.on_cycle_finished)
    bridge.cycle_started.connect(window.on_cycle_started)

    window.set_sim_mode(use_simulator)

    # 3. Infrastructure d'acquisition (variables mutables via nonlocal dans _restart_sim_cycle)
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
        cycle_started_callback=bridge.emit_cycle_started,
        sim_mode=use_simulator,
    )

    # 4. Demarrage du thread DataProcessor
    processor.start()

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

    # 6. Callback relance cycle simulateur (bouton "NOUVEAU CYCLE")
    def _restart_sim_cycle() -> None:
        """Recrée un DataProcessor et un acq_thread pour un nouveau cycle sim."""
        nonlocal data_queue, stop_event, processor, acq_thread

        # Signaler l'arrêt des anciens threads (déjà terminés, mais par précaution)
        stop_event.set()

        # Nouveau stop_event et queue propres
        stop_event = threading.Event()
        data_queue = queue.Queue(maxsize=QUEUE_MAXSIZE)

        # Nouveau CycleManager (repart de zéro)
        new_cycle_manager = CycleManager(
            tools=build_tools_from_yaml(pm_id=window._pm_id),
            mode=DisplayMode.FORCE_POSITION,
        )

        new_processor = DataProcessor(
            data_queue=data_queue,
            stop_event=stop_event,
            cycle_manager=new_cycle_manager,
            pm_id=window._pm_id,
            point_callback=bridge.emit_point,
            cycle_callback=bridge.emit_cycle_finished,
            cycle_started_callback=bridge.emit_cycle_started,
            sim_mode=True,
        )
        new_processor.start()

        new_acq_thread = threading.Thread(
            target=fake_acquisition_loop,
            kwargs={
                "data_queue": data_queue,
                "stop_event": stop_event,
                "inject_fault": inject_fault,
            },
            name="AcquisitionThread",
            daemon=True,
        )
        new_acq_thread.start()

        processor = new_processor
        acq_thread = new_acq_thread

    if use_simulator:
        window.set_restart_callback(_restart_sim_cycle)

    # 7. Boucle evenements Qt (bloquant jusqu'a fermeture de la fenetre)
    exit_code = app.exec()

    # 8. Arret propre des threads d'acquisition
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
    parser.add_argument(
        "--windowed",
        action="store_true",
        help="Lancer en mode fenetre (sans plein ecran)",
    )
    args = parser.parse_args()
    main(use_simulator=args.sim, inject_fault=args.fault, fullscreen=not args.windowed)