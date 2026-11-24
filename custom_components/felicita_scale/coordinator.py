"""Coordinator for the Felicita Scale integration."""

from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime
import logging
from typing import TYPE_CHECKING, Any

from bleak import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection
from homeassistant.components import bluetooth
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CHARACTERISTIC_UUID,
    COMMAND_RESET_TIMER,
    COMMAND_START_TIMER,
    COMMAND_STOP_TIMER,
    COMMAND_TARE,
    COMMAND_TOGGLE_PRECISION,
    COMMAND_TOGGLE_UNIT,
    DOMAIN,
    MANUFACTURER,
)
from .models import FelicitaScaleData
from .protocol import StabilityTracker, parse_notification

if TYPE_CHECKING:
    from bleak.backends.characteristic import BleakGATTCharacteristic

    from .models import FelicitaScaleConfigEntry

_LOGGER = logging.getLogger(__name__)

# Reconnection policy
ADVERTISEMENT_FRESH_SECONDS = 30  # Scale counts as awake if it advertised this recently
IDLE_POLL_SECONDS = 5  # How often to check for advertisements while the scale sleeps
RETRY_BACKOFF_SECONDS = (
    2,
    5,
    10,
    20,
    30,
)  # Delay after each consecutive failed connect
CONNECT_MAX_ATTEMPTS = 2  # Attempts per connect; the reconnect loop retries beyond that


class FelicitaConnectionError(HomeAssistantError):
    """Raised when the scale cannot be reached."""


