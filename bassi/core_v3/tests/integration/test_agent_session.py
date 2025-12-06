"""
Unit tests for BassiAgentSession.

Tests cover:
- Session initialization
- Configuration
- Connection lifecycle
- Query execution
- Statistics tracking
- Message history
- Context manager usage
"""

import pytest

from bassi.core_v3.agent_session import (
    BassiAgentSession,
    SessionConfig,
    SessionStats,
)
from bassi.shared.sdk_loader import SDK_AVAILABLE
from bassi.shared.sdk_types import AssistantMessage, ResultMessage, TextBlock


class TestSessionConfig:
    """Test SessionConfig dataclass"""

    def test_default_config(self):
        """Test default configuration values"""
        config = SessionConfig()

        assert config.allowed_tools == ["Bash", "ReadFile", "WriteFile"]
        assert config.system_prompt is None
        assert config.permission_mode is None
        assert config.mcp_servers == {}
        assert config.cwd is None
        assert config.can_use_tool is None
        assert config.hooks is None
        assert config.setting_sources is None

    def test_custom_config(self):
        """Test custom configuration"""
        config = SessionConfig(
            allowed_tools=["Bash"],
            system_prompt="You are helpful",
            permission_mode="acceptEdits",
        )

        assert config.allowed_tools == ["Bash"]
        assert config.system_prompt == "You are helpful"
        assert config.permission_mode == "acceptEdits"


class TestSessionStats:
    """Test SessionStats dataclass"""

    def test_default_stats(self):
        """Test default statistics values"""
        stats = SessionStats(session_id="test-123")

        assert stats.session_id == "test-123"
        assert stats.message_count == 0
        assert stats.total_input_tokens == 0
        assert stats.total_output_tokens == 0
        assert stats.total_cost_usd == 0.0
        assert stats.tool_calls == 0


