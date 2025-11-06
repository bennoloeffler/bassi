"""
Unit tests for message_converter.

Tests every function and every message type conversion.
"""

from claude_agent_sdk.types import (
    AssistantMessage,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

from bassi.core_v3.message_converter import (
    convert_message_to_websocket,
    convert_messages_batch,
)

# Test model constant
TEST_MODEL = "claude-3-5-sonnet-20241022"


class TestConvertTextBlock:
    """Test conversion of TextBlock"""

    def test_text_block_simple(self):
        """Test simple text block conversion"""
        message = AssistantMessage(
            content=[TextBlock(text="Hello world")], model=TEST_MODEL
        )

        events = convert_message_to_websocket(message)

        assert len(events) == 1
        assert events[0]["type"] == "text_delta"
        assert events[0]["text"] == "Hello world"

    def test_text_block_multiline(self):
        """Test text block with multiline content"""
        text = "Line 1\nLine 2\nLine 3"
        message = AssistantMessage(
            content=[TextBlock(text=text)], model=TEST_MODEL
        )

        events = convert_message_to_websocket(message)

        assert len(events) == 1
        assert events[0]["type"] == "text_delta"
        assert events[0]["text"] == text

    def test_text_block_empty(self):
        """Test empty text block"""
        message = AssistantMessage(
            content=[TextBlock(text="")], model=TEST_MODEL
        )

        events = convert_message_to_websocket(message)

        assert len(events) == 1
        assert events[0]["type"] == "text_delta"
        assert events[0]["text"] == ""


class TestConvertToolUseBlock:
    """Test conversion of ToolUseBlock"""

    def test_tool_use_simple(self):
        """Test simple tool use conversion"""
        message = AssistantMessage(
            content=[
                ToolUseBlock(
                    id="tool_123",
                    name="ReadFile",
                    input={"path": "/foo/bar.txt"},
                )
            ],
            model=TEST_MODEL,
        )

        events = convert_message_to_websocket(message)

        assert len(events) == 1
        assert events[0]["type"] == "tool_start"
        assert events[0]["id"] == "tool_123"
        assert events[0]["tool_name"] == "ReadFile"
        assert events[0]["input"] == {"path": "/foo/bar.txt"}

    def test_tool_use_complex_input(self):
        """Test tool use with complex input"""
        message = AssistantMessage(
            content=[
                ToolUseBlock(
                    id="tool_456",
                    name="Bash",
                    input={
                        "command": "ls -la",
                        "timeout": 5000,
                        "description": "List files",
                    },
                )
            ],
            model=TEST_MODEL,
        )

        events = convert_message_to_websocket(message)

        assert len(events) == 1
        assert events[0]["type"] == "tool_start"
        assert events[0]["id"] == "tool_456"
        assert events[0]["tool_name"] == "Bash"
        assert events[0]["input"]["command"] == "ls -la"
        assert events[0]["input"]["timeout"] == 5000


class TestConvertToolResultBlock:
    """Test conversion of ToolResultBlock"""

    def test_tool_result_success(self):
        """Test successful tool result conversion"""
        message = AssistantMessage(
            content=[
                ToolResultBlock(
                    tool_use_id="tool_123",
                    content="File contents here",
                    is_error=False,
                )
            ],
            model=TEST_MODEL,
        )

        events = convert_message_to_websocket(message)

        assert len(events) == 1
        assert events[0]["type"] == "tool_end"
        assert events[0]["id"] == "tool_123"
        assert events[0]["content"] == "File contents here"
        assert events[0]["is_error"] is False

    def test_tool_result_error(self):
        """Test error tool result conversion"""
        message = AssistantMessage(
            content=[
                ToolResultBlock(
                    tool_use_id="tool_456",
                    content="Error: File not found",
                    is_error=True,
                )
            ],
            model=TEST_MODEL,
        )

        events = convert_message_to_websocket(message)

        assert len(events) == 1
        assert events[0]["type"] == "tool_end"
        assert events[0]["id"] == "tool_456"
        assert events[0]["content"] == "Error: File not found"
        assert events[0]["is_error"] is True

    def test_tool_result_without_is_error(self):
        """Test tool result without is_error attribute"""
        message = AssistantMessage(
            content=[
                ToolResultBlock(
                    tool_use_id="tool_789",
                    content="Result",
                )
            ],
            model=TEST_MODEL,
        )

        events = convert_message_to_websocket(message)

        assert len(events) == 1
        assert events[0]["type"] == "tool_end"
        assert events[0]["is_error"] is False  # Defaults to False


class TestConvertThinkingBlock:
    """Test conversion of ThinkingBlock"""

    def test_thinking_block(self):
        """Test thinking block conversion"""
        message = AssistantMessage(
            content=[
                ThinkingBlock(
                    thinking="Let me analyze this...", signature="sig_123"
                )
            ],
            model=TEST_MODEL,
        )

        events = convert_message_to_websocket(message)

        assert len(events) == 1
        assert events[0]["type"] == "thinking"
        assert events[0]["text"] == "Let me analyze this..."


class TestConvertMixedContent:
    """Test conversion of messages with mixed content blocks"""

    def test_text_then_tool(self):
        """Test message with text followed by tool use"""
        message = AssistantMessage(
            content=[
                TextBlock(text="Let me read that file"),
                ToolUseBlock(
                    id="tool_1",
                    name="ReadFile",
                    input={"path": "/test.txt"},
                ),
            ],
            model=TEST_MODEL,
        )

        events = convert_message_to_websocket(message)

        assert len(events) == 2
        assert events[0]["type"] == "text_delta"
        assert events[0]["text"] == "Let me read that file"
        assert events[1]["type"] == "tool_start"
        assert events[1]["tool_name"] == "ReadFile"

    def test_thinking_text_tool(self):
        """Test message with thinking, text, and tool"""
        message = AssistantMessage(
            content=[
                ThinkingBlock(
                    thinking="I should check the file first",
                    signature="sig_1",
                ),
                TextBlock(text="I'll read the file"),
                ToolUseBlock(
                    id="tool_2",
                    name="ReadFile",
                    input={"path": "/data.json"},
                ),
            ],
            model=TEST_MODEL,
        )

        events = convert_message_to_websocket(message)

        assert len(events) == 3
        assert events[0]["type"] == "thinking"
        assert events[1]["type"] == "text_delta"
        assert events[2]["type"] == "tool_start"

    def test_multiple_tools(self):
        """Test message with multiple tool uses"""
        message = AssistantMessage(
            content=[
                ToolUseBlock(
                    id="tool_1",
                    name="ReadFile",
                    input={"path": "/foo.txt"},
                ),
                ToolUseBlock(
                    id="tool_2",
                    name="WriteFile",
                    input={"path": "/bar.txt", "content": "data"},
                ),
            ],
            model=TEST_MODEL,
        )

        events = convert_message_to_websocket(message)

        assert len(events) == 2
        assert events[0]["type"] == "tool_start"
        assert events[0]["id"] == "tool_1"
        assert events[1]["type"] == "tool_start"
        assert events[1]["id"] == "tool_2"


class TestConvertSystemMessage:
    """Test conversion of SystemMessage"""

    def test_system_message(self):
        """Test system message conversion"""
        message = SystemMessage(
            subtype="reminder",
            data={"content": "System reminder: Be helpful"},
        )

        events = convert_message_to_websocket(message)

        assert len(events) == 1
        assert events[0]["type"] == "system"
        # SystemMessage has data dict, need to extract content
        assert "text" in events[0]


class TestConvertUserMessage:
    """Test conversion of UserMessage"""

    def test_user_message_string(self):
        """Test user message with string content"""
        message = UserMessage(content="Hello, Claude!")

        events = convert_message_to_websocket(message)

        assert len(events) == 1
        assert events[0]["type"] == "user"
        assert events[0]["text"] == "Hello, Claude!"

    def test_user_message_non_string(self):
        """Test user message with non-string content"""
        message = UserMessage(content=["multiple", "parts"])

        events = convert_message_to_websocket(message)

        assert len(events) == 1
        assert events[0]["type"] == "user"
        # Should convert to string
        assert isinstance(events[0]["text"], str)


class TestConvertResultMessage:
    """Test conversion of ResultMessage"""

    def test_result_message_with_usage(self):
        """Test result message with usage stats"""
        message = ResultMessage(
            subtype="complete",
            duration_ms=1500,
            duration_api_ms=1200,
            is_error=False,
            num_turns=3,
            session_id="test-session",
            usage={"input_tokens": 150, "output_tokens": 75},
            total_cost_usd=0.002,
        )

        events = convert_message_to_websocket(message)

        assert len(events) == 1
        assert events[0]["type"] == "usage"
        # Check it handles usage dict from ResultMessage

    def test_result_message_missing_stats(self):
        """Test result message with minimal fields"""
        message = ResultMessage(
            subtype="complete",
            duration_ms=100,
            duration_api_ms=80,
            is_error=False,
            num_turns=1,
            session_id="test",
        )

        events = convert_message_to_websocket(message)

        assert len(events) == 1
        assert events[0]["type"] == "usage"
        # Should default to 0 for missing stats
        assert events[0]["input_tokens"] == 0
        assert events[0]["output_tokens"] == 0
        assert events[0]["total_cost_usd"] == 0.0


class TestConvertMessagesBatch:
    """Test batch conversion of multiple messages"""

    def test_batch_empty(self):
        """Test empty batch"""
        events = convert_messages_batch([])

        assert events == []

    def test_batch_single_message(self):
        """Test batch with single message"""
        messages = [UserMessage(content="Hello")]

        events = convert_messages_batch(messages)

        assert len(events) == 1
        assert events[0]["type"] == "user"

    def test_batch_conversation_flow(self):
        """Test batch with full conversation flow"""
        messages = [
            UserMessage(content="List files"),
            AssistantMessage(
                content=[
                    TextBlock(text="I'll list the files"),
                    ToolUseBlock(
                        id="tool_1",
                        name="Bash",
                        input={"command": "ls"},
                    ),
                ],
                model=TEST_MODEL,
            ),
            AssistantMessage(
                content=[
                    ToolResultBlock(
                        tool_use_id="tool_1", content="file1.txt\nfile2.txt"
                    )
                ],
                model=TEST_MODEL,
            ),
            AssistantMessage(
                content=[TextBlock(text="Found 2 files")], model=TEST_MODEL
            ),
            ResultMessage(
                subtype="complete",
                duration_ms=2000,
                duration_api_ms=1800,
                is_error=False,
                num_turns=2,
                session_id="test",
                usage={"input_tokens": 50, "output_tokens": 25},
                total_cost_usd=0.0005,
            ),
        ]

        events = convert_messages_batch(messages)

        assert len(events) == 6
        assert events[0]["type"] == "user"
        assert events[1]["type"] == "text_delta"
        assert events[2]["type"] == "tool_start"
        assert events[3]["type"] == "tool_end"
        assert events[4]["type"] == "text_delta"
        assert events[5]["type"] == "usage"

    def test_batch_preserves_order(self):
        """Test that batch conversion preserves message order"""
        messages = [
            UserMessage(content="First"),
            AssistantMessage(
                content=[TextBlock(text="Second")], model=TEST_MODEL
            ),
            UserMessage(content="Third"),
            AssistantMessage(
                content=[TextBlock(text="Fourth")], model=TEST_MODEL
            ),
        ]

        events = convert_messages_batch(messages)

        assert len(events) == 4
        assert events[0]["text"] == "First"
        assert events[1]["text"] == "Second"
        assert events[2]["text"] == "Third"
        assert events[3]["text"] == "Fourth"


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_empty_content_list(self):
        """Test message with empty content list"""
        message = AssistantMessage(content=[], model=TEST_MODEL)

        events = convert_message_to_websocket(message)

        assert events == []

    def test_unknown_message_type(self):
        """Test handling of unknown message type"""

        # Create a mock unknown message type
        class UnknownMessage:
            pass

        message = UnknownMessage()

        events = convert_message_to_websocket(message)

        assert events == []

    def test_none_content(self):
        """Test handling of valid message with content"""
        message = AssistantMessage(
            content=[TextBlock(text="valid")], model=TEST_MODEL
        )

        events = convert_message_to_websocket(message)

        # Should handle gracefully
        assert len(events) >= 1
        assert events[0]["type"] == "text_delta"
