"""
Tests for permission configuration helpers.
"""

import logging

from bassi.shared.permission_config import get_permission_mode


def test_permission_mode_defaults_to_fallback(monkeypatch):
    """Should return fallback when env var is missing."""
    monkeypatch.delenv("BASSI_PERMISSION_MODE", raising=False)
    assert get_permission_mode() == "bypassPermissions"


def test_permission_mode_reads_env_case_insensitive(monkeypatch):
    """Should accept case-insensitive values from env."""
    monkeypatch.setenv("BASSI_PERMISSION_MODE", "AcCePtEdItS")
    assert get_permission_mode() == "acceptEdits"


def test_permission_mode_strips_whitespace(monkeypatch):
    """Should strip whitespace when parsing env value."""
    monkeypatch.setenv("BASSI_PERMISSION_MODE", " default ")
    assert get_permission_mode() == "default"


def test_permission_mode_invalid_value_logs_warning(monkeypatch, caplog):
    """Should fall back and log warning when env value invalid."""
    monkeypatch.setenv("BASSI_PERMISSION_MODE", "danger-zone")

    with caplog.at_level(logging.WARNING):
        mode = get_permission_mode()

    assert mode == "bypassPermissions"
    assert "Invalid permission mode" in caplog.text


def test_permission_mode_empty_string_falls_back(monkeypatch):
    """Should fall back when env var is empty string."""
    monkeypatch.setenv("BASSI_PERMISSION_MODE", "")
    assert get_permission_mode() == "bypassPermissions"


def test_permission_mode_whitespace_only_falls_back(monkeypatch):
    """Should fall back when env var is only whitespace (covers line 43)."""
    monkeypatch.setenv("BASSI_PERMISSION_MODE", "   ")
    assert get_permission_mode() == "bypassPermissions"


def test_permission_mode_all_valid_values(monkeypatch):
    """Should accept all canonical permission modes."""
    valid_modes = {
        "bypasspermissions": "bypassPermissions",
        "acceptedits": "acceptEdits",
        "default": "default",
        "plan": "plan",
    }

    for input_val, expected in valid_modes.items():
        monkeypatch.setenv("BASSI_PERMISSION_MODE", input_val)
        assert get_permission_mode() == expected


def test_permission_mode_case_variations(monkeypatch):
    """Should handle various case combinations."""
    test_cases = [
        "BYPASSPERMISSIONS",
        "BypassPermissions",
        "ACCEPTEDITS",
        "AcceptEdits",
        "DEFAULT",
        "Default",
        "PLAN",
        "Plan",
    ]

    expected_map = {
        "BYPASSPERMISSIONS": "bypassPermissions",
        "BypassPermissions": "bypassPermissions",
        "ACCEPTEDITS": "acceptEdits",
        "AcceptEdits": "acceptEdits",
        "DEFAULT": "default",
        "Default": "default",
        "PLAN": "plan",
        "Plan": "plan",
    }

    for test_val in test_cases:
        monkeypatch.setenv("BASSI_PERMISSION_MODE", test_val)
        assert get_permission_mode() == expected_map[test_val]


def test_permission_mode_custom_env_var(monkeypatch):
    """Should read from custom env var name."""
    monkeypatch.setenv("MY_CUSTOM_MODE", "acceptedits")
    assert get_permission_mode(env_var="MY_CUSTOM_MODE") == "acceptEdits"


def test_permission_mode_custom_fallback(monkeypatch):
    """Should use custom fallback value."""
    monkeypatch.delenv("BASSI_PERMISSION_MODE", raising=False)
    assert get_permission_mode(fallback="plan") == "plan"


def test_permission_mode_invalid_with_custom_fallback(monkeypatch):
    """Should use custom fallback when value invalid."""
    monkeypatch.setenv("BASSI_PERMISSION_MODE", "invalid")
    assert get_permission_mode(fallback="default") == "default"


def test_permission_mode_special_characters(monkeypatch, caplog):
    """Should handle special characters in invalid mode."""
    monkeypatch.setenv("BASSI_PERMISSION_MODE", "bypass@permissions!")

    with caplog.at_level(logging.WARNING):
        mode = get_permission_mode()

    assert mode == "bypassPermissions"
    assert "Invalid permission mode" in caplog.text


def test_permission_mode_very_long_value(monkeypatch, caplog):
    """Should handle very long invalid values."""
    long_value = "a" * 1000

    monkeypatch.setenv("BASSI_PERMISSION_MODE", long_value)

    with caplog.at_level(logging.WARNING):
        mode = get_permission_mode()

    assert mode == "bypassPermissions"
    assert "Invalid permission mode" in caplog.text


def test_permission_mode_tabs_and_newlines(monkeypatch):
    """Should strip tabs and handle values with whitespace."""
    monkeypatch.setenv("BASSI_PERMISSION_MODE", "\tbypasspermissions\n")
    assert get_permission_mode() == "bypassPermissions"


def test_permission_mode_unicode_characters(monkeypatch, caplog):
    """Should handle unicode characters in invalid mode."""
    monkeypatch.setenv("BASSI_PERMISSION_MODE", "bypass🔒permissions")

    with caplog.at_level(logging.WARNING):
        mode = get_permission_mode()

    assert mode == "bypassPermissions"
    assert "Invalid permission mode" in caplog.text


def test_permission_mode_logging_includes_valid_modes(monkeypatch, caplog):
    """Should log valid modes in warning message."""
    monkeypatch.setenv("BASSI_PERMISSION_MODE", "invalid")

    with caplog.at_level(logging.WARNING):
        get_permission_mode()

    # Check that warning includes the list of valid modes
    assert "acceptEdits" in caplog.text
    assert "bypassPermissions" in caplog.text
    assert "default" in caplog.text
    assert "plan" in caplog.text
