"""
bassi - Benno's Assistant

A personal AI agent for getting things done.
Uses Anthropic Agent SDK to interact via CLI.
"""

__version__ = "0.1.0"

# Export event classes for web UI
from bassi.agent import (
    AgentEvent,
    ContentDeltaEvent,
    ErrorEvent,
    EventType,
    MessageCompleteEvent,
    StatusUpdateEvent,
    ToolCallEndEvent,
    ToolCallStartEvent,
)

__all__ = [
    "__version__",
    "AgentEvent",
    "ContentDeltaEvent",
    "ErrorEvent",
    "EventType",
    "MessageCompleteEvent",
    "StatusUpdateEvent",
    "ToolCallEndEvent",
    "ToolCallStartEvent",
]
