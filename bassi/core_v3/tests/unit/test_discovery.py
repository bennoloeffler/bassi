"""Tests for discovery.py - MCP/Slash Command/Skills discovery."""

import json
from pathlib import Path

import pytest

from bassi.core_v3.discovery import BassiDiscovery, display_startup_discovery


@pytest.fixture
def tmp_project(tmp_path):
    """Create a temporary project directory structure for testing."""
    # Create project command directory
    project_cmds = tmp_path / ".claude" / "commands"
    project_cmds.mkdir(parents=True)

    # Create some test commands
    (project_cmds / "test-cmd.md").write_text("# Test command")
    (project_cmds / "another-cmd.md").write_text("# Another command")

    # Create MCP config
    mcp_config = {
        "mcpServers": {
            "test-server": {"command": "npx", "args": ["-y", "test-package"]},
            "python-server": {"command": "python", "args": ["server.py"]},
        }
    }
    (tmp_path / ".mcp.json").write_text(json.dumps(mcp_config))

    # Create skills directory
    skills_dir = tmp_path / ".claude" / "skills"
    skills_dir.mkdir(parents=True)

    # Create test skill
    skill1 = skills_dir / "skill-one"
    skill1.mkdir()
    (skill1 / "SKILL.md").write_text("# Skill One")

    # Create skill without SKILL.md (should be ignored)
    skill2 = skills_dir / "incomplete-skill"
    skill2.mkdir()

    # Create a file (not directory) - should be ignored
    (skills_dir / "not-a-skill.md").write_text("# Not a skill")

    # Create hooks directory with scripts
    hooks_dir = tmp_path / ".claude" / "hooks"
    hooks_dir.mkdir(parents=True)
    (hooks_dir / "security.py").write_text("# Hook script")
    (hooks_dir / "analytics.py").write_text("# Another hook")

    # Create agents directory
    agents_dir = tmp_path / ".claude" / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "writer-agent.md").write_text("# Writer Agent")

    return tmp_path


@pytest.fixture
def tmp_personal(tmp_path_factory):
    """Create temporary personal directory structure."""
    personal_dir = tmp_path_factory.mktemp("home")

    # Create personal commands
    personal_cmds = personal_dir / ".claude" / "commands"
    personal_cmds.mkdir(parents=True)
    (personal_cmds / "personal-cmd.md").write_text("# Personal command")

    # Create personal skills
    skills_dir = personal_dir / ".claude" / "skills"
    skills_dir.mkdir(parents=True)

    skill = skills_dir / "personal-skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text("# Personal Skill")

    # Create personal agent
    agents_dir = personal_dir / ".claude" / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "personal-agent.md").write_text("# Personal Agent")

    return personal_dir


