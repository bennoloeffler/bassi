# CRM Database Schema Reference

## Overview

PostgreSQL database schema for a CRM system with companies, contacts, sales opportunities, and activity tracking.

## Entity Relationships

```
company_site (1) ←→ (many) person
    │                       │
    │                       │
    └─────→ (many) sales_opportunity (many) ←─────┘
                    │
                    │
                    ↓
                  event (can reference person, company_site, or opportunity)
```

## Tables

### company_site
Company and organization information.

**Columns:**
- `id` INTEGER PRIMARY KEY (auto-increment)
- `name` VARCHAR NOT NULL - Company name
- `address_street` VARCHAR - Street address
- `address_city` VARCHAR - City
- `address_state` VARCHAR - State/region
- `address_postal_code` VARCHAR - Postal code
- `address_country` VARCHAR - Country
- `industry` VARCHAR - Industry sector
- `website` VARCHAR - Company website URL
- `linkedin_company_url` VARCHAR - LinkedIn company page URL
- `company_size` VARCHAR - Company size description
- `annual_revenue` BIGINT - Annual revenue amount
- `notes` TEXT - Free-form notes
- `tags` JSONB - JSON array of tags
- `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
- `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP

**Foreign Keys:** None (root entity)

**Example Tags:**
```json
["prospect", "technology", "enterprise"]
```

---

### person
Individual contacts and their relationships to companies.

**Columns:**
- `id` INTEGER PRIMARY KEY (auto-increment)
- `name` VARCHAR NOT NULL - Full name
- `email` VARCHAR - Email address
- `phone` VARCHAR - Phone number
- `linkedin_url` VARCHAR - LinkedIn profile URL
- `company_site_id` INTEGER - Foreign key to company_site.id
- `job_title` VARCHAR - Job title
- `department` VARCHAR - Department name
- `notes` TEXT - Free-form notes
- `tags` JSONB - JSON array of tags
- `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
- `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP

**Foreign Keys:**
- `company_site_id` → `company_site(id)`

**Example Tags:**
```json
["decision-maker", "technical", "champion"]
```

---

### sales_opportunity
Sales pipeline and opportunity tracking.

**Columns:**
- `id` INTEGER PRIMARY KEY (auto-increment)
- `title` VARCHAR NOT NULL - Opportunity name
- `value_eur` NUMERIC - Opportunity value in EUR
- `probability` INTEGER - Win probability (0-100)
- `status` VARCHAR DEFAULT 'open' - Status (open, won, lost, etc.)
- `description` TEXT - Detailed description
- `expected_close_date` DATE - Expected closing date
- `actual_close_date` DATE - Actual closing date
- `person_id` INTEGER - Primary contact
- `company_site_id` INTEGER - Company
- `source` VARCHAR - Lead source
- `competitors` TEXT - Competitor information
- `next_steps` TEXT - Next action items
- `notes` TEXT - Free-form notes
- `tags` JSONB - JSON array of tags
- `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
- `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP

**Foreign Keys:**
- `person_id` → `person(id)`
- `company_site_id` → `company_site(id)`

**Common Status Values:**
- `open` - Active opportunity
- `won` - Successfully closed
- `lost` - Lost to competitor or no decision
- `qualified` - Qualified lead
- `proposal` - Proposal submitted

**Example Tags:**
```json
["high-priority", "q4-2025", "recurring-revenue"]
```

---

### event
Activity timeline tracking interactions and milestones.

**Columns:**
- `id` INTEGER PRIMARY KEY (auto-increment)
- `type` VARCHAR NOT NULL - Event type
- `description` TEXT NOT NULL - Event description
- `event_date` TIMESTAMP NOT NULL - When event occurred
- `person_id` INTEGER - Related person (optional)
- `company_site_id` INTEGER - Related company (optional)
- `opportunity_id` INTEGER - Related opportunity (optional)
- `metadata` JSONB - Additional structured data
- `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP

**Foreign Keys:**
- `person_id` → `person(id)`
- `company_site_id` → `company_site(id)`
- `opportunity_id` → `sales_opportunity(id)`

**Common Event Types:**
- `email` - Email sent/received
- `call` - Phone call
- `meeting` - Meeting held
- `note` - General note
- `status_change` - Opportunity status change
- `demo` - Product demo
- `proposal` - Proposal sent

**Example Metadata:**
```json
{
  "subject": "Follow-up on demo",
  "duration_minutes": 30,
  "outcome": "positive",
  "next_action": "Send proposal"
}
```

---

## JSONB Field Guidelines

### Querying JSONB Tags

**Check if tag exists:**
```sql
WHERE tags ? 'enterprise'
```

**Check if any tag exists:**
```sql
WHERE tags ?| ARRAY['prospect', 'customer']
```

**Check if all tags exist:**
```sql
WHERE tags ?& ARRAY['enterprise', 'technology']
```

**Filter by nested JSONB:**
```sql
WHERE metadata @> '{"outcome": "positive"}'
```

### Updating JSONB Fields

**Add a tag:**
```sql
UPDATE person
SET tags = tags || '["new-tag"]'::jsonb
WHERE id = 1;
```

**Remove a tag:**
```sql
UPDATE person
SET tags = tags - 'old-tag'
WHERE id = 1;
```

**Update nested metadata:**
```sql
UPDATE event
SET metadata = jsonb_set(metadata, '{outcome}', '"positive"')
WHERE id = 1;
```

---

## Indexes

Consider creating indexes for common query patterns:

```sql
-- Email lookups
CREATE INDEX idx_person_email ON person(email);

-- Company lookups
CREATE INDEX idx_person_company ON person(company_site_id);

-- Opportunity status
CREATE INDEX idx_opportunity_status ON sales_opportunity(status);

-- Event dates
CREATE INDEX idx_event_date ON event(event_date);

-- JSONB tag searches
CREATE INDEX idx_person_tags ON person USING gin(tags);
CREATE INDEX idx_opportunity_tags ON sales_opportunity USING gin(tags);
```
