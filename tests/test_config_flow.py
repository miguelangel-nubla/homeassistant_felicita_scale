"""Tests for the Felicita Scale config flow."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.components import bluetooth
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.felicita_scale.config_flow import normalize_address
from custom_components.felicita_scale.const import DOMAIN

from .conftest import ADDRESS, NAME, make_service_info


@pytest.fixture(autouse=True)
def mock_setup_entry():
    with patch(
        "custom_components.felicita_scale.async_setup_entry", return_value=True
    ) as mock:
        yield mock


async def test_bluetooth_discovery(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=make_service_info()
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"] == {CONF_ADDRESS: ADDRESS}
    assert result["result"].unique_id == ADDRESS


async def test_bluetooth_discovery_lowercase_address(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=make_service_info(address=ADDRESS.lower()),
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["data"] == {CONF_ADDRESS: ADDRESS}


@pytest.mark.parametrize("name", [None, "HMSoft", "Some speaker"])
async def test_bluetooth_discovery_not_supported(
    hass: HomeAssistant, name: str | None
) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=make_service_info(name=name)
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_supported"


async def test_bluetooth_discovery_already_configured(hass: HomeAssistant) -> None:
    MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=make_service_info()
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_pick_discovered(hass: HomeAssistant) -> None:
    other = make_service_info(name="HMSoft", address="11:22:33:44:55:66")
    with (
        patch.object(
            bluetooth,
            "async_discovered_service_info",
            return_value=[make_service_info(), other],
        ),
        patch.object(bluetooth, "async_ble_device_from_address", return_value=object()),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        selector = result["data_schema"].schema[CONF_ADDRESS]
        assert [o["value"] for o in selector.config["options"]] == [ADDRESS, "manual"]

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ADDRESS: ADDRESS}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"] == {CONF_ADDRESS: ADDRESS}


async def test_user_pick_out_of_range(hass: HomeAssistant) -> None:
    with (
        patch.object(
            bluetooth,
            "async_discovered_service_info",
            return_value=[make_service_info()],
        ),
        patch.object(bluetooth, "async_ble_device_from_address", return_value=None),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ADDRESS: ADDRESS}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_ADDRESS: "cannot_connect"}


async def test_user_hides_configured(hass: HomeAssistant) -> None:
    MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS).add_to_hass(hass)
    with patch.object(
        bluetooth, "async_discovered_service_info", return_value=[make_service_info()]
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    # Nothing left to pick, so the flow goes straight to manual entry
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"


async def test_user_manual_entry(hass: HomeAssistant) -> None:
    with patch.object(
        bluetooth, "async_discovered_service_info", return_value=[make_service_info()]
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: "manual"}
    )
    assert result["step_id"] == "manual"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: "not a mac"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_ADDRESS: "invalid_address"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: " aa-bb-cc-dd-ee-ff "}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_ADDRESS: ADDRESS}
    assert result["result"].unique_id == ADDRESS


async def test_manual_entry_already_configured(hass: HomeAssistant) -> None:
    MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS).add_to_hass(hass)
    with patch.object(bluetooth, "async_discovered_service_info", return_value=[]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: ADDRESS.lower()}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("AA:BB:CC:DD:EE:FF", ADDRESS),
        ("aabbccddeeff", ADDRESS),
        ("aa-bb-cc-dd-ee-ff", ADDRESS),
        ("AA BB CC DD EE FF", ADDRESS),
        ("AA:BB:CC:DD:EE", None),
        ("GG:BB:CC:DD:EE:FF", None),
        ("", None),
    ],
)
def test_normalize_address(value: str, expected: str | None) -> None:
    assert normalize_address(value) == expected
