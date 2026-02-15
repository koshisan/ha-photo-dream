"""Update platform for PhotoDream."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import aiohttp

from homeassistant.components.update import (
    UpdateEntity,
    UpdateEntityFeature,
    UpdateDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    ENTRY_TYPE_HUB,
    CONF_DEVICES,
    CONF_DEVICE_IP,
    CONF_DEVICE_PORT,
    DEFAULT_PORT,
    ATTR_APP_VERSION,
    GITHUB_API_RELEASES,
)
from .helpers import get_device_info

_LOGGER = logging.getLogger(__name__)

# Cache release info for 1 hour
SCAN_INTERVAL = timedelta(hours=1)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PhotoDream update entities from a config entry."""
    entry_type = entry.data.get("entry_type")
    
    if entry_type != ENTRY_TYPE_HUB:
        return
    
    devices = entry.data.get(CONF_DEVICES, {})
    
    entities = []
    for device_id, device_config in devices.items():
        entities.append(PhotoDreamUpdateEntity(hass, entry, device_id, device_config))
    
    async_add_entities(entities)


class PhotoDreamUpdateEntity(UpdateEntity):
    """Update entity for a PhotoDream tablet."""

    _attr_has_entity_name = True
    _attr_name = "Firmware"
    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL
        | UpdateEntityFeature.RELEASE_NOTES
    )

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device_id: str,
        device_config: dict,
    ) -> None:
        """Initialize the update entity."""
        self.hass = hass
        self._entry = entry
        self._device_id = device_id
        self._device_config = device_config
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_update"
        self._attr_device_info = get_device_info(hass, entry, device_id, device_config)
        
        # Cached release info
        self._latest_version: str | None = None
        self._release_notes: str | None = None
        self._apk_url: str | None = None
        self._release_url: str | None = None

    def _get_device_data(self) -> dict | None:
        """Get device data from hass.data."""
        hub_data = self.hass.data.get(DOMAIN, {}).get("hub")
        if not hub_data:
            return None
        return hub_data.get("devices", {}).get(self._device_id)

    @property
    def installed_version(self) -> str | None:
        """Return the installed version."""
        device_data = self._get_device_data()
        if device_data:
            return device_data.get(ATTR_APP_VERSION)
        return None

    @property
    def latest_version(self) -> str | None:
        """Return the latest version."""
        return self._latest_version

    @property
    def release_url(self) -> str | None:
        """Return the release URL."""
        return self._release_url

    async def async_release_notes(self) -> str | None:
        """Return the release notes."""
        return self._release_notes

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        # Listen for device updates
        self.async_on_remove(
            self.hass.bus.async_listen(
                f"{DOMAIN}_device_update",
                self._handle_device_update,
            )
        )
        # Fetch initial release info
        await self._fetch_latest_release()

    @callback
    def _handle_device_update(self, event) -> None:
        """Handle device update event."""
        if event.data.get("device_id") == self._device_id:
            self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the entity."""
        await self._fetch_latest_release()

    async def _fetch_latest_release(self) -> None:
        """Fetch the latest release info from GitHub."""
        try:
            session = async_get_clientsession(self.hass)
            async with session.get(
                GITHUB_API_RELEASES,
                headers={"Accept": "application/vnd.github.v3+json"},
                timeout=30,
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    
                    # Parse version from tag (e.g., "v1.2.0" -> "1.2.0")
                    tag = data.get("tag_name", "")
                    self._latest_version = tag.lstrip("v")
                    
                    # Get release notes
                    self._release_notes = data.get("body", "")
                    
                    # Get release URL
                    self._release_url = data.get("html_url")
                    
                    # Find release APK asset (prefer -release.apk over -debug.apk)
                    for asset in data.get("assets", []):
                        name = asset.get("name", "")
                        if name.endswith("-release.apk"):
                            self._apk_url = asset.get("browser_download_url")
                            break
                    # Fallback: any .apk if no -release.apk found
                    if not self._apk_url:
                        for asset in data.get("assets", []):
                            if asset.get("name", "").endswith(".apk"):
                                self._apk_url = asset.get("browser_download_url")
                                break
                    
                    _LOGGER.debug(
                        "Latest release: %s, APK: %s",
                        self._latest_version,
                        self._apk_url,
                    )
                else:
                    _LOGGER.warning("Failed to fetch release: %d", resp.status)
        except Exception as e:
            _LOGGER.error("Error fetching release info: %s", e)

    async def async_install(
        self,
        version: str | None,
        backup: bool,
        **kwargs: Any,
    ) -> None:
        """Install the update (push APK to device)."""
        if not self._apk_url:
            _LOGGER.error("No APK URL available")
            return
        
        device_ip = self._device_config.get(CONF_DEVICE_IP)
        device_port = self._device_config.get(CONF_DEVICE_PORT, DEFAULT_PORT)
        
        if not device_ip:
            _LOGGER.error("No IP configured for device %s", self._device_id)
            return
        
        url = f"http://{device_ip}:{device_port}/prepare-update"
        
        try:
            session = async_get_clientsession(self.hass)
            async with session.post(
                url,
                json={
                    "apk_url": self._apk_url,
                    "version": self._latest_version,
                },
                timeout=60,  # APK download might take a while
            ) as resp:
                if resp.status == 200:
                    _LOGGER.info(
                        "Update prepared for %s: %s",
                        self._device_id,
                        self._latest_version,
                    )
                else:
                    text = await resp.text()
                    _LOGGER.error(
                        "Failed to prepare update for %s: %d - %s",
                        self._device_id,
                        resp.status,
                        text,
                    )
        except Exception as e:
            _LOGGER.error("Error preparing update for %s: %s", self._device_id, e)
