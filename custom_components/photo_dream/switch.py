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
    CONF_CALENDAR,
    CONF_CALENDAR_SHOW_LOCATION,
    DEFAULT_CALENDAR,
    DEFAULT_CALENDAR_SHOW_LOCATION,
    CONF_SKIP_WRONG_ASPECT,
    CONF_ALWAYS_PLAY_FULL_VIDEO,
    DEFAULT_SKIP_WRONG_ASPECT,
    DEFAULT_ALWAYS_PLAY_FULL_VIDEO,
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
        entities.append(PhotoDreamCalendarSwitch(hass, entry, device_id, device_config))
        entities.append(PhotoDreamCalendarShowLocationSwitch(hass, entry, device_id, device_config))
        entities.append(PhotoDreamSkipWrongAspectSwitch(hass, entry, device_id, device_config))
        entities.append(PhotoDreamAlwaysPlayFullVideoSwitch(hass, entry, device_id, device_config))
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
        # Deep-copy the devices map so async_update_entry detects a real change
        # and fires update listeners (re-subscriptions). Mutating the shared
        # dict in place makes HA see "no change" and skip the listeners.
        devices = {k: dict(v) for k, v in new_data.get(CONF_DEVICES, {}).items()}
        devices.setdefault(self._device_id, dict(self._device_config))
        devices[self._device_id][key] = value
        new_data[CONF_DEVICES] = devices
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


class PhotoDreamCalendarSwitch(PhotoDreamBaseSwitch):
    """Switch to toggle calendar overlay on a PhotoDream device."""

    _attr_name = "Calendar"
    _attr_icon = "mdi:calendar-month"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device_id: str,
        device_config: dict,
    ) -> None:
        """Initialize the switch."""
        super().__init__(hass, entry, device_id, device_config)
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_calendar"

    @property
    def is_on(self) -> bool:
        """Return true if calendar overlay is enabled."""
        return self._get_device_config().get(CONF_CALENDAR, DEFAULT_CALENDAR)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the calendar overlay and push fresh events."""
        self._update_device_config(CONF_CALENDAR, True)
        await push_config_to_device(self.hass, self._device_id)
        # push_config_to_device already triggers a calendar push when enabled.
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the calendar overlay."""
        self._update_device_config(CONF_CALENDAR, False)
        await push_config_to_device(self.hass, self._device_id)
        self.async_write_ha_state()


class PhotoDreamCalendarShowLocationSwitch(PhotoDreamBaseSwitch):
    """Switch to toggle showing the location per calendar event."""

    _attr_name = "Calendar Show Location"
    _attr_icon = "mdi:map-marker-outline"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device_id: str,
        device_config: dict,
    ) -> None:
        """Initialize the switch."""
        super().__init__(hass, entry, device_id, device_config)
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_calendar_show_location"

    @property
    def is_on(self) -> bool:
        """Return true if event locations are shown."""
        return self._get_device_config().get(
            CONF_CALENDAR_SHOW_LOCATION, DEFAULT_CALENDAR_SHOW_LOCATION
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Show event locations."""
        self._update_device_config(CONF_CALENDAR_SHOW_LOCATION, True)
        await push_config_to_device(self.hass, self._device_id)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Hide event locations."""
        self._update_device_config(CONF_CALENDAR_SHOW_LOCATION, False)
        await push_config_to_device(self.hass, self._device_id)
        self.async_write_ha_state()


class PhotoDreamSkipWrongAspectSwitch(PhotoDreamBaseSwitch):
    """Switch to only show media whose aspect ratio fits the display (~20%)."""

    _attr_name = "Skip Wrong Aspect"
    _attr_icon = "mdi:aspect-ratio"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device_id: str,
        device_config: dict,
    ) -> None:
        """Initialize the switch."""
        super().__init__(hass, entry, device_id, device_config)
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_skip_wrong_aspect"

    @property
    def is_on(self) -> bool:
        """Return true if wrong-aspect media is skipped."""
        return self._get_device_config().get(
            CONF_SKIP_WRONG_ASPECT, DEFAULT_SKIP_WRONG_ASPECT
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable aspect-ratio filtering."""
        self._update_device_config(CONF_SKIP_WRONG_ASPECT, True)
        await push_config_to_device(self.hass, self._device_id)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable aspect-ratio filtering."""
        self._update_device_config(CONF_SKIP_WRONG_ASPECT, False)
        await push_config_to_device(self.hass, self._device_id)
        self.async_write_ha_state()


class PhotoDreamAlwaysPlayFullVideoSwitch(PhotoDreamBaseSwitch):
    """Switch to let videos finish before the slideshow advances."""

    _attr_name = "Always Play Full Video"
    _attr_icon = "mdi:play-box-multiple"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device_id: str,
        device_config: dict,
    ) -> None:
        """Initialize the switch."""
        super().__init__(hass, entry, device_id, device_config)
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_always_play_full_video"

    @property
    def is_on(self) -> bool:
        """Return true if videos always play to the end."""
        return self._get_device_config().get(
            CONF_ALWAYS_PLAY_FULL_VIDEO, DEFAULT_ALWAYS_PLAY_FULL_VIDEO
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Let videos play to the end."""
        self._update_device_config(CONF_ALWAYS_PLAY_FULL_VIDEO, True)
        await push_config_to_device(self.hass, self._device_id)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Cut videos at the slide interval."""
        self._update_device_config(CONF_ALWAYS_PLAY_FULL_VIDEO, False)
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
