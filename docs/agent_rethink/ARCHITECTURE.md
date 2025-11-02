# Multi-Model Agent Platform - Complete Architecture

## 🎯 Design Goals

1. **Single Execution Path** - All models (Anthropic, DeepSeek, Moonshot) go through unified adapter
2. **Proper Async** - TaskGroups, cancellation, no orphaned tasks
3. **Event Sourcing** - Immutable event log as source of truth
4. **Session Isolation** - Zero shared state between sessions
5. **Show Everything** - Every action visible in both CLI and Web UI

---

## 🏗️ Core Architecture

```
┌─────────────────────────────────────────────────────┐
│              Agent Session (per user)                │
│  ┌────────────────────────────────────────────────┐ │
│  │ Event Store (append-only, immutable)           │ │
│  │ ┌────────────────────────────────────────────┐ │ │
│  │ │ Subscribers:                               │ │ │
│  │ │ - WebSocket (bounded queue, drop on full) │ │ │
│  │ │ - CLI Renderer (blocking queue)            │ │ │
│  │ │ - Persistence (optional)                   │ │ │
│  │ └────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────┐ │
│  │ Agent Loop (anyio TaskGroup)                   │ │
│  │ ├─ Model Adapter (emits events)                │ │
│  │ ├─ Tool Executor (concurrent, tracked)         │ │
│  │ ├─ Hook Pipeline (security, pre/post)          │ │
│  │ └─ Cancellation Scope (propagates to all)      │ │
│  └────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

---

## 📦 Core Components

### 1. **Event System** (`events.py`)

**Strongly typed events** (no dict soup):

```python
@dataclass(frozen=True)  # Immutable!
class ToolCallEvent(BaseEvent):
    type: EventType = EventType.TOOL_CALL_STARTED
    tool_name: str
    tool_id: str
    tool_input: Dict[str, Any]
    # Inherited: timestamp, event_id, run_id, session_id
```

**All event types:**
- `SESSION_STARTED`, `SESSION_ENDED`
- `PROMPT_RECEIVED`, `PLAN_GENERATED`
- `TOKEN_DELTA` (streaming)
- `TOOL_CALL_STARTED`, `TOOL_CALL_COMPLETED`, `TOOL_CALL_FAILED`
- `HOOK_EXECUTED`, `HOOK_DENIED`
- `MESSAGE_COMPLETED`, `RUN_COMPLETED`, `RUN_CANCELLED`
- `ERROR`

---

### 2. **Event Store** (`event_store.py`)

**Append-only log with pub/sub:**

```python
class EventStore:
    async def append(self, event: AgentEvent):
        """ONLY way events enter system"""
        # 1. Store in history (bounded)
        # 2. Notify all subscribers concurrently
        # 3. Handle failures gracefully

    def subscribe(self, name, queue_size=1000, drop_on_full=True):
        """Create subscriber with backpressure handling"""

    async def stream(self, subscriber) -> AsyncIterator[AgentEvent]:
        """Stream events to consumer (CLI, WS)"""
```

**Backpressure handling:**
- WebSocket subscribers: `drop_on_full=True` (don't block model)
- CLI subscribers: `drop_on_full=False` (block on backpressure)
- Bounded queues prevent memory explosion

---

### 3. **Model Adapters** (`model_adapter.py`)

**Unified interface for all providers:**

```python
class ModelAdapter(ABC):
    async def execute(
        self,
        messages: List[Message],
        tools: List[Dict],
        tool_executor: ToolExecutor
    ) -> AsyncIterator[AgentEvent]:
        """
        Execute model and YIELD events as they occur.

        All adapters emit the same event types,
        ensuring UI consistency regardless of model.
        """
