"""cal-provider: Multi-backend calendar provider library.

Public API — import directly from the package:

    from cal_provider import CalendarProvider, TimeSlot, CalendarEvent, get_provider
"""

from cal_provider.models import CalendarEvent, CalendarInfo, TimeSlot
from cal_provider.provider import CalendarProvider
from cal_provider.registry import get_provider, register_provider

__all__ = [
    "CalendarProvider",
    "CalendarEvent",
    "CalendarInfo",
    "TimeSlot",
    "get_provider",
    "register_provider",
]
