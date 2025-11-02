"""
Custom MCP Tools for Bassi V3.

This module defines MCP tools that can be used by the agent,
including the AskUserQuestion tool for interactive questions.
"""

from typing import Any

from bassi.core_v3.interactive_questions import (
    InteractiveQuestionService,
    Question,
    QuestionOption,
    QuestionValidationError,
)


def create_bassi_tools(question_service: InteractiveQuestionService) -> list:
    """
    Create Bassi's custom MCP tools.

    Args:
        question_service: The interactive question service for this session

    Returns:
        List of tool functions that can be registered with MCP server
    """
    from claude_agent_sdk import tool

    @tool(
        "AskUserQuestion",
        "Use this tool when you need to ask the user questions during execution. "
        "Gather user preferences, clarify ambiguous instructions, get decisions on "
        "implementation choices, or offer choices about what direction to take.",
        {
            "type": "object",
            "required": ["questions"],
            "properties": {
                "questions": {
                    "type": "array",
                    "description": "1-4 questions to ask the user",
                    "minItems": 1,
                    "maxItems": 4,
                    "items": {
                        "type": "object",
                        "required": ["question", "header", "multiSelect", "options"],
                        "properties": {
                            "question": {
                                "type": "string",
                                "description": "The complete question to ask"
                            },
                            "header": {
                                "type": "string",
                                "description": "Very short label (max 12 chars)",
                                "maxLength": 12
                            },
                            "multiSelect": {
                                "type": "boolean",
                                "description": "Set to true to allow multiple selections. Use for non-mutually exclusive choices."
                            },
                            "options": {
                                "type": "array",
                                "description": "2-4 options for the user to choose from",
                                "minItems": 2,
                                "maxItems": 4,
                                "items": {
                                    "type": "object",
                                    "required": ["label", "description"],
                                    "properties": {
                                        "label": {
                                            "type": "string",
                                            "description": "Display text (1-5 words, concise)"
                                        },
                                        "description": {
                                            "type": "string",
                                            "description": "Explanation of what this option means or what will happen if chosen"
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
    )
    async def ask_user_question(args: dict[str, Any]) -> dict[str, Any]:
        """
        Ask user structured questions with multiple-choice options.

        Note: Users will always be able to select "Other" to provide custom
        text input - this option is added automatically by the UI.

        Example:
            ```python
            # Single question, single select
            result = ask_user_question({
                "questions": [{
                    "question": "Which auth method should we use?",
                    "header": "Auth Method",
                    "multiSelect": False,
                    "options": [
                        {"label": "OAuth", "description": "Industry standard"},
                        {"label": "JWT", "description": "Token-based"}
                    ]
                }]
            })
            # Returns answers keyed by question text

            # Multiple questions with multiSelect
            result = ask_user_question({
                "questions": [
                    {
                        "question": "Which features should we build?",
                        "header": "Features",
                        "multiSelect": True,
                        "options": [
                            {"label": "Login", "description": "User auth"},
                            {"label": "API", "description": "REST API"},
                            {"label": "Dashboard", "description": "Analytics"}
                        ]
                    },
                    {
                        "question": "What database?",
                        "header": "Database",
                        "multiSelect": False,
                        "options": [
                            {"label": "PostgreSQL", "description": "Relational"},
                            {"label": "MongoDB", "description": "Document"}
                        ]
                    }
                ]
            })
            ```
        """
        try:
            # Parse questions from args
            questions_data = args.get("questions", [])
            questions = []

            for q_data in questions_data:
                options = [
                    QuestionOption(
                        label=opt["label"],
                        description=opt["description"],
                    )
                    for opt in q_data.get("options", [])
                ]

                questions.append(
                    Question(
                        question=q_data["question"],
                        header=q_data["header"],
                        multiSelect=q_data["multiSelect"],
                        options=options,
                    )
                )

            # Ask via service and wait for answer
            answers = await question_service.ask(questions)

            # Format response
            # The answers dict maps question text to answer(s)
            # Return it in a format that Claude can understand
            formatted_answers = []
            for question_text, answer in answers.items():
                if isinstance(answer, list):
                    answer_text = ", ".join(answer)
                    formatted_answers.append(f'"{question_text}"={answer_text}')
                else:
                    formatted_answers.append(f'"{question_text}"={answer}')

            response_text = (
                "User has answered your questions: "
                + ". ".join(formatted_answers)
                + ". You can now continue with the user's answers in mind."
            )

            return {"content": [{"type": "text", "text": response_text}]}

        except QuestionValidationError as e:
            return {
                "content": [{"type": "text", "text": f"Question validation error: {e}"}],
                "isError": True,
            }
        except Exception as e:
            return {
                "content": [
                    {"type": "text", "text": f"Error asking user question: {e}"}
                ],
                "isError": True,
            }

    return [ask_user_question]
