"""PhotoDream integration for Home Assistant."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.components import webhook
from homeassistant.helpers import device_registry as dr

from .const import (
    DOMAIN,
    CONF_IMMICH_URL,
    CONF_IMMICH_API_KEY,
    CONF_DEVICES,
    CONF_PROFILES,
    CONF_DEVICE_ID,
    CONF_DEVICE_IP,
    CONF_DEVICE_PORT,
    DEFAULT_PORT,
    SERVICE_NEXT_IMAGE,
    SERVICE_REFRESH_CONFIG,
    SERVICE_SET_PROFILE,
    ATTR_DEVICE_ID,
    ATTR_PROFILE,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.SELECT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PhotoDream from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Store config data
    hass.data[DOMAIN][entry.entry_id] = {
        "config": entry.data,
        "devices": {},  # Will store device status
    }
    
    # Register webhook for device status updates
    webhook_id = entry.data.get("webhook_id", entry.entry_id)
    webhook.async_register(
        hass,
        DOMAIN,
        "PhotoDream Device Status",
        webhook_id,
        handle_webhook,
    )
    _LOGGER.info("Registered webhook with ID: %s", webhook_id)
    
    # Setup platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Register services
    await async_setup_services(hass)
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Unregister webhook
    webhook_id = entry.data.get("webhook_id", entry.entry_id)
    webhook.async_unregister(hass, webhook_id)
    
    # Unload platforms
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def handle_webhook(
    hass: HomeAssistant, webhook_id: str, request: aiohttp.web.Request
) -> aiohttp.web.Response:
    """Handle webhook from PhotoDream devices."""
    try:
        data = await request.json()
        device_id = data.get("device_id")
        
        if not device_id:
            return aiohttp.web.Response(status=400, text="Missing device_id")
        
        _LOGGER.debug("Received webhook from device %s: %s", device_id, data)
        
        # Find the config entry for this webhook
        for entry_id, entry_data in hass.data.get(DOMAIN, {}).items():
            if isinstance(entry_data, dict) and "devices" in entry_data:
                # Store device status
                entry_data["devices"][device_id] = {
                    "online": data.get("online", True),
                    "current_image": data.get("current_image"),
                    "current_image_url": data.get("current_image_url"),
                    "profile": data.get("profile"),
                    "last_seen": data.get("last_refresh"),
                }
                
                # Fire event for entity updates
                hass.bus.async_fire(
                    f"{DOMAIN}_device_update",
                    {"device_id": device_id, "data": data},
                )
                break
        
        # Return config for the device
        config = await get_device_config(hass, device_id)
        if config:
            return aiohttp.web.json_response(config)
        
        return aiohttp.web.json_response({"status": "ok"})
        
    except Exception as e:
        _LOGGER.error("Error handling webhook: %s", e)
        return aiohttp.web.Response(status=500, text=str(e))


async def get_device_config(hass: HomeAssistant, device_id: str) -> dict | None:
    """Get configuration for a specific device."""
    for entry_id, entry_data in hass.data.get(DOMAIN, {}).items():
        if not isinstance(entry_data, dict) or "config" not in entry_data:
            continue
            
        config = entry_data["config"]
        devices = config.get(CONF_DEVICES, {})
        
        if device_id in devices:
            device = devices[device_id]
            profiles = config.get(CONF_PROFILES, {})
            profile_name = device.get("profile", "default")
            profile = profiles.get(profile_name, {})
            
            return {
                "device_id": device_id,
                "immich": {
                    "base_url": config.get(CONF_IMMICH_URL, ""),
                    "api_key": config.get(CONF_IMMICH_API_KEY, ""),
                },
                "display": {
                    "clock": device.get("clock", True),
                    "clock_position": device.get("clock_position", 3),
                    "clock_format": device.get("clock_format", "24h"),
                    "weather": device.get("weather", False),
                    "interval_seconds": device.get("interval_seconds", 30),
                    "pan_speed": device.get("pan_speed", 0.5),
                    "mode": device.get("display_mode", "smart_shuffle"),
                },
                "profile": {
                    "name": profile_name,
                    "search_queries": profile.get("search_queries", []),
                    "exclude_paths": profile.get("exclude_paths", []),
                },
                "webhook_url": webhook.async_generate_url(
                    hass, config.get("webhook_id", entry_id)
                ),
            }
    
    return None


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up PhotoDream services."""
    
    async def handle_next_image(call: ServiceCall) -> None:
        """Handle next_image service call."""
        device_id = call.data.get(ATTR_DEVICE_ID)
        await send_command_to_device(hass, device_id, "next")
    
    async def handle_refresh_config(call: ServiceCall) -> None:
        """Handle refresh_config service call."""
        device_id = call.data.get(ATTR_DEVICE_ID)
        await send_command_to_device(hass, device_id, "refresh-config")
    
    async def handle_set_profile(call: ServiceCall) -> None:
        """Handle set_profile service call."""
        device_id = call.data.get(ATTR_DEVICE_ID)
        profile = call.data.get(ATTR_PROFILE)
        await send_command_to_device(hass, device_id, "set-profile", {"profile": profile})
    
    hass.services.async_register(DOMAIN, SERVICE_NEXT_IMAGE, handle_next_image)
    hass.services.async_register(DOMAIN, SERVICE_REFRESH_CONFIG, handle_refresh_config)
    hass.services.async_register(DOMAIN, SERVICE_SET_PROFILE, handle_set_profile)


async def send_command_to_device(
    hass: HomeAssistant, device_id: str, command: str, data: dict | None = None
) -> bool:
    """Send a command to a PhotoDream device."""
    # Find device IP and port
    for entry_id, entry_data in hass.data.get(DOMAIN, {}).items():
        if not isinstance(entry_data, dict) or "config" not in entry_data:
            continue
            
        config = entry_data["config"]
        devices = config.get(CONF_DEVICES, {})
        
        if device_id in devices:
            device = devices[device_id]
            ip = device.get(CONF_DEVICE_IP)
            port = device.get(CONF_DEVICE_PORT, DEFAULT_PORT)
            
            if not ip:
                _LOGGER.error("No IP configured for device %s", device_id)
                return False
            
            url = f"http://{ip}:{port}/{command}"
            
            try:
                async with aiohttp.ClientSession() as session:
                    if data:
                        async with session.post(url, json=data, timeout=5) as resp:
                            _LOGGER.debug("Command %s sent to %s: %s", command, device_id, resp.status)
                            return resp.status == 200
                    else:
                        async with session.post(url, timeout=5) as resp:
                            _LOGGER.debug("Command %s sent to %s: %s", command, device_id, resp.status)
                            return resp.status == 200
            except Exception as e:
                _LOGGER.error("Failed to send command to device %s: %s", device_id, e)
                return False
    
    _LOGGER.error("Device %s not found", device_id)
    return False
