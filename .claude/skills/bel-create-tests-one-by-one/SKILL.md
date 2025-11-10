# Skill: Create Tests One by One

**Description:** Orchestrates parallel test-writer agents to create comprehensive tests for a module, then intelligently merges them.

## Overview

This skill implements a parallel test-writing workflow:
1. Analyze source file to determine test coverage gaps
2. Spawn N parallel test-writer agents (each writes ONE test)
3. Each agent works independently on temp file (test_module_AGENT_XX.py)
4. Wait for all agents to complete
5. Spawn collector agent to merge all tests into final file
6. Verify final tests pass and cleanup temp files

## When to Use This Skill

- Creating comprehensive test coverage for a module
- Writing tests for complex modules that need many edge case tests
- Parallelizing test creation to save time
- Ensuring diverse test patterns (unit, integration, e2e)

## Parameters

**Required:**
- `source_file`: Source file to test (e.g., "bassi/core_v3/agent_session.py")

**Optional:**
- `num_agents`: Number of parallel agents (default: 3, max: 10)
- `test_types`: Comma-separated list: "unit", "integration", "e2e" (default: "unit,integration")
- `focus_areas`: Specific areas to test (e.g., "error handling,race conditions,edge cases")

## Process

### 1. Analyze Source File

Read source file to understand:
- What functions/classes exist
- Current test coverage (if test file exists)
- Complexity and potential test areas
- Dependencies and integration points

```bash
# Check current coverage
uv run coverage run --branch -m pytest tests/test_<module>.py -v 2>/dev/null
uv run coverage report --include="bassi/<module>.py" --show-missing

# Analyze source
# - Count functions/classes
# - Identify async functions (need @pytest.mark.asyncio)
# - Identify external dependencies (may need mocks or integration tests)
```

### 2. Determine Test Strategy

Based on analysis, decide:
- How many tests needed (aim for ~80%+ coverage)
- What test types (unit vs integration vs e2e)
- How many parallel agents to spawn

**Example Strategy:**
```
Source: bassi/core_v3/agent_session.py (275 lines)
Current Coverage: 45%
Missing: Lines 50-80, 120-145, 200-220

Plan:
- 6 unit tests (error handling, edge cases)
- 2 integration tests (real API calls)
- 1 e2e test (browser workflow)

Agents: 9 parallel agents (one test each)
```

### 3. Spawn Parallel Test-Writer Agents

Use the Task tool to launch multiple instances of test-writer-agent-ONLY-ONE in parallel:

```python
# Conceptual structure (actual implementation via Task tool)
agents = []
for agent_id in range(1, num_agents + 1):
    agents.append({
        "id": f"{agent_id:02d}",
        "env": {
            "TEST_AGENT_ID": f"{agent_id:02d}",
            "TEST_SOURCE_FILE": source_file,
            "TEST_TARGET_FILE": target_test_file,
            "TEST_TEMP_FILE": f"{test_base}_AGENT_{agent_id:02d}.py"
        },
        "agent": "test-writer-agent-ONLY-ONE"
    })

# Launch all agents in parallel
# Each agent will:
# 1. Read CLAUDE_TESTS.md
# 2. Write ONE test
# 3. Execute and iterate until perfect
# 4. Mark STATUS: COMPLETE
```

### 4. Monitor Agent Progress

Track completion:
```bash
# Check which agents are done
for i in 01 02 03 04 05; do
    if grep -q "STATUS: COMPLETE" test_module_AGENT_${i}.py 2>/dev/null; then
        echo "✓ AGENT_${i} complete"
    else
        echo "⧗ AGENT_${i} working..."
    fi
done
```

### 5. Wait for All Agents

**Timeout:** 10 minutes per agent (should be plenty for ONE test)

If agent times out or fails:
- Check its temp file for errors
- May need to relaunch that specific agent
- Or reduce num_agents if capacity issue

### 6. Spawn Collector Agent

Once all test-writer agents complete, launch test-collector-agent-MANY:

```python
collector_env = {
    "TEST_TARGET_FILE": target_test_file,
    "TEST_TEMP_PATTERN": f"{test_base}_AGENT_*.py",
    "TEST_SOURCE_FILE": source_file,
}

# Launch collector agent
# Collector will:
# 1. Find all AGENT_* files
# 2. Verify all STATUS: COMPLETE
# 3. Merge intelligently
# 4. Validate merged tests
# 5. Cleanup temp files
# 6. Report summary
```

### 7. Final Verification

After collector completes:
```bash
# Ensure final tests pass
uv run pytest ${target_test_file} -v

# Check coverage improvement
uv run coverage run --branch -m pytest ${target_test_file} -v
uv run coverage report --include="${source_file}" --show-missing

# Ensure temp files cleaned up
ls ${test_base}_AGENT_*.py 2>/dev/null
# Should be empty
```

## Example Invocation

```bash
# Via command
/bel-write-tests-one-by-one bassi/core_v3/agent_session.py

# Via skill (more control)
Skill: bel-create-tests-one-by-one
Parameters:
  source_file: bassi/shared/permission_config.py
  num_agents: 5
  test_types: unit
  focus_areas: edge cases,error handling,validation
```

## Agent Coordination

### Parallel Safety

Each agent works on isolated temp file:
```
test_logging_AGENT_01.py  ← Agent 01 (ONLY)
test_logging_AGENT_02.py  ← Agent 02 (ONLY)
test_logging_AGENT_03.py  ← Agent 03 (ONLY)
...
test_logging.py           ← NEVER touched until collector
```

