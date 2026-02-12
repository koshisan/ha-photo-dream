"""DataUpdateCoordinator for PhotoDream Immich instances."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

import aiohttp
from homeassistant.util import dt as dt_util

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
        self.last_update_success_time: datetime | None = None
        
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
        
        # Update success time
        self.last_update_success_time = dt_util.utcnow()
        
        return result

    async def _get_image_count(
        self, immich_url: str, api_key: str, search_filter: dict
    ) -> int:
        """Query Immich API to get image count for a search filter.
        
        Immich doesn't return true total count, so we paginate to count.
        Uses /api/search/smart if query is present, otherwise /api/search/metadata.
        """
        headers = {"x-api-key": api_key, "Content-Type": "application/json"}
        
        # Choose endpoint based on whether we have a semantic query
        has_query = search_filter and search_filter.get("query")
        endpoint = "smart" if has_query else "metadata"
        url = f"{immich_url}/api/search/{endpoint}"
        
        total_count = 0
        page = 1
        page_size = 1000  # Max supported by Immich
        
        try:
            async with aiohttp.ClientSession() as session:
                while True:
                    payload = dict(search_filter) if search_filter else {}
                    payload["size"] = page_size
                    payload["page"] = page
                    payload["type"] = payload.get("type", "IMAGE")
                    
                    async with session.post(
                        url,
                        headers=headers,
                        json=payload,
                        timeout=30,
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            assets = data.get("assets", {})
                            items = assets.get("items", [])
                            count = len(items)
                            total_count += count
                            next_page = assets.get("nextPage")
                            
                            _LOGGER.debug(
                                "Image count page %d: got %d, total so far: %d, nextPage: %s",
                                page, count, total_count, next_page
                            )
                            
                            # Stop if no more pages
                            if not next_page or count == 0:
                                break
                            
                            page += 1
                            
                            # Safety limit
                            if page > 100:
                                _LOGGER.warning("Image count pagination limit reached")
                                break
                        else:
                            text = await resp.text()
                            _LOGGER.error("Immich API error %d: %s", resp.status, text)
                            raise UpdateFailed(f"Immich API returned {resp.status}")
                
                _LOGGER.debug("Total image count for filter: %d", total_count)
                return total_count
                
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
