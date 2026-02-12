"""Config flow for PhotoDream integration."""
from __future__ import annotations

import logging
import json
from typing import Any
from urllib.parse import urlparse, parse_qs, unquote

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow, ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr

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
    CONF_DEVICE_NAME,
    CONF_DEVICE_IP,
    CONF_DEVICE_PORT,
    CONF_PROFILE_NAME,
    CONF_PROFILE_ID,
    CONF_SEARCH_FILTER,
    CONF_EXCLUDE_PATHS,
    CONF_CLOCK,
    CONF_CLOCK_POSITION,
    CONF_CLOCK_FORMAT,
    CONF_CLOCK_FONT_SIZE,
    CONF_DATE,
    CONF_DATE_FORMAT,
    CONF_INTERVAL,
    CONF_PAN_SPEED,
    DEFAULT_PORT,
    DEFAULT_CLOCK,
    DEFAULT_CLOCK_POSITION,
    DEFAULT_CLOCK_FORMAT,
    DEFAULT_CLOCK_FONT_SIZE,
    DEFAULT_DATE,
    DEFAULT_DATE_FORMAT,
    DEFAULT_INTERVAL,
    DEFAULT_PAN_SPEED,
    CLOCK_POSITIONS,
    DATE_FORMATS,
)

_LOGGER = logging.getLogger(__name__)


def parse_immich_search_input(input_str: str) -> dict:
    """Parse Immich search URL or JSON into a search filter dict."""
    input_str = input_str.strip()
    
    if input_str.startswith("http"):
        try:
            parsed = urlparse(input_str)
            query_params = parse_qs(parsed.query)
            if "query" in query_params:
                json_str = unquote(query_params["query"][0])
                return json.loads(json_str)
        except Exception as e:
            _LOGGER.debug("Failed to parse as URL: %s", e)
    
    if "%7B" in input_str or "%22" in input_str:
        try:
            decoded = unquote(input_str)
            return json.loads(decoded)
        except Exception as e:
            _LOGGER.debug("Failed to parse as URL-encoded JSON: %s", e)
    
    try:
        return json.loads(input_str)
    except Exception as e:
        _LOGGER.debug("Failed to parse as JSON: %s", e)
    
    return {"query": input_str}


def generate_profile_id(immich_entry_id: str, profile_name: str) -> str:
    """Generate a unique profile ID."""
    return f"{immich_entry_id}_{profile_name}".replace(" ", "_").lower()


class PhotoDreamConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PhotoDream."""

    VERSION = 2  # Bumped for new architecture

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._data: dict[str, Any] = {}
        self._discovered_device: dict[str, Any] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        # Check if hub exists
        hub_exists = any(
            entry.data.get("entry_type") == ENTRY_TYPE_HUB
            for entry in self._async_current_entries()
        )
        
        # If no hub exists, create it first then continue to Immich
        if not hub_exists:
            return await self.async_step_create_hub()
        
        # Hub exists, go directly to Immich setup
        return await self.async_step_immich()
    
    async def async_step_create_hub(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create the Hub and continue to Immich setup."""
        if user_input is not None:
            # User confirmed, create hub entry
            # We need to create hub as separate entry, then start new flow for Immich
            self._hub_created = True
            return self.async_create_entry(
                title="PhotoDream",
                data={
                    "entry_type": ENTRY_TYPE_HUB,
                    CONF_DEVICES: {},
                },
            )
        
        # Show confirmation that hub will be created
        return self.async_show_form(
            step_id="create_hub",
            data_schema=vol.Schema({}),
            description_placeholders={},
        )

    async def async_step_immich(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up an Immich server."""
        errors: dict[str, str] = {}

        if user_input is not None:
            valid = await self._test_immich_connection(
                user_input[CONF_IMMICH_URL],
                user_input[CONF_IMMICH_API_KEY],
            )
            
            if valid:
                self._data = {
                    "entry_type": ENTRY_TYPE_IMMICH,
                    CONF_IMMICH_NAME: user_input[CONF_IMMICH_NAME],
                    CONF_IMMICH_URL: user_input[CONF_IMMICH_URL].rstrip("/"),
                    CONF_IMMICH_API_KEY: user_input[CONF_IMMICH_API_KEY],
                    CONF_PROFILES: {},
                }
                return await self.async_step_profile()
            else:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="immich",
            data_schema=vol.Schema({
                vol.Required(CONF_IMMICH_NAME, default="Home Server"): str,
                vol.Required(CONF_IMMICH_URL, default="https://immich.example.com"): str,
                vol.Required(CONF_IMMICH_API_KEY): str,
            }),
            errors=errors,
        )

    async def async_step_profile(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle adding initial profile to Immich server."""
        if user_input is not None:
            profile_name = user_input[CONF_PROFILE_NAME]
            search_input = user_input.get(CONF_SEARCH_FILTER, "")
            search_filter = parse_immich_search_input(search_input) if search_input else {}
            exclude_paths = [
                p.strip() for p in user_input.get(CONF_EXCLUDE_PATHS, "").split(",") if p.strip()
            ]
            
            self._data[CONF_PROFILES][profile_name] = {
                CONF_SEARCH_FILTER: search_filter,
                CONF_EXCLUDE_PATHS: exclude_paths,
            }
            
            if user_input.get("add_another"):
                return await self.async_step_profile()
            
            # Done - create entry
            immich_name = self._data.get(CONF_IMMICH_NAME, "Immich")
            return self.async_create_entry(
                title=f"Immich: {immich_name}",
                data=self._data,
            )

        return self.async_show_form(
            step_id="profile",
            data_schema=vol.Schema({
                vol.Required(CONF_PROFILE_NAME, default="default"): str,
                vol.Optional(CONF_SEARCH_FILTER, default=""): str,
                vol.Optional(CONF_EXCLUDE_PATHS, default="/Private/*"): str,
                vol.Optional("add_another", default=False): bool,
            }),
            description_placeholders={
                "profile_count": str(len(self._data.get(CONF_PROFILES, {}))),
                "immich_name": self._data.get(CONF_IMMICH_NAME, "Immich"),
            },
        )

    async def async_step_import(
        self, import_data: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle import from migration."""
        if import_data is None:
            return self.async_abort(reason="no_data")
        
        # Create Immich entry directly from migration data
        immich_name = import_data.get(CONF_IMMICH_NAME, "Home Server")
        return self.async_create_entry(
            title=f"Immich: {immich_name}",
            data=import_data,
        )

    async def async_step_discovery(
        self, discovery_info: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle device discovery."""
        if discovery_info is None:
            return self.async_abort(reason="no_device")
        
        device_id = discovery_info.get("device_id")
        device_ip = discovery_info.get("device_ip")
        device_port = discovery_info.get("device_port", DEFAULT_PORT)
        
        if not device_id or not device_ip:
            return self.async_abort(reason="no_device")
        
        self._discovered_device = {
            "device_id": device_id,
            "device_ip": device_ip,
            "device_port": device_port,
        }
        
        await self.async_set_unique_id(f"photodream_device_{device_id}")
        self._abort_if_unique_id_configured()
        
        self.context["title_placeholders"] = {"device_id": device_id}
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm device discovery and configure."""
        if not self._discovered_device:
            return self.async_abort(reason="no_device")
        
        device_id = self._discovered_device["device_id"]
        device_ip = self._discovered_device["device_ip"]
        device_port = self._discovered_device["device_port"]
        
        # Find the hub entry
        hub_entry = None
        for entry in self._async_current_entries():
            if entry.data.get("entry_type") == ENTRY_TYPE_HUB:
                hub_entry = entry
                break
        
        if not hub_entry:
            return self.async_abort(reason="no_hub")
        
        # Collect all profiles from all Immich instances
        all_profiles = await self._get_all_profiles()
        
        if not all_profiles:
            return self.async_abort(reason="no_profiles")
        
        if user_input is not None:
            # Add device to hub
            new_data = dict(hub_entry.data)
            if CONF_DEVICES not in new_data:
                new_data[CONF_DEVICES] = {}
            
            new_data[CONF_DEVICES][device_id] = {
                CONF_DEVICE_NAME: user_input.get(CONF_DEVICE_NAME, device_id),
                CONF_DEVICE_IP: device_ip,
                CONF_DEVICE_PORT: device_port,
                CONF_PROFILE_ID: user_input.get(CONF_PROFILE_ID, list(all_profiles.keys())[0]),
                CONF_CLOCK: user_input.get(CONF_CLOCK, DEFAULT_CLOCK),
                CONF_CLOCK_POSITION: user_input.get(CONF_CLOCK_POSITION, DEFAULT_CLOCK_POSITION),
                CONF_CLOCK_FORMAT: user_input.get(CONF_CLOCK_FORMAT, DEFAULT_CLOCK_FORMAT),
                CONF_CLOCK_FONT_SIZE: user_input.get(CONF_CLOCK_FONT_SIZE, DEFAULT_CLOCK_FONT_SIZE),
                CONF_DATE: user_input.get(CONF_DATE, DEFAULT_DATE),
                CONF_DATE_FORMAT: user_input.get(CONF_DATE_FORMAT, DEFAULT_DATE_FORMAT),
                CONF_INTERVAL: user_input.get(CONF_INTERVAL, DEFAULT_INTERVAL),
                CONF_PAN_SPEED: user_input.get(CONF_PAN_SPEED, DEFAULT_PAN_SPEED),
            }
            
            # Update hub entry
            self.hass.config_entries.async_update_entry(hub_entry, data=new_data)
            
            # Push config to device
            from . import push_config_to_device
            await push_config_to_device(self.hass, device_id)
            
            # Remove from pending
            for entry_data in self.hass.data.get(DOMAIN, {}).values():
                if isinstance(entry_data, dict) and "pending_devices" in entry_data:
                    entry_data["pending_devices"].pop(device_id, None)
            
            # Reload hub to create entities
            await self.hass.config_entries.async_reload(hub_entry.entry_id)
            
            return self.async_abort(reason="device_configured")

        return self.async_show_form(
            step_id="discovery_confirm",
            data_schema=vol.Schema({
                vol.Optional(CONF_DEVICE_NAME, default=device_id): str,
                vol.Required(CONF_PROFILE_ID): vol.In(all_profiles),
                vol.Optional(CONF_CLOCK, default=DEFAULT_CLOCK): bool,
                vol.Optional(CONF_CLOCK_POSITION, default=DEFAULT_CLOCK_POSITION): vol.In(CLOCK_POSITIONS),
                vol.Optional(CONF_CLOCK_FORMAT, default=DEFAULT_CLOCK_FORMAT): vol.In(["12h", "24h"]),
                vol.Optional(CONF_CLOCK_FONT_SIZE, default=DEFAULT_CLOCK_FONT_SIZE): int,
                vol.Optional(CONF_DATE, default=DEFAULT_DATE): bool,
                vol.Optional(CONF_DATE_FORMAT, default=DEFAULT_DATE_FORMAT): vol.In(DATE_FORMATS),
                vol.Optional(CONF_INTERVAL, default=DEFAULT_INTERVAL): int,
                vol.Optional(CONF_PAN_SPEED, default=DEFAULT_PAN_SPEED): vol.Coerce(float),
            }),
            description_placeholders={
                "device_id": device_id,
                "device_ip": device_ip,
            },
        )

    async def _get_all_profiles(self) -> dict[str, str]:
        """Get all profiles from all Immich instances as {profile_id: display_name}."""
        profiles = {}
        for entry in self._async_current_entries():
            if entry.data.get("entry_type") == ENTRY_TYPE_IMMICH:
                immich_name = entry.data.get(CONF_IMMICH_NAME, "Immich")
                for profile_name in entry.data.get(CONF_PROFILES, {}).keys():
                    profile_id = generate_profile_id(entry.entry_id, profile_name)
                    profiles[profile_id] = f"{immich_name} / {profile_name}"
        return profiles

    async def _test_immich_connection(self, url: str, api_key: str) -> bool:
        """Test connection to Immich server."""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"x-api-key": api_key}
                async with session.get(
                    f"{url.rstrip('/')}/api/server/ping",
                    headers=headers,
                    timeout=10,
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("res") == "pong"
        except Exception as e:
            _LOGGER.error("Failed to connect to Immich: %s", e)
        return False

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        entry_type = config_entry.data.get("entry_type")
        if entry_type == ENTRY_TYPE_HUB:
            return HubOptionsFlow(config_entry)
        else:
            return ImmichOptionsFlow(config_entry)


class HubOptionsFlow(OptionsFlow):
    """Handle options flow for PhotoDream Hub (device management)."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry
        self._devices = dict(config_entry.data.get(CONF_DEVICES, {}))
        self._editing_device: str | None = None
    
    @property
    def _entry(self) -> ConfigEntry:
        """Get config entry."""
        try:
            return self.config_entry
        except AttributeError:
            return self._config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage Hub options - device management."""
        device_list = ", ".join(self._devices.keys()) if self._devices else "None (waiting for discovery)"
        
        if not self._devices:
            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema({}),
                description_placeholders={"devices": device_list},
            )
        
        if user_input is not None:
            action = user_input.get("action")
            if action == "edit":
                return await self.async_step_select_device_edit()
            elif action == "delete":
                return await self.async_step_select_device_delete()
        
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required("action"): vol.In({
                    "edit": "Edit device",
                    "delete": "Delete device",
                }),
            }),
            description_placeholders={"devices": device_list},
        )

    async def async_step_select_device_edit(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select device to edit."""
        if user_input is not None:
            self._editing_device = user_input["device"]
            return await self.async_step_edit_device()
        
        device_options = {
            did: self._devices[did].get(CONF_DEVICE_NAME, did)
            for did in self._devices
        }
        
        return self.async_show_form(
            step_id="select_device_edit",
            data_schema=vol.Schema({
                vol.Required("device"): vol.In(device_options),
            }),
        )

    async def async_step_edit_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit a device."""
        device_id = self._editing_device
        device = self._devices.get(device_id, {})
        
        # Get all profiles
        all_profiles = {}
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.data.get("entry_type") == ENTRY_TYPE_IMMICH:
                immich_name = entry.data.get(CONF_IMMICH_NAME, "Immich")
                for profile_name in entry.data.get(CONF_PROFILES, {}).keys():
                    profile_id = generate_profile_id(entry.entry_id, profile_name)
                    all_profiles[profile_id] = f"{immich_name} / {profile_name}"
        
        if user_input is not None:
            self._devices[device_id] = {
                **device,
                CONF_DEVICE_NAME: user_input.get(CONF_DEVICE_NAME, device_id),
                CONF_PROFILE_ID: user_input.get(CONF_PROFILE_ID),
                CONF_CLOCK: user_input.get(CONF_CLOCK, DEFAULT_CLOCK),
                CONF_CLOCK_POSITION: user_input.get(CONF_CLOCK_POSITION, DEFAULT_CLOCK_POSITION),
                CONF_CLOCK_FORMAT: user_input.get(CONF_CLOCK_FORMAT, DEFAULT_CLOCK_FORMAT),
                CONF_CLOCK_FONT_SIZE: user_input.get(CONF_CLOCK_FONT_SIZE, DEFAULT_CLOCK_FONT_SIZE),
                CONF_DATE: user_input.get(CONF_DATE, DEFAULT_DATE),
                CONF_DATE_FORMAT: user_input.get(CONF_DATE_FORMAT, DEFAULT_DATE_FORMAT),
                CONF_INTERVAL: user_input.get(CONF_INTERVAL, DEFAULT_INTERVAL),
                CONF_PAN_SPEED: user_input.get(CONF_PAN_SPEED, DEFAULT_PAN_SPEED),
            }
            
            return await self._save_and_finish()

        current_profile = device.get(CONF_PROFILE_ID, device.get("profile", ""))
        
        return self.async_show_form(
            step_id="edit_device",
            data_schema=vol.Schema({
                vol.Optional(CONF_DEVICE_NAME, default=device.get(CONF_DEVICE_NAME, device_id)): str,
                vol.Required(CONF_PROFILE_ID, default=current_profile): vol.In(all_profiles),
                vol.Optional(CONF_CLOCK, default=device.get(CONF_CLOCK, DEFAULT_CLOCK)): bool,
                vol.Optional(CONF_CLOCK_POSITION, default=device.get(CONF_CLOCK_POSITION, DEFAULT_CLOCK_POSITION)): vol.In(CLOCK_POSITIONS),
                vol.Optional(CONF_CLOCK_FORMAT, default=device.get(CONF_CLOCK_FORMAT, DEFAULT_CLOCK_FORMAT)): vol.In(["12h", "24h"]),
                vol.Optional(CONF_CLOCK_FONT_SIZE, default=device.get(CONF_CLOCK_FONT_SIZE, DEFAULT_CLOCK_FONT_SIZE)): int,
                vol.Optional(CONF_DATE, default=device.get(CONF_DATE, DEFAULT_DATE)): bool,
                vol.Optional(CONF_DATE_FORMAT, default=device.get(CONF_DATE_FORMAT, DEFAULT_DATE_FORMAT)): vol.In(DATE_FORMATS),
                vol.Optional(CONF_INTERVAL, default=device.get(CONF_INTERVAL, DEFAULT_INTERVAL)): int,
                vol.Optional(CONF_PAN_SPEED, default=device.get(CONF_PAN_SPEED, DEFAULT_PAN_SPEED)): vol.Coerce(float),
            }),
            description_placeholders={"device_id": device_id},
        )

    async def async_step_select_device_delete(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select device to delete."""
        if user_input is not None:
            del self._devices[user_input["device"]]
            return await self._save_and_finish()
        
        device_options = {
            did: self._devices[did].get(CONF_DEVICE_NAME, did)
            for did in self._devices
        }
        
        return self.async_show_form(
            step_id="select_device_delete",
            data_schema=vol.Schema({
                vol.Required("device"): vol.In(device_options),
            }),
        )

    async def _save_and_finish(self) -> ConfigFlowResult:
        """Save devices and finish."""
        new_data = dict(self._entry.data)
        new_data[CONF_DEVICES] = self._devices
        
        self.hass.config_entries.async_update_entry(
            self._entry,
            data=new_data,
        )
        
        # Push config to all devices
        from . import push_config_to_device
        for device_id in self._devices:
            await push_config_to_device(self.hass, device_id)
        
        return self.async_create_entry(title="", data={})


class ImmichOptionsFlow(OptionsFlow):
    """Handle options flow for Immich instance (profile management)."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry
        self._profiles = dict(config_entry.data.get(CONF_PROFILES, {}))
        self._editing_profile: str | None = None
    
    @property
    def _entry(self) -> ConfigEntry:
        """Get config entry."""
        try:
            return self.config_entry
        except AttributeError:
            return self._config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage Immich options - main menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["manage_profiles", "immich_settings"],
        )

    async def async_step_manage_profiles(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage profiles."""
        if user_input is not None:
            action = user_input.get("action")
            if action == "add":
                return await self.async_step_add_profile()
            elif action == "edit":
                return await self.async_step_select_profile_edit()
            elif action == "delete":
                return await self.async_step_select_profile_delete()
        
        profile_list = ", ".join(self._profiles.keys()) if self._profiles else "None"
        
        return self.async_show_form(
            step_id="manage_profiles",
            data_schema=vol.Schema({
                vol.Required("action"): vol.In({
                    "add": "Add new profile",
                    "edit": "Edit profile",
                    "delete": "Delete profile",
                }),
            }),
            description_placeholders={"profiles": profile_list},
        )

    async def async_step_add_profile(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a new profile."""
        if user_input is not None:
            profile_name = user_input[CONF_PROFILE_NAME]
            search_input = user_input.get(CONF_SEARCH_FILTER, "")
            search_filter = parse_immich_search_input(search_input) if search_input else {}
            exclude_paths = [p.strip() for p in user_input.get(CONF_EXCLUDE_PATHS, "").split(",") if p.strip()]
            
            self._profiles[profile_name] = {
                CONF_SEARCH_FILTER: search_filter,
                CONF_EXCLUDE_PATHS: exclude_paths,
            }
            
            return await self._save_and_finish()

        return self.async_show_form(
            step_id="add_profile",
            data_schema=vol.Schema({
                vol.Required(CONF_PROFILE_NAME): str,
                vol.Optional(CONF_SEARCH_FILTER, default=""): str,
                vol.Optional(CONF_EXCLUDE_PATHS, default=""): str,
            }),
        )

    async def async_step_select_profile_edit(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select profile to edit."""
        if not self._profiles:
            return await self.async_step_manage_profiles()
        
        if user_input is not None:
            self._editing_profile = user_input["profile"]
            return await self.async_step_edit_profile()
        
        return self.async_show_form(
            step_id="select_profile_edit",
            data_schema=vol.Schema({
                vol.Required("profile"): vol.In(list(self._profiles.keys())),
            }),
        )

    async def async_step_edit_profile(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit a profile."""
        profile_name = self._editing_profile
        profile = self._profiles.get(profile_name, {})
        
        if user_input is not None:
            search_input = user_input.get(CONF_SEARCH_FILTER, "")
            search_filter = parse_immich_search_input(search_input) if search_input else {}
            exclude_paths = [p.strip() for p in user_input.get(CONF_EXCLUDE_PATHS, "").split(",") if p.strip()]
            
            self._profiles[profile_name] = {
                CONF_SEARCH_FILTER: search_filter,
                CONF_EXCLUDE_PATHS: exclude_paths,
            }
            
            return await self._save_and_finish()

        existing_filter = profile.get(CONF_SEARCH_FILTER, {})
        filter_str = json.dumps(existing_filter) if existing_filter else ""
        
        return self.async_show_form(
            step_id="edit_profile",
            data_schema=vol.Schema({
                vol.Optional(CONF_SEARCH_FILTER, default=filter_str): str,
                vol.Optional(CONF_EXCLUDE_PATHS, default=", ".join(profile.get(CONF_EXCLUDE_PATHS, []))): str,
            }),
            description_placeholders={"profile_name": profile_name},
        )

    async def async_step_select_profile_delete(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select profile to delete."""
        if not self._profiles:
            return await self.async_step_manage_profiles()
        
        if user_input is not None:
            profile_name = user_input["profile"]
            
            # Remove the device from device registry
            profile_id = generate_profile_id(self._entry.entry_id, profile_name)
            device_registry = dr.async_get(self.hass)
            device = device_registry.async_get_device(
                identifiers={(DOMAIN, f"profile_{profile_id}")}
            )
            if device:
                device_registry.async_remove_device(device.id)
                _LOGGER.debug("Removed device for profile: %s", profile_name)
            
            del self._profiles[profile_name]
            return await self._save_and_finish()
        
        return self.async_show_form(
            step_id="select_profile_delete",
            data_schema=vol.Schema({
                vol.Required("profile"): vol.In(list(self._profiles.keys())),
            }),
        )

    async def async_step_immich_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit Immich settings."""
        if user_input is not None:
            new_data = dict(self._entry.data)
            new_data[CONF_IMMICH_NAME] = user_input[CONF_IMMICH_NAME]
            new_data[CONF_IMMICH_URL] = user_input[CONF_IMMICH_URL].rstrip("/")
            new_data[CONF_IMMICH_API_KEY] = user_input[CONF_IMMICH_API_KEY]
            
            self.hass.config_entries.async_update_entry(
                self._entry,
                data=new_data,
                title=f"Immich: {user_input[CONF_IMMICH_NAME]}",
            )
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="immich_settings",
            data_schema=vol.Schema({
                vol.Required(CONF_IMMICH_NAME, default=self._entry.data.get(CONF_IMMICH_NAME, "")): str,
                vol.Required(CONF_IMMICH_URL, default=self._entry.data.get(CONF_IMMICH_URL, "")): str,
                vol.Required(CONF_IMMICH_API_KEY, default=self._entry.data.get(CONF_IMMICH_API_KEY, "")): str,
            }),
        )

    async def _save_and_finish(self) -> ConfigFlowResult:
        """Save profiles and finish."""
        new_data = dict(self._entry.data)
        new_data[CONF_PROFILES] = self._profiles
        
        self.hass.config_entries.async_update_entry(
            self._entry,
            data=new_data,
        )
        
        # Reload to update profile devices
        await self.hass.config_entries.async_reload(self._entry.entry_id)
        
        return self.async_create_entry(title="", data={})
