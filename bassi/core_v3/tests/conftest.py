"""
Pytest fixtures for bassi.core_v3 tests.
"""

import threading
import time
from typing import Any

import httpx
import pytest
import uvicorn

from bassi.core_v3.agent_session import BassiAgentSession, SessionConfig
from bassi.core_v3.interactive_questions import InteractiveQuestionService
from bassi.core_v3.session_workspace import SessionWorkspace
from bassi.core_v3.tests.fixtures.mock_agent_client import MockAgentClient
from bassi.core_v3.tools import create_bassi_tools
from bassi.core_v3.web_server_v3 import WebUIServerV3
from bassi.shared.sdk_loader import create_sdk_mcp_server


@pytest.fixture
def mock_agent_client() -> MockAgentClient:
    """Provide a mock AgentClient instance scoped per test."""
    return MockAgentClient()


class AutoRespondingMockAgentClient(MockAgentClient):
    """
    MockAgentClient that automatically generates context-aware responses.

    This enables E2E tests to work without manually queuing responses.
    The mock analyzes the conversation history and generates relevant responses.
    """

    def _extract_user_message(self, prompt: Any) -> str:
        """
        Extract the user's LATEST message text from the prompt.

        The prompt can be:
        1. A list of SDK Message objects (UserMessage, AssistantMessage, etc.)
        2. A list of messages consumed from async generator (control protocol format)
        3. A dict with user message content
        """
        # Handle list of messages
        if isinstance(prompt, list):
            # Look through messages (could be SDK objects or dicts)
            for msg in prompt:
                # Handle dict format (from consumed async generator)
                if isinstance(msg, dict):
                    # Check for control protocol format: {'type': 'user', 'message': {...}}
                    if msg.get("type") == "user" and "message" in msg:
                        message_data = msg["message"]
                        content = message_data.get("content", [])
                        if isinstance(content, list):
                            # Get the LAST text block (the actual user query, not history)
                            for block in reversed(content):
                                if (
                                    isinstance(block, dict)
                                    and block.get("type") == "text"
                                ):
                                    text = block.get("text", "")
                                    # Skip history blocks
                                    if not text.startswith(
                                        "[CONVERSATION HISTORY"
                                    ):
                                        return text.lower()
                    # Check for user_message in older control protocol format
                    elif "user_message" in msg:
                        content = msg["user_message"].get("content", [])
                        if isinstance(content, list):
                            for block in reversed(content):
                                if (
                                    isinstance(block, dict)
                                    and block.get("type") == "text"
                                ):
                                    return block.get("text", "").lower()
                    # Check for direct content field
                    elif "content" in msg:
                        content = msg.get("content", [])
                        if isinstance(content, list):
                            for block in reversed(content):
                                if (
                                    isinstance(block, dict)
                                    and block.get("type") == "text"
                                ):
                                    return block.get("text", "").lower()
                # Handle SDK Message objects
                elif hasattr(msg, "content"):
                    # Handle list of content blocks
                    if isinstance(msg.content, list):
                        for block in reversed(msg.content):
                            if hasattr(block, "text"):
                                return block.text.lower()
                    # Handle string content
                    elif isinstance(msg.content, str):
                        return msg.content.lower()
        # Fallback: return empty string
        return ""

    def _generate_contextual_response(
        self, user_message: str, full_prompt_text: str
    ) -> str:
        """
        Generate a context-aware response based on user message and conversation context.

        This mock agent simulates memory by:
        1. Extracting information from previous messages (e.g., "my name is X")
        2. Recalling that information when asked (e.g., "what's my name?")

        Args:
            user_message: The latest user message (lowercase)
            full_prompt_text: The full prompt including conversation context (lowercase)
        """
        user_msg_lower = user_message.lower()

        # Pattern 1: User introduces themselves ("my name is X")
        if "my name is" in user_msg_lower:
            # Extract the name after "my name is"
            name_start = user_msg_lower.find("my name is") + len("my name is")
            name = user_message[name_start:].strip()
            # Remove trailing punctuation
            name = name.rstrip(".,!?")
            return f"Nice to meet you, {name}! I'll remember your name."

        # Pattern 2: User asks for their name ("what's my name?")
        if (
            "what" in user_msg_lower
            and "my name" in user_msg_lower
            or "what's my name" in user_msg_lower
        ):
            # Search in the full prompt (includes conversation context)
            if "my name is" in full_prompt_text:
                # Extract the name from context
                name_start = full_prompt_text.find("my name is") + len(
                    "my name is"
                )
                # Find the end of the name (first newline or punctuation)
                rest = full_prompt_text[name_start:].strip()
                # Split by common delimiters
                for delimiter in ["\n", ".", ",", "!", "?"]:
                    if delimiter in rest:
                        rest = rest.split(delimiter)[0]
                        break
                name = rest.strip()
                if name:
                    return f"Your name is {name}."

            return "I don't recall you telling me your name."

        # Default response
        return "Mock agent response"

    def _extract_full_prompt_text(self, prompt: Any) -> str:
        """
        Extract ALL text from the prompt, including conversation context.

        This is used to search for information across the entire conversation.
        """
        full_text = ""

        if isinstance(prompt, list):
            for msg in prompt:
                # Handle dict format (from consumed async generator)
                if isinstance(msg, dict):
                    # Check for control protocol format: {'type': 'user', 'message': {...}}
                    if msg.get("type") == "user" and "message" in msg:
                        message_data = msg["message"]
                        content = message_data.get("content", [])
                        if isinstance(content, list):
                            for block in content:
                                if (
                                    isinstance(block, dict)
                                    and block.get("type") == "text"
                                ):
                                    full_text += block.get("text", "") + " "
                    # Check for user_message in older control protocol format
                    elif "user_message" in msg:
                        content = msg["user_message"].get("content", [])
                        if isinstance(content, list):
                            for block in content:
                                if (
                                    isinstance(block, dict)
                                    and block.get("type") == "text"
                                ):
                                    full_text += block.get("text", "") + " "
                    # Check for direct content field
                    elif "content" in msg:
                        content = msg.get("content", [])
                        if isinstance(content, list):
                            for block in content:
                                if (
                                    isinstance(block, dict)
                                    and block.get("type") == "text"
                                ):
                                    full_text += block.get("text", "") + " "
                # Handle SDK Message objects
                elif hasattr(msg, "content"):
                    if isinstance(msg.content, list):
                        for block in msg.content:
                            if hasattr(block, "text"):
                                full_text += block.text + " "
                    elif isinstance(msg.content, str):
                        full_text += msg.content + " "

        return full_text.lower()

    async def query(
        self, prompt: Any, /, *, session_id: str = "default"
    ) -> None:
        # Call parent to track the query (this consumes the async generator)
        await super().query(prompt, session_id=session_id)

        # Auto-generate a context-aware response if none was queued
        if not self._active_stream:
            from bassi.shared.sdk_types import AssistantMessage, TextBlock

            # Get the consumed prompt from sent_prompts (parent class stores it there)
            if self.sent_prompts:
                last_prompt = self.sent_prompts[-1]["prompt"]

                # Extract user message from consumed prompt (latest message)
                user_message = self._extract_user_message(last_prompt)

                # Extract full prompt text (includes conversation context)
                full_prompt_text = self._extract_full_prompt_text(last_prompt)

                # Generate context-aware response
                response_text = self._generate_contextual_response(
                    user_message, full_prompt_text
                )
            else:
                # Fallback if no prompts tracked
                response_text = "Mock agent response"

            # Wrap in SDK format
            text_block = TextBlock(text=response_text)
            assistant_msg = AssistantMessage(
                content=[text_block], model="mock-model"
            )
            self._active_stream.append(assistant_msg)


