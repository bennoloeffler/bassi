"""
Web server V3 - Built on Claude Agent SDK.

This module provides the FastAPI web server that connects the web UI
to BassiAgentSession (which wraps ClaudeSDKClient from claude-agent-sdk).

Key differences from V2 web_server.py:
- Uses BassiAgentSession instead of BassiAgent
- Uses message_converter to transform Agent SDK messages
- Simpler architecture (no custom event system needed)
"""

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from bassi.core_v3.agent_session import BassiAgentSession, SessionConfig
from bassi.core_v3.message_converter import convert_message_to_websocket
from bassi.core_v3.interactive_questions import InteractiveQuestionService
from bassi.core_v3.tools import create_bassi_tools

logger = logging.getLogger(__name__)


class WebUIServerV3:
    """
    Web UI server using FastAPI and Agent SDK.

    Each WebSocket connection gets its own BassiAgentSession instance,
    ensuring complete isolation between conversations.
    """

    def __init__(
        self,
        session_factory: Callable[[InteractiveQuestionService], BassiAgentSession],
        host: str = "localhost",
        port: int = 8765,
    ):
        """
        Initialize web server.

        Args:
            session_factory: Factory function to create BassiAgentSession instances
                           Takes InteractiveQuestionService as parameter
            host: Server hostname
            port: Server port
        """
        self.session_factory = session_factory
        self.host = host
        self.port = port
        self.app = FastAPI(title="Bassi Web UI V3")

        # Track active WebSocket connections
        self.active_connections: list[WebSocket] = []
        # connection_id -> BassiAgentSession
        self.active_sessions: dict[str, BassiAgentSession] = {}
        # connection_id -> InteractiveQuestionService
        self.question_services: dict[str, InteractiveQuestionService] = {}

        self._setup_routes()

    def _setup_routes(self):
        """Set up FastAPI routes"""

        # Add cache-control middleware for development (enables browser hot reload)
        @self.app.middleware("http")
        async def add_cache_headers(request, call_next):
            response = await call_next(request)
            # Disable caching for static files and HTML in development
            if (
                request.url.path.startswith("/static/")
                or request.url.path == "/"
            ):
                response.headers["Cache-Control"] = (
                    "no-cache, no-store, must-revalidate"
                )
                response.headers["Pragma"] = "no-cache"
                response.headers["Expires"] = "0"
            return response

        # Serve static files (HTML, CSS, JS)
        static_dir = Path(__file__).parent.parent / "static"
        if static_dir.exists():
            self.app.mount("/static", StaticFiles(directory=static_dir), name="static")

            # Serve index.html at root
            @self.app.get("/", response_class=HTMLResponse)
            async def root():
                with open(static_dir / "index.html") as f:
                    return HTMLResponse(content=f.read())

        # Health check
        @self.app.get("/health")
        async def health():
            return JSONResponse({
                "status": "ok",
                "service": "bassi-web-ui-v3",
                "active_sessions": len(self.active_sessions),
            })

        # WebSocket endpoint
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await self._handle_websocket(websocket)

    async def _handle_websocket(self, websocket: WebSocket):
        """Handle WebSocket connection with isolated agent session"""
        # Generate unique connection ID
        connection_id = str(uuid.uuid4())

        # Create interactive question service for this session
        question_service = InteractiveQuestionService()
        question_service.websocket = websocket
        self.question_services[connection_id] = question_service

        # Create dedicated agent session with question service
        session = self.session_factory(question_service)
        self.active_sessions[connection_id] = session

        await websocket.accept()
        self.active_connections.append(websocket)

        logger.info(
            f"New session: {connection_id[:8]}... | Total connections: {len(self.active_connections)}"
        )

        try:
            # Connect agent session
            await session.connect()

            # Send welcome message with session ID
            await websocket.send_json({
                "type": "connected",
                "session_id": connection_id,
                "message": "Connected to Bassi V3 (Agent SDK)",
            })

            # Send discovery info (available tools, commands, skills, MCP servers)
            from bassi.core_v3.discovery import BassiDiscovery
            discovery = BassiDiscovery(Path(__file__).parent.parent.parent)
            discovery_summary = discovery.get_summary()

            # Format as a practical, well-designed welcome message
            mcp_servers = discovery_summary.get("mcp_servers", {})
            project_cmds = discovery_summary["slash_commands"]["project"]
            personal_cmds = discovery_summary["slash_commands"]["personal"]
            skills = discovery_summary.get("skills", [])

            # MCP server short descriptions
            mcp_info = {
                "ms365": "📧 Email, Calendar, Contacts",
                "playwright": "🌐 Web Automation",
                "postgresql": "🗄️ CRM Database"
            }

            welcome_html = f"""<div class="startup-welcome">
<div class="startup-header">
<h2>Ready to assist</h2>
<p class="startup-subtitle">All capabilities loaded and available</p>
</div>

<div class="startup-grid">
<div class="startup-section">
<h3>📡 MCP Servers <span class="count">({len(mcp_servers)})</span></h3>
<div class="capability-list">
{"".join([f'<div class="capability-item"><span class="cap-name">{name}</span><span class="cap-desc">{mcp_info.get(name, "MCP Server")}</span></div>' for name in mcp_servers.keys()])}
</div>
</div>

<div class="startup-section">
<h3>💻 Commands <span class="count">({len(project_cmds) + len(personal_cmds)})</span></h3>
<div class="capability-list">
{"".join([f'<div class="capability-item"><code class="cap-name">{cmd["name"]}</code></div>' for cmd in project_cmds + personal_cmds])}
</div>
</div>

<div class="startup-section">
<h3>🎯 Skills <span class="count">({len(skills)})</span></h3>
<div class="capability-list capability-compact">
{"".join([f'<span class="skill-tag">{s["name"]}</span>' for s in skills[:8]])}
</div>
</div>
</div>

<div class="startup-footer">
<p>Type <code>/help</code> for detailed documentation and examples</p>
</div>
</div>"""

            await websocket.send_json({
                "type": "system_message",
                "content": welcome_html
            })

            # Listen for messages
            # We need to handle messages concurrently so we don't block
            # when waiting for tool responses (like AskUserQuestion)
            async def message_receiver():
                """Continuously receive and process WebSocket messages"""
                try:
                    while True:
                        data = await websocket.receive_json()
                        # Process message without awaiting to avoid blocking
                        asyncio.create_task(
                            self._process_message(websocket, data, connection_id)
                        )
                except WebSocketDisconnect:
                    pass
                except Exception as e:
                    logger.error(f"Message receiver error: {e}", exc_info=True)

            # Start message receiver as background task and keep connection alive
            receiver_task = asyncio.create_task(message_receiver())
            await receiver_task

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected: {connection_id[:8]}...")
        except Exception as e:
            logger.error(f"WebSocket error: {e}", exc_info=True)
        finally:
            # Cancel any pending questions
            if connection_id in self.question_services:
                question_service = self.question_services[connection_id]
                question_service.cancel_all()
                del self.question_services[connection_id]

            # Clean up session
            if connection_id in self.active_sessions:
                try:
                    session = self.active_sessions[connection_id]
                    await session.disconnect()
                except Exception as e:
                    logger.error(f"Error disconnecting session: {e}")
                del self.active_sessions[connection_id]

            if websocket in self.active_connections:
                self.active_connections.remove(websocket)

            logger.info(
                f"Session ended: {connection_id[:8]}... | Remaining: {len(self.active_connections)}"
            )

    async def _process_message(
        self, websocket: WebSocket, data: dict[str, Any], connection_id: str
    ):
        """Process incoming message from client"""
        msg_type = data.get("type")

        # Get session
        session = self.active_sessions.get(connection_id)
        if not session:
            return

        if msg_type == "user_message":
            # User sent a chat message
            content = data.get("content", "")

            # IMPORTANT: Echo user's message back so it appears in conversation history
            await websocket.send_json({
                "type": "user_message_echo",
                "content": content,
            })

            # Handle /help command - show available capabilities
            if content.strip().lower() in ["/help", "help", "/?"]:
                from bassi.core_v3.discovery import BassiDiscovery
                discovery = BassiDiscovery(Path(__file__).parent.parent.parent)
                discovery_summary = discovery.get_summary()

                # Format help message with better structure
                mcp_servers = discovery_summary.get("mcp_servers", {})
                project_cmds = discovery_summary["slash_commands"]["project"]
                personal_cmds = discovery_summary["slash_commands"]["personal"]
                skills = discovery_summary.get("skills", [])

                help_message = """<div class="help-container">
<h1>🎯 Bassi Help Guide</h1>

<div class="help-intro">
<p>Bassi gives you access to multiple types of capabilities. Here's what you have available and how to use them:</p>
</div>

<div class="help-section">
<h2>📚 Understanding the Different Types</h2>

<div class="concept-box">
<h3>🔌 MCP Servers (Model Context Protocol)</h3>
<p><strong>What:</strong> External services that provide specialized tools and data access</p>
<p><strong>When:</strong> Database queries, email access, web automation, external APIs</p>
<p><strong>How:</strong> Just ask me naturally - I'll use the right MCP tools automatically</p>
<p><strong>Example:</strong> <em>"Show me all companies in the PostgreSQL database"</em> → I use the <code>postgresql</code> MCP server</p>
</div>

<div class="concept-box">
<h3>💻 Slash Commands</h3>
<p><strong>What:</strong> Pre-defined workflows that extract data and perform complex tasks</p>
<p><strong>When:</strong> Structured data entry, multi-step processes, guided workflows</p>
<p><strong>How:</strong> Type the command name starting with <code>/</code></p>
<p><strong>Example:</strong> <code>/crm Add company TechStart GmbH in Berlin</code> → Extracts data and creates CRM records</p>
</div>

<div class="concept-box">
<h3>🎯 Skills</h3>
<p><strong>What:</strong> Knowledge libraries with schemas, workflows, and domain expertise</p>
<p><strong>When:</strong> Working with databases, documents, specialized domains</p>
<p><strong>How:</strong> I load them automatically when needed - you don't call them directly</p>
<p><strong>Example:</strong> When you use <code>/crm</code>, I automatically load the <code>crm-db</code> skill for database schema knowledge</p>
</div>

<div class="concept-box">
<h3>🤖 Agents (Sub-agents)</h3>
<p><strong>What:</strong> Specialized AI assistants for specific complex tasks</p>
<p><strong>When:</strong> Code review, testing, debugging, long-running analysis</p>
<p><strong>How:</strong> I can spawn them as needed for specialized work</p>
<p><strong>Example:</strong> <em>"Review this code for security issues"</em> → I might spawn a security-auditor agent</p>
</div>
</div>

<div class="help-section">
<h2>📡 MCP Servers ({len(mcp_servers)})</h2>
"""

                # Add each MCP server in a nice box
                mcp_descriptions = {
                    "ms365": {
                        "desc": "Microsoft 365 integration - emails, calendar, contacts",
                        "tools": ["read emails", "send emails", "schedule meetings", "list contacts"],
                        "example": '"Check my emails from today"'
                    },
                    "playwright": {
                        "desc": "Web browser automation and testing",
                        "tools": ["navigate websites", "take screenshots", "fill forms", "click elements"],
                        "example": '"Take a screenshot of example.com"'
                    },
                    "postgresql": {
                        "desc": "PostgreSQL database access for CRM data",
                        "tools": ["query database", "list tables", "insert records", "update records"],
                        "example": '"Show all companies in the database"'
                    }
                }

                for name, config in mcp_servers.items():
                    desc_info = mcp_descriptions.get(name, {"desc": "MCP server", "tools": [], "example": ""})
                    help_message += f"""
<div class="mcp-box">
<h3 class="mcp-name">{name}</h3>
<p class="mcp-desc">{desc_info['desc']}</p>
<div class="mcp-tools">
<strong>Available tools:</strong> {', '.join(desc_info['tools']) if desc_info['tools'] else 'Multiple tools available'}
</div>
<div class="mcp-example">
<strong>Example:</strong> <em>{desc_info['example'] if desc_info['example'] else f'Use the {name} server'}</em>
</div>
</div>
"""

                help_message += """
</div>

<div class="help-section">
<h2>💻 Slash Commands ({len(project_cmds) + len(personal_cmds)})</h2>
"""

                # Command descriptions
                cmd_descriptions = {
                    "/crm": {
                        "desc": "Extract CRM data from text and manage database records",
                        "example": '<code>/crm New company: TechStart GmbH, Berlin, Software Development industry</code>'
                    },
                    "/epct": {
                        "desc": "Personal command for EPCT-related tasks",
                        "example": '<code>/epct [your command]</code>'
                    },
                    "/crm-analyse-customer": {
                        "desc": "Analyze customer data and generate insights",
                        "example": '<code>/crm-analyse-customer CompanyName</code>'
                    }
                }

                if project_cmds:
                    help_message += "<h3>Project Commands:</h3>"
                    for cmd in project_cmds:
                        cmd_info = cmd_descriptions.get(cmd['name'], {"desc": "Command", "example": cmd['name']})
                        help_message += f"""
<div class="command-box">
<h4 class="command-name">{cmd['name']}</h4>
<p class="command-desc">{cmd_info['desc']}</p>
<div class="command-example">
<strong>Example:</strong> {cmd_info['example']}
</div>
</div>
"""

                if personal_cmds:
                    help_message += "<h3>Personal Commands:</h3>"
                    for cmd in personal_cmds:
                        cmd_info = cmd_descriptions.get(cmd['name'], {"desc": "Personal command", "example": cmd['name']})
                        help_message += f"""
<div class="command-box">
<h4 class="command-name">{cmd['name']}</h4>
<p class="command-desc">{cmd_info['desc']}</p>
<div class="command-example">
<strong>Example:</strong> {cmd_info['example']}
</div>
</div>
"""

                help_message += f"""
</div>

<div class="help-section">
<h2>🎯 Skills ({len(skills)})</h2>
<p class="skills-intro">Skills are automatically loaded when needed - you don't need to call them directly!</p>
"""

                # Skill descriptions
                skill_descriptions = {
                    "crm-db": {
                        "desc": "CRM database schema and query knowledge",
                        "used_by": "Automatically loaded by /crm command"
                    },
                    "xlsx": {
                        "desc": "Excel spreadsheet creation and editing",
                        "used_by": "When working with .xlsx files"
                    },
                    "pdf": {
                        "desc": "PDF document creation and manipulation",
                        "used_by": "When working with .pdf files"
                    },
                    "docx": {
                        "desc": "Word document creation and editing",
                        "used_by": "When working with .docx files"
                    },
                    "pptx": {
                        "desc": "PowerPoint presentation creation",
                        "used_by": "When working with .pptx files"
                    }
                }

                for skill in skills:
                    skill_info = skill_descriptions.get(skill['name'], {"desc": "Skill", "used_by": "As needed"})
                    help_message += f"""
<div class="skill-box">
<h4 class="skill-name">{skill['name']}</h4>
<p class="skill-desc">{skill_info['desc']}</p>
<div class="skill-usage">
<strong>Automatically used:</strong> {skill_info['used_by']}
</div>
</div>
"""

                help_message += """
</div>

<div class="help-section">
<h2>💡 Quick Start Examples</h2>

<div class="example-box">
<h3>Database Operations (MCP + Skill + Command)</h3>
<p><strong>You type:</strong> <code>/crm New contact: Maria Schmidt, maria@tech.de, CTO at TechStart GmbH</code></p>
<p><strong>What happens:</strong></p>
<ol>
<li>The <code>/crm</code> slash command activates</li>
<li>It loads the <code>crm-db</code> skill for database schema</li>
<li>It uses the <code>postgresql</code> MCP server to insert data</li>
<li>You get confirmation with the new record ID</li>
</ol>
</div>

<div class="example-box">
<h3>Email Check (Pure MCP)</h3>
<p><strong>You type:</strong> <em>"Check my emails from today"</em></p>
<p><strong>What happens:</strong></p>
<ol>
<li>I use the <code>ms365</code> MCP server directly</li>
<li>Fetch today's emails from your account</li>
<li>Show you a summary</li>
</ol>
</div>

<div class="example-box">
<h3>Document Creation (Skill)</h3>
<p><strong>You type:</strong> <em>"Create a PDF report with Q4 sales data"</em></p>
<p><strong>What happens:</strong></p>
<ol>
<li>I automatically load the <code>pdf</code> skill</li>
<li>Generate the document structure</li>
<li>Save it to a file</li>
</ol>
</div>
</div>

<div class="help-footer">
<h3>🚀 Pro Tips</h3>
<ul>
<li>I have full access to all capabilities - no permission prompts needed</li>
<li>Mix and match: Commands can use MCPs, MCPs can work with Skills</li>
<li>Just ask naturally - I'll figure out which tools to use</li>
<li>Type <code>/help</code> anytime to see this again</li>
</ul>
</div>

</div>"""

                await websocket.send_json({
                    "type": "assistant_message",
                    "content": help_message,
                })

                # Don't process further - help is handled
                return  # Exit this message processing

            # Track message ID counter for web UI
            message_counter = 0
            text_block_counter = 0
            tool_counter = 0
            current_text_block_id = None
            tool_id_map = {}  # tool_use_id -> display_id

            print(f"🔄 Starting query...", flush=True)

            try:
                # Stream response from agent session
                async for message in session.query(content):
                    msg_type_name = type(message).__name__
                    print(f"📦 Got message: {msg_type_name}", flush=True)

                    # Debug content blocks
                    if hasattr(message, 'content'):
                        if isinstance(message.content, list):
                            blocks = [type(b).__name__ for b in message.content]
                            print(f"   Content blocks: {blocks}", flush=True)
                        else:
                            print(f"   Content: {type(message.content).__name__}", flush=True)

                    # Skip UserMessage ONLY if it's plain text (user's input echo)
                    # BUT keep UserMessage with ToolResultBlock (tool results from SDK)
                    from claude_agent_sdk.types import UserMessage, ToolResultBlock
                    if isinstance(message, UserMessage):
                        # Check if this UserMessage contains ToolResultBlock
                        has_tool_result = False
                        if hasattr(message, 'content') and isinstance(message.content, list):
                            has_tool_result = any(isinstance(block, ToolResultBlock) for block in message.content)

                        if not has_tool_result:
                            # Plain user message - skip it (we already showed it in UI)
                            print("   ⏩ Skipping plain UserMessage", flush=True)
                            continue
                        else:
                            # UserMessage with tool results - keep it!
                            print("   ✅ UserMessage contains ToolResultBlock - processing", flush=True)

                    # Convert Agent SDK message to web UI events
                    events = convert_message_to_websocket(message)
                    logger.info(f"   📤 Generated {len(events)} events: {[e.get('type') for e in events]}")

                    # Enhance events with IDs for web UI
                    for event in events:
                        event_type = event.get("type")

                        if event_type == "text_delta":
                            # Create or reuse text block ID
                            if current_text_block_id is None:
                                current_text_block_id = f"msg-{message_counter}-text-{text_block_counter}"
                                text_block_counter += 1
                            event["id"] = current_text_block_id

                        elif event_type == "tool_start":
                            # Create tool block ID
                            tool_use_id = event.get("id")  # Agent SDK's tool_use_id
                            display_id = f"msg-{message_counter}-tool-{tool_counter}"
                            tool_counter += 1
                            tool_id_map[tool_use_id] = display_id
                            event["id"] = display_id
                            logger.info(f"🛠️ tool_start - tool_use_id: {tool_use_id} → display_id: {display_id}")
                            # Reset text block so next text starts new block
                            current_text_block_id = None

                        elif event_type == "tool_end":
                            # Map Agent SDK tool_use_id to our display ID
                            tool_use_id = event.get("id")
                            logger.info(f"🔧 tool_end - tool_use_id: {tool_use_id}, tool_id_map: {tool_id_map}")
                            display_id = tool_id_map.get(tool_use_id)
                            if display_id:
                                event["id"] = display_id
                                logger.info(f"✅ Mapped to display_id: {display_id}")
                            else:
                                logger.warning(f"❌ No display ID for tool_use_id: {tool_use_id}")

                        elif event_type == "thinking":
                            # Create thinking block ID
                            thinking_id = f"msg-{message_counter}-thinking-0"
                            event["id"] = thinking_id

                        # Send event to client
                        await websocket.send_json(event)

            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)
                await websocket.send_json({
                    "type": "error",
                    "message": str(e),
                })

        elif msg_type == "interrupt":
            # User requested to interrupt agent execution
            logger.info("Interrupt request received")
            try:
                await session.interrupt()
                await websocket.send_json({
                    "type": "interrupted",
                    "message": "Agent execution stopped",
                })
                logger.info("Agent interrupted successfully")
            except Exception as e:
                logger.error(f"Failed to interrupt agent: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": f"Failed to interrupt: {str(e)}",
                })

        elif msg_type == "get_server_info":
            # User requested server info (commands, MCP tools, agents, etc.)
            logger.info("Server info request received")
            try:
                info = await session.get_server_info()
                await websocket.send_json({
                    "type": "server_info",
                    "data": info,
                })
                logger.info("Server info sent successfully")
            except Exception as e:
                logger.error(f"Failed to get server info: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": f"Failed to get server info: {str(e)}",
                })

        elif msg_type == "answer":
            # User answered an interactive question
            question_id = data.get("question_id")
            answers = data.get("answers", {})
            logger.info(f"Question answer received: {question_id}")
            logger.info(f"Answers: {answers}")

            # Get the question service for this connection
            question_service = self.question_services.get(connection_id)
            if question_service:
                question_service.submit_answer(question_id, answers)
                logger.info(f"Answer submitted to question service")
            else:
                logger.error(f"No question service found for connection {connection_id}")

        else:
            logger.warning(f"Unknown message type: {msg_type}")

    async def run(self, reload: bool = False):
        """
        Run the web server.

        Args:
            reload: Enable hot reload for development
        """
        import uvicorn

        logger.info(f"Starting Bassi Web UI V3 on http://{self.host}:{self.port}")

        if reload:
            logger.info("🔥 Hot reload enabled - server will restart on file changes")
            logger.info("   Watching: bassi/core_v3/**/*.py")
            logger.info("   Watching: bassi/static/*.{html,css,js}")
            logger.info("")
            logger.info("💡 Tip: Edit files and they'll auto-reload in ~2-3 seconds")
            logger.info("")

        config = uvicorn.Config(
            app=self.app,
            host=self.host,
            port=self.port,
            log_level="info",
            reload=reload,
            reload_dirs=[str(Path(__file__).parent.parent)] if reload else None,
        )
        server = uvicorn.Server(config)
        await server.serve()


