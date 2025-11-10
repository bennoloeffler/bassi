"""Tests for session_naming.py - Session naming service."""

from unittest.mock import MagicMock, patch

import pytest

from bassi.core_v3.session_naming import SessionNamingService


class TestSessionNamingService:
    """Test SessionNamingService class."""

    @pytest.fixture
    def mock_config(self):
        """Create mock config."""
        config = MagicMock()
        config.anthropic_api_key = "test-api-key"
        return config

    @pytest.fixture
    def naming_service(self, mock_config):
        """Create naming service with mock config."""
        with patch("bassi.core_v3.session_naming.Anthropic"):
            return SessionNamingService(config=mock_config)

    def test_init_with_config(self, mock_config):
        """Test initialization with config."""
        with patch(
            "bassi.core_v3.session_naming.Anthropic"
        ) as mock_anthropic:
            service = SessionNamingService(config=mock_config)

            assert service.config == mock_config
            mock_anthropic.assert_called_once_with(api_key="test-api-key")

    def test_init_without_config(self):
        """Test initialization without config (uses default)."""
        with (
            patch("bassi.core_v3.session_naming.Anthropic"),
            patch("bassi.core_v3.session_naming.Config") as mock_config_class,
        ):
            mock_config_class.return_value.anthropic_api_key = "default-key"

            service = SessionNamingService()

            assert service.config is not None

    @pytest.mark.asyncio
    async def test_generate_session_name_success(self, naming_service):
        """Test successful session name generation."""
        # Mock Claude API response
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="fix-python-import-error")]
        naming_service.client.messages.create.return_value = mock_response

        result = await naming_service.generate_session_name(
            user_message="I'm getting an import error in my Python code",
            assistant_response="Let me help you fix that import error",
        )

        assert result == "fix-python-import-error"
        naming_service.client.messages.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_session_name_with_long_messages(
        self, naming_service
    ):
        """Test with messages that need truncation."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="long-conversation")]
        naming_service.client.messages.create.return_value = mock_response

        long_message = "a" * 1000  # 1000 chars

        result = await naming_service.generate_session_name(
            user_message=long_message, assistant_response=long_message
        )

        assert result == "long-conversation"

        # Verify truncation happened in the API call
        call_args = naming_service.client.messages.create.call_args
        prompt = call_args.kwargs["messages"][0]["content"]
        # Each message should be truncated to 500 + "..."
        assert len(prompt) < len(long_message) * 2

    @pytest.mark.asyncio
    async def test_generate_session_name_api_error(self, naming_service):
        """Test handling of API errors with fallback."""
        naming_service.client.messages.create.side_effect = Exception(
            "API Error"
        )

        result = await naming_service.generate_session_name(
            user_message="fix my code", assistant_response="sure"
        )

        # Should return fallback name
        assert result == "fix-my-code"

    @pytest.mark.asyncio
    async def test_generate_session_name_cleans_response(
        self, naming_service
    ):
        """Test that generated names are properly cleaned."""
        # Mock API returns name with quotes and special chars
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='"Fix Python Import Error!"')]
        naming_service.client.messages.create.return_value = mock_response

        result = await naming_service.generate_session_name(
            user_message="help", assistant_response="ok"
        )

        # Should be cleaned to kebab-case
        assert result == "fix-python-import-error"

    def test_truncate_message_short(self, naming_service):
        """Test truncating message that's already short enough."""
        message = "Hello, world!"
        result = naming_service._truncate_message(message, 100)
        assert result == message

    def test_truncate_message_long(self, naming_service):
        """Test truncating long message."""
        message = "a" * 100
        result = naming_service._truncate_message(message, 50)
        assert result == "a" * 50 + "..."
        assert len(result) == 53  # 50 chars + "..."

    def test_clean_name_basic(self, naming_service):
        """Test basic name cleaning."""
        assert (
            naming_service._clean_name("Fix Python Error")
            == "fix-python-error"
        )

    def test_clean_name_with_quotes(self, naming_service):
        """Test cleaning name with quotes."""
        assert naming_service._clean_name('"my-session"') == "my-session"
        assert naming_service._clean_name("'my-session'") == "my-session"

    def test_clean_name_with_underscores(self, naming_service):
        """Test converting underscores to hyphens."""
        assert (
            naming_service._clean_name("fix_python_error")
            == "fix-python-error"
        )

    def test_clean_name_with_special_chars(self, naming_service):
        """Test removing special characters."""
        assert (
            naming_service._clean_name("fix@python#error!")
            == "fixpythonerror"
        )

    def test_clean_name_multiple_hyphens(self, naming_service):
        """Test collapsing multiple hyphens."""
        assert (
            naming_service._clean_name("fix---python---error")
            == "fix-python-error"
        )

    def test_clean_name_leading_trailing_hyphens(self, naming_service):
        """Test stripping leading/trailing hyphens."""
        assert (
            naming_service._clean_name("-fix-python-error-")
            == "fix-python-error"
        )

    def test_clean_name_too_long(self, naming_service):
        """Test truncating name to 50 chars."""
        long_name = "a" * 100
        result = naming_service._clean_name(long_name)
        assert len(result) == 50

    def test_clean_name_empty(self, naming_service):
        """Test handling empty name."""
        assert naming_service._clean_name("") == "unnamed-session"
        assert naming_service._clean_name("!!!") == "unnamed-session"

    def test_generate_fallback_name_basic(self, naming_service):
        """Test basic fallback name generation."""
        result = naming_service._generate_fallback_name("Fix my Python code")
        assert result == "fix-my-python-code"

    def test_generate_fallback_name_long(self, naming_service):
        """Test fallback name truncation."""
        long_message = "a" * 100
        result = naming_service._generate_fallback_name(long_message)
        assert len(result) == 50

    def test_generate_fallback_name_special_chars(self, naming_service):
        """Test fallback name with special characters."""
        result = naming_service._generate_fallback_name("Fix @#$ my code!")
        assert result == "fix-my-code"

    def test_generate_fallback_name_empty(self, naming_service):
        """Test fallback name with empty/invalid message."""
        assert naming_service._generate_fallback_name("") == "new-session"
        assert naming_service._generate_fallback_name("!!!") == "new-session"

    def test_should_auto_name_created_state_with_messages(
        self, naming_service
    ):
        """Test should auto-name when conditions are met."""
        assert naming_service.should_auto_name("CREATED", 2) is True
        assert naming_service.should_auto_name("CREATED", 3) is True

    def test_should_auto_name_created_state_no_messages(self, naming_service):
        """Test should not auto-name without enough messages."""
        assert naming_service.should_auto_name("CREATED", 0) is False
        assert naming_service.should_auto_name("CREATED", 1) is False

    def test_should_auto_name_other_states(self, naming_service):
        """Test should not auto-name in other states."""
        assert naming_service.should_auto_name("AUTO_NAMED", 2) is False
        assert naming_service.should_auto_name("FINALIZED", 2) is False
        assert naming_service.should_auto_name("ARCHIVED", 2) is False

    def test_get_next_state_created_to_auto_named(self, naming_service):
        """Test state transition from CREATED to AUTO_NAMED."""
        result = naming_service.get_next_state("CREATED", auto_named=True)
        assert result == "AUTO_NAMED"

    def test_get_next_state_created_not_auto_named(self, naming_service):
        """Test CREATED state remains when not auto-naming."""
        result = naming_service.get_next_state("CREATED", auto_named=False)
        assert result == "CREATED"

    def test_get_next_state_other_states(self, naming_service):
        """Test other states remain unchanged."""
        assert naming_service.get_next_state("AUTO_NAMED") == "AUTO_NAMED"
        assert naming_service.get_next_state("FINALIZED") == "FINALIZED"
        assert naming_service.get_next_state("ARCHIVED") == "ARCHIVED"
