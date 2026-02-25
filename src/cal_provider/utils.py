"""Shared utilities for calendar providers."""

from datetime import datetime, timedelta, timezone, tzinfo

from cal_provider.models import TimeSlot


def compute_available_slots(
    busy: list[tuple[datetime, datetime]],
    window_start: datetime,
    window_end: datetime,
    duration_minutes: int = 60,
    tz: tzinfo | None = None,
) -> list[TimeSlot]:
    """Invert busy intervals into available time slots.

    Given a list of (start, end) busy intervals and a search window,
    returns the free gaps that are at least ``duration_minutes`` long.

    Args:
        busy: List of (start, end) datetime pairs representing busy times.
              Need not be sorted — this function sorts them internally.
        window_start: Beginning of the search window.
        window_end: End of the search window.
        duration_minutes: Minimum slot length in minutes.
        tz: If provided, returned slots are converted to this timezone.

    Returns:
        List of TimeSlot objects representing available windows.
    """
    # Ensure timezone-aware
    if window_start.tzinfo is None:
        window_start = window_start.replace(tzinfo=timezone.utc)
    if window_end.tzinfo is None:
        window_end = window_end.replace(tzinfo=timezone.utc)

    # Sort by start time
    busy_sorted = sorted(busy, key=lambda b: b[0])

    available: list[TimeSlot] = []
    min_duration = timedelta(minutes=duration_minutes)
    cursor = window_start

    for b_start, b_end in busy_sorted:
        if cursor < b_start:
            gap = b_start - cursor
            if gap >= min_duration:
                available.append(TimeSlot(start=cursor, end=b_start))
        cursor = max(cursor, b_end)

    # Trailing free time after last busy block
    if cursor < window_end:
        gap = window_end - cursor
        if gap >= min_duration:
            available.append(TimeSlot(start=cursor, end=window_end))

    # Convert to target timezone if requested
    if tz is not None:
        available = [
            TimeSlot(start=s.start.astimezone(tz), end=s.end.astimezone(tz))
            for s in available
        ]

    return available
