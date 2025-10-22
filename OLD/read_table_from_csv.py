#!/usr/bin/env python3
"""
Script to read and display tables from CSV files
Supports basic CSV parsing and pretty-printing with rich library
"""

import csv
import sys
from pathlib import Path
from typing import List

try:
    from rich.console import Console
    from rich.table import Table

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


def read_csv_file(filepath: str) -> tuple[List[str], List[List[str]]]:
    """
    Read a CSV file and return headers and rows

    Args:
        filepath: Path to the CSV file

    Returns:
        Tuple of (headers, rows)
    """
    csv_path = Path(filepath)

    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {filepath}")

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        raise ValueError("CSV file is empty")

    headers = rows[0]
    data_rows = rows[1:]

    return headers, data_rows


def display_table_rich(
    headers: List[str], rows: List[List[str]], title: str = "CSV Table"
):
    """Display table using rich library"""
    console = Console()

    table = Table(title=title, show_header=True, header_style="bold magenta")

    # Add columns
    for header in headers:
        table.add_column(header, style="cyan")

    # Add rows
    for row in rows:
        # Pad row if it has fewer columns than headers
        padded_row = row + [""] * (len(headers) - len(row))
        table.add_row(*padded_row[: len(headers)])

    console.print(table)
    console.print(f"\n[bold blue]Total rows:[/bold blue] {len(rows)}")


def display_table_simple(
    headers: List[str], rows: List[List[str]], title: str = "CSV Table"
):
    """Display table using simple ASCII formatting (fallback)"""
    print(f"\n{title}")
    print("=" * 80)

    # Calculate column widths
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(str(cell)))

    # Print headers
    header_line = " | ".join(h.ljust(w) for h, w in zip(headers, col_widths))
    print(header_line)
    print("-" * len(header_line))

    # Print rows
    for row in rows:
        padded_row = row + [""] * (len(headers) - len(row))
        row_line = " | ".join(
            str(cell).ljust(w)
            for cell, w in zip(padded_row[: len(headers)], col_widths)
        )
        print(row_line)

    print(f"\nTotal rows: {len(rows)}")


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python read_table_from_csv.py <csv_file> [title]")
        print("\nExample:")
        print("  python read_table_from_csv.py data.csv")
        print("  python read_table_from_csv.py data.csv 'My Custom Title'")
        sys.exit(1)

    csv_file = sys.argv[1]
    title = (
        sys.argv[2]
        if len(sys.argv) > 2
        else f"Data from {Path(csv_file).name}"
    )

    try:
        headers, rows = read_csv_file(csv_file)

        if RICH_AVAILABLE:
            display_table_rich(headers, rows, title)
        else:
            print(
                "Note: Install 'rich' library for better formatting (pip install rich)"
            )
            display_table_simple(headers, rows, title)

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading CSV: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
