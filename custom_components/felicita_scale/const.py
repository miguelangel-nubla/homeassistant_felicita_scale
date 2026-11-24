"""Constants for the Felicita Scale integration."""

from typing import Final

DOMAIN: Final = "felicita_scale"

MANUFACTURER: Final = "Felicita"

# Bluetooth service and characteristic UUIDs
SERVICE_UUID: Final = "0000ffe0-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_UUID: Final = "0000ffe1-0000-1000-8000-00805f9b34fb"

# Device name prefixes for auto-discovery
DEVICE_NAME_PREFIXES: Final = ("FELICITA",)

# Felicita command constants
COMMAND_START_TIMER: Final = 0x52
COMMAND_STOP_TIMER: Final = 0x53
COMMAND_RESET_TIMER: Final = 0x43
COMMAND_TOGGLE_TIMER: Final = 0x42
COMMAND_TOGGLE_PRECISION: Final = 0x44
COMMAND_TARE: Final = 0x54
COMMAND_TOGGLE_UNIT: Final = 0x55


def is_supported_device_name(name: str | None) -> bool:
    """Return True if a Bluetooth device name belongs to a Felicita scale."""
    if not name:
        return False
    return name.upper().startswith(DEVICE_NAME_PREFIXES)
