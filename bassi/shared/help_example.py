#!/usr/bin/env python3
"""
Example usage of the enhanced help system.

This script demonstrates how to use the EcosystemScanner and HelpFormatter
to display help about your local Claude Code environment.

Usage:
    python help_example.py                  # Show overview
    python help_example.py agents           # List agents
    python help_example.py skills           # List skills
    python help_example.py commands         # List commands
    python help_example.py ecosystem        # Show ecosystem map
    python help_example.py <name>           # Show details for specific item
    python help_example.py search <term>    # Search for items
"""

import sys

from help_formatter import format_help


def main():
    """Main entry point for help system."""
    if len(sys.argv) == 1:
        # No arguments - show overview
        output = format_help()
    elif len(sys.argv) == 2:
        # One argument
        query = sys.argv[1]
        output = format_help(query)
    else:
        # Multiple arguments - treat as search query
        query = " ".join(sys.argv[1:])
        output = format_help(query)

    print(output)


if __name__ == "__main__":
    main()
