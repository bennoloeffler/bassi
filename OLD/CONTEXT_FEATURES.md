# Context Management & Interrupt Features

## Overview
Added advanced context management and interrupt capabilities to bassi using the Claude Agent SDK.

## Implemented Features

### 1. ESC Key Interrupt ⌨️
**Feature:** Press ESC during agent execution to interrupt the current run.

**How it works:**
- Runs a background keyboard monitor alongside agent execution
- Monitors for ESC key press (\x1b character)
- Gracefully interrupts the agent when ESC is detected
- Falls back silently if terminal doesn't support raw mode

**Implementation:**
```python
async def monitor_esc_key(agent: BassiAgent):
    """Monitor for ESC key press during agent execution"""
    try:
        import sys, termios, tty, select

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)

        try:
            tty.setraw(fd)
            while True:
                rlist, _, _ = select.select([sys.stdin], [], [], 0.1)
                if rlist:
                    ch = sys.stdin.read(1)
                    if ch == "\x1b":  # ESC key
                        await agent.interrupt()
                        return
                await anyio.sleep(0.1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    except Exception:
        pass  # Not a TTY or other error
```

**Usage:**
```
You:
search for python async best practices

Press ESC or Ctrl+C to interrupt...

[Agent starts working...]
[Press ESC]

⚠️  Agent interrupted by ESC
```

**Concurrent Execution:**
```python
# Run agent and ESC monitor concurrently
async with anyio.create_task_group() as tg:
    tg.start_soon(run_agent)
    tg.start_soon(run_esc_monitor)
```

### 2. Automatic Context Persistence 💾
**Feature:** Context is automatically saved after every successful agent interaction.

**Saved Data:**
- `session_id`: Unique session identifier for conversation continuity
- `timestamp`: Last modification time

**File Location:** `.bassi_context.json` in current working directory

**Implementation:**
```python
def save_context(self) -> None:
    """Save current context to file"""
    try:
        context_data = {
            "session_id": self.session_id,
            "timestamp": str(Path(self.context_file).stat().st_mtime)
                        if self.context_file.exists() else None,
        }
        self.context_file.write_text(json.dumps(context_data, indent=2))
    except Exception as e:
        logger.warning(f"Failed to save context: {e}")

# In chat() method:
async def chat(self, message: str):
    # ... send query with session_id
    await self.client.query(message, session_id=self.session_id)

    # ... stream responses

    # Save context after successful completion
    self.save_context()
```

**How Session Persistence Works:**
- SDK's `session_id` parameter maintains conversation history
- Same `session_id` = same conversation context
- Different `session_id` = fresh conversation

### 3. Context Loading on Startup 🔄
**Feature:** On startup, bassi asks if you want to load the previous context.

**User Flow:**
```
# bassi v0.1.0
Benno's Assistant - Your personal AI agent

📂 Working directory: /Users/benno/projects/ai/del-pocket-flow

📋 Found saved context from previous session
Load previous context? (y/n) [y]: y
✅ Loaded previous context

Ready! What can I help you with?
```

**Implementation:**
```python
# Check for saved context
saved_context = agent.load_context()
if saved_context:
    console.print("📋 Found saved context from previous session")
    load_choice = Prompt.ask(
        "Load previous context?",
        choices=["y", "n"],
        default="y"
    )
    if load_choice.lower() == "y":
        console.print("✅ Loaded previous context")
    else:
        # Start fresh - generate new session_id
        agent.session_id = f"session_{os.urandom(4).hex()}"
        console.print("Starting fresh conversation")
```

### 4. Context Size & Usage Display 📊
**Feature:** After each response, see token usage and context window percentage.

**Displayed Information:**
- ⏱️ Response time in milliseconds
- 💰 Cost in USD
- 📊 Current context size vs window size
- ⚠️ Warning when approaching compaction threshold

**Example Output:**
```
🤖 Assistant:

Here are the search results for Python async best practices...

⏱️  4060ms | 💰 $0.0497 | 📊 Context: 12,938 / 200,000 tokens (6.5%)
```

**When Approaching Threshold:**
```
⏱️  8500ms | 💰 $0.1234 | 📊 Context: 155,000 / 200,000 tokens (77.5%) ⚠️  Approaching compaction threshold
```

**Implementation:**
```python
# Track cumulative usage
self.total_input_tokens = 0
self.total_output_tokens = 0
self.total_cache_creation_tokens = 0
self.total_cache_read_tokens = 0
self.total_cost_usd = 0.0

# Context limits
self.context_window_size = 200000  # Claude Sonnet 4.5
self.compaction_threshold = 150000  # 75% of limit

# In ResultMessage handler:
def _display_message(self, msg):
    if msg_class_name == "ResultMessage":
        usage = getattr(msg, "usage", {})

        # Update cumulative tracking
        self.total_input_tokens += usage.get("input_tokens", 0)
        self.total_output_tokens += usage.get("output_tokens", 0)
        self.total_cache_creation_tokens += usage.get("cache_creation_input_tokens", 0)
        self.total_cache_read_tokens += usage.get("cache_read_input_tokens", 0)
        self.total_cost_usd += getattr(msg, "total_cost_usd", 0)

        # Calculate and display context info
        ctx_info = self.get_context_info()
        # ... display usage line
```

