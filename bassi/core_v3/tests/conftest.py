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
    MockAgentClient that automatically generates simple text responses.

    This enables E2E tests to work without manually queuing responses.
    """

    async def query(
        self, prompt: Any, /, *, session_id: str = "default"
    ) -> None:
        # Call parent to track the query
        await super().query(prompt, session_id=session_id)

        # Auto-generate a simple response if none was queued
        if not self._active_stream:
            from bassi.shared.sdk_types import AssistantMessage, TextBlock

            # Simple mock response wrapped in AssistantMessage (SDK format)
            response_text = "Mock agent response"
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

    # CRITICAL FIX: Manually initialize single agent BEFORE starting server
    # The @app.on_event("startup") doesn't fire when uvicorn runs in a background thread
    # We must create the agent using the session_factory (not _create_single_agent)
    # because _create_single_agent doesn't use the mock client factory
    print("\n🔧 [TEST] Manually initializing single agent with mock factory...")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        # Create a minimal workspace for the single agent
        from bassi.core_v3.interactive_questions import InteractiveQuestionService
        from bassi.core_v3.session_workspace import SessionWorkspace

        question_service = InteractiveQuestionService()
        # SessionWorkspace takes session_id and base_path
        # It will create physical_path as base_path / session_id
        workspace = SessionWorkspace(
            session_id="single_agent",
            base_path=tmp_workspace,
            create=True
        )

        # Use session_factory to create agent with mock client
        server_instance.single_agent = session_factory(question_service, workspace)

        # Connect the agent
        loop.run_until_complete(server_instance.single_agent.connect())
        print("✅ [TEST] Single agent initialized successfully with mock client")
    finally:
        # Don't close the loop - uvicorn needs it
        pass

    app = server_instance.app

    # CRITICAL: Clear startup/shutdown events since we manually initialized the agent
    # The @app.on_event("startup") handler would try to create the agent again
    app.router.on_startup = []
    app.router.on_shutdown = []
    print("🔧 [TEST] Cleared FastAPI startup/shutdown events (agent already initialized)")

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
        import sys

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
                    print(f"⚠️  [TEST] Thread is alive but server not responding after {max_retries * 0.1}s")
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
        # Cleanup single agent
        if server_instance.single_agent:
            print("\n🧹 [TEST] Cleaning up single agent...")
            loop.run_until_complete(server_instance.single_agent.disconnect())
            print("✅ [TEST] Agent disconnected")

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


