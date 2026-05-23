"""
FACT System Tool Decorators

This module provides decorators and utilities for defining and registering
tools in the FACT system following the architecture specification.
"""

import json
import time
import functools
from typing import Dict, Any, Callable, Optional, List
from dataclasses import dataclass
import structlog

try:
    # Try relative imports first (when used as package)
    from ..core.errors import (
        ToolValidationError,
        ToolExecutionError,
        ValidationError,
        InvalidArgumentsError,
    )
except ImportError:
    # Fall back to absolute imports (when run as script)
    import sys
    from pathlib import Path

    # Add src to path if not already there
    src_path = str(Path(__file__).parent.parent)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    from core.errors import (
        ToolValidationError,
        ToolExecutionError,
        ValidationError,
        InvalidArgumentsError,
    )


logger = structlog.get_logger(__name__)


@dataclass
class ToolDefinition:
    """Represents a tool definition with metadata and validation."""

    name: str
    description: str
    parameters: Dict[str, Any]
    function: Callable
    created_at: float
    version: str = "1.0.0"
    requires_auth: bool = False
    timeout_seconds: int = 30


class ToolRegistry:
    """
    Central registry for managing tool definitions and schemas.

    Maintains a consistent state of registered tools and provides
    schema export capabilities for Claude integration.
    """

    def __init__(self):
        """Initialize empty tool registry."""
        self.tools: Dict[str, ToolDefinition] = {}
        self.schemas: Dict[str, Dict[str, Any]] = {}
        self.last_updated = time.time()

    def register_tool(self, tool_definition: ToolDefinition) -> None:
        """
        Register a tool definition in the registry.

        Args:
            tool_definition: Tool definition to register

        Raises:
            ToolValidationError: If tool definition is invalid
        """
        tool_name = tool_definition.name

        # Validate tool definition
        self._validate_tool_definition(tool_definition)

        # Check for duplicates (allow version updates)
        if tool_name in self.tools:
            existing_version = self.tools[tool_name].version
            new_version = tool_definition.version

            if not self._is_newer_version(new_version, existing_version):
                logger.warning(
                    "Tool registration skipped - same or older version",
                    tool_name=tool_name,
                    existing_version=existing_version,
                    new_version=new_version,
                )
                return

        # Register tool
        self.tools[tool_name] = tool_definition
        self.schemas[tool_name] = self._extract_schema(tool_definition)
        self.last_updated = time.time()

        logger.info(
            "Tool registered successfully",
            tool_name=tool_name,
            version=tool_definition.version,
        )

    def get_tool(self, tool_name: str) -> ToolDefinition:
        """
        Get a tool definition by name.

        Args:
            tool_name: Name of the tool to retrieve

        Returns:
            ToolDefinition for the requested tool

        Raises:
            ToolNotFoundError: If tool is not found
        """
        if tool_name not in self.tools:
            raise ToolValidationError(f"Tool not found: {tool_name}")

        return self.tools[tool_name]

    def export_all_schemas(self) -> List[Dict[str, Any]]:
        """
        Export all tool schemas in Claude-compatible format.

        Returns:
            List of tool schemas for Claude API
        """
        schema_list = []
        for tool_name in self.tools:
            schema_list.append(self.schemas[tool_name])

        logger.debug("Exported tool schemas", count=len(schema_list))
        return schema_list

    def list_tools(self) -> List[str]:
        """
        Get list of all registered tool names.

        Returns:
            List of tool names
        """
        return list(self.tools.keys())

    def get_tool_info(self) -> Dict[str, Any]:
        """
        Get registry information and statistics.

        Returns:
            Dictionary containing registry metadata
        """
        return {
            "total_tools": len(self.tools),
            "tool_names": list(self.tools.keys()),
            "last_updated": self.last_updated,
            "schema_count": len(self.schemas),
        }

    def _validate_tool_definition(self, tool_definition: ToolDefinition) -> None:
        """
        Validate tool definition structure and constraints.

        Args:
            tool_definition: Tool definition to validate

        Raises:
            ToolValidationError: If validation fails
        """
        # Validate name
        if not tool_definition.name or not tool_definition.name.strip():
            raise ToolValidationError("Tool name cannot be empty")

        if not self._follows_naming_convention(tool_definition.name):
            raise ToolValidationError(
                f"Tool name '{tool_definition.name}' does not follow naming convention"
            )

        # Validate description
        if not tool_definition.description or not tool_definition.description.strip():
            raise ToolValidationError("Tool description cannot be empty")

        # Validate parameters schema
        if not isinstance(tool_definition.parameters, dict):
            raise ToolValidationError("Tool parameters must be a dictionary")

        # Validate function is callable
        if not callable(tool_definition.function):
            raise ToolValidationError("Tool function must be callable")

        logger.debug(
            "Tool definition validation passed", tool_name=tool_definition.name
        )

    def _follows_naming_convention(self, name: str) -> bool:
        """
        Check if tool name follows the expected naming convention.

        Args:
            name: Tool name to check

        Returns:
            True if name follows convention, False otherwise
        """
        # Expected format: Category_ActionName (e.g., SQL_QueryReadonly)
        # Anthropic API requires names to match ^[a-zA-Z0-9_-]{1,64}$
        if "_" not in name:
            return False

        parts = name.split("_", 1)  # Split on first underscore only
        if len(parts) != 2:
            return False

        category, action = parts

        # Validation for Anthropic API compatibility
        import re

        pattern = r"^[a-zA-Z0-9_-]{1,64}$"

        return bool(re.match(pattern, name) and len(name) <= 64)

    def _is_newer_version(self, new_version: str, existing_version: str) -> bool:
        """
        Compare version strings to determine if new version is newer.

        Args:
            new_version: New version string
            existing_version: Existing version string

        Returns:
            True if new version is newer
        """

        def version_tuple(version: str) -> tuple:
            """Convert version string to comparable tuple."""
            try:
                return tuple(map(int, version.split(".")))
            except ValueError:
                return (0, 0, 0)  # Default for invalid versions

        return version_tuple(new_version) > version_tuple(existing_version)

    def _extract_schema(self, tool_definition: ToolDefinition) -> Dict[str, Any]:
        """
        Extract Claude-compatible schema from tool definition.

        Args:
            tool_definition: Tool definition to extract schema from

        Returns:
            Claude-compatible tool schema
        """
        # Anthropic Claude format - no "type": "function" wrapper
        schema = {
            "name": tool_definition.name,
            "description": tool_definition.description,
            "input_schema": {
                "type": "object",
                "properties": tool_definition.parameters,
                "required": self._extract_required_params(tool_definition.parameters),
            },
        }

        return schema

    def _extract_required_params(self, parameters: Dict[str, Any]) -> List[str]:
        """
        Extract required parameter names from parameters schema.

        Args:
            parameters: Parameters schema dictionary

        Returns:
            List of required parameter names
        """
        required = []
        for param_name, param_schema in parameters.items():
            if isinstance(param_schema, dict):
                # Check if parameter has no default and is not marked as optional
                if "default" not in param_schema and param_schema.get("required", True):
                    required.append(param_name)

        return required


