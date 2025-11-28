"""
Agent Session - Wrapper around the Claude Agent SDK client.

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

from bassi.shared.agent_protocol import (
    AgentClient,
    AgentClientFactory,
    default_claude_client_factory,
    resolve_model_id,
)
from bassi.shared.sdk_types import (
    AssistantMessage,
    Message,
    ResultMessage,
    ToolUseBlock,
    UserMessage,
)


@dataclass
class SessionConfig:
    """Configuration for a Bassi agent session"""

    # Core settings
    allowed_tools: list[str] | None = field(
        default_factory=lambda: ["Bash", "ReadFile", "WriteFile"]
    )
    system_prompt: Optional[str] = None
    permission_mode: Optional[str] = (
        None  # "default", "acceptEdits", "plan", "bypassPermissions"
    )

    # Model configuration
    model_id: str = "claude-sonnet-4-5-20250929"
    thinking_mode: bool = False  # Enable extended thinking via thinking parameter (not model suffix)

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

    # Resume / streaming support
    resume_session_id: Optional[str] = None
    include_partial_messages: bool = False
    max_thinking_tokens: int = 10000


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

    def __init__(
        self,
        config: Optional[SessionConfig] = None,
        client_factory: Optional[AgentClientFactory] = None,
    ):
        """
        Initialize agent session.

        Args:
            config: Session configuration. If None, uses defaults.
            client_factory: Optional factory for creating AgentClient instances.
        """
        self.config = config or SessionConfig()
        self.session_id = str(uuid.uuid4())
        self.client_factory: AgentClientFactory = (
            client_factory or default_claude_client_factory
        )

        # Client instance (created on connect)
        self.client: Optional[AgentClient] = None

        # Session state
        self._connected = False
        self.message_history: list[Message] = []
        self.stats = SessionStats(session_id=self.session_id)
        # Track the current workspace/session id when reusing the single agent
        self.current_workspace_id: Optional[str] = None
        # Conversation context for injecting previous chat history into prompts
        self._conversation_context: Optional[str] = None

    def reset_for_new_session(self, session_id: str) -> None:
        """
        Reset all in-memory state when reusing the single shared agent.

        Without this, the agent keeps the previous conversation history and
        replies with stale context after a user creates a brand-new session.
        """
        import logging

        logger = logging.getLogger(__name__)
        logger.info(
            "🧹 [SESSION] Resetting agent state for new session %s "
            "(clearing %d history messages)",
            session_id[:8],
            len(self.message_history),
        )
        self.message_history.clear()
        # Clear any pending conversation context
        self._conversation_context = None
        # Reset stats and align identifiers
        self.stats = SessionStats(session_id=session_id)
        self.session_id = session_id
        self.current_workspace_id = session_id

    async def prepare_for_session(self, session_id: str, resume: bool) -> None:
        """
        Prepare agent for a new or resumed session.

        With pool architecture, we keep the SDK client connected and just
        reset in-memory state. The SDK manages server-side conversation
        state via session_id passed to each query.
        
        NOTE: We do NOT disconnect/reconnect here because:
        1. The SDK client may be connected from a different async task (pool startup)
        2. Disconnecting from a different task causes "cancel scope" errors
        3. The SDK's session_id parameter handles conversation isolation
        
        Args:
            session_id: The chat ID to use for this session
            resume: Whether this is resuming an existing chat (loads history)
        """
        import logging

        logger = logging.getLogger(__name__)

        # Clear in-memory state
        self.reset_for_new_session(session_id)

        # Configure resume for SDK (only when reopening an existing session)
        self.config.resume_session_id = session_id if resume else None

        # Ensure connected (don't reconnect, just connect if needed)
        if not self._connected:
            await self.connect()
            logger.info(
                "🔌 [SESSION] Connected SDK client for session %s (resume=%s)",
                session_id[:8],
                resume,
            )
        else:
            logger.info(
                "♻️ [SESSION] Reusing connected SDK client for session %s (resume=%s)",
                session_id[:8],
                resume,
            )

    def get_model_id(self) -> str:
        """Get the effective model ID based on thinking mode."""
        return resolve_model_id(self.config)

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
        import logging

        logger = logging.getLogger(__name__)

        logger.info(
            f"🔶 [SESSION] connect() called, _connected={self._connected}"
        )
        if self._connected:
            logger.info("🔶 [SESSION] Already connected, returning")
            return

        logger.info("🔶 [SESSION] Creating AgentClient via factory")
        self.client = self.client_factory(self.config)
        logger.info("🔶 [SESSION] AgentClient created, calling connect()...")
        await self.client.connect()
        logger.info("🔶 [SESSION] client.connect() completed successfully")
        self._connected = True
        logger.info("🔶 [SESSION] Session connected")

    async def disconnect(self):
        """Disconnect from Claude Code"""
        if not self._connected or not self.client:
            return

        await self.client.disconnect()
        self._connected = False
        self.client = None

    def restore_conversation_history(self, history: list[dict]) -> None:
        """
        Restore conversation history from workspace.

        Args:
            history: List of message dicts with role, content, timestamp
                     Format: [{"role": "user", "content": "...", "timestamp": "..."}]

        This method:
        1. Clears existing message history
        2. Stores a conversation summary for context injection
        3. Populates message_history for local tracking
        
        NOTE: Since we don't reconnect the SDK (to avoid cancel scope errors),
        we store a summary that gets prepended to the next query to give
        the agent context about the previous conversation.
        """
        import logging

        logger = logging.getLogger(__name__)

        logger.info(
            f"🔷 [SESSION] Restoring {len(history)} messages from workspace"
        )

        # CRITICAL: Clear existing message history before restoring
        if self.message_history:
            logger.info(
                f"🧹 [SESSION] Clearing {len(self.message_history)} existing messages"
            )
            self.message_history.clear()

        # Import TextBlock for AssistantMessage content
        from bassi.shared.sdk_types import TextBlock

        # Get model for AssistantMessage (required parameter)
        model = self.get_model_id()

        # Build FULL conversation context for injection
        # The SDK doesn't persist history across agent pool reuse, so we inject it
        # Use full messages with a character limit to avoid exceeding context window
        MAX_CONTEXT_CHARS = 50000  # ~12k tokens, safe for Claude's context
        
        if history:
            context_lines = ["[CONVERSATION HISTORY - You are continuing this chat:]"]
            total_chars = len(context_lines[0])
            
            # Start from oldest, but we may need to truncate old messages if too long
            for msg in history:
                role = msg["role"].upper()
                content = msg["content"]
                line = f"\n{role}: {content}"
                
                if total_chars + len(line) > MAX_CONTEXT_CHARS:
                    # Would exceed limit - truncate remaining messages
                    context_lines.append(f"\n[...earlier messages truncated...]")
                    # Add the last few messages that fit
                    remaining = MAX_CONTEXT_CHARS - total_chars - 100
                    if remaining > 0 and len(content) > 0:
                        context_lines.append(f"\n{role}: {content[:remaining]}...")
                    break
                
                context_lines.append(line)
                total_chars += len(line)
            
            context_lines.append("\n[END OF HISTORY - Continue the conversation from here.]")
            self._conversation_context = "".join(context_lines)
            logger.info(
                f"📝 [SESSION] Built FULL conversation context: "
                f"{len(history)} messages, {len(self._conversation_context)} chars"
            )
        else:
            self._conversation_context = None

        # Populate message_history for local tracking
        for msg in history:
            role = msg["role"]
            content = msg["content"]

            if role == "user":
                self.message_history.append(UserMessage(content=content))
            elif role == "assistant":
                self.message_history.append(
                    AssistantMessage(
                        content=[TextBlock(text=content)], model=model
                    )
                )
            else:
                logger.warning(f"⚠️ Unknown message role: {role}, skipping")

        logger.info(
            f"✅ [SESSION] Restored {len(self.message_history)} messages to local history"
        )

    async def update_thinking_mode(self, thinking_mode: bool):
        """
        Update thinking mode and reconnect with new model.

        Args:
            thinking_mode: Enable/disable thinking mode

        Note:
            This will disconnect and reconnect the session with the new model.
        """
        import logging

        logger = logging.getLogger(__name__)

        logger.info(
            f"🔄 [SESSION] Updating thinking mode: {self.config.thinking_mode} → {thinking_mode}"
        )

        # Update config
        self.config.thinking_mode = thinking_mode

        # If already connected, reconnect with new client
        if self._connected:
            logger.info("🔄 [SESSION] Reconnecting with new model...")
            await self.disconnect()
            await self.connect()
            logger.info(
                f"✅ [SESSION] Reconnected with model: {self.get_model_id()}"
            )

    async def _create_multimodal_message(
        self, content_blocks: list[dict], session_id: str
    ):
        """
        Create an async generator for multimodal content.

        The Agent SDK expects an AsyncIterable of message dictionaries in Anthropic API format.

        Args:
            content_blocks: List of content block dictionaries (Anthropic API format)
            session_id: Session identifier

        Yields:
            Message dictionary in Agent SDK control protocol format
        """
        # Create a single message with multimodal content
        message = {
            "type": "user",
            "message": {
                "role": "user",
                "content": content_blocks,  # Pass content blocks directly (Anthropic API format)
            },
            "parent_tool_use_id": None,
            "session_id": session_id,
        }
        yield message

    async def query(
        self, prompt: str | list[dict], session_id: str = "default"
    ) -> AsyncIterator[Message]:
        """
        Send a query and stream responses.

        Args:
            prompt: User prompt (string) or content blocks (list of dicts for multimodal)
            session_id: Session identifier for multi-turn conversations

        Yields:
            Message objects from the Agent SDK

        Example:
            ```python
            # Text-only query
            async for message in session.query("Hello"):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        print(block.text)

            # Multimodal query (text + image)
            content_blocks = [
                {"type": "text", "text": "What's in this image?"},
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "..."}}
            ]
            async for message in session.query(content_blocks):
                ...
            ```
        """
        if not self._connected:
            await self.connect()

        # Inject conversation context if we resumed a chat
        # This gives the agent context about previous messages since SDK session may not persist
        if self._conversation_context:
            import logging
            logger = logging.getLogger(__name__)
            logger.info("📝 [SESSION] Injecting conversation context into prompt")
            
            if isinstance(prompt, list):
                # Multimodal: prepend context as first text block
                context_block = {"type": "text", "text": self._conversation_context + "\n\n"}
                prompt = [context_block] + prompt
            else:
                # Text: prepend context to string
                prompt = self._conversation_context + "\n\n" + prompt
            
            # Clear context after first use (don't repeat in subsequent queries)
            self._conversation_context = None

        # Handle multimodal vs text-only
        if isinstance(prompt, list):
            # Multimodal: Create async generator with message dictionary
            sdk_prompt = self._create_multimodal_message(prompt, session_id)
        else:
            # Text-only: Pass string directly
            sdk_prompt = prompt

        # Send query (Agent SDK handles both string and AsyncIterable[dict])
        await self.client.query(sdk_prompt, session_id=session_id)

        # Track in history
        # If prompt is a list, convert to UserMessage with content blocks
        if isinstance(prompt, list):
            self.message_history.append(UserMessage(content=prompt))
        else:
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

    async def set_permission_mode(self, mode: str):
        """
        Change permission mode during conversation.

        Args:
            mode: 'default', 'acceptEdits', or 'bypassPermissions'
        """
        import logging
        logger = logging.getLogger(__name__)
        
        if not self._connected or not self.client:
            logger.warning("⚠️ Cannot set permission mode: not connected")
            return

        logger.info(f"🔐 [SESSION] Setting permission mode to: {mode}")
        await self.client.set_permission_mode(mode)
        self.config.permission_mode = mode

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
        # Extract tokens from usage dict
        if message.usage:
            input_tokens = message.usage.get("input_tokens")
            output_tokens = message.usage.get("output_tokens")
            if input_tokens is not None:
                self.stats.total_input_tokens += input_tokens
            if output_tokens is not None:
                self.stats.total_output_tokens += output_tokens

        # Add cost if available
        if message.total_cost_usd is not None:
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
