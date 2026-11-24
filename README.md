# Felicita Scale for Home Assistant

<!-- ha-marketplace:exclude-start -->
[![GitHub Release][releases-shield]][releases]
[![Validate][validate-shield]][validate]
[![Tests][tests-shield]][tests]
[![License][license-shield]](LICENSE)

[![Open your Home Assistant instance and open this repository in the Marketplace.](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=miguelangel-nubla&repository=homeassistant_felicita_scale&category=integration)
<!-- ha-marketplace:exclude-end -->

A Home Assistant integration for FELICITA Bluetooth coffee scales, such as the Arc. It shows live weight and battery level, and lets you tare the scale, run its timer, and switch units from Home Assistant.

## Features

- **Automatic discovery**: Home Assistant finds scales advertising as `FELICITA`, through a local adapter or an ESPHome Bluetooth proxy.
- **Live weight**: the scale pushes readings, with no polling. Negative weights after a tare are reported correctly.
- **Controls**: tare, timer start/stop/reset, precision mode and unit (grams/ounces).
- **Battery friendly**: connects only while the scale is advertising, and keeps retrying while it is awake so a failed attempt or a quick power cycle never leaves it disconnected.
- **Clear availability**: all entities go unavailable when the scale sleeps and come back when it wakes up.

## Installation

### Marketplace (recommended)

1. In Home Assistant, go to **Settings** → **Marketplace**, or use the button above.
2. Search for **Felicita Scale** and download it.
3. Restart Home Assistant.

Until the integration is in the default catalog, add `https://github.com/miguelangel-nubla/homeassistant_felicita_scale` as a custom repository of type **Integration** first.

### Manual

1. Download the latest release from the [releases page][releases].
2. Copy the `custom_components/felicita_scale` folder into your Home Assistant `config/custom_components` folder.
3. Restart Home Assistant.

## Configuration

Turn the scale on near a Bluetooth adapter or proxy. Home Assistant shows it under **Settings** → **Devices & services** as discovered. Select **Add** to set it up.

To add it by hand, go to **Settings** → **Devices & services** → **Add integration**, search for **Felicita Scale**, and pick the scale from the list or enter its Bluetooth address.

## Entities

| Entity | Type | Description |
| --- | --- | --- |
| Weight | Sensor | Current weight in grams, whatever unit the scale shows. |
| Battery | Sensor (diagnostic) | Battery level in percent. |
| Tare | Button | Zero the scale. |
| Reset timer | Button | Reset the scale's timer to zero. |
| Timer | Switch | Start or stop the scale's timer. |
| Precision | Switch | Toggle high precision mode. |
| Unit | Select | Unit shown on the scale: grams or ounces. |

The scale does not report the timer or precision state, so those switches show the state Home Assistant last set (an *assumed state*). They reset to off when the scale disconnects. Changing a setting on the scale itself does not update them.

The weight sensor also has these attributes:

- `scale_unit`: unit shown on the scale (`g` or `oz`).
- `raw_weight`: weight in that unit, at full precision.
- `is_stable`: `true` after four identical consecutive readings. An empty scale is never stable.
- `last_measurement`: time of the last reading.

## Troubleshooting

- **Scale not discovered**: make sure the scale is on and in range of a Bluetooth adapter or proxy, and that the Bluetooth integration is set up. Other apps connected to the scale (such as a phone app) block Home Assistant from connecting.
- **Entities unavailable**: this is normal while the scale is off or asleep. They come back when you turn it on.
- **Diagnostics**: go to **Settings** → **Devices & services** → **Felicita Scale** → ⋮ → **Download diagnostics**. The Bluetooth address is redacted.
- **Debug logs**: enable debug logging for the integration from the same menu to see every packet the scale sends.

## Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements_test.txt
pytest
ruff check . && ruff format --check .
```

The packet format is documented in [protocol_notes.txt](protocol_notes.txt).

To release, bump `version` in `custom_components/felicita_scale/manifest.json`, merge to `master`, then push a tag with the same version (for example `git tag 1.3.0 && git push origin 1.3.0`). The release workflow checks the tag matches the manifest, runs the tests and publishes the GitHub release with generated notes. A tag such as `1.4.0b1` is published as a pre-release.

The icon is drawn in [assets/icon.svg](assets/icon.svg). After editing it, run `python assets/build_brand.py` (needs `rsvg-convert` from librsvg) to regenerate the light and dark PNGs in `custom_components/felicita_scale/brand/`.

## Contributing

Issues and pull requests are welcome. Please check the [issue tracker][issues] first.

## License

MIT. See [LICENSE](LICENSE).

[releases-shield]: https://img.shields.io/github/release/miguelangel-nubla/homeassistant_felicita_scale.svg?style=for-the-badge
[releases]: https://github.com/miguelangel-nubla/homeassistant_felicita_scale/releases
[validate-shield]: https://img.shields.io/github/actions/workflow/status/miguelangel-nubla/homeassistant_felicita_scale/validate.yaml?style=for-the-badge&label=validate
[validate]: https://github.com/miguelangel-nubla/homeassistant_felicita_scale/actions/workflows/validate.yaml
[tests-shield]: https://img.shields.io/github/actions/workflow/status/miguelangel-nubla/homeassistant_felicita_scale/tests.yaml?style=for-the-badge&label=tests
[tests]: https://github.com/miguelangel-nubla/homeassistant_felicita_scale/actions/workflows/tests.yaml
[license-shield]: https://img.shields.io/github/license/miguelangel-nubla/homeassistant_felicita_scale.svg?style=for-the-badge
[issues]: https://github.com/miguelangel-nubla/homeassistant_felicita_scale/issues
