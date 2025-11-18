"""Tests for ConfigService."""

import json
import os

from bassi.core_v3.services.config_service import ConfigService


def test_default_config_created(tmp_path):
    """Config file created with defaults if missing"""
    config_path = tmp_path / "config.json"
    service = ConfigService(config_path)

    assert config_path.exists()
    assert service.get_global_bypass_permissions() is True


def test_config_has_version(tmp_path):
    """Config file includes version number"""
    config_path = tmp_path / "config.json"
    service = ConfigService(config_path)

    with open(config_path, "r") as f:
        data = json.load(f)

    assert data["version"] == "1.0"


def test_get_set_global_bypass(tmp_path):
    """Can get and set global bypass setting"""
    service = ConfigService(tmp_path / "config.json")

    # Default is True
    assert service.get_global_bypass_permissions() is True

    # Change to False
    service.set_global_bypass_permissions(False)
    assert service.get_global_bypass_permissions() is False

    # Persists across instances
    service2 = ConfigService(tmp_path / "config.json")
    assert service2.get_global_bypass_permissions() is False


def test_config_file_permissions(tmp_path):
    """Config file has secure permissions (600)"""
    config_path = tmp_path / "config.json"
    service = ConfigService(config_path)

    stat_info = os.stat(config_path)
    permissions = oct(stat_info.st_mode)[-3:]

    assert permissions == "600"  # User read/write only


def test_config_includes_timestamps(tmp_path):
    """Config includes created_at and updated_at timestamps"""
    config_path = tmp_path / "config.json"
    service = ConfigService(config_path)

    with open(config_path, "r") as f:
        data = json.load(f)

    assert "created_at" in data
    assert "updated_at" in data
    assert data["created_at"] is not None
    assert data["updated_at"] is not None


def test_config_updates_timestamp(tmp_path):
    """Updating config updates the updated_at timestamp"""
    config_path = tmp_path / "config.json"
    service = ConfigService(config_path)

    # Get initial timestamp
    with open(config_path, "r") as f:
        data1 = json.load(f)
    initial_updated = data1["updated_at"]

    # Update setting
    import time

    time.sleep(0.01)  # Ensure timestamp differs
    service.set_global_bypass_permissions(False)

    # Check timestamp changed
    with open(config_path, "r") as f:
        data2 = json.load(f)

    assert data2["updated_at"] != initial_updated


def test_config_handles_corrupted_file(tmp_path):
    """Service handles corrupted config gracefully"""
    config_path = tmp_path / "config.json"

    # Create corrupted file
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w") as f:
        f.write("not valid json {")

    # Should fall back to defaults
    service = ConfigService(config_path)
    assert service.get_global_bypass_permissions() is True


def test_config_directory_created(tmp_path):
    """Config directory is created if it doesn't exist"""
    config_path = tmp_path / "nested" / "path" / "config.json"

    # Directory doesn't exist yet
    assert not config_path.parent.exists()

    # Creating service creates directory
    service = ConfigService(config_path)

    assert config_path.parent.exists()
    assert config_path.exists()


def test_multiple_updates(tmp_path):
    """Can update setting multiple times"""
    service = ConfigService(tmp_path / "config.json")

    # Toggle multiple times
    for i in range(5):
        expected = i % 2 == 0
        service.set_global_bypass_permissions(expected)
        assert service.get_global_bypass_permissions() == expected
