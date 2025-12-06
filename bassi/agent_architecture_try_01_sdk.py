"""
Try 01 (SDK): Single-occupant, fresh client per connection.

This mirrors the safest pattern to avoid context pollution: do not reuse a
ClaudeSDKClient across users. A new client is created on WebSocket connect and
disposed on disconnect. Only one connection is allowed at a time; others get a
1013 busy response.
"""

import asyncio
import uuid

from claude_agent_sdk import ClaudeAgentOptions
from claude_agent_sdk.client import ClaudeSDKClient
from claude_agent_sdk.types import AssistantMessage, ResultMessage, TextBlock
from websockets.asyncio.server import (
    Request,
    Response,
    ServerConnection,
    serve,
)
from websockets.exceptions import ConnectionClosed
from websockets.http import Headers

from bassi.agent_architecture_utils_common import (
    basic_html,
    start_simple_http_server,
)

ACTIVE: ServerConnection | None = None


async def stream_response(client: ClaudeSDKClient, conn: ServerConnection):
    async for msg in client.receive_response():
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    await conn.send(block.text)
        if isinstance(msg, ResultMessage):
            return


async def handle_ws(conn: ServerConnection) -> None:
    global ACTIVE
    if ACTIVE is not None:
        await conn.close(code=1013, reason="busy: single user mode")
        return

    ACTIVE = conn
    options = ClaudeAgentOptions(model="claude-haiku-4-5-20251001")
    client = ClaudeSDKClient(options=options)
    await client.connect()

    try:
        await conn.send("connected to ClaudeSDKClient (haiku, single-tenant)")
        while True:
            try:
                prompt = await conn.recv()
            except ConnectionClosed:
                break
            session_id = f"ws-{uuid.uuid4()}"
            await client.query(prompt, session_id=session_id)
            try:
                await stream_response(client, conn)
            except Exception as exc:  # noqa: BLE001
                await conn.send(f"error: {exc}")
                break
    finally:
        await client.disconnect()
        ACTIVE = None


async def main(http_port: int = 9301, ws_port: int = 9302) -> None:
    html = basic_html(
        "Try 01 SDK — Single Occupant",
        f"ws://127.0.0.1:{ws_port}/ws",
        "Uses claude-haiku-4-5-20251001. One connection at a time; new client per session.",
    )
    http_server = await start_simple_http_server(http_port, lambda: html)
    ws_server = await serve(
        handle_ws, "127.0.0.1", ws_port, process_request=_reject_non_ws
    )
    print(
        f"[try01-sdk] HTTP http://127.0.0.1:{http_port} | "
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
