#!/usr/bin/env python3
"""
Test Softeria MS365 MCP Server - Login Flow
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def load_env():
    """Load .env file"""
    env_file = Path(".env")
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()


async def main():
    """Test Softeria MCP server login and email reading"""
    load_env()

    client_id = os.environ.get("MS365_CLIENT_ID")
    tenant_id = os.environ.get("MS365_TENANT_ID")
    client_secret = os.environ.get("MS365_CLIENT_SECRET")

    logger.info("=" * 80)
    logger.info("Testing Softeria MS365 MCP Server")
    logger.info("=" * 80)

    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        # Create server parameters
        server_params = StdioServerParameters(
            command="npx",
            args=["-y", "@softeria/ms-365-mcp-server"],
            env={
                "MS365_MCP_CLIENT_ID": client_id,
                "MS365_MCP_TENANT_ID": tenant_id,
                "MS365_MCP_CLIENT_SECRET": client_secret,
            },
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                logger.info("✅ Connected to MCP server")

                # List all available tools
                tools = await session.list_tools()
                logger.info(f"✅ Found {len(tools.tools)} tools")

                # Print all tool names
                logger.info("\nAvailable tools:")
                for tool in tools.tools:
                    logger.info(f"  - {tool.name}: {tool.description[:80]}")

                # Try to login
                logger.info("\n" + "=" * 80)
                logger.info("Attempting login...")
                logger.info("=" * 80)

                try:
                    result = await session.call_tool("login", arguments={})
                    logger.info("Login result:")
                    logger.info(json.dumps(result.model_dump(), indent=2))

                except Exception as e:
                    logger.error(f"Login failed: {e}")

                # Check login status
                logger.info("\n" + "=" * 80)
                logger.info("Checking login status...")
                logger.info("=" * 80)

                try:
                    result = await session.call_tool(
                        "verify-login", arguments={}
                    )
                    logger.info("Verify login result:")
                    logger.info(json.dumps(result.model_dump(), indent=2))

                except Exception as e:
                    logger.error(f"Verify login failed: {e}")

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        logger.exception("Full traceback:")
        return 1

    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.warning("⚠️  Interrupted")
        sys.exit(130)
