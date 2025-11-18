"""Configuration service for user settings.

Manages persistent user preferences stored in ~/.bassi/config.json.
"""

import json
import logging
from pathlib import Path
from typing import Optional

LOGGER = logging.getLogger(__name__)


class ConfigService:
    """Manage user configuration stored in ~/.bassi/config.json"""

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize config service.

        Args:
            config_path: Override default config location (for testing)
        """
        if config_path is None:
            config_path = Path.home() / ".bassi" / "config.json"

        self.config_path = config_path
        self._ensure_config_exists()

    def _ensure_config_exists(self):
        """Create default config if it doesn't exist"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        if not self.config_path.exists():
            default_config = {
                "version": "1.0",
                "global_bypass_permissions": True,  # Current behavior
                "created_at": None,  # Will be set on first save
            }
            self._save_config(default_config)
            LOGGER.info(
                f"Created default config at {self.config_path}"
            )

    def _load_config(self) -> dict:
        """Load configuration from disk"""
        try:
            with open(self.config_path, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            LOGGER.warning(
                f"Failed to load config: {e}, using defaults"
            )
            return {"global_bypass_permissions": True}

    def _save_config(self, config: dict):
        """Save configuration to disk"""
        from datetime import datetime, timezone

        if "created_at" not in config or config["created_at"] is None:
            config["created_at"] = datetime.now(timezone.utc).isoformat()

        config["updated_at"] = datetime.now(timezone.utc).isoformat()

        with open(self.config_path, "w") as f:
            json.dump(config, f, indent=2)

        # Secure file permissions (user read/write only)
        self.config_path.chmod(0o600)

    def get_global_bypass_permissions(self) -> bool:
        """Get whether bypassPermissions mode is enabled

        Returns:
            True if agent should use bypassPermissions mode (autonomous),
            False if agent should use default mode (ask for permission)
        """
        config = self._load_config()
        return config.get("global_bypass_permissions", True)

    def set_global_bypass_permissions(self, enabled: bool):
        """Set whether bypassPermissions mode is enabled

        Args:
            enabled: True to enable bypassPermissions (autonomous),
                    False to use default mode (ask for permission)
        """
        config = self._load_config()
        config["global_bypass_permissions"] = enabled
        self._save_config(config)
        LOGGER.info(f"Global bypass permissions set to: {enabled}")

    def get_persistent_permissions(self) -> list[str]:
        """Get list of tools with persistent permission across all sessions

        Returns:
            List of tool names that are persistently allowed
        """
        config = self._load_config()
        return config.get("persistent_permissions", [])

    def set_persistent_permissions(self, tool_names: list[str]):
        """Set list of tools with persistent permission

        Args:
            tool_names: List of tool names to allow persistently
        """
        config = self._load_config()
        config["persistent_permissions"] = tool_names
        self._save_config(config)
        LOGGER.info(f"Persistent permissions updated: {tool_names}")
