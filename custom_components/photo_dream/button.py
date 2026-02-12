"""Button platform for PhotoDream."""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import (
    DOMAIN,
    ENTRY_TYPE_HUB,
    CONF_DEVICES,
)
from .helpers import get_device_info
from . import send_command_to_device

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PhotoDream buttons from a config entry."""
    # Only create entities for Hub entries
    if entry.data.get("entry_type") != ENTRY_TYPE_HUB:
        return
    
    devices = entry.data.get(CONF_DEVICES, {})
    
    entities = []
    for device_id, device_config in devices.items():
        entities.append(PhotoDreamNextImageButton(hass, entry, device_id, device_config))
    
    async_add_entities(entities)


class PhotoDreamNextImageButton(ButtonEntity):
    """Button to advance to next image on a PhotoDream device."""

    _attr_has_entity_name = True
    _attr_name = "Next Image"
    _attr_icon = "mdi:skip-next"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device_id: str,
        device_config: dict,
    ) -> None:
        """Initialize the button."""
        self.hass = hass
        self._entry = entry
        self._device_id = device_id
        self._device_config = device_config
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_next_image"
        self._attr_device_info = get_device_info(hass, entry, device_id, device_config)

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.info("Next image requested for device %s", self._device_id)
        await send_command_to_device(self.hass, self._device_id, "next")
