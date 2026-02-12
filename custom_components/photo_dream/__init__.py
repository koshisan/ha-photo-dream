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
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, format_mac

from .const import (
    DOMAIN,
    ENTRY_TYPE_HUB,
    ENTRY_TYPE_IMMICH,
    CONF_IMMICH_URL,
    CONF_IMMICH_API_KEY,
    CONF_IMMICH_NAME,
    CONF_DEVICES,
    CONF_PROFILES,
    CONF_DEVICE_ID,
    CONF_DEVICE_IP,
    CONF_DEVICE_PORT,
    CONF_PROFILE_ID,
    CONF_SEARCH_FILTER,
    CONF_EXCLUDE_PATHS,
    CONF_WEATHER_ENTITY,
    DEFAULT_PORT,
    SERVICE_NEXT_IMAGE,
    SERVICE_REFRESH_CONFIG,
    SERVICE_SET_PROFILE,
    ATTR_DEVICE_ID,
    ATTR_PROFILE_ID,
    WEBHOOK_REGISTER,
    WEBHOOK_STATUS,
)

_LOGGER = logging.getLogger(__name__)

# Platforms for Hub entries (tablets)
HUB_PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SELECT,
    Platform.BUTTON,
    Platform.SWITCH,
    Platform.NUMBER,
]

# Platforms for Immich entries (profiles)
IMMICH_PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BUTTON,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PhotoDream from a config entry."""
    hass.data.setdefault(DOMAIN, {"hub": None, "immich": {}})
    
    entry_type = entry.data.get("entry_type", ENTRY_TYPE_HUB)
    
    if entry_type == ENTRY_TYPE_HUB:
        return await async_setup_hub_entry(hass, entry)
    else:
        return await async_setup_immich_entry(hass, entry)


async def async_setup_hub_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PhotoDream Hub (tablets)."""
    hass.data[DOMAIN]["hub"] = {
        "entry": entry,
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
    
    # Register webhook for device status updates
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
    await hass.config_entries.async_forward_entry_setups(entry, HUB_PLATFORMS)
    
    # Register services
    await async_setup_services(hass)
    
    return True


async def async_setup_immich_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up an Immich instance (profile source)."""
    from .coordinator import async_get_coordinator
    
    # Create coordinator for polling image counts
    coordinator = await async_get_coordinator(hass, entry)
    
    hass.data[DOMAIN]["immich"][entry.entry_id] = {
        "entry": entry,
        "coordinator": coordinator,
    }
    
    # Create profile devices in registry
    await create_profile_devices(hass, entry)
    
    # Setup platforms
    await hass.config_entries.async_forward_entry_setups(entry, IMMICH_PLATFORMS)
    
    return True


async def create_profile_devices(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Create device registry entries for each profile."""
    device_registry = dr.async_get(hass)
    immich_name = entry.data.get(CONF_IMMICH_NAME, "Immich")
    profiles = entry.data.get(CONF_PROFILES, {})
    
    for profile_name in profiles:
        profile_id = f"{entry.entry_id}_{profile_name}".replace(" ", "_").lower()
        
        # Create profile as a device directly under this config entry
        # (no via_device needed - HA handles the hierarchy automatically)
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"profile_{profile_id}")},
            name=profile_name,
            manufacturer="PhotoDream",
            model="Immich Profile",
            sw_version="1.0",
        )
        _LOGGER.info("Created profile device: %s", profile_name)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    entry_type = entry.data.get("entry_type", ENTRY_TYPE_HUB)
    
    if entry_type == ENTRY_TYPE_HUB:
        return await async_unload_hub_entry(hass, entry)
    else:
        return await async_unload_immich_entry(hass, entry)


async def async_unload_hub_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Hub entry."""
    # Unregister webhooks
    webhook.async_unregister(hass, WEBHOOK_REGISTER)
    webhook.async_unregister(hass, f"{WEBHOOK_STATUS}_{entry.entry_id}")
    
    # Unload platforms
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, HUB_PLATFORMS):
        hass.data[DOMAIN]["hub"] = None

    return unload_ok


async def async_unload_immich_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Immich entry."""
    if IMMICH_PLATFORMS:
        if not await hass.config_entries.async_unload_platforms(entry, IMMICH_PLATFORMS):
            return False
    
    hass.data[DOMAIN]["immich"].pop(entry.entry_id, None)
    return True


