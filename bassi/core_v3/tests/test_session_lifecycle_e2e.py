"""
End-to-end tests covering session creation, listing, and deletion flows.
"""

import pytest

# Ensure tests run serially with the shared live_server instance
pytestmark = [
    pytest.mark.integration,
    pytest.mark.e2e,
    pytest.mark.xdist_group(name="e2e_server"),
]


def _wait_for_initial_session(page):
    page.wait_for_selector(
        "#connection-status:has-text('Connected')", timeout=15000
    )
    handle = page.wait_for_function(
        "() => (window.bassiClient && window.bassiClient.sessionId) || null",
        timeout=15000,
    )
    return handle.json_value()


def _wait_for_new_session(page, previous_id):
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
    page.fill("#message-input", text)
    page.click("#send-button")
    page.wait_for_selector(
        f".user-message .message-content:has-text('{text}')", timeout=10000
    )
    page.wait_for_function(
        "() => window.bassiClient && window.bassiClient.isAgentWorking === false",
        timeout=10000,
    )


def _ensure_sidebar_open(page):
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
    page.evaluate(
        "async () => { if (window.bassiClient?.loadSessions) { await window.bassiClient.loadSessions(); } }"
    )


def _wait_for_session_rows(page, expected_count):
    page.wait_for_function(
        """(count) => {
            const nodes = document.querySelectorAll('#session-list .session-item')
            return nodes.length >= count
        }""",
        arg=expected_count,
        timeout=10000,
    )


def _get_session_ids(page):
    return page.eval_on_selector_all(
        "#session-list .session-item",
        "nodes => nodes.map(node => node.dataset.sessionId)",
    )


def test_session_lifecycle_create_switch_delete(page, live_server):
    """Create two sessions via the UI and verify list/deletion workflow."""
    page.goto(live_server)
    first_session_id = _wait_for_initial_session(page)

    _send_message(page, "First session message")
    _ensure_sidebar_open(page)
    _refresh_sessions(page)
    _wait_for_session_rows(page, 1)
    assert first_session_id in _get_session_ids(page)

    # Create second session
    page.click("#new-session-button")
    page.wait_for_selector(
        "#connection-status:has-text('Connected')", timeout=15000
    )
    second_session_id = _wait_for_new_session(page, first_session_id)

    _send_message(page, "Second session message")
    _ensure_sidebar_open(page)
    _refresh_sessions(page)
    _wait_for_session_rows(page, 2)
    session_ids = _get_session_ids(page)
    assert first_session_id in session_ids
    assert second_session_id in session_ids

    # Delete the first (now inactive) session (auto-accept confirm)
    page.evaluate(
        """() => {
            window._testConfirm = window.confirm
            window.confirm = () => true
        }"""
    )
    page.evaluate(
        "sid => window.bassiClient.deleteSession(sid)", first_session_id
    )
    page.evaluate(
        """() => {
            if (window._testConfirm) {
                window.confirm = window._testConfirm
                delete window._testConfirm
            }
        }"""
    )

    _ensure_sidebar_open(page)
    _refresh_sessions(page)
    page.wait_for_function(
        """(target) => {
            return Array.from(document.querySelectorAll('#session-list .session-item'))
                .every(node => node.dataset.sessionId !== target)
        }""",
        arg=first_session_id,
        timeout=10000,
    )

    remaining_ids = _get_session_ids(page)
    assert first_session_id not in remaining_ids
    assert second_session_id in remaining_ids
