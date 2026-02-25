"""Shared test fixtures for cal-provider."""

from datetime import datetime, timedelta, timezone, tzinfo

import pytest

from cal_provider.models import CalendarEvent, CalendarInfo, TimeSlot
from cal_provider.provider import CalendarProvider


class MockCalendarProvider(CalendarProvider):
    """Fully in-memory provider for testing."""

    def __init__(self):
        self.calendars = [
            CalendarInfo(id="cal-1", name="Work", description="Work calendar", primary=True),
            CalendarInfo(id="cal-2", name="Personal", description="", primary=False),
        ]
        self.events: list[CalendarEvent] = []
        self._next_id = 1

    async def list_calendars(self) -> list[CalendarInfo]:
        return list(self.calendars)

    async def get_available_slots(
        self, calendar_id, start, end, duration_minutes=60, tz=None
    ) -> list[TimeSlot]:
        from cal_provider.utils import compute_available_slots

        busy = [(e.start, e.end) for e in self.events]
        return compute_available_slots(busy, start, end, duration_minutes, tz=tz)

    async def get_events(self, calendar_id, start, end, tz=None) -> list[CalendarEvent]:
        results = [
            e for e in self.events
            if e.start < end and e.end > start
        ]
        if tz is not None:
            results = [
                CalendarEvent(
                    summary=e.summary,
                    start=e.start.astimezone(tz),
                    end=e.end.astimezone(tz),
                    description=e.description,
                    attendees=list(e.attendees),
                    location=e.location,
                )
                for e in results
            ]
        return results

    async def create_event(self, calendar_id, event) -> dict:
        self.events.append(event)
        event_id = f"mock-evt-{self._next_id}"
        self._next_id += 1
        return {"event_id": event_id, "status": "confirmed"}

    async def cancel_event(self, calendar_id, event_id) -> bool:
        return True


@pytest.fixture
def mock_provider():
    """Return a fresh MockCalendarProvider."""
    return MockCalendarProvider()


@pytest.fixture
def sample_event():
    """Return a sample CalendarEvent."""
    now = datetime(2026, 3, 15, 14, 0, tzinfo=timezone.utc)
    return CalendarEvent(
        summary="Team Meeting",
        start=now,
        end=now + timedelta(hours=1),
        description="Weekly sync",
        attendees=["alice@example.com"],
        location="Room 42",
    )