```

**Implementations:**

1. **AnthropicAdapter**
   - Uses Agent SDK natively
   - Tool execution via SDK's ToolUseBlock
   - Streaming via SDK's message stream

2. **OpenAICompatAdapter**
   - Works with DeepSeek, Moonshot, any OpenAI-compatible API
   - Function calling → our ToolExecutor
   - Streaming via OpenAI chat completions stream

**Key insight:** Both adapters emit identical events, so UI doesn't care which model is running!

---

### 4. **Agent Session** (`agent_session.py`)

**Isolated execution environment per user:**

```python
class AgentSession:
    def __init__(self, session_id: str, config: AgentConfig):
        self.session_id = session_id
        self.event_store = EventStore()
        self.tool_executor = ToolExecutor()
        self.hook_pipeline = HookPipeline()
        self.cancel_scope: Optional[CancelScope] = None

    async def execute(self, prompt: str, model_pref: Optional[str]):
        """
        Main execution loop with proper async lifecycle.
        """
        run_id = str(uuid.uuid4())

        # Create adapter for chosen model
        adapter = self._create_adapter(model_pref, run_id)

        async with anyio.create_task_group() as tg:
            self.cancel_scope = tg.cancel_scope

            try:
                # Execute model (yields events)
                async for event in adapter.execute(
                    messages=self.conversation_history,
                    tools=self.tool_executor.get_tool_schemas(),
                    tool_executor=self.tool_executor
                ):
                    # Append to event store (pub/sub happens here)
                    await self.event_store.append(event)

                    # Update conversation history
                    if isinstance(event, ToolCallEvent):
                        # Add to history for next turn
                        pass

            except Exception as e:
                await self.event_store.append(ErrorEvent(...))

            finally:
                # Cleanup always runs
                await self._cleanup()

    async def cancel(self):
        """Cancel execution gracefully"""
        if self.cancel_scope:
            self.cancel_scope.cancel()
            await self.event_store.append(
                SessionEvent(type=EventType.RUN_CANCELLED, ...)
            )
```

**Concurrency guarantees:**
- TaskGroup ensures all child tasks complete or cancelled
- No orphaned tasks
- Cancellation propagates to all tools
- Cleanup always runs (finally block)

---

### 5. **Tool Executor** (`tool_executor.py`)

**Unified tool execution:**

```python
class ToolExecutor:
    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        self._active_calls: Dict[str, asyncio.Task] = {}

    async def execute(self, tool_name: str, tool_input: Dict) -> Any:
        """
        Execute tool with:
        - Hook pipeline (pre/post)
        - Timeout protection
        - Error isolation
        - Concurrent execution tracking
        """
        tool_id = str(uuid.uuid4())

        # Pre-execution hooks
        hook_decision = await self.hook_pipeline.execute_pre(
            tool_name, tool_input
        )
        if hook_decision == "deny":
            raise ToolDeniedError(...)

        # Execute with timeout
        try:
            task = asyncio.create_task(
                self._tools[tool_name].execute(tool_input)
            )
            self._active_calls[tool_id] = task

            result = await asyncio.wait_for(task, timeout=300.0)

            # Post-execution hooks
            await self.hook_pipeline.execute_post(
                tool_name, result
            )

            return result

        finally:
            del self._active_calls[tool_id]

    async def cancel_all(self):
        """Cancel all active tool calls"""
        for task in self._active_calls.values():
            task.cancel()
        await asyncio.gather(*self._active_calls.values(), return_exceptions=True)
```

**Tool types:**
1. **SDK MCP Tools** (in-process, fast)
2. **External MCP Servers** (stdio)
3. **Skills** (Python functions from plugins)
4. **Commands** (bash, grep, etc)

---

### 6. **Session Manager** (`session_manager.py`)

**Multi-session coordination:**

```python
class SessionManager:
    def __init__(self):
        self._sessions: Dict[str, AgentSession] = {}
        self._lock = asyncio.Lock()  # Protects session registry

    async def create_session(self, config: AgentConfig) -> AgentSession:
        """Create isolated session"""
        async with self._lock:
            session = AgentSession(str(uuid.uuid4()), config)
            self._sessions[session.session_id] = session
            return session

    async def get_session(self, session_id: str) -> Optional[AgentSession]:
        """Get existing session (thread-safe)"""
        async with self._lock:
            return self._sessions.get(session_id)

    async def close_session(self, session_id: str):
        """Close and cleanup session"""
        async with self._lock:
            session = self._sessions.pop(session_id, None)
            if session:
                await session.cancel()
                await session.cleanup()
