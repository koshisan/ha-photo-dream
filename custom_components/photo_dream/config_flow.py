"""Config flow for PhotoDream integration."""
from __future__ import annotations

import logging
import secrets
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
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
    CONF_DEVICE_PROFILE,
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
        self._profiles: dict[str, Any] = {}
        self._devices: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step - Immich configuration."""
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
                    "webhook_id": secrets.token_hex(16),
                }
                return await self.async_step_profile()
            else:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_IMMICH_URL, default="http://192.168.1.100:2283"): str,
                    vol.Required(CONF_IMMICH_API_KEY): str,
                }
            ),
            errors=errors,
        )

    async def async_step_profile(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle adding a profile."""
        if user_input is not None:
            profile_name = user_input[CONF_PROFILE_NAME]
            search_queries = [
                q.strip() for q in user_input[CONF_SEARCH_QUERIES].split(",") if q.strip()
            ]
            exclude_paths = [
                p.strip() for p in user_input.get(CONF_EXCLUDE_PATHS, "").split(",") if p.strip()
            ]
            
            self._profiles[profile_name] = {
                CONF_SEARCH_QUERIES: search_queries,
                CONF_EXCLUDE_PATHS: exclude_paths,
            }
            
            if user_input.get("add_another"):
                return await self.async_step_profile()
            
            return await self.async_step_device()

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
                "profile_count": str(len(self._profiles)),
            },
        )

    async def async_step_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle adding a device."""
        if user_input is not None:
            device_id = user_input[CONF_DEVICE_ID]
            
            self._devices[device_id] = {
                CONF_DEVICE_NAME: user_input.get(CONF_DEVICE_NAME, device_id),
                CONF_DEVICE_IP: user_input[CONF_DEVICE_IP],
                CONF_DEVICE_PORT: user_input.get(CONF_DEVICE_PORT, DEFAULT_PORT),
                "profile": user_input.get(CONF_DEVICE_PROFILE, "default"),
                CONF_CLOCK: user_input.get(CONF_CLOCK, DEFAULT_CLOCK),
                CONF_CLOCK_POSITION: user_input.get(CONF_CLOCK_POSITION, DEFAULT_CLOCK_POSITION),
                CONF_CLOCK_FORMAT: user_input.get(CONF_CLOCK_FORMAT, DEFAULT_CLOCK_FORMAT),
                CONF_INTERVAL: user_input.get(CONF_INTERVAL, DEFAULT_INTERVAL),
            }
            
            if user_input.get("add_another"):
                return await self.async_step_device()
            
            # Finalize
            self._data[CONF_PROFILES] = self._profiles
            self._data[CONF_DEVICES] = self._devices
            
            return self.async_create_entry(
                title="PhotoDream",
                data=self._data,
            )

        profile_options = list(self._profiles.keys())
        
        return self.async_show_form(
            step_id="device",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_ID, default="kitchen"): str,
                    vol.Optional(CONF_DEVICE_NAME): str,
                    vol.Required(CONF_DEVICE_IP): str,
                    vol.Optional(CONF_DEVICE_PORT, default=DEFAULT_PORT): int,
                    vol.Required(CONF_DEVICE_PROFILE, default=profile_options[0] if profile_options else "default"): vol.In(profile_options or ["default"]),
                    vol.Optional(CONF_CLOCK, default=DEFAULT_CLOCK): bool,
                    vol.Optional(CONF_CLOCK_POSITION, default=DEFAULT_CLOCK_POSITION): vol.In(CLOCK_POSITIONS),
                    vol.Optional(CONF_CLOCK_FORMAT, default=DEFAULT_CLOCK_FORMAT): vol.In(["12h", "24h"]),
                    vol.Optional(CONF_INTERVAL, default=DEFAULT_INTERVAL): int,
                    vol.Optional("add_another", default=False): bool,
                }
            ),
            description_placeholders={
                "device_count": str(len(self._devices)),
                "profiles": ", ".join(profile_options),
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
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return PhotoDreamOptionsFlow(config_entry)


class PhotoDreamOptionsFlow(OptionsFlow):
    """Handle options flow for PhotoDream."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            # Update the config entry
            new_data = {**self.config_entry.data}
            # Apply updates from user_input
            return self.async_create_entry(title="", data=new_data)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_IMMICH_URL,
                        default=self.config_entry.data.get(CONF_IMMICH_URL, ""),
                    ): str,
                }
            ),
        )
