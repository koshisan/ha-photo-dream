"""DataUpdateCoordinator for PhotoDream Immich instances."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    ENTRY_TYPE_HUB,
    ENTRY_TYPE_IMMICH,
    CONF_IMMICH_URL,
    CONF_IMMICH_API_KEY,
    CONF_PROFILES,
    CONF_SEARCH_FILTER,
    CONF_DEVICES,
)

_LOGGER = logging.getLogger(__name__)

# Poll interval for checking image counts
SCAN_INTERVAL = timedelta(hours=1)

# Delay between tablet refreshes (seconds)
TABLET_REFRESH_STAGGER = 25


class ImmichCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to poll Immich for profile image counts."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.entry = entry
        self._previous_counts: dict[str, int] = {}
        
        super().__init__(
            hass,
            _LOGGER,
            name=f"PhotoDream Immich ({entry.data.get('immich_name', 'Unknown')})",
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch image counts for all profiles."""
        immich_url = self.entry.data.get(CONF_IMMICH_URL, "").rstrip("/")
        api_key = self.entry.data.get(CONF_IMMICH_API_KEY, "")
        profiles = self.entry.data.get(CONF_PROFILES, {})
        
        if not immich_url or not api_key:
            raise UpdateFailed("Immich URL or API key not configured")
        
        result = {}
        counts_changed = False
        
        for profile_name, profile_config in profiles.items():
            search_filter = profile_config.get(CONF_SEARCH_FILTER, {})
            
            try:
                count = await self._get_image_count(immich_url, api_key, search_filter)
                profile_id = f"{self.entry.entry_id}_{profile_name}".replace(" ", "_").lower()
                
                result[profile_name] = {
                    "image_count": count,
                    "profile_id": profile_id,
                }
                
                # Check if count changed
                old_count = self._previous_counts.get(profile_name)
                if old_count is not None and old_count != count:
                    _LOGGER.info(
                        "Profile '%s' image count changed: %d -> %d",
                        profile_name, old_count, count
                    )
                    counts_changed = True
                
                self._previous_counts[profile_name] = count
                
            except Exception as e:
                _LOGGER.error("Failed to get image count for profile '%s': %s", profile_name, e)
                result[profile_name] = {
                    "image_count": None,
                    "profile_id": f"{self.entry.entry_id}_{profile_name}".replace(" ", "_").lower(),
                    "error": str(e),
                }
        
        # If any count changed, trigger tablet refreshes
        if counts_changed:
            self.hass.async_create_task(self._refresh_all_tablets())
        
        return result

    async def _get_image_count(
        self, immich_url: str, api_key: str, search_filter: dict
    ) -> int:
        """Query Immich API to get image count for a search filter."""
        # Use the search/metadata endpoint with count
        url = f"{immich_url}/api/search/metadata"
        headers = {"x-api-key": api_key, "Content-Type": "application/json"}
        
        # Build search payload
        payload = dict(search_filter) if search_filter else {}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=30,
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        # The response has assets.items array
                        assets = data.get("assets", {})
                        items = assets.get("items", [])
                        total = assets.get("total", len(items))
                        return total
                    else:
                        text = await resp.text()
                        _LOGGER.error("Immich API error %d: %s", resp.status, text)
                        raise UpdateFailed(f"Immich API returned {resp.status}")
        except aiohttp.ClientError as e:
            raise UpdateFailed(f"Cannot connect to Immich: {e}")

    async def _refresh_all_tablets(self) -> None:
        """Refresh all tablets with staggered timing."""
        _LOGGER.info("Image count changed - refreshing all tablets")
        
        # Find the hub entry to get tablet list
        hub_data = self.hass.data.get(DOMAIN, {}).get("hub")
        if not hub_data:
            _LOGGER.warning("No hub found, cannot refresh tablets")
            return
        
        hub_entry = hub_data.get("entry")
        if not hub_entry:
            return
        
        devices = hub_entry.data.get(CONF_DEVICES, {})
        
        # Import here to avoid circular imports
        from . import push_config_to_device
        
        for i, device_id in enumerate(devices.keys()):
            if i > 0:
                # Stagger refreshes
                delay = TABLET_REFRESH_STAGGER + (i * 5)  # 25s, 30s, 35s, etc.
                _LOGGER.debug("Scheduling refresh for %s in %d seconds", device_id, delay)
                self.hass.loop.call_later(
                    delay,
                    lambda did=device_id: self.hass.async_create_task(
                        push_config_to_device(self.hass, did)
                    ),
                )
            else:
                # First tablet immediately
                await push_config_to_device(self.hass, device_id)

    async def async_manual_refresh(self) -> None:
        """Manually trigger a refresh and update tablets if count changed."""
        _LOGGER.info("Manual refresh triggered")
        await self.async_request_refresh()


async def async_get_coordinator(
    hass: HomeAssistant, entry: ConfigEntry
) -> ImmichCoordinator:
    """Get or create coordinator for an Immich entry."""
    coordinators = hass.data[DOMAIN].setdefault("coordinators", {})
    
    if entry.entry_id not in coordinators:
        coordinator = ImmichCoordinator(hass, entry)
        await coordinator.async_config_entry_first_refresh()
        coordinators[entry.entry_id] = coordinator
    
    return coordinators[entry.entry_id]
