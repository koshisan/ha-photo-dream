"""Select platform for PhotoDream."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .const import (
    DOMAIN,
    CONF_DEVICES,
    CONF_PROFILES,
    CONF_DEVICE_NAME,
    ATTR_PROFILE,
)
from . import send_command_to_device

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PhotoDream select entities from a config entry."""
    config = entry.data
    devices = config.get(CONF_DEVICES, {})
    profiles = list(config.get(CONF_PROFILES, {}).keys())
    
    entities = []
    for device_id, device_config in devices.items():
        entities.append(PhotoDreamProfileSelect(hass, entry, device_id, device_config, profiles))
    
    async_add_entities(entities)


class PhotoDreamProfileSelect(SelectEntity):
    """Select entity for choosing the active profile on a PhotoDream device."""

    _attr_has_entity_name = True
    _attr_name = "Profile"
    _attr_icon = "mdi:palette"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device_id: str,
        device_config: dict,
        profiles: list[str],
    ) -> None:
        """Initialize the select entity."""
        self.hass = hass
        self._entry = entry
        self._device_id = device_id
        self._device_config = device_config
        self._profiles = profiles
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_profile"
        self._attr_options = profiles if profiles else ["default"]
        
        device_name = device_config.get(CONF_DEVICE_NAME, device_id)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{device_id}")},
            name=f"PhotoDream {device_name}",
            manufacturer="PhotoDream",
            model="Android Tablet",
        )

    @property
    def current_option(self) -> str | None:
        """Return the current selected profile."""
        device_data = self._get_device_data()
        if device_data:
            return device_data.get(ATTR_PROFILE)
        # Fall back to configured default
        return self._device_config.get("profile", self._attr_options[0] if self._attr_options else None)

    async def async_select_option(self, option: str) -> None:
        """Change the selected profile."""
        _LOGGER.info("Setting profile to %s for device %s", option, self._device_id)
        
        # Update in device config
        entry_data = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id, {})
        if "devices" in entry_data:
            if self._device_id not in entry_data["devices"]:
                entry_data["devices"][self._device_id] = {}
            entry_data["devices"][self._device_id][ATTR_PROFILE] = option
        
        # Send command to device
        await send_command_to_device(
            self.hass,
            self._device_id,
            "set-profile",
            {"profile": option},
        )
        
        self.async_write_ha_state()

    def _get_device_data(self) -> dict | None:
        """Get device data from hass.data."""
        entry_data = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id, {})
        devices = entry_data.get("devices", {})
        return devices.get(self._device_id)

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        self.async_on_remove(
            self.hass.bus.async_listen(
                f"{DOMAIN}_device_update",
                self._handle_device_update,
            )
        )

    @callback
    def _handle_device_update(self, event) -> None:
        """Handle device update event."""
        if event.data.get("device_id") == self._device_id:
            self.async_write_ha_state()
