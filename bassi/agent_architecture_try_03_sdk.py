"""
Try 03 (SDK): Tiny dedicated pool, no cross-user reuse.

A small pool of SDK clients exists, but each client is exclusively assigned to
one websocket connection. If all clients are busy, new connections get 1013
busy. This preserves isolation (no context leakage) while allowing a few
concurrent users.
"""

import asyncio
import os
import uuid
from dataclasses import dataclass, field

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


@dataclass
class Lease:
    client: ClaudeSDKClient
    in_use: bool = False
    ws: ServerConnection | None = None
    lease_id: str = field(default_factory=lambda: str(uuid.uuid4()))


class DedicatedPool:
    def __init__(self, size: int = 2) -> None:
        self.size = size
        self.leases: list[Lease] = []

    async def start(self) -> None:
        for _ in range(self.size):
            options = ClaudeAgentOptions(model="claude-haiku-4-5-20251001")
            client = ClaudeSDKClient(options=options)
            lease = Lease(client=client)
            self.leases.append(lease)

    def acquire(self) -> Lease | None:
        for lease in self.leases:
            if not lease.in_use:
                lease.in_use = True
                return lease
        return None

    async def release(self, lease: Lease) -> None:
        lease.in_use = False
        lease.ws = None
        lease.lease_id = str(uuid.uuid4())


pool = DedicatedPool(size=2)


async def _stream_client(client: ClaudeSDKClient, ws: ServerConnection):
    async for msg in client.receive_response():
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    await ws.send(block.text)
        if isinstance(msg, ResultMessage):
            return


async def handle_ws(ws: ServerConnection) -> None:
    lease = pool.acquire()
    if lease is None:
        await ws.close(code=1013, reason="busy: pool exhausted")
        return

    lease.ws = ws
    await lease.client.connect()
    await ws.send(
        f"connected to dedicated client (haiku) lease={lease.lease_id}; no context sharing"
    )

    try:
        while True:
            try:
                prompt = await ws.recv()
            except ConnectionClosed:
                break
            session_id = f"lease-{lease.lease_id}-{uuid.uuid4()}"
            await lease.client.query(prompt, session_id=session_id)
            try:
                await _stream_client(lease.client, ws)
            except Exception as exc:  # noqa: BLE001
                await ws.send(f"error: {exc}")
                break
    finally:
        await lease.client.disconnect()
        await pool.release(lease)


async def main(http_port: int = 9321, ws_port: int = 9322) -> None:
    await pool.start()
    html = basic_html(
        "Try 03 SDK — Dedicated Pool",
        f"ws://127.0.0.1:{ws_port}/ws",
        "Pool of 2 SDK clients; each bound to one websocket at a time (claude-haiku-4-5-20251001, no shared context).",
    )
    http_server = await start_simple_http_server(http_port, lambda: html)
    ws_server = await serve(handle_ws, "127.0.0.1", ws_port, process_request=_reject_non_ws)
    print(
        f"[try03-sdk] HTTP http://127.0.0.1:{http_port} | "
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
