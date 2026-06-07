"""Constants for PhotoDream integration."""
from datetime import timedelta
from typing import Final

DOMAIN: Final = "photo_dream"

# Entry types (stored in entry.data["entry_type"])
ENTRY_TYPE_HUB: Final = "hub"
ENTRY_TYPE_IMMICH: Final = "immich"

# Config keys - Hub
CONF_DEVICES: Final = "devices"

# Config keys - Immich instance
CONF_IMMICH_URL: Final = "immich_url"
CONF_IMMICH_API_KEY: Final = "immich_api_key"
CONF_IMMICH_NAME: Final = "immich_name"
CONF_PROFILES: Final = "profiles"

# Device config keys
CONF_DEVICE_ID: Final = "device_id"
CONF_DEVICE_NAME: Final = "device_name"
CONF_DEVICE_IP: Final = "device_ip"
CONF_DEVICE_PORT: Final = "device_port"
CONF_DEVICE_PROFILE: Final = "device_profile"

# Display config keys
CONF_CLOCK: Final = "clock"
CONF_CLOCK_POSITION: Final = "clock_position"
CONF_CLOCK_FORMAT: Final = "clock_format"
CONF_CLOCK_FONT_SIZE: Final = "clock_font_size"
CONF_DATE: Final = "date"
CONF_DATE_FORMAT: Final = "date_format"
CONF_WEATHER: Final = "weather"
CONF_INTERVAL: Final = "interval_seconds"
CONF_PAN_SPEED: Final = "pan_speed"
CONF_DISPLAY_MODE: Final = "display_mode"

# Profile config keys
CONF_PROFILE_NAME: Final = "name"
CONF_PROFILE_ID: Final = "profile_id"
CONF_SEARCH_FILTER: Final = "search_filter"
CONF_EXCLUDE_PATHS: Final = "exclude_paths"
CONF_MEDIA_TYPE: Final = "media_type"

# Calendar config keys (per device)
CONF_CALENDAR: Final = "calendar"  # overlay enabled (bool)
CONF_CALENDAR_POSITION: Final = "calendar_position"
CONF_CALENDAR_MAX_EVENTS: Final = "calendar_max_events"
CONF_CALENDAR_SHOW_LOCATION: Final = "calendar_show_location"
CONF_CALENDAR_FONT_SIZE: Final = "calendar_font_size"
CONF_CALENDAR_ENTITIES: Final = "calendar_entities"  # list[str] of calendar.* entity_ids
CONF_CALENDAR_COLORS: Final = "calendar_colors"  # dict[entity_id -> "#RRGGBB"]
CONF_CALENDAR_LOOKAHEAD_DAYS: Final = "calendar_lookahead_days"

# Calendar defaults
DEFAULT_CALENDAR: Final = False
DEFAULT_CALENDAR_POSITION: Final = 3  # bottom-left (same scheme as clock)
DEFAULT_CALENDAR_MAX_EVENTS: Final = 5
DEFAULT_CALENDAR_SHOW_LOCATION: Final = False
DEFAULT_CALENDAR_FONT_SIZE: Final = 16
DEFAULT_CALENDAR_LOOKAHEAD_DAYS: Final = 7

# Default color palette used when a calendar has no explicit color mapping
CALENDAR_COLOR_PALETTE: Final = [
    "#03a9f4",  # light blue
    "#8bc34a",  # light green
    "#ff9800",  # orange
    "#e91e63",  # pink
    "#9c27b0",  # purple
    "#00bcd4",  # cyan
    "#cddc39",  # lime
    "#f44336",  # red
]

# How often the integration pushes merged calendar events to devices
CALENDAR_PUSH_INTERVAL: Final = timedelta(minutes=15)
# Coalesce window for calendar state-change driven pushes (seconds)
CALENDAR_DEBOUNCE_SECONDS: Final = 5

