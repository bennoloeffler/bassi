"""Unit tests for ErrorRecoveryService."""

import pytest

from bassi.core_v3.services.error_recovery_service import (
    ErrorCategory,
    ErrorRecoveryService,
    get_error_recovery_service,
)


class TestErrorCategorization:
    """Tests for error categorization."""

    def test_buffer_overflow_categorization(self):
        """Test that buffer overflow errors are correctly categorized."""
        service = ErrorRecoveryService()

        # Exact error from Claude SDK
        error_msg = (
            "Failed to decode JSON: JSON message exceeded maximum buffer size "
            "of 1048576 bytes..."
        )
        category = service.categorize_error(error_msg)
        assert (
            category == ErrorCategory.BUFFER_OVERFLOW
        ), f"Expected BUFFER_OVERFLOW, got {category}"

    def test_buffer_overflow_variations(self):
        """Test various buffer overflow error messages."""
        service = ErrorRecoveryService()

        test_cases = [
            "exceeded maximum buffer size",
            "Response too large for processing",
            "Payload too large",
            "Message size exceeded",
            "Content length exceeded the limit",
            "JSON message exceeded maximum buffer",
        ]

        for error_msg in test_cases:
            category = service.categorize_error(error_msg)
            assert (
                category == ErrorCategory.BUFFER_OVERFLOW
            ), f"Failed for: {error_msg}"

    def test_mcp_tool_failure_categorization(self):
        """Test MCP tool failure errors are categorized."""
        service = ErrorRecoveryService()

        test_cases = [
            "MCP server error occurred",
            "Tool execution failed",
            "Server disconnected unexpectedly",
            "Connection was closed unexpectedly",
        ]

        for error_msg in test_cases:
            category = service.categorize_error(error_msg)
            assert (
                category == ErrorCategory.MCP_TOOL_FAILURE
            ), f"Failed for: {error_msg}"

    def test_timeout_categorization(self):
        """Test timeout errors are categorized."""
        service = ErrorRecoveryService()

        test_cases = [
            "Request timed out",
            "Operation timed out",
            "Timeout waiting for response",
            "Deadline exceeded",
        ]

        for error_msg in test_cases:
            category = service.categorize_error(error_msg)
            assert category == ErrorCategory.TIMEOUT, f"Failed for: {error_msg}"

    def test_unknown_error_categorization(self):
        """Test that unknown errors are categorized as UNKNOWN."""
        service = ErrorRecoveryService()

        category = service.categorize_error("Something totally unexpected happened")
        assert category == ErrorCategory.UNKNOWN


class TestErrorAnalysis:
    """Tests for error analysis."""

    def test_analyze_error_returns_context(self):
        """Test that analyze_error returns proper ErrorContext."""
        service = ErrorRecoveryService()

        # Set tool info before analysis
        service.set_last_tool_info("mcp__playwright__screenshot", {"url": "http://example.com"})

        error = Exception("Failed to decode JSON: JSON message exceeded maximum buffer size")
        context = service.analyze_error(error)

        assert context.category == ErrorCategory.BUFFER_OVERFLOW
        assert context.tool_name == "mcp__playwright__screenshot"
        assert context.tool_params == {"url": "http://example.com"}
        assert context.original_error == str(error)
        assert context.suggestions is not None
        assert len(context.suggestions) > 0

    def test_analyze_error_with_explicit_tool_info(self):
        """Test that explicit tool info overrides tracked info."""
        service = ErrorRecoveryService()

        # Set tracked info
        service.set_last_tool_info("tool_a", {"param": "a"})

        error = Exception("Something failed")
        context = service.analyze_error(
            error, tool_name="tool_b", tool_params={"param": "b"}
        )

        # Explicit info should be used
        assert context.tool_name == "tool_b"
        assert context.tool_params == {"param": "b"}


