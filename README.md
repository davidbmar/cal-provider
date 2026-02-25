# cal-provider

Unified async calendar API for Python. One interface across Google Calendar and CalDAV (iCloud, Nextcloud, Fastmail), with an optional MCP server for AI agents and an admin UI for setup.

## 30-Second Quick Start

```bash
pip install -e ".[google]"
```

```python
import asyncio
from datetime import datetime, timezone
from cal_provider import get_provider

async def main():
    provider = get_provider("google", service_account_path="/path/to/sa.json")
    slots = await provider.get_available_slots(
        "primary",
        start=datetime(2026, 3, 15, 9, 0, tzinfo=timezone.utc),
        end=datetime(2026, 3, 15, 18, 0, tzinfo=timezone.utc),
        duration_minutes=30,
    )
    for slot in slots:
        print(f"{slot.start:%I:%M %p} - {slot.end:%I:%M %p} ({slot.duration_minutes} min)")

asyncio.run(main())
```

## 5-Minute Setup (Admin UI)

The admin UI walks you through provider configuration with a 4-step wizard.

```bash
pip install -e ".[admin,google]"
cal-provider-admin
```

Open `http://localhost:8100`. The wizard flow:

1. **Choose provider** -- Google Calendar or CalDAV
2. **Enter credentials** -- service account path (Google) or URL + username + password (CalDAV)
3. **Test connection** -- verifies credentials, shows your calendars
4. **Generate config** -- creates `.env` file and Claude Code / Cursor config snippets

The admin also includes a dashboard for browsing calendars, viewing events, checking availability, and running a create/cancel round-trip test.

## Recipes

### Check availability

```python
slots = await provider.get_available_slots(
    "primary",
    start=datetime(2026, 3, 15, 9, 0, tzinfo=timezone.utc),
    end=datetime(2026, 3, 15, 18, 0, tzinfo=timezone.utc),
    duration_minutes=30,
)
```

### Book a meeting

```python
from cal_provider import CalendarEvent

event = CalendarEvent(
    summary="Project sync",
    start=datetime(2026, 3, 15, 14, 0, tzinfo=timezone.utc),
    end=datetime(2026, 3, 15, 15, 0, tzinfo=timezone.utc),
    description="Weekly sync with the team",
    attendees=["alice@example.com", "bob@example.com"],
    location="Room 42",
)
result = await provider.create_event("primary", event)
print(result["event_id"])   # provider-specific ID
print(result["status"])     # "confirmed"
```

### List all calendars

```python
calendars = await provider.list_calendars()
for cal in calendars:
    print(f"{cal.name} (id={cal.id}, primary={cal.primary})")
```

### Get events in your timezone

```python
from zoneinfo import ZoneInfo

chicago = ZoneInfo("America/Chicago")
events = await provider.get_events(
    "primary",
    start=datetime(2026, 3, 15, 0, 0, tzinfo=timezone.utc),
    end=datetime(2026, 3, 16, 0, 0, tzinfo=timezone.utc),
    tz=chicago,
)
for e in events:
    print(f"{e.summary}: {e.start:%I:%M %p} - {e.end:%I:%M %p}")
```

The optional `tz` parameter works on both `get_events` and `get_available_slots`. It converts all returned datetimes via `astimezone()`. Pass any `tzinfo` object. When omitted, times come back as-is from the backend.

### Handle errors gracefully

```python
from cal_provider import (
    CalendarProviderError,
    AuthenticationError,
    CalendarNotFoundError,
    EventNotFoundError,
    CalendarPermissionError,
)

try:
    result = await provider.create_event("primary", event)
except CalendarPermissionError:
    print("Service account lacks write permission on this calendar")
except CalendarNotFoundError:
    print("Calendar ID doesn't exist -- check calendar_id")
except AuthenticationError:
    print("Bad credentials or expired token")
except EventNotFoundError:
    print("Event ID doesn't exist")
except CalendarProviderError as e:
    # Catches all of the above plus any other provider error
    print(f"Calendar error: {e}")
```

## API Reference

All methods are async. The provider is obtained via `get_provider()`.

