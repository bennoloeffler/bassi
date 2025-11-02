# Interactive Questions Implementation - Complete

## Summary

Successfully implemented Claude Code's `AskUserQuestion` functionality for Bassi V3, enabling the agent to ask users structured questions with multiple-choice options during execution.

## What Was Implemented

### 1. API Investigation ✅
- Called Claude Code's own `AskUserQuestion` tool to understand its behavior
- Reverse-engineered the exact API from GitHub Gist and live testing
- Documented the complete JSON schema and constraints

### 2. Backend Components ✅

#### `bassi/core_v3/interactive_questions.py`
- `InteractiveQuestionService` class
  - Manages question/answer lifecycle
  - Uses `asyncio.Event` for synchronization
  - Handles timeouts (default 5 minutes)
  - Per-session isolation
  - Graceful error handling
- Custom exceptions:
  - `QuestionTimeoutError`
  - `QuestionCancelledError`
  - `QuestionValidationError`
- Data classes:
  - `Question`
  - `QuestionOption`
  - `PendingQuestion`

#### `bassi/core_v3/tools.py`
- `AskUserQuestion` MCP tool
  - Matches Claude Code's API exactly
  - Zod schema validation
  - Supports 1-4 questions per call
  - Supports 2-4 options per question
  - MultiSelect support
  - Automatic "Other" option (implemented in UI)
  - Returns answers in Claude-friendly format

#### `bassi/core_v3/web_server_v3.py` Updates
- Integrated `InteractiveQuestionService` into session lifecycle
- Per-session question service instances
- WebSocket message handler for "answer" events
- Automatic cleanup on disconnect
- Factory function updated to inject service

### 3. Frontend Components ✅

#### `bassi/static/app.js`
- `handleQuestion()` - Process question events from backend
- `createQuestionDialog()` - Build interactive UI
  - Single-select and multi-select support
  - Rich option descriptions
  - "Other" text input field
  - Validation before submission
  - Answer summary display
- `sendQuestionAnswer()` - Send answers to backend

#### `bassi/static/style.css`
- Complete styling for question dialogs
- Responsive button states
- Smooth transitions and hover effects
- Selected state highlighting
- Summary panel styling
- Dark theme consistent design

### 4. Documentation ✅
- `docs/features_concepts/interactive_questions.md` - Complete feature guide
- `docs/INTERACTIVE_QUESTIONS_IMPLEMENTATION.md` - This document
- Inline code documentation

### 5. Tests ✅
- `bassi/core_v3/tests/test_interactive_questions.py`
  - Question validation tests
  - Single question tests
  - Multiple questions tests
  - MultiSelect tests
  - Timeout tests
  - Cancellation tests
  - Error handling tests

## API Specification

### Tool Signature
```python
@tool("AskUserQuestion", description, schema)
async def ask_user_question(args: dict) -> dict
```

### Input Schema
```typescript
{
  questions: [  // 1-4 questions required
    {
      question: string,      // Complete question text
      header: string,        // Max 12 chars
      multiSelect: boolean,  // Allow multiple selections
      options: [             // 2-4 options
        {
          label: string,       // 1-5 words
          description: string  // Explanation
        }
      ]
    }
  ]
}
```

### Output Format
```typescript
{
  [questionText: string]: string | string[]
  // Single answer for non-multiSelect
  // Array of answers for multiSelect
}
```

## Example Usage

### From a Skill or Command
```python
# The agent can now call this tool:
result = ask_user_question({
    "questions": [{
        "question": "Which authentication method should we use?",
        "header": "Auth Method",
        "multiSelect": False,
        "options": [
            {"label": "OAuth 2.0", "description": "Industry-standard OAuth protocol"},
            {"label": "JWT", "description": "JSON Web Token authentication"},
            {"label": "API Key", "description": "Simple API key authentication"}
        ]
    }]
})

# Agent receives:
# "User has answered your questions: 'Which authentication method should we use?'=OAuth 2.0.
#  You can now continue with the user's answers in mind."
```

### Multiple Questions with MultiSelect
```python
result = ask_user_question({
    "questions": [
        {
            "question": "Which features should we implement?",
            "header": "Features",
            "multiSelect": True,
            "options": [
                {"label": "User Login", "description": "Authentication system"},
                {"label": "Dashboard", "description": "Analytics dashboard"},
                {"label": "API", "description": "REST API endpoints"}
            ]
        },
        {
            "question": "What database should we use?",
            "header": "Database",
            "multiSelect": False,
            "options": [
                {"label": "PostgreSQL", "description": "Relational database"},
                {"label": "MongoDB", "description": "Document database"}
            ]
        }
    ]
})

# Returns answers for both questions
```

