"""FastAPI admin app for cal-provider.

Run via CLI: cal-provider-admin
Or: uvicorn cal_provider.admin.app:app --port 8100
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from cal_provider.models import CalendarEvent
from cal_provider.registry import get_provider

app = FastAPI(title="cal-provider admin")

# Template and static file paths
_HERE = Path(__file__).parent
app.mount("/static", StaticFiles(directory=_HERE / "static"), name="static")
templates = Jinja2Templates(directory=_HERE / "templates")

# In-process state (not persisted — lives for the lifetime of the server)
_provider = None
_provider_config: dict = {}


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    return RedirectResponse(url="/setup")


@app.get("/setup")
async def setup_page(request: Request):
    return templates.TemplateResponse(request, "setup.html")


@app.get("/dashboard")
async def dashboard_page(request: Request):
    return templates.TemplateResponse(request, "dashboard.html")


@app.get("/config")
async def config_page(request: Request):
    return templates.TemplateResponse(request, "config.html")


@app.get("/api/status")
async def status():
    """Connection health check."""
    return {
        "configured": _provider is not None,
        "provider": _provider_config.get("provider_name", None),
        "calendar_id": _provider_config.get("calendar_id", None),
    }


# ---------------------------------------------------------------------------
# POST /api/test-connection
# ---------------------------------------------------------------------------

class ConnectionRequest(BaseModel):
    provider: str
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


# ---------------------------------------------------------------------------
# POST /api/save-config
# ---------------------------------------------------------------------------

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

    output_path = Path(req.output_dir) / ".env"
    try:
        output_path.write_text(env_content)
    except OSError as e:
        return {"success": False, "error": f"Failed to write .env: {e}"}

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


# ---------------------------------------------------------------------------
# Dashboard API helpers
# ---------------------------------------------------------------------------

def _require_provider():
    """Return provider or error dict."""
    if _provider is None:
        return None, {"error": "Not configured. Run the setup wizard first."}
    return _provider, None


# ---------------------------------------------------------------------------
# GET /api/calendars
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# GET /api/events
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# GET /api/available-slots
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# POST /api/test-event
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    """CLI entry point for cal-provider-admin."""
    port = int(os.environ.get("CAL_PROVIDER_ADMIN_PORT", "8100"))
    print(f"cal-provider admin → http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
