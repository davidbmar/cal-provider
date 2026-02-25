"""Custom exception hierarchy for calendar providers.

All exceptions inherit from ``CalendarProviderError`` so consumers can
catch every provider error with a single ``except`` clause, or handle
specific failure modes individually.
"""


class CalendarProviderError(Exception):
    """Base exception for all calendar provider errors."""


class AuthenticationError(CalendarProviderError):
    """Bad credentials, expired token, or missing service account."""


class CalendarNotFoundError(CalendarProviderError):
    """The requested calendar_id does not exist or is inaccessible."""


class EventNotFoundError(CalendarProviderError):
    """The requested event_id does not exist."""


class CalendarPermissionError(CalendarProviderError):
    """Insufficient permissions (e.g. sendUpdates on service account, no write access)."""
