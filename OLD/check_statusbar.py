#!/usr/bin/env python3
"""
Demo of the status bar feature
"""

import time

from bassi.status_bar import create_status_bar
from rich.console import Console
from rich.panel import Panel

console = Console()

print("\n" * 2)
console.print("[bold magenta]📊 Status Bar Demo[/bold magenta]\n")

# Simulate different status messages
statuses = [
    "Ready",
    "⏳ Calling API...",
    "📡 Streaming response...",
    "⚡ EXECUTING BASH: fd '*.py'",
    "⚡ EXECUTING BASH: ls -la",
    "✅ Ready",
]

for status in statuses:
    console.print(f"\n[bold cyan]Current status:[/bold cyan] {status}")
    console.print(
        Panel(
            create_status_bar(status),
            style="dim",
            border_style="dim blue",
            padding=0,
        )
    )
    time.sleep(1)

console.print("\n[bold green]✅ Status bar demo complete![/bold green]\n")
console.print("[yellow]The status bar shows:[/yellow]")
console.print("  📂 Current working directory (cyan)")
console.print("  │  Current status/log message (white)")
console.print("  │  Help shortcuts (yellow)\n")
