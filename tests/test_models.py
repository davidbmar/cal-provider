"""Tests for cal_provider.models dataclasses."""

from datetime import datetime, timedelta, timezone

import pytest

from cal_provider.models import CalendarEvent, CalendarInfo, TimeSlot


class TestTimeSlot:
    def test_creation(self):
        now = datetime.now(tz=timezone.utc)
        slot = TimeSlot(start=now, end=now + timedelta(hours=1))
        assert (slot.end - slot.start).total_seconds() == 3600

    def test_equality(self):
        dt = datetime(2026, 3, 15, 9, 0, tzinfo=timezone.utc)
        a = TimeSlot(start=dt, end=dt + timedelta(hours=1))
        b = TimeSlot(start=dt, end=dt + timedelta(hours=1))
        assert a == b

    def test_duration(self):
        dt = datetime(2026, 3, 15, 9, 0, tzinfo=timezone.utc)
        slot = TimeSlot(start=dt, end=dt + timedelta(hours=2, minutes=30))
        assert slot.duration == timedelta(hours=2, minutes=30)

    def test_duration_minutes(self):
        dt = datetime(2026, 3, 15, 9, 0, tzinfo=timezone.utc)
        slot = TimeSlot(start=dt, end=dt + timedelta(hours=1, minutes=30))
        assert slot.duration_minutes == 90

    def test_repr(self):
        dt = datetime(2026, 3, 15, 10, 0, tzinfo=timezone.utc)
        slot = TimeSlot(start=dt, end=dt + timedelta(minutes=30))
        r = repr(slot)
        assert "10:00 AM" in r
        assert "30 min" in r


class TestCalendarEvent:
    def test_defaults(self):
        now = datetime.now(tz=timezone.utc)
        event = CalendarEvent(
            summary="Test",
            start=now,
            end=now + timedelta(minutes=30),
        )
        assert event.description == ""
        assert event.attendees == []
        assert event.location == ""

    def test_with_all_fields(self):
        now = datetime.now(tz=timezone.utc)
        event = CalendarEvent(
            summary="Viewing",
            start=now,
            end=now + timedelta(minutes=30),
            description="Apartment viewing",
            attendees=["a@test.com", "b@test.com"],
            location="123 Main St",
        )
        assert len(event.attendees) == 2
        assert event.location == "123 Main St"
        assert event.description == "Apartment viewing"

    def test_mutable_default_not_shared(self):
        """Each instance gets its own attendees list."""
        now = datetime.now(tz=timezone.utc)
        later = now + timedelta(minutes=30)
        e1 = CalendarEvent(summary="A", start=now, end=later)
        e2 = CalendarEvent(summary="B", start=now, end=later)
        e1.attendees.append("shared@bug.com")
        assert e2.attendees == []

    def test_validation_start_after_end_raises(self):
        """start >= end should raise ValueError."""
        now = datetime.now(tz=timezone.utc)
        with pytest.raises(ValueError, match="must be before end"):
            CalendarEvent(summary="Bad", start=now, end=now - timedelta(hours=1))

    def test_validation_start_equals_end_raises(self):
        """start == end should raise ValueError."""
        now = datetime.now(tz=timezone.utc)
        with pytest.raises(ValueError, match="must be before end"):
            CalendarEvent(summary="Zero", start=now, end=now)

    def test_validation_empty_summary_raises(self):
        """Empty summary should raise ValueError."""
        now = datetime.now(tz=timezone.utc)
        with pytest.raises(ValueError, match="summary must not be empty"):
            CalendarEvent(summary="", start=now, end=now + timedelta(hours=1))

    def test_validation_whitespace_summary_raises(self):
        """Whitespace-only summary should raise ValueError."""
        now = datetime.now(tz=timezone.utc)
        with pytest.raises(ValueError, match="summary must not be empty"):
            CalendarEvent(summary="   ", start=now, end=now + timedelta(hours=1))

    def test_repr(self):
        now = datetime(2026, 3, 15, 14, 0, tzinfo=timezone.utc)
        event = CalendarEvent(
            summary="Viewing",
            start=now,
            end=now + timedelta(minutes=30),
        )
        r = repr(event)
        assert "Viewing" in r
        assert "2026-03-15" in r


class TestCalendarInfo:
    def test_defaults(self):
        info = CalendarInfo(id="cal-1", name="Work")
        assert info.description == ""
        assert info.primary is False

    def test_primary(self):
        info = CalendarInfo(id="primary", name="Main", primary=True)
        assert info.primary is True

    def test_repr(self):
        info = CalendarInfo(id="cal-1", name="Work", primary=True)
        r = repr(info)
        assert "Work" in r
        assert "[primary]" in r

    def test_repr_non_primary(self):
        info = CalendarInfo(id="cal-2", name="Personal")
        r = repr(info)
        assert "Personal" in r
        assert "[primary]" not in r