class TestBassiDiscovery:
    """Test discovery service functionality."""

    def test_initialization(self, tmp_project):
        """Test initialization with explicit project root."""
        discovery = BassiDiscovery(tmp_project)
        assert discovery.project_root == tmp_project

    def test_initialization_defaults_to_cwd(self, monkeypatch, tmp_project):
        """Test initialization defaults to current working directory."""
        monkeypatch.chdir(tmp_project)
        discovery = BassiDiscovery()
        assert discovery.project_root == Path.cwd()

    def test_discover_slash_commands_project(self, tmp_project):
        """Test discovering project slash commands."""
        discovery = BassiDiscovery(tmp_project)
        commands = discovery.discover_slash_commands()

        assert "project" in commands
        assert "personal" in commands

        # Check project commands
        project_cmds = commands["project"]
        assert len(project_cmds) == 2

        cmd_names = {cmd["name"] for cmd in project_cmds}
        assert "/test-cmd" in cmd_names
        assert "/another-cmd" in cmd_names

        # Verify command structure
        for cmd in project_cmds:
            assert "name" in cmd
            assert "file" in cmd
            assert "source" in cmd
            assert cmd["source"] == "project"

    def test_discover_slash_commands_no_directory(self, tmp_path):
        """Test discovering commands when project directory doesn't exist."""
        discovery = BassiDiscovery(tmp_path)
        commands = discovery.discover_slash_commands()

        # Project should have no commands
        assert commands["project"] == []
        # Personal may or may not have commands (depends on user's home directory)
        assert isinstance(commands["personal"], list)

    def test_discover_mcp_servers_valid_config(self, tmp_project):
        """Test discovering MCP servers from valid config."""
        discovery = BassiDiscovery(tmp_project)
        servers = discovery.discover_mcp_servers()

        assert len(servers) == 2
        assert "test-server" in servers
        assert "python-server" in servers

        # Check test-server config
        assert servers["test-server"]["command"] == "npx"
        assert servers["test-server"]["args"] == ["-y", "test-package"]

        # Check python-server config
        assert servers["python-server"]["command"] == "python"
        assert servers["python-server"]["args"] == ["server.py"]

    def test_discover_mcp_servers_no_config(self, tmp_path):
        """Test discovering MCP servers when config doesn't exist."""
        discovery = BassiDiscovery(tmp_path)
        servers = discovery.discover_mcp_servers()

        assert servers == {}

    def test_discover_mcp_servers_invalid_json(self, tmp_path):
        """Test discovering MCP servers with invalid JSON config."""
        # Create invalid JSON file
        (tmp_path / ".mcp.json").write_text("{ invalid json }")

        discovery = BassiDiscovery(tmp_path)
        servers = discovery.discover_mcp_servers()

        # Should return empty dict on error
        assert servers == {}

    def test_discover_mcp_servers_no_servers_key(self, tmp_path):
        """Test discovering MCP servers when config has no mcpServers key."""
        # Create valid JSON but without mcpServers
        (tmp_path / ".mcp.json").write_text(json.dumps({"other": "config"}))

        discovery = BassiDiscovery(tmp_path)
        servers = discovery.discover_mcp_servers()

        assert servers == {}

    def test_discover_skills_with_valid_skills(self, tmp_project):
        """Test discovering skills with valid SKILL.md files."""
        discovery = BassiDiscovery(tmp_project)

        # Provide explicit skill directories
        skill_dirs = [tmp_project / ".claude" / "skills"]
        skills = discovery.discover_skills(skill_dirs)

        # Should find only skill-one (has SKILL.md)
        assert len(skills) == 1
        assert skills[0]["name"] == "skill-one"
        assert "path" in skills[0]
        assert "skill_file" in skills[0]
        assert skills[0]["skill_file"].endswith("SKILL.md")

    def test_discover_skills_default_locations(
        self, tmp_project, monkeypatch
    ):
        """Test discovering skills from default locations."""
        monkeypatch.chdir(tmp_project)
        discovery = BassiDiscovery(tmp_project)

        # Use default locations (will check project and home)
        skills = discovery.discover_skills()

        # Should find at least the project skill
        assert len(skills) >= 1
        skill_names = {s["name"] for s in skills}
        assert "skill-one" in skill_names

    def test_discover_skills_no_directory(self, tmp_path):
        """Test discovering skills when directory doesn't exist."""
        discovery = BassiDiscovery(tmp_path)

        # Provide non-existent directory
        skills = discovery.discover_skills([tmp_path / "nonexistent"])

        assert skills == []

    def test_discover_skills_ignores_non_directories(self, tmp_project):
        """Test that files in skills directory are ignored."""
        discovery = BassiDiscovery(tmp_project)

        skill_dirs = [tmp_project / ".claude" / "skills"]
        skills = discovery.discover_skills(skill_dirs)

        # Should only find skill-one, not not-a-skill.md
        skill_names = {s["name"] for s in skills}
        assert "not-a-skill" not in skill_names

    def test_get_summary(self, tmp_project):
        """Test getting complete summary of all capabilities."""
        discovery = BassiDiscovery(tmp_project)
        summary = discovery.get_summary()

        assert "slash_commands" in summary
        assert "mcp_servers" in summary
        assert "skills" in summary

        # Check slash commands
        assert len(summary["slash_commands"]["project"]) == 2

        # Check MCP servers
        assert len(summary["mcp_servers"]) == 2

        # Check skills
        assert len(summary["skills"]) >= 1
        # Check agents
        assert len(summary["agents"]) >= 1

    def test_discover_agents_project(self, tmp_project):
        """Test discovering agents within the project."""
        discovery = BassiDiscovery(tmp_project)
        agent_dir = tmp_project / ".claude" / "agents"
        agents = discovery.discover_agents([agent_dir])

        assert len(agents) == 1
        agent = agents[0]
        assert agent["name"] == "writer-agent"
        assert agent["source"] == "project"
        assert agent["file"].endswith("writer-agent.md")

    def test_discover_agents_handles_missing_dir(self, tmp_path):
        """Test discovering agents when directory missing."""
        discovery = BassiDiscovery(tmp_path)
        agents = discovery.discover_agents([tmp_path / "nope"])
        assert agents == []

    def test_format_summary_with_all_items(self, tmp_project):
        """Test formatting summary with all types of items."""
        discovery = BassiDiscovery(tmp_project)
        summary = discovery.get_summary()
        formatted = discovery.format_summary(summary)

        # Check that formatted string contains expected sections
        assert "BASSI DISCOVERY" in formatted
        assert "MCP SERVERS:" in formatted
        assert "SLASH COMMANDS:" in formatted
        assert "SKILLS:" in formatted
        assert "AGENTS:" in formatted

        # Check for specific items
        assert "test-server" in formatted
        assert "python-server" in formatted
        assert "/test-cmd" in formatted
        assert "/another-cmd" in formatted
        assert "skill-one" in formatted
        assert "writer-agent" in formatted

        # Check for package info (npx command)
        assert "Package: test-package" in formatted

    def test_format_summary_with_no_items(self, tmp_path, monkeypatch):
        """Test formatting summary when no project items are found."""
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
        discovery = BassiDiscovery(tmp_path)
        summary = discovery.get_summary()
        formatted = discovery.format_summary(summary)

        # Should show "(none configured)" for MCP servers and agents
        assert "MCP SERVERS: 0" in formatted
        assert "AGENTS: 0" in formatted
        assert "(none configured)" in formatted

        # Skills should be 0 (no project or personal skills in tmp_path)
        assert "SKILLS: 0" in formatted
        assert "(none found)" in formatted

        # Note: Personal commands may exist in user's home directory, so we don't check command count

    def test_format_summary_with_precomputed_summary(self, tmp_project):
        """Test formatting with pre-computed summary."""
        discovery = BassiDiscovery(tmp_project)

        # Create custom summary
        custom_summary = {
            "mcp_servers": {
                "custom-server": {"command": "node", "args": ["server.js"]}
            },
            "slash_commands": {
                "project": [
                    {
                        "name": "/custom",
                        "file": "/path/to/custom.md",
                        "source": "project",
                    }
                ],
                "personal": [],
            },
            "skills": [
                {
                    "name": "custom-skill",
                    "path": "/path/to/skill",
                    "skill_file": "/path/to/skill/SKILL.md",
                }
            ],
        }

        formatted = discovery.format_summary(custom_summary)

        assert "custom-server" in formatted
        assert "/custom" in formatted
        assert "custom-skill" in formatted

    def test_format_summary_shows_timestamp(self, tmp_project):
        """Test that formatted summary includes timestamp."""
        discovery = BassiDiscovery(tmp_project)
        formatted = discovery.format_summary()

        # Should contain timestamp
        assert "Discovery run at:" in formatted

        # Should contain date in YYYY-MM-DD format
        import re

        assert re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", formatted)

    def test_format_summary_with_personal_commands(self, tmp_project):
        """Test formatting summary with personal commands."""
        discovery = BassiDiscovery(tmp_project)

        # Create custom summary with personal commands
        custom_summary = {
            "mcp_servers": {},
            "slash_commands": {
                "project": [],
                "personal": [
                    {
                        "name": "/personal-cmd",
                        "file": "/home/user/.claude/commands/personal-cmd.md",
                        "source": "personal",
                    },
                    {
                        "name": "/another-personal",
                        "file": "/home/user/.claude/commands/another-personal.md",
                        "source": "personal",
                    },
                ],
            },
            "skills": [],
        }

        formatted = discovery.format_summary(custom_summary)

        # Should show personal commands section
        assert "Personal commands (2):" in formatted
        assert "/personal-cmd" in formatted
        assert "/another-personal" in formatted

    def test_format_summary_with_zero_commands(self, tmp_project):
        """Test formatting summary when there are no slash commands at all."""
        discovery = BassiDiscovery(tmp_project)

        # Create custom summary with zero commands (neither project nor personal)
        custom_summary = {
            "mcp_servers": {},
            "slash_commands": {
                "project": [],
                "personal": [],
            },
            "skills": [],
        }

        formatted = discovery.format_summary(custom_summary)

        # Should show "(none found)" for slash commands when total is 0
        assert "SLASH COMMANDS: 0" in formatted
        assert "(none found)" in formatted


class TestDisplayStartupDiscovery:
    """Test startup discovery display function."""

    def test_display_startup_discovery(self, tmp_project, capsys):
        """Test displaying discovery summary at startup."""
        display_startup_discovery(tmp_project)

        # Capture printed output
        captured = capsys.readouterr()

        # Should print formatted summary
        assert "BASSI DISCOVERY" in captured.out
        assert "MCP SERVERS:" in captured.out
        assert "SLASH COMMANDS:" in captured.out
        assert "SKILLS:" in captured.out

    def test_display_startup_discovery_defaults_to_cwd(
        self, tmp_project, capsys, monkeypatch
    ):
        """Test display with default project root (cwd)."""
        monkeypatch.chdir(tmp_project)
        display_startup_discovery()

        captured = capsys.readouterr()
        assert "BASSI DISCOVERY" in captured.out