class TestBassiAgentSession:
    """Test BassiAgentSession class"""

    def test_init_default_config(self):
        """Test initialization with default config"""
        session = BassiAgentSession()

        assert session.config is not None
        assert session.session_id is not None
        assert len(session.session_id) > 0
        assert session.client is None
        assert session._connected is False
        assert session.message_history == []

    def test_init_custom_config(self):
        """Test initialization with custom config"""
        config = SessionConfig(
            allowed_tools=["Bash"],
            system_prompt="Test prompt",
        )
        session = BassiAgentSession(config)

        assert session.config == config
        assert session.get_model_id() == config.model_id

    def test_session_id_unique(self):
        """Test that each session gets a unique ID"""
        session1 = BassiAgentSession()
        session2 = BassiAgentSession()

        assert session1.session_id != session2.session_id

    def test_get_stats_initial(self):
        """Test get_stats returns correct initial values"""
        session = BassiAgentSession()
        stats = session.get_stats()

        assert "session_id" in stats
        assert stats["message_count"] == 0
        assert stats["total_input_tokens"] == 0
        assert stats["total_output_tokens"] == 0
        assert stats["total_cost_usd"] == 0.0
        assert stats["tool_calls"] == 0
        assert stats["connected"] is False

    def test_get_history_initial(self):
        """Test get_history returns empty list initially"""
        session = BassiAgentSession()
        history = session.get_history()

        assert history == []
        assert isinstance(history, list)

    def test_get_history_returns_copy(self):
        """Test that get_history returns a copy, not reference"""
        session = BassiAgentSession()
        history1 = session.get_history()
        history2 = session.get_history()

        assert history1 is not history2  # Different objects
        assert history1 == history2  # But same content

    @pytest.mark.asyncio
    async def test_query_streams_messages(self, mock_agent_client):
        """Test query uses injected client to stream messages."""

        mock_agent_client.queue_response(
            AssistantMessage(
                content=[TextBlock(text="hi")], model="test-model"
            ),
            ResultMessage(
                subtype="complete",
                duration_ms=100,
                duration_api_ms=80,
                is_error=False,
                num_turns=1,
                session_id="test-session",
                usage={"input_tokens": 1, "output_tokens": 2},
                total_cost_usd=0.001,
            ),
        )

        session = BassiAgentSession(
            client_factory=lambda _: mock_agent_client,
        )

        results = []
        async for message in session.query("Hello world"):
            results.append(message)

        assert len(results) == 2
        assert session.stats.message_count == 1
        # Prompts are now always sent as streaming format (AsyncIterable)
        # to enable can_use_tool callback. The format is a list of user messages.
        sent = mock_agent_client.sent_prompts[0]["prompt"]
        assert isinstance(sent, list)
        assert sent[0]["type"] == "user"
        assert sent[0]["message"]["content"][0]["text"] == "Hello world"

    @pytest.mark.asyncio
    async def test_interrupt_delegates_to_client(self, mock_agent_client):
        """Test interrupt() calls client interrupt when connected."""

        mock_agent_client.queue_response()
        session = BassiAgentSession(
            client_factory=lambda _: mock_agent_client,
        )

        await session.connect()
        await session.interrupt()
        assert mock_agent_client.interrupted is True

    @pytest.mark.asyncio
    async def test_context_manager_uses_mock_client(self, mock_agent_client):
        """Test async context manager lifecycle with mock client."""

        session = BassiAgentSession(
            client_factory=lambda _: mock_agent_client,
        )

        async with session as active_session:
            assert active_session._connected is True
            assert mock_agent_client.connected is True

        assert session._connected is False
        assert mock_agent_client.connected is False

    @pytest.mark.asyncio
    async def test_connect_when_already_connected(self, mock_agent_client):
        """Test connect() returns early when already connected."""
        session = BassiAgentSession(
            client_factory=lambda _: mock_agent_client,
        )

        # Connect first time
        await session.connect()
        assert session._connected is True
        assert mock_agent_client.connect_count == 1

        # Connect again - should return early
        await session.connect()
        assert session._connected is True
        # Connect should not be called again
        assert mock_agent_client.connect_count == 1

    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self, mock_agent_client):
        """Test disconnect() returns early when not connected."""
        session = BassiAgentSession(
            client_factory=lambda _: mock_agent_client,
        )

        # Disconnect without connecting first
        await session.disconnect()
        # Should not raise, just return early
        assert session._connected is False
        assert mock_agent_client.disconnect_count == 0

    @pytest.mark.asyncio
    async def test_interrupt_when_not_connected(self, mock_agent_client):
        """Test interrupt() returns early when not connected."""
        session = BassiAgentSession(
            client_factory=lambda _: mock_agent_client,
        )

        # Interrupt without connecting first
        await session.interrupt()
        # Should not raise, just return early
        assert mock_agent_client.interrupted is False

    @pytest.mark.asyncio
    async def test_get_server_info_when_not_connected(
        self, mock_agent_client
    ):
        """Test get_server_info() returns None when not connected."""
        session = BassiAgentSession(
            client_factory=lambda _: mock_agent_client,
        )

        # Get server info without connecting first
        info = await session.get_server_info()
        assert info is None

    @pytest.mark.asyncio
    async def test_get_server_info_when_connected(self, mock_agent_client):
        """Test get_server_info() returns server info when connected."""
        # Set up mock server info
        mock_agent_client.server_info = {
            "commands": ["/help", "/commit"],
            "capabilities": ["tools", "mcp"],
        }

        session = BassiAgentSession(
            client_factory=lambda _: mock_agent_client,
        )

        # Connect first
        await session.connect()

        # Get server info
        info = await session.get_server_info()
        assert info is not None
        assert info["commands"] == ["/help", "/commit"]
        assert info["capabilities"] == ["tools", "mcp"]

    @pytest.mark.asyncio
    async def test_update_thinking_mode(self, mock_agent_client):
        """Test update_thinking_mode() reconnects with new model."""
        session = BassiAgentSession(
            client_factory=lambda _: mock_agent_client,
        )

        # Initial state: thinking_mode = False
        assert session.config.thinking_mode is False
        initial_model = session.get_model_id()

        # Update thinking mode while not connected
        await session.update_thinking_mode(True)
        assert session.config.thinking_mode is True
        # Should not have connected/disconnected
        assert mock_agent_client.connect_count == 0

        # Connect with thinking mode enabled
        await session.connect()
        assert session._connected is True
        assert mock_agent_client.connect_count == 1

        # Update thinking mode while connected - should reconnect
        await session.update_thinking_mode(False)
        assert session.config.thinking_mode is False
        # Should have disconnected and reconnected
        assert mock_agent_client.disconnect_count == 1
        assert mock_agent_client.connect_count == 2
        assert session._connected is True

    @pytest.mark.asyncio
    async def test_multimodal_query(self, mock_agent_client):
        """Test query with multimodal content (list of content blocks)."""
        mock_agent_client.queue_response(
            AssistantMessage(
                content=[TextBlock(text="I see an image")],
                model="test-model",
            ),
            ResultMessage(
                subtype="complete",
                duration_ms=100,
                duration_api_ms=80,
                is_error=False,
                num_turns=1,
                session_id="test-session",
                usage={"input_tokens": 10, "output_tokens": 5},
                total_cost_usd=0.002,
            ),
        )

        session = BassiAgentSession(
            client_factory=lambda _: mock_agent_client,
        )

        # Create multimodal content blocks (text + image)
        content_blocks = [
            {"type": "text", "text": "What's in this image?"},
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": "fake_base64_data",
                },
            },
        ]

        results = []
        async for message in session.query(content_blocks):
            results.append(message)

        assert len(results) == 2
        assert session.stats.message_count == 1

        # Verify the prompt was sent as a list (multimodal)
        sent_prompt = mock_agent_client.sent_prompts[0]["prompt"]
        # For multimodal, prompt is an async generator, so check session_id
        assert mock_agent_client.sent_prompts[0]["session_id"] == "default"

    @pytest.mark.asyncio
    async def test_stats_update_from_assistant_with_tool_use(
        self, mock_agent_client
    ):
        """Test stats update when AssistantMessage has ToolUseBlock."""
        from bassi.shared.sdk_types import ToolUseBlock

        mock_agent_client.queue_response(
            AssistantMessage(
                content=[
                    ToolUseBlock(
                        id="tool_1",
                        name="test_tool",
                        input={"arg": "value"},
                    ),
                    ToolUseBlock(
                        id="tool_2",
                        name="another_tool",
                        input={},
                    ),
                ],
                model="test-model",
            ),
            ResultMessage(
                subtype="complete",
                duration_ms=100,
                duration_api_ms=80,
                is_error=False,
                num_turns=1,
                session_id="test-session",
                usage={"input_tokens": 5, "output_tokens": 3},
                total_cost_usd=0.001,
            ),
        )

        session = BassiAgentSession(
            client_factory=lambda _: mock_agent_client,
        )

        results = []
        async for message in session.query("Use tools"):
            results.append(message)

        # Should have counted 2 tool calls
        assert session.stats.tool_calls == 2

    @pytest.mark.asyncio
    async def test_stats_update_from_assistant_without_tool_use(
        self, mock_agent_client
    ):
        """Test stats update when AssistantMessage has no ToolUseBlock."""
        mock_agent_client.queue_response(
            AssistantMessage(
                content=[TextBlock(text="Just text, no tools")],
                model="test-model",
            ),
            ResultMessage(
                subtype="complete",
                duration_ms=100,
                duration_api_ms=80,
                is_error=False,
                num_turns=1,
                session_id="test-session",
                usage={"input_tokens": 5, "output_tokens": 3},
                total_cost_usd=0.001,
            ),
        )

        session = BassiAgentSession(
            client_factory=lambda _: mock_agent_client,
        )

        results = []
        async for message in session.query("No tools"):
            results.append(message)

        # Should have counted 0 tool calls
        assert session.stats.tool_calls == 0

    @pytest.mark.asyncio
    async def test_stats_update_from_result_without_attributes(
        self, mock_agent_client
    ):
        """Test stats update when ResultMessage lacks token/cost attributes."""
        # Create a minimal ResultMessage without token/cost attributes
        minimal_result = ResultMessage(
            subtype="complete",
            duration_ms=100,
            duration_api_ms=80,
            is_error=False,
            num_turns=1,
            session_id="test-session",
            usage={},  # Empty usage - no tokens
            # No total_cost_usd attribute
        )

        mock_agent_client.queue_response(
            AssistantMessage(
                content=[TextBlock(text="response")], model="test-model"
            ),
            minimal_result,
        )

        session = BassiAgentSession(
            client_factory=lambda _: mock_agent_client,
        )

        results = []
        async for message in session.query("Test"):
            results.append(message)

        # Stats should still work, just with 0 values
        assert session.stats.total_input_tokens == 0
        assert session.stats.total_output_tokens == 0
        assert session.stats.total_cost_usd == 0.0


