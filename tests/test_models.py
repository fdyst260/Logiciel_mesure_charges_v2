"""Tests unitaires purs pour EvaluationTool et EvalStatus (aucun hardware, aucun I/O)."""

from __future__ import annotations

from core.models import EvalStatus, EvaluationTool, EvaluationType, Point2D


# ---------------------------------------------------------------------------
# NO_PASS
# ---------------------------------------------------------------------------

def test_no_pass_inside_zone():
    """Point dans la zone interdite (x dans [x_min, x_max] et y > y_limit) -> NOK."""
    tool = EvaluationTool(
        name="test",
        tool_type=EvaluationType.NO_PASS,
        x_min=20.0,
        x_max=80.0,
        y_limit=4200.0,
    )
    result = tool.evaluate(x=50.0, y=4500.0)
    assert result.status == EvalStatus.NOK


def test_no_pass_outside_zone():
    """Point hors plage x -> RUNNING (zone interdite non atteinte)."""
    tool = EvaluationTool(
        name="test",
        tool_type=EvaluationType.NO_PASS,
        x_min=20.0,
        x_max=80.0,
        y_limit=4200.0,
    )
    result = tool.evaluate(x=10.0, y=4500.0)
    assert result.status == EvalStatus.RUNNING


def test_no_pass_below_limit():
    """Point dans la plage x mais y sous y_limit -> RUNNING."""
    tool = EvaluationTool(
        name="test",
        tool_type=EvaluationType.NO_PASS,
        x_min=20.0,
        x_max=80.0,
        y_limit=4200.0,
    )
    result = tool.evaluate(x=50.0, y=3000.0)
    assert result.status == EvalStatus.RUNNING


# ---------------------------------------------------------------------------
# ENVELOPE
# ---------------------------------------------------------------------------

def test_envelope_inside():
    """Point entre les deux courbes -> RUNNING."""
    tool = EvaluationTool(
        name="test",
        tool_type=EvaluationType.ENVELOPE,
        lower_curve=[Point2D(0, 0), Point2D(100, 1000)],
        upper_curve=[Point2D(0, 500), Point2D(100, 5000)],
    )
    result = tool.evaluate(x=50.0, y=2000.0)
    assert result.status == EvalStatus.RUNNING


def test_envelope_outside_above():
    """Point au-dessus de la courbe superieure -> NOK."""
    tool = EvaluationTool(
        name="test",
        tool_type=EvaluationType.ENVELOPE,
        lower_curve=[Point2D(0, 0), Point2D(100, 1000)],
        upper_curve=[Point2D(0, 500), Point2D(100, 5000)],
    )
    result = tool.evaluate(x=50.0, y=5500.0)
    assert result.status == EvalStatus.NOK


def test_envelope_outside_x_range():
    """Point hors de la plage x des courbes -> RUNNING (pas de donnees = pas d'erreur)."""
    tool = EvaluationTool(
        name="test",
        tool_type=EvaluationType.ENVELOPE,
        lower_curve=[Point2D(0, 0), Point2D(100, 1000)],
        upper_curve=[Point2D(0, 500), Point2D(100, 5000)],
    )
    result = tool.evaluate(x=150.0, y=2000.0)
    assert result.status == EvalStatus.RUNNING


# ---------------------------------------------------------------------------
# UNI_BOX
# ---------------------------------------------------------------------------

def test_unibox_valid_entry_exit():
    """Entree par la gauche, sortie par la droite -> PASS."""
    tool = EvaluationTool(
        name="test",
        tool_type=EvaluationType.UNI_BOX,
        box_x_min=10.0,
        box_x_max=40.0,
        box_y_min=500.0,
        box_y_max=2500.0,
        entry_side="left",
        exit_side="right",
    )
    p_before = Point2D(5.0, 1000.0)    # hors boite, a gauche
    p_inside = Point2D(25.0, 1000.0)   # dans la boite
    p_after  = Point2D(50.0, 1000.0)   # hors boite, a droite

    tool.evaluate(x=p_before.x, y=p_before.y)
    tool.evaluate(x=p_inside.x, y=p_inside.y, previous=p_before)
    result = tool.evaluate(x=p_after.x, y=p_after.y, previous=p_inside)
    assert result.status == EvalStatus.PASS


def test_unibox_invalid_entry():
    """Entree par le bas alors qu'on attend la gauche -> NOK."""
    tool = EvaluationTool(
        name="test",
        tool_type=EvaluationType.UNI_BOX,
        box_x_min=10.0,
        box_x_max=40.0,
        box_y_min=500.0,
        box_y_max=2500.0,
        entry_side="left",
        exit_side="right",
    )
    p_before = Point2D(25.0, 200.0)   # hors boite, par le bas (y < box_y_min)
    p_inside = Point2D(25.0, 800.0)   # dans la boite

    result = tool.evaluate(x=p_inside.x, y=p_inside.y, previous=p_before)
    assert result.status == EvalStatus.NOK


def test_tool_reset():
    """reset() remet _entered=False, _entry_side_seen=None, _exit_validated=False."""
    tool = EvaluationTool(
        name="test",
        tool_type=EvaluationType.UNI_BOX,
        box_x_min=10.0,
        box_x_max=40.0,
        box_y_min=500.0,
        box_y_max=2500.0,
        entry_side="left",
        exit_side="right",
    )
    # Simule une entree dans la boite pour alterer l'etat interne
    p_before = Point2D(5.0, 1000.0)
    p_inside = Point2D(25.0, 1000.0)
    tool.evaluate(x=p_before.x, y=p_before.y)
    tool.evaluate(x=p_inside.x, y=p_inside.y, previous=p_before)
    assert tool._entered is True

    tool.reset()

    assert tool._entered is False
    assert tool._entry_side_seen is None
    assert tool._exit_validated is False
