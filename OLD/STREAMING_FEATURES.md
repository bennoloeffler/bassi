# Streaming & Status Features

## What Changed

bassi now has **FULL STREAMING** with **ALWAYS VISIBLE STATUS**!

### Before (Old Version)
```
> list all python files

[Long silence... user waits 5-10 seconds wondering what's happening]

Here are all the python files:
- file1.py
- file2.py
...
```

### Now (Streaming Version)
```
> list all python files

📨 User Message: list all python files

→ Iteration 1/10
⏳ CALLING API...........  [changes to]
📡 STREAMING RESPONSE...

[Text appears IN REAL-TIME as Claude types]:
I'll search for Python files in your configured directories.

→ Agent wants to use tools

🔧 Tool: bash
{
  "command": "fd '\\.py$'"
}

⚡ EXECUTING BASH: fd '\.py$' [animated while executing]

💻 Bash Result
Exit Code: 0
Success: True

STDOUT:
bassi/agent.py
bassi/main.py
...

→ Iteration 2/10
📡 STREAMING RESPONSE...

[More text streams in real-time]:
I found 15 Python files in your configured directories...

→ Agent finished
```

## New Features

### 1. ⏳ Status Lines During API Calls
While waiting for Claude API response:
```
⏳ CALLING API...........
```

Then changes to:
```
📡 STREAMING RESPONSE...
```

### 2. ⚡ Status Lines During Tool Execution

**Bash commands:**
```
⚡ EXECUTING BASH: ls -la
```

**Any bash command:**
```
⚡ EXECUTING BASH: fd '*.py'
```

### 3. 📡 Real-Time Response Streaming

The response appears **character by character** as Claude generates it!

No more waiting - you see the answer being typed in real-time.

### 4. 🔧 Verbose Mode Still Works

All the tool Input/Output panels still show when verbose is ON:
- Tool parameters (JSON formatted)
- Tool results (formatted with colors)
- Exit codes, STDOUT, STDERR for bash commands

### 5. 📊 Iteration Counter

Always shows which iteration (helps debug infinite loops):
```
→ Iteration 1/10
→ Iteration 2/10
...
```

## Technical Implementation

### Streaming API
Uses Anthropic's streaming API:
```python
with self.client.messages.stream(...) as stream:
    for event in stream:
        if event.type == "content_block_delta":
            text = event.delta.text
            # Print immediately!
            console.print(text, end="")
```

### Live Status Updates
Uses Rich Live display:
```python
with Live(Text("⚡ EXECUTING BASH: cmd"), console=console):
    result = execute_tool(...)
```

### No More Blocking
- Old version: `response = agent.chat(msg)` - blocks until done
- New version: `agent.chat(msg)` - streams output as it happens

## User Experience

### Interactive & Responsive
- **See** what's happening at every step
- **Know** when API is being called
- **Watch** tools being executed
- **Read** responses as they're generated

### No More Mystery
- Never wonder "is it working?"
- Never wait in silence
- Never guess what's taking so long

### Full Transparency
- See every API call
- See every tool execution
- See every decision
- See every result

## Files Changed

1. **bassi/agent.py** - Complete rewrite for streaming
   - `_process_with_streaming()` - Streaming message loop
   - `_execute_tools_with_status()` - Tools with status lines
   - `_get_tool_status_text()` - Status text for each tool

2. **bassi/main.py** - Simplified (agent handles display)
   - Removed `with console.status()`
   - Removed `Panel()` wrapping
   - Just calls `agent.chat()` which streams

## Run It

```bash
# Start bassi (streaming is default)
uv run bassi

# Or test directly
uv run python test_streaming.py

# Watch it stream!
> find all python files
[Watch the magic happen in real-time]
```

## Benefits

1. **Better UX** - User always knows what's happening
2. **Faster Perceived Speed** - Streaming feels faster than blocking
3. **More Engaging** - Watching text appear is more interesting
4. **Debugging** - Easy to see where things get stuck
5. **Transparency** - Full visibility into agent behavior

## Next Steps

Possible improvements:
- Adjust status line styles/colors
- Add animation to status lines (spinner, dots)
- Show token count during streaming
- Add ETA for long operations
- Streaming for file search results

---

**bassi is now fully interactive - you see EVERYTHING as it happens!** 🚀
