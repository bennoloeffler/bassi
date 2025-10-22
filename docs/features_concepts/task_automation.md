# Task Automation

**Status**: Implemented
**Version**: 1.0
**Last Updated**: 2025-01-22

## Overview

The Task Automation feature enables Bassi to execute Python code for repeatable automation tasks. This allows Claude to write and execute custom Python scripts on-demand to solve batch processing problems that would be tedious to do manually.

## Purpose

Enable autonomous execution of Python code for tasks like:
- **Image Processing**: Batch compress, resize, convert image formats
- **File Organization**: Batch rename, sort by metadata, organize by date
- **Data Processing**: CSV/JSON transformation, data cleaning, format conversion
- **Text Processing**: Batch find/replace, encoding conversion, text extraction
- **Automation**: Any repeatable task that benefits from Python's ecosystem

## Architecture

### How It Works with Agent SDK

```
┌─────────────────────────────────────────────────────────────┐
│                    BASSI ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  User ──► CLI ──► BassiAgent ──► Claude API                │
│                        │                                     │
│                        ├──► MCP Servers (SDK)               │
│                        │    ├─ bash_server.py               │
│                        │    ├─ web_search_server.py         │
│                        │    └─ task_automation_server.py    │
│                        │                                     │
│                        └──► External MCP Servers            │
│                             ├─ ms365 (subprocess)            │
│                             └─ playwright (subprocess)       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Execution Flow

1. **User Request**: "Compress all PNG images in ~/Pictures/vacation/"
2. **Claude Analysis**: Claude determines it needs to execute Python code
3. **Tool Selection**: Claude chooses `mcp__task_automation__execute_python` tool
4. **Code Generation**: Claude writes Python code using PIL/Pillow
5. **Agent SDK Routing**: Routes tool call to `task_automation_server.py`
6. **Execution**: MCP server executes code in isolated subprocess
7. **Results**: Stdout, stderr, exit code returned to Agent SDK
8. **Response**: Claude synthesizes human-friendly response with results

### Why Subprocess Isolation?

The task automation server executes Python code in a **subprocess** rather than `eval()` for critical safety reasons:

- **Process Isolation**: Errors or infinite loops don't crash Bassi
- **Resource Limits**: Can enforce CPU/memory/timeout limits
- **Clean Environment**: Fresh Python interpreter for each execution
- **Signal Handling**: Can interrupt/kill hanging processes
- **Security**: Reduced risk from malicious/buggy code

## MCP Server Implementation

**File**: `bassi/mcp_servers/task_automation_server.py`

### Tool Definition

**Tool Name**: `execute_python`

**Parameters**:
- `code` (required): Python code to execute
- `description` (required): Human-readable task description for logging
- `working_dir` (optional): Directory to execute in (defaults to current working directory)
- `timeout` (optional): Maximum execution time in seconds (default: 300 = 5 minutes)

**Returns**:
```python
{
    "success": bool,           # True if exit code 0
    "stdout": str,             # Standard output
    "stderr": str,             # Standard error
    "exit_code": int,          # Process exit code
    "execution_time": float    # Actual time taken (seconds)
}
```

### Available Libraries

The following libraries are pre-installed and available in automation scripts:

**Image Processing**:
- `PIL` / `Pillow` - Image manipulation (resize, compress, convert)

**Data Processing**:
- `pandas` - DataFrames, CSV, Excel processing
- `numpy` - Numerical operations

**Standard Library**:
- `pathlib` - Modern file path handling
- `json` - JSON processing
- `csv` - CSV file handling
- `re` - Regular expressions
- `os`, `shutil` - File operations
- `datetime` - Date/time handling

### Safety Features

1. **Subprocess Isolation**
   - Runs in separate Python process
   - Parent process unaffected by crashes
   - Clean environment for each execution

2. **Timeout Enforcement**
   - Default: 5 minutes
   - Customizable per execution
   - Process killed if exceeded

3. **Working Directory Restrictions**
   - Defaults to current working directory
   - Can be restricted to specific paths
   - No access outside working directory by default

4. **Resource Monitoring**
   - Execution time tracked
   - Output size limits (prevent memory exhaustion)
   - Exit code monitoring

5. **Error Handling**
   - Syntax errors caught and reported
   - Runtime errors captured in stderr
   - Timeout errors clearly indicated

## Use Cases

### UC-1: Batch Image Compression

**User Request**: "Compress all PNG images in ~/Pictures/vacation/ to 70% quality"

**Claude's Action**:
1. Generates Python code using PIL
2. Calls `execute_python` tool with code
3. Code finds all PNG files
4. Compresses each with PIL at 70% quality
5. Reports results (count, size reduction)

**Example Code** (generated by Claude):
```python
from PIL import Image
from pathlib import Path

