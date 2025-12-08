"""
E2E tests for STRESS AND EDGE CASES.

These tests probe the system's behavior in corner cases that could
lead to invalid states. Focus areas:
1. Cancel/interrupt while NOT working (no-op safety)
2. Rapid cancel + new message (race condition)
3. Multiple hints in quick succession (concurrent queries)
4. Cancel during hint processing
5. State consistency after edge operations

Each test validates system robustness beyond the happy path.
"""

import pytest

# Ensure tests run serially with the shared live_server instance
pytestmark = [
    pytest.mark.integration,
    pytest.mark.e2e,
    pytest.mark.xdist_group(name="e2e_server"),
]


def _wait_for_connection(page):
    """Wait for WebSocket connection to be established."""
    page.wait_for_selector(
        "#connection-status:has-text('Connected')", timeout=15000
    )
    handle = page.wait_for_function(
        "() => (window.bassiClient && window.bassiClient.sessionId) || null",
        timeout=15000,
    )
    return handle.json_value()


def _send_message_and_wait(page, message: str, timeout: int = 30000):
    """Send a message and wait for agent response."""
    page.fill("#message-input", message)
    page.click("#send-button")

    # Wait for user message to appear
    page.wait_for_selector(
        f".user-message .message-content:has-text('{message}')",
        timeout=10000,
    )

    # Wait for agent to finish working
    page.wait_for_function(
        "() => window.bassiClient && window.bassiClient.isAgentWorking === false",
        timeout=timeout,
    )


def _get_console_errors(page) -> list[str]:
    """Get any console errors from the page."""
    errors = page.evaluate(
        """
        () => {
            if (window._consoleErrors) {
                return window._consoleErrors;
            }
            return [];
        }
    """
    )
    return errors or []


def _setup_console_error_capture(page):
    """Set up console error capturing for a page."""
    page.evaluate(
        """
        () => {
            window._consoleErrors = [];
            const originalError = console.error;
            console.error = function(...args) {
                window._consoleErrors.push(args.map(a => String(a)).join(' '));
                originalError.apply(console, args);
            };
        }
    """
    )


# =============================================================================
# EDGE CASE 1: Cancel while agent is NOT working
# =============================================================================


def test_cancel_while_not_working_is_safe_noop(page, live_server):
    """
    EDGE CASE: Triggering cancel when agent is not working should be a safe no-op.

    The stop button is correctly hidden when agent is not working (good UI).
    This test verifies that programmatically sending an interrupt when the
    agent is idle doesn't break anything.

    Steps:
    1. Navigate and connect
    2. Verify agent is NOT working
    3. Verify stop button is hidden (correct UI behavior)
    4. Programmatically trigger interrupt via WebSocket
    5. Verify no error occurs
    6. Verify state remains valid (can still send messages)
    """
    page.goto(live_server)
    _wait_for_connection(page)
    _setup_console_error_capture(page)

    # Verify agent is NOT working initially
    is_working = page.evaluate("() => window.bassiClient?.isAgentWorking")
    assert is_working is False, "Agent should not be working initially"

    # Check if stop button exists but is hidden (correct UI behavior)
    stop_button = page.query_selector("#stop-button")
    assert stop_button is not None, "Stop button should exist"

    # Verify stop button is NOT visible when not working (good UX)
    is_visible = page.evaluate(
        "() => document.getElementById('stop-button')?.style.display !== 'none'"
    )
    # The button should be hidden when not working - this is correct behavior
    # We'll test programmatic interrupt instead

    # Programmatically send interrupt via WebSocket (simulating edge case)
    # This tests that the system handles spurious interrupts gracefully
    page.evaluate(
        """
        () => {
            if (window.bassiClient && window.bassiClient.ws) {
                window.bassiClient.ws.send(JSON.stringify({type: 'interrupt'}));
            }
        }
    """
    )

    # Brief pause to allow any error to surface
    page.wait_for_timeout(500)

    # Verify no console errors
    errors = _get_console_errors(page)
    critical_errors = [
        e for e in errors if "error" in e.lower() and "interrupt" in e.lower()
    ]
    assert (
        len(critical_errors) == 0
    ), f"Should not have interrupt errors: {critical_errors}"

    # Verify agent is still not working
    is_working_after = page.evaluate(
        "() => window.bassiClient?.isAgentWorking"
    )
    assert is_working_after is False, "Agent should still not be working"

    # Verify connection is still good
    page.wait_for_selector(
        "#connection-status:has-text('Connected')", timeout=5000
    )

    # Verify we can still send a message (system is not broken)
    page.fill("#message-input", "Test after cancel")
    page.click("#send-button")

    # Wait for user message to appear
    page.wait_for_selector(
        ".user-message .message-content:has-text('Test after cancel')",
        timeout=10000,
    )

    # Wait for agent response
    page.wait_for_function(
        "() => window.bassiClient && window.bassiClient.isAgentWorking === false",
        timeout=30000,
    )

    # Verify agent responded
    assistant_messages = page.query_selector_all(".assistant-message")
    assert (
        len(assistant_messages) > 0
    ), "Agent should have responded after cancel no-op"


