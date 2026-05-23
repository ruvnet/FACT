"""
FACT System File System Connector

This module provides secure file system operations with path validation
and access controls to prevent unauthorized file access.
"""

import os
import json
import time
from typing import Dict, Any, List, Optional
from pathlib import Path
import structlog

from tools.decorators import Tool
from ...core.errors import ToolExecutionError, SecurityError, ValidationError

logger = structlog.get_logger(__name__)


# Configuration for allowed directories
ALLOWED_BASE_PATHS = [
    "/workspace/data",
    "/workspace/docs",
    "/workspace/output",
    "./data",
    "./docs",
    "./output",
]

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_DIRECTORY_DEPTH = 10


@Tool(
    name="FileSystem.ReadFile",
    description="Read contents of a file within allowed directories with security validation",
    parameters={
        "file_path": {
            "type": "string",
            "description": "Path to file to read (relative to allowed directories)",
            "pattern": r"^[a-zA-Z0-9/._-]+$",
            "maxLength": 500,
        },
        "encoding": {
            "type": "string",
            "description": "File encoding",
            "enum": ["utf-8", "ascii", "latin-1", "utf-16"],
            "default": "utf-8",
        },
        "max_lines": {
            "type": "integer",
            "description": "Maximum number of lines to read (0 = all)",
            "default": 0,
            "minimum": 0,
            "maximum": 10000,
        },
    },
    requires_auth=False,
    timeout_seconds=30,
)
def read_file_tool(
    file_path: str, encoding: str = "utf-8", max_lines: int = 0
) -> Dict[str, Any]:
    """
    Read contents of a file with security validation.

    Args:
        file_path: Path to file to read
        encoding: File encoding
        max_lines: Maximum lines to read (0 = all)

    Returns:
        File content and metadata

    Raises:
        SecurityError: If file path is not allowed
        ToolExecutionError: If file operation fails
    """
    try:
        # Security validation
        validated_path = _validate_file_path_security(file_path, operation="read")

        # Check if file exists
        if not validated_path.exists():
            return {
                "success": False,
                "error": f"File does not exist: {file_path}",
                "file_path": file_path,
            }

        if not validated_path.is_file():
            return {
                "success": False,
                "error": f"Path is not a file: {file_path}",
                "file_path": file_path,
            }

        # Check file size
        file_size = validated_path.stat().st_size
        if file_size > MAX_FILE_SIZE:
            return {
                "success": False,
                "error": f"File too large: {file_size} bytes (max: {MAX_FILE_SIZE})",
                "file_path": file_path,
                "file_size": file_size,
            }

        # Read file content
        start_time = time.time()

        with open(validated_path, "r", encoding=encoding) as file:
            if max_lines > 0:
                lines = []
                for i, line in enumerate(file):
                    if i >= max_lines:
                        break
                    lines.append(line.rstrip("\n\r"))
                content = "\n".join(lines)
                truncated = True
            else:
                content = file.read()
                truncated = False

        read_time = (time.time() - start_time) * 1000

        # Get file metadata
        stat = validated_path.stat()

        result = {
            "success": True,
            "file_path": file_path,
            "content": content,
            "size_bytes": len(content.encode(encoding)),
            "original_size_bytes": file_size,
            "line_count": content.count("\n") + 1 if content else 0,
            "encoding": encoding,
            "truncated": truncated,
            "max_lines_applied": max_lines if max_lines > 0 else None,
            "last_modified": stat.st_mtime,
            "read_time_ms": read_time,
        }

        logger.info(
            "File read successfully",
            file_path=file_path,
            size_bytes=result["size_bytes"],
            read_time_ms=read_time,
        )

        return result

    except UnicodeDecodeError as e:
        logger.error(
            "File encoding error", file_path=file_path, encoding=encoding, error=str(e)
        )
        return {
            "success": False,
            "error": f"File encoding error: {str(e)}",
            "file_path": file_path,
            "encoding": encoding,
        }

    except Exception as e:
        logger.error("File read failed", file_path=file_path, error=str(e))
        return {
            "success": False,
            "error": f"Failed to read file: {str(e)}",
            "file_path": file_path,
        }