```

---

## 🔌 Plugin System

### Plugin Manifest (`plugin.yaml`)

```yaml
name: my-plugin
version: 1.0.0

# Model configurations
models:
  - provider: anthropic
    model: claude-3.7-sonnet
    api_key_env: ANTHROPIC_API_KEY

  - provider: openai_compat
    name: deepseek-chat
    base_url: https://api.deepseek.com
    api_key_env: DEEPSEEK_API_KEY

  - provider: openai_compat
    name: moonshot-v1-8k
    base_url: https://api.moonshot.cn/v1
    api_key_env: MOONSHOT_API_KEY

# Skills (Python functions)
skills:
  - module: plugins.my_plugin.skills:summarize_text
  - module: plugins.my_plugin.skills:extract_tasks

# Commands (shell commands with safety)
commands:
  - name: grep
    command: grep
    allowed_args: ["-n", "-i", "-r"]
    sandbox_path: /workspace

# External MCP servers
mcp_servers:
  - name: postgres
    type: stdio
    command: npx
    args: ["@executeautomation/database-server", "--postgresql"]

# Sub-agents (delegated execution)
agents:
  - name: code-refactorer
    system_prompt: "You are a code refactoring specialist..."
    model_override: claude-3.7-sonnet

# Hooks (security, validation)
hooks:
  - event: pre_tool_use
    module: plugins.my_plugin.hooks:block_dangerous_bash
  - event: post_tool_use
    module: plugins.my_plugin.hooks:sanitize_output
```

---

## 🖥️ CLI Implementation

```python
# main_cli.py
import asyncio
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel

async def cli_main(prompt: str, model: str = "claude-3.7-sonnet"):
    # Create session
    session_manager = SessionManager()
    session = await session_manager.create_session(
        AgentConfig(plugin_paths=["plugins/my_plugin"])
    )

    # Subscribe to events
    cli_subscriber = session.event_store.subscribe(
        name="cli",
        queue_size=10000,
        drop_on_full=False  # Block on backpressure
    )

    # Render loop
    layout = Layout()
    with Live(layout, refresh_per_second=10) as live:
        # Start execution (non-blocking)
        exec_task = asyncio.create_task(
            session.execute(prompt, model_pref=model)
        )

        # Consume events and render
        async for event in session.event_store.stream(cli_subscriber):
            # Update layout based on event type
            layout["header"].update(Panel(f"Run: {event.run_id}"))

            if event.type == EventType.TOKEN_DELTA:
                layout["content"].update(Panel(event.delta))

            elif event.type == EventType.TOOL_CALL_STARTED:
                layout["tools"].update(
                    Panel(f"🔧 {event.tool_name}\n{event.tool_input}")
                )

            elif event.type == EventType.RUN_COMPLETED:
                break

        # Wait for execution to complete
        await exec_task
```

**Features:**
- Live updating UI (Rich library)
- Shows everything: tokens, tools, errors
- Keyboard interrupt → cancel
- Plan mode toggle
- Model selector

---

## 🌐 Web Server Implementation

```python
# main_web.py
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse

app = FastAPI()
session_manager = SessionManager()

@app.post("/api/session")
async def create_session():
    """Create new isolated session"""
    session = await session_manager.create_session(
        AgentConfig(plugin_paths=["plugins"])
    )
    return {"session_id": session.session_id}

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(ws: WebSocket, session_id: str):
    """Stream events to client"""
    await ws.accept()

    session = await session_manager.get_session(session_id)
    if not session:
        await ws.close()
        return

    # Subscribe to events
    ws_subscriber = session.event_store.subscribe(
        name=f"ws-{session_id}",
        queue_size=1000,
        drop_on_full=True  # Don't block model on slow client
    )

    try:
        # Stream events to WebSocket
        async for event in session.event_store.stream(ws_subscriber):
            await ws.send_json(event.to_dict())

            if event.type in (EventType.RUN_COMPLETED, EventType.RUN_CANCELLED):
                # Keep connection open for next query
                pass

    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        session.event_store.unsubscribe(ws_subscriber)