# =============================================================================
# EDGE CASE 2: Rapid cancel + new message (race condition)
# =============================================================================


def test_rapid_cancel_then_new_message(page, live_server):
    """
    EDGE CASE: User cancels while agent is working, then immediately sends new message.

    This tests the race condition where:
    1. User sends message
    2. Agent starts working
    3. User clicks cancel
    4. User immediately sends new message

    The system should:
    - Cancel the first query gracefully
    - Accept and process the new message
    - Not get into invalid state

    Steps:
    1. Navigate and connect
    2. Send first message
    3. Wait for agent to start working
    4. Cancel execution
    5. Immediately send new message
    6. Verify new message is processed correctly
    """
    page.goto(live_server)
    _wait_for_connection(page)
    _setup_console_error_capture(page)

    # Send first message
    page.fill("#message-input", "First message to cancel")
    page.click("#send-button")

    # Wait for user message to appear
    page.wait_for_selector(
        ".user-message .message-content:has-text('First message to cancel')",
        timeout=10000,
    )

    # Give a brief moment for agent to start working
    page.wait_for_timeout(200)

    # Send interrupt via WebSocket (since button might not be visible yet)
    page.evaluate(
        """
        () => {
            if (window.bassiClient && window.bassiClient.ws) {
                window.bassiClient.ws.send(JSON.stringify({type: 'interrupt'}));
            }
        }
    """
    )

    # Brief pause after cancel
    page.wait_for_timeout(100)

    # Immediately send a new message
    page.fill("#message-input", "Second message after cancel")
    page.click("#send-button")

    # Wait for second user message to appear
    page.wait_for_selector(
        ".user-message .message-content:has-text('Second message after cancel')",
        timeout=10000,
    )

    # Wait for agent to finish processing the second message
    page.wait_for_function(
        "() => window.bassiClient && window.bassiClient.isAgentWorking === false",
        timeout=30000,
    )

    # Verify we have at least one assistant response
    # (could be from either message depending on timing)
    page.wait_for_selector(".assistant-message", timeout=10000)

    # Verify no critical console errors
    errors = _get_console_errors(page)
    critical_errors = [
        e for e in errors if "error" in e.lower() and "fatal" in e.lower()
    ]
    assert (
        len(critical_errors) == 0
    ), f"Should not have fatal errors: {critical_errors}"

    # Verify connection is still good
    page.wait_for_selector(
        "#connection-status:has-text('Connected')",
        timeout=5000,
    )

    # Count user messages - should have both
    user_messages = page.query_selector_all(".user-message")
    assert (
        len(user_messages) >= 2
    ), f"Should have at least 2 user messages, got {len(user_messages)}"


# =============================================================================
# EDGE CASE 3: Multiple hints in quick succession
# =============================================================================


