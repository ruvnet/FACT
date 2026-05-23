"""
FACT System Error Definitions and Handling

This module defines custom exceptions and error handling utilities
for the FACT system following the architecture specification.
"""

from typing import Optional, Dict, Any
import structlog

logger = structlog.get_logger(__name__)


class FACTError(Exception):
    """Base exception class for all FACT system errors."""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize FACT error.

        Args:
            message: Human-readable error message
            error_code: Optional error code for categorization
            context: Optional context information for debugging
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.context = context or {}


class ConfigurationError(FACTError):
    """Raised when system configuration is invalid or missing."""

    pass


class ConnectionError(FACTError):
    """Raised when API connectivity tests fail."""

    pass


class AuthenticationError(FACTError):
    """Raised when API authentication fails."""

    pass


class ValidationError(FACTError):
    """Raised when input validation fails."""

    pass


class ToolExecutionError(FACTError):
    """Raised when tool execution fails."""

    pass


class ToolValidationError(FACTError):
    """Raised when tool validation fails."""

    pass


class ToolNotFoundError(FACTError):
    """Raised when a requested tool is not found."""

    pass


class UnauthorizedError(FACTError):
    """Raised when user lacks authorization for a tool."""

    pass


class InvalidArgumentsError(FACTError):
    """Raised when tool arguments are invalid."""

    pass


class DatabaseError(FACTError):
    """Raised when database operations fail."""

    pass


class SecurityError(FACTError):
    """Raised when security violations are detected."""

    pass


class InvalidSQLError(FACTError):
    """Raised when SQL statements are invalid or dangerous."""

    pass


class CacheError(FACTError):
    """Raised when cache operations fail."""

    pass


class ToolRegistrationError(FACTError):
    """Raised when tool registration fails."""

    pass


class FinalRetryError(FACTError):
    """Raised when maximum retry attempts are exceeded."""

    pass


def classify_error(error: Exception) -> str:
    """
    Classify an error into a category for handling strategies.

    Args:
        error: Exception to classify

    Returns:
        String category of the error
    """
    error_type = type(error)

    # Map error types to categories
    error_categories = {
        ConfigurationError: "configuration",
        ConnectionError: "connectivity",
        AuthenticationError: "authentication",
        ValidationError: "validation",
        ToolExecutionError: "tool_execution",
        ToolValidationError: "tool_execution",
        ToolNotFoundError: "tool_execution",
        UnauthorizedError: "authentication",
        InvalidArgumentsError: "validation",
        DatabaseError: "database",
        SecurityError: "security",
        InvalidSQLError: "security",
        CacheError: "cache",
        ToolRegistrationError: "tool_registration",
        FinalRetryError: "connectivity",
    }

    category = error_categories.get(error_type, "unknown")

    logger.debug(
        "Error classified",
        error_type=error_type.__name__,
        category=category,
        message=str(error),
    )

    return category


def create_user_friendly_message(error: Exception) -> str:
    """
    Create a user-friendly error message from an exception.

    Args:
        error: Exception to convert

    Returns:
        User-friendly error message
    """
    category = classify_error(error)

    # Default user-friendly messages by category
    friendly_messages = {
        "configuration": "System configuration error. Please check your setup.",
        "connectivity": "Connection error. Please check your internet connection and try again.",
        "authentication": "Authentication failed. Please check your API credentials.",
        "validation": f"Input validation error: {str(error)}",
        "tool_execution": "Tool execution failed. The requested operation could not be completed.",
        "database": "Database error. Please try again later.",
        "security": "Security violation detected. Operation blocked for safety.",
        "cache": "Cache operation failed. Continuing without cache optimization.",
        "tool_registration": "Tool registration failed. Please check your tool configuration.",
        "unknown": "An unexpected error occurred. Please try again later.",
    }

    # Use specific message if available, otherwise use category default
    if hasattr(error, "message"):
        return error.message

    return friendly_messages.get(category, str(error))


def log_error_with_context(
    error: Exception, context: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log error with full context information.

    Args:
        error: Exception to log
        context: Additional context information
    """
    error_context = {
        "error_type": type(error).__name__,
        "error_message": str(error),
        "error_category": classify_error(error),
    }

    # Add specific error context if available
    if hasattr(error, "context"):
        error_context.update(error.context)

    # Add provided context
    if context:
        error_context.update(context)

    logger.error("Error occurred", **error_context)


def provide_graceful_degradation(failed_component: str) -> str:
    """
    Provide graceful degradation message for failed components.

    Args:
        failed_component: Name of the component that failed

    Returns:
        Graceful degradation message
    """
    degradation_messages = {
        "cache": "Cache unavailable, processing without cache optimization",
        "tools": "I'm sorry, I can't access live data right now. Please try again later.",
        "database": "Database is temporarily unavailable. Please contact support.",
        "anthropic": "Claude API is temporarily unavailable. Please try again later.",
        "arcade": "Tool execution service is temporarily unavailable. Please try again later.",
    }

    message = degradation_messages.get(
        failed_component, "System is experiencing issues. Please try again later."
    )

    logger.warning(
        "Graceful degradation activated", component=failed_component, message=message
    )

    return message
