#!/usr/bin/env python3
"""
Test bassi agent with MS365 email integration
"""

import asyncio
import sys

from bassi.agent import BassiAgent


async def main():
    """Test bassi with email query"""
    print("=" * 80)
    print("Testing bassi with MS365 Email Integration")
    print("=" * 80)
    print()

    # Create agent
    agent = BassiAgent()

    # Send email query
    query = "Show me my 3 most recent emails"
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
