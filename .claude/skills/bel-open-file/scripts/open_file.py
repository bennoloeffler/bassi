#!/usr/bin/env python3
"""
Open a file with the operating system's default application.

This script opens files using the appropriate OS command:
- macOS: uses 'open'
- Linux: uses 'xdg-open'
- Windows: uses 'start' via os.startfile()

Usage:
    python open_file.py <file_path>
    python open_file.py /path/to/document.pdf
    python open_file.py "_RESULTS_FROM_AGENT/report.xlsx"

Supported file types:
    - Documents: PDF, DOCX, TXT, MD, etc.
    - Spreadsheets: XLSX, CSV, XLS
    - Images: PNG, JPG, GIF, SVG
    - Archives: ZIP, TAR, GZ
    - Emails: EML, MSG
    - Any file type with a registered default application
"""

import argparse
import os
import platform
import subprocess
import sys
from pathlib import Path


def open_file(file_path: str) -> bool:
    """
    Open a file with the operating system's default application.

    Args:
        file_path: Path to the file to open

    Returns:
        True if successful, False otherwise

    Raises:
        FileNotFoundError: If the file doesn't exist
        Exception: For other OS-specific errors
    """
    path = Path(file_path)

    # Check if file exists
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Get absolute path for reliability
    abs_path = path.resolve()

    # Detect OS and use appropriate command
    system = platform.system()

    try:
        if system == "Darwin":  # macOS
            subprocess.run(["open", str(abs_path)], check=True)

        elif system == "Linux":
            subprocess.run(["xdg-open", str(abs_path)], check=True)

        elif system == "Windows":
            os.startfile(str(abs_path))

        else:
            raise OSError(f"Unsupported operating system: {system}")

        return True

    except subprocess.CalledProcessError as e:
        raise Exception(f"Failed to open file: {e}")
    except Exception as e:
        raise Exception(f"Error opening file: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Open a file with the OS default application"
    )
    parser.add_argument(
        "file_path",
        type=str,
        help="Path to the file to open"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress output messages"
    )

    args = parser.parse_args()

    try:
        open_file(args.file_path)

        if not args.quiet:
            print(f"✅ Opened file: {args.file_path}")
            print(f"   (Using {platform.system()} default application)")

    except FileNotFoundError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
