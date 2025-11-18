"""
E2E test for agent context memory across session switches.

This test verifies the exact scenario reported by the user:
1. Session 1: User says "my name is benno"
2. Create and switch to Session 2
3. Switch back to Session 1
4. User asks "what's my name?"
5. Agent should answer "benno" (proving it remembers the context)
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


def _send_message_and_wait(page, text):
    """Send a message and wait for agent to finish responding."""
    # Count messages before
    message_count_before = page.evaluate(
        "() => document.querySelectorAll('.user-message').length"
    )

    # Send message
    page.fill("#message-input", text)
    page.click("#send-button")

    # Wait for new user message to appear
    page.wait_for_function(
        "(count) => document.querySelectorAll('.user-message').length > count",
        arg=message_count_before,
        timeout=10000,
    )

    # Wait for agent to finish working
    page.wait_for_function(
        "() => window.bassiClient && window.bassiClient.isAgentWorking === false",
        timeout=60000,  # Longer timeout for real agent responses
    )


def _create_new_session(page):
    """Create a new session via the UI."""
    # Open sidebar
    is_open = page.evaluate(
        "() => document.getElementById('session-sidebar')?.classList.contains('open') || false"
    )
    if not is_open:
        page.click("#session-sidebar-toggle")
        page.wait_for_timeout(500)

    # Click new session button
    page.click("#new-session-button")

    # Wait for new session to be created
    page.wait_for_function(
        "() => window.bassiClient && window.bassiClient.sessionId && window.bassiClient.sessionId !== null",
        timeout=10000,
    )


def _switch_to_session(page, session_id):
    """Switch to a specific session by ID."""
    # Open sidebar if needed
    is_open = page.evaluate(
        "() => document.getElementById('session-sidebar')?.classList.contains('open') || false"
    )
    if not is_open:
        page.click("#session-sidebar-toggle")
        page.wait_for_timeout(500)

    # Find and click the session item
    # The session items have data-session-id attribute
    page.click(f'[data-session-id="{session_id}"]')

    # Wait for connection to be re-established
    page.wait_for_selector(
        "#connection-status:has-text('Connected')", timeout=15000
    )

    # Wait for the session ID to change
    page.wait_for_function(
        f"() => window.bassiClient && window.bassiClient.sessionId === '{session_id}'",
        timeout=10000,
    )


def _get_last_assistant_message_text(page):
    """Get the text content of the last assistant message."""
    return page.evaluate(
        """() => {
            const messages = document.querySelectorAll('.assistant-message .message-content')
            if (messages.length === 0) return null
            return messages[messages.length - 1].textContent.trim()
        }"""
    )


def test_agent_remembers_name_after_session_switch(page, live_server):
    """
    Test that agent remembers context after switching sessions.

    Flow:
    1. Session 1: "my name is benno"
    2. Create Session 2 (switch away)
    3. Switch back to Session 1
    4. Ask: "what's my name?"
    5. Verify: Agent says "benno"
    """
    print("\n" + "=" * 60)
    print("TEST: Agent Context Memory Across Session Switches")
    print("=" * 60)

    # Step 1: Create first session and tell agent your name
    print("\n📍 Step 1: Creating Session 1 and telling agent my name...")
    page.goto(live_server)
    session_1_id = _wait_for_connection(page)
    print(f"   ✅ Session 1 created: {session_1_id[:8]}...")

    print('   💬 User: "my name is benno"')
    _send_message_and_wait(page, "my name is benno")

    response_1 = _get_last_assistant_message_text(page)
    print(f"   🤖 Agent: {response_1[:100]}...")

    # Step 2: Create a second session (switch away from Session 1)
    print("\n📍 Step 2: Creating Session 2 (switching away)...")
    _create_new_session(page)
    session_2_id = page.evaluate(
        "() => window.bassiClient ? window.bassiClient.sessionId : null"
    )
    print(f"   ✅ Session 2 created: {session_2_id[:8]}...")
    print("   ℹ️  Context should be cleared (new session has no history)")

    # Verify we're in Session 2
    current_messages = page.evaluate(
        "() => document.querySelectorAll('.user-message').length"
    )
    print(f"   📊 Messages in Session 2: {current_messages} (should be 0)")
    assert current_messages == 0, "Session 2 should be empty"

    # Step 3: Switch back to Session 1
    print("\n📍 Step 3: Switching back to Session 1...")
    _switch_to_session(page, session_1_id)
    print(f"   ✅ Switched to Session 1: {session_1_id[:8]}...")

    # Wait for messages to load
    page.wait_for_timeout(2000)

    # Verify Session 1 messages are visible
    messages_after_switch = page.evaluate(
        "() => document.querySelectorAll('.user-message').length"
    )
    print(f"   📊 Messages restored in UI: {messages_after_switch}")
    assert messages_after_switch >= 1, "UI should show previous message"

    # Step 4: CRITICAL TEST - Ask agent to recall the name
    print("\n📍 Step 4: CRITICAL TEST - Asking agent my name...")
    print('   💬 User: "what\'s my name?"')
    _send_message_and_wait(page, "what's my name?")

    response_2 = _get_last_assistant_message_text(page)
    print(f"   🤖 Agent: {response_2}")

    # Step 5: VERIFY - Agent should remember "benno"
    print("\n📍 Step 5: VERIFICATION...")
    response_lower = response_2.lower()

    if "benno" in response_lower:
        print("   ✅ SUCCESS: Agent remembered the name!")
        print(f"      Agent response contains 'benno': {response_2[:200]}")
    else:
        print("   ❌ FAILED: Agent did NOT remember the name!")
        print(f"      Agent response: {response_2}")
        pytest.fail(
            f"Agent should remember 'benno' but responded: {response_2}"
        )

    print("\n" + "=" * 60)
    print("✅ TEST PASSED: Agent Context Memory Works!")
    print("=" * 60 + "\n")

    # Final assertion
    assert "benno" in response_lower, (
        f"Agent should remember the name 'benno' from Session 1. "
        f"Response was: {response_2}"
    )


def test_agent_maintains_separate_contexts(page, live_server):
    """
    Test that different sessions maintain separate contexts.

    Flow:
    1. Session 1: "my name is alice"
    2. Session 2: "my name is bob"
    3. Switch to Session 1: "what's my name?" → should say "alice"
    4. Switch to Session 2: "what's my name?" → should say "bob"
    """
    print("\n" + "=" * 60)
    print("TEST: Separate Context Per Session")
    print("=" * 60)

    # Session 1: Alice
    print("\n📍 Step 1: Session 1 - Alice...")
    page.goto(live_server)
    session_1_id = _wait_for_connection(page)
    print(f"   ✅ Session 1: {session_1_id[:8]}...")
    print('   💬 User: "my name is alice"')
    _send_message_and_wait(page, "my name is alice")
    response_1a = _get_last_assistant_message_text(page)
    print(f"   🤖 Agent: {response_1a[:100]}...")

    # Session 2: Bob
    print("\n📍 Step 2: Session 2 - Bob...")
    _create_new_session(page)
    session_2_id = page.evaluate(
        "() => window.bassiClient ? window.bassiClient.sessionId : null"
    )
    print(f"   ✅ Session 2: {session_2_id[:8]}...")
    print('   💬 User: "my name is bob"')
    _send_message_and_wait(page, "my name is bob")
    response_2a = _get_last_assistant_message_text(page)
    print(f"   🤖 Agent: {response_2a[:100]}...")

    # Test Session 1: Should remember Alice
    print("\n📍 Step 3: Switch to Session 1 - Should remember Alice...")
    _switch_to_session(page, session_1_id)
    page.wait_for_timeout(2000)
    print('   💬 User: "what\'s my name?"')
    _send_message_and_wait(page, "what's my name?")
    response_1b = _get_last_assistant_message_text(page)
    print(f"   🤖 Agent: {response_1b}")

    # Test Session 2: Should remember Bob
    print("\n📍 Step 4: Switch to Session 2 - Should remember Bob...")
    _switch_to_session(page, session_2_id)
    page.wait_for_timeout(2000)
    print('   💬 User: "what\'s my name?"')
    _send_message_and_wait(page, "what's my name?")
    response_2b = _get_last_assistant_message_text(page)
    print(f"   🤖 Agent: {response_2b}")

    # Verify results
    print("\n📍 Step 5: VERIFICATION...")
    response_1b_lower = response_1b.lower()
    response_2b_lower = response_2b.lower()

    # Session 1 should remember Alice (not Bob)
    assert "alice" in response_1b_lower, (
        f"Session 1 should remember 'alice'. Response: {response_1b}"
    )
    assert "bob" not in response_1b_lower, (
        f"Session 1 should NOT know about 'bob'. Response: {response_1b}"
    )
    print("   ✅ Session 1 correctly remembers Alice")

    # Session 2 should remember Bob (not Alice)
    assert "bob" in response_2b_lower, (
        f"Session 2 should remember 'bob'. Response: {response_2b}"
    )
    assert "alice" not in response_2b_lower, (
        f"Session 2 should NOT know about 'alice'. Response: {response_2b}"
    )
    print("   ✅ Session 2 correctly remembers Bob")

    print("\n" + "=" * 60)
    print("✅ TEST PASSED: Sessions Maintain Separate Contexts!")
    print("=" * 60 + "\n")
