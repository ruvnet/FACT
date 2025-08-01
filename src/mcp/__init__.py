"""
FACT MCP Server Module

Model Context Protocol (MCP) server implementation for the FACT system.
Provides tools, resources, and prompts for AI assistants to interact with FACT.
"""

from .server import FACTMCPServer
from .transport import StdioTransport, JSONRPCTransport
from .tools import (
    FACTQueryTool,
    DatabaseQueryTool,
    SystemMetricsTool,
    CacheInspectorTool,
    ToolRegistryInspectorTool
)
from .resources import (
    ConfigurationResource,
    DatabaseSchemaResource,
    ToolSchemaResource,
    SystemStatusResource
)
from .protocol import MCPMessage, MCPRequest, MCPResponse, MCPNotification

__version__ = "1.0.0"
__all__ = [
    "FACTMCPServer",
    "StdioTransport",
    "JSONRPCTransport", 
    "FACTQueryTool",
    "DatabaseQueryTool",
    "SystemMetricsTool",
    "CacheInspectorTool",
    "ToolRegistryInspectorTool",
    "ConfigurationResource",
    "DatabaseSchemaResource",
    "ToolSchemaResource",
    "SystemStatusResource",
    "MCPMessage",
    "MCPRequest", 
    "MCPResponse",
    "MCPNotification"
]