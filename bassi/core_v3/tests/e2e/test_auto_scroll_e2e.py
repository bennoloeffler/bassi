"""
E2E tests for auto-scroll behavior.

Tests that the page automatically scrolls to show new content during conversations.
"""

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
@pytest.mark.xdist_group(name="e2e_server")
def test_auto_scroll_on_agent_response(page: Page, live_server: str):
    """
    Test that page auto-scrolls to show agent's response as it streams in.

    This is the core auto-scroll behavior: when user asks a question and the
    agent responds, the page should automatically scroll down to show the
    complete response as it's being typed out.

    Reproduces the bug where asking "was ist ein Stofftier?" shows only the
    beginning of the response, requiring manual scroll to see the rest.
    """
    # Navigate to app
    page.goto(live_server)

    # Wait for welcome message
    expect(page.locator(".welcome-message")).to_be_visible(timeout=10000)

    # Get initial scroll position - should be at bottom after welcome message loads
    initial_scroll = page.evaluate(
        """
        () => window.pageYOffset || document.documentElement.scrollTop
    """
    )

    # Get page height
    initial_height = page.evaluate(
        """
        () => document.documentElement.scrollHeight
    """
    )

    print(
        f"Initial scroll: {initial_scroll}, Initial height: {initial_height}"
    )

    # Verify we're at the bottom (within 100px threshold)
    viewport_height = page.evaluate("() => window.innerHeight")
    distance_from_bottom = initial_height - initial_scroll - viewport_height
    print(f"Distance from bottom: {distance_from_bottom}px (should be < 100)")

    # Send a message that will generate a multi-paragraph response
    message_input = page.locator("#message-input")
    message_input.click()
    message_input.fill("was ist ein Stofftier?")

    # Click send button
    send_button = page.locator("#send-button")
    send_button.click()

    # Wait for user message to appear
    user_message = page.locator(".user-message").last
    expect(user_message).to_be_visible(timeout=5000)

    # Get scroll position after user message
    user_msg_scroll = page.evaluate(
        """
        () => window.pageYOffset || document.documentElement.scrollTop
    """
    )
    print(f"Scroll after user message: {user_msg_scroll}")

    # Wait for assistant message to start appearing
    assistant_message = page.locator(".assistant-message").last
    expect(assistant_message).to_be_visible(timeout=10000)

    # Wait for text to start streaming (first text block should appear)
    text_block = assistant_message.locator(".text-block").first
    expect(text_block).to_be_visible(timeout=5000)

    # Wait a bit for some text to accumulate and scroll to happen
    # forceScrollToBottomSmooth uses double RAF, so we need a bit more time
    page.wait_for_timeout(2500)

    # Check scroll position after initial text appears
    text_scroll = page.evaluate(
        """
        () => window.pageYOffset || document.documentElement.scrollTop
    """
    )
    page_height = page.evaluate(
        """
        () => document.documentElement.scrollHeight
    """
    )
    viewport = page.evaluate("() => window.innerHeight")

    print("After text starts streaming:")
    print(f"  Scroll position: {text_scroll}")
    print(f"  Page height: {page_height}")
    print(f"  Viewport height: {viewport}")

    # Calculate distance from bottom
    distance_from_bottom = page_height - text_scroll - viewport
    print(f"  Distance from bottom: {distance_from_bottom}px")

    # ASSERTION: We should be near the bottom (within 150px to allow for streaming)
    assert distance_from_bottom < 150, (
        f"Page should auto-scroll to show streaming text. "
        f"Distance from bottom: {distance_from_bottom}px (expected < 150px)"
    )

    # Wait for message to complete (typing indicator disappears)
    typing_indicator = assistant_message.locator(".typing-indicator")
    expect(typing_indicator).not_to_be_visible(timeout=30000)

    # Get final scroll position
    final_scroll = page.evaluate(
        """
        () => window.pageYOffset || document.documentElement.scrollTop
    """
    )
    final_height = page.evaluate(
        """
        () => document.documentElement.scrollHeight
    """
    )

    print(f"Final scroll: {final_scroll}, Final height: {final_height}")

    # Calculate final distance from bottom
    final_distance = final_height - final_scroll - viewport
    print(f"Final distance from bottom: {final_distance}px")

    # ASSERTION: Final position should also be at bottom (within 100px)
    assert final_distance < 100, (
        f"Page should be at bottom after response completes. "
        f"Distance from bottom: {final_distance}px (expected < 100px)"
    )


@pytest.mark.e2e
@pytest.mark.xdist_group(name="e2e_server")
def test_auto_scroll_respects_user_scroll_up(page: Page, live_server: str):
    """
    Test that auto-scroll stops when user manually scrolls up.

    This ensures the smart scroll behavior works - if the user scrolls up
    to read earlier content, the page should NOT auto-scroll and interrupt them.
    """
    # Navigate to app
    page.goto(live_server)

    # Wait for welcome message
    expect(page.locator(".welcome-message")).to_be_visible(timeout=10000)

    # Send a message
    message_input = page.locator("#message-input")
    message_input.click()
    message_input.fill("tell me a long story about a teddy bear")

    send_button = page.locator("#send-button")
    send_button.click()

    # Wait for response to start
    assistant_message = page.locator(".assistant-message").last
    expect(assistant_message).to_be_visible(timeout=10000)

    # Wait for some text to appear
    page.wait_for_timeout(1000)

    # Manually scroll to top
    page.evaluate("window.scrollTo({ top: 0, behavior: 'instant' })")

    # Wait a bit to let text continue streaming
    page.wait_for_timeout(2000)

    # Check scroll position - should still be at top
    current_scroll = page.evaluate(
        """
        () => window.pageYOffset || document.documentElement.scrollTop
    """
    )

    print(
        f"Scroll position after manually scrolling to top: {current_scroll}"
    )

    # ASSERTION: Should still be near the top (< 200px to allow for small movements)
    assert current_scroll < 200, (
        f"Auto-scroll should respect user scrolling up. "
        f"Current scroll: {current_scroll}px (expected < 200px)"
    )


@pytest.mark.e2e
@pytest.mark.xdist_group(name="e2e_server")
def test_auto_scroll_on_new_session(page: Page, live_server: str):
    """
    Test that new session welcome message is visible at bottom.

    When starting a new session, the welcome message should be visible
    and the page should be scrolled to the bottom.
    """
    # Navigate to app
    page.goto(live_server)

    # Wait for welcome message
    welcome = page.locator(".welcome-message")
    expect(welcome).to_be_visible(timeout=10000)

    # Give it time for layout to stabilize and scroll to complete
    # forceScrollToBottom waits for layout stability (up to 10 RAF frames)
    page.wait_for_timeout(500)

    # Get scroll metrics
    scroll_pos = page.evaluate(
        """
        () => window.pageYOffset || document.documentElement.scrollTop
    """
    )
    page_height = page.evaluate(
        """
        () => document.documentElement.scrollHeight
    """
    )
    viewport_height = page.evaluate("() => window.innerHeight")

    distance_from_bottom = page_height - scroll_pos - viewport_height

    print("New session scroll:")
    print(f"  Scroll position: {scroll_pos}")
    print(f"  Page height: {page_height}")
    print(f"  Viewport: {viewport_height}")
    print(f"  Distance from bottom: {distance_from_bottom}px")

    # ASSERTION: Should be at bottom (within 100px)
    assert distance_from_bottom < 100, (
        f"New session should auto-scroll to show welcome message. "
        f"Distance from bottom: {distance_from_bottom}px (expected < 100px)"
    )
