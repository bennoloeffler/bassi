"""
Configuration management for bassi

Handles loading from ~/.bassi/config.json and .env files
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load .env file from project root
load_dotenv()


class Config(BaseModel):
    """Configuration model for bassi"""

    root_folders: list[str] = Field(
        default_factory=lambda: [str(Path.home())],
        description="Root folders to search for files",
    )
    log_level: str = Field(
        default="INFO", description="Logging level (DEBUG, INFO, WARNING)"
    )
    max_search_results: int = Field(
        default=50, description="Maximum number of search results"
    )
    anthropic_api_key: str | None = Field(
        default=None, description="Anthropic API key (optional override)"
    )
    tavily_api_key: str | None = Field(
        default=None,
        description="Tavily API key for web search (optional override)",
    )


class ConfigManager:
    """
    Black Box: Configuration Manager

    Interface:
    - get_config() -> Config: Returns current configuration
    - save_config(config: Config) -> None: Saves configuration
    - get_api_key() -> str: Returns Anthropic API key
    - get_tavily_api_key() -> str | None: Returns Tavily API key
    """

    CONFIG_DIR = Path.home() / ".bassi"
    CONFIG_FILE = CONFIG_DIR / "config.json"

    def __init__(self) -> None:
        self._ensure_config_exists()
        self.config = self._load_config()

    def _ensure_config_exists(self) -> None:
        """Create config directory and file if they don't exist"""
        if not self.CONFIG_DIR.exists():
            self.CONFIG_DIR.mkdir(parents=True)

        if not self.CONFIG_FILE.exists():
            default_config = Config()
            self._save_to_file(default_config)

    def _load_config(self) -> Config:
        """Load configuration from file"""
        with open(self.CONFIG_FILE) as f:
            data = json.load(f)
        return Config(**data)

    def _save_to_file(self, config: Config) -> None:
        """Save configuration to file"""
        with open(self.CONFIG_FILE, "w") as f:
            json.dump(config.model_dump(), f, indent=2)

    def get_config(self) -> Config:
        """Get current configuration"""
        return self.config

    def save_config(self, config: Config) -> None:
        """Save configuration"""
        self._save_to_file(config)
        self.config = config

    def get_api_key(self) -> str:
        """
        Get Anthropic API key from config or environment

        Priority: config.json > .env > environment variable
        """
        # Check config first
        if self.config.anthropic_api_key:
            return self.config.anthropic_api_key

        # Check environment
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY not found. "
                "Set it in .env or ~/.bassi/config.json"
            )

        return api_key

    def get_tavily_api_key(self) -> str | None:
        """
        Get Tavily API key from config or environment

        Priority: config.json > .env > environment variable
        Returns None if not configured (web search will be unavailable)
        """
        # Check config first
        if self.config.tavily_api_key:
            return self.config.tavily_api_key

        # Check environment
        return os.getenv("TAVILY_API_KEY")


# Global instance
_config_manager: ConfigManager | None = None


def get_config_manager() -> ConfigManager:
    """Get the global config manager instance"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager
