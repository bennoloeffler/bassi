# Simple Test for Context Persistence

## Quick Test (Manual)

1. **First session** - Teach bassi something:
   ```bash
   ./run-agent.sh
   ```
   ```
   You: remember: my favorite programming language is Python
   ```
   Wait for response, then quit: `/quit`

2. **Check the context file was saved:**
   ```bash
   cat .bassi_context.json
   ```
   You should see a UUID session_id like `ae7bbada-f363-4f81-9df3-b24f3dea8f97`

3. **Second session** - Test if bassi remembers:
   ```bash
   ./run-agent.sh
   ```
   Choose `y` when prompted to load context.

   You should see:
   ```
   ✅ Loaded previous context
      Session ID: ae7bbada-f363-4f81-9df3-b24f3dea8f97
   ```

   ```
   You: what's my favorite programming language?
   ```

   **Expected:** Bassi should answer "Python" ✅

   **If broken:** Bassi says "I don't know" or asks you ❌

## Check Session Files

See all saved sessions:
```bash
ls -lh ~/.claude/projects/-Users-benno-projects-ai-bassi/
```

View the actual conversation history (last 10 lines):
```bash
# Replace {UUID} with actual UUID from .bassi_context.json
tail -10 ~/.claude/projects/-Users-benno-projects-ai-bassi/{UUID}.jsonl | jq
```

## Debug Logs

Watch session activity in real-time:
```bash
tail -f bassi_debug.log | grep -i session
```

Look for these messages:
- First run: `"SDK session_id captured: {UUID}"`
- First run: `"Context saved - session_id: {UUID}"`
- Second run: `"Context loaded - session_id: {UUID}"`
- Second run: `"Resuming session: {UUID}"`

## What Should Happen

### ✅ Success:
- Session ID is a UUID (e.g., `ae7bbada-f363-4f81-9df3-b24f3dea8f97`)
- `.bassi_context.json` contains this UUID
- Corresponding `.jsonl` file exists in `~/.claude/projects/`
- On restart, bassi remembers previous conversations
- Logs show "Resuming session" message

### ❌ Failure:
- Session ID is a custom format (e.g., `session_1234_abcd`)
- No `.jsonl` file in `~/.claude/projects/` matches the session ID
- On restart, bassi doesn't remember anything
- Logs show "Starting new session" every time

## Expected Output

```
# First run
$ ./run-agent.sh
Ready! What can I help you with?

You: remember: my favorite color is purple

🤖 Assistant:
Got it! I'll remember that your favorite color is purple.

⏱️  2345ms | 💰 $0.0012 | 📊 Context: 2,341 / 200,000 tokens (1.2%)

You: /quit
Goodbye! 👋

# Check context
$ cat .bassi_context.json
{
  "session_id": "ae7bbada-f363-4f81-9df3-b24f3dea8f97",
  "timestamp": 1761077389.274942,
  "last_updated": "2025-10-21 22:30:45"
}

# Second run
$ ./run-agent.sh
📋 Found saved context from previous session
Load previous context? [y/n] (y): y
✅ Loaded previous context
   Session ID: ae7bbada-f363-4f81-9df3-b24f3dea8f97

Ready! What can I help you with?

You: what's my favorite color?

🤖 Assistant:
Your favorite color is purple!

⏱️  1234ms | 💰 $0.0008 | 📊 Context: 4,125 / 200,000 tokens (2.1%)
```

## Troubleshooting

### Issue: Session ID is still custom format
**Fix:** Delete `.bassi_context.json` and start fresh:
```bash
rm .bassi_context.json
./run-agent.sh
```

### Issue: Bassi doesn't remember after restart
**Check:**
1. Is session ID a UUID? `cat .bassi_context.json`
2. Does the session file exist? `ls ~/.claude/projects/-Users-benno-projects-ai-bassi/`
3. Check logs: `grep "session_id" bassi_debug.log | tail -20`

### Issue: "No session ID in context, starting fresh"
This means `.bassi_context.json` exists but has no `session_id` field.
**Fix:** Delete it and let bassi create a new one:
```bash
rm .bassi_context.json
```
