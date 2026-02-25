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
