# PostgreSQL SQL Examples for CRM Database

## INSERT Operations

### Insert a New Company

```sql
INSERT INTO company_site (
    name,
    address_street,
    address_city,
    address_postal_code,
    address_country,
    industry,
    website,
    linkedin_company_url,
    company_size,
    annual_revenue,
    notes,
    tags
) VALUES (
    'TechCorp AG',
    'Bahnhofstrasse 123',
    'Zürich',
    '8001',
    'Switzerland',
    'Technology',
    'https://techcorp.ch',
    'https://linkedin.com/company/techcorp',
    '50-200 employees',
    5000000,
    'Potential client in fintech space',
    '["prospect", "technology", "fintech"]'::jsonb
)
RETURNING id, name, created_at;
```

### Insert a New Person

```sql
INSERT INTO person (
    name,
    email,
    phone,
    linkedin_url,
    company_site_id,
    job_title,
    department,
    notes,
    tags
) VALUES (
    'Hans Müller',
    'hans.mueller@techcorp.ch',
    '+41 44 123 45 67',
    'https://linkedin.com/in/hansmueller',
    1,  -- company_site_id
    'CTO',
    'Engineering',
    'Met at tech conference in Zurich',
    '["decision-maker", "technical"]'::jsonb
)
RETURNING id, name, company_site_id;
```

### Insert a New Sales Opportunity

```sql
INSERT INTO sales_opportunity (
    title,
    value_eur,
    probability,
    status,
    description,
    expected_close_date,
    person_id,
    company_site_id,
    source,
    next_steps,
    tags
) VALUES (
    'TechCorp - Enterprise License',
    75000,
    60,
    'qualified',
    'Enterprise license for 100 users, 3-year contract',
    '2025-12-31',
    1,  -- person_id
    1,  -- company_site_id
    'Conference',
    'Schedule demo with engineering team',
    '["high-value", "recurring-revenue", "q4-2025"]'::jsonb
)
RETURNING id, title, value_eur, status;
```

### Insert an Event

```sql
INSERT INTO event (
    type,
    description,
    event_date,
    person_id,
    company_site_id,
    opportunity_id,
    metadata
) VALUES (
    'meeting',
    'Initial discovery call with Hans Müller',
    '2025-11-28 14:00:00',
    1,  -- person_id
    1,  -- company_site_id
    1,  -- opportunity_id
    '{
        "duration_minutes": 45,
        "outcome": "positive",
        "attendees": ["Hans Müller", "CTO"],
        "topics": ["product demo", "pricing", "integration"],
        "next_action": "Send proposal by Friday"
    }'::jsonb
)
RETURNING id, type, event_date;
```

---

## UPDATE Operations

### Update Company Information

```sql
UPDATE company_site
SET
    annual_revenue = 8000000,
    company_size = '200-500 employees',
    notes = notes || E'\n\nUpdated: Revenue increased due to new funding round',
    updated_at = CURRENT_TIMESTAMP
WHERE id = 1
RETURNING id, name, annual_revenue;
```

### Update Person's Job Title

```sql
UPDATE person
SET
    job_title = 'VP of Engineering',
    department = 'Engineering',
    updated_at = CURRENT_TIMESTAMP
WHERE id = 1
RETURNING id, name, job_title;
```

### Update Opportunity Status

```sql
UPDATE sales_opportunity
SET
    status = 'won',
    actual_close_date = CURRENT_DATE,
    probability = 100,
    notes = notes || E'\n\nDeal closed successfully!',
    updated_at = CURRENT_TIMESTAMP
WHERE id = 1
RETURNING id, title, status, actual_close_date;
```

### Add Tag to Person

```sql
UPDATE person
SET
    tags = tags || '["champion"]'::jsonb,
    updated_at = CURRENT_TIMESTAMP
WHERE id = 1
RETURNING id, name, tags;
```

### Remove Tag from Opportunity

```sql
UPDATE sales_opportunity
SET
    tags = tags - 'low-priority',
    updated_at = CURRENT_TIMESTAMP
WHERE id = 1
RETURNING id, title, tags;
```

### Update Event Metadata

```sql
UPDATE event
SET metadata = jsonb_set(
    metadata,
    '{outcome}',
    '"deal_closed"'
)
WHERE id = 1
RETURNING id, type, metadata;
```

---

## SELECT Queries

### Get All Companies with Contact Count

```sql
SELECT
    c.id,
    c.name,
    c.industry,
    c.address_city,
    c.address_country,
    c.tags,
    COUNT(p.id) as contact_count
FROM company_site c
LEFT JOIN person p ON p.company_site_id = c.id
GROUP BY c.id, c.name, c.industry, c.address_city, c.address_country, c.tags
ORDER BY c.name;
```

