"""
Shared logging configuration helpers.

Provides a single entry point to configure logging so that different
processes (CLI, web server, tests) do not fight over logging.basicConfig.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

DEFAULT_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def configure_logging(
    *,
    level: int = logging.INFO,
    log_file: Optional[str] = "bassi_debug.log",
    include_console: bool = False,
    force: bool = False,
) -> None:
    """
    Configure root logging once.

    Args:
        level: Default logging level to apply.
        log_file: Optional filename to log to. Pass None to skip file logging.
        include_console: Whether to emit logs to stderr/stdout as well.
        force: When True, reconfigure even if handlers already exist.
    """
    root_logger = logging.getLogger()

    if root_logger.handlers and not force:
        root_logger.setLevel(level)
        return

    handlers: list[logging.Handler] = []
    formatter = logging.Formatter(DEFAULT_FORMAT)

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path)
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    if include_console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        handlers.append(console_handler)

    logging.basicConfig(
        level=level,
        handlers=handlers or None,
        format=DEFAULT_FORMAT,
        force=force,
    )
