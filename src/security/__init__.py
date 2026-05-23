"""
FACT System Security Components

This package provides security functionality including authentication,
authorization, validation, and audit logging.
"""

# Use try/except to handle both relative and absolute imports
try:
    from .auth import AuthorizationManager, Authorization, AuthFlow
except ImportError:
    # Fallback to absolute imports when called from scripts
    from security.auth import AuthorizationManager, Authorization, AuthFlow

__all__ = ["AuthorizationManager", "Authorization", "AuthFlow"]
