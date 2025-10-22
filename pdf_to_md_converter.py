#!/usr/bin/env python3
"""
PDF to Markdown Converter
Finds the first 10 PDFs recursively in home directory and converts them to Markdown.
Saves the output in pdf_to_md/ directory.
"""

import os
import subprocess
from pathlib import Path


def find_pdfs(root_dir: Path, max_count: int = 10) -> list[Path]:
    """Find PDF files recursively up to max_count."""
    pdfs = []

    print(f"🔍 Searching for PDFs in {root_dir}...")

    for pdf_path in root_dir.rglob("*.pdf"):
        if len(pdfs) >= max_count:
            break

        # Skip hidden directories and system directories
        if any(part.startswith('.') for part in pdf_path.parts):
            continue
        if 'Library' in pdf_path.parts or 'System' in pdf_path.parts:
            continue

        pdfs.append(pdf_path)
        print(f"  Found: {pdf_path.name}")

    return pdfs


def pdf_to_markdown(pdf_path: Path, output_dir: Path) -> bool:
    """
    Convert a PDF to Markdown using pdftotext.
    Falls back to basic text extraction if pdftotext is not available.
    """
    # Create output filename
    output_file = output_dir / f"{pdf_path.stem}.md"

    try:
        # Try using pdftotext (from poppler-utils)
        result = subprocess.run(
            ["pdftotext", "-layout", str(pdf_path), "-"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            # Add header and save
            markdown_content = f"# {pdf_path.name}\n\n"
            markdown_content += f"**Source**: `{pdf_path}`\n\n"
            markdown_content += "---\n\n"
            markdown_content += result.stdout

            output_file.write_text(markdown_content)
            print(f"  ✓ Converted: {pdf_path.name} → {output_file.name}")
            return True
        else:
            print(f"  ✗ Failed to convert {pdf_path.name}: {result.stderr}")
            return False

    except FileNotFoundError:
        print(f"  ⚠️  pdftotext not found. Install with: brew install poppler")
        print(f"     Skipping: {pdf_path.name}")
        return False
    except subprocess.TimeoutExpired:
        print(f"  ✗ Timeout converting {pdf_path.name}")
        return False
    except Exception as e:
        print(f"  ✗ Error converting {pdf_path.name}: {e}")
        return False


def main():
    """Main conversion process."""
    # Setup paths
    home_dir = Path.home()
    output_dir = Path("/Users/benno/projects/ai/bassi/pdf_to_md")

    # Create output directory
    output_dir.mkdir(exist_ok=True)
    print(f"📁 Output directory: {output_dir}\n")

    # Find PDFs
    pdfs = find_pdfs(home_dir, max_count=10)

    if not pdfs:
        print("\n❌ No PDFs found!")
        return

    print(f"\n📄 Found {len(pdfs)} PDF(s)\n")
    print("=" * 60)
    print("Starting conversion...\n")

    # Convert each PDF
    success_count = 0
    for i, pdf_path in enumerate(pdfs, 1):
        print(f"[{i}/{len(pdfs)}] Processing: {pdf_path.name}")
        if pdf_to_markdown(pdf_path, output_dir):
            success_count += 1
        print()

    # Summary
    print("=" * 60)
    print(f"\n✅ Conversion complete!")
    print(f"   Successful: {success_count}/{len(pdfs)}")
    print(f"   Output directory: {output_dir}")

    if success_count < len(pdfs):
        print(f"\n⚠️  Some conversions failed. Make sure pdftotext is installed:")
        print(f"   brew install poppler")


if __name__ == "__main__":
    main()
