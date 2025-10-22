"""
Pytest configuration and fixtures for bassi tests

Provides reusable fixtures for testing bassi, including:
- Environment setup
- Mock API keys
- Isolated test directories
- PTY session management
"""

import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def test_environment(monkeypatch, tmp_path):
    """
    Set up isolated test environment for all tests

    This fixture automatically runs for every test and ensures:
    - Tests run in isolated temporary directory
    - Mock API key is set (won't hit real API)
    - Test-specific history and context files
    """
    # Use temporary directory for test runs
    original_cwd = Path.cwd()
    os.chdir(tmp_path)

    # Set mock API key for tests
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-12345-mock-testing")

    # Use test-specific history file
    test_home = tmp_path / "home"
    test_home.mkdir()
    monkeypatch.setenv("HOME", str(test_home))

    yield tmp_path

    # Restore original directory
    os.chdir(original_cwd)


@pytest.fixture
def mock_api_key(monkeypatch):
    """Provide a mock API key for tests"""
    api_key = "sk-ant-test-mock-key-for-testing-12345"
    monkeypatch.setenv("ANTHROPIC_API_KEY", api_key)
    return api_key


@pytest.fixture
def temp_config_dir(tmp_path, monkeypatch):
    """
    Create a temporary config directory for testing

    Returns the path to the temporary config directory
    """
    config_dir = tmp_path / ".config" / "bassi"
    config_dir.mkdir(parents=True)

    # Point bassi to use this config dir
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))

    return config_dir


@pytest.fixture
def isolated_working_dir(tmp_path, monkeypatch):
    """
    Change to isolated temporary directory for test

    Returns the path to the temporary directory
    """
    os.chdir(tmp_path)
    return tmp_path


# Special key sequences for terminal testing
TERMINAL_KEYS = {
    "ENTER": "\r",
    "NEWLINE": "\n",
    "ESC": "\x1b",
    "CTRL_C": "\x03",
    "CTRL_D": "\x04",
    "CTRL_R": "\x12",  # Reverse search
    "TAB": "\t",
    "BACKSPACE": "\x7f",
    "DELETE": "\x1b[3~",
    "ARROW_UP": "\x1b[A",
    "ARROW_DOWN": "\x1b[B",
    "ARROW_LEFT": "\x1b[D",
    "ARROW_RIGHT": "\x1b[C",
    "HOME": "\x1b[H",
    "END": "\x1b[F",
}


@pytest.fixture
def terminal_keys():
    """Provide terminal key sequences for testing"""
    return TERMINAL_KEYS
