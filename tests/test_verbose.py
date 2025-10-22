"""
Tests for verbose mode functionality
"""

import os

from bassi.agent import BassiAgent


def test_verbose_toggle():
    """Test verbose mode toggle"""
    os.environ["ANTHROPIC_API_KEY"] = "test-key"

    agent = BassiAgent()

    # Should start with verbose = True (default)
    assert agent.verbose is True

    # Toggle to False
    result = agent.toggle_verbose()
    assert result is False
    assert agent.verbose is False

    # Toggle back to True
    result = agent.toggle_verbose()
    assert result is True
    assert agent.verbose is True

    # Clean up
    del os.environ["ANTHROPIC_API_KEY"]


def test_set_verbose():
    """Test setting verbose mode directly"""
    os.environ["ANTHROPIC_API_KEY"] = "test-key"

    agent = BassiAgent()

    # Set to True
    agent.set_verbose(True)
    assert agent.verbose is True

    # Set to False
    agent.set_verbose(False)
    assert agent.verbose is False

    # Clean up
    del os.environ["ANTHROPIC_API_KEY"]


def test_verbose_mode_exists():
    """Test that verbose mode attributes exist"""
    os.environ["ANTHROPIC_API_KEY"] = "test-key"

    agent = BassiAgent()

    # Check attributes exist
    assert hasattr(agent, "verbose")
    assert hasattr(agent, "console")
    assert hasattr(agent, "toggle_verbose")
    assert hasattr(agent, "set_verbose")

    # Check methods are callable
    assert callable(agent.toggle_verbose)
    assert callable(agent.set_verbose)

    # Clean up
    del os.environ["ANTHROPIC_API_KEY"]
