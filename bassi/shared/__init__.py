"""
Shared modules for bassi

Common functionality used across V1 (CLI) and V3 (Web) systems.
"""

from bassi.shared.logging_config import configure_logging
from bassi.shared.mcp_registry import (
    create_mcp_registry,
    create_sdk_mcp_servers,
    load_external_mcp_servers,
)

__all__ = [
    "configure_logging",
    "create_mcp_registry",
    "create_sdk_mcp_servers",
    "load_external_mcp_servers",
]
