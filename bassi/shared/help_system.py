"""
Enhanced Help System for Claude Code Local Ecosystem

Scans .claude/ directory for:
- Custom commands (.claude/commands/*.md)
- Skills (.claude/skills/*/SKILL.md)
- Agents (.claude/agents/*.md)

Builds relationship graph and provides queries.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml


@dataclass
class HelpItem:
    """Represents a help item (command, skill, or agent)."""

    type: str  # "command", "skill", "agent"
    name: str
    title: Optional[str] = None
    description: str = ""
    file_path: str = ""
    metadata: Dict = field(default_factory=dict)
    capabilities: List[str] = field(default_factory=list)
    when_to_use: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    related_items: List[str] = field(default_factory=list)
    raw_content: str = ""

    def __post_init__(self):
        """Normalize name to lowercase with hyphens."""
        self.name = self.name.lower().strip()

    def to_dict(self) -> Dict:
        """Serialize help item for API responses or UI use."""
        return {
            "type": self.type,
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "file_path": self.file_path,
            "metadata": self.metadata,
            "capabilities": self.capabilities,
            "when_to_use": self.when_to_use,
            "examples": self.examples,
            "related_items": self.related_items,
            "raw_content": self.raw_content,
        }


class EcosystemScanner:
    """Scans and indexes the local Claude Code ecosystem."""

    def __init__(self, project_root: Optional[Path] = None):
        """Initialize scanner with optional project root."""
        if project_root is None:
            # Try to find .claude directory
            current = Path.cwd()
            while current != current.parent:
                if (current / ".claude").exists():
                    project_root = current
                    break
                current = current.parent
            if project_root is None:
                # Fall back to home directory
                project_root = Path.home()

        self.project_root = Path(project_root)
        self.claude_dir = self.project_root / ".claude"
        self.items: Dict[str, HelpItem] = {}
        self.relationships: Dict[str, List[str]] = {}

    def scan_all(self) -> Dict[str, HelpItem]:
        """Scan all commands, skills, and agents."""
        self.items = {}

        if self.claude_dir.exists():
            self._scan_commands()
            self._scan_skills()
            self._scan_agents()
            self._build_relationships()

        return self.items

    def _scan_commands(self) -> None:
        """Scan .claude/commands/*.md files."""
        commands_dir = self.claude_dir / "commands"
        if not commands_dir.exists():
            return

        for cmd_file in commands_dir.glob("*.md"):
            try:
                item = self._parse_markdown_file(
                    cmd_file, item_type="command", name_override=cmd_file.stem
                )
                if item:
                    # Command names have slash prefix
                    key = f"/{item.name}"
                    self.items[key] = item
            except Exception as e:
                print(f"Warning: Could not parse {cmd_file}: {e}")

    def _scan_skills(self) -> None:
        """Scan .claude/skills/*/SKILL.md files."""
        skills_dir = self.claude_dir / "skills"
        if not skills_dir.exists():
            return

        for skill_dir in skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_file = skill_dir / "SKILL.md"
            if skill_file.exists():
                try:
                    item = self._parse_markdown_file(
                        skill_file,
                        item_type="skill",
                        name_override=skill_dir.name,
                    )
                    if item:
                        self.items[item.name] = item
                except Exception as e:
                    print(f"Warning: Could not parse {skill_file}: {e}")

    def _scan_agents(self) -> None:
        """Scan .claude/agents/*.md files."""
        agents_dir = self.claude_dir / "agents"
        if not agents_dir.exists():
            return

        for agent_file in agents_dir.glob("*.md"):
            # Skip non-agent files
            if agent_file.name.startswith("BULK_"):
                continue

            try:
                item = self._parse_markdown_file(
                    agent_file,
                    item_type="agent",
                    name_override=agent_file.stem,
                )
                if item:
                    self.items[item.name] = item
            except Exception as e:
                print(f"Warning: Could not parse {agent_file}: {e}")

    def _parse_markdown_file(
        self,
        file_path: Path,
        item_type: str,
        name_override: Optional[str] = None,
    ) -> Optional[HelpItem]:
        """Parse a markdown file with YAML frontmatter."""
        content = file_path.read_text(encoding="utf-8").strip()

        # Extract YAML frontmatter
        metadata = {}
        body = content

        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    metadata = yaml.safe_load(parts[1]) or {}
                    body = parts[2].strip()
                except yaml.YAMLError:
                    pass

        # Extract name
        name = name_override or metadata.get("name", file_path.stem)

        # Extract description from metadata or first line of body
        description = metadata.get("description", "")
        if not description:
            # Try to get first non-empty line that's not a heading
            for line in body.split("\n"):
                line = line.strip()
                if (
                    line
                    and not line.startswith("#")
                    and not line.startswith("---")
                ):
                    description = line
                    break

        item = HelpItem(
            type=item_type,
            name=name,
            description=description,
            file_path=str(file_path),
            metadata=metadata,
            raw_content=content,
        )

        # Extract sections from body
        item.capabilities = self._extract_section(
            body, "capabilities", "when to use"
        )
        item.when_to_use = self._extract_section(
            body, "when to use", "examples"
        )
        item.examples = self._extract_section(body, "examples", None)

        return item

    def _extract_section(
        self, text: str, start_marker: str, end_marker: Optional[str] = None
    ) -> List[str]:
        """Extract a section from markdown text."""
        items = []

        # Find start of section (case-insensitive, match heading level)
        start_pattern = rf"^#+\s+{re.escape(start_marker)}"
        start_match = re.search(
            start_pattern, text, re.IGNORECASE | re.MULTILINE
        )

        if not start_match:
            return items

        # Find content between start and end markers
        start_pos = start_match.end()

        if end_marker:
            end_pattern = rf"^#+\s+{re.escape(end_marker)}"
            end_match = re.search(
                end_pattern, text[start_pos:], re.IGNORECASE | re.MULTILINE
            )
            content = (
                text[start_pos : start_pos + end_match.start()]
                if end_match
                else text[start_pos:]
            )
        else:
            content = text[start_pos:]

        # Extract bullet points and list items
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith(("- ", "* ", "• ")):
                items.append(line[2:].strip())
            elif line.startswith(("1. ", "2. ", "3. ")):
                # Numbered list
                items.append(re.sub(r"^\d+\.\s+", "", line))

        return items

    def _build_relationships(self) -> None:
        """Build relationship graph between items."""
        self.relationships = {}

        for name, item in self.items.items():
            related = []

            # Check if command references a skill
            if item.type == "command":
                skill_ref = item.metadata.get("skill")
                if skill_ref:
                    related.append(skill_ref)

            # Check references in content
            for ref_name, ref_item in self.items.items():
                if ref_name != name:
                    # Simple heuristic: check if name appears in description
                    if ref_item.name in item.description.lower():
                        related.append(ref_name)

            self.relationships[name] = list(set(related))

    def get_item(self, name: str) -> Optional[HelpItem]:
        """Get a help item by name."""
        # Normalize name
        normalized = name.lower().strip()
        if not normalized.startswith("/"):
            normalized = (
                "/" + normalized if name.startswith("/") else normalized
            )

        # Try exact match first
        if normalized in self.items:
            return self.items[normalized]

        # Try without slash for commands
        if normalized.startswith("/"):
            if normalized[1:] in self.items:
                return self.items[normalized[1:]]

        # Try case-insensitive lookup
        for key, item in self.items.items():
            if key.lower().rstrip("/") == normalized.rstrip("/"):
                return item

        return None

    def get_by_type(self, item_type: str) -> List[HelpItem]:
        """Get all items of a specific type."""
        return [
            item for item in self.items.values() if item.type == item_type
        ]

    def search(self, query: str) -> List[HelpItem]:
        """Search items by name or description."""
        query_lower = query.lower()
        results = []

        for item in self.items.values():
            if (
                query_lower in item.name
                or query_lower in item.description.lower()
                or any(query_lower in cap for cap in item.capabilities)
                or any(query_lower in use for use in item.when_to_use)
            ):
                results.append(item)

        return results
