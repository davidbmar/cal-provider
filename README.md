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

slots = await provider.get_available_slots(
    "primary",
    start=datetime(2026, 3, 15, 9, 0, tzinfo=timezone.utc),
    end=datetime(2026, 3, 15, 18, 0, tzinfo=timezone.utc),
    duration_minutes=30,
)

events = await provider.get_events("primary", start, end)

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
| `get_available_slots` | `(calendar_id, start, end, duration_minutes=60)` | `list[TimeSlot]` |
| `get_events` | `(calendar_id, start, end)` | `list[CalendarEvent]` |
| `create_event` | `(calendar_id, event: CalendarEvent)` | `dict` with `event_id`, `status` |
| `cancel_event` | `(calendar_id, event_id)` | `bool` |
| `update_event` | `(calendar_id, event_id, **updates)` | `dict` (optional, raises `NotImplementedError` by default) |

### Models

- **`TimeSlot(start, end)`** — A window of free time
- **`CalendarEvent(summary, start, end, description?, attendees?, location?)`** — An event to create or retrieve
- **`CalendarInfo(id, name, description?, primary?)`** — Calendar metadata

### Registry

```python
from cal_provider import get_provider, register_provider

# Built-in providers (lazily imported)
provider = get_provider("google", service_account_path="...")
provider = get_provider("caldav", url="...", username="...", password="...")

# Register a custom provider
register_provider("outlook", MyOutlookProvider)
provider = get_provider("outlook", tenant_id="...")
```

## Backend Setup

### Google Calendar

1. Enable the [Google Calendar API](https://console.cloud.google.com/apis/library/calendar-json.googleapis.com)
2. Create a service account and download the JSON key
3. Share your calendar with the service account email (give "Make changes to events" permission)

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
python -m pytest tests/ -v   # 40 tests, all mocked (no credentials needed)
```

## Architecture

```
cal_provider/
  models.py             # TimeSlot, CalendarEvent, CalendarInfo
  provider.py           # CalendarProvider ABC
  utils.py              # Shared busy→available slot inversion
  registry.py           # get_provider() factory with lazy imports
  providers/
    google.py           # Google Calendar API v3
    caldav_provider.py  # CalDAV (iCloud, Nextcloud, Fastmail)
  mcp/
    server.py           # FastMCP server (6 tools)
    config.py           # Env var → provider factory
```

Zero mandatory dependencies. Google and CalDAV libraries are optional — install only what you need.
