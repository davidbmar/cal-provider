"""Tests for CalDAVProvider (mocked caldav client)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from cal_provider.exceptions import CalendarNotFoundError
from cal_provider.models import CalendarEvent

# Minimal valid iCalendar data for a single event
SAMPLE_VEVENT_ICAL = """\
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
SUMMARY:Team Standup
DTSTART:20260315T100000Z
DTEND:20260315T103000Z
DESCRIPTION:Daily standup
LOCATION:Room B
ATTENDEE:mailto:dev@example.com
UID:test-uid-001
END:VEVENT
END:VCALENDAR"""


class TestCalDAVProvider:
    @pytest.fixture
    def mock_provider(self):
        """Create a CalDAVProvider with mocked CalDAV client."""
        with patch("cal_provider.providers.caldav_provider.caldav") as mock_caldav:
            mock_client = MagicMock()
            mock_caldav.DAVClient.return_value = mock_client
            mock_principal = MagicMock()
            mock_client.principal.return_value = mock_principal

            # Set up a mock calendar
            mock_cal = MagicMock()
            mock_cal.url = "https://caldav.example.com/cal/work/"
            mock_cal.name = "Work"
            mock_principal.calendars.return_value = [mock_cal]

            from cal_provider.providers.caldav_provider import CalDAVProvider

            provider = CalDAVProvider(
                url="https://caldav.example.com/",
                username="user",
                password="pass",
            )

            # Expose the mock calendar for per-test configuration
            provider._mock_cal = mock_cal
            return provider

    async def test_list_calendars(self, mock_provider):
        calendars = await mock_provider.list_calendars()

        assert len(calendars) == 1
        assert calendars[0].name == "Work"
        assert calendars[0].primary is True  # First calendar is primary

    async def test_get_events(self, mock_provider):
        mock_event = MagicMock()
        mock_event.data = SAMPLE_VEVENT_ICAL
        mock_provider._mock_cal.date_search.return_value = [mock_event]

        start = datetime(2026, 3, 15, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 3, 16, 0, 0, tzinfo=timezone.utc)

        events = await mock_provider.get_events("primary", start, end)

        assert len(events) == 1
        assert events[0].summary == "Team Standup"
        assert events[0].location == "Room B"
        assert events[0].attendees == ["dev@example.com"]

    async def test_get_events_with_tz(self, mock_provider):
        """tz parameter converts event times to target timezone."""
        mock_event = MagicMock()
        mock_event.data = SAMPLE_VEVENT_ICAL  # 10:00 UTC
        mock_provider._mock_cal.date_search.return_value = [mock_event]

        start = datetime(2026, 3, 15, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 3, 16, 0, 0, tzinfo=timezone.utc)

        chicago = ZoneInfo("America/Chicago")
        events = await mock_provider.get_events("primary", start, end, tz=chicago)

        assert events[0].start.hour == 5  # 10:00 UTC → 5:00 AM CDT

    async def test_get_available_slots(self, mock_provider):
        """Events on calendar should create busy intervals."""
        mock_event = MagicMock()
        mock_event.data = SAMPLE_VEVENT_ICAL  # 10:00-10:30
        mock_provider._mock_cal.date_search.return_value = [mock_event]

        start = datetime(2026, 3, 15, 9, 0, tzinfo=timezone.utc)
        end = datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc)

        slots = await mock_provider.get_available_slots("primary", start, end, 30)

        # 9:00-10:00 (free), 10:00-10:30 (busy), 10:30-12:00 (free)
        assert len(slots) == 2
        assert slots[0].start.hour == 9
        assert slots[0].end.hour == 10
        assert slots[1].start.hour == 10
        assert slots[1].start.minute == 30
        assert slots[1].end.hour == 12

    async def test_get_available_slots_empty(self, mock_provider):
        """Empty calendar → one big slot."""
        mock_provider._mock_cal.date_search.return_value = []

        start = datetime(2026, 3, 15, 9, 0, tzinfo=timezone.utc)
        end = datetime(2026, 3, 15, 18, 0, tzinfo=timezone.utc)

        slots = await mock_provider.get_available_slots("primary", start, end, 30)

        assert len(slots) == 1
        assert slots[0].start == start
        assert slots[0].end == end

    async def test_get_available_slots_with_tz(self, mock_provider):
        """tz parameter converts slot times to target timezone."""
        mock_provider._mock_cal.date_search.return_value = []

        start = datetime(2026, 3, 15, 14, 0, tzinfo=timezone.utc)
        end = datetime(2026, 3, 15, 20, 0, tzinfo=timezone.utc)

        chicago = ZoneInfo("America/Chicago")
        slots = await mock_provider.get_available_slots(
            "primary", start, end, 30, tz=chicago
        )

        assert len(slots) == 1
        assert slots[0].start.hour == 9  # 14 UTC → 9 AM CDT

    async def test_create_event(self, mock_provider):
        mock_created = MagicMock()
        mock_created.url = "https://caldav.example.com/cal/work/new-event.ics"
        mock_provider._mock_cal.save_event.return_value = mock_created

        now = datetime(2026, 3, 15, 14, 0, tzinfo=timezone.utc)
        event = CalendarEvent(
            summary="Viewing",
            start=now,
            end=now + timedelta(minutes=30),
            attendees=["visitor@example.com"],
            location="456 Oak Ave",
        )

        result = await mock_provider.create_event("primary", event)

        assert result["event_id"] == "https://caldav.example.com/cal/work/new-event.ics"
        assert result["status"] == "confirmed"
        # Verify save_event was called with iCalendar data
        mock_provider._mock_cal.save_event.assert_called_once()

    async def test_cancel_event(self, mock_provider):
        mock_event = MagicMock()
        mock_provider._mock_cal.event_by_url.return_value = mock_event

        result = await mock_provider.cancel_event(
            "primary", "https://caldav.example.com/cal/work/evt.ics"
        )

        assert result is True
        mock_event.delete.assert_called_once()

    async def test_cancel_event_failure(self, mock_provider):
        mock_provider._mock_cal.event_by_url.side_effect = Exception("Not found")

        result = await mock_provider.cancel_event("primary", "bad-url")
        assert result is False

    async def test_calendar_not_found_raises(self, mock_provider):
        """Looking up a non-existent calendar raises CalendarNotFoundError."""
        with pytest.raises(CalendarNotFoundError, match="Calendar not found"):
            await mock_provider.get_events(
                "nonexistent-cal",
                datetime(2026, 3, 15, 0, 0, tzinfo=timezone.utc),
                datetime(2026, 3, 16, 0, 0, tzinfo=timezone.utc),
            )

    async def test_no_calendars_raises(self, mock_provider):
        """No calendars on account raises CalendarNotFoundError."""
        mock_provider._principal.calendars.return_value = []

        with pytest.raises(CalendarNotFoundError, match="No calendars found"):
            await mock_provider.get_events(
                "primary",
                datetime(2026, 3, 15, 0, 0, tzinfo=timezone.utc),
                datetime(2026, 3, 16, 0, 0, tzinfo=timezone.utc),
            )
