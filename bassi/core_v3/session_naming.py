"""
Session Naming Service

Automatically generates meaningful session names using Claude based on the
first user-assistant message exchange.

State Machine:
- CREATED: New session, no messages yet
- AUTO_NAMED: LLM generated name after first exchange
- FINALIZED: User manually renamed or session completed
- ARCHIVED: Old session, read-only
"""

import logging
from typing import Optional

from anthropic import Anthropic

from bassi.config import Config

logger = logging.getLogger(__name__)


class SessionNamingService:
    """
    Service for generating session names using Claude.

    Responsibilities:
    - Generate concise names from conversation context
    - Update session workspace with new name
    - Trigger symlink updates
    - Manage state transitions
    """

    # Naming prompt optimized for concise, descriptive names
    NAMING_PROMPT = """You are a session naming assistant. Generate a concise, descriptive name for this conversation based on the user's first message and the assistant's response.

Requirements:
- Maximum 50 characters
- Use kebab-case (lowercase with hyphens)
- Be specific and descriptive
- Focus on the main topic or task
- No generic names like "chat" or "conversation"

Examples of good names:
- "fix-python-import-error"
- "implement-user-authentication"
- "debug-react-component-rendering"
- "analyze-sales-data-q4"
- "write-api-documentation"

User message: {user_message}

Assistant response: {assistant_response}

Generate ONLY the session name (no quotes, no explanation, just the kebab-case name):"""

    def __init__(self, config: Optional[Config] = None):
        """
        Initialize naming service.

        Args:
            config: Application config (defaults to Config())
        """
        import os

        self.config = config or Config()

        # Get API key from config or environment
        api_key = self.config.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")

        # Only create client if API key is available (test environments may not have one)
        try:
            if api_key:
                self.client = Anthropic(api_key=api_key)
                logger.debug("✅ SessionNamingService initialized with API key")
            else:
                self.client = None
                logger.warning(
                    "⚠️  No Anthropic API key - session naming will use fallback names"
                )
        except Exception as e:
            self.client = None
            logger.warning(
                f"⚠️  Failed to create Anthropic client: {e} - using fallback names"
            )

    async def generate_session_name(
        self, user_message: str, assistant_response: str
    ) -> str:
        """
        Generate session name from first message exchange.

        Args:
            user_message: User's first message
            assistant_response: Assistant's first response

        Returns:
            Generated session name in kebab-case

        Raises:
            Exception: If API call fails
        """
        # If no client available (no API key), use fallback immediately
        if self.client is None:
            logger.debug("🏷️  No API client - using fallback name")
            return self._generate_fallback_name(user_message)

        try:
            # Truncate messages to avoid excessive token usage
            user_truncated = self._truncate_message(user_message, 500)
            assistant_truncated = self._truncate_message(
                assistant_response, 500
            )

            # Format prompt
            prompt = self.NAMING_PROMPT.format(
                user_message=user_truncated,
                assistant_response=assistant_truncated,
            )

            logger.info("🏷️  Generating session name...")

            # Call Claude for name generation (use fast model)
            response = self.client.messages.create(
                model="claude-3-5-haiku-20241022",  # Fast, cheap model
                max_tokens=50,  # Only need a few words
                temperature=0.3,  # Low temperature for consistency
                messages=[{"role": "user", "content": prompt}],
            )

            # Extract generated name
            generated_name = response.content[0].text.strip()

            # Clean and validate name
            clean_name = self._clean_name(generated_name)

            logger.info(f"✅ Generated session name: {clean_name}")

            return clean_name

        except Exception as e:
            logger.error(f"❌ Failed to generate session name: {e}")
            # Fallback to generic name
            return self._generate_fallback_name(user_message)

    def _truncate_message(self, message: str, max_chars: int) -> str:
        """
        Truncate message to max_chars, adding ellipsis if truncated.

        Args:
            message: Original message
            max_chars: Maximum characters to keep

        Returns:
            Truncated message
        """
        if len(message) <= max_chars:
            return message

        return message[:max_chars] + "..."

    def _clean_name(self, name: str) -> str:
        """
        Clean and validate generated name.

        - Lowercase
        - Replace spaces/underscores with hyphens
        - Remove non-alphanumeric except hyphens
        - Truncate to 50 chars
        - Ensure not empty

        Args:
            name: Raw generated name

        Returns:
            Cleaned kebab-case name
        """
        import re

        # Remove quotes if present
        name = name.strip("\"'")

        # Lowercase and replace spaces/underscores with hyphens
        name = name.lower().replace(" ", "-").replace("_", "-")

        # Remove non-alphanumeric except hyphens
        name = re.sub(r"[^a-z0-9-]", "", name)

        # Collapse multiple hyphens
        name = re.sub(r"-+", "-", name)

        # Strip leading/trailing hyphens
        name = name.strip("-")

        # Truncate to 50 chars
        name = name[:50]

        # Ensure not empty
        if not name:
            return "unnamed-session"

        return name

    def _generate_fallback_name(self, user_message: str) -> str:
        """
        Generate fallback name from user message (no API call).

        Args:
            user_message: User's message

        Returns:
            Fallback name
        """
        # Take first 50 chars of user message and clean
        preview = user_message[:50].lower()
        preview = preview.replace(" ", "-")

        import re

        preview = re.sub(r"[^a-z0-9-]", "", preview)
        preview = re.sub(r"-+", "-", preview)
        preview = preview.strip("-")

        if not preview:
            return "new-session"

        return preview

    def should_auto_name(
        self, session_state: str, message_count: int
    ) -> bool:
        """
        Determine if session should be auto-named.

        Auto-naming triggers after first user-assistant exchange
        (when message_count reaches 2 and state is still CREATED).

        Args:
            session_state: Current session state
            message_count: Number of messages in session

        Returns:
            True if should auto-name
        """
        return session_state == "CREATED" and message_count >= 2

    def get_next_state(
        self, current_state: str, auto_named: bool = False
    ) -> str:
        """
        Get next state in state machine.

        Args:
            current_state: Current state
            auto_named: True if auto-naming just completed

        Returns:
            Next state
        """
        if current_state == "CREATED" and auto_named:
            return "AUTO_NAMED"

        # For now, keep other transitions simple
        return current_state
