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
    fallback: str = "default",
) -> str:
    """
    Determine the permission mode to pass to the Agent SDK.

    NOTE: Always returns "default" so can_use_tool_callback gets called.
    The callback (PermissionManager) handles permission logic internally,
    including global bypass, session permissions, and persistent permissions.

    Priority order:
    1. User settings from ConfigService (forces "default" mode)
    2. Environment variable BASSI_PERMISSION_MODE
    3. Fallback to "default"

    Returns:
        Permission mode string ("default" in most cases, or env var override)
    """
    # Priority 1: Check user settings from config file
    try:
        from bassi.core_v3.services.config_service import ConfigService

        config_service = ConfigService()
        global_bypass = config_service.get_global_bypass_permissions()

        # ALWAYS use "default" mode so can_use_tool_callback gets called
        # The callback (PermissionManager) handles the global_bypass check internally
        mode = "default"
        LOGGER.info(
            f"🔐 ConfigService: global_bypass={global_bypass} → mode={mode} (callback handles bypass)"
        )
        return mode
    except Exception as e:
        # If ConfigService fails, fall back to environment variable
        LOGGER.warning(
            f"ConfigService not available ({e}), using environment variable"
        )

    # Priority 2: Check environment variable
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
