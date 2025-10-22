"""
Status bar for bassi - persistent footer display
"""

import os


def create_status_bar(
    cost: float = 0.0, tokens_used: int = 0, tokens_max: int = 200000
) -> str:
    """
    Create a compact status line

    Args:
        cost: Current session cost
        tokens_used: Current session tokens used
        tokens_max: Maximum context tokens

    Returns:
        Formatted status string
    """
    cwd = os.getcwd()

    # Compact single line: folder | context usage | cost
    parts = [f"📂 {cwd}"]

    if tokens_used > 0:
        pct = (tokens_used / tokens_max) * 100
        parts.append(f"📊 {tokens_used:,}/{tokens_max:,} ({pct:.1f}%)")

    if cost > 0:
        parts.append(f"💰 ${cost:.4f}")

    return " │ ".join(parts)
