"""Config flow for the Felicita Scale integration."""

from __future__ import annotations

import re
from typing import Any

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)
import voluptuous as vol

from .const import DOMAIN, is_supported_device_name

MANUAL_ENTRY = "manual"
MAC_ADDRESS_RE = re.compile(r"^[0-9A-F]{12}$")


def normalize_address(address: str) -> str | None:
    """Return the address as AA:BB:CC:DD:EE:FF, or None if it is not a MAC."""
    cleaned = re.sub(r"[\s:\-.]", "", address).upper()
    if not MAC_ADDRESS_RE.match(cleaned):
        return None
    return ":".join(cleaned[i : i + 2] for i in range(0, 12, 2))


class FelicitaScaleConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Felicita Scale."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        # Discovered address -> device name
        self._discovered_devices: dict[str, str] = {}
        self._discovery_info: bluetooth.BluetoothServiceInfoBleak | None = None

    async def async_step_bluetooth(
        self, discovery_info: bluetooth.BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle the bluetooth discovery step."""
        if not is_supported_device_name(discovery_info.name):
            return self.async_abort(reason="not_supported")

        await self.async_set_unique_id(discovery_info.address.upper())
        self._abort_if_unique_id_configured()

        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {"name": self._discovery_title}
        return await self.async_step_bluetooth_confirm()

    @property
    def _discovery_title(self) -> str:
        assert self._discovery_info is not None
        return self._discovery_info.name or self._discovery_info.address

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        assert self._discovery_info is not None

        if user_input is not None:
            return self.async_create_entry(
                title=self._discovery_title,
                data={CONF_ADDRESS: self._discovery_info.address.upper()},
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": self._discovery_title},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick a discovered scale or choose to enter an address."""
        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            if address == MANUAL_ENTRY:
                return await self.async_step_manual()

            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()

            ble_device = bluetooth.async_ble_device_from_address(
                self.hass, address, connectable=True
            )
            if ble_device:
                return self.async_create_entry(
                    title=self._discovered_devices.get(address, address),
                    data={CONF_ADDRESS: address},
                )
            errors[CONF_ADDRESS] = "cannot_connect"

        current_addresses = self._async_current_ids(include_ignore=False)
        self._discovered_devices = {}
        for service_info in bluetooth.async_discovered_service_info(self.hass):
            address = service_info.address.upper()
            if address in current_addresses or not is_supported_device_name(
                service_info.name
            ):
                continue
            self._discovered_devices[address] = service_info.name

        if not self._discovered_devices:
            # Nothing to pick from; go straight to manual entry
            return await self.async_step_manual()

        # Discovered devices are labelled by name; the manual entry option is
        # translated through the selector's translation key
        options = [
            SelectOptionDict(value=address, label=f"{name} ({address})")
            for address, name in self._discovered_devices.items()
        ]
        options.append(
            SelectOptionDict(value=MANUAL_ENTRY, label="Enter address manually")
        )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): SelectSelector(
                        SelectSelectorConfig(options=options, translation_key="address")
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual address entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            address = normalize_address(user_input[CONF_ADDRESS])
            if address is None:
                errors[CONF_ADDRESS] = "invalid_address"
            else:
                await self.async_set_unique_id(address, raise_on_progress=False)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=address, data={CONF_ADDRESS: address}
                )

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): str}),
            errors=errors,
        )
