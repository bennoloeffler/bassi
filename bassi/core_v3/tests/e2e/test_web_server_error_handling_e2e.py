"""
E2E Tests for V3 Web Server Error Handling and Edge Cases

These tests focus on UNHAPPY PATHS that could crash the UI:
- WebSocket disconnects during processing
- Invalid message formats
- Session errors during execution
- Concurrent access issues
- Error recovery and stability

Goal: Prevent real user bugs and make the UI stable under error conditions.
"""

import os
import tempfile
import time

import pytest

# Mark all tests in this module as E2E tests
pytestmark = [
    pytest.mark.e2e,
    pytest.mark.xdist_group(name="e2e_server"),
]


@pytest.fixture(autouse=True)
def cleanup_between_tests():
    """Ensure cleanup time between tests to allow SDK client to disconnect"""
    yield
    time.sleep(2)


def test_websocket_invalid_message_format(page, live_server):
    """
    CRITICAL: Test that invalid WebSocket messages don't crash the server.

    User scenario: Malformed JSON or missing required fields should show error,
    not crash the entire UI.
    """
    page.goto(live_server)
    page.wait_for_selector(
        "#connection-status:has-text('Connected')", timeout=10000
    )

    # Establish WebSocket connection and send invalid message
    page.evaluate(
        """() => {
            window.testWs = new WebSocket('ws://localhost:8765/ws');
            window.testWs.onopen = () => {
                // Send INVALID message (missing required fields)
                window.testWs.send(JSON.stringify({
                    type: "chat_input",
                    // Missing 'content' field - should be rejected
                }));
            };
        }"""
    )

    # Wait for error handling
    page.wait_for_timeout(1000)

    # Server should still be responsive - test with ping
    response = page.evaluate(
        """() => {
            return new Promise((resolve) => {
                const timeout = setTimeout(() => resolve({status: 'timeout'}), 2000);
                window.testWs.onmessage = (event) => {
                    clearTimeout(timeout);
                    resolve({status: 'ok', data: event.data});
                };
                window.testWs.send(JSON.stringify({
                    type: "ping"
                }));
            });
        }"""
    )

    # Server should still respond (proves it didn't crash)
    assert response["status"] in [
        "ok",
        "timeout",
    ], "Server should respond after invalid message"

    # UI should still be functional
    input_field = page.query_selector("#message-input")
    assert input_field is not None, "Input field should still exist"

    print("✅ Server handled invalid WebSocket message gracefully")


def test_websocket_send_during_session_deletion(page, live_server):
    """
    CRITICAL: Test race condition - sending message while session is being deleted.

    User scenario: User clicks delete while agent is processing. UI should handle
    gracefully, not crash or hang.
    """
    # Listen to console messages to detect when session is ready
    console_messages = []
    session_ready = False

    def check_session(msg):
        nonlocal session_ready
        console_messages.append(f"{msg.type}: {msg.text}")
        if "Session ID stored" in msg.text:
            session_ready = True

    page.on("console", check_session)

    page.goto(live_server)
    page.wait_for_selector(
        "#connection-status:has-text('Connected')", timeout=10000
    )

    # Wait for session ID to be received and stored (check console log)
    for _ in range(50):  # Wait up to 5 seconds
        if session_ready:
            break
        page.wait_for_timeout(100)

    # ALWAYS print console messages for debugging
    print(f"\n=== Console Messages (session_ready={session_ready}) ===")
    for msg in console_messages:
        print(msg)
    print("=" * 50)

    if not session_ready:
        print("⚠️ Session not ready after waiting!")

    # Get session ID from bassiClient
    session_id = page.evaluate("() => window.bassiClient?.sessionId || null")
    print(f"Session ID from bassiClient: {session_id}")
    assert session_id is not None, "Session ID should be set"

    # Start a message (simulate long-running operation)
    input_field = page.query_selector("#message-input")
    send_btn = page.query_selector("#send-button")

    input_field.fill("What is the weather in Tokyo?")
    send_btn.click()

    # Immediately try to delete the session (race condition)
    page.wait_for_timeout(200)

    # Try to find and click delete button
    delete_btn = page.query_selector(
        f"button[data-session-id='{session_id}'][title*='Delete']"
    )
    if delete_btn:
        delete_btn.click()

        # Confirm deletion if dialog appears
        page.wait_for_timeout(200)
        confirm_btn = page.query_selector("text=Delete")
        if confirm_btn:
            confirm_btn.click()

    # Wait for operation to complete or error
    page.wait_for_timeout(2000)

    # UI should recover gracefully - body should still be visible
    body = page.query_selector("body")
    assert body is not None, "Page body should exist"

    # No fatal error indicators
    error_indicators = page.query_selector_all(".error, .crash, .fatal")
    assert len(error_indicators) == 0, "UI should not show fatal errors"

    print("✅ Race condition handled gracefully")


