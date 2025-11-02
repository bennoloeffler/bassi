"""
Agent Session - Wrapper around Claude Agent SDK's ClaudeSDKClient.

This module provides a clean interface to the Agent SDK while adding:
- Session lifecycle management
- Message history tracking
- Statistics and monitoring
- Event conversion for web UI
"""

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Optional

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from claude_agent_sdk.types import (
    AssistantMessage,
    ContentBlock,
    Message,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)


@dataclass
class SessionConfig:
    """Configuration for a Bassi agent session"""

    # Core settings
    allowed_tools: list[str] = field(default_factory=lambda: ["Bash", "ReadFile", "WriteFile"])
    system_prompt: Optional[str] = None
    permission_mode: Optional[str] = None  # "default", "acceptEdits", "plan", "bypassPermissions"

    # MCP servers
    mcp_servers: dict[str, Any] = field(default_factory=dict)

    # Working directory
    cwd: Optional[Path] = None

    # Permission callback
    can_use_tool: Optional[Callable] = None

    # Hooks
    hooks: Optional[dict[str, Callable]] = None

    # Settings sources
    setting_sources: Optional[list[str]] = None


@dataclass
class SessionStats:
    """Statistics for a session"""

    session_id: str
    message_count: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    tool_calls: int = 0


class BassiAgentSession:
    """
    Wrapper around ClaudeSDKClient providing session management.

    Features:
    - Automatic session lifecycle management
    - Message history tracking
    - Statistics collection
    - Event conversion for web UI
    - Context manager support

    Example:
        ```python
        config = SessionConfig(
            allowed_tools=["Bash", "ReadFile"],
            system_prompt="You are helpful"
        )

        async with BassiAgentSession(config) as session:
            async for message in session.query("What files are here?"):
                print(message)
        ```
    """

    def __init__(self, config: Optional[SessionConfig] = None):
        """
        Initialize agent session.

        Args:
            config: Session configuration. If None, uses defaults.
        """
        self.config = config or SessionConfig()
        self.session_id = str(uuid.uuid4())

        # Convert our config to Agent SDK options
        self.sdk_options = ClaudeAgentOptions(
            allowed_tools=self.config.allowed_tools,
            system_prompt=self.config.system_prompt,
            permission_mode=self.config.permission_mode,
            mcp_servers=self.config.mcp_servers,
            cwd=self.config.cwd,
            can_use_tool=self.config.can_use_tool,
            hooks=self.config.hooks,
            setting_sources=self.config.setting_sources,
        )

        # Client instance (created on connect)
        self.client: Optional[ClaudeSDKClient] = None

        # Session state
        self._connected = False
        self.message_history: list[Message] = []
        self.stats = SessionStats(session_id=self.session_id)

    async def __aenter__(self):
        """Context manager entry"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        await self.disconnect()

    async def connect(self):
        """
        Connect to Claude Code.

        Raises:
            CLINotFoundError: If Claude Code is not installed
            CLIConnectionError: If connection fails
        """
        if self._connected:
            return

        self.client = ClaudeSDKClient(options=self.sdk_options)
        await self.client.connect()
        self._connected = True

    async def disconnect(self):
        """Disconnect from Claude Code"""
        if not self._connected or not self.client:
            return

        await self.client.disconnect()
        self._connected = False

    async def query(
        self,
        prompt: str,
        session_id: str = "default"
    ) -> AsyncIterator[Message]:
        """
        Send a query and stream responses.

        Args:
            prompt: User prompt to send
            session_id: Session identifier for multi-turn conversations

        Yields:
            Message objects from the Agent SDK

        Example:
            ```python
            async for message in session.query("Hello"):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            print(block.text)
            ```
        """
        if not self._connected:
            await self.connect()

        # Send query
        await self.client.query(prompt, session_id=session_id)

        # Track in history
        self.message_history.append(UserMessage(content=prompt))
        self.stats.message_count += 1

        # Stream responses
        async for message in self.client.receive_response():
            # Track in history
            self.message_history.append(message)

            # Update stats
            if isinstance(message, AssistantMessage):
                self._update_stats_from_assistant(message)
            elif isinstance(message, ResultMessage):
                self._update_stats_from_result(message)

            yield message

    async def interrupt(self):
        """
        Interrupt the current execution.

        This stops Claude Code from executing further actions.
        """
        if not self._connected or not self.client:
            return

        await self.client.interrupt()

    async def get_server_info(self) -> dict[str, Any] | None:
        """
        Get server information including available commands, MCP tools, agents, etc.

        Returns:
            Dictionary with server info including:
            - commands: Available slash commands
            - output_style: Current output style settings
            - capabilities: Server capabilities
            - mcp_tools: Available MCP tools (if any)

        Example:
            ```python
            info = await session.get_server_info()
            if info:
                print(f"Commands: {info.get('commands', [])}")
                print(f"MCP tools available")
            ```
        """
        if not self._connected or not self.client:
            return None

        return await self.client.get_server_info()

    def _update_stats_from_assistant(self, message: AssistantMessage):
        """Update statistics from assistant message"""
        # Count tool calls
        for block in message.content:
            if isinstance(block, ToolUseBlock):
                self.stats.tool_calls += 1

    def _update_stats_from_result(self, message: ResultMessage):
        """Update statistics from result message"""
        if hasattr(message, 'input_tokens'):
            self.stats.total_input_tokens += message.input_tokens
        if hasattr(message, 'output_tokens'):
            self.stats.total_output_tokens += message.output_tokens
        if hasattr(message, 'total_cost_usd'):
            self.stats.total_cost_usd += message.total_cost_usd

    def get_stats(self) -> dict[str, Any]:
        """
        Get session statistics.

        Returns:
            Dictionary with session stats
        """
        return {
            "session_id": self.stats.session_id,
            "message_count": self.stats.message_count,
            "total_input_tokens": self.stats.total_input_tokens,
            "total_output_tokens": self.stats.total_output_tokens,
            "total_cost_usd": self.stats.total_cost_usd,
            "tool_calls": self.stats.tool_calls,
            "connected": self._connected,
        }

    def get_history(self) -> list[Message]:
        """
        Get message history.

        Returns:
            List of all messages in this session
        """
        return self.message_history.copy()
