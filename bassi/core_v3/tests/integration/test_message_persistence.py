"""
Tests for message persistence in WebSocket handler.

These tests verify that:
1. User messages are saved to workspace
2. Assistant responses are saved to workspace
3. Message counts are tracked correctly
4. Session index is updated
5. History.md file contains all messages
"""

import json

import pytest

from bassi.core_v3.session_workspace import SessionWorkspace


@pytest.fixture
def workspace(tmp_path):
    """Create a test workspace."""
    session_id = "test-session-msg-persist"
    workspace = SessionWorkspace(session_id, base_path=tmp_path, create=True)
    return workspace


def test_user_message_saved(workspace):
    """
    Test that user message is saved to workspace.

    Verify:
    - Message count increments from 0 to 1
    - Message appears in history.md
    - Metadata is updated
    """
    # Initial state
    assert workspace.metadata.get("message_count", 0) == 0

    # Save user message
    user_message = "Hello, can you help me with Python?"
    workspace.save_message("user", user_message)

    # Verify message count incremented
    assert workspace.metadata["message_count"] == 1

    # Verify message in history file
    history_path = workspace.physical_path / "history.md"
    assert history_path.exists(), "history.md should be created"

    history_content = history_path.read_text()
    assert "User -" in history_content
    assert user_message in history_content

    # Verify last_activity updated
    assert "last_activity" in workspace.metadata

    print("✅ User message saved correctly")


def test_assistant_message_saved(workspace):
    """
    Test that assistant response is saved to workspace.

    Verify:
    - Message count increments from 1 to 2
    - Assistant message appears in history.md
    - Multiple text blocks handled correctly
    """
    # Setup: Save user message first
    workspace.save_message("user", "Hello")
    assert workspace.metadata["message_count"] == 1

    # Save assistant response
    assistant_response = "Hi! I'd be happy to help you with Python."
    workspace.save_message("assistant", assistant_response)

    # Verify message count incremented
    assert workspace.metadata["message_count"] == 2

    # Verify both messages in history
    history_content = (workspace.physical_path / "history.md").read_text()
    assert "User -" in history_content
    assert "Assistant -" in history_content
    assert assistant_response in history_content

    print("✅ Assistant message saved correctly")


def test_multiple_message_exchanges(workspace):
    """
    Test that message count and history persist through multiple exchanges.

    Verify:
    - Message count reaches 6 after 3 exchanges
    - All messages in correct order
    - Timestamps are sequential
    """
    # Exchange 1
    workspace.save_message("user", "What is Python?")
    workspace.save_message("assistant", "Python is a programming language.")

    # Exchange 2
    workspace.save_message("user", "How do I install it?")
    workspace.save_message(
        "assistant", "You can download it from python.org."
    )

    # Exchange 3
    workspace.save_message("user", "Thank you!")
    workspace.save_message("assistant", "You're welcome!")

    # Verify final count
    assert workspace.metadata["message_count"] == 6

    # Verify all messages in history
    history_content = (workspace.physical_path / "history.md").read_text()
    assert history_content.count("User -") == 3
    assert history_content.count("Assistant -") == 3
    assert "What is Python?" in history_content
    assert "How do I install it?" in history_content
    assert "Thank you!" in history_content

    print("✅ Multiple exchanges tracked correctly")


def test_message_count_starts_at_zero(tmp_path):
    """
    Test that new workspace starts with message_count=0.
    """
    workspace = SessionWorkspace(
        "test-new-session", base_path=tmp_path, create=True
    )
    assert workspace.metadata.get("message_count", 0) == 0

    print("✅ New workspace has message_count=0")


def test_history_file_creation(workspace):
    """
    Test that history.md is created on first message.
    """
    history_path = workspace.physical_path / "history.md"
    assert not history_path.exists(), "history.md shouldn't exist initially"

    # Save first message
    workspace.save_message("user", "First message")

    # Verify file created
    assert history_path.exists(), "history.md should be created"

    # Verify header
    history_content = history_path.read_text()
    assert "# Chat History:" in history_content

    print("✅ history.md created on first message")


