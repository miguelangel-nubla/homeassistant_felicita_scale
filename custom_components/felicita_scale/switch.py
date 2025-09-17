"""Switch platform for Felicita Scale integration."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
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
    """Set up Felicita Scale switches based on a config entry."""
    coordinator = config_entry.runtime_data

    async_add_entities([
        FelicitaScaleTimerSwitch(coordinator, config_entry),
        FelicitaScalePrecisionSwitch(coordinator, config_entry),
    ])


class FelicitaScaleBaseSwitch(CoordinatorEntity[FelicitaScaleDataUpdateCoordinator], SwitchEntity):
    """Base class for Felicita Scale switches."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FelicitaScaleDataUpdateCoordinator,
        config_entry: FelicitaScaleConfigEntry,
        switch_type: str,
        name: str,
        icon: str,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{config_entry.entry_id}_{switch_type}"
        self._attr_name = name
        self._attr_icon = icon
        
        self._attr_device_info = coordinator.device_info

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.is_connected
        )



class FelicitaScaleTimerSwitch(FelicitaScaleBaseSwitch):
    """Switch to control the scale timer."""

    def __init__(
        self,
        coordinator: FelicitaScaleDataUpdateCoordinator,
        config_entry: FelicitaScaleConfigEntry,
    ) -> None:
        """Initialize the timer switch."""
        super().__init__(coordinator, config_entry, "timer", "Timer", "mdi:timer")
        self._timer_running = False

    @property
    def is_on(self) -> bool:
        """Return true if timer is running."""
        return self._timer_running

    async def async_turn_on(self) -> None:
        """Start the timer."""
        await self.coordinator.async_start_timer()
        self._timer_running = True
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Stop the timer."""
        await self.coordinator.async_stop_timer()
        self._timer_running = False
        self.async_write_ha_state()


class FelicitaScalePrecisionSwitch(FelicitaScaleBaseSwitch):
    """Switch to toggle precision mode."""

    def __init__(
        self,
        coordinator: FelicitaScaleDataUpdateCoordinator,
        config_entry: FelicitaScaleConfigEntry,
    ) -> None:
        """Initialize the precision switch."""
        super().__init__(coordinator, config_entry, "precision", "Precision", "mdi:target")
        self._precision_mode = False

    @property
    def is_on(self) -> bool:
        """Return true if in high precision mode."""
        return self._precision_mode

    async def async_turn_on(self) -> None:
        """Enable high precision mode."""
        if self.is_on:
            return  # Already in high precision
        await self.coordinator.async_toggle_precision()
        self._precision_mode = True
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Disable high precision mode."""
        if not self.is_on:
            return  # Already in normal precision
        await self.coordinator.async_toggle_precision()
        self._precision_mode = False
        self.async_write_ha_state()