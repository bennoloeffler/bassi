---
description: Create comprehensive test coverage using parallel test-writer agents
skill: bel-create-tests-one-by-one
---

# Parallel Test Writer

**This command activates the `bel-create-tests-one-by-one` skill** to create comprehensive test coverage using parallel agents.

## Usage Modes

### Mode 1: Smart Detection (Recommended)
Just describe what you want in natural language:

```bash
/bel-write-tests-one-by-one I want to test agent_session.py with 5 agents focusing on error handling
/bel-write-tests-one-by-one test message_converter.py for edge cases and race conditions
/bel-write-tests-one-by-one web_server_v3.py needs e2e tests for WebSocket errors
```

The command will:
1. **Detect parameters** from your text
2. **Show suggestions** for how to call it
3. **Ask for confirmation** before proceeding

### Mode 2: Direct Parameters
Provide parameters explicitly:

```bash
/bel-write-tests-one-by-one <source_file> [num_agents] [test_types] [focus_areas]
```

## Parameters

**Required:**
- `source_file`: Source file to test (e.g., "bassi/core_v3/agent_session.py")

**Optional:**
- `num_agents`: Number of parallel agents (default: 3, max: 10)
- `test_types`: Comma-separated: "unit", "integration", "e2e" (default: "unit,integration")
- `focus_areas`: Specific areas (e.g., "error handling,race conditions,edge cases")

## Smart Detection Examples

**Example 1: Minimal Input**
```
User: /bel-write-tests-one-by-one test agent_session.py

Detected Parameters:
✓ source_file: bassi/core_v3/agent_session.py (found matching file)
  num_agents: 3 (default)
  test_types: unit,integration (default)
  focus_areas: (none)

Suggested Command:
/bel-write-tests-one-by-one bassi/core_v3/agent_session.py 3 unit,integration

Proceed with these parameters? (yes/no/edit)
```

**Example 2: With Agent Count**
```
User: /bel-write-tests-one-by-one I need 5 agents to test message_converter.py

Detected Parameters:
✓ source_file: bassi/core_v3/message_converter.py
✓ num_agents: 5
  test_types: unit,integration (default)
  focus_areas: (none)

Suggested Command:
/bel-write-tests-one-by-one bassi/core_v3/message_converter.py 5 unit,integration

Proceed with these parameters? (yes/no/edit)
```

**Example 3: With Test Types**
```
User: /bel-write-tests-one-by-one web_server_v3.py needs e2e tests

Detected Parameters:
✓ source_file: bassi/core_v3/web_server_v3.py
  num_agents: 3 (default)
✓ test_types: e2e
  focus_areas: (none)

Suggested Command:
/bel-write-tests-one-by-one bassi/core_v3/web_server_v3.py 3 e2e

Proceed with these parameters? (yes/no/edit)
```

**Example 4: Full Specification**
```
User: /bel-write-tests-one-by-one I want 7 agents to write unit tests for permission_config.py focusing on error handling and edge cases

Detected Parameters:
✓ source_file: bassi/shared/permission_config.py
✓ num_agents: 7
✓ test_types: unit
✓ focus_areas: error handling,edge cases

Suggested Command:
/bel-write-tests-one-by-one bassi/shared/permission_config.py 7 unit "error handling,edge cases"

Proceed with these parameters? (yes/no/edit)
```

**Example 5: Ambiguous File**
```
User: /bel-write-tests-one-by-one test agent.py

Multiple files found matching "agent.py":
1. bassi/agent.py (V1 CLI agent, 1039 lines)
2. bassi/core_v3/agent_session.py (V3 web agent, 275 lines)

Please specify which file:
- /bel-write-tests-one-by-one bassi/agent.py
- /bel-write-tests-one-by-one bassi/core_v3/agent_session.py
```

## Detection Rules

The command uses these rules to parse your input:

### Source File Detection
- **Pattern**: Look for `.py` file names or paths
- **Fuzzy Matching**: Finds closest match in project
- **Examples**:
  - "agent_session.py" → bassi/core_v3/agent_session.py
  - "message converter" → bassi/core_v3/message_converter.py
  - "bassi/agent.py" → bassi/agent.py (exact match)

### Number Detection
- **Patterns**:
  - "X agents" → num_agents = X
  - "with X" → num_agents = X
  - "X parallel" → num_agents = X
- **Validation**: 1 ≤ num_agents ≤ 10

### Test Type Detection
- **Keywords**:
  - "unit" → unit tests only
  - "integration" → integration tests only
  - "e2e" or "end-to-end" → e2e tests only
  - "unit and integration" → both
- **Default**: unit,integration (if not specified)

### Focus Area Detection
- **Keywords**: "focus", "focusing on", "for", "about"
- **Common Areas**:
  - error handling
  - edge cases
  - race conditions
  - validation
  - async behavior
  - WebSocket errors
  - file upload
  - session management

## Parameter Confirmation Flow

After detecting parameters, the command will:

1. **Show Detection Results**
   ```
   Detected Parameters:
   ✓ source_file: bassi/core_v3/agent_session.py
   ✓ num_agents: 5
   ✓ test_types: unit
   ✓ focus_areas: error handling,async behavior
   ```

2. **Suggest Command**
   ```
   Suggested Command:
   /bel-write-tests-one-by-one bassi/core_v3/agent_session.py 5 unit "error handling,async behavior"
   ```

