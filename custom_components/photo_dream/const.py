"""Constants for PhotoDream integration."""
from typing import Final

DOMAIN: Final = "photo_dream"

# Config keys
CONF_IMMICH_URL: Final = "immich_url"
CONF_IMMICH_API_KEY: Final = "immich_api_key"
CONF_DEVICES: Final = "devices"
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
CONF_WEATHER: Final = "weather"
CONF_INTERVAL: Final = "interval_seconds"
CONF_PAN_SPEED: Final = "pan_speed"
CONF_DISPLAY_MODE: Final = "display_mode"

# Profile config keys
CONF_PROFILE_NAME: Final = "name"
CONF_SEARCH_QUERIES: Final = "search_queries"
CONF_EXCLUDE_PATHS: Final = "exclude_paths"

# Defaults
DEFAULT_PORT: Final = 8080
DEFAULT_CLOCK: Final = True
DEFAULT_CLOCK_POSITION: Final = 3  # bottom-right
DEFAULT_CLOCK_FORMAT: Final = "24h"
DEFAULT_WEATHER: Final = False
DEFAULT_INTERVAL: Final = 30
DEFAULT_PAN_SPEED: Final = 0.5
DEFAULT_DISPLAY_MODE: Final = "smart_shuffle"

# Clock positions
CLOCK_POSITIONS: Final = {
    0: "Top Left",
    1: "Top Right",
    2: "Bottom Left",
    3: "Bottom Right",
}

# Services
SERVICE_NEXT_IMAGE: Final = "next_image"
SERVICE_REFRESH_CONFIG: Final = "refresh_config"
SERVICE_SET_PROFILE: Final = "set_profile"

# Attributes
ATTR_DEVICE_ID: Final = "device_id"
ATTR_PROFILE: Final = "profile"
ATTR_CURRENT_IMAGE: Final = "current_image"
ATTR_CURRENT_IMAGE_URL: Final = "current_image_url"
ATTR_LAST_SEEN: Final = "last_seen"

# Webhooks
WEBHOOK_REGISTER: Final = "photo_dream_register"
WEBHOOK_STATUS: Final = "photo_dream_status"