# Global tool registry instance
_tool_registry = ToolRegistry()


def Tool(
    name: str,
    description: str,
    parameters: Dict[str, Any],
    requires_auth: bool = False,
    timeout_seconds: int = 30,
    version: str = "1.0.0",
) -> Callable:
    """
    Decorator for defining FACT system tools.

    Args:
        name: Tool name following Category.Action format
        description: Clear description of tool functionality
        parameters: JSON schema describing tool parameters
        requires_auth: Whether tool requires user authorization
        timeout_seconds: Execution timeout in seconds
        version: Tool version string

    Returns:
        Decorated function with tool metadata and validation

    Example:
        @Tool(
            name="SQL.QueryReadonly",
            description="Execute SELECT queries on the database",
            parameters={
                "statement": {
                    "type": "string",
                    "description": "SQL SELECT statement to execute"
                }
            }
        )
        def execute_sql_query(statement: str) -> Dict[str, Any]:
            # Tool implementation
            pass
    """

    def decorator(tool_function: Callable) -> Callable:
        import asyncio
        import inspect

        # Determine if we need async or sync wrapper
        is_async_tool = asyncio.iscoroutinefunction(tool_function)

        # Create the appropriate wrapper function
        if is_async_tool:

            @functools.wraps(tool_function)
            async def async_wrapped_tool(*args, **kwargs) -> Dict[str, Any]:
                """Wrapped async tool function with validation and error handling."""
                start_time = time.time()

                try:
                    # Validate input parameters against schema
                    if args or kwargs:
                        # Convert positional args to kwargs based on function signature
                        sig = inspect.signature(tool_function)
                        bound_args = sig.bind(*args, **kwargs)
                        bound_args.apply_defaults()
                        validated_kwargs = dict(bound_args.arguments)

                        # Validate against parameter schema
                        validate_tool_parameters(validated_kwargs, parameters)
                    else:
                        validated_kwargs = {}

                    # Execute async function
                    result = await tool_function(**validated_kwargs)

                    # Validate output format
                    if not isinstance(result, dict):
                        result = {"result": result}

                    # Ensure result is JSON serializable
                    json.dumps(result)

                    execution_time = (time.time() - start_time) * 1000
                    result["execution_time_ms"] = execution_time
                    result["status"] = "success"

                    logger.debug(
                        "Tool executed successfully",
                        tool_name=name,
                        execution_time_ms=execution_time,
                    )

                    return result

                except ValidationError as e:
                    execution_time = (time.time() - start_time) * 1000
                    logger.error(
                        "Tool parameter validation failed",
                        tool_name=name,
                        error=str(e),
                        execution_time_ms=execution_time,
                    )
                    raise ToolValidationError(f"Parameter validation failed: {e}")

                except Exception as e:
                    execution_time = (time.time() - start_time) * 1000
                    logger.error(
                        "Tool execution failed",
                        tool_name=name,
                        error=str(e),
                        execution_time_ms=execution_time,
                    )
                    raise ToolExecutionError(f"Tool execution failed: {e}")

            wrapped_tool = async_wrapped_tool

        else:

            @functools.wraps(tool_function)
            def sync_wrapped_tool(*args, **kwargs) -> Dict[str, Any]:
                """Wrapped sync tool function with validation and error handling."""
                start_time = time.time()

                try:
                    # Validate input parameters against schema
                    if args or kwargs:
                        # Convert positional args to kwargs based on function signature
                        sig = inspect.signature(tool_function)
                        bound_args = sig.bind(*args, **kwargs)
                        bound_args.apply_defaults()
                        validated_kwargs = dict(bound_args.arguments)

                        # Validate against parameter schema
                        validate_tool_parameters(validated_kwargs, parameters)
                    else:
                        validated_kwargs = {}

                    # Execute sync function
                    result = tool_function(**validated_kwargs)

                    # Validate output format
                    if not isinstance(result, dict):
                        result = {"result": result}

                    # Ensure result is JSON serializable
                    json.dumps(result)

                    execution_time = (time.time() - start_time) * 1000
                    result["execution_time_ms"] = execution_time
                    result["status"] = "success"

                    logger.debug(
                        "Tool executed successfully",
                        tool_name=name,
                        execution_time_ms=execution_time,
                    )

                    return result

                except ValidationError as e:
                    execution_time = (time.time() - start_time) * 1000
                    logger.error(
                        "Tool parameter validation failed",
                        tool_name=name,
                        error=str(e),
                        execution_time_ms=execution_time,
                    )
                    raise ToolValidationError(f"Parameter validation failed: {e}")

                except Exception as e:
                    execution_time = (time.time() - start_time) * 1000
                    logger.error(
                        "Tool execution failed",
                        tool_name=name,
                        error=str(e),
                        execution_time_ms=execution_time,
                    )
                    raise ToolExecutionError(f"Tool execution failed: {e}")

            wrapped_tool = sync_wrapped_tool

        # Create tool definition
        tool_definition = ToolDefinition(
            name=name,
            description=description,
            parameters=parameters,
            function=wrapped_tool,
            created_at=time.time(),
            version=version,
            requires_auth=requires_auth,
            timeout_seconds=timeout_seconds,
        )

        # Attach metadata to function
        wrapped_tool.tool_definition = tool_definition

        # Register tool automatically
        _tool_registry.register_tool(tool_definition)

        return wrapped_tool

    return decorator


