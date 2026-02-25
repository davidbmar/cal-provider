"""Tests for cal_provider.exceptions hierarchy."""

import pytest

from cal_provider.exceptions import (
    AuthenticationError,
    CalendarNotFoundError,
    CalendarProviderError,
    EventNotFoundError,
    PermissionError,
)


class TestExceptionHierarchy:
    def test_all_inherit_from_base(self):
        """All custom exceptions should be subclasses of CalendarProviderError."""
        for exc_class in [
            AuthenticationError,
            CalendarNotFoundError,
            EventNotFoundError,
            PermissionError,
        ]:
            assert issubclass(exc_class, CalendarProviderError)

    def test_base_is_exception(self):
        assert issubclass(CalendarProviderError, Exception)

    def test_catch_base_catches_all(self):
        """Catching CalendarProviderError should catch all subtypes."""
        for exc_class in [
            AuthenticationError,
            CalendarNotFoundError,
            EventNotFoundError,
            PermissionError,
        ]:
            with pytest.raises(CalendarProviderError):
                raise exc_class("test message")

    def test_specific_catch(self):
        """Each exception can be caught specifically."""
        with pytest.raises(AuthenticationError):
            raise AuthenticationError("bad token")

        with pytest.raises(CalendarNotFoundError):
            raise CalendarNotFoundError("no such calendar")

        with pytest.raises(EventNotFoundError):
            raise EventNotFoundError("no such event")

        with pytest.raises(PermissionError):
            raise PermissionError("no write access")

    def test_message_preserved(self):
        exc = AuthenticationError("expired token")
        assert str(exc) == "expired token"


class TestPublicImports:
    def test_import_from_package(self):
        """Exceptions should be importable from cal_provider top-level."""
        from cal_provider import (
            CalendarPermissionError,
            CalendarProviderError,
            AuthenticationError,
            CalendarNotFoundError,
            EventNotFoundError,
        )
        assert issubclass(CalendarPermissionError, CalendarProviderError)

    def test_version_importable(self):
        from cal_provider import __version__
        assert __version__ == "0.2.0"
