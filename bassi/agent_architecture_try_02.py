"""
Try 02: Single worker queue.

Purpose: Allow multiple websocket clients while respecting the Claude Agent SDK
constraint that a client must be driven from one async context. We route all
requests through a single worker task that owns the agent.

Behavior:
- Any number of clients can connect.
- Prompts are enqueued and processed one at a time by the worker.
- Responses stream back only to the requesting client.
- Backpressure: if the queue is full, clients receive a busy error.
"""

import asyncio
from dataclasses import dataclass

from websockets.asyncio.server import Request, Response, ServerConnection, serve
from websockets.exceptions import ConnectionClosed
from websockets.http import Headers

from bassi.agent_architecture_utils_common import (
    DemoAgent,
    basic_html,
    start_simple_http_server,
)

MAX_QUEUE = 20


@dataclass
class Job:
    ws: ServerConnection
    prompt: str
    job_id: int


class QueueServer:
    def __init__(self) -> None:
        self.queue: asyncio.Queue[Job] = asyncio.Queue(MAX_QUEUE)
        self.agent = DemoAgent("queue-worker")
        self.job_counter = 0

    async def start(self) -> None:
        await self.agent.connect()
        asyncio.create_task(self._worker())

    async def _worker(self) -> None:
        """Single task that owns all agent interactions."""
        while True:
            job = await self.queue.get()
            try:
                await self.agent.reset()
                await job.ws.send(f"[job {job.job_id}] start")
                async for token in self.agent.query(job.prompt):
                    try:
                        await job.ws.send(f"[job {job.job_id}] {token}")
                    except Exception:
                        break
                try:
                    await job.ws.send(f"[job {job.job_id}] done")
                except Exception:
                    pass
            except Exception as exc:  # noqa: BLE001
                try:
                    await job.ws.send(f"[job {job.job_id}] error: {exc}")
                except Exception:
                    pass
            finally:
                self.queue.task_done()

    async def enqueue(self, ws: ServerConnection, prompt: str) -> None:
        if self.queue.full():
            await ws.send("server busy: queue full")
            return
        self.job_counter += 1
        await self.queue.put(Job(ws=ws, prompt=prompt, job_id=self.job_counter))

    async def stop(self) -> None:
        await self.agent.disconnect()


server = QueueServer()


async def handle_ws(conn: ServerConnection) -> None:
    await conn.send("connected to queue worker (one agent, serialized jobs)")
    while True:
        try:
            prompt = await conn.recv()
        except ConnectionClosed:
            break
        await server.enqueue(conn, prompt)


async def main(http_port: int = 9011, ws_port: int = 9012) -> None:
    await server.start()
    html = basic_html(
        "Try 02 — Single Worker Queue",
        f"ws://127.0.0.1:{ws_port}/ws",
        "Multiple clients allowed; prompts are serialized through one agent.",
    )
    http_server = await start_simple_http_server(http_port, lambda: html)
    ws_server = await serve(handle_ws, "127.0.0.1", ws_port, process_request=_reject_non_ws)

    print(
        f"[try02] HTTP http://127.0.0.1:{http_port}  | "
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
