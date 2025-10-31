#!/usr/bin/env python3
"""
Convert PDFs in the current directory to Markdown
"""

import subprocess
from pathlib import Path


def convert_pdf_to_markdown(pdf_path, output_dir):
    """Convert a PDF file to Markdown using pdftotext."""
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create output filename
    md_filename = pdf_path.stem + ".md"
    md_path = output_dir / md_filename

    print(f"\nConverting: {pdf_path.name}")
    print(f"  To: {md_path}")

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

            # Add markdown header
            markdown_content = f"# {pdf_path.stem}\n\n"
            markdown_content += f"*Converted from: {pdf_path.name}*\n\n"
            markdown_content += (
                f"*File size: {pdf_path.stat().st_size / 1024:.1f} KB*\n\n"
            )
            markdown_content += "---\n\n"
            markdown_content += text_content

            # Write to markdown file
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)

            char_count = len(text_content.strip())
            print(f"  ✅ Success ({char_count} chars)")
            return True
        else:
            print(f"  ❌ Error: {result.stderr.strip()}")
            return False

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def main():
    """Convert all PDFs in current directory."""
    current_dir = Path.cwd()
    output_dir = current_dir / "converted_md"

    print("=" * 60)
    print("PDF to Markdown Converter (Local Directory)")
    print("=" * 60)
    print(f"Working directory: {current_dir}")
    print(f"Output directory:  {output_dir}")
    print()

    # Find PDFs in current directory
    pdfs = list(current_dir.glob("*.pdf"))

    if not pdfs:
        print("❌ No PDF files found in current directory!")
        return

    print(f"Found {len(pdfs)} PDF file(s):")
    for pdf in pdfs:
        print(f"  - {pdf.name}")

    print("\n" + "=" * 60)
    print("Converting...")
    print("=" * 60)

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
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Total:      {len(pdfs)}")
    print(f"✅ Success: {successful}")
    print(f"❌ Failed:  {failed}")
    print(f"\n📁 Output: {output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
