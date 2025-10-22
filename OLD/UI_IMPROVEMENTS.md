# UI Improvements - Simple, Unix-Native Design

## Overview
Reworked bassi's UI to provide a clean, Unix-native prompt experience with standard key bindings and /edit command for multiline input.

## Philosophy

**Terminal-First Design:**
- Single-line input by default (like bash, psql, mysql, redis-cli)
- Standard Unix key bindings (Ctrl+C exits, Enter sends)
- `/edit` command opens $EDITOR for complex multiline prompts
- No fighting against terminal limitations

## Key Bindings

| Key | Action | Standard |
|-----|--------|----------|
| **Enter** | Send message | ✅ Like every CLI tool |
| **Ctrl+C** | Exit application | ✅ Standard SIGINT |
| **Ctrl+D** | Exit application | ✅ Standard EOF |
| **ESC** | Interrupt agent | ✅ During execution only |
| **Up/Down** | Navigate history | ✅ Standard readline |
| **Ctrl+R** | Reverse search | ✅ Standard readline |

**For multiline input:** Use `/edit` command to open your $EDITOR

## Implementation

### Clean Prompt Session

**File:** `bassi/main.py:86-107`

```python
def create_prompt_session(agent=None):
    """Create a prompt_toolkit session for single-line input

    Key bindings:
    - Enter: Send message immediately
    - Ctrl+C: Exit application (standard Unix)
    - Ctrl+D: Exit application (EOF)
    - Up/Down: Navigate command history
    - Ctrl+R: Reverse search history

    For multiline input, use the /edit command to open $EDITOR
    """
    from prompt_toolkit.history import FileHistory

    # No custom key bindings - use standard prompt_toolkit defaults
    # This gives us proper Ctrl+C (exit), Enter (submit), history navigation
    return PromptSession(
        history=FileHistory(os.path.expanduser("~/.bassi_history")),
        enable_history_search=True,
    )
```

**What This Gives Us:**
- ✅ No `multiline=True` confusion
- ✅ No custom key bindings fighting the library
- ✅ Standard Ctrl+C behavior (exits app)
- ✅ Persistent command history
- ✅ Reverse search with Ctrl+R

### /edit Command for Multiline

**File:** `bassi/main.py:329-376`

Opens `$EDITOR` (vim/nano/emacs) for complex prompts:

```python
elif command == "/edit":
    import subprocess
    import tempfile

    editor = os.environ.get("EDITOR", "vim")

    with tempfile.NamedTemporaryFile(mode="w+", suffix=".txt", delete=False) as tf:
        tf_name = tf.name

    try:
        # Open editor
        result = subprocess.run([editor, tf_name])

        # Read content
        with open(tf_name) as f:
            user_input = f.read().strip()

        # Process with agent (falls through to agent processing)
    finally:
        os.unlink(tf_name)
```

**Benefits:**
- ✅ Use your familiar editor (syntax highlighting, plugins, etc.)
- ✅ Perfect for long, complex prompts
- ✅ Copy/paste works naturally
- ✅ No awkward terminal key combinations

## User Experience

### Single Line (Default)
```
You:
list python files[Enter]
→ Sent immediately!
```

### Multiline (When Needed)
```
You:
/edit[Enter]

[Opens vim/nano/emacs with:]
Create a Python script that:
1. Reads CSV files
2. Processes the data
3. Generates reports
[Save and close editor]

→ Entire multiline prompt sent to agent!
```

### Exiting
```
[Press Ctrl+C]
→ App exits immediately (standard Unix)

or

You:
/quit[Enter]
→ Clean exit
```

## Welcome Screen

```
# bassi v0.1.0
Benno's Assistant - Your personal AI agent

📂 Working directory: /Users/benno/projects/ai/del-pocket-flow

Type your request or use commands:
  • Type / to see command menu
  • Type /help for detailed help
  • Press Enter to send, /edit for multiline
  • Press ESC to interrupt agent, Ctrl+C to exit
  • Type /alles_anzeigen to toggle verbose mode
```

