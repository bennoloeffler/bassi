# Bug: Tool Outputs and Reasoning Text Not Showing in Web UI

## Problem
1. Tool outputs show "Running..." but never update with actual output
2. Assistant reasoning text (between tool calls) not visible
3. Only usage stats and "Success" badges show

## Expected Behavior (from CLI)

```
Assistant: I'll help you list files...

[Tool: bash execute]
Output: file1.txt, file2.txt...