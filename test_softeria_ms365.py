#!/usr/bin/env python3
"""
Test script for Softeria MS365 MCP Server
Tests authentication and basic email reading functionality
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Setup detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("test_softeria_ms365.log"),
    ],
)
logger = logging.getLogger(__name__)


def load_env_file():
    """Load .env file manually"""
    logger.info("=" * 80)
    logger.info("STEP 1: Loading .env file")
    logger.info("=" * 80)

    env_file = Path(".env")
    if not env_file.exists():
        logger.error(f"❌ .env file not found at: {env_file.absolute()}")
        return False

    logger.info(f"✅ Found .env file at: {env_file.absolute()}")

    # Read and parse .env file
    with open(env_file) as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                os.environ[key] = value

                # Log without showing full value (security)
                if "ID" in key or "SECRET" in key:
                    logger.info(
                        f"  Line {line_num}: Set {key} = {value[:8]}...{value[-4:]}"
                    )
                else:
                    logger.info(f"  Line {line_num}: Set {key}")

    return True


def check_configuration():
    """Check if required configuration is present"""
    logger.info("")
    logger.info("=" * 80)
    logger.info("STEP 2: Checking Configuration")
    logger.info("=" * 80)

    client_id = os.environ.get("MS365_CLIENT_ID")
    tenant_id = os.environ.get("MS365_TENANT_ID", "common")
    client_secret = os.environ.get("MS365_CLIENT_SECRET")

    missing = []
    if not client_id:
        missing.append("MS365_CLIENT_ID")
    if not client_secret:
        missing.append("MS365_CLIENT_SECRET")

    if missing:
        logger.error(f"❌ Missing configuration: {', '.join(missing)}")
        return None, None, None

    logger.info(f"✅ MS365_CLIENT_ID: {client_id[:8]}...{client_id[-4:]}")
    logger.info(f"✅ MS365_TENANT_ID: {tenant_id}")
    logger.info(
        f"✅ MS365_CLIENT_SECRET: {client_secret[:8]}...{client_secret[-4:]}"
    )

    return client_id, tenant_id, client_secret


async def test_softeria_server_authentication(
    client_id: str, tenant_id: str, client_secret: str
):
    """Test Softeria MCP server authentication using client secret"""
    logger.info("")
    logger.info("=" * 80)
    logger.info("STEP 3: Testing Softeria MCP Server Authentication")
    logger.info("=" * 80)

    try:
        # Test using subprocess to call npx
        import subprocess

        logger.info("Testing authentication with client secret flow...")

        env_vars = os.environ.copy()
        env_vars.update(
            {
                "MS365_MCP_CLIENT_ID": client_id,
                "MS365_MCP_TENANT_ID": tenant_id,
                "MS365_MCP_CLIENT_SECRET": client_secret,
            }
        )

        # Try to verify login
        logger.info(
            "Running: npx -y @softeria/ms-365-mcp-server --verify-login"
        )

        result = subprocess.run(
            ["npx", "-y", "@softeria/ms-365-mcp-server", "--verify-login"],
            env=env_vars,
            capture_output=True,
            text=True,
            timeout=60,
        )

        logger.info(f"Exit code: {result.returncode}")
        logger.info("STDOUT:")
        logger.info(result.stdout)

        if result.stderr:
            logger.info("STDERR:")
            logger.info(result.stderr)

        if result.returncode == 0:
            logger.info("✅ Authentication successful!")
            return True
        else:
            logger.warning("⚠️  Authentication may need device code flow")
            return False

    except subprocess.TimeoutExpired:
        logger.error("❌ Command timed out")
        return False
    except Exception as e:
        logger.error(f"❌ Authentication test failed: {e}")
        logger.exception("Full traceback:")
        return False


async def test_mcp_server_tools(
    client_id: str, tenant_id: str, client_secret: str
):
    """Test MCP server tools via MCP protocol"""
    logger.info("")
    logger.info("=" * 80)
    logger.info("STEP 4: Testing MCP Server Tools")
    logger.info("=" * 80)

    try:
        # Import MCP client libraries
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        logger.info("Creating MCP client session...")

        # Prepare environment variables
        env_vars = {
            "MS365_MCP_CLIENT_ID": client_id,
            "MS365_MCP_TENANT_ID": tenant_id,
            "MS365_MCP_CLIENT_SECRET": client_secret,
        }

        # Create server parameters
        server_params = StdioServerParameters(
            command="npx",
            args=["-y", "@softeria/ms-365-mcp-server"],
            env=env_vars,
        )

        logger.info("Connecting to MCP server...")

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                logger.info("✅ Connected to MCP server")

                # Initialize the connection
                await session.initialize()
                logger.info("✅ Session initialized")

                # List available tools
                logger.info("Listing available tools...")
                tools = await session.list_tools()

                logger.info(f"✅ Found {len(tools.tools)} tools:")
                for tool in tools.tools[:10]:  # Show first 10 tools
                    logger.info(f"  - {tool.name}: {tool.description}")

                if len(tools.tools) > 10:
                    logger.info(
                        f"  ... and {len(tools.tools) - 10} more tools"
                    )

                # Try to call a simple tool (e.g., list messages)
                logger.info("")
                logger.info("Testing 'list_messages' tool...")

                try:
                    result = await session.call_tool(
                        "list_messages", arguments={"max_results": 5}
                    )

                    logger.info("✅ Successfully called list_messages tool!")
                    logger.info("Result:")
                    logger.info(json.dumps(result, indent=2))

                except Exception as tool_error:
                    logger.warning(f"⚠️  Tool call failed: {tool_error}")
                    logger.info(
                        "This may be expected if authentication hasn't completed"
                    )

                return True

    except ImportError as e:
        logger.error(f"❌ Import error: {e}")
        logger.error("   Make sure mcp is installed: uv add mcp")
        return False
    except Exception as e:
        logger.error(f"❌ MCP server test failed: {e}")
        logger.exception("Full traceback:")
        return False


async def main():
    """Main test flow"""
    logger.info("")
    logger.info("╔" + "=" * 78 + "╗")
    logger.info("║" + " " * 78 + "║")
    logger.info("║" + "  TEST: Softeria MS365 MCP Server".center(78) + "║")
    logger.info("║" + " " * 78 + "║")
    logger.info("╚" + "=" * 78 + "╝")
    logger.info("")

    # Step 1: Load .env
    if not load_env_file():
        logger.error("❌ Failed to load .env file")
        return 1

    # Step 2: Check configuration
    client_id, tenant_id, client_secret = check_configuration()
    if not client_id:
        logger.error("❌ Configuration incomplete")
        return 1

    # Step 3: Test authentication
    await test_softeria_server_authentication(
        client_id, tenant_id, client_secret
    )

    # Step 4: Test MCP server tools
    logger.info("")
    logger.info(
        "Note: For full MCP protocol testing, we need the MCP library"
    )
    logger.info("Installing MCP library...")

    import subprocess

    try:
        subprocess.run(["uv", "add", "mcp"], check=True, capture_output=True)
        logger.info("✅ MCP library installed")

        # Now test MCP server tools
        await test_mcp_server_tools(client_id, tenant_id, client_secret)

    except subprocess.CalledProcessError:
        logger.warning("⚠️  Could not install MCP library")
        logger.info("For full testing, manually run: uv add mcp")

    logger.info("")
    logger.info("╔" + "=" * 78 + "╗")
    logger.info("║" + " " * 78 + "║")
    logger.info("║" + "  TEST COMPLETE".center(78) + "║")
    logger.info("║" + " " * 78 + "║")
    logger.info("╚" + "=" * 78 + "╝")
    logger.info("")
    logger.info("📄 Full log saved to: test_softeria_ms365.log")

    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("")
        logger.warning("⚠️  Interrupted by user (Ctrl+C)")
        sys.exit(130)
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        logger.exception("Full traceback:")
        sys.exit(1)
