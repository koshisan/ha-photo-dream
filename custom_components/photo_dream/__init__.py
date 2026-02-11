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
    WEBHOOK_REGISTER,
    WEBHOOK_STATUS,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SELECT,
    Platform.BUTTON,
    Platform.SWITCH,
    Platform.NUMBER,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PhotoDream from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Store config data
    hass.data[DOMAIN][entry.entry_id] = {
        "config": dict(entry.data),
        "options": dict(entry.options),
        "devices": {},  # Runtime device status
        "pending_devices": {},  # Devices waiting for approval
    }
    
    # Register webhook for device registration (discovery)
    webhook.async_register(
        hass,
        DOMAIN,
        "PhotoDream Device Registration",
        WEBHOOK_REGISTER,
        handle_register_webhook,
    )
    _LOGGER.info("Registered discovery webhook: %s", WEBHOOK_REGISTER)
    
    # Register webhook for device status updates (per-device)
    status_webhook_id = f"{WEBHOOK_STATUS}_{entry.entry_id}"
    webhook.async_register(
        hass,
        DOMAIN,
        "PhotoDream Device Status",
        status_webhook_id,
        handle_status_webhook,
    )
    _LOGGER.info("Registered status webhook: %s", status_webhook_id)
    
    # Setup platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Register services
    await async_setup_services(hass)
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Unregister webhooks
    webhook.async_unregister(hass, WEBHOOK_REGISTER)
    webhook.async_unregister(hass, f"{WEBHOOK_STATUS}_{entry.entry_id}")
    
    # Unload platforms
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def handle_register_webhook(
    hass: HomeAssistant, webhook_id: str, request: aiohttp.web.Request
) -> aiohttp.web.Response:
    """Handle device registration webhook (discovery)."""
    try:
        # Handle POST only (HA webhooks don't support GET)
        data = await request.json()
        
        # Check if this is a poll request
        if data.get("action") == "poll":
            device_id = data.get("device_id")
            if not device_id:
                return aiohttp.web.json_response({"status": "error", "message": "Missing device_id"}, status=400)
            
            # Check if device is configured
            config = await get_device_config(hass, device_id)
            if config:
                return aiohttp.web.json_response({"status": "configured", "config": config})
            
            # Check if device is pending
            for entry_id, entry_data in hass.data.get(DOMAIN, {}).items():
                if isinstance(entry_data, dict):
                    pending = entry_data.get("pending_devices", {})
                    if device_id in pending:
                        return aiohttp.web.json_response({"status": "pending"})
            
            return aiohttp.web.json_response({"status": "unknown"})
        
        # Handle device registration
        device_id = data.get("device_id")
        device_ip = data.get("device_ip")
        device_port = data.get("device_port", DEFAULT_PORT)
        
        if not device_id or not device_ip:
            return aiohttp.web.json_response(
                {"status": "error", "message": "Missing device_id or device_ip"},
                status=400
            )
        
        _LOGGER.info("Device registration request: %s at %s:%s", device_id, device_ip, device_port)
        
        # Find the config entry and add to pending
        for entry_id, entry_data in hass.data.get(DOMAIN, {}).items():
            if isinstance(entry_data, dict) and "pending_devices" in entry_data:
                # Check if already configured
                devices = entry_data.get("config", {}).get(CONF_DEVICES, {})
                if device_id in devices:
                    # Already configured - return config
                    config = await get_device_config(hass, device_id)
                    return aiohttp.web.json_response({"status": "configured", "config": config})
                
                # Add to pending
                entry_data["pending_devices"][device_id] = {
                    "device_ip": device_ip,
                    "device_port": device_port,
                }
                
                # Fire discovery event for config flow
                hass.bus.async_fire(
                    f"{DOMAIN}_device_discovered",
                    {"device_id": device_id, "device_ip": device_ip, "device_port": device_port},
                )
                
                # Trigger discovery flow
                hass.async_create_task(
                    hass.config_entries.flow.async_init(
                        DOMAIN,
                        context={"source": "discovery"},
                        data={
                            "device_id": device_id,
                            "device_ip": device_ip,
                            "device_port": device_port,
                        },
                    )
                )
                
                return aiohttp.web.json_response({"status": "pending", "message": "Waiting for approval in Home Assistant"})
        
        return aiohttp.web.json_response(
            {"status": "error", "message": "PhotoDream integration not configured"},
            status=400
        )
        
    except Exception as e:
        _LOGGER.error("Error handling register webhook: %s", e)
        return aiohttp.web.Response(status=500, text=str(e))


