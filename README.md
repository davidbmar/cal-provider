# cal-provider

Multi-backend calendar provider library for Python. Provides a unified async API across Google Calendar and CalDAV (iCloud, Nextcloud, Fastmail), plus an optional MCP server for AI agent integration.

## Install

```bash
pip install -e ".[google]"   # Google Calendar
pip install -e ".[caldav]"   # CalDAV (iCloud, Nextcloud, Fastmail)
pip install -e ".[all]"      # Everything + MCP server
```

## Quick Start

```python
from cal_provider import get_provider, CalendarEvent
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# Google Calendar
provider = get_provider("google", service_account_path="/path/to/sa.json")

# CalDAV
provider = get_provider("caldav",
    url="https://caldav.icloud.com/",
    username="you@icloud.com",
    password="app-specific-password",
)

# Same API regardless of backend
calendars = await provider.list_calendars()

# Get availability in your local timezone
chicago = ZoneInfo("America/Chicago")
slots = await provider.get_available_slots(
    "primary",
    start=datetime(2026, 3, 15, 9, 0, tzinfo=timezone.utc),
    end=datetime(2026, 3, 15, 18, 0, tzinfo=timezone.utc),
    duration_minutes=30,
    tz=chicago,  # Returns Central time slots
)

events = await provider.get_events("primary", start, end, tz=chicago)

result = await provider.create_event("primary", CalendarEvent(
    summary="Meeting",
    start=datetime(2026, 3, 15, 14, 0, tzinfo=timezone.utc),
    end=datetime(2026, 3, 15, 15, 0, tzinfo=timezone.utc),
    attendees=["colleague@example.com"],
    location="Room 42",
))

await provider.cancel_event("primary", result["event_id"])
```

## API

### CalendarProvider (ABC)

| Method | Signature | Returns |
|--------|-----------|---------|
| `list_calendars` | `()` | `list[CalendarInfo]` |
| `get_available_slots` | `(calendar_id, start, end, duration_minutes=60, tz=None)` | `list[TimeSlot]` |
| `get_events` | `(calendar_id, start, end, tz=None)` | `list[CalendarEvent]` |
| `create_event` | `(calendar_id, event: CalendarEvent)` | `dict` with `event_id`, `status` |
| `cancel_event` | `(calendar_id, event_id)` | `bool` |
| `update_event` | `(calendar_id, event_id, **updates)` | `dict` (optional, raises `NotImplementedError` by default) |

The optional `tz` parameter on `get_available_slots` and `get_events` converts returned datetimes to the specified timezone. Pass any `tzinfo` object (e.g., `ZoneInfo("America/Chicago")`). Default `None` returns times as-is from the backend.

### Models

- **`TimeSlot(start, end)`** — A window of free time
  - `.duration` → `timedelta`
  - `.duration_minutes` → `int`
- **`CalendarEvent(summary, start, end, description?, attendees?, location?)`** — An event to create or retrieve
  - Validates: `summary` not empty, `start < end`
- **`CalendarInfo(id, name, description?, primary?)`** — Calendar metadata

### Exceptions

All exceptions inherit from `CalendarProviderError`:

```python
from cal_provider import (
    CalendarProviderError,    # Base — catch all provider errors
    AuthenticationError,      # Bad credentials, expired token
    CalendarNotFoundError,    # calendar_id doesn't exist
    EventNotFoundError,       # event_id doesn't exist
    CalendarPermissionError,  # No write access, sendUpdates forbidden
)

try:
    await provider.create_event("primary", event)
except CalendarPermissionError:
    print("Service account lacks write permission")
except CalendarNotFoundError:
    print("Calendar doesn't exist — check calendar_id")
except CalendarProviderError as e:
    print(f"Calendar error: {e}")
```

### Registry

```python
from cal_provider import get_provider, register_provider

# Built-in providers (lazily imported)
provider = get_provider("google", service_account_path="...")
provider = get_provider("caldav", url="...", username="...", password="...")

# Google with invitation emails enabled (requires Domain-Wide Delegation)
provider = get_provider("google", service_account_path="...", send_updates="all")

# Register a custom provider
register_provider("outlook", MyOutlookProvider)
provider = get_provider("outlook", tenant_id="...")
```

## Backend Setup

### Google Calendar

1. Enable the [Google Calendar API](https://console.cloud.google.com/apis/library/calendar-json.googleapis.com)
2. Create a service account and download the JSON key
3. Share your calendar with the service account email (give "Make changes to events" permission)

**Note:** By default, `sendUpdates="none"` — the service account creates events silently. Set `send_updates="all"` only if you have Domain-Wide Delegation configured.

### CalDAV

| Provider | URL | Auth |
|----------|-----|------|
| iCloud | `https://caldav.icloud.com/` | Apple ID + [app-specific password](https://appleid.apple.com/) |
| Nextcloud | `https://your-server/remote.php/dav/` | Account credentials |
| Fastmail | `https://caldav.fastmail.com/dav/calendars/` | Account + app password |

## MCP Server

Expose calendar tools to AI agents (Claude, Cursor, etc.):

```bash
export CAL_PROVIDER=google
export GOOGLE_SERVICE_ACCOUNT_JSON=/path/to/sa.json
cal-provider-mcp
```

Or for CalDAV:

```bash
export CAL_PROVIDER=caldav
export CALDAV_URL=https://caldav.icloud.com/
export CALDAV_USERNAME=you@icloud.com
export CALDAV_PASSWORD=xxxx-xxxx-xxxx-xxxx
cal-provider-mcp
```

**MCP tools exposed:** `list_calendars`, `get_available_slots`, `get_events`, `create_event`, `update_event`, `cancel_event`

### Claude Code integration

Add to `.claude/settings.json`:

```json
{
  "mcpServers": {
    "calendar": {
      "command": "/path/to/cal-provider/.venv/bin/cal-provider-mcp",
      "env": {
        "CAL_PROVIDER": "google",
        "GOOGLE_SERVICE_ACCOUNT_JSON": "/path/to/sa.json"
      }
    }
  }
}
```

## Tests

```bash
python -m pytest tests/ -v   # 68 tests, all mocked (no credentials needed)
```

## Architecture

```
cal_provider/
  __init__.py           # Public API + __version__
  models.py             # TimeSlot, CalendarEvent, CalendarInfo
  provider.py           # CalendarProvider ABC
  exceptions.py         # CalendarProviderError hierarchy
  utils.py              # Shared busy→available slot inversion
  registry.py           # get_provider() factory with lazy imports
  py.typed              # PEP 561 marker
  providers/
    google.py           # Google Calendar API v3
    caldav_provider.py  # CalDAV (iCloud, Nextcloud, Fastmail)
  mcp/
    server.py           # FastMCP server (6 tools)
    config.py           # Env var → provider factory
```

Zero mandatory dependencies. Google and CalDAV libraries are optional — install only what you need.
