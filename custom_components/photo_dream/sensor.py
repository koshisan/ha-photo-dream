"""Sensor platform for PhotoDream."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    ENTRY_TYPE_HUB,
    ENTRY_TYPE_IMMICH,
    CONF_DEVICES,
    CONF_PROFILES,
    CONF_PROFILE_ID,
    CONF_IMMICH_NAME,
    CONF_SEARCH_FILTER,
    CONF_EXCLUDE_PATHS,
    ATTR_CURRENT_IMAGE,
    ATTR_CURRENT_IMAGE_URL,
    ATTR_PROFILE,
    ATTR_LAST_SEEN,
    ATTR_MAC_ADDRESS,
    ATTR_IP_ADDRESS,
    ATTR_DISPLAY_WIDTH,
    ATTR_DISPLAY_HEIGHT,
    ATTR_APP_VERSION,
)
from .helpers import get_device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PhotoDream sensors from a config entry."""
    entry_type = entry.data.get("entry_type")
    
    if entry_type == ENTRY_TYPE_HUB:
        await async_setup_hub_sensors(hass, entry, async_add_entities)
    elif entry_type == ENTRY_TYPE_IMMICH:
        await async_setup_immich_sensors(hass, entry, async_add_entities)


async def async_setup_hub_sensors(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up tablet sensors for Hub entry."""
    devices = entry.data.get(CONF_DEVICES, {})
    
    entities = []
    for device_id, device_config in devices.items():
        entities.append(PhotoDreamCurrentImageSensor(hass, entry, device_id, device_config))
        entities.append(PhotoDreamMacAddressSensor(hass, entry, device_id, device_config))
        entities.append(PhotoDreamIpAddressSensor(hass, entry, device_id, device_config))
        entities.append(PhotoDreamResolutionSensor(hass, entry, device_id, device_config))
        entities.append(PhotoDreamVersionSensor(hass, entry, device_id, device_config))
    
    async_add_entities(entities)


class PhotoDreamBaseSensor(SensorEntity):
    """Base class for PhotoDream sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device_id: str,
        device_config: dict,
    ) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._entry = entry
        self._device_id = device_id
        self._device_config = device_config
        self._attr_device_info = get_device_info(hass, entry, device_id, device_config)

    def _get_device_data(self) -> dict | None:
        """Get device data from hass.data."""
        hub_data = self.hass.data.get(DOMAIN, {}).get("hub")
        if not hub_data:
            return None
        return hub_data.get("devices", {}).get(self._device_id)

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


class PhotoDreamCurrentImageSensor(PhotoDreamBaseSensor):
    """Sensor showing current image on a PhotoDream device."""

    _attr_name = "Current Image"
    _attr_icon = "mdi:image"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device_id: str,
        device_config: dict,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(hass, entry, device_id, device_config)
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_current_image"

    @property
    def native_value(self) -> str | None:
        """Return the Immich web URL for the current image."""
        device_data = self._get_device_data()
        if not device_data:
            return None
        
        image_id = device_data.get(ATTR_CURRENT_IMAGE)
        if not image_id:
            return None
        
        # Get Immich URL by resolving the profile
        immich_url = self._get_immich_url()
        
        if immich_url:
            return f"{immich_url}/photos/{image_id}"
        return image_id

    def _get_immich_url(self) -> str | None:
        """Get Immich URL from the device's profile."""
        from . import resolve_profile
        
        profile_id = self._device_config.get(CONF_PROFILE_ID, self._device_config.get("profile", ""))
        immich_entry, _, _ = resolve_profile(self.hass, profile_id)
        
        if immich_entry:
            from .const import CONF_IMMICH_URL
            return immich_entry.data.get(CONF_IMMICH_URL, "").rstrip("/")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        device_data = self._get_device_data()
        if not device_data:
            return {}
        
        return {
            "image_id": device_data.get(ATTR_CURRENT_IMAGE),
            "api_url": device_data.get(ATTR_CURRENT_IMAGE_URL),
            ATTR_PROFILE: device_data.get(ATTR_PROFILE),
            ATTR_LAST_SEEN: device_data.get(ATTR_LAST_SEEN),
        }


class PhotoDreamMacAddressSensor(PhotoDreamBaseSensor):
    """Sensor showing MAC address of a PhotoDream device."""

    _attr_name = "MAC Address"
    _attr_icon = "mdi:ethernet"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device_id: str,
        device_config: dict,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(hass, entry, device_id, device_config)
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_mac_address"

    @property
    def native_value(self) -> str | None:
        """Return the MAC address."""
        device_data = self._get_device_data()
        return device_data.get(ATTR_MAC_ADDRESS) if device_data else None


class PhotoDreamIpAddressSensor(PhotoDreamBaseSensor):
    """Sensor showing IP address of a PhotoDream device."""

    _attr_name = "IP Address"
    _attr_icon = "mdi:ip-network"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device_id: str,
        device_config: dict,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(hass, entry, device_id, device_config)
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_ip_address"

    @property
    def native_value(self) -> str | None:
        """Return the IP address."""
        device_data = self._get_device_data()
        return device_data.get(ATTR_IP_ADDRESS) if device_data else None


class PhotoDreamResolutionSensor(PhotoDreamBaseSensor):
    """Sensor showing display resolution of a PhotoDream device."""

    _attr_name = "Display Resolution"
    _attr_icon = "mdi:monitor"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device_id: str,
        device_config: dict,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(hass, entry, device_id, device_config)
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_resolution"

    @property
    def native_value(self) -> str | None:
        """Return the resolution as WxH."""
        device_data = self._get_device_data()
        if not device_data:
            return None
        width = device_data.get(ATTR_DISPLAY_WIDTH)
        height = device_data.get(ATTR_DISPLAY_HEIGHT)
        if width and height:
            return f"{width}x{height}"
        return None


