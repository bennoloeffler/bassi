# CRM Data Files

## Overview

The `data_files` table stores files (PDFs, images, Office documents) AND complete emails with attachments in the CRM database, linked to CRM entities (person, company_site, event, sales_opportunity).

## Key Features

- **Base64 Storage**: Files stored as Base64-encoded TEXT (up to 100MB)
- **Complete Emails**: Store full email with body (text + HTML) and attachments
- **Deduplication**: SHA-256 hash prevents duplicate uploads
- **Text Extraction**: Full-text search on extracted content (German language)
- **Email Integration**: Store emails and attachments from MS365
- **Multi-Entity Linking**: Files can be linked to any CRM entity
- **Email-Attachment Linking**: Attachments linked via `source_email_id`

## Database Schema

```sql
CREATE TABLE data_files (
    id SERIAL PRIMARY KEY,

    -- Relationships
    person_id INTEGER REFERENCES person(id),
    company_site_id INTEGER REFERENCES company_site(id),
    event_id INTEGER REFERENCES event(id),
    sales_opportunity_id INTEGER REFERENCES sales_opportunity(id),

    -- File identification
    filename VARCHAR(500) NOT NULL,
    file_type VARCHAR(50) NOT NULL,  -- pdf, image, docx, pptx, xlsx, email, other
    mime_type VARCHAR(100),
    file_size_bytes BIGINT,
    file_hash VARCHAR(64),           -- SHA-256

    -- Source tracking
    source VARCHAR(50) NOT NULL,     -- email_attachment, user_upload, agent_download, email_message
    source_email_id VARCHAR(500),    -- MS365 message ID (links email + attachments)
    source_path VARCHAR(1000),

    -- Content
    file_data TEXT,                  -- Base64 encoded (NULL for emails without attachments)
    email_metadata JSONB,            -- Email headers: from, to, cc, subject, date, importance
    email_body_text TEXT,            -- Email body as plain text
    email_body_html TEXT,            -- Email body as HTML

    -- Text extraction
    extracted_text TEXT,
    extraction_method VARCHAR(50),   -- pdf_text, ocr, docx_parse, email_body, etc.
    extraction_status VARCHAR(20) DEFAULT 'pending',
    extraction_error TEXT,

    -- Metadata
    description TEXT,
    tags JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Workflows

### 1. Complete Email Storage (MS365)

```
User: "Save email from john@example.com about contract to CRM"

Flow:
1. mcp__ms365__list-mail-messages (search for emails)
2. mcp__ms365__get-mail-message (get full email with body)
3. Find/create person by sender email
4. INSERT INTO data_files with source='email_message', file_type='email'
5. If hasAttachments=true:
   a. mcp__ms365__list-mail-attachments
   b. mcp__ms365__get-mail-attachment (for each)
   c. INSERT attachments with same source_email_id
```

**email_metadata Structure** (extended for complete emails):
```json
{
  "message_id": "AAMkAGI2TG93AAA=",
  "subject": "Re: Contract Draft",
  "from": {
    "name": "John Doe",
    "email": "john@example.com"
  },
  "to": [{"name": "You", "email": "you@company.com"}],
  "cc": [{"email": "legal@company.com"}],
  "received_at": "2025-01-15T10:30:00Z",
  "importance": "high",
  "hasAttachments": true,
  "conversationId": "AAQkAGI2..."
}
```

### 2. Email Attachment Extraction (MS365)

```
User: "Save attachments from john@example.com to CRM"

Flow:
1. mcp__ms365__list-mail-messages (search for emails)
2. mcp__ms365__list-mail-attachments (get attachment list)
3. mcp__ms365__get-mail-attachment (get Base64 content)
4. Find/create person by email
5. INSERT INTO data_files with source='email_attachment'
```

**MS365 Attachment Response** (contentBytes is already Base64):
```json
{
  "@odata.type": "#microsoft.graph.fileAttachment",
  "id": "AAMkAGI2...",
  "name": "contract.pdf",
  "contentType": "application/pdf",
  "size": 245678,
  "contentBytes": "JVBERi0xLjQKJe..."
}
```

### 3. User Upload from _DATA_FROM_USER

```
User: "Upload proposal.pdf to CRM for Acme Corp"

