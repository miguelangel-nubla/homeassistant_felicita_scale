"""Base entity for the Felicita Scale integration."""

from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import FelicitaScaleDataUpdateCoordinator


class FelicitaScaleEntity(CoordinatorEntity[FelicitaScaleDataUpdateCoordinator]):
    """An entity that is available while the scale is connected."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: FelicitaScaleDataUpdateCoordinator, unique_id: str
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_unique_id = unique_id
        self._attr_device_info = coordinator.device_info

    @property
    def available(self) -> bool:
        """Return if the scale is connected."""
        return super().available and self.coordinator.is_connected
