"""
Main CLI entry point for bassi - Async version with Claude Agent SDK
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

import anyio
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from bassi import __version__
from bassi.agent import BassiAgent
from bassi.config import get_config_manager

logger = logging.getLogger(__name__)

console = Console()

# Command registry for interactive selector
COMMANDS = {
    "/help": "Show detailed help and examples",
    "/config": "Display current configuration",
    "/edit": "Open $EDITOR for multiline input",
    "/alles_anzeigen": "Toggle verbose mode (show all tool calls)",
    "/reset": "Reset conversation history",
    "/quit": "Exit bassi",
}


async def monitor_esc_key(agent: BassiAgent):
    """Monitor for ESC key press during agent execution

    NOTE: Disabled for now as it interferes with terminal state.
    User can use Ctrl+C to interrupt instead.
    """
    # Disabled - terminal state conflicts with prompt_toolkit
    pass


def print_welcome() -> None:
    """Print welcome banner"""
    cwd = os.getcwd()
    api_endpoint = os.getenv(
        "ANTHROPIC_BASE_URL", "https://api.anthropic.com"
    )

    console.print(f"\n[bold magenta]# bassi v{__version__}[/bold magenta]")
    console.print("BELs Benno's Assistant - Your personal AI agent\n")
    console.print(f"[bold blue]📂 Working directory: {cwd}[/bold blue]")
    console.print(f"[bold blue]🌐 API Endpoint: {api_endpoint}[/bold blue]\n")
    console.print("Type your request or use commands:")
    console.print("  • Type [bold green]/[/bold green] to see command menu")
    console.print("  • Type [bold green]/help[/bold green] for detailed help")
    console.print(
        "  • Press [bold green]Enter[/bold green] to send, [bold green]/edit[/bold green] for multiline"
    )
    console.print(
        "  • Press [bold green]Ctrl+C[/bold green] to interrupt agent or exit"
    )
    console.print(
        "  • Type [bold green]/alles_anzeigen[/bold green] to toggle verbose mode\n"
    )


def get_user_input(prompt: str = "You: ") -> str | None:
    """Get user input with simple readline support

    Returns:
        User input string, or None on EOF/interrupt
    """
    try:
        # Use simple input() with readline support
        import readline

        # Setup history file
        history_file = os.path.expanduser("~/.bassi_history")
        try:
            readline.read_history_file(history_file)
        except FileNotFoundError:
            pass

        # Set max history entries
        readline.set_history_length(1000)

        # Get input
        user_input = input(prompt)

        # Save to history
        readline.write_history_file(history_file)

        return user_input

    except EOFError:
        return None
    except KeyboardInterrupt:
        # Re-raise to be handled at higher level
        raise


def print_config() -> None:
    """Print current configuration"""
    config = get_config_manager().get_config()

    console.print("\n[bold cyan]## Configuration[/bold cyan]\n")
    console.print(
        f"[bold blue]Config file:[/bold blue] {get_config_manager().CONFIG_FILE}\n"
    )
    console.print("[bold blue]Root folders:[/bold blue]")
    for folder in config.root_folders:
        console.print(f"  • {folder}")
    console.print("\n[bold blue]Settings:[/bold blue]")
    console.print(f"  • Log level: {config.log_level}")
    console.print(f"  • Max search results: {config.max_search_results}\n")


def print_commands() -> None:
    """Print all available commands"""
    console.print("\n[bold cyan]## Available Commands[/bold cyan]\n")
    console.print(
        "  • [bold green]/[/bold green] - Show numbered command menu"
    )
    console.print(
        "  • [bold green]/help[/bold green] - Show detailed help and examples"
    )
    console.print(
        "  • [bold green]/config[/bold green] - Show current configuration"
    )
    console.print(
        "  • [bold green]/edit[/bold green] - Open $EDITOR for multiline input"
    )
    console.print(
        "  • [bold green]/alles_anzeigen[/bold green] - Toggle verbose mode (show all tool calls)"
    )
    console.print(
        "  • [bold green]/reset[/bold green] - Reset conversation history"
    )
    console.print(
        "  • [bold green]/quit[/bold green] or [bold green]/exit[/bold green] - Exit bassi\n"
    )


def print_help() -> None:
    """Print detailed help"""
    console.print(
        "\n[bold cyan]## Help: bassi - Benno's Assistant[/bold cyan]\n"
    )

    console.print("[bold yellow]### Available Commands[/bold yellow]\n")
    print_commands()

    console.print("[bold yellow]### Usage Examples[/bold yellow]\n")

    console.print("[bold blue]File Operations:[/bold blue]")
    console.print('  • "find all python files modified today"')
    console.print('  • "what\'s in my downloads folder?"')
    console.print('  • "create a backup script for my documents"\n')

    console.print("[bold blue]Web Search:[/bold blue]")
    console.print('  • "what\'s the current weather in Berlin?"')
    console.print('  • "search for latest Python 3.12 features"')
    console.print('  • "find recent news about AI developments"\n')

    console.print("[bold blue]Python Automation:[/bold blue]")
    console.print(
        '  • "compress all PNG images in ~/Pictures/vacation/ to 70% quality"'
    )
    console.print(
        '  • "rename all files in Downloads to include their creation date"'
    )
    console.print('  • "convert contacts.csv to JSON format"')
    console.print(
        '  • "find all TODO comments in Python files and create a report"\n'
    )

    console.print(
        "[bold blue]Email & Calendar (when configured):[/bold blue]"
    )
    console.print('  • "show my recent emails"')
    console.print('  • "draft an email to John about the meeting"')
    console.print('  • "what\'s on my calendar today?"')
    console.print('  • "schedule a meeting for tomorrow at 2pm"\n')


def show_command_selector() -> str | None:
    """Show interactive command selector"""
    console.print("\n[bold cyan]## Select a command:[/bold cyan]\n")

    commands_list = list(COMMANDS.items())
    for i, (cmd, desc) in enumerate(commands_list, start=1):
        console.print(f"  [bold green]{i}.[/bold green] {cmd} - {desc}")

    console.print()

    try:
        choice = Prompt.ask(
            "[bold]Enter number[/bold]",
            default="",
            show_default=False,
        )

        if not choice.strip():
            return None

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(commands_list):
                return commands_list[idx][0]
            else:
                console.print("[red]Invalid number. Please try again.[/red]")
                return None
        except ValueError:
            console.print("[red]Invalid input. Please enter a number.[/red]")
            return None

    except KeyboardInterrupt:
        console.print()
        return None


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="bassi - Benno's Personal Assistant"
    )
    parser.add_argument("--web", action="store_true", help="Enable web UI")
    parser.add_argument(
        "--no-cli",
        action="store_true",
        help="Disable CLI (web-only mode)",
    )
    parser.add_argument(
        "--port", type=int, default=8765, help="Web UI port (default: 8765)"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="Web UI host (default: localhost)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable hot reload for development (watches Python files)",
    )
    return parser.parse_args()


async def cli_main_loop(agent: BassiAgent) -> None:
    """Run the CLI main loop (extracted for clarity)"""
    import termios

    # Ensure terminal is in sane cooked mode at startup
    try:
        fd = sys.stdin.fileno()
        attrs = termios.tcgetattr(fd)
        # Enable canonical mode and echo
        attrs[3] |= termios.ICANON | termios.ECHO
        termios.tcsetattr(fd, termios.TCSANOW, attrs)
    except Exception:
        pass  # Not a TTY, ignore

    try:
        print_welcome()

        # Initialize agent with status callback
        current_status = ["Ready"]  # Use list for mutable reference

        def update_status(message: str):
            current_status[0] = message

        # Check for saved context FIRST
        resume_session_id: str | None = None
        saved_context = None

        context_file = Path.cwd() / ".bassi_context.json"
        if context_file.exists():
            try:
                saved_context = json.loads(context_file.read_text())
                console.print(
                    "\n[bold yellow]📋 Found saved context from previous session[/bold yellow]"
                )

                try:
                    load_choice = Prompt.ask(
                        "Load previous context?",
                        choices=["y", "n"],
                        default="y",
                    )
                    if load_choice.lower() == "y":
                        resume_session_id = saved_context.get("session_id")
                        if resume_session_id:
                            # Calculate time since last session
                            import time

                            last_timestamp = saved_context.get("timestamp", 0)
                            last_updated = saved_context.get(
                                "last_updated", "unknown"
                            )

                            # Calculate time ago
                            time_ago = ""
                            if last_timestamp:
                                seconds_ago = time.time() - last_timestamp
                                if seconds_ago < 60:
                                    time_ago = (
                                        f"{int(seconds_ago)} seconds ago"
                                    )
                                elif seconds_ago < 3600:
                                    time_ago = (
                                        f"{int(seconds_ago / 60)} minutes ago"
                                    )
                                elif seconds_ago < 86400:
                                    time_ago = (
                                        f"{int(seconds_ago / 3600)} hours ago"
                                    )
                                else:
                                    time_ago = (
                                        f"{int(seconds_ago / 86400)} days ago"
                                    )

                            # Show session summary
                            console.print()
                            console.print(
                                Panel(
                                    f"[bold green]📋 Session Resumed[/bold green]\n\n"
                                    f"Session ID: [cyan]{resume_session_id[:8]}...[/cyan]\n"
                                    f"Last Activity: [dim]{last_updated}[/dim] ({time_ago})\n\n"
                                    "[dim]Claude has full access to previous conversation context.\n"
                                    "The SDK will automatically compact old messages if needed.[/dim]",
                                    title="🔄 Previous Session Loaded",
                                    border_style="green",
                                    padding=(1, 2),
                                )
                            )
                            console.print()
                        else:
                            console.print(
                                "[bold yellow]⚠️  No session ID in context, starting fresh[/bold yellow]"
                            )
                    else:
                        console.print(
                            "[bold blue]Starting fresh conversation[/bold blue]"
                        )
                except (EOFError, KeyboardInterrupt):
                    # Non-interactive mode - load context by default
                    resume_session_id = saved_context.get("session_id")
                    if resume_session_id:
                        console.print(
                            "[bold green]✅ Will resume previous session (non-interactive mode)[/bold green]"
                        )
            except Exception as e:
                logger.warning(f"Failed to load context: {e}")

        # Initialize agent with resume session ID (if any)
        with console.status(
            "[bold green]Initializing bassi...", spinner="dots"
        ):
            agent = BassiAgent(
                status_callback=update_status,
                resume_session_id=resume_session_id,
            )

        console.print(
            "\n[bold green]Ready![/bold green] What can I help you with?\n"
        )

        # Main conversation loop
        while True:
            try:
                # Get user input (simple readline-based)
                user_input = get_user_input("You: ")

                if user_input is None:
                    # EOF - exit gracefully
                    console.print("\n[bold blue]Goodbye![/bold blue] 👋\n")
                    break

                if not user_input.strip():
                    continue

                # Handle commands
                if user_input.startswith("/"):
                    command = user_input.lower().strip()

                    # Show command menu for "/" or "//"
                    if command == "/" or command == "//":
                        selected = show_command_selector()
                        if selected:
                            # User selected a command, process it
                            command = selected
                        else:
                            # User cancelled, continue to next iteration
                            continue

                    if command in ["/quit", "/exit"]:
                        console.print(
                            "\n[bold blue]Goodbye![/bold blue] 👋\n"
                        )
                        break

                    elif command == "/help":
                        print_help()
                        continue

                    elif command == "/config":
                        print_config()
                        continue

                    elif command == "/edit":
                        # Open $EDITOR for multiline input
                        import subprocess
                        import tempfile

                        editor = os.environ.get("EDITOR", "vim")

                        with tempfile.NamedTemporaryFile(
                            mode="w+", suffix=".txt", delete=False
                        ) as tf:
                            tf_name = tf.name

                        try:
                            # Open editor
                            result = subprocess.run([editor, tf_name])
                            if result.returncode != 0:
                                console.print(
                                    f"[red]Editor exited with error code {result.returncode}[/red]\n"
                                )
                                continue

                            # Read the content
                            with open(tf_name) as f:
                                user_input = f.read().strip()

                            if not user_input:
                                console.print(
                                    "[yellow]No input provided, cancelled[/yellow]\n"
                                )
                                continue

                            # Process the multiline input as if it was typed
                            # (will be handled below, outside the command block)

                        finally:
                            # Clean up temp file
                            try:
                                os.unlink(tf_name)
                            except Exception:
                                pass

                        # Don't continue here - let it fall through to process user_input
                        # But we need to break out of command handling
                        # Actually, we should just process it here

                        # Show what was entered
                        console.print(
                            "\n[dim]Multiline input from editor:[/dim]"
                        )
                        console.print(
                            f"[dim]{user_input[:200]}{'...' if len(user_input) > 200 else ''}[/dim]\n"
                        )

                    elif command == "/alles_anzeigen":
                        # Toggle verbose mode
                        new_state = agent.toggle_verbose()
                        if new_state:
                            console.print(
                                "[bold green]✅ Verbose Modus AN[/bold green]"
                                " - Zeige alle Tool-Aufrufe\n"
                            )
                        else:
                            console.print(
                                "[bold yellow]Verbose Modus AUS[/bold yellow]\n"
                            )
                        continue

                    elif command == "/reset":
                        await agent.reset()
                        console.print(
                            "[bold yellow]Conversation reset[/bold yellow]\n"
                        )
                        continue

                    else:
                        console.print(
                            f"[red]Unknown command: {command}[/red]\n"
                            f"Type [bold]/[/bold] to see all commands\n"
                        )
                        continue

                # Process with agent (ASYNC - streams directly to console)
                try:
                    # Run agent chat
                    async for _ in agent.chat(user_input):
                        pass

                except KeyboardInterrupt:
                    # Handle Ctrl+C during agent run
                    await agent.interrupt()
                    console.print("\n[yellow]⚠️  Agent interrupted[/yellow]\n")

                console.print()  # Extra newline for spacing

            except Exception as e:
                console.print(f"[bold red]Error:[/bold red] {str(e)}\n")
                continue

    except KeyboardInterrupt:
        # Handled by finally block or outer main()
        pass

    except Exception as e:
        console.print(f"[bold red]Fatal error:[/bold red] {str(e)}\n")
        sys.exit(1)

    finally:
        # Clean up agent resources
        try:
            if "agent" in locals() and agent:
                await agent.cleanup()
        except Exception:
            pass  # Suppress any cleanup errors

        # Ensure terminal is restored on exit
        try:
            fd = sys.stdin.fileno()
            attrs = termios.tcgetattr(fd)
            attrs[3] |= termios.ICANON | termios.ECHO
            termios.tcsetattr(fd, termios.TCSANOW, attrs)
        except Exception:
            pass


async def main_async() -> None:
    """Main async entry point with web UI support"""
    args = parse_args()

    # Print banner (if CLI mode)
    if not args.no_cli:
        print_welcome()

    # Initialize agent with status callback
    current_status = ["Ready"]  # Use list for mutable reference

    def update_status(message: str):
        current_status[0] = message

    # Check for saved context FIRST
    resume_session_id: str | None = None
    saved_context = None

    context_file = Path.cwd() / ".bassi_context.json"
    if context_file.exists() and not args.no_cli:
        # Only prompt if in CLI mode
        try:
            saved_context = json.loads(context_file.read_text())
            console.print(
                "\n[bold yellow]📋 Found saved context from previous session[/bold yellow]"
            )

            load_choice = Prompt.ask(
                "Load previous context?", choices=["y", "n"], default="y"
            )
            if load_choice.lower() == "y":
                resume_session_id = saved_context.get("session_id")
                if resume_session_id:
                    console.print(
                        f"[dim]Resuming session: {resume_session_id[:8]}...[/dim]\n"
                    )
        except Exception as e:
            console.print(
                f"[yellow]Warning: Could not load context: {e}[/yellow]"
            )

    # Initialize agent (for CLI) - only if not in web-only mode
    agent = None
    if not args.no_cli:
        agent = BassiAgent(
            status_callback=update_status, resume_session_id=resume_session_id
        )

    # Start web server if enabled
    if args.web:
        from bassi.web_server import start_web_server

        # Create agent factory for web UI (one agent per connection)
        def create_agent_instance():
            """Factory function to create isolated agent instances for web UI"""
            return BassiAgent(
                status_callback=None,  # No CLI status callback for web UI
                resume_session_id=None,  # Each connection starts fresh
                display_tools=False,  # Suppress tools display for web UI agents
            )

        console.print(
            f"[bold green]🌐 Starting web UI on http://{args.host}:{args.port}[/bold green]"
        )

        # In web-only mode, create a temporary agent just to display tools once
        if args.no_cli:
            display_agent = BassiAgent(
                status_callback=None,
                resume_session_id=None,
                display_tools=True,  # Show tools once at startup
            )
            # Clean up display agent immediately after showing tools
            await display_agent.cleanup()

        async with anyio.create_task_group() as tg:
            # Start web server in background with agent factory
            tg.start_soon(
                start_web_server,
                create_agent_instance,
                args.host,
                args.port,
                args.reload,
            )

            # Run CLI unless --no-cli specified
            if not args.no_cli:
                await cli_main_loop(agent)
                tg.cancel_scope.cancel()  # Stop web server when CLI exits
            else:
                # Web-only mode - keep running
                if args.reload:
                    console.print(
                        "[bold green]🔥 Hot reload enabled - server will restart on file changes[/bold green]"
                    )
                console.print(
                    "[bold green]Running in web-only mode. Press Ctrl+C to stop.[/bold green]"
                )
                try:
                    await anyio.sleep_forever()
                except KeyboardInterrupt:
                    console.print(
                        "\n[bold blue]Shutting down web server...[/bold blue]"
                    )
    else:
        # CLI-only mode (default)
        await cli_main_loop(agent)


def main() -> None:
    """Entry point - runs async main"""
    # Configure logging once for CLI mode
    from bassi.logging_utils import configure_logging
    configure_logging()

    # Enable DEBUG logging via environment variable
    if os.getenv("BASSI_DEBUG"):
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        anyio.run(main_async)
    except KeyboardInterrupt:
        # Graceful exit on Ctrl+C
        console.print("\n[bold blue]Goodbye![/bold blue] 👋\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
