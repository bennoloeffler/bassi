#!/usr/bin/env python3
"""
Demo of the new clean UI (no dark backgrounds)
"""

import os
import sys

# Add bassi to path
sys.path.insert(0, os.path.dirname(__file__))

from bassi.main import print_commands, print_config, print_help, print_welcome

print("\n" + "=" * 60)
print("CLEAN UI DEMO - No Dark Backgrounds!")
print("=" * 60 + "\n")

print("1. WELCOME SCREEN:")
print("-" * 60)
print_welcome()

print("\n2. COMMANDS LIST:")
print("-" * 60)
print_commands()

print("\n3. HELP SCREEN:")
print("-" * 60)
print_help()

print("\n4. CONFIG SCREEN:")
print("-" * 60)
print_config()

print("\n" + "=" * 60)
print("✅ Demo complete - all clean, no dark backgrounds!")
print("=" * 60 + "\n")
