"""Abstract base class for calendar providers.

Defines the interface for calendar operations. Any calendar backend
(Google, CalDAV, Outlook, etc.) implements this ABC.
"""

from abc import ABC, abstractmethod
from datetime import datetime, tzinfo

from cal_provider.models import CalendarEvent, CalendarInfo, TimeSlot


class CalendarProvider(ABC):
    """Abstract calendar backend.

    Subclasses must implement all abstract methods. ``update_event``
    is optional — the default raises ``NotImplementedError``.
    """

    @abstractmethod
    async def list_calendars(self) -> list[CalendarInfo]:
        """Discover available calendars.

        Returns:
            List of CalendarInfo objects describing each calendar.
        """

    @abstractmethod
    async def get_available_slots(
        self,
        calendar_id: str,
        start: datetime,
        end: datetime,
        duration_minutes: int = 60,
        tz: tzinfo | None = None,
    ) -> list[TimeSlot]:
        """Return available time slots within the given range.

        Args:
            calendar_id: The calendar to query.
            start: Beginning of the search window.
            end: End of the search window.
            duration_minutes: Minimum slot length in minutes.
            tz: If provided, returned slots use this timezone.

        Returns:
            List of TimeSlot objects that are free and at least
            ``duration_minutes`` long.
        """

    @abstractmethod
    async def get_events(
        self,
        calendar_id: str,
        start: datetime,
        end: datetime,
        tz: tzinfo | None = None,
    ) -> list[CalendarEvent]:
        """Retrieve events within a time range.

        Args:
            calendar_id: The calendar to query.
            start: Beginning of the search window.
            end: End of the search window.
            tz: If provided, returned events use this timezone.

        Returns:
            List of CalendarEvent objects in the range.
        """

    @abstractmethod
    async def create_event(
        self, calendar_id: str, event: CalendarEvent
    ) -> dict:
        """Create a calendar event.

        Args:
            calendar_id: The calendar to create the event on.
            event: Event details.

        Returns:
            Dict containing at least ``"event_id"`` and ``"status"``.
        """

    @abstractmethod
    async def cancel_event(
        self, calendar_id: str, event_id: str
    ) -> bool:
        """Cancel / delete a calendar event.

        Args:
            calendar_id: The calendar that owns the event.
            event_id: Provider-specific event identifier.

        Returns:
            True if the event was successfully cancelled.
        """

    async def update_event(
        self,
        calendar_id: str,
        event_id: str,
        **updates,
    ) -> dict:
        """Update fields on an existing calendar event.

        Optional — not all providers need to support this.

        Args:
            calendar_id: The calendar that owns the event.
            event_id: Provider-specific event identifier.
            **updates: Field names and new values.

        Returns:
            Dict with updated event data.

        Raises:
            NotImplementedError: If the provider doesn't support updates.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support update_event"
        )
