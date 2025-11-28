"""
Browser Session Model

Represents an active WebSocket connection from a browser tab.

NOTE: This is distinct from "chat context" (ChatWorkspace).
- Browser session: ephemeral WebSocket connection
- Chat context: persistent conversation history + files

A browser session can switch between different chat contexts.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from fastapi import WebSocket


@dataclass
class BrowserSession:
    """
    Represents an active browser WebSocket connection.

    Lifecycle:
    - Created when browser connects via WebSocket
    - Destroyed when WebSocket disconnects
    - Has exactly one agent assigned from the pool
    - Can view/edit any chat context

    Attributes:
        browser_id: Unique identifier for this browser connection
        websocket: The WebSocket connection
        agent: Agent assigned from pool
        current_chat_id: Currently active chat context (or None for new)
        connected_at: When browser connected
        question_service: Service for interactive questions
    """

    browser_id: str
    websocket: WebSocket
    agent: Any  # BassiAgentSession (avoid circular import)
    current_chat_id: Optional[str] = None
    connected_at: datetime = field(default_factory=datetime.now)
    question_service: Any = None  # InteractiveQuestionService
    workspace: Any = None  # ChatWorkspace

    def __str__(self) -> str:
        chat = self.current_chat_id[:8] if self.current_chat_id else "new"
        return f"BrowserSession({self.browser_id[:8]}, chat={chat})"

    def get_info(self) -> dict:
        """Get browser session info for debugging/logging."""
        return {
            "browser_id": self.browser_id,
            "current_chat_id": self.current_chat_id,
            "connected_at": self.connected_at.isoformat(),
            "has_agent": self.agent is not None,
            "has_workspace": self.workspace is not None,
        }

