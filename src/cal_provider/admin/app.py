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
from pydantic import BaseModel

from cal_provider.registry import get_provider

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


def main():
    """CLI entry point for cal-provider-admin."""
    port = int(os.environ.get("CAL_PROVIDER_ADMIN_PORT", "8100"))
    print(f"cal-provider admin → http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
