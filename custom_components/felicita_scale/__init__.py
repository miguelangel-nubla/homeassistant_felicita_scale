"""The Felicita Scale integration."""

from __future__ import annotations

from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant

from .coordinator import FelicitaScaleDataUpdateCoordinator
from .models import FelicitaScaleConfigEntry

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(
    hass: HomeAssistant, entry: FelicitaScaleConfigEntry
) -> bool:
    """Set up Felicita Scale from a config entry."""
    coordinator = FelicitaScaleDataUpdateCoordinator(
        hass, entry.data[CONF_ADDRESS], entry
    )
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Watch for advertisements and keep the scale connected while it is awake.
    # Started after the platforms so the first reading has entities to update.
    entry.async_on_unload(coordinator.async_start())
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: FelicitaScaleConfigEntry
) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_shutdown()
    return unload_ok
