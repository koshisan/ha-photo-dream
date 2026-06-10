"""Build and push now-playing media state to PhotoDream devices.

The app renders a now-playing player (compact card or full-cover focus mode).
This module reads a per-device ``media_player.*`` entity, builds the state
payload and pushes it to ``POST http://<ip>:<port>/media``. Transport buttons
in the app call back into per-device webhooks (registered in __init__).
"""
from __future__ import annotations

import logging

from homeassistant.components import webhook
from homeassistant.components.media_player import MediaPlayerEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    CONF_DEVICES,
    CONF_MEDIA_MODE,
    CONF_MEDIA_PLAYER_ENTITY,
    DEFAULT_MEDIA_MODE,
    WEBHOOK_MEDIA,
)

_LOGGER = logging.getLogger(__name__)

# Map HA media_player states to the app's four states.
_STATE_MAP = {
    "playing": "playing",
    "buffering": "playing",
    "paused": "paused",
    "idle": "idle",
    "standby": "idle",
    "on": "idle",
    "off": "off",
}

# Keyword -> MDI icon name, matched against source/app_name (lowercased).
_SOURCE_ICON_KEYWORDS = [
    ("spotify", "spotify"),
    ("youtube", "youtube"),
    ("plex", "plex"),
    ("kodi", "kodi"),
    ("radio", "radio"),
    ("tune", "radio"),
    ("podcast", "podcast"),
    ("cast", "cast"),
    ("airplay", "cast"),
    ("tv", "television"),
    ("netflix", "netflix"),
    ("soundcloud", "soundcloud"),
    ("apple", "apple"),
]


def _get_hub_devices(hass: HomeAssistant) -> dict[str, dict]:
    """Return the devices dict from the (fresh) hub config entry."""
    hub_data = hass.data.get(DOMAIN, {}).get("hub")
    if not hub_data:
        return {}
    entry_id = hub_data.get("entry_id")
    entry = hass.config_entries.async_get_entry(entry_id) if entry_id else None
    if not entry:
        return {}
    return entry.data.get(CONF_DEVICES, {})


def get_media_player_entities(hass: HomeAssistant) -> list[str]:
    """Union of media_player entities used by media-enabled devices."""
    entities: set[str] = set()
    for device in _get_hub_devices(hass).values():
        if device.get(CONF_MEDIA_MODE, DEFAULT_MEDIA_MODE) != "off":
            eid = device.get(CONF_MEDIA_PLAYER_ENTITY)
            if eid:
                entities.add(eid)
    return sorted(entities)


def _guess_source_icon(attrs: dict) -> str:
    """Best-effort MDI icon name from the player's source/app_name."""
    haystack = " ".join(
        str(attrs.get(k, "")) for k in ("source", "app_name", "app_id")
    ).lower()
    for keyword, icon in _SOURCE_ICON_KEYWORDS:
        if keyword in haystack:
            return icon
    return "music"


def _current_position(state_str: str, attrs: dict) -> int | None:
    """Interpolated playback position in seconds."""
    pos = attrs.get("media_position")
    if pos is None:
        return None
    if state_str == "playing":
        updated = attrs.get("media_position_updated_at")
        if updated is not None:
            pos = pos + (dt_util.utcnow() - updated).total_seconds()
    duration = attrs.get("media_duration")
    pos = max(0, int(pos))
    if duration:
        pos = min(pos, int(duration))
    return pos


def async_build_media_state(
    hass: HomeAssistant, device_id: str, device: dict
) -> dict | None:
    """Build the now-playing payload for a device, or None if not applicable."""
    if device.get(CONF_MEDIA_MODE, DEFAULT_MEDIA_MODE) == "off":
        return None
    entity_id = device.get(CONF_MEDIA_PLAYER_ENTITY)
    if not entity_id:
        return None
    st = hass.states.get(entity_id)
    if st is None:
        return None

    attrs = st.attributes
    state = _STATE_MAP.get(st.state, "off")

    # Cover art: entity_picture is a relative proxy path (token included).
    cover_url = ""
    pic = attrs.get("entity_picture")
    if pic:
        if pic.startswith(("http://", "https://")):
            cover_url = pic
        else:
            try:
                cover_url = get_url(hass) + pic
            except NoURLAvailableError:
                cover_url = ""

    features = attrs.get("supported_features", 0) or 0

    def _wh(action: str) -> str:
        return webhook.async_generate_url(
            hass, f"{WEBHOOK_MEDIA}_{device_id}_{action}"
        )

    payload: dict = {
        "state": state,
        "title": attrs.get("media_title") or "",
        "artist": attrs.get("media_artist") or "",
        "source": attrs.get("source") or attrs.get("app_name") or "",
        "source_icon": _guess_source_icon(attrs),
        "cover_url": cover_url,
        "can_prev": bool(features & MediaPlayerEntityFeature.PREVIOUS_TRACK),
        "can_next": bool(features & MediaPlayerEntityFeature.NEXT_TRACK),
        "controls": {
            "play_pause_url": _wh("playpause"),
            "next_url": _wh("next"),
            "prev_url": _wh("prev"),
        },
    }

    position = _current_position(state, attrs)
    if position is not None:
        payload["position"] = position
    duration = attrs.get("media_duration")
    if duration is not None:
        payload["duration"] = int(duration)

    return payload


async def async_push_media_to_device(hass: HomeAssistant, device_id: str) -> bool:
    """Push the now-playing state to a single device (if media is enabled)."""
    devices = _get_hub_devices(hass)
    device = devices.get(device_id)
    if not device or device.get(CONF_MEDIA_MODE, DEFAULT_MEDIA_MODE) == "off":
        return False

    payload = async_build_media_state(hass, device_id, device)
    if payload is None:
        return False

    from . import send_command_to_device

    return await send_command_to_device(hass, device_id, "media", payload)


async def async_push_media_all(hass: HomeAssistant, only_playing: bool = False) -> None:
    """Push now-playing state to media-enabled devices.

    With only_playing=True, skip devices whose player isn't currently playing
    (used by the periodic position-refresh timer to limit traffic).
    """
    for device_id, device in _get_hub_devices(hass).items():
        if device.get(CONF_MEDIA_MODE, DEFAULT_MEDIA_MODE) == "off":
            continue
        if only_playing:
            eid = device.get(CONF_MEDIA_PLAYER_ENTITY)
            st = hass.states.get(eid) if eid else None
            if st is None or st.state not in ("playing", "buffering"):
                continue
        await async_push_media_to_device(hass, device_id)
