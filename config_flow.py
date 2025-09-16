"""Config flow for Chipsea Scale integration."""
from __future__ import annotations

import logging
from typing import Any

from bleak import BleakScanner
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import bluetooth
from homeassistant.const import CONF_ADDRESS
from homeassistant.data_entry_flow import FlowResult

from .const import DEVICE_NAME_PREFIXES, DOMAIN

_LOGGER = logging.getLogger(__name__)


class ChipseaScaleConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Chipsea Scale."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_devices: dict[str, str] = {}
        self._discovery_info: bluetooth.BluetoothServiceInfoBleak | None = None

    async def async_step_bluetooth(
        self, discovery_info: bluetooth.BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle the bluetooth discovery step."""
        # Check if this is actually a supported Chipsea scale device
        if not self._is_supported_device(discovery_info.name, discovery_info.address):
            return self.async_abort(reason="not_supported")

        await self.async_set_unique_id(discovery_info.address.upper())
        self._abort_if_unique_id_configured()

        device_name = discovery_info.name or discovery_info.address
        self.context["title_placeholders"] = {"name": device_name}
        self._discovery_info = discovery_info

        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery."""
        assert self._discovery_info is not None

        if user_input is not None:
            return self.async_create_entry(
                title=self._discovery_info.name or self._discovery_info.address,
                data={CONF_ADDRESS: self._discovery_info.address.upper()},
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={
                "name": self._discovery_info.name or self._discovery_info.address
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input[CONF_ADDRESS]

            # Handle manual entry selection
            if address == "manual":
                return await self.async_step_manual()

            address = address.upper()
            await self.async_set_unique_id(address)
            self._abort_if_unique_id_configured()

            # Try to find the device via Bluetooth
            ble_device = bluetooth.async_ble_device_from_address(
                self.hass, address, connectable=True
            )

            if not ble_device:
                errors[CONF_ADDRESS] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=ble_device.name or address,
                    data={CONF_ADDRESS: address},
                )

        # Discover available scales
        await self._async_discover_scales()

        data_schema = vol.Schema({
            vol.Required(CONF_ADDRESS): vol.In(self._discovered_devices)
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def _async_discover_scales(self) -> None:
        """Discover Chipsea scales."""
        self._discovered_devices = {}

        try:
            # First try to get devices from Bluetooth integration
            for service_info in bluetooth.async_discovered_service_info(self.hass):
                if self._is_supported_device(service_info.name, service_info.address):
                    name = service_info.name or service_info.address
                    self._discovered_devices[service_info.address.upper()] = (
                        f"{name} ({service_info.address})"
                    )

            # If no devices found, try active scanning
            if not self._discovered_devices:
                devices = await BleakScanner.discover(timeout=10.0)
                for device in devices:
                    if self._is_supported_device(device.name, device.address):
                        name = device.name or device.address
                        self._discovered_devices[device.address.upper()] = (
                            f"{name} ({device.address})"
                        )

        except Exception:
            _LOGGER.exception("Error discovering scales")

        # Add manual entry option
        self._discovered_devices["manual"] = "Enter address manually"

    def _is_supported_device(self, name: str | None, address: str) -> bool:
        """Check if this is a supported Chipsea scale device."""
        if not name:
            return False

        name_lower = name.lower()
        return any(name_lower.startswith(prefix.lower()) for prefix in DEVICE_NAME_PREFIXES)

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle manual address entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input[CONF_ADDRESS].upper().replace(":", "").replace("-", "")

            # Format as proper MAC address
            if len(address) == 12:
                formatted_address = ":".join([address[i:i+2] for i in range(0, 12, 2)])
            else:
                formatted_address = user_input[CONF_ADDRESS].upper()

            await self.async_set_unique_id(formatted_address)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=formatted_address,
                data={CONF_ADDRESS: formatted_address},
            )

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema({
                vol.Required(CONF_ADDRESS): str,
            }),
            errors=errors,
        )