### Get Person with Company Details

```sql
SELECT
    p.id,
    p.name,
    p.email,
    p.phone,
    p.job_title,
    p.department,
    p.tags as person_tags,
    c.name as company_name,
    c.industry,
    c.address_city,
    c.address_country,
    c.website
FROM person p
LEFT JOIN company_site c ON p.company_site_id = c.id
WHERE p.id = 1;
```

### Get All Open Opportunities with Details

```sql
SELECT
    o.id,
    o.title,
    o.value_eur,
    o.probability,
    o.status,
    o.expected_close_date,
    o.tags,
    p.name as contact_name,
    p.email as contact_email,
    c.name as company_name,
    c.industry
FROM sales_opportunity o
LEFT JOIN person p ON o.person_id = p.id
LEFT JOIN company_site c ON o.company_site_id = c.id
WHERE o.status IN ('open', 'qualified', 'proposal')
ORDER BY o.expected_close_date, o.value_eur DESC;
```

### Get Opportunity Pipeline Value by Status

```sql
SELECT
    status,
    COUNT(*) as opportunity_count,
    SUM(value_eur) as total_value,
    AVG(value_eur) as average_value,
    AVG(probability) as average_probability,
    SUM(value_eur * probability / 100.0) as weighted_value
FROM sales_opportunity
WHERE status NOT IN ('lost', 'won')
GROUP BY status
ORDER BY
    CASE status
        WHEN 'qualified' THEN 1
        WHEN 'proposal' THEN 2
        WHEN 'negotiation' THEN 3
        WHEN 'open' THEN 4
        ELSE 5
    END;
```

### Get Recent Events for a Company

```sql
SELECT
    e.id,
    e.type,
    e.description,
    e.event_date,
    e.metadata,
    p.name as person_name,
    o.title as opportunity_title
FROM event e
LEFT JOIN person p ON e.person_id = p.id
LEFT JOIN sales_opportunity o ON e.opportunity_id = o.id
WHERE e.company_site_id = 1
ORDER BY e.event_date DESC
LIMIT 20;
```

### Get Activity Timeline for an Opportunity

```sql
SELECT
    e.id,
    e.type,
    e.description,
    e.event_date,
    e.metadata,
    p.name as person_name
FROM event e
LEFT JOIN person p ON e.person_id = p.id
WHERE e.opportunity_id = 1
ORDER BY e.event_date DESC;
```

### Search Companies by Tag

```sql
SELECT
    id,
    name,
    industry,
    address_city,
    tags
FROM company_site
WHERE tags ? 'enterprise'  -- has 'enterprise' tag
ORDER BY name;
```

### Search People by Multiple Tags (OR)

```sql
SELECT
    p.id,
    p.name,
    p.email,
    p.job_title,
    p.tags,
    c.name as company_name
FROM person p
LEFT JOIN company_site c ON p.company_site_id = c.id
WHERE tags ?| ARRAY['decision-maker', 'champion']  -- has any of these tags
ORDER BY p.name;
```

### Search Events by Metadata

```sql
SELECT
    id,
    type,
    description,
    event_date,
    metadata
FROM event
WHERE
    metadata @> '{"outcome": "positive"}'  -- outcome is positive
    AND event_date >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY event_date DESC;
```

### Get Companies with High-Value Opportunities

```sql
SELECT
    c.id,
    c.name,
    c.industry,
    COUNT(o.id) as opportunity_count,
    SUM(o.value_eur) as total_pipeline_value,
    SUM(CASE WHEN o.status = 'won' THEN o.value_eur ELSE 0 END) as won_value,
    MAX(o.expected_close_date) as latest_close_date
FROM company_site c
INNER JOIN sales_opportunity o ON c.id = o.company_site_id
WHERE o.value_eur > 50000
GROUP BY c.id, c.name, c.industry
HAVING SUM(o.value_eur) > 100000
ORDER BY total_pipeline_value DESC;
```

### Get Decision Makers at Target Companies

```sql
SELECT
    p.id,
    p.name,
    p.email,
    p.phone,
    p.job_title,
    p.linkedin_url,
    c.name as company_name,
    c.industry,
    c.website
FROM person p
INNER JOIN company_site c ON p.company_site_id = c.id
WHERE
    p.tags ? 'decision-maker'
    AND c.tags ? 'prospect'
    AND p.email IS NOT NULL
ORDER BY c.name, p.name;
```

---

## Complex JOIN Queries

### Get Full Sales Pipeline Report

