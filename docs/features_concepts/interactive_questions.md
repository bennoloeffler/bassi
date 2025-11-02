# Interactive Questions Feature

## Overview

This feature implements Claude Code's `AskUserQuestion` tool functionality for Bassi V3, allowing the agent to ask users structured questions with multiple-choice options during execution.

## API Specification (Based on Claude Code's AskUserQuestion)

### Tool Signature

```python
async def ask_user(questions: list[Question]) -> dict[str, str | list[str]]
```

### Input Schema

```typescript
interface AskUserQuestionInput {
  questions: Question[];  // Array of 1-4 questions (required)
}

interface Question {
  question: string;       // Complete question text (required)
  header: string;         // Short label, max 12 chars (required)
  multiSelect: boolean;   // Allow multiple selections (required)
  options: Option[];      // Array of 2-4 options (required)
}

interface Option {
  label: string;          // Display text, 1-5 words (required)
  description: string;    // Explanation of the choice (required)
}
```

### Output Schema

```typescript
interface AskUserQuestionOutput {
  [questionText: string]: string | string[];
  // Single answer for non-multiSelect questions
  // Array of answers for multiSelect questions
}
```

### Constraints

- **Questions per call**: Minimum 1, maximum 4
- **Options per question**: Minimum 2, maximum 4
- **Header length**: Maximum 12 characters
- **Option label**: 1-5 words, concise
- **Automatic "Other" option**: Always available for custom text input (not included in options array)
- **MultiSelect**: When `true`, user can select multiple options; when `false`, only one option

### Example Usage

```python
# Single question, single select
result = await ask_user(questions=[
    {
        "question": "Which authentication method should we use?",
        "header": "Auth Method",
        "multiSelect": False,
        "options": [
            {"label": "OAuth 2.0", "description": "Industry-standard OAuth protocol"},
            {"label": "JWT", "description": "JSON Web Token authentication"},
            {"label": "API Key", "description": "Simple API key authentication"}
        ]
    }
])
# Returns: {"Which authentication method should we use?": "OAuth 2.0"}

# Multiple questions with multiSelect
result = await ask_user(questions=[
    {
        "question": "Which features should we implement first?",
        "header": "Features",
        "multiSelect": True,
        "options": [
            {"label": "User Login", "description": "Basic authentication system"},
            {"label": "Dashboard", "description": "Analytics dashboard"},
            {"label": "API", "description": "REST API endpoints"}
        ]
    },
    {
        "question": "What database should we use?",
        "header": "Database",
        "multiSelect": False,
        "options": [
            {"label": "PostgreSQL", "description": "Robust relational database"},
            {"label": "MongoDB", "description": "Flexible document database"}
        ]
    }
])
# Returns: {
#   "Which features should we implement first?": ["User Login", "Dashboard"],
#   "What database should we use?": "PostgreSQL"
# }
```

## Implementation Architecture

### Components

1. **InteractiveQuestionService** (`bassi/core_v3/interactive_questions.py`)
   - Manages question/answer lifecycle
   - Uses asyncio.Event for synchronization
   - Handles timeouts and errors
   - Per-session isolation

2. **MCP Tool** (`bassi/core_v3/tools.py`)
   - `ask_user` tool exposed to the agent
   - Validates input according to schema
   - Calls InteractiveQuestionService
   - Returns answers in correct format

3. **WebSocket Protocol Extension** (`bassi/core_v3/web_server_v3.py`)
   - New event type: `question` (backend → frontend)
   - New event type: `answer` (frontend → backend)
   - Integrates with existing message handling

4. **UI Components** (`bassi/static/`)
   - QuestionDialog component
   - Support for single/multi-select
   - Rich option descriptions
   - "Other" option with text input

### Message Flow

