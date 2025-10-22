# Architecture Simplification - Bash-Only Tools

## What Changed

Removed the separate `file_search` tool completely. Now **everything is done via bash commands**.

This simplifies the architecture significantly and gives the agent more flexibility.

## Before (Two Tools)

```python
# Agent had two tools
self.tools = {
    "bash": bash_tool,
    "file_search": file_search_tool,  # Separate tool for file search
}
```

Agent would use:
- `file_search` tool with pattern parameter
- `bash` tool for other commands

## After (Bash Only)

```python
# Agent has only bash tool
self.tools = {
    "bash": bash_tool,  # Everything via bash!
}
```

Agent now uses bash for everything:
- `fd '*.py'` - Fast file search
- `rg 'pattern'` - Fast content search
- `find . -name '*.txt'` - Classic file search
- `grep -r 'text'` - Classic content search
- Any other Unix command

## Benefits

### 1. Simpler Architecture
- **One tool** instead of two
- Less code to maintain
- Cleaner agent implementation
- No special-case handling for file search

### 2. More Flexibility
Agent can now use:
- Any Unix tool (fd, rg, find, grep, awk, sed, etc.)
- Complex pipelines (e.g., `fd '*.py' | xargs grep 'pattern'`)
- Custom combinations
- Shell features (wildcards, pipes, redirects)

### 3. More Transparent
- User sees exact bash commands being executed
- No abstraction hiding what's happening
- Easy to reproduce commands manually
- Better debugging

### 4. Smarter Agent
Instead of being limited to a fixed file_search API, the agent can:
- Choose the best tool for each situation
- Combine multiple commands
- Use advanced Unix features
- Adapt based on what's available

## Files Removed

- `bassi/tools/file_tool_fast.py` - Fast Unix-based file search
- `bassi/tools/file_tool_slow_backup.py` - Old Python implementation
- `tests/test_file_tool.py` - File tool tests
- `bassi/agent_streaming.py` - Duplicate of agent.py (was development leftover)
- `test_streaming.py` - Test for unused agent_streaming.py
- `bassi/agent_old_backup.py` - Old non-streaming version
- `PERFORMANCE_UPGRADE.md` - No longer relevant

## Files Modified

1. **bassi/agent.py** - Removed file_search tool (this is the ONLY agent file now)
   - Updated SYSTEM_PROMPT to mention bash-only approach
   - Removed file_search from tools registry
   - Removed file_search result display code

2. **bassi/tools/__init__.py** - Only exports bash_tool now

3. **tests/test_agent.py** - Updated to test only bash tool

4. **README.md** - Updated documentation

5. **STREAMING_FEATURES.md** - Updated examples

## System Prompt Update

The agent now knows it should use bash commands for file operations:

```
You have access to:
- bash: Execute shell commands (use fd/rg for fast file search)

Available Unix tools:
- fd: Fast file search (fd pattern)
- rg: Fast content search (rg pattern)
- find: Classic file search (find . -name pattern)
- grep: Classic content search (grep -r pattern)
```

## Example Usage

### Before
```
User: Find all Python files
Agent: Uses file_search tool with pattern=".py"
```

### After
```
User: Find all Python files
Agent: Uses bash with command="fd '\\.py$'"
```

The agent can now choose the best approach:
- Fast search: `fd '\\.py$'`
- With content: `rg --files-with-matches 'import'`
- Complex: `find . -name '*.py' -newer somefile.txt`
- With processing: `fd '\.py$' | wc -l`

## Quality Assurance

All checks pass:
- ✅ **20 tests passed** (1 skipped)
- ✅ **Black** - Code formatting
- ✅ **Ruff** - Linting
- ✅ **Mypy** - Type checking

## Philosophy

This change aligns with the **Black Box Design** principle:
- Simple, clear interface (just bash)
- Maximum flexibility
- No unnecessary abstraction
- Direct access to powerful Unix tools

**Result: Simpler architecture, more powerful agent! 🚀**