input_dir = Path.home() / "Pictures" / "vacation"
images = list(input_dir.glob("*.png"))

total_before = 0
total_after = 0

for img_path in images:
    img = Image.open(img_path)

    # Get original size
    total_before += img_path.stat().st_size

    # Compress and save
    img.save(img_path, "PNG", optimize=True, quality=70)

    # Get new size
    total_after += img_path.stat().st_size

print(f"Processed {len(images)} images")
print(f"Before: {total_before / 1024 / 1024:.1f} MB")
print(f"After: {total_after / 1024 / 1024:.1f} MB")
print(f"Saved: {(total_before - total_after) / 1024 / 1024:.1f} MB ({100 * (total_before - total_after) / total_before:.1f}%)")
```

**User Experience**:
```
You: compress all PNG images in ~/Pictures/vacation/ to 70% quality

🤖 I'll compress those images for you...

[Executing Python task: Compress vacation images]
Processed 127 images
Before: 245.3 MB
After: 89.1 MB
Saved: 156.2 MB (63.7%)

All images compressed successfully! Saved 156 MB of disk space.
```

---

### UC-2: Batch File Renaming

**User Request**: "Rename all JPG files in Downloads to include their creation date"

**Claude's Action**:
1. Generates Python code using pathlib and datetime
2. Iterates through JPG files
3. Reads file creation time
4. Renames files to `YYYYMMDD_original_name.jpg`

**Example Code**:
```python
from pathlib import Path
from datetime import datetime

downloads = Path.home() / "Downloads"
jpg_files = list(downloads.glob("*.jpg"))

renamed = 0
for jpg_file in jpg_files:
    # Get creation time
    ctime = jpg_file.stat().st_birthtime
    date_str = datetime.fromtimestamp(ctime).strftime("%Y%m%d")

    # New name with date prefix
    new_name = f"{date_str}_{jpg_file.name}"
    new_path = jpg_file.parent / new_name

    # Avoid overwriting
    if not new_path.exists():
        jpg_file.rename(new_path)
        renamed += 1
        print(f"Renamed: {jpg_file.name} → {new_name}")

print(f"\nRenamed {renamed} files")
```

---

### UC-3: CSV Data Transformation

**User Request**: "Convert contacts.csv to JSON format with proper structure"

**Claude's Action**:
1. Generates pandas code to read CSV
2. Transforms data structure
3. Exports as JSON

**Example Code**:
```python
import pandas as pd
import json

# Read CSV
df = pd.read_csv("contacts.csv")

# Transform to list of dicts
contacts = df.to_dict(orient="records")

# Write JSON
with open("contacts.json", "w") as f:
    json.dump(contacts, f, indent=2)

print(f"Converted {len(contacts)} contacts from CSV to JSON")
```

---

### UC-4: Extract Text from Multiple Files

**User Request**: "Extract all TODO comments from Python files in src/"

**Claude's Action**:
1. Generates code to walk directory tree
2. Finds Python files
3. Extracts lines with TODO comments
4. Saves to report file

**Example Code**:
```python
from pathlib import Path
import re

src_dir = Path("src")
todos = []

for py_file in src_dir.rglob("*.py"):
    with open(py_file) as f:
        for line_num, line in enumerate(f, 1):
            if re.search(r"#\s*TODO", line, re.IGNORECASE):
                todos.append(f"{py_file}:{line_num}: {line.strip()}")

# Write report
with open("todos.txt", "w") as f:
    f.write("\n".join(todos))

