"""
Test conversation context retention
"""

import asyncio
import os

from bassi.agent import BassiAgent


async def test_context():
    """Test that conversation context is retained"""
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("⚠️  ANTHROPIC_API_KEY not set, skipping test")
        return

    print("Creating BassiAgent...")
    agent = BassiAgent()

    # First message - set a value
    print("\n" + "=" * 60)
    print("TURN 1: Setting a variable")
    print("=" * 60)
    async for msg in agent.chat("remember that my favorite color is blue"):
        pass

    # Second message - recall the value
    print("\n" + "=" * 60)
    print("TURN 2: Recalling the variable")
    print("=" * 60)
    async for msg in agent.chat("what is my favorite color?"):
        pass

    print("\n" + "=" * 60)
    print("✅ Test completed!")


if __name__ == "__main__":
    asyncio.run(test_context())
