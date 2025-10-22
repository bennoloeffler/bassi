"""
Comprehensive tests for all bassi use cases
"""

import json
import os
from unittest.mock import AsyncMock, Mock

import pytest

from bassi.agent import BassiAgent


class TestUseCase1FirstTimeStartup:
    """UC-1: First-time startup"""

    def test_fresh_startup_no_context_file(self, tmp_path, monkeypatch):
        """Test agent starts fresh when no context file exists"""
        # Change to temp directory
        monkeypatch.chdir(tmp_path)

        # Verify no context file exists
        context_file = tmp_path / ".bassi_context.json"
        assert not context_file.exists()

        # Create agent without resume_session_id
        agent = BassiAgent(resume_session_id=None)

        # Verify agent initialized with no session_id
        assert agent.session_id is None
        assert agent.client is None  # Client not created yet


class TestUseCase2ResumePreviousSession:
    """UC-2: Resume previous session"""

    def test_load_context_from_file(self, tmp_path, monkeypatch):
        """Test loading session_id from context file"""
        # Change to temp directory
        monkeypatch.chdir(tmp_path)

        # Create context file
        context_file = tmp_path / ".bassi_context.json"
        test_session_id = "test-session-123"
        context_data = {
            "session_id": test_session_id,
            "timestamp": 1705852800.0,
            "last_updated": "2025-01-21 14:30:00",
        }
        context_file.write_text(json.dumps(context_data))

        # Create agent
        agent = BassiAgent()

        # Load context
        loaded_context = agent.load_context()

        assert loaded_context is not None
        assert loaded_context["session_id"] == test_session_id

    def test_resume_with_session_id(self, tmp_path, monkeypatch):
        """Test agent initialized with resume_session_id"""
        monkeypatch.chdir(tmp_path)

        test_session_id = "test-session-456"

        # Create agent with resume_session_id
        agent = BassiAgent(resume_session_id=test_session_id)

        # Verify session_id set
        assert agent.session_id == test_session_id

        # Verify resume passed to options
        assert agent.options.resume == test_session_id


