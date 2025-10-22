"""
Format image listings in nice markdown
"""

from pathlib import Path
from typing import Dict, List


def format_size(size_bytes: int) -> str:
    """Format file size in human-readable format"""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f}{unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f}TB"


def categorize_images(directory: Path) -> Dict[str, List[tuple]]:
    """Categorize images by type/folder"""
    categories = {}

    for img_path in directory.rglob("*.jpg"):
        # Determine category
        if img_path.parent == directory:
            category = "Personal Photos"
        else:
            category = img_path.parent.name.replace("_", " ").title()

        if category not in categories:
            categories[category] = []

        # Get file info
        size = img_path.stat().st_size
        categories[category].append((img_path, size))

    return categories


def format_image_list(directory: Path) -> str:
    """Format all images in directory as nice markdown"""
    categories = categorize_images(directory)

    output = ["# 📸 Image Gallery\n"]

    for category, images in sorted(categories.items()):
        output.append(f"\n## {category}\n")

        # Sort by name
        images.sort(key=lambda x: x[0].name)

        # Create table
        output.append("| Image | Size | Description |")
        output.append("|-------|------|-------------|")

        for img_path, size in images:
            name = img_path.name
            size_str = format_size(size)

            # Determine description based on filename
            desc = ""
            if "bw" in name.lower():
                desc = "Black & White"
            if "rotated" in name.lower():
                desc += " (Rotated)" if desc else "Rotated"
            if "small" in name.lower():
                desc += " - Small version" if desc else "Small version"
            if "tiny" in name.lower():
                desc += " - Tiny version" if desc else "Tiny version"
            if "5k" in name.lower():
                desc += " - 5K resolution" if desc else "5K resolution"

            if not desc:
                desc = "Original"

            output.append(f"| `{name}` | {size_str} | {desc} |")

        # Add total
        total_size = sum(size for _, size in images)
        output.append(
            f"\n**Total:** {len(images)} images, {format_size(total_size)}\n"
        )

    return "\n".join(output)


def format_image_list_simple(directory: Path) -> str:
    """Format images in a simpler, cleaner list format"""
    categories = categorize_images(directory)

    output = ["# 📸 Image Gallery", ""]

    for category, images in sorted(categories.items()):
        output.append(f"## {category}")
        output.append("")

        # Sort by size (largest first)
        images.sort(key=lambda x: x[1], reverse=True)

        for img_path, size in images:
            name = img_path.name
            size_str = format_size(size)

            # Use emoji indicators for file types
            emoji = "🖼️ "
            if "bw" in name.lower():
                emoji = "⚫ "
            elif "tiny" in name.lower():
                emoji = "🔍 "
            elif "small" in name.lower():
                emoji = "📱 "
            elif size > 1_000_000:  # > 1MB
                emoji = "🎨 "

            output.append(f"- {emoji}**{name}** — {size_str}")

        # Add summary line
        total_size = sum(size for _, size in images)
        output.append(
            f"\n> {len(images)} images • {format_size(total_size)} total\n"
        )

    return "\n".join(output)


def main():
    """Demo the formatter"""
    # Example: format current directory
    cwd = Path.cwd()

    print("=== TABLE FORMAT ===")
    print(format_image_list(cwd))
    print("\n\n=== SIMPLE FORMAT ===")
    print(format_image_list_simple(cwd))


if __name__ == "__main__":
    main()
