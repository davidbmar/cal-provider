# Design: cal-provider Admin UI + README Rewrite

**Date:** 2026-02-25
**Status:** Approved
**Author:** David Mar

## Goal

Make cal-provider delightful for AI-tool developers to get started with. Two deliverables:

1. **Admin UI** — A built-in FastAPI web app that walks developers through credential setup, tests the connection, and generates config snippets.
2. **README rewrite** — Task-oriented, progressive-disclosure README that teaches by showing working code.

## Target User

AI-tool developers building agents/apps that need calendar access. They'll use cal-provider as a library and/or run the MCP server for Claude Code / Cursor integration.

## Admin UI

### Architecture

The admin UI is an optional sub-package inside cal-provider, following the same pattern as the MCP server:

```
src/cal_provider/
  admin/
    __init__.py
    app.py                  # FastAPI app
    templates/
      base.html             # Shared layout with nav
      setup.html            # Setup wizard
      dashboard.html        # Connection status + calendar explorer
      config.html           # Generated config snippets
    static/
      style.css             # Minimal CSS (no build step)
```

**Entry point:** `cal-provider-admin` CLI → uvicorn on port 8100.

**Dependency group:** `pip install cal-provider[admin]` adds fastapi, uvicorn, jinja2, python-multipart.

### Setup Wizard Flow

1. **Choose provider** — Radio buttons: Google Calendar / CalDAV. Brief description of each + what you'll need.
2. **Enter credentials** — Google: file upload for SA JSON + send_updates toggle. CalDAV: URL, username, password + preset buttons for iCloud/Nextcloud/Fastmail.
3. **Test connection** — Calls `list_calendars()`, shows results. Clear error messages with fix instructions on failure.
4. **Generate config** — Three tabs: env vars (copy-paste), `.env` file (download), Claude Code JSON snippet. "Save .env" button writes to project root.

### Dashboard

- **Connection panel** — Green/red status, provider type, calendar ID, last successful call.
- **Calendar explorer** — List accessible calendars. Click → see upcoming events.
- **Test panel** — Check availability (date range → free slots), create test event (creates + immediately cancels), raw API response viewer.

### Backend API

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/test-connection` | POST | Test credentials, return calendar list |
| `/api/save-config` | POST | Write .env file to disk |
| `/api/calendars` | GET | List calendars for current config |
| `/api/status` | GET | Connection health + provider info |
| `/api/events` | GET | Events for a calendar in a date range |
| `/api/available-slots` | GET | Available slots for a calendar |
| `/api/test-event` | POST | Create and immediately cancel a test event |

No server-side storage beyond the current process. Credentials only persist when developer saves .env.

## README Structure

Progressive disclosure — each section goes deeper:

```
# cal-provider

One-line pitch + badges

## 30-Second Quick Start        — Copy-paste, see it work
## 5-Minute Setup Guide         — Admin UI wizard walkthrough
## Recipes                      — Task-oriented code examples
  - Check availability (5 lines)
  - Book a meeting (8 lines)
  - List calendars (3 lines)
  - Timezone-aware queries (6 lines)
  - Handle errors gracefully (10 lines)
## API Reference                — Full method signatures table
## Backend Setup Guides         — Google service account, CalDAV providers
## For AI Agents (MCP Server)   — Claude Code / Cursor config
## Writing a Custom Provider    — Extend with Outlook, Zoho, etc.
```

Each recipe: working code + one-sentence explanation of what and why.

## Decisions

- **Built-in FastAPI admin** over separate frontend — single package, credentials stay local, consistent with MCP server pattern.
- **Jinja2 templates + minimal CSS** over React/Next.js — no build step, no Node.js dependency, functional UI for developer tooling.
- **Optional dependency group** — `[admin]` keeps core library zero-dependency.
- **No persistent storage** — wizard generates config files, doesn't store credentials server-side.

## Out of Scope (for now)

- OAuth flow for end-user calendar access (service accounts only)
- PyPI publishing automation
- CI/CD pipeline
- Real-time event webhooks
