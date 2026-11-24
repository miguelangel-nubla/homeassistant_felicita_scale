"""Tests for the Felicita protocol parser."""

from __future__ import annotations

import pytest

from custom_components.felicita_scale.protocol import (
    StabilityTracker,
    battery_percentage,
    parse_notification,
)

from .conftest import make_packet


def test_parse_grams() -> None:
    reading = parse_notification(make_packet("000540"))
    assert reading is not None
    assert reading.weight == pytest.approx(5.40)
    assert reading.raw_weight == pytest.approx(5.40)
    assert reading.unit == "g"
    assert reading.battery_level == 55


def test_parse_negative() -> None:
    reading = parse_notification(make_packet("001250", sign="-"))
    assert reading is not None
    assert reading.weight == pytest.approx(-12.5)


def test_parse_ounces() -> None:
    reading = parse_notification(make_packet("020140", unit=b"oz"))
    assert reading is not None
    assert reading.unit == "oz"
    assert reading.raw_weight == pytest.approx(2.014)
    assert reading.weight == pytest.approx(2.014 * 28.349523125)


def test_parse_zero() -> None:
    reading = parse_notification(make_packet("000000"))
    assert reading is not None
    assert reading.weight == 0


def test_parse_padded_digits() -> None:
    reading = parse_notification(make_packet("  5400"))
    assert reading is not None
    assert reading.weight == pytest.approx(54.0)


@pytest.mark.parametrize(
    "data",
    [
        bytearray(),
        bytearray(17),
        make_packet() + b"\x00",
        make_packet("      "),
        make_packet("999999"),  # 9999.99 g is beyond the scale's range
    ],
)
def test_parse_rejects(data: bytearray) -> None:
    assert parse_notification(data) is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(0, 0), (129, 0), (145, 55), (158, 100), (200, 100)],
)
def test_battery_percentage(raw: int, expected: int) -> None:
    assert battery_percentage(raw) == expected


def test_stability() -> None:
    tracker = StabilityTracker(readings=3)
    assert not tracker.update(10.0)
    assert not tracker.update(10.0)
    assert tracker.update(10.04)  # Rounds to the same 10.0
    assert not tracker.update(10.5)
    assert not tracker.update(10.5)
    assert tracker.update(10.5)


def test_stability_zero_resets() -> None:
    tracker = StabilityTracker(readings=2)
    assert not tracker.update(5.0)
    assert not tracker.update(0.0)
    assert not tracker.update(5.0)
    assert tracker.update(5.0)
    assert not tracker.update(0.0)
    assert not tracker.update(0.0)
    tracker.reset()
    assert not tracker.update(5.0)
