"""Tests unitaires pour SensorCalibrator (aucun hardware, aucun I/O)."""

from __future__ import annotations

import pytest

from core.acquisition import SensorCalibrator


def test_force_zero_volt():
    """0.0 V -> 0.0 N."""
    cal = SensorCalibrator()
    assert cal.calibrate_force(0.0) == 0.0


def test_force_full_scale():
    """10.0 V -> 5000.0 N."""
    cal = SensorCalibrator()
    assert cal.calibrate_force(10.0) == pytest.approx(5000.0)


def test_force_mid_scale():
    """5.0 V -> 2500.0 N."""
    cal = SensorCalibrator()
    assert cal.calibrate_force(5.0) == pytest.approx(2500.0)


def test_position_zero_volt():
    """0.0 V -> 0.0 mm."""
    cal = SensorCalibrator()
    assert cal.calibrate_position(0.0) == 0.0


def test_position_full_scale():
    """10.0 V -> 100.0 mm."""
    cal = SensorCalibrator()
    assert cal.calibrate_position(10.0) == pytest.approx(100.0)


def test_calibrate_pair():
    """(5.0 V, 2.5 V) -> (2500.0 N, 25.0 mm)."""
    cal = SensorCalibrator()
    force_n, pos_mm = cal.calibrate_pair(5.0, 2.5)
    assert force_n == pytest.approx(2500.0)
    assert pos_mm == pytest.approx(25.0)


def test_force_negative_voltage():
    """Tension negative : comportement lineaire attendu, pas d'exception."""
    cal = SensorCalibrator()
    assert cal.calibrate_force(-1.0) == pytest.approx(-500.0)


def test_force_overflow_voltage():
    """Tension > pleine echelle : pas de clamp, comportement lineaire attendu."""
    cal = SensorCalibrator()
    assert cal.calibrate_force(11.0) == pytest.approx(5500.0)
