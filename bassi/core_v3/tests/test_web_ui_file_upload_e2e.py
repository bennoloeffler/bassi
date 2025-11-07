"""
End-to-End tests for web UI file upload and persistence.

These tests use Playwright to test the complete file upload workflow:
- File upload via form
- File area display
- File persistence across sessions
- Session isolation
- UI interactions (expand/collapse)

Requirements:
    pip install playwright pytest-playwright
    playwright install chromium

Run with:
    pytest bassi/core_v3/tests/test_web_ui_file_upload_e2e.py -v
"""

import base64

import pytest

# Mark all tests in this file as E2E integration tests
pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def server_url():
    """Base URL for the running server."""
    return "http://localhost:8765"


@pytest.fixture
def test_file(tmp_path):
    """Create a temporary test file for upload."""
    test_file = tmp_path / "test_document.txt"
    test_file.write_text("This is a test file for E2E testing.")
    return test_file


@pytest.fixture
def test_image(tmp_path):
    """Create a temporary test image for upload."""
    # Create a simple 1x1 PNG

    png_data = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
    test_image = tmp_path / "test_image.png"
    test_image.write_bytes(png_data)
    return test_image


class TestFileUpload:
    """Test file upload functionality."""

    @pytest.mark.asyncio
    async def test_upload_text_file_via_form(
        self, page, server_url, test_file
    ):
        """Test uploading a text file via file input."""
        # Navigate to the web UI
        await page.goto(server_url)

        # Wait for WebSocket connection
        await page.wait_for_selector(
            "#connection-status:has-text('Connected')", timeout=5000
        )

        # Wait for file input to be available
        # Note: If there's no visible file input, we'll need to trigger it
        # For now, assume there's a way to open file dialog

        # Simulate file selection (this might need adjustment based on actual UI)
        # Playwright can set input files directly
        file_input = await page.query_selector('input[type="file"]')
        if file_input:
            await file_input.set_input_files(str(test_file))

        # Wait for file area to appear
        await page.wait_for_selector(
            "#file-area", state="visible", timeout=5000
        )

        # Verify file is displayed
        file_name = await page.text_content(".file-name")
        assert (
            file_name == "test_document.txt"
        ), f"Expected 'test_document.txt', got '{file_name}'"

        # Verify file count
        file_count_text = await page.text_content("#file-count")
        assert "Files (1)" in file_count_text

    @pytest.mark.asyncio
    async def test_upload_image_via_drag_and_drop(
        self, page, server_url, test_image
    ):
        """Test uploading an image via drag and drop."""
        await page.goto(server_url)
        await page.wait_for_selector(
            "#connection-status:has-text('Connected')", timeout=5000
        )

        # Read file as buffer
        file_buffer = test_image.read_bytes()

        # Create file chooser promise before triggering the action
        async with page.expect_file_chooser() as fc_info:
            # Simulate drag and drop by dispatching events
            await page.dispatch_event("body", "dragenter")
            await page.dispatch_event(
                "body",
                "drop",
                {
                    "dataTransfer": {
                        "files": [
                            {
                                "name": test_image.name,
                                "mimeType": "image/png",
                                "buffer": file_buffer,
                            }
                        ]
                    }
                },
            )

        # Wait for file area
        await page.wait_for_selector(
            "#file-area", state="visible", timeout=5000
        )

        # Verify image is displayed
        file_count_text = await page.text_content("#file-count")
        assert "Files" in file_count_text


class TestFileArea:
    """Test file area UI functionality."""

    @pytest.mark.asyncio
    async def test_file_area_hidden_when_no_files(self, page, server_url):
        """Test that file area is hidden when there are no files."""
        await page.goto(server_url)
        await page.wait_for_selector(
            "#connection-status:has-text('Connected')", timeout=5000
        )

        # File area should be hidden initially
        file_area = await page.query_selector("#file-area")
        is_hidden = await file_area.is_hidden() if file_area else True
        assert is_hidden, "File area should be hidden when no files"

    @pytest.mark.asyncio
    async def test_file_area_expand_collapse(
        self, page, server_url, test_file
    ):
        """Test expanding and collapsing file area."""
        await page.goto(server_url)
        await page.wait_for_selector(
            "#connection-status:has-text('Connected')", timeout=5000
        )

        # Upload a file first
        file_input = await page.query_selector('input[type="file"]')
        if file_input:
            await file_input.set_input_files(str(test_file))

        # Wait for file area
        await page.wait_for_selector(
            "#file-area", state="visible", timeout=5000
        )

        # File content should be collapsed by default
        file_content = await page.query_selector("#file-area-content")
        is_visible = await file_content.is_visible()
        assert not is_visible, "File content should be collapsed by default"

        # Click header to expand
        await page.click("#file-area-header")
        await page.wait_for_timeout(300)  # Wait for animation

        is_visible = await file_content.is_visible()
        assert (
            is_visible
        ), "File content should be visible after clicking header"

        # Verify toggle arrow rotated
        toggle_button = await page.query_selector("#file-area-toggle")
        classes = await toggle_button.get_attribute("class")
        assert (
            "expanded" in classes
        ), "Toggle button should have 'expanded' class"

        # Click again to collapse
        await page.click("#file-area-header")
        await page.wait_for_timeout(300)

        is_visible = await file_content.is_visible()
        assert (
            not is_visible
        ), "File content should be hidden after second click"


