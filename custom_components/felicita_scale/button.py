"""Button platform for the Felicita Scale integration."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FelicitaScaleDataUpdateCoordinator
from .entity import FelicitaScaleEntity
from .models import FelicitaScaleConfigEntry

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class FelicitaScaleButtonEntityDescription(ButtonEntityDescription):
    """Describes a Felicita Scale button."""

    press_fn: Callable[[FelicitaScaleDataUpdateCoordinator], Coroutine[Any, Any, None]]


BUTTON_DESCRIPTIONS: tuple[FelicitaScaleButtonEntityDescription, ...] = (
    FelicitaScaleButtonEntityDescription(
        # Unique ID suffixes predate the descriptions and must stay stable
        key="tare",
        translation_key="tare",
        press_fn=lambda coordinator: coordinator.async_tare(),
    ),
    FelicitaScaleButtonEntityDescription(
        key="timer_reset",
        translation_key="reset_timer",
        press_fn=lambda coordinator: coordinator.async_reset_timer(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FelicitaScaleConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Felicita Scale buttons based on a config entry."""
    coordinator = config_entry.runtime_data
    async_add_entities(
        FelicitaScaleButton(coordinator, config_entry, description)
        for description in BUTTON_DESCRIPTIONS
    )


class FelicitaScaleButton(FelicitaScaleEntity, ButtonEntity):
    """A button that sends a command to the scale."""

    entity_description: FelicitaScaleButtonEntityDescription

    def __init__(
        self,
        coordinator: FelicitaScaleDataUpdateCoordinator,
        config_entry: FelicitaScaleConfigEntry,
        description: FelicitaScaleButtonEntityDescription,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator, f"{config_entry.entry_id}_{description.key}")
        self.entity_description = description

    async def async_press(self) -> None:
        """Press the button."""
        await self.entity_description.press_fn(self.coordinator)
