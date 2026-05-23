"""
FACT System Tool Management

This package provides tool registration, execution, and management
functionality for the FACT system.
"""

# Use try/except to handle both relative and absolute imports
try:
    from .decorators import Tool, get_tool_registry, ToolDefinition, ToolRegistry
    from .executor import (
        ToolExecutor,
        ToolCall,
        ToolResult,
        create_tool_call,
        format_tool_result_for_llm,
    )
    from .validation import ParameterValidator, SecurityValidator
except ImportError:
    # Fallback to absolute imports when called from scripts
    from tools.decorators import Tool, get_tool_registry, ToolDefinition, ToolRegistry
    from tools.executor import (
        ToolExecutor,
        ToolCall,
        ToolResult,
        create_tool_call,
        format_tool_result_for_llm,
    )
    from tools.validation import ParameterValidator, SecurityValidator

__all__ = [
    "Tool",
    "get_tool_registry",
    "ToolDefinition",
    "ToolRegistry",
    "ToolExecutor",
    "ToolCall",
    "ToolResult",
    "create_tool_call",
    "format_tool_result_for_llm",
    "ParameterValidator",
    "SecurityValidator",
]
