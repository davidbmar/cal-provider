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