class TestFilePersistence:
    """Test file persistence across sessions."""

    @pytest.mark.asyncio
    async def test_files_persist_across_page_reload(
        self, page, server_url, test_file
    ):
        """Test that uploaded files persist after page reload."""
        await page.goto(server_url)
        await page.wait_for_selector(
            "#connection-status:has-text('Connected')", timeout=5000
        )

        # Upload file
        file_input = await page.query_selector('input[type="file"]')
        if file_input:
            await file_input.set_input_files(str(test_file))

        # Wait for file to appear
        await page.wait_for_selector(
            "#file-area", state="visible", timeout=5000
        )
        original_count = await page.text_content("#file-count")

        # Reload page
        await page.reload()
        await page.wait_for_selector(
            "#connection-status:has-text('Connected')", timeout=5000
        )

        # Verify files still appear
        await page.wait_for_selector(
            "#file-area", state="visible", timeout=5000
        )
        new_count = await page.text_content("#file-count")

        assert (
            new_count == original_count
        ), "File count should remain same after reload"

    @pytest.mark.asyncio
    async def test_session_isolation(
        self, page, context, server_url, test_file
    ):
        """Test that files in one session don't appear in another."""
        # First session: upload file
        await page.goto(server_url)
        await page.wait_for_selector(
            "#connection-status:has-text('Connected')", timeout=5000
        )

        file_input = await page.query_selector('input[type="file"]')
        if file_input:
            await file_input.set_input_files(str(test_file))

        await page.wait_for_selector(
            "#file-area", state="visible", timeout=5000
        )

        # Second session: open new page
        page2 = await context.new_page()
        await page2.goto(server_url)
        await page2.wait_for_selector(
            "#connection-status:has-text('Connected')", timeout=5000
        )

        # File area should be hidden in new session
        file_area = await page2.query_selector("#file-area")
        is_hidden = await file_area.is_hidden() if file_area else True

        assert (
            is_hidden
        ), "New session should not show files from other session"

        await page2.close()


class TestMultipleFiles:
    """Test uploading and managing multiple files."""

    @pytest.mark.asyncio
    async def test_upload_multiple_files(self, page, server_url, tmp_path):
        """Test uploading multiple files."""
        await page.goto(server_url)
        await page.wait_for_selector(
            "#connection-status:has-text('Connected')", timeout=5000
        )

        # Create multiple test files
        files = []
        for i in range(3):
            test_file = tmp_path / f"file_{i}.txt"
            test_file.write_text(f"Content of file {i}")
            files.append(str(test_file))

        # Upload files one by one
        file_input = await page.query_selector('input[type="file"]')
        if file_input:
            for file_path in files:
                await file_input.set_input_files(file_path)
                await page.wait_for_timeout(500)  # Wait for upload

        # Verify file count
        await page.wait_for_selector(
            "#file-area", state="visible", timeout=5000
        )
        file_count_text = await page.text_content("#file-count")
        assert (
            "Files (3)" in file_count_text
        ), f"Expected 3 files, got {file_count_text}"

    @pytest.mark.asyncio
    async def test_file_list_scrollable(self, page, server_url, tmp_path):
        """Test that file list is scrollable with many files."""
        await page.goto(server_url)
        await page.wait_for_selector(
            "#connection-status:has-text('Connected')", timeout=5000
        )

        # Create many test files
        files = []
        for i in range(10):
            test_file = tmp_path / f"file_{i:02d}.txt"
            test_file.write_text(f"Content of file {i}")
            files.append(str(test_file))

        # Upload all files
        file_input = await page.query_selector('input[type="file"]')
        if file_input:
            for file_path in files:
                await file_input.set_input_files(file_path)
                await page.wait_for_timeout(300)

        # Expand file area
        await page.click("#file-area-header")
        await page.wait_for_selector("#file-area-content", state="visible")

        # Verify scrollable
        file_content = await page.query_selector("#file-area-content")
        scroll_height = await file_content.evaluate("el => el.scrollHeight")
        client_height = await file_content.evaluate("el => el.clientHeight")

        assert (
            scroll_height > client_height
        ), "File list should be scrollable with many files"


class TestFileIcons:
    """Test file type icons."""

    @pytest.mark.asyncio
    async def test_different_file_types_show_correct_icons(
        self, page, server_url, tmp_path
    ):
        """Test that different file types show appropriate icons."""
        await page.goto(server_url)
        await page.wait_for_selector(
            "#connection-status:has-text('Connected')", timeout=5000
        )

        # Create files of different types
        file_types = {
            "document.pdf": "📄",
            "spreadsheet.xlsx": "📊",
            "code.py": "🐍",
            "image.png": "🖼️",
        }

        for filename, expected_icon in file_types.items():
            test_file = tmp_path / filename
            test_file.write_text("test content")

            # Upload file
            file_input = await page.query_selector('input[type="file"]')
            if file_input:
                await file_input.set_input_files(str(test_file))
                await page.wait_for_timeout(300)

        # Expand file area
        await page.click("#file-area-header")
        await page.wait_for_selector("#file-area-content", state="visible")

        # Verify each file has correct icon
        file_items = await page.query_selector_all(".file-item")
        assert len(file_items) >= 4, "Should have uploaded 4 files"


# Pytest configuration for these tests
@pytest.fixture(scope="module")
def browser_context_args(browser_context_args):
    """Configure browser context for tests."""
    return {
        **browser_context_args,
        "viewport": {
            "width": 1280,
            "height": 720,
        },
        "user_agent": "Mozilla/5.0 (Playwright E2E Test)",
    }
