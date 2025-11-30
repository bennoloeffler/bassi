"""Tests for model service.

Tests model level constants, info retrieval, and escalation tracking.
"""

import pytest

from bassi.core_v3.services.model_service import (
    DEFAULT_MODEL_LEVEL,
    FAILURES_BEFORE_ESCALATION,
    MAX_MODEL_LEVEL,
    MIN_MODEL_LEVEL,
    MODEL_LEVELS,
    ModelEscalationTracker,
    get_level_for_model_id,
    get_model_id,
    get_model_info,
)


class TestModelConstants:
    """Tests for model level constants."""

    def test_model_levels_exist(self):
        """All three model levels should be defined."""
        assert 1 in MODEL_LEVELS
        assert 2 in MODEL_LEVELS
        assert 3 in MODEL_LEVELS
        assert len(MODEL_LEVELS) == 3

    def test_default_model_level(self):
        """Default should be Haiku (level 1)."""
        assert DEFAULT_MODEL_LEVEL == 1

    def test_max_model_level(self):
        """Max should be Opus (level 3)."""
        assert MAX_MODEL_LEVEL == 3

    def test_min_model_level(self):
        """Min should be Haiku (level 1)."""
        assert MIN_MODEL_LEVEL == 1

    def test_failures_before_escalation(self):
        """Should require 3 failures before escalation."""
        assert FAILURES_BEFORE_ESCALATION == 3


class TestModelInfo:
    """Tests for model info retrieval."""

    def test_get_model_info_haiku(self):
        """Should return correct info for Haiku."""
        info = get_model_info(1)
        assert info.name == "Haiku 4.5"
        assert "haiku" in info.id.lower()
        assert info.icon_color == "green"

    def test_get_model_info_sonnet(self):
        """Should return correct info for Sonnet."""
        info = get_model_info(2)
        assert info.name == "Sonnet 4.5"
        assert "sonnet" in info.id.lower()
        assert info.icon_color == "blue"

    def test_get_model_info_opus(self):
        """Should return correct info for Opus."""
        info = get_model_info(3)
        assert info.name == "Opus 4.5"
        assert "opus" in info.id.lower()
        assert info.icon_color == "purple"

    def test_get_model_info_invalid(self):
        """Should raise ValueError for invalid level."""
        with pytest.raises(ValueError, match="Invalid model level"):
            get_model_info(0)
        with pytest.raises(ValueError, match="Invalid model level"):
            get_model_info(4)

    def test_get_model_id(self):
        """Should return model ID string."""
        model_id = get_model_id(1)
        assert isinstance(model_id, str)
        assert "haiku" in model_id.lower()

    def test_get_level_for_model_id(self):
        """Should return level for known model ID."""
        haiku_id = get_model_id(1)
        assert get_level_for_model_id(haiku_id) == 1

        sonnet_id = get_model_id(2)
        assert get_level_for_model_id(sonnet_id) == 2

        opus_id = get_model_id(3)
        assert get_level_for_model_id(opus_id) == 3

    def test_get_level_for_unknown_model_id(self):
        """Should return None for unknown model ID."""
        assert get_level_for_model_id("unknown-model") is None


