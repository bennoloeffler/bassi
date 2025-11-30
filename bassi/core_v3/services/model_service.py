"""Model service for managing AI model selection and auto-escalation.

Provides:
- Model level constants (Haiku, Sonnet, Opus)
- Model selection persistence
- Auto-escalation logic on consecutive failures
"""

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelInfo:
    """Information about a Claude model."""

    id: str
    name: str
    description: str
    icon_color: str  # CSS color class: green, blue, purple


# Model level configuration
# Model IDs from: https://docs.anthropic.com/en/docs/about-claude/models
MODEL_LEVELS: dict[int, ModelInfo] = {
    1: ModelInfo(
        id="claude-haiku-4-5-20251001",
        name="Haiku 4.5",
        description="Fastest for quick answers",
        icon_color="green",
    ),
    2: ModelInfo(
        id="claude-sonnet-4-5-20250929",
        name="Sonnet 4.5",
        description="Best for everyday tasks",
        icon_color="blue",
    ),
    3: ModelInfo(
        id="claude-opus-4-5-20251101",
        name="Opus 4.5",
        description="Most capable for complex work",
        icon_color="purple",
    ),
}

# Constants
DEFAULT_MODEL_LEVEL = 1  # Start with Haiku
MAX_MODEL_LEVEL = 3
MIN_MODEL_LEVEL = 1
FAILURES_BEFORE_ESCALATION = 3


def get_model_info(level: int) -> ModelInfo:
    """Get model info for a given level.

    Args:
        level: Model level (1-3)

    Returns:
        ModelInfo for the level

    Raises:
        ValueError: If level is invalid
    """
    if level not in MODEL_LEVELS:
        raise ValueError(f"Invalid model level: {level}. Must be 1-3.")
    return MODEL_LEVELS[level]


def get_model_id(level: int) -> str:
    """Get model ID string for a given level.

    Args:
        level: Model level (1-3)

    Returns:
        Model ID string (e.g., "claude-haiku-4-5-20250929")
    """
    return get_model_info(level).id


def get_level_for_model_id(model_id: str) -> Optional[int]:
    """Get the level for a given model ID.

    Args:
        model_id: Model ID string

    Returns:
        Level (1-3) or None if not found
    """
    for level, info in MODEL_LEVELS.items():
        if info.id == model_id:
            return level
    return None


class ModelEscalationTracker:
    """Tracks consecutive failures for auto-escalation.

    Usage:
        tracker = ModelEscalationTracker(current_level=1)
        tracker.on_failure()  # 1st failure
        tracker.on_failure()  # 2nd failure
        tracker.on_failure()  # 3rd failure → returns new level 2
        tracker.on_success()  # reset counter
    """

    def __init__(
        self,
        current_level: int = DEFAULT_MODEL_LEVEL,
        auto_escalate: bool = True,
    ):
        """Initialize tracker.

        Args:
            current_level: Starting model level (1-3)
            auto_escalate: Whether to auto-escalate on failures
        """
        self.current_level = current_level
        self.auto_escalate = auto_escalate
        self.consecutive_failures = 0

    def on_failure(self) -> Optional[int]:
        """Record a failure and check if escalation needed.

        Returns:
            New model level if escalation occurred, None otherwise
        """
        self.consecutive_failures += 1
        logger.debug(
            f"Model failure recorded: {self.consecutive_failures}/{FAILURES_BEFORE_ESCALATION}"
        )

        if not self.auto_escalate:
            return None

        if self.consecutive_failures >= FAILURES_BEFORE_ESCALATION:
            if self.current_level < MAX_MODEL_LEVEL:
                self.current_level += 1
                self.consecutive_failures = 0
                old_level = self.current_level - 1
                logger.info(
                    f"Auto-escalating model: level {old_level} → {self.current_level} "
                    f"({get_model_info(self.current_level).name})"
                )
                return self.current_level

        return None

    def on_success(self) -> None:
        """Record a success, resetting the failure counter."""
        if self.consecutive_failures > 0:
            logger.debug(
                f"Success recorded, resetting failure counter from {self.consecutive_failures}"
            )
            self.consecutive_failures = 0

    def set_level(self, level: int) -> None:
        """Manually set model level.

        Args:
            level: New model level (1-3)

        Raises:
            ValueError: If level is invalid
        """
        if level not in MODEL_LEVELS:
            raise ValueError(f"Invalid model level: {level}. Must be 1-3.")
        old_level = self.current_level
        self.current_level = level
        self.consecutive_failures = 0
        logger.info(
            f"Model level changed: {old_level} → {level} "
            f"({get_model_info(level).name})"
        )

    def get_state(self) -> dict:
        """Get current state for serialization.

        Returns:
            Dict with current_level, auto_escalate, consecutive_failures
        """
        return {
            "current_level": self.current_level,
            "auto_escalate": self.auto_escalate,
            "consecutive_failures": self.consecutive_failures,
            "model_info": {
                "id": get_model_info(self.current_level).id,
                "name": get_model_info(self.current_level).name,
                "description": get_model_info(self.current_level).description,
                "icon_color": get_model_info(self.current_level).icon_color,
            },
        }