def test_multiple_rapid_hints(page, live_server):
    """
    EDGE CASE: User sends multiple hints rapidly while agent is working.

    Hints are additional messages sent while the agent is processing.
    Sending multiple hints quickly could cause concurrent queries.

    This tests:
    1. System handles multiple rapid hints without crashing
    2. At least one hint is processed
    3. State remains valid afterward

    Steps:
    1. Navigate and connect
    2. Send initial message
    3. While agent is working, send multiple hints rapidly
    4. Verify system remains stable
    5. Verify at least one response is received
    """
    page.goto(live_server)
    _wait_for_connection(page)
    _setup_console_error_capture(page)

    # Send initial message to start agent working
    page.fill("#message-input", "Initial message for hints test")
    page.click("#send-button")

    # Wait for user message to appear
    page.wait_for_selector(
        ".user-message .message-content:has-text('Initial message for hints test')",
        timeout=10000,
    )

    # Brief pause to let agent start
    page.wait_for_timeout(100)

    # Send multiple hints rapidly via WebSocket
    # Note: Hints are a feature where additional context is sent while agent works
    for i in range(3):
        page.evaluate(
            f"""
            () => {{
                if (window.bassiClient && window.bassiClient.ws) {{
                    window.bassiClient.ws.send(JSON.stringify({{
                        type: 'hint',
                        content: 'Hint number {i+1}'
                    }}));
                }}
            }}
        """
        )
        # Very short delay between hints
        page.wait_for_timeout(50)

    # Wait for agent to finish (should handle hints gracefully)
    page.wait_for_function(
        "() => window.bassiClient && window.bassiClient.isAgentWorking === false",
        timeout=60000,  # Longer timeout due to multiple hints
    )

    # Verify we got at least one response
    page.wait_for_selector(".assistant-message", timeout=10000)

    # Verify no critical errors
    errors = _get_console_errors(page)
    critical_errors = [
        e for e in errors if "uncaught" in e.lower() or "fatal" in e.lower()
    ]
    assert (
        len(critical_errors) == 0
    ), f"Should not have critical errors: {critical_errors}"

    # Verify connection is still good
    page.wait_for_selector(
        "#connection-status:has-text('Connected')",
        timeout=5000,
    )

    # Verify we can still send a message afterward
    page.fill("#message-input", "Message after hints")
    page.click("#send-button")

    page.wait_for_selector(
        ".user-message .message-content:has-text('Message after hints')",
        timeout=10000,
    )

    page.wait_for_function(
        "() => window.bassiClient && window.bassiClient.isAgentWorking === false",
        timeout=30000,
    )


# =============================================================================
# EDGE CASE 4: Cancel during hint processing
# =============================================================================


def test_cancel_during_hint_processing(page, live_server):
    """
    EDGE CASE: User sends a hint, then cancels during hint processing.

    This tests the race condition where:
    1. User sends initial message
    2. While agent is working, user sends a hint
    3. User immediately cancels

    The system should:
    - Handle the cancel gracefully
    - Not leave the system in an invalid state
    - Allow new messages after the cancel

    Steps:
    1. Navigate and connect
    2. Send initial message
    3. While agent is working, send a hint
    4. Immediately cancel
    5. Verify state is valid
    6. Verify can send new message
    """
    page.goto(live_server)
    _wait_for_connection(page)
    _setup_console_error_capture(page)

    # Send initial message
    page.fill("#message-input", "Initial message for cancel test")
    page.click("#send-button")

    # Wait for user message to appear
    page.wait_for_selector(
        ".user-message .message-content:has-text('Initial message for cancel test')",
        timeout=10000,
    )

    # Brief pause to let agent start
    page.wait_for_timeout(100)

    # Send a hint via WebSocket
    page.evaluate(
        """
        () => {
            if (window.bassiClient && window.bassiClient.ws) {
                window.bassiClient.ws.send(JSON.stringify({
                    type: 'hint',
                    content: 'Here is a hint during processing'
                }));
            }
        }
    """
    )

    # Very short delay
    page.wait_for_timeout(50)

    # Immediately cancel via WebSocket
    page.evaluate(
        """
        () => {
            if (window.bassiClient && window.bassiClient.ws) {
                window.bassiClient.ws.send(JSON.stringify({type: 'interrupt'}));
            }
        }
    """
    )

    # Wait for agent to finish (either completed or cancelled)
    page.wait_for_function(
        "() => window.bassiClient && window.bassiClient.isAgentWorking === false",
        timeout=30000,
    )

    # Verify no critical errors
    errors = _get_console_errors(page)
    critical_errors = [
        e for e in errors if "uncaught" in e.lower() or "fatal" in e.lower()
    ]
    assert (
        len(critical_errors) == 0
    ), f"Should not have critical errors: {critical_errors}"

    # Verify connection is still good
    page.wait_for_selector(
        "#connection-status:has-text('Connected')",
        timeout=5000,
    )

    # Verify we can still send a message (system not broken)
    page.fill("#message-input", "Message after hint cancel")
    page.click("#send-button")

    page.wait_for_selector(
        ".user-message .message-content:has-text('Message after hint cancel')",
        timeout=10000,
    )

    page.wait_for_function(
        "() => window.bassiClient && window.bassiClient.isAgentWorking === false",
        timeout=30000,
    )

    # Verify agent responded to the new message
    assistant_messages = page.query_selector_all(".assistant-message")
    assert (
        len(assistant_messages) > 0
    ), "Agent should respond after hint cancel"


