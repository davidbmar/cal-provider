"""Tests for the admin web UI."""

from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from fastapi.testclient import TestClient

from cal_provider.admin.app import app
from cal_provider.models import CalendarInfo


@pytest.fixture
def client():
    return TestClient(app)


class TestAdminHealth:
    def test_health_endpoint(self, client):
        resp = client.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "configured" in data


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
