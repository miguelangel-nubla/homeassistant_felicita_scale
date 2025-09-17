"""Constants for the Felicita Scale integration."""

DOMAIN = "felicita_scale"

# Bluetooth service and characteristic UUIDs
SERVICE_UUID = "0000ffe0-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"

# Device name prefixes for auto-discovery
DEVICE_NAME_PREFIXES = ["FELICITA"]

# Felicita command constants
COMMAND_START_TIMER = 0x52
COMMAND_STOP_TIMER = 0x53
COMMAND_RESET_TIMER = 0x43
COMMAND_TOGGLE_TIMER = 0x42
COMMAND_TOGGLE_PRECISION = 0x44
COMMAND_TARE = 0x54
COMMAND_TOGGLE_UNIT = 0x55

