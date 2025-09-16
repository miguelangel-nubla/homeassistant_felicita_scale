"""Sensor platform for Chipsea Scale integration."""
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
from .coordinator import ChipseaScaleDataUpdateCoordinator
from .models import ChipseaScaleConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0  # No limit since coordinator manages all updates

SENSOR_DESCRIPTIONS = [
    SensorEntityDescription(
        key="weight",
        translation_key="weight",
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfMass.GRAMS,
        suggested_display_precision=0,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ChipseaScaleConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Chipsea Scale sensor based on a config entry."""
    coordinator = config_entry.runtime_data

    entities = [
        ChipseaScaleSensor(coordinator, config_entry, description)
        for description in SENSOR_DESCRIPTIONS
    ]

    async_add_entities(entities)


class ChipseaScaleSensor(CoordinatorEntity[ChipseaScaleDataUpdateCoordinator], SensorEntity):
    """Representation of a Chipsea Scale sensor."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: ChipseaScaleDataUpdateCoordinator,
        config_entry: ChipseaScaleConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description

        self._address = config_entry.data[CONF_ADDRESS]
        self._attr_unique_id = f"{self._address}_{description.key}"

        # Set up device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._address)},
            name=config_entry.title or "Chipsea Scale",
            manufacturer="Chipsea",
            model="Smart Scale",
            connections={("bluetooth", self._address.lower())},
        )

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor (always in grams)."""
        if not self.coordinator.data:
            return None

        return round(self.coordinator.data.weight) if self.coordinator.data.weight is not None else None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self.coordinator.data is not None
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
            
        if hasattr(self.coordinator.data, 'decimals') and self.coordinator.data.decimals is not None:
            attributes["decimal_places"] = self.coordinator.data.decimals

        if self.coordinator.data.is_stable is not None:
            attributes["is_stable"] = self.coordinator.data.is_stable

        if self.coordinator.data.battery_level is not None:
            attributes["battery_level"] = self.coordinator.data.battery_level

        if self.coordinator.data.last_measurement is not None:
            attributes["last_measurement"] = self.coordinator.data.last_measurement.isoformat()

        return attributes if attributes else None

