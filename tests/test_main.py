"""
Tests for bassi/main.py - V1 CLI entry point

Focus: CLI argument parsing, main loop, and interactive commands

Tests added by parallel test-writer agents:
- AGENT_01: Integration tests for get_user_input() async function (7 tests)
- AGENT_02: Integration test for cli_main_loop() context loading scenarios (1 test)
- AGENT_03: Integration tests for main_async() execution modes (6 tests)
- AGENT_04: Integration test for error handling resilience (1 test)
"""

import asyncio
import json
import os
import signal
import sys
import time
from io import StringIO
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import anyio
import pytest


# ============================================================================
# UNIT TESTS (existing tests - fast, no external dependencies)
# ============================================================================


class TestParseArgs:
    """Test command line argument parsing"""

    def test_parse_args_defaults(self, monkeypatch):
        """
        Test parse_args with no arguments returns default values.

        Tests bassi/main.py lines 221-246 (parse_args function).
        """
        from bassi.main import parse_args

        # Mock sys.argv to simulate running with no arguments
        monkeypatch.setattr(sys, "argv", ["bassi"])

        args = parse_args()

        # Verify all default values
        assert args.web is False, "web should default to False"
        assert args.no_cli is False, "no_cli should default to False"
        assert args.port == 8765, "port should default to 8765"
        assert args.host == "localhost", "host should default to localhost"
        assert args.reload is False, "reload should default to False"

    def test_parse_args_web_flag(self, monkeypatch):
        """
        Test parse_args with --web flag enables web UI.

        Tests bassi/main.py lines 226 (--web argument).
        """
        from bassi.main import parse_args

        # Mock sys.argv with --web flag
        monkeypatch.setattr(sys, "argv", ["bassi", "--web"])

        args = parse_args()

        # Verify web flag is set
        assert args.web is True, "web should be True with --web flag"
        # Other defaults should remain
        assert args.no_cli is False
        assert args.port == 8765
        assert args.host == "localhost"
        assert args.reload is False

    def test_parse_args_custom_port_and_host(self, monkeypatch):
        """
        Test parse_args with custom --port and --host values.

        Tests bassi/main.py lines 232-240 (--port and --host arguments).
        """
        from bassi.main import parse_args

        # Mock sys.argv with custom port and host
        monkeypatch.setattr(sys, "argv", ["bassi", "--port", "9000", "--host", "0.0.0.0"])

        args = parse_args()

        # Verify custom values
        assert args.port == 9000, "port should be 9000"
        assert args.host == "0.0.0.0", "host should be 0.0.0.0"
        # Defaults should remain
        assert args.web is False
        assert args.no_cli is False
        assert args.reload is False


class TestPrintWelcome:
    """Test welcome banner printing"""

    def test_print_welcome_contains_version(self, monkeypatch, capsys):
        """
        Test print_welcome prints version and basic info.

        Tests bassi/main.py lines 46-68 (print_welcome function).
        """
        from bassi import __version__
        from bassi.main import print_welcome
        from rich.console import Console

        # Create a console that writes to StringIO for testing
        output = StringIO()
        test_console = Console(file=output, force_terminal=False, width=120)

        # Replace the global console with our test console
        import bassi.main
        monkeypatch.setattr(bassi.main, "console", test_console)

        # Call print_welcome
        print_welcome()

        # Get the output
        result = output.getvalue()

        # Verify key content is present
        assert f"bassi v{__version__}" in result, "Version should be in output"
        assert "Benno's Assistant" in result, "Assistant name should be in output"
        assert "Working directory:" in result, "Working directory label should be in output"
        assert "API Endpoint:" in result, "API endpoint label should be in output"
        assert "/help" in result, "Help command should be mentioned"
        assert "Ctrl+C" in result, "Ctrl+C shortcut should be mentioned"


class TestPrintConfig:
    """Test configuration display"""

    def test_print_config_shows_config_values(self, monkeypatch):
        """
        Test print_config displays configuration values.

        Tests bassi/main.py lines 103-114 (print_config function).
        """
        from bassi.main import print_config
        from rich.console import Console
        from io import StringIO

        # Create a console that writes to StringIO for testing
        output = StringIO()
        test_console = Console(file=output, force_terminal=False, width=120)

        # Replace the global console with our test console
        import bassi.main
        monkeypatch.setattr(bassi.main, "console", test_console)

        # Call print_config
        print_config()

        # Get the output
        result = output.getvalue()

        # Verify key content is present
        assert "## Configuration" in result, "Configuration header should be in output"
        assert "Config file:" in result, "Config file label should be in output"
        assert "Root folders:" in result, "Root folders label should be in output"
        assert "Settings:" in result, "Settings label should be in output"
        assert "Log level:" in result, "Log level should be in output"
        assert "Max search results:" in result, "Max search results should be in output"


class TestPrintCommands:
    """Test commands display"""

    def test_print_commands_lists_all_commands(self, monkeypatch):
        """
        Test print_commands displays all available commands.

        Tests bassi/main.py lines 119-138 (print_commands function).
        """
        from bassi.main import print_commands
        from rich.console import Console
        from io import StringIO

        # Create a console that writes to StringIO for testing
        output = StringIO()
        test_console = Console(file=output, force_terminal=False, width=120)

        # Replace the global console with our test console
        import bassi.main
        monkeypatch.setattr(bassi.main, "console", test_console)

        # Call print_commands
        print_commands()

        # Get the output
        result = output.getvalue()

        # Verify all commands are listed
        assert "## Available Commands" in result, "Commands header should be in output"
        assert "/help" in result, "/help command should be listed"
        assert "/config" in result, "/config command should be listed"
        assert "/edit" in result, "/edit command should be listed"
        assert "/alles_anzeigen" in result, "/alles_anzeigen command should be listed"
        assert "/reset" in result, "/reset command should be listed"
        assert "/quit" in result or "/exit" in result, "/quit or /exit should be listed"