class TestUseCase3BasicConversation:
    """UC-3: Basic conversation"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_chat_streaming_response(self):
        """Test basic conversation with streaming response"""
        # This test requires ANTHROPIC_API_KEY
        if not os.getenv("ANTHROPIC_API_KEY"):
            pytest.skip("ANTHROPIC_API_KEY not set")

        agent = BassiAgent()

        message_count = 0
        has_result_message = False

        async for msg in agent.chat("Say 'test' and nothing else"):
            message_count += 1
            msg_type = type(msg).__name__

            # Check ResultMessage has session_id
            if msg_type == "ResultMessage":
                has_result_message = True
                assert agent.session_id is not None
                assert len(agent.session_id) > 0

        # Verify messages received
        assert message_count > 0
        # Verify ResultMessage received (indicates successful completion)
        assert has_result_message

    def test_save_context_after_chat(self, tmp_path, monkeypatch):
        """Test context saved after chat"""
        monkeypatch.chdir(tmp_path)

        agent = BassiAgent()
        agent.session_id = "test-session-789"

        # Save context
        agent.save_context()

        # Verify file created
        context_file = tmp_path / ".bassi_context.json"
        assert context_file.exists()

        # Verify content
        data = json.loads(context_file.read_text())
        assert data["session_id"] == "test-session-789"
        assert "timestamp" in data
        assert "last_updated" in data


class TestUseCase6ContextCompaction:
    """UC-6: Context compaction"""

    def test_context_info_calculation(self):
        """Test context size calculation"""
        agent = BassiAgent()

        # Set token counts
        agent.total_input_tokens = 10000
        agent.total_cache_creation_tokens = 50000
        agent.total_cache_read_tokens = 90000

        # Get context info
        ctx_info = agent.get_context_info()

        # Expected: 10000 + 50000 + 90000 = 150000
        assert ctx_info["current_size"] == 150000
        assert ctx_info["window_size"] == 200000
        assert ctx_info["compaction_threshold"] == 150000
        assert ctx_info["will_compact_soon"] is True  # At threshold
        assert ctx_info["percentage_used"] == 75.0

    def test_compaction_threshold_not_reached(self):
        """Test context below compaction threshold"""
        agent = BassiAgent()

        # Set lower token counts
        agent.total_input_tokens = 50000
        agent.total_cache_creation_tokens = 30000
        agent.total_cache_read_tokens = 20000

        ctx_info = agent.get_context_info()

        # Expected: 50000 + 30000 + 20000 = 100000
        assert ctx_info["current_size"] == 100000
        assert ctx_info["will_compact_soon"] is False  # Below threshold
        assert ctx_info["percentage_used"] == 50.0


class TestUseCase7ToggleVerboseMode:
    """UC-7: Toggle verbose mode"""

    def test_toggle_verbose_on_to_off(self):
        """Test toggling verbose from ON to OFF"""
        agent = BassiAgent()

        # Default is ON
        assert agent.verbose is True

        # Toggle to OFF
        result = agent.toggle_verbose()
        assert result is False
        assert agent.verbose is False

    def test_toggle_verbose_off_to_on(self):
        """Test toggling verbose from OFF to ON"""
        agent = BassiAgent()
        agent.verbose = False

        # Toggle to ON
        result = agent.toggle_verbose()
        assert result is True
        assert agent.verbose is True

    def test_set_verbose_explicit(self):
        """Test setting verbose mode explicitly"""
        agent = BassiAgent()

        # Set to False
        agent.set_verbose(False)
        assert agent.verbose is False

        # Set to True
        agent.set_verbose(True)
        assert agent.verbose is True


class TestUseCase8ResetConversation:
    """UC-8: Reset conversation"""

    @pytest.mark.asyncio
    async def test_reset_clears_client(self):
        """Test reset clears client"""
        agent = BassiAgent()

        # Mock client
        mock_client = AsyncMock()
        agent.client = mock_client

        # Reset
        await agent.reset()

        # Verify client cleared
        assert agent.client is None

        # Verify __aexit__ called
        mock_client.__aexit__.assert_called_once()


class TestUseCase13InterruptAgent:
    """UC-13: Interrupt agent"""

    @pytest.mark.asyncio
    async def test_interrupt_calls_client_interrupt(self):
        """Test interrupt calls client.interrupt()"""
        agent = BassiAgent()

        # Mock client
        mock_client = AsyncMock()
        agent.client = mock_client

        # Mock status callback
        status_messages = []

        def capture_status(msg):
            status_messages.append(msg)

        agent.status_callback = capture_status

        # Interrupt
        await agent.interrupt()

        # Verify client.interrupt called
        mock_client.interrupt.assert_called_once()

        # Verify status callback called
        assert "Interrupted" in status_messages[-1]

    @pytest.mark.asyncio
    async def test_interrupt_no_client(self):
        """Test interrupt when no client exists"""
        agent = BassiAgent()
        agent.client = None

        # Should not raise exception
        await agent.interrupt()


class TestStatusCallback:
    """Test status callback functionality"""

    def test_status_callback_on_assistant_message(self):
        """Test status callback updates on AssistantMessage"""
        status_messages = []

        def capture_status(msg):
            status_messages.append(msg)

        agent = BassiAgent(status_callback=capture_status)

        # Create mock AssistantMessage
        msg = Mock()
        msg.__class__.__name__ = "AssistantMessage"

        # Update status
        agent._update_status_from_message(msg)

        # Verify callback called
        assert len(status_messages) > 0
        assert "Responding" in status_messages[-1]

    def test_status_callback_on_system_message_compaction(self):
        """Test status callback on compaction SystemMessage"""
        status_messages = []

        def capture_status(msg):
            status_messages.append(msg)

        agent = BassiAgent(status_callback=capture_status)

        # Create mock SystemMessage with compaction
        msg = Mock()
        msg.__class__.__name__ = "SystemMessage"
        msg.subtype = "compaction_start"

        # Update status
        agent._update_status_from_message(msg)

        # Verify callback called with compaction message
        assert any("compact" in m.lower() for m in status_messages)


class TestStreamingState:
    """Test streaming state management"""

    def test_streaming_state_initialization(self):
        """Test streaming state initialized correctly"""
        agent = BassiAgent()

        assert agent._streaming_response is False
        assert agent._last_text_length == 0
        assert agent._accumulated_text == ""

    def test_streaming_state_reset_on_result_message(self):
        """Test streaming state reset when ResultMessage received"""
        agent = BassiAgent()

        # Set streaming state as if streaming
        agent._streaming_response = True
        agent._accumulated_text = "test response"
        agent._last_text_length = 13

        # Create mock ResultMessage
        msg = Mock()
        msg.__class__.__name__ = "ResultMessage"
        msg.duration_ms = 1000
        msg.total_cost_usd = 0.01
        msg.usage = {}

        # Display message (which resets streaming state)
        agent._display_message(msg)

        # Verify state reset
        assert agent._streaming_response is False
        assert agent._accumulated_text == ""
        assert agent._last_text_length == 0


class TestTokenTracking:
    """Test token tracking functionality"""

    def test_token_tracking_initialization(self):
        """Test token counters initialized to zero"""
        agent = BassiAgent()

        assert agent.total_input_tokens == 0
        assert agent.total_output_tokens == 0
        assert agent.total_cache_creation_tokens == 0
        assert agent.total_cache_read_tokens == 0
        assert agent.total_cost_usd == 0.0

    def test_token_tracking_cumulative(self):
        """Test token tracking is cumulative"""
        agent = BassiAgent()

        # Simulate first ResultMessage
        agent.total_input_tokens += 100
        agent.total_output_tokens += 50
        agent.total_cost_usd += 0.005

        # Simulate second ResultMessage
        agent.total_input_tokens += 200
        agent.total_output_tokens += 75
        agent.total_cost_usd += 0.010

        # Verify cumulative totals
        assert agent.total_input_tokens == 300
        assert agent.total_output_tokens == 125
        assert agent.total_cost_usd == 0.015


class TestSystemPrompt:
    """Test system prompt configuration"""

    def test_system_prompt_includes_mcp_tools(self):
        """Test system prompt mentions mcp__ tools"""
        prompt = BassiAgent.SYSTEM_PROMPT

        assert "mcp__bash__execute" in prompt
        assert "mcp__web__search" in prompt

    def test_system_prompt_includes_instructions(self):
        """Test system prompt includes key instructions"""
        prompt = BassiAgent.SYSTEM_PROMPT

        assert "bassi" in prompt.lower()
        assert "personal assistant" in prompt.lower()
        assert "bash command" in prompt.lower()
        assert "web search" in prompt.lower()
