"""Provider registry and factory.

Built-in providers are registered lazily — their optional dependencies
are only imported when ``get_provider()`` is called for that backend.
Third-party providers can register themselves via ``register_provider()``.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from cal_provider.provider import CalendarProvider

logger = logging.getLogger(__name__)

# Maps provider name → factory callable
_registry: dict[str, Callable[..., CalendarProvider]] = {}


def register_provider(
    name: str,
    factory: Callable[..., CalendarProvider],
) -> None:
    """Register a provider factory under the given name.

    Args:
        name: Short identifier (e.g. ``"google"``, ``"caldav"``).
        factory: Callable that accepts keyword arguments and returns
                 a ``CalendarProvider`` instance.
    """
    _registry[name] = factory
    logger.debug("Registered calendar provider: %s", name)


def get_provider(name: str, **kwargs: Any) -> CalendarProvider:
    """Instantiate a calendar provider by name.

    Built-in providers (``"google"``, ``"caldav"``) are imported lazily.
    Third-party providers must be registered first via
    ``register_provider()``.

    Args:
        name: Provider name.
        **kwargs: Passed to the provider constructor.

    Returns:
        A ``CalendarProvider`` instance.

    Raises:
        ValueError: If the provider name is not recognized.
        ImportError: If required optional dependencies are missing.
    """
    # Lazy-register built-in providers on first access
    if name not in _registry:
        _try_register_builtin(name)

    if name not in _registry:
        available = ", ".join(sorted(_registry.keys())) or "(none)"
        raise ValueError(
            f"Unknown calendar provider: {name!r}. "
            f"Available providers: {available}"
        )

    return _registry[name](**kwargs)


def _try_register_builtin(name: str) -> None:
    """Attempt to lazily register a built-in provider."""
    if name == "google":
        try:
            from cal_provider.providers.google import GoogleCalendarProvider
            register_provider("google", GoogleCalendarProvider)
        except ImportError:
            raise ImportError(
                "Google Calendar dependencies not installed. "
                "Install with: pip install cal-provider[google]"
            )
    elif name == "caldav":
        try:
            from cal_provider.providers.caldav_provider import CalDAVProvider
            register_provider("caldav", CalDAVProvider)
        except ImportError:
            raise ImportError(
                "CalDAV dependencies not installed. "
                "Install with: pip install cal-provider[caldav]"
            )
