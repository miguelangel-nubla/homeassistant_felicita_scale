"""Tests for Felicita Scale diagnostics."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from .conftest import ADDRESS, MockScale, make_packet


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    connected_scale: MockScale,
) -> None:
    connected_scale.notify(None, make_packet("001000"))
    await hass.async_block_till_done()

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    )
    assert ADDRESS not in str(diagnostics)
    assert diagnostics["entry"]["data"] == {"address": "**REDACTED**"}
    assert diagnostics["coordinator"]["connected"] is True
    assert diagnostics["coordinator"]["connection_stats"]["connection_attempts"] == 1
    assert diagnostics["data"]["weight"] == 10.0
    assert diagnostics["data"]["battery_level"] == 55
