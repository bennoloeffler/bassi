# Simple Prompt Editor - Unix-Native Design

## Overview
A clean, simple prompt editor that follows Unix conventions and terminal best practices.

## Problem Statement
Previous attempts to replicate web app UX (ChatGPT/Slack) in terminals failed because:
- Shift+Enter doesn't exist as a terminal key code (hardware limitation)
- Alt+Enter is unreliable (doesn't work on macOS Terminal)
- Hijacking Ctrl+C breaks Unix conventions
- `multiline=True` + Enter-to-submit creates confusion
- Fighting against prompt_toolkit's design patterns

## Solution
**Unix-Native Approach:**
- Single-line input by default (like bash, psql, mysql, redis-cli)
- Standard Ctrl+C to exit (SIGINT)
- `/edit` command to open $EDITOR for multiline input
- No custom key bindings - use prompt_toolkit defaults

## Key Bindings

| Key | Action | Standard |
|-----|--------|----------|
| **Enter** | Send message | ✅ Universal CLI pattern |
| **Ctrl+C** | Exit application | ✅ Unix SIGINT |
| **Ctrl+D** | Exit application | ✅ Unix EOF |
| **ESC** | Interrupt agent | ✅ During execution only |
| **Up/Down** | Navigate history | ✅ Readline standard |
| **Ctrl+R** | Reverse search | ✅ Readline standard |

## Implementation

### Core Prompt Session
`bassi/main.py:86-107`

```python
def create_prompt_session(agent=None):
    """Create a prompt_toolkit session for single-line input"""
    from prompt_toolkit.history import FileHistory

    # No custom key bindings - use standard defaults
    return PromptSession(
        history=FileHistory(os.path.expanduser("~/.bassi_history")),
        enable_history_search=True,
    )
```

**Design Decisions:**
- No `multiline=True` → avoids confusion
- No custom key bindings → uses prompt_toolkit defaults
- No Ctrl+C override → standard Unix exit signal
- History enabled → persistent across sessions

### /edit Command
`bassi/main.py:329-376`

Opens user's configured $EDITOR for complex prompts:

```python
elif command == "/edit":
    import subprocess
    import tempfile

    editor = os.environ.get("EDITOR", "vim")

    with tempfile.NamedTemporaryFile(mode="w+", suffix=".txt", delete=False) as tf:
        tf_name = tf.name

    try:
        result = subprocess.run([editor, tf_name])

        with open(tf_name) as f:
            user_input = f.read().strip()

        # Falls through to agent processing
    finally:
        os.unlink(tf_name)
```

## User Experience

### Single-Line Input (Default)
```bash
You:
list python files[Enter]
→ Sent!
```

### Multiline Input (When Needed)
```bash
You:
/edit[Enter]

# Opens vim/nano/emacs:
Create a Python script that:
1. Reads CSV files
2. Processes data
3. Generates reports

# Save and close → sent to agent
```

### Standard Exit
```bash
[Ctrl+C]
→ Exits immediately (standard Unix)
```

## Benefits

1. **Familiar** - Works like bash, psql, mysql, redis-cli
2. **Standard** - Follows Unix conventions (Ctrl+C, Ctrl+D)
3. **Simple** - No weird key combinations
4. **Powerful** - Use real editor (vim/emacs) for complex input
5. **Reliable** - No terminal compatibility issues
6. **Clean Code** - No custom key bindings, no hacks

## Files Modified

- `bassi/main.py` - Simplified prompt session, added /edit command
- `tests/test_key_bindings.py` - Updated tests for new behavior
- `UI_IMPROVEMENTS.md` - Complete rewrite of documentation

## Testing

All tests pass:
```bash
./check.sh
# ✅ 24/24 tests pass
```

Key test cases:
- Enter sends message immediately
- Ctrl+C exits with code 130 (SIGINT)
- Ctrl+D exits cleanly
- Command history persists
- /edit command works

## Design Philosophy

**Terminal-First Thinking:**
- Embrace terminal strengths (external editors!)
- Accept terminal limitations (no Shift+Enter)
- Follow Unix conventions (Ctrl+C exits)
- Keep it simple (single-line by default)

**Result:** A prompt editor that feels natural to Unix users, works reliably on all terminals, and provides power when needed through $EDITOR integration.

## Related Features

- [Command Selector](command_selector.md) - Interactive /command menu
- [Verbose Mode](verbose_mode.md) - Toggle tool visibility
- ESC key monitoring - Interrupt running agent

## References

- Implementation: `bassi/main.py:86-107` (prompt session)
- Implementation: `bassi/main.py:329-376` (/edit command)
- Tests: `tests/test_key_bindings.py`
- Documentation: `UI_IMPROVEMENTS.md`
