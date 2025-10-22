# Bassi Architecture Documentation - Complete Index

This directory contains comprehensive documentation of the Bassi architecture. Use this index to find the right document for your needs.

## Document Overview

### 1. ARCHITECTURE_OVERVIEW.md (35 KB)
**Purpose**: Complete, detailed reference of the entire system architecture

**Covers**:
- Executive summary & three-layer architecture diagram
- Complete directory structure with file descriptions
- BassiAgent class detailed reference (attributes, methods, message flow)
- MCP Server types (SDK in-process & external subprocess)
- Data models & configuration (Config, ConfigManager, .bassi_context.json)
- Streaming & response handling (message types, real-time text, markdown rendering)
- Context management (window size, auto-compaction, token tracking)
- Permission model (bypassPermissions mode and alternatives)
- System prompt architecture
- Dependency management
- Testing architecture
- Logging & debugging
- Async architecture
- Complete example conversation flow
- Key architectural decisions (14 major decisions explained)
- Integration points (SDK, external servers, APIs)
- Future architecture considerations
- Quality assurance pipeline
- Documentation structure

**Best for**:
- Deep understanding of system
- Reference during development
- Understanding design decisions
- Troubleshooting complex issues
- System redesign/major changes

**How to read**:
1. Start with Executive Summary
2. Read Overall Architecture section
3. Jump to specific sections as needed
4. Use table of contents (section numbers)

---

### 2. ARCHITECTURE_QUICK_REF.md (5.4 KB)
**Purpose**: Quick lookup reference for common questions

**Covers**:
- Three-layer architecture diagram
- Core files table (5 key files, line counts, purposes)
- Key concepts (MCP servers, agent state, message flow)
- Commands reference (7 user-facing commands)
- Configuration (priority, environment variables)
- Permission model (bypassPermissions explanation)
- Async architecture overview
- Testing commands
- Logging location & debug enable
- Session resumption flow
- Adding new MCP servers (quick steps for both types)
- Dependencies (key packages)
- System prompt location
- Design decisions table
- Future roadmap

**Best for**:
- Quick lookups while coding
- Print and post near desk
- New team members learning basics
- Command reference
- Quick architecture refresh

**How to read**:
- Use table of contents
- Search for specific topic
- Each section is self-contained

---

### 3. MCP_SERVER_ARCHITECTURE.md (17 KB)
**Purpose**: Comprehensive guide to MCP (Model Context Protocol) server integration

**Covers**:
- Overview of two server types
- SDK MCP Servers in detail:
  - Design pattern with code example
  - Bash server implementation (code walkthrough)
  - Web search server implementation (code walkthrough)
  - Registration pattern
  - Return format specification
- External MCP Servers in detail:
  - Configuration via .mcp.json
  - Environment variable substitution
  - MS365 MCP Server setup
  - Playwright MCP Server setup
  - Loading process flowchart
  - Subprocess management
- Tool naming convention
- Tool registration in allowed_tools
- System prompt integration
- Adding new MCP servers (detailed steps for both types)
- Tool execution flow with diagrams
- Error handling patterns
- Tool interaction patterns
- Testing MCP servers
- Performance considerations
- Debugging guidance
- Common issues table
- Summary

**Best for**:
- Adding new MCP servers (SDK or external)
- Understanding tool execution
- Debugging MCP-related issues
- Understanding tool naming convention
- Configuration reference

**How to read**:
1. Start with Overview
2. Read relevant server type section
3. Use "Adding New MCP Servers" when extending
4. Reference Tool Execution Flow for understanding
5. Use Debugging section for troubleshooting

---

## Quick Navigation Guide

### I want to...

**Understand the overall system**
→ Start with ARCHITECTURE_OVERVIEW.md, section 1-2, then Executive Summary

**Add a new SDK MCP server**
→ MCP_SERVER_ARCHITECTURE.md, "Adding SDK MCP Server" section

**Add a new external MCP server**
→ MCP_SERVER_ARCHITECTURE.md, "Adding External MCP Server" section

**Understand message flow**
→ ARCHITECTURE_OVERVIEW.md, section 5 (Streaming & Response Handling)