print(f"Found {len(todos)} TODO comments")
print(f"Report saved to todos.txt")
```

---

## Configuration

### Timeout Settings

Default timeout is **5 minutes** (300 seconds). This can be adjusted per execution:

```python
# Claude will specify timeout in tool call
execute_python(
    code="...",
    description="Long-running data processing",
    timeout=600  # 10 minutes
)
```

### Working Directory

By default, code executes in the **current working directory** where Bassi was launched. Claude can specify a different directory:

```python
execute_python(
    code="...",
    description="Process images",
    working_dir="/Users/benno/Pictures/vacation"
)
```

## Security Considerations

### What's Allowed

✅ File operations within working directory
✅ Standard library usage
✅ Pre-installed libraries (PIL, pandas, etc.)
✅ Read/write local files
✅ Process data

### What's Restricted

⚠️ **Network Access**: Not restricted (Python can make network calls)
⚠️ **System Calls**: Not restricted (can run subprocess commands)
⚠️ **File System**: Not restricted (can access entire file system)

### Trust Model

This feature assumes a **trusted user** environment (consistent with Bassi's `bypassPermissions` design):

- You trust Claude to write safe Python code
- You trust yourself to review what Claude is doing (verbose mode)
- You understand the risks of autonomous code execution

### Recommended Practices

1. **Use Verbose Mode**: Enable `/alles_anzeigen` to see generated code
2. **Review First**: For sensitive operations, ask Claude to show code first
3. **Limit Scope**: Be specific about which directories to process
4. **Backup Data**: Before bulk operations, ensure you have backups

## Testing

### Unit Tests

**File**: `tests/test_task_automation.py`

**Test Cases**:
1. `test_simple_print` - Basic print statement execution
2. `test_math_calculation` - Simple computation and output
3. `test_file_operations` - Read/write files in temp directory
4. `test_timeout_enforcement` - Code exceeding timeout is killed
5. `test_syntax_error` - Invalid Python code returns error
6. `test_runtime_error` - Runtime exception captured in stderr
7. `test_working_directory` - Verify code runs in specified directory

### Integration Tests

**File**: `tests/test_task_automation_integration.py`

**Scenarios**:
1. Full conversation flow with image compression
2. Error recovery (bad code, then corrected code)
3. Multi-step automation (Claude plans and executes multiple scripts)

### Running Tests

```bash
# Run all tests
uv run pytest

# Task automation tests only
uv run pytest tests/test_task_automation.py

# With verbose output
uv run pytest tests/test_task_automation.py -v

# Full quality check
./check.sh
```

## Troubleshooting

### Issue: Timeout Errors

**Symptom**: Code execution times out
**Solution**: Increase timeout parameter or optimize code

### Issue: Import Errors

**Symptom**: `ModuleNotFoundError` for expected library
**Solution**: Install library: `uv add <package>`

### Issue: File Not Found

**Symptom**: Code can't find files
**Solution**: Use absolute paths or specify `working_dir`

### Issue: Permission Denied

**Symptom**: Can't read/write files
**Solution**: Check file permissions and working directory

## Future Enhancements

1. **Sandboxing**: Restrict file system access to specific directories
2. **Network Isolation**: Option to disable network access
3. **Resource Limits**: Enforce CPU/memory limits
4. **Execution History**: Save/replay successful automation scripts
5. **Template Library**: Pre-built templates for common tasks
6. **Progress Streaming**: Real-time output during long operations
7. **Dry Run Mode**: Preview what code will do before execution

## Related Documentation

- **Architecture**: `ARCHITECTURE_OVERVIEW.md` - System architecture overview
- **MCP Servers**: `MCP_SERVER_ARCHITECTURE.md` - MCP server patterns
- **Design**: `docs/design.md` - Overall design philosophy
- **Vision**: `docs/vision.md` - Product vision (Iteration 8: Create Python scripts)

## Examples for Help Command

```
Task Automation Examples:

  Image Processing:
  > compress all PNG images in ~/Pictures/vacation/ to 70% quality
  > resize all JPG files in Downloads to 1920x1080
  > convert all HEIC photos to JPG format

  File Organization:
  > rename all files in Downloads to include their creation date
  > sort PDFs in Documents by year into subdirectories
  > find duplicate images in ~/Pictures and list them

  Data Processing:
  > convert contacts.csv to JSON format
  > merge all CSV files in data/ into one combined.csv
  > extract email addresses from all text files

  Text Processing:
  > find all TODO comments in Python files and create a report
  > replace "old_name" with "new_name" in all .md files
  > extract URLs from all HTML files

Claude will write and execute Python code to accomplish these tasks!
```

---

**Document Status**: Complete
**Next Review**: After production usage feedback
