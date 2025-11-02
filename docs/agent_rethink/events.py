"""
Strongly typed event system for agent execution.

Every action generates an immutable event that flows through:
- Event store (append-only log)
- Subscribers (WebSocket, CLI, persistence)
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union


class EventType(str, Enum):
    """All possible event types in the system"""

    # Session lifecycle
    SESSION_STARTED = "session_started"
    SESSION_ENDED = "session_ended"

    # Agent execution
    PROMPT_RECEIVED = "prompt_received"
    PLAN_GENERATED = "plan_generated"
    MODEL_SWITCHED = "model_switched"

    # Streaming
    TOKEN_DELTA = "token_delta"
    CONTENT_BLOCK_START = "content_block_start"
    CONTENT_BLOCK_END = "content_block_end"

    # Tool execution
    TOOL_CALL_STARTED = "tool_call_started"
    TOOL_CALL_COMPLETED = "tool_call_completed"
    TOOL_CALL_FAILED = "tool_call_failed"

    # Hooks
    HOOK_EXECUTED = "hook_executed"
    HOOK_DENIED = "hook_denied"

    # Completion
    MESSAGE_COMPLETED = "message_completed"
    RUN_COMPLETED = "run_completed"
    RUN_CANCELLED = "run_cancelled"

    # Errors
    ERROR = "error"


@dataclass(frozen=True)
class BaseEvent:
    """Base class for all events - immutable"""

    type: EventType
    timestamp: datetime = field(default_factory=datetime.utcnow)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str = ""
    session_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for transport"""
        return {
            "type": self.type.value,
            "timestamp": self.timestamp.isoformat(),
            "event_id": self.event_id,
            "run_id": self.run_id,
            "session_id": self.session_id,
        }


@dataclass(frozen=True)
class SessionEvent(BaseEvent):
    """Session lifecycle events"""

    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {**super().to_dict(), "metadata": self.metadata}


@dataclass(frozen=True)
class PromptEvent(BaseEvent):
    """User prompt received"""

    type: EventType = EventType.PROMPT_RECEIVED
    content: str = ""
    model_preference: Optional[str] = None
    plan_mode: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            **super().to_dict(),
            "content": self.content,
            "model_preference": self.model_preference,
            "plan_mode": self.plan_mode,
        }


@dataclass(frozen=True)
class PlanEvent(BaseEvent):
    """Generated plan before execution"""

    type: EventType = EventType.PLAN_GENERATED
    plan_steps: List[str] = field(default_factory=list)
    plan_text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            **super().to_dict(),
            "plan_steps": self.plan_steps,
            "plan_text": self.plan_text,
        }


@dataclass(frozen=True)
class TokenDeltaEvent(BaseEvent):
    """Streaming token delta"""

    type: EventType = EventType.TOKEN_DELTA
    delta: str = ""
    block_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            **super().to_dict(),
            "delta": self.delta,
            "block_id": self.block_id,
        }


@dataclass(frozen=True)
class ToolCallEvent(BaseEvent):
    """Tool call lifecycle"""

    tool_name: str = ""
    tool_id: str = ""
    tool_input: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            **super().to_dict(),
            "tool_name": self.tool_name,
            "tool_id": self.tool_id,
            "tool_input": self.tool_input,
        }


@dataclass(frozen=True)
class ToolResultEvent(BaseEvent):
    """Tool execution result"""

    type: EventType = EventType.TOOL_CALL_COMPLETED
    tool_name: str = ""
    tool_id: str = ""
    result: Any = None
    success: bool = True
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            **super().to_dict(),
            "tool_name": self.tool_name,
            "tool_id": self.tool_id,
            "result": result,
            "success": self.success,
            "duration_ms": self.duration_ms,
        }


@dataclass(frozen=True)
class HookEvent(BaseEvent):
    """Hook execution"""

    type: EventType = EventType.HOOK_EXECUTED
    hook_name: str = ""
    hook_type: str = ""  # pre_tool, post_tool, etc
    decision: str = "allow"  # allow, deny, modify
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            **super().to_dict(),
            "hook_name": self.hook_name,
            "hook_type": self.hook_type,
            "decision": self.decision,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ErrorEvent(BaseEvent):
    """Error occurred"""

    type: EventType = EventType.ERROR
    error_type: str = ""
    error_message: str = ""
    traceback: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            **super().to_dict(),
            "error_type": self.error_type,
            "error_message": self.error_message,
            "traceback": self.traceback,
            "context": self.context,
        }


@dataclass(frozen=True)
class MessageCompleteEvent(BaseEvent):
    """Message execution completed"""

    type: EventType = EventType.MESSAGE_COMPLETED
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    duration_ms: float = 0.0
    model_used: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            **super().to_dict(),
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": self.cost_usd,
            "duration_ms": self.duration_ms,
            "model_used": self.model_used,
        }


# Union type for all events
AgentEvent = Union[
    SessionEvent,
    PromptEvent,
    PlanEvent,
    TokenDeltaEvent,
    ToolCallEvent,
    ToolResultEvent,
    HookEvent,
    ErrorEvent,
    MessageCompleteEvent,
]
