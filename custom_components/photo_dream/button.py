"""Button platform for PhotoDream."""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import (
    DOMAIN,
    ENTRY_TYPE_HUB,
    ENTRY_TYPE_IMMICH,
    CONF_DEVICES,
    CONF_PROFILES,
    CONF_IMMICH_NAME,
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
    entry_type = entry.data.get("entry_type")
    
    if entry_type == ENTRY_TYPE_HUB:
        await async_setup_hub_buttons(hass, entry, async_add_entities)
    elif entry_type == ENTRY_TYPE_IMMICH:
        await async_setup_immich_buttons(hass, entry, async_add_entities)


async def async_setup_hub_buttons(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up tablet buttons for Hub entry."""
    devices = entry.data.get(CONF_DEVICES, {})
    
    entities = []
    for device_id, device_config in devices.items():
        entities.append(PhotoDreamNextImageButton(hass, entry, device_id, device_config))
    
    async_add_entities(entities)


async def async_setup_immich_buttons(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up profile buttons for Immich entry."""
    immich_data = hass.data.get(DOMAIN, {}).get("immich", {}).get(entry.entry_id)
    if not immich_data:
        _LOGGER.error("No Immich data found for entry %s", entry.entry_id)
        return
    
    coordinator = immich_data.get("coordinator")
    if not coordinator:
        _LOGGER.error("No coordinator found for Immich entry %s", entry.entry_id)
        return
    
    profiles = entry.data.get(CONF_PROFILES, {})
    
    entities = []
    for profile_name in profiles:
        profile_id = f"{entry.entry_id}_{profile_name}".replace(" ", "_").lower()
        entities.append(ProfileRefreshButton(coordinator, entry, profile_name, profile_id))
    
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


# ============================================================================
# Profile Buttons
# ============================================================================

class ProfileRefreshButton(CoordinatorEntity, ButtonEntity):
    """Button to manually refresh a profile and trigger tablet updates."""

    _attr_has_entity_name = True
    _attr_name = "Refresh"
    _attr_icon = "mdi:refresh"

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        profile_name: str,
        profile_id: str,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._entry = entry
        self._profile_name = profile_name
        self._profile_id = profile_id
        self._attr_unique_id = f"profile_{profile_id}_refresh"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"profile_{profile_id}")},
        }

    async def async_press(self) -> None:
        """Handle the button press - refresh this profile."""
        _LOGGER.info("Manual refresh requested for profile '%s'", self._profile_name)
        await self.coordinator.async_manual_refresh()
