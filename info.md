# Felicita Scale Integration

Integrate your Felicita-based Bluetooth smart scales with Home Assistant for real-time weight monitoring.

## Supported Devices

- FELICITA branded scales
- Generic Felicita-based scales

## Key Features

- **Automatic Discovery** - Bluetooth scales are found automatically
- **Real-time Updates** - Instant weight readings when in use  
- **Multiple Units** - Supports grams and ounces with unit switching
- **Smart Controls** - Tare, timer, precision, and unit selection controls
- **Battery Monitoring** - Dedicated battery sensor with percentage
- **Stability Detection** - Intelligent weight stability calculation
- **Smart Availability** - All entities show unavailable when scale sleeps
- **Battery Efficient** - No unnecessary polling or connections
- **Gold Quality** - Meets Home Assistant's quality standards

## Quick Setup

1. Install via HACS
2. Restart Home Assistant  
3. Go to Settings → Devices & Services
4. Add Integration → Search "Felicita Scale"
5. Your scale should be automatically discovered

The integration creates multiple entities:
- **Weight Sensor** - Real-time measurements in grams (1 decimal precision)
- **Battery Sensor** - Current battery percentage 
- **Control Buttons** - Tare and timer reset functions
- **Control Switches** - Timer and precision mode toggles
- **Unit Selector** - Choose between grams and ounces

All entities update instantly when you use your scale and go unavailable when the scale sleeps to save battery.

Perfect for kitchen automation, fitness tracking, or any application where you need to monitor weights and control scale functions in Home Assistant!