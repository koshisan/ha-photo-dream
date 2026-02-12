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
    ENTRY_TYPE_HUB,
    ENTRY_TYPE_IMMICH,
    CONF_DEVICES,
    CONF_PROFILES,
    CONF_PROFILE_ID,
    CONF_IMMICH_NAME,
    CONF_CLOCK_POSITION,
    CONF_CLOCK_FORMAT,
    CONF_DATE_FORMAT,
    CONF_DISPLAY_MODE,
    CONF_WEATHER_ENTITY,
    DEFAULT_CLOCK_POSITION,
    DEFAULT_CLOCK_FORMAT,
    DEFAULT_DATE_FORMAT,
    DEFAULT_DISPLAY_MODE,
    CLOCK_POSITIONS,
    DATE_FORMATS,
    ATTR_PROFILE,
)
from . import send_command_to_device, push_config_to_device

_LOGGER = logging.getLogger(__name__)


def get_all_profiles(hass: HomeAssistant) -> dict[str, str]:
    """Get all profiles from all Immich instances as {profile_id: display_name}."""
    profiles = {}
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data.get("entry_type") == ENTRY_TYPE_IMMICH:
            immich_name = entry.data.get(CONF_IMMICH_NAME, "Immich")
            for profile_name in entry.data.get(CONF_PROFILES, {}).keys():
                profile_id = f"{entry.entry_id}_{profile_name}".replace(" ", "_").lower()
                profiles[profile_id] = f"{immich_name} / {profile_name}"
    return profiles


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PhotoDream select entities from a config entry."""
    # Only create entities for Hub entries
    if entry.data.get("entry_type") != ENTRY_TYPE_HUB:
        return
    
    devices = entry.data.get(CONF_DEVICES, {})
    
    entities = []
    for device_id, device_config in devices.items():
        entities.append(PhotoDreamProfileSelect(hass, entry, device_id, device_config))
        entities.append(PhotoDreamClockPositionSelect(hass, entry, device_id, device_config))
        entities.append(PhotoDreamClockFormatSelect(hass, entry, device_id, device_config))
        entities.append(PhotoDreamDateFormatSelect(hass, entry, device_id, device_config))
        entities.append(PhotoDreamDisplayModeSelect(hass, entry, device_id, device_config))
        entities.append(PhotoDreamWeatherEntitySelect(hass, entry, device_id, device_config))
    
    async_add_entities(entities)


class PhotoDreamBaseSelect(SelectEntity):
    """Base class for PhotoDream select entities."""

    _attr_has_entity_name = True

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
        self._attr_device_info = get_device_info(hass, entry, device_id, device_config)

    def _get_device_data(self) -> dict | None:
        """Get device runtime data from hass.data."""
        hub_data = self.hass.data.get(DOMAIN, {}).get("hub")
        if not hub_data:
            return None
        return hub_data.get("devices", {}).get(self._device_id)

    def _get_device_config(self) -> dict:
        """Get device config from entry data."""
        return self._entry.data.get(CONF_DEVICES, {}).get(self._device_id, {})

    def _update_device_config(self, key: str, value) -> None:
        """Update device config in entry data."""
        new_data = dict(self._entry.data)
        if CONF_DEVICES not in new_data:
            new_data[CONF_DEVICES] = {}
        if self._device_id not in new_data[CONF_DEVICES]:
            new_data[CONF_DEVICES][self._device_id] = dict(self._device_config)
        new_data[CONF_DEVICES][self._device_id][key] = value
        self.hass.config_entries.async_update_entry(self._entry, data=new_data)

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


class PhotoDreamProfileSelect(PhotoDreamBaseSelect):
    """Select entity for choosing the active profile on a PhotoDream device."""

    _attr_name = "Profile"
    _attr_icon = "mdi:palette"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device_id: str,
        device_config: dict,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(hass, entry, device_id, device_config)
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_profile"
        self._update_options()

    def _update_options(self) -> None:
        """Update available profile options."""
        profiles = get_all_profiles(self.hass)
        self._profile_map = profiles  # {profile_id: display_name}
        self._attr_options = list(profiles.values()) if profiles else ["No profiles configured"]

    @property
    def current_option(self) -> str | None:
        """Return the current selected profile display name."""
        # First check runtime data for current profile name
        device_data = self._get_device_data()
        if device_data and device_data.get(ATTR_PROFILE):
            # Runtime data has profile name, try to find matching display name
            profile_name = device_data.get(ATTR_PROFILE)
            for pid, display in self._profile_map.items():
                if profile_name in display:
                    return display
        
        # Fall back to configured profile_id
        profile_id = self._get_device_config().get(CONF_PROFILE_ID, self._get_device_config().get("profile", ""))
        return self._profile_map.get(profile_id, self._attr_options[0] if self._attr_options else None)

    async def async_select_option(self, option: str) -> None:
        """Change the selected profile."""
        # Find profile_id from display name
        profile_id = None
        for pid, display in self._profile_map.items():
            if display == option:
                profile_id = pid
                break
        
        if not profile_id:
            _LOGGER.error("Could not find profile_id for option: %s", option)
            return
        
        _LOGGER.info("Setting profile to %s (%s) for device %s", option, profile_id, self._device_id)
        
        # Update config
        self._update_device_config(CONF_PROFILE_ID, profile_id)
        
        # Push to device
        await push_config_to_device(self.hass, self._device_id)
        self.async_write_ha_state()


class PhotoDreamClockPositionSelect(PhotoDreamBaseSelect):
    """Select entity for clock position on a PhotoDream device."""

    _attr_name = "Clock Position"
    _attr_icon = "mdi:clock-outline"
    _attr_options = list(CLOCK_POSITIONS.values())

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device_id: str,
        device_config: dict,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(hass, entry, device_id, device_config)
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_clock_position"

    @property
    def current_option(self) -> str | None:
        """Return the current clock position."""
        pos = self._get_device_config().get(CONF_CLOCK_POSITION, DEFAULT_CLOCK_POSITION)
        return CLOCK_POSITIONS.get(pos, CLOCK_POSITIONS[DEFAULT_CLOCK_POSITION])

    async def async_select_option(self, option: str) -> None:
        """Change the clock position."""
        pos_map = {v: k for k, v in CLOCK_POSITIONS.items()}
        pos = pos_map.get(option, DEFAULT_CLOCK_POSITION)
        
        self._update_device_config(CONF_CLOCK_POSITION, pos)
        await push_config_to_device(self.hass, self._device_id)
        self.async_write_ha_state()


class PhotoDreamClockFormatSelect(PhotoDreamBaseSelect):
    """Select entity for clock format on a PhotoDream device."""

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
        super().__init__(hass, entry, device_id, device_config)
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_clock_format"

    @property
    def current_option(self) -> str | None:
        """Return the current clock format."""
        return self._get_device_config().get(CONF_CLOCK_FORMAT, DEFAULT_CLOCK_FORMAT)

    async def async_select_option(self, option: str) -> None:
        """Change the clock format."""
        self._update_device_config(CONF_CLOCK_FORMAT, option)
        await push_config_to_device(self.hass, self._device_id)
        self.async_write_ha_state()


class PhotoDreamDateFormatSelect(PhotoDreamBaseSelect):
    """Select entity for date format on a PhotoDream device."""

    _attr_name = "Date Format"
    _attr_icon = "mdi:calendar"
    _attr_options = list(DATE_FORMATS.keys())

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device_id: str,
        device_config: dict,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(hass, entry, device_id, device_config)
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_date_format"

    @property
    def current_option(self) -> str | None:
        """Return the current date format."""
        return self._get_device_config().get(CONF_DATE_FORMAT, DEFAULT_DATE_FORMAT)

    async def async_select_option(self, option: str) -> None:
        """Change the date format."""
        self._update_device_config(CONF_DATE_FORMAT, option)
        await push_config_to_device(self.hass, self._device_id)
        self.async_write_ha_state()


class PhotoDreamDisplayModeSelect(PhotoDreamBaseSelect):
    """Select entity for display mode on a PhotoDream device."""

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
        super().__init__(hass, entry, device_id, device_config)
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_display_mode"

    @property
    def current_option(self) -> str | None:
        """Return the current display mode."""
        return self._get_device_config().get(CONF_DISPLAY_MODE, DEFAULT_DISPLAY_MODE)

    async def async_select_option(self, option: str) -> None:
        """Change the display mode."""
        self._update_device_config(CONF_DISPLAY_MODE, option)
        await push_config_to_device(self.hass, self._device_id)
        self.async_write_ha_state()


class PhotoDreamWeatherEntitySelect(PhotoDreamBaseSelect):
    """Select entity for choosing weather entity on a PhotoDream device."""

    _attr_name = "Weather Entity"
    _attr_icon = "mdi:weather-partly-cloudy"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device_id: str,
        device_config: dict,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(hass, entry, device_id, device_config)
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_weather_entity"
        self._update_options()

    def _update_options(self) -> None:
        """Update available weather entity options."""
        weather_entities = ["None"]  # Allow disabling weather
        
        # Find all weather entities
        for state in self.hass.states.async_all("weather"):
            friendly_name = state.attributes.get("friendly_name", state.entity_id)
            weather_entities.append(f"{friendly_name} ({state.entity_id})")
        
        self._weather_map = {}  # {display_name: entity_id}
        self._weather_map["None"] = None
        for state in self.hass.states.async_all("weather"):
            friendly_name = state.attributes.get("friendly_name", state.entity_id)
            display = f"{friendly_name} ({state.entity_id})"
            self._weather_map[display] = state.entity_id
        
        self._attr_options = list(self._weather_map.keys())

    @property
    def current_option(self) -> str | None:
        """Return the current weather entity."""
        entity_id = self._get_device_config().get(CONF_WEATHER_ENTITY)
        if not entity_id:
            return "None"
        
        # Find display name for entity_id
        for display, eid in self._weather_map.items():
            if eid == entity_id:
                return display
        
        # Entity not found in map, return entity_id directly
        return entity_id

    async def async_select_option(self, option: str) -> None:
        """Change the weather entity."""
        entity_id = self._weather_map.get(option)
        
        _LOGGER.info("Setting weather entity to %s for device %s", entity_id, self._device_id)
        
        self._update_device_config(CONF_WEATHER_ENTITY, entity_id)
        await push_config_to_device(self.hass, self._device_id)
        self.async_write_ha_state()
