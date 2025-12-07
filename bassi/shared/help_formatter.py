"""
Terminal output formatter for enhanced help system.

Generates beautifully formatted help text for the console.
"""

from typing import List, Optional
from .help_system import HelpItem, EcosystemScanner


class HelpFormatter:
    """Formats help content for terminal display."""

    # Unicode box drawing characters
    BOX_TOP_LEFT = "╔"
    BOX_TOP_RIGHT = "╗"
    BOX_BOTTOM_LEFT = "╚"
    BOX_BOTTOM_RIGHT = "╝"
    BOX_HORIZONTAL = "═"
    BOX_VERTICAL = "║"
    BOX_CROSS = "╬"

    SECTION_TOP_LEFT = "┌"
    SECTION_TOP_RIGHT = "┐"
    SECTION_BOTTOM_LEFT = "└"
    SECTION_BOTTOM_RIGHT = "┘"
    SECTION_HORIZONTAL = "─"
    SECTION_VERTICAL = "│"

    def __init__(self, width: int = 60):
        """Initialize formatter with terminal width."""
        self.width = width

    def format_item(self, item: HelpItem) -> str:
        """Format a single help item with full details."""
        lines = []

        # Header
        lines.append(self._make_box(item.name.upper(), item.type))
        lines.append("")

        # Quick facts
        lines.append("QUICK FACTS:")
        lines.append(f"• Type: {item.type.capitalize()} (specialized {'toolkit' if item.type == 'skill' else item.type})")
        if item.file_path:
            rel_path = item.file_path.replace(str(item.file_path.split('/.claude')[0]), "")
            lines.append(f"• Location: {rel_path}")
        lines.append("")

        # Description
        if item.description:
            lines.append("DESCRIPTION:")
            lines.append(self._wrap_text(item.description))
            lines.append("")

        # Capabilities
        if item.capabilities:
            lines.append("CAPABILITIES:")
            for cap in item.capabilities[:10]:  # Limit to 10
                lines.append(f"✓ {cap}")
            lines.append("")

        # When to use
        if item.when_to_use:
            lines.append("WHEN TO USE:")
            for use in item.when_to_use[:5]:  # Limit to 5
                lines.append(f"→ {use}")
            lines.append("")

        # Examples
        if item.examples:
            lines.append("EXAMPLES:")
            for i, example in enumerate(item.examples[:3], 1):  # Limit to 3
                lines.append(f"{i}. {example}")
            lines.append("")

        # Metadata
        if item.metadata:
            lines.append("METADATA:")
            for key, value in item.metadata.items():
                if key not in ("name", "description") and value:
                    lines.append(f"• {key}: {value}")
            lines.append("")

        return "\n".join(lines)

    def format_item_brief(self, item: HelpItem, index: Optional[int] = None) -> str:
        """Format item as a brief list entry."""
        prefix = f"{index}️⃣  " if index else "   "

        icon = {
            "command": "🟠",
            "skill": "🟡",
            "agent": "🔷"
        }.get(item.type, "◆")

        lines = [f"{icon} {item.name}"]
        if item.description:
            lines.append(f"   {item.description[:60]}...")
        return "\n".join(lines)

    def format_items_list(self, items: List[HelpItem], title: str = "") -> str:
        """Format multiple items as a list."""
        lines = []

        if title:
            lines.append(self._make_section_header(title))

        # Group by type
        by_type = {}
        for item in items:
            if item.type not in by_type:
                by_type[item.type] = []
            by_type[item.type].append(item)

        type_order = ["command", "skill", "agent"]
        for item_type in type_order:
            if item_type not in by_type:
                continue

            type_items = sorted(by_type[item_type], key=lambda x: x.name)

            if item_type == "command":
                icon, label = "🟠", "CUSTOM COMMANDS"
            elif item_type == "skill":
                icon, label = "🟡", "SKILLS"
            else:
                icon, label = "🔷", "AGENTS"

            lines.append("")
            lines.append(f"{icon} {label} ({len(type_items)} available)")
            lines.append("─" * self.width)

            for item in type_items:
                lines.append(f"  {item.name}")
                if item.description:
                    desc = item.description[:self.width - 10]
                    lines.append(f"     {desc}")
                lines.append("")

        return "\n".join(lines)

    def format_overview(self, scanner: EcosystemScanner) -> str:
        """Format overview of entire ecosystem."""
        lines = []

        commands = scanner.get_by_type("command")
        skills = scanner.get_by_type("skill")
        agents = scanner.get_by_type("agent")

        # Header
        lines.append(self._make_box("Claude Code Help Center", "help"))
        lines.append("")

        # Overview text
        overview = """Your Claude Code environment integrates three powerful tool types:

🔷 AGENTS (Specialized AI Workers)
   Pre-built AI agents that handle complex, multi-step tasks
   autonomously. Each agent has specific expertise.

🟡 SKILLS (Specialized Toolkits)
   Purpose-built tools for specific domains (PDF, spreadsheets,
   databases, email, etc). More focused than agents.

🟠 COMMANDS (Quick Access Shortcuts)
   Custom slash commands that wrap workflows combining
   multiple tools for specific tasks.
"""
        lines.append(overview)
        lines.append("")

        # Counts
        lines.append("LOCAL ECOSYSTEM:")
        lines.append(f"  {len(agents)} Agents available")
        lines.append(f"  {len(skills)} Skills available")
        lines.append(f"  {len(commands)} Custom Commands available")
        lines.append("")

        # Quick navigation
        lines.append("QUICK NAVIGATION:")
        lines.append("  /help agents     → List all agents")
        lines.append("  /help skills     → List all skills")
        lines.append("  /help commands   → List all custom commands")
        lines.append("  /help ecosystem  → Full ecosystem map")
        lines.append("  /help <name>     → Details on specific tool")
        lines.append("")

        return "\n".join(lines)

    def format_ecosystem_map(self, scanner: EcosystemScanner) -> str:
        """Format the complete ecosystem map dynamically from discovered items."""
        lines = []

        lines.append(self._make_box("Local Ecosystem Map", "ecosystem"))
        lines.append("")

        # Get all discovered items
        commands = scanner.get_by_type("command")
        skills = scanner.get_by_type("skill")
        agents = scanner.get_by_type("agent")

        # Workflow patterns - derived dynamically from command→skill relationships
        lines.append("WORKFLOW PATTERNS (command → skill/agent):")
        lines.append("")

        workflows = self._get_workflow_patterns(scanner)
        if workflows:
            for i, (cmd_name, related) in enumerate(workflows.items(), 1):
                lines.append(f"{i}. {cmd_name}")
                lines.append(f"   → {', '.join(related)}")
                lines.append("")
        else:
            lines.append("   (No workflow patterns found)")
            lines.append("")

        # Reference table - generated dynamically from discovered items
        lines.append("AVAILABLE TOOLS BY TYPE:")
        lines.append("")

        if agents:
            lines.append("🔷 AGENTS:")
            for agent in sorted(agents, key=lambda x: x.name):
                desc = agent.description[:40] + "..." if len(agent.description) > 40 else agent.description
                lines.append(f"   • {agent.name}: {desc}")
            lines.append("")

        if skills:
            lines.append("🟡 SKILLS:")
            for skill in sorted(skills, key=lambda x: x.name):
                desc = skill.description[:40] + "..." if len(skill.description) > 40 else skill.description
                lines.append(f"   • {skill.name}: {desc}")
            lines.append("")

        if commands:
            lines.append("🟠 COMMANDS:")
            for cmd in sorted(commands, key=lambda x: x.name):
                desc = cmd.description[:40] + "..." if len(cmd.description) > 40 else cmd.description
                lines.append(f"   • {cmd.name}: {desc}")
            lines.append("")

        return "\n".join(lines)

    def _make_box(self, title: str, box_type: str = "help") -> str:
        """Create a box with title."""
        padding = max(0, (self.width - len(title) - 2) // 2)
        left_pad = " " * padding
        right_pad = " " * (self.width - padding - len(title) - 2)

        icon = {
            "help": "🤖",
            "ecosystem": "🗺️",
            "skill": "📊",
            "command": "⚙️",
            "agent": "🔧"
        }.get(box_type, "ℹ️")

        top = self.BOX_TOP_LEFT + self.BOX_HORIZONTAL * (self.width - 2) + self.BOX_TOP_RIGHT
        middle = f"{self.BOX_VERTICAL}{left_pad}{icon} {title}{right_pad}{self.BOX_VERTICAL}"
        bottom = self.BOX_BOTTOM_LEFT + self.BOX_HORIZONTAL * (self.width - 2) + self.BOX_BOTTOM_RIGHT

        return f"{top}\n{middle}\n{bottom}"

    def _make_section_header(self, title: str) -> str:
        """Create a section header."""
        return f"\n{self.SECTION_TOP_LEFT}{self.SECTION_HORIZONTAL * (len(title) + 2)}{self.SECTION_TOP_RIGHT}\n{self.SECTION_VERTICAL} {title} {self.SECTION_VERTICAL}"

    def _wrap_text(self, text: str, width: Optional[int] = None) -> str:
        """Wrap text to specified width."""
        if width is None:
            width = self.width - 4

        lines = []
        for paragraph in text.split("\n"):
            if not paragraph.strip():
                lines.append("")
                continue

            words = paragraph.split()
            current_line = ""

            for word in words:
                if len(current_line) + len(word) + 1 <= width:
                    current_line += word + " "
                else:
                    if current_line:
                        lines.append(current_line.rstrip())
                    current_line = word + " "

            if current_line:
                lines.append(current_line.rstrip())

        return "\n".join(lines)

    def _get_workflow_patterns(self, scanner: EcosystemScanner) -> dict:
        """Get workflow patterns dynamically from command→skill/agent relationships."""
        patterns = {}

        # Look at commands and their skill references in metadata
        commands = scanner.get_by_type("command")

        for cmd in commands:
            related = []

            # Check for skill reference in metadata
            skill_ref = cmd.metadata.get("skill")
            if skill_ref:
                related.append(skill_ref)

            # Check for agent reference in metadata
            agent_ref = cmd.metadata.get("agent")
            if agent_ref:
                related.append(agent_ref)

            # Check relationships built by scanner
            cmd_key = f"/{cmd.name}" if not cmd.name.startswith("/") else cmd.name
            if cmd_key in scanner.relationships:
                related.extend(scanner.relationships[cmd_key])

            # Also check raw key
            if cmd.name in scanner.relationships:
                related.extend(scanner.relationships[cmd.name])

            # Remove duplicates while preserving order
            seen = set()
            unique_related = []
            for item in related:
                if item not in seen:
                    seen.add(item)
                    unique_related.append(item)

            if unique_related:
                patterns[cmd.name] = unique_related

        return patterns


def format_help(
    query: Optional[str] = None,
    width: int = 60,
    scanner: Optional[EcosystemScanner] = None,
) -> str:
    """
    Main entry point for help formatting.

    Args:
        query: What to show help for. None = overview
        width: Terminal width

    Returns:
        Formatted help text
    """
    formatter = HelpFormatter(width)
    scanner = scanner or EcosystemScanner()

    # Avoid double scanning when a pre-seeded scanner is passed in
    if not scanner.items:
        scanner.scan_all()

    if query is None:
        # Show overview
        return formatter.format_overview(scanner)

    elif query.lower() == "ecosystem":
        # Show ecosystem map
        return formatter.format_ecosystem_map(scanner)

    elif query.lower() == "agents":
        # List agents
        agents = scanner.get_by_type("agent")
        return formatter.format_items_list(agents, "🔷 AGENTS")

    elif query.lower() == "skills":
        # List skills
        skills = scanner.get_by_type("skill")
        return formatter.format_items_list(skills, "🟡 SKILLS")

    elif query.lower() == "commands":
        # List commands
        commands = scanner.get_by_type("command")
        return formatter.format_items_list(commands, "🟠 COMMANDS")

    else:
        # Look up specific item
        item = scanner.get_item(query)
        if item:
            return formatter.format_item(item)

        # Try search
        results = scanner.search(query)
        if results:
            lines = [f"Found {len(results)} matching items:\n"]
            for item in results:
                lines.append(formatter.format_item_brief(item))
                lines.append("")
            return "\n".join(lines)

        return f"No help found for '{query}'. Try /help ecosystem"
