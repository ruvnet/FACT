"""
MCP Protocol Implementation

JSON-RPC 2.0 based protocol for Model Context Protocol communication.
Handles message serialization, validation, and transport.
"""

import json
import uuid
from typing import Dict, Any, Optional, Union, List
from dataclasses import dataclass, asdict
from enum import Enum
import structlog

logger = structlog.get_logger(__name__)


class MCPErrorCode(Enum):
    """MCP-specific error codes based on JSON-RPC 2.0 specification."""
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    
    # MCP-specific error codes
    TOOL_NOT_FOUND = -32001
    TOOL_EXECUTION_ERROR = -32002
    RESOURCE_NOT_FOUND = -32003
    UNAUTHORIZED = -32004
    RATE_LIMITED = -32005


@dataclass
class MCPError:
    """MCP error object following JSON-RPC 2.0 error format."""
    code: int
    message: str
    data: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        error_dict = {
            "code": self.code,
            "message": self.message
        }
        if self.data:
            error_dict["data"] = self.data
        return error_dict


@dataclass
class MCPMessage:
    """Base MCP message with JSON-RPC 2.0 structure."""
    jsonrpc: str = "2.0"
    id: Optional[Union[str, int]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MCPMessage':
        """Create instance from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})


@dataclass
class MCPRequest(MCPMessage):
    """MCP request message."""
    method: str
    params: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.id is None:
            self.id = str(uuid.uuid4())


@dataclass
class MCPResponse(MCPMessage):
    """MCP response message."""
    result: Optional[Dict[str, Any]] = None
    error: Optional[MCPError] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format with proper error handling."""
        response_dict = {
            "jsonrpc": self.jsonrpc,
            "id": self.id
        }
        
        if self.error:
            response_dict["error"] = self.error.to_dict()
        else:
            response_dict["result"] = self.result or {}
            
        return response_dict


@dataclass 
class MCPNotification(MCPMessage):
    """MCP notification message (no response expected)."""
    method: str
    params: Optional[Dict[str, Any]] = None
    id: None = None  # Notifications never have IDs


class MCPProtocolHandler:
    """
    Handles MCP protocol message parsing, validation, and routing.
    """
    
    def __init__(self):
        """Initialize protocol handler."""
        self.methods: Dict[str, callable] = {}
        self.resources: Dict[str, callable] = {}
        self.prompts: Dict[str, callable] = {}
        
        # Register core MCP methods
        self._register_core_methods()
        
        logger.info("MCP Protocol Handler initialized")
    
    def _register_core_methods(self):
        """Register core MCP protocol methods."""
        self.methods.update({
            "initialize": self._handle_initialize,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
            "resources/list": self._handle_resources_list,
            "resources/read": self._handle_resources_read,
            "prompts/list": self._handle_prompts_list,
            "prompts/get": self._handle_prompts_get,
            "completion/complete": self._handle_completion,
            "logging/setLevel": self._handle_logging_set_level
        })
    
    def register_tool(self, name: str, handler: callable):
        """Register a tool handler."""
        self.methods[f"tools/{name}"] = handler
        logger.debug("Tool registered", tool_name=name)
    
    def register_resource(self, uri: str, handler: callable):
        """Register a resource handler."""
        self.resources[uri] = handler
        logger.debug("Resource registered", resource_uri=uri)
    
    def register_prompt(self, name: str, handler: callable):
        """Register a prompt handler."""
        self.prompts[name] = handler
        logger.debug("Prompt registered", prompt_name=name)
    
    async def handle_message(self, message_data: Dict[str, Any]) -> Optional[MCPResponse]:
        """
        Handle incoming MCP message and route to appropriate handler.
        
        Args:
            message_data: Raw message dictionary
            
        Returns:
            MCPResponse if request, None if notification
        """
        try:
            # Validate JSON-RPC 2.0 structure
            if not self._validate_message_structure(message_data):
                return self._create_error_response(
                    None,
                    MCPErrorCode.INVALID_REQUEST.value,
                    "Invalid JSON-RPC 2.0 message structure"
                )
            
            # Determine message type
            is_notification = "id" not in message_data
            method = message_data.get("method")
            
            if not method:
                return self._create_error_response(
                    message_data.get("id"),
                    MCPErrorCode.INVALID_REQUEST.value,
                    "Missing method field"
                )
            
            # Route to handler
            handler = self.methods.get(method)
            if not handler:
                if not is_notification:
                    return self._create_error_response(
                        message_data.get("id"),
                        MCPErrorCode.METHOD_NOT_FOUND.value,
                        f"Method '{method}' not found"
                    )
                return None
            
            # Execute handler
            try:
                params = message_data.get("params", {})
                result = await handler(params)
                
                if not is_notification:
                    return MCPResponse(
                        id=message_data.get("id"),
                        result=result
                    )
                    
            except Exception as e:
                logger.error("Handler execution failed", 
                           method=method, 
                           error=str(e))
                if not is_notification:
                    return self._create_error_response(
                        message_data.get("id"),
                        MCPErrorCode.INTERNAL_ERROR.value,
                        f"Handler execution failed: {str(e)}"
                    )
            
            return None
            
        except Exception as e:
            logger.error("Message handling failed", error=str(e))
            return self._create_error_response(
                message_data.get("id") if isinstance(message_data, dict) else None,
                MCPErrorCode.INTERNAL_ERROR.value,
                f"Internal error: {str(e)}"
            )
    
    def _validate_message_structure(self, data: Dict[str, Any]) -> bool:
        """Validate JSON-RPC 2.0 message structure."""
        if not isinstance(data, dict):
            return False
        
        # Check required fields
        if data.get("jsonrpc") != "2.0":
            return False
            
        if "method" not in data:
            return False
        
        # Validate id field (can be string, number, or null, but not missing for requests)
        if "id" in data:
            id_value = data["id"]
            if not isinstance(id_value, (str, int, type(None))):
                return False
        
        return True
    
    def _create_error_response(self, 
                             request_id: Optional[Union[str, int]], 
                             code: int, 
                             message: str,
                             data: Optional[Dict[str, Any]] = None) -> MCPResponse:
        """Create error response."""
        error = MCPError(code=code, message=message, data=data)
        return MCPResponse(id=request_id, error=error)
    
    # Core MCP method handlers
    
    async def _handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle initialize request."""
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {
                    "listChanged": True
                },
                "resources": {
                    "subscribe": True,
                    "listChanged": True
                },
                "prompts": {
                    "listChanged": True
                },
                "completion": {
                    "supports": ["tools", "resources"]
                },
                "logging": {}
            },
            "serverInfo": {
                "name": "FACT MCP Server",
                "version": "1.0.0",
                "description": "Model Context Protocol server for FACT system"
            }
        }
    
    async def _handle_tools_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/list request."""
        # This will be overridden by the main server
        return {"tools": []}
    
    async def _handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/call request."""
        # This will be overridden by the main server
        tool_name = params.get("name")
        if not tool_name:
            raise ValueError("Tool name is required")
        
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Tool '{tool_name}' execution not implemented"
                }
            ]
        }
    
    async def _handle_resources_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resources/list request."""
        return {
            "resources": [
                {
                    "uri": uri,
                    "name": uri.split("/")[-1],
                    "description": f"Resource: {uri}",
                    "mimeType": "application/json"
                }
                for uri in self.resources.keys()
            ]
        }
    
    async def _handle_resources_read(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resources/read request."""
        uri = params.get("uri")
        if not uri:
            raise ValueError("Resource URI is required")
        
        handler = self.resources.get(uri)
        if not handler:
            raise ValueError(f"Resource '{uri}' not found")
        
        content = await handler()
        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "application/json",
                    "text": json.dumps(content, indent=2)
                }
            ]
        }
    
    async def _handle_prompts_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle prompts/list request."""
        return {
            "prompts": [
                {
                    "name": name,
                    "description": f"Prompt: {name}"
                }
                for name in self.prompts.keys()
            ]
        }
    
    async def _handle_prompts_get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle prompts/get request."""
        name = params.get("name")
        if not name:
            raise ValueError("Prompt name is required")
        
        handler = self.prompts.get(name)
        if not handler:
            raise ValueError(f"Prompt '{name}' not found")
        
        prompt_data = await handler(params.get("arguments", {}))
        return {
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": prompt_data.get("text", "")
                    }
                }
            ]
        }
    
    async def _handle_completion(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle completion/complete request."""
        ref = params.get("ref")
        if not ref:
            raise ValueError("Completion reference is required")
        
        # Basic completion for tools and resources
        if ref.get("type") == "ref/tool":
            tool_names = [name.replace("tools/", "") for name in self.methods.keys() 
                         if name.startswith("tools/")]
            return {
                "completion": {
                    "values": tool_names,
                    "total": len(tool_names),
                    "hasMore": False
                }
            }
        elif ref.get("type") == "ref/resource":
            return {
                "completion": {
                    "values": list(self.resources.keys()),
                    "total": len(self.resources),
                    "hasMore": False
                }
            }
        
        return {
            "completion": {
                "values": [],
                "total": 0,
                "hasMore": False
            }
        }
    
    async def _handle_logging_set_level(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle logging/setLevel request."""
        level = params.get("level", "info")
        logger.info("Log level change requested", level=level)
        return {}


def parse_message(raw_message: str) -> Dict[str, Any]:
    """
    Parse raw JSON message into dictionary.
    
    Args:
        raw_message: Raw JSON string
        
    Returns:
        Parsed message dictionary
        
    Raises:
        json.JSONDecodeError: If message is invalid JSON
    """
    try:
        data = json.loads(raw_message)
        if not isinstance(data, dict):
            raise ValueError("Message must be a JSON object")
        return data
    except json.JSONDecodeError as e:
        logger.error("JSON parse error", error=str(e), message=raw_message[:100])
        raise


def format_response(response: MCPResponse) -> str:
    """
    Format MCP response as JSON string.
    
    Args:
        response: MCP response object
        
    Returns:
        JSON string representation
    """
    return response.to_json()