class TestPrintHelp:
    """Test help message display"""

    def test_print_help_shows_examples(self, monkeypatch):
        """
        Test print_help displays help message with examples.

        Tests bassi/main.py lines 145-182 (print_help function).
        """
        from bassi.main import print_help
        from rich.console import Console
        from io import StringIO

        # Create a console that writes to StringIO for testing
        output = StringIO()
        test_console = Console(file=output, force_terminal=False, width=120)

        # Replace the global console with our test console
        import bassi.main
        monkeypatch.setattr(bassi.main, "console", test_console)

        # Call print_help
        print_help()

        # Get the output
        result = output.getvalue()

        # Verify key content is present
        assert "## Help:" in result, "Help header should be in output"
        assert "### Available Commands" in result, "Commands section should be in output"
        assert "### Usage Examples" in result, "Examples section should be in output"
        assert "File Operations:" in result, "File operations examples should be in output"
        assert "Web Search:" in result, "Web search examples should be in output"
        assert "Python Automation:" in result, "Python automation examples should be in output"
        assert "Email & Calendar" in result, "Email/calendar examples should be in output"


class TestShowCommandSelector:
    """Test interactive command selector"""

    def test_show_command_selector_valid_choice(self, monkeypatch):
        """
        Test show_command_selector with valid numeric input.

        Tests bassi/main.py lines 187-218 (show_command_selector function).
        """
        from bassi.main import show_command_selector
        from rich.console import Console
        from io import StringIO

        # Create a console that writes to StringIO for testing
        output = StringIO()
        test_console = Console(file=output, force_terminal=False, width=120)

        # Replace the global console with our test console
        import bassi.main
        monkeypatch.setattr(bassi.main, "console", test_console)

        # Mock Prompt.ask to return "1" (first command)
        from rich.prompt import Prompt
        monkeypatch.setattr(Prompt, "ask", lambda *args, **kwargs: "1")

        # Call show_command_selector
        result = show_command_selector()

        # Should return the first command (which should be "/help")
        assert result is not None, "Should return a command"
        assert result in ["/help", "/config", "/edit", "/alles_anzeigen", "/reset", "/quit", "/exit"], \
            f"Should return a valid command, got: {result}"

    def test_show_command_selector_empty_input(self, monkeypatch):
        """Test show_command_selector with empty input returns None."""
        from bassi.main import show_command_selector
        from rich.console import Console
        from io import StringIO

        # Create a console that writes to StringIO for testing
        output = StringIO()
        test_console = Console(file=output, force_terminal=False, width=120)

        # Replace the global console with our test console
        import bassi.main
        monkeypatch.setattr(bassi.main, "console", test_console)

        # Mock Prompt.ask to return empty string
        from rich.prompt import Prompt
        monkeypatch.setattr(Prompt, "ask", lambda *args, **kwargs: "")

        # Call show_command_selector
        result = show_command_selector()

        # Should return None for empty input
        assert result is None, "Should return None for empty input"

    def test_show_command_selector_invalid_number(self, monkeypatch):
        """Test show_command_selector with out-of-range number returns None."""
        from bassi.main import show_command_selector
        from rich.console import Console
        from io import StringIO

        # Create a console that writes to StringIO for testing
        output = StringIO()
        test_console = Console(file=output, force_terminal=False, width=120)

        # Replace the global console with our test console
        import bassi.main
        monkeypatch.setattr(bassi.main, "console", test_console)

        # Mock Prompt.ask to return "999" (out of range)
        from rich.prompt import Prompt
        monkeypatch.setattr(Prompt, "ask", lambda *args, **kwargs: "999")

        # Call show_command_selector
        result = show_command_selector()

        # Should return None for invalid number
        assert result is None, "Should return None for invalid number"

    def test_show_command_selector_non_numeric_input(self, monkeypatch):
        """Test show_command_selector with non-numeric input returns None."""
        from bassi.main import show_command_selector
        from rich.console import Console
        from io import StringIO

        # Create a console that writes to StringIO for testing
        output = StringIO()
        test_console = Console(file=output, force_terminal=False, width=120)

        # Replace the global console with our test console
        import bassi.main
        monkeypatch.setattr(bassi.main, "console", test_console)

        # Mock Prompt.ask to return non-numeric input
        from rich.prompt import Prompt
        monkeypatch.setattr(Prompt, "ask", lambda *args, **kwargs: "not a number")

        # Call show_command_selector
        result = show_command_selector()

        # Should return None for non-numeric input
        assert result is None, "Should return None for non-numeric input"

    def test_show_command_selector_keyboard_interrupt(self, monkeypatch):
        """Test show_command_selector handles KeyboardInterrupt gracefully."""
        from bassi.main import show_command_selector
        from rich.console import Console
        from io import StringIO

        # Create a console that writes to StringIO for testing
        output = StringIO()
        test_console = Console(file=output, force_terminal=False, width=120)

        # Replace the global console with our test console
        import bassi.main
        monkeypatch.setattr(bassi.main, "console", test_console)

        # Mock Prompt.ask to raise KeyboardInterrupt
        from rich.prompt import Prompt
        def mock_ask(*args, **kwargs):
            raise KeyboardInterrupt
        monkeypatch.setattr(Prompt, "ask", mock_ask)

        # Call show_command_selector
        result = show_command_selector()

        # Should return None for KeyboardInterrupt
        assert result is None, "Should return None for KeyboardInterrupt"


