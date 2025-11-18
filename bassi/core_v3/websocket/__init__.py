"""
WebSocket package for V3 web server.

Contains WebSocket connection and message handling.
"""

from bassi.core_v3.websocket.connection_manager import ConnectionManager
from bassi.core_v3.websocket.message_handler import MessageHandler

__all__ = ["ConnectionManager", "MessageHandler"]
