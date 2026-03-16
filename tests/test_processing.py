"""Tests d'integration DataProcessor + queue + threads (sans hardware).

Utilise de vraies queues et de vrais threads. pytest-timeout evite les
blocages infinis (timeout global defini dans pytest.ini : 10 s).
"""

from __future__ import annotations

import queue
import threading
from pathlib import Path

import pytest

import core.storage
from core.analysis import CycleManager
from core.models import EvaluationTool, EvaluationType
from core.processing import DataProcessor


def _make_processor(
    data_queue: queue.Queue,
    stop_event: threading.Event,
    tools: list | None = None,
    pm_id: int = 1,
) -> DataProcessor:
    """Fabrique un DataProcessor avec un CycleManager minimal."""
    cycle_manager = CycleManager(tools=tools or [])
    return DataProcessor(
        data_queue=data_queue,
        stop_event=stop_event,
        cycle_manager=cycle_manager,
        pm_id=pm_id,
    )


@pytest.mark.timeout(10)
def test_processor_consumes_one_block(tmp_path, monkeypatch):
    """Un bloc de 10 points valides suivi de None -> CSV cree."""
    monkeypatch.setattr(core.storage, "DATA_DIR", str(tmp_path))

    dq: queue.Queue = queue.Queue()
    stop = threading.Event()

    block = [(float(i) * 0.001, 1000.0, 30.0) for i in range(10)]
    dq.put(block)
    dq.put(None)

    proc = _make_processor(dq, stop)
    proc.start()
    proc.join(timeout=3.0)

    assert proc.saved_csv_path is not None
    assert Path(proc.saved_csv_path).exists()


@pytest.mark.timeout(10)
def test_processor_nok_on_force_overload(tmp_path, monkeypatch):
    """Force > y_limit dans la zone x -> resultat NOK dans le nom du CSV."""
    monkeypatch.setattr(core.storage, "DATA_DIR", str(tmp_path))

    dq: queue.Queue = queue.Queue()
    stop = threading.Event()

    no_pass_tool = EvaluationTool(
        name="overload",
        tool_type=EvaluationType.NO_PASS,
        x_min=20.0,
        x_max=80.0,
        y_limit=4200.0,
    )
    # force=5000 N > y_limit=4200, pos=50 mm dans [20, 80] -> NOK immediat
    block = [(0.001 * i, 5000.0, 50.0) for i in range(10)]
    dq.put(block)
    dq.put(None)

    cycle_manager = CycleManager(tools=[no_pass_tool])
    proc = DataProcessor(
        data_queue=dq,
        stop_event=stop,
        cycle_manager=cycle_manager,
        pm_id=1,
    )
    proc.start()
    proc.join(timeout=3.0)

    assert proc.saved_csv_path is not None
    assert "NOK" in proc.saved_csv_path


@pytest.mark.timeout(10)
def test_processor_empty_queue(tmp_path, monkeypatch):
    """Queue vide (None seul) -> termine proprement, CSV avec seulement le header."""
    monkeypatch.setattr(core.storage, "DATA_DIR", str(tmp_path))

    dq: queue.Queue = queue.Queue()
    stop = threading.Event()

    dq.put(None)

    proc = _make_processor(dq, stop)
    proc.start()
    proc.join(timeout=3.0)

    assert proc.saved_csv_path is not None
    csv_path = Path(proc.saved_csv_path)
    assert csv_path.exists()
    lines = csv_path.read_text(encoding="utf-8").strip().splitlines()
    # Seulement le header, aucune donnee
    assert len(lines) == 1
    assert lines[0].startswith("time_s")


@pytest.mark.timeout(10)
def test_processor_multiple_blocks(tmp_path, monkeypatch):
    """5 blocs de 50 points -> CSV contient 250 lignes de donnees (+ 1 header)."""
    monkeypatch.setattr(core.storage, "DATA_DIR", str(tmp_path))

    dq: queue.Queue = queue.Queue()
    stop = threading.Event()

    for b in range(5):
        block = [(b * 50 * 0.001 + i * 0.001, 1000.0, 30.0) for i in range(50)]
        dq.put(block)
    dq.put(None)

    proc = _make_processor(dq, stop)
    proc.start()
    proc.join(timeout=3.0)

    assert proc.saved_csv_path is not None
    csv_path = Path(proc.saved_csv_path)
    assert csv_path.exists()
    lines = csv_path.read_text(encoding="utf-8").strip().splitlines()
    # 1 header + 250 lignes de donnees
    assert len(lines) == 251
