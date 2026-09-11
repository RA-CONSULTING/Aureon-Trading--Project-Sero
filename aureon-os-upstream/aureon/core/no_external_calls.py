"""Global air-gap guard for external API calls.

Provides a single environment switch, ``AUREON_NO_EXTERNAL_API_CALLS=1``,
that consumers can read at call-time to fail-closed against outbound
network requests when the system must run fully autonomously without
external dependencies.
"""

from __future__ import annotations

import os


_TRUTHY = {"1", "true", "yes", "on", "t", "y"}


def no_external_api_calls() -> bool:
    """Return True when ``AUREON_NO_EXTERNAL_API_CALLS`` is set to a truthy value."""
    return os.environ.get("AUREON_NO_EXTERNAL_API_CALLS", "").strip().lower() in _TRUTHY


def external_calls_blocked_reason() -> str:
    return "AUREON_NO_EXTERNAL_API_CALLS is set"
