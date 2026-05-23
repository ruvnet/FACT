"""
FACT System Arcade.dev Client

This module provides the ArcadeClient class for integrating with Arcade.dev
tool hosting and execution platform using the arcadepy library.
"""

import asyncio
import json
import time
from typing import Dict, Any, List, Optional, Union
import structlog

# Import arcadepy when available
try:
    import arcade

    ARCADE_AVAILABLE = True
except ImportError:
    ARCADE_AVAILABLE = False
    arcade = None

try:
    # Try relative imports first (when used as package)
    from .errors import (
        ArcadeConnectionError,
        ArcadeAuthenticationError,
        ArcadeExecutionError,
        ArcadeTimeoutError,
        ArcadeRegistrationError,
        ArcadeSerializationError,
    )
    from ..core.errors import ToolExecutionError
except ImportError:
    # Fall back to absolute imports (when run as script)
    import sys
    from pathlib import Path

    # Add src to path if not already there
    src_path = str(Path(__file__).parent.parent)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    from arcade.errors import (
        ArcadeConnectionError,
        ArcadeAuthenticationError,
        ArcadeExecutionError,
        ArcadeTimeoutError,
        ArcadeRegistrationError,
        ArcadeSerializationError,
    )
    from core.errors import ToolExecutionError


logger = structlog.get_logger(__name__)