def create_mock_session_factory():
    """
    Create session factory using AutoRespondingMockAgentClient for E2E tests.

    This factory creates BassiAgentSession instances that use the mock client
    instead of the real Claude API, allowing tests to run without API keys
    and without making real API calls.
    """

    def mock_client_factory(config: SessionConfig):
        """Factory that creates AutoRespondingMockAgentClient instances"""
        return AutoRespondingMockAgentClient()

    def factory(
        question_service: InteractiveQuestionService,
        workspace: SessionWorkspace,
    ):
        # Create Bassi interactive tools (including AskUserQuestion)
        bassi_tools = create_bassi_tools(question_service)
        bassi_mcp_server = create_sdk_mcp_server(
            name="bassi-interactive", version="1.0.0", tools=bassi_tools
        )

        # Create MCP registry (minimal for tests)
        mcp_servers = {
            "bassi-interactive": bassi_mcp_server,
        }

        # Generate workspace context
        workspace_context = workspace.get_workspace_context()

        config = SessionConfig(
            allowed_tools=["*"],
            system_prompt=workspace_context,
            permission_mode="bypassPermissions",
            mcp_servers=mcp_servers,
            setting_sources=["project", "local"],
        )

        # Create session with mock client factory
        session = BassiAgentSession(
            config, client_factory=mock_client_factory
        )
        # Attach workspace to session for later access
        session.workspace = workspace
        return session

    return factory


