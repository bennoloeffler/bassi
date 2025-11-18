"""
E2E test fixtures - Playwright browser tests.

INFRASTRUCTURE:
- Uses pytest-playwright (NOT pytest-asyncio)
- All tests are synchronous (def test_*, not async def)
- Never use @pytest.mark.asyncio with Playwright
- Playwright provides 'page' fixture automatically

EXAMPLE TEST:
    def test_homepage(page, running_server):
        page.goto(running_server["base_url"])
        assert "Bassi" in page.title()

NOTE: Currently no E2E tests exist. This file is a placeholder
      for when Playwright tests are added in the future.
"""

import socket

import pytest


def free_port() -> int:
    """Get an ephemeral port from the OS."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    _, port = s.getsockname()
    s.close()
    return port


@pytest.fixture(scope="function")
def running_server(tmp_path):
    """
    Start isolated server for Playwright E2E tests.

    CRITICAL DIFFERENCES FROM INTEGRATION:
    - NO pytest-asyncio (sync fixture)
    - Tests use Playwright's 'page' fixture (handles async internally)
    - Tests are synchronous: def test_*, NOT async def

    Returns:
        dict: {"base_url": "http://127.0.0.1:<port>"}
    """
    port = free_port()

    # Create isolated workspace
    tmp_workspace = tmp_path / "chats"
    tmp_workspace.mkdir()

    # Create server (would need mock session factory)
    # from bassi.core_v3.tests.integration.conftest import create_mock_session_factory
    # session_factory = create_mock_session_factory()
    # server_instance = WebUIServerV3(
    #     workspace_base_path=str(tmp_workspace),
    #     session_factory=session_factory,
    # )

    # For now, just a placeholder - uncomment when Playwright tests are added
    # app = server_instance.app
    # config = uvicorn.Config(app=app, host="127.0.0.1", port=port, log_level="warning")
    # server = uvicorn.Server(config)
    # thread = threading.Thread(target=server.run, daemon=True)
    # thread.start()

    # base_url = f"http://127.0.0.1:{port}"

    # Health probe would go here
    # for _ in range(100):
    #     try:
    #         import httpx
    #         with httpx.Client(timeout=0.1) as client:
    #             response = client.get(f"{base_url}/health")
    #             if response.status_code == 200:
    #                 break
    #     except Exception:
    #         time.sleep(0.05)

    # yield {"base_url": base_url}

    # Teardown would go here
    # server.should_exit = True
    # thread.join(timeout=3)

    # Placeholder return for now
    pytest.skip("Playwright E2E tests not yet implemented")
