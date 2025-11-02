"""
OpenAPI to MCP Server Converter using FastMCP's built-in support

This module makes it trivial to create MCP servers from OpenAPI specifications
using FastMCP's native from_openapi() functionality.

Features:
- One-line MCP server creation from OpenAPI specs
- Automatic tool generation for all API endpoints
- Built-in authentication support
- Config file system for managing multiple APIs

Usage:
    ```python
    from bassi.core_v3.openapi_mcp import create_mcp_from_openapi

    # Create MCP server from OpenAPI spec (single line!)
    mcp = await create_mcp_from_openapi(
        name="github",
        openapi_url="https://api.github.com/openapi.json",
        auth_token="ghp_xxx"
    )
    ```
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

logger = logging.getLogger(__name__)


async def create_mcp_from_openapi(
    name: str,
    openapi_url: str,
    auth_token: str | None = None,
    api_key: str | None = None,
    api_key_header: str = "X-API-Key",
) -> FastMCP:
    """
    Create a FastMCP server from an OpenAPI specification.

    This uses FastMCP's built-in from_openapi() method which automatically:
    - Fetches and parses the OpenAPI spec
    - Creates tools for all API endpoints
    - Handles authentication
    - Manages HTTP requests

    Args:
        name: Name for the MCP server
        openapi_url: URL to OpenAPI JSON/YAML specification
        auth_token: Bearer token for authentication (optional)
        api_key: API key for authentication (optional)
        api_key_header: Header name for API key (default: X-API-Key)

    Returns:
        FastMCP server instance with all API endpoints as tools

    Example:
        ```python
        # Public API (no auth)
        mcp = await create_mcp_from_openapi(
            name="petstore",
            openapi_url="https://petstore3.swagger.io/api/v3/openapi.json"
        )

        # With bearer token
        mcp = await create_mcp_from_openapi(
            name="github",
            openapi_url="https://api.github.com/openapi.json",
            auth_token="ghp_xxx"
        )

        # With API key
        mcp = await create_mcp_from_openapi(
            name="weatherapi",
            openapi_url="https://weatherapi.com/openapi.json",
            api_key="abc123",
            api_key_header="X-API-Key"
        )
        ```
    """
    import httpx

    logger.info(f"Creating FastMCP server '{name}' from: {openapi_url}")

    # Prepare authentication headers
    headers = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    elif api_key:
        headers[api_key_header] = api_key

    # Fetch the OpenAPI spec
    async with httpx.AsyncClient() as temp_client:
        response = await temp_client.get(openapi_url, timeout=30.0)
        response.raise_for_status()
        openapi_spec = response.json()

    # Create httpx client with auth headers
    client = httpx.AsyncClient(headers=headers if headers else None, timeout=30.0)

    # Use FastMCP's built-in from_openapi() method
    mcp = FastMCP.from_openapi(
        openapi_spec=openapi_spec,
        client=client,
        name=name,
    )

    logger.info(f"✅ Created FastMCP server '{name}' using FastMCP.from_openapi()")

    return mcp


async def load_mcp_servers_from_config(config_file: str) -> dict[str, FastMCP]:
    """
    Load MCP servers from .api.json configuration file.

    Config file format:
    ```json
    {
        "servers": {
            "github": {
                "openapi_url": "https://api.github.com/openapi.json",
                "auth_token": "${GITHUB_TOKEN}"
            },
            "petstore": {
                "openapi_url": "https://petstore3.swagger.io/api/v3/openapi.json"
            },
            "weatherapi": {
                "openapi_url": "https://weatherapi.com/openapi.json",
                "api_key": "${WEATHER_API_KEY}",
                "api_key_header": "X-API-Key"
            }
        }
    }
    ```

    Environment variables in ${VAR} format will be expanded.

    Args:
        config_file: Path to .api.json file

    Returns:
        Dict mapping server names to FastMCP instances

    Example:
        ```python
        # Load all configured APIs
        servers = await load_mcp_servers_from_config(".api.json")

        # Use with BassiAgentSession
        config = SessionConfig(
            mcp_servers=servers  # Pass all servers
        )
        ```
    """
    config_path = Path(config_file)
    if not config_path.exists():
        logger.warning(f"Config file not found: {config_file}")
        return {}

    # Load config
    with open(config_path) as f:
        config = json.load(f)

    # Expand environment variables
    def expand_env_vars(obj):
        """Recursively expand ${VAR} in strings"""
        if isinstance(obj, str):
            def replacer(match):
                var_name = match.group(1)
                value = os.getenv(var_name)
                if value is None:
                    logger.warning(f"Environment variable ${{{var_name}}} not set")
                    return match.group(0)  # Return original ${VAR}
                return value
            return re.sub(r'\$\{(\w+)\}', replacer, obj)
        elif isinstance(obj, dict):
            return {k: expand_env_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [expand_env_vars(item) for item in obj]
        else:
            return obj

    config = expand_env_vars(config)

    # Create MCP servers
    mcp_servers = {}

    for server_name, server_config in config.get("servers", {}).items():
        try:
            logger.info(f"Loading MCP server: {server_name}")

            server = await create_mcp_from_openapi(
                name=server_name,
                openapi_url=server_config["openapi_url"],
                auth_token=server_config.get("auth_token"),
                api_key=server_config.get("api_key"),
                api_key_header=server_config.get("api_key_header", "X-API-Key"),
            )

            mcp_servers[server_name] = server
            logger.info(f"✅ Loaded MCP server: {server_name}")

        except Exception as e:
            logger.error(f"❌ Failed to load MCP server '{server_name}': {e}", exc_info=True)

    return mcp_servers