def validate_tool_parameters(
    parameters: Dict[str, Any], schema: Dict[str, Any]
) -> None:
    """
    Validate tool parameters against schema definition.

    Args:
        parameters: Parameter values to validate
        schema: JSON schema for parameters

    Raises:
        ValidationError: If validation fails
    """
    errors = []

    # Check required parameters
    required_params = []
    for param_name, param_schema in schema.items():
        if (
            isinstance(param_schema, dict)
            and param_schema.get("required", True)
            and "default" not in param_schema
        ):
            required_params.append(param_name)

    for required_param in required_params:
        if required_param not in parameters:
            errors.append(f"Missing required parameter: {required_param}")

    # Validate parameter types and constraints
    for param_name, param_value in parameters.items():
        if param_name in schema:
            param_schema = schema[param_name]
            if isinstance(param_schema, dict):
                # Type validation
                expected_type = param_schema.get("type")
                if expected_type and not _validate_type(param_value, expected_type):
                    errors.append(
                        f"Invalid type for {param_name}: expected {expected_type}"
                    )

                # String constraints
                if expected_type == "string" and isinstance(param_value, str):
                    min_length = param_schema.get("minLength")
                    max_length = param_schema.get("maxLength")
                    pattern = param_schema.get("pattern")

                    if min_length and len(param_value) < min_length:
                        errors.append(
                            f"{param_name} is too short (minimum {min_length} characters)"
                        )

                    if max_length and len(param_value) > max_length:
                        errors.append(
                            f"{param_name} is too long (maximum {max_length} characters)"
                        )

                    if pattern:
                        import re

                        if not re.match(pattern, param_value):
                            errors.append(
                                f"{param_name} does not match required pattern"
                            )

                # Enum validation
                enum_values = param_schema.get("enum")
                if enum_values and param_value not in enum_values:
                    errors.append(f"{param_name} must be one of: {enum_values}")

    if errors:
        raise ValidationError("; ".join(errors))


def _validate_type(value: Any, expected_type: str) -> bool:
    """
    Validate value type against expected JSON schema type.

    Args:
        value: Value to validate
        expected_type: Expected JSON schema type

    Returns:
        True if type matches, False otherwise
    """
    type_mapping = {
        "string": str,
        "number": (int, float),
        "integer": int,
        "boolean": bool,
        "object": dict,
        "array": list,
    }

    expected_python_type = type_mapping.get(expected_type)
    if expected_python_type:
        return isinstance(value, expected_python_type)

    return False


def get_tool_registry() -> ToolRegistry:
    """
    Get the global tool registry instance.

    Returns:
        Global ToolRegistry instance
    """
    return _tool_registry