@pytest.fixture(scope="session")
def live_server(tmp_path_factory):
    """
    Start web server on localhost:8765 for E2E tests.

    Uses mock agent client to avoid real API calls.
    Server runs for entire test session and is shared by all E2E tests.
    Uses isolated temporary workspace to avoid session pollution.

    NOTE: Tests using this fixture MUST have @pytest.mark.xdist_group(name="e2e_server")
    to ensure they run in the same worker. Markers on fixtures have no effect.
    """
    import asyncio

    # Create isolated temporary workspace for tests
    tmp_workspace = tmp_path_factory.mktemp("e2e_chats")

    # Create server with mock session factory and isolated workspace
    session_factory = create_mock_session_factory()
    server_instance = WebUIServerV3(
        workspace_base_path=str(tmp_workspace),
        session_factory=session_factory,
    )

    # CRITICAL FIX: Manually start the Agent Pool BEFORE starting server
    # The lifespan handler doesn't fire when uvicorn runs in a background thread
    # We must start the pool manually to ensure agents are ready
    #
    # IMPORTANT: Do NOT use asyncio.set_event_loop() here!
    # Setting a global event loop pollutes pytest-asyncio's ability to manage
    # event loops for async tests that run later in the session.
    print("\n🔧 [TEST] Manually starting Agent Pool with mock factory...")
    loop = asyncio.new_event_loop()
    # Note: We do NOT call asyncio.set_event_loop(loop) to avoid polluting global state
    try:
        # Start the agent pool (this pre-connects agents with mock client)
        loop.run_until_complete(server_instance.agent_pool.start())
        print("✅ [TEST] Agent Pool started successfully with mock client")
    except Exception as e:
        print(f"❌ [TEST] Failed to start Agent Pool: {e}")
        raise

    app = server_instance.app

    # CRITICAL: Replace lifespan with no-op since we manually started the pool
    # The lifespan handler would try to start the pool again
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def noop_lifespan(app):
        yield  # No startup/shutdown actions

    app.router.lifespan_context = noop_lifespan
    print(
        "🔧 [TEST] Replaced lifespan with no-op (pool already started manually)"
    )

    # Configure uvicorn to run in background thread
    # Use port 18765 to avoid conflict with production server on 8765
    config = uvicorn.Config(
        app=app,
        host="localhost",
        port=18765,
        log_level="error",  # Suppress logs during tests
    )
    server = uvicorn.Server(config)

    # Run server in background thread (daemon=True allows workers to exit cleanly)
    # When using pytest-xdist + coverage, daemon threads are REQUIRED to prevent
    # workers from hanging during coverage finalization.
    def run_server_with_loop():
        """Run uvicorn server with its own event loop in the thread."""
        import asyncio

        async def serve_async():
            """Async wrapper for server.serve()"""
            print("🚀 [TEST] Starting server.serve() task...", flush=True)
            await server.serve()
            print("⚠️  [TEST] Uvicorn server task completed", flush=True)

        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Run server.serve() in the loop
            # This will block until server is shut down
            loop.run_until_complete(serve_async())
            print("⚠️  [TEST] Uvicorn server exited", flush=True)
        except Exception as e:
            print(f"❌ [TEST] Server crashed: {e}", flush=True)
            import traceback

            traceback.print_exc()
        finally:
            loop.close()
            print("🔚 [TEST] Thread cleanup complete", flush=True)

    thread = threading.Thread(target=run_server_with_loop, daemon=True)
    thread.start()

    # Give server a moment to start binding to port
    print("⏳ [TEST] Waiting for server to bind to port...")
    time.sleep(2.0)  # Increased to 2.0s to give server more time

    # Check if thread is still alive
    if not thread.is_alive():
        print("❌ [TEST] Server thread died immediately!")
        raise RuntimeError("Server thread exited before binding to port")

    # Wait for server to be ready (check health endpoint)
    base_url = "http://localhost:18765"
    max_retries = 100  # 10 seconds total
    for i in range(max_retries):
        try:
            response = httpx.get(f"{base_url}/health", timeout=0.5)
            if response.status_code == 200:
                print(f"✅ [TEST] Test server ready at {base_url}")
                break
        except (httpx.ConnectError, httpx.ReadTimeout):
            if i == max_retries - 1:
                # Check if thread is still alive
                if thread.is_alive():
                    print(
                        f"⚠️  [TEST] Thread is alive but server not responding after {max_retries * 0.1}s"
                    )
                else:
                    print("❌ [TEST] Thread died during startup")
                raise RuntimeError(
                    f"Test server failed to start after {max_retries * 0.1}s"
                )
            time.sleep(0.1)

    yield base_url

    # Shutdown server after tests
    # With daemon=True, the thread will automatically terminate when the worker exits.
    # This allows pytest-xdist + coverage to finalize properly without hanging.
    try:
        # Cleanup Agent Pool
        print("\n🧹 [TEST] Cleaning up Agent Pool...")
        loop.run_until_complete(
            server_instance.agent_pool.shutdown(force=True)
        )
        print("✅ [TEST] Agent Pool shutdown complete")

        # Signal server to shutdown gracefully
        server.should_exit = True
        if hasattr(server, "force_exit"):
            server.force_exit = True

        # Wake up the server by making a dummy request
        try:
            httpx.get(f"{base_url}/health", timeout=0.5)
        except Exception:
            pass  # Server might already be shutting down

        # Give server brief time to cleanup (don't block worker exit)
        thread.join(timeout=0.5)

    except Exception as e:
        # Don't let cleanup errors block worker exit
        print(f"⚠️ [TEST] Warning: Error during server shutdown: {e}")
    finally:
        # Close the event loop
        try:
            loop.close()
        except Exception:
            pass


@pytest.fixture(scope="session")
def running_server(live_server):
    """
    Alias for live_server - provides running server URL.

    Returns:
        str: Base URL of running test server (e.g., "http://localhost:18765")
    """
    return live_server


@pytest.fixture(scope="session")
def chrome_devtools_client():
    """
    Provide Chrome DevTools MCP client for E2E browser testing.

    Returns an object with methods:
    - navigate_page(url): Navigate to URL
    - take_snapshot(): Get accessibility tree snapshot
    - evaluate_script(function): Execute JavaScript
    - click(uid): Click element by accessibility tree UID
    - list_console_messages(): Get console logs

    Raises:
        pytest.skip: If chrome-devtools MCP server is not available
    """
    try:
        # Import MCP client utilities
        # This will fail if chrome-devtools MCP is not configured
        from bassi.core_v3.tests.fixtures.mcp_client import get_mcp_client

        client = get_mcp_client("chrome-devtools")
        return client
    except Exception as e:
        pytest.skip(f"Chrome DevTools MCP not available: {e}")
