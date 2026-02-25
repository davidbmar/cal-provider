"""Data models for calendar providers.

These are pure dataclasses with no external dependencies.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class TimeSlot:
    """A window of availability on a calendar."""

    start: datetime
    end: datetime

    @property
    def duration(self) -> timedelta:
        """Duration of the slot as a timedelta."""
        return self.end - self.start

    @property
    def duration_minutes(self) -> int:
        """Duration of the slot in whole minutes."""
        return int(self.duration.total_seconds() // 60)

    def __repr__(self) -> str:
        fmt = "%I:%M %p"
        return (
            f"TimeSlot({self.start.strftime(fmt)} - "
            f"{self.end.strftime(fmt)}, {self.duration_minutes} min)"
        )


@dataclass
class CalendarEvent:
    """Represents a calendar event to be created or retrieved."""

    summary: str
    start: datetime
    end: datetime
    description: str = ""
    attendees: list[str] = field(default_factory=list)  # email addresses
    location: str = ""

    def __post_init__(self) -> None:
        if not self.summary or not self.summary.strip():
            raise ValueError("CalendarEvent summary must not be empty")
        if self.start >= self.end:
            raise ValueError(
                f"CalendarEvent start ({self.start}) must be before end ({self.end})"
            )

    def __repr__(self) -> str:
        fmt = "%Y-%m-%d %I:%M %p"
        return (
            f"CalendarEvent({self.summary!r}, "
            f"{self.start.strftime(fmt)} - {self.end.strftime(fmt)})"
        )


@dataclass
class CalendarInfo:
    """Metadata about a calendar returned by list_calendars."""

    id: str
    name: str
    description: str = ""
    primary: bool = False

    def __repr__(self) -> str:
        primary_tag = " [primary]" if self.primary else ""
        return f"CalendarInfo({self.name!r}{primary_tag}, id={self.id!r})"
