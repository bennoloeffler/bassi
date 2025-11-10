"""
Integration tests for bassi key bindings using pexpect

These tests spawn an actual bassi process with a pseudo-terminal (PTY)
and simulate user keyboard input to verify key bindings work correctly.

Key bindings tested:
- Enter: Send message (single-line mode)
- Ctrl+C: Exit application (standard Unix)
- Ctrl+D: Exit application (EOF)
- ESC: Interrupt running agent
- /quit: Exit cleanly
- /edit: Open $EDITOR for multiline input
"""

import os
import signal
import sys

import pexpect
import pytest

# Skip all PTY-based tests on macOS due to PTY permission issues
pytestmark = pytest.mark.skipif(
    sys.platform == "darwin",
    reason="pexpect PTY tests not supported on macOS due to permission issues",
)


class TestKeyBindings:
    """Integration tests for keyboard bindings using PTY simulation"""

    @pytest.fixture
    def bassi_session(self):
        """Spawn a bassi session with pseudo-terminal for testing"""
        # Set mock API key for testing
        env = os.environ.copy()
        env["ANTHROPIC_API_KEY"] = "test-key-12345-mock"

        # Spawn bassi with PTY
        command = f"{sys.executable} -m bassi.main"
        child = pexpect.spawn(
            command,
            env=env,
            encoding="utf-8",
            timeout=10,
        )

        # Wait for initial prompt
        try:
            child.expect("You:", timeout=10)
        except pexpect.TIMEOUT:
            print(f"Startup output: {child.before}")
            raise

        yield child

        # Cleanup
        try:
            if child.isalive():
                child.sendcontrol("d")  # Ctrl+D to exit
                child.expect(pexpect.EOF, timeout=3)
        except Exception:
            # Force kill if graceful shutdown fails
            child.kill(0)

    def test_slash_quit_exits_cleanly(self, bassi_session):
        """Test that /quit command exits the application"""
        # Send /quit command
        bassi_session.sendline("/quit")

        # Expect goodbye message
        bassi_session.expect("Goodbye!", timeout=5)

        # Process should exit cleanly
        bassi_session.expect(pexpect.EOF, timeout=3)

        assert not bassi_session.isalive()

    def test_ctrl_d_exits(self, bassi_session):
        """Test that Ctrl+D (EOF) exits the application"""
        # Send Ctrl+D
        bassi_session.sendcontrol("d")

        # Expect goodbye message
        bassi_session.expect("Goodbye!", timeout=5)

        # Process should exit
        bassi_session.expect(pexpect.EOF, timeout=3)

        assert not bassi_session.isalive()

    def test_ctrl_c_during_prompt_exits_app(self, bassi_session):
        """Test that Ctrl+C at prompt exits the application (standard Unix behavior)"""
        # Press Ctrl+C to exit (send SIGINT)
        bassi_session.sendcontrol("c")

        # Should exit (EOF)
        bassi_session.expect(pexpect.EOF, timeout=3)

        # Verify exit status
        # Exit code 130 means terminated by Ctrl+C (128 + SIGINT)
        bassi_session.close()
        assert (
            bassi_session.exitstatus in (0, 130)
            or bassi_session.signalstatus == signal.SIGINT
        )

    def test_empty_input_ignored(self, bassi_session):
        """Test that pressing Enter with empty input is ignored"""
        # Send empty line
        bassi_session.sendline("")

        # Should just get another prompt, no agent response
        bassi_session.expect("You:", timeout=3)

        # No "Assistant:" should appear
        assert "Assistant:" not in bassi_session.before

    def test_slash_help_shows_help(self, bassi_session):
        """Test that /help command displays help information"""
        # Send /help command
        bassi_session.sendline("/help")

        # Should see help header
        bassi_session.expect("Help: bassi", timeout=5)

        # Should see commands section
        bassi_session.expect("Available Commands", timeout=2)

        # Should return to prompt
        bassi_session.expect("You:", timeout=2)

    def test_slash_config_shows_config(self, bassi_session):
        """Test that /config command displays configuration"""
        # Send /config command
        bassi_session.sendline("/config")

        # Should see configuration header
        bassi_session.expect("Configuration", timeout=5)

        # Should see config file path
        bassi_session.expect("Config file:", timeout=2)

        # Should return to prompt
        bassi_session.expect("You:", timeout=2)

    def test_multiline_input_with_manual_newlines(self, bassi_session):
        """Test entering multiline text by typing newlines manually"""
        # Since Shift+Enter escape sequences are terminal-dependent,
        # we test by checking if the prompt supports multiline

        # Send text with embedded newline character
        bassi_session.send("line 1\nline 2\nline 3")

        # Send final Enter to submit
        bassi_session.sendline()

        # The input should be processed (we won't test agent response
        # since we don't have real API key, but we verify it was accepted)

        # Should see prompt again (either from agent response or error)
        bassi_session.expect("You:|Error:", timeout=5)

    def test_slash_command_menu(self, bassi_session):
        """Test that typing / shows command menu"""
        # Send just /
        bassi_session.sendline("/")

        # Should see command selector
        bassi_session.expect("Select a command:", timeout=5)

        # Should show numbered commands
        bassi_session.expect("1.", timeout=2)

        # Send empty to cancel
        bassi_session.sendline()

        # Should return to prompt
        bassi_session.expect("You:", timeout=3)

    def test_invalid_command_shows_error(self, bassi_session):
        """Test that invalid commands show helpful error"""
        # Send invalid command
        bassi_session.sendline("/invalidcommand")

        # Should see error message
        bassi_session.expect("Unknown command:", timeout=3)

        # Should suggest help
        bassi_session.expect("Type .* to see all commands", timeout=2)

        # Should return to prompt
        bassi_session.expect("You:", timeout=2)

    @pytest.mark.skip(reason="Requires real API key and network access")
    def test_enter_sends_message_to_agent(self, bassi_session):
        """Test that Enter key sends message to agent (integration test)"""
        # This test requires a real API key and network
        # Skip in normal test runs

        bassi_session.sendline("what is 2 + 2")

        # Wait for agent response
        bassi_session.expect("Assistant:", timeout=30)

        # Should see response with "4"
        bassi_session.expect("4", timeout=5)

    @pytest.mark.skip(reason="Requires real API key and agent execution")
    def test_esc_interrupts_running_agent(self, bassi_session):
        """Test that ESC interrupts a running agent (integration test)"""
        # This test requires actual agent execution
        # Skip in normal test runs

        # Send a query that would take time
        bassi_session.sendline("search for python tutorials")

        # Wait for interrupt instruction to appear
        bassi_session.expect("Press ESC or Ctrl\\+C to interrupt", timeout=5)

        # Send ESC key
        bassi_session.send("\x1b")

        # Should see interrupt message
        bassi_session.expect("Agent interrupted", timeout=5)


