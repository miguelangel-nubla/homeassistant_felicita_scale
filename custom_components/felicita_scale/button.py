"""Button platform for Felicita Scale integration."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
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
    """Set up Felicita Scale button based on a config entry."""
    coordinator = config_entry.runtime_data

    async_add_entities([
        FelicitaScaleTareButton(coordinator, config_entry),
        FelicitaScaleTimerResetButton(coordinator, config_entry),
    ])


class FelicitaScaleTareButton(CoordinatorEntity[FelicitaScaleDataUpdateCoordinator], ButtonEntity):
    """Representation of a Felicita Scale tare button."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FelicitaScaleDataUpdateCoordinator,
        config_entry: FelicitaScaleConfigEntry,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{config_entry.entry_id}_tare"
        self._attr_name = "Tare"
        self._attr_icon = "mdi:scale-balance"
        
        self._attr_device_info = coordinator.device_info

    async def async_press(self) -> None:
        """Press the button."""
        await self.coordinator.async_tare()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.is_connected
        )


class FelicitaScaleTimerResetButton(CoordinatorEntity[FelicitaScaleDataUpdateCoordinator], ButtonEntity):
    """Representation of a Felicita Scale timer reset button."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FelicitaScaleDataUpdateCoordinator,
        config_entry: FelicitaScaleConfigEntry,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{config_entry.entry_id}_timer_reset"
        self._attr_name = "Reset Timer"
        self._attr_icon = "mdi:timer-off"
        
        self._attr_device_info = coordinator.device_info

    async def async_press(self) -> None:
        """Press the button."""
        await self.coordinator.async_reset_timer()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.is_connected
        )