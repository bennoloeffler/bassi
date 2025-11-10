"""Tests for logging_config.py - Logging configuration."""

import logging
from unittest.mock import MagicMock, patch

from bassi.shared.logging_config import DEFAULT_FORMAT, configure_logging


class TestConfigureLogging:
    """Test configure_logging function."""

    @patch("bassi.shared.logging_config.logging.basicConfig")
    @patch("bassi.shared.logging_config.logging.FileHandler")
    @patch("bassi.shared.logging_config.logging.getLogger")
    def test_configure_logging_default(
        self, mock_getLogger, mock_file_handler, mock_basicConfig, tmp_path
    ):
        """Test default configuration with file logging."""
        # Mock root logger with no handlers to avoid early return
        mock_root = MagicMock()
        mock_root.handlers = []
        mock_getLogger.return_value = mock_root

        log_file = tmp_path / "test.log"
        mock_handler = MagicMock()
        mock_file_handler.return_value = mock_handler

        configure_logging(log_file=str(log_file))

        # File handler should be created
        mock_file_handler.assert_called_once()
        # Formatter should be set
        mock_handler.setFormatter.assert_called_once()
        # basicConfig should be called with the handler
        mock_basicConfig.assert_called_once()
        call_kwargs = mock_basicConfig.call_args.kwargs
        assert call_kwargs["level"] == logging.INFO
        assert mock_handler in call_kwargs["handlers"]

    @patch("bassi.shared.logging_config.logging.basicConfig")
    @patch("bassi.shared.logging_config.logging.StreamHandler")
    @patch("bassi.shared.logging_config.logging.FileHandler")
    @patch("bassi.shared.logging_config.logging.getLogger")
    def test_configure_logging_with_console(
        self,
        mock_getLogger,
        mock_file_handler,
        mock_stream_handler,
        mock_basicConfig,
        tmp_path,
    ):
        """Test configuration with both file and console logging."""
        # Mock root logger with no handlers
        mock_root = MagicMock()
        mock_root.handlers = []
        mock_getLogger.return_value = mock_root

        log_file = tmp_path / "test.log"
        mock_file = MagicMock()
        mock_stream = MagicMock()
        mock_file_handler.return_value = mock_file
        mock_stream_handler.return_value = mock_stream

        configure_logging(log_file=str(log_file), include_console=True)

        # Both handlers should be created
        mock_file_handler.assert_called_once()
        mock_stream_handler.assert_called_once()

        # basicConfig should be called with both handlers
        call_kwargs = mock_basicConfig.call_args.kwargs
        assert mock_file in call_kwargs["handlers"]
        assert mock_stream in call_kwargs["handlers"]

    @patch("bassi.shared.logging_config.logging.basicConfig")
    @patch("bassi.shared.logging_config.logging.StreamHandler")
    @patch("bassi.shared.logging_config.logging.getLogger")
    def test_configure_logging_console_only(
        self, mock_getLogger, mock_stream_handler, mock_basicConfig
    ):
        """Test configuration with console logging only."""
        # Mock root logger with no handlers
        mock_root = MagicMock()
        mock_root.handlers = []
        mock_getLogger.return_value = mock_root

        mock_stream = MagicMock()
        mock_stream_handler.return_value = mock_stream

        configure_logging(log_file=None, include_console=True)

        # Only stream handler should be created
        mock_stream_handler.assert_called_once()

        # basicConfig should be called with stream handler
        call_kwargs = mock_basicConfig.call_args.kwargs
        assert mock_stream in call_kwargs["handlers"]

    @patch("bassi.shared.logging_config.logging.basicConfig")
    @patch("bassi.shared.logging_config.logging.getLogger")
    def test_configure_logging_no_file_no_console(
        self, mock_getLogger, mock_basicConfig
    ):
        """Test configuration with neither file nor console."""
        # Mock root logger with no handlers
        mock_root = MagicMock()
        mock_root.handlers = []
        mock_getLogger.return_value = mock_root

        configure_logging(log_file=None, include_console=False)

        # basicConfig should be called with None handlers
        call_kwargs = mock_basicConfig.call_args.kwargs
        assert call_kwargs["handlers"] is None

    @patch("bassi.shared.logging_config.logging.basicConfig")
    @patch("bassi.shared.logging_config.logging.FileHandler")
    @patch("bassi.shared.logging_config.logging.getLogger")
    def test_configure_logging_custom_level(
        self, mock_getLogger, mock_file_handler, mock_basicConfig, tmp_path
    ):
        """Test configuration with custom logging level."""
        # Mock root logger with no handlers
        mock_root = MagicMock()
        mock_root.handlers = []
        mock_getLogger.return_value = mock_root

        log_file = tmp_path / "test.log"

        configure_logging(log_file=str(log_file), level=logging.DEBUG)

        call_kwargs = mock_basicConfig.call_args.kwargs
        assert call_kwargs["level"] == logging.DEBUG

    def test_configure_logging_creates_directory(self, tmp_path):
        """Test that log file directory is created if it doesn't exist."""
        log_file = tmp_path / "subdir" / "nested" / "test.log"
        assert not log_file.parent.exists()

        # Mock root logger with no handlers
        mock_root = MagicMock()
        mock_root.handlers = []

        with (
            patch("bassi.shared.logging_config.logging.basicConfig"),
            patch(
                "bassi.shared.logging_config.logging.getLogger",
                return_value=mock_root,
            ),
        ):
            configure_logging(log_file=str(log_file))

        # Directory should be created
        assert log_file.parent.exists()

    def test_configure_logging_early_return_when_handlers_exist(
        self, tmp_path
    ):
        """Test early return when handlers exist and force=False."""
        log_file = tmp_path / "test.log"

        with patch(
            "bassi.shared.logging_config.logging.basicConfig"
        ) as mock_basicConfig:
            # Mock root logger to have existing handlers
            mock_root = MagicMock()
            mock_root.handlers = [MagicMock()]  # One existing handler

            with patch(
                "bassi.shared.logging_config.logging.getLogger",
                return_value=mock_root,
            ):
                configure_logging(
                    log_file=str(log_file), level=logging.WARNING
                )

                # Should only set level and return
                assert mock_root.setLevel.called
                mock_root.setLevel.assert_called_with(logging.WARNING)

                # Should NOT call basicConfig because force=False
                mock_basicConfig.assert_not_called()

    @patch("bassi.shared.logging_config.logging.basicConfig")
    @patch("bassi.shared.logging_config.logging.FileHandler")
    def test_configure_logging_force_reconfigure(
        self, mock_file_handler, mock_basicConfig, tmp_path
    ):
        """Test force reconfiguration even when handlers exist."""
        log_file = tmp_path / "test.log"

        # Mock root logger to have existing handlers
        mock_root = MagicMock()
        mock_root.handlers = [MagicMock()]

        with patch(
            "bassi.shared.logging_config.logging.getLogger",
            return_value=mock_root,
        ):
            configure_logging(
                log_file=str(log_file), level=logging.INFO, force=True
            )

            # Should call basicConfig with force=True
            call_kwargs = mock_basicConfig.call_args.kwargs
            assert call_kwargs["force"] is True

    @patch("bassi.shared.logging_config.logging.basicConfig")
    @patch("bassi.shared.logging_config.logging.FileHandler")
    @patch("bassi.shared.logging_config.logging.getLogger")
    def test_configure_logging_formatter_applied(
        self, mock_getLogger, mock_file_handler, mock_basicConfig, tmp_path
    ):
        """Test that formatter is applied to file handler."""
        # Mock root logger with no handlers
        mock_root = MagicMock()
        mock_root.handlers = []
        mock_getLogger.return_value = mock_root

        log_file = tmp_path / "test.log"
        mock_handler = MagicMock()
        mock_file_handler.return_value = mock_handler

        configure_logging(log_file=str(log_file))

        # Formatter should be created and set
        mock_handler.setFormatter.assert_called_once()
        formatter_arg = mock_handler.setFormatter.call_args[0][0]
        assert isinstance(formatter_arg, logging.Formatter)
        assert formatter_arg._fmt == DEFAULT_FORMAT

    @patch("bassi.shared.logging_config.logging.basicConfig")
    @patch("bassi.shared.logging_config.logging.StreamHandler")
    @patch("bassi.shared.logging_config.logging.getLogger")
    def test_configure_logging_stream_formatter_applied(
        self, mock_getLogger, mock_stream_handler, mock_basicConfig
    ):
        """Test that formatter is applied to stream handler."""
        # Mock root logger with no handlers
        mock_root = MagicMock()
        mock_root.handlers = []
        mock_getLogger.return_value = mock_root

        mock_handler = MagicMock()
        mock_stream_handler.return_value = mock_handler

        configure_logging(log_file=None, include_console=True)

        # Formatter should be created and set
        mock_handler.setFormatter.assert_called_once()
        formatter_arg = mock_handler.setFormatter.call_args[0][0]
        assert isinstance(formatter_arg, logging.Formatter)
        assert formatter_arg._fmt == DEFAULT_FORMAT

    @patch("bassi.shared.logging_config.logging.basicConfig")
    @patch("bassi.shared.logging_config.logging.FileHandler")
    @patch("bassi.shared.logging_config.logging.getLogger")
    def test_configure_logging_level_debug(
        self, mock_getLogger, mock_file_handler, mock_basicConfig, tmp_path
    ):
        """Test DEBUG level logging."""
        # Mock root logger with no handlers
        mock_root = MagicMock()
        mock_root.handlers = []
        mock_getLogger.return_value = mock_root

        log_file = tmp_path / "test.log"

        configure_logging(log_file=str(log_file), level=logging.DEBUG)

        call_kwargs = mock_basicConfig.call_args.kwargs
        assert call_kwargs["level"] == logging.DEBUG

    @patch("bassi.shared.logging_config.logging.basicConfig")
    @patch("bassi.shared.logging_config.logging.FileHandler")
    @patch("bassi.shared.logging_config.logging.getLogger")
    def test_configure_logging_level_warning(
        self, mock_getLogger, mock_file_handler, mock_basicConfig, tmp_path
    ):
        """Test WARNING level logging."""
        # Mock root logger with no handlers
        mock_root = MagicMock()
        mock_root.handlers = []
        mock_getLogger.return_value = mock_root

        log_file = tmp_path / "test.log"

        configure_logging(log_file=str(log_file), level=logging.WARNING)

        call_kwargs = mock_basicConfig.call_args.kwargs
        assert call_kwargs["level"] == logging.WARNING

    @patch("bassi.shared.logging_config.logging.basicConfig")
    @patch("bassi.shared.logging_config.logging.FileHandler")
    @patch("bassi.shared.logging_config.logging.getLogger")
    def test_configure_logging_level_error(
        self, mock_getLogger, mock_file_handler, mock_basicConfig, tmp_path
    ):
        """Test ERROR level logging."""
        # Mock root logger with no handlers
        mock_root = MagicMock()
        mock_root.handlers = []
        mock_getLogger.return_value = mock_root

        log_file = tmp_path / "test.log"

        configure_logging(log_file=str(log_file), level=logging.ERROR)

        call_kwargs = mock_basicConfig.call_args.kwargs
        assert call_kwargs["level"] == logging.ERROR

    @patch("bassi.shared.logging_config.logging.basicConfig")
    @patch("bassi.shared.logging_config.logging.FileHandler")
    @patch("bassi.shared.logging_config.logging.getLogger")
    def test_configure_logging_default_format_in_basicConfig(
        self, mock_getLogger, mock_file_handler, mock_basicConfig, tmp_path
    ):
        """Test that DEFAULT_FORMAT is passed to basicConfig."""
        # Mock root logger with no handlers
        mock_root = MagicMock()
        mock_root.handlers = []
        mock_getLogger.return_value = mock_root

        log_file = tmp_path / "test.log"

        configure_logging(log_file=str(log_file))

        call_kwargs = mock_basicConfig.call_args.kwargs
        assert call_kwargs["format"] == DEFAULT_FORMAT
