#!/usr/bin/env python3
"""
Simple test to verify Claude Agent SDK streaming works
"""
import asyncio
import sys

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient


async def test_streaming():
    """Test basic streaming with include_partial_messages"""
    print("=== Testing Claude Agent SDK Streaming ===\n")
    print("Testing WITH include_partial_messages=True\n")

    # Configure with streaming enabled
    options = ClaudeAgentOptions(
        include_partial_messages=True,
        max_turns=1,  # Single response for testing
    )

    async with ClaudeSDKClient(options=options) as client:
        # Send a simple query
        await client.query("Count from 1 to 10 slowly")

        print("🤖 Assistant:\n")

        # Receive streaming response
        async for msg in client.receive_response():
            msg_type = type(msg).__name__

            if msg_type == "StreamEvent":
                # This is the streaming event!
                event = getattr(msg, "event", {})
                event_type = event.get("type")

                if event_type == "content_block_delta":
                    # Get the delta text
                    delta = event.get("delta", {})
                    if delta.get("type") == "text_delta":
                        text = delta.get("text", "")
                        # STREAM IT! Print without newline
                        print(text, end="", flush=True)

            elif msg_type == "AssistantMessage":
                # Final complete message (we can ignore if we already streamed)
                pass

            elif msg_type == "ResultMessage":
                print("\n\n✅ Done!")
                usage = getattr(msg, "usage", {})
                print(f"Tokens: {usage.get('output_tokens', 0)}")

            elif msg_type == "SystemMessage":
                # Ignore system init
                pass


if __name__ == "__main__":
    # Ensure unbuffered output
    sys.stdout.reconfigure(line_buffering=True)

    try:
        asyncio.run(test_streaming())
    except KeyboardInterrupt:
        print("\n\nInterrupted")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback

        traceback.print_exc()
