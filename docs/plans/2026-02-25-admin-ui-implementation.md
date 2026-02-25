# Admin UI + README Rewrite Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a built-in admin web UI to cal-provider that walks AI-tool developers through setup, and rewrite the README as a progressive task-oriented guide.

**Architecture:** FastAPI sub-package (`cal_provider.admin`) with Jinja2 templates and minimal CSS. Same optional-dependency pattern as the MCP server. Setup wizard collects credentials, tests connection, generates config snippets. Dashboard shows connected calendars and lets you test API calls.

**Tech Stack:** FastAPI, Jinja2, uvicorn, python-multipart (file upload). No JavaScript framework — vanilla JS for form interactions.

---

### Task 1: pyproject.toml — Add admin dependency group and entry point

**Files:**
- Modify: `pyproject.toml`

**Step 1: Edit pyproject.toml**

Add the `admin` dependency group and CLI entry point. Also add `admin` to `all`.

```toml
[project.optional-dependencies]
google = ["google-api-python-client>=2.100", "google-auth>=2.20"]
caldav = ["caldav>=2.0", "icalendar>=5.0"]
mcp = ["mcp[cli]>=1.0"]
admin = ["fastapi>=0.100", "uvicorn>=0.20", "jinja2>=3.1", "python-multipart>=0.0.6"]
all = ["cal-provider[google,caldav,mcp,admin]"]

[project.scripts]
cal-provider-mcp = "cal_provider.mcp.server:main"
cal-provider-admin = "cal_provider.admin.app:main"
```

**Step 2: Install the new deps**

Run: `cd ~/src/cal-provider && .venv/bin/pip install -e ".[admin,google]"`

Expected: Successfully installed fastapi, uvicorn, jinja2, python-multipart.

**Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "Add admin optional dependency group and CLI entry point

Session: S-2026-02-25-0235-cal-provider-v020-hardening"
```

---

### Task 2: Admin package scaffolding — app.py with health endpoint

**Files:**
- Create: `src/cal_provider/admin/__init__.py`
- Create: `src/cal_provider/admin/app.py`

**Step 1: Write the failing test**

Create `tests/test_admin.py`:

```python
"""Tests for the admin web UI."""

import pytest
from fastapi.testclient import TestClient

from cal_provider.admin.app import app


@pytest.fixture
def client():
    return TestClient(app)


class TestAdminHealth:
    def test_health_endpoint(self, client):
        resp = client.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "configured" in data
```

**Step 2: Run test to verify it fails**

Run: `cd ~/src/cal-provider && .venv/bin/python -m pytest tests/test_admin.py::TestAdminHealth::test_health_endpoint -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'cal_provider.admin'`

**Step 3: Write minimal implementation**

`src/cal_provider/admin/__init__.py`:
```python
"""Admin web UI for cal-provider setup and debugging."""
```

`src/cal_provider/admin/app.py`:
```python
"""FastAPI admin app for cal-provider.

Run via CLI: cal-provider-admin
Or: uvicorn cal_provider.admin.app:app --port 8100
"""

from __future__ import annotations

import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI(title="cal-provider admin")

# Template and static file paths
_HERE = Path(__file__).parent
app.mount("/static", StaticFiles(directory=_HERE / "static"), name="static")
templates = Jinja2Templates(directory=_HERE / "templates")

# In-process state (not persisted — lives for the lifetime of the server)
_provider = None
_provider_config: dict = {}


@app.get("/api/status")
async def status():
    """Connection health check."""
    return {
        "configured": _provider is not None,
        "provider": _provider_config.get("provider_name", None),
        "calendar_id": _provider_config.get("calendar_id", None),
    }


