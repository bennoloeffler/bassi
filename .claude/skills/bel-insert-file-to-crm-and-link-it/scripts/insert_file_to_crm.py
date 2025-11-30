#!/usr/bin/env python3
"""
Insert a file into the CRM database (data_files table) with proper encoding and metadata.

This script:
1. Reads a file and encodes it as base64
2. Calculates SHA256 hash for integrity
3. Detects MIME type automatically
4. Generates and executes SQL INSERT statement
5. Links file to company/person/event/opportunity if specified

Usage:
    python3 insert_file_to_crm.py <file_path> --company-id <id> [options]

Examples:
    # Insert image linked to company
    python3 insert_file_to_crm.py photo.jpg --company-id 1 --description "Workshop photo"

    # Insert Excel file with tags
    python3 insert_file_to_crm.py data.xlsx --company-id 1 --tags crm,leads,contacts

    # Insert document linked to person
    python3 insert_file_to_crm.py contract.pdf --person-id 5 --description "Signed contract"
"""

import argparse
import base64
import hashlib
import json
import mimetypes
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, List


# MIME type mapping for common file extensions
MIME_TYPE_MAP = {
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    '.xls': 'application/vnd.ms-excel',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.doc': 'application/msword',
    '.pdf': 'application/pdf',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.gif': 'image/gif',
    '.txt': 'text/plain',
    '.csv': 'text/csv',
    '.json': 'application/json',
}

# File type categories
FILE_TYPE_MAP = {
    'image/jpeg': 'image',
    'image/png': 'image',
    'image/gif': 'image',
    'application/pdf': 'document',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'spreadsheet',
    'application/vnd.ms-excel': 'spreadsheet',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'document',
    'application/msword': 'document',
    'text/plain': 'document',
    'text/csv': 'spreadsheet',
}


def detect_mime_type(file_path: Path) -> str:
    """Detect MIME type from file extension."""
    ext = file_path.suffix.lower()

    # Try our custom mapping first
    if ext in MIME_TYPE_MAP:
        return MIME_TYPE_MAP[ext]

    # Fall back to mimetypes library
    mime_type, _ = mimetypes.guess_type(str(file_path))
    if mime_type:
        return mime_type

    # Default to binary
    return 'application/octet-stream'


def get_file_type(mime_type: str) -> str:
    """Get file type category from MIME type."""
    return FILE_TYPE_MAP.get(mime_type, 'other')


def encode_file(file_path: Path) -> tuple[str, str, int]:
    """
    Read file, encode as base64, and calculate hash.

    Returns:
        (base64_data, sha256_hash, file_size)
    """
    with open(file_path, 'rb') as f:
        file_data = f.read()

    # Calculate hash
    file_hash = hashlib.sha256(file_data).hexdigest()

    # Encode as base64
    file_b64 = base64.b64encode(file_data).decode('utf-8')

    return file_b64, file_hash, len(file_data)


def escape_sql_string(s: str) -> str:
    """Escape string for SQL by replacing single quotes."""
    return s.replace("'", "''")


def generate_sql_insert(
    filename: str,
    file_type: str,
    mime_type: str,
    file_size: int,
    file_hash: str,
    file_data: str,
    source_path: str,
    description: Optional[str] = None,
    tags: Optional[List[str]] = None,
    company_id: Optional[int] = None,
    person_id: Optional[int] = None,
    event_id: Optional[int] = None,
    opportunity_id: Optional[int] = None,
) -> str:
    """Generate SQL INSERT statement for data_files table."""

    # Build tags JSON
    tags_json = 'NULL'
    if tags:
        tags_dict = {
            'type': tags,
            'imported_by': os.environ.get('USER', 'unknown')
        }
        tags_json = f"'{escape_sql_string(json.dumps(tags_dict))}'::jsonb"

    # Build SQL
    sql = f"""INSERT INTO data_files (
    company_site_id,
    person_id,
    event_id,
    sales_opportunity_id,
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
    {company_id if company_id else 'NULL'},
    {person_id if person_id else 'NULL'},
    {event_id if event_id else 'NULL'},
    {opportunity_id if opportunity_id else 'NULL'},
    '{escape_sql_string(filename)}',
    '{escape_sql_string(file_type)}',
    '{escape_sql_string(mime_type)}',
    {file_size},
    '{file_hash}',
    'manual_upload',
    '{escape_sql_string(source_path)}',
    '{file_data}',
    {f"'{escape_sql_string(description)}'" if description else 'NULL'},
    {tags_json},
    'pending'
) RETURNING id, filename, file_size_bytes, created_at;
"""
    return sql


