"""Environment-based configuration for the MCP server.

Reads env vars to determine which provider to instantiate:

    CAL_PROVIDER          - Provider name ("google" or "caldav")
    GOOGLE_SERVICE_ACCOUNT_JSON  - Path to Google service account JSON
    CALDAV_URL            - CalDAV server URL
    CALDAV_USERNAME       - CalDAV username
    CALDAV_PASSWORD       - CalDAV password
"""

from __future__ import annotations

import os

from cal_provider.provider import CalendarProvider
from cal_provider.registry import get_provider


def create_provider_from_env() -> CalendarProvider:
    """Create a CalendarProvider from environment variables.

    Raises:
        ValueError: If CAL_PROVIDER is not set or unsupported.
        ImportError: If required optional deps are missing.
    """
    provider_name = os.environ.get("CAL_PROVIDER", "").lower()
    if not provider_name:
        raise ValueError(
            "CAL_PROVIDER environment variable must be set "
            "(e.g. 'google' or 'caldav')"
        )

    if provider_name == "google":
        sa_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
        return get_provider("google", service_account_path=sa_path)

    elif provider_name == "caldav":
        url = os.environ.get("CALDAV_URL", "")
        username = os.environ.get("CALDAV_USERNAME", "")
        password = os.environ.get("CALDAV_PASSWORD", "")
        if not url:
            raise ValueError("CALDAV_URL environment variable must be set")
        return get_provider(
            "caldav", url=url, username=username, password=password
        )

    else:
        return get_provider(provider_name)
