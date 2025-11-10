"""Tests for cli.py - bassi-web command entry point."""

import logging
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest


class TestMain:
    """Test main() function."""

    @patch("bassi.core_v3.cli.start_web_server_v3", new_callable=AsyncMock)
    @patch("bassi.core_v3.cli.display_startup_discovery")
    def test_main_success(self, mock_display, mock_start_server):
        """Test successful startup flow."""
        # Import main after patching to avoid module-level issues
        from bassi.core_v3.cli import main

        main()

        # Verify discovery displayed with current directory
        mock_display.assert_called_once()
        call_args = mock_display.call_args[0]
        assert isinstance(call_args[0], Path)

        # Verify server started with correct params
        mock_start_server.assert_called_once_with(
            host="localhost",
            port=8765,
            reload=True,
        )

    @patch("bassi.core_v3.cli.start_web_server_v3", new_callable=AsyncMock)
    @patch("bassi.core_v3.cli.display_startup_discovery")
    def test_main_keyboard_interrupt(self, mock_display, mock_start_server):
        """Test graceful shutdown on KeyboardInterrupt."""
        from bassi.core_v3.cli import main

        # Simulate KeyboardInterrupt during server start
        mock_start_server.side_effect = KeyboardInterrupt()

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0

    @patch("bassi.core_v3.cli.start_web_server_v3", new_callable=AsyncMock)
    @patch("bassi.core_v3.cli.display_startup_discovery")
    def test_main_discovery_uses_cwd(self, mock_display, mock_start_server):
        """Test that discovery is called with current working directory."""
        from bassi.core_v3.cli import main

        main()

        # Verify display_startup_discovery called with Path.cwd()
        mock_display.assert_called_once()
        project_root = mock_display.call_args[0][0]
        assert isinstance(project_root, Path)
        # Should be current working directory
        assert project_root == Path.cwd()


class TestModuleLevel:
    """Test module-level code execution."""

    def test_logger_created(self):
        """Test that module-level logger is created."""
        from bassi.core_v3 import cli

        assert hasattr(cli, "logger")
        assert isinstance(cli.logger, logging.Logger)
        assert cli.logger.name == "bassi.core_v3.cli"


class TestServerConfig:
    """Test web server configuration."""

    @patch("bassi.core_v3.cli.start_web_server_v3", new_callable=AsyncMock)
    @patch("bassi.core_v3.cli.display_startup_discovery")
    def test_server_host_localhost(self, mock_display, mock_start_server):
        """Test server binds to localhost."""
        from bassi.core_v3.cli import main

        main()

        call_kwargs = mock_start_server.call_args.kwargs
        assert call_kwargs["host"] == "localhost"

    @patch("bassi.core_v3.cli.start_web_server_v3", new_callable=AsyncMock)
    @patch("bassi.core_v3.cli.display_startup_discovery")
    def test_server_port_8765(self, mock_display, mock_start_server):
        """Test server uses port 8765."""
        from bassi.core_v3.cli import main

        main()

        call_kwargs = mock_start_server.call_args.kwargs
        assert call_kwargs["port"] == 8765

    @patch("bassi.core_v3.cli.start_web_server_v3", new_callable=AsyncMock)
    @patch("bassi.core_v3.cli.display_startup_discovery")
    def test_server_reload_enabled(self, mock_display, mock_start_server):
        """Test hot reload is enabled."""
        from bassi.core_v3.cli import main

        main()

        call_kwargs = mock_start_server.call_args.kwargs
        assert call_kwargs["reload"] is True


class TestErrorHandling:
    """Test error handling."""

    @patch("bassi.core_v3.cli.start_web_server_v3", new_callable=AsyncMock)
    @patch("bassi.core_v3.cli.display_startup_discovery")
    def test_generic_exception_not_caught(
        self, mock_display, mock_start_server
    ):
        """Test that generic exceptions propagate."""
        from bassi.core_v3.cli import main

        mock_start_server.side_effect = RuntimeError("Test error")

        with pytest.raises(RuntimeError, match="Test error"):
            main()

    @patch("bassi.core_v3.cli.start_web_server_v3", new_callable=AsyncMock)
    @patch("bassi.core_v3.cli.display_startup_discovery")
    def test_keyboard_interrupt_exit_code(
        self, mock_display, mock_start_server
    ):
        """Test KeyboardInterrupt exits with code 0."""
        from bassi.core_v3.cli import main

        mock_start_server.side_effect = KeyboardInterrupt()

        with pytest.raises(SystemExit) as exc_info:
            main()

        # Exit code should be 0 for clean shutdown
        assert exc_info.value.code == 0
