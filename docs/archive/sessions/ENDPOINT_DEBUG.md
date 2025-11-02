# API Endpoint Debugging Feature

## Summary

Added debugging features to display which API endpoint bassi is using when it starts up. This is particularly useful when using alternative API providers like DeepSeek.

## Changes Made

### 1. Agent Initialization Logging (bassi/agent.py)

Added logging in `BassiAgent.__init__()` to show:
- API endpoint being used (from `ANTHROPIC_BASE_URL` or default)
- First 10 characters of API key for verification

```python
# Log API configuration for debugging
api_base_url = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
api_key_preview = os.getenv("ANTHROPIC_API_KEY", "not-set")[:10] + "..."
logger.info(f"🌐 API Endpoint: {api_base_url}")
logger.info(f"🔑 API Key: {api_key_preview}")
```

These logs appear in `bassi_debug.log`.

### 2. Welcome Banner Display (bassi/main.py)

Added API endpoint display to the welcome message:

```
# bassi v0.1.0
Benno's Assistant - Your personal AI agent

📂 Working directory: /your/current/directory
🌐 API Endpoint: https://api.deepseek.com/anthropic

Type your request or use commands:
...
```

### 3. Documentation (docs/deepseek-setup.md)

Created comprehensive guide for using DeepSeek with bassi, including:
- Configuration steps
- How it works (SDK respects `ANTHROPIC_BASE_URL`)
- Verification methods
- Troubleshooting tips

## How to Use DeepSeek

```bash
export ANTHROPIC_API_KEY=sk-<your-deepseek-key>
export ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic
./run-agent.sh
```

## Important Notes

### Anthropic SDK Support

The Anthropic Python SDK **does** support `ANTHROPIC_BASE_URL`:

From `anthropic/_client.py:101`:
```python
base_url = os.environ.get("ANTHROPIC_BASE_URL")
```

### Claude Agent SDK Caveat

The Claude Agent SDK spawns the `claude` CLI tool as a subprocess via `SubprocessCLITransport`. The environment variables are passed to the subprocess, so:

- `ANTHROPIC_BASE_URL` should be inherited by the subprocess
- The `claude` CLI tool itself needs to respect this variable
- The SDK doesn't directly instantiate an `Anthropic()` client

### Verification

You can verify the configuration by:

1. **Check welcome banner** - Shows endpoint immediately on startup
2. **Check logs** - `bassi_debug.log` contains endpoint info
3. **Enable debug mode** - `export BASSI_DEBUG=1` for detailed logging

## Testing

Tested with:
```bash
ANTHROPIC_BASE_URL="https://api.deepseek.com/anthropic" \
ANTHROPIC_API_KEY="sk-test123456" \
python -c "from bassi.main import print_welcome; print_welcome()"
```

Output shows the correct endpoint in the banner.

## Files Modified

- `bassi/agent.py` - Added endpoint logging on initialization
- `bassi/main.py` - Added endpoint display to welcome banner
- `docs/deepseek-setup.md` - New documentation file
- `ENDPOINT_DEBUG.md` - This file

## Future Enhancements

Potential improvements:
- Add endpoint to `/config` command output
- Show model name being used (e.g., "deepseek-chat")
- Validate endpoint is reachable on startup
- Support for other Anthropic-compatible endpoints (e.g., OpenRouter)
