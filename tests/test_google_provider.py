"""Tests for GoogleCalendarProvider (mocked Google API)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from cal_provider.models import CalendarEvent


class TestGoogleCalendarProvider:
    @pytest.fixture
    def mock_provider(self):
        """Create a GoogleCalendarProvider with mocked Google APIs."""
        with patch(
            "cal_provider.providers.google.Credentials"
        ) as mock_creds, patch(
            "cal_provider.providers.google.build"
        ) as mock_build:
            mock_creds.from_service_account_file.return_value = MagicMock()

            from cal_provider.providers.google import GoogleCalendarProvider

            provider = GoogleCalendarProvider(
                service_account_path="/fake/path.json"
            )
            provider._service = mock_build.return_value
            return provider

    async def test_list_calendars(self, mock_provider):
        mock_provider._service.calendarList.return_value.list.return_value.execute.return_value = {
            "items": [
                {"id": "primary", "summary": "Main", "primary": True},
                {"id": "work@group", "summary": "Work"},
            ]
        }

        calendars = await mock_provider.list_calendars()

        assert len(calendars) == 2
        assert calendars[0].id == "primary"
        assert calendars[0].primary is True
        assert calendars[1].name == "Work"

    async def test_get_available_slots_empty_calendar(self, mock_provider):
        """Fully free calendar → one big slot."""
        start = datetime(2026, 3, 15, 9, 0, tzinfo=timezone.utc)
        end = datetime(2026, 3, 15, 18, 0, tzinfo=timezone.utc)

        mock_provider._service.freebusy.return_value.query.return_value.execute.return_value = {
            "calendars": {"primary": {"busy": []}}
        }

        slots = await mock_provider.get_available_slots("primary", start, end, 30)

        assert len(slots) == 1
        assert slots[0].start == start
        assert slots[0].end == end

    async def test_get_available_slots_with_busy(self, mock_provider):
        """Busy blocks should create gaps."""
        start = datetime(2026, 3, 15, 9, 0, tzinfo=timezone.utc)
        end = datetime(2026, 3, 15, 18, 0, tzinfo=timezone.utc)

        mock_provider._service.freebusy.return_value.query.return_value.execute.return_value = {
            "calendars": {
                "primary": {
                    "busy": [
                        {
                            "start": "2026-03-15T10:00:00+00:00",
                            "end": "2026-03-15T11:00:00+00:00",
                        },
                        {
                            "start": "2026-03-15T14:00:00+00:00",
                            "end": "2026-03-15T15:00:00+00:00",
                        },
                    ]
                }
            }
        }

        slots = await mock_provider.get_available_slots("primary", start, end, 30)

        assert len(slots) == 3
        assert slots[0].start.hour == 9
        assert slots[0].end.hour == 10
        assert slots[1].start.hour == 11
        assert slots[1].end.hour == 14
        assert slots[2].start.hour == 15
        assert slots[2].end.hour == 18

    async def test_get_events(self, mock_provider):
        start = datetime(2026, 3, 15, 9, 0, tzinfo=timezone.utc)
        end = datetime(2026, 3, 15, 18, 0, tzinfo=timezone.utc)

        mock_provider._service.events.return_value.list.return_value.execute.return_value = {
            "items": [
                {
                    "summary": "Meeting",
                    "start": {"dateTime": "2026-03-15T10:00:00+00:00"},
                    "end": {"dateTime": "2026-03-15T11:00:00+00:00"},
                    "description": "Team sync",
                    "attendees": [{"email": "bob@example.com"}],
                    "location": "Room A",
                }
            ]
        }

        events = await mock_provider.get_events("primary", start, end)

        assert len(events) == 1
        assert events[0].summary == "Meeting"
        assert events[0].attendees == ["bob@example.com"]
        assert events[0].location == "Room A"

    async def test_create_event(self, mock_provider):
        now = datetime(2026, 3, 15, 14, 0, tzinfo=timezone.utc)
        event = CalendarEvent(
            summary="Apartment Viewing",
            start=now,
            end=now + timedelta(minutes=30),
            attendees=["test@example.com"],
            location="123 Main St",
        )

        mock_provider._service.events.return_value.insert.return_value.execute.return_value = {
            "id": "evt_123",
            "htmlLink": "https://calendar.google.com/event/evt_123",
            "status": "confirmed",
        }

        result = await mock_provider.create_event("primary", event)

        assert result["event_id"] == "evt_123"
        assert result["html_link"] == "https://calendar.google.com/event/evt_123"

    async def test_cancel_event(self, mock_provider):
        mock_provider._service.events.return_value.delete.return_value.execute.return_value = None

        result = await mock_provider.cancel_event("primary", "evt_123")
        assert result is True

    async def test_cancel_event_failure(self, mock_provider):
        mock_provider._service.events.return_value.delete.return_value.execute.side_effect = Exception(
            "Not found"
        )

        result = await mock_provider.cancel_event("primary", "evt_404")
        assert result is False
