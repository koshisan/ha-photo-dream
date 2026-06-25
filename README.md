# PhotoDream - Home Assistant Integration

Home Assistant custom integration for [PhotoDream](https://github.com/koshisan/PhotoDream) - an Immich-based photo slideshow for Android tablets.

## Features

- 📱 Central configuration for multiple PhotoDream tablets
- 🖼️ Connect to your Immich server for photo management
- 🎨 Create filter profiles with search queries and path exclusions
- ⏰ Configure display settings (clock, interval, Ken Burns effect)
- 📅 Calendar overlay – merge multiple `calendar.*` entities onto the slideshow
- 🔔 Notification overlay – HA-styled popups with image, sound and tap callback
- 🎵 Media player overlay – now-playing card/focus mode with transport controls
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
| `switch.photodream_<device>_calendar` | Switch | Toggle the calendar overlay |
| `switch.photodream_<device>_calendar_show_location` | Switch | Show event location |
| `switch.photodream_<device>_skip_wrong_aspect` | Switch | Only show media whose aspect ratio fits the display (~20%) |
| `switch.photodream_<device>_always_play_full_video` | Switch | Let videos finish before advancing |
| `select.photodream_<device>_calendar_position` | Select | Calendar overlay position |
| `number.photodream_<device>_calendar_max_events` | Number | Max events shown |
| `number.photodream_<device>_calendar_font_size` | Number | Calendar font size |
| `select.photodream_<device>_media_mode` | Select | Media overlay mode (off/compact/focus) |
| `select.photodream_<device>_media_player` | Select | Media player source entity |
| `notify.photodream_<device>` | Notify | Simple message/title popup |

## Services

| Service | Description |
|---------|-------------|
| `photo_dream.next_image` | Advance to the next image |
| `photo_dream.refresh_config` | Reload configuration on tablet |
| `photo_dream.set_profile` | Change the active profile |
| `photo_dream.notify` | Show a rich notification popup on the slideshow |

## Calendar Overlay

The calendar overlay shows upcoming events on top of the slideshow. Calendars are
configured **per device**, so each tablet can show a different set of calendars.

**Setup:** Settings → Devices & Services → PhotoDream → *Configure* → edit a device:

1. Enable **Show Calendar** and pick one or more **Calendars to show** (any `calendar.*` entity).
2. Choose **Calendar Position**, **Max Events**, **Show Event Location** and **Calendar Font Size**.
3. On the next step, pick an accent **color** per calendar (a palette is pre-assigned).

The integration polls `calendar.get_events` over the selected calendars (next 7 days),
merges and sorts them, and pushes the list to the device automatically — every
15 minutes, whenever a selected calendar changes, and right after a config change.
No automation required. Events are grouped on-device by day ("Today", "Tomorrow", …).

## Notifications

Two ways to show a popup over the slideshow:

- **`notify.photodream_<device>`** entity — for simple `message` + `title` popups
  (uses the app's default color/duration). Works anywhere a notify target is accepted.
- **`photo_dream.notify`** service — for the full feature set (icon, image, sound,
  duration, tap callback). `shown` is `false` if no slideshow is currently running.
  The `icon` field takes an MDI name (e.g. `mdi:doorbell`); unknown/empty falls back
  to `mdi:bell`.

```yaml
automation:
  - alias: "Doorbell popup on the kitchen tablet"
    trigger:
      - platform: state
        entity_id: binary_sensor.front_door_ring
        to: "on"
    action:
      - service: photo_dream.notify
        data:
          device_id: kitchen
          title: "Front Door"
          message: "Someone is at the door"
          icon: "mdi:doorbell"
          color: "#f44336"
          image_url: "https://ha.local/api/camera_proxy/camera.door?token=XYZ"
          duration: 10
          sound: true
          callback_url: "https://ha.local/api/webhook/doorbell_ack"
          callback_method: POST
```

The tap **callback** is fire-and-forget. Point `callback_url` at an HA webhook and
trigger an automation on it (e.g. acknowledge the doorbell, turn on a light).
The `image_url` must be reachable **without** authentication (e.g. `camera_proxy`
with a token in the URL).

## Media Player

Shows a now-playing card over the slideshow, driven by a `media_player.*` entity —
configured **per device**.

**Setup:** Settings → Devices & Services → PhotoDream → *Configure* → edit a device:

1. Set **Media Player Mode**: `off`, `compact` (small card top-left), or `focus`
   (full cover, slideshow dimmed, artist background).
2. Pick the **Media Player** entity for that tablet.

The integration pushes the now-playing state to the device automatically — on every
state/track change and every 5 s while playing (so the progress bar advances). The
player only appears while something is `playing`/`paused`. `source_icon` is derived
automatically from the player's source/app (Spotify, YouTube, radio, cast …).

**Transport controls** are zero-config: the integration registers three webhooks per
device and includes their URLs in the pushed state. Tapping play/pause, next or prev
on the tablet calls `media_player.media_play_pause` / `media_next_track` /
`media_previous_track` on that device's player.

**Focus-mode HD art (optional):** register a free project key at
[fanart.tv](https://fanart.tv) and enter it under *Configure → Hub settings
(fanart.tv key)* — it applies to all devices. Without a key the app falls back to
TheAudioDB (free, no key).

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