class TestModelEscalationTracker:
    """Tests for auto-escalation tracking."""

    def test_initial_state(self):
        """Should start with default level and no failures."""
        tracker = ModelEscalationTracker()
        assert tracker.current_level == DEFAULT_MODEL_LEVEL
        assert tracker.auto_escalate is True
        assert tracker.consecutive_failures == 0

    def test_custom_initial_state(self):
        """Should accept custom initial state."""
        tracker = ModelEscalationTracker(current_level=2, auto_escalate=False)
        assert tracker.current_level == 2
        assert tracker.auto_escalate is False

    def test_single_failure_no_escalation(self):
        """Single failure should not escalate."""
        tracker = ModelEscalationTracker()
        result = tracker.on_failure()
        assert result is None
        assert tracker.current_level == 1
        assert tracker.consecutive_failures == 1

    def test_two_failures_no_escalation(self):
        """Two failures should not escalate."""
        tracker = ModelEscalationTracker()
        tracker.on_failure()
        result = tracker.on_failure()
        assert result is None
        assert tracker.current_level == 1
        assert tracker.consecutive_failures == 2

    def test_three_failures_triggers_escalation(self):
        """Three failures should trigger escalation."""
        tracker = ModelEscalationTracker()
        tracker.on_failure()
        tracker.on_failure()
        result = tracker.on_failure()
        assert result == 2  # New level
        assert tracker.current_level == 2
        assert tracker.consecutive_failures == 0  # Reset after escalation

    def test_escalation_to_opus(self):
        """Should escalate from Sonnet to Opus."""
        tracker = ModelEscalationTracker(current_level=2)
        for _ in range(3):
            result = tracker.on_failure()
        assert result == 3
        assert tracker.current_level == 3

    def test_no_escalation_beyond_opus(self):
        """Should not escalate beyond Opus (level 3)."""
        tracker = ModelEscalationTracker(current_level=3)
        for _ in range(3):
            result = tracker.on_failure()
        assert result is None  # No escalation
        assert tracker.current_level == 3
        assert tracker.consecutive_failures == 3  # Not reset since no escalation

    def test_auto_escalate_disabled(self):
        """Should not escalate when auto_escalate is False."""
        tracker = ModelEscalationTracker(auto_escalate=False)
        for _ in range(5):
            result = tracker.on_failure()
        assert result is None
        assert tracker.current_level == 1
        assert tracker.consecutive_failures == 5

    def test_success_resets_failures(self):
        """Success should reset failure counter."""
        tracker = ModelEscalationTracker()
        tracker.on_failure()
        tracker.on_failure()
        assert tracker.consecutive_failures == 2
        tracker.on_success()
        assert tracker.consecutive_failures == 0

    def test_success_does_not_change_level(self):
        """Success should not change model level."""
        tracker = ModelEscalationTracker(current_level=2)
        tracker.on_success()
        assert tracker.current_level == 2

    def test_set_level(self):
        """Should allow manual level changes."""
        tracker = ModelEscalationTracker()
        tracker.set_level(3)
        assert tracker.current_level == 3
        assert tracker.consecutive_failures == 0  # Reset on level change

    def test_set_invalid_level(self):
        """Should raise error for invalid level."""
        tracker = ModelEscalationTracker()
        with pytest.raises(ValueError, match="Invalid model level"):
            tracker.set_level(0)
        with pytest.raises(ValueError, match="Invalid model level"):
            tracker.set_level(4)

    def test_get_state(self):
        """Should return serializable state."""
        tracker = ModelEscalationTracker(current_level=2)
        tracker.on_failure()
        state = tracker.get_state()

        assert state["current_level"] == 2
        assert state["auto_escalate"] is True
        assert state["consecutive_failures"] == 1
        assert "model_info" in state
        assert state["model_info"]["name"] == "Sonnet 4.5"

    def test_escalation_sequence(self):
        """Should escalate through all levels correctly."""
        tracker = ModelEscalationTracker(current_level=1)

        # 3 failures → escalate to level 2
        for _ in range(3):
            tracker.on_failure()
        assert tracker.current_level == 2

        # 3 more failures → escalate to level 3
        for _ in range(3):
            tracker.on_failure()
        assert tracker.current_level == 3

        # 3 more failures → stay at level 3
        for _ in range(3):
            tracker.on_failure()
        assert tracker.current_level == 3

    def test_success_between_failures_resets_count(self):
        """Success should reset counter, preventing escalation."""
        tracker = ModelEscalationTracker()

        # 2 failures
        tracker.on_failure()
        tracker.on_failure()
        assert tracker.consecutive_failures == 2

        # Success resets
        tracker.on_success()
        assert tracker.consecutive_failures == 0

        # 2 more failures - should not escalate yet
        tracker.on_failure()
        tracker.on_failure()
        assert tracker.current_level == 1  # Still level 1
        assert tracker.consecutive_failures == 2
