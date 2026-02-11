"""Number platform for PhotoDream."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .helpers import get_device_info

from .const import (
    DOMAIN,
    CONF_DEVICES,
    CONF_INTERVAL,
    CONF_PAN_SPEED,
    CONF_CLOCK_FONT_SIZE,
    DEFAULT_INTERVAL,
    DEFAULT_PAN_SPEED,
    DEFAULT_CLOCK_FONT_SIZE,
)
from . import push_config_to_device

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PhotoDream number entities from a config entry."""
    config = entry.data
    devices = config.get(CONF_DEVICES, {})
    
    entities = []
    for device_id, device_config in devices.items():
        entities.append(PhotoDreamIntervalNumber(hass, entry, device_id, device_config))
        entities.append(PhotoDreamPanSpeedNumber(hass, entry, device_id, device_config))
        entities.append(PhotoDreamClockFontSizeNumber(hass, entry, device_id, device_config))
    
    async_add_entities(entities)


class PhotoDreamIntervalNumber(NumberEntity):
    """Number entity for slide interval on a PhotoDream device."""

    _attr_has_entity_name = True
    _attr_name = "Slide Interval"
    _attr_icon = "mdi:timer-outline"
    _attr_native_min_value = 5
    _attr_native_max_value = 300
    _attr_native_step = 5
    _attr_native_unit_of_measurement = "s"
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device_id: str,
        device_config: dict,
    ) -> None:
        """Initialize the number entity."""
        self.hass = hass
        self._entry = entry
        self._device_id = device_id
        self._device_config = device_config
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_interval"
        
        self._attr_device_info = get_device_info(hass, entry, device_id, device_config)

    @property
    def native_value(self) -> float:
        """Return the current interval."""
        return self._get_device_config().get(CONF_INTERVAL, DEFAULT_INTERVAL)

    async def async_set_native_value(self, value: float) -> None:
        """Set the interval."""
        self._update_device_config(CONF_INTERVAL, int(value))
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


class PhotoDreamPanSpeedNumber(NumberEntity):
    """Number entity for pan speed (Ken Burns) on a PhotoDream device."""

    _attr_has_entity_name = True
    _attr_name = "Pan Speed"
    _attr_icon = "mdi:pan"
    _attr_native_min_value = 0.0
    _attr_native_max_value = 2.0
    _attr_native_step = 0.1
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device_id: str,
        device_config: dict,
    ) -> None:
        """Initialize the number entity."""
        self.hass = hass
        self._entry = entry
        self._device_id = device_id
        self._device_config = device_config
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_pan_speed"
        
        self._attr_device_info = get_device_info(hass, entry, device_id, device_config)

    @property
    def native_value(self) -> float:
        """Return the current pan speed."""
        return self._get_device_config().get(CONF_PAN_SPEED, DEFAULT_PAN_SPEED)

    async def async_set_native_value(self, value: float) -> None:
        """Set the pan speed."""
        self._update_device_config(CONF_PAN_SPEED, round(value, 1))
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


class PhotoDreamClockFontSizeNumber(NumberEntity):
    """Number entity for clock font size on a PhotoDream device."""

    _attr_has_entity_name = True
    _attr_name = "Clock Font Size"
    _attr_icon = "mdi:format-size"
    _attr_native_min_value = 12
    _attr_native_max_value = 200
    _attr_native_step = 2
    _attr_native_unit_of_measurement = "sp"
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device_id: str,
        device_config: dict,
    ) -> None:
        """Initialize the number entity."""
        self.hass = hass
        self._entry = entry
        self._device_id = device_id
        self._device_config = device_config
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_clock_font_size"
        self._attr_device_info = get_device_info(hass, entry, device_id, device_config)

    @property
    def native_value(self) -> int:
        """Return the current font size."""
        return self._get_device_config().get(CONF_CLOCK_FONT_SIZE, DEFAULT_CLOCK_FONT_SIZE)

    async def async_set_native_value(self, value: float) -> None:
        """Set the font size."""
        self._update_device_config(CONF_CLOCK_FONT_SIZE, int(value))
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