async def handle_register_webhook(
    hass: HomeAssistant, webhook_id: str, request: aiohttp.web.Request
) -> aiohttp.web.Response:
    """Handle device registration webhook (discovery)."""
    try:
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
            hub_data = hass.data.get(DOMAIN, {}).get("hub")
            if hub_data:
                pending = hub_data.get("pending_devices", {})
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
        
        hub_data = hass.data.get(DOMAIN, {}).get("hub")
        if not hub_data:
            return aiohttp.web.json_response(
                {"status": "error", "message": "PhotoDream Hub not configured"},
                status=400
            )
        
        # Check if already configured
        devices = hub_data.get("entry").data.get(CONF_DEVICES, {})
        if device_id in devices:
            config = await get_device_config(hass, device_id)
            return aiohttp.web.json_response({"status": "configured", "config": config})
        
        # Add to pending
        hub_data["pending_devices"][device_id] = {
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
        
        hub_data = hass.data.get(DOMAIN, {}).get("hub")
        if hub_data:
            hub_data["devices"][device_id] = {
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
                "app_version": data.get("app_version"),
            }
            
            # Update device registry with MAC address
            mac_address = data.get("mac_address")
            if mac_address:
                await _update_device_mac(hass, hub_data["entry"].entry_id, device_id, mac_address)
            
            # Fire event for entity updates
            hass.bus.async_fire(
                f"{DOMAIN}_device_update",
                {"device_id": device_id, "data": data},
            )
        
        return aiohttp.web.json_response({"status": "ok"})
        
    except Exception as e:
        _LOGGER.error("Error handling status webhook: %s", e)
        return aiohttp.web.Response(status=500, text=str(e))


async def _update_device_mac(
    hass: HomeAssistant, entry_id: str, device_id: str, mac_address: str
) -> None:
    """Update device registry with MAC address."""
    try:
        formatted_mac = format_mac(mac_address)
        device_registry = dr.async_get(hass)
        
        device = device_registry.async_get_device(
            identifiers={(DOMAIN, f"{entry_id}_{device_id}")}
        )
        
        if device:
            mac_connection = (CONNECTION_NETWORK_MAC, formatted_mac)
            if mac_connection not in device.connections:
                new_connections = set(device.connections)
                new_connections.add(mac_connection)
                device_registry.async_update_device(
                    device.id,
                    new_connections=new_connections,
                )
                _LOGGER.debug("Updated device %s with MAC %s", device_id, formatted_mac)
    except Exception as e:
        _LOGGER.debug("Could not update device MAC: %s", e)


def resolve_profile(hass: HomeAssistant, profile_id: str) -> tuple[ConfigEntry | None, str | None, dict]:
    """Resolve a profile_id to its Immich entry and profile config.
    
    Supports both new format (entryid_profilename) and old format (just profilename).
    Returns (immich_entry, profile_name, profile_config) or (None, None, {}) if not found.
    """
    if not profile_id:
        profile_id = ""
    
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data.get("entry_type") != ENTRY_TYPE_IMMICH:
            continue
        
        profiles = entry.data.get(CONF_PROFILES, {})
        
        for profile_name, profile_config in profiles.items():
            # Try new format: {entry_id}_{profile_name}
            expected_id = f"{entry.entry_id}_{profile_name}".replace(" ", "_").lower()
            if expected_id == profile_id or expected_id == profile_id.lower():
                return entry, profile_name, profile_config
            
            # Try old format: just the profile name
            if profile_name == profile_id or profile_name.lower() == profile_id.lower():
                _LOGGER.info("Resolved old-format profile '%s' to Immich entry %s", profile_id, entry.entry_id)
                return entry, profile_name, profile_config
    
    # If no match and we have any Immich entry, return the first profile as fallback
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data.get("entry_type") != ENTRY_TYPE_IMMICH:
            continue
        profiles = entry.data.get(CONF_PROFILES, {})
        if profiles:
            first_name = list(profiles.keys())[0]
            _LOGGER.warning("Could not resolve profile '%s', falling back to '%s'", profile_id, first_name)
            return entry, first_name, profiles[first_name]
    
    return None, None, {}


async def get_device_config(hass: HomeAssistant, device_id: str) -> dict | None:
    """Get configuration for a specific device."""
    hub_data = hass.data.get(DOMAIN, {}).get("hub")
    if not hub_data:
        return None
    
    entry = hub_data.get("entry")
    if not entry:
        return None
    
    devices = entry.data.get(CONF_DEVICES, {})
    if device_id not in devices:
        return None
    
    device = devices[device_id]
    profile_id = device.get(CONF_PROFILE_ID, device.get("profile", ""))
    
    # Resolve profile to Immich instance
    immich_entry, profile_name, profile_config = resolve_profile(hass, profile_id)
    
    if not immich_entry:
        _LOGGER.error("Could not resolve profile %s for device %s", profile_id, device_id)
        return None
    
    # Generate status webhook URL
    status_webhook_url = webhook.async_generate_url(
        hass, f"{WEBHOOK_STATUS}_{entry.entry_id}"
    )
    
    # Get weather data if configured
    weather_config = None
    weather_entity_id = device.get(CONF_WEATHER_ENTITY)
    if weather_entity_id:
        weather_state = hass.states.get(weather_entity_id)
        if weather_state:
            # Get temperature unit from HA config
            temp_unit = hass.config.units.temperature_unit
            weather_config = {
                "enabled": True,
                "entity_id": weather_entity_id,
                "condition": weather_state.state,
                "temperature": weather_state.attributes.get("temperature"),
                "temperature_unit": temp_unit,
            }
            _LOGGER.debug("Weather for %s: %s", device_id, weather_config)
    
    return {
        "device_id": device_id,
        "immich": {
            "base_url": immich_entry.data.get(CONF_IMMICH_URL, ""),
            "api_key": immich_entry.data.get(CONF_IMMICH_API_KEY, ""),
        },
        "display": {
            "clock": device.get("clock", True),
            "clock_position": device.get("clock_position", 3),
            "clock_format": device.get("clock_format", "24h"),
            "clock_font_size": device.get("clock_font_size", 32),
            "date": device.get("date", False),
            "date_format": device.get("date_format", "dd.MM.yyyy"),
            "weather": weather_config,
            "interval_seconds": device.get("interval_seconds", 30),
            "pan_speed": device.get("pan_speed", 0.5),
            "mode": device.get("display_mode", "smart_shuffle"),
        },
        "profile": {
            "name": profile_name,
            "search_filter": profile_config.get(CONF_SEARCH_FILTER, {}),
            "exclude_paths": profile_config.get(CONF_EXCLUDE_PATHS, []),
        },
        "webhook_url": status_webhook_url,
    }


async def push_config_to_device(hass: HomeAssistant, device_id: str) -> bool:
    """Push configuration to a device."""
    config = await get_device_config(hass, device_id)
    if not config:
        _LOGGER.error("No config found for device %s", device_id)
        return False
    
    hub_data = hass.data.get(DOMAIN, {}).get("hub")
    if not hub_data:
        return False
    
    devices = hub_data.get("entry").data.get(CONF_DEVICES, {})
    if device_id not in devices:
        return False
    
    device = devices[device_id]
    ip = device.get(CONF_DEVICE_IP)
    port = device.get(CONF_DEVICE_PORT, DEFAULT_PORT)
    
    if not ip:
        _LOGGER.error("No IP for device %s", device_id)
        return False
    
    url = f"http://{ip}:{port}/configure"
    _LOGGER.info("Pushing config to device %s at %s", device_id, url)
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=config, timeout=10) as resp:
                if resp.status == 200:
                    _LOGGER.info("Config pushed to device %s", device_id)
                    return True
                else:
                    _LOGGER.error("Failed to push config to %s: HTTP %s", device_id, resp.status)
    except aiohttp.ClientConnectorError as e:
        _LOGGER.error("Cannot connect to device %s at %s: %s", device_id, url, e)
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
        profile_id = call.data.get(ATTR_PROFILE_ID)
        
        hub_data = hass.data.get(DOMAIN, {}).get("hub")
        if not hub_data:
            return
        
        entry = hub_data.get("entry")
        if not entry:
            return
        
        devices = dict(entry.data.get(CONF_DEVICES, {}))
        if device_id in devices:
            devices[device_id] = {**devices[device_id], CONF_PROFILE_ID: profile_id}
            new_data = dict(entry.data)
            new_data[CONF_DEVICES] = devices
            hass.config_entries.async_update_entry(entry, data=new_data)
            await push_config_to_device(hass, device_id)
    
    hass.services.async_register(DOMAIN, SERVICE_NEXT_IMAGE, handle_next_image)
    hass.services.async_register(DOMAIN, SERVICE_REFRESH_CONFIG, handle_refresh_config)
    hass.services.async_register(DOMAIN, SERVICE_SET_PROFILE, handle_set_profile)


