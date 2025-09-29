"""DataUpdateCoordinator for Felicita Scale."""
from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime
import logging
from typing import TYPE_CHECKING, Any

from bleak import BleakError
from bleak.backends.device import BLEDevice
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CHARACTERISTIC_UUID, 
    DOMAIN,
    COMMAND_START_TIMER,
    COMMAND_STOP_TIMER,
    COMMAND_RESET_TIMER,
    COMMAND_TOGGLE_TIMER,
    COMMAND_TOGGLE_PRECISION,
    COMMAND_TARE,
    COMMAND_TOGGLE_UNIT,
)
from .models import FelicitaScaleData

if TYPE_CHECKING:
    from homeassistant.components.bluetooth import BluetoothServiceInfoBleak

_LOGGER = logging.getLogger(__name__)

# Felicita protocol constants
PACKET_LENGTH = 18  # Felicita uses 18-byte packets
WEIGHT_BYTES_START = 3  # Weight data starts at byte 3
WEIGHT_BYTES_END = 9    # Weight data ends at byte 9
UNIT_BYTES_START = 9    # Unit data at bytes 9-11
UNIT_BYTES_END = 11
BATTERY_BYTE_INDEX = 15 # Battery level at byte 15

# Battery level constants (from reference implementation)
MIN_BATTERY_LEVEL = 129
MAX_BATTERY_LEVEL = 158

# Weight validation limits
MAX_WEIGHT_GRAMS = 5000  # 5kg in grams


