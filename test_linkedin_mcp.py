#!/usr/bin/env python3
"""Test script for LinkedIn MCP server"""

import json
import os
import subprocess
import sys


def test_linkedin():
    """Test LinkedIn MCP connection and profile fetching"""

    # Check if LINKEDIN_COOKIE is set
    cookie = os.environ.get('LINKEDIN_COOKIE')
    if not cookie:
        print("❌ LINKEDIN_COOKIE not set!")
        return False

    print(f"✅ LINKEDIN_COOKIE found (length: {len(cookie)})")
    print(f"   Has li_at prefix: {'Yes' if cookie.startswith('li_at=') else 'No'}")
    print(f"   First 20 chars: {cookie[:20]}...")
    print()

    # Start Docker container
    docker_cmd = [
        "docker", "run", "--rm", "-i",
        "-e", "LINKEDIN_COOKIE",
        "stickerdaniel/linkedin-mcp-server:latest"
    ]

    print("🚀 Starting LinkedIn MCP server...")
    proc = subprocess.Popen(
        docker_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=os.environ.copy(),
        text=True,
        bufsize=1
    )

    try:
        # Send initialize request
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0"}
            }
        }

        print("📤 Sending initialize request...")
        proc.stdin.write(json.dumps(init_request) + "\n")
        proc.stdin.flush()

        # Read response
        response_line = proc.stdout.readline()
        if response_line:
            response = json.loads(response_line)
            print("✅ Initialized:", response.get("result", {}).get("serverInfo", {}))
        else:
            print("❌ No response from server")
            return False

        # Send initialized notification
        initialized = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        proc.stdin.write(json.dumps(initialized) + "\n")
        proc.stdin.flush()

        # List tools
        list_tools = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list"
        }

        print("\n📤 Requesting tools list...")
        proc.stdin.write(json.dumps(list_tools) + "\n")
        proc.stdin.flush()

        response_line = proc.stdout.readline()
        if response_line:
            response = json.loads(response_line)
            if "result" in response:
                tools = response["result"].get("tools", [])
                print(f"✅ Available tools ({len(tools)}):")
                for tool in tools:
                    print(f"   - {tool['name']}")
            else:
                print(f"❌ Error: {response.get('error')}")

        # Try to get profile
        get_profile = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "get_person_profile",
                "arguments": {
                    "linkedin_username": "benno-loeffler-stuttgart"
                }
            }
        }

        print("\n📤 Fetching profile for 'benno-loeffler-stuttgart'...")
        proc.stdin.write(json.dumps(get_profile) + "\n")
        proc.stdin.flush()

        response_line = proc.stdout.readline()
        if response_line:
            response = json.loads(response_line)
            if "result" in response:
                print("✅ Profile fetch successful!")
                print(json.dumps(response["result"], indent=2))
            else:
                error = response.get("error", {})
                print(f"❌ Profile fetch failed:")
                print(f"   Code: {error.get('code')}")
                print(f"   Message: {error.get('message')}")
                print(f"   Data: {error.get('data')}")
                return False

        return True

    finally:
        proc.stdin.close()
        proc.terminate()
        proc.wait(timeout=5)


if __name__ == "__main__":
    success = test_linkedin()
    sys.exit(0 if success else 1)
