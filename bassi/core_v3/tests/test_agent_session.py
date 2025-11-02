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
from bassi.core_v3.agent_session import BassiAgentSession, SessionConfig, SessionStats


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
        assert session.sdk_options.allowed_tools == ["Bash"]
        assert session.sdk_options.system_prompt == "Test prompt"

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


# Integration tests (require Claude Code to be installed)
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