class FelicitaScaleDataUpdateCoordinator(DataUpdateCoordinator[FelicitaScaleData]):
    """Class to manage fetching data from the Felicita Scale."""

    def __init__(
        self,
        hass: HomeAssistant,
        address: str,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        self.address = address.upper()
        self._config_entry = config_entry
        self._client: BleakClientWithServiceCache | None = None
        self._ble_device: BLEDevice | None = None
        self._connect_lock = asyncio.Lock()
        self._notification_enabled = False
        self._unavailable_logged = False
        self._connection_attempts = 0
        self._last_successful_connection = None
        self._total_disconnections = 0
        self._weight_history = []
        self._stability_count = 4
        self._reconnect_task: asyncio.Task | None = None
        self._ha_started = False
        self._pending_reconnect = False

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=None,
            config_entry=config_entry,
        )

        self._bluetooth_callback_unload = None

        # Listen for HA startup completion
        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STARTED, self._on_ha_started
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
    def device_info(self) -> dict[str, Any]:
        """Return device information for all entities."""
        return {
            "identifiers": {(DOMAIN, self.address)},
            "name": self._config_entry.title or "Felicita Scale",
            "manufacturer": "Felicita",
            "model": "Scale",
            "sw_version": "1.0",
            "connections": {("bluetooth", self.address.lower())},
        }

    @property
    def device_name(self) -> str:
        """Return the device name for entity naming."""
        return self.device_info["name"]

    def get_entity_name(self, entity_type: str) -> str:
        """Generate entity name with device prefix."""
        return f"{self.device_name} {entity_type}"

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
    def _on_ha_started(self, _) -> None:
        """Handle HA startup completion."""
        self._ha_started = True
        if self._pending_reconnect:
            _LOGGER.info("HA started, processing pending reconnection")
            self._pending_reconnect = False
            self._reconnect_task = self.hass.async_create_task(self._async_reconnect())

    @callback
    def _async_handle_bluetooth_event(
        self,
        service_info: BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Handle Bluetooth events."""
        _LOGGER.debug("Bluetooth event received: change=%s, address=%s, rssi=%s",
                     change, service_info.address, getattr(service_info, 'rssi', 'N/A'))
        if change == bluetooth.BluetoothChange.ADVERTISEMENT:
            self._ble_device = service_info.device
            if not self._client or not self._client.is_connected:
                # Cancel any ongoing reconnection attempt
                if self._reconnect_task and not self._reconnect_task.done():
                    self._reconnect_task.cancel()

                if self._ha_started:
                    # HA has started, safe to reconnect immediately
                    _LOGGER.info("Scale detected, attempting reconnection")
                    self._reconnect_task = self.hass.async_create_task(self._async_reconnect())
                else:
                    # HA still starting up, defer reconnection
                    _LOGGER.info("Scale detected during startup, deferring reconnection")
                    self._pending_reconnect = True

    async def _async_update_data(self) -> FelicitaScaleData:
        """Return current data - all updates are reactive via Bluetooth notifications."""
        return self.data or FelicitaScaleData()

    async def _ensure_connected(self) -> None:
        """Ensure we have a connection to the scale."""
        async with self._connect_lock:
            if self._client and self._client.is_connected:
                return

            _LOGGER.debug("Connecting to Felicita Scale at %s", self.address)

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
                )

                await self._setup_notifications()

                self._last_successful_connection = datetime.now()

                if not self._unavailable_logged:
                    _LOGGER.info("Successfully connected to Felicita Scale (attempt %d)",
                                self._connection_attempts)

                if self._unavailable_logged:
                    _LOGGER.info("Felicita Scale is back online")
                    self._unavailable_logged = False

            except (TimeoutError, BleakError) as err:
                error_msg = str(err).lower()
                expected_errors = {
                    "no backend with an available connection slot",
                    "device is no longer reachable", 
                    "out of connection slots",
                    "device disconnected",
                    "not connected"
                }
                
                is_expected_error = any(phrase in error_msg for phrase in expected_errors)
                
                if not self._unavailable_logged:
                    if is_expected_error:
                        _LOGGER.info("Device not reachable (expected for battery-powered scales): %s", err)
                    else:
                        _LOGGER.error("Failed to connect to Felicita Scale: %s", err)
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
                    self.data = FelicitaScaleData()

                # Update all weight-related fields
                new_weight = weight_data["weight"]  # Normalized to grams
                self.data.weight = new_weight
                self.data.unit = weight_data["unit"]  # Scale's native unit
                self.data.raw_weight = weight_data["raw_weight"]  # Weight in native unit
                self.data.last_measurement = datetime.now()
                
                # Calculate stability based on consecutive identical readings
                self.data.is_stable = self._calculate_stability(new_weight)

                # Update battery level if available
                if "battery_level" in weight_data:
                    self.data.battery_level = weight_data["battery_level"]


                # Notify Home Assistant of the update
                self.async_set_updated_data(self.data)

        except (KeyError, TypeError, ValueError) as err:
            _LOGGER.error("Error processing notification: %s", err)


    def _validate_packet(self, data: bytearray) -> bool:
        """Validate Felicita packet structure."""
        if len(data) != PACKET_LENGTH:
            _LOGGER.debug("Invalid packet length: %d bytes (expected %d)", len(data), PACKET_LENGTH)
            return False
        return True

    def _extract_unit_from_bytes(self, data: bytearray) -> str:
        """Extract unit from bytes 9-11 using Felicita protocol."""
        if len(data) < UNIT_BYTES_END:
            return "g"  # Default to grams
        
        try:
            # Extract unit bytes and decode as text
            unit_bytes = data[UNIT_BYTES_START:UNIT_BYTES_END]
            unit_str = bytes(unit_bytes).decode('utf-8', errors='ignore').strip()
            
            # Map to standard units
            if 'g' in unit_str.lower():
                return "g"
            elif 'oz' in unit_str.lower():
                return "oz"
            else:
                return "g"  # Default to grams
                
        except (UnicodeDecodeError, IndexError):
            return "g"  # Default to grams

    def _calculate_stability(self, weight: float) -> bool:
        """Calculate if weight is stable based on consecutive identical readings."""
        # Round weight to 1 decimal place for stability comparison
        rounded_weight = round(weight, 1)
        
        # Zero weight is never considered stable (tared/empty scale)
        if rounded_weight == 0.0:
            self._weight_history.clear()  # Reset history when at zero
            return False
        
        # Add to history
        self._weight_history.append(rounded_weight)
        
        # Keep only the last stability_count readings
        if len(self._weight_history) > self._stability_count:
            self._weight_history.pop(0)
        
        # Check if we have enough readings and they're all the same
        if len(self._weight_history) >= self._stability_count:
            return all(w == self._weight_history[0] for w in self._weight_history)
        
        return False

    def _calculate_battery_percentage(self, battery_byte: int) -> int:
        """Calculate battery percentage from Felicita protocol."""
        if battery_byte < MIN_BATTERY_LEVEL:
            return 0
        elif battery_byte > MAX_BATTERY_LEVEL:
            return 100
        else:
            # Calculate percentage within the known range
            percentage = ((battery_byte - MIN_BATTERY_LEVEL) / (MAX_BATTERY_LEVEL - MIN_BATTERY_LEVEL)) * 100
            return round(percentage)
    
    def _convert_to_grams(self, weight: float, unit: str) -> float:
        """Convert weight from native unit to grams."""
        conversion_factors = {
            "g": 1.0,
            "kg": 1000.0,
            "lb": 453.592,
            "oz": 28.3495
        }
        
        if unit in conversion_factors:
            return weight * conversion_factors[unit]
        else:
            return weight

    def _decode_weight_bytes(self, data: bytearray) -> dict[str, Any] | None:
        """Decode weight from characteristic data using Felicita protocol."""
        if not self._validate_packet(data):
            return None

        try:
            _LOGGER.debug("Raw packet: %s", ' '.join(f'{b:02x}' for b in data))
            
            # Extract weight from bytes 3-9 as ASCII values (Felicita protocol)
            weight_bytes = data[WEIGHT_BYTES_START:WEIGHT_BYTES_END]
            
            # Convert ASCII bytes directly to string, then to number
            weight_str = ""
            weight_digits = ""
            try:
                weight_str = weight_bytes.decode('ascii', errors='ignore')
                # Remove any non-digit characters
                weight_digits = ''.join(c for c in weight_str if c.isdigit())
                    
            except (UnicodeDecodeError, ValueError):
                _LOGGER.warning("Failed to decode weight from bytes: %s", weight_bytes.hex())
                weight_digits = ""
            
            # Extract unit from bytes 9-11 FIRST, then adjust weight parsing
            unit_detected = self._extract_unit_from_bytes(data)
            
            # Now re-parse weight with correct decimal places based on unit
            if not weight_digits:
                weight_in_detected_unit = 0.0
            else:
                weight_raw = int(weight_digits)
                
                # Different units have different decimal precision
                if unit_detected == "oz":
                    # Ounces: "020140" → 2.014 oz (divide by 10000)
                    weight_in_detected_unit = float(weight_raw) / 10000.0
                else:
                    # Grams: "000640" → 6.40 g (divide by 100)
                    weight_in_detected_unit = float(weight_raw) / 100.0
            
            # Extract battery level from byte 15
            battery_level = None
            if len(data) > BATTERY_BYTE_INDEX:
                battery_byte = data[BATTERY_BYTE_INDEX]
                battery_level = self._calculate_battery_percentage(battery_byte)
            
            # Convert to grams for consistency
            weight_grams = self._convert_to_grams(weight_in_detected_unit, unit_detected)

            if abs(weight_grams) > MAX_WEIGHT_GRAMS:
                _LOGGER.warning("Weight value out of range: %.1fg (max: %dg)", weight_grams, MAX_WEIGHT_GRAMS)
                return None

            _LOGGER.debug(
                "Weight parsing: raw_bytes=%s ascii=%s digits=%s -> %.3f%s -> %.1fg (battery: %s%%)",
                weight_bytes.hex(), weight_str, weight_digits, weight_in_detected_unit, unit_detected, weight_grams, battery_level
            )

            return {
                "weight": weight_grams,
                "unit": unit_detected,
                "raw_weight": weight_in_detected_unit,
                "battery_level": battery_level
            }

        except (ValueError, IndexError) as err:
            _LOGGER.error("Error decoding weight data: %s", err)
            return None

    def _on_disconnect(self, _: BleakClientWithServiceCache) -> None:
        """Handle disconnection."""
        self._total_disconnections += 1
        _LOGGER.info("Felicita Scale disconnected (total: %d)", self._total_disconnections)

        # Reset connection state
        self._client = None
        self._notification_enabled = False
        self._weight_history.clear()
        self._unavailable_logged = False
        self.data = None

        # Cancel ongoing reconnection and re-register callback
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
        self._register_bluetooth_callback()

        self.async_update_listeners()

    def _register_bluetooth_callback(self) -> None:
        """Register Bluetooth callback for device detection."""
        if self._bluetooth_callback_unload:
            self._bluetooth_callback_unload()

        self._bluetooth_callback_unload = bluetooth.async_register_callback(
            self.hass,
            self._async_handle_bluetooth_event,
            {"address": self.address},
            bluetooth.BluetoothScanningMode.ACTIVE,
        )
        

    async def _async_reconnect(self) -> None:
        """Attempt to reconnect to the scale."""
        _LOGGER.debug("Attempting to reconnect to Felicita Scale")
        try:
            await self._ensure_connected()
        except asyncio.CancelledError:
            _LOGGER.debug("Connection attempt was cancelled")
            raise
        except UpdateFailed:
            pass

    async def async_shutdown(self) -> None:
        """Disconnect from the scale."""
        # Cancel reconnection task and unload callback
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
        if self._bluetooth_callback_unload:
            self._bluetooth_callback_unload()

        # Disconnect client
        if self._client and self._client.is_connected:
            with contextlib.suppress(BleakError):
                if self._notification_enabled:
                    await self._client.stop_notify(CHARACTERISTIC_UUID)
                await self._client.disconnect()

        self._client = None
        self._notification_enabled = False

    async def _send_command(self, command: int) -> bool:
        """Send a command to the Felicita scale."""
        try:
            await self._ensure_connected()
            if not self._client or not self._client.is_connected:
                _LOGGER.error("Cannot send command: not connected to scale")
                return False
            
            command_bytes = bytes([command])
            await self._client.write_gatt_char(CHARACTERISTIC_UUID, command_bytes)
            _LOGGER.debug("Sent command 0x%02x to Felicita scale", command)
            return True
            
        except BleakError as err:
            _LOGGER.error("Error sending command 0x%02x: %s", command, err)
            return False

    async def async_tare(self) -> bool:
        """Tare the scale (reset to zero)."""
        _LOGGER.info("Taring Felicita scale")
        return await self._send_command(COMMAND_TARE)

    async def async_toggle_unit(self) -> bool:
        """Toggle between grams and ounces."""
        _LOGGER.info("Toggling unit on Felicita scale")
        return await self._send_command(COMMAND_TOGGLE_UNIT)

    async def async_start_timer(self) -> bool:
        """Start the scale's timer."""
        _LOGGER.info("Starting timer on Felicita scale")
        return await self._send_command(COMMAND_START_TIMER)

    async def async_stop_timer(self) -> bool:
        """Stop the scale's timer."""
        _LOGGER.info("Stopping timer on Felicita scale")
        return await self._send_command(COMMAND_STOP_TIMER)

    async def async_reset_timer(self) -> bool:
        """Reset the scale's timer to zero."""
        _LOGGER.info("Resetting timer on Felicita scale")
        return await self._send_command(COMMAND_RESET_TIMER)

    async def async_toggle_timer(self) -> bool:
        """Toggle the scale's timer (start/stop)."""
        _LOGGER.info("Toggling timer on Felicita scale")
        return await self._send_command(COMMAND_TOGGLE_TIMER)

    async def async_toggle_precision(self) -> bool:
        """Toggle the scale's precision mode."""
        _LOGGER.info("Toggling precision on Felicita scale")
        return await self._send_command(COMMAND_TOGGLE_PRECISION)

