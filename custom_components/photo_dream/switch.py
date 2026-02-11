"""Switch platform for PhotoDream."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .const import (
    DOMAIN,
    CONF_DEVICES,
    CONF_DEVICE_NAME,
    CONF_CLOCK,
    CONF_WEATHER,
)
from . import push_config_to_device

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PhotoDream switches from a config entry."""
    config = entry.data
    devices = config.get(CONF_DEVICES, {})
    
    entities = []
    for device_id, device_config in devices.items():
        entities.append(PhotoDreamClockSwitch(hass, entry, device_id, device_config))
        entities.append(PhotoDreamWeatherSwitch(hass, entry, device_id, device_config))
    
    async_add_entities(entities)


class PhotoDreamClockSwitch(SwitchEntity):
    """Switch to toggle clock display on a PhotoDream device."""

    _attr_has_entity_name = True
    _attr_name = "Clock"
    _attr_icon = "mdi:clock-outline"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device_id: str,
        device_config: dict,
    ) -> None:
        """Initialize the switch."""
        self.hass = hass
        self._entry = entry
        self._device_id = device_id
        self._device_config = device_config
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_clock"
        
        device_name = device_config.get(CONF_DEVICE_NAME, device_id)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{device_id}")},
            name=f"PhotoDream {device_name}",
            manufacturer="PhotoDream",
            model="Android Tablet",
        )

    @property
    def is_on(self) -> bool:
        """Return true if clock is enabled."""
        return self._get_device_config().get(CONF_CLOCK, True)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the clock."""
        await self._set_clock(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the clock."""
        await self._set_clock(False)

    async def _set_clock(self, enabled: bool) -> None:
        """Set clock state and push config."""
        self._update_device_config(CONF_CLOCK, enabled)
        await push_config_to_device(self.hass, self._device_id)
        self.async_write_ha_state()

    def _get_device_config(self) -> dict:
        """Get current device config."""
        config = self._entry.data
        return config.get(CONF_DEVICES, {}).get(self._device_id, {})

    def _update_device_config(self, key: str, value: Any) -> None:
        """Update device config in entry data."""
        new_data = dict(self._entry.data)
        if CONF_DEVICES not in new_data:
            new_data[CONF_DEVICES] = {}
        if self._device_id not in new_data[CONF_DEVICES]:
            new_data[CONF_DEVICES][self._device_id] = {}
        new_data[CONF_DEVICES][self._device_id][key] = value
        self.hass.config_entries.async_update_entry(self._entry, data=new_data)


class PhotoDreamWeatherSwitch(SwitchEntity):
    """Switch to toggle weather display on a PhotoDream device."""

    _attr_has_entity_name = True
    _attr_name = "Weather"
    _attr_icon = "mdi:weather-partly-cloudy"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device_id: str,
        device_config: dict,
    ) -> None:
        """Initialize the switch."""
        self.hass = hass
        self._entry = entry
        self._device_id = device_id
        self._device_config = device_config
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_weather"
        
        device_name = device_config.get(CONF_DEVICE_NAME, device_id)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{device_id}")},
            name=f"PhotoDream {device_name}",
            manufacturer="PhotoDream",
            model="Android Tablet",
        )

    @property
    def is_on(self) -> bool:
        """Return true if weather is enabled."""
        return self._get_device_config().get(CONF_WEATHER, False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on weather display."""
        await self._set_weather(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off weather display."""
        await self._set_weather(False)

    async def _set_weather(self, enabled: bool) -> None:
        """Set weather state and push config."""
        self._update_device_config(CONF_WEATHER, enabled)
        await push_config_to_device(self.hass, self._device_id)
        self.async_write_ha_state()

    def _get_device_config(self) -> dict:
        """Get current device config."""
        config = self._entry.data
        return config.get(CONF_DEVICES, {}).get(self._device_id, {})

    def _update_device_config(self, key: str, value: Any) -> None:
        """Update device config in entry data."""
        new_data = dict(self._entry.data)
        if CONF_DEVICES not in new_data:
            new_data[CONF_DEVICES] = {}
        if self._device_id not in new_data[CONF_DEVICES]:
            new_data[CONF_DEVICES][self._device_id] = {}
        new_data[CONF_DEVICES][self._device_id][key] = value
        self.hass.config_entries.async_update_entry(self._entry, data=new_data)
