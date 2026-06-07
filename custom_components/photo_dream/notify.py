"""Notify platform for PhotoDream.

Provides one ``notify.*`` entity per device as a convenient wrapper for simple
message + title popups. Rich notifications (image, sound, duration, tap callback)
go through the ``photo_dream.notify`` service, since NotifyEntity carries no
extra data fields.
"""
from __future__ import annotations

import logging

from homeassistant.components.notify import NotifyEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .helpers import get_device_info
from .const import ENTRY_TYPE_HUB, CONF_DEVICES, ATTR_MESSAGE, ATTR_TITLE
from . import send_command_to_device

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PhotoDream notify entities from a config entry."""
    if entry.data.get("entry_type") != ENTRY_TYPE_HUB:
        return

    devices = entry.data.get(CONF_DEVICES, {})

    entities = [
        PhotoDreamNotifyEntity(hass, entry, device_id, device_config)
        for device_id, device_config in devices.items()
    ]
    async_add_entities(entities)


class PhotoDreamNotifyEntity(NotifyEntity):
    """Notify entity that shows a popup overlay on a PhotoDream device."""

    _attr_has_entity_name = True
    _attr_name = "Notify"
    _attr_icon = "mdi:message-alert-outline"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device_id: str,
        device_config: dict,
    ) -> None:
        """Initialize the notify entity."""
        self.hass = hass
        self._entry = entry
        self._device_id = device_id
        self._device_config = device_config
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_notify"
        self._attr_device_info = get_device_info(hass, entry, device_id, device_config)

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send a simple notification popup to the device."""
        payload: dict[str, str] = {ATTR_MESSAGE: message}
        if title:
            payload[ATTR_TITLE] = title
        await send_command_to_device(self.hass, self._device_id, "notify", payload)
