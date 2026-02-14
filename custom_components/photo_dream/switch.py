"""Switch platform for PhotoDream."""
from __future__ import annotations

import logging
from typing import Any, Callable

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .helpers import get_device_info

from .const import (
    DOMAIN,
    ENTRY_TYPE_HUB,
    CONF_DEVICES,
    CONF_CLOCK,
    CONF_DATE,
    CONF_WEATHER,
)
from . import push_config_to_device, get_device_data, send_command_to_device

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PhotoDream switches from a config entry."""
    # Only create entities for Hub entries
    if entry.data.get("entry_type") != ENTRY_TYPE_HUB:
        return
    
    devices = entry.data.get(CONF_DEVICES, {})
    
    entities = []
    for device_id, device_config in devices.items():
        entities.append(PhotoDreamClockSwitch(hass, entry, device_id, device_config))
        entities.append(PhotoDreamDateSwitch(hass, entry, device_id, device_config))
        entities.append(PhotoDreamWeatherSwitch(hass, entry, device_id, device_config))
        entities.append(PhotoDreamAutoBrightnessSwitch(hass, entry, device_id, device_config))
    
    async_add_entities(entities)


class PhotoDreamBaseSwitch(SwitchEntity):
    """Base class for PhotoDream switches."""

    _attr_has_entity_name = True

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
        self._attr_device_info = get_device_info(hass, entry, device_id, device_config)

    def _get_device_config(self) -> dict:
        """Get current device config."""
        return self._entry.data.get(CONF_DEVICES, {}).get(self._device_id, {})

    def _update_device_config(self, key: str, value: Any) -> None:
        """Update device config in entry data."""
        new_data = dict(self._entry.data)
        if CONF_DEVICES not in new_data:
            new_data[CONF_DEVICES] = {}
        if self._device_id not in new_data[CONF_DEVICES]:
            new_data[CONF_DEVICES][self._device_id] = dict(self._device_config)
        new_data[CONF_DEVICES][self._device_id][key] = value
        self.hass.config_entries.async_update_entry(self._entry, data=new_data)


class PhotoDreamClockSwitch(PhotoDreamBaseSwitch):
    """Switch to toggle clock display on a PhotoDream device."""

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
        super().__init__(hass, entry, device_id, device_config)
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_clock"

    @property
    def is_on(self) -> bool:
        """Return true if clock is enabled."""
        return self._get_device_config().get(CONF_CLOCK, True)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the clock."""
        self._update_device_config(CONF_CLOCK, True)
        await push_config_to_device(self.hass, self._device_id)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the clock."""
        self._update_device_config(CONF_CLOCK, False)
        await push_config_to_device(self.hass, self._device_id)
        self.async_write_ha_state()


class PhotoDreamDateSwitch(PhotoDreamBaseSwitch):
    """Switch to toggle date display on a PhotoDream device."""

    _attr_name = "Date"
    _attr_icon = "mdi:calendar"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device_id: str,
        device_config: dict,
    ) -> None:
        """Initialize the switch."""
        super().__init__(hass, entry, device_id, device_config)
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_date"

    @property
    def is_on(self) -> bool:
        """Return true if date is enabled."""
        return self._get_device_config().get(CONF_DATE, False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the date."""
        self._update_device_config(CONF_DATE, True)
        await push_config_to_device(self.hass, self._device_id)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the date."""
        self._update_device_config(CONF_DATE, False)
        await push_config_to_device(self.hass, self._device_id)
        self.async_write_ha_state()


class PhotoDreamWeatherSwitch(PhotoDreamBaseSwitch):
    """Switch to toggle weather display on a PhotoDream device."""

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
        super().__init__(hass, entry, device_id, device_config)
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_weather"

    @property
    def is_on(self) -> bool:
        """Return true if weather is enabled."""
        return self._get_device_config().get(CONF_WEATHER, False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the weather."""
        self._update_device_config(CONF_WEATHER, True)
        await push_config_to_device(self.hass, self._device_id)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the weather."""
        self._update_device_config(CONF_WEATHER, False)
        await push_config_to_device(self.hass, self._device_id)
        self.async_write_ha_state()


class PhotoDreamAutoBrightnessSwitch(SwitchEntity):
    """Switch to toggle auto-brightness on a PhotoDream device."""

    _attr_has_entity_name = True
    _attr_name = "Auto Brightness"
    _attr_icon = "mdi:brightness-auto"

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
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_auto_brightness"
        self._attr_device_info = get_device_info(hass, entry, device_id, device_config)
        self._is_on: bool = False  # Default until first poll
        self._supported: bool = True
        self._remove_listener: Any = None
    
    async def async_added_to_hass(self) -> None:
        """Register event listener when added to hass."""
        from .const import DOMAIN
        
        async def handle_brightness_changed(event):
            """Handle brightness change event - refresh our state."""
            if event.data.get("device_id") == self._device_id:
                await self.async_update()
                self.async_write_ha_state()
        
        self._remove_listener = self.hass.bus.async_listen(
            f"{DOMAIN}_brightness_changed",
            handle_brightness_changed
        )
    
    async def async_will_remove_from_hass(self) -> None:
        """Remove event listener when removed from hass."""
        if self._remove_listener:
            self._remove_listener()

    @property
    def is_on(self) -> bool:
        """Return true if auto-brightness is enabled."""
        return self._is_on

    @property
    def available(self) -> bool:
        """Return true if auto-brightness is supported by device."""
        return self._supported

    async def async_update(self) -> None:
        """Fetch latest auto-brightness state from device."""
        data = await get_device_data(self.hass, self._device_id, "auto-brightness")
        if data:
            self._is_on = data.get("auto_brightness", False)
            self._supported = data.get("supported", True)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on auto-brightness."""
        success = await send_command_to_device(
            self.hass, self._device_id, "auto-brightness", {"enabled": True}
        )
        if success:
            self._is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off auto-brightness."""
        success = await send_command_to_device(
            self.hass, self._device_id, "auto-brightness", {"enabled": False}
        )
        if success:
            self._is_on = False
            self.async_write_ha_state()
