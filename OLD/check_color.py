#!/usr/bin/env python3
"""
Simple color check for bassi agent output
Run this to see if colors work properly
"""

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

console = Console()

# Welcome
console.print("\n[bold magenta]🎨 bassi Color Check[/bold magenta]\n")

# User message
console.print(
    "[bold cyan]📨 User:[/bold cyan] [white]find all python files[/white]\n"
)

# Iteration
console.print("[dim cyan]→ Iteration 1/10[/dim cyan]")

# Status lines (simulated)
console.print(Text("⏳ CALLING API...........", style="bold yellow"))
console.print(Text("📡 STREAMING RESPONSE...", style="bold cyan"))

# Agent response (normal white text)
console.print("\nI'll search for Python files using fd.\n")

# Agent wants tools
console.print("[dim yellow]→ Agent wants to use tools[/dim yellow]\n")

# Tool panel
tool_json = """{
  "command": "fd '\\\\.py$'"
}"""
syntax = Syntax(tool_json, "json", theme="monokai")
console.print(
    Panel(
        syntax,
        title="[bold yellow]🔧 Tool: bash[/bold yellow]",
        border_style="yellow",
    )
)

# Bash execution status
console.print(Text("\n⚡ EXECUTING BASH: fd '\\.py$'", style="bold yellow"))

# Success result
console.print(
    Panel(
        """[bold cyan]Exit Code:[/bold cyan] 0
[bold cyan]Success:[/bold cyan] True

[bold white]STDOUT:[/bold white]
[dim]bassi/agent.py
bassi/main.py
bassi/config.py
tests/test_agent.py[/dim]

[bold red]STDERR:[/bold red]
[dim](empty)[/dim]""",
        title="[bold green]💻 Bash Result[/bold green]",
        border_style="green",
    )
)

# Agent response continues
console.print("\nI found 4 Python files in the project.\n")

# Finished
console.print("[dim green]→ Agent finished[/dim green]\n")

# Error example
console.print("\n[bold magenta]📛 Error Example:[/bold magenta]\n")
console.print(
    Panel(
        """[bold cyan]Exit Code:[/bold cyan] 2
[bold cyan]Success:[/bold cyan] False

[bold white]STDOUT:[/bold white]
[dim](empty)[/dim]

[bold red]STDERR:[/bold red]
[dim]ls: cannot access 'nonexistent': No such file or directory[/dim]""",
        title="[bold red]💻 Bash Result[/bold red]",
        border_style="red",
    )
)

console.print("\n[bold green]✅ Color test complete![/bold green]\n")
