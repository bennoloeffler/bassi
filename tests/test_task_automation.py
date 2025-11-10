"""
Unit tests for task automation MCP server
"""

import tempfile
from pathlib import Path

import pytest

from bassi.mcp_servers.task_automation_server import (
    create_task_automation_server,
    execute_python_task,
)


@pytest.mark.asyncio
async def test_simple_print():
    """Test basic print statement execution"""
    code = """
print("Hello from Python!")
print("Line 2")
"""

    result = await execute_python_task(
        code=code, description="Simple print test", timeout=5
    )

    assert result["success"] is True
    assert result["exit_code"] == 0
    assert "Hello from Python!" in result["stdout"]
    assert "Line 2" in result["stdout"]
    assert result["stderr"] == ""
    assert result["execution_time"] < 2.0


@pytest.mark.asyncio
async def test_math_calculation():
    """Test simple computation and output"""
    code = """
result = 2 + 2
print(f"2 + 2 = {result}")
"""

    result = await execute_python_task(
        code=code, description="Math test", timeout=5
    )

    assert result["success"] is True
    assert "2 + 2 = 4" in result["stdout"]


@pytest.mark.asyncio
async def test_file_operations():
    """Test reading and writing files in temp directory"""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.txt"

        code = f"""
from pathlib import Path

# Write file
test_file = Path("{test_file}")
test_file.write_text("Hello from file!")

# Read it back
content = test_file.read_text()
print(f"Read: {{content}}")
"""

        result = await execute_python_task(
            code=code,
            description="File operations test",
            working_dir=tmpdir,
            timeout=5,
        )

        assert result["success"] is True
        assert "Read: Hello from file!" in result["stdout"]
        assert test_file.exists()
        assert test_file.read_text() == "Hello from file!"


@pytest.mark.asyncio
async def test_timeout_enforcement():
    """Test that code exceeding timeout is killed"""
    code = """
import time
print("Starting...")
time.sleep(10)  # Sleep longer than timeout
print("This should not print")
"""

    result = await execute_python_task(
        code=code, description="Timeout test", timeout=2  # 2 second timeout
    )

    assert result["success"] is False
    assert result["exit_code"] == -1
    assert "timed out" in result["stderr"].lower()
    assert (
        result["execution_time"] >= 2.0
    )  # Should take at least timeout duration


@pytest.mark.asyncio
async def test_syntax_error():
    """Test that syntax errors are captured"""
    code = """
print("Valid line")
this is not valid python syntax
print("Should not reach here")
"""

    result = await execute_python_task(
        code=code, description="Syntax error test", timeout=5
    )

    assert result["success"] is False
    assert result["exit_code"] != 0
    assert (
        "SyntaxError" in result["stderr"]
        or "invalid syntax" in result["stderr"]
    )


@pytest.mark.asyncio
async def test_runtime_error():
    """Test that runtime exceptions are captured"""
    code = """
print("Before error")
x = 1 / 0  # Division by zero
print("After error")
"""

    result = await execute_python_task(
        code=code, description="Runtime error test", timeout=5
    )

    assert result["success"] is False
    assert result["exit_code"] != 0
    assert "Before error" in result["stdout"]
    assert "ZeroDivisionError" in result["stderr"]
    assert "After error" not in result["stdout"]


@pytest.mark.asyncio
async def test_working_directory():
    """Test that code runs in specified directory"""
    with tempfile.TemporaryDirectory() as tmpdir:
        code = """
from pathlib import Path
import os

cwd = Path.cwd()
print(f"CWD: {cwd}")
print(f"Exists: {cwd.exists()}")
"""

        result = await execute_python_task(
            code=code,
            description="Working directory test",
            working_dir=tmpdir,
            timeout=5,
        )

        assert result["success"] is True
        assert tmpdir in result["stdout"]
        assert "Exists: True" in result["stdout"]


@pytest.mark.asyncio
async def test_invalid_working_directory():
    """Test handling of non-existent working directory"""
    result = await execute_python_task(
        code="print('test')",
        description="Invalid dir test",
        working_dir="/nonexistent/path/that/does/not/exist",
        timeout=5,
    )

    assert result["success"] is False
    assert "does not exist" in result["stderr"]


@pytest.mark.asyncio
async def test_multiline_output():
    """Test handling of multiline output"""
    code = """
for i in range(5):
    print(f"Line {i}")
"""

    result = await execute_python_task(
        code=code, description="Multiline test", timeout=5
    )

    assert result["success"] is True
    for i in range(5):
        assert f"Line {i}" in result["stdout"]