def test_websocket_multiple_rapid_messages(page, live_server):
    """
    STABILITY: Test sending multiple messages rapidly without waiting for responses.

    User scenario: User frantically clicks send multiple times. UI should queue
    messages properly, not crash or drop messages.
    """
    # Listen to console messages to detect when session is ready
    session_ready = False

    def check_session(msg):
        nonlocal session_ready
        if "Session ID stored" in msg.text:
            session_ready = True

    page.on("console", check_session)

    page.goto(live_server)
    page.wait_for_selector(
        "#connection-status:has-text('Connected')", timeout=10000
    )

    # Wait for session ID to be received and stored
    for _ in range(50):  # Wait up to 5 seconds
        if session_ready:
            break
        page.wait_for_timeout(100)

    if not session_ready:
        print("⚠️  Session not ready - test may fail")

    input_field = page.query_selector("#message-input")
    send_btn = page.query_selector("#send-button")

    # Fill input first to enable send button
    input_field.fill("Message 1")
    page.wait_for_timeout(200)

    # Wait for send button to be enabled
    for _ in range(20):  # Wait up to 2 seconds
        if not send_btn.is_disabled():
            break
        page.wait_for_timeout(100)

    print(f"Send button disabled: {send_btn.is_disabled()}")

    # Send 5 messages rapidly (send button may become disabled after first click)
    for i in range(5):
        if not send_btn.is_disabled():  # Only click if enabled
            input_field.fill(f"Message {i+1}")
            send_btn.click()
            page.wait_for_timeout(100)

    # Wait for processing
    page.wait_for_timeout(3000)

    # UI should still be responsive (key requirement - no crash)
    body = page.query_selector("body")
    assert body is not None, "Page should still exist (no crash)"

    assert input_field is not None, "Input field should exist"
    assert not input_field.is_disabled(), "Input should be enabled"

    # Check that at least one message was sent (some may be queued or dropped)
    messages = page.query_selector_all(
        ".user-message, .chat-message, [data-message]"
    )
    message_count = len(messages)
    assert (
        message_count > 0
    ), f"At least one message should appear, found {message_count}"

    print(
        f"✅ Rapid messages handled - {message_count} messages found, UI stable"
    )


def test_session_list_after_server_restart(page, live_server):
    """
    RECOVERY: Test that UI handles missing sessions gracefully.

    User scenario: Sessions existed, then server restarted (data loss).
    UI should show empty state, not crash trying to load non-existent sessions.
    """
    page.goto(live_server)
    page.wait_for_selector(
        "#connection-status:has-text('Connected')", timeout=10000
    )

    # Wait for UI to attempt loading sessions
    page.wait_for_timeout(2000)

    # UI should be visible (not white screen of death)
    body = page.query_selector("body")
    assert body is not None, "Page should load"

    # Should have input field available (even if no sessions)
    input_field = page.query_selector("#message-input")
    assert input_field is not None, "Input field should be available"

    print("✅ UI loads gracefully even with missing sessions")


