"""Point d'entree du systeme d'acquisition bi-canal de rivetage."""

from __future__ import annotations

import queue
import threading

from core.acquisition import AcquisitionError, acquisition_loop
from core.analysis import CycleManager, DisplayMode
from config import PM_DEFINITIONS, QUEUE_MAXSIZE
from core.models import EvaluationTool, EvaluationType, Point2D
from core.processing import DataProcessor


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


def main() -> None:
    pm_id = 1
    pm = PM_DEFINITIONS[pm_id]
    print(f"[MAIN] Programme actif: PM{pm.pm_id:02d} - {pm.name}")

    data_queue: queue.Queue = queue.Queue(maxsize=QUEUE_MAXSIZE)
    stop_event = threading.Event()

    cycle_manager = CycleManager(
        tools=build_default_tools(),
        mode=DisplayMode.FORCE_POSITION,
    )
    processor = DataProcessor(
        data_queue=data_queue,
        stop_event=stop_event,
        cycle_manager=cycle_manager,
        pm_id=pm_id,
    )
    processor.start()

    try:
        acquisition_loop(data_queue=data_queue, stop_event=stop_event)

    except KeyboardInterrupt:
        print("\n[MAIN] Ctrl+C recu: arret demande...")

    except AcquisitionError as exc:
        print(f"[MAIN] Erreur acquisition: {exc}")

    finally:
        stop_event.set()
        try:
            data_queue.put_nowait(None)
        except queue.Full:
            pass

        processor.join(timeout=4.0)
        print("[MAIN] Arret propre termine.")


if __name__ == "__main__":
    main()
