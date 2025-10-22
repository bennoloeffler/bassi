"""
Test to see tool usage messages
"""

import asyncio
import os

from bassi.agent import BassiAgent


async def test_tool_usage():
    """Test with a query that should use bash tool"""
    # Make sure API key is set
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("⚠️  ANTHROPIC_API_KEY not set, skipping test")
        return

    print("Creating BassiAgent...")
    agent = BassiAgent()

    print("\nSending message: 'list python files in current directory'")
    print("=" * 60)

    try:
        async for msg in agent.chat("list python files in current directory"):
            msg_class = type(msg).__name__
            print(f"\n[{msg_class}]")
            if hasattr(msg, "__dict__"):
                print(f"  Attributes: {msg.__dict__}")
            elif hasattr(msg, "content"):
                print(f"  Content: {msg.content}")

        print("\n" + "=" * 60)
        print("✅ Test completed!")

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    # Enable debug mode
    os.environ["BASSI_DEBUG"] = "1"
    asyncio.run(test_tool_usage())
