"""
End-to-end tests for loading message history when switching sessions.

This test file focuses on verifying that when a user clicks on an existing
session in the sidebar, all previous messages are loaded and displayed in
the UI.

CRITICAL BUG: Currently, messages do NOT load when switching sessions.
This test suite will help us identify and fix the issue.
"""

import pytest

# Ensure tests run serially with the shared live_server instance
pytestmark = [
    pytest.mark.integration,
    pytest.mark.e2e,
    pytest.mark.xdist_group(name="e2e_server"),
]


def _wait_for_initial_session(page):
    """Wait for the initial session to be created and connected."""
    page.wait_for_selector(
        "#connection-status:has-text('Connected')", timeout=15000
    )
    handle = page.wait_for_function(
        "() => (window.bassiClient && window.bassiClient.sessionId) || null",
        timeout=15000,
    )
    return handle.json_value()


def _wait_for_new_session(page, previous_id):
    """Wait for a new session to be created (different from previous_id)."""
    handle = page.wait_for_function(
        """(prev) => {
            const client = window.bassiClient
            if (!client || !client.sessionId) return null
            return client.sessionId !== prev ? client.sessionId : null
        }""",
        arg=previous_id,
        timeout=15000,
    )
    return handle.json_value()


def _send_message(page, text):
    """Send a message and wait for the agent to finish processing."""
    page.fill("#message-input", text)
    page.click("#send-button")

    # Wait for user message to appear
    page.wait_for_selector(
        f".user-message .message-content:has-text('{text}')", timeout=10000
    )

    # Wait for agent to finish working
    page.wait_for_function(
        "() => window.bassiClient && window.bassiClient.isAgentWorking === false",
        timeout=30000,  # Give agent time to respond
    )


def _ensure_sidebar_open(page):
    """Ensure the session sidebar is open."""
    is_open = page.evaluate(
        "() => document.getElementById('session-sidebar')?.classList.contains('open') || false"
    )
    if not is_open:
        page.click("#session-sidebar-toggle")
        page.wait_for_function(
            "() => document.getElementById('session-sidebar')?.classList.contains('open')",
            timeout=5000,
        )


def _refresh_sessions(page):
    """Refresh the session list."""
    page.evaluate(
        "async () => { if (window.bassiClient?.loadSessions) { await window.bassiClient.loadSessions(); } }"
    )


def _wait_for_session_rows(page, expected_count):
    """Wait for the expected number of session rows to appear."""
    page.wait_for_function(
        """(count) => {
            const nodes = document.querySelectorAll('#session-list .session-item')
            return nodes.length >= count
        }""",
        arg=expected_count,
        timeout=10000,
    )


def _get_session_ids(page):
    """Get all session IDs from the sidebar."""
    return page.eval_on_selector_all(
        "#session-list .session-item",
        "nodes => nodes.map(node => node.dataset.sessionId)",
    )


def _count_messages(page):
    """Count total number of messages in the conversation."""
    return page.evaluate(
        """() => {
            const userMessages = document.querySelectorAll('.user-message').length
            const assistantMessages = document.querySelectorAll('.assistant-message').length
            return { user: userMessages, assistant: assistantMessages, total: userMessages + assistantMessages }
        }"""
    )


def _get_message_texts(page):
    """Get all message texts from the conversation."""
    return page.evaluate(
        """() => {
            const messages = []
            document.querySelectorAll('.user-message, .assistant-message').forEach(msg => {
                const role = msg.classList.contains('user-message') ? 'user' : 'assistant'
                const content = msg.querySelector('.message-content')?.textContent || ''
                messages.push({ role, content: content.trim() })
            })
            return messages
        }"""
    )


def _switch_to_session(page, session_id):
    """Switch to a specific session by directly calling switchSession()."""
    # Call switchSession() directly via JavaScript (more reliable than clicking)
    page.evaluate(
        f"async () => {{ await window.bassiClient.switchSession('{session_id}') }}"
    )

    # Wait for the connection to be re-established
    page.wait_for_selector(
        "#connection-status:has-text('Connected')", timeout=15000
    )

    # Wait for the session ID to change in the client
    page.wait_for_function(
        f"() => window.bassiClient && window.bassiClient.sessionId === '{session_id}'",
        timeout=10000,
    )


