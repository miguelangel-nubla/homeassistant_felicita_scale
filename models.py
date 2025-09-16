"""Data models for Chipsea Scale integration."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from homeassistant.util.unit_conversion import MassConverter

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from .coordinator import ChipseaScaleDataUpdateCoordinator


@dataclass
class ChipseaScaleData:
    """Data class for Chipsea scale measurements."""

    weight: float | None = None
    unit: str = "g"
    is_stable: bool = False
    battery_level: int | None = None
    last_measurement: datetime | None = field(default_factory=lambda: datetime.now())

    def update_weight(self, weight: float, is_stable: bool = False) -> None:
        """Update weight measurement."""
        self.weight = weight
        self.is_stable = is_stable
        self.last_measurement = datetime.now()

    def get_weight_in_unit(self, target_unit: str) -> float | None:
        """Get weight converted to target unit using Home Assistant's converter."""
        if self.weight is None:
            return None

        try:
            return MassConverter.convert(self.weight, self.unit, target_unit)
        except ValueError:
            # Return original value if conversion not supported
            return self.weight


type ChipseaScaleConfigEntry = ConfigEntry[ChipseaScaleDataUpdateCoordinator]

