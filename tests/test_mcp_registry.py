"""Tests for mcp_registry.py - MCP server registry management."""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from bassi.shared.mcp_registry import (
    create_mcp_registry,
    create_sdk_mcp_servers,
    load_external_mcp_servers,
)


class TestLoadExternalMCPServers:
    """Test load_external_mcp_servers function."""

    def test_load_no_file(self, tmp_path):
        """Test when .mcp.json file doesn't exist."""
        config_path = tmp_path / ".mcp.json"
        result = load_external_mcp_servers(config_path)
        assert result == {}

    def test_load_empty_config(self, tmp_path):
        """Test with empty mcpServers section."""
        config_path = tmp_path / ".mcp.json"
        config_path.write_text(json.dumps({"mcpServers": {}}))

        result = load_external_mcp_servers(config_path)
        assert result == {}

    def test_load_valid_config(self, tmp_path):
        """Test loading valid MCP server config."""
        config_path = tmp_path / ".mcp.json"
        config = {
            "mcpServers": {
                "test-server": {
                    "command": "npx",
                    "args": ["-y", "test-package"],
                    "env": {"API_KEY": "test-key"},
                }
            }
        }
        config_path.write_text(json.dumps(config))

        result = load_external_mcp_servers(config_path)

        assert "test-server" in result
        assert result["test-server"]["command"] == "npx"
        assert result["test-server"]["args"] == ["-y", "test-package"]
        assert result["test-server"]["env"]["API_KEY"] == "test-key"

    def test_load_multiple_servers(self, tmp_path):
        """Test loading multiple MCP servers."""
        config_path = tmp_path / ".mcp.json"
        config = {
            "mcpServers": {
                "server1": {"command": "cmd1", "args": ["arg1"], "env": {}},
                "server2": {"command": "cmd2", "args": ["arg2"], "env": {}},
            }
        }
        config_path.write_text(json.dumps(config))

        result = load_external_mcp_servers(config_path)

        assert len(result) == 2
        assert "server1" in result
        assert "server2" in result

    def test_env_var_substitution_simple(self, tmp_path):
        """Test environment variable substitution ${VAR_NAME}."""
        config_path = tmp_path / ".mcp.json"
        config = {
            "mcpServers": {
                "postgres": {
                    "command": "uvx",
                    "args": ["mcp-server-postgres"],
                    "env": {"DATABASE_URL": "${DB_CONNECTION}"},
                }
            }
        }
        config_path.write_text(json.dumps(config))

        # Set environment variable
        with patch.dict(
            os.environ, {"DB_CONNECTION": "postgresql://localhost/test"}
        ):
            result = load_external_mcp_servers(config_path)

        assert (
            result["postgres"]["env"]["DATABASE_URL"]
            == "postgresql://localhost/test"
        )

    def test_env_var_substitution_with_default(self, tmp_path):
        """Test environment variable substitution ${VAR_NAME:-default}."""
        config_path = tmp_path / ".mcp.json"
        config = {
            "mcpServers": {
                "postgres": {
                    "command": "uvx",
                    "args": [],
                    "env": {
                        "DATABASE_URL": "${MISSING_VAR:-postgresql://localhost/default}"
                    },
                }
            }
        }
        config_path.write_text(json.dumps(config))

        # Don't set MISSING_VAR, should use default
        result = load_external_mcp_servers(config_path)

        assert (
            result["postgres"]["env"]["DATABASE_URL"]
            == "postgresql://localhost/default"
        )

    def test_env_var_missing_no_default(self, tmp_path):
        """Test missing environment variable with no default (should be empty string)."""
        config_path = tmp_path / ".mcp.json"
        config = {
            "mcpServers": {
                "test": {
                    "command": "test",
                    "args": [],
                    "env": {"MISSING": "${MISSING_VAR}"},
                }
            }
        }
        config_path.write_text(json.dumps(config))

        result = load_external_mcp_servers(config_path)

        assert result["test"]["env"]["MISSING"] == ""

    def test_env_var_non_string_value(self, tmp_path):
        """Test that non-string env values are preserved as-is."""
        config_path = tmp_path / ".mcp.json"
        config = {
            "mcpServers": {
                "test": {
                    "command": "test",
                    "args": [],
                    "env": {
                        "NUMBER": 42,
                        "BOOLEAN": True,
                        "STRING": "plain-string",
                    },
                }
            }
        }
        config_path.write_text(json.dumps(config))

        result = load_external_mcp_servers(config_path)

        assert result["test"]["env"]["NUMBER"] == 42
        assert result["test"]["env"]["BOOLEAN"] is True
        assert result["test"]["env"]["STRING"] == "plain-string"

    def test_invalid_json(self, tmp_path):
        """Test handling of invalid JSON."""
        config_path = tmp_path / ".mcp.json"
        config_path.write_text("{ invalid json }")

        result = load_external_mcp_servers(config_path)

        # Should return empty dict on error
        assert result == {}

    def test_default_path(self, tmp_path, monkeypatch):
        """Test using default .mcp.json path in current directory."""
        # Change to temp directory
        monkeypatch.chdir(tmp_path)

        # Create .mcp.json in current directory
        config_path = tmp_path / ".mcp.json"
        config = {
            "mcpServers": {"test": {"command": "test", "args": [], "env": {}}}
        }
        config_path.write_text(json.dumps(config))

        # Call without config_path (should use current directory)
        result = load_external_mcp_servers()

        assert "test" in result

    def test_missing_args_field(self, tmp_path):
        """Test server config without args field."""
        config_path = tmp_path / ".mcp.json"
        config = {
            "mcpServers": {
                "test": {
                    "command": "test",
                    # No args field
                    "env": {},
                }
            }
        }
        config_path.write_text(json.dumps(config))

        result = load_external_mcp_servers(config_path)

        assert result["test"]["args"] == []

    def test_missing_env_field(self, tmp_path):
        """Test server config without env field."""
        config_path = tmp_path / ".mcp.json"
        config = {
            "mcpServers": {
                "test": {
                    "command": "test",
                    "args": [],
                    # No env field
                }
            }
        }
        config_path.write_text(json.dumps(config))

        result = load_external_mcp_servers(config_path)

        assert result["test"]["env"] == {}


