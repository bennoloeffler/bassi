#!/bin/bash
# Start bassi with hot reload enabled for development

echo "🔥 Starting bassi with hot reload enabled"
echo ""
echo "Features:"
echo "  • Backend hot reload (watches Python files)"
echo "  • Frontend auto-reconnect (on server restart)"
echo "  • Web UI on http://localhost:8765"
echo ""
echo "Logs will be written to server.log"
echo "Press Ctrl+C to stop"
echo ""

# Enable unbuffered output for real-time streaming
export PYTHONUNBUFFERED=1

# Run bassi with web UI and reload enabled
uv run bassi --web --reload
