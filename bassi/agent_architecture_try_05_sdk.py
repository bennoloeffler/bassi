"""
Try 05 (SDK): User-named sticky sessions with stored history.

Goal: let a user supply a unique name, and persist both the agent_session
identifier and chat history so that reconnecting restores context. Each browser
session (websocket) gets its own ClaudeSDKClient, but if the user is known we
resume their agent_session via ClaudeAgentOptions.resume and reuse the same
session_id for queries.
"""

import asyncio
import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from string import Template

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

STORAGE_DIR = Path("chats/try05_sdk")
STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def _user_path(user: str) -> Path:
    safe = "".join(c for c in user if c.isalnum() or c in ("-", "_", "."))
    return STORAGE_DIR / f"{safe or 'anon'}.json"


def load_user(user: str) -> dict | None:
    path = _user_path(user)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def save_user(user: str, agent_session: str, messages: list[dict]) -> None:
    path = _user_path(user)
    payload = {
        "agent_session": agent_session,
        "messages": messages,
    }
    path.write_text(json.dumps(payload, indent=2))


def list_users() -> list[str]:
    users: list[str] = []
    for path in STORAGE_DIR.glob("*.json"):
        users.append(path.stem)
    return sorted(users)


async def stream_response(
    client: ClaudeSDKClient, conn: ServerConnection
) -> str:
    """Stream assistant text blocks back; return concatenated assistant text."""
    chunks: list[str] = []
    async for msg in client.receive_response():
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    chunks.append(block.text)
                    await conn.send(block.text)
        if isinstance(msg, ResultMessage):
            break
    return "".join(chunks)


async def handle_ws(conn: ServerConnection) -> None:
    """
    Protocol:
    - Client first sends JSON: {"type":"hello","user":"alice","browser_session":"uuid"}
    - Then chat messages: {"type":"chat","text":"..."}
    """
    try:
        hello_raw = await conn.recv()
    except ConnectionClosed:
        return

    try:
        hello = json.loads(hello_raw)
    except Exception:
        await conn.close(code=1003, reason="expected JSON hello")
        return

    if (
        not isinstance(hello, dict)
        or hello.get("type") != "hello"
        or not hello.get("user")
    ):
        await conn.close(code=1003, reason="invalid hello payload")
        return

    user = str(hello["user"])
    reset = bool(hello.get("reset"))
    record = load_user(user)
    messages = record["messages"] if record and "messages" in record else []
    if reset:
        # Start fresh: new agent session, clear history
        path = _user_path(user)
        if path.exists():
            path.unlink()
        record = None
        messages = []
    agent_session = (
        record["agent_session"]
        if record and "agent_session" in record
        else f"agent-session-{uuid.uuid4()}"
    )

    options = ClaudeAgentOptions(
        model="claude-haiku-4-5-20251001",
        resume=agent_session if record else None,
    )
    client = ClaudeSDKClient(options=options)
    await client.connect()

    await conn.send(
        f"connected as {user}; agent_session={agent_session} "
        "(history will persist across reconnects)"
    )
    if messages:
        await conn.send(f"[history] restored {len(messages)} messages")
        for m in messages[-10:]:  # send a preview of last 10
            await conn.send(
                f"[history] {m.get('role','?')}: {m.get('text','')}"
            )

    try:
        while True:
            try:
                raw = await conn.recv()
            except ConnectionClosed:
                break
            try:
                payload = json.loads(raw)
            except Exception:
                await conn.send("invalid payload (expected JSON)")
                continue
            if payload.get("type") != "chat" or "text" not in payload:
                await conn.send(
                    "invalid payload (expected {'type':'chat','text':...})"
                )
                continue
            text = str(payload["text"])
            messages.append({"role": "user", "text": text})
            await client.query(text, session_id=agent_session)
            assistant_text = await stream_response(client, conn)
            if assistant_text:
                messages.append({"role": "assistant", "text": assistant_text})
            save_user(user, agent_session, messages)
    finally:
        await client.disconnect()