class TestCreateSDKMCPServers:
    """Test create_sdk_mcp_servers function."""

    @patch("bassi.mcp_servers.create_bash_mcp_server")
    @patch("bassi.mcp_servers.create_web_search_mcp_server")
    @patch("bassi.mcp_servers.create_task_automation_server")
    def test_create_sdk_servers(self, mock_task, mock_web, mock_bash):
        """Test creating SDK MCP servers."""
        mock_bash.return_value = MagicMock(name="bash_server")
        mock_web.return_value = MagicMock(name="web_server")
        mock_task.return_value = MagicMock(name="task_server")

        result = create_sdk_mcp_servers()

        assert "bash" in result
        assert "web" in result
        assert "task_automation" in result

        mock_bash.assert_called_once()
        mock_web.assert_called_once()
        mock_task.assert_called_once()


class TestCreateMCPRegistry:
    """Test create_mcp_registry function."""

    @patch("bassi.shared.mcp_registry.create_sdk_mcp_servers")
    @patch("bassi.shared.mcp_registry.load_external_mcp_servers")
    def test_registry_with_sdk_only(
        self, mock_load_external, mock_create_sdk
    ):
        """Test creating registry with SDK servers only."""
        mock_create_sdk.return_value = {
            "bash": MagicMock(name="bash"),
            "web": MagicMock(name="web"),
            "task_automation": MagicMock(name="task"),
        }
        mock_load_external.return_value = {}

        result = create_mcp_registry(include_sdk=True)

        assert len(result) == 3
        assert "bash" in result
        assert "web" in result
        assert "task_automation" in result

        mock_create_sdk.assert_called_once()

    @patch("bassi.shared.mcp_registry.create_sdk_mcp_servers")
    @patch("bassi.shared.mcp_registry.load_external_mcp_servers")
    def test_registry_without_sdk(self, mock_load_external, mock_create_sdk):
        """Test creating registry without SDK servers."""
        mock_load_external.return_value = {"external1": {"command": "test1"}}

        result = create_mcp_registry(include_sdk=False)

        assert len(result) == 1
        assert "external1" in result
        mock_create_sdk.assert_not_called()

    @patch("bassi.shared.mcp_registry.create_sdk_mcp_servers")
    @patch("bassi.shared.mcp_registry.load_external_mcp_servers")
    def test_registry_with_external(
        self, mock_load_external, mock_create_sdk
    ):
        """Test creating registry with SDK and external servers."""
        mock_create_sdk.return_value = {
            "bash": MagicMock(name="bash"),
        }
        mock_load_external.return_value = {"postgres": {"command": "uvx"}}

        result = create_mcp_registry(include_sdk=True)

        assert len(result) == 2
        assert "bash" in result
        assert "postgres" in result

    @patch("bassi.shared.mcp_registry.create_sdk_mcp_servers")
    @patch("bassi.shared.mcp_registry.load_external_mcp_servers")
    def test_registry_with_custom(self, mock_load_external, mock_create_sdk):
        """Test creating registry with custom servers."""
        mock_create_sdk.return_value = {
            "bash": MagicMock(name="bash"),
        }
        mock_load_external.return_value = {}

        custom_server = MagicMock(name="custom")
        result = create_mcp_registry(
            include_sdk=True, custom_servers={"custom": custom_server}
        )

        assert len(result) == 2
        assert "bash" in result
        assert "custom" in result
        assert result["custom"] == custom_server

    @patch("bassi.shared.mcp_registry.create_sdk_mcp_servers")
    @patch("bassi.shared.mcp_registry.load_external_mcp_servers")
    def test_registry_priority_custom_overrides(
        self, mock_load_external, mock_create_sdk
    ):
        """Test that custom servers override SDK and external servers."""
        mock_create_sdk.return_value = {
            "bash": MagicMock(name="sdk_bash"),
        }
        mock_load_external.return_value = {
            "bash": {"command": "external_bash"}
        }

        custom_bash = MagicMock(name="custom_bash")
        result = create_mcp_registry(
            include_sdk=True, custom_servers={"bash": custom_bash}
        )

        # Custom should override both SDK and external
        assert result["bash"] == custom_bash

    @patch("bassi.shared.mcp_registry.create_sdk_mcp_servers")
    @patch("bassi.shared.mcp_registry.load_external_mcp_servers")
    def test_registry_config_path(self, mock_load_external, mock_create_sdk):
        """Test passing custom config_path to registry."""
        mock_create_sdk.return_value = {}
        mock_load_external.return_value = {}

        custom_path = Path("/custom/path/.mcp.json")
        create_mcp_registry(include_sdk=False, config_path=custom_path)

        # Verify custom path was passed to load_external_mcp_servers
        mock_load_external.assert_called_once_with(custom_path)

    @patch("bassi.shared.mcp_registry.create_sdk_mcp_servers")
    @patch("bassi.shared.mcp_registry.load_external_mcp_servers")
    def test_registry_all_options(self, mock_load_external, mock_create_sdk):
        """Test registry with all options: SDK + external + custom."""
        mock_create_sdk.return_value = {
            "bash": MagicMock(name="bash"),
        }
        mock_load_external.return_value = {"postgres": {"command": "uvx"}}
        custom_server = MagicMock(name="custom")

        result = create_mcp_registry(
            include_sdk=True, custom_servers={"custom": custom_server}
        )

        assert len(result) == 3
        assert "bash" in result
        assert "postgres" in result
        assert "custom" in result
