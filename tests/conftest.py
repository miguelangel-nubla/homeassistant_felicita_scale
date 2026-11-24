"""Fixtures for the Felicita Scale tests."""

from __future__ import annotations

from collections.abc import Callable, Generator
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from bleak.backends.device import BLEDevice
from homeassistant.components import bluetooth
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.felicita_scale.const import DOMAIN

ADDRESS = "AA:BB:CC:DD:EE:FF"
NAME = "FELICITA"


def make_packet(
    digits: str = "000540",
    sign: str = "+",
    unit: bytes = b"g ",
    battery: int = 145,
) -> bytearray:
    """Build an 18-byte Felicita notification."""
    packet = bytearray(
        [1, 2, ord(sign), *digits.encode(), *unit, 83, 79, 48, 34, battery, 13, 10]
    )
    assert len(packet) == 18
    return packet


def make_service_info(
    name: str | None = NAME, address: str = ADDRESS
) -> bluetooth.BluetoothServiceInfoBleak:
    """Build a Bluetooth service info for the scale."""
    service_info = MagicMock(spec=bluetooth.BluetoothServiceInfoBleak)
    service_info.name = name
    service_info.address = address
    service_info.rssi = -60
    service_info.time = bluetooth.MONOTONIC_TIME()
    service_info.device = BLEDevice(address, name, None)
    return service_info


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None, mock_bluetooth: None
) -> None:
    """Enable custom integrations and mock out the Bluetooth stack."""


@dataclass
class MockScale:
    """Controls for a simulated scale."""

    client: MagicMock
    register_callback: MagicMock
    establish_connection: AsyncMock
    last_service_info: MagicMock
    ble_device_from_address: MagicMock
    disconnected_callbacks: list[Callable[[Any], None]] = field(default_factory=list)

    @property
    def notify(self) -> Callable[[Any, bytearray], None]:
        """Return the notification callback the integration subscribed with."""
        return self.client.start_notify.call_args.args[1]

    def advertise(self) -> None:
        """Deliver an advertisement to the integration."""
        callback = self.register_callback.call_args.args[1]
        self.last_service_info.return_value = make_service_info()
        callback(make_service_info(), bluetooth.BluetoothChange.ADVERTISEMENT)

    def disconnect(self) -> None:
        """Simulate the scale dropping the link."""
        self.client.is_connected = False
        self.disconnected_callbacks[-1](self.client)


@pytest.fixture
def mock_scale() -> Generator[MockScale]:
    """Patch Bluetooth so the integration talks to a simulated scale."""
    client = MagicMock()
    client.is_connected = True
    client.start_notify = AsyncMock()
    client.stop_notify = AsyncMock()
    client.write_gatt_char = AsyncMock()
    client.disconnect = AsyncMock()

    with (
        patch.object(bluetooth, "async_register_callback") as register_callback,
        patch.object(
            bluetooth, "async_last_service_info", return_value=None
        ) as last_service_info,
        patch.object(
            bluetooth,
            "async_ble_device_from_address",
            return_value=BLEDevice(ADDRESS, NAME, None),
        ) as ble_device_from_address,
        patch(
            "custom_components.felicita_scale.coordinator.establish_connection"
        ) as establish_connection,
    ):
        scale = MockScale(
            client=client,
            register_callback=register_callback,
            establish_connection=establish_connection,
            last_service_info=last_service_info,
            ble_device_from_address=ble_device_from_address,
        )

        async def _connect(*args: Any, **kwargs: Any) -> MagicMock:
            client.is_connected = True
            scale.disconnected_callbacks.append(kwargs["disconnected_callback"])
            return client

        establish_connection.side_effect = _connect
        yield scale


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Add a config entry for the scale."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=NAME,
        unique_id=ADDRESS,
        data={CONF_ADDRESS: ADDRESS},
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def connected_scale(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_scale: MockScale
) -> MockScale:
    """Set up the integration and connect it to the simulated scale."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    mock_scale.advertise()
    await hass.async_block_till_done(wait_background_tasks=True)
    assert mock_scale.establish_connection.call_count == 1
    return mock_scale
