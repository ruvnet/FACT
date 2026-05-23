"""
FACT System Secure Error Handling

This module provides secure error handling to prevent information disclosure
while maintaining useful error reporting for debugging and monitoring.
"""

import traceback
import sys
from typing import Any, Dict, Optional, Tuple
from dataclasses import dataclass
import structlog

from core.errors import (
    SecurityError,
    AuthenticationError,
    ValidationError,
    DatabaseError,
    ToolExecutionError,
    CacheError,
)

logger = structlog.get_logger(__name__)


@dataclass
class SecureErrorResponse:
    """Represents a sanitized error response."""

    error_code: str
    message: str
    status_code: int
    details: Optional[Dict[str, Any]] = None
    error_id: Optional[str] = None


class SecureErrorHandler:
    """
    Secure error handler that sanitizes error responses to prevent
    information disclosure while maintaining debugging capabilities.
    """

    def __init__(self, debug_mode: bool = False):
        """
        Initialize secure error handler.

        Args:
            debug_mode: Whether to include debug information in responses
        """
        self.debug_mode = debug_mode

        # Error code mappings for different exception types
        self.error_mappings = {
            SecurityError: ("SECURITY_ERROR", 403),
            AuthenticationError: ("AUTH_ERROR", 401),
            ValidationError: ("VALIDATION_ERROR", 400),
            DatabaseError: ("DATABASE_ERROR", 500),
            ToolExecutionError: ("TOOL_ERROR", 500),
            CacheError: ("CACHE_ERROR", 500),
            PermissionError: ("PERMISSION_ERROR", 403),
            FileNotFoundError: ("NOT_FOUND", 404),
            ValueError: ("INVALID_VALUE", 400),
            TypeError: ("INVALID_TYPE", 400),
            KeyError: ("MISSING_KEY", 400),
            ConnectionError: ("CONNECTION_ERROR", 503),
            TimeoutError: ("TIMEOUT_ERROR", 504),
        }

        # Safe error messages that don't reveal system internals
        self.safe_messages = {
            "SECURITY_ERROR": "Access denied due to security policy",
            "AUTH_ERROR": "Authentication required or invalid credentials",
            "VALIDATION_ERROR": "Input validation failed",
            "DATABASE_ERROR": "Database operation failed",
            "TOOL_ERROR": "Tool execution failed",
            "CACHE_ERROR": "Cache operation failed",
            "PERMISSION_ERROR": "Insufficient permissions",
            "NOT_FOUND": "Resource not found",
            "INVALID_VALUE": "Invalid input value provided",
            "INVALID_TYPE": "Invalid input type provided",
            "MISSING_KEY": "Required parameter missing",
            "CONNECTION_ERROR": "Service temporarily unavailable",
            "TIMEOUT_ERROR": "Request timed out",
            "INTERNAL_ERROR": "An internal error occurred",
        }

        # Patterns to sanitize from error messages
        self.sensitive_patterns = [
            r"password[=:]\s*\S+",
            r"api[_-]?key[=:]\s*\S+",
            r"token[=:]\s*\S+",
            r"secret[=:]\s*\S+",
            r"auth[=:]\s*\S+",
            r"/[a-zA-Z]:/.*",  # Windows paths
            r"/home/[^/\s]+",  # Unix home paths
            r"/etc/[^/\s]+",  # System config paths
            r"localhost:\d+",  # Local endpoints
            r"127\.0\.0\.1:\d+",  # Local IP endpoints
            r"(\d{1,3}\.){3}\d{1,3}:\d+",  # IP:port combinations
        ]

    def handle_exception(
        self, exception: Exception, context: Optional[Dict[str, Any]] = None
    ) -> SecureErrorResponse:
        """
        Handle an exception and return a secure error response.

        Args:
            exception: The exception to handle
            context: Optional context information

        Returns:
            SecureErrorResponse with sanitized error information
        """
        # Generate unique error ID for tracking
        import uuid

        error_id = str(uuid.uuid4())

        # Get error code and status code
        error_code, status_code = self._get_error_info(exception)

        # Get safe message
        safe_message = self._get_safe_message(exception, error_code)

        # Log full error details for debugging
        self._log_error_details(exception, error_id, context)

        # Prepare response details
        details = None
        if self.debug_mode:
            details = self._get_debug_details(exception, context)

        return SecureErrorResponse(
            error_code=error_code,
            message=safe_message,
            status_code=status_code,
            details=details,
            error_id=error_id,
        )

    def sanitize_error_message(self, message: str) -> str:
        """
        Sanitize an error message to remove sensitive information.

        Args:
            message: Original error message

        Returns:
            Sanitized error message
        """
        import re

        sanitized = message

        # Remove sensitive patterns
        for pattern in self.sensitive_patterns:
            sanitized = re.sub(pattern, "[REDACTED]", sanitized, flags=re.IGNORECASE)

        # Remove file paths
        sanitized = re.sub(r"/[\w/.]+\.py", "[FILE_PATH]", sanitized)
        sanitized = re.sub(r"[A-Z]:\\[\w\\/.]+\.py", "[FILE_PATH]", sanitized)

        # Remove line numbers from stack traces
        sanitized = re.sub(r"line \d+", "line [NUM]", sanitized)

        # Remove memory addresses
        sanitized = re.sub(r"0x[0-9a-fA-F]+", "[MEMORY_ADDR]", sanitized)

        # Truncate very long messages
        if len(sanitized) > 500:
            sanitized = sanitized[:497] + "..."

        return sanitized

    def format_error_response(
        self, error_response: SecureErrorResponse
    ) -> Dict[str, Any]:
        """
        Format error response for API consumption.

        Args:
            error_response: SecureErrorResponse to format

        Returns:
            Formatted error response dictionary
        """
        response = {
            "error": True,
            "error_code": error_response.error_code,
            "message": error_response.message,
            "error_id": error_response.error_id,
        }

        if error_response.details and self.debug_mode:
            response["details"] = error_response.details

        return response

    def _get_error_info(self, exception: Exception) -> Tuple[str, int]:
        """Get error code and HTTP status code for exception."""
        exception_type = type(exception)

        # Check for exact type match
        if exception_type in self.error_mappings:
            error_code, status_code = self.error_mappings[exception_type]
            return error_code, status_code

        # Check for inheritance
        for exc_type, (error_code, status_code) in self.error_mappings.items():
            if isinstance(exception, exc_type):
                return error_code, status_code

        # Default for unknown exceptions
        return "INTERNAL_ERROR", 500

    def _get_safe_message(self, exception: Exception, error_code: str) -> str:
        """Get a safe error message that doesn't reveal system internals."""
        # First try to get the safe message from our mappings
        safe_message = self.safe_messages.get(error_code, "An error occurred")

        # For known security-related exceptions, we can include some details
        if isinstance(exception, (ValidationError, SecurityError)):
            # These exceptions are designed to be user-facing
            original_message = str(exception)
            sanitized_message = self.sanitize_error_message(original_message)

            # Only use the original message if it's reasonably safe
            if len(sanitized_message) < 200 and not any(
                keyword in sanitized_message.lower()
                for keyword in ["password", "token", "key", "secret", "internal"]
            ):
                return sanitized_message

        return safe_message

    def _log_error_details(
        self, exception: Exception, error_id: str, context: Optional[Dict[str, Any]]
    ) -> None:
        """Log full error details for debugging purposes."""
        error_details = {
            "error_id": error_id,
            "exception_type": type(exception).__name__,
            "exception_message": str(exception),
            "context": context or {},
        }

        # Add stack trace in debug mode
        if self.debug_mode:
            error_details["stack_trace"] = traceback.format_exc()

        # Log based on severity
        if isinstance(exception, (SecurityError, AuthenticationError)):
            logger.warning("Security-related error occurred", **error_details)
        elif isinstance(exception, (ValidationError, ValueError, TypeError)):
            logger.info("Input validation error occurred", **error_details)
        else:
            logger.error("System error occurred", **error_details)

    def _get_debug_details(
        self, exception: Exception, context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Get debug details for development environment."""
        if not self.debug_mode:
            return {}

        details = {
            "exception_type": type(exception).__name__,
            "exception_message": self.sanitize_error_message(str(exception)),
        }

        if context:
            # Sanitize context information
            sanitized_context = {}
            for key, value in context.items():
                if isinstance(value, str):
                    sanitized_context[key] = self.sanitize_error_message(value)
                elif isinstance(value, (int, float, bool)):
                    sanitized_context[key] = value
                else:
                    sanitized_context[key] = str(type(value))

            details["context"] = sanitized_context

        return details


# Global error handler instance
_error_handler_instance: Optional[SecureErrorHandler] = None


def get_error_handler(debug_mode: bool = False) -> SecureErrorHandler:
    """
    Get or create global error handler instance.

    Args:
        debug_mode: Whether to enable debug mode

    Returns:
        SecureErrorHandler instance
    """
    global _error_handler_instance

    if _error_handler_instance is None:
        _error_handler_instance = SecureErrorHandler(debug_mode)

    return _error_handler_instance


def handle_error(
    exception: Exception,
    context: Optional[Dict[str, Any]] = None,
    debug_mode: bool = False,
) -> Dict[str, Any]:
    """
    Convenience function to handle an error and return a formatted response.

    Args:
        exception: Exception to handle
        context: Optional context information
        debug_mode: Whether to include debug information

    Returns:
        Formatted error response dictionary
    """
    error_handler = get_error_handler(debug_mode)
    error_response = error_handler.handle_exception(exception, context)
    return error_handler.format_error_response(error_response)


def sanitize_message(message: str) -> str:
    """
    Convenience function to sanitize an error message.

    Args:
        message: Message to sanitize

    Returns:
        Sanitized message
    """
    error_handler = get_error_handler()
    return error_handler.sanitize_error_message(message)
