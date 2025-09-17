"""Select platform for Felicita Scale integration."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import FelicitaScaleDataUpdateCoordinator
from .models import FelicitaScaleConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FelicitaScaleConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Felicita Scale select based on a config entry."""
    coordinator = config_entry.runtime_data

    async_add_entities([
        FelicitaScaleUnitSelect(coordinator, config_entry),
    ])


class FelicitaScaleUnitSelect(CoordinatorEntity[FelicitaScaleDataUpdateCoordinator], SelectEntity):
    """Select entity for choosing scale units."""

    _attr_has_entity_name = True
    _attr_options = ["grams", "ounces"]

    def __init__(
        self,
        coordinator: FelicitaScaleDataUpdateCoordinator,
        config_entry: FelicitaScaleConfigEntry,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{config_entry.entry_id}_unit_select"
        self._attr_name = "Unit"
        self._attr_icon = "mdi:weight-gram"
        
        self._attr_device_info = coordinator.device_info

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        if self.coordinator.data and self.coordinator.data.unit:
            # Map scale units to select options
            unit_map = {
                "g": "grams",
                "oz": "ounces"
            }
            return unit_map.get(self.coordinator.data.unit, "grams")
        return "grams"

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        current = self.current_option
        
        # Only toggle if selecting a different option
        if current != option:
            await self.coordinator.async_toggle_unit()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.is_connected
        )