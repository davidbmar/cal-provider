"""Google Calendar provider implementation.

Uses a Google Cloud service account to interact with the Calendar API v3.
The service account JSON key path can be provided directly or read from
the ``GOOGLE_SERVICE_ACCOUNT_JSON`` environment variable.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone, tzinfo
from functools import partial
from typing import Any

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from cal_provider.exceptions import (
    AuthenticationError,
    CalendarNotFoundError,
    EventNotFoundError,
    PermissionError as CalendarPermissionError,
)
from cal_provider.models import CalendarEvent, CalendarInfo, TimeSlot
from cal_provider.provider import CalendarProvider
from cal_provider.utils import compute_available_slots

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]


class GoogleCalendarProvider(CalendarProvider):
    """CalendarProvider backed by Google Calendar API v3."""

    def __init__(
        self,
        service_account_path: str | None = None,
        send_updates: str = "none",
    ) -> None:
        sa_path = service_account_path or os.environ.get(
            "GOOGLE_SERVICE_ACCOUNT_JSON", ""
        )
        if not sa_path:
            raise AuthenticationError(
                "Google service account JSON path must be provided via "
                "constructor argument or GOOGLE_SERVICE_ACCOUNT_JSON env var."
            )
        self._send_updates = send_updates
        try:
            self._credentials = Credentials.from_service_account_file(
                sa_path, scopes=SCOPES
            )
        except Exception as exc:
            raise AuthenticationError(
                f"Failed to load service account credentials: {exc}"
            ) from exc
        self._service = build(
            "calendar", "v3", credentials=self._credentials
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _run_in_executor(self, func, *args, **kwargs) -> Any:
        """Run a synchronous Google API call in the default thread pool."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, partial(func, *args, **kwargs)
        )

    @staticmethod
    def _to_rfc3339(dt: datetime) -> str:
        """Convert a datetime to an RFC 3339 string with timezone."""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()

    # ------------------------------------------------------------------
    # CalendarProvider interface
    # ------------------------------------------------------------------

    async def list_calendars(self) -> list[CalendarInfo]:
        """List all calendars accessible to the service account."""
        from googleapiclient.errors import HttpError

        try:
            result = await self._run_in_executor(
                self._service.calendarList().list().execute
            )
        except HttpError as exc:
            if exc.resp.status == 401:
                raise AuthenticationError(str(exc)) from exc
            raise
        calendars = []
        for item in result.get("items", []):
            calendars.append(
                CalendarInfo(
                    id=item["id"],
                    name=item.get("summary", item["id"]),
                    description=item.get("description", ""),
                    primary=item.get("primary", False),
                )
            )
        return calendars

    async def get_available_slots(
        self,
        calendar_id: str,
        start: datetime,
        end: datetime,
        duration_minutes: int = 60,
        tz: tzinfo | None = None,
    ) -> list[TimeSlot]:
        """Query Google freebusy API and derive available slots."""
        from googleapiclient.errors import HttpError

        body = {
            "timeMin": self._to_rfc3339(start),
            "timeMax": self._to_rfc3339(end),
            "items": [{"id": calendar_id}],
        }

        try:
            response = await self._run_in_executor(
                self._service.freebusy().query(body=body).execute
            )
        except HttpError as exc:
            if exc.resp.status == 404:
                raise CalendarNotFoundError(
                    f"Calendar not found: {calendar_id}"
                ) from exc
            raise

        busy_intervals: list[dict] = (
            response.get("calendars", {})
            .get(calendar_id, {})
            .get("busy", [])
        )

        busy: list[tuple[datetime, datetime]] = []
        for interval in busy_intervals:
            b_start = datetime.fromisoformat(interval["start"])
            b_end = datetime.fromisoformat(interval["end"])
            busy.append((b_start, b_end))

        return compute_available_slots(busy, start, end, duration_minutes, tz=tz)

    async def get_events(
        self,
        calendar_id: str,
        start: datetime,
        end: datetime,
        tz: tzinfo | None = None,
    ) -> list[CalendarEvent]:
        """Retrieve events from Google Calendar in a time range."""
        from googleapiclient.errors import HttpError

        try:
            result = await self._run_in_executor(
                self._service.events()
                .list(
                    calendarId=calendar_id,
                    timeMin=self._to_rfc3339(start),
                    timeMax=self._to_rfc3339(end),
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute
            )
        except HttpError as exc:
            if exc.resp.status == 404:
                raise CalendarNotFoundError(
                    f"Calendar not found: {calendar_id}"
                ) from exc
            raise

        events = []
        for item in result.get("items", []):
            event_start = item.get("start", {})
            event_end = item.get("end", {})
            # Events can have dateTime (timed) or date (all-day)
            start_dt = datetime.fromisoformat(
                event_start.get("dateTime", event_start.get("date", ""))
            )
            end_dt = datetime.fromisoformat(
                event_end.get("dateTime", event_end.get("date", ""))
            )
            if tz is not None:
                start_dt = start_dt.astimezone(tz)
                end_dt = end_dt.astimezone(tz)
            attendee_emails = [
                a["email"] for a in item.get("attendees", [])
            ]
            events.append(
                CalendarEvent(
                    summary=item.get("summary", ""),
                    start=start_dt,
                    end=end_dt,
                    description=item.get("description", ""),
                    attendees=attendee_emails,
                    location=item.get("location", ""),
                )
            )
        return events

    async def create_event(
        self, calendar_id: str, event: CalendarEvent
    ) -> dict:
        """Insert an event into the Google Calendar."""
        from googleapiclient.errors import HttpError

        body: dict[str, Any] = {
            "summary": event.summary,
            "start": {"dateTime": self._to_rfc3339(event.start)},
            "end": {"dateTime": self._to_rfc3339(event.end)},
        }
        if event.description:
            body["description"] = event.description
        if event.location:
            body["location"] = event.location
        if event.attendees:
            body["attendees"] = [
                {"email": addr} for addr in event.attendees
            ]

        try:
            result = await self._run_in_executor(
                self._service.events()
                .insert(
                    calendarId=calendar_id,
                    body=body,
                    sendUpdates=self._send_updates,
                )
                .execute
            )
        except HttpError as exc:
            if exc.resp.status == 403:
                raise CalendarPermissionError(
                    f"Permission denied creating event on {calendar_id}: {exc}"
                ) from exc
            if exc.resp.status == 404:
                raise CalendarNotFoundError(
                    f"Calendar not found: {calendar_id}"
                ) from exc
            raise

        logger.info("Created event %s on calendar %s", result["id"], calendar_id)

        return {
            "event_id": result["id"],
            "html_link": result.get("htmlLink", ""),
            "status": result.get("status", "confirmed"),
        }

    async def cancel_event(
        self, calendar_id: str, event_id: str
    ) -> bool:
        """Delete an event from Google Calendar."""
        from googleapiclient.errors import HttpError

        try:
            await self._run_in_executor(
                self._service.events()
                .delete(calendarId=calendar_id, eventId=event_id)
                .execute
            )
            logger.info(
                "Cancelled event %s on calendar %s", event_id, calendar_id
            )
            return True
        except HttpError as exc:
            if exc.resp.status == 404:
                raise EventNotFoundError(
                    f"Event not found: {event_id}"
                ) from exc
            logger.exception(
                "Failed to cancel event %s on calendar %s",
                event_id,
                calendar_id,
            )
            return False
        except Exception:
            logger.exception(
                "Failed to cancel event %s on calendar %s",
                event_id,
                calendar_id,
            )
            return False
