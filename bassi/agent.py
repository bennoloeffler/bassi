"""
Agent implementation for bassi using Claude Agent SDK

Complete rewrite to use Claude Agent SDK with MCP servers.
Features:
- Async streaming responses
- SDK MCP servers (in-process)
- External MCP servers (via .mcp.json)
- Status updates during operations
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, AsyncIterator

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from bassi.mcp_servers import (
    create_bash_mcp_server,
    create_web_search_mcp_server,
)
from bassi.mcp_servers.task_automation_server import (
    create_task_automation_server,
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,  # Changed from DEBUG to INFO for production
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("bassi_debug.log"),
    ],
)
logger = logging.getLogger(__name__)

# Enable DEBUG logging via environment variable
if os.getenv("BASSI_DEBUG"):
    logger.setLevel(logging.DEBUG)
    logging.getLogger().setLevel(logging.DEBUG)


class BassiAgent:
    """
    Personal Assistant Agent using Claude Agent SDK

    Interface:
    - chat(message: str) -> AsyncIterator: Stream response in real-time
    - reset() -> None: Reset conversation (restart client)
    - toggle_verbose() -> bool: Toggle verbose mode
    """

    SYSTEM_PROMPT = """
You are bassi, Benno's personal assistant. You help with tasks by:
1. Executing bash commands to solve problems
2. Searching the web for current information
3. Managing emails and calendar (Microsoft 365)
4. Automating browser interactions (Playwright)
5. Planning and executing multi-step tasks
6. Providing clear, helpful responses

IMPORTANT: File Organization - Unless explicitly told otherwise, use these folders:
- Read user-provided files (images, PDFs, documents) from: _DATA_FROM_USER/
- Save reusable scripts you create to: _SCRIPTS_FROM_AGENT/
- Save output and results (analysis, reports, generated data) to: _RESULTS_FROM_AGENT/
- Save files downloaded from web to: _DOWNLOADS_FROM_AGENT/

When solving tasks:
- Break down complex tasks into steps
- Use bash commands for file operations (fd, rg, find, grep, etc.)
- Use web search for current information, facts, and real-time data
- Use MS365 tools for email and calendar management
- Use Playwright tools for browser automation (navigate, click, type, etc.)
- Be proactive and thorough
- Explain what you're doing

IMPORTANT: Microsoft 365 Authentication:
- BEFORE using ANY MS365 tools (email, calendar), you MUST ensure authentication
- First, call mcp__ms365__verify-login to check if already authenticated
- If NOT authenticated or token is invalid, call mcp__ms365__login
- The login tool will:
  * Check for cached tokens first (automatic)
  * If no valid token, provide a URL and code for browser authentication
  * Wait for user to complete authentication in browser
- After successful login, proceed with MS365 operations
- Token caching is automatic - subsequent sessions will use cached credentials

IMPORTANT: You must use these specific tools:
- mcp__bash__execute: Execute shell commands (use fd/rg for fast file search)
- mcp__web__search: Search the web for current information
- mcp__task_automation__execute_python: Execute Python code for automation tasks (image processing, file organization, data transformation)
- mcp__ms365__login: Authenticate to Microsoft 365 (checks cache first, then browser auth)
- mcp__ms365__verify-login: Check authentication status
- mcp__ms365__list-mail-messages: Read emails from Outlook
- mcp__ms365__send-mail: Send emails via Outlook
- mcp__ms365__list-calendar-events: View calendar events
- mcp__ms365__create-calendar-event: Create calendar events
- mcp__playwright__browser_navigate: Navigate to URL in browser
- mcp__playwright__browser_click: Click elements in browser
- mcp__playwright__browser_type: Type text in browser
- mcp__playwright__browser_screenshot: Take screenshots

Do NOT use the built-in Bash or other tools - only use the mcp__ prefixed tools.

