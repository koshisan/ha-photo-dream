"""Sensor platform for PhotoDream."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    CONF_DEVICES,
    ATTR_CURRENT_IMAGE,
    ATTR_CURRENT_IMAGE_URL,
    ATTR_PROFILE,
    ATTR_LAST_SEEN,
    ATTR_MAC_ADDRESS,
    ATTR_IP_ADDRESS,
    ATTR_DISPLAY_WIDTH,
    ATTR_DISPLAY_HEIGHT,
)
from .helpers import get_device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PhotoDream sensors from a config entry."""
    config = entry.data
    devices = config.get(CONF_DEVICES, {})
    
    entities = []
    for device_id, device_config in devices.items():
        entities.append(PhotoDreamCurrentImageSensor(hass, entry, device_id, device_config))
        entities.append(PhotoDreamMacAddressSensor(hass, entry, device_id, device_config))
        entities.append(PhotoDreamIpAddressSensor(hass, entry, device_id, device_config))
        entities.append(PhotoDreamResolutionSensor(hass, entry, device_id, device_config))
    
    async_add_entities(entities)


class PhotoDreamCurrentImageSensor(SensorEntity):
    """Sensor showing current image on a PhotoDream device."""

    _attr_has_entity_name = True
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
        self.hass = hass
        self._entry = entry
        self._device_id = device_id
        self._device_config = device_config
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_current_image"
        self._attr_device_info = get_device_info(hass, entry, device_id, device_config)

    @property
    def native_value(self) -> str | None:
        """Return the Immich web URL for the current image.
        
        Clicking this URL opens the photo in Immich's web interface.
        """
        device_data = self._get_device_data()
        if not device_data:
            return None
        
        image_id = device_data.get(ATTR_CURRENT_IMAGE)
        if not image_id:
            return None
        
        # Get Immich base URL from config
        entry_data = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id, {})
        config = entry_data.get("config", {})
        immich_url = config.get("immich_url", "").rstrip("/")
        
        if immich_url:
            return f"{immich_url}/photos/{image_id}"
        return image_id

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


class PhotoDreamMacAddressSensor(SensorEntity):
    """Sensor showing MAC address of a PhotoDream device."""

    _attr_has_entity_name = True
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
        self.hass = hass
        self._entry = entry
        self._device_id = device_id
        self._device_config = device_config
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_mac_address"
        self._attr_device_info = get_device_info(hass, entry, device_id, device_config)

    @property
    def native_value(self) -> str | None:
        """Return the MAC address."""
        device_data = self._get_device_data()
        return device_data.get(ATTR_MAC_ADDRESS) if device_data else None

    def _get_device_data(self) -> dict | None:
        entry_data = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id, {})
        return entry_data.get("devices", {}).get(self._device_id)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self.hass.bus.async_listen(f"{DOMAIN}_device_update", self._handle_update)
        )

    @callback
    def _handle_update(self, event) -> None:
        if event.data.get("device_id") == self._device_id:
            self.async_write_ha_state()


class PhotoDreamIpAddressSensor(SensorEntity):
    """Sensor showing IP address of a PhotoDream device."""

    _attr_has_entity_name = True
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
        self.hass = hass
        self._entry = entry
        self._device_id = device_id
        self._device_config = device_config
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_ip_address"
        self._attr_device_info = get_device_info(hass, entry, device_id, device_config)

    @property
    def native_value(self) -> str | None:
        """Return the IP address."""
        device_data = self._get_device_data()
        return device_data.get(ATTR_IP_ADDRESS) if device_data else None

    def _get_device_data(self) -> dict | None:
        entry_data = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id, {})
        return entry_data.get("devices", {}).get(self._device_id)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self.hass.bus.async_listen(f"{DOMAIN}_device_update", self._handle_update)
        )

    @callback
    def _handle_update(self, event) -> None:
        if event.data.get("device_id") == self._device_id:
            self.async_write_ha_state()


class PhotoDreamResolutionSensor(SensorEntity):
    """Sensor showing display resolution of a PhotoDream device."""

    _attr_has_entity_name = True
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
        self.hass = hass
        self._entry = entry
        self._device_id = device_id
        self._device_config = device_config
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_resolution"
        self._attr_device_info = get_device_info(hass, entry, device_id, device_config)

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

    def _get_device_data(self) -> dict | None:
        entry_data = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id, {})
        return entry_data.get("devices", {}).get(self._device_id)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self.hass.bus.async_listen(f"{DOMAIN}_device_update", self._handle_update)
        )

    @callback
    def _handle_update(self, event) -> None:
        if event.data.get("device_id") == self._device_id:
            self.async_write_ha_state()
