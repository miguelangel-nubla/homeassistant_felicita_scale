"""Diagnostics support for Chipsea Scale."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .models import ChipseaScaleConfigEntry

TO_REDACTED = {"address"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ChipseaScaleConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    return {
        "entry": {
            "title": entry.title,
            "data": {
                key: ("**REDACTED**" if key in TO_REDACTED else value)
                for key, value in entry.data.items()
            },
            "options": entry.options,
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "last_exception": str(coordinator.last_exception) if coordinator.last_exception else None,
            "update_interval": str(coordinator.update_interval) if coordinator.update_interval else None,
            "address": "**REDACTED**",
            "connected": coordinator.is_connected,
            "notification_enabled": coordinator.notification_enabled,
            "connection_stats": coordinator.connection_stats,
        },
        "data": {
            "weight": coordinator.data.weight if coordinator.data else None,
            "unit": coordinator.data.unit if coordinator.data else None,
            "is_stable": coordinator.data.is_stable if coordinator.data else None,
            "battery_level": coordinator.data.battery_level if coordinator.data else None,
            "last_measurement": (
                coordinator.data.last_measurement.isoformat()
                if coordinator.data and coordinator.data.last_measurement
                else None
            ),
        },
    }


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    return await async_get_config_entry_diagnostics(hass, entry)

