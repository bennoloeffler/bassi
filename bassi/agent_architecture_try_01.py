"""
Try 01: Single-occupant gate.

Purpose: Mirror the Claude Agent SDK async-context caveat by allowing only one
connected client. Any second client is rejected with a busy code. This is the
simplest "one person at a time" mitigation.

Relevant SDK note: docs/features_concepts/sdk_session_limitation.md documents
that a single client cannot be used across async contexts; this try enforces
exclusive use to avoid that problem entirely.
"""

import asyncio

from websockets.asyncio.server import Request, Response, ServerConnection, serve
from websockets.exceptions import ConnectionClosed
from websockets.http import Headers

from bassi.agent_architecture_utils_common import (
    DemoAgent,
    basic_html,
    start_simple_http_server,
)

ACTIVE_CLIENT: ServerConnection | None = None


async def handle_ws(conn: ServerConnection) -> None:
    """Reject if another client is active; otherwise echo via a single agent."""
    global ACTIVE_CLIENT
    if ACTIVE_CLIENT is not None:
        await conn.close(code=1013, reason="busy: only one user allowed")
        return

    ACTIVE_CLIENT = conn
    agent = DemoAgent("single-tenant")
    await agent.connect()

    try:
        await conn.send("connected to single-tenant agent")
        while True:
            try:
                prompt = await conn.recv()
            except ConnectionClosed:
                break
            await agent.reset()  # ensure no previous context leaks
            async for token in agent.query(prompt):
                try:
                    await conn.send(token)
                except Exception:
                    break
    finally:
        await agent.disconnect()
        ACTIVE_CLIENT = None


async def main(http_port: int = 9001, ws_port: int = 9002) -> None:
    html = basic_html(
        "Try 01 — Single Occupant Gate",
        f"ws://127.0.0.1:{ws_port}/ws",
        "Only one websocket allowed at a time; others receive 1013 busy.",
    )
    http_server = await start_simple_http_server(http_port, lambda: html)
    ws_server = await serve(handle_ws, "127.0.0.1", ws_port, process_request=_reject_non_ws)

    print(
        f"[try01] HTTP http://127.0.0.1:{http_port}  | "
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
