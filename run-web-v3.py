#!/usr/bin/env -S uv run python
"""
Start Bassi Web UI V3 - Built on Claude Agent SDK

This script starts the web server using the V3 architecture.
"""

import asyncio
import logging
from pathlib import Path

from dotenv import load_dotenv

from bassi.core_v3 import start_web_server_v3

# Load environment variables from .env file
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


async def main():
    """Start the web server V3"""
    logger.info("🚀 Starting Bassi Web UI V3 (Agent SDK)")
    logger.info("📁 Open http://localhost:8765 in your browser")
    logger.info("")

    # Display discovery information
    from bassi.core_v3 import display_startup_discovery
    from pathlib import Path

    project_root = Path(__file__).parent
    display_startup_discovery(project_root)

    # Start server with default config
    # - Uses claude-agent-sdk
    # - Auto-accepts file edits
    # - All tools enabled (including MCP)
    await start_web_server_v3(
        host="localhost",
        port=8765,
        reload=True,  # Set to True for hot reload during development
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n👋 Shutting down...")
