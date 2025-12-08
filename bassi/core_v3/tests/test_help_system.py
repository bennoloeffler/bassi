"""
Tests for the enhanced help system.

Tests ecosystem scanner, help formatter, and integration.
"""

import tempfile
from pathlib import Path
from textwrap import dedent

from bassi.shared.help_formatter import HelpFormatter, format_help
from bassi.shared.help_system import EcosystemScanner, HelpItem


class TestHelpItem:
    """Tests for HelpItem dataclass."""

    def test_help_item_creation(self):
        """Test creating a help item."""
        item = HelpItem(
            type="skill",
            name="Test Skill",
            description="A test skill",
            file_path="/path/to/file",
        )
        assert item.type == "skill"
        assert item.name == "test skill"  # Should be normalized
        assert item.description == "A test skill"

    def test_help_item_name_normalization(self):
        """Test that item names are normalized."""
        item = HelpItem(type="command", name="  TEST-CMD  ")
        assert item.name == "test-cmd"

    def test_help_item_relationships(self):
        """Test setting related items."""
        item = HelpItem(
            type="skill",
            name="pdf",
            description="PDF tool",
            related_items=["docx", "xlsx"],
        )
        assert len(item.related_items) == 2
        assert "docx" in item.related_items


class TestEcosystemScanner:
    """Tests for the ecosystem scanner."""

    def test_scanner_initialization(self):
        """Test scanner can be initialized."""
        scanner = EcosystemScanner()
        assert scanner.claude_dir is not None
        assert scanner.items is not None

    def test_scan_all_returns_dict(self):
        """Test scan_all returns a dictionary."""
        scanner = EcosystemScanner()
        result = scanner.scan_all()
        assert isinstance(result, dict)

    def test_get_item_by_name(self):
        """Test retrieving an item by name."""
        scanner = EcosystemScanner()
        scanner.scan_all()

        # Try to get a command (should have / prefix)
        item = scanner.get_item("/crm")
        if item:  # Only if .claude exists
            assert item.type == "command"
            assert "crm" in item.name

    def test_get_by_type(self):
        """Test filtering items by type."""
        scanner = EcosystemScanner()
        scanner.scan_all()

        agents = scanner.get_by_type("agent")
        assert isinstance(agents, list)
        for agent in agents:
            assert agent.type == "agent"

        skills = scanner.get_by_type("skill")
        assert isinstance(skills, list)
        for skill in skills:
            assert skill.type == "skill"

        commands = scanner.get_by_type("command")
        assert isinstance(commands, list)
        for command in commands:
            assert command.type == "command"

    def test_search_functionality(self):
        """Test searching for items."""
        scanner = EcosystemScanner()
        scanner.scan_all()

        # Search for something that should exist
        results = scanner.search("test")
        assert isinstance(results, list)

    def test_parse_markdown_with_frontmatter(self):
        """Test parsing markdown with YAML frontmatter."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as f:
            f.write(
                dedent(
                    """
                ---
                name: test-skill
                description: A test skill for unit tests
                ---

                # Test Skill

                This is a test skill.

                ## Capabilities
                - Do something
                - Do another thing

                ## When to Use
                - When you need to test
                - When you're learning
            """
                )
            )
            f.flush()

            scanner = EcosystemScanner()
            item = scanner._parse_markdown_file(
                Path(f.name),
                item_type="skill",
                name_override="test-skill",  # Override with the expected name
            )

            assert item is not None
            assert item.name == "test-skill"
            assert item.description == "A test skill for unit tests"
            assert len(item.capabilities) > 0
            assert len(item.when_to_use) > 0

    def test_case_insensitive_lookup(self):
        """Test case-insensitive item lookup."""
        scanner = EcosystemScanner()
        scanner.scan_all()

        if scanner.items:
            # Get first item
            first_name = list(scanner.items.keys())[0]

            # Try different cases
            item1 = scanner.get_item(first_name.lower())
            item2 = scanner.get_item(first_name.upper())

            # Both should work
            if item1:
                assert item1.name is not None
            if item2:
                assert item2.name is not None


class TestHelpFormatter:
    """Tests for the help formatter."""

    def test_formatter_initialization(self):
        """Test formatter can be initialized."""
        formatter = HelpFormatter(width=60)
        assert formatter.width == 60

    def test_format_item(self):
        """Test formatting a single item."""
        item = HelpItem(
            type="skill",
            name="pdf",
            description="PDF manipulation tool",
            capabilities=["Create PDFs", "Edit PDFs"],
            when_to_use=["When you need PDF operations"],
            examples=["Create a PDF from images"],
        )
        formatter = HelpFormatter()
        result = formatter.format_item(item)

        assert "PDF" in result.upper()
        assert "Create PDFs" in result
        assert "When you need PDF operations" in result

    def test_format_item_brief(self):
        """Test brief item formatting."""
        item = HelpItem(
            type="skill",
            name="xlsx",
            description="Spreadsheet tool for Excel files",
        )
        formatter = HelpFormatter()
        result = formatter.format_item_brief(item, index=1)

        assert "xlsx" in result
        assert "Spreadsheet" in result

    def test_format_items_list(self):
        """Test formatting multiple items."""
        items = [
            HelpItem(type="skill", name="pdf", description="PDF tool"),
            HelpItem(
                type="skill", name="xlsx", description="Spreadsheet tool"
            ),
            HelpItem(type="command", name="crm", description="CRM command"),
        ]
        formatter = HelpFormatter()
        result = formatter.format_items_list(items, title="Tools")

        assert "Tools" in result
        assert "pdf" in result
        assert "xlsx" in result
        assert "crm" in result

    def test_format_overview(self):
        """Test formatting ecosystem overview."""
        scanner = EcosystemScanner()
        scanner.scan_all()

        formatter = HelpFormatter()
        result = formatter.format_overview(scanner)

        assert "Claude Code" in result
        assert "AGENTS" in result
        assert "SKILLS" in result
        assert "COMMANDS" in result

    def test_format_ecosystem_map(self):
        """Test formatting ecosystem map."""
        scanner = EcosystemScanner()
        scanner.scan_all()

        formatter = HelpFormatter()
        result = formatter.format_ecosystem_map(scanner)

        assert "WORKFLOW PATTERNS" in result
        assert "Email" in result or "email" in result.lower()

    def test_wrap_text(self):
        """Test text wrapping."""
        formatter = HelpFormatter(width=40)
        text = "This is a very long line that should be wrapped to fit within the specified width"
        result = formatter._wrap_text(text, width=30)

        lines = result.split("\n")
        for line in lines:
            assert len(line) <= 30

    def test_make_box(self):
        """Test box creation."""
        formatter = HelpFormatter()
        result = formatter._make_box("Test", "help")

        assert "╔" in result
        assert "╗" in result
        assert "╚" in result
        assert "╝" in result
        assert "Test" in result

    def test_make_section_header(self):
        """Test section header creation."""
        formatter = HelpFormatter()
        result = formatter._make_section_header("Test Section")

        assert "┌" in result
        assert "┐" in result
        assert "Test Section" in result


class TestFormatHelpFunction:
    """Tests for the format_help convenience function."""

    def test_format_help_overview(self):
        """Test format_help with no argument shows overview."""
        result = format_help()
        assert result is not None
        assert len(result) > 0

    def test_format_help_agents(self):
        """Test format_help agents command."""
        result = format_help("agents")
        assert result is not None
        assert "AGENTS" in result or "agents" in result.lower()

    def test_format_help_skills(self):
        """Test format_help skills command."""
        result = format_help("skills")
        assert result is not None
        assert "SKILLS" in result or "skills" in result.lower()

    def test_format_help_commands(self):
        """Test format_help commands command."""
        result = format_help("commands")
        assert result is not None
        assert "COMMAND" in result or "command" in result.lower()

    def test_format_help_ecosystem(self):
        """Test format_help ecosystem command."""
        result = format_help("ecosystem")
        assert result is not None
        assert "WORKFLOW" in result or "workflow" in result.lower()

    def test_format_help_specific_item(self):
        """Test format_help for a specific item."""
        scanner = EcosystemScanner()
        scanner.scan_all()

        if scanner.items:
            # Pick first item
            first_name = list(scanner.items.keys())[0]
            result = format_help(first_name)
            assert result is not None
            assert len(result) > 0

    def test_format_help_search(self):
        """Test format_help search functionality."""
        result = format_help("test")
        assert result is not None
        assert len(result) > 0

    def test_format_help_unknown_query(self):
        """Test format_help with unknown query."""
        result = format_help("xyzabc123unknown")
        assert result is not None
        # Should either return search results or guidance


class TestIntegration:
    """Integration tests for help system."""

    def test_full_workflow(self):
        """Test complete help system workflow."""
        # Initialize scanner
        scanner = EcosystemScanner()
        items = scanner.scan_all()

        # Should have some items (if .claude directory exists)
        if items:
            # Get different types
            agents = scanner.get_by_type("agent")
            skills = scanner.get_by_type("skill")
            commands = scanner.get_by_type("command")

            # Create formatter
            formatter = HelpFormatter()

            # Format overview
            overview = formatter.format_overview(scanner)
            assert len(overview) > 0

            # Format each type
            if agents:
                agents_output = formatter.format_items_list(agents, "Agents")
                assert len(agents_output) > 0

            if skills:
                skills_output = formatter.format_items_list(skills, "Skills")
                assert len(skills_output) > 0

            if commands:
                commands_output = formatter.format_items_list(
                    commands, "Commands"
                )
                assert len(commands_output) > 0

    def test_scanner_and_formatter_together(self):
        """Test scanner and formatter working together."""
        scanner = EcosystemScanner()
        scanner.scan_all()
        formatter = HelpFormatter()

        # Format each discovered item
        for name, item in list(scanner.items.items())[:5]:  # Limit to 5
            output = formatter.format_item(item)
            assert len(output) > 0
            assert item.name in output.lower()
