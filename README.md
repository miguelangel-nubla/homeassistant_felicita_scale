# Felicita Scale Integration for Home Assistant

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)
[![hacs][hacsbadge]][hacs]

[![Add to HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=miguelangel-nubla&repository=homeassistant_felicita_scale&category=integration)

A Home Assistant custom integration for Felicita-based Bluetooth smart scales including:
- FELICITA branded scales
- And other Felicita-based smart scales

## Features

- **Automatic Discovery**: Bluetooth devices are automatically discovered
- **Real-time Updates**: Instant weight readings when scale is in use
- **Multiple Units**: Supports grams, kilograms, pounds, and ounces
- **Smart Availability**: Entity becomes unavailable when scale goes to sleep
- **Battery Efficient**: Purely reactive - no unnecessary polling or connection attempts
- **Gold Quality**: Meets Home Assistant's Gold quality standards

## Supported Devices

This integration works with Bluetooth smart scales that use the Felicita chipset and protocol, including:

- Scales advertising as "FELICITA"
- Scales using service UUID `0000ffe0-0000-1000-8000-00805f9b34fb` or `0000fee0-0000-1000-8000-00805f9b34fb`
- Scales with manufacturer ID 58000 and specific manufacturer data patterns

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to "Integrations" 
3. Click the 3 dots menu and select "Custom repositories"
4. Add this repository URL: `https://github.com/miguelangel-nubla/homeassistant_felicita_scale`
5. Select category "Integration" and click "Add"
6. Find "Felicita Scale" in the list and click "Download"
7. Restart Home Assistant

### Manual Installation

1. Download the latest release from the [releases page][releases]
2. Extract the files to your `custom_components` directory:
   ```
   custom_components/
   └── felicita_scale/
       ├── __init__.py
       ├── config_flow.py
       ├── coordinator.py
       ├── models.py
       ├── sensor.py
       ├── const.py
       ├── diagnostics.py
       ├── manifest.json
       ├── strings.json
       └── hacs.json
   ```
3. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for "Felicita Scale"
4. Follow the setup wizard:
   - Your scale should be automatically discovered
   - If not found, you can manually enter the Bluetooth address
5. The integration will create sensors and controls for your scale

## Usage

- **Power on your scale** by stepping on it or placing an item
- The weight sensor shows the current measurement in grams (always normalized)
- The battery sensor shows the current battery percentage
- Use the controls to tare, toggle units, and manage timer functions
- When the scale goes to sleep, all entities become "unavailable"
- Wake the scale by using it again - entities will immediately become available

## Entities Created

### Sensors
- **Weight**: Current weight in grams (1 decimal place precision)
- **Battery**: Battery percentage

### Controls  
- **Tare Button**: Zero/tare the scale
- **Reset Timer Button**: Reset the scale's timer
- **Timer Switch**: Start/stop the scale's timer
- **Precision Switch**: Toggle high precision mode
- **Unit Select**: Choose between grams and ounces

### Weight Sensor Attributes

- `scale_unit`: The unit reported by the scale (g, oz)
- `raw_weight`: The weight in the scale's native unit with full precision
- `is_stable`: Whether the reading is stable (requires 4 consecutive identical readings)
- `last_measurement`: Timestamp of the last reading

## Troubleshooting

### Scale Not Discovered
- Ensure the scale is powered on and in pairing/advertising mode
- Check that Bluetooth is enabled on your Home Assistant system
- Try manually adding the scale using its MAC address

### Connection Issues
- Battery-powered scales disconnect frequently to save power - this is normal
- The integration will automatically reconnect when the scale advertises
- Check the diagnostic information for connection statistics

### Getting Diagnostic Information
Go to **Settings** → **Devices & Services** → **Felicita Scale** → **Download Diagnostics** to get detailed information for troubleshooting.

## Contributing

Issues and feature requests are welcome! Please check the [issue tracker][issues] before creating a new issue.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

[releases-shield]: https://img.shields.io/github/release/miguelangel-nubla/homeassistant_felicita_scale.svg?style=for-the-badge
[releases]: https://github.com/miguelangel-nubla/homeassistant_felicita_scale/releases
[commits-shield]: https://img.shields.io/github/commit-activity/y/miguelangel-nubla/homeassistant_felicita_scale.svg?style=for-the-badge
[commits]: https://github.com/miguelangel-nubla/homeassistant_felicita_scale/commits/main
[license-shield]: https://img.shields.io/github/license/miguelangel-nubla/homeassistant_felicita_scale.svg?style=for-the-badge
[hacs]: https://github.com/hacs/integration
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[issues]: https://github.com/miguelangel-nubla/homeassistant_felicita_scale/issues