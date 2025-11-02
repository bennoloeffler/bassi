# CRM Command Documentation

## Overview

The `/crm` slash command is a powerful CRM data extraction and management tool that:

1. **Extracts** CRM data from natural language text
2. **Identifies** actions to perform
3. **Executes** database operations using the `crm-db` skill and PostgreSQL MCP server

## Quick Start

### Basic Usage

In Bassi chat, use the `/crm` command followed by your request:

```
/crm Create a new company "TechStart GmbH" in Berlin, industry: Software Development
```

```
/crm Add contact: Maria Schmidt, email maria@techstart.de, CTO at TechStart GmbH
```

```
/crm Log meeting with Maria Schmidt about new software license deal worth €50,000
```

## What the Command Does

### 1. Data Extraction

The command automatically extracts CRM entities from your text:

**Companies**
- Name (required)
- Address (street, city, postal code, country)
- Industry
- Website
- LinkedIn URL
- Company size
- Annual revenue

**Contacts/Persons**
- Name (required)
- Email
- Phone
- Job title
- Department
- Company affiliation

**Sales Opportunities**
- Title (required)
- Value in EUR
- Probability (%)
- Status (open, in_progress, won, lost)
- Expected close date
- Related contacts and companies

**Events/Activities**
- Type (meeting, call, email, note, task)
- Description
- Date/time
- Related entities

### 2. Database Operations

Uses the `crm-db` skill to interact with PostgreSQL:

- **CREATE**: Add new records
- **READ**: Search and retrieve data
- **UPDATE**: Modify existing records
- **DELETE**: Remove records (with confirmation)
- **ANALYZE**: Generate reports and insights

## Example Use Cases

### Creating a New Company

```
/crm New company: Acme Corporation
Address: Hauptstraße 123, 10115 Berlin, Germany
Industry: Manufacturing
Website: www.acme-corp.de
Size: 50-200 employees
Annual revenue: €5M
```

**What happens:**
1. Extracts company data from text
2. Checks for duplicates
3. Inserts into `company_site` table
4. Returns the new company ID and confirmation

### Adding a Contact Person

```
/crm Contact: John Müller
Email: j.mueller@acme-corp.de
Phone: +49 30 12345678
Company: Acme Corporation
Job Title: Sales Director
Department: Sales
```

**What happens:**
1. Extracts person data
2. Finds the company (Acme Corporation)
3. Creates person record linked to company
4. Returns person ID and details

### Creating a Sales Opportunity

```
/crm New opportunity: "ERP System Implementation"
Value: €150,000
Probability: 60%
Status: open
Expected close: 2025-12-31
Contact: John Müller at Acme Corporation
Description: Full ERP system replacement project
Next steps: Schedule technical workshop
```

**What happens:**
1. Extracts opportunity details
2. Links to John Müller and Acme Corporation
3. Creates sales_opportunity record
4. Logs initial activity event
5. Returns opportunity tracking info

### Logging Activities

```
/crm Meeting with John Müller today at 14:00
Discussed ERP requirements, technical specifications, and timeline.
Next step: Prepare technical proposal by next Friday.
```

**What happens:**
1. Creates event record (type: meeting)
2. Links to John Müller and related opportunity
3. Extracts next steps
4. Timestamps the activity

### Searching and Reporting

```
/crm Show all open opportunities for Acme Corporation
```

```
/crm List all contacts in the Software Development industry
```

```
/crm What activities did we have with John Müller in the last 30 days?
```

```
/crm Total value of all open opportunities in Q4 2025
```

## Database Schema

The CRM database has 5 main tables:

1. **company_site** - Company locations and information
2. **person** - Contact persons linked to companies
3. **sales_opportunity** - Sales pipeline and deals
4. **event** - Activity history (meetings, calls, emails, notes)
5. **adressen** - Legacy address table (for migration)

### Relationships

```
company_site (1) ──┬── (N) person
                   ├── (N) sales_opportunity
                   └── (N) event

person (1) ────────┬── (N) sales_opportunity
                   └── (N) event

sales_opportunity (1) ── (N) event
```

## Advanced Features

### JSONB Tags

All main entities support flexible tagging:

```
/crm Tag Acme Corporation with: vip, manufacturing, large-account
```

### Metadata

Events can store structured metadata:

```
/crm Log call with John - metadata: duration: 45min, quality: good, follow-up-needed: true
```

### Bulk Operations

```
/crm Import contacts from this list:
- Maria Schmidt, maria@techstart.de, CTO, TechStart GmbH
- Peter Weber, p.weber@innovate.de, CEO, InnovateLabs
- Anna Klein, anna@fastgrow.de, CFO, FastGrow AG
```

### Analytics

```
/crm Analyze: conversion rate by industry for Q4 2025
```

```
/crm Report: top 10 opportunities by value, show expected close dates
```

## Best Practices

### 1. Always Link Entities

When creating opportunities or events, always reference the related company and person:

✅ **Good:**
```
/crm Meeting with Maria Schmidt at TechStart about the software deal
```

❌ **Avoid:**
```
/crm Meeting about software
```

### 2. Use Descriptive Titles

For opportunities and events:

✅ **Good:**
```
/crm Opportunity: "TechStart - Cloud Migration Project Q1 2026"
```

❌ **Avoid:**
```
/crm New deal
```

### 3. Track Everything

Log all customer interactions:

```
/crm Email to Maria - sent proposal for cloud migration, awaiting feedback
```

```
/crm Note: Maria mentioned budget concerns, need to prepare ROI analysis
```

### 4. Update Probabilities

Keep opportunity probabilities current:

```
/crm Update TechStart cloud migration opportunity: probability 80%, status in_progress
```

### 5. Use Tags for Organization

```
/crm Tag this opportunity: q1-priority, cloud, existing-customer
```

## Troubleshooting

### Command Not Found

If `/crm` doesn't work:

1. Check `.claude/commands/crm.md` exists
2. Restart Bassi server
3. Verify in startup discovery output

### Skill Not Loading

If `crm-db` skill isn't available:

1. Check `.claude/skills/crm-db/SKILL.md` exists
2. Verify `setting_sources` includes "project"
3. Check startup logs for skill loading

### PostgreSQL Connection Issues

If database operations fail:

1. Ensure PostgreSQL is running
2. Check database `crm_data_bassi` exists
3. Verify credentials in `.mcp.json`
4. Test with: `psql -h localhost -U postgres -d crm_data_bassi`

## Technical Details

### Files

- **Command**: `.claude/commands/crm.md`
- **Skill**: `.claude/skills/crm-db/SKILL.md`
- **Database**: PostgreSQL `crm_data_bassi`
- **MCP Server**: `@executeautomation/database-server`

### Tools Used

The command orchestrates these tools:

1. **Skill** - Loads `crm-db` skill for schema knowledge
2. **MCP Tools**:
   - `mcp__postgresql__read_query` - SELECT queries
   - `mcp__postgresql__write_query` - INSERT/UPDATE/DELETE

### Workflow

```
User Input
    ↓
/crm command invoked
    ↓
Extract CRM entities
    ↓
Load crm-db skill
    ↓
Validate data
    ↓
Execute PostgreSQL queries
    ↓
Return results
    ↓
Suggest next steps
```

## Examples Repository

See `docs/examples/crm_examples.md` for more detailed examples and templates.

## See Also

- [MCP Integration](./mcp_integration.md) - PostgreSQL MCP server setup
- [Skills](https://docs.claude.com/en/docs/agents-and-tools/agent-skills) - About Claude skills
- [Slash Commands](https://docs.claude.com/en/docs/claude-code/slash-commands) - Command documentation
