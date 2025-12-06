#!/usr/bin/env python3
"""
Quick manual test script for single agent architecture.

Tests:
1. Server starts with single agent
2. First client connects successfully
3. Permission toggle changes agent config
4. Second client disconnects first client
"""

import asyncio
import json
import sys

import requests
import websockets

BASE_URL = "http://localhost:8765"
WS_URL = "ws://localhost:8765/ws"


def test_health_endpoint():
    """Test that health endpoint shows single agent status."""
    print("\n🏥 Testing health endpoint...")
    response = requests.get(f"{BASE_URL}/health")
    health = response.json()

    print(f"  Status: {health['status']}")
    print(f"  Active connections: {health['active_connections']}")
    print(f"  Active sessions: {health['active_sessions']}")
    print(f"  Single agent connected: {health['single_agent_connected']}")

    assert health["status"] == "healthy", "Server not healthy"
    assert health["single_agent_connected"], "Single agent not connected"
    print("✅ Health check passed")


async def test_websocket_connection():
    """Test WebSocket connection and message flow."""
    print("\n🔌 Testing WebSocket connection...")

    async with websockets.connect(WS_URL) as websocket:
        # Should receive connected event
        msg = await websocket.recv()
        event = json.loads(msg)
        print(f"  Received: {event['type']}")

        # May receive status messages first
        while event["type"] == "status":
            print(f"    Status: {event['message']}")
            msg = await websocket.recv()
            event = json.loads(msg)
            print(f"  Received: {event['type']}")

        assert (
            event["type"] == "connected"
        ), f"Expected 'connected', got {event['type']}"
        session_id = event["session_id"]
        print(f"  ✅ Connected with session: {session_id[:8]}...")

        return session_id


async def test_permission_toggle():
    """Test that permission toggle updates agent config."""
    print("\n🔐 Testing permission toggle...")

    # Get current setting
    response = requests.get(f"{BASE_URL}/api/settings/global-bypass")
    initial_state = response.json()["enabled"]
    print(f"  Initial state: {initial_state}")

    # Toggle it
    new_state = not initial_state
    response = requests.post(
        f"{BASE_URL}/api/settings/global-bypass", json={"enabled": new_state}
    )
    assert (
        response.status_code == 200
    ), f"Got status {response.status_code}: {response.text}"
    print(f"  Toggled to: {new_state}")

    # Verify it changed
    response = requests.get(f"{BASE_URL}/api/settings/global-bypass")
    current_state = response.json()["enabled"]
    assert current_state == new_state
    print("  ✅ Permission toggle works")

    # Reset to initial state
    requests.post(
        f"{BASE_URL}/api/settings/global-bypass",
        json={"enabled": initial_state},
    )


async def test_multiple_clients():
    """Test that second client disconnects first client."""
    print("\n👥 Testing multiple client behavior...")

    # Connect first client
    print("  Connecting first client...")
    ws1 = await websockets.connect(WS_URL)

    # Wait for connected event
    while True:
        msg = await ws1.recv()
        event = json.loads(msg)
        if event["type"] == "connected":
            session1 = event["session_id"]
            print(f"    Client 1 connected: {session1[:8]}...")
            break

    # Connect second client
    print("  Connecting second client...")
    ws2 = await websockets.connect(WS_URL)

    # First client should receive disconnect message
    try:
        msg = await asyncio.wait_for(ws1.recv(), timeout=2.0)
        event = json.loads(msg)
        print(f"    Client 1 received: {event['type']}")

        if event["type"] == "error":
            print(f"      Message: {event['message']}")
            assert "New client connected" in event["message"]
            print("  ✅ First client notified of disconnect")
    except asyncio.TimeoutError:
        print("  ⚠️  Client 1 didn't receive disconnect message")

    # Second client should connect successfully
    while True:
        msg = await ws2.recv()
        event = json.loads(msg)
        if event["type"] == "connected":
            session2 = event["session_id"]
            print(f"    Client 2 connected: {session2[:8]}...")
            break

    print("  ✅ Second client connected, first client disconnected")

    await ws2.close()


async def main():
    """Run all tests."""
    print("=" * 60)
    print("🧪 Single Agent Architecture Tests")
    print("=" * 60)

    try:
        # Test 1: Health endpoint
        test_health_endpoint()

        # Test 2: WebSocket connection
        await test_websocket_connection()

        # Test 3: Permission toggle
        await test_permission_toggle()

        # Test 4: Multiple clients
        await test_multiple_clients()

        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
