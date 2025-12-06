"""
Try 02 (SDK): Serialized queue, fresh client per job.

Multiple WebSocket clients can connect. Each prompt is enqueued and processed
one at a time by a worker task. To eliminate context pollution, every job
creates a new ClaudeSDKClient, connects, runs the prompt with a unique
session_id, streams back text blocks, then disconnects.
"""

import asyncio
import uuid
from dataclasses import dataclass

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

MAX_QUEUE = 20


@dataclass
class Job:
    ws: ServerConnection
    prompt: str
    job_id: int


class QueueServer:
    def __init__(self) -> None:
        self.queue: asyncio.Queue[Job] = asyncio.Queue(MAX_QUEUE)
        self.job_counter = 0
        self.worker_task: asyncio.Task | None = None

    async def start(self) -> None:
        self.worker_task = asyncio.create_task(self._worker())

    async def enqueue(self, ws: ServerConnection, prompt: str) -> None:
        if self.queue.full():
            await ws.send("server busy: queue full")
            return
        self.job_counter += 1
        await self.queue.put(
            Job(ws=ws, prompt=prompt, job_id=self.job_counter)
        )

    async def _worker(self) -> None:
        while True:
            job = await self.queue.get()
            try:
                await self._run_job(job)
            finally:
                self.queue.task_done()

    async def _run_job(self, job: Job) -> None:
        options = ClaudeAgentOptions(model="claude-haiku-4-5-20251001")
        client = ClaudeSDKClient(options=options)
        await client.connect()

        try:
            await job.ws.send(f"[job {job.job_id}] start")
            session_id = f"job-{job.job_id}-{uuid.uuid4()}"
            await client.query(job.prompt, session_id=session_id)
            async for msg in client.receive_response():
                if isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, TextBlock):
                            try:
                                await job.ws.send(
                                    f"[job {job.job_id}] {block.text}"
                                )
                            except Exception:
                                return
                if isinstance(msg, ResultMessage):
                    try:
                        await job.ws.send(f"[job {job.job_id}] done")
                    except Exception:
                        pass
                    return
        except Exception as exc:  # noqa: BLE001
            try:
                await job.ws.send(f"[job {job.job_id}] error: {exc}")
            except Exception:
                pass
        finally:
            await client.disconnect()


server = QueueServer()


async def handle_ws(ws: ServerConnection) -> None:
    await ws.send(
        "connected to SDK queue worker (fresh client per job; no context reuse)"
    )
    while True:
        try:
            prompt = await ws.recv()
        except ConnectionClosed:
            break
        await server.enqueue(ws, prompt)


async def main(http_port: int = 9311, ws_port: int = 9312) -> None:
    await server.start()
    html = basic_html(
        "Try 02 SDK — Serialized Queue",
        f"ws://127.0.0.1:{ws_port}/ws",
        "Multiple clients accepted; each job uses a new ClaudeSDKClient with claude-haiku-4-5-20251001.",
    )
    http_server = await start_simple_http_server(http_port, lambda: html)
    ws_server = await serve(
        handle_ws, "127.0.0.1", ws_port, process_request=_reject_non_ws
    )
    print(
        f"[try02-sdk] HTTP http://127.0.0.1:{http_port} | "
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
