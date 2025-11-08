"""
Graceful import helpers for Claude Agent SDK message types.

The repo's tests run without the proprietary ``claude-agent-sdk`` package
installed, so importing the real SDK types at module import time would raise
``ModuleNotFoundError``.  This module attempts to import the official classes
and, if they are unavailable, provides lightweight stub implementations with the
same attribute surface that the application and tests rely on.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "AssistantMessage",
    "ContentBlock",
    "Message",
    "ResultMessage",
    "SystemMessage",
    "TextBlock",
    "ThinkingBlock",
    "ToolResultBlock",
    "ToolUseBlock",
    "UserMessage",
]


class _SDKStub:
    """Base class for stubbed SDK objects."""

    def __init__(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


try:  # pragma: no cover - exercised when SDK is installed
    from claude_agent_sdk.types import (
        AssistantMessage,
        ContentBlock,
        Message,
        ResultMessage,
        SystemMessage,
        TextBlock,
        ThinkingBlock,
        ToolResultBlock,
        ToolUseBlock,
        UserMessage,
    )
except ModuleNotFoundError:  # pragma: no cover - triggered in OSS/CI envs

    class Message(_SDKStub):
        """Placeholder for claude_agent_sdk.types.Message"""

    class AssistantMessage(Message):
        """Placeholder for AssistantMessage"""

    class ResultMessage(Message):
        """Placeholder for ResultMessage"""

    class SystemMessage(Message):
        """Placeholder for SystemMessage"""

    class UserMessage(Message):
        """Placeholder for UserMessage"""

    class ContentBlock(_SDKStub):
        """Base class for stub content blocks"""

    class TextBlock(ContentBlock):
        def __init__(self, text: str = "", **kwargs: Any) -> None:
            super().__init__(text=text, **kwargs)

    class ThinkingBlock(ContentBlock):
        def __init__(self, thinking: str = "", **kwargs: Any) -> None:
            super().__init__(thinking=thinking, **kwargs)

    class ToolUseBlock(ContentBlock):
        def __init__(
            self,
            id: str = "",
            name: str = "",
            input: Any = None,
            **kwargs: Any,
        ) -> None:
            super().__init__(id=id, name=name, input=input or {}, **kwargs)

    class ToolResultBlock(ContentBlock):
        def __init__(
            self,
            tool_use_id: str = "",
            content: Any = None,
            is_error: bool | None = False,
            **kwargs: Any,
        ) -> None:
            super().__init__(
                tool_use_id=tool_use_id,
                content=content or [],
                is_error=is_error,
                **kwargs,
            )

    # Re-export stubs
    AssistantMessage = AssistantMessage
    ContentBlock = ContentBlock
    ResultMessage = ResultMessage
    SystemMessage = SystemMessage
    TextBlock = TextBlock
    ThinkingBlock = ThinkingBlock
    ToolResultBlock = ToolResultBlock
    ToolUseBlock = ToolUseBlock
    UserMessage = UserMessage