class PhotoDreamVersionSensor(PhotoDreamBaseSensor):
    """Sensor showing app version of a PhotoDream device."""

    _attr_name = "App Version"
    _attr_icon = "mdi:tag"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device_id: str,
        device_config: dict,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(hass, entry, device_id, device_config)
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_app_version"

    @property
    def native_value(self) -> str | None:
        """Return the app version."""
        device_data = self._get_device_data()
        return device_data.get(ATTR_APP_VERSION) if device_data else None


# ============================================================================
# Immich Profile Sensors
# ============================================================================

async def async_setup_immich_sensors(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up profile sensors for Immich entry."""
    immich_data = hass.data.get(DOMAIN, {}).get("immich", {}).get(entry.entry_id)
    if not immich_data:
        _LOGGER.error("No Immich data found for entry %s", entry.entry_id)
        return
    
    coordinator = immich_data.get("coordinator")
    if not coordinator:
        _LOGGER.error("No coordinator found for Immich entry %s", entry.entry_id)
        return
    
    profiles = entry.data.get(CONF_PROFILES, {})
    immich_name = entry.data.get(CONF_IMMICH_NAME, "Immich")
    
    entities = []
    for profile_name, profile_config in profiles.items():
        profile_id = f"{entry.entry_id}_{profile_name}".replace(" ", "_").lower()
        entities.append(ProfileImageCountSensor(coordinator, entry, profile_name, profile_id))
        entities.append(ProfileLastRefreshSensor(coordinator, entry, profile_name, profile_id))
        entities.append(ProfileSearchFilterSensor(coordinator, entry, profile_name, profile_id, profile_config))
        entities.append(ProfileExcludePathsSensor(coordinator, entry, profile_name, profile_id, profile_config))
    
    async_add_entities(entities)


class ProfileImageCountSensor(CoordinatorEntity, SensorEntity):
    """Sensor showing image count for a profile."""

    _attr_has_entity_name = True
    _attr_name = "Image Count"
    _attr_icon = "mdi:image-multiple"

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        profile_name: str,
        profile_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._profile_name = profile_name
        self._profile_id = profile_id
        self._attr_unique_id = f"profile_{profile_id}_image_count"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"profile_{profile_id}")},
        }

    @property
    def native_value(self) -> int | None:
        """Return the image count."""
        if self.coordinator.data and self._profile_name in self.coordinator.data:
            return self.coordinator.data[self._profile_name].get("image_count")
        return None


class ProfileLastRefreshSensor(CoordinatorEntity, SensorEntity):
    """Sensor showing when profile was last refreshed."""

    _attr_has_entity_name = True
    _attr_name = "Last Refresh"
    _attr_icon = "mdi:clock-outline"
    _attr_device_class = "timestamp"

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        profile_name: str,
        profile_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._profile_name = profile_name
        self._profile_id = profile_id
        self._attr_unique_id = f"profile_{profile_id}_last_refresh"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"profile_{profile_id}")},
        }

    @property
    def native_value(self) -> datetime | None:
        """Return the last refresh time."""
        if self.coordinator.last_update_success_time:
            return self.coordinator.last_update_success_time
        return None


class ProfileSearchFilterSensor(CoordinatorEntity, SensorEntity):
    """Sensor showing the search filter/URL for a profile."""

    _attr_has_entity_name = True
    _attr_name = "Search Filter"
    _attr_icon = "mdi:filter"

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        profile_name: str,
        profile_id: str,
        profile_config: dict,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._profile_name = profile_name
        self._profile_id = profile_id
        self._profile_config = profile_config
        self._attr_unique_id = f"profile_{profile_id}_search_filter"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"profile_{profile_id}")},
        }

    @property
    def native_value(self) -> str | None:
        """Return the search filter as string/URL."""
        raw_filter = self._profile_config.get(CONF_SEARCH_FILTER)
        if not raw_filter:
            return None
        
        # If it's already a string (URL), return as-is
        if isinstance(raw_filter, str):
            return raw_filter
        
        # If it's a dict, convert to readable string
        if isinstance(raw_filter, dict):
            import json
            return json.dumps(raw_filter, ensure_ascii=False)
        
        return str(raw_filter)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the parsed filter as attributes."""
        from . import parse_immich_url
        
        raw_filter = self._profile_config.get(CONF_SEARCH_FILTER, {})
        parsed = parse_immich_url(raw_filter)
        
        return {
            "raw_input": raw_filter if isinstance(raw_filter, str) else None,
            "parsed_filter": parsed,
        }


class ProfileExcludePathsSensor(CoordinatorEntity, SensorEntity):
    """Sensor showing the exclude paths for a profile."""

    _attr_has_entity_name = True
    _attr_name = "Exclude Paths"
    _attr_icon = "mdi:folder-remove"

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        profile_name: str,
        profile_id: str,
        profile_config: dict,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._profile_name = profile_name
        self._profile_id = profile_id
        self._profile_config = profile_config
        self._attr_unique_id = f"profile_{profile_id}_exclude_paths"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"profile_{profile_id}")},
        }

    @property
    def native_value(self) -> int:
        """Return the number of exclude paths."""
        exclude_paths = self._profile_config.get(CONF_EXCLUDE_PATHS, [])
        return len(exclude_paths)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the exclude paths as attributes."""
        exclude_paths = self._profile_config.get(CONF_EXCLUDE_PATHS, [])
        return {
            "paths": exclude_paths,
            "patterns": [p.replace("*", "") for p in exclude_paths],
        }