```sql
SELECT
    o.id as opportunity_id,
    o.title,
    o.value_eur,
    o.probability,
    o.status,
    o.expected_close_date,
    o.tags as opportunity_tags,
    c.name as company_name,
    c.industry,
    c.company_size,
    c.tags as company_tags,
    p.name as contact_name,
    p.email as contact_email,
    p.job_title,
    p.tags as contact_tags,
    (
        SELECT COUNT(*)
        FROM event e
        WHERE e.opportunity_id = o.id
    ) as event_count,
    (
        SELECT MAX(event_date)
        FROM event e
        WHERE e.opportunity_id = o.id
    ) as last_activity_date
FROM sales_opportunity o
LEFT JOIN company_site c ON o.company_site_id = c.id
LEFT JOIN person p ON o.person_id = p.id
ORDER BY o.expected_close_date, o.value_eur DESC;
```

### Get Company Overview with All Related Data

```sql
SELECT
    c.id,
    c.name,
    c.industry,
    c.address_city,
    c.address_country,
    c.website,
    c.company_size,
    c.annual_revenue,
    c.tags,
    -- Contact counts
    (
        SELECT COUNT(*)
        FROM person p
        WHERE p.company_site_id = c.id
    ) as total_contacts,
    -- Opportunity stats
    (
        SELECT COUNT(*)
        FROM sales_opportunity o
        WHERE o.company_site_id = c.id
        AND o.status = 'open'
    ) as open_opportunities,
    (
        SELECT SUM(value_eur)
        FROM sales_opportunity o
        WHERE o.company_site_id = c.id
        AND o.status NOT IN ('lost')
    ) as pipeline_value,
    (
        SELECT SUM(value_eur)
        FROM sales_opportunity o
        WHERE o.company_site_id = c.id
        AND o.status = 'won'
    ) as won_value,
    -- Activity stats
    (
        SELECT COUNT(*)
        FROM event e
        WHERE e.company_site_id = c.id
        AND e.event_date >= CURRENT_DATE - INTERVAL '30 days'
    ) as recent_activities,
    (
        SELECT MAX(event_date)
        FROM event e
        WHERE e.company_site_id = c.id
    ) as last_activity_date
FROM company_site c
WHERE c.id = 1;
```

---

## Date and Time Queries

### Get Events from Today

```sql
SELECT *
FROM event
WHERE event_date >= CURRENT_DATE
  AND event_date < CURRENT_DATE + INTERVAL '1 day'
ORDER BY event_date DESC;
```

### Get Opportunities Closing This Quarter

```sql
SELECT
    id,
    title,
    value_eur,
    probability,
    expected_close_date,
    status
FROM sales_opportunity
WHERE
    expected_close_date >= DATE_TRUNC('quarter', CURRENT_DATE)
    AND expected_close_date < DATE_TRUNC('quarter', CURRENT_DATE) + INTERVAL '3 months'
    AND status IN ('open', 'qualified', 'proposal', 'negotiation')
ORDER BY expected_close_date;
```

### Get Companies with No Activity in Last 30 Days

```sql
SELECT
    c.id,
    c.name,
    c.industry,
    MAX(e.event_date) as last_activity
FROM company_site c
LEFT JOIN event e ON e.company_site_id = c.id
GROUP BY c.id, c.name, c.industry
HAVING
    MAX(e.event_date) < CURRENT_DATE - INTERVAL '30 days'
    OR MAX(e.event_date) IS NULL
ORDER BY last_activity DESC NULLS LAST;
```

---

## Common Patterns

### Upsert (INSERT ... ON CONFLICT)

```sql
INSERT INTO person (
    name,
    email,
    company_site_id,
    job_title
) VALUES (
    'Jane Smith',
    'jane.smith@example.com',
    1,
    'Director of Sales'
)
ON CONFLICT (email)
DO UPDATE SET
    name = EXCLUDED.name,
    job_title = EXCLUDED.job_title,
    updated_at = CURRENT_TIMESTAMP
RETURNING id, name, email;
```

Note: Requires a UNIQUE constraint on the email column.

### Bulk Insert with RETURNING

```sql
INSERT INTO event (type, description, event_date, company_site_id)
VALUES
    ('email', 'Follow-up email sent', '2025-11-28 10:00:00', 1),
    ('call', 'Phone call attempted', '2025-11-28 11:30:00', 1),
    ('note', 'Research on company needs', '2025-11-28 14:00:00', 1)
RETURNING id, type, event_date;
```

### Conditional Update

```sql
UPDATE sales_opportunity
SET
    status = CASE
        WHEN actual_close_date IS NOT NULL AND value_eur > 0 THEN 'won'
        WHEN actual_close_date IS NOT NULL THEN 'lost'
        WHEN expected_close_date < CURRENT_DATE THEN 'overdue'
        ELSE status
    END,
    updated_at = CURRENT_TIMESTAMP
WHERE status = 'open'
RETURNING id, title, status;
```
