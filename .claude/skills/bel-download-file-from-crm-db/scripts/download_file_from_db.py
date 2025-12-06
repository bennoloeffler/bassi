#!/usr/bin/env python3
"""
Download a file from the CRM database and save it to the filesystem.

This script connects to the PostgreSQL CRM database, retrieves a file by its ID,
and saves it to the _RESULTS_FROM_AGENT/ directory.

Usage:
    python download_file_from_db.py <file_id>
    python download_file_from_db.py <file_id> --output-dir /custom/path

Requirements:
    - psycopg2-binary
    - Environment variables: POSTGRES_URL or individual connection params
"""

import argparse
import base64
import os
import sys
from pathlib import Path
from typing import Optional, Tuple

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    print(
        "Error: psycopg2-binary is required. Install with: pip install psycopg2-binary"
    )
    sys.exit(1)


def get_db_connection():
    """
    Establish connection to the CRM PostgreSQL database.
    Uses POSTGRES_URL env var or falls back to individual connection params.
    """
    postgres_url = os.environ.get("POSTGRES_URL")

    if postgres_url:
        return psycopg2.connect(postgres_url)

    # Fallback to individual parameters
    conn_params = {
        "host": os.environ.get("POSTGRES_HOST", "localhost"),
        "port": os.environ.get("POSTGRES_PORT", "5432"),
        "database": os.environ.get("POSTGRES_DB", "crm"),
        "user": os.environ.get("POSTGRES_USER", "postgres"),
        "password": os.environ.get("POSTGRES_PASSWORD", ""),
    }

    return psycopg2.connect(**conn_params)


def download_file(
    file_id: int, output_dir: Optional[Path] = None
) -> Tuple[str, dict]:
    """
    Download a file from the database and save it to disk.

    Args:
        file_id: The ID of the file in the 'file' table
        output_dir: Optional custom output directory (defaults to _RESULTS_FROM_AGENT/)

    Returns:
        Tuple of (file_path, metadata_dict)

    Raises:
        ValueError: If file_id not found
        Exception: For database or I/O errors
    """
    # Default output directory
    if output_dir is None:
        output_dir = Path("_RESULTS_FROM_AGENT")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Connect to database
    conn = get_db_connection()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Query the data_files table
            cur.execute(
                """
                SELECT
                    id,
                    file_hash,
                    filename,
                    mime_type,
                    file_data,
                    file_size_bytes,
                    created_at,
                    updated_at
                FROM data_files
                WHERE id = %s
                """,
                (file_id,),
            )

            result = cur.fetchone()

            if not result:
                raise ValueError(
                    f"File with ID {file_id} not found in database"
                )

            # Extract file data and metadata
            file_name = result["filename"]
            file_data_b64 = result["file_data"]
            # Decode base64 data
            file_data = base64.b64decode(file_data_b64)
            mime_type = result["mime_type"]
            file_size = (
                int(result["file_size_bytes"])
                if result["file_size_bytes"] is not None
                else 0
            )
            file_hash = result["file_hash"]

            # Sanitize filename to avoid path traversal
            safe_filename = Path(file_name).name

            # Generate unique filename if file already exists
            output_path = output_dir / safe_filename
            if output_path.exists():
                base_name = output_path.stem
                suffix = output_path.suffix
                counter = 1
                while output_path.exists():
                    output_path = (
                        output_dir / f"{base_name}_{counter}{suffix}"
                    )
                    counter += 1

            # Write file to disk
            output_path.write_bytes(file_data)

            # Prepare metadata
            metadata = {
                "file_id": result["id"],
                "file_name": file_name,
                "saved_as": str(output_path),
                "mime_type": mime_type,
                "file_size": file_size,
                "file_hash": file_hash,
                "created_at": (
                    str(result["created_at"])
                    if result["created_at"]
                    else None
                ),
                "updated_at": (
                    str(result["updated_at"])
                    if result["updated_at"]
                    else None
                ),
            }

            return str(output_path), metadata

    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Download a file from the CRM database to the filesystem"
    )
    parser.add_argument(
        "file_id", type=int, help="ID of the file in the database"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: _RESULTS_FROM_AGENT/)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress output (only print file path)",
    )

    args = parser.parse_args()

    try:
        file_path, metadata = download_file(args.file_id, args.output_dir)

        if args.quiet:
            print(file_path)
        else:
            print("✅ File downloaded successfully!")
            print(f"   File path: {file_path}")
            print(f"   Original name: {metadata['file_name']}")
            print(f"   MIME type: {metadata['mime_type']}")
            print(f"   Size: {metadata['file_size']:,} bytes")
            print(f"   Hash: {metadata['file_hash']}")

    except ValueError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
