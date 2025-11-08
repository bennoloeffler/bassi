"""
MCP Server Registry - Shared Module

Provides centralized MCP server management for both V1 (CLI) and V3 (Web).

Functions:
- load_external_mcp_servers() - Load .mcp.json with environment variable substitution
- create_sdk_mcp_servers() - Create built-in SDK MCP servers (bash, web, task_automation)
- create_mcp_registry() - Combine SDK + external + custom servers into unified registry
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def load_external_mcp_servers(config_path: Optional[Path] = None) -> dict:
    """
    Load external MCP server configuration from .mcp.json

    This function loads MCP servers defined in .mcp.json and performs environment
    variable substitution for configuration values.

    Args:
        config_path: Path to .mcp.json file. If None, uses .mcp.json in current directory.

    Returns:
        Dict mapping server name to MCP server config in Claude SDK format.
        Returns empty dict if file not found or on error.

    Environment Variable Substitution:
        - ${VAR_NAME} - Replaced with env var value or empty string
        - ${VAR_NAME:-default} - Replaced with env var value or default

    Example .mcp.json:
        {
          "mcpServers": {
            "postgresql": {
              "command": "uvx",
              "args": ["mcp-server-postgres", "${DB_CONNECTION_STRING}"],
              "env": {
                "DATABASE_URL": "${DATABASE_URL:-postgresql://localhost/mydb}"
              }
            }
          }
        }
    """
    # Default to .mcp.json in current working directory
    if config_path is None:
        config_path = Path.cwd() / ".mcp.json"

    if not config_path.exists():
        logger.info(
            f"No .mcp.json file found at {config_path} - skipping external MCP servers"
        )
        return {}

    try:
        with open(config_path) as f:
            config = json.load(f)

        mcp_servers_config = config.get("mcpServers", {})

        if not mcp_servers_config:
            logger.info(f"No MCP servers configured in {config_path}")
            return {}

        # Load environment variables for substitution
        from dotenv import load_dotenv

        load_dotenv()

        # Convert .mcp.json format to Claude SDK format
        external_servers = {}

        for server_name, server_config in mcp_servers_config.items():
            command = server_config.get("command")
            args = server_config.get("args", [])
            env = server_config.get("env", {})

            # Substitute environment variables in env values
            resolved_env = {}
            for key, value in env.items():
                if (
                    isinstance(value, str)
                    and value.startswith("${")
                    and value.endswith("}")
                ):
                    # Extract variable name: ${VAR_NAME} -> VAR_NAME
                    var_name = value[2:-1]
                    # Handle default values: ${VAR_NAME:-default}
                    if ":-" in var_name:
                        var_name, default = var_name.split(":-", 1)
                        resolved_env[key] = os.getenv(var_name, default)
                    else:
                        resolved_env[key] = os.getenv(var_name, "")
                else:
                    resolved_env[key] = value

            # Create MCP server config in Claude SDK format
            external_servers[server_name] = {
                "command": command,
                "args": args,
                "env": resolved_env,
            }

            logger.info(f"📦 Loaded external MCP server: {server_name}")
            logger.debug(f"   Command: {command}")
            logger.debug(f"   Args: {args}")
            logger.debug(f"   Env vars: {list(resolved_env.keys())}")

        return external_servers

    except Exception as e:
        logger.error(f"Error loading .mcp.json from {config_path}: {e}")
        logger.exception("Full traceback:")
        return {}


def create_sdk_mcp_servers() -> dict:
    """
    Create built-in SDK MCP servers (in-process, no subprocess overhead)

    These are lightweight SDK servers that run in the same process as the agent.
    They provide core functionality without external dependencies.

    Returns:
        Dict mapping server name to SDK MCP server instance:
        - "bash": Execute bash commands safely
        - "web": Web search capabilities
        - "task_automation": Task automation tools
    """
    from bassi.mcp_servers import (
        create_bash_mcp_server,
        create_task_automation_server,
        create_web_search_mcp_server,
    )

    logger.info("Creating SDK MCP servers (bash, web, task_automation)")

    return {
        "bash": create_bash_mcp_server(),
        "web": create_web_search_mcp_server(),
        "task_automation": create_task_automation_server(),
    }


def create_mcp_registry(
    *,
    include_sdk: bool = True,
    config_path: Optional[Path] = None,
    custom_servers: Optional[dict] = None,
) -> dict:
    """
    Create complete MCP server registry combining SDK, external, and custom servers

    This is the main entry point for creating a unified MCP server registry that
    can be passed directly to the Claude Agent SDK.

    Args:
        include_sdk: Whether to include built-in SDK servers (bash, web, task_automation).
                     Default: True
        config_path: Path to .mcp.json file. If None, uses .mcp.json in current directory.
        custom_servers: Optional dict of additional custom MCP servers to include.
                        These are added last and can override SDK/external servers.

    Returns:
        Dict mapping server name to MCP server config/instance, ready for SDK Agent

    Example:
        # V1 CLI usage:
        mcp_registry = create_mcp_registry(include_sdk=True)

        # V3 Web usage with custom server:
        from bassi.shared.sdk_loader import create_sdk_mcp_server
        bassi_interactive = create_sdk_mcp_server(...)
        mcp_registry = create_mcp_registry(
            include_sdk=True,
            custom_servers={"bassi-interactive": bassi_interactive}
        )

    Server Priority (later overwrites earlier):
        1. SDK servers (bash, web, task_automation) - if include_sdk=True
        2. External servers from .mcp.json
        3. Custom servers from custom_servers parameter
    """
    logger.info("Creating MCP registry...")

    registry = {}

    # 1. Add SDK MCP servers (optional)
    if include_sdk:
        sdk_servers = create_sdk_mcp_servers()
        registry.update(sdk_servers)
        logger.info(
            f"  Added {len(sdk_servers)} SDK servers: {list(sdk_servers.keys())}"
        )

    # 2. Add external MCP servers from .mcp.json
    external_servers = load_external_mcp_servers(config_path)
    if external_servers:
        registry.update(external_servers)
        logger.info(
            f"  Added {len(external_servers)} external servers: {list(external_servers.keys())}"
        )

    # 3. Add custom MCP servers (highest priority)
    if custom_servers:
        registry.update(custom_servers)
        logger.info(
            f"  Added {len(custom_servers)} custom servers: {list(custom_servers.keys())}"
        )

    logger.info(f"✅ MCP registry created with {len(registry)} total servers")

    return registry