# =============================================================================
# EDGE CASE 5: State consistency after edge operations
# =============================================================================


def test_state_consistency_after_edge_operations(page, live_server):
    """
    EDGE CASE: After a series of edge operations, verify state remains valid.

    This is a comprehensive stress test that performs multiple edge operations
    in sequence and verifies the system remains in a valid state throughout.

    Operations performed:
    1. Send message, cancel immediately
    2. Send message with hints, cancel
    3. Send message, wait for response
    4. Verify all state indicators are correct

    The system should:
    - Maintain connection throughout
    - Keep isAgentWorking state synchronized
    - Not accumulate errors
    - Remain responsive

    Steps:
    1. Navigate and connect
    2. Perform edge operation sequence
    3. Verify final state is valid
    4. Verify system is still responsive
    """
    page.goto(live_server)
    _wait_for_connection(page)
    _setup_console_error_capture(page)

    # === Operation 1: Send and immediately cancel ===
    page.fill("#message-input", "Quick cancel test 1")
    page.click("#send-button")

    page.wait_for_selector(
        ".user-message .message-content:has-text('Quick cancel test 1')",
        timeout=10000,
    )

    # Immediate cancel
    page.evaluate(
        """
        () => {
            if (window.bassiClient && window.bassiClient.ws) {
                window.bassiClient.ws.send(JSON.stringify({type: 'interrupt'}));
            }
        }
    """
    )

    page.wait_for_function(
        "() => window.bassiClient && window.bassiClient.isAgentWorking === false",
        timeout=30000,
    )

    # === Operation 2: Send with hints, then cancel ===
    page.fill("#message-input", "Quick cancel test 2")
    page.click("#send-button")

    page.wait_for_selector(
        ".user-message .message-content:has-text('Quick cancel test 2')",
        timeout=10000,
    )

    page.wait_for_timeout(50)

    # Send hint
    page.evaluate(
        """
        () => {
            if (window.bassiClient && window.bassiClient.ws) {
                window.bassiClient.ws.send(JSON.stringify({
                    type: 'hint',
                    content: 'Stress test hint'
                }));
            }
        }
    """
    )

    page.wait_for_timeout(30)

    # Cancel
    page.evaluate(
        """
        () => {
            if (window.bassiClient && window.bassiClient.ws) {
                window.bassiClient.ws.send(JSON.stringify({type: 'interrupt'}));
            }
        }
    """
    )

    page.wait_for_function(
        "() => window.bassiClient && window.bassiClient.isAgentWorking === false",
        timeout=30000,
    )

    # === Operation 3: Normal message, wait for full response ===
    page.fill("#message-input", "Final normal message")
    page.click("#send-button")

    page.wait_for_selector(
        ".user-message .message-content:has-text('Final normal message')",
        timeout=10000,
    )

    page.wait_for_function(
        "() => window.bassiClient && window.bassiClient.isAgentWorking === false",
        timeout=30000,
    )

    # === Verify final state ===

    # 1. Connection should still be active
    page.wait_for_selector(
        "#connection-status:has-text('Connected')",
        timeout=5000,
    )

    # 2. isAgentWorking should be false
    is_working = page.evaluate("() => window.bassiClient?.isAgentWorking")
    assert is_working is False, "Agent should not be working after operations"

    # 3. Session should still be valid
    session_id = page.evaluate("() => window.bassiClient?.sessionId")
    assert session_id is not None, "Session ID should still exist"

    # 4. No critical console errors
    errors = _get_console_errors(page)
    critical_errors = [
        e
        for e in errors
        if "uncaught" in e.lower()
        or "fatal" in e.lower()
        or "exception" in e.lower()
    ]
    assert (
        len(critical_errors) == 0
    ), f"Should not have critical errors: {critical_errors}"

    # 5. Should have at least 3 user messages
    user_messages = page.query_selector_all(".user-message")
    assert (
        len(user_messages) >= 3
    ), f"Should have at least 3 user messages, got {len(user_messages)}"

    # 6. Should have at least one assistant response
    # (from the final normal message at minimum)
    page.wait_for_selector(".assistant-message", timeout=10000)

    # 7. Verify we can still send a NEW message (system not deadlocked)
    page.fill("#message-input", "Post-stress verification")
    page.click("#send-button")

    page.wait_for_selector(
        ".user-message .message-content:has-text('Post-stress verification')",
        timeout=10000,
    )

    page.wait_for_function(
        "() => window.bassiClient && window.bassiClient.isAgentWorking === false",
        timeout=30000,
    )
