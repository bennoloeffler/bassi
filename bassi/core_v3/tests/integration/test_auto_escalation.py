"""Integration tests for auto-escalation feature.

Tests the integration of:
1. Tool error detection from tool_end events
2. ModelEscalationTracker on_failure/on_success calls
3. _handle_model_escalation method execution
4. WebSocket notifications to user
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from bassi.core_v3.models.browser_session import BrowserSession
from bassi.core_v3.services.model_service import (
    ModelEscalationTracker,
    get_model_id,
)


class TestModelEscalationTrackerIntegration:
    """Test ModelEscalationTracker in context of browser session."""

    def test_tracker_attached_to_browser_session(self):
        """Browser session should have model tracker attached."""
        tracker = ModelEscalationTracker(current_level=1, auto_escalate=True)
        browser_session = BrowserSession(
            browser_id="test-browser",
            websocket=MagicMock(),
            agent=MagicMock(),
            current_chat_id="test-chat",
            question_service=MagicMock(),
            workspace=MagicMock(),
            model_tracker=tracker,
        )

        assert browser_session.model_tracker is not None
        assert browser_session.model_tracker.current_level == 1
        assert browser_session.model_tracker.auto_escalate is True

    def test_tracker_escalation_returns_new_level(self):
        """Tracker should return new level when escalation triggers."""
        tracker = ModelEscalationTracker(current_level=1, auto_escalate=True)

        # First two failures return None
        assert tracker.on_failure() is None
        assert tracker.on_failure() is None

        # Third failure triggers escalation
        new_level = tracker.on_failure()
        assert new_level == 2
        assert tracker.current_level == 2
        assert tracker.consecutive_failures == 0

    def test_tracker_success_resets_counter(self):
        """Success should reset failure counter."""
        tracker = ModelEscalationTracker(current_level=1)

        tracker.on_failure()
        tracker.on_failure()
        assert tracker.consecutive_failures == 2

        tracker.on_success()
        assert tracker.consecutive_failures == 0
        assert tracker.current_level == 1  # Level unchanged


class TestHandleModelEscalation:
    """Test _handle_model_escalation method."""

    @pytest.fixture
    def mock_websocket(self):
        """Create mock WebSocket."""
        ws = AsyncMock()
        ws.send_json = AsyncMock()
        return ws

    @pytest.fixture
    def mock_session(self):
        """Create mock agent session."""
        session = AsyncMock()
        session.set_model = AsyncMock()
        return session

    @pytest.fixture
    def mock_browser_session(self):
        """Create mock browser session with tracker."""
        tracker = ModelEscalationTracker(current_level=1)
        browser_session = MagicMock()
        browser_session.model_tracker = tracker
        return browser_session

    @pytest.mark.asyncio
    async def test_handle_model_escalation_changes_model(
        self, mock_websocket, mock_session, mock_browser_session
    ):
        """_handle_model_escalation should change model via SDK."""
        from bassi.core_v3.web_server_v3_old import WebUIServerV3

        # Create minimal server instance
        server = WebUIServerV3.__new__(WebUIServerV3)

        # Call the method
        new_level = 2
        await server._handle_model_escalation(
            mock_websocket, mock_session, mock_browser_session, new_level
        )

        # Verify model was changed
        expected_model_id = get_model_id(2)
        mock_session.set_model.assert_called_once_with(expected_model_id)

    @pytest.mark.asyncio
    async def test_handle_model_escalation_notifies_user(
        self, mock_websocket, mock_session, mock_browser_session
    ):
        """_handle_model_escalation should send WebSocket notifications."""
        from bassi.core_v3.web_server_v3_old import WebUIServerV3

        server = WebUIServerV3.__new__(WebUIServerV3)

        await server._handle_model_escalation(
            mock_websocket, mock_session, mock_browser_session, 2
        )

        # Should send at least 2 messages (model_escalated + status)
        assert mock_websocket.send_json.call_count == 2

        # Check first call is model_escalated event
        call_args = mock_websocket.send_json.call_args_list
        first_msg = call_args[0][0][0]  # First call, first positional arg
        assert first_msg["type"] == "model_escalated"
        assert first_msg["old_level"] == 1
        assert first_msg["new_level"] == 2
        assert first_msg["reason"] == "auto_escalation"

        # Check second call is status message
        second_msg = call_args[1][0][0]
        assert second_msg["type"] == "status"
        assert "Model upgraded" in second_msg["message"]

    @pytest.mark.asyncio
    async def test_handle_model_escalation_to_opus(
        self, mock_websocket, mock_session, mock_browser_session
    ):
        """Should escalate correctly to Opus (level 3)."""
        from bassi.core_v3.web_server_v3_old import WebUIServerV3

        server = WebUIServerV3.__new__(WebUIServerV3)
        mock_browser_session.model_tracker.current_level = 2

        await server._handle_model_escalation(
            mock_websocket, mock_session, mock_browser_session, 3
        )

        expected_model_id = get_model_id(3)
        mock_session.set_model.assert_called_once_with(expected_model_id)

        # Verify notification mentions Opus
        call_args = mock_websocket.send_json.call_args_list
        first_msg = call_args[0][0][0]
        assert "Opus" in first_msg["new_model_name"]

    @pytest.mark.asyncio
    async def test_handle_model_escalation_error_handling(
        self, mock_websocket, mock_session, mock_browser_session
    ):
        """Should handle errors gracefully and notify user."""
        from bassi.core_v3.web_server_v3_old import WebUIServerV3

        server = WebUIServerV3.__new__(WebUIServerV3)

        # Make set_model fail
        mock_session.set_model.side_effect = Exception("SDK error")

        # Should not raise
        await server._handle_model_escalation(
            mock_websocket, mock_session, mock_browser_session, 2
        )

        # Should send error notification
        call_args = mock_websocket.send_json.call_args_list
        last_msg = call_args[-1][0][0]
        assert last_msg["type"] == "error"
        assert "Failed to auto-escalate" in last_msg["message"]


class TestToolErrorDetection:
    """Test that tool errors trigger escalation tracking."""

    def test_tool_end_with_is_error_true(self):
        """tool_end event with is_error=True should trigger on_failure."""
        tracker = ModelEscalationTracker(current_level=1)

        # Simulate what happens in _process_message
        event = {"type": "tool_end", "id": "tool-1", "is_error": True}
        is_error = event.get("is_error", False)

        if is_error:
            result = tracker.on_failure()
        else:
            tracker.on_success()
            result = None

        assert tracker.consecutive_failures == 1
        assert result is None  # Not enough failures yet

    def test_tool_end_with_is_error_false(self):
        """tool_end event with is_error=False should trigger on_success."""
        tracker = ModelEscalationTracker(current_level=1)
        tracker.on_failure()  # Pre-existing failure

        event = {"type": "tool_end", "id": "tool-1", "is_error": False}
        is_error = event.get("is_error", False)

        if is_error:
            tracker.on_failure()
        else:
            tracker.on_success()

        assert tracker.consecutive_failures == 0  # Reset by success

    def test_tool_end_missing_is_error_defaults_to_false(self):
        """tool_end event without is_error should default to success."""
        tracker = ModelEscalationTracker(current_level=1)
        tracker.on_failure()  # Pre-existing failure

        event = {"type": "tool_end", "id": "tool-1"}  # No is_error field
        is_error = event.get("is_error", False)

        if is_error:
            tracker.on_failure()
        else:
            tracker.on_success()

        assert tracker.consecutive_failures == 0  # Reset (default = success)

    def test_three_tool_errors_trigger_escalation(self):
        """Three consecutive tool errors should trigger escalation."""
        tracker = ModelEscalationTracker(current_level=1)

        results = []
        for i in range(3):
            event = {"type": "tool_end", "id": f"tool-{i}", "is_error": True}
            is_error = event.get("is_error", False)
            if is_error:
                result = tracker.on_failure()
                results.append(result)

        # First two return None, third returns new level
        assert results == [None, None, 2]
        assert tracker.current_level == 2


class TestModelLogging:
    """Test model logging on agent activation."""

    def test_model_id_accessible_from_config(self):
        """Agent config should expose model_id."""
        from bassi.core_v3.agent_session import SessionConfig

        config = SessionConfig(model_id="claude-haiku-4-5-20251001")
        assert config.model_id == "claude-haiku-4-5-20251001"

    def test_get_model_id_returns_model_info(self):
        """get_model_id should return valid model string."""
        model_id = get_model_id(1)
        assert "haiku" in model_id.lower()

        model_id = get_model_id(2)
        assert "sonnet" in model_id.lower()

        model_id = get_model_id(3)
        assert "opus" in model_id.lower()