def main():
    """CLI entry point for cal-provider-admin."""
    port = int(os.environ.get("CAL_PROVIDER_ADMIN_PORT", "8100"))
    print(f"cal-provider admin → http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
```

**Step 4: Create empty static/templates dirs so StaticFiles doesn't crash**

```bash
mkdir -p src/cal_provider/admin/static
mkdir -p src/cal_provider/admin/templates
touch src/cal_provider/admin/static/.gitkeep
touch src/cal_provider/admin/templates/.gitkeep
```

**Step 5: Run test to verify it passes**

Run: `cd ~/src/cal-provider && .venv/bin/python -m pytest tests/test_admin.py::TestAdminHealth::test_health_endpoint -v`

Expected: PASS

**Step 6: Commit**

```bash
git add src/cal_provider/admin/ tests/test_admin.py
git commit -m "Add admin package scaffolding with /api/status endpoint

Session: S-2026-02-25-0235-cal-provider-v020-hardening"
```

---

### Task 3: POST /api/test-connection — Test credentials and return calendars

This is the core of the setup wizard backend. Accepts provider type + credentials, instantiates a provider, calls `list_calendars()`, returns results or error.

**Files:**
- Modify: `src/cal_provider/admin/app.py`
- Modify: `tests/test_admin.py`

**Step 1: Write the failing tests**

Add to `tests/test_admin.py`:

```python
from unittest.mock import patch, MagicMock, AsyncMock
from cal_provider.models import CalendarInfo


class TestTestConnection:
    def test_google_success(self, client):
        """Successful Google connection returns calendar list."""
        mock_provider = MagicMock()
        mock_provider.list_calendars = AsyncMock(return_value=[
            CalendarInfo(id="primary", name="Main", primary=True),
            CalendarInfo(id="work@group", name="Work"),
        ])

        with patch("cal_provider.admin.app.get_provider", return_value=mock_provider):
            resp = client.post("/api/test-connection", json={
                "provider": "google",
                "google_service_account_json": "/fake/sa.json",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert len(data["calendars"]) == 2
        assert data["calendars"][0]["name"] == "Main"

    def test_caldav_success(self, client):
        """Successful CalDAV connection returns calendar list."""
        mock_provider = MagicMock()
        mock_provider.list_calendars = AsyncMock(return_value=[
            CalendarInfo(id="https://cal.example.com/work/", name="Work", primary=True),
        ])

        with patch("cal_provider.admin.app.get_provider", return_value=mock_provider):
            resp = client.post("/api/test-connection", json={
                "provider": "caldav",
                "caldav_url": "https://caldav.example.com/",
                "caldav_username": "user",
                "caldav_password": "pass",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    def test_connection_failure(self, client):
        """Auth failure returns success=False with error message."""
        with patch("cal_provider.admin.app.get_provider", side_effect=Exception("Bad credentials")):
            resp = client.post("/api/test-connection", json={
                "provider": "google",
                "google_service_account_json": "/bad/path.json",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "Bad credentials" in data["error"]
```

**Step 2: Run tests to verify they fail**

Run: `cd ~/src/cal-provider && .venv/bin/python -m pytest tests/test_admin.py::TestTestConnection -v`

Expected: FAIL — 404 (route not defined yet)

**Step 3: Implement the endpoint**

Add to `app.py`:

```python
from pydantic import BaseModel
from cal_provider.registry import get_provider
from cal_provider.exceptions import CalendarProviderError


class ConnectionRequest(BaseModel):
    provider: str  # "google" or "caldav"
    google_service_account_json: str | None = None
    google_send_updates: str = "none"
    caldav_url: str | None = None
    caldav_username: str | None = None
    caldav_password: str | None = None


@app.post("/api/test-connection")
async def test_connection(req: ConnectionRequest):
    """Test provider credentials and return available calendars."""
    global _provider, _provider_config

    try:
        if req.provider == "google":
            provider = get_provider(
                "google",
                service_account_path=req.google_service_account_json,
                send_updates=req.google_send_updates,
            )
        elif req.provider == "caldav":
            provider = get_provider(
                "caldav",
                url=req.caldav_url,
                username=req.caldav_username,
                password=req.caldav_password,
            )
        else:
            return {"success": False, "error": f"Unknown provider: {req.provider}"}

        calendars = await provider.list_calendars()
        _provider = provider
        _provider_config = {
            "provider_name": req.provider,
            "calendar_id": calendars[0].id if calendars else None,
        }

        return {
            "success": True,
            "calendars": [
                {"id": c.id, "name": c.name, "primary": c.primary}
                for c in calendars
            ],
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
```

**Step 4: Run tests to verify they pass**

Run: `cd ~/src/cal-provider && .venv/bin/python -m pytest tests/test_admin.py -v`

Expected: All PASS

**Step 5: Commit**

```bash
git add src/cal_provider/admin/app.py tests/test_admin.py
git commit -m "Add /api/test-connection endpoint for setup wizard

Session: S-2026-02-25-0235-cal-provider-v020-hardening"
```

---

### Task 4: POST /api/save-config — Generate and save .env file

**Files:**
- Modify: `src/cal_provider/admin/app.py`
- Modify: `tests/test_admin.py`

**Step 1: Write the failing test**

```python
import tempfile
from pathlib import Path


class TestSaveConfig:
    def test_save_google_env(self, client, tmp_path):
        """Saves a .env file with Google config."""
        resp = client.post("/api/save-config", json={
            "provider": "google",
            "google_service_account_json": "/path/to/sa.json",
            "google_send_updates": "none",
            "output_dir": str(tmp_path),
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

        env_file = tmp_path / ".env"
        assert env_file.exists()
        content = env_file.read_text()
        assert "CAL_PROVIDER=google" in content
        assert "GOOGLE_SERVICE_ACCOUNT_JSON=/path/to/sa.json" in content

    def test_save_generates_claude_config(self, client, tmp_path):
        """Response includes Claude Code config snippet."""
        resp = client.post("/api/save-config", json={
            "provider": "google",
            "google_service_account_json": "/path/to/sa.json",
            "output_dir": str(tmp_path),
        })

        data = resp.json()
        assert "claude_config" in data
        assert "mcpServers" in data["claude_config"]
```

**Step 2: Run tests, verify fail**

**Step 3: Implement**

```python
class SaveConfigRequest(BaseModel):
    provider: str
    google_service_account_json: str | None = None
    google_send_updates: str = "none"
    caldav_url: str | None = None
    caldav_username: str | None = None
    caldav_password: str | None = None
    output_dir: str = "."


@app.post("/api/save-config")
async def save_config(req: SaveConfigRequest):
    """Generate config files (.env, env vars, Claude Code snippet)."""
    lines = [f"CAL_PROVIDER={req.provider}"]

    if req.provider == "google":
        lines.append(f"GOOGLE_SERVICE_ACCOUNT_JSON={req.google_service_account_json or ''}")
    elif req.provider == "caldav":
        lines.append(f"CALDAV_URL={req.caldav_url or ''}")
        lines.append(f"CALDAV_USERNAME={req.caldav_username or ''}")
        lines.append(f"CALDAV_PASSWORD={req.caldav_password or ''}")

    env_content = "\n".join(lines) + "\n"

    # Write .env file
    output_path = Path(req.output_dir) / ".env"
    try:
        output_path.write_text(env_content)
    except OSError as e:
        return {"success": False, "error": f"Failed to write .env: {e}"}

    # Build Claude Code config snippet
    env_block = {}
    for line in lines:
        key, _, value = line.partition("=")
        env_block[key] = value

    claude_config = {
        "mcpServers": {
            "calendar": {
                "command": "cal-provider-mcp",
                "env": env_block,
            }
        }
    }

    return {
        "success": True,
        "env_file": str(output_path),
        "env_content": env_content,
        "export_commands": "\n".join(f"export {line}" for line in lines),
        "claude_config": claude_config,
    }
```

**Step 4: Run tests, verify pass**

**Step 5: Commit**

```bash
git add src/cal_provider/admin/app.py tests/test_admin.py
git commit -m "Add /api/save-config endpoint for .env generation

Session: S-2026-02-25-0235-cal-provider-v020-hardening"
```

---

### Task 5: Dashboard API — calendars, events, available slots, test event

**Files:**
- Modify: `src/cal_provider/admin/app.py`
- Modify: `tests/test_admin.py`

**Step 1: Write the failing tests**

```python
class TestDashboardAPI:
    @pytest.fixture(autouse=True)
    def setup_provider(self, client):
        """Pre-configure a mock provider in the admin app."""
        import cal_provider.admin.app as admin_app

        mock = MagicMock()
        mock.list_calendars = AsyncMock(return_value=[
            CalendarInfo(id="primary", name="Main", primary=True),
        ])
        mock.get_events = AsyncMock(return_value=[])
        mock.get_available_slots = AsyncMock(return_value=[])
        mock.create_event = AsyncMock(return_value={
            "event_id": "test-evt-1", "status": "confirmed"
        })
        mock.cancel_event = AsyncMock(return_value=True)

        admin_app._provider = mock
        admin_app._provider_config = {
            "provider_name": "google",
            "calendar_id": "primary",
        }
        yield
        admin_app._provider = None
        admin_app._provider_config = {}

    def test_list_calendars(self, client):
        resp = client.get("/api/calendars")
        assert resp.status_code == 200
        assert len(resp.json()["calendars"]) == 1

    def test_get_events(self, client):
        resp = client.get("/api/events", params={
            "calendar_id": "primary",
            "start": "2026-03-15T09:00:00+00:00",
            "end": "2026-03-15T18:00:00+00:00",
        })
        assert resp.status_code == 200
        assert "events" in resp.json()

    def test_get_available_slots(self, client):
        resp = client.get("/api/available-slots", params={
            "calendar_id": "primary",
            "start": "2026-03-15T09:00:00+00:00",
            "end": "2026-03-15T18:00:00+00:00",
        })
        assert resp.status_code == 200
        assert "slots" in resp.json()

    def test_test_event(self, client):
        resp = client.post("/api/test-event", json={
            "calendar_id": "primary",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["created_event_id"] == "test-evt-1"
        assert data["cancelled"] is True

    def test_not_configured_returns_error(self, client):
        """API calls before setup return helpful error."""
        import cal_provider.admin.app as admin_app
        admin_app._provider = None

        resp = client.get("/api/calendars")
        assert resp.status_code == 200
        assert resp.json()["error"] is not None
```

**Step 2: Run tests, verify fail**

**Step 3: Implement the four dashboard endpoints**

```python
from datetime import datetime, timedelta, timezone
from cal_provider.models import CalendarEvent


def _require_provider():
    """Return provider or error dict."""
    if _provider is None:
        return None, {"error": "Not configured. Run the setup wizard first."}
    return _provider, None


@app.get("/api/calendars")
async def list_calendars():
    provider, err = _require_provider()
    if err:
        return err
    calendars = await provider.list_calendars()
    return {
        "calendars": [
            {"id": c.id, "name": c.name, "primary": c.primary, "description": c.description}
            for c in calendars
        ]
    }


@app.get("/api/events")
async def get_events(calendar_id: str, start: str, end: str):
    provider, err = _require_provider()
    if err:
        return err
    events = await provider.get_events(
        calendar_id,
        datetime.fromisoformat(start),
        datetime.fromisoformat(end),
    )
    return {
        "events": [
            {
                "summary": e.summary,
                "start": e.start.isoformat(),
                "end": e.end.isoformat(),
                "location": e.location,
                "attendees": e.attendees,
            }
            for e in events
        ]
    }


@app.get("/api/available-slots")
async def get_available_slots(
    calendar_id: str, start: str, end: str, duration_minutes: int = 60
):
    provider, err = _require_provider()
    if err:
        return err
    slots = await provider.get_available_slots(
        calendar_id,
        datetime.fromisoformat(start),
        datetime.fromisoformat(end),
        duration_minutes,
    )
    return {
        "slots": [
            {"start": s.start.isoformat(), "end": s.end.isoformat(), "duration_minutes": s.duration_minutes}
            for s in slots
        ]
    }


class TestEventRequest(BaseModel):
    calendar_id: str


@app.post("/api/test-event")
async def test_event(req: TestEventRequest):
    provider, err = _require_provider()
    if err:
        return err
    now = datetime.now(tz=timezone.utc) + timedelta(days=1)
    event = CalendarEvent(
        summary="[cal-provider test] Delete me",
        start=now,
        end=now + timedelta(minutes=15),
        description="Automatically created by cal-provider admin. Safe to delete.",
    )
    try:
        result = await provider.create_event(req.calendar_id, event)
        event_id = result["event_id"]
        cancelled = await provider.cancel_event(req.calendar_id, event_id)
        return {
            "success": True,
            "created_event_id": event_id,
            "cancelled": cancelled,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
```

**Step 4: Run tests, verify pass**

Run: `cd ~/src/cal-provider && .venv/bin/python -m pytest tests/test_admin.py -v`

**Step 5: Commit**

```bash
git add src/cal_provider/admin/app.py tests/test_admin.py
git commit -m "Add dashboard API endpoints: calendars, events, slots, test-event

Session: S-2026-02-25-0235-cal-provider-v020-hardening"
```

---

### Task 6: HTML templates — base layout + setup wizard

**Files:**
- Create: `src/cal_provider/admin/static/style.css`
- Create: `src/cal_provider/admin/templates/base.html`
- Create: `src/cal_provider/admin/templates/setup.html`
- Modify: `src/cal_provider/admin/app.py` (add page routes)

**Step 1: Write a smoke test for the page routes**

```python
class TestPageRoutes:
    def test_setup_page_loads(self, client):
        resp = client.get("/setup")
        assert resp.status_code == 200
        assert "cal-provider" in resp.text.lower()

    def test_root_redirects_to_setup(self, client):
        resp = client.get("/", follow_redirects=False)
        assert resp.status_code in (302, 307)
```

**Step 2: Run, verify fail**

**Step 3: Create the CSS, base template, setup template, and page routes**

`style.css` — Clean, minimal developer-tool aesthetic. System fonts. ~100 lines covering layout, cards, forms, status indicators, code blocks.

`base.html` — Jinja2 layout with nav (Setup | Dashboard), block content, links to style.css.

`setup.html` — Four-step wizard:
- Step 1: Provider radio buttons (Google / CalDAV)
- Step 2: Credential form (dynamic — shows Google or CalDAV fields based on selection)
- Step 3: "Test Connection" button → calls `/api/test-connection` via fetch → shows calendar list
- Step 4: "Generate Config" → calls `/api/save-config` → shows three tabs (env vars, .env, Claude Code JSON)

All interactivity via vanilla JS `fetch()` calls — no framework needed.

Add to `app.py`:
```python
from fastapi.responses import RedirectResponse

@app.get("/")
async def root():
    return RedirectResponse(url="/setup")

@app.get("/setup")
async def setup_page(request: Request):
    return templates.TemplateResponse("setup.html", {"request": request})
```

**Step 4: Run tests, verify pass. Also manually verify: `cal-provider-admin` → open `localhost:8100/setup`**

**Step 5: Commit**

```bash
git add src/cal_provider/admin/
git commit -m "Add setup wizard page with provider selection and config generation

Session: S-2026-02-25-0235-cal-provider-v020-hardening"
```

---

### Task 7: HTML templates — dashboard page

**Files:**
- Create: `src/cal_provider/admin/templates/dashboard.html`
- Modify: `src/cal_provider/admin/app.py` (add dashboard route)

**Step 1: Write a smoke test**

```python
    def test_dashboard_page_loads(self, client):
        resp = client.get("/dashboard")
        assert resp.status_code == 200
        assert "dashboard" in resp.text.lower()
```

**Step 2: Run, verify fail**

**Step 3: Create dashboard template and route**

`dashboard.html` — Three panels:
- **Connection status** — Fetches `/api/status` on load, shows green/red indicator
- **Calendar explorer** — Fetches `/api/calendars`, lists them. Click → fetches `/api/events` for today
- **Test panel** — "Check Availability" form (calendar, date range) → calls `/api/available-slots`. "Create Test Event" button → calls `/api/test-event`. Collapsible raw JSON viewer for API responses.

Add to `app.py`:
```python
@app.get("/dashboard")
async def dashboard_page(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})
```

**Step 4: Run tests + manual verification**

**Step 5: Commit**

```bash
git add src/cal_provider/admin/
git commit -m "Add dashboard page with calendar explorer and test panel

Session: S-2026-02-25-0235-cal-provider-v020-hardening"
```

---

### Task 8: Config snippet page

**Files:**
- Create: `src/cal_provider/admin/templates/config.html`
- Modify: `src/cal_provider/admin/app.py`

**Step 1: Write smoke test**

```python
    def test_config_page_loads(self, client):
        resp = client.get("/config")
        assert resp.status_code == 200
```

**Step 2: Run, verify fail**

**Step 3: Create config template**

`config.html` — Three-tab view for generated config. Populated by JS calling `/api/save-config`. Copy-to-clipboard buttons. Preview of what each format looks like before saving.

```python
@app.get("/config")
async def config_page(request: Request):
    return templates.TemplateResponse("config.html", {"request": request})
```

**Step 4: Run tests, verify pass**

**Step 5: Commit**

```bash
git add src/cal_provider/admin/
git commit -m "Add config snippet page with env vars, .env, and Claude Code tabs

Session: S-2026-02-25-0235-cal-provider-v020-hardening"
```

---

### Task 9: README rewrite — progressive, task-oriented

**Files:**
- Rewrite: `README.md`

**Step 1: No test needed — this is documentation**

**Step 2: Write the README**

Structure (see design doc for full spec):

```markdown
# cal-provider

Unified async calendar API for Python. One interface, multiple backends.

## 30-Second Quick Start

[pip install + 5 lines of code that check availability]

## 5-Minute Setup (Admin UI)

[pip install cal-provider[admin,google] → cal-provider-admin → screenshot description of wizard]

## Recipes

### Check availability
[5 lines]

### Book a meeting
[8 lines]

### List all calendars
[3 lines]

### Get events in your timezone
[6 lines]

### Handle errors gracefully
[10 lines with try/except showing exception hierarchy]

## API Reference
[Table of all methods with signatures]

## Models
[TimeSlot, CalendarEvent, CalendarInfo with properties]

## Exceptions
[Hierarchy diagram + example]

## Backend Setup

### Google Calendar
[Step-by-step: enable API, create SA, share calendar]

### CalDAV
[Table: iCloud, Nextcloud, Fastmail URLs + auth]

## For AI Agents (MCP Server)
[CLI command + Claude Code / Cursor config JSON]

## Admin Dashboard
[What it does, how to run, endpoints]

## Writing a Custom Provider
[ABC pattern, 20-line skeleton]

## Architecture
[File tree with one-line descriptions]
```

Key principles:
- Every code example is copy-pasteable and works
- Concepts explained inline, not in separate sections
- No "see the docs for more" — everything is here
- Progressive: each section assumes you read the previous ones

**Step 3: Commit**

```bash
git add README.md
git commit -m "Rewrite README as progressive task-oriented developer guide

Session: S-2026-02-25-0235-cal-provider-v020-hardening"
```

---

### Task 10: Integration test — full wizard flow

**Files:**
- Modify: `tests/test_admin.py`

**Step 1: Write an end-to-end test**

```python
class TestWizardFlow:
    def test_full_setup_flow(self, client, tmp_path):
        """Simulate the complete setup wizard: test connection → save config → verify status."""
        mock_provider = MagicMock()
        mock_provider.list_calendars = AsyncMock(return_value=[
            CalendarInfo(id="primary", name="Main", primary=True),
        ])

        with patch("cal_provider.admin.app.get_provider", return_value=mock_provider):
            # Step 1: Test connection
            resp = client.post("/api/test-connection", json={
                "provider": "google",
                "google_service_account_json": "/fake/sa.json",
            })
            assert resp.json()["success"] is True

        # Step 2: Verify status shows configured
        resp = client.get("/api/status")
        assert resp.json()["configured"] is True
        assert resp.json()["provider"] == "google"

        # Step 3: Save config
        resp = client.post("/api/save-config", json={
            "provider": "google",
            "google_service_account_json": "/fake/sa.json",
            "output_dir": str(tmp_path),
        })
        assert resp.json()["success"] is True
        assert (tmp_path / ".env").exists()

        # Step 4: Verify .env content
        content = (tmp_path / ".env").read_text()
        assert "CAL_PROVIDER=google" in content
```

**Step 2: Run, verify pass**

**Step 3: Run full test suite**

Run: `cd ~/src/cal-provider && .venv/bin/python -m pytest tests/ -v`

Expected: All tests pass (68 existing + new admin tests)

**Step 4: Commit**

```bash
git add tests/test_admin.py
git commit -m "Add integration test for full setup wizard flow

Session: S-2026-02-25-0235-cal-provider-v020-hardening"
```

---

### Task 11: Final verification and cleanup

**Step 1: Run entire test suite**

```bash
cd ~/src/cal-provider && .venv/bin/python -m pytest tests/ -v
```

**Step 2: Verify CLI entry point works**

```bash
cd ~/src/cal-provider && .venv/bin/pip install -e ".[admin,google]"
.venv/bin/cal-provider-admin &
sleep 2
curl -s http://localhost:8100/api/status | python -m json.tool
kill %1
```

**Step 3: Verify version**

```bash
.venv/bin/python -c "import cal_provider; print(cal_provider.__version__)"
```

**Step 4: Verify FSM tests still pass**

```bash
cd ~/src/voice-calendar-scheduler-FSM
PYTHONPATH=".:engine-repo" .venv/bin/python -m pytest tests/ -v
```

**Step 5: Final commit if any cleanup needed**

---

## Summary

| Task | What | Tests |
|------|------|-------|
| 1 | pyproject.toml deps + entry point | — |
| 2 | Admin scaffolding + /api/status | 1 test |
| 3 | POST /api/test-connection | 3 tests |
| 4 | POST /api/save-config | 2 tests |
| 5 | Dashboard API (calendars, events, slots, test-event) | 5 tests |
| 6 | Setup wizard HTML (base + setup templates) | 2 tests |
| 7 | Dashboard HTML | 1 test |
| 8 | Config snippet page | 1 test |
| 9 | README rewrite | — |
| 10 | Integration test | 1 test |
| 11 | Verification + cleanup | — |

**Total new tests:** ~16
**Total estimated commits:** 11