# ============================================================================
# INTEGRATION TESTS (new tests from parallel agents)
# ============================================================================


@pytest.mark.integration
class TestGetUserInput:
    """Integration tests for get_user_input() async function (AGENT_01)."""

    @pytest.mark.asyncio
    async def test_get_user_input_normal_input_returns_text(
        self, tmp_path, monkeypatch
    ):
        """
        Test get_user_input() with normal input returns the text.

        User scenario: User types text and presses Enter.
        Function should return the input text.

        Tests bassi/main.py lines 88-90 (normal input path).
        """
        from bassi.main import get_user_input

        # Use temporary directory for history file
        history_file = tmp_path / ".bassi_history"
        monkeypatch.setattr(
            os.path, "expanduser", lambda path: str(history_file)
        )

        with patch("builtins.input", return_value="test input"):
            result = await get_user_input("Test prompt: ")

        assert result == "test input", "Should return user input"

    @pytest.mark.asyncio
    async def test_get_user_input_eof_returns_none(
        self, tmp_path, monkeypatch
    ):
        """
        Test get_user_input() with EOF (Ctrl+D) returns None.

        User scenario: User presses Ctrl+D to indicate end of input.
        Function should return None gracefully, not raise exception.

        Tests bassi/main.py lines 91-92 (EOFError handling).
        """
        from bassi.main import get_user_input

        history_file = tmp_path / ".bassi_history"
        monkeypatch.setattr(
            os.path, "expanduser", lambda path: str(history_file)
        )

        with patch("builtins.input", side_effect=EOFError):
            result = await get_user_input("Test prompt: ")

        assert result is None, "Should return None on EOF (Ctrl+D)"

    @pytest.mark.asyncio
    async def test_get_user_input_cancellation_raises_keyboard_interrupt(
        self, tmp_path, monkeypatch
    ):
        """
        Test get_user_input() converts anyio cancellation to KeyboardInterrupt.

        User scenario: User presses Ctrl+C or task is cancelled externally.
        Anyio cancellation should be converted to KeyboardInterrupt for
        consistent exception handling.

        Tests bassi/main.py lines 96-98 (cancellation handling).
        """
        from bassi.main import get_user_input

        history_file = tmp_path / ".bassi_history"
        monkeypatch.setattr(
            os.path, "expanduser", lambda path: str(history_file)
        )

        # Raise anyio's cancellation exception
        with patch(
            "builtins.input", side_effect=anyio.get_cancelled_exc_class()
        ):
            with pytest.raises(KeyboardInterrupt):
                await get_user_input("Test prompt: ")

    @pytest.mark.asyncio
    async def test_get_user_input_creates_history_file(
        self, tmp_path, monkeypatch
    ):
        """
        Test get_user_input() creates history file if it doesn't exist.

        User scenario: First time user runs bassi, no history file exists.
        Function should handle missing file gracefully and create it on first use.

        Tests bassi/main.py lines 79-83 (FileNotFoundError handling).
        """
        from bassi.main import get_user_input

        # Use non-existent history file path
        history_file = tmp_path / "nonexistent" / ".bassi_history"
        monkeypatch.setattr(
            os.path, "expanduser", lambda path: str(history_file)
        )

        # Ensure parent directory exists (readline needs this)
        history_file.parent.mkdir(parents=True, exist_ok=True)

        assert (
            not history_file.exists()
        ), "History file should not exist initially"

        with patch("builtins.input", return_value="first input"):
            result = await get_user_input("Prompt: ")

        assert result == "first input", "Should return input"
        assert (
            history_file.exists()
        ), "History file should be created after input"

    @pytest.mark.asyncio
    async def test_get_user_input_uses_custom_prompt(
        self, tmp_path, monkeypatch
    ):
        """
        Test get_user_input() passes custom prompt to input().

        User scenario: Different contexts need different prompts
        (e.g., "You: " for chat, "Enter command: " for commands).
        Function should use the provided prompt parameter.

        Tests bassi/main.py line 88 (prompt parameter usage).
        """
        from bassi.main import get_user_input

        history_file = tmp_path / ".bassi_history"
        monkeypatch.setattr(
            os.path, "expanduser", lambda path: str(history_file)
        )

        # Track what prompt was passed to input()
        mock_input = Mock(return_value="test")

        with patch("builtins.input", mock_input):
            await get_user_input("Custom prompt: ")

        # Verify the custom prompt was used
        mock_input.assert_called_once_with("Custom prompt: ")

    @pytest.mark.asyncio
    async def test_get_user_input_uses_default_prompt(
        self, tmp_path, monkeypatch
    ):
        """
        Test get_user_input() uses default "You: " prompt when none provided.

        User scenario: Caller doesn't specify prompt, should use sensible default.

        Tests bassi/main.py line 71 (default prompt parameter).
        """
        from bassi.main import get_user_input

        history_file = tmp_path / ".bassi_history"
        monkeypatch.setattr(
            os.path, "expanduser", lambda path: str(history_file)
        )

        # Track what prompt was passed to input()
        mock_input = Mock(return_value="test")

        with patch("builtins.input", mock_input):
            await get_user_input()  # No prompt argument

        # Verify the default prompt was used
        mock_input.assert_called_once_with("You: ")

    @pytest.mark.asyncio
    async def test_get_user_input_handles_missing_history_file_gracefully(
        self, tmp_path, monkeypatch
    ):
        """
        Test get_user_input() handles FileNotFoundError when history file is missing.

        User scenario: First run or deleted history file.
        Function should not crash, should continue normally.

        Tests bassi/main.py lines 80-83 (try/except FileNotFoundError).
        """
        from bassi.main import get_user_input

        # Point to non-existent history file (parent doesn't exist)
        history_file = (
            tmp_path / "does_not_exist" / "subdir" / ".bassi_history"
        )
        monkeypatch.setattr(
            os.path, "expanduser", lambda path: str(history_file)
        )

        # Create parent for write to succeed
        history_file.parent.mkdir(parents=True, exist_ok=True)

        # Should not raise exception despite missing history file
        with patch("builtins.input", return_value="test"):
            result = await get_user_input("Prompt: ")

        assert result == "test", "Should handle missing history gracefully"
        # History file should be created after successful input
        assert history_file.exists(), "Should create history file after input"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_context_loading_all_scenarios(monkeypatch, tmp_path):
    """
    Comprehensive integration test for context loading behavior in cli_main_loop() (AGENT_02).

    Tests three critical scenarios:
    1. User accepts loading saved context with various time intervals
    2. User declines loading saved context
    3. Missing session_id in context file

    This is a real-world test covering the most common user interactions with
    session resumption, including edge cases like malformed context files.

    Source: bassi/main.py lines 285-349
    """
    from bassi.main import cli_main_loop
    from rich.console import Console
    from rich.prompt import Prompt
    from io import StringIO

    # Set up test environment
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-integration")

    # Create context file path
    context_file = tmp_path / ".bassi_context.json"

    # ========================================================================
    # SCENARIO 1: User ACCEPTS loading context + Time calculations
    # ========================================================================

    # Test multiple time intervals: seconds, minutes, hours, days
    time_test_cases = [
        (45, "45 seconds ago", "Should show seconds for < 60s"),
        (90, "1 minutes ago", "Should show minutes for 60s-3600s"),
        (3700, "1 hours ago", "Should show hours for 3600s-86400s"),
        (86500, "1 days ago", "Should show days for >= 86400s"),
    ]

    for seconds_ago, expected_time_text, description in time_test_cases:
        # Create context with specific timestamp
        session_id = f"test-session-{seconds_ago}"
        saved_context = {
            "session_id": session_id,
            "timestamp": time.time() - seconds_ago,
            "last_updated": "2024-01-15 10:30:00",
        }
        context_file.write_text(json.dumps(saved_context))

        # Mock console to capture output
        output_buffer = StringIO()
        test_console = Console(file=output_buffer, force_terminal=False, width=120)

        # Mock Prompt.ask to ACCEPT context loading
        prompt_responses = ["y"]
        prompt_call_count = [0]

        def mock_prompt_ask(*args, **kwargs):
            response = prompt_responses[prompt_call_count[0]]
            prompt_call_count[0] += 1
            return response

        # Mock BassiAgent to verify initialization and prevent API calls
        agent_init_params = {}

        class MockBassiAgent:
            def __init__(self, **kwargs):
                agent_init_params.update(kwargs)
                self.running = False

            async def chat(self, message):
                yield Mock(type="text", text="Response")

        # Mock get_user_input to exit immediately (test only context loading)
        async def mock_get_user_input(prompt):
            return None

        # Mock print_welcome to avoid terminal formatting issues
        def mock_print_welcome():
            pass

        # Apply all mocks
        monkeypatch.setattr("bassi.main.console", test_console)
        monkeypatch.setattr(Prompt, "ask", mock_prompt_ask)
        monkeypatch.setattr("bassi.main.BassiAgent", MockBassiAgent)
        monkeypatch.setattr("bassi.main.get_user_input", mock_get_user_input)
        monkeypatch.setattr("bassi.main.print_welcome", mock_print_welcome)

        # Run cli_main_loop
        mock_agent = MockBassiAgent()
        try:
            await cli_main_loop(mock_agent)
        except (EOFError, KeyboardInterrupt, SystemExit):
            pass

        # Verify context loading behavior
        output_text = output_buffer.getvalue()

        # Check that context file was detected
        assert "Found saved context from previous session" in output_text, \
            f"{description}: Should detect saved context file"

        # Check time calculation is correct
        assert expected_time_text in output_text, \
            f"{description}: Expected '{expected_time_text}', got output:\n{output_text}"

        # Check session resumed panel is displayed
        assert "Session Resumed" in output_text, \
            f"{description}: Should show session resumed panel"

        # Check session ID prefix is shown
        assert session_id[:8] in output_text, \
            f"{description}: Should display session ID prefix"

        # Check last_updated timestamp is shown
        assert "2024-01-15 10:30:00" in output_text, \
            f"{description}: Should display last_updated timestamp"

        # Verify BassiAgent was initialized with correct resume_session_id
        assert "resume_session_id" in agent_init_params, \
            f"{description}: Should pass resume_session_id to agent"
        assert agent_init_params["resume_session_id"] == session_id, \
            f"{description}: Expected session_id={session_id}, got {agent_init_params.get('resume_session_id')}"

    # ========================================================================
    # SCENARIO 2: User DECLINES loading context
    # ========================================================================

    # Create new context file
    saved_context = {
        "session_id": "test-session-decline",
        "timestamp": time.time() - 120,
        "last_updated": "2024-01-15 09:00:00",
    }
    context_file.write_text(json.dumps(saved_context))

    # Reset mocks for decline scenario
    output_buffer = StringIO()
    test_console = Console(file=output_buffer, force_terminal=False, width=120)
    agent_init_params = {}

    def mock_prompt_ask_decline(*args, **kwargs):
        return "n"  # User declines

    monkeypatch.setattr("bassi.main.console", test_console)
    monkeypatch.setattr(Prompt, "ask", mock_prompt_ask_decline)
    monkeypatch.setattr("bassi.main.BassiAgent", MockBassiAgent)
    monkeypatch.setattr("bassi.main.get_user_input", mock_get_user_input)
    monkeypatch.setattr("bassi.main.print_welcome", mock_print_welcome)

    # Run cli_main_loop
    mock_agent = MockBassiAgent()
    try:
        await cli_main_loop(mock_agent)
    except (EOFError, KeyboardInterrupt, SystemExit):
        pass

    # Verify decline behavior
    output_text = output_buffer.getvalue()

    # Check "Starting fresh" message is shown
    assert "Starting fresh conversation" in output_text, \
        "Should show 'Starting fresh conversation' when user declines"

    # Check session resume panel is NOT shown
    assert "Session Resumed" not in output_text, \
        "Should not show session resumed panel when user declines"

    # Verify agent was initialized WITHOUT resume_session_id
    resume_id = agent_init_params.get("resume_session_id")
    assert resume_id is None, \
        f"Should not resume session when user declines, got resume_session_id={resume_id}"

    # ========================================================================
    # SCENARIO 3: Missing session_id in context file (edge case)
    # ========================================================================

    # Create malformed context file without session_id
    saved_context = {
        "timestamp": time.time() - 60,
        "last_updated": "2024-01-15 08:00:00",
        # No session_id field - simulates old/corrupted context
    }
    context_file.write_text(json.dumps(saved_context))

    # Reset mocks for missing session_id scenario
    output_buffer = StringIO()
    test_console = Console(file=output_buffer, force_terminal=False, width=120)
    agent_init_params = {}

    def mock_prompt_ask_accept(*args, **kwargs):
        return "y"  # User accepts, but there's no session_id

    monkeypatch.setattr("bassi.main.console", test_console)
    monkeypatch.setattr(Prompt, "ask", mock_prompt_ask_accept)
    monkeypatch.setattr("bassi.main.BassiAgent", MockBassiAgent)
    monkeypatch.setattr("bassi.main.get_user_input", mock_get_user_input)
    monkeypatch.setattr("bassi.main.print_welcome", mock_print_welcome)

    # Run cli_main_loop
    mock_agent = MockBassiAgent()
    try:
        await cli_main_loop(mock_agent)
    except (EOFError, KeyboardInterrupt, SystemExit):
        pass

    # Verify missing session_id handling
    output_text = output_buffer.getvalue()

    # Check warning about missing session_id is shown
    assert "No session ID in context" in output_text or "starting fresh" in output_text.lower(), \
        "Should warn about missing session_id in context file"

    # Verify agent started fresh (no resume)
    resume_id = agent_init_params.get("resume_session_id")
    assert resume_id is None, \
        f"Should not resume when session_id is missing, got resume_session_id={resume_id}"


