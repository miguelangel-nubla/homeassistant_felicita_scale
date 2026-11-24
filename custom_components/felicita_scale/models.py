"""Data models for the Felicita Scale integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from homeassistant.util import dt as dt_util

from .protocol import UNIT_GRAMS

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from .coordinator import FelicitaScaleDataUpdateCoordinator


@dataclass(slots=True)
class FelicitaScaleData:
    """Latest state reported by the scale."""

    weight: float | None = None  # Weight in grams (normalized)
    unit: str = UNIT_GRAMS  # Unit shown on the scale
    raw_weight: float | None = None  # Weight in the unit shown on the scale
    is_stable: bool = False
    battery_level: int | None = None
    last_measurement: datetime = field(default_factory=dt_util.utcnow)


type FelicitaScaleConfigEntry = ConfigEntry[FelicitaScaleDataUpdateCoordinator]