```
1. Agent calls ask_user tool
   ↓
2. Tool calls InteractiveQuestionService.ask()
   ↓
3. Service sends "question" event via WebSocket
   ↓
4. UI displays dialog with options
   ↓
5. User selects option(s) and clicks Submit
   ↓
6. UI sends "answer" event via WebSocket
   ↓
7. Service receives answer and unblocks asyncio.Event
   ↓
8. Tool returns answer to agent
   ↓
9. Agent continues with user's answer
```

### WebSocket Events

**Question Event (Backend → Frontend)**
```json
{
  "type": "question",
  "id": "uuid-123",
  "questions": [
    {
      "question": "Which authentication method should we use?",
      "header": "Auth Method",
      "multiSelect": false,
      "options": [
        {"label": "OAuth 2.0", "description": "Industry-standard OAuth protocol"},
        {"label": "JWT", "description": "JSON Web Token authentication"},
        {"label": "API Key", "description": "Simple API key authentication"}
      ]
    }
  ]
}
```

**Answer Event (Frontend → Backend)**
```json
{
  "type": "answer",
  "question_id": "uuid-123",
  "answers": {
    "Which authentication method should we use?": "OAuth 2.0"
  }
}
```

## Use Cases

### Skill/Command Questions

```python
# In /crm slash command
result = await ask_user(questions=[{
    "question": "What type of CRM entity should I create?",
    "header": "Entity Type",
    "multiSelect": False,
    "options": [
        {"label": "Company", "description": "Create a new company record"},
        {"label": "Contact", "description": "Create a new contact person"},
        {"label": "Opportunity", "description": "Create a sales opportunity"}
    ]
}])

entity_type = result["What type of CRM entity should I create?"]
# Continue based on user's choice
```

### Clarifying Requirements

```python
# When ambiguous request is detected
result = await ask_user(questions=[{
    "question": "Which library should I use for date formatting?",
    "header": "Library",
    "multiSelect": False,
    "options": [
        {"label": "arrow", "description": "Human-friendly dates"},
        {"label": "pendulum", "description": "Drop-in datetime replacement"},
        {"label": "dateutil", "description": "Standard library extension"}
    ]
}])
```

### Feature Selection

```python
# Multiple related questions
result = await ask_user(questions=[
    {
        "question": "Which features do you want to enable?",
        "header": "Features",
        "multiSelect": True,
        "options": [
            {"label": "Email notifications", "description": "Send email alerts"},
            {"label": "SMS notifications", "description": "Send SMS alerts"},
            {"label": "Push notifications", "description": "Browser push alerts"}
        ]
    },
    {
        "question": "What environment should I deploy to?",
        "header": "Environment",
        "multiSelect": False,
        "options": [
            {"label": "Development", "description": "Local dev environment"},
            {"label": "Staging", "description": "Testing environment"},
            {"label": "Production", "description": "Live environment"}
        ]
    }
])

features = result["Which features do you want to enable?"]  # List of selected features
environment = result["What environment should I deploy to?"]  # Single selection
```

## Error Handling

### Timeout
- Default: 5 minutes (300 seconds)
- Configurable per question
- On timeout: Raise `QuestionTimeoutError`

### User Disconnection
- If WebSocket disconnects while waiting: Raise `QuestionCancelledError`

### Validation Errors
- Invalid question format: Raise `QuestionValidationError`
- Too many questions (>4): Raise `QuestionValidationError`
- Too few/many options: Raise `QuestionValidationError`

## Testing

### Unit Tests
- Test question validation
- Test timeout handling
- Test multiSelect vs single select
- Test "Other" option handling

### Integration Tests
- Test WebSocket event flow
- Test multiple questions
- Test session isolation

### E2E Tests
- Test UI interaction
- Test full agent workflow
- Test error scenarios

## Future Enhancements

1. **Conditional Questions**: Show questions based on previous answers
2. **Validation Rules**: Add regex/range validation for "Other" text input
3. **Default Values**: Pre-select certain options
4. **Question History**: Track user preferences across sessions
5. **Rich Media**: Support images in option descriptions