**Debug an issue**
→ ARCHITECTURE_OVERVIEW.md, section 11 (Logging & Debugging)
→ MCP_SERVER_ARCHITECTURE.md, "Debugging MCP Servers" section

**Understand context management**
→ ARCHITECTURE_OVERVIEW.md, section 6 (Context Management)

**Understand permission model**
→ ARCHITECTURE_OVERVIEW.md, section 7 (Permission Model)
OR
→ docs/features_concepts/permissions.md (user-facing documentation)

**Quick reference while coding**
→ ARCHITECTURE_QUICK_REF.md

**Understand configuration**
→ ARCHITECTURE_OVERVIEW.md, section 4 (Data Models & Configuration)

**Understand testing**
→ ARCHITECTURE_OVERVIEW.md, section 10 (Testing Architecture)

**Understand MCP server types**
→ MCP_SERVER_ARCHITECTURE.md, sections "SDK MCP Servers" or "External MCP Servers"

**Complete example flow**
→ ARCHITECTURE_OVERVIEW.md, section 13 (Example Flow: Complete Conversation)

**Design decisions**
→ ARCHITECTURE_OVERVIEW.md, section 14 (Key Architectural Decisions)

---

## Related Documentation

These documents complement the architecture documentation:

### Project Documentation
- **CLAUDE.md** - Claude Code project instructions
- **CLAUDE_BBS.md** - BBS philosophy for project development
- **README.md** - User-facing project overview

### Feature-Specific Documentation
- **docs/vision.md** - Project vision & roadmap (iterations 1-9)
- **docs/design.md** - Design document with use cases
- **docs/requirements.md** - Technical requirements
- **docs/features_concepts/permissions.md** - Permission model (user docs)
- **docs/features_concepts/o365_authentication.md** - O365 authentication guide
- **docs/features_concepts/web_search.md** - Web search feature documentation
- **docs/features_concepts/context_compaction.md** - Context management details
- **docs/features_concepts/verbose_mode.md** - Verbose mode feature docs

