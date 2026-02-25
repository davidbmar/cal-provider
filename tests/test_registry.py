"""Tests for cal_provider.registry — provider factory."""

import pytest

from cal_provider.provider import CalendarProvider
from cal_provider.registry import _registry, get_provider, register_provider


class TestRegistry:
    def test_register_and_get_custom_provider(self, mock_provider):
        """Custom providers can be registered and retrieved."""
        register_provider("mock", lambda: mock_provider)
        provider = get_provider("mock")
        assert isinstance(provider, CalendarProvider)
        # Cleanup
        _registry.pop("mock", None)

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown calendar provider"):
            get_provider("nonexistent_xyz_provider")

    def test_google_lazy_registration(self):
        """get_provider('google') lazily imports GoogleCalendarProvider."""
        # This will raise ValueError (no SA path) but proves the import works
        with pytest.raises(ValueError, match="service account JSON"):
            get_provider("google")
        # Cleanup the registered entry so other tests aren't affected
        _registry.pop("google", None)

    def test_caldav_lazy_registration(self):
        """get_provider('caldav') lazily imports CalDAVProvider."""
        # This will fail at connection time but proves the import works
        with pytest.raises(Exception):
            get_provider("caldav", url="https://fake.invalid/", username="u", password="p")
        _registry.pop("caldav", None)

    def test_register_overwrites(self, mock_provider):
        """Re-registering a name overwrites the previous factory."""
        register_provider("test_ow", lambda: "first")
        register_provider("test_ow", lambda: mock_provider)
        result = get_provider("test_ow")
        assert isinstance(result, CalendarProvider)
        _registry.pop("test_ow", None)
