"""
FACT System Arcade Integration

This package provides integration with Arcade.dev for secure tool hosting
and execution in containerized environments.
"""

# Use try/except to handle both relative and absolute imports
try:
    from .client import ArcadeClient
    from .gateway import ArcadeGateway
    from .errors import ArcadeError, ArcadeConnectionError, ArcadeExecutionError
except ImportError:
    # Fallback to absolute imports when called from scripts
    from arcade.client import ArcadeClient
    from arcade.gateway import ArcadeGateway
    from arcade.errors import ArcadeError, ArcadeConnectionError, ArcadeExecutionError

__all__ = [
    "ArcadeClient",
    "ArcadeGateway",
    "ArcadeError",
    "ArcadeConnectionError",
    "ArcadeExecutionError",
]
