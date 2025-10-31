# Using DeepSeek with bassi

Bassi can use DeepSeek's Anthropic-compatible API endpoint as an alternative to the official Anthropic API.

## Configuration

Set these environment variables before running bassi:

```bash
export ANTHROPIC_API_KEY=sk-<your-deepseek-api-key>
export ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic
```

## How it Works

The Anthropic Python SDK respects the `ANTHROPIC_BASE_URL` environment variable and will route all API requests to that endpoint instead of the default `https://api.anthropic.com`.

When bassi starts, it will display the active API endpoint in the welcome banner:

```
# bassi v0.1.0
Benno's Assistant - Your personal AI agent

📂 Working directory: /your/current/directory
🌐 API Endpoint: https://api.deepseek.com/anthropic

Type your request or use commands:
...
```

Additionally, the endpoint and API key (first 10 characters) are logged to `bassi_debug.log` on startup:

```
INFO:bassi.agent:🌐 API Endpoint: https://api.deepseek.com/anthropic
INFO:bassi.agent:🔑 API Key: sk-e1232fc...
```

## Model Compatibility

According to DeepSeek documentation, when using their Anthropic-compatible endpoint:
- The API accepts Anthropic-style requests
- You should specify `model: "deepseek-chat"` in API calls
- If an unsupported model name is provided, requests are automatically redirected to `deepseek-chat`

**Note**: The Claude Agent SDK spawns the `claude` CLI tool as a subprocess. The CLI tool needs to support `ANTHROPIC_BASE_URL` for this to work properly. If using the Agent SDK, the environment variables are inherited by the subprocess.

## Verification

To verify your configuration is working:

1. Check the welcome banner shows the correct endpoint
2. Check the `bassi_debug.log` file for endpoint information
3. Run a simple query and observe the logs

## Troubleshooting

If requests aren't reaching DeepSeek:

1. Verify environment variables are set:
   ```bash
   echo $ANTHROPIC_BASE_URL
   echo $ANTHROPIC_API_KEY
   ```

2. Check bassi_debug.log for endpoint configuration:
   ```bash
   grep "API Endpoint" bassi_debug.log
   ```

3. Enable debug logging:
   ```bash
   export BASSI_DEBUG=1
   ./run-agent.sh
   ```

## References

- [DeepSeek Anthropic API Documentation](https://api-docs.deepseek.com/guides/anthropic_api)
- [Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python)
1. * 	> 