"""
FACT System Tool Parameter Validation

This module provides validation utilities for tool parameters and security
constraints to ensure safe and reliable tool execution.
"""

import re
import json
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import structlog

try:
    # Try relative imports first (when used as package)
    from ..core.errors import ValidationError, SecurityError
except ImportError:
    # Fall back to absolute imports (when run as script)
    import sys
    from pathlib import Path

    # Add src to path if not already there
    src_path = str(Path(__file__).parent.parent)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    from core.errors import ValidationError, SecurityError


logger = structlog.get_logger(__name__)


class ParameterValidator:
    """
    Validates tool parameters against JSON schema definitions.

    Provides comprehensive validation including type checking, constraint
    validation, and security sanitization.
    """

    def __init__(self):
        """Initialize parameter validator."""
        self.type_validators = {
            "string": self._validate_string,
            "number": self._validate_number,
            "integer": self._validate_integer,
            "boolean": self._validate_boolean,
            "object": self._validate_object,
            "array": self._validate_array,
        }

    def validate(self, parameters: Dict[str, Any], schema: Dict[str, Any]) -> None:
        """
        Validate parameters against schema definition.

        Args:
            parameters: Parameter values to validate
            schema: JSON schema for parameters

        Raises:
            ValidationError: If validation fails
        """
        errors = []

        try:
            # Check required parameters
            required_params = self._extract_required_params(schema)
            for required_param in required_params:
                if required_param not in parameters:
                    errors.append(f"Missing required parameter: {required_param}")

            # Validate each parameter
            for param_name, param_value in parameters.items():
                if param_name in schema:
                    param_schema = schema[param_name]
                    param_errors = self._validate_parameter(
                        param_name, param_value, param_schema
                    )
                    errors.extend(param_errors)
                else:
                    # Allow extra parameters but log warning
                    logger.warning(
                        "Unknown parameter provided",
                        parameter=param_name,
                        value=str(param_value)[:100],
                    )

            if errors:
                error_message = "; ".join(errors)
                logger.error(
                    "Parameter validation failed",
                    errors=errors,
                    parameter_count=len(parameters),
                )
                raise ValidationError(error_message)

            logger.debug("Parameter validation passed", parameter_count=len(parameters))

        except ValidationError:
            raise
        except Exception as e:
            logger.error("Unexpected validation error", error=str(e))
            raise ValidationError(f"Validation failed: {str(e)}")

    def _extract_required_params(self, schema: Dict[str, Any]) -> List[str]:
        """Extract required parameter names from schema."""
        required = []

        for param_name, param_schema in schema.items():
            if isinstance(param_schema, dict):
                # Parameter is required if it has no default and is not marked as optional
                if (
                    "default" not in param_schema
                    and param_schema.get("required", True)
                    and not param_schema.get("optional", False)
                ):
                    required.append(param_name)

        return required

    def _validate_parameter(
        self, name: str, value: Any, schema: Dict[str, Any]
    ) -> List[str]:
        """Validate a single parameter against its schema."""
        errors = []

        # Type validation
        param_type = schema.get("type")
        if param_type:
            type_validator = self.type_validators.get(param_type)
            if type_validator:
                type_errors = type_validator(name, value, schema)
                errors.extend(type_errors)
            else:
                errors.append(f"Unknown type '{param_type}' for parameter {name}")

        # Enum validation
        enum_values = schema.get("enum")
        if enum_values and value not in enum_values:
            errors.append(f"{name} must be one of: {enum_values}")

        return errors

    def _validate_string(
        self, name: str, value: Any, schema: Dict[str, Any]
    ) -> List[str]:
        """Validate string parameter."""
        errors = []

        if not isinstance(value, str):
            errors.append(f"{name} must be a string")
            return errors

        # Length constraints
        min_length = schema.get("minLength")
        max_length = schema.get("maxLength")

        if min_length is not None and len(value) < min_length:
            errors.append(f"{name} must be at least {min_length} characters long")

        if max_length is not None and len(value) > max_length:
            errors.append(f"{name} must be at most {max_length} characters long")

        # Pattern validation
        pattern = schema.get("pattern")
        if pattern:
            try:
                if not re.match(pattern, value):
                    errors.append(f"{name} does not match required pattern")
            except re.error as e:
                errors.append(f"Invalid pattern for {name}: {str(e)}")

        # Format validation
        format_type = schema.get("format")
        if format_type:
            format_errors = self._validate_string_format(name, value, format_type)
            errors.extend(format_errors)

        return errors

    def _validate_number(
        self, name: str, value: Any, schema: Dict[str, Any]
    ) -> List[str]:
        """Validate number parameter."""
        errors = []

        if not isinstance(value, (int, float)):
            errors.append(f"{name} must be a number")
            return errors

        # Range constraints
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        exclusive_minimum = schema.get("exclusiveMinimum")
        exclusive_maximum = schema.get("exclusiveMaximum")

        if minimum is not None and value < minimum:
            errors.append(f"{name} must be >= {minimum}")

        if maximum is not None and value > maximum:
            errors.append(f"{name} must be <= {maximum}")

        if exclusive_minimum is not None and value <= exclusive_minimum:
            errors.append(f"{name} must be > {exclusive_minimum}")

        if exclusive_maximum is not None and value >= exclusive_maximum:
            errors.append(f"{name} must be < {exclusive_maximum}")

        # Multiple of constraint
        multiple_of = schema.get("multipleOf")
        if multiple_of is not None and value % multiple_of != 0:
            errors.append(f"{name} must be a multiple of {multiple_of}")

        return errors

    def _validate_integer(
        self, name: str, value: Any, schema: Dict[str, Any]
    ) -> List[str]:
        """Validate integer parameter."""
        errors = []

        if not isinstance(value, int) or isinstance(value, bool):
            errors.append(f"{name} must be an integer")
            return errors

        # Use number validation for range constraints
        number_errors = self._validate_number(name, value, schema)
        errors.extend(number_errors)

        return errors

    def _validate_boolean(
        self, name: str, value: Any, schema: Dict[str, Any]
    ) -> List[str]:
        """Validate boolean parameter."""
        errors = []

        if not isinstance(value, bool):
            errors.append(f"{name} must be a boolean")

        return errors

    def _validate_object(
        self, name: str, value: Any, schema: Dict[str, Any]
    ) -> List[str]:
        """Validate object parameter."""
        errors = []

        if not isinstance(value, dict):
            errors.append(f"{name} must be an object")
            return errors

        # Validate object properties if schema provided
        properties = schema.get("properties")
        if properties:
            for prop_name, prop_value in value.items():
                if prop_name in properties:
                    prop_schema = properties[prop_name]
                    prop_errors = self._validate_parameter(
                        f"{name}.{prop_name}", prop_value, prop_schema
                    )
                    errors.extend(prop_errors)

        # Additional properties validation
        additional_properties = schema.get("additionalProperties", True)
        if not additional_properties and properties:
            for prop_name in value:
                if prop_name not in properties:
                    errors.append(f"{name} contains unexpected property: {prop_name}")

        return errors

    def _validate_array(
        self, name: str, value: Any, schema: Dict[str, Any]
    ) -> List[str]:
        """Validate array parameter."""
        errors = []

        if not isinstance(value, list):
            errors.append(f"{name} must be an array")
            return errors

        # Length constraints
        min_items = schema.get("minItems")
        max_items = schema.get("maxItems")

        if min_items is not None and len(value) < min_items:
            errors.append(f"{name} must have at least {min_items} items")

        if max_items is not None and len(value) > max_items:
            errors.append(f"{name} must have at most {max_items} items")

        # Items validation
        items_schema = schema.get("items")
        if items_schema:
            for i, item in enumerate(value):
                item_errors = self._validate_parameter(
                    f"{name}[{i}]", item, items_schema
                )
                errors.extend(item_errors)

        # Unique items constraint
        unique_items = schema.get("uniqueItems", False)
        if unique_items:
            # Convert to JSON strings for comparison to handle complex types
            json_items = []
            for item in value:
                try:
                    json_items.append(json.dumps(item, sort_keys=True))
                except (TypeError, ValueError):
                    json_items.append(str(item))

            if len(set(json_items)) != len(json_items):
                errors.append(f"{name} must contain unique items")

        return errors

    def _validate_string_format(
        self, name: str, value: str, format_type: str
    ) -> List[str]:
        """Validate string format constraints."""
        errors = []

        format_validators = {
            "email": self._validate_email,
            "uri": self._validate_uri,
            "date": self._validate_date,
            "datetime": self._validate_datetime,
            "ipv4": self._validate_ipv4,
            "ipv6": self._validate_ipv6,
        }

        validator = format_validators.get(format_type)
        if validator:
            if not validator(value):
                errors.append(f"{name} is not a valid {format_type}")
        else:
            logger.warning("Unknown string format", format=format_type, parameter=name)

        return errors

    def _validate_email(self, value: str) -> bool:
        """Validate email format."""
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(email_pattern, value))

    def _validate_uri(self, value: str) -> bool:
        """Validate URI format."""
        uri_pattern = r"^https?://.+"
        return bool(re.match(uri_pattern, value))

    def _validate_date(self, value: str) -> bool:
        """Validate date format (YYYY-MM-DD)."""
        try:
            datetime.strptime(value, "%Y-%m-%d")
            return True
        except ValueError:
            return False

    def _validate_datetime(self, value: str) -> bool:
        """Validate datetime format (ISO 8601)."""
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
            return True
        except ValueError:
            return False

    def _validate_ipv4(self, value: str) -> bool:
        """Validate IPv4 address format."""
        ipv4_pattern = r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
        return bool(re.match(ipv4_pattern, value))

    def _validate_ipv6(self, value: str) -> bool:
        """Validate IPv6 address format."""
        try:
            import ipaddress

            ipaddress.IPv6Address(value)
            return True
        except ValueError:
            return False


