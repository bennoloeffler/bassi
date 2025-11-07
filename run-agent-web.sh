#!/bin/bash
# Start Bassi V3 Web UI with hot reload enabled for development
#
# Usage: ./run-agent-web.sh
#
# This starts the web-only interface with:
# - Backend hot reload (watches Python files, auto-restarts in 2-3 sec)
# - Browser cache-control headers (F5 to reload frontend changes instantly)
# - WebSocket streaming interface
# - Interactive questions support
# - Startup discovery (shows MCP servers, slash commands, skills)
#
# Access: http://localhost:8765

echo "⏰ Started at: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""
echo "🚀 Starting Bassi V3 Web UI"
echo ""
echo "Features:"
echo "  • 🔥 Hot reload enabled (backend auto-restarts on .py changes)"
echo "  • 🌐 Web UI on http://localhost:8765"
echo "  • 💬 WebSocket streaming"
echo "  • ❓ Interactive questions"
echo "  • 🔍 Startup discovery"
echo ""
echo "💡 Tip: Edit Python files → auto-reload in ~2-3 seconds"
echo "💡 Tip: Edit static files → press F5 to reload browser"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Clean up any existing bassi-web processes on port 8765
if lsof -i :8765 >/dev/null 2>&1; then
    echo "⚠️  Cleaning up existing processes on port 8765..."
    pkill -9 -f "bassi-web|uvicorn.*bassi.core_v3" 2>/dev/null || true
    sleep 1
    echo "✅ Port 8765 is now free"
    echo ""
fi

# Enable unbuffered output for real-time streaming
export PYTHONUNBUFFERED=1

# Clear log file and write timestamp at the very beginning
echo "⏰ Log started at: $(date '+%Y-%m-%d %H:%M:%S')" > /tmp/bassi-web.log
echo "" >> /tmp/bassi-web.log

# Run V3 web UI using the bassi-web command (has reload=True)
# Logs to both stdout and /tmp/bassi-web.log
uv run bassi-web 2>&1 | tee -a /tmp/bassi-web.log
