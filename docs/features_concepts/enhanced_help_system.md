# Enhanced Help System

## Overview

The enhanced help system provides interactive, intelligent help for your Claude Code local ecosystem. It automatically discovers and indexes:

- **Agents** - Specialized AI workers from `.claude/agents/`
- **Skills** - Purpose-built tool kits from `.claude/skills/`
- **Custom Commands** - Slash commands from `.claude/commands/`

## Architecture

### Core Components

1. **EcosystemScanner** (`bassi/shared/help_system.py`)
   - Scans `.claude/` directory structure
   - Parses YAML frontmatter and markdown sections
   - Builds relationship graph between tools
   - Provides search and lookup functionality

2. **HelpFormatter** (`bassi/shared/help_formatter.py`)
   - Generates beautifully formatted terminal output
   - Uses Unicode box-drawing characters
   - Supports different output formats (overview, list, detail, ecosystem map)
   - Handles text wrapping and layout

3. **Command** (`.claude/commands/help-enhanced.md`)
   - User-facing interface to the help system
   - Can be invoked as `/help-enhanced <query>`

## Usage

### Basic Commands

```bash
/help-enhanced                # Show overview of entire ecosystem
/help-enhanced agents         # List all agents
/help-enhanced skills         # List all skills
/help-enhanced commands       # List all custom commands
/help-enhanced ecosystem      # Show complete ecosystem map
/help-enhanced <name>         # Show details for specific tool
```

### Example: Get Help on XLSX Skill

```
/help-enhanced xlsx

Output:
═══════════════════════════════════════════════════
           📊 XLSX Skill - Spreadsheet Operations
═══════════════════════════════════════════════════

QUICK FACTS:
• Type: Skill (specialized toolkit)
• Location: .claude/skills/xlsx/SKILL.md

DESCRIPTION:
Comprehensive spreadsheet creation, editing, and analysis
with support for formulas, formatting, data analysis, and
visualization...

CAPABILITIES:
✓ Create spreadsheets
✓ Edit existing files
✓ Data analysis
✓ Visualization

WHEN TO USE:
→ Creating expense reports or budgets
→ Analyzing data with formulas
→ Converting data to different formats

EXAMPLES:
1. Create a budget spreadsheet
2. Analyze sales data
3. Format a report
```

## What Gets Scanned

### Agents Directory
Pattern: `.claude/agents/*.md`

Extracts:
- Agent name (from filename)
- Description (from YAML or first paragraph)
- Purpose and capabilities
- When to use recommendations

### Skills Directory
Pattern: `.claude/skills/*/SKILL.md`

Extracts:
- Skill name (from directory name)
- Type/category
- Capabilities list
- When to use guidelines
- Examples (if present)

### Commands Directory
Pattern: `.claude/commands/*.md`

Extracts:
- Command name (from filename)
- Description (from YAML)
- Usage patterns
- Related skills (from YAML metadata)

## Key Features

### 1. Auto-Discovery
No manual configuration needed. The system automatically:
- Detects new commands/skills/agents
- Parses their documentation
- Updates the help system

### 2. Relationship Mapping
The system understands:
- Which commands activate which skills
- Which skills depend on tools
- Workflow patterns (email → contacts → CRM)

### 3. Interactive Exploration
Users can:
- Browse by type (agents/skills/commands)
- Look up specific items by name
- Search across descriptions
- See related items

### 4. Beautiful Terminal Output
Uses Unicode characters for:
- Box borders
- Section headers
- Visual hierarchy
- Proper text wrapping

## Testing

Comprehensive test suite with 29 tests:

```bash
# Run help system tests
uv run pytest bassi/core_v3/tests/test_help_system.py -v

# Run specific test class
uv run pytest bassi/core_v3/tests/test_help_system.py::TestHelpFormatter -v

# Run with coverage
uv run pytest bassi/core_v3/tests/test_help_system.py --cov=bassi.shared.help_system
```

### Test Coverage

- **HelpItem**: Creation and normalization
- **EcosystemScanner**: Directory scanning, parsing, searching
- **HelpFormatter**: Formatting, wrapping, box drawing
- **Integration**: End-to-end workflows
- **Markdown Parsing**: YAML frontmatter extraction

## Implementation Details

### YAML Frontmatter Format

All help items should include:

```yaml
---
name: unique-identifier
description: Short description for lists
skill: linked-skill-name (for commands only)
---

# Full Title

Detailed description...

## Capabilities
- Feature 1
- Feature 2

## When to Use
- Scenario 1
- Scenario 2

## Examples
- Example 1
```

### File Organization

```
.claude/
├── commands/
│   ├── help-enhanced.md
│   ├── crm.md
│   └── email-analysis.md
├── skills/
│   ├── pdf/
│   │   └── SKILL.md
│   ├── xlsx/
│   │   └── SKILL.md
│   └── ...
└── agents/
    ├── test-writer-agent.md
    ├── bulk-archive-agent.md
    └── ...
```

## Usage in Code

### Basic Usage

```python
from bassi.shared.help_formatter import format_help

# Show overview
output = format_help()

# Show agents
output = format_help("agents")

# Show details for specific item
output = format_help("xlsx")

print(output)
```

### Advanced Usage

```python
from bassi.shared.help_system import EcosystemScanner
from bassi.shared.help_formatter import HelpFormatter

# Scan ecosystem
scanner = EcosystemScanner()
scanner.scan_all()

# Create formatter
formatter = HelpFormatter(width=80)

# Get specific item
item = scanner.get_item("crm")
if item:
    print(formatter.format_item(item))

# Search for items
results = scanner.search("email")
print(formatter.format_items_list(results, "Email-related tools"))

# Get all skills
skills = scanner.get_by_type("skill")
print(formatter.format_items_list(skills, "Available Skills"))
```

## Workflow Patterns

The help system recognizes common workflows:

### Email Management
```
/email-analysis (command)
  → bel-email-manager (skill)
    → Microsoft 365 email tools
```

### Contact Creation
```
/adresse-erstellen (command)
  → contact-creator (skill)
    → Outlook contacts
```

### CRM Operations
```
/crm (command)
  → bel-crm-db (skill)
    → PostgreSQL database
```

### Test Writing
```
/bel-write-tests-one-by-one (command)
  → test-writer-agent (agent, parallel)
    → test-collector-agent (agent)
      → merged tests
```

## Future Enhancements

Potential improvements:

1. **Interactive Exploration**
   - Add clickable items in web UI
   - Progressive detail disclosure
   - Expandable sections

2. **Search Improvements**
   - Fuzzy matching
   - Tag-based filtering
   - Workflow suggestions

3. **Ecosystem Visualization**
   - ASCII diagrams of tool relationships
   - Dependency graphs
   - Usage frequency tracking

4. **Caching**
   - Cache ecosystem scans
   - Invalidate on file changes
   - Faster subsequent lookups

5. **Integration with Claude Code**
   - Hook into `/help` command directly
   - Show relevant help contextually
   - Link to file locations for quick editing

## Files

- **Implementation**: `bassi/shared/help_system.py`, `bassi/shared/help_formatter.py`
- **Tests**: `bassi/core_v3/tests/test_help_system.py`
- **Command**: `.claude/commands/help-enhanced.md`
- **Example**: `bassi/shared/help_example.py`

## See Also

- [Interactive Questions](./interactive_questions.md) - User input during execution
- [Permissions](./permissions.md) - Tool permission model
- CLAUDE.md - Project guidance
- CLAUDE_TESTS.md - Testing patterns