class FelicitaScaleDataUpdateCoordinator(
    DataUpdateCoordinator[FelicitaScaleData | None]
):
    """Keep a Bluetooth connection to the scale and publish its readings.

    The scale pushes notifications, so there is no polling: data is set from
    the notification callback, and is None while the scale is disconnected.
    """

    config_entry: FelicitaScaleConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        address: str,
        config_entry: FelicitaScaleConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=None,
            config_entry=config_entry,
        )
        self.address = address.upper()
        self.data = None
        self._client: BleakClientWithServiceCache | None = None
        self._connect_lock = asyncio.Lock()
        self._notification_enabled = False
        self._unavailable_logged = False
        self._connection_attempts = 0
        self._last_successful_connection: datetime | None = None
        self._total_disconnections = 0
        self._stability = StabilityTracker()
        self._reconnect_task: asyncio.Task[None] | None = None
        self._shutting_down = False

        # The scale does not report these, so they are tracked optimistically
        # from the commands we send and reset whenever the link drops
        self.timer_running = False
        self.precision_enabled = False

        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, self.address)},
            # Lowercase as registered by earlier versions
            connections={(CONNECTION_BLUETOOTH, self.address.lower())},
            name=config_entry.title or "Felicita Scale",
            manufacturer=MANUFACTURER,
        )

    @property
    def is_connected(self) -> bool:
        """Return True if connected to the scale."""
        return self._client is not None and self._client.is_connected

    @property
    def notification_enabled(self) -> bool:
        """Return True if notifications are enabled."""
        return self._notification_enabled

    @property
    def connection_stats(self) -> dict[str, Any]:
        """Return connection statistics for diagnostics."""
        last = self._last_successful_connection
        return {
            "connection_attempts": self._connection_attempts,
            "total_disconnections": self._total_disconnections,
            "last_successful_connection": last.isoformat() if last else None,
            "current_connection_duration": (
                (dt_util.utcnow() - last).total_seconds()
                if last and self.is_connected
                else None
            ),
        }

    @callback
    def async_start(self) -> CALLBACK_TYPE:
        """Start watching for the scale; returns a callback that stops it."""
        # Registering replays the last known advertisement, so this also
        # starts the first connection attempt if the scale is already awake.
        return bluetooth.async_register_callback(
            self.hass,
            self._async_handle_bluetooth_event,
            {"address": self.address},
            bluetooth.BluetoothScanningMode.ACTIVE,
        )

    @callback
    def _async_handle_bluetooth_event(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Handle Bluetooth events."""
        _LOGGER.debug(
            "Bluetooth event received: change=%s, address=%s, rssi=%s",
            change,
            service_info.address,
            service_info.rssi,
        )
        if change == bluetooth.BluetoothChange.ADVERTISEMENT:
            self._async_ensure_reconnect_loop()

    @callback
    def _async_ensure_reconnect_loop(self) -> None:
        """Start the reconnect loop unless connected or it is already running."""
        if self._shutting_down or self.is_connected:
            return
        if self._reconnect_task and not self._reconnect_task.done():
            # Never cancel an attempt in flight; the loop retries on its own
            return
        # Background task so a connection attempt never holds up HA startup
        self._reconnect_task = self.config_entry.async_create_background_task(
            self.hass,
            self._async_reconnect_loop(),
            f"{DOMAIN} reconnect {self.address}",
        )

    async def _async_reconnect_loop(self) -> None:
        """Connect while the scale is advertising, retrying until it succeeds.

        HA only calls back when an advertisement's content changes, and the
        scale always sends the same one. Once HA has seen the scale, nothing
        calls back again until HA forgets it, minutes after it goes quiet.
        So this loop watches the last advertisement's timestamp instead of
        waiting for callbacks.
        """
        failures = 0
        while not self.is_connected and not self._shutting_down:
            service_info = bluetooth.async_last_service_info(
                self.hass, self.address, connectable=True
            )
            if service_info is None:
                # HA forgot the scale; its next advertisement calls back again
                _LOGGER.debug(
                    "Scale no longer known to Bluetooth, stopping reconnect loop"
                )
                return

            if (
                bluetooth.MONOTONIC_TIME() - service_info.time
                > ADVERTISEMENT_FRESH_SECONDS
            ):
                # Asleep, but HA still remembers it, so waking up with the same
                # advertisement will not call back. Keep watching.
                failures = 0
                await asyncio.sleep(IDLE_POLL_SECONDS)
                continue

            try:
                await self._ensure_connected()
            except FelicitaConnectionError:
                pass
            except Exception:  # an escaped error would end the loop for good
                _LOGGER.exception("Unexpected error while connecting to Felicita Scale")
            if self.is_connected:
                return

            delay = RETRY_BACKOFF_SECONDS[min(failures, len(RETRY_BACKOFF_SECONDS) - 1)]
            failures += 1
            _LOGGER.debug("Connection attempt failed, retrying in %ds", delay)
            await asyncio.sleep(delay)

    async def _async_update_data(self) -> FelicitaScaleData | None:
        """Return current data; all updates arrive as Bluetooth notifications."""
        return self.data

    async def _ensure_connected(self) -> None:
        """Connect to the scale unless already connected."""
        async with self._connect_lock:
            if self.is_connected:
                return

            _LOGGER.debug("Connecting to Felicita Scale at %s", self.address)

            # Always look up the current device; a cached one may point at a
            # proxy that no longer hears the scale
            ble_device = bluetooth.async_ble_device_from_address(
                self.hass, self.address, connectable=True
            )
            if not ble_device:
                raise FelicitaConnectionError(
                    f"Could not find device with address {self.address}"
                )

            self._connection_attempts += 1
            try:
                client = await establish_connection(
                    BleakClientWithServiceCache,
                    ble_device,
                    self.address,
                    disconnected_callback=self._on_disconnect,
                    max_attempts=CONNECT_MAX_ATTEMPTS,
                    ble_device_callback=lambda: (
                        bluetooth.async_ble_device_from_address(
                            self.hass, self.address, connectable=True
                        )
                        or ble_device
                    ),
                )
            except (TimeoutError, BleakError) as err:
                self._log_unavailable(err)
                raise FelicitaConnectionError(f"Failed to connect: {err}") from err

            self._client = client
            try:
                await client.start_notify(
                    CHARACTERISTIC_UUID, self._notification_callback
                )
            except BleakError as err:
                # Connected but useless without weight notifications;
                # drop the link so the reconnect loop starts over
                self._client = None
                with contextlib.suppress(BleakError):
                    await client.disconnect()
                self._log_unavailable(err)
                raise FelicitaConnectionError(
                    f"Failed to enable notifications: {err}"
                ) from err

            self._notification_enabled = True
            self._last_successful_connection = dt_util.utcnow()
            # Controls are usable now, before the first reading arrives
            self.async_update_listeners()
            if self._unavailable_logged:
                _LOGGER.info("Felicita Scale is back online")
                self._unavailable_logged = False
            else:
                _LOGGER.debug(
                    "Connected to Felicita Scale (attempt %d)",
                    self._connection_attempts,
                )

    def _log_unavailable(self, err: Exception) -> None:
        """Log a failed connection once until the next success."""
        if not self._unavailable_logged:
            _LOGGER.info("Felicita Scale is unavailable, will keep retrying: %s", err)
            self._unavailable_logged = True
        else:
            _LOGGER.debug("Connection to Felicita Scale failed: %s", err)

    @callback
    def _notification_callback(
        self, _: BleakGATTCharacteristic | int, data: bytearray
    ) -> None:
        """Handle a notification from the scale."""
        _LOGGER.debug("Received notification data: %s", data.hex())
        reading = parse_notification(data)
        if reading is None:
            _LOGGER.debug("Ignoring unrecognized notification: %s", data.hex())
            return

        self.async_set_updated_data(
            FelicitaScaleData(
                weight=reading.weight,
                unit=reading.unit,
                raw_weight=reading.raw_weight,
                is_stable=self._stability.update(reading.weight),
                battery_level=reading.battery_level,
            )
        )

    @callback
    def _on_disconnect(self, client: BleakClientWithServiceCache) -> None:
        """Handle disconnection."""
        if self._client is not None and client is not self._client:
            # Late callback from a client we already replaced
            return

        self._total_disconnections += 1
        _LOGGER.debug(
            "Felicita Scale disconnected (total: %d)", self._total_disconnections
        )

        self._client = None
        self._notification_enabled = False
        self._stability.reset()
        self.timer_running = False
        self.precision_enabled = False
        self.data = None
        self.async_update_listeners()

        # If the scale is still on (link drop) it advertises again right away
        # and the loop reconnects; if it was switched off, the loop waits
        self._async_ensure_reconnect_loop()

    async def async_shutdown(self) -> None:
        """Stop reconnecting and disconnect from the scale."""
        self._shutting_down = True
        await super().async_shutdown()
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reconnect_task

        client, self._client = self._client, None
        if client and client.is_connected:
            with contextlib.suppress(BleakError):
                if self._notification_enabled:
                    await client.stop_notify(CHARACTERISTIC_UUID)
                await client.disconnect()
        self._notification_enabled = False

    async def _send_command(self, command: int) -> None:
        """Send a single-byte command to the scale."""
        client = self._client
        if client is None or not client.is_connected:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="not_connected"
            )
        try:
            await client.write_gatt_char(CHARACTERISTIC_UUID, bytes([command]))
        except BleakError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        _LOGGER.debug("Sent command 0x%02x to Felicita scale", command)

    async def async_tare(self) -> None:
        """Tare the scale (reset to zero)."""
        await self._send_command(COMMAND_TARE)

    async def async_toggle_unit(self) -> None:
        """Toggle between grams and ounces."""
        await self._send_command(COMMAND_TOGGLE_UNIT)

    async def async_start_timer(self) -> None:
        """Start the scale's timer."""
        await self._send_command(COMMAND_START_TIMER)
        self.timer_running = True
        self.async_update_listeners()

    async def async_stop_timer(self) -> None:
        """Stop the scale's timer."""
        await self._send_command(COMMAND_STOP_TIMER)
        self.timer_running = False
        self.async_update_listeners()

    async def async_reset_timer(self) -> None:
        """Reset the scale's timer to zero."""
        await self._send_command(COMMAND_RESET_TIMER)

    async def async_set_precision(self, enabled: bool) -> None:
        """Switch high precision mode on or off."""
        if enabled == self.precision_enabled:
            return
        await self._send_command(COMMAND_TOGGLE_PRECISION)
        self.precision_enabled = enabled
        self.async_update_listeners()
