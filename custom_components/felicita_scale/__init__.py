"""The Felicita Scale integration."""
from __future__ import annotations

import logging

from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .coordinator import FelicitaScaleDataUpdateCoordinator
from .models import FelicitaScaleConfigEntry

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON, Platform.SWITCH, Platform.SELECT]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: FelicitaScaleConfigEntry) -> bool:
    """Set up Felicita Scale from a config entry."""
    address = entry.data[CONF_ADDRESS]

    coordinator = FelicitaScaleDataUpdateCoordinator(hass, address, entry)
    entry.runtime_data = coordinator

    # Watch for advertisements and keep the scale connected while it is awake
    entry.async_on_unload(coordinator.async_start())

    # No services needed - all functionality provided by entities

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: FelicitaScaleConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_shutdown()
        
        # No services to remove
        
    return unload_ok