| Method | Signature | Returns |
|--------|-----------|---------|
| `list_calendars` | `()` | `list[CalendarInfo]` |
| `get_available_slots` | `(calendar_id, start, end, duration_minutes=60, tz=None)` | `list[TimeSlot]` |
| `get_events` | `(calendar_id, start, end, tz=None)` | `list[CalendarEvent]` |
| `create_event` | `(calendar_id, event: CalendarEvent)` | `dict` with `event_id`, `status` (Google also includes `html_link`) |
| `cancel_event` | `(calendar_id, event_id)` | `bool` |
| `update_event` | `(calendar_id, event_id, **updates)` | `dict` (optional -- raises `NotImplementedError` by default) |

## Models

**`TimeSlot(start, end)`** -- A window of free time.

- `.duration` returns a `timedelta`
- `.duration_minutes` returns an `int`

**`CalendarEvent(summary, start, end, description="", attendees=[], location="")`** -- An event to create or retrieve.

- Validates that `summary` is not empty and `start < end` at construction time
- `attendees` is a list of email address strings

**`CalendarInfo(id, name, description="", primary=False)`** -- Calendar metadata returned by `list_calendars()`.

## Exceptions

All exceptions inherit from `CalendarProviderError`, so you can catch everything with one clause or handle specific cases:

```
CalendarProviderError          (base -- catches all provider errors)
  +-- AuthenticationError      (bad credentials, expired token, missing service account)
  +-- CalendarNotFoundError    (calendar_id doesn't exist or is inaccessible)
  +-- EventNotFoundError       (event_id doesn't exist)
  +-- CalendarPermissionError  (no write access, sendUpdates forbidden)
```

Catch-all pattern:

```python
from cal_provider import CalendarProviderError

try:
    await provider.create_event("primary", event)
except CalendarProviderError as e:
    print(f"Something went wrong: {e}")
```

## Backend Setup

### Google Calendar