3. **Ask for Confirmation**
   ```
   Options:
   - Type 'yes' or 'y' to proceed with these parameters
   - Type 'no' or 'n' to cancel
   - Type 'edit' to manually adjust parameters
   ```

4. **Handle Response**
   - **yes**: Proceed with skill invocation
   - **no**: Cancel operation
   - **edit**: Show editable parameters

## Implementation Logic

When this command is invoked, perform the following:

### Step 1: Parse Input Text

```python
# Pseudo-code for parameter detection
input_text = "{user input after command}"

# Detect source file
source_files = find_python_files_in_project()
source_file = fuzzy_match(input_text, source_files)

# Detect number of agents
num_agents = extract_number(input_text, keywords=["agents", "parallel", "with"])
if not num_agents:
    num_agents = 3  # default

# Detect test types
test_types = []
if "unit" in input_text:
    test_types.append("unit")
if "integration" in input_text:
    test_types.append("integration")
if "e2e" in input_text or "end-to-end" in input_text:
    test_types.append("e2e")
if not test_types:
    test_types = ["unit", "integration"]  # default

# Detect focus areas
focus_keywords = ["focus", "focusing on", "for", "about"]
focus_areas = extract_after_keywords(input_text, focus_keywords)
```

### Step 2: Validate Parameters

```python
# Validate source_file exists
if not os.path.exists(source_file):
    # Try to find similar files
    suggestions = find_similar_files(source_file)
    if suggestions:
        show_suggestions(suggestions)
        return
    else:
        error("No matching Python file found")
        return

# Validate num_agents
if num_agents < 1 or num_agents > 10:
    error("num_agents must be between 1 and 10")
    return

# Validate test_types
valid_types = ["unit", "integration", "e2e"]
for t in test_types:
    if t not in valid_types:
        error(f"Invalid test type: {t}. Must be one of: {valid_types}")
        return
```

### Step 3: Show Detection Results

```markdown
Detected Parameters:
✓ source_file: {source_file}
{✓ if specified, else "  "} num_agents: {num_agents} {(default) if default}
{✓ if specified, else "  "} test_types: {",".join(test_types)} {(default) if default}
{✓ if specified, else "  "} focus_areas: {focus_areas or "(none)"}
```

### Step 4: Suggest Command

```bash
Suggested Command:
/bel-write-tests-one-by-one {source_file} {num_agents} {test_types} "{focus_areas}"
```

### Step 5: Confirm with User

Use AskUserQuestion tool:

```python
response = ask_user_question(
    question="Proceed with these parameters?",
    options=[
        {"label": "Yes", "description": "Proceed with detected parameters"},
        {"label": "No", "description": "Cancel operation"},
        {"label": "Edit", "description": "Manually adjust parameters"}
    ]
)

if response == "Yes":
    invoke_skill(source_file, num_agents, test_types, focus_areas)
elif response == "Edit":
    show_edit_form()
else:
    cancel()
```

### Step 6: Invoke Skill

If user confirms, invoke the `bel-create-tests-one-by-one` skill:

```python
# Invoke skill with confirmed parameters
Skill(skill="bel-create-tests-one-by-one")

# Pass parameters to skill
Parameters:
  source_file: {source_file}
  num_agents: {num_agents}
  test_types: {test_types}
  focus_areas: {focus_areas}
```

## Direct Parameter Mode (Fallback)

If the input looks like direct parameters (e.g., starts with a clear file path):

```bash
/bel-write-tests-one-by-one bassi/core_v3/agent_session.py 5 unit "error handling"
```

Skip detection and parse as:
1. First argument: source_file
2. Second argument (optional): num_agents
3. Third argument (optional): test_types
4. Fourth argument (optional): focus_areas

## Workflow

```
User invokes command with freeform text
    ↓
Parse text → detect parameters
    ↓
Validate parameters
    ↓
Show detection results + suggested command
    ↓
Ask user for confirmation
    ↓
User responds (yes/no/edit)
    ↓
If yes: Invoke skill
If edit: Show editable form → Invoke skill
If no: Cancel
```

## Expected Output

When smart detection is used:

```
## Parameter Detection

Analyzing input: "I want to test agent_session.py with 5 agents focusing on error handling"

Detected Parameters:
✓ source_file: bassi/core_v3/agent_session.py
✓ num_agents: 5
  test_types: unit,integration (default)
✓ focus_areas: error handling

Suggested Command:
/bel-write-tests-one-by-one bassi/core_v3/agent_session.py 5 unit,integration "error handling"

Proceed with these parameters? (yes/no/edit)
> User responds: yes

## Invoking Skill: bel-create-tests-one-by-one

Parameters:
- source_file: bassi/core_v3/agent_session.py
- num_agents: 5
- test_types: unit,integration
- focus_areas: error handling

[Skill execution continues as documented in SKILL.md]
```

## Invoke the Skill

After user confirms parameters, invoke the skill:

**Skill:** bel-create-tests-one-by-one

**Parameters:**
- source_file: {confirmed_source_file}
- num_agents: {confirmed_num_agents}
- test_types: {confirmed_test_types}
- focus_areas: {confirmed_focus_areas}

The skill will orchestrate test-writer-agent-ONLY-ONE (multiple instances in parallel) and test-collector-agent-MANY (single instance for merging).

**For complete orchestration details, refer to the `bel-create-tests-one-by-one` skill documentation.**