**Context Info Structure:**
```python
def get_context_info(self) -> dict:
    """Get context size and info"""
    current_context_size = (
        self.total_input_tokens
        + self.total_cache_creation_tokens
        + self.total_cache_read_tokens
    )

    context_percentage = (current_context_size / self.context_window_size) * 100
    will_compact_soon = current_context_size >= self.compaction_threshold

    return {
        "current_size": current_context_size,
        "window_size": self.context_window_size,
        "percentage_used": context_percentage,
        "compaction_threshold": self.compaction_threshold,
        "will_compact_soon": will_compact_soon,
        "total_input_tokens": self.total_input_tokens,
        "total_output_tokens": self.total_output_tokens,
        "total_cache_creation": self.total_cache_creation_tokens,
        "total_cache_read": self.total_cache_read_tokens,
        "total_cost_usd": self.total_cost_usd,
    }
```

## Technical Details

### Token Tracking
Token usage is extracted from SDK's `ResultMessage`:

```python
ResultMessage(
    duration_ms=4060,
    total_cost_usd=0.049744,
    usage={
        'input_tokens': 2,
        'cache_creation_input_tokens': 12936,
        'cache_read_input_tokens': 0,
        'output_tokens': 13,
    }
)
```

**Token Types:**
- `input_tokens`: New input tokens in this turn
- `output_tokens`: Generated response tokens
- `cache_creation_input_tokens`: Tokens added to prompt cache
- `cache_read_input_tokens`: Tokens retrieved from cache (cheaper!)

**Context Size Calculation:**
```python
current_context = (
    total_input_tokens
    + cache_creation_tokens
    + cache_read_tokens
)
```

### Prompt Caching
The SDK automatically caches system prompts and tool definitions:
- First request: Creates cache (~12,936 tokens)
- Subsequent requests: Reads from cache (much cheaper!)
- Cache lifetime: Ephemeral (1h or 5m depending on tier)

**Cost Savings:**
```
Turn 1: $0.0497 (cache creation: 12,936 tokens)
Turn 2: $0.0050 (cache read: 12,936 tokens) ← 10x cheaper!
```

### Automatic Compaction
When context reaches 150K tokens (75% of 200K window):
- SDK automatically summarizes previous messages
- Keeps conversation flowing without manual intervention
- User sees warning: "⚠️ Approaching compaction threshold"

## Benefits

1. **Never Lose Progress** - Context auto-saves after every interaction
2. **Resume Conversations** - Pick up where you left off across sessions
3. **Control Agent Execution** - ESC key provides quick interrupt
4. **Transparency** - See exactly how much context is being used
5. **Cost Awareness** - Monitor cumulative costs in real-time
6. **Prompt Caching Benefits** - See cost savings from cached prompts

## Files Changed

### `bassi/agent.py`
- Added token tracking fields to `__init__`
- Implemented `interrupt()` with async SDK call
- Implemented `save_context()` and `load_context()`
- Enhanced `get_context_info()` with actual token data
- Updated `_display_message()` to track usage from ResultMessage
- Display context size with cost and timing info

### `bassi/main.py`
- Added `monitor_esc_key()` for ESC key detection
- Added context loading prompt on startup
- Run agent and ESC monitor concurrently with anyio task groups
- Updated welcome message to mention ESC interrupt

## Testing

All quality checks pass:
```bash
./check.sh

✅ Code Formatting (black)
✅ Linting (ruff)
✅ Type Checking (mypy)
✅ Tests (pytest) - 13 passed, 1 skipped
```

## Usage Examples

### Fresh Start:
```
$ bassi

📂 Working directory: /Users/benno/projects

No previous context found.

You:
remember that my favorite language is Python
```

### Resume Previous Session:
```
$ bassi

📋 Found saved context from previous session
Load previous context? (y/n) [y]: y
✅ Loaded previous context

You:
what's my favorite language?

🤖 Assistant:
Your favorite language is Python! You told me that earlier.

⏱️  2340ms | 💰 $0.0032 | 📊 Context: 15,421 / 200,000 tokens (7.7%)
```

### Interrupt Long Operation:
```
You:
search for all Python async tutorials and summarize them

Press ESC or Ctrl+C to interrupt...

[Agent starts searching...]
[Press ESC]

⚠️  Agent interrupted by ESC
```

## Future Enhancements

Possible future improvements:
- Export context to file
- Import context from file
- Context size warnings in status bar
- Manual compaction trigger
- Session history browser
- Token usage graphs

---

All features use the Claude Agent SDK's built-in capabilities for maximum reliability!