Flow:
1. Read file from _DATA_FROM_USER/proposal.pdf
2. Base64-encode the binary content
3. Calculate SHA-256 hash
4. Check for duplicates (SELECT WHERE file_hash = ?)
5. Find company_site by name
6. INSERT INTO data_files with source='user_upload'
```

### 4. Text Extraction

| File Type | Method | Library | extraction_method |
|-----------|--------|---------|-------------------|
| PDF | Text extraction | pypdf | pdf_text |
| PDF (scanned) | OCR | pytesseract + pdf2image | pdf_ocr |
| Image | OCR | pytesseract + Pillow | ocr |
| DOCX | Parse | python-docx | docx_parse |
| PPTX | Parse | python-pptx | pptx_parse |
| XLSX | Parse | openpyxl | xlsx_parse |
| Email | Body text | MS365 API | email_body |

**extraction_status values**:
- `pending` - Not yet processed
- `completed` - Text extracted successfully
- `failed` - Extraction failed (see extraction_error)
- `skipped` - Binary file, no text to extract

## Example Queries

### Store Complete Email (with Body)
```sql
INSERT INTO data_files (
    person_id, filename, file_type, mime_type,
    source, source_email_id, email_metadata,
    email_body_text, email_body_html,
    extracted_text, extraction_method, extraction_status
) VALUES (
    1,
    'Re: Contract Draft',           -- Subject as filename
    'email',
    'message/rfc822',
    'email_message',
    'AAMkAGI2TG93AAA=',
    '{
      "subject": "Re: Contract Draft",
      "from": {"name": "John Doe", "email": "john@example.com"},
      "to": [{"email": "you@company.com"}],
      "cc": [{"email": "legal@company.com"}],
      "received_at": "2025-01-15T10:30:00Z",
      "importance": "high",
      "hasAttachments": true
    }'::jsonb,
    'Hallo, anbei der überarbeitete Vertragsentwurf...',
    '<html><body><p>Hallo, anbei der überarbeitete Vertragsentwurf...</p></body></html>',
    'Hallo, anbei der überarbeitete Vertragsentwurf...',
    'email_body',
    'completed'
) RETURNING id, filename;
```

### Store Email Attachment (linked to email)
```sql
-- Use same source_email_id to link attachment to email
INSERT INTO data_files (
    person_id, filename, file_type, mime_type, file_size_bytes,
    source, source_email_id, file_data, email_metadata
) VALUES (
    1, 'contract.pdf', 'pdf', 'application/pdf', 245678,
    'email_attachment', 'AAMkAGI2TG93AAA=',  -- Same ID as email!
    'JVBERi0xLjQK...',  -- Base64 from MS365
    '{"subject": "Re: Contract Draft", "from": {"email": "john@example.com"}}'::jsonb
) RETURNING id, filename;
```

### Find All Files for an Email (email + attachments)
```sql
SELECT id, filename, file_type, source, file_size_bytes
FROM data_files
WHERE source_email_id = 'AAMkAGI2TG93AAA='
ORDER BY file_type = 'email' DESC, filename;
```

### User Upload
```sql
INSERT INTO data_files (
    company_site_id, filename, file_type, mime_type, file_size_bytes, file_hash,
    source, source_path, file_data
) VALUES (
    5, 'proposal.pdf', 'pdf', 'application/pdf', 512000,
    'a1b2c3d4e5f6...',  -- SHA-256
    'user_upload', '_DATA_FROM_USER/proposal.pdf',
    'JVBERi0xLjQK...'   -- Base64
) RETURNING id, filename;
```

### Full-Text Search
```sql
SELECT id, filename, person_id, company_site_id,
       ts_headline('german', extracted_text, q) as headline
FROM data_files, to_tsquery('german', 'Vertrag & Angebot') q
WHERE to_tsvector('german', extracted_text) @@ q
ORDER BY ts_rank(to_tsvector('german', extracted_text), q) DESC;
```

### List Files for Contact
```sql
SELECT df.id, df.filename, df.file_type, df.file_size_bytes,
       df.source, df.created_at, df.description
FROM data_files df
JOIN person p ON df.person_id = p.id
WHERE p.email = 'john@example.com'
ORDER BY df.created_at DESC;
```

### Check for Duplicates
```sql
SELECT id, filename, person_id, company_site_id, created_at
FROM data_files
WHERE file_hash = 'a1b2c3d4e5f6...';
```

## Size Considerations

| File Size | Base64 Size | Notes |
|-----------|-------------|-------|
| 1 MB | ~1.33 MB | Typical document |
| 10 MB | ~13.3 MB | Large PDF with images |
| 50 MB | ~66.5 MB | Presentation with media |
| 100 MB | ~133 MB | Maximum allowed |

**Recommendation**: Files > 100MB should be stored externally (OneDrive, SharePoint) with URL reference.

## Indexes

- `idx_data_files_person` - Find files by person
- `idx_data_files_company` - Find files by company
- `idx_data_files_event` - Find files by event
- `idx_data_files_opportunity` - Find files by opportunity
- `idx_data_files_type` - Filter by file type
- `idx_data_files_source` - Filter by source
- `idx_data_files_hash` - Deduplication lookup
- `idx_data_files_tags` - GIN index for tag search
- `idx_data_files_extracted_text` - GIN index for German full-text search

## Future Enhancements

1. **Automatic OCR**: Background job to extract text from pending files
2. **Thumbnail Generation**: Store preview images for documents
3. **Version History**: Track file updates with versioning
4. **External Storage**: S3/Azure Blob for files > 100MB
5. **AI Summarization**: Generate summaries of document content
