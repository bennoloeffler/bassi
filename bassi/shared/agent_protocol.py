"""
Agent client abstraction and default Claude SDK factory.

The production system communicates with the Claude Agent SDK, but our test
environments run without the proprietary ``claude-agent-sdk`` package.  This
module defines a light-weight protocol plus a default factory that encapsulates
all direct imports of the SDK so callers can depend on a stable interface and
easily inject mocks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator, Callable, Optional, Protocol

if False:  # pragma: no cover - help type checkers without runtime import
    from bassi.core_v3.agent_session import SessionConfig


__all__ = [
    "AgentClient",
    "AgentClientFactory",
    "ClaudeAgentClient",
    "build_claude_agent_options",
    "default_claude_client_factory",
    "resolve_model_id",
]


class AgentClient(Protocol):
    """Protocol describing the subset of SDK client features we rely on."""

    async def connect(self) -> None: ...

    async def disconnect(self) -> None: ...

    async def query(
        self, prompt: Any, /, *, session_id: str = "default"
    ) -> None: ...

    async def receive_response(self) -> AsyncIterator[Any]: ...

    async def interrupt(self) -> None: ...

    async def get_server_info(self) -> Optional[dict[str, Any]]: ...


AgentClientFactory = Callable[["SessionConfig"], AgentClient]


@dataclass
class ClaudeAgentClient:
    """
    Adapter that wraps ``ClaudeSDKClient`` behind the :class:`AgentClient`
    protocol.
    """

    sdk_client: Any

    async def connect(self) -> None:
        await self.sdk_client.connect()

    async def disconnect(self) -> None:
        await self.sdk_client.disconnect()

    async def query(
        self, prompt: Any, /, *, session_id: str = "default"
    ) -> None:
        await self.sdk_client.query(prompt, session_id=session_id)

    async def receive_response(self) -> AsyncIterator[Any]:
        async for message in self.sdk_client.receive_response():
            yield message

    async def interrupt(self) -> None:
        await self.sdk_client.interrupt()

    async def get_server_info(self) -> Optional[dict[str, Any]]:
        return await self.sdk_client.get_server_info()


def resolve_model_id(config: "SessionConfig") -> str:
    """Get the base model ID (without thinking suffix - thinking is handled via parameter)."""
    return getattr(config, "model_id", "claude-sonnet-4-5-20250929")


def default_claude_client_factory(config: "SessionConfig") -> AgentClient:
    """
    Build a real Claude SDK client using ``SessionConfig`` values.

    Importing ``claude_agent_sdk`` is delayed until this function is called so
    that modules can be imported without the package in test environments.
    """

    from bassi.shared.sdk_loader import ClaudeSDKClient

    options = build_claude_agent_options(config)
    sdk_client = ClaudeSDKClient(options=options)
    return ClaudeAgentClient(sdk_client=sdk_client)


def build_claude_agent_options(config: "SessionConfig"):
    """Construct ``ClaudeAgentOptions`` from ``SessionConfig``."""

    from bassi.shared.sdk_loader import ClaudeAgentOptions

    # Build options - note: SDK doesn't support 'thinking' parameter
    # Thinking mode would need to be enabled via model suffix if supported
    options = ClaudeAgentOptions(
        model=resolve_model_id(config),
        allowed_tools=getattr(config, "allowed_tools", None),
        system_prompt=getattr(config, "system_prompt", None),
        permission_mode=getattr(config, "permission_mode", None),
        mcp_servers=getattr(config, "mcp_servers", None),
        cwd=getattr(config, "cwd", None),
        can_use_tool=getattr(config, "can_use_tool", None),
        hooks=getattr(config, "hooks", None),
        setting_sources=getattr(config, "setting_sources", None),
        include_partial_messages=getattr(
            config, "include_partial_messages", False
        ),
        max_thinking_tokens=getattr(config, "max_thinking_tokens", 10000),
    )

    if getattr(config, "resume_session_id", None):
        options.resume = config.resume_session_id

    return options
