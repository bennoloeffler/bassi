"""
Tests for configuration management
"""

import pytest

from bassi.config import Config, ConfigManager


def test_config_defaults():
    """Test default configuration values"""
    config = Config()

    assert len(config.root_folders) > 0
    assert config.log_level == "INFO"
    assert config.max_search_results == 50
    assert config.anthropic_api_key is None


def test_config_custom_values():
    """Test configuration with custom values"""
    config = Config(
        root_folders=["/tmp", "/home"],
        log_level="DEBUG",
        max_search_results=100,
    )

    assert config.root_folders == ["/tmp", "/home"]
    assert config.log_level == "DEBUG"
    assert config.max_search_results == 100


def test_config_manager_creates_config_dir(tmp_path, monkeypatch):
    """Test that ConfigManager creates config directory"""
    test_config_dir = tmp_path / ".bassi"
    test_config_file = test_config_dir / "config.json"

    # Mock the config paths
    monkeypatch.setattr(ConfigManager, "CONFIG_DIR", test_config_dir)
    monkeypatch.setattr(ConfigManager, "CONFIG_FILE", test_config_file)

    # Create manager
    manager = ConfigManager()

    assert test_config_dir.exists()
    assert test_config_file.exists()
    assert manager.get_config() is not None


def test_config_manager_loads_existing_config(tmp_path, monkeypatch):
    """Test loading existing configuration"""
    test_config_dir = tmp_path / ".bassi"
    test_config_file = test_config_dir / "config.json"

    test_config_dir.mkdir()

    # Write test config
    import json

    test_data = {
        "root_folders": ["/test1", "/test2"],
        "log_level": "DEBUG",
        "max_search_results": 75,
        "anthropic_api_key": None,
    }

    with open(test_config_file, "w") as f:
        json.dump(test_data, f)

    # Mock the config paths
    monkeypatch.setattr(ConfigManager, "CONFIG_DIR", test_config_dir)
    monkeypatch.setattr(ConfigManager, "CONFIG_FILE", test_config_file)

    # Load config
    manager = ConfigManager()
    config = manager.get_config()

    assert config.root_folders == ["/test1", "/test2"]
    assert config.log_level == "DEBUG"
    assert config.max_search_results == 75


def test_get_api_key_from_env(tmp_path, monkeypatch):
    """Test getting API key from environment"""
    test_config_dir = tmp_path / ".bassi"
    test_config_file = test_config_dir / "config.json"

    monkeypatch.setattr(ConfigManager, "CONFIG_DIR", test_config_dir)
    monkeypatch.setattr(ConfigManager, "CONFIG_FILE", test_config_file)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-123")

    manager = ConfigManager()
    api_key = manager.get_api_key()

    assert api_key == "test-key-123"


def test_get_api_key_missing_raises_error(tmp_path, monkeypatch):
    """Test that missing API key raises ValueError"""
    test_config_dir = tmp_path / ".bassi"
    test_config_file = test_config_dir / "config.json"

    monkeypatch.setattr(ConfigManager, "CONFIG_DIR", test_config_dir)
    monkeypatch.setattr(ConfigManager, "CONFIG_FILE", test_config_file)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    manager = ConfigManager()

    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY not found"):
        manager.get_api_key()
