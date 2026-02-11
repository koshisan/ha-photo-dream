"""Helper functions for PhotoDream integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, format_mac
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, CONF_DEVICE_NAME, ATTR_MAC_ADDRESS


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
