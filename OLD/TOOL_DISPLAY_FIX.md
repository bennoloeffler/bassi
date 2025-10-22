# Tool Display Fix

## Issue
Tool results were displaying the raw nested structure instead of extracting the actual text content.

**Before:**
```
╭────────────── ✅ Tool Result ──────────────╮
│ [{'type': 'text', 'text': 'Exit Code: 0   │
│ Success: True\n\nSTDOUT:\n...'}]          │
│ ... (truncated)                            │
╰────────────────────────────────────────────╯
```

**After:**
```
╭────────────── ✅ Tool Result ──────────────╮
│ Exit Code: 0                               │
│ Success: True                              │
│                                            │
│ STDOUT:                                    │
│ .                                          │
│ ├── BUG_FIX_SUMMARY.md                     │
│ ├── bassi                                  │
│ │   ├── agent.py                           │
│ ... (truncated)                            │
╰────────────────────────────────────────────╯
```

## Root Cause
The Claude Agent SDK returns tool results in a nested structure:
```python
content = [{'type': 'text', 'text': 'actual output here'}]
```

The display code was using `str(result_content)` which converted the entire list to a string, showing the Python representation instead of extracting the text.

## Solution
Added intelligent content extraction in `_display_message()`:

```python
if isinstance(result_content, list):
    # Extract text from [{'type': 'text', 'text': '...'}] format
    text_parts = []
    for item in result_content:
        if isinstance(item, dict) and "text" in item:
            text_parts.append(item["text"])
        else:
            text_parts.append(str(item))
    result_content = "\n".join(text_parts)
else:
    result_content = str(result_content)
```

This handles:
1. **List of dicts** with 'text' key - extracts the text value
2. **Other list items** - converts to string
3. **Non-list content** - converts directly to string

## Examples

### Bash Tool Result
```
╭────────────── ✅ Tool Result ──────────────╮
│ Exit Code: 0                               │
│ Success: True                              │
│                                            │
│ STDOUT:                                    │
│ .rwxr-xr-x  690 benno check_clean_ui.py   │
│ .rwxr-xr-x 2.3k benno check_color.py      │
│ .rw-r--r--  860 benno test_chat.py        │
╰────────────────────────────────────────────╯
```

### Web Search Tool Result
```
╭────────────── ✅ Tool Result ──────────────╮
│ Search Results for: latest Python version │
│                                            │
│ 1. Python documentation by version        │
│    URL: https://www.python.org/doc/...    │
│    Python 3.12.4, documentation released  │
│    on 6 June 2024...                      │
╰────────────────────────────────────────────╯
```

## Testing
- ✅ Tested with `tree -L 2` command
- ✅ Tested with web search
- ✅ All quality checks pass
- ✅ Clean, readable output

## Files Changed
- `bassi/agent.py` - Updated `_display_message()` method to extract text from nested content structures
