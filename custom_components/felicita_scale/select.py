"""Select platform for the Felicita Scale integration."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FelicitaScaleDataUpdateCoordinator
from .entity import FelicitaScaleEntity
from .models import FelicitaScaleConfigEntry
from .protocol import UNIT_GRAMS, UNIT_OUNCES

PARALLEL_UPDATES = 0

UNIT_TO_OPTION = {UNIT_GRAMS: "grams", UNIT_OUNCES: "ounces"}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FelicitaScaleConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Felicita Scale unit select based on a config entry."""
    async_add_entities(
        [FelicitaScaleUnitSelect(config_entry.runtime_data, config_entry)]
    )


class FelicitaScaleUnitSelect(FelicitaScaleEntity, SelectEntity):
    """Select the unit shown on the scale."""

    _attr_translation_key = "unit"
    _attr_options = list(UNIT_TO_OPTION.values())

    def __init__(
        self,
        coordinator: FelicitaScaleDataUpdateCoordinator,
        config_entry: FelicitaScaleConfigEntry,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator, f"{config_entry.entry_id}_unit_select")

    @property
    def available(self) -> bool:
        """Return if the scale has reported its unit."""
        return super().available and self.coordinator.data is not None

    @property
    def current_option(self) -> str | None:
        """Return the unit the scale currently shows."""
        if (data := self.coordinator.data) is None:
            return None
        return UNIT_TO_OPTION.get(data.unit)

    async def async_select_option(self, option: str) -> None:
        """Change the unit; the scale only supports toggling it."""
        if option != self.current_option:
            await self.coordinator.async_toggle_unit()
