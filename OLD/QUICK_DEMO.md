# Quick Demo - New Features

## Status Line Example

After each interaction with bassi, you'll see a status line like this:

```
You: hello

🤖 Assistant:
Hello! How can I help you today?

╭────────────────────────────────────────────────────────────╮
│ [✅ Ready] • Active 1s ago • Context: 1,234 tokens (0.6%) │
│ • Session: 651fcfd6                                        │
╰────────────────────────────────────────────────────────────╯

You:
```

### What Each Part Means

```
[✅ Ready]                  ← Status (green = ready, cyan = working)
• Active 1s ago             ← Time since last activity
• Context: 1,234 tokens     ← Context usage
  (0.6%)                    ← Percentage of 200K window
• Session: 651fcfd6         ← Your session ID (abbreviated)
```

### Status Colors

| Status | Color | Meaning |
|--------|-------|---------|
| ✅ Ready | Green | Agent is idle, waiting for input |
| ⏳ Thinking... | Cyan | Processing your request |
| ⚡ Executing bash... | Cyan | Running a command |
| ⚠️  Warning | Yellow | High context usage or issue |
| ❌ Error | Red | Something went wrong |

### Context Usage Colors

| Usage | Color | Meaning |
|-------|-------|---------|
| 0-75% | Gray (dim) | Normal, plenty of space |
| 75-90% | Yellow | Getting full, compaction may trigger soon |
| >90% | Red | Critical, compaction imminent |

## Auto-Compaction Example

When context approaches 95%, you'll see:

```
You: <your very long conversation>

⚡ Context approaching limit - auto-compacting...

🤖 Assistant:
<continues with summarized context>

╭────────────────────────────────────────────────────────────────╮
│ [✅ Ready] • Active 2s ago • Context: 125,000 tokens (62.5%) │
│ • Session: 651fcfd6                                            │
╰────────────────────────────────────────────────────────────────╯
```

Notice:
1. Yellow warning before compaction
2. Context usage drops after compaction (was >90%, now 62%)
3. Conversation continues seamlessly

## Live Example

Try it yourself:

```bash
./run-agent.sh
```

```
You: what is 2 + 2?

🤖 Assistant:
2 + 2 = 4

╭────────────────────────────────────────────────────────────╮
│ [✅ Ready] • Active 1s ago • Context: 234 tokens (0.1%)   │
│ • Session: 651fcfd6                                        │
╰────────────────────────────────────────────────────────────╯

You: tell me about the weather

🤖 Assistant:
I don't have direct access to real-time weather data...

╭────────────────────────────────────────────────────────────╮
│ [✅ Ready] • Active 2s ago • Context: 1,456 tokens (0.7%) │
│ • Session: 651fcfd6                                        │
╰────────────────────────────────────────────────────────────╯

You: /quit
Goodbye! 👋
```

## Debugging with Status Line

The status line helps you debug issues:

### Stuck Agent?
Check the "Active" time:
```
[⏳ Thinking...] • Active 45s ago  ← Agent is still working!
```

### Context Problems?
Check the usage:
```
• Context: 185,234 tokens (92.6%)  ← High usage, compaction coming
```

### Wrong Session?
Check the session ID:
```
• Session: 651fcfd6  ← Should match .bassi_context.json
```

## Detailed Logs

For even more detail, check the log file:

```bash
tail -f bassi_debug.log
```

You'll see:
- Every status change
- Compaction events
- Session ID captures
- Tool executions
- Errors and warnings
