"""
FACT System Arcade Gateway

This module provides gateway functionality for routing tool execution
requests between local execution and Arcade.dev platform.
"""

import asyncio
from typing import Dict, Any, Optional
import structlog

try:
    # Try relative imports first (when used as package)
    from .client import ArcadeClient
    from .errors import ArcadeError, ArcadeExecutionError
    from ..core.errors import ToolExecutionError
except ImportError:
    # Fall back to absolute imports (when run as script)
    import sys
    from pathlib import Path

    # Add src to path if not already there
    src_path = str(Path(__file__).parent.parent)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    from arcade.client import ArcadeClient
    from arcade.errors import ArcadeError, ArcadeExecutionError
    from core.errors import ToolExecutionError


logger = structlog.get_logger(__name__)


class ArcadeGateway:
    """
    Gateway for routing tool execution between local and Arcade.dev execution.

    Provides intelligent routing, fallback mechanisms, and execution
    orchestration for tools that can run locally or on Arcade.dev.
    """

    def __init__(
        self,
        arcade_client: Optional[ArcadeClient] = None,
        enable_fallback: bool = True,
        prefer_arcade: bool = False,
    ):
        """
        Initialize Arcade gateway.

        Args:
            arcade_client: Optional Arcade client for remote execution
            enable_fallback: Whether to fallback to local execution on Arcade failure
            prefer_arcade: Whether to prefer Arcade execution over local
        """
        self.arcade_client = arcade_client
        self.enable_fallback = enable_fallback
        self.prefer_arcade = prefer_arcade

        logger.info(
            "ArcadeGateway initialized",
            has_arcade_client=bool(arcade_client),
            enable_fallback=enable_fallback,
            prefer_arcade=prefer_arcade,
        )

    async def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        local_function: Optional[callable] = None,
        user_id: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Execute a tool using the best available method.

        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments
            local_function: Local function to execute if available
            user_id: Optional user identifier
            timeout: Execution timeout

        Returns:
            Tool execution result

        Raises:
            ToolExecutionError: If execution fails on all available methods
        """
        execution_methods = self._determine_execution_order(tool_name, local_function)

        last_error = None

        for method in execution_methods:
            try:
                if method == "arcade":
                    logger.debug(
                        "Attempting Arcade execution",
                        tool_name=tool_name,
                        user_id=user_id,
                    )

                    result = await self._execute_via_arcade(
                        tool_name, arguments, user_id, timeout
                    )

                    logger.info(
                        "Tool executed successfully via Arcade",
                        tool_name=tool_name,
                        user_id=user_id,
                    )

                    return result

                elif method == "local":
                    logger.debug(
                        "Attempting local execution",
                        tool_name=tool_name,
                        user_id=user_id,
                    )

                    result = await self._execute_locally(
                        tool_name, local_function, arguments
                    )

                    logger.info(
                        "Tool executed successfully locally",
                        tool_name=tool_name,
                        user_id=user_id,
                    )

                    return result

            except Exception as e:
                last_error = e
                logger.warning(
                    "Execution method failed",
                    method=method,
                    tool_name=tool_name,
                    error=str(e),
                )

                # If this is the last method and fallback is disabled, raise immediately
                if not self.enable_fallback and method == execution_methods[0]:
                    raise

        # All methods failed
        error_msg = f"Tool execution failed on all available methods. Last error: {str(last_error)}"
        logger.error(
            "All execution methods failed",
            tool_name=tool_name,
            methods_tried=execution_methods,
            last_error=str(last_error),
        )

        raise ToolExecutionError(error_msg)

    def _determine_execution_order(
        self, tool_name: str, local_function: Optional[callable]
    ) -> list:
        """
        Determine the order of execution methods to try.

        Args:
            tool_name: Name of the tool
            local_function: Local function if available

        Returns:
            List of execution methods in order of preference
        """
        methods = []

        # If we prefer Arcade and have a client, try Arcade first
        if self.prefer_arcade and self.arcade_client:
            methods.append("arcade")

            # Add local as fallback if available and fallback is enabled
            if local_function and self.enable_fallback:
                methods.append("local")

        # If we prefer local or don't have Arcade client
        else:
            # Try local first if available
            if local_function:
                methods.append("local")

            # Add Arcade as fallback if available and fallback is enabled
            if self.arcade_client and self.enable_fallback:
                methods.append("arcade")

        # If no methods are available, at least try what we have
        if not methods:
            if self.arcade_client:
                methods.append("arcade")
            elif local_function:
                methods.append("local")

        return methods

    async def _execute_via_arcade(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        user_id: Optional[str],
        timeout: Optional[int],
    ) -> Dict[str, Any]:
        """
        Execute tool via Arcade.dev platform.

        Args:
            tool_name: Name of the tool
            arguments: Tool arguments
            user_id: Optional user identifier
            timeout: Execution timeout

        Returns:
            Arcade execution result

        Raises:
            ArcadeExecutionError: If Arcade execution fails
        """
        if not self.arcade_client:
            raise ArcadeExecutionError("No Arcade client available")

        try:
            result = await self.arcade_client.execute_tool(
                tool_name=tool_name,
                arguments=arguments,
                timeout=timeout,
                user_id=user_id,
            )

            # Ensure result has expected structure
            if not isinstance(result, dict):
                raise ArcadeExecutionError("Invalid result format from Arcade")

            # Add execution metadata
            result["execution_method"] = "arcade"
            result["platform"] = "arcade.dev"

            return result

        except ArcadeError:
            raise
        except Exception as e:
            raise ArcadeExecutionError(f"Arcade execution failed: {str(e)}")

    async def _execute_locally(
        self, tool_name: str, local_function: callable, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute tool locally using provided function.

        Args:
            tool_name: Name of the tool
            local_function: Local function to execute
            arguments: Tool arguments

        Returns:
            Local execution result

        Raises:
            ToolExecutionError: If local execution fails
        """
        if not local_function:
            raise ToolExecutionError("No local function available")

        try:
            # Execute function (handle both sync and async functions)
            if asyncio.iscoroutinefunction(local_function):
                result = await local_function(**arguments)
            else:
                # Run sync function in thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None, lambda: local_function(**arguments)
                )

            # Ensure result is a dictionary
            if not isinstance(result, dict):
                result = {"result": result}

            # Add execution metadata
            result["execution_method"] = "local"
            result["platform"] = "local"

            return result

        except Exception as e:
            raise ToolExecutionError(f"Local execution failed: {str(e)}")

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on available execution methods.

        Returns:
            Health check results
        """
        health_status = {
            "gateway_healthy": True,
            "arcade_available": False,
            "local_available": True,  # Local execution is always available
            "methods": [],
        }

        # Check Arcade availability
        if self.arcade_client:
            try:
                # Simple connectivity test
                await self.arcade_client.connect()
                health_status["arcade_available"] = True
                health_status["methods"].append("arcade")

                logger.debug("Arcade health check passed")

            except Exception as e:
                logger.warning("Arcade health check failed", error=str(e))
                health_status["arcade_error"] = str(e)

        # Local execution is always available
        health_status["methods"].append("local")

        # Overall health
        health_status["gateway_healthy"] = len(health_status["methods"]) > 0

        return health_status

    def get_execution_stats(self) -> Dict[str, Any]:
        """
        Get execution statistics and configuration.

        Returns:
            Execution statistics
        """
        return {
            "arcade_client_configured": bool(self.arcade_client),
            "fallback_enabled": self.enable_fallback,
            "prefer_arcade": self.prefer_arcade,
            "available_methods": ["arcade"] if self.arcade_client else [] + ["local"],
        }


def create_arcade_gateway(
    arcade_client: Optional[ArcadeClient] = None,
    enable_fallback: bool = True,
    prefer_arcade: bool = False,
) -> ArcadeGateway:
    """
    Create and configure an Arcade gateway.

    Args:
        arcade_client: Optional Arcade client
        enable_fallback: Whether to enable fallback between methods
        prefer_arcade: Whether to prefer Arcade over local execution

    Returns:
        Configured ArcadeGateway instance
    """
    return ArcadeGateway(
        arcade_client=arcade_client,
        enable_fallback=enable_fallback,
        prefer_arcade=prefer_arcade,
    )
