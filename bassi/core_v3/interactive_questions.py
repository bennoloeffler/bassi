"""
Interactive Questions Service - Implements Claude Code's AskUserQuestion functionality.

This module provides the coordination layer for asking users structured questions
with multiple-choice options during agent execution.
"""

import asyncio
import uuid
from dataclasses import dataclass
from typing import Any, Optional

from fastapi import WebSocket


class QuestionTimeoutError(Exception):
    """Raised when a question times out waiting for user response"""

    pass


class QuestionCancelledError(Exception):
    """Raised when a question is cancelled (e.g., WebSocket disconnect)"""

    pass


class QuestionValidationError(Exception):
    """Raised when question format is invalid"""

    pass


@dataclass
class QuestionOption:
    """A single option in a question"""

    label: str  # 1-5 words
    description: str


@dataclass
class Question:
    """A single question with options"""

    question: str  # The question text
    header: str  # Short label (max 12 chars)
    multiSelect: bool  # Allow multiple selections
    options: list[QuestionOption]  # 2-4 options

    def validate(self):
        """Validate question format"""
        if not self.question:
            raise QuestionValidationError("Question text is required")

        if not self.header or len(self.header) > 12:
            raise QuestionValidationError("Header must be 1-12 characters")

        if len(self.options) < 2 or len(self.options) > 4:
            raise QuestionValidationError("Must have 2-4 options")

        for option in self.options:
            if not option.label or not option.description:
                raise QuestionValidationError("Option label and description required")


@dataclass
class PendingQuestion:
    """A question waiting for user response"""

    question_id: str
    questions: list[Question]
    event: asyncio.Event
    answer: Optional[dict[str, str | list[str]]] = None
    error: Optional[Exception] = None


class InteractiveQuestionService:
    """
    Service for coordinating interactive questions between agent and UI.

    This service manages the lifecycle of questions:
    1. Agent calls ask() with questions
    2. Service sends question to UI via WebSocket
    3. Service waits for user response
    4. User answers via WebSocket
    5. Service returns answer to agent

    Features:
    - Timeout handling
    - Session isolation (one service per WebSocket connection)
    - MultiSelect support
    - Automatic "Other" option
    - Question validation

    Example:
        ```python
        service = InteractiveQuestionService()
        service.websocket = websocket  # Set by web server

        # Ask a question
        answer = await service.ask(questions=[
            Question(
                question="Which auth method?",
                header="Auth",
                multiSelect=False,
                options=[
                    QuestionOption("OAuth", "Industry standard"),
                    QuestionOption("JWT", "Token-based auth")
                ]
            )
        ])
        # Returns: {"Which auth method?": "OAuth"}
        ```
    """

    def __init__(self):
        self.websocket: Optional[WebSocket] = None
        self.pending_questions: dict[str, PendingQuestion] = {}

    async def ask(
        self,
        questions: list[Question],
        timeout: float = 300.0,  # 5 minutes default
    ) -> dict[str, str | list[str]]:
        """
        Ask user questions and wait for response.

        Args:
            questions: List of 1-4 questions to ask
            timeout: Maximum seconds to wait for response

        Returns:
            Dictionary mapping question text to answer(s)
            - Single answer (string) for non-multiSelect
            - Multiple answers (list[str]) for multiSelect

        Raises:
            QuestionValidationError: Invalid question format
            QuestionTimeoutError: User didn't respond in time
            QuestionCancelledError: Question was cancelled
            RuntimeError: WebSocket not connected

        Example:
            ```python
            answers = await service.ask(questions=[
                Question(
                    question="Which features?",
                    header="Features",
                    multiSelect=True,
                    options=[
                        QuestionOption("Login", "User authentication"),
                        QuestionOption("API", "REST API endpoints")
                    ]
                )
            ])
            # Returns: {"Which features?": ["Login", "API"]}
            ```
        """
        # Validate inputs
        if not questions or len(questions) > 4:
            raise QuestionValidationError("Must provide 1-4 questions")

        for question in questions:
            question.validate()

        if not self.websocket:
            raise RuntimeError("WebSocket not connected")

        # Create pending question
        question_id = str(uuid.uuid4())
        event = asyncio.Event()
        pending = PendingQuestion(
            question_id=question_id,
            questions=questions,
            event=event,
        )
        self.pending_questions[question_id] = pending

        # Send question to UI
        try:
            await self.websocket.send_json(
                {
                    "type": "question",
                    "id": question_id,
                    "questions": [
                        {
                            "question": q.question,
                            "header": q.header,
                            "multiSelect": q.multiSelect,
                            "options": [
                                {"label": opt.label, "description": opt.description}
                                for opt in q.options
                            ],
                        }
                        for q in questions
                    ],
                }
            )
        except Exception as e:
            # Clean up on send failure
            del self.pending_questions[question_id]
            raise QuestionCancelledError(f"Failed to send question: {e}") from e

        # Wait for response with timeout
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            # Clean up
            del self.pending_questions[question_id]
            raise QuestionTimeoutError(
                f"Question timed out after {timeout} seconds"
            ) from None

        # Check for errors
        if pending.error:
            error = pending.error
            del self.pending_questions[question_id]
            raise error

        # Get answer
        answer = pending.answer
        del self.pending_questions[question_id]

        if answer is None:
            raise QuestionCancelledError("Question was cancelled without answer")

        return answer

    def submit_answer(
        self, question_id: str, answers: dict[str, str | list[str]]
    ) -> None:
        """
        Submit user's answer to a pending question.

        This is called by the WebSocket handler when user submits their answer.

        Args:
            question_id: ID of the question being answered
            answers: Dictionary mapping question text to answer(s)

        Example:
            ```python
            # User selected "OAuth" for single-select question
            service.submit_answer(
                "uuid-123",
                {"Which auth method?": "OAuth"}
            )

            # User selected multiple options
            service.submit_answer(
                "uuid-456",
                {"Which features?": ["Login", "API"]}
            )
            ```
        """
        if question_id not in self.pending_questions:
            # Question already answered or timed out - ignore
            return

        pending = self.pending_questions[question_id]
        pending.answer = answers
        pending.event.set()

    def cancel_question(self, question_id: str, error: Optional[Exception] = None):
        """
        Cancel a pending question.

        This is called when the WebSocket disconnects or an error occurs.

        Args:
            question_id: ID of the question to cancel
            error: Optional error to attach
        """
        if question_id not in self.pending_questions:
            return

        pending = self.pending_questions[question_id]
        pending.error = error or QuestionCancelledError("Question cancelled")
        pending.event.set()

    def cancel_all(self, error: Optional[Exception] = None):
        """
        Cancel all pending questions.

        This is called when the WebSocket disconnects.

        Args:
            error: Optional error to attach to all questions
        """
        for question_id in list(self.pending_questions.keys()):
            self.cancel_question(question_id, error)
