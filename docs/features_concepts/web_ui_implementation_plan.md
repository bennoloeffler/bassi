# Web UI Implementation Plan & Code Examples

**Feature**: Web UI Implementation
**Status**: Planning - Code Examples & Task Breakdown
**Version**: 1.0

---

## Table of Contents
1. [Backend Implementation](#backend-implementation)
2. [Frontend Implementation](#frontend-implementation)
3. [Detailed Task Breakdown](#detailed-task-breakdown)
4. [Testing Plan](#testing-plan)

---

## Backend Implementation

### 1. FastAPI Web Server (`bassi/web_server.py`)

```python
"""
FastAPI web server for bassi web UI

Provides:
- Static file serving (HTML, CSS, JS)
- WebSocket endpoint for bidirectional chat
- Health check endpoint
"""

import logging
from pathlib import Path
from typing import Dict, Any
import json

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
import anyio

logger = logging.getLogger(__name__)


class WebUIServer:
    """Web UI server using FastAPI"""

    def __init__(self, agent, host: str = "localhost", port: int = 8765):
        self.agent = agent
        self.host = host
        self.port = port
        self.app = FastAPI(title="bassi Web UI")

        # Track active WebSocket connections
        self.active_connections: list[WebSocket] = []

        # Setup routes
        self._setup_routes()

    def _setup_routes(self):
        """Setup FastAPI routes"""

        # Serve static files
        static_dir = Path(__file__).parent / "static"
        self.app.mount(
            "/static",
            StaticFiles(directory=str(static_dir)),
            name="static"
        )

        # Root route - serve index.html
        @self.app.get("/")
        async def root():
            static_dir = Path(__file__).parent / "static"
            index_path = static_dir / "index.html"
            return HTMLResponse(content=index_path.read_text())

        # Health check
        @self.app.get("/health")
        async def health():
            return JSONResponse({"status": "ok", "service": "bassi-web-ui"})

        # WebSocket endpoint
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await self._handle_websocket(websocket)

    async def _handle_websocket(self, websocket: WebSocket):
        """Handle WebSocket connection"""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

        try:
            # Send welcome message
            await websocket.send_json({
                "type": "connected",
                "message": "Connected to bassi"
            })

            # Listen for messages
            while True:
                data = await websocket.receive_json()
                await self._process_message(websocket, data)

        except WebSocketDisconnect:
            logger.info("WebSocket disconnected")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            self.active_connections.remove(websocket)
            logger.info(f"Remaining connections: {len(self.active_connections)}")

    async def _process_message(self, websocket: WebSocket, data: Dict[str, Any]):
        """Process incoming message from client"""
        msg_type = data.get("type")

        if msg_type == "user_message":
            # User sent a chat message
            content = data.get("content", "")
            logger.info(f"User message: {content}")

            # Stream response from agent
            try:
                async for event in self.agent.chat(content):
                    # Convert agent event to WebSocket message
                    ws_message = self._agent_event_to_ws_message(event)
                    if ws_message:
                        await websocket.send_json(ws_message)
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": str(e)
                })

        else:
            logger.warning(f"Unknown message type: {msg_type}")

    def _agent_event_to_ws_message(self, event: Any) -> Dict[str, Any] | None:
        """
        Convert agent event to WebSocket message format

        This needs to be implemented based on the actual event structure
        from BassiAgent.chat()
        """
        # TODO: Implement based on actual agent event structure
        # This is a placeholder showing the expected message types

        event_type = type(event).__name__

        # Content delta (streaming text)
        if event_type == "ContentDelta":
            return {
                "type": "content_delta",
                "text": event.text
            }

        # Tool call started
        elif event_type == "ToolCallStart":
            return {
                "type": "tool_call_start",
                "tool_name": event.tool_name,
                "input": event.input_data
            }

        # Tool call completed
        elif event_type == "ToolCallEnd":
            return {
                "type": "tool_call_end",
                "tool_name": event.tool_name,
                "output": event.output_data
            }

        # Message completed
        elif event_type == "MessageComplete":
            return {
                "type": "message_complete",
                "usage": {
                    "input_tokens": event.input_tokens,
                    "output_tokens": event.output_tokens,
                    "cost_usd": event.cost_usd,
                    "duration_ms": event.duration_ms
                }
            }

        # Status update
        elif event_type == "StatusUpdate":
            return {
                "type": "status",
                "message": event.message
            }

        return None

    async def run(self):
        """Run the web server"""
        import uvicorn

        logger.info(f"Starting web UI server on http://{self.host}:{self.port}")

        config = uvicorn.Config(
            app=self.app,
            host=self.host,
            port=self.port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()


async def start_web_server(agent, host: str = "localhost", port: int = 8765):
    """
    Start the web UI server

    Args:
        agent: BassiAgent instance
        host: Server host
        port: Server port
    """
    server = WebUIServer(agent, host, port)
    await server.run()
```

---

### 2. Agent Event Emission (`bassi/agent.py` modifications)

```python
# Add to BassiAgent class

from dataclasses import dataclass
from typing import Any, AsyncIterator
from enum import Enum

class EventType(Enum):
    """Event types emitted by agent"""
    CONTENT_DELTA = "content_delta"
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_END = "tool_call_end"
    MESSAGE_COMPLETE = "message_complete"
    STATUS_UPDATE = "status_update"
    ERROR = "error"


@dataclass
class AgentEvent:
    """Base event class"""
    type: EventType


@dataclass
class ContentDeltaEvent(AgentEvent):
    """Streaming text chunk"""
    text: str

    def __post_init__(self):
        self.type = EventType.CONTENT_DELTA


@dataclass
class ToolCallStartEvent(AgentEvent):
    """Tool call started"""
    tool_name: str
    input_data: dict

    def __post_init__(self):
        self.type = EventType.TOOL_CALL_START


@dataclass
class ToolCallEndEvent(AgentEvent):
    """Tool call completed"""
    tool_name: str
    output_data: Any
    success: bool

    def __post_init__(self):
        self.type = EventType.TOOL_CALL_END


@dataclass
class MessageCompleteEvent(AgentEvent):
    """Message completed"""
    input_tokens: int
    output_tokens: int
    cost_usd: float
    duration_ms: int

    def __post_init__(self):
        self.type = EventType.MESSAGE_COMPLETE


@dataclass
class StatusUpdateEvent(AgentEvent):
    """Status message"""
    message: str

    def __post_init__(self):
        self.type = EventType.STATUS_UPDATE


# Modify BassiAgent.chat() to yield events

async def chat(self, message: str) -> AsyncIterator[AgentEvent]:
    """
    Chat with agent, yielding events for streaming

    Args:
        message: User message

    Yields:
        AgentEvent: Events for content, tool calls, status, etc.
    """
    # ... existing implementation ...

    # When processing StreamEvent
    if msg_class_name == "StreamEvent":
        event = getattr(msg, "event", {})
        if event.get("type") == "content_block_delta":
            delta = event.get("delta", {})
            if delta.get("type") == "text_delta":
                text = delta.get("text", "")

                # Emit event
                yield ContentDeltaEvent(text=text)

    # When tool call detected
    if msg_class_name == "ToolUseBlock":
        yield ToolCallStartEvent(
            tool_name=msg.name,
            input_data=msg.input
        )

    # When tool result received
    if msg_class_name == "ToolResult":
        yield ToolCallEndEvent(
            tool_name=msg.tool_name,
            output_data=msg.output,
            success=msg.is_error is False
        )

    # When message complete
    if usage_data:
        yield MessageCompleteEvent(
            input_tokens=usage_data.input_tokens,
            output_tokens=usage_data.output_tokens,
            cost_usd=calculated_cost,
            duration_ms=duration_ms
        )
```

---

### 3. Main Entry Point (`bassi/main.py` modifications)

```python
# Add to main.py

import argparse
from bassi.web_server import start_web_server


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="bassi - Benno's Assistant")
    parser.add_argument(
        "--web",
        action="store_true",
        help="Enable web UI"
    )
    parser.add_argument(
        "--no-cli",
        action="store_true",
        help="Disable CLI (web-only mode)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Web UI port (default: 8765)"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="Web UI host (default: localhost)"
    )
    return parser.parse_args()


async def main_async():
    """Main async entry point with web UI support"""
    args = parse_args()

    # Initialize agent
    agent = BassiAgent(...)

    # Start web server if enabled
    web_task = None
    if args.web:
        console.print(f"[bold green]🌐 Starting web UI on http://{args.host}:{args.port}[/bold green]")

        async def run_web_server():
            await start_web_server(agent, args.host, args.port)

        # Start web server in background
        async with anyio.create_task_group() as tg:
            tg.start_soon(run_web_server)

            # Run CLI unless --no-cli specified
            if not args.no_cli:
                await cli_main_loop(agent)
            else:
                # Keep running (web-only mode)
                await anyio.sleep_forever()
    else:
        # CLI-only mode
        await cli_main_loop(agent)


async def cli_main_loop(agent: BassiAgent):
    """CLI main loop (existing implementation)"""
    # ... existing main loop code ...
    pass
```

---

## Frontend Implementation

### 1. HTML Structure (`bassi/static/index.html`)

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>bassi - Benno's Assistant</title>
    <link rel="stylesheet" href="/static/style.css">
    <!-- Prism.js for code highlighting -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism-tomorrow.min.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/prism.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-python.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-javascript.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-bash.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-json.min.js"></script>
</head>
<body>
    <!-- Header -->
    <header class="header">
        <div class="header-content">
            <h1 class="title">🤖 bassi</h1>
            <div class="connection-status">
                <span id="status-indicator" class="status-dot offline"></span>
                <span id="status-text">Connecting...</span>
            </div>
        </div>
    </header>

    <!-- Conversation Container -->
    <main class="conversation-container" id="conversation">
        <!-- Messages will be appended here dynamically -->
        <div class="welcome-message">
            <h2>Welcome to bassi!</h2>
            <p>Your personal AI assistant. Type a message below to get started.</p>
        </div>
    </main>

    <!-- Input Area -->
    <footer class="input-container">
        <textarea
            id="message-input"
            placeholder="Type your message here..."
            rows="1"
            autocomplete="off"
        ></textarea>
        <button id="send-button" class="btn-send" disabled>
            <span>Send</span>
        </button>
    </footer>

    <script src="/static/app.js"></script>
</body>
</html>
```

---

### 2. Styling (`bassi/static/style.css`)

```css
/* Variables */
:root {
    /* Colors - Terminal Theme */
    --bg-primary: #1e1e1e;
    --bg-secondary: #252526;
    --bg-elevated: #2d2d30;
    --bg-hover: #37373d;

    --text-primary: #d4d4d4;
    --text-secondary: #858585;
    --text-bright: #ffffff;
    --text-muted: #6a6a6a;

    --accent-blue: #4fc3f7;
    --accent-green: #81c784;
    --accent-yellow: #ffd54f;
    --accent-red: #e57373;
    --accent-purple: #ba68c8;

    --border: #3e3e42;
    --code-bg: #1e1e1e;

    /* Spacing */
    --spacing-xs: 4px;
    --spacing-sm: 8px;
    --spacing-md: 16px;
    --spacing-lg: 24px;
    --spacing-xl: 32px;

    /* Typography */
    --font-mono: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
    --font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

/* Reset & Base */
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: var(--font-sans);
    background: var(--bg-primary);
    color: var(--text-primary);
    height: 100vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

/* Header */
.header {
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border);
    padding: var(--spacing-md);
    flex-shrink: 0;
}

.header-content {
    display: flex;
    justify-content: space-between;
    align-items: center;
    max-width: 1200px;
    margin: 0 auto;
}

.title {
    font-size: 1.5rem;
    font-weight: 600;
    color: var(--accent-blue);
}

.connection-status {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
    font-size: 0.875rem;
    color: var(--text-secondary);
}

.status-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    display: inline-block;
}

.status-dot.online {
    background: var(--accent-green);
    box-shadow: 0 0 8px var(--accent-green);
}

.status-dot.offline {
    background: var(--text-muted);
}

/* Conversation Container */
.conversation-container {
    flex: 1;
    overflow-y: auto;
    padding: var(--spacing-lg);
    scroll-behavior: smooth;
}

.welcome-message {
    text-align: center;
    padding: var(--spacing-xl);
    color: var(--text-secondary);
}

.welcome-message h2 {
    color: var(--accent-blue);
    margin-bottom: var(--spacing-md);
}

/* Message Bubbles */
.message {
    margin-bottom: var(--spacing-lg);
    max-width: 900px;
    margin-left: auto;
    margin-right: auto;
}

.message-header {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
    margin-bottom: var(--spacing-sm);
}

.message-header .icon {
    font-size: 1.25rem;
}

.message-header .label {
    font-weight: 600;
    color: var(--text-bright);
}

.message-header .timestamp {
    font-size: 0.75rem;
    color: var(--text-muted);
    margin-left: auto;
}

.message-header .status {
    font-size: 0.75rem;
    color: var(--accent-yellow);
}

.message-content {
    background: var(--bg-secondary);
    padding: var(--spacing-md);
    border-radius: 8px;
    border-left: 3px solid var(--border);
}

.user-message .message-content {
    border-left-color: var(--accent-blue);
}

.assistant-message .message-content {
    border-left-color: var(--accent-green);
}

/* Markdown Content */
.markdown {
    line-height: 1.6;
}

.markdown p {
    margin-bottom: var(--spacing-md);
}

.markdown h1, .markdown h2, .markdown h3 {
    margin-top: var(--spacing-md);
    margin-bottom: var(--spacing-sm);
    color: var(--text-bright);
}

.markdown code {
    background: var(--code-bg);
    padding: 2px 6px;
    border-radius: 4px;
    font-family: var(--font-mono);
    font-size: 0.875rem;
}

.markdown pre {
    background: var(--code-bg);
    padding: var(--spacing-md);
    border-radius: 6px;
    overflow-x: auto;
    margin: var(--spacing-md) 0;
}

.markdown pre code {
    background: none;
    padding: 0;
}

.markdown ul, .markdown ol {
    margin-left: var(--spacing-lg);
    margin-bottom: var(--spacing-md);
}

.markdown li {
    margin-bottom: var(--spacing-xs);
}

.markdown a {
    color: var(--accent-blue);
    text-decoration: none;
}

.markdown a:hover {
    text-decoration: underline;
}

/* Tool Call Panel */
.tool-call {
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: 6px;
    margin: var(--spacing-md) 0;
}

.tool-header {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
    padding: var(--spacing-sm) var(--spacing-md);
    cursor: pointer;
    user-select: none;
    background: var(--bg-secondary);
    border-radius: 6px 6px 0 0;
}

.tool-header:hover {
    background: var(--bg-hover);
}

.tool-header .icon {
    font-size: 1rem;
}

.tool-header .name {
    font-family: var(--font-mono);
    font-size: 0.875rem;
    color: var(--accent-purple);
    font-weight: 600;
}

.tool-header .toggle {
    margin-left: auto;
    color: var(--text-secondary);
    transition: transform 0.2s;
}

.tool-call.expanded .tool-header .toggle {
    transform: rotate(180deg);
}

.tool-body {
    padding: var(--spacing-md);
    display: none;
}

.tool-call.expanded .tool-body {
    display: block;
}

.tool-input, .tool-output {
    margin-bottom: var(--spacing-md);
}

.tool-input h4, .tool-output h4 {
    font-size: 0.75rem;
    text-transform: uppercase;
    color: var(--text-secondary);
    margin-bottom: var(--spacing-sm);
    letter-spacing: 0.5px;
}

.tool-input pre, .tool-output pre {
    background: var(--code-bg);
    padding: var(--spacing-md);
    border-radius: 4px;
    overflow-x: auto;
    font-family: var(--font-mono);
    font-size: 0.875rem;
    line-height: 1.5;
}

/* JSON Syntax Highlighting */
.json-key { color: #9876aa; }
.json-string { color: #6a8759; }
.json-number { color: #6897bb; }
.json-boolean { color: #cc7832; }
.json-null { color: #808080; }

/* Usage Stats */
.usage-stats {
    display: flex;
    gap: var(--spacing-md);
    padding: var(--spacing-sm) var(--spacing-md);
    background: var(--bg-secondary);
    border-radius: 6px;
    font-size: 0.875rem;
    margin-top: var(--spacing-md);
}

.usage-stats .stat {
    color: var(--text-secondary);
}

/* Input Area */
.input-container {
    background: var(--bg-secondary);
    border-top: 1px solid var(--border);
    padding: var(--spacing-md);
    flex-shrink: 0;
    display: flex;
    gap: var(--spacing-md);
    max-width: 1200px;
    margin: 0 auto;
    width: 100%;
}

#message-input {
    flex: 1;
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: var(--spacing-md);
    color: var(--text-primary);
    font-family: var(--font-sans);
    font-size: 0.95rem;
    resize: none;
    max-height: 200px;
    overflow-y: auto;
}

#message-input:focus {
    outline: none;
    border-color: var(--accent-blue);
}

.btn-send {
    background: var(--accent-blue);
    color: var(--bg-primary);
    border: none;
    border-radius: 6px;
    padding: var(--spacing-md) var(--spacing-lg);
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    font-size: 0.95rem;
}

.btn-send:hover:not(:disabled) {
    background: var(--accent-green);
    transform: translateY(-1px);
}

.btn-send:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

/* Scrollbar */
.conversation-container::-webkit-scrollbar {
    width: 8px;
}

.conversation-container::-webkit-scrollbar-track {
    background: var(--bg-primary);
}

.conversation-container::-webkit-scrollbar-thumb {
    background: var(--border);
    border-radius: 4px;
}

.conversation-container::-webkit-scrollbar-thumb:hover {
    background: var(--text-muted);
}

/* Responsive */
@media (max-width: 768px) {
    .header-content {
        flex-direction: column;
        gap: var(--spacing-sm);
    }

    .conversation-container {
        padding: var(--spacing-md);
    }

    .message {
        max-width: 100%;
    }
}
```

---

### 3. JavaScript Application (`bassi/static/app.js`)

```javascript
/**
 * bassi Web UI Client
 *
 * Handles:
 * - WebSocket connection
 * - Message sending/receiving
 * - Streaming markdown rendering
 * - Tool call display
 * - UI updates
 */

class BassiWebClient {
    constructor() {
        this.ws = null;
        this.isConnected = false;
        this.currentAssistantMessage = null;
        this.markdownRenderer = new StreamingMarkdownRenderer();

        // DOM elements
        this.conversationEl = document.getElementById('conversation');
        this.messageInput = document.getElementById('message-input');
        this.sendButton = document.getElementById('send-button');
        this.statusIndicator = document.getElementById('status-indicator');
        this.statusText = document.getElementById('status-text');

        this.init();
    }

    init() {
        // Setup event listeners
        this.sendButton.addEventListener('click', () => this.sendMessage());
        this.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Auto-resize textarea
        this.messageInput.addEventListener('input', () => {
            this.messageInput.style.height = 'auto';
            this.messageInput.style.height = this.messageInput.scrollHeight + 'px';
        });

        // Connect to WebSocket
        this.connect();
    }

    connect() {
        const wsUrl = `ws://${window.location.host}/ws`;
        console.log('Connecting to WebSocket:', wsUrl);

        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => this.onConnected();
        this.ws.onmessage = (event) => this.onMessage(event);
        this.ws.onclose = () => this.onDisconnected();
        this.ws.onerror = (error) => this.onError(error);
    }

    onConnected() {
        console.log('WebSocket connected');
        this.isConnected = true;
        this.updateConnectionStatus('online', 'Connected');
        this.sendButton.disabled = false;

        // Remove welcome message if exists
        const welcome = this.conversationEl.querySelector('.welcome-message');
        if (welcome) {
            welcome.remove();
        }
    }

    onDisconnected() {
        console.log('WebSocket disconnected');
        this.isConnected = false;
        this.updateConnectionStatus('offline', 'Disconnected');
        this.sendButton.disabled = true;

        // Attempt reconnection after 3 seconds
        setTimeout(() => this.connect(), 3000);
    }

    onError(error) {
        console.error('WebSocket error:', error);
        this.updateConnectionStatus('offline', 'Connection error');
    }

    onMessage(event) {
        const data = JSON.parse(event.data);
        console.log('Received:', data);

        switch (data.type) {
            case 'connected':
                // Initial connection message
                break;

            case 'content_delta':
                this.handleContentDelta(data);
                break;

            case 'tool_call_start':
                this.handleToolCallStart(data);
                break;

            case 'tool_call_end':
                this.handleToolCallEnd(data);
                break;

            case 'message_complete':
                this.handleMessageComplete(data);
                break;

            case 'status':
                this.handleStatus(data);
                break;

            case 'error':
                this.handleError(data);
                break;

            default:
                console.warn('Unknown message type:', data.type);
        }
    }

    updateConnectionStatus(status, text) {
        this.statusIndicator.className = `status-dot ${status}`;
        this.statusText.textContent = text;
    }

    sendMessage() {
        const content = this.messageInput.value.trim();
        if (!content || !this.isConnected) return;

        // Display user message
        this.addUserMessage(content);

        // Send to server
        this.ws.send(JSON.stringify({
            type: 'user_message',
            content: content
        }));

        // Clear input
        this.messageInput.value = '';
        this.messageInput.style.height = 'auto';
        this.messageInput.focus();
    }

    addUserMessage(content) {
        const messageEl = this.createMessageElement('user', content);
        this.conversationEl.appendChild(messageEl);
        this.scrollToBottom();
    }

    createMessageElement(role, content = '') {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}-message`;

        const timestamp = new Date().toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit'
        });

        const icon = role === 'user' ? '👤' : '🤖';
        const label = role === 'user' ? 'You' : 'Assistant';

        messageDiv.innerHTML = `
            <div class="message-header">
                <span class="icon">${icon}</span>
                <span class="label">${label}</span>
                <span class="timestamp">${timestamp}</span>
            </div>
            <div class="message-content markdown">${this.escapeHtml(content)}</div>
        `;

        return messageDiv;
    }

    handleContentDelta(data) {
        // Create assistant message if doesn't exist
        if (!this.currentAssistantMessage) {
            this.currentAssistantMessage = this.createMessageElement('assistant');
            this.conversationEl.appendChild(this.currentAssistantMessage);

            // Add streaming indicator
            const header = this.currentAssistantMessage.querySelector('.message-header');
            const statusEl = document.createElement('span');
            statusEl.className = 'status';
            statusEl.textContent = '● streaming...';
            header.appendChild(statusEl);
        }

        // Append text using streaming markdown renderer
        const contentEl = this.currentAssistantMessage.querySelector('.message-content');
        this.markdownRenderer.appendChunk(contentEl, data.text);

        this.scrollToBottom();
    }

    handleToolCallStart(data) {
        if (!this.currentAssistantMessage) {
            this.currentAssistantMessage = this.createMessageElement('assistant');
            this.conversationEl.appendChild(this.currentAssistantMessage);
        }

        const contentEl = this.currentAssistantMessage.querySelector('.message-content');
        const toolCallEl = this.createToolCallElement(data.tool_name, data.input);
        contentEl.appendChild(toolCallEl);

        this.scrollToBottom();
    }

    handleToolCallEnd(data) {
        // Find the tool call element and update it
        const contentEl = this.currentAssistantMessage.querySelector('.message-content');
        const toolCallEl = contentEl.querySelector(`[data-tool="${data.tool_name}"]`);

        if (toolCallEl) {
            const outputEl = toolCallEl.querySelector('.tool-output pre');
            outputEl.textContent = this.formatToolOutput(data.output);

            // Update tool call status
            toolCallEl.classList.add('completed');
            if (!data.success) {
                toolCallEl.classList.add('error');
            }
        }

        this.scrollToBottom();
    }

    handleMessageComplete(data) {
        if (!this.currentAssistantMessage) return;

        // Remove streaming indicator
        const statusEl = this.currentAssistantMessage.querySelector('.status');
        if (statusEl) {
            statusEl.remove();
        }

        // Add usage stats
        const contentEl = this.currentAssistantMessage.querySelector('.message-content');
        const usageEl = this.createUsageStatsElement(data.usage);
        contentEl.appendChild(usageEl);

        // Finalize markdown rendering
        const markdownEl = contentEl.querySelector('.markdown-content');
        if (markdownEl) {
            this.markdownRenderer.finalize(markdownEl);
        }

        // Reset current message
        this.currentAssistantMessage = null;

        this.scrollToBottom();
    }

    handleStatus(data) {
        this.updateConnectionStatus('online', data.message);
    }

    handleError(data) {
        console.error('Error from server:', data.message);

        // Display error message
        const errorEl = document.createElement('div');
        errorEl.className = 'message error-message';
        errorEl.innerHTML = `
            <div class="message-header">
                <span class="icon">⚠️</span>
                <span class="label">Error</span>
            </div>
            <div class="message-content">
                ${this.escapeHtml(data.message)}
            </div>
        `;
        this.conversationEl.appendChild(errorEl);

        this.currentAssistantMessage = null;
        this.scrollToBottom();
    }

    createToolCallElement(toolName, input) {
        const toolEl = document.createElement('div');
        toolEl.className = 'tool-call collapsed';
        toolEl.setAttribute('data-tool', toolName);

        const inputHtml = this.syntaxHighlightJSON(input);

        toolEl.innerHTML = `
            <div class="tool-header" onclick="this.parentElement.classList.toggle('expanded')">
                <span class="icon">🔧</span>
                <span class="name">${this.escapeHtml(toolName)}</span>
                <span class="toggle">▼</span>
            </div>
            <div class="tool-body">
                <div class="tool-input">
                    <h4>Input:</h4>
                    <pre>${inputHtml}</pre>
                </div>
                <div class="tool-output">
                    <h4>Output:</h4>
                    <pre>Running...</pre>
                </div>
            </div>
        `;

        return toolEl;
    }

    createUsageStatsElement(usage) {
        const statsEl = document.createElement('div');
        statsEl.className = 'usage-stats';

        const duration = (usage.duration_ms / 1000).toFixed(1);
        const cost = usage.cost_usd.toFixed(4);
        const totalCost = usage.total_cost_usd ? usage.total_cost_usd.toFixed(4) : cost;

        statsEl.innerHTML = `
            <span class="stat">⏱️ ${duration}s</span>
            <span class="stat">💰 $${cost}</span>
            <span class="stat">💵 Total: $${totalCost}</span>
        `;

        return statsEl;
    }

    syntaxHighlightJSON(obj) {
        let json = JSON.stringify(obj, null, 2);
        json = this.escapeHtml(json);

        return json.replace(
            /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g,
            (match) => {
                let cls = 'json-number';
                if (/^"/.test(match)) {
                    cls = /:$/.test(match) ? 'json-key' : 'json-string';
                } else if (/true|false/.test(match)) {
                    cls = 'json-boolean';
                } else if (/null/.test(match)) {
                    cls = 'json-null';
                }
                return `<span class="${cls}">${match}</span>`;
            }
        );
    }

    formatToolOutput(output) {
        if (typeof output === 'object') {
            return JSON.stringify(output, null, 2);
        }
        return String(output);
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    scrollToBottom() {
        this.conversationEl.scrollTop = this.conversationEl.scrollHeight;
    }
}


/**
 * Streaming Markdown Renderer
 *
 * Handles incremental rendering of markdown as it streams in
 */
class StreamingMarkdownRenderer {
    constructor() {
        this.buffer = '';
    }

    appendChunk(containerEl, text) {
        this.buffer += text;

        // Simple approach: just append text and let browser render
        // We'll use marked.js to re-render periodically
        containerEl.textContent = this.buffer;

        // TODO: Implement proper incremental rendering
        // For now, using simple text append
    }

    finalize(containerEl) {
        // Final render with marked.js
        if (typeof marked !== 'undefined') {
            const html = marked.parse(this.buffer);
            containerEl.innerHTML = html;

            // Highlight code blocks with Prism
            containerEl.querySelectorAll('pre code').forEach((block) => {
                Prism.highlightElement(block);
            });
        }

        this.buffer = '';
    }
}


// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.bassiClient = new BassiWebClient();
});
```

---

## Detailed Task Breakdown

### Phase 1: Backend Foundation (2-3 hours)

#### Task 1.1: Create FastAPI Server Structure
**File**: `bassi/web_server.py`
**Estimated Time**: 1 hour

**Subtasks:**
- [ ] Create `WebUIServer` class
- [ ] Setup FastAPI app with routes
- [ ] Implement static file serving
- [ ] Add health check endpoint
- [ ] Add WebSocket connection handling
- [ ] Test basic server startup

**Acceptance Criteria:**
- Server starts on specified port
- `/health` returns 200 OK
- `/` serves index.html
- WebSocket connections can be established

---

#### Task 1.2: Implement Agent Event System
**File**: `bassi/agent.py`
**Estimated Time**: 1.5 hours

**Subtasks:**
- [ ] Define event dataclasses (`ContentDeltaEvent`, etc.)
- [ ] Modify `chat()` method to yield events
- [ ] Handle streaming text events
- [ ] Handle tool call events
- [ ] Handle message complete events
- [ ] Test event emission in CLI mode

**Acceptance Criteria:**
- Events are emitted during agent chat
- CLI still works correctly
- All event types are covered
- No regressions in existing functionality

---

#### Task 1.3: Add Web Mode to Main Entry
**File**: `bassi/main.py`
**Estimated Time**: 0.5 hours

**Subtasks:**
- [ ] Add command-line argument parsing
- [ ] Add `--web`, `--no-cli`, `--port`, `--host` flags
- [ ] Start web server in background task
- [ ] Handle graceful shutdown
- [ ] Test CLI-only, web-only, and combined modes

**Acceptance Criteria:**
- `--web` starts web server
- `--no-cli` disables CLI
- Both can run simultaneously
- Ctrl+C shuts down gracefully

---

### Phase 2: Frontend Core (3-4 hours)

#### Task 2.1: Create HTML Structure
**File**: `bassi/static/index.html`
**Estimated Time**: 1 hour

**Subtasks:**
- [ ] Create basic HTML5 structure
- [ ] Add header with connection status
- [ ] Add conversation container
- [ ] Add input area with textarea and send button
- [ ] Include Prism.js for code highlighting
- [ ] Test responsive layout

**Acceptance Criteria:**
- Clean, semantic HTML
- All required elements present
- Responsive on different screen sizes
- Accessible (proper ARIA labels)

---

#### Task 2.2: Implement WebSocket Client
**File**: `bassi/static/app.js` (Part 1)
**Estimated Time**: 1.5 hours

**Subtasks:**
- [ ] Create `BassiWebClient` class
- [ ] Implement WebSocket connection logic
- [ ] Handle connection/disconnection events
- [ ] Implement auto-reconnection
- [ ] Add message sending functionality
- [ ] Add connection status updates
- [ ] Test WebSocket communication

**Acceptance Criteria:**
- WebSocket connects on page load
- Connection status updates correctly
- Auto-reconnect works after disconnect
- Messages can be sent to server

---

#### Task 2.3: Basic Message Display
**File**: `bassi/static/app.js` (Part 2)
**Estimated Time**: 1 hour

**Subtasks:**
- [ ] Create user message bubble
- [ ] Create assistant message bubble
- [ ] Handle message timestamps
- [ ] Implement auto-scroll to bottom
- [ ] Add text input handling (Enter key, Send button)
- [ ] Test message display

**Acceptance Criteria:**
- User messages appear immediately
- Assistant messages display correctly
- Auto-scroll works smoothly
- Input clears after sending

---

### Phase 3: Streaming Markdown (4-5 hours)

#### Task 3.1: Research Streaming Approaches
**Estimated Time**: 1 hour

**Subtasks:**
- [ ] Test marked.js with buffering
- [ ] Test custom incremental parser
- [ ] Benchmark performance
- [ ] Choose approach (recommend buffered marked.js for simplicity)
- [ ] Document decision

**Acceptance Criteria:**
- Approach chosen and documented
- Trade-offs understood
- Performance acceptable

---

#### Task 3.2: Implement Streaming Renderer (Simple)
**File**: `bassi/static/app.js` - `StreamingMarkdownRenderer`
**Estimated Time**: 2 hours

**Subtasks:**
- [ ] Create `StreamingMarkdownRenderer` class
- [ ] Implement buffer accumulation
- [ ] Add debounced re-rendering with marked.js
- [ ] Handle incomplete markdown gracefully
- [ ] Test with various markdown elements
- [ ] Optimize for smooth streaming

**Acceptance Criteria:**
- Text streams smoothly without flashing
- Markdown renders correctly
- Code blocks highlight properly
- No performance issues

---

#### Task 3.3: Integrate Prism.js
**Estimated Time**: 1 hour

**Subtasks:**
- [ ] Include Prism.js library
- [ ] Add language support (Python, JavaScript, Bash, JSON)
- [ ] Apply syntax highlighting after markdown render
- [ ] Choose color theme (recommend Tomorrow Night)
- [ ] Test code blocks

**Acceptance Criteria:**
- Code blocks have syntax highlighting
- Multiple languages supported
- Theme matches overall design

---

### Phase 4: Tool Call Display (2-3 hours)

#### Task 4.1: Implement JSON Highlighting
**File**: `bassi/static/app.js` - `syntaxHighlightJSON()`
**Estimated Time**: 1 hour

**Subtasks:**
- [ ] Create regex-based JSON highlighter
- [ ] Handle keys, strings, numbers, booleans, null
- [ ] Add proper HTML escaping
- [ ] Add CSS for JSON colors
- [ ] Test with complex JSON objects

**Acceptance Criteria:**
- JSON is pretty-printed
- Syntax highlighting works
- Colors match theme

---

#### Task 4.2: Create Tool Call Panels
**File**: `bassi/static/app.js` + `style.css`
**Estimated Time**: 1.5 hours

**Subtasks:**
- [ ] Create tool call panel component
- [ ] Implement collapse/expand toggle
- [ ] Display tool name, input, output
- [ ] Show tool call status (running, complete, error)
- [ ] Style panels attractively
- [ ] Test tool call flow

**Acceptance Criteria:**
- Tool calls appear during execution
- Panels are collapsible
- Input/output displayed correctly
- Status indicators work

---

### Phase 5: Polish & Features (2-3 hours)

#### Task 5.1: Styling & Responsiveness
**File**: `bassi/static/style.css`
**Estimated Time**: 1.5 hours

**Subtasks:**
- [ ] Implement terminal-inspired dark theme
- [ ] Add smooth animations
- [ ] Make responsive for tablet/mobile
- [ ] Style scrollbars
- [ ] Add hover effects
- [ ] Test on different screen sizes

**Acceptance Criteria:**
- UI looks polished and professional
- Animations are smooth
- Responsive on all screen sizes
- Theme is consistent

---

#### Task 5.2: Usage Stats Display
**File**: `bassi/static/app.js`
**Estimated Time**: 0.5 hours

**Subtasks:**
- [ ] Create usage stats component
- [ ] Display tokens, cost, duration
- [ ] Show cumulative cost
- [ ] Add warning indicators for context limits
- [ ] Style stats panel

**Acceptance Criteria:**
- Usage stats appear after each message
- All metrics displayed correctly
- Warnings show when needed

---

#### Task 5.3: Error Handling
**File**: `bassi/static/app.js`
**Estimated Time**: 1 hour

**Subtasks:**
- [ ] Implement error message display
- [ ] Handle API errors
- [ ] Handle WebSocket errors
- [ ] Add retry logic
- [ ] Test error scenarios

**Acceptance Criteria:**
- Errors display clearly
- User can recover from errors
- No silent failures

---

### Phase 6: Testing & Documentation (2-3 hours)

#### Task 6.1: Backend Tests
**File**: `tests/test_web_server.py`
**Estimated Time**: 1.5 hours

**Subtasks:**
- [ ] Test WebSocket connection
- [ ] Test message routing
- [ ] Test event emission
- [ ] Test error handling
- [ ] Test concurrent connections

**Acceptance Criteria:**
- All backend tests pass
- Code coverage >80%

---

#### Task 6.2: Manual Testing
**Estimated Time**: 1 hour

**Subtasks:**
- [ ] Test full chat flow
- [ ] Test streaming behavior
- [ ] Test tool calls
- [ ] Test reconnection
- [ ] Test multiple browsers
- [ ] Test mobile responsiveness

**Acceptance Criteria:**
- All manual test cases pass
- No critical bugs found

---

#### Task 6.3: Documentation
**Estimated Time**: 0.5 hours

**Subtasks:**
- [ ] Update README.md with web UI instructions
- [ ] Add usage examples
- [ ] Document configuration options
- [ ] Add troubleshooting guide

**Acceptance Criteria:**
- Documentation complete
- Examples are clear
- Configuration documented

---

## Testing Plan

### Backend Unit Tests

```python
# tests/test_web_server.py

import pytest
from fastapi.testclient import TestClient
from bassi.web_server import WebUIServer
from bassi.agent import BassiAgent


@pytest.fixture
def mock_agent():
    """Mock BassiAgent for testing"""
    # Create mock agent
    pass


@pytest.fixture
def test_server(mock_agent):
    """Test server instance"""
    server = WebUIServer(mock_agent, host="localhost", port=8765)
    return server


@pytest.fixture
def test_client(test_server):
    """Test client for HTTP requests"""
    return TestClient(test_server.app)


def test_health_endpoint(test_client):
    """Test /health endpoint"""
    response = test_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_root_serves_html(test_client):
    """Test / serves index.html"""
    response = test_client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_websocket_connection(test_server):
    """Test WebSocket connection"""
    with TestClient(test_server.app) as client:
        with client.websocket_connect("/ws") as websocket:
            data = websocket.receive_json()
            assert data["type"] == "connected"


@pytest.mark.asyncio
async def test_websocket_message_routing(test_server, mock_agent):
    """Test message routing through WebSocket"""
    # TODO: Implement test
    pass


@pytest.mark.asyncio
async def test_multiple_connections(test_server):
    """Test multiple simultaneous WebSocket connections"""
    # TODO: Implement test
    pass
```

### Manual Test Checklist

#### WebSocket Connection
- [ ] Page loads successfully
- [ ] WebSocket connects automatically
- [ ] Connection status shows "Connected"
- [ ] Reconnects after network interruption
- [ ] Multiple browser windows work

#### Message Flow
- [ ] User can type message
- [ ] Send button works
- [ ] Enter key sends message
- [ ] User message appears immediately
- [ ] Assistant response starts streaming
- [ ] Streaming is smooth (no lag)

#### Markdown Rendering
- [ ] Plain text renders correctly
- [ ] **Bold**, *italic*, `code` work
- [ ] Headers (H1, H2, H3) render
- [ ] Lists (ordered, unordered) render
- [ ] Code blocks have syntax highlighting
- [ ] Links are clickable
- [ ] No flashing during streaming

#### Tool Calls
- [ ] Tool call panel appears
- [ ] Tool name displayed correctly
- [ ] Input JSON is pretty-printed
- [ ] Input JSON has syntax highlighting
- [ ] Output appears after execution
- [ ] Panel is collapsible
- [ ] Expand/collapse works smoothly

#### Usage Stats
- [ ] Stats appear after response
- [ ] Duration displayed correctly
- [ ] Cost displayed correctly
- [ ] Cumulative cost tracks correctly
- [ ] Warnings show when needed

#### Responsiveness
- [ ] Desktop (1920x1080) looks good
- [ ] Laptop (1440x900) looks good
- [ ] Tablet (768x1024) looks good
- [ ] Mobile (375x667) usable
- [ ] Scrolling works smoothly

#### Browser Compatibility
- [ ] Chrome/Edge works
- [ ] Firefox works
- [ ] Safari works

---

## Summary

**Total Estimated Effort**: 15-20 hours

**Implementation Order**:
1. Backend foundation (3 hours)
2. Frontend core (4 hours)
3. Streaming markdown (5 hours)
4. Tool call display (3 hours)
5. Polish & features (3 hours)
6. Testing & docs (2 hours)

**Key Technical Decisions**:
- **Backend**: FastAPI + WebSockets (bidirectional, real-time)
- **Frontend**: Vanilla JavaScript (no React complexity)
- **Markdown**: Buffered rendering with marked.js (simplicity > perfection)
- **JSON**: Regex-based highlighting (lightweight, no dependencies)
- **Code**: Prism.js (mature, well-supported)

**Success Metrics**:
- Web UI is fully functional
- Streaming works smoothly
- Tool calls are visible and clear
- No regressions in CLI
- Tests pass
- Documentation complete

---

**Status**: Ready for implementation 🚀
