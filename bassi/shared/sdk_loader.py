"""
Optional Claude Agent SDK loader with test-friendly fallbacks.

The Claude Agent SDK is not available in all environments (e.g., CI for this OSS
repo).  Importing it unconditionally would break tests at collection time.  This
module provides thin wrappers that expose the real classes when the SDK is
installed and lightweight stubs otherwise.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Callable, TypeVar

__all__ = [
    "ClaudeAgentOptions",
    "ClaudeSDKClient",
    "MissingClaudeSDKError",
    "SDK_AVAILABLE",
    "create_sdk_mcp_server",
    "tool",
]


class MissingClaudeSDKError(RuntimeError):
    """Raised when code attempts to use SDK functionality without the package."""


T = TypeVar("T")


def _identity_decorator(func: T) -> T:
    return func


try:  # pragma: no cover - exercised only when SDK is installed
    from claude_agent_sdk import (
        ClaudeAgentOptions,
        ClaudeSDKClient,
        create_sdk_mcp_server,
        tool,
    )

    SDK_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover - default in CI/tests
    SDK_AVAILABLE = False

    class ClaudeAgentOptions(SimpleNamespace):  # type: ignore[override]
        """
        Minimal stand-in for the real ``ClaudeAgentOptions``.

        Stores attributes for inspection in tests.  Attempting to convert it
        back into a real SDK object requires the actual package.
        """

        pass

    class ClaudeSDKClient:
        """
        Stub client that raises :class:`MissingClaudeSDKError` when used.
        """

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self._error = MissingClaudeSDKError(
                "claude_agent_sdk is not installed; real Agent SDK actions "
                "are unavailable in this environment."
            )

        async def __aenter__(self):
            raise self._error

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return False

        async def connect(self) -> None:
            raise self._error

        async def disconnect(self) -> None:
            raise self._error

        async def query(self, *args: Any, **kwargs: Any) -> None:
            raise self._error

        async def receive_response(self):
            raise self._error

        async def get_server_info(self):
            raise self._error

        async def interrupt(self) -> None:
            raise self._error

    def create_sdk_mcp_server(
        *, name: str, version: str, tools: list[Callable[..., Any]]
    ) -> dict[str, Any]:
        """
        Stub MCP server factory.  Returns metadata so tests can inspect registry
        contents even without the SDK.
        """

        return {
            "name": name,
            "version": version,
            "tools": tools,
            "sdk_available": False,
        }

    def tool(*decorator_args: Any, **decorator_kwargs: Any):
        """
        Decorator stub.  Returns the wrapped function unchanged so MCP server
        modules remain importable without the SDK.
        """

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            return func

        return decorator
