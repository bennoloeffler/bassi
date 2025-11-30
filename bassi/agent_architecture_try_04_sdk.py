"""
Try 04 (SDK): Per-connection dedicated client with sticky session_id.

Fixes the "I told you my name" issue from Try 02 by keeping a single
ClaudeSDKClient alive for the entire websocket and reusing the same session_id
so the SDK maintains conversation context. Each websocket gets its own client
and session; no cross-user sharing.
"""

import asyncio
import uuid

from websockets.asyncio.server import Request, Response, ServerConnection, serve
from websockets.exceptions import ConnectionClosed
from websockets.http import Headers

from claude_agent_sdk import ClaudeAgentOptions
from claude_agent_sdk.client import ClaudeSDKClient
from claude_agent_sdk.types import AssistantMessage, ResultMessage, TextBlock

from bassi.agent_architecture_utils_common import (
    basic_html,
    start_simple_http_server,
)


async def stream_response(client: ClaudeSDKClient, conn: ServerConnection) -> None:
    """Stream assistant text blocks back to the websocket."""
    async for msg in client.receive_response():
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    await conn.send(block.text)
        if isinstance(msg, ResultMessage):
            return


async def handle_ws(conn: ServerConnection) -> None:
    """
    Each websocket gets its own ClaudeSDKClient and sticky session_id so
    conversation memory works across messages for that user only.
    """
    session_id = f"ws-session-{uuid.uuid4()}"
    client = ClaudeSDKClient(
        options=ClaudeAgentOptions(model="claude-haiku-4-5-20251001")
    )
    await client.connect()
    await conn.send(
        f"connected to dedicated client with session_id={session_id} "
        "(context stays for this websocket only)"
    )

    try:
        while True:
            try:
                prompt = await conn.recv()
            except ConnectionClosed:
                break
            await client.query(prompt, session_id=session_id)
            try:
                await stream_response(client, conn)
            except Exception as exc:  # noqa: BLE001
                await conn.send(f"error: {exc}")
                break
    finally:
        await client.disconnect()


async def main(http_port: int = 9331, ws_port: int = 9332) -> None:
    html = basic_html(
        "Try 04 SDK — Sticky Session",
        f"ws://127.0.0.1:{ws_port}/ws",
        "One ClaudeSDKClient per websocket; session_id is reused so the model remembers prior messages.",
    )
    http_server = await start_simple_http_server(http_port, lambda: html)
    ws_server = await serve(handle_ws, "127.0.0.1", ws_port, process_request=_reject_non_ws)
    print(
        f"[try04-sdk] HTTP http://127.0.0.1:{http_port} | "
        f"WS ws://127.0.0.1:{ws_port}/ws"
    )
    await asyncio.gather(ws_server.wait_closed(), http_server.serve_forever())


async def _reject_non_ws(conn: ServerConnection, request: Request):
    if request.path != "/ws":
        return Response(
            404,
            Headers([("Content-Type", "text/plain")]),
            b"websocket endpoint is /ws\n",
        )


if __name__ == "__main__":
    asyncio.run(main())
