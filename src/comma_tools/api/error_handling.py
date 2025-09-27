"""Enhanced error handling and recovery mechanisms for Phase 4A."""

import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .models import ErrorCategory

logger = logging.getLogger(__name__)


class ToolExecutionError(Exception):
    """Enhanced tool execution error with categorization."""

    def __init__(
        self,
        message: str,
        category: ErrorCategory,
        exit_code: Optional[int] = None,
        stderr: Optional[str] = None,
    ):
        super().__init__(message)
        self.category = category
        self.exit_code = exit_code
        self.stderr = stderr


class RetryableError(Exception):
    """Errors that should trigger automatic retry."""

    pass


class RecoveryStrategy:
    """Strategy enumeration for error recovery approaches."""

    AUTOMATIC = "automatic"  # Auto-retry transient failures
    PROMPT = "prompt"  # Ask user for permission
    MANUAL = "manual"  # Require explicit user action


class RecoveryManager:
    """Manages error recovery and retry logic with tenacity."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def get_recovery_strategy(self, error_category: ErrorCategory, error: Exception) -> str:
        """Determine recovery strategy based on error category and type.

        Args:
            error_category: Categorized error type
            error: The actual exception

        Returns:
            Recovery strategy string
        """
        if error_category == ErrorCategory.VALIDATION_ERROR:
            return RecoveryStrategy.MANUAL  # User must fix input

        elif error_category == ErrorCategory.SYSTEM_ERROR:
            if isinstance(error, (OSError, PermissionError)):
                return RecoveryStrategy.PROMPT  # Ask before retrying
            return RecoveryStrategy.AUTOMATIC  # Auto-retry transient issues

        elif error_category == ErrorCategory.TOOL_ERROR:
            if "memory" in str(error).lower():
                return RecoveryStrategy.PROMPT  # Ask to retry with different params
            return RecoveryStrategy.AUTOMATIC  # Auto-retry tool crashes

        return RecoveryStrategy.MANUAL

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(RetryableError),
    )
    async def execute_with_retry(self, execution_func: Callable[[], Awaitable[Any]]) -> Any:
        """Execute function with automatic retry for transient failures.

        Args:
            execution_func: Async function to execute with retry logic

        Returns:
            Result of successful execution

        Raises:
            RetryableError: For transient failures that should be retried
            Exception: For non-retryable errors
        """
        try:
            return await execution_func()
        except (OSError, asyncio.TimeoutError) as e:
            self.logger.warning(f"Transient failure detected, will retry: {e}")
            raise RetryableError(f"Transient failure: {e}") from e

    def categorize_error(self, error: Exception) -> ErrorCategory:
        """Categorize an error based on its type and message.

        Args:
            error: Exception to categorize

        Returns:
            Appropriate error category
        """
        if isinstance(error, (ValueError, TypeError)) and "parameter" in str(error).lower():
            return ErrorCategory.VALIDATION_ERROR
        elif isinstance(error, (OSError, PermissionError, FileNotFoundError)):
            return ErrorCategory.SYSTEM_ERROR
        elif isinstance(error, (RuntimeError, asyncio.TimeoutError)):
            return ErrorCategory.TOOL_ERROR
        else:
            return ErrorCategory.TOOL_ERROR

    def create_user_friendly_error(
        self,
        error: Exception,
        category: ErrorCategory,
        suggested_actions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create user-friendly error response with actionable guidance.

        Args:
            error: Original exception
            category: Error category
            suggested_actions: Optional list of suggested user actions

        Returns:
            Structured error response dictionary
        """
        base_message = str(error)

        if not suggested_actions:
            suggested_actions = self._get_default_suggestions(category, error)

        recovery_strategy = self.get_recovery_strategy(category, error)

        return {
            "error": base_message,
            "error_category": category.value,
            "suggested_actions": suggested_actions,
            "recovery_options": {
                "can_retry": recovery_strategy
                in [RecoveryStrategy.AUTOMATIC, RecoveryStrategy.PROMPT],
                "retry_strategy": recovery_strategy,
            },
            "technical_details": {
                "exception_type": type(error).__name__,
                "error_message": base_message,
            },
        }

    def _get_default_suggestions(self, category: ErrorCategory, error: Exception) -> List[str]:
        """Generate default suggestions based on error category.

        Args:
            category: Error category
            error: Original exception

        Returns:
            List of suggested actions
        """
        if category == ErrorCategory.VALIDATION_ERROR:
            return [
                "Check that all required parameters are provided",
                "Verify parameter types and values are correct",
                "Review tool documentation for parameter requirements",
            ]
        elif category == ErrorCategory.SYSTEM_ERROR:
            if isinstance(error, FileNotFoundError):
                return [
                    "Verify the input file path exists",
                    "Check file permissions",
                    "Ensure the file is not corrupted",
                ]
            elif isinstance(error, PermissionError):
                return [
                    "Check file and directory permissions",
                    "Run with appropriate user privileges",
                    "Verify write access to output directory",
                ]
            else:
                return [
                    "Check system resources (disk space, memory)",
                    "Verify environment configuration",
                    "Try again after a brief wait",
                ]
        elif category == ErrorCategory.TOOL_ERROR:
            if isinstance(error, asyncio.TimeoutError):
                return [
                    "Try with a smaller input file",
                    "Increase timeout setting if available",
                    "Check system performance and resources",
                ]
            else:
                return [
                    "Check tool-specific requirements",
                    "Verify input file format and integrity",
                    "Review tool logs for additional details",
                ]
        else:
            return ["Contact support with error details"]
