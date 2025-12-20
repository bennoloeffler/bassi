"""
Error Recovery Service - Catches agent errors and provides context for recovery.

This service:
1. Categorizes errors (buffer overflow, MCP failures, file constraints, etc.)
2. Extracts maximum context (tool name, parameters, stack trace)
3. Generates recovery prompts for the agent to continue intelligently
"""

import logging
import re
import traceback
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """Categories of errors that can occur during agent execution."""

    BUFFER_OVERFLOW = "buffer_overflow"  # Response too large (screenshots, files)
    MCP_TOOL_FAILURE = "mcp_tool_failure"  # MCP server/tool crashed
    FILE_CONSTRAINT = "file_constraint"  # File size, type, or access violation
    NETWORK_ERROR = "network_error"  # Connection, timeout issues
    PERMISSION_DENIED = "permission_denied"  # Access denied errors
    VALIDATION_ERROR = "validation_error"  # Invalid parameters or data
    RATE_LIMIT = "rate_limit"  # API rate limiting
    TIMEOUT = "timeout"  # Operation timed out
    SDK_ERROR = "sdk_error"  # Claude SDK internal error
    UNKNOWN = "unknown"  # Unclassified error


@dataclass
class ErrorContext:
    """Rich context about an error for agent recovery."""

    category: ErrorCategory
    original_error: str
    tool_name: str | None = None
    tool_params: dict[str, Any] | None = None
    stack_summary: str | None = None
    suggestions: list[str] | None = None
    raw_exception: Exception | None = None
    original_task: str | None = None  # The task the user was trying to accomplish


