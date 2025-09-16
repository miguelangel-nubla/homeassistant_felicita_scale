"""DataUpdateCoordinator for Chipsea Scale."""
from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime, timedelta
import logging
import struct
from typing import TYPE_CHECKING, Any

from bleak import BleakError
from bleak.backends.device import BLEDevice
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CHARACTERISTIC_UUID, DOMAIN
from .models import ChipseaScaleData

if TYPE_CHECKING:
    from homeassistant.components.bluetooth import BluetoothServiceInfoBleak

_LOGGER = logging.getLogger(__name__)


class ChipseaScaleDataUpdateCoordinator(DataUpdateCoordinator[ChipseaScaleData]):
    """Class to manage fetching data from the Chipsea Scale."""

    def __init__(
        self,
        hass: HomeAssistant,
        address: str,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        self.address = address.upper()
        self._client: BleakClientWithServiceCache | None = None
        self._ble_device: BLEDevice | None = None
        self._connect_lock = asyncio.Lock()
        self._notification_enabled = False
        self._unavailable_logged = False
        self._connection_attempts = 0
        self._last_successful_connection = None
        self._total_disconnections = 0

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=1),  # Fallback interval
            config_entry=config_entry,
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
        return {
            "connection_attempts": self._connection_attempts,
            "total_disconnections": self._total_disconnections,
            "last_successful_connection": (
                self._last_successful_connection.isoformat()
                if self._last_successful_connection
                else None
            ),
            "current_connection_duration": (
                (datetime.now() - self._last_successful_connection).total_seconds()
                if self._last_successful_connection and self.is_connected
                else None
            ),
        }

    @callback
    def _async_handle_bluetooth_event(
        self,
        service_info: BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Handle Bluetooth events."""
        if change == bluetooth.BluetoothChange.ADVERTISEMENT:
            self._ble_device = service_info.device

            # If we're not connected and we see an advertisement, try to reconnect
            if not self._client or not self._client.is_connected:
                _LOGGER.debug(
                    "Device advertisement detected for %s, attempting reconnection",
                    self.address,
                )
                self.hass.create_task(self._async_reconnect())

    async def _async_update_data(self) -> ChipseaScaleData:
        """Update data via Bluetooth."""
        if not self._client or not self._client.is_connected:
            await self._ensure_connected()

        # Return current data - updates come via notifications
        return self.data or ChipseaScaleData()

    async def _ensure_connected(self) -> None:
        """Ensure we have a connection to the scale."""
        async with self._connect_lock:
            if self._client and self._client.is_connected:
                return

            _LOGGER.debug("Connecting to Chipsea Scale at %s", self.address)

            # Get BLE device
            if not self._ble_device:
                self._ble_device = bluetooth.async_ble_device_from_address(
                    self.hass, self.address, connectable=True
                )

            if not self._ble_device:
                raise UpdateFailed(f"Could not find device with address {self.address}")

            # Connect to device using bleak-retry-connector
            try:
                self._connection_attempts += 1
                self._client = await establish_connection(
                    BleakClientWithServiceCache,
                    self._ble_device,
                    self.address,
                    disconnected_callback=self._on_disconnect,
                    timeout=10.0,
                    max_attempts=3,
                )

                # Enable notifications
                await self._setup_notifications()

                # Track successful connection
                self._last_successful_connection = datetime.now()

                if not self._unavailable_logged:
                    _LOGGER.info("Successfully connected to Chipsea Scale (attempt %d)",
                                self._connection_attempts)

                # Clear unavailable flag on successful connection
                if self._unavailable_logged:
                    _LOGGER.info("Chipsea Scale is back online")
                    self._unavailable_logged = False

            except (TimeoutError, BleakError) as err:
                # Check if this is a "no connection slots" or "device no longer reachable" error
                # These are expected for battery-powered devices that disconnect automatically
                error_msg = str(err).lower()
                if any(phrase in error_msg for phrase in [
                    "no backend with an available connection slot",
                    "device is no longer reachable",
                    "out of connection slots"
                ]):
                    if not self._unavailable_logged:
                        _LOGGER.info(
                            "Device not reachable (expected for battery-powered scales): %s",
                            err,
                        )
                        self._unavailable_logged = True
                elif not self._unavailable_logged:
                    _LOGGER.error("Failed to connect to Chipsea Scale: %s", err)
                    self._unavailable_logged = True
                raise UpdateFailed(f"Failed to connect: {err}") from err

    async def _setup_notifications(self) -> None:
        """Set up notifications for weight updates."""
        if not self._client or not self._client.is_connected:
            return

        try:
            await self._client.start_notify(CHARACTERISTIC_UUID, self._notification_callback)
            self._notification_enabled = True
            _LOGGER.debug("Notifications enabled for characteristic %s", CHARACTERISTIC_UUID)

        except BleakError as err:
            _LOGGER.error("Failed to enable notifications: %s", err)
            raise UpdateFailed(f"Failed to enable notifications: {err}") from err

    def _notification_callback(self, _: Any, data: bytearray) -> None:
        """Handle notification from the scale."""
        if not data:
            return

        _LOGGER.debug("Received notification data: %s", data.hex())

        try:
            weight_data = self._decode_weight_bytes(data)
            if weight_data:
                if not self.data:
                    self.data = ChipseaScaleData()

                self.data.update_weight(
                    weight_data["weight"],
                    weight_data.get("stable", False),
                )
                
                # Update unit if detected
                if "unit" in weight_data:
                    self.data.unit = weight_data["unit"]

                # Update battery level if available
                if "battery_level" in weight_data:
                    self.data.battery_level = weight_data["battery_level"]

                # Notify Home Assistant of the update
                self.async_set_updated_data(self.data)

        except (KeyError, TypeError, ValueError) as err:
            _LOGGER.error("Error processing notification: %s", err)

    def _decode_weight_bytes(self, data: bytearray) -> dict[str, Any] | None:
        """Decode weight from characteristic data using OKOK protocol."""
        if len(data) < 7:
            _LOGGER.debug("Insufficient data length: %d bytes", len(data))
            return None

        try:
            # Based on the existing script: weight at bytes 5-6 (big endian)
            weight_raw = struct.unpack('>H', data[5:7])[0]

            # Detect unit from protocol data and convert to grams using HA converter
            unit_detected = "g"  # Default assumption

            # Check for unit indicators in the data
            if len(data) > 3:
                unit_byte = data[3]
                _LOGGER.debug("Unit byte: 0x%02x", unit_byte)

                # Infer unit from byte patterns (adjust based on your scale's behavior)
                if unit_byte == 0x02:
                    unit_detected = "lb"
                elif unit_byte == 0x03:
                    unit_detected = "kg"
                elif unit_byte == 0x01:
                    unit_detected = "g"
                # Add more patterns as needed based on testing

            # Convert raw value based on detected unit
            if weight_raw == 0:
                weight_in_detected_unit = 0.0
            else:
                # If scale shows 0.928 lb but raw value is 928, divide by 1000
                # This handles the decimal scaling issue
                if unit_detected in ["lb", "kg"]:
                    weight_in_detected_unit = float(weight_raw) / 1000.0
                else:
                    weight_in_detected_unit = float(weight_raw)

            # Convert to grams using Home Assistant's converter
            try:
                from homeassistant.util.unit_conversion import MassConverter
                weight = MassConverter.convert(weight_in_detected_unit, unit_detected, "g")
            except (ValueError, ImportError):
                # Fallback if conversion fails
                weight = weight_in_detected_unit
                if unit_detected == "lb":
                    weight *= 453.592
                elif unit_detected == "kg":
                    weight *= 1000

            # Validate weight is within reasonable bounds (0-500kg)
            if weight < 0 or weight > 500000:
                _LOGGER.warning("Weight value out of range: %sg", weight)
                return None

            # Enhanced stability detection using protocol flags
            # Byte 4 contains status flags in OKOK protocol
            stable = False
            if len(data) > 4 and weight > 0:
                status_byte = data[4]
                # Different bits might indicate stability - let's log and test multiple patterns
                _LOGGER.debug("Status byte: 0x%02x (binary: %s)", status_byte, format(status_byte, '08b'))

                # Try different stability detection patterns based on common OKOK protocol patterns
                # Pattern 1: Bit 0 (0x01) - common for "measurement complete" 
                # Pattern 2: Bit 1 (0x02) - might indicate "stable reading"
                # Pattern 3: Bit 2 (0x04) - another stability flag
                # Pattern 4: Bit 4 (0x10) - sometimes used for stability
                stable_bit_0 = bool(status_byte & 0x01)
                stable_bit_1 = bool(status_byte & 0x02)
                stable_bit_2 = bool(status_byte & 0x04)
                stable_bit_4 = bool(status_byte & 0x10)

                _LOGGER.debug(
                    "Stability flags - bit0: %s, bit1: %s, bit2: %s, bit4: %s",
                    stable_bit_0, stable_bit_1, stable_bit_2, stable_bit_4
                )

                # Try multiple stability patterns - you can adjust based on your scale's behavior
                # Common patterns in OKOK protocol:
                # - 0x02 (bit 1): stable measurement
                # - 0x12 (bits 1,4): stable measurement with additional flags
                # - 0x22 (bits 1,5): another stability pattern
                if status_byte in [0x02, 0x12, 0x22, 0x06, 0x16, 0x26]:
                    stable = True
                elif stable_bit_1:  # Fallback to bit 1 check
                    stable = True
            elif weight == 0:
                # Zero weight can be considered "stable" (scale is empty)
                stable = True

            # Detect potential battery level from data
            battery_level = None
            if len(data) > 8:
                # Some scales include battery info in later bytes
                battery_raw = data[8] if data[8] <= 100 else None
                if battery_raw is not None:
                    battery_level = int(battery_raw)

            _LOGGER.debug(
                "Decoded weight: %.1f%s -> %.1fg (stable: %s, battery: %s)",
                weight_in_detected_unit, unit_detected, weight, stable, battery_level
            )

        except (struct.error, ValueError) as err:
            _LOGGER.error("Error decoding weight data: %s", err)
            return None
        else:
            result = {"weight": weight, "stable": stable, "unit": unit_detected}
            if battery_level is not None:
                result["battery_level"] = battery_level
            return result

    def _on_disconnect(self, _: BleakClientWithServiceCache) -> None:
        """Handle disconnection."""
        self._total_disconnections += 1
        _LOGGER.info("Chipsea Scale disconnected (total: %d)", self._total_disconnections)
        self._client = None
        self._notification_enabled = False

        # Schedule reconnection
        self.hass.create_task(self._async_reconnect())

    async def _async_reconnect(self) -> None:
        """Attempt to reconnect to the scale."""
        _LOGGER.debug("Attempting to reconnect to Chipsea Scale")
        with contextlib.suppress(UpdateFailed):
            # Errors are already logged in _ensure_connected
            # Will try again on next data request or advertisement
            await self._ensure_connected()

    async def async_shutdown(self) -> None:
        """Disconnect from the scale."""
        if self._client and self._client.is_connected:
            try:
                if self._notification_enabled:
                    await self._client.stop_notify(CHARACTERISTIC_UUID)
                await self._client.disconnect()
            except BleakError as err:
                _LOGGER.error("Error during shutdown: %s", err)
            finally:
                self._client = None
                self._notification_enabled = False

