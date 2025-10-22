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
