#!/usr/bin/env python3
"""
Test streaming with markdown rendering at the end
"""
import asyncio
import sys

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from rich.console import Console
from rich.markdown import Markdown

console = Console()


async def test_streaming_with_markdown():
    """Test streaming with final markdown render"""
    print("=== Testing Streaming + Markdown Rendering ===\n")

    options = ClaudeAgentOptions(
        include_partial_messages=True,
        max_turns=1,
    )

    async with ClaudeSDKClient(options=options) as client:
        await client.query(
            "Write a short Python code example with comments. Keep it under 10 lines."
        )

        console.print("\n[bold green]🤖 Assistant:[/bold green]\n")

        accumulated_text = ""

        async for msg in client.receive_response():
            msg_type = type(msg).__name__

            if msg_type == "StreamEvent":
                event = getattr(msg, "event", {})
                if event.get("type") == "content_block_delta":
                    delta = event.get("delta", {})
                    if delta.get("type") == "text_delta":
                        text = delta.get("text", "")
                        # Stream plain text
                        console.print(text, end="")
                        accumulated_text += text

            elif msg_type == "ResultMessage":
                # Render as pretty markdown when done
                if accumulated_text:
                    console.print("\n\n[dim]" + "─" * 60 + "[/dim]")
                    console.print(
                        "[bold cyan]📝 Rendered Markdown:[/bold cyan]"
                    )
                    console.print("[dim]" + "─" * 60 + "[/dim]\n")
                    markdown = Markdown(
                        accumulated_text, code_theme="monokai"
                    )
                    console.print(markdown)
                    console.print("\n[dim]" + "─" * 60 + "[/dim]")

                console.print("\n✅ Done!\n")


if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    try:
        asyncio.run(test_streaming_with_markdown())
    except KeyboardInterrupt:
        print("\n\nInterrupted")