## Available Commands

- `/` - Show command menu
- `/help` - Detailed help
- `/config` - Show configuration
- **`/edit`** - Open $EDITOR for multiline input
- `/alles_anzeigen` - Toggle verbose mode
- `/reset` - Reset conversation
- `/quit` or `/exit` - Exit bassi

## Technical Changes

### Files Modified

**`bassi/main.py`:**
- Removed `multiline=True` from PromptSession
- Removed all custom key bindings (Alt+Enter, Ctrl+J, Ctrl+C override)
- Added `/edit` command handler
- Restored standard Ctrl+C behavior (exits app)
- Removed KeyboardInterrupt exception handling during prompt
- Updated welcome message and help text

**`tests/test_key_bindings.py`:**
- Updated Ctrl+C test to verify exit behavior
- Updated test docstrings
- All 24 tests pass

## Benefits

1. **Simple & Predictable** - Works like every other CLI tool
2. **Unix-Native** - Ctrl+C exits, Enter sends, no surprises
3. **No Terminal Hacks** - No fighting key code limitations
4. **Powerful When Needed** - Use your real editor for complex input
5. **Familiar Patterns** - bash/zsh/psql/mysql muscle memory works
6. **Clean Codebase** - No custom key bindings, no multiline confusion
7. **Standard Behavior** - Follows Unix conventions
8. **Works Everywhere** - No terminal compatibility issues

## Why This Works

**Problem with Previous Approach:**
- Tried to replicate web app UX (ChatGPT/Slack) in terminal
- Shift+Enter doesn't exist in terminals (key code limitation)
- Alt+Enter unreliable (doesn't work on macOS Terminal)
- Hijacked Ctrl+C (broke Unix conventions)
- `multiline=True` + Enter-to-submit = contradiction
- Fighting against prompt_toolkit's design

**Current Approach:**
- Accept terminal limitations
- Use terminal strengths (external $EDITOR)
- Follow Unix conventions
- Simple, clean, predictable

## Testing

All tests pass:
```bash
./check.sh
# ✅ Black formatting
# ✅ Ruff linting
# ✅ MyPy type checking
# ✅ 24/24 pytest tests pass
```

**Key Tests:**
- ✅ Enter sends message immediately
- ✅ Ctrl+C exits application (exit code 130)
- ✅ Ctrl+D exits application
- ✅ Command history persists
- ✅ /quit exits cleanly
- ✅ Empty input ignored

## Comparison: Before vs After

### Before (Broken)
```
Problems:
❌ Shift+Enter impossible (terminal limitation)
❌ Alt+Enter unreliable (doesn't work on macOS)
❌ Ctrl+C hijacked (can't exit normally)
❌ multiline=True + Enter-submit = confusion
❌ Fighting prompt_toolkit design
❌ Users getting stuck
❌ Violated Unix conventions
```

### After (Fixed)
```
Features:
✅ Enter sends (like bash/psql/mysql)
✅ Ctrl+C exits (standard Unix SIGINT)
✅ /edit for multiline (use real editor!)
✅ Standard key bindings (no hacks)
✅ Command history (Up/Down/Ctrl+R)
✅ Simple, predictable, reliable
✅ Follows Unix conventions
✅ Works on all terminals
```

## Philosophy: Terminal != Web Browser

**Terminals Are Different:**
- No Shift+Enter key codes
- No DOM/JavaScript event model
- Limited key combinations
- But: Can spawn external editors!

**Embrace Terminal Strengths:**
- Single-line by default (fast, simple)
- External $EDITOR for complex input (powerful!)
- Standard Unix signals (Ctrl+C, Ctrl+D)
- Command history (Up/Down, Ctrl+R)

**Result:** Clean, Unix-native tool that feels natural to CLI users.

---

The UI now provides a **simple, reliable, Unix-native experience**. Enter to send (like every CLI tool), /edit when you need multiline (opens your editor), Ctrl+C to exit (standard). No tricks, no hacks, just clean design.