def test_load_session_with_messages(page, live_server):
    """
    Test that switching to an existing session loads all previous messages.

    EXPECTED BEHAVIOR:
    1. Create first session and send 2 messages (user + assistant response)
    2. Create second session (current messages should clear)
    3. Switch back to first session
    4. CRITICAL: Previous messages (user + assistant) should reappear

    CURRENT BUG: Step 4 fails - messages do NOT load
    """
    # Capture console messages for debugging
    console_messages = []
    def handle_console(msg):
        console_messages.append(f"[{msg.type}] {msg.text}")
    page.on("console", handle_console)

    # Step 1: Create first session and send messages
    page.goto(live_server)
    first_session_id = _wait_for_initial_session(page)

    print(f"✅ First session created: {first_session_id[:8]}...")

    # Send a simple message
    _send_message(page, "Hello, this is the first message")

    # Verify message appears (we only care about user message for this test)
    messages_after_first = _count_messages(page)
    print(f"📊 Messages after first message: {messages_after_first}")
    assert messages_after_first["user"] >= 1, "User message should appear"

    # Wait a bit for assistant response (but don't fail if it doesn't come)
    page.wait_for_timeout(3000)
    messages_after_first = _count_messages(page)

    # Get the actual message texts for verification
    first_session_messages = _get_message_texts(page)
    print(f"📝 First session messages: {len(first_session_messages)}")
    for msg in first_session_messages:
        print(f"   - [{msg['role']}] {msg['content'][:50]}...")

    # Step 2: Create second session
    _ensure_sidebar_open(page)
    _refresh_sessions(page)
    _wait_for_session_rows(page, 1)

    page.click("#new-session-button")
    second_session_id = _wait_for_new_session(page, first_session_id)

    print(f"✅ Second session created: {second_session_id[:8]}...")

    # Verify conversation is cleared
    messages_in_second = _count_messages(page)
    print(f"📊 Messages in second session: {messages_in_second}")
    assert messages_in_second["total"] == 0, "Second session should start empty"

    # Step 3: Switch back to first session
    _ensure_sidebar_open(page)
    _refresh_sessions(page)
    _wait_for_session_rows(page, 2)

    print(f"🔄 Switching back to first session: {first_session_id[:8]}...")
    _switch_to_session(page, first_session_id)

    # Step 4: CRITICAL TEST - Messages should reappear
    # Give the UI time to load messages (if it works)
    page.wait_for_timeout(3000)

    # Print console logs for debugging
    print(f"🔍 Browser console logs (showing all {len(console_messages)} messages):")
    for msg in console_messages:
        print(f"   {msg}")

    messages_after_switch = _count_messages(page)
    print(f"📊 Messages after switch: {messages_after_switch}")

    # This is the CRITICAL assertion that currently fails
    assert messages_after_switch["total"] > 0, (
        "🐛 BUG CONFIRMED: Messages do NOT load when switching to existing session!\n"
        f"Expected: {len(first_session_messages)} messages\n"
        f"Got: {messages_after_switch['total']} messages"
    )

    # Verify the actual content matches
    loaded_messages = _get_message_texts(page)
    print(f"📝 Loaded messages after switch: {len(loaded_messages)}")

    # We should have the same messages
    assert len(loaded_messages) == len(first_session_messages), (
        f"Message count mismatch: expected {len(first_session_messages)}, got {len(loaded_messages)}"
    )

    # Verify the first user message is present
    user_messages = [m for m in loaded_messages if m["role"] == "user"]
    assert any("first message" in m["content"] for m in user_messages), (
        "Original user message should be present after session switch"
    )

    print("✅ TEST PASSED: Messages loaded successfully after session switch!")


def test_empty_session_has_no_messages(page, live_server):
    """
    Baseline test: Verify that a brand new session starts with no messages.

    This ensures our message counting logic is correct.
    """
    page.goto(live_server)
    _wait_for_initial_session(page)

    messages = _count_messages(page)
    assert messages["total"] == 0, "New session should have no messages"

    print("✅ Empty session verified")


def test_session_sidebar_shows_message_count(page, live_server):
    """
    Test that the session list displays the correct message count.

    EXPECTED: Session item shows "X messages"
    """
    page.goto(live_server)
    first_session_id = _wait_for_initial_session(page)

    # Send a message
    _send_message(page, "Test message for count")

    # Open sidebar and check message count
    _ensure_sidebar_open(page)
    _refresh_sessions(page)
    _wait_for_session_rows(page, 1)

    # Get the message count from the session item
    message_count_text = page.eval_on_selector(
        f"#session-list .session-item[data-session-id='{first_session_id}']",
        "node => node.textContent"
    )

    print(f"📋 Session item text: {message_count_text}")

    # Should show at least 1 message (more if agent responded)
    assert "message" in message_count_text.lower(), (
        "Session item should display message count"
    )

    print("✅ Session message count displayed")