class SecurityValidator:
    """
    Validates tool calls for security constraints and potential threats.

    Provides security validation to prevent dangerous operations and
    protect against malicious tool usage.
    """

    def __init__(self):
        """Initialize security validator."""
        self.dangerous_patterns = [
            # SQL injection patterns
            r"\b(union\s+select|drop\s+table|delete\s+from|insert\s+into|update\s+set)\b",
            # Command injection patterns
            r"[;&|`$(){}[\]\\]",
            # Path traversal patterns
            r"\.\./|\.\.\\",
            # Script injection patterns
            r"<script\b|javascript:|data:text/html",
        ]

        self.max_string_length = 10000
        self.max_array_length = 1000
        self.max_object_depth = 10

    async def validate_tool_call(
        self, tool_name: str, arguments: Dict[str, Any], user_id: Optional[str] = None
    ) -> None:
        """
        Validate tool call for security issues.

        Args:
            tool_name: Name of the tool being called
            arguments: Tool arguments to validate
            user_id: Optional user identifier

        Raises:
            SecurityError: If security validation fails
        """
        try:
            # Validate tool name
            self._validate_tool_name(tool_name)

            # Validate arguments structure
            self._validate_arguments_structure(arguments)

            # Check for dangerous patterns
            self._check_dangerous_patterns(arguments)

            # Validate argument sizes
            self._validate_argument_sizes(arguments)

            logger.debug(
                "Security validation passed",
                tool_name=tool_name,
                user_id=user_id,
                argument_count=len(arguments),
            )

        except SecurityError:
            raise
        except Exception as e:
            logger.error("Security validation error", tool_name=tool_name, error=str(e))
            raise SecurityError(f"Security validation failed: {str(e)}")

    def _validate_tool_name(self, tool_name: str) -> None:
        """Validate tool name for security issues."""
        if not tool_name or not isinstance(tool_name, str):
            raise SecurityError("Invalid tool name")

        # Check for dangerous characters
        if re.search(r"[<>;&|`$(){}[\]\\]", tool_name):
            raise SecurityError("Tool name contains dangerous characters")

        # Check length
        if len(tool_name) > 100:
            raise SecurityError("Tool name too long")

        # Validate naming convention
        if not re.match(r"^[A-Za-z][A-Za-z0-9_.]*$", tool_name):
            raise SecurityError("Tool name does not follow naming convention")

    def _validate_arguments_structure(self, arguments: Dict[str, Any]) -> None:
        """Validate arguments structure for security."""
        if not isinstance(arguments, dict):
            raise SecurityError("Arguments must be a dictionary")

        # Check argument count
        if len(arguments) > 50:
            raise SecurityError("Too many arguments provided")

        # Validate argument names
        for arg_name in arguments.keys():
            if not isinstance(arg_name, str):
                raise SecurityError("Argument names must be strings")

            if len(arg_name) > 100:
                raise SecurityError(f"Argument name too long: {arg_name}")

            if re.search(r"[<>;&|`$(){}[\]\\]", arg_name):
                raise SecurityError(
                    f"Argument name contains dangerous characters: {arg_name}"
                )

    def _check_dangerous_patterns(
        self, arguments: Dict[str, Any], depth: int = 0
    ) -> None:
        """Check for dangerous patterns in arguments."""
        if depth > self.max_object_depth:
            raise SecurityError("Argument structure too deep")

        for key, value in arguments.items():
            if isinstance(value, str):
                # Check string for dangerous patterns
                for pattern in self.dangerous_patterns:
                    if re.search(pattern, value, re.IGNORECASE):
                        logger.warning(
                            "Dangerous pattern detected",
                            pattern=pattern,
                            argument=key,
                            value=value[:100],
                        )
                        raise SecurityError(
                            f"Dangerous pattern detected in argument: {key}"
                        )

            elif isinstance(value, dict):
                # Recursively check nested objects
                self._check_dangerous_patterns(value, depth + 1)

            elif isinstance(value, list):
                # Check array elements
                for item in value:
                    if isinstance(item, (dict, list)):
                        self._check_dangerous_patterns({"item": item}, depth + 1)
                    elif isinstance(item, str):
                        for pattern in self.dangerous_patterns:
                            if re.search(pattern, item, re.IGNORECASE):
                                raise SecurityError(
                                    f"Dangerous pattern detected in array argument: {key}"
                                )

    def _validate_argument_sizes(self, arguments: Dict[str, Any]) -> None:
        """Validate argument sizes to prevent DoS attacks."""

        def check_size(obj, current_depth=0):
            if current_depth > self.max_object_depth:
                raise SecurityError("Argument structure too deep")

            if isinstance(obj, str):
                if len(obj) > self.max_string_length:
                    raise SecurityError(
                        f"String argument too long: {len(obj)} characters"
                    )

            elif isinstance(obj, list):
                if len(obj) > self.max_array_length:
                    raise SecurityError(f"Array argument too long: {len(obj)} items")

                for item in obj:
                    check_size(item, current_depth + 1)

            elif isinstance(obj, dict):
                if len(obj) > 100:
                    raise SecurityError(f"Object has too many properties: {len(obj)}")

                for value in obj.values():
                    check_size(value, current_depth + 1)

        for arg_name, arg_value in arguments.items():
            try:
                check_size(arg_value)
            except SecurityError as e:
                raise SecurityError(
                    f"Size validation failed for argument '{arg_name}': {str(e)}"
                )
