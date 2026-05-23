"""
FACT System Tool Execution Engine

This module provides the ToolExecutor class that handles tool calls from LLMs,
integrates with Arcade.dev, and manages tool execution with security validation
and rate limiting.
"""

import asyncio
import time
import json
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
import structlog

try:
    # Try relative imports first (when used as package)
    from ..core.errors import (
        ToolExecutionError,
        ToolValidationError,
        ToolNotFoundError,
        UnauthorizedError,
        SecurityError,
        FinalRetryError,
    )
    from .decorators import get_tool_registry, ToolDefinition
    from .validation import ParameterValidator, SecurityValidator
    from ..arcade.client import ArcadeClient
    from ..security.auth import AuthorizationManager
    from ..monitoring.metrics import MetricsCollector
except ImportError:
    # Fall back to absolute imports (when run as script)
    import sys
    from pathlib import Path

    # Add src to path if not already there
    src_path = str(Path(__file__).parent.parent)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    from core.errors import (
        ToolExecutionError,
        ToolValidationError,
        ToolNotFoundError,
        UnauthorizedError,
        SecurityError,
        FinalRetryError,
    )
    from tools.decorators import get_tool_registry, ToolDefinition
    from tools.validation import ParameterValidator, SecurityValidator
    from arcade.client import ArcadeClient
    from security.auth import AuthorizationManager
    from arcade.client import ArcadeClient
    from monitoring.metrics import MetricsCollector


logger = structlog.get_logger(__name__)


@dataclass
class ToolCall:
    """Represents a tool call request from an LLM."""

    id: str
    name: str
    arguments: Dict[str, Any]
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    timestamp: float = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()


