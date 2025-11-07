#!/usr/bin/env python
"""
CLI entry point for bassi-web (V3 Web UI)

This provides a dedicated command for the V3 web-only interface.
For CLI usage, use the main 'bassi' command instead.
"""

import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

import logging
from bassi.core_v3 import display_startup_discovery, start_web_server_v3
from bassi.logging_utils import configure_logging

# Load environment variables from .env file
env_path = Path.cwd() / ".env"
load_dotenv(dotenv_path=env_path)

# Setup logging with DEBUG level for intensive debugging (console)
configure_logging(level=logging.DEBUG, include_console=True)

logger = logging.getLogger(__name__)


def main():
    """Main entry point for bassi-web command"""
    logger.info("🚀 Starting Bassi Web UI V3 (Agent SDK)")
    logger.info("📁 Open http://localhost:8765 in your browser")
    logger.info("")

    # Display discovery information
    project_root = Path.cwd()
    display_startup_discovery(project_root)

    # Start server with default config
    # - Uses claude-agent-sdk
    # - Auto-accepts file edits
    # - All tools enabled (including MCP)
    try:
        asyncio.run(
            start_web_server_v3(
                host="localhost",
                port=8765,
                reload=True,  # Hot reload enabled for development
            )
        )
    except KeyboardInterrupt:
        logger.info("\n👋 Shutting down...")
        sys.exit(0)


if __name__ == "__main__":
    main()
