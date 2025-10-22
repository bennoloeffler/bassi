#!/usr/bin/env python3
"""
Test bassi with Playwright MCP server integration
"""

import asyncio
import sys

from bassi.agent import BassiAgent


async def main():
    """Test bassi with Playwright browser automation"""
    print("=" * 80)
    print("Testing bassi with Playwright MCP Server Integration")
    print("=" * 80)
    print()

    # Create agent
    agent = BassiAgent()

    # Send browser automation query
    query = "Open google.com in a browser and search for 'Claude AI'"
    print(f"Query: {query}\n")

    async for msg in agent.chat(query):
        # Messages are displayed by the agent itself
        pass

    print("\n" + "=" * 80)
    print("Test complete!")
    print("=" * 80)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted")
        sys.exit(130)