class TestRecoveryPromptGeneration:
    """Tests for recovery prompt generation."""

    def test_generate_recovery_prompt_includes_error_info(self):
        """Test that recovery prompt includes error details."""
        service = ErrorRecoveryService()
        service.set_last_tool_info("mcp__playwright__screenshot", {"fullPage": True})

        error = Exception("Response too large for buffer")
        context = service.analyze_error(error)
        prompt = service.generate_recovery_prompt(context)

        # Should include key information
        assert "Buffer Overflow" in prompt
        assert "Response too large for buffer" in prompt
        assert "mcp__playwright__screenshot" in prompt
        assert "Suggested Recovery Actions" in prompt

    def test_recovery_prompt_truncates_large_params(self):
        """Test that large tool params are truncated."""
        service = ErrorRecoveryService()

        # Create very large params
        large_params = {"data": "x" * 1000}
        service.set_last_tool_info("some_tool", large_params)

        error = Exception("Error occurred")
        context = service.analyze_error(error)
        prompt = service.generate_recovery_prompt(context)

        # Should be truncated
        assert "truncated" in prompt

    def test_recovery_prompt_includes_required_action(self):
        """Test that recovery prompt demands action, not just acknowledgment."""
        service = ErrorRecoveryService()

        error = Exception("Response too large for buffer")
        context = service.analyze_error(error)
        prompt = service.generate_recovery_prompt(context)

        # Should include action-oriented language
        assert "CONTINUE YOUR TASK" in prompt
        assert "alternative approach" in prompt.lower()
        assert "immediately" in prompt.lower()
        # Should tell agent to use tools
        assert "tools" in prompt.lower()

    def test_recovery_prompt_includes_original_task(self):
        """Test that recovery prompt includes the original task when provided."""
        service = ErrorRecoveryService()

        error = Exception("Response too large for buffer")
        original_task = "Take a screenshot of the webpage and describe what you see"
        context = service.analyze_error(error, original_task=original_task)
        prompt = service.generate_recovery_prompt(context)

        # Should include the original task prominently
        assert "YOUR CURRENT TASK" in prompt
        assert original_task in prompt
        # Original task should come before error details
        task_pos = prompt.find(original_task)
        error_pos = prompt.find("ERROR ENCOUNTERED")
        assert task_pos < error_pos, "Original task should appear before error details"

    def test_buffer_overflow_has_specific_instructions(self):
        """Test that buffer overflow errors get specific recovery instructions."""
        service = ErrorRecoveryService()

        error = Exception("Response too large for buffer")
        context = service.analyze_error(error)
        prompt = service.generate_recovery_prompt(context)

        # Should have buffer-specific instructions
        assert "smaller area" in prompt.lower() or "smaller" in prompt.lower()
        assert "screenshot" in prompt.lower() or "file" in prompt.lower()

    def test_mcp_tool_failure_has_specific_instructions(self):
        """Test that MCP tool failures get specific recovery instructions."""
        service = ErrorRecoveryService()

        error = Exception("MCP server error occurred")
        context = service.analyze_error(error)
        prompt = service.generate_recovery_prompt(context)

        # Should have MCP-specific instructions
        assert "retry" in prompt.lower()
        assert "different tool" in prompt.lower() or "alternative" in prompt.lower()

    def test_timeout_has_specific_instructions(self):
        """Test that timeout errors get specific recovery instructions."""
        service = ErrorRecoveryService()

        error = Exception("Request timed out")
        context = service.analyze_error(error)
        prompt = service.generate_recovery_prompt(context)

        # Should have timeout-specific instructions
        assert "simpler" in prompt.lower() or "smaller steps" in prompt.lower()

    def test_action_instructions_for_all_categories(self):
        """Test that all error categories have action instructions."""
        service = ErrorRecoveryService()

        categories = [
            ErrorCategory.BUFFER_OVERFLOW,
            ErrorCategory.MCP_TOOL_FAILURE,
            ErrorCategory.FILE_CONSTRAINT,
            ErrorCategory.NETWORK_ERROR,
            ErrorCategory.TIMEOUT,
            ErrorCategory.RATE_LIMIT,
            ErrorCategory.PERMISSION_DENIED,
            ErrorCategory.VALIDATION_ERROR,
            ErrorCategory.UNKNOWN,
        ]

        for category in categories:
            instructions = service._get_action_instructions(category)
            assert len(instructions) > 0, f"No instructions for {category}"
            # All should end with an action
            assert any(
                "immediately" in line.lower() or "continue" in line.lower()
                for line in instructions
            ), f"No immediate action for {category}"


class TestShouldAttemptRecovery:
    """Tests for should_attempt_recovery."""

    def test_recoverable_errors(self):
        """Test that most errors are considered recoverable."""
        service = ErrorRecoveryService()

        recoverable_categories = [
            ErrorCategory.BUFFER_OVERFLOW,
            ErrorCategory.MCP_TOOL_FAILURE,
            ErrorCategory.FILE_CONSTRAINT,
            ErrorCategory.NETWORK_ERROR,
            ErrorCategory.TIMEOUT,
            ErrorCategory.UNKNOWN,
        ]

        for category in recoverable_categories:
            error = Exception("test error")
            context = service.analyze_error(error)
            context.category = category  # Override for testing
            assert service.should_attempt_recovery(
                context
            ), f"{category} should be recoverable"

    def test_sdk_error_not_recoverable(self):
        """Test that SDK errors are not recoverable."""
        service = ErrorRecoveryService()

        error = Exception("cancel scope error in anyio")
        context = service.analyze_error(error)

        # SDK errors should not be recoverable
        assert context.category == ErrorCategory.SDK_ERROR
        assert not service.should_attempt_recovery(context)


class TestGlobalInstance:
    """Tests for global singleton."""

    def test_get_error_recovery_service_returns_singleton(self):
        """Test that get_error_recovery_service returns same instance."""
        service1 = get_error_recovery_service()
        service2 = get_error_recovery_service()

        assert service1 is service2

    def test_tool_tracking_persists_across_calls(self):
        """Test that tool tracking persists in singleton."""
        service = get_error_recovery_service()
        service.set_last_tool_info("my_tool", {"arg": "value"})

        # Get singleton again
        same_service = get_error_recovery_service()

        error = Exception("test")
        context = same_service.analyze_error(error)

        assert context.tool_name == "my_tool"