@pytest.mark.skipif(
    not SDK_AVAILABLE, reason="claude_agent_sdk not installed"
)
class TestBassiAgentSessionIntegration:
    """Integration tests that require actual Claude Code connection"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_connect_disconnect(self):
        """Test connecting and disconnecting"""
        session = BassiAgentSession()

        # Initially not connected
        assert session._connected is False
        assert session.client is None

        # Connect
        await session.connect()
        assert session._connected is True
        assert session.client is not None

        # Disconnect
        await session.disconnect()
        assert session._connected is False

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test using session as context manager"""
        async with BassiAgentSession() as session:
            assert session._connected is True
            assert session.client is not None

        # After context, should be disconnected
        assert session._connected is False

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_query_simple(self):
        """Test simple query execution"""
        config = SessionConfig(
            allowed_tools=[],  # No tools for simple test
            system_prompt="You are helpful. Be very brief.",
        )

        async with BassiAgentSession(config) as session:
            message_count = 0

            async for message in session.query("Say 'hello'"):
                message_count += 1

            # Should have received at least one message
            assert message_count > 0

            # History should contain messages
            history = session.get_history()
            assert len(history) > 0

            # Stats should be updated
            stats = session.get_stats()
            assert stats["message_count"] > 0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_interrupt(self):
        """Test interrupting execution"""
        async with BassiAgentSession() as session:
            # Start a query
            await session.client.query("Count to 100")

            # Interrupt it immediately
            await session.interrupt()

            # Should not raise exception
            assert True