## Architecture Flow

```
┌─────────────┐
│   Agent     │
│  (Claude)   │
└──────┬──────┘
       │ Calls AskUserQuestion tool
       ▼
┌──────────────────────────┐
│ AskUserQuestion Tool     │
│ (bassi/core_v3/tools.py) │
└──────┬───────────────────┘
       │ Calls service.ask()
       ▼
┌─────────────────────────────────┐
│ InteractiveQuestionService      │
│ (creates asyncio.Event)         │
└──────┬──────────────────────────┘
       │ Sends "question" event
       ▼
┌──────────────────┐
│   WebSocket      │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│   Web UI         │
│ - Shows dialog   │
│ - User selects   │
│ - Clicks Submit  │
└──────┬───────────┘
       │ Sends "answer" event
       ▼
┌──────────────────┐
│   WebSocket      │
└──────┬───────────┘
       │ Calls service.submit_answer()
       ▼
┌─────────────────────────────────┐
│ InteractiveQuestionService      │
│ (triggers asyncio.Event)        │
└──────┬──────────────────────────┘
       │ Returns answer
       ▼
┌──────────────────────────┐
│ AskUserQuestion Tool     │
│ (formats response)       │
└──────┬───────────────────┘
       │ Returns to agent
       ▼
┌─────────────┐
│   Agent     │
│  continues  │
└─────────────┘
```

## WebSocket Protocol

### Question Event (Backend → Frontend)
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
        {
          "label": "OAuth 2.0",
          "description": "Industry-standard OAuth protocol"
        },
        {
          "label": "JWT",
          "description": "JSON Web Token authentication"
        }
      ]
    }
  ]
}
```

### Answer Event (Frontend → Backend)
```json
{
  "type": "answer",
  "question_id": "uuid-123",
  "answers": {
    "Which authentication method should we use?": "OAuth 2.0"
  }
}
```

## Key Features

✅ **Full API Compatibility** - Matches Claude Code's AskUserQuestion exactly
✅ **MultiSelect Support** - Users can select multiple options
✅ **Rich Descriptions** - Each option has a detailed explanation
✅ **"Other" Option** - Always available for custom text input
✅ **Multiple Questions** - Ask up to 4 related questions at once
✅ **Timeout Handling** - Auto-fail after 5 minutes (configurable)
✅ **Session Isolation** - Each WebSocket connection has its own service
✅ **Graceful Cleanup** - Cancels pending questions on disconnect
✅ **Validation** - Schema validation on both backend and frontend
✅ **Beautiful UI** - Polished, responsive design matching Bassi's theme
✅ **Answer Summary** - Shows what user selected after submission

## Testing

Run tests:
```bash
uv run pytest bassi/core_v3/tests/test_interactive_questions.py -v
```

## Future Enhancements

Potential improvements:
1. **Conditional Questions** - Show questions based on previous answers
2. **Validation Rules** - Add regex/range validation for "Other" input
3. **Default Values** - Pre-select certain options
4. **Question History** - Track user preferences across sessions
5. **Rich Media** - Support images in option descriptions
6. **Keyboard Navigation** - Arrow keys to navigate options
7. **Analytics** - Track which options users commonly select

## Files Modified/Created

### Created:
- `bassi/core_v3/interactive_questions.py` (230 lines)
- `bassi/core_v3/tools.py` (160 lines)
- `bassi/core_v3/tests/test_interactive_questions.py` (280 lines)
- `docs/features_concepts/interactive_questions.md`
- `docs/INTERACTIVE_QUESTIONS_IMPLEMENTATION.md` (this file)

### Modified:
- `bassi/core_v3/web_server_v3.py` (added question handling)
- `bassi/static/app.js` (added question UI)
- `bassi/static/style.css` (added question styles)

## Conclusion

The interactive questions system is now fully functional and ready to use. Skills and commands can ask structured questions during execution, providing a much better UX than text-based confirmation prompts.

The implementation closely mirrors Claude Code's own AskUserQuestion tool, ensuring familiar behavior for users and consistent API for developers.

**Status: ✅ COMPLETE AND READY FOR USE**