@pytest.mark.asyncio
async def test_empty_code():
    """Test handling of empty code"""
    result = await execute_python_task(
        code="", description="Empty code test", timeout=5
    )

    # Empty code should succeed (no-op)
    assert result["success"] is True
    assert result["stdout"] == ""


@pytest.mark.asyncio
async def test_python_imports():
    """Test that common libraries are available"""
    code = """
import json
import csv
import pathlib
import re
import os
import shutil

print("All imports successful")
"""

    result = await execute_python_task(
        code=code, description="Import test", timeout=5
    )

    assert result["success"] is True
    assert "All imports successful" in result["stdout"]


@pytest.mark.asyncio
async def test_pillow_available():
    """Test that PIL/Pillow is available"""
    code = """
from PIL import Image
print("Pillow is available")
print(f"PIL version: {Image.__version__}")
"""

    result = await execute_python_task(
        code=code, description="Pillow test", timeout=5
    )

    assert result["success"] is True
    assert "Pillow is available" in result["stdout"]


@pytest.mark.asyncio
async def test_pandas_available():
    """Test that pandas is available"""
    code = """
import pandas as pd
print("pandas is available")
print(f"pandas version: {pd.__version__}")
"""

    result = await execute_python_task(
        code=code, description="pandas test", timeout=5
    )

    assert result["success"] is True
    assert "pandas is available" in result["stdout"]


@pytest.mark.asyncio
async def test_mcp_server_creation():
    """Test MCP server can be created"""
    server = create_task_automation_server()
    assert server is not None
    # SDK MCP servers don't expose list_tools/call_tool directly
    # They are used internally by the Agent SDK


@pytest.mark.asyncio
async def test_image_processing():
    """Test real image processing with PIL"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        code = f"""
from PIL import Image
from pathlib import Path

# Create a simple test image
img = Image.new('RGB', (100, 100), color='red')
img_path = Path("{tmpdir_path}") / "test.png"
img.save(img_path)

# Verify it was created
print(f"Created: {{img_path}}")
print(f"Size: {{img_path.stat().st_size}} bytes")

# Resize it
img_resized = img.resize((50, 50))
resized_path = Path("{tmpdir_path}") / "test_resized.png"
img_resized.save(resized_path)

print(f"Resized: {{resized_path}}")
print(f"New size: {{resized_path.stat().st_size}} bytes")
"""

        result = await execute_python_task(
            code=code,
            description="Image processing test",
            working_dir=tmpdir,
            timeout=10,
        )

        assert result["success"] is True
        assert "Created:" in result["stdout"]
        assert "Resized:" in result["stdout"]
        assert (tmpdir_path / "test.png").exists()
        assert (tmpdir_path / "test_resized.png").exists()


@pytest.mark.asyncio
async def test_batch_file_processing():
    """Test batch file operations"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test files
        tmpdir_path = Path(tmpdir)
        for i in range(5):
            (tmpdir_path / f"file{i}.txt").write_text(f"Content {i}")

        code = f"""
from pathlib import Path

work_dir = Path("{tmpdir_path}")
files = sorted(work_dir.glob("*.txt"))

print(f"Found {{len(files)}} files")

# Rename them
for i, file in enumerate(files):
    new_name = f"renamed_{{i}}.txt"
    file.rename(file.parent / new_name)
    print(f"Renamed: {{file.name}} -> {{new_name}}")

print("Done!")
"""

        result = await execute_python_task(
            code=code,
            description="Batch rename test",
            working_dir=tmpdir,
            timeout=10,
        )

        assert result["success"] is True
        assert "Found 5 files" in result["stdout"]
        assert "Done!" in result["stdout"]

        # Verify renamed files exist
        for i in range(5):
            assert (tmpdir_path / f"renamed_{i}.txt").exists()


# ============================================================================
# SECURITY TESTS - Document malicious code behavior
# ============================================================================