async def handle_status_webhook(
    hass: HomeAssistant, webhook_id: str, request: aiohttp.web.Request
) -> aiohttp.web.Response:
    """Handle webhook from PhotoDream devices (status updates)."""
    try:
        data = await request.json()
        device_id = data.get("device_id")
        
        if not device_id:
            return aiohttp.web.Response(status=400, text="Missing device_id")
        
        _LOGGER.debug("Received status from device %s: %s", device_id, data)
        
        # Find the config entry for this webhook
        for entry_id, entry_data in hass.data.get(DOMAIN, {}).items():
            if isinstance(entry_data, dict) and "devices" in entry_data:
                # Store device status
                entry_data["devices"][device_id] = {
                    "online": data.get("online", True),
                    "active": data.get("active", False),
                    "current_image": data.get("current_image"),
                    "current_image_url": data.get("current_image_url"),
                    "profile": data.get("profile"),
                    "last_seen": data.get("last_refresh"),
                    "mac_address": data.get("mac_address"),
                    "ip_address": data.get("ip_address"),
                    "display_width": data.get("display_width"),
                    "display_height": data.get("display_height"),
                }
                
                # Fire event for entity updates
                hass.bus.async_fire(
                    f"{DOMAIN}_device_update",
                    {"device_id": device_id, "data": data},
                )
                break
        
        return aiohttp.web.json_response({"status": "ok"})
        
    except Exception as e:
        _LOGGER.error("Error handling status webhook: %s", e)
        return aiohttp.web.Response(status=500, text=str(e))


async def get_device_config(hass: HomeAssistant, device_id: str) -> dict | None:
    """Get configuration for a specific device."""
    for entry_id, entry_data in hass.data.get(DOMAIN, {}).items():
        if not isinstance(entry_data, dict) or "config" not in entry_data:
            continue
            
        config = entry_data["config"]
        options = entry_data.get("options", {})
        devices = config.get(CONF_DEVICES, {})
        
        # Merge options into config (options override config)
        profiles = {**config.get(CONF_PROFILES, {}), **options.get(CONF_PROFILES, {})}
        
        if device_id in devices:
            device = devices[device_id]
            profile_name = device.get("profile", "default")
            profile = profiles.get(profile_name, {})
            
            # Generate status webhook URL
            status_webhook_url = webhook.async_generate_url(
                hass, f"{WEBHOOK_STATUS}_{entry_id}"
            )
            
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
                    "search_filter": profile.get("search_filter", {}),
                    "exclude_paths": profile.get("exclude_paths", []),
                },
                "webhook_url": status_webhook_url,
            }
    
    return None


async def push_config_to_device(hass: HomeAssistant, device_id: str) -> bool:
    """Push configuration to a device."""
    config = await get_device_config(hass, device_id)
    if not config:
        _LOGGER.error("No config found for device %s", device_id)
        return False
    
    # Find device IP
    for entry_id, entry_data in hass.data.get(DOMAIN, {}).items():
        if not isinstance(entry_data, dict):
            continue
        
        devices = entry_data.get("config", {}).get(CONF_DEVICES, {})
        if device_id in devices:
            device = devices[device_id]
            ip = device.get(CONF_DEVICE_IP)
            port = device.get(CONF_DEVICE_PORT, DEFAULT_PORT)
            
            if not ip:
                _LOGGER.error("No IP for device %s", device_id)
                return False
            
            url = f"http://{ip}:{port}/configure"
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=config, timeout=10) as resp:
                        if resp.status == 200:
                            _LOGGER.info("Config pushed to device %s", device_id)
                            return True
                        else:
                            _LOGGER.error("Failed to push config to %s: %s", device_id, resp.status)
            except Exception as e:
                _LOGGER.error("Error pushing config to %s: %s", device_id, e)
    
    return False


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up PhotoDream services."""
    
    async def handle_next_image(call: ServiceCall) -> None:
        """Handle next_image service call."""
        device_id = call.data.get(ATTR_DEVICE_ID)
        await send_command_to_device(hass, device_id, "next")
    
    async def handle_refresh_config(call: ServiceCall) -> None:
        """Handle refresh_config service call."""
        device_id = call.data.get(ATTR_DEVICE_ID)
        await push_config_to_device(hass, device_id)
    
    async def handle_set_profile(call: ServiceCall) -> None:
        """Handle set_profile service call."""
        device_id = call.data.get(ATTR_DEVICE_ID)
        profile = call.data.get(ATTR_PROFILE)
        
        # Update device profile in config
        for entry_id, entry_data in hass.data.get(DOMAIN, {}).items():
            if not isinstance(entry_data, dict):
                continue
            devices = entry_data.get("config", {}).get(CONF_DEVICES, {})
            if device_id in devices:
                devices[device_id]["profile"] = profile
                # Push new config
                await push_config_to_device(hass, device_id)
                break
    
    hass.services.async_register(DOMAIN, SERVICE_NEXT_IMAGE, handle_next_image)
    hass.services.async_register(DOMAIN, SERVICE_REFRESH_CONFIG, handle_refresh_config)
    hass.services.async_register(DOMAIN, SERVICE_SET_PROFILE, handle_set_profile)


async def send_command_to_device(
    hass: HomeAssistant, device_id: str, command: str, data: dict | None = None
) -> bool:
    """Send a command to a PhotoDream device."""
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
                            return resp.status == 200
                    else:
                        async with session.post(url, timeout=5) as resp:
                            return resp.status == 200
            except Exception as e:
                _LOGGER.error("Failed to send command to device %s: %s", device_id, e)
                return False
    
    _LOGGER.error("Device %s not found", device_id)
    return False
