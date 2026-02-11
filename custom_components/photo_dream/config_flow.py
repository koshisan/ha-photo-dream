"""Config flow for PhotoDream integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow, ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .const import (
    DOMAIN,
    CONF_IMMICH_URL,
    CONF_IMMICH_API_KEY,
    CONF_DEVICES,
    CONF_PROFILES,
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_DEVICE_IP,
    CONF_DEVICE_PORT,
    CONF_PROFILE_NAME,
    CONF_SEARCH_QUERIES,
    CONF_EXCLUDE_PATHS,
    CONF_CLOCK,
    CONF_CLOCK_POSITION,
    CONF_CLOCK_FORMAT,
    CONF_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_CLOCK,
    DEFAULT_CLOCK_POSITION,
    DEFAULT_CLOCK_FORMAT,
    DEFAULT_INTERVAL,
    CLOCK_POSITIONS,
)

_LOGGER = logging.getLogger(__name__)


class PhotoDreamConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PhotoDream."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._data: dict[str, Any] = {}
        self._discovered_device: dict[str, Any] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step - Immich configuration."""
        # Check if already configured
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate Immich connection
            valid = await self._test_immich_connection(
                user_input[CONF_IMMICH_URL],
                user_input[CONF_IMMICH_API_KEY],
            )
            
            if valid:
                self._data = {
                    CONF_IMMICH_URL: user_input[CONF_IMMICH_URL].rstrip("/"),
                    CONF_IMMICH_API_KEY: user_input[CONF_IMMICH_API_KEY],
                    CONF_PROFILES: {},
                    CONF_DEVICES: {},
                }
                return await self.async_step_profile()
            else:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_IMMICH_URL, default="https://immich.example.com"): str,
                    vol.Required(CONF_IMMICH_API_KEY): str,
                }
            ),
            errors=errors,
        )

    async def async_step_profile(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle adding initial profile."""
        if user_input is not None:
            profile_name = user_input[CONF_PROFILE_NAME]
            search_queries = [
                q.strip() for q in user_input[CONF_SEARCH_QUERIES].split(",") if q.strip()
            ]
            exclude_paths = [
                p.strip() for p in user_input.get(CONF_EXCLUDE_PATHS, "").split(",") if p.strip()
            ]
            
            self._data[CONF_PROFILES][profile_name] = {
                CONF_SEARCH_QUERIES: search_queries,
                CONF_EXCLUDE_PATHS: exclude_paths,
            }
            
            if user_input.get("add_another"):
                return await self.async_step_profile()
            
            # Done - create entry (devices will be added via discovery)
            return self.async_create_entry(
                title="PhotoDream",
                data=self._data,
            )

        return self.async_show_form(
            step_id="profile",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PROFILE_NAME, default="default"): str,
                    vol.Required(CONF_SEARCH_QUERIES, default="family, vacation"): str,
                    vol.Optional(CONF_EXCLUDE_PATHS, default="/Private/*"): str,
                    vol.Optional("add_another", default=False): bool,
                }
            ),
            description_placeholders={
                "profile_count": str(len(self._data.get(CONF_PROFILES, {}))),
            },
        )

    async def async_step_discovery(
        self, discovery_info: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle device discovery."""
        device_id = discovery_info["device_id"]
        device_ip = discovery_info["device_ip"]
        device_port = discovery_info.get("device_port", DEFAULT_PORT)
        
        # Store discovered device info
        self._discovered_device = {
            "device_id": device_id,
            "device_ip": device_ip,
            "device_port": device_port,
        }
        
        # Set unique ID to prevent duplicate flows
        await self.async_set_unique_id(f"photodream_{device_id}")
        self._abort_if_unique_id_configured()
        
        # Show confirmation
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
        
        # Get existing config entry
        entries = self._async_current_entries()
        if not entries:
            return self.async_abort(reason="no_config")
        
        entry = entries[0]
        profiles = list(entry.data.get(CONF_PROFILES, {}).keys())
        
        if not profiles:
            profiles = ["default"]
        
        if user_input is not None:
            # Add device to config
            new_data = dict(entry.data)
            if CONF_DEVICES not in new_data:
                new_data[CONF_DEVICES] = {}
            
            new_data[CONF_DEVICES][device_id] = {
                CONF_DEVICE_NAME: user_input.get(CONF_DEVICE_NAME, device_id),
                CONF_DEVICE_IP: device_ip,
                CONF_DEVICE_PORT: device_port,
                "profile": user_input.get("profile", profiles[0]),
                CONF_CLOCK: user_input.get(CONF_CLOCK, DEFAULT_CLOCK),
                CONF_CLOCK_POSITION: user_input.get(CONF_CLOCK_POSITION, DEFAULT_CLOCK_POSITION),
                CONF_CLOCK_FORMAT: user_input.get(CONF_CLOCK_FORMAT, DEFAULT_CLOCK_FORMAT),
                CONF_INTERVAL: user_input.get(CONF_INTERVAL, DEFAULT_INTERVAL),
            }
            
            # Update config entry
            self.hass.config_entries.async_update_entry(entry, data=new_data)
            
            # Push config to device
            from . import push_config_to_device
            await push_config_to_device(self.hass, device_id)
            
            # Remove from pending
            for entry_data in self.hass.data.get(DOMAIN, {}).values():
                if isinstance(entry_data, dict) and "pending_devices" in entry_data:
                    entry_data["pending_devices"].pop(device_id, None)
            
            # Reload integration to create entities for new device
            await self.hass.config_entries.async_reload(entry.entry_id)
            
            return self.async_abort(reason="device_configured")

        return self.async_show_form(
            step_id="discovery_confirm",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_DEVICE_NAME, default=device_id): str,
                    vol.Required("profile", default=profiles[0]): vol.In(profiles),
                    vol.Optional(CONF_CLOCK, default=DEFAULT_CLOCK): bool,
                    vol.Optional(CONF_CLOCK_POSITION, default=DEFAULT_CLOCK_POSITION): vol.In(CLOCK_POSITIONS),
                    vol.Optional(CONF_CLOCK_FORMAT, default=DEFAULT_CLOCK_FORMAT): vol.In(["12h", "24h"]),
                    vol.Optional(CONF_INTERVAL, default=DEFAULT_INTERVAL): int,
                }
            ),
            description_placeholders={
                "device_id": device_id,
                "device_ip": device_ip,
            },
        )

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
    def async_get_options_flow(config_entry: ConfigEntry) -> PhotoDreamOptionsFlow:
        """Get the options flow for this handler."""
        return PhotoDreamOptionsFlow(config_entry)


