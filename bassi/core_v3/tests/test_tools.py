"""Tests for tools.py - Custom MCP tools."""

from unittest.mock import AsyncMock, patch

import pytest

from bassi.core_v3.interactive_questions import (
    QuestionValidationError,
)
from bassi.core_v3.tools import create_bassi_tools


class TestCreateBassiTools:
    """Test create_bassi_tools function and AskUserQuestion tool."""

    @pytest.fixture
    def mock_question_service(self):
        """Create a mock interactive question service."""
        service = AsyncMock()
        service.ask = AsyncMock()
        return service

    @pytest.fixture
    def mock_tool_decorator(self):
        """Mock the tool decorator to capture the function."""
        captured_func = None

        def mock_decorator(name, description, schema):
            def wrapper(func):
                nonlocal captured_func
                captured_func = func
                return func

            return wrapper

        with patch(
            "bassi.shared.sdk_loader.tool", side_effect=mock_decorator
        ):
            yield lambda: captured_func

    def test_create_bassi_tools_returns_list(self, mock_question_service):
        """Test that create_bassi_tools returns a list of tools."""
        tools = create_bassi_tools(mock_question_service)
        assert isinstance(tools, list)
        assert len(tools) == 1

    @pytest.mark.asyncio
    async def test_ask_user_question_single_select(
        self, mock_question_service, mock_tool_decorator
    ):
        """Test asking a single question with single select."""
        # Setup
        mock_question_service.ask.return_value = {
            "Which auth method should we use?": "OAuth"
        }

        # Create tools
        create_bassi_tools(mock_question_service)
        ask_user_question = mock_tool_decorator()

        # Test single question
        args = {
            "questions": [
                {
                    "question": "Which auth method should we use?",
                    "header": "Auth Method",
                    "multiSelect": False,
                    "options": [
                        {
                            "label": "OAuth",
                            "description": "Industry standard",
                        },
                        {"label": "JWT", "description": "Token-based"},
                    ],
                }
            ]
        }

        result = await ask_user_question(args)

        # Verify
        assert "content" in result
        assert len(result["content"]) == 1
        assert result["content"][0]["type"] == "text"
        assert (
            '"Which auth method should we use?"=OAuth'
            in result["content"][0]["text"]
        )
        assert (
            "User has answered your questions:"
            in result["content"][0]["text"]
        )

        # Verify service was called
        mock_question_service.ask.assert_called_once()
        questions = mock_question_service.ask.call_args[0][0]
        assert len(questions) == 1
        assert questions[0].question == "Which auth method should we use?"
        assert questions[0].header == "Auth Method"
        assert questions[0].multiSelect is False
        assert len(questions[0].options) == 2

    @pytest.mark.asyncio
    async def test_ask_user_question_multi_select(
        self, mock_question_service, mock_tool_decorator
    ):
        """Test asking a question with multi-select enabled."""
        # Setup - multi-select returns list
        mock_question_service.ask.return_value = {
            "Which features should we build?": ["Login", "API", "Dashboard"]
        }

        create_bassi_tools(mock_question_service)
        ask_user_question = mock_tool_decorator()

        args = {
            "questions": [
                {
                    "question": "Which features should we build?",
                    "header": "Features",
                    "multiSelect": True,
                    "options": [
                        {"label": "Login", "description": "User auth"},
                        {"label": "API", "description": "REST API"},
                        {"label": "Dashboard", "description": "Analytics"},
                    ],
                }
            ]
        }

        result = await ask_user_question(args)

        # Verify list answer formatting
        assert "content" in result
        text = result["content"][0]["text"]
        assert (
            '"Which features should we build?"=Login, API, Dashboard' in text
        )

    @pytest.mark.asyncio
    async def test_ask_user_question_multiple_questions(
        self, mock_question_service, mock_tool_decorator
    ):
        """Test asking multiple questions at once."""
        # Setup
        mock_question_service.ask.return_value = {
            "Which features should we build?": ["Login", "API"],
            "What database?": "PostgreSQL",
        }

        create_bassi_tools(mock_question_service)
        ask_user_question = mock_tool_decorator()

        args = {
            "questions": [
                {
                    "question": "Which features should we build?",
                    "header": "Features",
                    "multiSelect": True,
                    "options": [
                        {"label": "Login", "description": "User auth"},
                        {"label": "API", "description": "REST API"},
                    ],
                },
                {
                    "question": "What database?",
                    "header": "Database",
                    "multiSelect": False,
                    "options": [
                        {"label": "PostgreSQL", "description": "Relational"},
                        {"label": "MongoDB", "description": "Document"},
                    ],
                },
            ]
        }

        result = await ask_user_question(args)

        # Verify both answers are formatted
        text = result["content"][0]["text"]
        assert '"Which features should we build?"=Login, API' in text
        assert '"What database?"=PostgreSQL' in text

        # Verify service was called with 2 questions
        questions = mock_question_service.ask.call_args[0][0]
        assert len(questions) == 2

    @pytest.mark.asyncio
    async def test_ask_user_question_validation_error(
        self, mock_question_service, mock_tool_decorator
    ):
        """Test handling of QuestionValidationError."""
        # Setup - service raises validation error
        mock_question_service.ask.side_effect = QuestionValidationError(
            "Invalid question format"
        )

        create_bassi_tools(mock_question_service)
        ask_user_question = mock_tool_decorator()

        args = {
            "questions": [
                {
                    "question": "Test?",
                    "header": "Test",
                    "multiSelect": False,
                    "options": [
                        {"label": "A", "description": "Option A"},
                        {"label": "B", "description": "Option B"},
                    ],
                }
            ]
        }

        result = await ask_user_question(args)

        # Verify error response
        assert "content" in result
        assert "isError" in result
        assert result["isError"] is True
        assert "Question validation error:" in result["content"][0]["text"]
        assert "Invalid question format" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_ask_user_question_generic_error(
        self, mock_question_service, mock_tool_decorator
    ):
        """Test handling of generic exceptions."""
        # Setup - service raises generic error
        mock_question_service.ask.side_effect = RuntimeError(
            "Something went wrong"
        )

        create_bassi_tools(mock_question_service)
        ask_user_question = mock_tool_decorator()

        args = {
            "questions": [
                {
                    "question": "Test?",
                    "header": "Test",
                    "multiSelect": False,
                    "options": [
                        {"label": "A", "description": "Option A"},
                        {"label": "B", "description": "Option B"},
                    ],
                }
            ]
        }

        result = await ask_user_question(args)

        # Verify error response
        assert "content" in result
        assert "isError" in result
        assert result["isError"] is True
        assert "Error asking user question:" in result["content"][0]["text"]
        assert "Something went wrong" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_ask_user_question_empty_options(
        self, mock_question_service, mock_tool_decorator
    ):
        """Test with no options in question data."""
        mock_question_service.ask.return_value = {"Test?": "Answer"}

        create_bassi_tools(mock_question_service)
        ask_user_question = mock_tool_decorator()

        args = {
            "questions": [
                {
                    "question": "Test?",
                    "header": "Test",
                    "multiSelect": False,
                    "options": [],  # Empty options
                }
            ]
        }

        result = await ask_user_question(args)

        # Should handle empty options gracefully
        assert "content" in result

        # Verify Question object was created with empty options list
        questions = mock_question_service.ask.call_args[0][0]
        assert len(questions[0].options) == 0
