---
description: Enhanced help system showing local ecosystem of agents, skills, and commands with interactive exploration
---

# Enhanced Help Command

**Interactive help system for Claude Code local ecosystem.**

Shows available agents, skills, and custom commands with detailed information, examples, and workflow patterns.

## Usage

```
/help-enhanced              → Overview of entire ecosystem
/help-enhanced agents       → List all agents
/help-enhanced skills       → List all skills
/help-enhanced commands     → List all custom commands
/help-enhanced ecosystem    → Complete ecosystem map with workflows
/help-enhanced <name>       → Details on specific agent/skill/command
/help-enhanced search <term> → Search for tools by keyword
```

## What This Shows

### 1. AGENTS (Specialized AI Workers)
- test-writer-agent: Creates individual tests with high quality
- test-collector-agent: Merges tests from parallel agents
- bulk-archive-agent: Archives multiple emails efficiently

### 2. SKILLS (Specialized Toolkits)
- Document tools: pdf, docx, pptx, xlsx
- Integration tools: bel-email-manager, bel-contact-creator, bel-crm-db
- Utilities: time-formatter, mcp-builder, skill-creator

### 3. COMMANDS (Quick Access Shortcuts)
- /adresse-erstellen: Create Outlook contacts from text
- /bel-write-tests-one-by-one: Parallel test writing
- /crm: CRM data operations
- /email-analysis: Email analysis and categorization

### 4. ECOSYSTEM MAP
- Shows workflow patterns (email → contacts → CRM)
- How tools connect to each other
- "When to use what" decision tree

## Interactive Exploration

Click on any item name to see full details:
- Complete description
- All capabilities
- When to use
- Real examples
- Links to related tools
- File location in project

## Common Workflows

**Email Management:**
/email-analysis → bel-email-manager → Microsoft 365

**Contact Creation:**
/adresse-erstellen → contact-creator → Outlook

**CRM Operations:**
/crm → bel-crm-db → PostgreSQL database

**Test Writing:**
/bel-write-tests-one-by-one → test-writer-agent (parallel) → test-collector-agent → merged tests

**Document Processing:**
xlsx (create data) → pdf (export) → pptx (present)

## Implementation Details

The help system is powered by:
- `bassi/shared/help_system.py`: Ecosystem scanner
- `bassi/shared/help_formatter.py`: Terminal output formatter
- Scans `.claude/` directory automatically
- Always reflects your current tools
- No manual updates needed