class ErrorRecoveryService:
    """
    Service to handle agent errors and generate recovery context.

    Usage:
        service = ErrorRecoveryService()
        context = service.analyze_error(exception, last_tool_info)
        recovery_prompt = service.generate_recovery_prompt(context)
    """

    # Patterns to detect error categories
    ERROR_PATTERNS = {
        ErrorCategory.BUFFER_OVERFLOW: [
            r"exceeded maximum buffer size",
            r"failed to decode json.*buffer",
            r"json message exceeded",
            r"response too large",
            r"payload too large",
            r"message size exceeded",
            r"content length exceeded",
        ],
        ErrorCategory.MCP_TOOL_FAILURE: [
            r"mcp.*error",
            r"mcp.*failed",
            r"mcp.*crash",
            r"tool.*failed",
            r"server disconnected",
            r"connection.*closed.*unexpectedly",
        ],
        ErrorCategory.FILE_CONSTRAINT: [
            r"file.*too large",
            r"file.*not found",
            r"invalid file type",
            r"file size.*exceeded",
            r"unsupported.*format",
        ],
        ErrorCategory.NETWORK_ERROR: [
            r"connection.*refused",
            r"connection.*reset",
            r"network.*unreachable",
            r"dns.*failed",
            r"socket.*error",
            r"ssl.*error",
        ],
        ErrorCategory.PERMISSION_DENIED: [
            r"permission denied",
            r"access denied",
            r"unauthorized",
            r"forbidden",
            r"not allowed",
        ],
        ErrorCategory.VALIDATION_ERROR: [
            r"invalid.*parameter",
            r"validation.*failed",
            r"required.*missing",
            r"invalid.*format",
            r"schema.*error",
        ],
        ErrorCategory.RATE_LIMIT: [
            r"rate.*limit",
            r"too many requests",
            r"throttl",
            r"quota.*exceeded",
        ],
        ErrorCategory.TIMEOUT: [
            r"timeout",
            r"timed out",
            r"deadline exceeded",
            r"operation.*took too long",
        ],
        ErrorCategory.SDK_ERROR: [
            r"cancel.*scope",
            r"anyio",
            r"trio",
            r"asyncio.*error",
        ],
    }

    # Suggestions for each error category
    CATEGORY_SUGGESTIONS = {
        ErrorCategory.BUFFER_OVERFLOW: [
            "Request smaller data (e.g., smaller screenshot area)",
            "Reduce viewport/window size before capturing",
            "Use text-based alternatives instead of images",
            "Process data in chunks if possible",
        ],
        ErrorCategory.MCP_TOOL_FAILURE: [
            "Try the operation again - it may be a transient failure",
            "Check if the MCP server is still running",
            "Use an alternative tool or approach",
            "Simplify the request parameters",
        ],
        ErrorCategory.FILE_CONSTRAINT: [
            "Check if the file exists and is accessible",
            "Verify the file type is supported",
            "Try with a smaller file",
            "Use a different file format",
        ],
        ErrorCategory.NETWORK_ERROR: [
            "Retry the operation - network issues are often transient",
            "Check if the target service is available",
            "Try an alternative endpoint or service",
        ],
        ErrorCategory.PERMISSION_DENIED: [
            "Check if you have the required permissions",
            "Request access from the user if needed",
            "Try an alternative approach that doesn't require this access",
        ],
        ErrorCategory.VALIDATION_ERROR: [
            "Review the parameters and fix any invalid values",
            "Check the expected format and constraints",
            "Provide all required parameters",
        ],
        ErrorCategory.RATE_LIMIT: [
            "Wait a moment before retrying",
            "Reduce the frequency of requests",
            "Batch multiple operations together",
        ],
        ErrorCategory.TIMEOUT: [
            "Retry the operation - it may succeed on another attempt",
            "Simplify the request to reduce processing time",
            "Break the operation into smaller steps",
        ],
        ErrorCategory.SDK_ERROR: [
            "This is an internal error - the system will attempt to recover",
            "If this persists, the session may need to be restarted",
        ],
        ErrorCategory.UNKNOWN: [
            "Try the operation again",
            "Simplify your approach",
            "Use an alternative method to achieve the same goal",
        ],
    }

    def __init__(self):
        self._last_tool_info: dict[str, Any] | None = None

    def set_last_tool_info(
        self, tool_name: str | None, tool_params: dict[str, Any] | None
    ):
        """Track the last tool that was invoked (call this before tool execution)."""
        if tool_name:
            self._last_tool_info = {
                "tool_name": tool_name,
                "tool_params": tool_params or {},
            }

    def clear_last_tool_info(self):
        """Clear tool tracking after successful completion."""
        self._last_tool_info = None

    def categorize_error(self, error_message: str) -> ErrorCategory:
        """Determine the category of an error based on its message."""
        error_lower = error_message.lower()

        for category, patterns in self.ERROR_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, error_lower):
                    return category

        return ErrorCategory.UNKNOWN

    def extract_numbers_and_limits(self, error_message: str) -> dict[str, str]:
        """Extract any numbers, sizes, or limits mentioned in the error."""
        extracted = {}

        # Find byte sizes
        byte_matches = re.findall(
            r"(\d+(?:,\d+)*)\s*bytes?", error_message, re.IGNORECASE
        )
        if byte_matches:
            extracted["bytes"] = byte_matches

        # Find percentages
        pct_matches = re.findall(r"(\d+(?:\.\d+)?)\s*%", error_message)
        if pct_matches:
            extracted["percentages"] = pct_matches

        # Find general numbers with context
        num_matches = re.findall(
            r"(\d+(?:,\d+)*(?:\.\d+)?)\s*(mb|kb|gb|ms|seconds?|minutes?)?",
            error_message,
            re.IGNORECASE,
        )
        if num_matches:
            extracted["numbers"] = [
                f"{n[0]} {n[1]}".strip() for n in num_matches if n[0]
            ]

        return extracted

    def get_stack_summary(self, exception: Exception, max_frames: int = 5) -> str:
        """Get a summarized stack trace for context."""
        tb_lines = traceback.format_exception(
            type(exception), exception, exception.__traceback__
        )
        # Get the last N frames (most relevant)
        relevant_lines = []
        for line in tb_lines:
            if "File " in line or "Error" in line or "Exception" in line:
                relevant_lines.append(line.strip())

        return "\n".join(relevant_lines[-max_frames:])

    def analyze_error(
        self,
        exception: Exception,
        tool_name: str | None = None,
        tool_params: dict[str, Any] | None = None,
        original_task: str | None = None,
    ) -> ErrorContext:
        """
        Analyze an exception and create rich error context.

        Args:
            exception: The exception that occurred
            tool_name: Name of the tool that was running (if known)
            tool_params: Parameters passed to the tool (if known)
            original_task: The original user query/task being attempted

        Returns:
            ErrorContext with all available information
        """
        error_message = str(exception)
        category = self.categorize_error(error_message)

        # Use provided tool info or fall back to tracked info
        actual_tool_name = tool_name or (
            self._last_tool_info.get("tool_name") if self._last_tool_info else None
        )
        actual_tool_params = tool_params or (
            self._last_tool_info.get("tool_params") if self._last_tool_info else None
        )

        # Get suggestions for this category
        suggestions = self.CATEGORY_SUGGESTIONS.get(
            category, self.CATEGORY_SUGGESTIONS[ErrorCategory.UNKNOWN]
        )

        # Build context
        context = ErrorContext(
            category=category,
            original_error=error_message,
            tool_name=actual_tool_name,
            tool_params=actual_tool_params,
            stack_summary=self.get_stack_summary(exception),
            suggestions=suggestions,
            raw_exception=exception,
            original_task=original_task,
        )

        logger.info(
            f"🔍 Error analyzed: category={category.value}, tool={actual_tool_name}"
        )

        return context

    def generate_recovery_prompt(self, context: ErrorContext) -> str:
        """
        Generate a recovery prompt for the agent with full error context.

        The prompt gives the agent maximum information to understand what
        happened and how to proceed. CRITICAL: Includes the original task
        so the agent knows what to continue doing.
        """
        lines = []

        # Start with the ORIGINAL TASK - this is what the agent should continue
        if context.original_task:
            lines.extend(
                [
                    "**YOUR CURRENT TASK (continue this):**",
                    f"> {context.original_task}",
                    "",
                    "---",
                    "",
                ]
            )

        lines.extend(
            [
                "**ERROR ENCOUNTERED:**",
                f"- Category: {context.category.value.replace('_', ' ').title()}",
                f"- Message: {context.original_error}",
            ]
        )

        # Add tool information if available
        if context.tool_name:
            lines.append(f"**Failed Tool:** `{context.tool_name}`")

        if context.tool_params:
            # Truncate large params for readability
            params_str = str(context.tool_params)
            if len(params_str) > 500:
                params_str = params_str[:500] + "... (truncated)"
            lines.append(f"**Tool Parameters:** {params_str}")

        # Extract and show any numbers/limits
        extracted = self.extract_numbers_and_limits(context.original_error)
        if extracted:
            lines.append("**Relevant Values:**")
            for key, values in extracted.items():
                lines.append(f"  - {key}: {', '.join(str(v) for v in values)}")

        # Add suggestions
        if context.suggestions:
            lines.append("")
            lines.append("**Suggested Recovery Actions:**")
            for i, suggestion in enumerate(context.suggestions, 1):
                lines.append(f"  {i}. {suggestion}")

        # Add stack trace summary for debugging
        if context.stack_summary:
            lines.append("")
            lines.append("**Stack Trace (summary):**")
            lines.append("```")
            lines.append(context.stack_summary)
            lines.append("```")

        # Add category-specific action instructions (concise)
        action_instructions = self._get_action_instructions(context.category)

        # Build the recovery instruction - emphasize CONTINUING the task
        lines.extend(
            [
                "",
                "---",
                "",
                "**CONTINUE YOUR TASK using an alternative approach:**",
            ]
        )
        lines.extend(action_instructions)

        # Final instruction emphasizing action, not description
        lines.extend(
            [
                "",
                "Now continue working on the task above. Use tools directly.",
            ]
        )

        return "\n".join(lines)

    def _get_action_instructions(self, category: ErrorCategory) -> list[str]:
        """Get specific action instructions based on error category."""
        instructions = {
            ErrorCategory.BUFFER_OVERFLOW: [
                "The response was too large. Try ONE of these alternatives NOW:",
                "- For screenshots: Use a smaller area (set specific coordinates or reduce viewport)",
                "- For file reads: Read in smaller chunks or request specific sections",
                "- For data retrieval: Add filters or limits to reduce the response size",
                "",
                "Pick the most appropriate alternative and execute it immediately.",
            ],
            ErrorCategory.MCP_TOOL_FAILURE: [
                "The tool failed. Try ONE of these alternatives NOW:",
                "- Retry the same operation once (transient failures often resolve)",
                "- Use a different tool that can achieve the same goal",
                "- Simplify the parameters and try again",
                "",
                "Pick the most appropriate alternative and execute it immediately.",
            ],
            ErrorCategory.FILE_CONSTRAINT: [
                "The file operation failed. Try ONE of these alternatives NOW:",
                "- Verify the file path exists using a list/search command",
                "- Try a different file format if the current one isn't supported",
                "- Read/write in smaller chunks if the file is too large",
                "",
                "Pick the most appropriate alternative and execute it immediately.",
            ],
            ErrorCategory.NETWORK_ERROR: [
                "Network operation failed. Try ONE of these alternatives NOW:",
                "- Retry the operation (network issues are often transient)",
                "- Try an alternative URL or endpoint if available",
                "- Use cached data or a fallback approach",
                "",
                "Pick the most appropriate alternative and execute it immediately.",
            ],
            ErrorCategory.TIMEOUT: [
                "The operation timed out. Try ONE of these alternatives NOW:",
                "- Retry with a simpler request",
                "- Break the operation into smaller steps",
                "- Use a faster alternative approach",
                "",
                "Pick the most appropriate alternative and execute it immediately.",
            ],
            ErrorCategory.RATE_LIMIT: [
                "Rate limited. Do the following:",
                "- Wait 5-10 seconds before retrying",
                "- Batch multiple operations together if possible",
                "- Reduce request frequency",
                "",
                "After a brief pause, continue with your task.",
            ],
            ErrorCategory.PERMISSION_DENIED: [
                "Access denied. Try ONE of these alternatives NOW:",
                "- Check if there's a different way to access the resource",
                "- Try a different resource that achieves the same goal",
                "- Ask the user for permission if necessary",
                "",
                "Pick the most appropriate alternative and execute it immediately.",
            ],
            ErrorCategory.VALIDATION_ERROR: [
                "Invalid parameters. Fix and retry NOW:",
                "- Review the error message for the specific validation issue",
                "- Correct the parameter values",
                "- Retry with valid parameters",
                "",
                "Fix the issue and execute the corrected command immediately.",
            ],
        }

        return instructions.get(
            category,
            [
                "Try an alternative approach to achieve your goal.",
                "Consider what caused the error and work around it.",
                "",
                "Pick the most appropriate alternative and execute it immediately.",
            ],
        )

    def should_attempt_recovery(self, context: ErrorContext) -> bool:
        """
        Determine if automatic recovery should be attempted.

        Some errors are recoverable (agent can try alternative),
        others require user intervention or session restart.
        """
        # Always attempt recovery except for critical SDK errors
        non_recoverable = {
            ErrorCategory.SDK_ERROR,  # Internal errors need restart
        }

        return context.category not in non_recoverable


# Global instance for easy access
_error_recovery_service: ErrorRecoveryService | None = None


def get_error_recovery_service() -> ErrorRecoveryService:
    """Get the global error recovery service instance."""
    global _error_recovery_service
    if _error_recovery_service is None:
        _error_recovery_service = ErrorRecoveryService()
    return _error_recovery_service