def test_message_timestamps(workspace):
    """
    Test that messages have timestamps and they're sequential.
    """
    # Save two messages
    workspace.save_message("user", "Message 1")
    workspace.save_message("assistant", "Response 1")

    # Read history
    history_content = (workspace.physical_path / "history.md").read_text()

    # Both should have timestamps (ISO format)
    assert history_content.count("User - ") == 1
    assert history_content.count("Assistant - ") == 1

    # Verify ISO format timestamp present (rough check)
    assert "T" in history_content  # ISO format has T separator
    assert ":" in history_content  # Time portion

    print("✅ Messages have timestamps")


def test_workspace_stats_after_messages(workspace):
    """
    Test that workspace.get_stats() reflects message count.
    """
    # Add messages
    workspace.save_message("user", "Hello")
    workspace.save_message("assistant", "Hi")

    # Get stats
    stats = workspace.get_stats()

    # Verify message count in stats
    assert stats["message_count"] == 2
    assert "last_activity" in stats

    print("✅ Workspace stats include message count")


def test_metadata_persists_to_disk(workspace):
    """
    Test that message_count is persisted to chat.json.
    """
    # Save messages
    workspace.save_message("user", "Test")
    workspace.save_message("assistant", "Response")

    # Read chat.json directly (renamed from session.json)
    chat_json_path = workspace.physical_path / "chat.json"
    assert chat_json_path.exists()

    with open(chat_json_path) as f:
        metadata = json.load(f)

    assert metadata["message_count"] == 2

    print("✅ Message count persisted to chat.json")


def test_reload_workspace_preserves_count(tmp_path):
    """
    Test that reloading workspace preserves message count.
    """
    session_id = "test-reload"

    # Create workspace and add messages
    workspace1 = SessionWorkspace(session_id, base_path=tmp_path, create=True)
    workspace1.save_message("user", "Message 1")
    workspace1.save_message("assistant", "Response 1")
    assert workspace1.metadata["message_count"] == 2

    # Reload workspace
    workspace2 = SessionWorkspace.load(session_id, base_path=tmp_path)

    # Verify count preserved
    assert workspace2.metadata["message_count"] == 2

    # Add more messages
    workspace2.save_message("user", "Message 2")

    # Count should be 3
    assert workspace2.metadata["message_count"] == 3

    print("✅ Message count preserved across reload")


# Integration test with session index
def test_session_index_updated_with_messages(tmp_path):
    """
    Test that SessionIndex reflects updated message count.

    This is an integration test verifying the full flow:
    1. Save message to workspace
    2. Update session index
    3. Index shows correct count
    """
    from bassi.core_v3.session_index import SessionIndex

    # Create workspace and index
    session_id = "test-index-update"
    workspace = SessionWorkspace(session_id, base_path=tmp_path, create=True)
    session_index = SessionIndex(base_path=tmp_path)

    # Add workspace to index
    session_index.add_session(workspace)

    # Initially 0 messages
    sessions = session_index.list_sessions()
    assert len(sessions) == 1
    assert sessions[0]["message_count"] == 0

    # Add messages
    workspace.save_message("user", "Hello")
    workspace.save_message("assistant", "Hi")

    # Update index
    session_index.update_session(workspace)

    # Verify index updated
    sessions = session_index.list_sessions()
    assert sessions[0]["message_count"] == 2

    print("✅ Session index updated with message count")


# Test for empty content
def test_empty_message_not_saved(workspace):
    """
    Test that empty messages are handled gracefully.
    """
    # Save empty message
    workspace.save_message("user", "")

    # Message count should still increment
    assert workspace.metadata["message_count"] == 1

    # Empty content should be in history
    history_content = (workspace.physical_path / "history.md").read_text()
    assert "User -" in history_content

    print("✅ Empty messages handled correctly")


# Test for very long messages
def test_long_message_saved(workspace):
    """
    Test that long messages are saved correctly.
    """
    # Create long message (10KB)
    long_message = "x" * 10000

    workspace.save_message("user", long_message)

    # Verify saved
    assert workspace.metadata["message_count"] == 1

    # Verify in history
    history_content = (workspace.physical_path / "history.md").read_text()
    assert long_message in history_content

    print("✅ Long messages saved correctly")


# Test for messages with special characters
def test_message_with_special_characters(workspace):
    """
    Test that messages with special characters are saved correctly.
    """
    special_message = 'Test with "quotes", emoji 🎉, and symbols: <>&'

    workspace.save_message("user", special_message)

    # Verify in history
    history_content = (workspace.physical_path / "history.md").read_text()
    assert special_message in history_content

    print("✅ Messages with special characters saved correctly")