class TestTaskAutomationSecurity:
    """Security tests for task automation server.

    These tests verify behavior when executing potentially malicious code.
    The server runs code in a subprocess, which provides SOME isolation,
    but these tests document what attacks are still possible.
    """

    @pytest.mark.asyncio
    async def test_file_system_access_outside_workdir(self):
        """Test that code CAN access files outside working directory.

        SECURITY WARNING: This test documents that task automation
        does NOT restrict file system access. Code can read/write
        ANY file the Python process has permission to access.
        """
        code = """
import os
# Attempt to access system files
try:
    with open('/etc/hosts', 'r') as f:
        content = f.read()
        print(f"SUCCESS: Read {len(content)} bytes from /etc/hosts")
except Exception as e:
    print(f"FAILED: {e}")
"""
        result = await execute_python_task(
            code=code, description="File access test", timeout=5
        )

        # Task succeeds - NO file system isolation
        assert result["success"] is True
        # Code CAN read system files
        assert "SUCCESS" in result["stdout"]
        assert "/etc/hosts" in result["stdout"]

    @pytest.mark.asyncio
    async def test_path_traversal_attack(self):
        """Test path traversal to access parent directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            code = """
from pathlib import Path
# Attempt path traversal
parent = Path("..").resolve()
print(f"Parent: {parent}")
print(f"Can access parent: {parent.exists()}")
"""
            result = await execute_python_task(
                code=code,
                description="Path traversal test",
                working_dir=tmpdir,
                timeout=5,
            )

            # Documents that path traversal works
            assert result["success"] is True
            assert "Can access parent: True" in result["stdout"]

    @pytest.mark.asyncio
    async def test_subprocess_execution(self):
        """Test that code can execute system commands via subprocess.

        SECURITY WARNING: Code can run arbitrary shell commands.
        """
        code = """
import subprocess
result = subprocess.run(['echo', 'Hello from shell'],
                       capture_output=True, text=True)
print(f"Shell output: {result.stdout.strip()}")
print(f"Exit code: {result.returncode}")
"""
        result = await execute_python_task(
            code=code, description="Subprocess test", timeout=5
        )

        # Documents that subprocess execution works
        assert result["success"] is True
        assert "Shell output: Hello from shell" in result["stdout"]

    @pytest.mark.asyncio
    async def test_os_system_execution(self):
        """Test that code can execute shell commands via os.system."""
        code = """
import os
# Execute shell command
exit_code = os.system('echo "OS system test" > /tmp/bassi_test_file.txt')
print(f"os.system exit code: {exit_code}")

# Verify it worked
import pathlib
if pathlib.Path('/tmp/bassi_test_file.txt').exists():
    content = pathlib.Path('/tmp/bassi_test_file.txt').read_text()
    print(f"File created: {content.strip()}")
    pathlib.Path('/tmp/bassi_test_file.txt').unlink()
"""
        result = await execute_python_task(
            code=code, description="os.system test", timeout=5
        )

        # Documents that os.system works
        assert result["success"] is True
        assert "File created: OS system test" in result["stdout"]

    @pytest.mark.asyncio
    async def test_network_access(self):
        """Test that code can make network connections.

        SECURITY WARNING: Code can make HTTP requests, send data externally.
        """
        code = """
import socket
# Test basic socket creation (doesn't actually connect)
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
print("Socket created successfully")
sock.close()
print("Network access allowed")
"""
        result = await execute_python_task(
            code=code, description="Network test", timeout=5
        )

        # Documents that network access works
        assert result["success"] is True
        assert "Socket created successfully" in result["stdout"]

    @pytest.mark.asyncio
    async def test_environment_variable_access(self):
        """Test that code can read environment variables."""
        code = """
import os
# Read environment variables
home = os.environ.get('HOME', 'not set')
path = os.environ.get('PATH', 'not set')
print(f"HOME={home}")
print(f"PATH={path}")
print(f"Total env vars: {len(os.environ)}")
"""
        result = await execute_python_task(
            code=code, description="Env var test", timeout=5
        )

        # Documents that env var access works
        assert result["success"] is True
        assert "HOME=" in result["stdout"]
        assert "PATH=" in result["stdout"]

    @pytest.mark.asyncio
    async def test_memory_consumption_large_allocation(self):
        """Test that code can allocate large amounts of memory.

        Note: This test documents behavior, doesn't prevent memory bombs.
        """
        code = """
# Allocate 100MB of memory
data = bytearray(100 * 1024 * 1024)  # 100 MB
print(f"Allocated: {len(data) / 1024 / 1024:.1f} MB")
del data
print("Memory freed")
"""
        result = await execute_python_task(
            code=code, description="Memory test", timeout=10
        )

        # Documents that large allocations work (no memory limit)
        assert result["success"] is True
        assert "Allocated: 100.0 MB" in result["stdout"]

    @pytest.mark.asyncio
    async def test_infinite_loop_with_timeout(self):
        """Test that infinite loops are killed by timeout."""
        code = """
# Infinite loop
while True:
    pass