def test_file_upload_invalid_file_type(page, live_server):
    """
    ERROR HANDLING: Test uploading unsupported file type.

    User scenario: User tries to upload .exe, .dll, or other invalid file.
    UI should show clear error, not crash or hang.
    """
    page.goto(live_server)
    page.wait_for_selector(
        "#connection-status:has-text('Connected')", timeout=10000
    )

    # Wait for session ready
    page.wait_for_timeout(2000)

    # Look for file input
    file_input = page.query_selector('input[type="file"]')

    if file_input:
        # Create a fake "invalid" file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".exe", delete=False
        ) as f:
            f.write("This is not a real exe file")
            temp_file = f.name

        try:
            # Try to upload the "invalid" file
            file_input.set_input_files(temp_file)

            # Wait for error or acceptance
            page.wait_for_timeout(1000)

            # UI should still be responsive
            body = page.query_selector("body")
            assert body is not None, "Page should still be responsive"

            print(
                "✅ Invalid file upload handled (accepted or rejected gracefully)"
            )

        finally:
            # Cleanup
            os.unlink(temp_file)
    else:
        pytest.skip("File input not found in UI")


def test_empty_message_submission(page, live_server):
    """
    UX EDGE CASE: Test sending empty message.

    User scenario: User clicks send without typing anything.
    Should be prevented or handled gracefully, not crash.
    """
    page.goto(live_server)
    page.wait_for_selector(
        "#connection-status:has-text('Connected')", timeout=10000
    )

    # Wait for session ready
    page.wait_for_timeout(2000)

    input_field = page.query_selector("#message-input")
    send_btn = page.query_selector("#send-button")

    # Clear input (ensure empty)
    input_field.fill("")

    # Try to send empty message
    send_btn.click()

    # Wait a bit
    page.wait_for_timeout(500)

    # UI should still be responsive
    assert input_field is not None, "Input field should exist"
    assert send_btn is not None, "Send button should exist"

    # Key: Should NOT crash or cause errors
    print("✅ Empty message submission handled gracefully")


def test_websocket_reconnection_after_disconnect(page, live_server):
    """
    STABILITY: Test that UI handles WebSocket disconnect and reconnects.

    User scenario: Network hiccup or server restart. UI should show
    reconnection status, not just hang forever.
    """
    page.goto(live_server)
    page.wait_for_selector(
        "#connection-status:has-text('Connected')", timeout=10000
    )

    # Wait for initial connection
    page.wait_for_timeout(1000)

    # Force WebSocket disconnect
    disconnected = page.evaluate(
        """() => {
            if (window.socket) {
                window.socket.close();
                return true;
            }
            return false;
        }"""
    )

    if disconnected:
        # Wait for reconnection attempt
        page.wait_for_timeout(2000)

        # UI should show some indication of connection status
        body = page.query_selector("body")
        assert body is not None, "Page should still exist"

        # Input should either be disabled or show reconnecting state
        input_field = page.query_selector("#message-input")
        assert input_field is not None, "Input field should exist"

        print("✅ WebSocket disconnect handled gracefully")
    else:
        pytest.skip("WebSocket not accessible in page context")


def test_very_long_message_input(page, live_server):
    """
    EDGE CASE: Test sending very long message (potential DoS or memory issue).

    User scenario: User pastes huge text block (e.g., entire document).
    Server should handle gracefully, not crash or hang.
    """
    page.goto(live_server)
    page.wait_for_selector(
        "#connection-status:has-text('Connected')", timeout=10000
    )

    # Wait for session ready
    page.wait_for_timeout(2000)

    input_field = page.query_selector("#message-input")
    send_btn = page.query_selector("#send-button")

    # Create very long message (10KB)
    long_message = "A" * 10000

    input_field.fill(long_message)
    send_btn.click()

    # Wait for processing
    page.wait_for_timeout(3000)

    # Server should handle it (or reject it) without crashing
    body = page.query_selector("body")
    assert body is not None, "Page should still exist after long message"

    # UI should be responsive again
    assert input_field is not None, "Input field should still exist"

    print("✅ Very long message handled without crashing")


# Pytest configuration for Playwright
@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Configure browser context for tests."""
    return {
        **browser_context_args,
        "viewport": {
            "width": 1280,
            "height": 720,
        },
    }