async def main(http_port: int = 9333, ws_port: int = 9334) -> None:
    def html_factory() -> str:
        users_json = json.dumps(list_users())

        tpl = Template(
            r"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Try 05 SDK — Persisted Sessions</title>
  <style>
    body { font-family: monospace; background:#0b1021; color:#e0e6ff; padding:18px; }
    input, button, select { padding:6px; margin:4px; }
    .log { white-space: pre-wrap; background:#0f1630; padding:12px; min-height:200px; line-height:1.4; }
    .user { color:#8be1ff; }
    .assistant { color:#f5f5f5; }
    .code { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; background:#0a1026; display:block; padding:8px; margin:6px 0; border-radius:4px; }
  </style>
</head>
<body>
  <h3>Try 05 SDK — Persisted Sessions</h3>
  <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
    <label>Known chats:
      <select id="user-select"></select>
    </label>
    <button id="load">Load Selected</button>
    <button id="refresh">Refresh List</button>
    <button id="new-chat">New Chat</button>
  </div>
  <div style="margin-top:8px;">
    <input id="user" placeholder="user name" value="alice" />
    <button id="connect">Connect</button>
  </div>
  <div>
    <input id="msg" placeholder="message" size="50" />
    <button id="send">Send</button>
  </div>
  <div class="log" id="log"></div>
  <script id="known-users" type="application/json">${users_json}</script>
  <script>
    let ws = null;
    let resetNext = false;
    const log = document.getElementById('log');
    function escapeHtml(s) {
      return s.replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
    }
    function renderMarkdown(text) {
      // minimal markdown: code fences and inline code, otherwise escape
      const fenced = text.split(/```/);
      if (fenced.length > 1) {
        return fenced.map((chunk, idx) => idx % 2 === 1 ? '<span class="code">' + escapeHtml(chunk) + '</span>' : escapeHtml(chunk)).join('');
      }
      return escapeHtml(text).replace(/`([^`]+)`/g, '<span class="code">$1</span>');
    }
    function write(line, cls) {
      const span = document.createElement('div');
      span.innerHTML = (cls ? `<span class="${cls}">${renderMarkdown(line)}</span>` : renderMarkdown(line));
      log.appendChild(span);
      log.scrollTop = log.scrollHeight;
    }
    function populateUsers(list) {
      const sel = document.getElementById('user-select');
      sel.innerHTML = '';
      list.forEach(u => {
        const opt = document.createElement('option');
        opt.value = u; opt.textContent = u;
        sel.appendChild(opt);
      });
    }
    populateUsers(JSON.parse(document.getElementById('known-users').textContent || '[]'));
    document.getElementById('refresh').onclick = async () => {
      try {
        const res = await fetch('/users');
        const data = await res.json();
        populateUsers(data);
        write('refreshed user list');
      } catch (e) { write('failed to refresh users: ' + e); }
    };
    document.getElementById('load').onclick = () => {
      const sel = document.getElementById('user-select');
      if (sel.value) {
        document.getElementById('user').value = sel.value;
        resetNext = false;
        connect();
      }
    };
    document.getElementById('new-chat').onclick = () => {
      // Keep the current user; just reset their agent_session/history.
      const sel = document.getElementById('user-select');
      if (!document.getElementById('user').value && sel.value) {
        document.getElementById('user').value = sel.value;
      }
      resetNext = true;
      connect();
    };
    function connect() {
      if (ws) ws.close();
      const user = document.getElementById('user').value || 'anon';
      ws = new WebSocket('ws://127.0.0.1:${ws_port}/ws');
      ws.onopen = () => {
        write('ws open');
        ws.send(JSON.stringify({type:'hello', user, browser_session: crypto.randomUUID(), reset: resetNext}));
        resetNext = false;
      };
      ws.onmessage = (ev) => write(ev.data, ev.data.startsWith('you →') ? 'user' : 'assistant');
      ws.onclose = (ev) => write('ws closed ' + ev.code + ' ' + ev.reason);
    }
    document.getElementById('connect').onclick = () => {
      resetNext = false;
      connect();
    };
    document.getElementById('send').onclick = () => {
      if (!ws || ws.readyState !== WebSocket.OPEN) return write('ws not open');
      const text = document.getElementById('msg').value;
      ws.send(JSON.stringify({type:'chat', text}));
      write('you -> ' + text, 'user');
    };
  </script>
</body>
</html>"""
        )
        return tpl.substitute(ws_port=ws_port, users_json=users_json)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):  # noqa: ANN001
            return  # silence

        def do_GET(self):  # noqa: N802
            if self.path == "/users":
                body = json.dumps(list_users()).encode()
                content_type = "application/json"
            else:
                body = html_factory().encode()
                content_type = "text/html; charset=utf-8"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    http_server = ThreadingHTTPServer(("127.0.0.1", http_port), Handler)
    http_thread = threading.Thread(
        target=http_server.serve_forever, daemon=True
    )
    http_thread.start()
    ws_server = await serve(
        handle_ws, "127.0.0.1", ws_port, process_request=_reject_non_ws
    )
    print(
        f"[try05-sdk] HTTP http://127.0.0.1:{http_port} | "
        f"WS ws://127.0.0.1:{ws_port}/ws"
    )
    try:
        await asyncio.Future()  # run until cancelled
    except asyncio.CancelledError:
        pass
    finally:
        ws_server.close()
        http_server.shutdown()
        http_server.server_close()
        await ws_server.wait_closed()
        http_thread.join()


async def _reject_non_ws(conn: ServerConnection, request: Request):
    if request.path != "/ws":
        return Response(
            404,
            Headers([("Content-Type", "text/plain")]),
            b"websocket endpoint is /ws\n",
        )


if __name__ == "__main__":
    asyncio.run(main())