# Media type options
DEFAULT_MEDIA_TYPE: Final = "image"
MEDIA_TYPES: Final = {
    "image": "Photos only",
    "video": "Videos only",
    "both": "Photos & Videos",
}

# Defaults
DEFAULT_PORT: Final = 8080
DEFAULT_CLOCK: Final = True
DEFAULT_CLOCK_POSITION: Final = 3  # bottom-left
DEFAULT_CLOCK_FORMAT: Final = "24h"
DEFAULT_CLOCK_FONT_SIZE: Final = 32
DEFAULT_DATE: Final = False
DEFAULT_DATE_FORMAT: Final = "dd.MM.yyyy"
DEFAULT_WEATHER: Final = False
DEFAULT_INTERVAL: Final = 30
DEFAULT_PAN_SPEED: Final = 0.5
DEFAULT_DISPLAY_MODE: Final = "smart_shuffle"

# Clock positions (0-6)
CLOCK_POSITIONS: Final = {
    0: "Top Left",
    1: "Top Center",
    2: "Top Right",
    3: "Bottom Left",
    4: "Bottom Center",
    5: "Bottom Right",
    6: "Center",
}

# Date formats
DATE_FORMATS: Final = {
    "dd.MM.yyyy": "31.12.2025",
    "MM/dd/yyyy": "12/31/2025",
    "yyyy-MM-dd": "2025-12-31",
    "dd MMM yyyy": "31 Dec 2025",
    "EEEE, dd.MM.": "Wednesday, 31.12.",
    "EEE, dd.MM.": "Wed, 31.12.",
}

# Services
SERVICE_NEXT_IMAGE: Final = "next_image"
SERVICE_REFRESH_CONFIG: Final = "refresh_config"
SERVICE_SET_PROFILE: Final = "set_profile"
SERVICE_NOTIFY: Final = "notify"

# Notify service attributes
ATTR_MESSAGE: Final = "message"
ATTR_TITLE: Final = "title"
ATTR_ICON: Final = "icon"
ATTR_COLOR: Final = "color"
ATTR_IMAGE_URL: Final = "image_url"
ATTR_DURATION: Final = "duration"
ATTR_SOUND: Final = "sound"
ATTR_CALLBACK_URL: Final = "callback_url"
ATTR_CALLBACK_METHOD: Final = "callback_method"

# Notify defaults (match the app-side defaults from the handover doc)
DEFAULT_NOTIFY_COLOR: Final = "#2196F3"
DEFAULT_NOTIFY_DURATION: Final = 8
DEFAULT_NOTIFY_SOUND: Final = False
DEFAULT_NOTIFY_CALLBACK_METHOD: Final = "POST"

# Attributes
ATTR_DEVICE_ID: Final = "device_id"
ATTR_PROFILE: Final = "profile"
ATTR_PROFILE_ID: Final = "profile_id"
ATTR_CURRENT_IMAGE: Final = "current_image"
ATTR_CURRENT_IMAGE_URL: Final = "current_image_url"
ATTR_LAST_SEEN: Final = "last_seen"
ATTR_ACTIVE: Final = "active"
ATTR_MAC_ADDRESS: Final = "mac_address"
ATTR_IP_ADDRESS: Final = "ip_address"
ATTR_DISPLAY_WIDTH: Final = "display_width"
ATTR_DISPLAY_HEIGHT: Final = "display_height"
ATTR_APP_VERSION: Final = "app_version"

# Webhooks
WEBHOOK_REGISTER: Final = "photo_dream_register"
WEBHOOK_STATUS: Final = "photo_dream_status"
WEBHOOK_KEY_EVENT: Final = "photo_dream_key_event"

# Weather config
CONF_WEATHER_ENTITY: Final = "weather_entity"
CONF_WEATHER_ENABLED: Final = "weather_enabled"
DEFAULT_WEATHER_ENABLED: Final = False

# Update config
GITHUB_REPO: Final = "koshisan/PhotoDream"
GITHUB_API_RELEASES: Final = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