### Implementation Files
- **bassi/main.py** - CLI entry point and main loop
- **bassi/agent.py** - BassiAgent class (core logic)
- **bassi/config.py** - Configuration management
- **bassi/mcp_servers/** - MCP server implementations
- **tests/** - Test suite

---

## Architecture at a Glance

### Three-Layer System

```
┌─────────────────────────────────────────┐
│ CLI Layer (main.py)                     │
│ - User input handling                   │
│ - Command routing                       │
│ - Session management                    │
└──────────────┬──────────────────────────┘
               ↓
┌─────────────────────────────────────────┐
│ Agent Layer (agent.py)                  │
│ - Streaming responses                   │
│ - Context management                    │
│ - MCP server coordination                │
└──────────────┬──────────────────────────┘
               ↓
┌─────────────────────────────────────────┐
│ MCP Servers                             │
│ - SDK: bash, web (in-process)           │
│ - External: ms365, playwright (subproc) │
└─────────────────────────────────────────┘
```

### Key Statistics

| Metric | Value |
|--------|-------|
| Main package files | 4 Python files |
| Total agent code | ~824 lines |
| Total CLI code | ~510 lines |
| SDK MCP servers | 2 (bash, web) |
| External MCP servers | 2 (ms365, playwright) |
| Total tools available | 20+ |
| Context window | 200K tokens |
| Compaction threshold | 150K tokens (75%) |
| Permission mode | bypassPermissions |

### Core Technologies

- **Framework**: Claude Agent SDK
- **API**: Anthropic API (Claude Sonnet 4.5)
- **Language**: Python 3.11+
- **Package Manager**: uv
- **Terminal UI**: Rich
- **Async Runtime**: anyio
- **Data Validation**: Pydantic
- **External APIs**: Tavily (web search), Microsoft Graph (O365)

---

## Document Statistics

| Document | Size | Sections | Best For |
|----------|------|----------|----------|
| ARCHITECTURE_OVERVIEW.md | 35 KB | 18 | Deep reference |
| ARCHITECTURE_QUICK_REF.md | 5.4 KB | 20 | Quick lookup |
| MCP_SERVER_ARCHITECTURE.md | 17 KB | 16 | MCP/tool development |

**Total documentation**: ~58 KB of detailed architecture reference

---

## Reading Paths

### Path 1: First-Time Understanding (30 minutes)
1. Read ARCHITECTURE_QUICK_REF.md (5 min)
2. Read ARCHITECTURE_OVERVIEW.md sections 1-3 (10 min)
3. Skim MCP_SERVER_ARCHITECTURE.md "Overview" (5 min)
4. Read ARCHITECTURE_OVERVIEW.md section 13 "Example Flow" (10 min)

### Path 2: Adding New Feature (1 hour)
1. ARCHITECTURE_QUICK_REF.md - Core concepts (5 min)
2. ARCHITECTURE_OVERVIEW.md sections 3 & 14 - Agent & decisions (15 min)
3. MCP_SERVER_ARCHITECTURE.md "Adding New MCP Servers" (20 min)
4. Feature-specific documentation in docs/features_concepts/ (20 min)

### Path 3: Debugging Issue (varies)
1. ARCHITECTURE_QUICK_REF.md - Find relevant section (5 min)
2. ARCHITECTURE_OVERVIEW.md section 11 - Logging & debugging (10 min)
3. Specific documentation section (5-30 min)
4. Code review as needed

### Path 4: Deep Dive (2+ hours)
1. ARCHITECTURE_OVERVIEW.md - Read all sections in order
2. MCP_SERVER_ARCHITECTURE.md - Read all sections in order
3. Review related code files (bassi/agent.py, bassi/main.py)
4. Review test files (tests/test_agent.py, tests/test_use_cases.py)

---

## Key Concepts Defined

### MCP (Model Context Protocol)
- Framework for connecting Claude to external tools
- Two implementation types: SDK (in-process) and external (subprocess)
- Tools accessed via naming convention: `mcp__<server>__<tool>`

### Session Resumption
- Persisting conversation context across CLI restarts
- Session ID saved to `.bassi_context.json`
- SDK handles resumption internally via `resume` parameter

### Context Window
- Total tokens available: 200K
- Auto-compaction at 150K (75%)
- Preserves recent conversation while making room for new interaction

### Permission Mode
- `bypassPermissions`: All tools execute without confirmation (current)
- `default`: Ask for permission for each operation
- `acceptEdits`: Auto-approve file operations, ask for others

### Streaming
- Real-time token-by-token response delivery
- Accumulates text for markdown rendering after completion

---

## Development Workflow

### Typical Development Cycle

1. **Understand feature** → Read relevant architecture section
2. **Design solution** → Reference architectural decisions
3. **Implement** → Follow existing patterns (SDK or external MCP)
4. **Test** → Use test patterns from section 10
5. **Document** → Update docs/features_concepts/
6. **Review** → Check quality with ./check.sh

### Quality Checks

```bash
./check.sh   # Format + lint + type check + test
```

Runs automatically:
1. black . - Code formatting
2. ruff check --fix . - Linting
3. mypy . - Type checking
4. uv run pytest - All tests

---

## Common Tasks

### Add SDK MCP Server
- Read: MCP_SERVER_ARCHITECTURE.md "Adding SDK MCP Server"
- Time: ~30 min
- Files: Create new file + 3 edits + test

### Add External MCP Server
- Read: MCP_SERVER_ARCHITECTURE.md "Adding External MCP Server"
- Time: ~20 min
- Files: .mcp.json + .env + agent.py edits

### Debug Streaming Issue
- Read: ARCHITECTURE_OVERVIEW.md section 5
- Time: ~15 min
- Files: Review _display_message() in agent.py

### Understand Token Usage
- Read: ARCHITECTURE_OVERVIEW.md section 6
- Time: ~10 min
- Files: Review ResultMessage handling in agent.py

---

## Feedback & Updates

These documents are maintained with the codebase:

- Update when architecture changes significantly
- Keep code examples synchronized
- Maintain document links/references
- Update statistics as project grows
- Review quarterly for accuracy

Last Updated: 2025-01-22

