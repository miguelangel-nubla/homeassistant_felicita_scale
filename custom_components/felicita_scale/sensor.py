"""Sensor platform for Felicita Scale integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import CONF_ADDRESS, UnitOfMass, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FelicitaScaleDataUpdateCoordinator
from .models import FelicitaScaleConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0  # No limit since coordinator manages all updates

SENSOR_DESCRIPTIONS = [
    SensorEntityDescription(
        key="weight",
        translation_key="weight",
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfMass.GRAMS,
    ),
    SensorEntityDescription(
        key="battery",
        translation_key="battery",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="%",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FelicitaScaleConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Felicita Scale sensor based on a config entry."""
    coordinator = config_entry.runtime_data

    entities = []
    
    # Add weight sensor
    weight_desc = next(desc for desc in SENSOR_DESCRIPTIONS if desc.key == "weight")
    entities.append(FelicitaScaleWeightSensor(coordinator, config_entry, weight_desc))
    
    # Add battery sensor
    battery_desc = next(desc for desc in SENSOR_DESCRIPTIONS if desc.key == "battery")
    entities.append(FelicitaScaleBatterySensor(coordinator, config_entry, battery_desc))

    async_add_entities(entities)


class FelicitaScaleWeightSensor(CoordinatorEntity[FelicitaScaleDataUpdateCoordinator], SensorEntity):
    """Weight sensor for Felicita Scale."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _unrecorded_attributes = frozenset({"scale_unit", "raw_weight", "is_stable", "last_measurement"})

    def __init__(
        self,
        coordinator: FelicitaScaleDataUpdateCoordinator,
        config_entry: FelicitaScaleConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the weight sensor."""
        super().__init__(coordinator)
        self.entity_description = description

        self._address = config_entry.data[CONF_ADDRESS]
        self._attr_unique_id = f"{self._address}_weight"
        self._attr_name = "Weight"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> float | None:
        """Return the weight value in grams."""
        if not self.coordinator.data:
            return None

        return round(self.coordinator.data.weight, 1) if self.coordinator.data.weight is not None else None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self.coordinator.data is not None
            and self.coordinator.is_connected
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        if not self.coordinator.data:
            return None

        attributes = {}

        # Show the scale's native unit and raw value
        if hasattr(self.coordinator.data, 'unit') and self.coordinator.data.unit:
            attributes["scale_unit"] = self.coordinator.data.unit
            
        if hasattr(self.coordinator.data, 'raw_weight') and self.coordinator.data.raw_weight is not None:
            attributes["raw_weight"] = self.coordinator.data.raw_weight

        if self.coordinator.data.is_stable is not None:
            attributes["is_stable"] = self.coordinator.data.is_stable

        if self.coordinator.data.last_measurement is not None:
            attributes["last_measurement"] = self.coordinator.data.last_measurement.isoformat()

        return attributes if attributes else None


class FelicitaScaleBatterySensor(CoordinatorEntity[FelicitaScaleDataUpdateCoordinator], SensorEntity):
    """Battery sensor for Felicita Scale."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: FelicitaScaleDataUpdateCoordinator,
        config_entry: FelicitaScaleConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the battery sensor."""
        super().__init__(coordinator)
        self.entity_description = description

        self._address = config_entry.data[CONF_ADDRESS]
        self._attr_unique_id = f"{self._address}_battery"
        self._attr_name = "Battery"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> int | None:
        """Return the battery level."""
        if not self.coordinator.data:
            return None

        return self.coordinator.data.battery_level

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self.coordinator.data is not None
            and self.coordinator.data.battery_level is not None
            and self.coordinator.is_connected
        )