def create_default_session_factory() -> Callable[[InteractiveQuestionService], BassiAgentSession]:
    """
    Create default session factory for web UI.

    Returns:
        Factory function that creates BassiAgentSession instances
        with interactive question support
    """

    def factory(question_service: InteractiveQuestionService):
        # Load MCP servers from .mcp.json in project root
        mcp_config_path = Path(__file__).parent.parent.parent / ".mcp.json"

        # Always load as dict so we can add our interactive tools
        import json
        mcp_servers = {}

        if mcp_config_path.exists():
            logger.info(f"Loading MCP servers from: {mcp_config_path}")
            try:
                with open(mcp_config_path) as f:
                    mcp_servers = json.load(f)
                    # The .mcp.json might have mcpServers wrapper
                    if "mcpServers" in mcp_servers:
                        mcp_servers = mcp_servers["mcpServers"]
            except Exception as e:
                logger.error(f"Error loading MCP config: {e}")
                mcp_servers = {}
        else:
            logger.warning(f"MCP config not found at: {mcp_config_path}")

        # Create Bassi tools (including AskUserQuestion)
        from claude_agent_sdk import create_sdk_mcp_server

        bassi_tools = create_bassi_tools(question_service)
        bassi_mcp_server = create_sdk_mcp_server(
            name="bassi-interactive",
            version="1.0.0",
            tools=bassi_tools
        )

        # Add our interactive tools server to the dict
        mcp_servers["bassi-interactive"] = bassi_mcp_server

        config = SessionConfig(
            allowed_tools=["*"],  # Allow ALL tools including MCP, Skills, SlashCommands
            system_prompt=None,  # Use default Claude Code prompt
            permission_mode="bypassPermissions",  # Bypass all permission checks
            mcp_servers=mcp_servers,
            setting_sources=["project", "local"],  # Enable skills from project and local
        )
        return BassiAgentSession(config)

    return factory


async def start_web_server_v3(
    session_factory: Callable[[InteractiveQuestionService], BassiAgentSession] | None = None,
    host: str = "localhost",
    port: int = 8765,
    reload: bool = False,
):
    """
    Start the web UI server V3.

    Args:
        session_factory: Factory to create BassiAgentSession instances.
                        Takes InteractiveQuestionService as parameter.
                        If None, uses default factory.
        host: Server hostname
        port: Server port
        reload: Enable hot reload for development
    """
    if session_factory is None:
        session_factory = create_default_session_factory()

    server = WebUIServerV3(session_factory, host, port)
    await server.run(reload=reload)
