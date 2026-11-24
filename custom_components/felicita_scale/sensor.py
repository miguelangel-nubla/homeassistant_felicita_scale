"""Sensor platform for the Felicita Scale integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfMass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FelicitaScaleDataUpdateCoordinator
from .entity import FelicitaScaleEntity
from .models import FelicitaScaleConfigEntry, FelicitaScaleData

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class FelicitaScaleSensorEntityDescription(SensorEntityDescription):
    """Describes a Felicita Scale sensor."""

    value_fn: Callable[[FelicitaScaleData], float | int | None]


SENSOR_DESCRIPTIONS: tuple[FelicitaScaleSensorEntityDescription, ...] = (
    FelicitaScaleSensorEntityDescription(
        key="weight",
        translation_key="weight",
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfMass.GRAMS,
        suggested_display_precision=1,
        value_fn=lambda data: data.weight,
    ),
    FelicitaScaleSensorEntityDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.battery_level,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FelicitaScaleConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Felicita Scale sensors based on a config entry."""
    coordinator = config_entry.runtime_data
    async_add_entities(
        FelicitaScaleSensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    )


class FelicitaScaleSensor(FelicitaScaleEntity, SensorEntity):
    """A sensor for a Felicita Scale reading."""

    entity_description: FelicitaScaleSensorEntityDescription
    _unrecorded_attributes = frozenset(
        {"scale_unit", "raw_weight", "is_stable", "last_measurement"}
    )

    def __init__(
        self,
        coordinator: FelicitaScaleDataUpdateCoordinator,
        description: FelicitaScaleSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, f"{coordinator.address}_{description.key}")
        self.entity_description = description

    @property
    def available(self) -> bool:
        """Return if the scale has sent a reading."""
        return (
            super().available
            and self.coordinator.data is not None
            and self.native_value is not None
        )

    @property
    def native_value(self) -> float | int | None:
        """Return the sensor value."""
        if (data := self.coordinator.data) is None:
            return None
        return self.entity_description.value_fn(data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes of the weight sensor."""
        if (
            self.entity_description.key != "weight"
            or (data := self.coordinator.data) is None
        ):
            return None
        return {
            "scale_unit": data.unit,
            "raw_weight": data.raw_weight,
            "is_stable": data.is_stable,
            "last_measurement": data.last_measurement.isoformat(),
        }