class TestPromptSessionFeatures:
    """Test prompt_toolkit session features"""

    @pytest.fixture
    def bassi_session(self):
        """Spawn bassi with PTY"""
        env = os.environ.copy()
        env["ANTHROPIC_API_KEY"] = "test-key-mock"

        child = pexpect.spawn(
            "uv run python -m bassi.main",
            env=env,
            encoding="utf-8",
            timeout=10,
        )

        child.expect("You:", timeout=10)
        yield child

        try:
            if child.isalive():
                child.sendcontrol("d")
                child.expect(pexpect.EOF, timeout=3)
        except Exception:
            child.kill(0)

    def test_history_file_created(self, bassi_session, tmp_path):
        """Test that command history is saved"""
        # History file should be created in home directory
        history_file = os.path.expanduser("~/.bassi_history")

        # Send some commands
        bassi_session.sendline("/help")
        bassi_session.expect("You:", timeout=5)

        bassi_session.sendline("/quit")
        bassi_session.expect(pexpect.EOF, timeout=3)

        # History file should exist
        assert os.path.exists(history_file)

    def test_welcome_message_shows_instructions(self, bassi_session):
        """Test that welcome message shows key binding instructions"""
        # The welcome message should already be in the buffer
        welcome = bassi_session.before

        # Check for key instructions
        assert "Enter" in welcome or "Shift+Enter" in welcome
        assert "ESC" in welcome or "interrupt" in welcome
        assert "/quit" in welcome or "exit" in welcome