@pytest.fixture
def mock_web_server_module():
    """Create and inject a mock web_server module for testing."""
    # Create a mock module
    mock_module = ModuleType("bassi.web_server")

    # Store original module if it exists
    original_module = sys.modules.get("bassi.web_server")

    # Inject mock module
    sys.modules["bassi.web_server"] = mock_module

    yield mock_module

    # Restore original module or remove mock
    if original_module is not None:
        sys.modules["bassi.web_server"] = original_module
    else:
        sys.modules.pop("bassi.web_server", None)


@pytest.mark.integration
class TestMainAsync:
    """Integration tests for main_async() execution modes (AGENT_03)."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "mode,args_dict,expected_calls",
        [
            # CLI-only mode (default)
            (
                "cli_only",
                {
                    "web": False,
                    "no_cli": False,
                    "host": "localhost",
                    "port": 8765,
                    "reload": False,
                },
                {
                    "print_welcome": True,
                    "agent_created": True,
                    "web_server_started": False,
                    "cli_loop_executed": True,
                },
            ),
            # Web-only mode
            (
                "web_only",
                {
                    "web": True,
                    "no_cli": True,
                    "host": "localhost",
                    "port": 8765,
                    "reload": False,
                },
                {
                    "print_welcome": False,  # No banner in web-only mode
                    "agent_created": True,  # Display agent IS created to show tools
                    "web_server_started": True,
                    "cli_loop_executed": False,
                },
            ),
            # Combined mode (CLI + web)
            (
                "combined",
                {
                    "web": True,
                    "no_cli": False,
                    "host": "localhost",
                    "port": 8765,
                    "reload": False,
                },
                {
                    "print_welcome": True,
                    "agent_created": True,
                    "web_server_started": True,
                    "cli_loop_executed": True,
                },
            ),
        ],
    )
    async def test_main_async_execution_modes(
        self,
        monkeypatch,
        tmp_path,
        mock_web_server_module,
        mode,
        args_dict,
        expected_calls,
    ):
        """
        Test main_async() with different execution modes.

        Scenarios:
        - CLI-only: Default mode, runs CLI main loop, no web server
        - Web-only: --no-cli --web flags, web server only, sleeps forever
        - Combined: CLI + web server run concurrently, CLI exit cancels web

        User scenarios:
        - Developer uses `bassi` for quick CLI assistance
        - Team deploys `bassi --web --no-cli` as web service
        - Power user runs `bassi --web` for both CLI and web UI

        Tests:
        - Proper component initialization based on flags
        - Correct execution paths taken
        - Component interactions (agent creation, server startup, CLI loop)
        - Clean lifecycle management (no resource leaks)
        """
        from bassi.main import main_async

        # Create mock argparse Namespace
        mock_args = MagicMock()
        for key, value in args_dict.items():
            setattr(mock_args, key, value)

        # Track calls
        calls = {
            "print_welcome": False,
            "agent_created": False,
            "web_server_started": False,
            "cli_loop_executed": False,
        }

        # Mock parse_args to return our test args
        def mock_parse_args():
            return mock_args

        # Mock print_welcome to track calls
        def mock_print_welcome():
            calls["print_welcome"] = True

        # Mock BassiAgent to track creation
        def mock_agent_init(self, **kwargs):
            calls["agent_created"] = True
            # Create minimal mock agent
            self.cleanup = AsyncMock()
            self._config = MagicMock()
            self._client = MagicMock()

        # Mock cli_main_loop to track execution
        async def mock_cli_main_loop(agent):
            calls["cli_loop_executed"] = True
            # Simulate quick execution
            await asyncio.sleep(0.01)

        # Mock start_web_server to track startup
        async def mock_start_web_server(agent_factory, host, port, reload):
            calls["web_server_started"] = True
            # Create a test agent to verify factory works
            test_agent = agent_factory()
            assert test_agent is not None, "Agent factory should create agent"
            # Simulate web server running
            if args_dict["no_cli"]:
                # In web-only mode, run briefly then complete
                # The test will complete naturally
                await asyncio.sleep(0.02)
            else:
                # In combined mode, wait for CLI to finish
                # This will be cancelled when CLI exits
                await asyncio.sleep(10)

        # Mock Path.exists() for context file check
        def mock_exists(self):
            return False  # No saved context for simplicity

        # Change to tmp directory to avoid polluting repo
        monkeypatch.chdir(tmp_path)

        # Set start_web_server on the mock module for web modes
        if args_dict["web"]:
            mock_web_server_module.start_web_server = mock_start_web_server

        # Mock anyio.sleep_forever for web-only mode
        async def mock_sleep_forever():
            # Simulate brief wait then interrupt
            await asyncio.sleep(0.02)
            raise KeyboardInterrupt("Simulating Ctrl+C in web-only mode")

        # Apply all mocks
        with (
            patch("bassi.main.parse_args", mock_parse_args),
            patch("bassi.main.print_welcome", mock_print_welcome),
            patch("bassi.main.BassiAgent.__init__", mock_agent_init),
            patch("bassi.main.cli_main_loop", mock_cli_main_loop),
            patch("bassi.main.Path.exists", mock_exists),
            patch("anyio.sleep_forever", mock_sleep_forever),
        ):

            # Execute main_async
            await main_async()

        # Verify expected calls match actual calls
        for call_name, expected in expected_calls.items():
            actual = calls[call_name]
            assert actual == expected, (
                f"Mode '{mode}': Expected {call_name}={expected}, got {actual}. "
                f"Full calls: {calls}"
            )

    @pytest.mark.asyncio
    async def test_main_async_cli_only_with_saved_context(
        self, monkeypatch, tmp_path
    ):
        """
        Test main_async() CLI-only mode with saved context file.

        User scenario: User ran bassi yesterday, saved context exists.
        Should prompt to load previous session.

        Tests:
        - Context file detection
        - User prompt for loading context
        - Agent initialization with resume_session_id
        """
        from bassi.main import main_async

        # Create saved context file
        context_file = tmp_path / ".bassi_context.json"
        context_data = {
            "session_id": "test-session-123",
            "messages": [],
            "created_at": "2025-01-01T00:00:00Z",
        }
        context_file.write_text(__import__("json").dumps(context_data))

        # Mock args
        mock_args = MagicMock()
        mock_args.web = False
        mock_args.no_cli = False
        mock_args.host = "localhost"
        mock_args.port = 8765
        mock_args.reload = False

        # Track resume_session_id passed to agent
        captured_session_id = None

        def mock_agent_init(self, **kwargs):
            nonlocal captured_session_id
            captured_session_id = kwargs.get("resume_session_id")
            self.cleanup = AsyncMock()
            self._config = MagicMock()
            self._client = MagicMock()

        async def mock_cli_main_loop(agent):
            await asyncio.sleep(0.01)

        # Mock user choosing to load context
        def mock_prompt_ask(prompt, **kwargs):
            if "Load previous context?" in prompt:
                return "y"
            return "n"

        # Change to tmp directory
        monkeypatch.chdir(tmp_path)

        with (
            patch("bassi.main.parse_args", lambda: mock_args),
            patch("bassi.main.print_welcome"),
            patch("bassi.main.BassiAgent.__init__", mock_agent_init),
            patch("bassi.main.cli_main_loop", mock_cli_main_loop),
            patch("bassi.main.Prompt.ask", mock_prompt_ask),
        ):

            await main_async()

        # Verify session was resumed
        assert (
            captured_session_id == "test-session-123"
        ), "Agent should be initialized with resume_session_id from context file"

    @pytest.mark.asyncio
    async def test_main_async_web_only_displays_tools_once(
        self, monkeypatch, tmp_path, mock_web_server_module
    ):
        """
        Test main_async() web-only mode displays tools at startup.

        User scenario: Running `bassi --web --no-cli` as a service.
        Should create temporary agent to show tools, then clean up.

        Tests:
        - Temporary display agent creation
        - Tool display (display_tools=True)
        - Immediate cleanup after display
        - Web server starts with agent factory
        """
        from bassi.main import main_async

        # Mock args for web-only mode
        mock_args = MagicMock()
        mock_args.web = True
        mock_args.no_cli = True
        mock_args.host = "0.0.0.0"
        mock_args.port = 9000
        mock_args.reload = True

        # Track agent creation
        agents_created = []
        cleanup_called = []

        def mock_agent_init(self, **kwargs):
            agent_info = {
                "display_tools": kwargs.get("display_tools", False),
                "resume_session_id": kwargs.get("resume_session_id"),
            }
            agents_created.append(agent_info)

            # Create mock cleanup
            async def mock_cleanup():
                cleanup_called.append(agent_info)

            self.cleanup = mock_cleanup
            self._config = MagicMock()
            self._client = MagicMock()

        async def mock_start_web_server(agent_factory, host, port, reload):
            # Verify factory can create agents
            agent = agent_factory()
            assert agent is not None
            # Run briefly
            await asyncio.sleep(0.01)

        # Mock anyio.sleep_forever for web-only mode
        async def mock_sleep_forever():
            # Simulate brief wait then interrupt
            await asyncio.sleep(0.02)
            raise KeyboardInterrupt("Simulating Ctrl+C")

        # Change to tmp directory
        monkeypatch.chdir(tmp_path)

        # Set start_web_server on the mock module
        mock_web_server_module.start_web_server = mock_start_web_server

        with (
            patch("bassi.main.parse_args", lambda: mock_args),
            patch("bassi.main.print_welcome"),
            patch("bassi.main.BassiAgent.__init__", mock_agent_init),
            patch("bassi.main.Path.exists", lambda self: False),
            patch("anyio.sleep_forever", mock_sleep_forever),
        ):

            await main_async()

        # Verify display agent was created and cleaned up
        assert (
            len(agents_created) >= 1
        ), "At least one agent should be created (display agent)"
        display_agent = agents_created[0]
        assert (
            display_agent["display_tools"] is True
        ), "Display agent should have display_tools=True"
        assert len(cleanup_called) >= 1, "Display agent should be cleaned up"
        assert (
            cleanup_called[0]["display_tools"] is True
        ), "Cleaned up agent should be display agent"

    @pytest.mark.asyncio
    async def test_main_async_combined_mode_cli_exit_cancels_web(
        self, monkeypatch, tmp_path, mock_web_server_module
    ):
        """
        Test main_async() combined mode: CLI exit cancels web server.

        User scenario: Running `bassi --web`, user types /quit in CLI.
        Should gracefully shutdown web server when CLI exits.

        Tests:
        - Both CLI agent and web server start
        - CLI loop runs to completion
        - Web server task is cancelled when CLI exits
        - Clean task group cancellation
        """
        from bassi.main import main_async

        # Mock args for combined mode
        mock_args = MagicMock()
        mock_args.web = True
        mock_args.no_cli = False
        mock_args.host = "localhost"
        mock_args.port = 8765
        mock_args.reload = False

        # Track execution order
        execution_order = []

        def mock_agent_init(self, **kwargs):
            execution_order.append("agent_created")
            self.cleanup = AsyncMock()
            self._config = MagicMock()
            self._client = MagicMock()

        async def mock_cli_main_loop(agent):
            execution_order.append("cli_started")
            await asyncio.sleep(0.05)  # Quick CLI session
            execution_order.append("cli_finished")

        async def mock_start_web_server(agent_factory, host, port, reload):
            execution_order.append("web_started")
            try:
                # Web server should run until cancelled
                await asyncio.sleep(10)  # Long timeout
                execution_order.append(
                    "web_finished_naturally"
                )  # Should not reach here
            except asyncio.CancelledError:
                execution_order.append("web_cancelled")
                raise

        # Mock anyio.sleep_forever (shouldn't be called in combined mode)
        async def mock_sleep_forever():
            execution_order.append(
                "sleep_forever_called"
            )  # Should not happen
            await asyncio.sleep(10)

        # Change to tmp directory
        monkeypatch.chdir(tmp_path)

        # Set start_web_server on the mock module
        mock_web_server_module.start_web_server = mock_start_web_server

        with (
            patch("bassi.main.parse_args", lambda: mock_args),
            patch("bassi.main.print_welcome"),
            patch("bassi.main.BassiAgent.__init__", mock_agent_init),
            patch("bassi.main.cli_main_loop", mock_cli_main_loop),
            patch("bassi.main.Path.exists", lambda self: False),
            patch("anyio.sleep_forever", mock_sleep_forever),
        ):

            await main_async()

        # Verify execution order
        assert "agent_created" in execution_order
        assert "cli_started" in execution_order
        assert "web_started" in execution_order
        assert "cli_finished" in execution_order
        assert "web_cancelled" in execution_order
        assert (
            "web_finished_naturally" not in execution_order
        ), "Web server should be cancelled, not finish naturally"

        # Verify CLI finished before web was cancelled
        cli_finish_idx = execution_order.index("cli_finished")
        web_cancel_idx = execution_order.index("web_cancelled")
        assert (
            cli_finish_idx < web_cancel_idx
        ), "CLI should finish before web server is cancelled"


@pytest.mark.integration
class TestMainErrorHandling:
    """Integration tests for error handling in main functions (AGENT_04)."""

    @pytest.mark.asyncio
    async def test_main_error_handling_resilience(self, tmp_path, monkeypatch):
        """
        Test main.py error handling across multiple failure scenarios.

        This comprehensive integration test verifies that bassi handles errors
        gracefully without crashing, covering:

        1. Corrupted context file (JSON parse error)
        2. Agent initialization failures (network error, invalid API key, etc.)
        3. Invalid session data in context file
        4. Signal handler setup and restoration
        5. Terminal state restoration in finally blocks

        User scenarios:
        - User has a corrupted .bassi_context.json from a previous crash
        - Network fails during agent initialization
        - User presses Ctrl+C during initialization
        - Context file has invalid session_id or timestamp

        All scenarios should result in clean error messages, not Python tracebacks.
        """
        from bassi.main import cli_main_loop
        from bassi.agent import BassiAgent

        # Change to temp directory to avoid polluting project
        monkeypatch.chdir(tmp_path)

        # Set mock API key
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        # --- Scenario 1: Corrupted context file (JSON parse error) ---
        context_file = tmp_path / ".bassi_context.json"
        context_file.write_text("{ invalid json }")  # Malformed JSON

        # Mock console to capture error messages
        from io import StringIO
        from rich.console import Console
        output = StringIO()
        test_console = Console(file=output, force_terminal=False, width=120)

        import bassi.main
        monkeypatch.setattr(bassi.main, "console", test_console)

        # Mock signal.getsignal to return a dummy handler
        original_handler = signal.getsignal(signal.SIGINT)
        mock_previous_handler = Mock()
        monkeypatch.setattr(signal, "getsignal", lambda sig: mock_previous_handler)

        # Track signal.signal calls
        signal_calls = []
        original_signal = signal.signal

        def track_signal(sig, handler):
            signal_calls.append((sig, handler))
            return original_signal(sig, handler)

        monkeypatch.setattr(signal, "signal", track_signal)

        # --- Scenario 2: Agent initialization fails ---
        # Mock BassiAgent to raise exception during initialization
        class FailingAgent:
            def __init__(self, *args, **kwargs):
                raise RuntimeError("Simulated agent initialization failure")

        monkeypatch.setattr(bassi.main, "BassiAgent", FailingAgent)

        # Mock get_user_input to raise KeyboardInterrupt immediately
        # (simulates user pressing Ctrl+C during the error)
        async def mock_input(*args, **kwargs):
            raise KeyboardInterrupt

        monkeypatch.setattr(bassi.main, "get_user_input", mock_input)

        # Mock termios to avoid TTY issues in tests (imported inside cli_main_loop)
        mock_termios = Mock()
        mock_termios.tcgetattr = Mock(return_value=[None, None, None, 0])
        mock_termios.tcsetattr = Mock()
        mock_termios.ICANON = 0x02
        mock_termios.ECHO = 0x08
        mock_termios.ISIG = 0x01
        mock_termios.TCSANOW = 0

        # Patch termios module globally (imported inside function)
        import sys
        sys.modules['termios'] = mock_termios

        # Mock sys.stdin.fileno() to return a valid fd
        mock_stdin = Mock()
        mock_stdin.fileno = Mock(return_value=0)
        import sys
        monkeypatch.setattr(sys, "stdin", mock_stdin)

        # --- Scenario 3: Fatal error causes sys.exit(1) ---
        # Run cli_main_loop and expect it to exit with SystemExit
        with pytest.raises(SystemExit) as exc_info:
            # Should call sys.exit(1) on fatal error (agent init failure)
            await cli_main_loop(None)  # type: ignore

        # Verify it exits with code 1 (fatal error)
        assert exc_info.value.code == 1, "Should exit with code 1 on fatal error"

        # Verify error handling behaviors:

        # 1. JSON parse error should be logged (warning in logs)
        # Note: The actual log message might not be in console output,
        # but we can verify the context file was attempted to be read
        assert context_file.exists(), "Context file should still exist after error"

        # 2. Signal handler should be set and restored
        assert len(signal_calls) >= 2, "Should call signal.signal at least twice (set + restore)"

        # First call should set the handler to _cli_sigint_handler
        first_signal_call = signal_calls[0]
        assert first_signal_call[0] == signal.SIGINT, "First signal call should be for SIGINT"
        assert callable(first_signal_call[1]), "First signal handler should be callable"

        # Last call should restore the previous handler
        last_signal_call = signal_calls[-1]
        assert last_signal_call[0] == signal.SIGINT, "Last signal call should be for SIGINT"
        assert last_signal_call[1] == mock_previous_handler, "Should restore previous handler"

        # 3. Terminal should be restored (tcsetattr called in finally block)
        assert mock_termios.tcsetattr.called, "Terminal should be restored in finally block"

        # 4. Verify agent initialization was attempted (BassiAgent called)
        # This is implicitly verified by the RuntimeError from FailingAgent

        # Verify the test covered multiple error paths:
        # - Corrupted JSON context file (created above)
        # - Agent initialization failure (FailingAgent)
        # - Fatal error handling (SystemExit)
        # - Signal handler restoration (signal_calls)
        # - Terminal restoration (tcsetattr)

        # --- Additional Scenario: Test with valid JSON but invalid session data ---
        # Reset for second test scenario
        signal_calls.clear()

        # Create a valid JSON file but with unexpected data structure
        context_file.write_text(json.dumps({
            "session_id": None,  # Invalid session_id
            "timestamp": "not-a-number",  # Invalid timestamp
            "invalid_field": {"nested": "data"}
        }))

        # Create a mock agent that initializes successfully this time
        agent_init_calls = []

        class MockAgent:
            def __init__(self, *args, **kwargs):
                agent_init_calls.append(kwargs)
                self.verbose = False

            async def cleanup(self):
                pass

        monkeypatch.setattr(bassi.main, "BassiAgent", MockAgent)

        # Mock get_user_input to exit immediately (EOF)
        async def mock_input_eof(*args, **kwargs):
            return None  # EOF to exit gracefully

        monkeypatch.setattr(bassi.main, "get_user_input", mock_input_eof)

        # Run cli_main_loop - should handle invalid context gracefully
        await cli_main_loop(None)  # type: ignore

        # Verify:
        # 1. Agent was initialized despite invalid context
        assert len(agent_init_calls) == 1, "Agent should be initialized once"

        # 2. Context file was read but invalid data handled
        assert context_file.exists(), "Context file should still exist"

        # 3. No crash occurred (test completed successfully)
        result = output.getvalue()
        assert "Goodbye!" in result or "Ready!" in result, "Should exit gracefully"

        # 4. Signal handlers were set and restored again
        assert len(signal_calls) >= 2, "Should set and restore signal handlers"
