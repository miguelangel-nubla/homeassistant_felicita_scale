"""The Felicita Scale integration."""
from __future__ import annotations

import logging

from homeassistant.components import bluetooth
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

    # Register for Bluetooth advertisements to detect when device comes back online
    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            coordinator._async_handle_bluetooth_event,  # noqa: SLF001
            {"address": address.upper()},
            bluetooth.BluetoothScanningMode.ACTIVE,
        )
    )

    # Don't fail setup if initial connection fails - just log and continue
    # The coordinator will handle reconnection when the device becomes available
    try:
        await coordinator.async_config_entry_first_refresh()
        _LOGGER.info("Successfully connected to Felicita Scale during setup")
    except Exception as err:
        _LOGGER.debug("Could not connect to Felicita Scale during setup, will retry when device is available: %s", err)

    entry.runtime_data = coordinator

    # No services needed - all functionality provided by entities

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: FelicitaScaleConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_shutdown()
        
        # No services to remove
        
    return unload_ok