Available Unix tools via mcp__bash__execute:
- fd: Fast file search (fd pattern)
- rg: Fast content search (rg pattern)
- find: Classic file search (find . -name pattern)
- grep: Classic content search (grep -r pattern)
"""

    def __init__(
        self, status_callback=None, resume_session_id: str | None = None
    ) -> None:
        """
        Initialize the Bassi Agent

        Args:
            status_callback: Optional callback for status updates
            resume_session_id: Optional session ID to resume from
        """
        # Log API configuration for debugging
        api_base_url = os.getenv(
            "ANTHROPIC_BASE_URL", "https://api.anthropic.com"
        )
        api_key_preview = (
            os.getenv("ANTHROPIC_API_KEY", "not-set")[:10] + "..."
        )
        logger.info(f"🌐 API Endpoint: {api_base_url}")
        logger.info(f"🔑 API Key: {api_key_preview}")

        # Create SDK MCP servers (in-process, no subprocess overhead)
        self.sdk_mcp_servers = {
            "bash": create_bash_mcp_server(),
            "web": create_web_search_mcp_server(),
            "task_automation": create_task_automation_server(),
        }

        # Load external MCP servers from .mcp.json
        self.external_mcp_servers = self._load_external_mcp_config()

        # Combine all MCP servers
        all_mcp_servers = {
            **self.sdk_mcp_servers,
            **self.external_mcp_servers,
        }

        # Collect all allowed tools
        allowed_tools = [
            "mcp__bash__execute",
            "mcp__web__search",
        ]

        # Add MS365 tools if configured
        if "ms365" in self.external_mcp_servers:
            ms365_tools = [
                "mcp__ms365__login",
                "mcp__ms365__verify-login",
                "mcp__ms365__list-mail-messages",
                "mcp__ms365__send-mail",
                "mcp__ms365__list-calendar-events",
                "mcp__ms365__create-calendar-event",
            ]
            allowed_tools.extend(ms365_tools)
            logger.info(
                f"📧 MS365 MCP server configured with {len(ms365_tools)} tools"
            )

        # Add Playwright tools if configured
        if "playwright" in self.external_mcp_servers:
            playwright_tools = [
                "mcp__playwright__browser_navigate",
                "mcp__playwright__browser_screenshot",
                "mcp__playwright__browser_click",
                "mcp__playwright__browser_type",
                "mcp__playwright__browser_select",
                "mcp__playwright__browser_hover",
                "mcp__playwright__browser_evaluate",
                "mcp__playwright__browser_install",
            ]
            allowed_tools.extend(playwright_tools)
            logger.info(
                f"🎭 Playwright MCP server configured with {len(playwright_tools)} tools"
            )

        # Agent options
        self.options = ClaudeAgentOptions(
            mcp_servers=all_mcp_servers,
            system_prompt=self.SYSTEM_PROMPT,
            allowed_tools=allowed_tools,
            permission_mode="bypassPermissions",  # Fully autonomous - no permission prompts
            resume=resume_session_id,  # Resume previous session if provided
            include_partial_messages=True,  # Enable streaming at token level
        )

        self.status_callback = status_callback
        self.verbose = True
        self.console = Console(force_terminal=True)
        self.client: ClaudeSDKClient | None = None
        # Session ID - will be set by SDK on first interaction or from resume
        # SDK uses UUID format like "ae7bbada-f363-4f81-9df3-b24f3dea8f97"
        self.session_id: str | None = resume_session_id
        self.context_file = Path.cwd() / ".bassi_context.json"

        # Track cumulative usage across session
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cache_creation_tokens = 0
        self.total_cache_read_tokens = 0
        self.total_cost_usd = 0.0

        # Streaming state for smooth text rendering
        self._streaming_response = False
        self._last_text_length = 0
        self._accumulated_text = ""

        # Context limits (Claude Sonnet 4.5 has 200K token window)
        self.context_window_size = 200000  # 200K tokens
        self.compaction_threshold = 150000  # Compact at 75% of limit

        # Display available MCP servers and tools
        self._display_available_tools()

    def _display_available_tools(self) -> None:
        """Display available MCP servers and tools at startup (fully dynamic)"""
        try:
            self.console.print()
            self.console.print(
                Panel(
                    "[bold cyan]🔧 Available MCP Servers & Tools[/bold cyan]",
                    border_style="cyan",
                )
            )

            # SDK MCP Servers (dynamically discovered)
            if self.sdk_mcp_servers:
                self.console.print(
                    "\n[bold green]📦 SDK MCP Servers (in-process):[/bold green]"
                )
                for server_name in self.sdk_mcp_servers:
                    self.console.print(f"  • [cyan]{server_name}[/cyan]")

            # External MCP Servers (from .mcp.json)
            if self.external_mcp_servers:
                self.console.print(
                    "\n[bold magenta]🌐 External MCP Servers:[/bold magenta]"
                )
                for server_name, config in self.external_mcp_servers.items():
                    command = config.get("command", "")
                    args = config.get("args", [])
                    self.console.print(
                        f"  • [magenta]{server_name}[/magenta]"
                    )
                    self.console.print(
                        f"    [dim]Command: {command} {' '.join(args)}[/dim]"
                    )

            # Available Tools Summary (fully dynamic)
            total_tools = (
                len(self.options.allowed_tools)
                if self.options.allowed_tools
                else 0
            )
            self.console.print(
                f"\n[bold yellow]📋 Total Available Tools:[/bold yellow] {total_tools}"
            )

            # Dynamically group tools by server
            # Tool names follow pattern: mcp__<server_name>__<tool_name>
            tools_by_server = {}
            for tool in self.options.allowed_tools or []:
                parts = tool.split("__")
                if len(parts) >= 3 and parts[0] == "mcp":
                    server_name = parts[1]
                    tool_name = "__".join(parts[2:])
                    if server_name not in tools_by_server:
                        tools_by_server[server_name] = []
                    tools_by_server[server_name].append(tool_name)

            # Display tools grouped by server
            for server_name, tools in sorted(tools_by_server.items()):
                # Use different colors for SDK vs external servers
                if server_name in self.sdk_mcp_servers:
                    color = "cyan"
                else:
                    color = "magenta"

                # Capitalize server name for display
                display_name = server_name.replace("_", " ").title()
                self.console.print(
                    f"  • [{color}]{display_name}[/{color}]: {len(tools)} tool(s)"
                )

                # Show first 3 tools as preview
                if tools:
                    preview_tools = tools[:3]
                    preview = ", ".join(preview_tools)
                    if len(tools) > 3:
                        preview += "..."
                    self.console.print(f"    [dim]→ {preview}[/dim]")

            self.console.print()

        except Exception as e:
            logger.warning(f"Error displaying available tools: {e}")

    def _load_external_mcp_config(self) -> dict:
        """
        Load external MCP server configuration from .mcp.json

        Returns:
            Dict mapping server name to MCP server config
        """
        mcp_config_file = Path.cwd() / ".mcp.json"

        if not mcp_config_file.exists():
            logger.info(
                "No .mcp.json file found - skipping external MCP servers"
            )
            return {}

        try:
            with open(mcp_config_file) as f:
                config = json.load(f)

            mcp_servers_config = config.get("mcpServers", {})

            if not mcp_servers_config:
                logger.info("No MCP servers configured in .mcp.json")
                return {}

            # Load environment variables for substitution
            from dotenv import load_dotenv

            load_dotenv()

            # Convert .mcp.json format to Claude SDK format
            external_servers = {}

            for server_name, server_config in mcp_servers_config.items():
                command = server_config.get("command")
                args = server_config.get("args", [])
                env = server_config.get("env", {})

                # Substitute environment variables in env values
                resolved_env = {}
                for key, value in env.items():
                    if (
                        isinstance(value, str)
                        and value.startswith("${")
                        and value.endswith("}")
                    ):
                        # Extract variable name: ${VAR_NAME} -> VAR_NAME
                        var_name = value[2:-1]
                        # Handle default values: ${VAR_NAME:-default}
                        if ":-" in var_name:
                            var_name, default = var_name.split(":-", 1)
                            resolved_env[key] = os.getenv(var_name, default)
                        else:
                            resolved_env[key] = os.getenv(var_name, "")
                    else:
                        resolved_env[key] = value

                # Create MCP server config in Claude SDK format
                external_servers[server_name] = {
                    "command": command,
                    "args": args,
                    "env": resolved_env,
                }

                logger.info(f"📦 Loaded external MCP server: {server_name}")
                logger.debug(f"   Command: {command}")
                logger.debug(f"   Args: {args}")
                logger.debug(f"   Env vars: {list(resolved_env.keys())}")

            return external_servers

        except Exception as e:
            logger.error(f"Error loading .mcp.json: {e}")
            logger.exception("Full traceback:")
            return {}

    async def interrupt(self) -> None:
        """Interrupt the current agent run"""
        if self.client:
            await self.client.interrupt()
            logger.info("Agent interrupted by user")
            if self.status_callback:
                self.status_callback("⚠️ Interrupted")

    def save_context(self) -> None:
        """Save current context to file"""
        try:
            import time

            context_data = {
                "session_id": self.session_id,
                "timestamp": time.time(),
                "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            self.context_file.write_text(json.dumps(context_data, indent=2))
            logger.info(f"Context saved - session_id: {self.session_id}")
        except Exception as e:
            logger.warning(f"Failed to save context: {e}")

    def load_context(self) -> dict | None:
        """Load context from file"""
        try:
            if self.context_file.exists():
                data: dict = json.loads(self.context_file.read_text())
                session_id = data.get("session_id", "unknown")
                last_updated = data.get("last_updated", "unknown")
                logger.info(
                    f"Context loaded - session_id: {session_id}, last_updated: {last_updated}"
                )
                return data
            logger.info("No previous context found")
            return None
        except Exception as e:
            logger.warning(f"Failed to load context: {e}")
            return None

    def get_context_info(self) -> dict:
        """Get context size and info"""
        # Calculate approximate current context size
        # Input tokens + cache = approximate current context
        current_context_size = (
            self.total_input_tokens
            + self.total_cache_creation_tokens
            + self.total_cache_read_tokens
        )

        # Calculate percentage of context window used
        context_percentage = (
            current_context_size / self.context_window_size
        ) * 100
        will_compact_soon = current_context_size >= self.compaction_threshold

        return {
            "current_size": current_context_size,
            "window_size": self.context_window_size,
            "percentage_used": context_percentage,
            "compaction_threshold": self.compaction_threshold,
            "will_compact_soon": will_compact_soon,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cache_creation": self.total_cache_creation_tokens,
            "total_cache_read": self.total_cache_read_tokens,
            "total_cost_usd": self.total_cost_usd,
        }

    async def chat(self, message: str) -> AsyncIterator[Any]:
        """
        Chat with the agent and stream responses

        Args:
            message: User message

        Yields:
            Messages from Claude (text, tool use, etc.)
        """
        logger.info(f"Chat starting with message: {message}")

        # Update status
        if self.status_callback:
            self.status_callback("⏳ Thinking...")

        try:
            # Create client if it doesn't exist (for conversation continuity)
            if self.client is None:
                logger.debug("Creating new ClaudeSDKClient")
                self.client = ClaudeSDKClient(options=self.options)
                await self.client.__aenter__()

            # Send the query
            # Session resumption is handled by ClaudeAgentOptions.resume
            if self.session_id:
                logger.info(f"Resuming session: {self.session_id}")
            else:
                logger.info(
                    "Starting new session (SDK will generate session_id)"
                )

            await self.client.query(message)

            # Stream responses
            async for msg in self.client.receive_response():
                # Capture session_id from ResultMessage (ALWAYS, not just in verbose mode)
                msg_class_name = type(msg).__name__
                if msg_class_name == "ResultMessage":
                    sdk_session_id = getattr(msg, "session_id", None)
                    if sdk_session_id and sdk_session_id != self.session_id:
                        logger.info(
                            f"SDK session_id captured: {sdk_session_id}"
                        )
                        self.session_id = sdk_session_id

                # Update status based on message type
                self._update_status_from_message(msg)

                # Display message if verbose
                if self.verbose:
                    self._display_message(msg)

                yield msg

            # Save context after successful completion
            self.save_context()

        except Exception as e:
            logger.exception(f"Error in chat: {e}")
            error_msg = f"Error: {str(e)}"
            self.console.print(f"[bold red]{error_msg}[/bold red]")

            if self.status_callback:
                self.status_callback("❌ Error")

            yield {"type": "error", "error": str(e)}

        finally:
            if self.status_callback:
                self.status_callback("✅ Ready")
            logger.info("Chat completed")

    def _update_status_from_message(self, msg: Any) -> None:
        """Update status bar based on message type"""
        if not self.status_callback:
            return

        try:
            msg_class_name = type(msg).__name__

            # Handle SDK message types
            if msg_class_name == "AssistantMessage":
                self.status_callback("💭 Responding...")
            elif msg_class_name == "ResultMessage":
                # Will be set to "Ready" in finally block
                pass
            elif msg_class_name == "SystemMessage":
                # Check for compaction or other events
                subtype = getattr(msg, "subtype", "")
                if "compact" in subtype.lower():
                    self.status_callback("⚡ Auto-compacting context...")
                    # Also show message to user
                    self.console.print(
                        "\n[bold yellow]⚡ Context window at ~95% - auto-compacting...[/bold yellow]\n"
                    )
                # else: Initialization or other system event

            # Legacy dict-based messages
            elif isinstance(msg, dict):
                msg_type = msg.get("type", "")

                if msg_type == "tool_use":
                    tool_name = msg.get("name", "unknown")
                    if tool_name.startswith("mcp__bash__"):
                        self.status_callback("⚡ Executing bash...")
                    elif tool_name.startswith("mcp__web__"):
                        self.status_callback("🔍 Searching web...")
                    elif tool_name.startswith("mcp__ms365__"):
                        self.status_callback("📧 Accessing O365...")
                    else:
                        self.status_callback(f"🔧 Using {tool_name}...")

                elif msg_type == "text":
                    self.status_callback("💭 Responding...")

        except Exception as e:
            logger.exception(f"Error updating status: {e}")

    def _display_message(self, msg: Any) -> None:
        """Display message in console"""
        try:
            msg_class_name = type(msg).__name__

            # Handle SDK message types
            if msg_class_name == "StreamEvent":
                # Streaming events - handle content_block_delta for real-time streaming
                event = getattr(msg, "event", {})
                event_type = event.get("type")

                if event_type == "content_block_delta":
                    # This is a streaming text chunk!
                    delta = event.get("delta", {})
                    if delta.get("type") == "text_delta":
                        text = delta.get("text", "")

                        # Print header on first chunk
                        if not self._streaming_response:
                            self.console.print(
                                "\n[bold green]🤖 Assistant:[/bold green]\n"
                            )
                            self._streaming_response = True

                        # Stream the text directly
                        self.console.print(text, end="")
                        self._accumulated_text += text

                return  # StreamEvents handled, skip other processing

            elif msg_class_name == "SystemMessage":
                # SystemMessage - initialization and events
                subtype = getattr(msg, "subtype", "")
                data = getattr(msg, "data", {})

                # Check for compaction event
                if (
                    subtype == "compaction_start"
                    or "compact" in subtype.lower()
                ):
                    # Show detailed compaction info
                    self.console.print()
                    self.console.print(
                        Panel(
                            "[bold yellow]⚡ Auto-Compaction Started[/bold yellow]\n\n"
                            "The Claude Agent SDK is automatically summarizing older parts of the conversation\n"
                            "to make room for new interactions. This preserves:\n"
                            "  • Recent code modifications and decisions\n"
                            "  • Current objectives and patterns\n"
                            "  • Project structure and configuration\n\n"
                            "[dim]Compaction happens automatically when the context window approaches ~95% capacity.[/dim]",
                            title="🔄 Context Management",
                            border_style="yellow",
                            padding=(1, 2),
                        )
                    )
                    self.console.print()
                    logger.info(f"Compaction event: {subtype}, data: {data}")
                    return

                # Other system messages - don't display by default
                logger.debug(f"SystemMessage: subtype={subtype}, data={data}")
                return

            elif msg_class_name == "AssistantMessage":
                # AssistantMessage - extract text and tool use from content blocks
                content = getattr(msg, "content", [])
                for block in content:
                    block_type = type(block).__name__

                    if block_type == "TextBlock":
                        # Text was already streamed via StreamEvent - skip
                        pass

                    elif block_type == "ToolUseBlock":
                        # Tool call - show what tool is being used
                        tool_name = getattr(block, "name", "unknown")
                        tool_input = getattr(block, "input", {})
                        tool_id = getattr(block, "id", "")

                        self.console.print(
                            Panel(
                                f"[bold yellow]🔧 Tool:[/bold yellow] {tool_name}\n"
                                f"[dim]Input:[/dim] {tool_input}\n"
                                f"[dim]ID: {tool_id}[/dim]",
                                border_style="yellow",
                                title="Tool Use",
                            )
                        )

            elif msg_class_name == "UserMessage":
                # UserMessage - contains tool results
                content = getattr(msg, "content", [])
                for block in content:
                    block_type = type(block).__name__

                    if block_type == "ToolResultBlock":
                        # Tool result - show what the tool returned
                        result_content = getattr(block, "content", "")
                        is_error = getattr(block, "is_error", False)

                        # Extract text from nested structure if needed
                        # Content can be: str, list of dicts with 'text' key, or other
                        if isinstance(result_content, list):
                            # Extract text from [{'type': 'text', 'text': '...'}] format
                            text_parts = []
                            for item in result_content:
                                if isinstance(item, dict) and "text" in item:
                                    text_parts.append(item["text"])
                                else:
                                    text_parts.append(str(item))
                            result_content = "\n".join(text_parts)
                        else:
                            result_content = str(result_content)

                        border_color = "red" if is_error else "green"
                        title = (
                            "❌ Tool Error" if is_error else "✅ Tool Result"
                        )

                        # Truncate very long output
                        if len(result_content) > 1000:
                            result_content = (
                                result_content[:1000] + "\n... (truncated)"
                            )

                        self.console.print(
                            Panel(
                                result_content,
                                title=title,
                                border_style=border_color,
                            )
                        )

            elif msg_class_name == "ResultMessage":
                # ResultMessage - show summary and update usage tracking
                duration_ms = getattr(msg, "duration_ms", 0)
                cost = getattr(msg, "total_cost_usd", 0)
                usage = getattr(msg, "usage", {})

                # Reset streaming state (response complete)
                if self._streaming_response:
                    # Render accumulated text as pretty markdown
                    if self._accumulated_text:
                        self.console.print("\n")  # Separator
                        self.console.print("[dim]─" * 60 + "[/dim]")
                        markdown = Markdown(
                            self._accumulated_text, code_theme="monokai"
                        )
                        self.console.print(markdown)
                        self.console.print("[dim]─" * 60 + "[/dim]")

                    self.console.print()  # Final newline
                    self._streaming_response = False
                    self._last_text_length = 0
                    self._accumulated_text = ""

                # Session ID is already captured in chat() method
                # Update cumulative token tracking
                self.total_input_tokens += usage.get("input_tokens", 0)
                self.total_output_tokens += usage.get("output_tokens", 0)
                self.total_cache_creation_tokens += usage.get(
                    "cache_creation_input_tokens", 0
                )
                self.total_cache_read_tokens += usage.get(
                    "cache_read_input_tokens", 0
                )
                self.total_cost_usd += cost

                if self.verbose:
                    # Simple, honest usage metrics
                    # Note: We don't show cumulative token counts because:
                    # - After auto-compaction, they don't reflect actual context size
                    # - SDK manages context internally with auto-compaction at ~95%
                    # - Only SDK knows the real context state after compaction
                    usage_line = (
                        f"⏱️  {duration_ms}ms | "
                        f"💰 ${cost:.4f} | "
                        f"💵 Total: ${self.total_cost_usd:.4f}"
                    )

                    self.console.print(f"\n[dim]{usage_line}[/dim]\n")
                return

            # Legacy dict-based messages (for backwards compatibility)
            elif isinstance(msg, dict):
                msg_type = msg.get("type", "")

                if msg_type == "text":
                    text = msg.get("text", "")
                    self.console.print(text, end="")

                elif msg_type == "tool_use":
                    tool_name = msg.get("name", "unknown")
                    tool_input = msg.get("input", {})
                    self.console.print(
                        Panel(
                            f"[bold yellow]Tool:[/bold yellow] {tool_name}\n"
                            f"[dim]{tool_input}[/dim]",
                            border_style="yellow",
                        )
                    )

                elif msg_type == "tool_result":
                    content = msg.get("content", "")
                    is_error = msg.get("isError", False)
                    border_color = "red" if is_error else "green"
                    title = "❌ Tool Error" if is_error else "✅ Tool Result"
                    self.console.print(
                        Panel(
                            content,
                            title=title,
                            border_style=border_color,
                        )
                    )

            else:
                logger.debug(f"Unknown message type: {msg_class_name}")

        except Exception as e:
            logger.exception(f"Error displaying message: {e}")
            self.console.print(
                f"[dim red]Error displaying message: {e}[/dim red]"
            )

    async def reset(self) -> None:
        """Reset conversation - will create new client on next chat"""
        if self.client:
            # Properly exit the client context
            try:
                # Suppress all exceptions during cleanup to avoid issues with KeyboardInterrupt
                await self.client.__aexit__(None, None, None)
            except (Exception, KeyboardInterrupt) as e:
                logger.warning(f"Error closing client during reset: {e}")
            finally:
                self.client = None

        self.console.print("[dim]Conversation reset.[/dim]")

    def toggle_verbose(self) -> bool:
        """Toggle verbose mode"""
        self.verbose = not self.verbose
        status = "ON" if self.verbose else "OFF"
        self.console.print(f"[dim]Verbose mode: {status}[/dim]")
        return self.verbose

    def set_verbose(self, value: bool) -> None:
        """Set verbose mode"""
        self.verbose = value

    async def cleanup(self) -> None:
        """Clean up resources properly on shutdown"""
        if self.client:
            try:
                # Properly close the client context
                await self.client.__aexit__(None, None, None)
            except (Exception, KeyboardInterrupt) as e:
                logger.warning(f"Error during cleanup: {e}")
            finally:
                self.client = None