@Tool(
    name="FileSystem.ListDirectory",
    description="List contents of a directory within allowed paths with file metadata",
    parameters={
        "directory_path": {
            "type": "string",
            "description": "Path to directory to list",
            "pattern": r"^[a-zA-Z0-9/._-]*$",
            "maxLength": 500,
        },
        "include_hidden": {
            "type": "boolean",
            "description": "Include hidden files and directories",
            "default": False,
        },
        "recursive": {
            "type": "boolean",
            "description": "List subdirectories recursively",
            "default": False,
        },
        "file_types": {
            "type": "array",
            "description": "Filter by file extensions (e.g., ['.txt', '.json'])",
            "items": {"type": "string"},
            "default": [],
        },
    },
    requires_auth=False,
    timeout_seconds=30,
)
def list_directory_tool(
    directory_path: str = "",
    include_hidden: bool = False,
    recursive: bool = False,
    file_types: List[str] = None,
) -> Dict[str, Any]:
    """
    List contents of a directory with security validation.

    Args:
        directory_path: Path to directory to list
        include_hidden: Include hidden files
        recursive: List recursively
        file_types: Filter by file extensions

    Returns:
        Directory listing with metadata
    """
    try:
        # Security validation
        validated_path = _validate_directory_path_security(directory_path)

        if not validated_path.exists():
            return {
                "success": False,
                "error": f"Directory does not exist: {directory_path}",
                "directory_path": directory_path,
            }

        if not validated_path.is_dir():
            return {
                "success": False,
                "error": f"Path is not a directory: {directory_path}",
                "directory_path": directory_path,
            }

        # List directory contents
        start_time = time.time()
        entries = []

        if file_types is None:
            file_types = []

        # Normalize file extensions
        file_types = [
            ext.lower() if ext.startswith(".") else f".{ext.lower()}"
            for ext in file_types
        ]

        try:
            if recursive:
                for root, dirs, files in os.walk(validated_path):
                    # Skip hidden directories if not requested
                    if not include_hidden:
                        dirs[:] = [d for d in dirs if not d.startswith(".")]

                    root_path = Path(root)

                    # Process directories
                    for dir_name in dirs:
                        if not include_hidden and dir_name.startswith("."):
                            continue

                        dir_path = root_path / dir_name
                        relative_path = dir_path.relative_to(validated_path)

                        entry = _create_directory_entry(
                            dir_path, str(relative_path), "directory"
                        )
                        if entry:
                            entries.append(entry)

                    # Process files
                    for file_name in files:
                        if not include_hidden and file_name.startswith("."):
                            continue

                        file_path = root_path / file_name
                        relative_path = file_path.relative_to(validated_path)

                        # Filter by file types if specified
                        if file_types:
                            file_ext = file_path.suffix.lower()
                            if file_ext not in file_types:
                                continue

                        entry = _create_directory_entry(
                            file_path, str(relative_path), "file"
                        )
                        if entry:
                            entries.append(entry)
            else:
                # Non-recursive listing
                for item in validated_path.iterdir():
                    if not include_hidden and item.name.startswith("."):
                        continue

                    # Filter by file types if specified
                    if file_types and item.is_file():
                        file_ext = item.suffix.lower()
                        if file_ext not in file_types:
                            continue

                    entry_type = "directory" if item.is_dir() else "file"
                    entry = _create_directory_entry(item, item.name, entry_type)
                    if entry:
                        entries.append(entry)

        except PermissionError as e:
            return {
                "success": False,
                "error": f"Permission denied: {str(e)}",
                "directory_path": directory_path,
            }

        list_time = (time.time() - start_time) * 1000

        # Sort entries by type (directories first) then by name
        entries.sort(key=lambda x: (x["type"] != "directory", x["name"].lower()))

        # Calculate statistics
        file_count = sum(1 for entry in entries if entry["type"] == "file")
        dir_count = sum(1 for entry in entries if entry["type"] == "directory")
        total_size = sum(
            entry.get("size_bytes", 0) for entry in entries if entry["type"] == "file"
        )

        result = {
            "success": True,
            "directory_path": directory_path,
            "entries": entries,
            "total_count": len(entries),
            "file_count": file_count,
            "directory_count": dir_count,
            "total_size_bytes": total_size,
            "include_hidden": include_hidden,
            "recursive": recursive,
            "file_types_filter": file_types,
            "list_time_ms": list_time,
        }

        logger.info(
            "Directory listed successfully",
            directory_path=directory_path,
            entry_count=len(entries),
            list_time_ms=list_time,
        )

        return result

    except Exception as e:
        logger.error(
            "Directory listing failed", directory_path=directory_path, error=str(e)
        )
        return {
            "success": False,
            "error": f"Failed to list directory: {str(e)}",
            "directory_path": directory_path,
        }