def execute_sql(sql: str, db_config: dict) -> dict:
    """Execute SQL using psql command via temporary file."""
    import tempfile

    # Write SQL to temporary file to avoid argument length limits
    with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as tmp:
        tmp.write(sql)
        tmp_path = tmp.name

    try:
        psql_cmd = [
            'psql',
            '-h', db_config['host'],
            '-U', db_config['user'],
            '-d', db_config['database'],
            '-f', tmp_path,  # Read from file instead of -c
            '-t',  # Tuples only (no headers)
            '-A',  # Unaligned output
        ]

        env = os.environ.copy()
        env['PGPASSWORD'] = db_config['password']

        result = subprocess.run(
            psql_cmd,
            env=env,
            capture_output=True,
            text=True,
            check=True
        )
        return {
            'success': True,
            'output': result.stdout.strip(),
            'error': None
        }
    except subprocess.CalledProcessError as e:
        return {
            'success': False,
            'output': None,
            'error': e.stderr
        }
    finally:
        # Clean up temporary file
        try:
            os.unlink(tmp_path)
        except:
            pass


def get_db_config() -> dict:
    """Get database configuration from .mcp.json."""
    mcp_config_path = Path.home() / 'projects/ai/bassi/.mcp.json'

    if not mcp_config_path.exists():
        print(f"❌ MCP config not found at {mcp_config_path}", file=sys.stderr)
        sys.exit(1)

    with open(mcp_config_path) as f:
        mcp_config = json.load(f)

    pg_config = mcp_config.get('mcpServers', {}).get('postgresql', {})
    args = pg_config.get('args', [])

    # Parse args to get connection details
    db_config = {
        'host': 'localhost',
        'database': 'crm_data_bassi',
        'user': 'postgres',
        'password': 'somethingsecure'
    }

    # Override with values from args if present
    for i, arg in enumerate(args):
        if arg == '--host' and i + 1 < len(args):
            db_config['host'] = args[i + 1]
        elif arg == '--database' and i + 1 < len(args):
            db_config['database'] = args[i + 1]
        elif arg == '--user' and i + 1 < len(args):
            db_config['user'] = args[i + 1]
        elif arg == '--password' and i + 1 < len(args):
            db_config['password'] = args[i + 1]

    return db_config


def main():
    parser = argparse.ArgumentParser(
        description='Insert a file into the CRM database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument('file_path', help='Path to the file to insert')
    parser.add_argument('--company-id', type=int, help='Company site ID to link to')
    parser.add_argument('--person-id', type=int, help='Person ID to link to')
    parser.add_argument('--event-id', type=int, help='Event ID to link to')
    parser.add_argument('--opportunity-id', type=int, help='Sales opportunity ID to link to')
    parser.add_argument('--description', help='Description of the file')
    parser.add_argument('--tags', help='Comma-separated tags (e.g., crm,leads,contacts)')
    parser.add_argument('--dry-run', action='store_true', help='Generate SQL but do not execute')

    args = parser.parse_args()

    # Validate file exists
    file_path = Path(args.file_path)
    if not file_path.exists():
        print(f"❌ File not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    # Validate at least one link is provided
    if not any([args.company_id, args.person_id, args.event_id, args.opportunity_id]):
        print("❌ At least one of --company-id, --person-id, --event-id, or --opportunity-id must be specified", file=sys.stderr)
        sys.exit(1)

    print(f"📄 Processing file: {file_path.name}")

    # Detect MIME type and file type
    mime_type = detect_mime_type(file_path)
    file_type = get_file_type(mime_type)
    print(f"   MIME type: {mime_type}")
    print(f"   File type: {file_type}")

    # Encode file
    print("🔐 Encoding file...")
    file_b64, file_hash, file_size = encode_file(file_path)
    print(f"   Size: {file_size:,} bytes")
    print(f"   Hash: {file_hash[:16]}...")

    # Parse tags
    tags_list = None
    if args.tags:
        tags_list = [tag.strip() for tag in args.tags.split(',')]
        print(f"   Tags: {', '.join(tags_list)}")

    # Generate SQL
    print("📝 Generating SQL...")
    sql = generate_sql_insert(
        filename=file_path.name,
        file_type=file_type,
        mime_type=mime_type,
        file_size=file_size,
        file_hash=file_hash,
        file_data=file_b64,
        source_path=str(file_path.absolute()),
        description=args.description,
        tags=tags_list,
        company_id=args.company_id,
        person_id=args.person_id,
        event_id=args.event_id,
        opportunity_id=args.opportunity_id,
    )

    if args.dry_run:
        print("\n" + "="*80)
        print("DRY RUN - SQL would be:")
        print("="*80)
        # Show first 500 chars of SQL (without the huge base64 data)
        sql_preview = sql[:500] + "...[base64 data]..." + sql[-200:]
        print(sql_preview)
        return

    # Get DB config
    db_config = get_db_config()

    # Execute SQL
    print("💾 Inserting into database...")
    result = execute_sql(sql, db_config)

    if result['success']:
        print("✅ File inserted successfully!")
        if result['output']:
            print(f"   {result['output']}")
    else:
        print(f"❌ Failed to insert file:", file=sys.stderr)
        print(f"   {result['error']}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