@dataclass
class ToolResult:
    """Represents the result of a tool execution."""

    call_id: str
    tool_name: str
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time_ms: float = 0
    status_code: int = 200
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary format."""
        result = {
            "call_id": self.call_id,
            "tool_name": self.tool_name,
            "success": self.success,
            "execution_time_ms": self.execution_time_ms,
            "status_code": self.status_code,
        }

        if self.success and self.data:
            result["data"] = self.data
        elif not self.success and self.error:
            result["error"] = self.error

        if self.metadata:
            result["metadata"] = self.metadata

        return result


class RateLimiter:
    """Simple token bucket rate limiter for tool execution."""

    def __init__(self, max_calls_per_minute: int = 60):
        """
        Initialize rate limiter.

        Args:
            max_calls_per_minute: Maximum calls allowed per minute
        """
        self.max_calls = max_calls_per_minute
        self.calls = []

    def can_execute(self, user_id: Optional[str] = None) -> bool:
        """
        Check if execution is allowed based on rate limits.

        Args:
            user_id: Optional user identifier for per-user limits

        Returns:
            True if execution is allowed
        """
        current_time = time.time()

        # Remove calls older than 1 minute
        cutoff_time = current_time - 60
        self.calls = [call_time for call_time in self.calls if call_time > cutoff_time]

        # Check if under limit
        return len(self.calls) < self.max_calls

    def record_call(self, user_id: Optional[str] = None) -> None:
        """
        Record a tool call for rate limiting.

        Args:
            user_id: Optional user identifier
        """
        self.calls.append(time.time())


class ToolExecutor:
    """
    Main tool execution engine that handles LLM tool calls.

    Provides secure tool execution with Arcade.dev integration,
    parameter validation, authorization checking, and rate limiting.
    """

    def __init__(
        self,
        arcade_client: Optional[ArcadeClient] = None,
        enable_rate_limiting: bool = True,
        max_calls_per_minute: int = 60,
        default_timeout: int = 30,
    ):
        """
        Initialize tool executor.

        Args:
            arcade_client: Arcade.dev client for tool execution
            enable_rate_limiting: Whether to enable rate limiting
            max_calls_per_minute: Maximum calls per minute
            default_timeout: Default timeout for tool execution
        """
        self.tool_registry = get_tool_registry()
        self.arcade_client = arcade_client
        self.parameter_validator = ParameterValidator()
        self.security_validator = SecurityValidator()
        self.auth_manager = AuthorizationManager()
        self.metrics_collector = MetricsCollector()

        # Rate limiting
        self.enable_rate_limiting = enable_rate_limiting
        self.rate_limiter = (
            RateLimiter(max_calls_per_minute) if enable_rate_limiting else None
        )

        self.default_timeout = default_timeout

        logger.info(
            "ToolExecutor initialized",
            rate_limiting=enable_rate_limiting,
            max_calls_per_minute=max_calls_per_minute,
        )

    async def execute_tool_call(self, tool_call: ToolCall) -> ToolResult:
        """
        Execute a single tool call with full validation and security.

        Args:
            tool_call: Tool call to execute

        Returns:
            ToolResult containing execution results
        """
        start_time = time.time()

        try:
            # Rate limiting check
            if self.enable_rate_limiting and not self.rate_limiter.can_execute(
                tool_call.user_id
            ):
                raise ToolExecutionError(
                    "Rate limit exceeded. Too many tool calls per minute."
                )

            # Get tool definition
            tool_definition = self._get_tool_definition(tool_call.name)

            # Security validation
            await self._validate_security(tool_call, tool_definition)

            # Parameter validation
            self._validate_parameters(tool_call.arguments, tool_definition)

            # Authorization check
            await self._check_authorization(tool_call, tool_definition)

            # Record call for rate limiting
            if self.enable_rate_limiting:
                self.rate_limiter.record_call(tool_call.user_id)

            # Execute tool
            result_data = await self._execute_tool(tool_call, tool_definition)

            execution_time = (time.time() - start_time) * 1000

            # Create successful result
            result = ToolResult(
                call_id=tool_call.id,
                tool_name=tool_call.name,
                success=True,
                data=result_data,
                execution_time_ms=execution_time,
                metadata={
                    "user_id": tool_call.user_id,
                    "session_id": tool_call.session_id,
                    "timestamp": tool_call.timestamp,
                },
            )

            # Log successful execution
            logger.info(
                "Tool executed successfully",
                tool_name=tool_call.name,
                call_id=tool_call.id,
                execution_time_ms=execution_time,
                user_id=tool_call.user_id,
            )

            # Record metrics
            self.metrics_collector.record_tool_execution(
                tool_name=tool_call.name, success=True, execution_time=execution_time
            )

            return result

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000

            # Create error result
            result = ToolResult(
                call_id=tool_call.id,
                tool_name=tool_call.name,
                success=False,
                error=str(e),
                execution_time_ms=execution_time,
                status_code=self._get_error_status_code(e),
                metadata={
                    "user_id": tool_call.user_id,
                    "session_id": tool_call.session_id,
                    "timestamp": tool_call.timestamp,
                    "error_type": type(e).__name__,
                },
            )

            # Log error
            logger.error(
                "Tool execution failed",
                tool_name=tool_call.name,
                call_id=tool_call.id,
                error=str(e),
                error_type=type(e).__name__,
                execution_time_ms=execution_time,
                user_id=tool_call.user_id,
            )

            # Record metrics
            self.metrics_collector.record_tool_execution(
                tool_name=tool_call.name,
                success=False,
                execution_time=execution_time,
                error_type=type(e).__name__,
            )

            return result

    async def execute_tool_calls(self, tool_calls: List[ToolCall]) -> List[ToolResult]:
        """
        Execute multiple tool calls concurrently.

        Args:
            tool_calls: List of tool calls to execute

        Returns:
            List of ToolResults in the same order as input
        """
        if not tool_calls:
            return []

        logger.info(
            "Executing tool calls batch",
            count=len(tool_calls),
            tool_names=[call.name for call in tool_calls],
        )

        # Execute all tool calls concurrently
        tasks = [self.execute_tool_call(call) for call in tool_calls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to error results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                error_result = ToolResult(
                    call_id=tool_calls[i].id,
                    tool_name=tool_calls[i].name,
                    success=False,
                    error=f"Execution failed: {str(result)}",
                    status_code=500,
                )
                processed_results.append(error_result)
            else:
                processed_results.append(result)

        return processed_results

    def get_available_tools(self) -> List[Dict[str, Any]]:
        """
        Get list of available tools with their schemas.

        Returns:
            List of tool schemas for LLM consumption
        """
        return self.tool_registry.export_all_schemas()

    def get_tool_info(self, tool_name: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Tool information dictionary
        """
        try:
            tool_definition = self.tool_registry.get_tool(tool_name)
            return {
                "name": tool_definition.name,
                "description": tool_definition.description,
                "parameters": tool_definition.parameters,
                "version": tool_definition.version,
                "requires_auth": tool_definition.requires_auth,
                "timeout_seconds": tool_definition.timeout_seconds,
                "created_at": tool_definition.created_at,
            }
        except Exception as e:
            raise ToolNotFoundError(f"Tool '{tool_name}' not found: {str(e)}")

    def _get_tool_definition(self, tool_name: str) -> ToolDefinition:
        """Get tool definition from registry."""
        try:
            return self.tool_registry.get_tool(tool_name)
        except Exception as e:
            raise ToolNotFoundError(f"Tool '{tool_name}' not found in registry")

    async def _validate_security(
        self, tool_call: ToolCall, tool_definition: ToolDefinition
    ) -> None:
        """Validate security constraints for tool call."""
        try:
            # Validate tool name and arguments for security issues
            await self.security_validator.validate_tool_call(
                tool_name=tool_call.name,
                arguments=tool_call.arguments,
                user_id=tool_call.user_id,
            )
        except Exception as e:
            raise SecurityError(f"Security validation failed: {str(e)}")

    def _validate_parameters(
        self, arguments: Dict[str, Any], tool_definition: ToolDefinition
    ) -> None:
        """Validate tool parameters against schema."""
        try:
            self.parameter_validator.validate(arguments, tool_definition.parameters)
        except Exception as e:
            raise ToolValidationError(f"Parameter validation failed: {str(e)}")

    async def _check_authorization(
        self, tool_call: ToolCall, tool_definition: ToolDefinition
    ) -> None:
        """Check user authorization for tool execution."""
        if not tool_definition.requires_auth:
            return

        if not tool_call.user_id:
            raise UnauthorizedError("User authentication required for this tool")

        try:
            await self.auth_manager.validate_authorization(
                user_id=tool_call.user_id, tool_name=tool_call.name
            )
        except Exception as e:
            raise UnauthorizedError(f"Authorization failed: {str(e)}")

    async def _execute_tool(
        self, tool_call: ToolCall, tool_definition: ToolDefinition
    ) -> Dict[str, Any]:
        """Execute the actual tool function."""
        if self.arcade_client:
            # Execute via Arcade.dev
            return await self._execute_via_arcade(tool_call, tool_definition)
        else:
            # Execute locally
            return await self._execute_locally(tool_call, tool_definition)

    async def _execute_via_arcade(
        self, tool_call: ToolCall, tool_definition: ToolDefinition
    ) -> Dict[str, Any]:
        """Execute tool via Arcade.dev gateway."""
        try:
            result = await self.arcade_client.execute_tool(
                tool_name=tool_call.name,
                arguments=tool_call.arguments,
                timeout=tool_definition.timeout_seconds,
            )
            return result
        except Exception as e:
            raise ToolExecutionError(f"Arcade execution failed: {str(e)}")

    async def _execute_locally(
        self, tool_call: ToolCall, tool_definition: ToolDefinition
    ) -> Dict[str, Any]:
        """Execute tool locally with timeout protection."""
        try:
            # Check if function is async
            import inspect

            if inspect.iscoroutinefunction(tool_definition.function):
                # Execute async function directly
                result = await asyncio.wait_for(
                    tool_definition.function(**tool_call.arguments),
                    timeout=tool_definition.timeout_seconds,
                )
            else:
                # Execute sync function in thread
                result = await asyncio.wait_for(
                    asyncio.to_thread(tool_definition.function, **tool_call.arguments),
                    timeout=tool_definition.timeout_seconds,
                )

            # Ensure result is a dictionary
            if not isinstance(result, dict):
                result = {"result": result}

            return result

        except asyncio.TimeoutError:
            raise ToolExecutionError(
                f"Tool execution timed out after {tool_definition.timeout_seconds} seconds"
            )
        except Exception as e:
            raise ToolExecutionError(f"Local execution failed: {str(e)}")

    def _get_error_status_code(self, error: Exception) -> int:
        """Get HTTP status code for error type."""
        error_codes = {
            ToolNotFoundError: 404,
            ToolValidationError: 400,
            UnauthorizedError: 401,
            SecurityError: 403,
            ToolExecutionError: 500,
            FinalRetryError: 503,
        }

        return error_codes.get(type(error), 500)


# Utility functions for tool execution


def create_tool_call(
    tool_name: str,
    arguments: Dict[str, Any],
    call_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> ToolCall:
    """
    Create a ToolCall instance with proper validation.

    Args:
        tool_name: Name of the tool to call
        arguments: Tool arguments
        call_id: Optional call identifier
        user_id: Optional user identifier

    Returns:
        ToolCall instance
    """
    if call_id is None:
        import uuid

        call_id = str(uuid.uuid4())

    return ToolCall(id=call_id, name=tool_name, arguments=arguments, user_id=user_id)


def format_tool_result_for_llm(result: ToolResult) -> Dict[str, Any]:
    """
    Format tool result for LLM consumption.

    Args:
        result: ToolResult to format

    Returns:
        Formatted result dictionary
    """
    formatted = {
        "role": "tool",
        "tool_call_id": result.call_id,
        "name": result.tool_name,
    }

    if result.success:
        formatted["content"] = json.dumps(result.data, indent=2)
    else:
        formatted["content"] = json.dumps(
            {
                "error": result.error,
                "status": "failed",
                "execution_time_ms": result.execution_time_ms,
            },
            indent=2,
        )

    return formatted