@Tool(
    name="FileSystem.GetFileInfo",
    description="Get detailed metadata about a file or directory",
    parameters={
        "path": {
            "type": "string",
            "description": "Path to file or directory",
            "pattern": r"^[a-zA-Z0-9/._-]+$",
            "maxLength": 500,
        }
    },
    requires_auth=False,
    timeout_seconds=10,
)
def get_file_info_tool(path: str) -> Dict[str, Any]:
    """
    Get detailed metadata about a file or directory.

    Args:
        path: Path to file or directory

    Returns:
        File/directory metadata
    """
    try:
        # Security validation
        validated_path = _validate_file_path_security(path, operation="info")

        if not validated_path.exists():
            return {
                "success": False,
                "error": f"Path does not exist: {path}",
                "path": path,
            }

        # Get file/directory stats
        stat = validated_path.stat()

        result = {
            "success": True,
            "path": path,
            "name": validated_path.name,
            "type": "directory" if validated_path.is_dir() else "file",
            "size_bytes": stat.st_size,
            "created": stat.st_ctime,
            "modified": stat.st_mtime,
            "accessed": stat.st_atime,
            "permissions": oct(stat.st_mode)[-3:],
            "is_readable": os.access(validated_path, os.R_OK),
            "is_writable": os.access(validated_path, os.W_OK),
            "is_executable": os.access(validated_path, os.X_OK),
        }

        # Add file-specific metadata
        if validated_path.is_file():
            result["extension"] = validated_path.suffix
            result["stem"] = validated_path.stem

            # Try to detect file type
            if validated_path.suffix.lower() in [
                ".txt",
                ".md",
                ".py",
                ".js",
                ".json",
                ".xml",
                ".html",
                ".css",
            ]:
                result["file_category"] = "text"
            elif validated_path.suffix.lower() in [
                ".jpg",
                ".jpeg",
                ".png",
                ".gif",
                ".bmp",
                ".svg",
            ]:
                result["file_category"] = "image"
            elif validated_path.suffix.lower() in [
                ".pdf",
                ".doc",
                ".docx",
                ".xls",
                ".xlsx",
            ]:
                result["file_category"] = "document"
            else:
                result["file_category"] = "other"

        # Add directory-specific metadata
        elif validated_path.is_dir():
            try:
                # Count items in directory
                items = list(validated_path.iterdir())
                result["item_count"] = len(items)
                result["file_count"] = sum(1 for item in items if item.is_file())
                result["directory_count"] = sum(1 for item in items if item.is_dir())
            except PermissionError:
                result["item_count"] = None
                result["access_denied"] = True

        logger.debug(
            "File info retrieved successfully",
            path=path,
            type=result["type"],
            size_bytes=result["size_bytes"],
        )

        return result

    except Exception as e:
        logger.error("Failed to get file info", path=path, error=str(e))
        return {
            "success": False,
            "error": f"Failed to get file info: {str(e)}",
            "path": path,
        }


def _validate_file_path_security(file_path: str, operation: str = "read") -> Path:
    """
    Validate file path for security constraints.

    Args:
        file_path: File path to validate
        operation: Operation being performed

    Returns:
        Validated Path object

    Raises:
        SecurityError: If path is not allowed
    """
    try:
        # Normalize path
        if not file_path:
            file_path = "."

        path = Path(file_path).resolve()

        # Check for directory traversal attempts
        path_str = str(path)
        if ".." in file_path or "~" in file_path:
            raise SecurityError("Directory traversal not allowed")

        # Check against allowed base paths
        is_allowed = False
        for base_path in ALLOWED_BASE_PATHS:
            try:
                base = Path(base_path).resolve()
                if path.is_relative_to(base):
                    is_allowed = True
                    break
            except (ValueError, OSError):
                # Handle cases where base path doesn't exist or is invalid
                continue

        if not is_allowed:
            # For relative paths, check if they're within current working directory's allowed subdirectories
            cwd = Path.cwd()
            for allowed_subdir in ["data", "docs", "output"]:
                allowed_path = cwd / allowed_subdir
                try:
                    if path.is_relative_to(allowed_path):
                        is_allowed = True
                        break
                except ValueError:
                    continue

        if not is_allowed:
            raise SecurityError(
                f"File access not allowed outside permitted directories: {file_path}"
            )

        # Check for dangerous file extensions
        dangerous_extensions = [".exe", ".bat", ".sh", ".ps1", ".cmd", ".scr", ".msi"]
        if path.suffix.lower() in dangerous_extensions:
            raise SecurityError(
                f"Access to executable files not allowed: {path.suffix}"
            )

        # Check path depth to prevent excessive nesting
        try:
            parts = path.parts
            if len(parts) > MAX_DIRECTORY_DEPTH:
                raise SecurityError(
                    f"Path too deep: {len(parts)} levels (max: {MAX_DIRECTORY_DEPTH})"
                )
        except Exception:
            pass

        return path

    except SecurityError:
        raise
    except Exception as e:
        raise SecurityError(f"Path validation failed: {str(e)}")


def _validate_directory_path_security(directory_path: str) -> Path:
    """Validate directory path for security constraints."""
    return _validate_file_path_security(directory_path, operation="list")


def _create_directory_entry(
    path: Path, relative_path: str, entry_type: str
) -> Optional[Dict[str, Any]]:
    """
    Create directory entry with metadata.

    Args:
        path: Full path to the item
        relative_path: Relative path for display
        entry_type: Type of entry ("file" or "directory")

    Returns:
        Directory entry dictionary or None if error
    """
    try:
        stat = path.stat()

        entry = {
            "name": path.name,
            "path": relative_path,
            "type": entry_type,
            "modified": stat.st_mtime,
            "permissions": oct(stat.st_mode)[-3:],
        }

        if entry_type == "file":
            entry["size_bytes"] = stat.st_size
            entry["extension"] = path.suffix

        return entry

    except (OSError, PermissionError) as e:
        logger.warning("Failed to get entry metadata", path=str(path), error=str(e))
        return {
            "name": path.name,
            "path": relative_path,
            "type": entry_type,
            "error": "Access denied",
        }