@app.post("/api/query/{session_id}")
async def execute_query(session_id: str, request: QueryRequest):
    """Execute agent query (non-blocking)"""
    session = await session_manager.get_session(session_id)
    if not session:
        return {"error": "Session not found"}

    # Start execution in background
    asyncio.create_task(
        session.execute(
            prompt=request.prompt,
            model_pref=request.model
        )
    )

    return {"ok": True}

@app.post("/api/cancel/{session_id}")
async def cancel_execution(session_id: str):
    """Cancel running execution"""
    session = await session_manager.get_session(session_id)
    if session:
        await session.cancel()
    return {"ok": True}
```

**Features:**
- Multi-session support
- WebSocket streaming (all events)
- Cancel endpoint
- Session isolation (zero cross-talk)
- Backpressure handling (drop events if client slow)

---

## 🔐 Concurrency Solutions

### Problem 1: Orphaned Tasks
**Solution:** `anyio.create_task_group()` - guarantees all tasks complete or cancelled

### Problem 2: Race Conditions
**Solution:** `asyncio.Lock()` on session registry, immutable events

### Problem 3: Cancellation
**Solution:** `cancel_scope.cancel()` propagates to all child tasks

### Problem 4: Backpressure
**Solution:** Bounded queues with drop policy for UI, blocking for persistence

### Problem 5: Tool Concurrency
**Solution:** Track active tool calls in dict, cancel all on abort

### Problem 6: Event Ordering
**Solution:** Single event queue per session, append-only log

---

## 📊 "Show Everything" - Event Visibility

**CLI Output:**
```
╭────────────────────────────────────────╮
│ 🤖 Agent: claude-3.7-sonnet           │
│ 📝 Prompt: List files in current dir │
╰────────────────────────────────────────╯

[12:34:56] 💭 I'll list the files for you

[12:34:57] 🔧 Tool Call: bash
           Input: {"command": "ls -la"}

[12:34:58] ✅ Tool Result (234ms):
           total 48
           drwxr-xr-x  12 user  staff   384 Nov  1 12:34 .
           ...

[12:34:59] 💭 Here are the files in your directory...

[12:35:01] ✨ Complete
           ⏱️  4.2s | 💰 $0.0023 | 📊 1,234 tokens
```

**Web UI:**
Every event creates a visual element:
- `TOKEN_DELTA` → Streaming text appears
- `TOOL_CALL_STARTED` → Tool panel with spinner
- `TOOL_CALL_COMPLETED` → Tool panel shows result
- `ERROR` → Red error banner
- `MESSAGE_COMPLETED` → Usage stats footer

---

## 🚀 Benefits Over Initial Design

| Aspect | Initial Design | Redesigned |
|--------|---------------|------------|
| **Concurrency** | Orphaned tasks, no cleanup | TaskGroups, guaranteed cleanup |
| **Events** | Dict soup | Strongly typed, immutable |
| **Tool Execution** | Untracked | Tracked, cancellable |
| **Backpressure** | Unbounded queues | Bounded with drop policy |
| **Multi-Model** | Two execution paths | Single unified path |
| **Session Isolation** | Shared state | Zero shared state |
| **Debuggability** | Hard | Easy (event log) |
| **Testing** | Hard | Easy (mock event store) |

---

## 📝 Next Steps

1. Implement core components (events, event_store, model_adapter)
2. Add Tool Executor with hook pipeline
3. Implement AgentSession with proper lifecycle
4. Add SessionManager for multi-session
5. Build CLI with Rich UI
6. Build Web Server with FastAPI + WebSocket
7. Load plugins from manifest
8. Add tests (event replay makes this easy!)

This architecture is **production-ready**, **testable**, and **maintainable** 🎯
