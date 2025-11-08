"""
Pytest fixtures for bassi.core_v3 tests.
"""

import asyncio
import threading
import time
from contextlib import contextmanager

import httpx
import pytest
import uvicorn

from tests.fixtures.mock_agent_client import MockAgentClient


@pytest.fixture
def mock_agent_client() -> MockAgentClient:
    """Provide a mock AgentClient instance scoped per test."""
    return MockAgentClient()


@pytest.fixture(scope="session")
@pytest.mark.xdist_group(name="e2e_server")
def live_server():
    """
    Start web server on localhost:8765 for E2E tests.

    Uses xdist_group to ensure all E2E tests run in same worker (avoids multiple servers).
    Server runs for entire test session and is shared by all E2E tests.
    """
    from bassi.core_v3.web_server_v3 import get_app

    # Get the FastAPI app instance
    app = get_app()

    # Configure uvicorn to run in background thread
    config = uvicorn.Config(
        app=app,
        host="localhost",
        port=8765,
        log_level="error",  # Suppress logs during tests
    )
    server = uvicorn.Server(config)

    # Run server in background thread
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait for server to be ready (check health endpoint)
    base_url = "http://localhost:8765"
    max_retries = 50  # 5 seconds total
    for i in range(max_retries):
        try:
            response = httpx.get(f"{base_url}/health", timeout=0.5)
            if response.status_code == 200:
                print(f"\n✅ Test server ready at {base_url}")
                break
        except (httpx.ConnectError, httpx.ReadTimeout):
            if i == max_retries - 1:
                raise RuntimeError(
                    f"Test server failed to start after {max_retries * 0.1}s"
                )
            time.sleep(0.1)

    yield base_url

    # Shutdown server after tests
    server.should_exit = True
    thread.join(timeout=5)
