"""
Discovery module for Bassi V3.

This module provides introspection capabilities for:
- MCP Tools (via tools/list API)
- Slash Commands (via filesystem scanning)
- Skills (via filesystem + configuration)
- Agents (via configuration)
"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class BassiDiscovery:
    """Discovery service for all Bassi capabilities"""

    def __init__(self, project_root: Path | None = None):
        """
        Initialize discovery service.

        Args:
            project_root: Project root directory (defaults to current working directory)
        """
        self.project_root = project_root or Path.cwd()

    def discover_slash_commands(self) -> dict[str, list[dict[str, Any]]]:
        """
        Discover slash commands by scanning filesystem.

        Scans:
        - .claude/commands/ (project commands)
        - ~/.claude/commands/ (personal commands)

        Returns:
            Dict with 'project' and 'personal' command lists
        """
        commands = {"project": [], "personal": []}

        # Project commands
        project_cmd_dir = self.project_root / ".claude" / "commands"
        if project_cmd_dir.exists():
            for cmd_file in project_cmd_dir.glob("*.md"):
                commands["project"].append(
                    {
                        "name": f"/{cmd_file.stem}",
                        "file": str(cmd_file),
                        "source": "project",
                    }
                )

        # Personal commands
        personal_cmd_dir = Path.home() / ".claude" / "commands"
        if personal_cmd_dir.exists():
            for cmd_file in personal_cmd_dir.glob("*.md"):
                commands["personal"].append(
                    {
                        "name": f"/{cmd_file.stem}",
                        "file": str(cmd_file),
                        "source": "personal",
                    }
                )

        return commands

    def discover_mcp_servers(self) -> dict[str, Any]:
        """
        Discover configured MCP servers from .mcp.json.

        Returns:
            Dict with MCP server configurations
        """
        mcp_config_path = self.project_root / ".mcp.json"

        if not mcp_config_path.exists():
            return {}

        try:
            with open(mcp_config_path) as f:
                config = json.load(f)
                return config.get("mcpServers", {})
        except Exception as e:
            logger.error(f"Failed to load MCP config: {e}")
            return {}

    def discover_skills(
        self, skill_dirs: list[Path] | None = None
    ) -> list[dict[str, Any]]:
        """
        Discover skills by scanning configured directories.

        Args:
            skill_dirs: List of directories to scan for skills

        Returns:
            List of discovered skills
        """
        if skill_dirs is None:
            # Default skill locations
            skill_dirs = [
                self.project_root / ".claude" / "skills",
                Path.home() / ".claude" / "skills",
            ]

        skills = []
        for skill_dir in skill_dirs:
            if not skill_dir.exists():
                continue

            # Each subdirectory with a SKILL.md is a skill
            for skill_path in skill_dir.iterdir():
                if not skill_path.is_dir():
                    continue

                skill_file = skill_path / "SKILL.md"
                if skill_file.exists():
                    skills.append(
                        {
                            "name": skill_path.name,
                            "path": str(skill_path),
                            "skill_file": str(skill_file),
                        }
                    )

        return skills

    def get_summary(self) -> dict[str, Any]:
        """
        Get a complete summary of all discoverable capabilities.

        Returns:
            Dict with all discovered items categorized
        """
        return {
            "slash_commands": self.discover_slash_commands(),
            "mcp_servers": self.discover_mcp_servers(),
            "skills": self.discover_skills(),
        }

    def format_summary(self, summary: dict[str, Any] | None = None) -> str:
        """
        Format discovery summary as readable text.

        Args:
            summary: Pre-computed summary (if None, will compute)

        Returns:
            Formatted string for display
        """
        if summary is None:
            summary = self.get_summary()

        from datetime import datetime

        lines = []
        lines.append(
            f"⏰ Discovery run at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        lines.append("")
        lines.append("=" * 70)
        lines.append("BASSI DISCOVERY - Available Capabilities")
        lines.append("=" * 70)

        # MCP Servers
        mcp_servers = summary.get("mcp_servers", {})
        lines.append(f"\n📡 MCP SERVERS: {len(mcp_servers)}")
        if mcp_servers:
            for name, config in mcp_servers.items():
                command = config.get("command", "unknown")
                lines.append(f"   • {name}")
                lines.append(f"     Command: {command}")
                if "args" in config:
                    args = config["args"]
                    if isinstance(args, list) and args:
                        # Show package name if it's npx
                        if command == "npx" and len(args) > 0:
                            # Find the package name (first non-flag argument)
                            pkg = None
                            for arg in args:
                                if not arg.startswith("-"):
                                    pkg = arg
                                    break
                            if pkg:
                                lines.append(f"     Package: {pkg}")
        else:
            lines.append("   (none configured)")

        # Slash Commands
        slash_cmds = summary.get("slash_commands", {})
        project_cmds = slash_cmds.get("project", [])
        personal_cmds = slash_cmds.get("personal", [])
        total_cmds = len(project_cmds) + len(personal_cmds)

        lines.append(f"\n💻 SLASH COMMANDS: {total_cmds}")
        if project_cmds:
            lines.append(f"   Project commands ({len(project_cmds)}):")
            for cmd in project_cmds:
                lines.append(f"   • {cmd['name']}")
        if personal_cmds:
            lines.append(f"   Personal commands ({len(personal_cmds)}):")
            for cmd in personal_cmds:
                lines.append(f"   • {cmd['name']}")
        if not total_cmds:
            lines.append("   (none found)")

        # Skills
        skills = summary.get("skills", [])
        lines.append(f"\n🎯 SKILLS: {len(skills)}")
        if skills:
            for skill in skills:
                lines.append(f"   • {skill['name']}")
                lines.append(f"     Path: {skill['path']}")
        else:
            lines.append("   (none found)")

        lines.append("\n" + "=" * 70)

        return "\n".join(lines)


def display_startup_discovery(project_root: Path | None = None):
    """
    Display discovery summary at startup.

    Args:
        project_root: Project root directory
    """
    discovery = BassiDiscovery(project_root)
    summary = discovery.get_summary()
    formatted = discovery.format_summary(summary)

    # Log to console
    print("\n" + formatted + "\n")

    # Also log via logger
    logger.info("Discovery complete")
    logger.info(f"MCP Servers: {len(summary['mcp_servers'])}")
    logger.info(
        f"Slash Commands: {len(summary['slash_commands']['project']) + len(summary['slash_commands']['personal'])}"
    )
    logger.info(f"Skills: {len(summary['skills'])}")
