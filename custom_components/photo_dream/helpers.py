"""Helper functions for PhotoDream integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, format_mac
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, CONF_DEVICES, CONF_DEVICE_NAME, ATTR_MAC_ADDRESS

_LOGGER = logging.getLogger(__name__)


def get_hub_entry(hass: HomeAssistant) -> ConfigEntry | None:
    """Return the live hub config entry.

    Every read AND write of device config must go through this, so both sides
    see the same entry (a cached ConfigEntry reference can diverge from it).
    """
    hub_data = hass.data.get(DOMAIN, {}).get("hub")
    entry_id = hub_data.get("entry_id") if hub_data else None
    return hass.config_entries.async_get_entry(entry_id) if entry_id else None


def update_device_config(
    hass: HomeAssistant,
    own_entry: ConfigEntry,
    device_id: str,
    device_config: dict,
    key: str,
    value: Any,
) -> None:
    """Persist one device setting into the hub entry that config pushes read."""
    entry = get_hub_entry(hass) or own_entry
    if entry is not own_entry:
        _LOGGER.warning(
            "Entity of %s belongs to entry %s but the hub is %s - writing to the hub",
            device_id, own_entry.entry_id, entry.entry_id,
        )
    # Deep-copy the devices map so async_update_entry detects a real change
    # and fires update listeners (re-subscriptions). Mutating the shared
    # dict in place makes HA see "no change" and skip the listeners.
    devices = {k: dict(v) for k, v in entry.data.get(CONF_DEVICES, {}).items()}
    devices.setdefault(device_id, dict(device_config))
    devices[device_id][key] = value
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, CONF_DEVICES: devices}
    )
    _LOGGER.debug("Set %s.%s=%r in hub entry %s", device_id, key, value, entry.entry_id)


def get_device_info(
    hass: HomeAssistant, 
    entry: ConfigEntry, 
    device_id: str, 
    device_config: dict
) -> DeviceInfo:
    """Create DeviceInfo with MAC address connection if available.
    
    This allows HA to match the device with network integrations (like TP-Link Deco)
    that also know the device by its MAC address.
    """
    device_name = device_config.get(CONF_DEVICE_NAME, device_id)
    
    # Try to get MAC address from device status
    entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    device_data = entry_data.get("devices", {}).get(device_id, {})
    mac_address = device_data.get(ATTR_MAC_ADDRESS)
    
    # Build connections set with MAC if available
    connections = set()
    if mac_address:
        try:
            formatted_mac = format_mac(mac_address)
            connections.add((CONNECTION_NETWORK_MAC, formatted_mac))
        except Exception:
            pass  # Invalid MAC format, skip
    
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_{device_id}")},
        connections=connections if connections else None,
        name=f"PhotoDream {device_name}",
        manufacturer="PhotoDream",
        model="Android Tablet",
    )
