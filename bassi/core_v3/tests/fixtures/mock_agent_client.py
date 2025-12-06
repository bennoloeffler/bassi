"""
Mock implementation of the AgentClient protocol for unit tests.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Deque, List, Optional

from bassi.shared.agent_protocol import AgentClient


@dataclass
class MockAgentClient(AgentClient):
    """
    Lightweight AgentClient implementation used in tests.

    Tests can queue lists of messages that will be streamed back when the next
    ``query`` call occurs.  No real network or SDK interactions happen.
    """

    responses: Deque[List[Any]] = field(default_factory=deque)
    connected: bool = False
    interrupted: bool = False
    sent_prompts: list[dict[str, Any]] = field(default_factory=list)
    server_info: Optional[dict[str, Any]] = field(default_factory=dict)

    # Tracking counters for verification in tests
    connect_count: int = 0
    disconnect_count: int = 0

    _active_stream: Deque[Any] = field(default_factory=deque, init=False)

    def queue_response(self, *messages: Any) -> None:
        """Queue a list of messages to return for the next query."""
        self.responses.append(list(messages))

    async def connect(self) -> None:
        self.connected = True
        self.connect_count += 1

    async def disconnect(self) -> None:
        self.connected = False
        self.disconnect_count += 1

    async def query(
        self, prompt: Any, /, *, session_id: str = "default"
    ) -> None:
        # If prompt is an async generator, consume it to enable coverage
        consumed_prompt = prompt
        if hasattr(prompt, "__aiter__"):
            # Consume async generator
            consumed_messages = []
            async for msg in prompt:
                consumed_messages.append(msg)
            consumed_prompt = consumed_messages

        self.sent_prompts.append(
            {"prompt": consumed_prompt, "session_id": session_id}
        )
        if self.responses:
            self._active_stream = deque(self.responses.popleft())
        else:
            self._active_stream = deque()

    async def receive_response(self) -> AsyncIterator[Any]:
        while self._active_stream:
            yield self._active_stream.popleft()

    async def interrupt(self) -> None:
        self.interrupted = True

    async def get_server_info(self) -> Optional[dict[str, Any]]:
        return self.server_info

    async def set_permission_mode(self, mode: str) -> None:
        """Mock set_permission_mode - just tracks the mode."""
        self.permission_mode = mode

    async def set_model(self, model: str | None = None) -> None:
        """Mock set_model - just tracks the model."""
        self.model = model
