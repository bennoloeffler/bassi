"""
Permission configuration helpers.

Provides a single source of truth for deriving the Agent SDK
``permission_mode`` from environment variables while validating inputs.
"""

from __future__ import annotations

import logging
import os
from typing import Final

LOGGER = logging.getLogger(__name__)

# Canonical permission mode names supported by the Claude Agent SDK
_CANONICAL_MODES: Final[dict[str, str]] = {
    "bypasspermissions": "bypassPermissions",
    "acceptedits": "acceptEdits",
    "default": "default",
    "plan": "plan",
}


def get_permission_mode(
    *,
    env_var: str = "BASSI_PERMISSION_MODE",
    fallback: str = "bypassPermissions",
) -> str:
    """
    Determine the permission mode to pass to the Agent SDK.

    Reads ``env_var`` (defaults to ``BASSI_PERMISSION_MODE``) and validates the
    value against the SDK's supported permission modes.  Returns ``fallback``
    when the environment variable is unset, empty, or invalid.
    """
    raw_value = os.getenv(env_var)
    if not raw_value:
        return fallback

    normalized = raw_value.strip()
    if not normalized:
        return fallback

    canonical = _CANONICAL_MODES.get(normalized.lower())
    if canonical:
        return canonical

    LOGGER.warning(
        "Invalid permission mode '%s' configured in %s; falling back to %s. "
        "Valid modes: %s",
        normalized,
        env_var,
        fallback,
        ", ".join(sorted(set(_CANONICAL_MODES.values()))),
    )
    return fallback


__all__ = ["get_permission_mode"]