No conflicts possible - each agent has exclusive file.

### Test Diversity

Ensure agents write different tests:
- Agent receives AGENT_ID to differentiate
- Agent reads existing tests (including other AGENT files) to avoid duplicates
- Each agent focuses on ONE unique scenario

### Quality Assurance

Each agent self-validates:
- Test must pass locally
- Test must add meaningful coverage
- Test must follow patterns from CLAUDE_TESTS.md
- Test marked with appropriate markers (integration/e2e)

Collector validates:
- No duplicate test names
- All tests still pass after merge
- Coverage improvement verified

## Error Handling

**Agent fails to complete:**
```
ERROR: AGENT_03 failed after 10 minutes

Action:
1. Check test_module_AGENT_03.py for partial work
2. Check errors in agent output
3. Relaunch AGENT_03 specifically
4. Or proceed with remaining agents
```

**Collector fails to merge:**
```
ERROR: Merge conflicts detected

Action:
1. Collector should resolve automatically
2. If not, manual intervention needed
3. Review temp files for conflicts
4. Manually merge and cleanup
```

**Tests fail after merge:**
```
ERROR: 2 tests failing after merge

Action:
1. Collector re-runs validation
2. Fixes import/fixture conflicts
3. Re-merges until all pass
4. Only then cleans up temp files
```

## Success Metrics

Skill succeeds when:
- ✓ N parallel agents spawned successfully
- ✓ All agents completed with STATUS: COMPLETE
- ✓ Collector merged all tests without conflicts
- ✓ Final test file passes: `pytest <target> -v`
- ✓ Coverage improved (verified)
- ✓ Temp files cleaned up
- ✓ Summary report generated

## Implementation Details

### Using Task Tool

To launch parallel agents:
```python
# Launch N agents in parallel (single message, multiple Task calls)
Task(
    subagent_type="general-purpose",
    description="Write test as AGENT_01",
    prompt=f"""
    You are test-writer-agent-ONLY-ONE with AGENT_ID=01.

    Your task:
    1. Read .claude/agents/test-writer-agent-ONLY-ONE.md
    2. Follow instructions EXACTLY
    3. Write ONE test for {source_file}
    4. Save to {temp_file_01}
    5. Execute and iterate until perfect
    6. Mark STATUS: COMPLETE

    Environment:
    - TEST_AGENT_ID=01
    - TEST_SOURCE_FILE={source_file}
    - TEST_TARGET_FILE={target_file}
    - TEST_TEMP_FILE={temp_file_01}
    """
)

Task(
    subagent_type="general-purpose",
    description="Write test as AGENT_02",
    prompt=f"""[similar for AGENT_02]"""
)

# ... repeat for N agents
```

### Monitoring Completion

After launching all agents:
```bash
# Poll for completion (check every 30 seconds)
while true; do
    all_complete=true
    for i in 01 02 03; do
        if ! grep -q "STATUS: COMPLETE" test_module_AGENT_${i}.py 2>/dev/null; then
            all_complete=false
            break
        fi
    done

    if $all_complete; then
        echo "✓ All agents complete!"
        break
    fi

    sleep 30
done
```

## Best Practices

1. **Start Small:** Begin with 3 agents to test workflow
2. **Scale Up:** Increase to 5-10 agents for complex modules
3. **Focus Tests:** Use focus_areas to guide agent priorities
4. **Monitor First Run:** Watch first execution to debug issues
5. **Verify Coverage:** Always check coverage improvement
6. **Clean Failures:** If agent fails, investigate before retrying

## Example Full Workflow

```bash
# User invokes command
/bel-write-tests-one-by-one bassi/core_v3/message_converter.py

# Skill activates:

## Step 1: Analysis
✓ Source: bassi/core_v3/message_converter.py (240 lines)
✓ Current coverage: 79% (51 statements missing)
✓ Strategy: 5 unit tests needed

## Step 2: Spawn Agents (parallel)
→ Launching AGENT_01 (test unknown content block type)
→ Launching AGENT_02 (test result message with content)
→ Launching AGENT_03 (test user message with tool results)
→ Launching AGENT_04 (test edge case - empty content)
→ Launching AGENT_05 (test performance - large messages)

## Step 3: Monitor (2 min elapsed)
✓ AGENT_01 complete (test_unknown_content_block_type)
✓ AGENT_02 complete (test_result_message_with_content_blocks)
⧗ AGENT_03 working... (test iteration in progress)
⧗ AGENT_04 working... (test execution)
⧗ AGENT_05 working... (test execution)

## Step 4: All Complete (5 min elapsed)
✓ All 5 agents completed successfully

## Step 5: Collector Merge
→ Launching test-collector-agent-MANY
✓ Found 5 temp files
✓ All marked COMPLETE
✓ Merging into tests/test_message_converter.py
✓ Resolved 1 import conflict
✓ Renamed 1 duplicate fixture
✓ Final file: 29 tests total (24 existing + 5 new)

## Step 6: Validation
✓ Running: pytest tests/test_message_converter.py -v
✓ 29 passed in 0.5s
✓ Coverage: 79% → 100% (+21%)
✓ Temp files cleaned up

## Summary
✓ Successfully added 5 tests via parallel agents
✓ Coverage increased by 21 percentage points
✓ All tests passing
✓ Execution time: 6 minutes (vs ~30 minutes serial)
```

## Notes

- Agents are stateless - each runs independently
- Collector is single-threaded (sequential merge)
- Total time: ~5-10 minutes for typical module
- Scales linearly with num_agents (more agents = more tests in same time)
