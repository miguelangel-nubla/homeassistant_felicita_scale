"""Switch platform for the Felicita Scale integration."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FelicitaScaleDataUpdateCoordinator
from .entity import FelicitaScaleEntity
from .models import FelicitaScaleConfigEntry

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class FelicitaScaleSwitchEntityDescription(SwitchEntityDescription):
    """Describes a Felicita Scale switch."""

    is_on_fn: Callable[[FelicitaScaleDataUpdateCoordinator], bool]
    set_fn: Callable[
        [FelicitaScaleDataUpdateCoordinator, bool], Coroutine[Any, Any, None]
    ]


async def _set_timer(coordinator: FelicitaScaleDataUpdateCoordinator, on: bool) -> None:
    if on:
        await coordinator.async_start_timer()
    else:
        await coordinator.async_stop_timer()


SWITCH_DESCRIPTIONS: tuple[FelicitaScaleSwitchEntityDescription, ...] = (
    FelicitaScaleSwitchEntityDescription(
        key="timer",
        translation_key="timer",
        is_on_fn=lambda coordinator: coordinator.timer_running,
        set_fn=_set_timer,
    ),
    FelicitaScaleSwitchEntityDescription(
        key="precision",
        translation_key="precision",
        is_on_fn=lambda coordinator: coordinator.precision_enabled,
        set_fn=lambda coordinator, on: coordinator.async_set_precision(on),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FelicitaScaleConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Felicita Scale switches based on a config entry."""
    coordinator = config_entry.runtime_data
    async_add_entities(
        FelicitaScaleSwitch(coordinator, config_entry, description)
        for description in SWITCH_DESCRIPTIONS
    )


class FelicitaScaleSwitch(FelicitaScaleEntity, SwitchEntity):
    """A switch for a scale feature.

    The scale does not report the state of these features, so the state is
    assumed from the commands sent and resets when the scale disconnects.
    """

    entity_description: FelicitaScaleSwitchEntityDescription
    _attr_assumed_state = True

    def __init__(
        self,
        coordinator: FelicitaScaleDataUpdateCoordinator,
        config_entry: FelicitaScaleConfigEntry,
        description: FelicitaScaleSwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, f"{config_entry.entry_id}_{description.key}")
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Return the assumed state."""
        return self.entity_description.is_on_fn(self.coordinator)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the feature on."""
        await self.entity_description.set_fn(self.coordinator, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the feature off."""
        await self.entity_description.set_fn(self.coordinator, False)
