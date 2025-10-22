"""
Bash Command Execution MCP Server

Provides bash command execution capability as an SDK MCP server
"""

import subprocess
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool


@tool(
    "execute",
    "Execute a bash command and return the result",
    {"command": str, "timeout": int},
)
async def bash_execute(args: dict[str, Any]) -> dict[str, Any]:
    """
    Execute a bash command

    Args:
        command: The bash command to execute
        timeout: Maximum execution time in seconds (default 30)

    Returns:
        Dictionary with exit code, stdout, and stderr
    """
    command = args["command"]
    timeout = args.get("timeout", 30)

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        output = f"""Exit Code: {result.returncode}
Success: {result.returncode == 0}

STDOUT:
{result.stdout or '(empty)'}

STDERR:
{result.stderr or '(empty)'}"""

        return {"content": [{"type": "text", "text": output}]}

    except subprocess.TimeoutExpired:
        error_msg = f"Command timed out after {timeout} seconds"
        return {
            "content": [{"type": "text", "text": f"ERROR: {error_msg}"}],
            "isError": True,
        }

    except Exception as e:
        error_msg = f"Error executing command: {str(e)}"
        return {
            "content": [{"type": "text", "text": f"ERROR: {error_msg}"}],
            "isError": True,
        }


def create_bash_mcp_server():
    """Create and return the Bash MCP server"""
    return create_sdk_mcp_server(
        name="bash",
        version="1.0.0",
        tools=[bash_execute],
    )
