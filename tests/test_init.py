"""Tests for setting up the Felicita Scale integration and its entities."""

from __future__ import annotations

from unittest.mock import patch

from bleak import BleakError
from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.felicita_scale.const import (
    CHARACTERISTIC_UUID,
    COMMAND_RESET_TIMER,
    COMMAND_START_TIMER,
    COMMAND_STOP_TIMER,
    COMMAND_TARE,
    COMMAND_TOGGLE_PRECISION,
    COMMAND_TOGGLE_UNIT,
    DOMAIN,
)

from .conftest import ADDRESS, MockScale, make_packet, make_service_info

WEIGHT = "sensor.felicita_weight"
BATTERY = "sensor.felicita_battery"
TARE = "button.felicita_tare"
RESET_TIMER = "button.felicita_reset_timer"
TIMER = "switch.felicita_timer"
PRECISION = "switch.felicita_precision"
UNIT = "select.felicita_unit"
ALL_ENTITIES = (WEIGHT, BATTERY, TARE, RESET_TIMER, TIMER, PRECISION, UNIT)


async def test_setup_and_unload(
    hass: HomeAssistant, config_entry: MockConfigEntry, connected_scale: MockScale
) -> None:
    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED
    connected_scale.client.stop_notify.assert_awaited_once_with(CHARACTERISTIC_UUID)
    connected_scale.client.disconnect.assert_awaited()


async def test_entities_unavailable_before_connecting(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_scale: MockScale
) -> None:
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    for entity_id in ALL_ENTITIES:
        assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_device_and_unique_ids(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    connected_scale: MockScale,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    devices = dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)
    assert len(devices) == 1
    device = devices[0]
    assert (DOMAIN, ADDRESS) in device.identifiers
    assert device.manufacturer == "Felicita"
    assert (dr.CONNECTION_BLUETOOTH, ADDRESS.lower()) in device.connections

    # Unique IDs must not change, or existing installs lose their entities
    entry_id = config_entry.entry_id
    expected = {
        WEIGHT: f"{ADDRESS}_weight",
        BATTERY: f"{ADDRESS}_battery",
        TARE: f"{entry_id}_tare",
        RESET_TIMER: f"{entry_id}_timer_reset",
        TIMER: f"{entry_id}_timer",
        PRECISION: f"{entry_id}_precision",
        UNIT: f"{entry_id}_unit_select",
    }
    for entity_id, unique_id in expected.items():
        entry = entity_registry.async_get(entity_id)
        assert entry is not None, entity_id
        assert entry.unique_id == unique_id
        assert entry.device_id == device.id


async def test_weight_notifications(
    hass: HomeAssistant, connected_scale: MockScale
) -> None:
    # Connected but no reading yet: controls work, sensors wait for data
    assert hass.states.get(TARE).state != STATE_UNAVAILABLE
    assert hass.states.get(WEIGHT).state == STATE_UNAVAILABLE

    connected_scale.notify(None, make_packet("012345"))
    await hass.async_block_till_done()

    state = hass.states.get(WEIGHT)
    assert float(state.state) == pytest.approx(123.45)
    assert state.attributes["unit_of_measurement"] == "g"
    assert state.attributes["scale_unit"] == "g"
    assert state.attributes["raw_weight"] == pytest.approx(123.45)
    assert state.attributes["is_stable"] is False
    assert hass.states.get(BATTERY).state == "55"
    assert hass.states.get(UNIT).state == "grams"

    for _ in range(3):
        connected_scale.notify(None, make_packet("012345"))
    await hass.async_block_till_done()
    assert hass.states.get(WEIGHT).attributes["is_stable"] is True

    connected_scale.notify(None, make_packet("000850", sign="-", unit=b"oz"))
    await hass.async_block_till_done()
    state = hass.states.get(WEIGHT)
    assert float(state.state) == pytest.approx(-0.085 * 28.349523125)
    assert state.attributes["scale_unit"] == "oz"
    assert hass.states.get(UNIT).state == "ounces"


