# data_files Table Schema

The `data_files` table stores files (documents, images, spreadsheets, etc.) in the CRM database with links to companies, people, events, and sales opportunities.

## Table Structure

```sql
CREATE TABLE data_files (
    id SERIAL PRIMARY KEY,

    -- Foreign key relationships (at least one should be set)
    person_id INTEGER REFERENCES person(id),
    company_site_id INTEGER REFERENCES company_site(id),
    event_id INTEGER REFERENCES event(id),
    sales_opportunity_id INTEGER REFERENCES sales_opportunity(id),

    -- File metadata
    filename VARCHAR NOT NULL,
    file_type VARCHAR NOT NULL,        -- 'image', 'document', 'spreadsheet', 'other'
    mime_type VARCHAR,                 -- 'image/jpeg', 'application/pdf', etc.
    file_size_bytes BIGINT,
    file_hash VARCHAR,                 -- SHA256 hash for integrity

    -- Source information
    source VARCHAR NOT NULL,           -- 'manual_upload', 'email', 'api', etc.
    source_email_id VARCHAR,
    source_path VARCHAR,

    -- File content
    file_data TEXT,                    -- Base64-encoded file content

    -- Email-specific fields
    email_metadata JSONB,
    email_body_text TEXT,
    email_body_html TEXT,

    -- Text extraction
    extracted_text TEXT,
    extraction_method VARCHAR,
    extraction_status VARCHAR DEFAULT 'pending',  -- 'pending', 'success', 'failed'
    extraction_error TEXT,

    -- User-provided metadata
    description TEXT,
    tags JSONB,                        -- Flexible tagging system

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Column Details

### Foreign Keys (Link Files to Entities)
- **person_id**: Link file to a specific person
- **company_site_id**: Link file to a company
- **event_id**: Link file to an event/activity
- **sales_opportunity_id**: Link file to a sales opportunity

**Note**: At least one foreign key should be set when inserting a file.

### File Metadata
- **filename**: Original filename (e.g., "contract.pdf", "photo.jpg")
- **file_type**: Category - 'image', 'document', 'spreadsheet', 'other'
- **mime_type**: Standard MIME type (e.g., 'image/jpeg', 'application/pdf')
- **file_size_bytes**: Size in bytes
- **file_hash**: SHA256 hash for data integrity verification

### Source Information
- **source**: Where the file came from ('manual_upload', 'email', 'api')
- **source_email_id**: Microsoft 365 email ID if from email
- **source_path**: Original file path or URL

### File Content
- **file_data**: Base64-encoded binary file content stored as TEXT

### Tags (JSONB)
Flexible tagging system using JSONB. Common structure:
```json
{
  "type": ["contract", "signed"],
  "imported_by": "username",
  "custom_field": "value"
}
```

Query examples:
```sql
-- Find files with specific tag
WHERE tags->'type' ? 'contract'

-- Find files with any of multiple tags
WHERE tags->'type' ?| ARRAY['contract', 'invoice']
```

## Common MIME Types and File Types

| Extension | MIME Type | File Type |
|-----------|-----------|-----------|
| .jpg, .jpeg | image/jpeg | image |
| .png | image/png | image |
| .pdf | application/pdf | document |
| .xlsx | application/vnd.openxmlformats-officedocument.spreadsheetml.sheet | spreadsheet |
| .docx | application/vnd.openxmlformats-officedocument.wordprocessingml.document | document |
| .csv | text/csv | spreadsheet |
| .txt | text/plain | document |

## Example INSERT

```sql
INSERT INTO data_files (
    company_site_id,
    filename,
    file_type,
    mime_type,
    file_size_bytes,
    file_hash,
    source,
    source_path,
    file_data,
    description,
    tags,
    extraction_status
) VALUES (
    1,
    'contract.pdf',
    'document',
    'application/pdf',
    125678,
    'a1b2c3d4e5f6...',
    'manual_upload',
    '/path/to/contract.pdf',
    'JVBERi0xLjQKJeLjz9M...',  -- Base64-encoded content
    'Signed customer contract',
    '{"type": ["contract", "signed"], "imported_by": "benno"}'::jsonb,
    'pending'
) RETURNING id, filename, created_at;
```

## Example SELECT Queries

```sql
-- Get all files for a company
SELECT id, filename, file_type, file_size_bytes, description, created_at
FROM data_files
WHERE company_site_id = 1
ORDER BY created_at DESC;

-- Get files with specific tags
SELECT filename, description
FROM data_files
WHERE tags->'type' ? 'contract'
  AND company_site_id = 1;

-- Count files by type
SELECT file_type, COUNT(*) as count
FROM data_files
WHERE company_site_id = 1
GROUP BY file_type;
```
