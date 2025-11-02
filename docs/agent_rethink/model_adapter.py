"""
Model Adapter Interface - Unified execution path for all LLM providers.

Adapters:
- AnthropicAdapter (using Agent SDK)
- OpenAICompatAdapter (for DeepSeek, Moonshot, etc)

All adapters emit the same events, ensuring consistent behavior.
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Optional

from event_store import EventStore
from events import (
    AgentEvent,
    ErrorEvent,
    TokenDeltaEvent,
    ToolCallEvent,
    ToolResultEvent,
)

logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """Model configuration"""

    provider: str  # anthropic, openai_compat
    model_name: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    max_tokens: int = 4096
    temperature: float = 1.0


@dataclass
class Message:
    """Unified message format"""

    role: str  # user, assistant, tool
    content: str | List[Dict[str, Any]]  # Text or content blocks
    tool_call_id: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None


class ModelAdapter(ABC):
    """
    Base class for all model adapters.

    Responsibilities:
    - Stream tokens
    - Execute tool calls
    - Emit events to EventStore
    - Handle errors gracefully
    """

    def __init__(
        self,
        config: ModelConfig,
        event_store: EventStore,
        session_id: str,
        run_id: str,
    ):
        self.config = config
        self.event_store = event_store
        self.session_id = session_id
        self.run_id = run_id

    @abstractmethod
    async def execute(
        self,
        messages: List[Message],
        tools: List[Dict[str, Any]],
        tool_executor: "ToolExecutor",  # type: ignore
    ) -> AsyncIterator[AgentEvent]:
        """
        Execute model with messages and tools.

        Yields events as they occur (streaming).

        Args:
            messages: Conversation history
            tools: Available tools (unified schema)
            tool_executor: Callback to execute tools

        Yields:
            AgentEvent instances
        """
        pass

    async def _emit(self, event: AgentEvent) -> None:
        """Helper to emit event"""
        await self.event_store.append(event)


# ============================================================
# Anthropic Adapter (using Agent SDK)
# ============================================================


class AnthropicAdapter(ModelAdapter):
    """
    Adapter for Anthropic models using Agent SDK.

    Uses native tool support and streaming.
    """

    async def execute(
        self,
        messages: List[Message],
        tools: List[Dict[str, Any]],
        tool_executor,
    ) -> AsyncIterator[AgentEvent]:
        """Execute with Anthropic Agent SDK"""
        try:
            # Import here to avoid hard dependency
            from anthropic import Anthropic
            from anthropic.types import (
                ToolUseBlock,
            )

            client = Anthropic(api_key=self.config.api_key)

            # Convert messages to Anthropic format
            anthropic_messages = self._convert_messages(messages)

            # Convert tools to Anthropic format
            anthropic_tools = self._convert_tools(tools)

            # Stream completion
            current_block_id = None
            tool_calls_in_flight: Dict[str, asyncio.Task] = {}

            async with client.messages.stream(
                model=self.config.model_name,
                messages=anthropic_messages,
                tools=anthropic_tools,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
            ) as stream:
                async for event in stream:
                    # Token delta
                    if hasattr(event, "delta") and hasattr(
                        event.delta, "text"
                    ):
                        current_block_id = current_block_id or str(
                            event.index
                        )
                        yield TokenDeltaEvent(
                            delta=event.delta.text,
                            block_id=current_block_id,
                            session_id=self.session_id,
                            run_id=self.run_id,
                        )

                    # Tool use
                    if hasattr(event, "content_block") and isinstance(
                        event.content_block, ToolUseBlock
                    ):
                        tool_block = event.content_block
                        tool_id = tool_block.id

                        # Emit tool call started
                        yield ToolCallEvent(
                            tool_name=tool_block.name,
                            tool_id=tool_id,
                            tool_input=tool_block.input,
                            session_id=self.session_id,
                            run_id=self.run_id,
                        )

                        # Execute tool concurrently
                        task = asyncio.create_task(
                            self._execute_tool(
                                tool_block.name,
                                tool_block.input,
                                tool_id,
                                tool_executor,
                            )
                        )
                        tool_calls_in_flight[tool_id] = task

                # Wait for all tool calls to complete
                if tool_calls_in_flight:
                    results = await asyncio.gather(
                        *tool_calls_in_flight.values(), return_exceptions=True
                    )
                    for (tool_id, task), result in zip(
                        tool_calls_in_flight.items(), results
                    ):
                        if isinstance(result, Exception):
                            yield ErrorEvent(
                                error_type="tool_execution",
                                error_message=str(result),
                                context={"tool_id": tool_id},
                                session_id=self.session_id,
                                run_id=self.run_id,
                            )

        except Exception as e:
            logger.error(f"Anthropic adapter error: {e}", exc_info=True)
            yield ErrorEvent(
                error_type="model_execution",
                error_message=str(e),
                traceback=str(e.__traceback__),
                session_id=self.session_id,
                run_id=self.run_id,
            )

    async def _execute_tool(
        self, tool_name: str, tool_input: Dict, tool_id: str, tool_executor
    ) -> None:
        """Execute tool and emit events"""
        import time

        start = time.time()
        try:
            result = await tool_executor.execute(tool_name, tool_input)
            duration_ms = (time.time() - start) * 1000

            await self._emit(
                ToolResultEvent(
                    tool_name=tool_name,
                    tool_id=tool_id,
                    result=result,
                    success=True,
                    duration_ms=duration_ms,
                    session_id=self.session_id,
                    run_id=self.run_id,
                )
            )
        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            await self._emit(
                ToolResultEvent(
                    tool_name=tool_name,
                    tool_id=tool_id,
                    result={"error": str(e)},
                    success=False,
                    duration_ms=duration_ms,
                    session_id=self.session_id,
                    run_id=self.run_id,
                )
            )

    def _convert_messages(self, messages: List[Message]) -> List[Dict]:
        """Convert unified messages to Anthropic format"""
        result = []
        for msg in messages:
            if msg.role == "tool":
                # Tool result
                result.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg.tool_call_id,
                                "content": msg.content,
                            }
                        ],
                    }
                )
            else:
                result.append({"role": msg.role, "content": msg.content})
        return result

    def _convert_tools(self, tools: List[Dict[str, Any]]) -> List[Dict]:
        """Convert unified tool schema to Anthropic format"""
        return tools  # Assuming already in Anthropic format


# ============================================================
# OpenAI-Compatible Adapter (DeepSeek, Moonshot, etc)
# ============================================================


class OpenAICompatAdapter(ModelAdapter):
    """
    Adapter for OpenAI-compatible providers (DeepSeek, Moonshot, etc).

    Uses function calling and streaming.
    """

    async def execute(
        self,
        messages: List[Message],
        tools: List[Dict[str, Any]],
        tool_executor,
    ) -> AsyncIterator[AgentEvent]:
        """Execute with OpenAI-compatible API"""
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
            )

            # Convert messages
            openai_messages = self._convert_messages(messages)

            # Convert tools to OpenAI function format
            functions = self._convert_tools_to_functions(tools)

            # Stream completion
            stream = await client.chat.completions.create(
                model=self.config.model_name,
                messages=openai_messages,
                tools=functions if functions else None,
                stream=True,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )

            current_block_id = "text-0"
            tool_calls_buffer = {}

            async for chunk in stream:
                choice = chunk.choices[0]

                # Token delta
                if choice.delta.content:
                    yield TokenDeltaEvent(
                        delta=choice.delta.content,
                        block_id=current_block_id,
                        session_id=self.session_id,
                        run_id=self.run_id,
                    )

                # Tool calls (streaming)
                if choice.delta.tool_calls:
                    for tc_delta in choice.delta.tool_calls:
                        idx = tc_delta.index
                        if idx not in tool_calls_buffer:
                            tool_calls_buffer[idx] = {
                                "id": tc_delta.id,
                                "name": "",
                                "arguments": "",
                            }

                        if tc_delta.function.name:
                            tool_calls_buffer[idx][
                                "name"
                            ] = tc_delta.function.name

                        if tc_delta.function.arguments:
                            tool_calls_buffer[idx][
                                "arguments"
                            ] += tc_delta.function.arguments

                # End of stream - execute accumulated tool calls
                if choice.finish_reason == "tool_calls":
                    for tc in tool_calls_buffer.values():
                        tool_name = tc["name"]
                        tool_id = tc["id"]
                        try:
                            tool_input = json.loads(tc["arguments"])
                        except json.JSONDecodeError:
                            tool_input = {"raw": tc["arguments"]}

                        # Emit tool call
                        yield ToolCallEvent(
                            tool_name=tool_name,
                            tool_id=tool_id,
                            tool_input=tool_input,
                            session_id=self.session_id,
                            run_id=self.run_id,
                        )

                        # Execute tool
                        await self._execute_tool(
                            tool_name, tool_input, tool_id, tool_executor
                        )

        except Exception as e:
            logger.error(f"OpenAI-compat adapter error: {e}", exc_info=True)
            yield ErrorEvent(
                error_type="model_execution",
                error_message=str(e),
                session_id=self.session_id,
                run_id=self.run_id,
            )

    async def _execute_tool(
        self, tool_name: str, tool_input: Dict, tool_id: str, tool_executor
    ) -> None:
        """Execute tool and emit event"""
        import time

        start = time.time()
        try:
            result = await tool_executor.execute(tool_name, tool_input)
            duration_ms = (time.time() - start) * 1000

            await self._emit(
                ToolResultEvent(
                    tool_name=tool_name,
                    tool_id=tool_id,
                    result=result,
                    success=True,
                    duration_ms=duration_ms,
                    session_id=self.session_id,
                    run_id=self.run_id,
                )
            )
        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            await self._emit(
                ToolResultEvent(
                    tool_name=tool_name,
                    tool_id=tool_id,
                    result={"error": str(e)},
                    success=False,
                    duration_ms=duration_ms,
                    session_id=self.session_id,
                    run_id=self.run_id,
                )
            )

    def _convert_messages(self, messages: List[Message]) -> List[Dict]:
        """Convert to OpenAI format"""
        result = []
        for msg in messages:
            if msg.role == "tool":
                result.append(
                    {
                        "role": "tool",
                        "tool_call_id": msg.tool_call_id,
                        "content": (
                            json.dumps(msg.content)
                            if isinstance(msg.content, dict)
                            else msg.content
                        ),
                    }
                )
            else:
                result.append({"role": msg.role, "content": msg.content})
        return result

    def _convert_tools_to_functions(
        self, tools: List[Dict[str, Any]]
    ) -> List[Dict]:
        """Convert unified tool schema to OpenAI function format"""
        functions = []
        for tool in tools:
            functions.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get(
                            "input_schema",
                            {"type": "object", "properties": {}},
                        ),
                    },
                }
            )
        return functions