async def test_garbage_notification_ignored(
    hass: HomeAssistant, connected_scale: MockScale
) -> None:
    connected_scale.notify(None, make_packet("000100"))
    connected_scale.notify(None, bytearray(b"\x01\x02\x03"))
    await hass.async_block_till_done()
    assert float(hass.states.get(WEIGHT).state) == pytest.approx(1.0)


async def test_disconnect_and_reconnect(
    hass: HomeAssistant, connected_scale: MockScale
) -> None:
    connected_scale.notify(None, make_packet())
    await hass.async_block_till_done()

    # Scale goes to sleep: no fresh advertisement, so no reconnect attempt
    connected_scale.last_service_info.return_value.time -= 60
    connected_scale.disconnect()
    await hass.async_block_till_done()
    for entity_id in ALL_ENTITIES:
        assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
    assert connected_scale.establish_connection.call_count == 1

    # Scale wakes up with the same advertisement; the loop notices the new time
    connected_scale.last_service_info.return_value.time = bluetooth.MONOTONIC_TIME()
    with patch("custom_components.felicita_scale.coordinator.asyncio.sleep"):
        await hass.async_block_till_done(wait_background_tasks=True)
    assert connected_scale.establish_connection.call_count == 2
    assert hass.states.get(TARE).state != STATE_UNAVAILABLE

    connected_scale.notify(None, make_packet("000200"))
    await hass.async_block_till_done()
    assert float(hass.states.get(WEIGHT).state) == pytest.approx(2.0)