print("This should never print")
"""
        result = await execute_python_task(
            code=code, description="Infinite loop test", timeout=2
        )

        # Timeout kills the process
        assert result["success"] is False
        assert "timed out" in result["stderr"].lower()
        assert result["exit_code"] == -1

    @pytest.mark.asyncio
    async def test_symlink_creation(self):
        """Test that code can create symlinks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            target = tmpdir_path / "target.txt"
            target.write_text("Target content")

            code = f"""
from pathlib import Path
import os

target = Path("{target}")
link = Path("{tmpdir_path}") / "link.txt"

# Create symlink
os.symlink(target, link)
print(f"Symlink created: {{link}}")
print(f"Link exists: {{link.exists()}}")
print(f"Content via link: {{link.read_text()}}")
"""
            result = await execute_python_task(
                code=code,
                description="Symlink test",
                working_dir=tmpdir,
                timeout=5,
            )

            # Documents that symlinks can be created
            assert result["success"] is True
            assert "Symlink created:" in result["stdout"]
            assert "Content via link: Target content" in result["stdout"]


# ============================================================================
# EDGE CASE TESTS
# ============================================================================


class TestTaskAutomationEdgeCases:
    """Edge case tests for corner cases and error conditions."""

    @pytest.mark.asyncio
    async def test_working_dir_relative_path(self):
        """Test that relative paths are resolved correctly."""
        code = """
import os
print(f"CWD: {os.getcwd()}")
"""
        # Pass relative path
        result = await execute_python_task(
            code=code, description="Relative path test", working_dir=".", timeout=5
        )

        assert result["success"] is True
        # Should resolve to absolute path
        assert "CWD:" in result["stdout"]

    @pytest.mark.asyncio
    async def test_working_dir_with_tilde(self):
        """Test that ~ is expanded to home directory."""
        code = """
import os
from pathlib import Path
cwd = Path.cwd()
home = Path.home()
print(f"CWD starts with HOME: {str(cwd).startswith(str(home))}")
"""
        result = await execute_python_task(
            code=code,
            description="Tilde expansion test",
            working_dir="~",
            timeout=5,
        )

        assert result["success"] is True
        # ~ should be expanded
        assert "CWD starts with HOME: True" in result["stdout"]

    @pytest.mark.asyncio
    async def test_very_long_output(self):
        """Test handling of large stdout output."""
        code = """
# Generate 10KB of output
for i in range(500):
    print(f"Line {i}: " + "x" * 100)
print("DONE")
"""
        result = await execute_python_task(
            code=code, description="Long output test", timeout=5
        )

        assert result["success"] is True
        # All output should be captured
        assert "Line 0:" in result["stdout"]
        assert "Line 499:" in result["stdout"]
        assert "DONE" in result["stdout"]

    @pytest.mark.asyncio
    async def test_unicode_in_output(self):
        """Test handling of Unicode characters in output."""
        code = """
print("Hello 世界 🌍")
print("Emoji: 🎉 🚀 💻")
print("Math: ∑ ∫ √ π")
"""
        result = await execute_python_task(
            code=code, description="Unicode test", timeout=5
        )

        assert result["success"] is True
        assert "世界" in result["stdout"]
        assert "🌍" in result["stdout"]
        assert "∑" in result["stdout"]

    @pytest.mark.asyncio
    async def test_stderr_with_exit_code_zero(self):
        """Test that stderr output doesn't make task fail if exit code is 0."""
        code = """
import sys
print("Normal output to stdout")
print("Warning to stderr", file=sys.stderr)
print("More stdout")
"""
        result = await execute_python_task(
            code=code, description="Stderr test", timeout=5
        )

        # Exit code 0 means success even with stderr
        assert result["success"] is True
        assert result["exit_code"] == 0
        assert "Normal output to stdout" in result["stdout"]
        assert "Warning to stderr" in result["stderr"]

    @pytest.mark.asyncio
    async def test_code_with_null_bytes(self):
        """Test handling of code containing null bytes."""
        code = "print('Before')\nprint('test\\x00null')\nprint('After')"

        result = await execute_python_task(
            code=code, description="Null byte test", timeout=5
        )

        # Python handles null bytes in strings
        assert result["success"] is True
        assert "Before" in result["stdout"]
        assert "After" in result["stdout"]

    @pytest.mark.asyncio
    async def test_binary_output_to_stdout(self):
        """Test handling of binary data written to stdout."""
        code = """
import sys
# Write text
print("Text line")
# Attempt binary write (will fail or encode)
sys.stdout.buffer.write(b"\\x00\\x01\\x02\\xff")
sys.stdout.flush()
print("After binary")
"""
        result = await execute_python_task(
            code=code, description="Binary output test", timeout=5
        )

        # Should handle with errors="replace"
        assert "Text line" in result["stdout"]

    @pytest.mark.asyncio
    async def test_process_spawns_child_background(self):
        """Test cleanup when process spawns child processes."""
        code = """
import subprocess
import os

# Spawn a background process (sleep in background)
subprocess.Popen(['sleep', '1'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print("Spawned background process")
print("Parent exiting")
"""
        result = await execute_python_task(
            code=code, description="Background process test", timeout=5
        )

        # Parent process completes successfully
        assert result["success"] is True
        assert "Parent exiting" in result["stdout"]
        # Note: Background process may still be running (no cleanup)


