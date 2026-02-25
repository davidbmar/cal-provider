"""Tests for cal_provider.models dataclasses."""

from datetime import datetime, timedelta, timezone

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
        e1 = CalendarEvent(summary="A", start=now, end=now)
        e2 = CalendarEvent(summary="B", start=now, end=now)
        e1.attendees.append("shared@bug.com")
        assert e2.attendees == []


class TestCalendarInfo:
    def test_defaults(self):
        info = CalendarInfo(id="cal-1", name="Work")
        assert info.description == ""
        assert info.primary is False

    def test_primary(self):
        info = CalendarInfo(id="primary", name="Main", primary=True)
        assert info.primary is True
