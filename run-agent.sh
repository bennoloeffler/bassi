#!/bin/bash
# Start bassi with logging to server.log

echo "Starting bassi..."
echo "Logs will be written to server.log"
echo ""

# Enable unbuffered output for real-time streaming
export PYTHONUNBUFFERED=1

# Run bassi directly (no tee - it breaks TTY)
# Logging is handled by the agent itself to bassi_debug.log
uv run bassi
