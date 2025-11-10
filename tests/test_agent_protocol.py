"""
Unit tests for agent_protocol module.

Tests the agent client protocol, adapter, and helper functions.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from bassi.shared.agent_protocol import (
    ClaudeAgentClient,
    build_claude_agent_options,
    default_claude_client_factory,
    resolve_model_id,
)


class TestResolveModelId:
    """Test model ID resolution with thinking mode"""

    def test_default_model_no_thinking(self):
        """Should return default model when no config attributes set"""

        class MinimalConfig:
            pass

        config = MinimalConfig()
        result = resolve_model_id(config)

        assert result == "claude-sonnet-4-5-20250929"

    def test_custom_model_no_thinking(self):
        """Should return custom model when specified without thinking mode"""

        class ConfigWithModel:
            model_id = "claude-opus-4-20250514"
            thinking_mode = False

        config = ConfigWithModel()
        result = resolve_model_id(config)

        assert result == "claude-opus-4-20250514"

    def test_default_model_with_thinking(self):
        """Should append :thinking suffix when thinking_mode is True"""

        class ConfigWithThinking:
            thinking_mode = True

        config = ConfigWithThinking()
        result = resolve_model_id(config)

        assert result == "claude-sonnet-4-5-20250929:thinking"

    def test_custom_model_with_thinking(self):
        """Should append :thinking suffix to custom model"""

        class ConfigWithBoth:
            model_id = "claude-opus-4-20250514"
            thinking_mode = True

        config = ConfigWithBoth()
        result = resolve_model_id(config)

        assert result == "claude-opus-4-20250514:thinking"

    def test_model_already_has_thinking_suffix(self):
        """Should not double-add :thinking suffix if already present"""

        class ConfigWithSuffix:
            model_id = "claude-opus-4-20250514:thinking"
            thinking_mode = True

        config = ConfigWithSuffix()
        result = resolve_model_id(config)

        # Should not become "...:thinking:thinking"
        assert result == "claude-opus-4-20250514:thinking"

    def test_thinking_mode_false_explicit(self):
        """Should not add suffix when thinking_mode explicitly False"""

        class ConfigNoThinking:
            model_id = "claude-opus-4-20250514"
            thinking_mode = False

        config = ConfigNoThinking()
        result = resolve_model_id(config)

        assert result == "claude-opus-4-20250514"


class TestClaudeAgentClientAdapter:
    """Test ClaudeAgentClient adapter wrapping SDK client"""

    @pytest.mark.asyncio
    async def test_connect_delegates_to_sdk(self):
        """Should delegate connect() to wrapped SDK client"""
        mock_sdk = AsyncMock()
        adapter = ClaudeAgentClient(sdk_client=mock_sdk)

        await adapter.connect()

        mock_sdk.connect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_disconnect_delegates_to_sdk(self):
        """Should delegate disconnect() to wrapped SDK client"""
        mock_sdk = AsyncMock()
        adapter = ClaudeAgentClient(sdk_client=mock_sdk)

        await adapter.disconnect()

        mock_sdk.disconnect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_query_delegates_to_sdk(self):
        """Should delegate query() with all parameters"""
        mock_sdk = AsyncMock()
        adapter = ClaudeAgentClient(sdk_client=mock_sdk)

        await adapter.query("Test prompt", session_id="test-session")

        mock_sdk.query.assert_awaited_once_with(
            "Test prompt", session_id="test-session"
        )

    @pytest.mark.asyncio
    async def test_query_default_session_id(self):
        """Should use default session_id when not specified"""
        mock_sdk = AsyncMock()
        adapter = ClaudeAgentClient(sdk_client=mock_sdk)

        await adapter.query("Test prompt")

        mock_sdk.query.assert_awaited_once_with(
            "Test prompt", session_id="default"
        )

    @pytest.mark.asyncio
    async def test_receive_response_yields_messages(self):
        """Should yield all messages from SDK receive_response()"""

        # Create async generator for mock
        async def mock_generator():
            yield {"type": "message", "content": "First"}
            yield {"type": "message", "content": "Second"}
            yield {"type": "message", "content": "Third"}

        mock_sdk = MagicMock()
        mock_sdk.receive_response = mock_generator
        adapter = ClaudeAgentClient(sdk_client=mock_sdk)

        messages = []
        async for message in adapter.receive_response():
            messages.append(message)

        assert len(messages) == 3
        assert messages[0]["content"] == "First"
        assert messages[1]["content"] == "Second"
        assert messages[2]["content"] == "Third"

    @pytest.mark.asyncio
    async def test_receive_response_empty_stream(self):
        """Should handle empty message stream gracefully"""

        async def empty_generator():
            # Yield nothing
            return
            yield  # Make it a generator

        mock_sdk = MagicMock()
        mock_sdk.receive_response = empty_generator
        adapter = ClaudeAgentClient(sdk_client=mock_sdk)

        messages = []
        async for message in adapter.receive_response():
            messages.append(message)

        assert messages == []

    @pytest.mark.asyncio
    async def test_interrupt_delegates_to_sdk(self):
        """Should delegate interrupt() to wrapped SDK client"""
        mock_sdk = AsyncMock()
        adapter = ClaudeAgentClient(sdk_client=mock_sdk)

        await adapter.interrupt()

        mock_sdk.interrupt.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_server_info_returns_dict(self):
        """Should return server info dict from SDK"""
        mock_sdk = AsyncMock()
        mock_sdk.get_server_info.return_value = {
            "version": "1.0.0",
            "capabilities": ["streaming", "interruption"],
        }
        adapter = ClaudeAgentClient(sdk_client=mock_sdk)

        result = await adapter.get_server_info()

        assert result == {
            "version": "1.0.0",
            "capabilities": ["streaming", "interruption"],
        }
        mock_sdk.get_server_info.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_server_info_returns_none(self):
        """Should handle None return from get_server_info()"""
        mock_sdk = AsyncMock()
        mock_sdk.get_server_info.return_value = None
        adapter = ClaudeAgentClient(sdk_client=mock_sdk)

        result = await adapter.get_server_info()

        assert result is None
        mock_sdk.get_server_info.assert_awaited_once()


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_resolve_model_id_with_none_attributes(self):
        """Should handle config with None values (returns None as-is)"""

        class ConfigWithNone:
            model_id = None
            thinking_mode = None

        config = ConfigWithNone()
        result = resolve_model_id(config)

        # getattr returns None when attribute exists but is None
        # This documents actual behavior (might be edge case to handle)
        assert result is None

    def test_resolve_model_id_empty_string(self):
        """Should handle empty string model_id (appends :thinking to empty)"""

        class ConfigEmpty:
            model_id = ""
            thinking_mode = True

        config = ConfigEmpty()
        result = resolve_model_id(config)

        # getattr returns "" when attribute exists but is empty
        # thinking_mode adds :thinking suffix
        # This documents actual behavior (edge case)
        assert result == ":thinking"

    @pytest.mark.asyncio
    async def test_adapter_query_with_complex_prompt(self):
        """Should handle complex prompt objects (not just strings)"""
        mock_sdk = AsyncMock()
        adapter = ClaudeAgentClient(sdk_client=mock_sdk)

        complex_prompt = {
            "text": "Analyze this",
            "context": {"file": "data.json"},
            "tools": ["ReadFile", "WriteFile"],
        }

        await adapter.query(complex_prompt, session_id="complex-session")

        # Should pass through the complex object
        mock_sdk.query.assert_awaited_once_with(
            complex_prompt, session_id="complex-session"
        )


class TestBuildClaudeAgentOptions:
    """Test build_claude_agent_options() function"""

    def test_build_options_minimal_config(self):
        """Should build options with minimal config (only model)"""

        class MinimalConfig:
            pass

        with patch("bassi.shared.sdk_loader.ClaudeAgentOptions") as mock_opts:
            mock_opts.return_value = MagicMock()

            config = MinimalConfig()
            result = build_claude_agent_options(config)

            # Should call constructor with default model and None for most fields
            mock_opts.assert_called_once()
            call_kwargs = mock_opts.call_args.kwargs
            assert call_kwargs["model"] == "claude-sonnet-4-5-20250929"
            assert call_kwargs["allowed_tools"] is None
            assert call_kwargs["system_prompt"] is None
            assert call_kwargs["permission_mode"] is None
            assert call_kwargs["mcp_servers"] is None
            assert call_kwargs["cwd"] is None
            assert call_kwargs["can_use_tool"] is None
            assert call_kwargs["hooks"] is None
            assert call_kwargs["setting_sources"] is None
            assert call_kwargs["include_partial_messages"] is False
            assert call_kwargs["max_thinking_tokens"] == 10000

    def test_build_options_with_all_fields(self):
        """Should pass through all config fields to options"""

        class FullConfig:
            model_id = "claude-opus-4-20250514"
            thinking_mode = True
            allowed_tools = ["ReadFile", "WriteFile"]
            system_prompt = "You are a helpful assistant"
            permission_mode = "acceptEdits"
            mcp_servers = {"bash": {}, "web_search": {}}
            cwd = "/workspace"
            can_use_tool = lambda x: True
            hooks = {"pre": lambda: None}
            setting_sources = ["user", "system"]
            include_partial_messages = True
            max_thinking_tokens = 20000

        with patch("bassi.shared.sdk_loader.ClaudeAgentOptions") as mock_opts:
            mock_opts.return_value = MagicMock()

            config = FullConfig()
            result = build_claude_agent_options(config)

            call_kwargs = mock_opts.call_args.kwargs
            assert call_kwargs["model"] == "claude-opus-4-20250514:thinking"
            assert call_kwargs["allowed_tools"] == ["ReadFile", "WriteFile"]
            assert call_kwargs["system_prompt"] == "You are a helpful assistant"
            assert call_kwargs["permission_mode"] == "acceptEdits"
            assert call_kwargs["mcp_servers"] == {"bash": {}, "web_search": {}}
            assert call_kwargs["cwd"] == "/workspace"
            assert call_kwargs["can_use_tool"] is not None
            assert call_kwargs["hooks"] is not None
            assert call_kwargs["setting_sources"] == ["user", "system"]
            assert call_kwargs["include_partial_messages"] is True
            assert call_kwargs["max_thinking_tokens"] == 20000

    def test_build_options_with_resume_session_id(self):
        """Should set options.resume when resume_session_id present"""

        class ConfigWithResume:
            resume_session_id = "session-abc-123"

        with patch("bassi.shared.sdk_loader.ClaudeAgentOptions") as mock_opts:
            mock_instance = MagicMock()
            mock_opts.return_value = mock_instance

            config = ConfigWithResume()
            result = build_claude_agent_options(config)

            # Should set resume attribute after construction
            assert mock_instance.resume == "session-abc-123"

    def test_build_options_without_resume_session_id(self):
        """Should not set resume when resume_session_id is None"""

        class ConfigNoResume:
            resume_session_id = None

        with patch("bassi.shared.sdk_loader.ClaudeAgentOptions") as mock_opts:
            mock_instance = MagicMock()
            # Remove resume attribute to verify it's not set
            del mock_instance.resume
            mock_opts.return_value = mock_instance

            config = ConfigNoResume()
            result = build_claude_agent_options(config)

            # Should not have resume attribute set
            assert not hasattr(mock_instance, "resume")


class TestDefaultClaudeClientFactory:
    """Test default_claude_client_factory() function"""

    def test_factory_creates_wrapped_client(self):
        """Should create ClaudeAgentClient wrapping SDK client"""

        class TestConfig:
            model_id = "test-model"

        with patch(
            "bassi.shared.sdk_loader.ClaudeSDKClient"
        ) as mock_sdk_class, patch(
            "bassi.shared.agent_protocol.build_claude_agent_options"
        ) as mock_build:

            mock_options = MagicMock()
            mock_build.return_value = mock_options

            mock_sdk_instance = MagicMock()
            mock_sdk_class.return_value = mock_sdk_instance

            config = TestConfig()
            result = default_claude_client_factory(config)

            # Should build options from config
            mock_build.assert_called_once_with(config)

            # Should create SDK client with options
            mock_sdk_class.assert_called_once_with(options=mock_options)

            # Should return wrapped client
            assert isinstance(result, ClaudeAgentClient)
            assert result.sdk_client == mock_sdk_instance
