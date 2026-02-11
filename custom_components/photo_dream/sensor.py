"""Sensor platform for PhotoDream."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .const import (
    DOMAIN,
    CONF_DEVICES,
    CONF_DEVICE_NAME,
    ATTR_CURRENT_IMAGE,
    ATTR_CURRENT_IMAGE_URL,
    ATTR_PROFILE,
    ATTR_LAST_SEEN,
)

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
        
        device_name = device_config.get(CONF_DEVICE_NAME, device_id)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{device_id}")},
            name=f"PhotoDream {device_name}",
            manufacturer="PhotoDream",
            model="Android Tablet",
        )

    @property
    def native_value(self) -> str | None:
        """Return the current image ID."""
        device_data = self._get_device_data()
        return device_data.get(ATTR_CURRENT_IMAGE) if device_data else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        device_data = self._get_device_data()
        if not device_data:
            return {}
        
        return {
            ATTR_CURRENT_IMAGE_URL: device_data.get(ATTR_CURRENT_IMAGE_URL),
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
