"""Tests for the MCP server tools."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from cal_provider.models import CalendarEvent, CalendarInfo, TimeSlot


# We test the MCP tool functions directly — they're just async functions
# that wrap the provider. We mock the provider via _get_provider().


@pytest.fixture
def mock_mcp_provider(mock_provider, sample_event):
    """Patch the MCP server's _get_provider to return our mock."""
    mock_provider.events.append(sample_event)
    with patch("cal_provider.mcp.server._get_provider", return_value=mock_provider):
        yield mock_provider


class TestMCPTools:
    async def test_list_calendars(self, mock_mcp_provider):
        from cal_provider.mcp.server import list_calendars

        result = await list_calendars()

        assert len(result) == 2
        assert result[0]["id"] == "cal-1"
        assert result[0]["primary"] is True

    async def test_get_available_slots(self, mock_mcp_provider):
        from cal_provider.mcp.server import get_available_slots

        result = await get_available_slots(
            calendar_id="cal-1",
            start="2026-03-15T09:00:00+00:00",
            end="2026-03-15T18:00:00+00:00",
            duration_minutes=30,
        )

        # sample_event is 14:00-15:00, so we expect two slots
        assert len(result) == 2
        assert "start" in result[0]
        assert "end" in result[0]

    async def test_get_events(self, mock_mcp_provider):
        from cal_provider.mcp.server import get_events

        result = await get_events(
            calendar_id="cal-1",
            start="2026-03-15T00:00:00+00:00",
            end="2026-03-16T00:00:00+00:00",
        )

        assert len(result) == 1
        assert result[0]["summary"] == "Team Meeting"
        assert result[0]["location"] == "Room 42"

    async def test_create_event(self, mock_mcp_provider):
        from cal_provider.mcp.server import create_event

        result = await create_event(
            calendar_id="cal-1",
            summary="New Event",
            start="2026-03-16T10:00:00+00:00",
            end="2026-03-16T11:00:00+00:00",
            description="Test event",
            attendees=["test@example.com"],
            location="Remote",
        )

        assert "event_id" in result
        assert result["status"] == "confirmed"
        # Verify event was added to mock provider's list
        assert len(mock_mcp_provider.events) == 2

    async def test_cancel_event(self, mock_mcp_provider):
        from cal_provider.mcp.server import cancel_event

        result = await cancel_event(
            calendar_id="cal-1",
            event_id="mock-evt-1",
        )

        assert result["success"] is True

    async def test_update_event_not_implemented(self, mock_mcp_provider):
        """MockProvider doesn't implement update_event → NotImplementedError."""
        from cal_provider.mcp.server import update_event

        with pytest.raises(NotImplementedError):
            await update_event(
                calendar_id="cal-1",
                event_id="mock-evt-1",
                summary="Updated",
            )