async def send_command_to_device(
    hass: HomeAssistant, device_id: str, command: str, data: dict | None = None
) -> bool:
    """Send a command to a PhotoDream device."""
    hub_data = hass.data.get(DOMAIN, {}).get("hub")
    if not hub_data:
        _LOGGER.error("No hub configured")
        return False
    
    devices = hub_data.get("entry").data.get(CONF_DEVICES, {})
    if device_id not in devices:
        _LOGGER.error("Device %s not found", device_id)
        return False
    
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


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry to new format."""
    if config_entry.version == 1:
        _LOGGER.info("Migrating PhotoDream config entry from version 1 to 2")
        
        # Version 1 had everything in one entry
        # We need to split it into Hub + Immich entries
        old_data = dict(config_entry.data)
        
        # This entry becomes the Hub
        new_hub_data = {
            "entry_type": ENTRY_TYPE_HUB,
            CONF_DEVICES: old_data.get(CONF_DEVICES, {}),
        }
        
        # Update this entry to be the Hub
        hass.config_entries.async_update_entry(
            config_entry,
            data=new_hub_data,
            title="PhotoDream",
            version=2,
        )
        
        # Create a new Immich entry with the old Immich settings
        if old_data.get(CONF_IMMICH_URL):
            immich_data = {
                "entry_type": ENTRY_TYPE_IMMICH,
                CONF_IMMICH_NAME: "Home Server",
                CONF_IMMICH_URL: old_data.get(CONF_IMMICH_URL, ""),
                CONF_IMMICH_API_KEY: old_data.get(CONF_IMMICH_API_KEY, ""),
                CONF_PROFILES: old_data.get(CONF_PROFILES, {}),
            }
            
            # Create the new Immich entry
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": "import"},
                    data=immich_data,
                )
            )
        
        _LOGGER.info("Migration complete: Hub entry updated, Immich entry will be created")
        return True
    
    return True
