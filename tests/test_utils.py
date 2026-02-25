"""Tests for cal_provider.utils — busy→available slot inversion."""

from datetime import datetime, timedelta, timezone

from cal_provider.models import TimeSlot
from cal_provider.utils import compute_available_slots


class TestComputeAvailableSlots:
    def test_empty_calendar(self):
        """No busy intervals → one big slot spanning the window."""
        start = datetime(2026, 3, 15, 9, 0, tzinfo=timezone.utc)
        end = datetime(2026, 3, 15, 18, 0, tzinfo=timezone.utc)

        slots = compute_available_slots([], start, end, 30)

        assert len(slots) == 1
        assert slots[0].start == start
        assert slots[0].end == end

    def test_single_busy_block(self):
        """One busy block → two gaps (before and after)."""
        start = datetime(2026, 3, 15, 9, 0, tzinfo=timezone.utc)
        end = datetime(2026, 3, 15, 18, 0, tzinfo=timezone.utc)
        busy = [
            (
                datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc),
                datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc),
            )
        ]

        slots = compute_available_slots(busy, start, end, 30)

        assert len(slots) == 2
        assert slots[0] == TimeSlot(start=start, end=busy[0][0])
        assert slots[1] == TimeSlot(start=busy[0][1], end=end)

    def test_multiple_busy_blocks(self):
        """Two busy blocks → three gaps."""
        start = datetime(2026, 3, 15, 9, 0, tzinfo=timezone.utc)
        end = datetime(2026, 3, 15, 18, 0, tzinfo=timezone.utc)
        busy = [
            (
                datetime(2026, 3, 15, 10, 0, tzinfo=timezone.utc),
                datetime(2026, 3, 15, 11, 0, tzinfo=timezone.utc),
            ),
            (
                datetime(2026, 3, 15, 14, 0, tzinfo=timezone.utc),
                datetime(2026, 3, 15, 15, 0, tzinfo=timezone.utc),
            ),
        ]

        slots = compute_available_slots(busy, start, end, 30)

        assert len(slots) == 3
        assert slots[0].start.hour == 9
        assert slots[0].end.hour == 10
        assert slots[1].start.hour == 11
        assert slots[1].end.hour == 14
        assert slots[2].start.hour == 15
        assert slots[2].end.hour == 18

    def test_unsorted_busy_intervals(self):
        """Busy intervals needn't be pre-sorted."""
        start = datetime(2026, 3, 15, 9, 0, tzinfo=timezone.utc)
        end = datetime(2026, 3, 15, 18, 0, tzinfo=timezone.utc)
        busy = [
            (
                datetime(2026, 3, 15, 14, 0, tzinfo=timezone.utc),
                datetime(2026, 3, 15, 15, 0, tzinfo=timezone.utc),
            ),
            (
                datetime(2026, 3, 15, 10, 0, tzinfo=timezone.utc),
                datetime(2026, 3, 15, 11, 0, tzinfo=timezone.utc),
            ),
        ]

        slots = compute_available_slots(busy, start, end, 30)
        assert len(slots) == 3

    def test_gap_too_short_filtered(self):
        """Gaps shorter than duration_minutes are excluded."""
        start = datetime(2026, 3, 15, 9, 0, tzinfo=timezone.utc)
        end = datetime(2026, 3, 15, 18, 0, tzinfo=timezone.utc)
        busy = [
            (
                datetime(2026, 3, 15, 9, 15, tzinfo=timezone.utc),
                datetime(2026, 3, 15, 17, 50, tzinfo=timezone.utc),
            ),
        ]

        # 15-min gap at start, 10-min gap at end — both < 30
        slots = compute_available_slots(busy, start, end, 30)
        assert len(slots) == 0

    def test_fully_busy(self):
        """Entire window is busy → no slots."""
        start = datetime(2026, 3, 15, 9, 0, tzinfo=timezone.utc)
        end = datetime(2026, 3, 15, 18, 0, tzinfo=timezone.utc)
        busy = [(start, end)]

        slots = compute_available_slots(busy, start, end, 30)
        assert len(slots) == 0

    def test_naive_datetimes_get_utc(self):
        """Naive window datetimes get UTC applied."""
        start = datetime(2026, 3, 15, 9, 0)  # naive
        end = datetime(2026, 3, 15, 18, 0)    # naive

        slots = compute_available_slots([], start, end, 30)
        assert len(slots) == 1
        assert slots[0].start.tzinfo == timezone.utc

    def test_overlapping_busy_blocks(self):
        """Overlapping busy blocks should not create phantom gaps."""
        start = datetime(2026, 3, 15, 9, 0, tzinfo=timezone.utc)
        end = datetime(2026, 3, 15, 18, 0, tzinfo=timezone.utc)
        busy = [
            (
                datetime(2026, 3, 15, 10, 0, tzinfo=timezone.utc),
                datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc),
            ),
            (
                datetime(2026, 3, 15, 11, 0, tzinfo=timezone.utc),
                datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc),
            ),
        ]

        slots = compute_available_slots(busy, start, end, 30)
        assert len(slots) == 2
        assert slots[0] == TimeSlot(
            start=start,
            end=datetime(2026, 3, 15, 10, 0, tzinfo=timezone.utc),
        )
        assert slots[1] == TimeSlot(
            start=datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc),
            end=end,
        )
