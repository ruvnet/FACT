"""
Arcade Integration Error Definitions

This module defines custom exceptions for Arcade.dev integration
errors and error handling utilities.
"""

from typing import Optional, Dict, Any

try:
    # Try relative imports first (when used as package)
    from ..core.errors import FACTError
except ImportError:
    # Fall back to absolute imports (when run as script)
    import sys
    from pathlib import Path

    # Add src to path if not already there
    src_path = str(Path(__file__).parent.parent)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    from core.errors import FACTError


class ArcadeError(FACTError):
    """Base exception class for all Arcade.dev integration errors."""

    pass


class ArcadeConnectionError(ArcadeError):
    """Raised when connection to Arcade.dev fails."""

    pass


class ArcadeAuthenticationError(ArcadeError):
    """Raised when Arcade.dev authentication fails."""

    pass


class ArcadeExecutionError(ArcadeError):
    """Raised when tool execution on Arcade.dev fails."""

    pass


class ArcadeTimeoutError(ArcadeError):
    """Raised when Arcade.dev operations timeout."""

    pass


class ArcadeRegistrationError(ArcadeError):
    """Raised when tool registration with Arcade.dev fails."""

    pass


class ArcadeSerializationError(ArcadeError):
    """Raised when request/response serialization fails."""

    pass
