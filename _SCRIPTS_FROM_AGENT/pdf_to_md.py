#!/usr/bin/env python3
"""
PDF to Markdown Converter
Finds the first 10 PDF files recursively in home directory and converts them to Markdown.
Saves output in the same directory as this script.
"""

import subprocess
from pathlib import Path


def find_pdfs(start_dir, max_count=10):
    """Find PDF files recursively in the given directory."""
    pdfs = []
    start_path = Path(start_dir).expanduser()

    print(f"Searching for PDFs in {start_path}...")

    try:
        for pdf_file in start_path.rglob("*.pdf"):
            if pdf_file.is_file():
                pdfs.append(pdf_file)
                print(f"Found ({len(pdfs)}): {pdf_file}")
                if len(pdfs) >= max_count:
                    break
    except PermissionError:
        print("⚠️  Permission denied for some directories, continuing...")

    return pdfs


def convert_pdf_to_markdown(pdf_path, output_dir):
    """Convert a PDF file to Markdown using pdftotext."""
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create output filename
    md_filename = pdf_path.stem + ".md"
    md_path = output_dir / md_filename

    print(f"\nConverting: {pdf_path.name}")
    print(f"  From: {pdf_path}")
    print(f"  To:   {md_path}")

    try:
        # Use pdftotext with layout preservation
        result = subprocess.run(
            ["pdftotext", "-layout", str(pdf_path), "-"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            text_content = result.stdout

            # Check if we got any content
            if not text_content.strip():
                print("  ⚠️  PDF appears to be empty or image-based")
                # Try without layout for image-based PDFs
                result2 = subprocess.run(
                    ["pdftotext", str(pdf_path), "-"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                text_content = result2.stdout

            # Add markdown header
            markdown_content = f"# {pdf_path.stem}\n\n"
            markdown_content += f"*Converted from: {pdf_path}*\n\n"
            markdown_content += (
                f"*File size: {pdf_path.stat().st_size / 1024:.1f} KB*\n\n"
            )
            markdown_content += "---\n\n"
            markdown_content += text_content

            # Write to markdown file
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)

            char_count = len(text_content.strip())
            print(
                f"  ✅ Successfully converted ({char_count} chars, {len(markdown_content)} total)"
            )
            return True
        else:
            error_msg = result.stderr.strip()
            print(f"  ❌ Error: {error_msg}")
            return False

    except FileNotFoundError:
        print(
            "  ❌ pdftotext not found. Please install: brew install poppler"
        )
        return False
    except subprocess.TimeoutExpired:
        print("  ❌ Timeout (file too large or complex)")
        return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def main():
    """Main function to orchestrate PDF to Markdown conversion."""
    # Get the directory where this script is located
    script_dir = Path(__file__).parent.absolute()
    output_dir = script_dir / "converted_md"

    home_dir = Path.home()

    print("=" * 70)
    print("PDF to Markdown Converter")
    print("=" * 70)
    print(f"Script location:  {script_dir}")
    print(f"Home directory:   {home_dir}")
    print(f"Output directory: {output_dir}")
    print()

    # Find PDFs
    pdfs = find_pdfs(home_dir, max_count=10)

    if not pdfs:
        print("\n❌ No PDF files found!")
        print(
            "   Try checking specific directories or adjusting search path."
        )
        return

    print(f"\n✅ Found {len(pdfs)} PDF file(s)")
    print("\n" + "=" * 70)
    print("Starting conversion...")
    print("=" * 70)

    # Convert PDFs
    successful = 0
    failed = 0

    for i, pdf in enumerate(pdfs, 1):
        print(f"\n[{i}/{len(pdfs)}]")
        if convert_pdf_to_markdown(pdf, output_dir):
            successful += 1
        else:
            failed += 1

    # Summary
    print("\n" + "=" * 70)
    print("Conversion Summary")
    print("=" * 70)
    print(f"Total PDFs processed:    {len(pdfs)}")
    print(f"✅ Successfully converted: {successful}")
    print(f"❌ Failed:                 {failed}")
    print(f"\n📁 Markdown files saved in: {output_dir}")
    print("=" * 70)


if __name__ == "__main__":
    main()