# ============================================================================
# WRAPPER FUNCTION TESTS - task_automation_execute_python
# ============================================================================


class TestTaskAutomationWrapper:
    """Tests for the @tool wrapper function task_automation_execute_python."""

    @pytest.mark.asyncio
    async def test_wrapper_no_code_provided(self):
        """Test wrapper with empty code argument."""
        from bassi.mcp_servers.task_automation_server import (
            task_automation_execute_python,
        )

        result = await task_automation_execute_python({"code": ""})

        assert "content" in result
        assert result["content"][0]["type"] == "text"
        assert "Error: No code provided" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_wrapper_success_formatting(self):
        """Test wrapper formats successful execution correctly."""
        from bassi.mcp_servers.task_automation_server import (
            task_automation_execute_python,
        )

        result = await task_automation_execute_python(
            {"code": "print('Hello')", "description": "Test task"}
        )

        content = result["content"][0]["text"]
        assert "✓" in content  # Success checkmark
        assert "Test task" in content
        assert "Execution time:" in content
        assert "Output:" in content
        assert "Hello" in content

    @pytest.mark.asyncio
    async def test_wrapper_failure_formatting(self):
        """Test wrapper formats failed execution correctly."""
        from bassi.mcp_servers.task_automation_server import (
            task_automation_execute_python,
        )

        result = await task_automation_execute_python(
            {"code": "raise ValueError('test error')", "description": "Failing task"}
        )

        content = result["content"][0]["text"]
        assert "✗" in content  # Failure X
        assert "Failing task" in content
        assert "Exit code:" in content
        assert "Execution time:" in content
        assert "Error:" in content
        assert "ValueError" in content

    @pytest.mark.asyncio
    async def test_wrapper_no_output_message(self):
        """Test wrapper shows 'No output' when stdout is empty."""
        from bassi.mcp_servers.task_automation_server import (
            task_automation_execute_python,
        )

        result = await task_automation_execute_python({"code": "x = 1 + 1"})

        content = result["content"][0]["text"]
        assert "No output" in content

    @pytest.mark.asyncio
    async def test_wrapper_no_error_message(self):
        """Test wrapper shows 'No error message' when stderr is empty."""
        from bassi.mcp_servers.task_automation_server import (
            task_automation_execute_python,
        )

        # Code that fails with exit code but no stderr
        result = await task_automation_execute_python(
            {"code": "import sys\nsys.exit(1)"}
        )

        content = result["content"][0]["text"]
        assert "No error message" in content

    @pytest.mark.asyncio
    async def test_wrapper_default_description(self):
        """Test wrapper uses default description when not provided."""
        from bassi.mcp_servers.task_automation_server import (
            task_automation_execute_python,
        )

        result = await task_automation_execute_python({"code": "print('test')"})

        content = result["content"][0]["text"]
        assert "Python task" in content  # Default description

    @pytest.mark.asyncio
    async def test_wrapper_custom_timeout(self):
        """Test wrapper respects custom timeout parameter."""
        from bassi.mcp_servers.task_automation_server import (
            task_automation_execute_python,
        )

        result = await task_automation_execute_python(
            {"code": "import time\ntime.sleep(10)", "timeout": 1}
        )

        content = result["content"][0]["text"]
        assert "timed out" in content.lower()

    @pytest.mark.asyncio
    async def test_wrapper_custom_working_dir(self):
        """Test wrapper respects custom working_dir parameter."""
        from bassi.mcp_servers.task_automation_server import (
            task_automation_execute_python,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            result = await task_automation_execute_python(
                {
                    "code": "import os; print(os.getcwd())",
                    "working_dir": tmpdir,
                }
            )

            content = result["content"][0]["text"]
            assert tmpdir in content