1. **Enable the API** -- Go to [Google Cloud Console](https://console.cloud.google.com/apis/library/calendar-json.googleapis.com) and enable the Google Calendar API.

2. **Create a service account** -- In IAM & Admin > Service Accounts, create one and download the JSON key file.

3. **Share your calendar** -- In Google Calendar settings, share the target calendar with the service account email address (it looks like `name@project.iam.gserviceaccount.com`). Give it "Make changes to events" permission.

4. **Use the provider:**

```python
provider = get_provider("google", service_account_path="/path/to/sa.json")
```

The `service_account_path` can also be set via the `GOOGLE_SERVICE_ACCOUNT_JSON` environment variable.

**About `send_updates`:** By default, `send_updates="none"` -- the service account creates events silently without sending invitation emails. If you need attendees to receive email notifications, set `send_updates="all"`, but this requires [Domain-Wide Delegation](https://developers.google.com/identity/protocols/oauth2/service-account#delegatingauthority) to be configured.

```python
provider = get_provider("google", service_account_path="/path/to/sa.json", send_updates="all")
```

### CalDAV

| Provider | URL | Auth |
|----------|-----|------|
| iCloud | `https://caldav.icloud.com/` | Apple ID + [app-specific password](https://appleid.apple.com/) |
| Nextcloud | `https://your-server/remote.php/dav/` | Account credentials |
| Fastmail | `https://caldav.fastmail.com/dav/calendars/` | Account + [app password](https://www.fastmail.com/help/clients/apppassword.html) |

```python
provider = get_provider("caldav",
    url="https://caldav.icloud.com/",
    username="you@icloud.com",
    password="xxxx-xxxx-xxxx-xxxx",
)
```

CalDAV treats `"primary"` as the first calendar on the account. You can also use the calendar URL or display name as the `calendar_id`.

## For AI Agents (MCP Server)

The MCP server exposes all calendar operations as tools that AI agents can call.

```bash
pip install -e ".[mcp,google]"
```

### Running with Google Calendar

```bash
export CAL_PROVIDER=google
export GOOGLE_SERVICE_ACCOUNT_JSON=/path/to/sa.json
cal-provider-mcp
```

### Running with CalDAV

```bash
export CAL_PROVIDER=caldav
export CALDAV_URL=https://caldav.icloud.com/
export CALDAV_USERNAME=you@icloud.com
export CALDAV_PASSWORD=xxxx-xxxx-xxxx-xxxx
cal-provider-mcp
```

### MCP tools exposed

`list_calendars`, `get_available_slots`, `get_events`, `create_event`, `update_event`, `cancel_event`

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

### Cursor integration

Add to `.cursor/mcp.json`:

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

## Admin Dashboard

The admin UI provides a setup wizard and a dashboard for exploring your calendar data.

```bash
pip install -e ".[admin,google]"
cal-provider-admin
# Runs on http://localhost:8100 (override with CAL_PROVIDER_ADMIN_PORT)
```

### Pages

| Path | Purpose |
|------|---------|
| `/setup` | 4-step setup wizard (choose provider, enter credentials, test, generate config) |
| `/dashboard` | Browse calendars, view events, check availability, run create/cancel test |
| `/config` | View generated config snippets (.env, export commands, Claude Code JSON) |

### API endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/status` | GET | Connection health check -- is a provider configured? |
| `/api/test-connection` | POST | Test provider credentials, returns available calendars |
| `/api/save-config` | POST | Generate .env file and config snippets |
| `/api/calendars` | GET | List all calendars (requires prior setup) |
| `/api/events` | GET | Get events in a time range (`?calendar_id=...&start=...&end=...`) |
| `/api/available-slots` | GET | Get available slots (`?calendar_id=...&start=...&end=...&duration_minutes=60`) |
| `/api/test-event` | POST | Create and immediately cancel a test event (round-trip verification) |

## Writing a Custom Provider

Subclass `CalendarProvider` and implement the five abstract methods:

```python
from cal_provider import CalendarProvider, CalendarEvent, CalendarInfo, TimeSlot
from datetime import datetime, tzinfo

class OutlookProvider(CalendarProvider):
    def __init__(self, tenant_id: str, client_secret: str):
        self._tenant_id = tenant_id
        self._client_secret = client_secret

    async def list_calendars(self) -> list[CalendarInfo]:
        # Your implementation here
        ...

    async def get_available_slots(
        self, calendar_id: str, start: datetime, end: datetime,
        duration_minutes: int = 60, tz: tzinfo | None = None,
    ) -> list[TimeSlot]:
        ...

    async def get_events(
        self, calendar_id: str, start: datetime, end: datetime,
        tz: tzinfo | None = None,
    ) -> list[CalendarEvent]:
        ...

    async def create_event(self, calendar_id: str, event: CalendarEvent) -> dict:
        ...

    async def cancel_event(self, calendar_id: str, event_id: str) -> bool:
        ...
```

Register it so `get_provider()` can find it:

```python
from cal_provider import register_provider

register_provider("outlook", OutlookProvider)
provider = get_provider("outlook", tenant_id="...", client_secret="...")
```

`update_event` is optional -- the default raises `NotImplementedError`. Override it if your backend supports partial updates.

## Architecture

```
src/cal_provider/
  __init__.py                 Public API + __version__ (0.2.0)
  provider.py                 CalendarProvider ABC (5 abstract + 1 optional method)
  models.py                   TimeSlot, CalendarEvent, CalendarInfo
  exceptions.py               CalendarProviderError hierarchy
  utils.py                    Shared busy-to-available slot inversion
  registry.py                 get_provider() factory with lazy imports
  py.typed                    PEP 561 marker
  providers/
    google.py                 Google Calendar API v3 (service account)
    caldav_provider.py        CalDAV (iCloud, Nextcloud, Fastmail)
  mcp/
    server.py                 FastMCP server (6 tools)
    config.py                 Env var -> provider factory
  admin/
    app.py                    FastAPI admin (setup wizard + dashboard + config viewer)
    templates/                Jinja2 HTML templates (base, setup, dashboard, config)
    static/                   CSS
```

Zero mandatory dependencies. Google and CalDAV libraries are optional -- install only what you need.

## Tests

```bash
pip install -e ".[all]"
python -m pytest tests/ -v
```

83 tests, all mocked (no credentials needed). Uses `pytest-asyncio` with `asyncio_mode = auto`.

```bash
pip install -e ".[all]" && pip install pytest pytest-asyncio
```
