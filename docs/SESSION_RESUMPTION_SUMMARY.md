# Session Resumption - Quick Reference Guide

## What's Saved in .bassi_context.json

```json
{
  "session_id": "a92190a4-290e-4182-be1b-56066ccccef4",
  "timestamp": 1761080958.621,
  "last_updated": "2025-10-21 23:09:18"
}
```

**Key Data**:
- `session_id`: UUID from Claude Agent SDK (uniquely identifies the conversation)
- `timestamp`: Unix timestamp for programmatic use
- `last_updated`: Human-readable datetime

## How Session Resumption Works

### 1. Save Process
- **When**: After each successful `agent.chat()` call
- **Where**: `bassi/agent.py` → `save_context()` (lines 145-158)
- **What**: Stores current session_id and timestamp to `.bassi_context.json`

### 2. Load Process
- **When**: Application startup in `main_async()`
- **Where**: `bassi/main.py` (lines 230-274)
- **How**:
  1. Check if `.bassi_context.json` exists
  2. Parse JSON file
  3. Prompt user: "Load previous context? [y/n]"
  4. If yes → extract `session_id` and pass to BassiAgent

### 3. Resume Process
- **Where**: `bassi/agent.py` → `BassiAgent.__init__()` (line 108)
- **How**: Pass `resume_session_id` to `ClaudeAgentOptions(resume=...)`
- **Result**: Claude Agent SDK handles session resumption internally

## Information Available on Session Resume

### From .bassi_context.json
- Session ID
- Last activity timestamp
- How long ago the session was created

### From SDK (ResultMessage)
After resuming and interacting, ResultMessage provides:

| Field | Value | Use Case |
|-------|-------|----------|
| `session_id` | UUID | Verify session resumed correctly |
| `num_turns` | Integer | Show conversation length |
| `duration_ms` | Integer | Performance tracking |
| `usage` dict | Token counts | Display context usage |
| `total_cost_usd` | Float | Show cost |

## What Can Be Displayed When Resuming

**Example UI Summary**:
```
📋 Session Resumed
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Session ID: a92190a4-290e-4182-be1b-56066ccccef4
Last Activity: 2025-10-21 23:09:18 (2 hours ago)
Total Interactions: 12
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total Tokens Used: 45,234
Total Cost: $0.23
Context Usage: 22,451 / 200,000 tokens (11%)
```

## Important Limitations

⚠️ **SDK Limitation**: Cannot retrieve historical messages from SDK API
- ❌ No API to get list of previous messages
- ❌ No API to access previous tool calls
- ✅ BUT: Claude has full internal access to history for context awareness

This is by design - the SDK focuses on session continuity, not message history replay.

## Code Flow Diagram

```
Application Startup
    ↓
.bassi_context.json exists?
    ↓ YES
Parse JSON → Extract session_id
    ↓
Ask User: "Load previous context?"
    ↓ YES
Pass session_id to BassiAgent(resume_session_id=...)
    ↓
ClaudeAgentOptions(resume=session_id)
    ↓
SDK Handles: Connect to existing session
    ↓
First interaction → ResultMessage(session_id=..., num_turns=...)
    ↓
Display summary using:
  - Timestamp from file
  - session_id from file
  - num_turns from ResultMessage
  - usage/cost from ResultMessage
    ↓
save_context() → Update .bassi_context.json
```

## Key Files

| File | Purpose | Lines |
|------|---------|-------|
| `bassi/main.py` | Load context, prompt user, pass to agent | 230-282 |
| `bassi/agent.py` → `save_context()` | Save session data | 145-158 |
| `bassi/agent.py` → `load_context()` | Load session data (optional) | 160-175 |
| `bassi/agent.py` → `chat()` | Capture session_id from ResultMessage | 244-250 |
| `bassi/agent.py` → `get_context_info()` | Get context usage stats | 177-204 |

## SDK Integration Points

1. **ClaudeAgentOptions**: Set `resume=session_id` (line 108 in agent.py)
2. **ResultMessage**: Contains `session_id` and `num_turns` (lines 244-250)
3. **Usage tracking**: Update cumulative totals from ResultMessage (lines 466-474)

## Token/Cost Tracking

- Context Window: 200,000 tokens (Claude Sonnet 4.5)
- Compaction Threshold: 150,000 tokens (75% of window)
- BassiAgent tracks cumulative usage:
  - `total_input_tokens`
  - `total_output_tokens`
  - `total_cache_creation_tokens`
  - `total_cache_read_tokens`
  - `total_cost_usd`

Access via: `agent.get_context_info()` method

## Non-Interactive Mode

When running in non-interactive mode (piped input):
- Automatically loads and resumes session
- No user prompt
- Useful for scripts and automation

(See main.py lines 265-271)

---

**For detailed analysis**, see: `SESSION_RESUMPTION_ANALYSIS.md`
