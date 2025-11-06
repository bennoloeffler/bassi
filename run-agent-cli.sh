#!/bin/bash
# Start Bassi V1 CLI with hot reload enabled for development
#
# Usage: ./run-agent-cli.sh
#
# This starts the CLI interface with:
# - Auto-restart when Python files change (using watchfiles)
# - Rich console interface
# - Keyboard shortcuts
# - Session persistence
# - Optional web UI (use --web flag)
#
# Note: The CLI will restart when you edit code files, losing current session.
# For development without restarts, run 'bassi' directly instead.

echo "🚀 Starting Bassi V1 CLI with Hot Reload"
echo ""
echo "Features:"
echo "  • 🔥 Hot reload enabled (CLI auto-restarts on .py changes)"
echo "  • 💬 Rich console interface"
echo "  • ⌨️  Keyboard shortcuts"
echo "  • 💾 Session persistence"
echo ""
echo "💡 Tip: Edit Python files → CLI restarts automatically"
echo "⚠️  Warning: Restart loses current conversation (use session_id to resume)"
echo ""
echo "Commands:"
echo "  • /help       - Show help"
echo "  • /config     - Show configuration"
echo "  • /quit       - Exit"
echo ""
echo "Press Ctrl+C twice to stop"
echo ""

# Enable unbuffered output for real-time streaming
export PYTHONUNBUFFERED=1

# Use watchfiles to auto-restart CLI when Python files change
# Watches bassi/ directory for *.py files
uv run watchfiles \
    --ignore-paths '/Users/benno/projects/ai/bassi/.venv' \
    --ignore-paths '/Users/benno/projects/ai/bassi/__pycache__' \
    --filter python \
    'uv run bassi' \
    /Users/benno/projects/ai/bassi/bassi
