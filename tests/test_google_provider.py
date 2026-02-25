"""Tests for GoogleCalendarProvider (mocked Google API)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from cal_provider.exceptions import AuthenticationError, CalendarNotFoundError, EventNotFoundError
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

    @pytest.fixture
    def mock_provider_send_all(self):
        """Create a GoogleCalendarProvider with sendUpdates='all'."""
        with patch(
            "cal_provider.providers.google.Credentials"
        ) as mock_creds, patch(
            "cal_provider.providers.google.build"
        ) as mock_build:
            mock_creds.from_service_account_file.return_value = MagicMock()

            from cal_provider.providers.google import GoogleCalendarProvider

            provider = GoogleCalendarProvider(
                service_account_path="/fake/path.json",
                send_updates="all",
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

    async def test_get_available_slots_with_tz(self, mock_provider):
        """tz parameter converts returned slots to target timezone."""
        start = datetime(2026, 3, 15, 14, 0, tzinfo=timezone.utc)
        end = datetime(2026, 3, 15, 20, 0, tzinfo=timezone.utc)

        mock_provider._service.freebusy.return_value.query.return_value.execute.return_value = {
            "calendars": {"primary": {"busy": []}}
        }

        chicago = ZoneInfo("America/Chicago")
        slots = await mock_provider.get_available_slots(
            "primary", start, end, 30, tz=chicago
        )

        assert len(slots) == 1
        assert slots[0].start.hour == 9  # 14 UTC → 9 AM CDT

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

    async def test_get_events_with_tz(self, mock_provider):
        """tz parameter converts event times to target timezone."""
        start = datetime(2026, 3, 15, 9, 0, tzinfo=timezone.utc)
        end = datetime(2026, 3, 15, 18, 0, tzinfo=timezone.utc)

        mock_provider._service.events.return_value.list.return_value.execute.return_value = {
            "items": [
                {
                    "summary": "Meeting",
                    "start": {"dateTime": "2026-03-15T14:00:00+00:00"},
                    "end": {"dateTime": "2026-03-15T15:00:00+00:00"},
                }
            ]
        }

        chicago = ZoneInfo("America/Chicago")
        events = await mock_provider.get_events("primary", start, end, tz=chicago)

        assert events[0].start.hour == 9  # 14 UTC → 9 AM CDT

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

    async def test_create_event_default_send_updates_none(self, mock_provider):
        """Default sendUpdates should be 'none' (not 'all')."""
        now = datetime(2026, 3, 15, 14, 0, tzinfo=timezone.utc)
        event = CalendarEvent(
            summary="Test",
            start=now,
            end=now + timedelta(minutes=30),
        )

        mock_provider._service.events.return_value.insert.return_value.execute.return_value = {
            "id": "evt_1",
            "status": "confirmed",
        }

        await mock_provider.create_event("primary", event)

        # Verify insert was called with sendUpdates="none"
        mock_provider._service.events.return_value.insert.assert_called_once_with(
            calendarId="primary",
            body={
                "summary": "Test",
                "start": {"dateTime": mock_provider._to_rfc3339(event.start)},
                "end": {"dateTime": mock_provider._to_rfc3339(event.end)},
            },
            sendUpdates="none",
        )

    async def test_create_event_configurable_send_updates(self, mock_provider_send_all):
        """send_updates='all' should be passed through to API."""
        now = datetime(2026, 3, 15, 14, 0, tzinfo=timezone.utc)
        event = CalendarEvent(
            summary="Test",
            start=now,
            end=now + timedelta(minutes=30),
        )

        mock_provider_send_all._service.events.return_value.insert.return_value.execute.return_value = {
            "id": "evt_1",
            "status": "confirmed",
        }

        await mock_provider_send_all.create_event("primary", event)

        mock_provider_send_all._service.events.return_value.insert.assert_called_once_with(
            calendarId="primary",
            body={
                "summary": "Test",
                "start": {"dateTime": mock_provider_send_all._to_rfc3339(event.start)},
                "end": {"dateTime": mock_provider_send_all._to_rfc3339(event.end)},
            },
            sendUpdates="all",
        )

    async def test_cancel_event(self, mock_provider):
        mock_provider._service.events.return_value.delete.return_value.execute.return_value = None

        result = await mock_provider.cancel_event("primary", "evt_123")
        assert result is True

    async def test_cancel_event_not_found_raises(self, mock_provider):
        """404 from Google API should raise EventNotFoundError."""
        from googleapiclient.errors import HttpError

        resp = MagicMock()
        resp.status = 404
        mock_provider._service.events.return_value.delete.return_value.execute.side_effect = HttpError(
            resp, b"Not found"
        )

        with pytest.raises(EventNotFoundError, match="Event not found"):
            await mock_provider.cancel_event("primary", "evt_404")

    async def test_missing_service_account_raises_auth_error(self):
        """Missing service account path should raise AuthenticationError."""
        import os
        from unittest.mock import patch as _patch

        with _patch.dict(os.environ, {}, clear=True):
            with pytest.raises(AuthenticationError, match="service account JSON"):
                from cal_provider.providers.google import GoogleCalendarProvider
                GoogleCalendarProvider(service_account_path=None)
