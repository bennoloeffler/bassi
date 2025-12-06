"""
Lightweight utilities for the agent-architecture try files.

These helpers avoid pulling in the full app stack so each try file can stay
self-contained while sharing HTML generation and a tiny fake agent that
simulates the Claude Agent SDK streaming contract.
"""

import asyncio
import datetime as _dt
import textwrap
from typing import AsyncGenerator, Callable

HtmlFactory = Callable[[], str]


class DemoAgent:
    """
    Tiny stand-in for a Claude Agent SDK client.

    It enforces a single async context for `query` to mirror the SDK caveat
    documented in docs/features_concepts/sdk_session_limitation.md.
    """

    def __init__(self, name: str, latency: float = 0.12) -> None:
        self.name = name
        self.latency = latency
        self._connected = False
        self._context_task: asyncio.Task | None = None

    async def connect(self) -> None:
        await asyncio.sleep(self.latency)
        self._connected = True

    async def disconnect(self) -> None:
        await asyncio.sleep(self.latency / 2)
        self._connected = False

    async def query(self, prompt: str) -> AsyncGenerator[str, None]:
        if not self._connected:
            raise RuntimeError(f"{self.name} not connected")

        # Force all work to happen on the task that called query so we can
        # detect cross-task misuse similar to the SDK restriction.
        if self._context_task is None:
            self._context_task = asyncio.current_task()
        elif self._context_task is not asyncio.current_task():
            raise RuntimeError(
                f"{self.name} used from multiple tasks; SDK would reject this"
            )

        timestamp = _dt.datetime.now().strftime("%H:%M:%S")
        text = (
            f"[{self.name}] {timestamp} Echo: {prompt} "
            f"(latency {self.latency:.2f}s)"
        )
        for token in textwrap.wrap(text, 24):
            await asyncio.sleep(self.latency)
            yield token

    async def reset(self) -> None:
        """
        Clear any simulated context between jobs.

        Real implementations should drop history/workspace here to prevent
        context leakage across users.
        """
        self._context_task = None


async def start_simple_http_server(
    port: int, html_factory: HtmlFactory
) -> asyncio.AbstractServer:
    """Serve a single HTML document for all requests."""

    async def _handler(
        reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        try:
            await reader.readline()  # Only care that something arrived
            body = html_factory().encode()
            header = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: text/html; charset=utf-8\r\n"
                "Cache-Control: no-cache\r\n"
                "Connection: close\r\n"
                f"Content-Length: {len(body)}\r\n\r\n"
            ).encode()
            writer.write(header)
            writer.write(body)
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    return await asyncio.start_server(_handler, "127.0.0.1", port)


def basic_html(title: str, ws_url: str, subtitle: str = "") -> str:
    """Return a minimal HTML page with a websocket console."""
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>{title}</title>
  <style>
    body {{ font-family: monospace; background: #0b1021; color: #e0e6ff; padding: 18px; }}
    .box {{ border: 1px solid #30395c; padding: 12px; margin-top: 12px; }}
    .log {{ white-space: pre-wrap; min-height: 180px; background: #0f1630; padding: 12px; }}
    button {{ background: #4f6bff; border: none; padding: 8px 12px; color: #fff; cursor: pointer; }}
  </style>
</head>
<body>
  <h2>{title}</h2>
  <p>{subtitle}</p>
  <div class="box">
    <input id="prompt" value="hello world" size="40" />
    <button id="send">Send</button>
  </div>
  <div class="box log" id="log"></div>
  <script>
    const log = document.getElementById('log');
    function write(line) {{
      log.textContent += line + "\\n";
      log.scrollTop = log.scrollHeight;
    }}
    const ws = new WebSocket('{ws_url}');
    ws.onopen = () => write('ws open → {ws_url}');
    ws.onmessage = (ev) => write(ev.data);
    ws.onclose = (ev) => write('ws closed ' + ev.code + ' ' + ev.reason);
    document.getElementById('send').onclick = () => {{
      const val = document.getElementById('prompt').value;
      ws.send(val);
      write('you → ' + val);
    }};
  </script>
</body>
</html>
"""
