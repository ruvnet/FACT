"""
FACT System Input Sanitization

This module provides comprehensive input sanitization and validation
to prevent XSS, injection attacks, and other security vulnerabilities.
"""

import re
import html
import urllib.parse
from typing import Any, Dict, List, Optional, Union
import structlog

try:
    # Try relative imports first (when used as package)
    from ..core.errors import SecurityError, ValidationError
except ImportError:
    # Fall back to absolute imports (when run as script)
    import sys
    from pathlib import Path

    # Add src to path if not already there
    src_path = str(Path(__file__).parent.parent)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    from core.errors import SecurityError, ValidationError


logger = structlog.get_logger(__name__)


class InputSanitizer:
    """
    Comprehensive input sanitization for security protection.

    Provides sanitization against XSS, SQL injection, command injection,
    and other common attack vectors.
    """

    def __init__(self):
        """Initialize input sanitizer with security patterns."""

        # XSS prevention patterns
        self.xss_patterns = [
            r"<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>",
            r"javascript:",
            r"data:text/html",
            r"vbscript:",
            r"onload\s*=",
            r"onerror\s*=",
            r"onclick\s*=",
            r"onmouseover\s*=",
            r"<iframe\b",
            r"<object\b",
            r"<embed\b",
            r"<form\b",
        ]

        # SQL injection patterns
        self.sql_injection_patterns = [
            r"\bunion\s+select\b",
            r"\bor\s+1\s*=\s*1\b",
            r"\band\s+1\s*=\s*1\b",
            r"--\s*",
            r"/\*.*?\*/",
            r";\s*drop\s+table\b",
            r";\s*delete\s+from\b",
            r";\s*insert\s+into\b",
            r";\s*update\s+.*\s+set\b",
            r"\bexec\s*\(",
            r"\bexecute\s*\(",
            r"\bsp_\w+",
            r"\bxp_\w+",
            r"0x[0-9a-f]+",
        ]

        # Command injection patterns (more specific to avoid false positives)
        self.command_injection_patterns = [
            r";\s*(rm|del|cat|ls|dir|mkdir|rmdir|cp|mv|chmod|chown)\b",  # Specific dangerous commands after semicolon
            r"\|\s*(rm|del|cat|ls|dir|mkdir|rmdir|cp|mv|chmod|chown)\b",  # Pipe to dangerous commands
            r"`[^`]*`",  # Backticks for command execution
            r"\$\([^)]*\)",  # Command substitution
            r"&&\s*(rm|del|cat|ls|dir|mkdir|rmdir|cp|mv|chmod|chown)\b",  # AND command execution with dangerous commands
            r"\|\|\s*(rm|del|cat|ls|dir|mkdir|rmdir|cp|mv|chmod|chown)\b",  # OR command execution with dangerous commands
            r">\s*/(?:etc|bin|usr|var|sys|proc)\b",  # Redirect to system paths
            r"<\s*/(?:etc|bin|usr|var|sys|proc)\b",  # Input from system paths
            r"\\\\x[0-9a-f]{2}",  # Hex escape sequences
        ]

        # Path traversal patterns
        self.path_traversal_patterns = [
            r"\.\./+",
            r"\.\.\\+",
            r"%2e%2e%2f",
            r"%2e%2e%5c",
            r"..%2f",
            r"..%5c",
        ]

        # Maximum safe lengths
        self.max_lengths = {
            "string": 10000,
            "url": 2000,
            "email": 254,
            "username": 100,
            "password": 256,
            "filename": 255,
            "path": 4096,
        }

    def sanitize_string(
        self,
        value: str,
        max_length: Optional[int] = None,
        allow_html: bool = False,
        field_type: str = "string",
    ) -> str:
        """
        Sanitize string input for security.

        Args:
            value: Input string to sanitize
            max_length: Maximum allowed length
            allow_html: Whether to allow HTML content
            field_type: Type of field for specific validation

        Returns:
            Sanitized string

        Raises:
            SecurityError: If dangerous content is detected
            ValidationError: If validation fails
        """
        if not isinstance(value, str):
            raise ValidationError("Input must be a string")

        # Check length limits
        max_len = max_length or self.max_lengths.get(
            field_type, self.max_lengths["string"]
        )
        if len(value) > max_len:
            raise ValidationError(f"Input too long: {len(value)} > {max_len}")

        # Check for null bytes
        if "\x00" in value:
            raise SecurityError("Null bytes not allowed in input")

        # Check for control characters (except common whitespace)
        control_chars = re.findall(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", value)
        if control_chars:
            raise SecurityError("Control characters not allowed in input")

        # XSS protection
        if not allow_html:
            self._check_xss_patterns(value)
            # HTML encode for safety
            value = html.escape(value, quote=True)

        # Check for injection patterns
        self._check_injection_patterns(value)

        # Field-specific sanitization
        if field_type == "url":
            value = self._sanitize_url(value)
        elif field_type == "email":
            value = self._sanitize_email(value)
        elif field_type == "filename":
            value = self._sanitize_filename(value)
        elif field_type == "path":
            value = self._sanitize_path(value)

        logger.debug(
            "String sanitized successfully",
            field_type=field_type,
            original_length=len(value),
            allow_html=allow_html,
        )

        return value

    def sanitize_dict(
        self,
        data: Dict[str, Any],
        field_rules: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Sanitize dictionary data recursively.

        Args:
            data: Dictionary to sanitize
            field_rules: Optional field-specific sanitization rules

        Returns:
            Sanitized dictionary
        """
        if not isinstance(data, dict):
            raise ValidationError("Input must be a dictionary")

        sanitized = {}
        field_rules = field_rules or {}

        for key, value in data.items():
            # Sanitize key
            sanitized_key = self._sanitize_dict_key(key)

            # Get field rules
            rules = field_rules.get(key, {})

            # Sanitize value based on type
            if isinstance(value, str):
                sanitized_value = self.sanitize_string(
                    value,
                    max_length=rules.get("max_length"),
                    allow_html=rules.get("allow_html", False),
                    field_type=rules.get("type", "string"),
                )
            elif isinstance(value, dict):
                nested_rules = rules.get("nested_rules", {})
                sanitized_value = self.sanitize_dict(value, nested_rules)
            elif isinstance(value, list):
                sanitized_value = self.sanitize_list(value, rules.get("item_rules", {}))
            else:
                # For other types (int, float, bool), validate but don't modify
                sanitized_value = self._validate_primitive(value, rules)

            sanitized[sanitized_key] = sanitized_value

        return sanitized

    def sanitize_list(
        self, data: List[Any], item_rules: Optional[Dict[str, Any]] = None
    ) -> List[Any]:
        """
        Sanitize list data.

        Args:
            data: List to sanitize
            item_rules: Rules for list items

        Returns:
            Sanitized list
        """
        if not isinstance(data, list):
            raise ValidationError("Input must be a list")

        # Check list length
        max_items = item_rules.get("max_items", 1000) if item_rules else 1000
        if len(data) > max_items:
            raise ValidationError(f"List too long: {len(data)} > {max_items}")

        sanitized = []
        item_rules = item_rules or {}

        for item in data:
            if isinstance(item, str):
                sanitized_item = self.sanitize_string(
                    item,
                    max_length=item_rules.get("max_length"),
                    allow_html=item_rules.get("allow_html", False),
                    field_type=item_rules.get("type", "string"),
                )
            elif isinstance(item, dict):
                nested_rules = item_rules.get("nested_rules", {})
                sanitized_item = self.sanitize_dict(item, nested_rules)
            elif isinstance(item, list):
                sanitized_item = self.sanitize_list(
                    item, item_rules.get("item_rules", {})
                )
            else:
                sanitized_item = self._validate_primitive(item, item_rules)

            sanitized.append(sanitized_item)

        return sanitized

    def _check_xss_patterns(self, value: str) -> None:
        """Check for XSS attack patterns."""
        value_lower = value.lower()

        for pattern in self.xss_patterns:
            if re.search(pattern, value_lower, re.IGNORECASE | re.DOTALL):
                raise SecurityError(f"Potential XSS attack detected")

    def _check_injection_patterns(self, value: str) -> None:
        """Check for various injection attack patterns."""
        value_lower = value.lower()

        # SQL injection check
        for pattern in self.sql_injection_patterns:
            if re.search(pattern, value_lower, re.IGNORECASE):
                raise SecurityError("Potential SQL injection detected")

        # Command injection check
        for pattern in self.command_injection_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                raise SecurityError("Potential command injection detected")

        # Path traversal check
        for pattern in self.path_traversal_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                raise SecurityError("Potential path traversal attack detected")

    def _sanitize_url(self, url: str) -> str:
        """Sanitize URL input."""
        # Parse URL to validate structure
        try:
            parsed = urllib.parse.urlparse(url)
        except Exception:
            raise ValidationError("Invalid URL format")

        # Check scheme
        if parsed.scheme not in ["http", "https"]:
            raise SecurityError("Only HTTP and HTTPS URLs allowed")

        # Check for dangerous characters
        dangerous_chars = ["<", ">", '"', "'", "&", "\x00"]
        for char in dangerous_chars:
            if char in url:
                raise SecurityError(f"Dangerous character in URL: {char}")

        return url

    def _sanitize_email(self, email: str) -> str:
        """Sanitize email input."""
        # Basic email format validation
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, email):
            raise ValidationError("Invalid email format")

        return email.lower().strip()

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename input."""
        # Remove path separators and dangerous characters
        dangerous_chars = ["/", "\\", ":", "*", "?", '"', "<", ">", "|", "\x00"]
        for char in dangerous_chars:
            if char in filename:
                raise SecurityError(f"Dangerous character in filename: {char}")

        # Check for reserved names (Windows)
        reserved_names = {
            "CON",
            "PRN",
            "AUX",
            "NUL",
            "COM1",
            "COM2",
            "COM3",
            "COM4",
            "COM5",
            "COM6",
            "COM7",
            "COM8",
            "COM9",
            "LPT1",
            "LPT2",
            "LPT3",
            "LPT4",
            "LPT5",
            "LPT6",
            "LPT7",
            "LPT8",
            "LPT9",
        }

        name_upper = filename.upper()
        if name_upper in reserved_names or name_upper.split(".")[0] in reserved_names:
            raise SecurityError("Reserved filename not allowed")

        return filename.strip()

    def _sanitize_path(self, path: str) -> str:
        """Sanitize file path input."""
        # Check for path traversal
        if ".." in path:
            raise SecurityError("Path traversal not allowed")

        # Check for absolute paths
        if path.startswith("/") or (len(path) > 1 and path[1] == ":"):
            raise SecurityError("Absolute paths not allowed")

        return path

    def _sanitize_dict_key(self, key: str) -> str:
        """Sanitize dictionary key."""
        if not isinstance(key, str):
            raise ValidationError("Dictionary keys must be strings")

        if len(key) > 100:
            raise ValidationError("Dictionary key too long")

        # Allow only alphanumeric characters, underscores, and hyphens
        if not re.match(r"^[a-zA-Z0-9_-]+$", key):
            raise SecurityError("Invalid characters in dictionary key")

        return key

    def _validate_primitive(self, value: Any, rules: Dict[str, Any]) -> Any:
        """Validate primitive values (int, float, bool)."""
        if isinstance(value, (int, float)):
            min_val = rules.get("min_value")
            max_val = rules.get("max_value")

            if min_val is not None and value < min_val:
                raise ValidationError(f"Value too small: {value} < {min_val}")

            if max_val is not None and value > max_val:
                raise ValidationError(f"Value too large: {value} > {max_val}")

        elif isinstance(value, bool):
            # Boolean values are safe as-is
            pass

        else:
            # For other types, convert to string and validate
            str_value = str(value)
            if len(str_value) > 1000:
                raise ValidationError("Value representation too long")

        return value


def create_input_sanitizer() -> InputSanitizer:
    """
    Create a configured input sanitizer instance.

    Returns:
        InputSanitizer instance
    """
    return InputSanitizer()


# Global sanitizer instance
_sanitizer_instance: Optional[InputSanitizer] = None


def get_sanitizer() -> InputSanitizer:
    """Get global sanitizer instance."""
    global _sanitizer_instance

    if _sanitizer_instance is None:
        _sanitizer_instance = create_input_sanitizer()

    return _sanitizer_instance


def sanitize_input(value: Any, **kwargs) -> Any:
    """
    Convenience function to sanitize input.

    Args:
        value: Value to sanitize
        **kwargs: Sanitization options

    Returns:
        Sanitized value
    """
    sanitizer = get_sanitizer()

    if isinstance(value, str):
        return sanitizer.sanitize_string(value, **kwargs)
    elif isinstance(value, dict):
        return sanitizer.sanitize_dict(value, kwargs.get("field_rules"))
    elif isinstance(value, list):
        return sanitizer.sanitize_list(value, kwargs.get("item_rules"))
    else:
        return sanitizer._validate_primitive(value, kwargs)