class ArcadeClient:
    """
    Client for interacting with Arcade.dev tool hosting platform.

    Provides secure tool execution, registration, and management
    through the Arcade.dev gateway infrastructure.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
    ):
        """
        Initialize Arcade client.

        Args:
            api_key: Arcade.dev API key
            base_url: Base URL for Arcade.dev API
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
        """
        if not ARCADE_AVAILABLE:
            raise ImportError(
                "arcadepy library not available. Install with: pip install arcadepy"
            )

        self.api_key = api_key
        self.base_url = base_url or "https://api.arcade.dev"
        self.timeout = timeout
        self.max_retries = max_retries

        # Initialize arcade client
        self._client = None
        self._connected = False

        logger.info("ArcadeClient initialized", base_url=self.base_url, timeout=timeout)

    async def connect(self) -> None:
        """
        Establish connection to Arcade.dev platform.

        Raises:
            ArcadeConnectionError: If connection fails
            ArcadeAuthenticationError: If authentication fails
        """
        try:
            # Initialize arcade client with API key
            if self.api_key:
                self._client = arcade.Client(
                    api_key=self.api_key, base_url=self.base_url, timeout=self.timeout
                )
            else:
                self._client = arcade.Client(
                    base_url=self.base_url, timeout=self.timeout
                )

            # Test connection with a simple API call
            await self._test_connection()

            self._connected = True
            logger.info("Connected to Arcade.dev successfully")

        except Exception as e:
            logger.error("Failed to connect to Arcade.dev", error=str(e))
            if "authentication" in str(e).lower() or "api key" in str(e).lower():
                raise ArcadeAuthenticationError(f"Authentication failed: {str(e)}")
            else:
                raise ArcadeConnectionError(f"Connection failed: {str(e)}")

    async def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        timeout: Optional[int] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a tool on Arcade.dev platform.

        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments
            timeout: Execution timeout in seconds
            user_id: Optional user identifier for logging

        Returns:
            Tool execution result

        Raises:
            ArcadeExecutionError: If execution fails
            ArcadeTimeoutError: If execution times out
        """
        if not self._connected or not self._client:
            await self.connect()

        execution_timeout = timeout or self.timeout
        start_time = time.time()

        try:
            logger.info(
                "Executing tool on Arcade.dev",
                tool_name=tool_name,
                user_id=user_id,
                timeout=execution_timeout,
            )

            # Prepare execution request
            execution_request = {
                "tool": tool_name,
                "arguments": arguments,
                "timeout": execution_timeout,
            }

            if user_id:
                execution_request["user_id"] = user_id

            # Execute tool with timeout
            result = await asyncio.wait_for(
                self._execute_with_retry(execution_request), timeout=execution_timeout
            )

            execution_time = (time.time() - start_time) * 1000

            logger.info(
                "Tool executed successfully on Arcade.dev",
                tool_name=tool_name,
                execution_time_ms=execution_time,
                user_id=user_id,
            )

            return self._process_execution_result(result, execution_time)

        except asyncio.TimeoutError:
            execution_time = (time.time() - start_time) * 1000
            logger.error(
                "Tool execution timed out",
                tool_name=tool_name,
                timeout=execution_timeout,
                execution_time_ms=execution_time,
            )
            raise ArcadeTimeoutError(
                f"Tool execution timed out after {execution_timeout} seconds"
            )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(
                "Tool execution failed",
                tool_name=tool_name,
                error=str(e),
                execution_time_ms=execution_time,
            )
            raise ArcadeExecutionError(f"Tool execution failed: {str(e)}")

    async def register_tool(
        self, tool_definition: Dict[str, Any], source_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Register a tool with Arcade.dev platform.

        Args:
            tool_definition: Tool definition including name, description, parameters
            source_code: Optional source code for the tool

        Returns:
            Registration result

        Raises:
            ArcadeRegistrationError: If registration fails
        """
        if not self._connected or not self._client:
            await self.connect()

        try:
            logger.info(
                "Registering tool with Arcade.dev",
                tool_name=tool_definition.get("name"),
            )

            # Prepare registration request
            registration_request = {
                "name": tool_definition["name"],
                "description": tool_definition["description"],
                "parameters": tool_definition["parameters"],
            }

            if source_code:
                registration_request["source_code"] = source_code

            # Add metadata
            registration_request["metadata"] = {
                "version": tool_definition.get("version", "1.0.0"),
                "requires_auth": tool_definition.get("requires_auth", False),
                "timeout_seconds": tool_definition.get("timeout_seconds", 30),
                "created_at": time.time(),
            }

            # Register tool
            result = await self._client.tools.register(registration_request)

            logger.info(
                "Tool registered successfully",
                tool_name=tool_definition["name"],
                tool_id=result.get("id"),
            )

            return result

        except Exception as e:
            logger.error(
                "Tool registration failed",
                tool_name=tool_definition.get("name"),
                error=str(e),
            )
            raise ArcadeRegistrationError(f"Tool registration failed: {str(e)}")

    async def list_tools(self) -> List[Dict[str, Any]]:
        """
        List all registered tools on Arcade.dev platform.

        Returns:
            List of registered tools

        Raises:
            ArcadeConnectionError: If request fails
        """
        if not self._connected or not self._client:
            await self.connect()

        try:
            result = await self._client.tools.list()

            logger.debug(
                "Retrieved tool list from Arcade.dev",
                tool_count=len(result.get("tools", [])),
            )

            return result.get("tools", [])

        except Exception as e:
            logger.error("Failed to list tools", error=str(e))
            raise ArcadeConnectionError(f"Failed to list tools: {str(e)}")

    async def get_tool_info(self, tool_name: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Tool information

        Raises:
            ArcadeConnectionError: If request fails
        """
        if not self._connected or not self._client:
            await self.connect()

        try:
            result = await self._client.tools.get(tool_name)

            logger.debug("Retrieved tool info from Arcade.dev", tool_name=tool_name)

            return result

        except Exception as e:
            logger.error("Failed to get tool info", tool_name=tool_name, error=str(e))
            raise ArcadeConnectionError(f"Failed to get tool info: {str(e)}")

    async def delete_tool(self, tool_name: str) -> bool:
        """
        Delete a tool from Arcade.dev platform.

        Args:
            tool_name: Name of the tool to delete

        Returns:
            True if deletion was successful

        Raises:
            ArcadeConnectionError: If request fails
        """
        if not self._connected or not self._client:
            await self.connect()

        try:
            await self._client.tools.delete(tool_name)

            logger.info("Tool deleted successfully", tool_name=tool_name)

            return True

        except Exception as e:
            logger.error("Failed to delete tool", tool_name=tool_name, error=str(e))
            raise ArcadeConnectionError(f"Failed to delete tool: {str(e)}")

    async def get_execution_logs(
        self, execution_id: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get execution logs for a specific execution.

        Args:
            execution_id: Execution identifier
            limit: Maximum number of log entries

        Returns:
            List of log entries

        Raises:
            ArcadeConnectionError: If request fails
        """
        if not self._connected or not self._client:
            await self.connect()

        try:
            result = await self._client.executions.get_logs(execution_id, limit=limit)

            logger.debug(
                "Retrieved execution logs",
                execution_id=execution_id,
                log_count=len(result.get("logs", [])),
            )

            return result.get("logs", [])

        except Exception as e:
            logger.error(
                "Failed to get execution logs", execution_id=execution_id, error=str(e)
            )
            raise ArcadeConnectionError(f"Failed to get execution logs: {str(e)}")

    async def close(self) -> None:
        """Close the Arcade client connection."""
        if self._client:
            try:
                await self._client.close()
            except Exception as e:
                logger.warning("Error closing Arcade client", error=str(e))
            finally:
                self._client = None
                self._connected = False
                logger.info("Arcade client connection closed")

    async def _test_connection(self) -> None:
        """Test connection to Arcade.dev platform."""
        try:
            # Simple health check or authentication test
            if hasattr(self._client, "health"):
                await self._client.health.check()
            else:
                # Fallback to listing tools as a connection test
                await self._client.tools.list()
        except Exception as e:
            logger.error("Connection test failed", error=str(e))
            raise

    async def _execute_with_retry(
        self, execution_request: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute tool with retry logic."""
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                return await self._client.tools.execute(execution_request)
            except Exception as e:
                last_error = e
                if attempt < self.max_retries:
                    wait_time = 2**attempt  # Exponential backoff
                    logger.warning(
                        "Tool execution attempt failed, retrying",
                        attempt=attempt + 1,
                        max_retries=self.max_retries,
                        wait_time=wait_time,
                        error=str(e),
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(
                        "All retry attempts exhausted",
                        attempts=self.max_retries + 1,
                        error=str(e),
                    )

        raise last_error

    def _process_execution_result(
        self, result: Dict[str, Any], execution_time: float
    ) -> Dict[str, Any]:
        """Process and validate execution result."""
        try:
            # Ensure result has required fields
            processed_result = {
                "success": result.get("success", True),
                "execution_time_ms": execution_time,
            }

            if result.get("success", True):
                processed_result["data"] = result.get("data", result)
            else:
                processed_result["error"] = result.get("error", "Unknown error")
                processed_result["success"] = False

            # Add metadata if available
            if "metadata" in result:
                processed_result["metadata"] = result["metadata"]

            return processed_result

        except Exception as e:
            logger.error("Failed to process execution result", error=str(e))
            raise ArcadeSerializationError(
                f"Failed to process execution result: {str(e)}"
            )


# Utility functions for Arcade integration


def create_arcade_client(
    api_key: Optional[str] = None, base_url: Optional[str] = None
) -> ArcadeClient:
    """
    Create and configure an Arcade client.

    Args:
        api_key: Arcade.dev API key
        base_url: Base URL for Arcade.dev API

    Returns:
        Configured ArcadeClient instance
    """
    return ArcadeClient(api_key=api_key, base_url=base_url)


async def test_arcade_connection(client: ArcadeClient) -> bool:
    """
    Test connection to Arcade.dev platform.

    Args:
        client: ArcadeClient instance

    Returns:
        True if connection is successful
    """
    try:
        await client.connect()
        return True
    except Exception as e:
        logger.error("Arcade connection test failed", error=str(e))
        return False
