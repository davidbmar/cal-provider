"""MCP server exposing calendar provider tools.

Run via CLI entry point: ``cal-provider-mcp``

Configure via environment variables:
    CAL_PROVIDER=google  (or caldav)
    GOOGLE_SERVICE_ACCOUNT_JSON=/path/to/sa.json
    CALDAV_URL=https://caldav.example.com/
    CALDAV_USERNAME=user
    CALDAV_PASSWORD=pass
"""

from __future__ import annotations

import asyncio
from datetime import datetime

from mcp.server.fastmcp import FastMCP

from cal_provider.mcp.config import create_provider_from_env
from cal_provider.models import CalendarEvent

mcp = FastMCP("cal-provider")

# Provider is initialized lazily on first tool call
_provider = None


def _get_provider():
    global _provider
    if _provider is None:
        _provider = create_provider_from_env()
    return _provider


@mcp.tool()
async def list_calendars() -> list[dict]:
    """List all available calendars.

    Returns a list of calendars with id, name, description, and primary flag.
    """
    provider = _get_provider()
    calendars = await provider.list_calendars()
    return [
        {
            "id": cal.id,
            "name": cal.name,
            "description": cal.description,
            "primary": cal.primary,
        }
        for cal in calendars
    ]


@mcp.tool()
async def get_available_slots(
    calendar_id: str,
    start: str,
    end: str,
    duration_minutes: int = 60,
) -> list[dict]:
    """Find available time slots on a calendar.

    Args:
        calendar_id: Calendar identifier (use "primary" for the default).
        start: Start of search window in ISO 8601 format.
        end: End of search window in ISO 8601 format.
        duration_minutes: Minimum slot length in minutes (default 60).

    Returns:
        List of available slots with start and end times.
    """
    provider = _get_provider()
    start_dt = datetime.fromisoformat(start)
    end_dt = datetime.fromisoformat(end)
    slots = await provider.get_available_slots(
        calendar_id, start_dt, end_dt, duration_minutes
    )
    return [
        {"start": s.start.isoformat(), "end": s.end.isoformat()}
        for s in slots
    ]


@mcp.tool()
async def get_events(
    calendar_id: str,
    start: str,
    end: str,
) -> list[dict]:
    """Retrieve events from a calendar in a time range.

    Args:
        calendar_id: Calendar identifier.
        start: Start of range in ISO 8601 format.
        end: End of range in ISO 8601 format.

    Returns:
        List of events with summary, start, end, description, attendees, location.
    """
    provider = _get_provider()
    start_dt = datetime.fromisoformat(start)
    end_dt = datetime.fromisoformat(end)
    events = await provider.get_events(calendar_id, start_dt, end_dt)
    return [
        {
            "summary": e.summary,
            "start": e.start.isoformat(),
            "end": e.end.isoformat(),
            "description": e.description,
            "attendees": e.attendees,
            "location": e.location,
        }
        for e in events
    ]


@mcp.tool()
async def create_event(
    calendar_id: str,
    summary: str,
    start: str,
    end: str,
    description: str = "",
    attendees: list[str] | None = None,
    location: str = "",
) -> dict:
    """Create a new calendar event.

    Args:
        calendar_id: Calendar to create the event on.
        summary: Event title.
        start: Event start time in ISO 8601 format.
        end: Event end time in ISO 8601 format.
        description: Optional event description.
        attendees: Optional list of attendee email addresses.
        location: Optional event location.

    Returns:
        Dict with event_id, status, and optionally html_link.
    """
    provider = _get_provider()
    event = CalendarEvent(
        summary=summary,
        start=datetime.fromisoformat(start),
        end=datetime.fromisoformat(end),
        description=description,
        attendees=attendees or [],
        location=location,
    )
    return await provider.create_event(calendar_id, event)


@mcp.tool()
async def update_event(
    calendar_id: str,
    event_id: str,
    summary: str | None = None,
    start: str | None = None,
    end: str | None = None,
    description: str | None = None,
    location: str | None = None,
) -> dict:
    """Update fields on an existing calendar event.

    Only provided fields are updated — omitted fields remain unchanged.

    Args:
        calendar_id: Calendar that owns the event.
        event_id: Event identifier.
        summary: New event title.
        start: New start time in ISO 8601 format.
        end: New end time in ISO 8601 format.
        description: New description.
        location: New location.

    Returns:
        Updated event data dict.
    """
    provider = _get_provider()
    updates = {}
    if summary is not None:
        updates["summary"] = summary
    if start is not None:
        updates["start"] = datetime.fromisoformat(start)
    if end is not None:
        updates["end"] = datetime.fromisoformat(end)
    if description is not None:
        updates["description"] = description
    if location is not None:
        updates["location"] = location
    return await provider.update_event(calendar_id, event_id, **updates)


@mcp.tool()
async def cancel_event(
    calendar_id: str,
    event_id: str,
) -> dict:
    """Cancel (delete) a calendar event.

    Args:
        calendar_id: Calendar that owns the event.
        event_id: Event identifier.

    Returns:
        Dict with success boolean.
    """
    provider = _get_provider()
    result = await provider.cancel_event(calendar_id, event_id)
    return {"success": result}


def main():
    """CLI entry point for cal-provider-mcp."""
    mcp.run()


if __name__ == "__main__":
    main()
