"""
Capability Service - Discovers available tools, MCP servers, slash commands, skills, and agents.

BLACK BOX INTERFACE:
- get_capabilities() -> Dict with tools, mcp_servers, slash_commands, skills, agents

DEPENDENCIES: BassiDiscovery, session_factory
"""

import logging
from typing import Any, Callable

import bassi.core_v3.discovery
from bassi.core_v3.session_workspace import SessionWorkspace
from bassi.core_v3.tools import InteractiveQuestionService
from bassi.shared.sdk_types import SystemMessage

logger = logging.getLogger(__name__)


class CapabilityService:
    """Service for discovering available capabilities (tools, MCP servers, etc.)."""

    def __init__(self, session_factory: Callable):
        """
        Initialize capability service.

        Args:
            session_factory: Factory function to create agent sessions
        """
        self.session_factory = session_factory

    async def get_capabilities(self) -> dict[str, Any]:
        """
        Get all available capabilities for the current session.

        Returns:
            Dictionary with:
            - tools: List of available tool names
            - mcp_servers: List of configured MCP servers
            - slash_commands: List of available slash commands
            - skills: List of available skills
            - agents: List of available agents

        Note:
            This method creates a temporary session to query the SDK for tool discovery.
            Filesystem-based capabilities (commands, skills) are discovered via BassiDiscovery,
            but SDK data (tools, agents) overrides where applicable.
        """
        try:
            # Get filesystem discovery data
            discovery = bassi.core_v3.discovery.BassiDiscovery()
            summary = discovery.get_summary()

            # Transform MCP servers with status field
            mcp_servers = []
            for name, config in summary.get("mcp_servers", {}).items():
                mcp_servers.append(
                    {
                        "name": name,
                        "status": "configured",  # Could be enhanced to check if running
                        **config,
                    }
                )

            # Initialize with discovery data (will be overridden by SDK if available)
            slash_commands = []
            for source, commands in summary.get("slash_commands", {}).items():
                slash_commands.extend(commands)

            skills = summary.get("skills", [])

            # Get SDK tools and agents via temporary session
            tools = []
            agents = summary.get("agents", [])

            temp_service = InteractiveQuestionService()
            temp_workspace = SessionWorkspace(
                "capabilities-discovery", create=True
            )
            logger.info("🔧 Creating temp session for capability discovery...")
            temp_session = self.session_factory(temp_service, temp_workspace)
            logger.info(f"🔧 Temp session created: {type(temp_session).__name__}")

            try:
                logger.info("🔗 Connecting temp session...")
                await temp_session.connect()
                logger.info("✅ Temp session connected")

                # Send a minimal query to trigger tool discovery
                tools_found = []

                logger.info("🔍 Starting tool discovery query...")
                async for message in temp_session.query(
                    "ready", session_id="capabilities-discovery"
                ):
                    msg_type = type(message).__name__
                    logger.info(f"📨 Capability discovery - received: {msg_type}")

                    # Extract tool names from system message with 'init' subtype
                    if isinstance(message, SystemMessage):
                        logger.info(
                            f"✅ Found SystemMessage with subtype: {message.subtype}"
                        )
                        logger.debug(
                            f"   Data keys: {list(message.data.keys()) if isinstance(message.data, dict) else 'not a dict'}"
                        )

                        # Only process 'init' subtype which contains tools/capabilities
                        if message.subtype != "init":
                            continue

                        # Extract data from SystemMessage.data
                        if isinstance(message.data, dict):
                            # Get tools (list of dicts with 'name' key)
                            sdk_tools = message.data.get("tools", [])
                            for tool in sdk_tools:
                                if isinstance(tool, dict) and "name" in tool:
                                    tools_found.append(tool["name"])
                                elif isinstance(tool, str):
                                    tools_found.append(tool)

                            # Extract agents
                            sdk_agents = message.data.get("agents", [])
                            if sdk_agents:
                                agents = sdk_agents

                            # Extract slash commands from SDK (overrides discovery)
                            sdk_slash_commands = message.data.get(
                                "slash_commands", []
                            )
                            if sdk_slash_commands:
                                slash_commands = sdk_slash_commands

                            # Extract skills from SDK (overrides discovery)
                            sdk_skills = message.data.get("skills", [])
                            if sdk_skills:
                                skills = sdk_skills

                            logger.info(
                                f"✅ Extracted {len(tools_found)} tools, "
                                f"{len(slash_commands)} commands, {len(agents)} agents"
                            )
                        else:
                            logger.warning(
                                "⚠️ SystemMessage.data is not a dict!"
                            )

                        break  # Stop after getting system message

                if tools_found:
                    logger.info(
                        f"✅ Tool discovery complete. Found {len(tools_found)} tools"
                    )
                else:
                    logger.warning(
                        "⚠️ Tool discovery completed but no tools found! "
                        "Check if SDK returned 'init' SystemMessage with tools."
                    )
                tools = tools_found

                await temp_session.disconnect()

            except Exception as sdk_error:
                logger.warning(
                    f"Could not fetch SDK tools: {sdk_error}", exc_info=True
                )
                # Continue without SDK tools - discovery data still works

            return {
                "tools": tools,
                "mcp_servers": mcp_servers,
                "slash_commands": slash_commands,
                "skills": skills,
                "agents": agents,
            }

        except Exception as e:
            logger.error(f"Error fetching capabilities: {e}", exc_info=True)
            raise
