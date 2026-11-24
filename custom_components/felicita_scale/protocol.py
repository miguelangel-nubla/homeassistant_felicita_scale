"""Felicita scale Bluetooth protocol.

Pure parsing helpers with no Home Assistant dependencies, so they can be unit
tested in isolation. See protocol_notes.txt for the packet layout.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

PACKET_LENGTH = 18
SIGN_BYTE_INDEX = 2
WEIGHT_SLICE = slice(3, 9)
UNIT_SLICE = slice(9, 11)
BATTERY_BYTE_INDEX = 15

SIGN_NEGATIVE = ord("-")

MIN_BATTERY_LEVEL = 129
MAX_BATTERY_LEVEL = 158

# The scale never reports anything this heavy; larger values are garbage
MAX_WEIGHT_GRAMS = 5000

UNIT_GRAMS = "g"
UNIT_OUNCES = "oz"

# Divisor that turns the six weight digits into the scale's native unit
UNIT_DIVISORS = {UNIT_GRAMS: 100, UNIT_OUNCES: 10000}
GRAMS_PER_UNIT = {UNIT_GRAMS: 1.0, UNIT_OUNCES: 28.349523125}

STABLE_READINGS = 4


@dataclass(frozen=True, slots=True)
class FelicitaReading:
    """A single decoded notification from the scale."""

    weight: float
    """Weight in grams."""
    raw_weight: float
    """Weight in the unit shown on the scale."""
    unit: str
    battery_level: int


def battery_percentage(value: int) -> int:
    """Convert the raw battery byte to a percentage."""
    value = min(max(value, MIN_BATTERY_LEVEL), MAX_BATTERY_LEVEL)
    return round(
        (value - MIN_BATTERY_LEVEL) / (MAX_BATTERY_LEVEL - MIN_BATTERY_LEVEL) * 100
    )


def parse_unit(data: bytes) -> str:
    """Return the unit shown on the scale."""
    text = bytes(data[UNIT_SLICE]).decode("ascii", errors="ignore").strip().lower()
    if text.startswith(UNIT_OUNCES):
        return UNIT_OUNCES
    return UNIT_GRAMS


def parse_notification(data: bytes | bytearray) -> FelicitaReading | None:
    """Decode a weight notification, or return None if it is not one."""
    if len(data) != PACKET_LENGTH:
        return None

    # Weight is six ASCII digits; tolerate padding by keeping only the digits
    digits = bytes(b for b in data[WEIGHT_SLICE] if 0x30 <= b <= 0x39)
    if not digits:
        return None

    unit = parse_unit(data)
    raw_weight = int(digits) / UNIT_DIVISORS[unit]
    if data[SIGN_BYTE_INDEX] == SIGN_NEGATIVE:
        raw_weight = -raw_weight

    weight = raw_weight * GRAMS_PER_UNIT[unit]
    if abs(weight) > MAX_WEIGHT_GRAMS:
        return None

    return FelicitaReading(
        weight=weight,
        raw_weight=raw_weight,
        unit=unit,
        battery_level=battery_percentage(data[BATTERY_BYTE_INDEX]),
    )


class StabilityTracker:
    """Report a weight as stable after several identical consecutive readings."""

    def __init__(self, readings: int = STABLE_READINGS) -> None:
        """Initialize the tracker."""
        self._history: deque[float] = deque(maxlen=readings)

    def update(self, weight: float) -> bool:
        """Add a reading and return whether the weight is now stable."""
        rounded = round(weight, 1)
        if rounded == 0:
            # An empty or freshly tared scale is never "stable"
            self._history.clear()
            return False
        self._history.append(rounded)
        return (
            len(self._history) == self._history.maxlen and len(set(self._history)) == 1
        )

    def reset(self) -> None:
        """Forget all readings."""
        self._history.clear()
