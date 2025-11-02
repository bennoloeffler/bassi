"""
Bassi Core V3 - Built on Claude Agent SDK

This is the CORRECT implementation using claude-agent-sdk.
"""

__version__ = "3.0.0"

from .agent_session import BassiAgentSession, SessionConfig
from .discovery import BassiDiscovery, display_startup_discovery
from .message_converter import convert_message_to_websocket, convert_messages_batch
from .web_server_v3 import WebUIServerV3, start_web_server_v3

__all__ = [
    "BassiAgentSession",
    "SessionConfig",
    "BassiDiscovery",
    "display_startup_discovery",
    "convert_message_to_websocket",
    "convert_messages_batch",
    "WebUIServerV3",
    "start_web_server_v3",
]
