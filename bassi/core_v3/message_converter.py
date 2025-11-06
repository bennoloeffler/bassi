"""
Message Converter - Convert Agent SDK messages to web UI format.

This module bridges the gap between Agent SDK's typed message objects
and the web UI's expected event format for WebSocket streaming.
"""

from typing import Any

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


def convert_message_to_websocket(message: Message) -> list[dict[str, Any]]:
    """
    Convert Agent SDK message to web UI format.

    Args:
        message: Message from Agent SDK (AssistantMessage, SystemMessage, etc.)

    Returns:
        List of web UI event dictionaries ready for WebSocket transmission

    Example:
        ```python
        # AssistantMessage with text and tool use
        message = AssistantMessage(content=[
            TextBlock(text="Let me check that file"),
            ToolUseBlock(id="tool_1", name="ReadFile", input={"path": "/foo/bar"})
        ])

        events = convert_message_to_websocket(message)
        # Returns:
        # [
        #     {"type": "text_delta", "text": "Let me check that file"},
        #     {"type": "tool_start", "id": "tool_1", "tool_name": "ReadFile",
        #      "input": {"path": "/foo/bar"}}
        # ]
        ```
    """
    if isinstance(message, AssistantMessage):
        return _convert_assistant_message(message)
    elif isinstance(message, SystemMessage):
        return _convert_system_message(message)
    elif isinstance(message, ResultMessage):
        return _convert_result_message(message)
    elif isinstance(message, UserMessage):
        return _convert_user_message(message)
    else:
        # Unknown message type - return empty list
        return []


def _convert_assistant_message(
    message: AssistantMessage,
) -> list[dict[str, Any]]:
    """Convert AssistantMessage to web UI events"""
    events = []

    for block in message.content:
        event = _convert_content_block(block)
        if event:
            events.append(event)

    return events


def _convert_content_block(block: ContentBlock) -> dict[str, Any] | None:
    """
    Convert a single content block to web UI event.

    Args:
        block: Content block from AssistantMessage

    Returns:
        Web UI event dictionary or None if block type is unknown
    """
    if isinstance(block, TextBlock):
        return {
            "type": "text_delta",
            "text": block.text,
        }
    elif isinstance(block, ToolUseBlock):
        return {
            "type": "tool_start",
            "id": block.id,
            "tool_name": block.name,
            "input": block.input,
        }
    elif isinstance(block, ToolResultBlock):
        # Handle is_error - could be True, False, or None
        is_error = getattr(block, "is_error", False)
        if is_error is None:
            is_error = False
        return {
            "type": "tool_end",
            "id": block.tool_use_id,
            "content": block.content,
            "is_error": is_error,
        }
    elif isinstance(block, ThinkingBlock):
        return {
            "type": "thinking",
            "text": block.thinking,
        }
    else:
        # Unknown content block type
        return None


def _convert_system_message(message: SystemMessage) -> list[dict[str, Any]]:
    """Convert SystemMessage to web UI events

    SystemMessage contains:
    - subtype: Type of system message (e.g., 'init', 'warning', 'compaction_start', etc.)
    - data: Dictionary with message-specific data

    For 'init' subtype, data contains:
    - tools: List of available tool names
    - mcp_servers: List of MCP server info
    - slash_commands: List of slash command names
    - skills: List of skill names
    - agents: List of agent names
    - And other session metadata

    Subtype handling:
    - 'init': Metadata only - should NOT be shown to users
    - 'compaction_start': Important status - SHOULD be shown
    - Other subtypes with 'content'/'message'/'text': Show to users
    """
    # Return event with preserved structure
    return [
        {
            "type": "system",
            "subtype": message.subtype,
            **message.data,  # Unpack all data fields into the event
        }
    ]


def _convert_result_message(message: ResultMessage) -> list[dict[str, Any]]:
    """Convert ResultMessage to web UI events with usage stats"""
    events = []

    # Convert content blocks if present
    if hasattr(message, "content") and message.content:
        for block in message.content:
            event = _convert_content_block(block)
            if event:
                events.append(event)

    # Extract usage from usage dict if present, otherwise default to 0
    usage = getattr(message, "usage", {}) or {}
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)

    # Add usage statistics
    usage_event = {
        "type": "usage",
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_cost_usd": getattr(message, "total_cost_usd", 0.0) or 0.0,
    }
    events.append(usage_event)

    return events


def _convert_user_message(message: UserMessage) -> list[dict[str, Any]]:
    """Convert UserMessage to web UI events

    Note: UserMessage can contain either:
    1. Plain text (user's input) - convert to type: "user"
    2. ToolResultBlock (tool results from Agent SDK) - convert to tool_end events
    """
    events = []

    # Check if message.content is a list of content blocks
    if isinstance(message.content, list):
        for block in message.content:
            event = _convert_content_block(block)
            if event:
                events.append(event)
    else:
        # Plain text user message
        events.append(
            {
                "type": "user",
                "text": (
                    message.content
                    if isinstance(message.content, str)
                    else str(message.content)
                ),
            }
        )

    return events


def convert_messages_batch(messages: list[Message]) -> list[dict[str, Any]]:
    """
    Convert a batch of messages to web UI format.

    Args:
        messages: List of Agent SDK messages

    Returns:
        Flattened list of web UI events

    Example:
        ```python
        messages = [
            UserMessage(content="Hello"),
            AssistantMessage(content=[TextBlock(text="Hi there!")])
        ]

        events = convert_messages_batch(messages)
        # Returns:
        # [
        #     {"type": "user", "text": "Hello"},
        #     {"type": "text_delta", "text": "Hi there!"}
        # ]
        ```
    """
    all_events = []
    for message in messages:
        events = convert_message_to_websocket(message)
        all_events.extend(events)
    return all_events
