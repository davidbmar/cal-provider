"""CalDAV calendar provider implementation.

Supports any CalDAV-compliant server: iCloud, Nextcloud, Fastmail,
Radicale, Baikal, etc. Uses HTTP Basic authentication.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, tzinfo
from functools import partial
from typing import Any

import caldav
from icalendar import Calendar as iCalendar
from icalendar import Event as iEvent

from cal_provider.exceptions import CalendarNotFoundError, EventNotFoundError
from cal_provider.models import CalendarEvent, CalendarInfo, TimeSlot
from cal_provider.provider import CalendarProvider
from cal_provider.utils import compute_available_slots

logger = logging.getLogger(__name__)


class CalDAVProvider(CalendarProvider):
    """CalendarProvider backed by a CalDAV server.

    Args:
        url: CalDAV server URL (e.g. ``https://caldav.icloud.com/``).
        username: Account username.
        password: Account password (or app-specific password for iCloud).
    """

    def __init__(self, url: str, username: str, password: str) -> None:
        self._client = caldav.DAVClient(
            url=url, username=username, password=password
        )
        self._principal = self._client.principal()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _run_in_executor(self, func, *args, **kwargs) -> Any:
        """Run a synchronous CalDAV call in the default thread pool."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, partial(func, *args, **kwargs)
        )

    def _get_calendar(self, calendar_id: str) -> caldav.Calendar:
        """Resolve a calendar_id to a caldav.Calendar object.

        If ``calendar_id`` is ``"primary"``, returns the first calendar.
        Otherwise matches by calendar URL or display name.
        """
        calendars = self._principal.calendars()
        if not calendars:
            raise CalendarNotFoundError("No calendars found on this CalDAV account")

        if calendar_id == "primary":
            return calendars[0]

        for cal in calendars:
            if calendar_id in (str(cal.url), cal.name):
                return cal

        raise CalendarNotFoundError(f"Calendar not found: {calendar_id}")

    @staticmethod
    def _parse_vevent(vevent) -> tuple[datetime, datetime, dict]:
        """Extract start, end, and metadata from a VEVENT component.

        Returns:
            Tuple of (start_dt, end_dt, metadata_dict).
        """
        dtstart = vevent.get("DTSTART")
        dtend = vevent.get("DTEND")

        start_dt = dtstart.dt if dtstart else datetime.min.replace(tzinfo=timezone.utc)
        end_dt = dtend.dt if dtend else start_dt

        # date objects (all-day events) → datetime at midnight UTC
        if not isinstance(start_dt, datetime):
            start_dt = datetime.combine(start_dt, datetime.min.time(), tzinfo=timezone.utc)
        if not isinstance(end_dt, datetime):
            end_dt = datetime.combine(end_dt, datetime.min.time(), tzinfo=timezone.utc)

        # Ensure timezone-aware
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=timezone.utc)

        attendees_raw = vevent.get("ATTENDEE", [])
        if not isinstance(attendees_raw, list):
            attendees_raw = [attendees_raw]
        attendees = []
        for a in attendees_raw:
            email = str(a).replace("mailto:", "").replace("MAILTO:", "")
            if email:
                attendees.append(email)

        metadata = {
            "summary": str(vevent.get("SUMMARY", "")),
            "description": str(vevent.get("DESCRIPTION", "")),
            "location": str(vevent.get("LOCATION", "")),
            "attendees": attendees,
            "uid": str(vevent.get("UID", "")),
        }

        return start_dt, end_dt, metadata

    # ------------------------------------------------------------------
    # CalendarProvider interface
    # ------------------------------------------------------------------

    async def list_calendars(self) -> list[CalendarInfo]:
        """List all calendars on the CalDAV account."""
        calendars = await self._run_in_executor(self._principal.calendars)
        result = []
        for i, cal in enumerate(calendars):
            result.append(
                CalendarInfo(
                    id=str(cal.url),
                    name=cal.name or str(cal.url),
                    description="",
                    primary=(i == 0),
                )
            )
        return result

    async def get_available_slots(
        self,
        calendar_id: str,
        start: datetime,
        end: datetime,
        duration_minutes: int = 60,
        tz: tzinfo | None = None,
    ) -> list[TimeSlot]:
        """Fetch events and compute available gaps."""
        cal = await self._run_in_executor(self._get_calendar, calendar_id)
        events = await self._run_in_executor(
            cal.date_search, start, end
        )

        busy: list[tuple[datetime, datetime]] = []
        for event in events:
            ical = iCalendar.from_ical(event.data)
            for component in ical.walk():
                if component.name == "VEVENT":
                    evt_start, evt_end, _ = self._parse_vevent(component)
                    busy.append((evt_start, evt_end))

        return compute_available_slots(busy, start, end, duration_minutes, tz=tz)

    async def get_events(
        self,
        calendar_id: str,
        start: datetime,
        end: datetime,
        tz: tzinfo | None = None,
    ) -> list[CalendarEvent]:
        """Retrieve events from the CalDAV calendar."""
        cal = await self._run_in_executor(self._get_calendar, calendar_id)
        raw_events = await self._run_in_executor(
            cal.date_search, start, end
        )

        result = []
        for event in raw_events:
            ical = iCalendar.from_ical(event.data)
            for component in ical.walk():
                if component.name == "VEVENT":
                    evt_start, evt_end, meta = self._parse_vevent(component)
                    if tz is not None:
                        evt_start = evt_start.astimezone(tz)
                        evt_end = evt_end.astimezone(tz)
                    result.append(
                        CalendarEvent(
                            summary=meta["summary"],
                            start=evt_start,
                            end=evt_end,
                            description=meta["description"],
                            attendees=meta["attendees"],
                            location=meta["location"],
                        )
                    )
        return result

    async def create_event(
        self, calendar_id: str, event: CalendarEvent
    ) -> dict:
        """Create an event on the CalDAV calendar using iCalendar format."""
        cal = await self._run_in_executor(self._get_calendar, calendar_id)

        vevent = iEvent()
        vevent.add("summary", event.summary)
        vevent.add("dtstart", event.start)
        vevent.add("dtend", event.end)
        if event.description:
            vevent.add("description", event.description)
        if event.location:
            vevent.add("location", event.location)
        for email in event.attendees:
            vevent.add("attendee", f"mailto:{email}")

        ical = iCalendar()
        ical.add("prodid", "-//cal-provider//EN")
        ical.add("version", "2.0")
        ical.add_component(vevent)

        created = await self._run_in_executor(
            cal.save_event, ical.to_ical().decode("utf-8")
        )

        event_id = str(created.url) if created else ""
        logger.info("Created CalDAV event %s on %s", event_id, calendar_id)

        return {
            "event_id": event_id,
            "status": "confirmed",
        }

    async def cancel_event(
        self, calendar_id: str, event_id: str
    ) -> bool:
        """Delete an event from the CalDAV calendar."""
        try:
            cal = await self._run_in_executor(self._get_calendar, calendar_id)
            event = await self._run_in_executor(
                cal.event_by_url, event_id
            )
            await self._run_in_executor(event.delete)
            logger.info(
                "Cancelled CalDAV event %s on %s", event_id, calendar_id
            )
            return True
        except (CalendarNotFoundError, EventNotFoundError):
            raise
        except caldav.error.NotFoundError as exc:
            raise EventNotFoundError(
                f"Event not found: {event_id}"
            ) from exc
        except Exception:
            logger.exception(
                "Failed to cancel CalDAV event %s on %s",
                event_id,
                calendar_id,
            )
            return False
