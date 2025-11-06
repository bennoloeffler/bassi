"""
Tests for Interactive Questions System
"""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from bassi.core_v3.interactive_questions import (
    InteractiveQuestionService,
    Question,
    QuestionCancelledError,
    QuestionOption,
    QuestionTimeoutError,
    QuestionValidationError,
)


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket"""
    ws = AsyncMock()
    ws.send_json = AsyncMock()
    return ws


@pytest.fixture
def question_service(mock_websocket):
    """Create a question service with mock WebSocket"""
    service = InteractiveQuestionService()
    service.websocket = mock_websocket
    return service


def test_question_validation():
    """Test question validation"""
    # Valid question
    q = Question(
        question="Test question?",
        header="Test",
        multiSelect=False,
        options=[
            QuestionOption("Option A", "Description A"),
            QuestionOption("Option B", "Description B"),
        ],
    )
    q.validate()  # Should not raise

    # Invalid - header too long
    q_invalid = Question(
        question="Test?",
        header="ThisIsWayTooLongForAHeader",
        multiSelect=False,
        options=[
            QuestionOption("A", "Desc A"),
            QuestionOption("B", "Desc B"),
        ],
    )
    with pytest.raises(QuestionValidationError):
        q_invalid.validate()

    # Invalid - too few options
    q_invalid = Question(
        question="Test?",
        header="Test",
        multiSelect=False,
        options=[QuestionOption("A", "Only one")],
    )
    with pytest.raises(QuestionValidationError):
        q_invalid.validate()

    # Invalid - too many options
    q_invalid = Question(
        question="Test?",
        header="Test",
        multiSelect=False,
        options=[
            QuestionOption("A", "Desc"),
            QuestionOption("B", "Desc"),
            QuestionOption("C", "Desc"),
            QuestionOption("D", "Desc"),
            QuestionOption("E", "Desc"),  # 5th option
        ],
    )
    with pytest.raises(QuestionValidationError):
        q_invalid.validate()


@pytest.mark.asyncio
async def test_ask_single_question(question_service, mock_websocket):
    """Test asking a single question"""
    question = Question(
        question="Which option?",
        header="Choice",
        multiSelect=False,
        options=[
            QuestionOption("Option A", "First choice"),
            QuestionOption("Option B", "Second choice"),
        ],
    )

    # Start ask() in background
    ask_task = asyncio.create_task(
        question_service.ask([question], timeout=5.0)
    )

    # Give it a moment to send the question
    await asyncio.sleep(0.1)

    # Verify question was sent
    assert mock_websocket.send_json.called
    call_args = mock_websocket.send_json.call_args[0][0]
    assert call_args["type"] == "question"
    assert "id" in call_args
    question_id = call_args["id"]

    # Submit answer
    question_service.submit_answer(question_id, {"Which option?": "Option A"})

    # Wait for result
    result = await ask_task

    assert result == {"Which option?": "Option A"}


@pytest.mark.asyncio
async def test_ask_multiple_questions_multiselect(
    question_service, mock_websocket
):
    """Test asking multiple questions with multiSelect"""
    questions = [
        Question(
            question="Which features?",
            header="Features",
            multiSelect=True,
            options=[
                QuestionOption("Feature A", "First feature"),
                QuestionOption("Feature B", "Second feature"),
                QuestionOption("Feature C", "Third feature"),
            ],
        ),
        Question(
            question="Which database?",
            header="Database",
            multiSelect=False,
            options=[
                QuestionOption("PostgreSQL", "Relational DB"),
                QuestionOption("MongoDB", "Document DB"),
            ],
        ),
    ]

    # Start ask
    ask_task = asyncio.create_task(
        question_service.ask(questions, timeout=5.0)
    )
    await asyncio.sleep(0.1)

    # Get question ID
    call_args = mock_websocket.send_json.call_args[0][0]
    question_id = call_args["id"]

    # Submit answers
    question_service.submit_answer(
        question_id,
        {
            "Which features?": ["Feature A", "Feature C"],
            "Which database?": "PostgreSQL",
        },
    )

    # Get result
    result = await ask_task

    assert result["Which features?"] == ["Feature A", "Feature C"]
    assert result["Which database?"] == "PostgreSQL"


@pytest.mark.asyncio
async def test_question_timeout(question_service):
    """Test question timeout"""
    question = Question(
        question="Test?",
        header="Test",
        multiSelect=False,
        options=[
            QuestionOption("A", "Desc A"),
            QuestionOption("B", "Desc B"),
        ],
    )

    # Should timeout after 0.5 seconds
    with pytest.raises(QuestionTimeoutError):
        await question_service.ask([question], timeout=0.5)


@pytest.mark.asyncio
async def test_cancel_question(question_service, mock_websocket):
    """Test cancelling a question"""
    question = Question(
        question="Test?",
        header="Test",
        multiSelect=False,
        options=[
            QuestionOption("A", "Desc A"),
            QuestionOption("B", "Desc B"),
        ],
    )

    # Start ask
    ask_task = asyncio.create_task(
        question_service.ask([question], timeout=5.0)
    )
    await asyncio.sleep(0.1)

    # Get question ID
    call_args = mock_websocket.send_json.call_args[0][0]
    question_id = call_args["id"]

    # Cancel it
    question_service.cancel_question(question_id)

    # Should raise
    with pytest.raises(QuestionCancelledError):
        await ask_task


@pytest.mark.asyncio
async def test_validation_errors(question_service):
    """Test validation errors"""
    # Too many questions
    questions = [
        Question(
            question=f"Q{i}?",
            header=f"Q{i}",
            multiSelect=False,
            options=[
                QuestionOption("A", "Desc"),
                QuestionOption("B", "Desc"),
            ],
        )
        for i in range(5)  # 5 questions (max is 4)
    ]

    with pytest.raises(QuestionValidationError):
        await question_service.ask(questions)

    # No questions
    with pytest.raises(QuestionValidationError):
        await question_service.ask([])


@pytest.mark.asyncio
async def test_websocket_not_connected():
    """Test error when WebSocket not connected"""
    service = InteractiveQuestionService()
    # Don't set websocket

    question = Question(
        question="Test?",
        header="Test",
        multiSelect=False,
        options=[
            QuestionOption("A", "Desc A"),
            QuestionOption("B", "Desc B"),
        ],
    )

    with pytest.raises(RuntimeError, match="WebSocket not connected"):
        await service.ask([question])


def test_cancel_all(question_service):
    """Test cancelling all pending questions"""
    # Add some fake pending questions
    for i in range(3):
        question_service.pending_questions[f"id-{i}"] = Mock(
            event=Mock(), error=None
        )

    assert len(question_service.pending_questions) == 3

    # Cancel all
    question_service.cancel_all()

    # All should have errors and events set
    for pending in question_service.pending_questions.values():
        assert pending.error is not None
        assert pending.event.set.called
