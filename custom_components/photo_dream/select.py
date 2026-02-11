"""Select platform for PhotoDream."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .helpers import get_device_info

from .const import (
    DOMAIN,
    CONF_DEVICES,
    CONF_PROFILES,
    
    CONF_CLOCK_POSITION,
    CONF_CLOCK_FORMAT,
    CONF_DISPLAY_MODE,
    DEFAULT_CLOCK_POSITION,
    DEFAULT_CLOCK_FORMAT,
    DEFAULT_DISPLAY_MODE,
    CLOCK_POSITIONS,
    ATTR_PROFILE,
)
from . import send_command_to_device, push_config_to_device

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
        entities.append(PhotoDreamClockPositionSelect(hass, entry, device_id, device_config))
        entities.append(PhotoDreamClockFormatSelect(hass, entry, device_id, device_config))
        entities.append(PhotoDreamDisplayModeSelect(hass, entry, device_id, device_config))
    
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
        
        self._attr_device_info = get_device_info(hass, entry, device_id, device_config)

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


class PhotoDreamClockPositionSelect(SelectEntity):
    """Select entity for clock position on a PhotoDream device."""

    _attr_has_entity_name = True
    _attr_name = "Clock Position"
    _attr_icon = "mdi:clock-outline"
    _attr_options = ["Top Left", "Top Right", "Bottom Left", "Bottom Right"]

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device_id: str,
        device_config: dict,
    ) -> None:
        """Initialize the select entity."""
        self.hass = hass
        self._entry = entry
        self._device_id = device_id
        self._device_config = device_config
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_clock_position"
        
        self._attr_device_info = get_device_info(hass, entry, device_id, device_config)

    @property
    def current_option(self) -> str | None:
        """Return the current clock position."""
        pos = self._get_device_config().get(CONF_CLOCK_POSITION, DEFAULT_CLOCK_POSITION)
        return CLOCK_POSITIONS.get(pos, "Bottom Right")

    async def async_select_option(self, option: str) -> None:
        """Change the clock position."""
        # Convert option back to number
        pos_map = {v: k for k, v in CLOCK_POSITIONS.items()}
        pos = pos_map.get(option, DEFAULT_CLOCK_POSITION)
        
        self._update_device_config(CONF_CLOCK_POSITION, pos)
        await push_config_to_device(self.hass, self._device_id)
        self.async_write_ha_state()

    def _get_device_config(self) -> dict:
        return self._entry.data.get(CONF_DEVICES, {}).get(self._device_id, {})

    def _update_device_config(self, key: str, value) -> None:
        new_data = dict(self._entry.data)
        if CONF_DEVICES not in new_data:
            new_data[CONF_DEVICES] = {}
        if self._device_id not in new_data[CONF_DEVICES]:
            new_data[CONF_DEVICES][self._device_id] = {}
        new_data[CONF_DEVICES][self._device_id][key] = value
        self.hass.config_entries.async_update_entry(self._entry, data=new_data)


class PhotoDreamClockFormatSelect(SelectEntity):
    """Select entity for clock format on a PhotoDream device."""

    _attr_has_entity_name = True
    _attr_name = "Clock Format"
    _attr_icon = "mdi:clock-digital"
    _attr_options = ["12h", "24h"]

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device_id: str,
        device_config: dict,
    ) -> None:
        """Initialize the select entity."""
        self.hass = hass
        self._entry = entry
        self._device_id = device_id
        self._device_config = device_config
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_clock_format"
        
        self._attr_device_info = get_device_info(hass, entry, device_id, device_config)

    @property
    def current_option(self) -> str | None:
        """Return the current clock format."""
        return self._get_device_config().get(CONF_CLOCK_FORMAT, DEFAULT_CLOCK_FORMAT)

    async def async_select_option(self, option: str) -> None:
        """Change the clock format."""
        self._update_device_config(CONF_CLOCK_FORMAT, option)
        await push_config_to_device(self.hass, self._device_id)
        self.async_write_ha_state()

    def _get_device_config(self) -> dict:
        return self._entry.data.get(CONF_DEVICES, {}).get(self._device_id, {})

    def _update_device_config(self, key: str, value) -> None:
        new_data = dict(self._entry.data)
        if CONF_DEVICES not in new_data:
            new_data[CONF_DEVICES] = {}
        if self._device_id not in new_data[CONF_DEVICES]:
            new_data[CONF_DEVICES][self._device_id] = {}
        new_data[CONF_DEVICES][self._device_id][key] = value
        self.hass.config_entries.async_update_entry(self._entry, data=new_data)


class PhotoDreamDisplayModeSelect(SelectEntity):
    """Select entity for display mode on a PhotoDream device."""

    _attr_has_entity_name = True
    _attr_name = "Display Mode"
    _attr_icon = "mdi:shuffle-variant"
    _attr_options = ["smart_shuffle", "random", "sequential"]

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device_id: str,
        device_config: dict,
    ) -> None:
        """Initialize the select entity."""
        self.hass = hass
        self._entry = entry
        self._device_id = device_id
        self._device_config = device_config
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_display_mode"
        
        self._attr_device_info = get_device_info(hass, entry, device_id, device_config)

    @property
    def current_option(self) -> str | None:
        """Return the current display mode."""
        return self._get_device_config().get(CONF_DISPLAY_MODE, DEFAULT_DISPLAY_MODE)

    async def async_select_option(self, option: str) -> None:
        """Change the display mode."""
        self._update_device_config(CONF_DISPLAY_MODE, option)
        await push_config_to_device(self.hass, self._device_id)
        self.async_write_ha_state()

    def _get_device_config(self) -> dict:
        return self._entry.data.get(CONF_DEVICES, {}).get(self._device_id, {})

    def _update_device_config(self, key: str, value) -> None:
        new_data = dict(self._entry.data)
        if CONF_DEVICES not in new_data:
            new_data[CONF_DEVICES] = {}
        if self._device_id not in new_data[CONF_DEVICES]:
            new_data[CONF_DEVICES][self._device_id] = {}
        new_data[CONF_DEVICES][self._device_id][key] = value
        self.hass.config_entries.async_update_entry(self._entry, data=new_data)
