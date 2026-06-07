"""Collect and push merged calendar events to PhotoDream devices.

Calendars in Home Assistant are split across multiple ``calendar.*`` entities.
The PhotoDream app expects a single, already-merged and sorted event list pushed
to ``POST http://<ip>:<port>/calendar``. Merging/sorting/colouring happens here.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    CONF_DEVICES,
    CONF_CALENDAR,
    CONF_CALENDAR_MAX_EVENTS,
    CONF_CALENDAR_ENTITIES,
    CONF_CALENDAR_COLORS,
    CONF_CALENDAR_LOOKAHEAD_DAYS,
    DEFAULT_CALENDAR_MAX_EVENTS,
    DEFAULT_CALENDAR_LOOKAHEAD_DAYS,
    CALENDAR_COLOR_PALETTE,
)

_LOGGER = logging.getLogger(__name__)


def _get_hub_devices(hass: HomeAssistant) -> dict[str, dict]:
    """Return the devices dict from the (fresh) hub config entry."""
    hub_data = hass.data.get(DOMAIN, {}).get("hub")
    if not hub_data:
        return {}
    entry_id = hub_data.get("entry_id")
    entry = hass.config_entries.async_get_entry(entry_id) if entry_id else None
    if not entry:
        return {}
    return entry.data.get(CONF_DEVICES, {})


def get_configured_calendar_entities(hass: HomeAssistant) -> list[str]:
    """Union of all calendar entity_ids used by calendar-enabled devices."""
    entities: set[str] = set()
    for device in _get_hub_devices(hass).values():
        if device.get(CONF_CALENDAR):
            entities.update(device.get(CONF_CALENDAR_ENTITIES, []) or [])
    return sorted(entities)


def _event_sort_key(start: str) -> datetime:
    """Parse an ISO start string into a comparable aware UTC datetime."""
    dt = dt_util.parse_datetime(start)
    if dt is None:
        day = dt_util.parse_date(start)
        if day is not None:
            dt = dt_util.start_of_local_day(day)
    if dt is None:
        return dt_util.utcnow()
    if dt.tzinfo is None:
        dt = dt_util.as_local(dt)
    return dt_util.as_utc(dt)


async def async_collect_events(hass: HomeAssistant, device: dict) -> list[dict]:
    """Fetch, merge, colour, sort and trim events for a single device."""
    entities = device.get(CONF_CALENDAR_ENTITIES, []) or []
    if not entities:
        return []

    lookahead = device.get(CONF_CALENDAR_LOOKAHEAD_DAYS, DEFAULT_CALENDAR_LOOKAHEAD_DAYS)
    max_events = device.get(CONF_CALENDAR_MAX_EVENTS, DEFAULT_CALENDAR_MAX_EVENTS)
    colors = device.get(CONF_CALENDAR_COLORS, {}) or {}

    now = dt_util.now()
    end = now + timedelta(days=lookahead)

    try:
        response = await hass.services.async_call(
            "calendar",
            "get_events",
            {
                "entity_id": entities,
                "start_date_time": now.isoformat(),
                "end_date_time": end.isoformat(),
            },
            blocking=True,
            return_response=True,
        )
    except Exception as err:  # noqa: BLE001 - one bad calendar shouldn't kill the push
        _LOGGER.error("calendar.get_events failed for %s: %s", entities, err)
        return []

    response = response or {}
    events: list[dict] = []

    for idx, entity_id in enumerate(entities):
        state = hass.states.get(entity_id)
        cal_name = (
            state.attributes.get("friendly_name", entity_id) if state else entity_id
        )
        color = colors.get(entity_id) or CALENDAR_COLOR_PALETTE[idx % len(CALENDAR_COLOR_PALETTE)]

        entity_events = (response.get(entity_id) or {}).get("events", [])
        for ev in entity_events:
            start = ev.get("start")
            if not start:
                continue
            item = {
                "title": ev.get("summary", ""),
                "start": start,
                # date-only start (no time component) means an all-day event
                "all_day": "T" not in start,
                "calendar": cal_name,
                "color": color,
            }
            if ev.get("end"):
                item["end"] = ev["end"]
            if ev.get("location"):
                item["location"] = ev["location"]
            events.append(item)

    events.sort(key=lambda e: _event_sort_key(e["start"]))
    return events[:max_events]


async def async_push_calendar_to_device(hass: HomeAssistant, device_id: str) -> bool:
    """Push the merged event list to a single device (if calendar is enabled)."""
    devices = _get_hub_devices(hass)
    device = devices.get(device_id)
    if not device or not device.get(CONF_CALENDAR):
        return False

    events = await async_collect_events(hass, device)

    # Imported lazily to avoid a circular import with __init__.
    from . import send_command_to_device

    _LOGGER.debug("Pushing %d calendar events to %s", len(events), device_id)
    return await send_command_to_device(hass, device_id, "calendar", {"events": events})


async def async_push_calendar_all(hass: HomeAssistant) -> None:
    """Push merged calendar events to every calendar-enabled device."""
    for device_id, device in _get_hub_devices(hass).items():
        if device.get(CONF_CALENDAR):
            await async_push_calendar_to_device(hass, device_id)
