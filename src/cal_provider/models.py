"""Data models for calendar providers.

These are pure dataclasses with no external dependencies.
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class TimeSlot:
    """A window of availability on a calendar."""

    start: datetime
    end: datetime


@dataclass
class CalendarEvent:
    """Represents a calendar event to be created or retrieved."""

    summary: str
    start: datetime
    end: datetime
    description: str = ""
    attendees: list[str] = field(default_factory=list)  # email addresses
    location: str = ""


@dataclass
class CalendarInfo:
    """Metadata about a calendar returned by list_calendars."""

    id: str
    name: str
    description: str = ""
    primary: bool = False
