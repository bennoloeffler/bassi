"""
Task Automation MCP Server

Provides Python code execution for repeatable automation tasks like:
- Image processing (compress, resize, convert)
- File organization (batch rename, sort)
- Data transformation (CSV/JSON processing)
- Text processing (batch operations)
"""

import asyncio
import logging
import tempfile
import time
from pathlib import Path
from typing import Any

from bassi.shared.sdk_loader import create_sdk_mcp_server, tool

logger = logging.getLogger(__name__)


async def execute_python_task(
    code: str,
    description: str,
    working_dir: str | None = None,
    timeout: int = 300,
) -> dict[str, Any]:
    """
    Execute Python code in an isolated subprocess.

    Args:
        code: Python code to execute
        description: Human-readable task description (for logging)
        working_dir: Directory to execute in (defaults to current working directory)
        timeout: Maximum execution time in seconds (default: 300 = 5 minutes)

    Returns:
        {
            "success": bool,
            "stdout": str,
            "stderr": str,
            "exit_code": int,
            "execution_time": float,
            "description": str,
        }
    """
    logger.info(f"Executing Python task: {description}")
    logger.debug(f"Code:\n{code}")

    # Use current working directory if not specified
    if working_dir is None:
        working_dir = str(Path.cwd())
    else:
        working_dir = str(Path(working_dir).expanduser().resolve())

    # Validate working directory exists
    if not Path(working_dir).exists():
        return {
            "success": False,
            "stdout": "",
            "stderr": f"Working directory does not exist: {working_dir}",
            "exit_code": 1,
            "execution_time": 0.0,
            "description": description,
        }

    # Create temporary file with the code
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False
    ) as temp_file:
        temp_file.write(code)
        temp_file_path = temp_file.name

    try:
        # Execute the code in a subprocess
        start_time = time.time()

        process = await asyncio.create_subprocess_exec(
            "python",
            temp_file_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=working_dir,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )

            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")
            exit_code = process.returncode or 0
            execution_time = time.time() - start_time

            success = exit_code == 0

            logger.info(
                f"Task completed: {description} (exit_code={exit_code}, time={execution_time:.2f}s)"
            )
            if not success:
                logger.warning(f"Task failed with stderr: {stderr}")

            return {
                "success": success,
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": exit_code,
                "execution_time": execution_time,
                "description": description,
            }

        except asyncio.TimeoutError:
            # Kill the process if it exceeds timeout
            process.kill()
            await process.wait()

            execution_time = time.time() - start_time

            logger.error(f"Task timed out after {timeout}s: {description}")

            return {
                "success": False,
                "stdout": "",
                "stderr": f"Execution timed out after {timeout} seconds",
                "exit_code": -1,
                "execution_time": execution_time,
                "description": description,
            }

    finally:
        # Clean up temporary file
        try:
            Path(temp_file_path).unlink()
        except Exception as e:
            logger.warning(f"Failed to delete temporary file: {e}")


@tool(
    "execute_python",
    """Execute Python code for automation tasks.

Use this for repeatable tasks like:
- Image processing: compress/resize/convert images (use PIL/Pillow)
- File organization: batch rename, sort by metadata (use pathlib)
- Data transformation: CSV/JSON processing (use pandas, json)
- Text processing: batch find/replace, format conversion (use re, pathlib)

Common libraries available:
- PIL/Pillow (images)
- pandas (data)
- pathlib (files)
- json, csv (formats)
- re (regex)
- os, shutil (file operations)

The code runs in an isolated subprocess with timeout enforcement.

IMPORTANT: Numeric parameters must be integers, not strings!
- timeout: 300 (correct)
- timeout: "300" (WRONG - causes TypeError)
""",
    {
        "code": str,
        "description": str,
        "working_dir": (str, None),
        "timeout": (int, 300),
    },
)
async def task_automation_execute_python(
    args: dict[str, Any],
) -> dict[str, Any]:
    """Execute Python code for automation tasks."""
    code = args.get("code", "")
    description = args.get("description", "Python task")
    working_dir = args.get("working_dir")
    # Defensive: coerce timeout to int in case LLM passes string
    timeout = int(args.get("timeout", 300))

    if not code:
        return {
            "content": [{"type": "text", "text": "Error: No code provided"}]
        }

    result = await execute_python_task(
        code=code,
        description=description,
        working_dir=working_dir,
        timeout=timeout,
    )

    # Format the response
    if result["success"]:
        response = f"✓ Task completed: {result['description']}\n\n"
        response += f"Execution time: {result['execution_time']:.2f}s\n\n"
        if result["stdout"]:
            response += f"Output:\n{result['stdout']}"
        else:
            response += "No output"
    else:
        response = f"✗ Task failed: {result['description']}\n\n"
        response += f"Exit code: {result['exit_code']}\n"
        response += f"Execution time: {result['execution_time']:.2f}s\n\n"
        if result["stderr"]:
            response += f"Error:\n{result['stderr']}"
        else:
            response += "No error message"

    return {"content": [{"type": "text", "text": response}]}


def create_task_automation_server():
    """Create and configure the task automation MCP server."""
    return create_sdk_mcp_server(
        name="task_automation",
        version="1.0.0",
        tools=[task_automation_execute_python],
    )
