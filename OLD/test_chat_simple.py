"""
Simple integration test for chat functionality
"""

import asyncio
import os

from bassi.agent import BassiAgent


async def test_simple_chat():
    """Test a simple chat interaction"""
    # Make sure API key is set
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("⚠️  ANTHROPIC_API_KEY not set, skipping test")
        return

    print("Creating BassiAgent...")
    agent = BassiAgent()

    print("\nSending message: '2 + 2'")
    print("=" * 60)

    try:
        async for msg in agent.chat("2 + 2"):
            print(f"Received: {type(msg).__name__}")

        print("\n" + "=" * 60)
        print("✅ Test completed successfully!")

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_simple_chat())
