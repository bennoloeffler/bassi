"""
Try 03: Tiny agent pool with per-agent worker tasks.

Purpose: Explore a minimal multi-user design that keeps the SDK invariant
("each client runs in one async context") by giving each agent its own worker
task. Clients are assigned to the agent with the smallest queue.

Behavior:
- Pool size configurable (default 2).
- Each agent has a dedicated queue and worker task.
- Requests are routed to the least-loaded agent; replies stream to the caller.
- If all queues are full, the client is told the pool is saturated.
"""

import asyncio
from dataclasses import dataclass, field

from websockets.asyncio.server import Request, Response, ServerConnection, serve
from websockets.exceptions import ConnectionClosed
from websockets.http import Headers

from bassi.agent_architecture_utils_common import (
    DemoAgent,
    basic_html,
    start_simple_http_server,
)


@dataclass
class Worker:
    name: str
    agent: DemoAgent
    queue: asyncio.Queue
    task: asyncio.Task | None = None
    jobs_processed: int = 0


@dataclass
class Job:
    ws: ServerConnection
    prompt: str
    job_id: int
    worker_name: str | None = None


class AgentPoolDemo:
    def __init__(self, size: int = 2, max_queue_per_worker: int = 8) -> None:
        self.size = size
        self.max_queue_per_worker = max_queue_per_worker
        self.workers: list[Worker] = []
        self.job_counter = 0

    async def start(self) -> None:
        for idx in range(self.size):
            worker = Worker(
                name=f"worker-{idx+1}",
                agent=DemoAgent(f"pooled-{idx+1}"),
                queue=asyncio.Queue(self.max_queue_per_worker),
            )
            await worker.agent.connect()
            worker.task = asyncio.create_task(self._run_worker(worker))
            self.workers.append(worker)

    async def _run_worker(self, worker: Worker) -> None:
        while True:
            job: Job = await worker.queue.get()
            try:
                await worker.agent.reset()
                await job.ws.send(f"[{worker.name} #{job.job_id}] start")
                async for token in worker.agent.query(job.prompt):
                    try:
                        await job.ws.send(
                            f"[{worker.name} #{job.job_id}] {token}"
                        )
                    except Exception:
                        break
                try:
                    await job.ws.send(f"[{worker.name} #{job.job_id}] done")
                except Exception:
                    pass
                worker.jobs_processed += 1
            except Exception as exc:  # noqa: BLE001
                try:
                    await job.ws.send(
                        f"[{worker.name} #{job.job_id}] error: {exc}"
                    )
                except Exception:
                    pass
            finally:
                worker.queue.task_done()

    async def route(self, ws: ServerConnection, prompt: str) -> None:
        worker = min(self.workers, key=lambda w: w.queue.qsize())
        if worker.queue.full():
            await ws.send("pool saturated: all workers are full")
            return
        self.job_counter += 1
        await worker.queue.put(
            Job(ws=ws, prompt=prompt, job_id=self.job_counter, worker_name=worker.name)
        )
        await ws.send(
            f"enqueued on {worker.name}; "
            f"q={worker.queue.qsize()}/{self.max_queue_per_worker}"
        )

    async def stop(self) -> None:
        for worker in self.workers:
            await worker.agent.disconnect()
            if worker.task:
                worker.task.cancel()


pool = AgentPoolDemo()


async def handle_ws(ws: WebSocketServerProtocol) -> None:
    await ws.send(
        "connected to tiny pool demo (per-agent workers; least-loaded routing)"
    )
    while True:
        try:
            prompt = await ws.recv()
        except ConnectionClosed:
            break
        await pool.route(ws, prompt)


async def main(http_port: int = 9021, ws_port: int = 9022) -> None:
    await pool.start()
    html = basic_html(
        "Try 03 — Tiny Agent Pool",
        f"ws://127.0.0.1:{ws_port}/ws",
        "Pool of 2 agents; each owns its context; routing to least-loaded queue.",
    )
    http_server = await start_simple_http_server(http_port, lambda: html)
    ws_server = await serve(handle_ws, "127.0.0.1", ws_port, process_request=_reject_non_ws)

    print(
        f"[try03] HTTP http://127.0.0.1:{http_port}  | "
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