class PhotoDreamOptionsFlow(OptionsFlow):
    """Handle options flow for PhotoDream - Profile and Device management."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self._profiles = dict(config_entry.data.get(CONF_PROFILES, {}))
        self._devices = dict(config_entry.data.get(CONF_DEVICES, {}))

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage options - main menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["manage_profiles", "manage_devices", "immich_settings"],
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
            data_schema=vol.Schema(
                {
                    vol.Required("action"): vol.In({
                        "add": "Add new profile",
                        "edit": "Edit profile",
                        "delete": "Delete profile",
                    }),
                }
            ),
            description_placeholders={"profiles": profile_list},
        )

    async def async_step_add_profile(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a new profile."""
        if user_input is not None:
            profile_name = user_input[CONF_PROFILE_NAME]
            search_queries = [q.strip() for q in user_input[CONF_SEARCH_QUERIES].split(",") if q.strip()]
            exclude_paths = [p.strip() for p in user_input.get(CONF_EXCLUDE_PATHS, "").split(",") if p.strip()]
            
            self._profiles[profile_name] = {
                CONF_SEARCH_QUERIES: search_queries,
                CONF_EXCLUDE_PATHS: exclude_paths,
            }
            
            return await self._save_and_finish()

        return self.async_show_form(
            step_id="add_profile",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PROFILE_NAME): str,
                    vol.Required(CONF_SEARCH_QUERIES): str,
                    vol.Optional(CONF_EXCLUDE_PATHS, default=""): str,
                }
            ),
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
            data_schema=vol.Schema(
                {
                    vol.Required("profile"): vol.In(list(self._profiles.keys())),
                }
            ),
        )

    async def async_step_edit_profile(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit a profile."""
        profile_name = self._editing_profile
        profile = self._profiles.get(profile_name, {})
        
        if user_input is not None:
            search_queries = [q.strip() for q in user_input[CONF_SEARCH_QUERIES].split(",") if q.strip()]
            exclude_paths = [p.strip() for p in user_input.get(CONF_EXCLUDE_PATHS, "").split(",") if p.strip()]
            
            self._profiles[profile_name] = {
                CONF_SEARCH_QUERIES: search_queries,
                CONF_EXCLUDE_PATHS: exclude_paths,
            }
            
            return await self._save_and_finish()

        return self.async_show_form(
            step_id="edit_profile",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SEARCH_QUERIES,
                        default=", ".join(profile.get(CONF_SEARCH_QUERIES, []))
                    ): str,
                    vol.Optional(
                        CONF_EXCLUDE_PATHS,
                        default=", ".join(profile.get(CONF_EXCLUDE_PATHS, []))
                    ): str,
                }
            ),
            description_placeholders={"profile_name": profile_name},
        )

    async def async_step_select_profile_delete(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select profile to delete."""
        if not self._profiles:
            return await self.async_step_manage_profiles()
        
        if user_input is not None:
            del self._profiles[user_input["profile"]]
            return await self._save_and_finish()
        
        return self.async_show_form(
            step_id="select_profile_delete",
            data_schema=vol.Schema(
                {
                    vol.Required("profile"): vol.In(list(self._profiles.keys())),
                }
            ),
        )

    async def async_step_manage_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage devices."""
        device_list = ", ".join(self._devices.keys()) if self._devices else "None (waiting for discovery)"
        
        if not self._devices:
            return self.async_show_form(
                step_id="manage_devices",
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
            step_id="manage_devices",
            data_schema=vol.Schema(
                {
                    vol.Required("action"): vol.In({
                        "edit": "Edit device",
                        "delete": "Delete device",
                    }),
                }
            ),
            description_placeholders={"devices": device_list},
        )

    async def async_step_select_device_edit(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select device to edit."""
        if user_input is not None:
            self._editing_device = user_input["device"]
            return await self.async_step_edit_device()
        
        return self.async_show_form(
            step_id="select_device_edit",
            data_schema=vol.Schema(
                {
                    vol.Required("device"): vol.In(list(self._devices.keys())),
                }
            ),
        )

    async def async_step_edit_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit a device."""
        device_id = self._editing_device
        device = self._devices.get(device_id, {})
        profiles = list(self._profiles.keys()) or ["default"]
        
        if user_input is not None:
            self._devices[device_id] = {
                **device,
                CONF_DEVICE_NAME: user_input.get(CONF_DEVICE_NAME, device_id),
                "profile": user_input.get("profile", profiles[0]),
                CONF_CLOCK: user_input.get(CONF_CLOCK, DEFAULT_CLOCK),
                CONF_CLOCK_POSITION: user_input.get(CONF_CLOCK_POSITION, DEFAULT_CLOCK_POSITION),
                CONF_CLOCK_FORMAT: user_input.get(CONF_CLOCK_FORMAT, DEFAULT_CLOCK_FORMAT),
                CONF_INTERVAL: user_input.get(CONF_INTERVAL, DEFAULT_INTERVAL),
            }
            
            return await self._save_and_finish()

        return self.async_show_form(
            step_id="edit_device",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_DEVICE_NAME, default=device.get(CONF_DEVICE_NAME, device_id)): str,
                    vol.Required("profile", default=device.get("profile", profiles[0])): vol.In(profiles),
                    vol.Optional(CONF_CLOCK, default=device.get(CONF_CLOCK, DEFAULT_CLOCK)): bool,
                    vol.Optional(CONF_CLOCK_POSITION, default=device.get(CONF_CLOCK_POSITION, DEFAULT_CLOCK_POSITION)): vol.In(CLOCK_POSITIONS),
                    vol.Optional(CONF_CLOCK_FORMAT, default=device.get(CONF_CLOCK_FORMAT, DEFAULT_CLOCK_FORMAT)): vol.In(["12h", "24h"]),
                    vol.Optional(CONF_INTERVAL, default=device.get(CONF_INTERVAL, DEFAULT_INTERVAL)): int,
                }
            ),
            description_placeholders={"device_id": device_id},
        )

    async def async_step_select_device_delete(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select device to delete."""
        if user_input is not None:
            del self._devices[user_input["device"]]
            return await self._save_and_finish()
        
        return self.async_show_form(
            step_id="select_device_delete",
            data_schema=vol.Schema(
                {
                    vol.Required("device"): vol.In(list(self._devices.keys())),
                }
            ),
        )

    async def async_step_immich_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit Immich settings."""
        if user_input is not None:
            # Update immich settings in data
            new_data = dict(self.config_entry.data)
            new_data[CONF_IMMICH_URL] = user_input[CONF_IMMICH_URL].rstrip("/")
            new_data[CONF_IMMICH_API_KEY] = user_input[CONF_IMMICH_API_KEY]
            
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=new_data,
            )
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="immich_settings",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_IMMICH_URL,
                        default=self.config_entry.data.get(CONF_IMMICH_URL, "")
                    ): str,
                    vol.Required(
                        CONF_IMMICH_API_KEY,
                        default=self.config_entry.data.get(CONF_IMMICH_API_KEY, "")
                    ): str,
                }
            ),
        )

    async def _save_and_finish(self) -> ConfigFlowResult:
        """Save profiles and devices, then finish."""
        new_data = dict(self.config_entry.data)
        new_data[CONF_PROFILES] = self._profiles
        new_data[CONF_DEVICES] = self._devices
        
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data=new_data,
        )
        
        # Push config to all devices
        from . import push_config_to_device
        for device_id in self._devices:
            await push_config_to_device(self.hass, device_id)
        
        return self.async_create_entry(title="", data={})
