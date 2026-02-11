"""Binary sensor platform for PhotoDream."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .helpers import get_device_info

from .const import (
    DOMAIN,
    CONF_DEVICES,
    
    ATTR_LAST_SEEN,
)

_LOGGER = logging.getLogger(__name__)

# Consider device offline if no update for 5 minutes
OFFLINE_THRESHOLD = timedelta(minutes=5)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PhotoDream binary sensors from a config entry."""
    config = entry.data
    devices = config.get(CONF_DEVICES, {})
    
    entities = []
    for device_id, device_config in devices.items():
        entities.append(PhotoDreamOnlineSensor(hass, entry, device_id, device_config))
        entities.append(PhotoDreamActiveSensor(hass, entry, device_id, device_config))
    
    async_add_entities(entities)


class PhotoDreamOnlineSensor(BinarySensorEntity):
    """Binary sensor showing if a PhotoDream device is online."""

    _attr_has_entity_name = True
    _attr_name = "Online"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

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
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_online"
        
        self._attr_device_info = get_device_info(hass, entry, device_id, device_config)

    @property
    def is_on(self) -> bool:
        """Return true if device is online."""
        device_data = self._get_device_data()
        if not device_data:
            return False
        
        # Check if we received a recent update
        last_seen = device_data.get(ATTR_LAST_SEEN)
        if last_seen:
            try:
                last_seen_dt = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
                if datetime.now(last_seen_dt.tzinfo) - last_seen_dt > OFFLINE_THRESHOLD:
                    return False
            except (ValueError, TypeError):
                pass
        
        return device_data.get("online", False)

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


class PhotoDreamActiveSensor(BinarySensorEntity):
    """Binary sensor showing if PhotoDream is actively displaying (in foreground)."""

    _attr_has_entity_name = True
    _attr_name = "Active"
    _attr_device_class = BinarySensorDeviceClass.RUNNING

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
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_active"
        
        self._attr_device_info = get_device_info(hass, entry, device_id, device_config)

    @property
    def is_on(self) -> bool:
        """Return true if PhotoDream is active (displaying)."""
        device_data = self._get_device_data()
        if not device_data:
            return False
        return device_data.get("active", False)

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
