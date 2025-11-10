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

from tests.fixtures.mock_agent_client import MockAgentClient


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

    # Ensure Python can import the project modules even after chdir
    existing_pythonpath = os.environ.get("PYTHONPATH")
    if existing_pythonpath:
        new_pythonpath = os.pathsep.join(
            [str(original_cwd), existing_pythonpath]
        )
    else:
        new_pythonpath = str(original_cwd)
    monkeypatch.setenv("PYTHONPATH", new_pythonpath)

    # Point uv (if used) back to the project root
    monkeypatch.setenv("UV_PROJECT_DIR", str(original_cwd))

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


@pytest.fixture
def mock_agent_client():
    """Provide a reusable mock AgentClient for unit tests."""
    return MockAgentClient()


def pytest_configure(config):
    """
    Pytest configuration hook - runs before test collection.

    This disables SDK wrapping for MCP server tests by replacing
    SDK functions with stubs before any MCP server modules are imported.

    IMPORTANT: Only stubs SDK for V1 tests, NOT E2E tests which need real SDK!
    """
    import sys
    from typing import Any, Callable

    # Check if we're running E2E tests - they need the real SDK
    # E2E tests are marked with @pytest.mark.e2e and run sequentially
    try:
        # Get marker expression from command line
        marker_expr = config.getoption("-m", default="")
        # If running E2E tests exclusively, skip SDK stubbing
        if marker_expr == "e2e":
            print("\n⚠️  Running E2E tests - keeping real SDK enabled")
            return
    except (ValueError, AttributeError):
        pass  # Marker not specified, proceed with stubbing

    # Delete sdk_loader if already imported
    if "bassi.shared.sdk_loader" in sys.modules:
        del sys.modules["bassi.shared.sdk_loader"]

    # Also delete MCP server modules if imported
    for module_name in list(sys.modules.keys()):
        if module_name.startswith("bassi.mcp_servers."):
            del sys.modules[module_name]

    # Import sdk_loader
    import bassi.shared.sdk_loader

    # Force SDK_AVAILABLE = False
    bassi.shared.sdk_loader.SDK_AVAILABLE = False

    # Replace SDK functions with stubs (critical - just setting SDK_AVAILABLE isn't enough!)
    def stub_tool(*decorator_args: Any, **decorator_kwargs: Any):
        """Stub decorator - returns function unchanged"""

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            return func

        return decorator

    def stub_create_sdk_mcp_server(
        *, name: str, version: str, tools: list[Callable[..., Any]]
    ) -> dict[str, Any]:
        """Stub MCP server factory"""
        return {
            "name": name,
            "version": version,
            "type": "mcp_server",  # Add type field expected by tests
            "tools": tools,
            "sdk_available": False,
        }

    # Monkey-patch the module to use stubs
    bassi.shared.sdk_loader.tool = stub_tool
    bassi.shared.sdk_loader.create_sdk_mcp_server = stub_create_sdk_mcp_server
