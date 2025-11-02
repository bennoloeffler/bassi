# Session Resumption Analysis - Documentation Index

Complete analysis of how bassi saves and loads conversation context, with focus on what information is available for UI display when resuming sessions.

## Documentation Files

### 1. **SESSION_RESUMPTION_SUMMARY.md** (Start Here)
Quick reference guide with:
- What's saved in .bassi_context.json
- How session resumption works (save/load/resume flow)
- Information available from SDK
- Example UI summary display
- Code locations and key files

**Best for**: Getting a quick overview, implementation planning

---

### 2. **SESSION_RESUMPTION_ANALYSIS.md** (Comprehensive)
In-depth technical analysis with:
- Detailed data structure of .bassi_context.json
- Line-by-line code walkthrough
- Information available from each message type (ResultMessage, SystemMessage, etc.)
- Complete session resumption flow diagram
- SDK limitations and capabilities
- Token tracking and context window management
- Non-interactive mode behavior

**Best for**: Deep understanding, feature development, troubleshooting

---

### 3. **SDK_MESSAGE_TYPES.md** (Reference)
SDK message type specifications including:
- ResultMessage: Usage stats, cost, turn count
- SystemMessage: Compaction events, initialization
- StreamEvent: Real-time text streaming
- AssistantMessage: Response content blocks
- UserMessage: User input structure
- Message flow during session resume
- Recommended UI display options
- Integration checklist

**Best for**: Understanding SDK data, building UI features, debugging messages

---

## Key Findings Summary

### What's Saved
```json
{
  "session_id": "UUID-format-string",
  "timestamp": 1761080958.621,
  "last_updated": "2025-10-21 23:09:18"
}
```

### What's Available on Resume
1. **From file**: session_id, timestamps
2. **From SDK**: num_turns, token usage, cost, performance metrics
3. **From agent**: cumulative stats, context window usage

### What Can Be Displayed to User
- Session ID (proof of resumption)
- Last activity timestamp
- Total interactions (from num_turns)
- Token usage and percentage of context window
- Cumulative cost
- Cache efficiency metrics

### Key Limitation
SDK does not expose historical messages via API - only maintains internal access for context awareness.

---

## Code Locations

| Component | File | Lines | Purpose |
|-----------|------|-------|---------|
| Save Context | agent.py | 145-158 | `save_context()` method |
| Load Context | agent.py | 160-175 | `load_context()` method |
| Session Init | agent.py | 81-119 | `__init__()` with resume parameter |
| Get Stats | agent.py | 177-204 | `get_context_info()` method |
| Capture Session ID | agent.py | 244-250 | Capture from ResultMessage |
| Track Usage | agent.py | 466-474 | Update cumulative totals |
| User Prompt | main.py | 230-274 | Check/load context on startup |
| SDK Resumption | agent.py | 108 | `ClaudeAgentOptions(resume=...)` |

---

## Quick Implementation Guide

### To Display Session Resume Summary

```python
# 1. Load from file
from pathlib import Path
import json

context_file = Path.cwd() / ".bassi_context.json"
if context_file.exists():
    saved_context = json.loads(context_file.read_text())
    session_id = saved_context.get("session_id")
    last_updated = saved_context.get("last_updated")

# 2. Get info from first interaction ResultMessage
if result_message.session_id == session_id:
    num_turns = result_message.num_turns
    cost = result_message.total_cost_usd

# 3. Get cumulative stats
context_info = agent.get_context_info()
current_usage = context_info["current_size"]
window_size = context_info["window_size"]

# 4. Display to user
print(f"Session: {session_id}")
print(f"Last Activity: {last_updated}")
print(f"Interactions: {num_turns}")
print(f"Context: {current_usage} / {window_size} tokens")
print(f"Cost: ${cost:.4f}")
```

---

## Architecture Overview

```
User Starts Application
         ↓
   .bassi_context.json exists?
         ↓ YES
   Parse JSON (session_id, timestamp)
         ↓
   Ask User: "Resume?"
         ↓ YES
   Pass session_id to Agent
         ↓
   SDK Resumes Session
         ↓
   First Interaction
         ↓
   Receive ResultMessage(num_turns, usage, cost, ...)
         ↓
   Display Summary to User
         ↓
   Update .bassi_context.json
```

---

## Data Flow

### Save Flow
```
agent.chat(message)
    ↓
[Process with SDK]
    ↓
[Receive ResultMessage]
    ↓
save_context()
    ↓
Write to .bassi_context.json
```

### Load/Resume Flow
```
Application Startup
    ↓
Check .bassi_context.json
    ↓
Load JSON
    ↓
Extract session_id
    ↓
Ask User
    ↓
Pass to BassiAgent(resume_session_id=...)
    ↓
ClaudeAgentOptions(resume=session_id)
    ↓
SDK handles resumption
    ↓
ResultMessage confirms session_id match
```

---

## Important Limitations

1. ⚠️ **No Message History API**
   - Cannot retrieve previous messages from SDK
   - Cannot display conversation history on startup
   - Claude has internal access for context awareness

2. ⚠️ **No Session Metadata from SDK**
   - Must store creation time manually (done in .bassi_context.json)
   - SDK only provides current turn count (num_turns)
   - No API to list all sessions

3. ⚠️ **Turn Count Available After First Interaction**
   - `num_turns` only in ResultMessage after resuming and chatting
   - Not available before first interaction

---

## Token/Cost Tracking

### Context Window
- Size: 200,000 tokens (Claude Sonnet 4.5)
- Compaction threshold: 150,000 tokens (75%)
- Auto-compaction triggered when approaching limit

### Tracked Metrics
- `total_input_tokens`: Tokens in prompts
- `total_output_tokens`: Tokens generated
- `total_cache_creation_tokens`: Cache creation cost
- `total_cache_read_tokens`: Cache hits
- `total_cost_usd`: USD cost

### Access
```python
info = agent.get_context_info()
print(f"Current: {info['current_size']} / {info['window_size']} tokens")
print(f"Usage: {info['percentage_used']:.1f}%")
print(f"Cost: ${info['total_cost_usd']:.4f}")
```

---

## Testing Session Resumption

See `/OLD/test_context_persistence.py` for automated test that:
1. Creates a session with a message
2. Verifies session_id is captured
3. Resumes the session with the saved ID
4. Confirms Claude remembers previous context
5. Validates context file persistence

---

## Related Files in Repository

- `.bassi_context.json` - Stored context (git-ignored)
- `bassi/agent.py` - Agent implementation with context methods
- `bassi/main.py` - Main loop with load/resume logic
- `docs/features_concepts/context_persistence.md` - Feature documentation
- `OLD/test_context_persistence.py` - Test implementation

---

## References

- **Claude Agent SDK**: https://docs.claude.com/en/api/agent-sdk
- **GitHub Issue #109**: Session history API limitations
- **ResultMessage**: Contains session_id, num_turns, usage, cost
- **ClaudeAgentOptions**: `resume` parameter for session continuation

---

## Next Steps for Implementation

If building UI features for session resumption:

1. Read **SESSION_RESUMPTION_SUMMARY.md** (5 min)
2. Review **SDK_MESSAGE_TYPES.md** (10 min)
3. Study code locations in **SESSION_RESUMPTION_ANALYSIS.md** (15 min)
4. Implement following the "Quick Implementation Guide" above
5. Test with OLD/test_context_persistence.py patterns

---

**Last Updated**: 2025-10-21  
**Analysis Scope**: Full session context management in bassi v1.0+
