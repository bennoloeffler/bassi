"""
Simplified E2E tests for file upload feature.

Run with:
    pytest bassi/core_v3/tests/test_file_upload_simple_e2e.py -v --headed
"""

import time

import pytest

# Mark all tests in this module as E2E tests that must run in same xdist worker
pytestmark = [
    pytest.mark.integration,
    pytest.mark.e2e,
    pytest.mark.xdist_group(name="e2e_server"),
]


@pytest.fixture(autouse=True)
def cleanup_between_tests():
    """Ensure cleanup time between tests to allow SDK client to disconnect"""
    yield
    # Give the server time to fully disconnect SDK client before next test
    # 2 seconds needed for Claude Agent SDK client to fully disconnect
    time.sleep(2)


@pytest.fixture
def test_file(tmp_path):
    """Create a temporary test file for upload."""
    test_file = tmp_path / "test_document.txt"
    test_file.write_text("This is a test file for E2E testing.")
    return test_file


def test_ui_loads(page, live_server):
    """Test that the UI loads successfully."""
    page.goto(live_server)

    # Wait for connection
    page.wait_for_selector(
        "#connection-status:has-text('Connected')", timeout=10000
    )

    # Verify key elements exist
    assert page.query_selector("#message-input") is not None
    assert page.query_selector("#send-button") is not None
    assert page.query_selector("#upload-button") is not None

    print("✅ UI loaded successfully")


def test_file_input_exists(page, live_server):
    """Test that file input element exists."""
    page.goto(live_server)
    page.wait_for_selector(
        "#connection-status:has-text('Connected')", timeout=10000
    )

    # Verify file input exists
    file_input = page.query_selector('input[type="file"]')
    assert file_input is not None, "File input element should exist"

    # Verify it's hidden
    is_visible = file_input.is_visible()
    assert not is_visible, "File input should be hidden"

    print("✅ File input element exists and is hidden")


def test_upload_button_exists(page, live_server):
    """Test that upload button exists and is visible."""
    page.goto(live_server)
    page.wait_for_selector(
        "#connection-status:has-text('Connected')", timeout=10000
    )

    # Verify upload button exists and is visible
    upload_button = page.query_selector("#upload-button")
    assert upload_button is not None, "Upload button should exist"
    assert upload_button.is_visible(), "Upload button should be visible"

    # Verify button has correct icon
    button_text = upload_button.text_content()
    assert (
        "📎" in button_text
    ), f"Upload button should have paperclip icon, got: {button_text}"

    print("✅ Upload button exists and is visible")


def test_chips_container_hidden_initially(page, live_server):
    """Test that file chips container is hidden when no files are uploaded."""
    page.goto(live_server)
    page.wait_for_selector(
        "#connection-status:has-text('Connected')", timeout=10000
    )

    # File chips container should be hidden initially
    chips_container = page.query_selector("#file-chips-container")
    assert (
        chips_container is not None
    ), "File chips container element should exist"

    is_hidden = chips_container.is_hidden()
    assert is_hidden, "File chips container should be hidden when no files"

    print("✅ File chips container is hidden initially")


def test_upload_file_via_button(page, live_server, test_file):
    """Test uploading a file via the upload button."""
    # Listen to console messages
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

    if not session_ready:
        print("⚠️ Session not ready after waiting!")
        print("\n=== Console Messages ===")
        for msg in console_messages:
            print(msg)

    # Get file input
    file_input = page.query_selector('input[type="file"]')
    assert file_input is not None, "File input should exist"

    # Set file
    file_input.set_input_files(str(test_file))

    # Wait for file chips container to become visible (up to 10 seconds)
    try:
        page.wait_for_selector(
            "#file-chips-container.has-files", state="visible", timeout=10000
        )
    except Exception as e:
        # If timeout, print debug info
        chips_container = page.query_selector("#file-chips-container")
        print(f"Debug: Container exists: {chips_container is not None}")
        if chips_container:
            print(f"Debug: Container visible: {chips_container.is_visible()}")
            print(
                f"Debug: Container classes: {chips_container.get_attribute('class')}"
            )
            print(
                f"Debug: Container style: {chips_container.get_attribute('style')}"
            )

        # Print console messages
        print("\n=== Console Messages ===")
        for msg in console_messages:
            print(msg)
        raise e

    # Verify file chips container is visible
    chips_container = page.query_selector("#file-chips-container")
    assert (
        chips_container is not None
    ), "File chips container should exist after upload"

    is_visible = chips_container.is_visible()
    assert (
        is_visible
    ), "File chips container should be visible after file upload"

    # Verify file chip appears in container
    file_chip = page.query_selector(".file-chip")
    assert file_chip is not None, "File chip should appear in container"

    # Verify file name is displayed (with hash suffix from server)
    file_name_el = page.query_selector(".file-chip-name")
    assert file_name_el is not None, "File name element should exist"
    file_name = file_name_el.text_content()
    # Server adds hash to filename: test_document_{hash}.txt
    # So we check for the base name and extension separately
    assert (
        "test_document" in file_name and ".txt" in file_name
    ), f"File name should contain base name and extension, got: {file_name}"

    print(f"✅ File uploaded successfully to chips container: {file_name}")


def test_file_chip_remove(page, live_server, test_file):
    """Test removing a file chip from container."""
    page.goto(live_server)
    page.wait_for_selector(
        "#connection-status:has-text('Connected')", timeout=10000
    )

    # Wait for session ID to be set
    page.wait_for_timeout(2000)

    # Upload a file first
    file_input = page.query_selector('input[type="file"]')
    file_input.set_input_files(str(test_file))

    # Wait for chips to appear
    page.wait_for_selector(
        "#file-chips-container.has-files", state="visible", timeout=10000
    )

    # Verify chips container is visible
    chips_container = page.query_selector("#file-chips-container")
    assert (
        chips_container.is_visible()
    ), "File chips container should be visible"

    # Verify file chip exists
    file_chip = page.query_selector(".file-chip")
    assert file_chip is not None, "File chip should exist"

    # Click remove button (×)
    remove_button = page.query_selector(".file-chip-remove")
    assert remove_button is not None, "Remove button should exist"
    page.click(".file-chip-remove")
    page.wait_for_timeout(500)

    # Verify chips container is hidden after removing file
    is_hidden = chips_container.is_hidden()
    assert (
        is_hidden
    ), "File chips container should be hidden after removing last file"

    # Verify no chips remain
    chips = page.query_selector_all(".file-chip")
    assert len(chips) == 0, "No file chips should remain"

    print("✅ File chip removal works correctly")


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