async def test_reconnect_retries_failures(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_scale: MockScale
) -> None:
    connect = mock_scale.establish_connection.side_effect
    calls = 0

    async def _flaky(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls < 3:
            raise BleakError("out of connection slots")
        return await connect(*args, **kwargs)

    mock_scale.establish_connection.side_effect = _flaky
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    with patch("custom_components.felicita_scale.coordinator.asyncio.sleep") as sleep:
        mock_scale.advertise()
        await hass.async_block_till_done(wait_background_tasks=True)

    assert calls == 3
    assert [c.args[0] for c in sleep.call_args_list if c.args[0]] == [2, 5]
    assert hass.states.get(TARE).state != STATE_UNAVAILABLE


async def test_notification_setup_failure_drops_link(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_scale: MockScale
) -> None:
    mock_scale.client.start_notify.side_effect = [BleakError("boom"), None]
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    with patch("custom_components.felicita_scale.coordinator.asyncio.sleep"):
        mock_scale.advertise()
        await hass.async_block_till_done(wait_background_tasks=True)

    mock_scale.client.disconnect.assert_awaited_once()
    assert mock_scale.establish_connection.call_count == 2
    assert hass.states.get(TARE).state != STATE_UNAVAILABLE


async def test_loop_stops_when_scale_forgotten(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_scale: MockScale
) -> None:
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    callback = mock_scale.register_callback.call_args.args[1]
    callback(make_service_info(), bluetooth.BluetoothChange.ADVERTISEMENT)
    await hass.async_block_till_done(wait_background_tasks=True)
    mock_scale.establish_connection.assert_not_called()


@pytest.mark.parametrize(
    ("domain", "service", "entity_id", "data", "command"),
    [
        ("button", "press", TARE, {}, COMMAND_TARE),
        ("button", "press", RESET_TIMER, {}, COMMAND_RESET_TIMER),
        ("switch", "turn_on", TIMER, {}, COMMAND_START_TIMER),
        ("switch", "turn_on", PRECISION, {}, COMMAND_TOGGLE_PRECISION),
        ("select", "select_option", UNIT, {"option": "ounces"}, COMMAND_TOGGLE_UNIT),
    ],
)
async def test_commands(
    hass: HomeAssistant,
    connected_scale: MockScale,
    domain: str,
    service: str,
    entity_id: str,
    data: dict,
    command: int,
) -> None:
    connected_scale.notify(None, make_packet())
    await hass.async_block_till_done()

    await hass.services.async_call(
        domain, service, {ATTR_ENTITY_ID: entity_id, **data}, blocking=True
    )
    connected_scale.client.write_gatt_char.assert_awaited_once_with(
        CHARACTERISTIC_UUID, bytes([command])
    )


async def test_select_same_unit_is_noop(
    hass: HomeAssistant, connected_scale: MockScale
) -> None:
    connected_scale.notify(None, make_packet())
    await hass.async_block_till_done()
    await hass.services.async_call(
        "select",
        "select_option",
        {ATTR_ENTITY_ID: UNIT, "option": "grams"},
        blocking=True,
    )
    connected_scale.client.write_gatt_char.assert_not_awaited()


async def test_switch_assumed_state(
    hass: HomeAssistant, connected_scale: MockScale
) -> None:
    write = connected_scale.client.write_gatt_char
    assert hass.states.get(TIMER).state == STATE_OFF
    assert hass.states.get(TIMER).attributes["assumed_state"] is True

    await hass.services.async_call(
        "switch", "turn_on", {ATTR_ENTITY_ID: TIMER}, blocking=True
    )
    assert hass.states.get(TIMER).state == STATE_ON
    await hass.services.async_call(
        "switch", "turn_off", {ATTR_ENTITY_ID: TIMER}, blocking=True
    )
    assert hass.states.get(TIMER).state == STATE_OFF
    assert write.await_args.args[1] == bytes([COMMAND_STOP_TIMER])

    # Precision is a toggle on the scale, so repeating a state sends nothing
    await hass.services.async_call(
        "switch", "turn_off", {ATTR_ENTITY_ID: PRECISION}, blocking=True
    )
    assert write.await_count == 2
    await hass.services.async_call(
        "switch", "turn_on", {ATTR_ENTITY_ID: PRECISION}, blocking=True
    )
    await hass.services.async_call(
        "switch", "turn_on", {ATTR_ENTITY_ID: PRECISION}, blocking=True
    )
    assert write.await_count == 3
    assert hass.states.get(PRECISION).state == STATE_ON

    # Power-cycling the scale resets both features
    connected_scale.last_service_info.return_value.time -= 60
    connected_scale.disconnect()
    connected_scale.last_service_info.return_value.time = bluetooth.MONOTONIC_TIME()
    with patch("custom_components.felicita_scale.coordinator.asyncio.sleep"):
        await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(PRECISION).state == STATE_OFF
    assert hass.states.get(TIMER).state == STATE_OFF


async def test_command_failure_raises(
    hass: HomeAssistant, connected_scale: MockScale
) -> None:
    connected_scale.client.write_gatt_char.side_effect = BleakError("gone")
    with pytest.raises(HomeAssistantError, match="gone"):
        await hass.services.async_call(
            "button", "press", {ATTR_ENTITY_ID: TARE}, blocking=True
        )

    # A failed command must not flip the assumed state
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "switch", "turn_on", {ATTR_ENTITY_ID: TIMER}, blocking=True
        )
    assert hass.states.get(TIMER).state == STATE_OFF


async def test_command_when_disconnected_raises(
    hass: HomeAssistant, config_entry: MockConfigEntry, connected_scale: MockScale
) -> None:
    coordinator = config_entry.runtime_data
    connected_scale.client.is_connected = False
    with pytest.raises(HomeAssistantError, match="not connected"):
        await coordinator.async_tare()


async def test_shutdown_cancels_reconnect_loop(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_scale: MockScale
) -> None:
    mock_scale.establish_connection.side_effect = BleakError("nope")
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    mock_scale.advertise()
    await hass.async_block_till_done()  # Loop is now sleeping between retries

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert config_entry.state is ConfigEntryState.NOT_LOADED
    attempts = mock_scale.establish_connection.call_count

    hass.loop.call_later(0, lambda: None)
    await hass.async_block_till_done()
    assert mock_scale.establish_connection.call_count == attempts
