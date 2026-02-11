# PhotoDream - Home Assistant Integration

Home Assistant custom integration for [PhotoDream](https://github.com/koshisan/PhotoDream) - an Immich-based photo slideshow for Android tablets.

## Features

- 📱 Central configuration for multiple PhotoDream tablets
- 🖼️ Connect to your Immich server for photo management
- 🎨 Create filter profiles with search queries and path exclusions
- ⏰ Configure display settings (clock, interval, Ken Burns effect)
- 🔄 Real-time status updates via webhook
- 🎛️ Control tablets via services and entities

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click on "Integrations"
3. Click the three dots menu → "Custom repositories"
4. Add `https://github.com/koshisan/ha-photo-dream` as category "Integration"
5. Install "PhotoDream"
6. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/photo_dream` folder to your Home Assistant's `custom_components` directory
2. Restart Home Assistant

## Configuration

1. Go to Settings → Devices & Services → Add Integration
2. Search for "PhotoDream"
3. Enter your Immich server URL and API key
4. Create one or more profiles (search queries + exclusions)
5. Add your tablets (IP address, profile, display settings)

## Entities

For each configured tablet, the following entities are created:

| Entity | Type | Description |
|--------|------|-------------|
| `sensor.photodream_<device>_current_image` | Sensor | Currently displayed image ID |
| `binary_sensor.photodream_<device>_online` | Binary Sensor | Device connectivity status |
| `select.photodream_<device>_profile` | Select | Active profile selector |

## Services

| Service | Description |
|---------|-------------|
| `photo_dream.next_image` | Advance to the next image |
| `photo_dream.refresh_config` | Reload configuration on tablet |
| `photo_dream.set_profile` | Change the active profile |

## Architecture

```
Home Assistant                          Android Tablet
┌─────────────────┐                    ┌─────────────────┐
│  PhotoDream     │◄── Webhook ────────│  PhotoDream     │
│  Integration    │    (status)        │  App            │
│                 │                    │                 │
│  • Profiles     │─── REST API ──────►│  • HTTP Server  │
│  • Devices      │    (commands)      │  • DreamService │
│  • Immich creds │                    │  • Immich Client│
└─────────────────┘                    └────────┬────────┘
                                                │
                                                ▼
                                       ┌─────────────────┐
                                       │     Immich      │
                                       │  (photos)       │
                                       └─────────────────┘
```

## Tablet App Setup

In the PhotoDream Android app, configure:

- **Home Assistant URL**: `http://your-ha-ip:8123`
- **Device ID**: Must match the Device ID in HA config (e.g., `kitchen`)
- **Webhook ID**: From HA (shown in integration config or find in `.storage`)

## Example Automation

```yaml
automation:
  - alias: "Christmas Mode in December"
    trigger:
      - platform: time
        at: "00:00:00"
    condition:
      - condition: template
        value_template: "{{ now().month == 12 }}"
    action:
      - service: photo_dream.set_profile
        data:
          device_id: kitchen
          profile: christmas
```

## License

MIT
