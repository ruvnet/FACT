"""
MCP Transport Layer

Handles communication transport for MCP server including stdio and HTTP.
Implements JSON-RPC 2.0 over various transport mechanisms.
"""

import asyncio
import sys
import json
from typing import Optional, Callable, Dict, Any
from abc import ABC, abstractmethod
import structlog

from .protocol import MCPProtocolHandler, MCPResponse, parse_message, format_response

logger = structlog.get_logger(__name__)


class TransportError(Exception):
    """Transport-related errors."""
    pass


class MCPTransport(ABC):
    """Abstract base class for MCP transport implementations."""
    
    def __init__(self, protocol_handler: MCPProtocolHandler):
        """
        Initialize transport with protocol handler.
        
        Args:
            protocol_handler: MCP protocol handler instance
        """
        self.protocol_handler = protocol_handler
        self.running = False
        
    @abstractmethod
    async def start(self):
        """Start the transport server."""
        pass
    
    @abstractmethod
    async def stop(self):
        """Stop the transport server."""
        pass
    
    @abstractmethod
    async def send_message(self, message: str):
        """Send message through transport."""
        pass


class StdioTransport(MCPTransport):
    """
    STDIO transport for MCP server.
    
    Reads from stdin and writes to stdout, following MCP stdio specification.
    Each message is a single line of JSON terminated by newline.
    """
    
    def __init__(self, protocol_handler: MCPProtocolHandler):
        """Initialize stdio transport."""
        super().__init__(protocol_handler)
        self.stdin_reader: Optional[asyncio.StreamReader] = None
        self.stdout_writer: Optional[asyncio.StreamWriter] = None
        self._read_task: Optional[asyncio.Task] = None
        
        logger.info("STDIO transport initialized")
    
    async def start(self):
        """Start STDIO transport server."""
        if self.running:
            logger.warning("STDIO transport already running")
            return
        
        try:
            # Create stdin/stdout streams
            self.stdin_reader = asyncio.StreamReader()
            stdin_protocol = asyncio.StreamReaderProtocol(self.stdin_reader)
            
            loop = asyncio.get_event_loop()
            await loop.connect_read_pipe(lambda: stdin_protocol, sys.stdin)
            
            # For stdout, we'll write directly to sys.stdout
            transport, protocol = await loop.connect_write_pipe(
                asyncio.streams.FlowControlMixin, sys.stdout
            )
            self.stdout_writer = asyncio.StreamWriter(transport, protocol, None, loop)
            
            self.running = True
            
            # Start reading messages
            self._read_task = asyncio.create_task(self._read_messages())
            
            logger.info("STDIO transport started successfully")
            
        except Exception as e:
            logger.error("Failed to start STDIO transport", error=str(e))
            raise TransportError(f"Failed to start STDIO transport: {e}")
    
    async def stop(self):
        """Stop STDIO transport."""
        if not self.running:
            return
        
        self.running = False
        
        # Cancel read task
        if self._read_task:
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass
        
        # Close streams
        if self.stdout_writer:
            self.stdout_writer.close()
            try:
                await self.stdout_writer.wait_closed()
            except Exception:
                pass
        
        logger.info("STDIO transport stopped")
    
    async def send_message(self, message: str):
        """
        Send message via stdout.
        
        Args:
            message: JSON message string
        """
        if not self.running or not self.stdout_writer:
            raise TransportError("STDIO transport not running")
        
        try:
            # Write message + newline
            message_bytes = (message + "\n").encode('utf-8')
            self.stdout_writer.write(message_bytes)
            await self.stdout_writer.drain()
            
            logger.debug("Message sent via STDIO", message_length=len(message))
            
        except Exception as e:
            logger.error("Failed to send message via STDIO", error=str(e))
            raise TransportError(f"Failed to send STDIO message: {e}")
    
    async def _read_messages(self):
        """Read and process messages from stdin."""
        logger.info("Starting STDIO message reading loop")
        
        try:
            while self.running and self.stdin_reader:
                try:
                    # Read line from stdin
                    line_bytes = await self.stdin_reader.readline()
                    
                    if not line_bytes:
                        # EOF reached
                        logger.info("EOF reached on stdin")
                        break
                    
                    line = line_bytes.decode('utf-8').strip()
                    
                    if not line:
                        continue
                    
                    logger.debug("Received STDIO message", message_length=len(line))
                    
                    # Process message
                    await self._process_message(line)
                    
                except asyncio.CancelledError:
                    logger.info("STDIO read loop cancelled")
                    break
                except Exception as e:
                    logger.error("Error reading STDIO message", error=str(e))
                    # Continue reading despite errors
                    
        except Exception as e:
            logger.error("STDIO read loop failed", error=str(e))
        finally:
            logger.info("STDIO message reading loop ended")
    
    async def _process_message(self, raw_message: str):
        """
        Process incoming message and send response if needed.
        
        Args:
            raw_message: Raw JSON message string
        """
        try:
            # Parse message
            message_data = parse_message(raw_message)
            
            # Handle via protocol handler
            response = await self.protocol_handler.handle_message(message_data)
            
            # Send response if this was a request (not notification)
            if response:
                response_json = format_response(response)
                await self.send_message(response_json)
                
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON received", error=str(e))
            
            # Send parse error response if we can determine request ID
            error_response = MCPResponse(
                id=None,
                error={
                    "code": -32700,
                    "message": "Parse error",
                    "data": {"original_error": str(e)}
                }
            )
            
            try:
                await self.send_message(format_response(error_response))
            except Exception:
                logger.error("Failed to send parse error response")
                
        except Exception as e:
            logger.error("Message processing failed", error=str(e))
            
            # Send internal error response
            error_response = MCPResponse(
                id=None,
                error={
                    "code": -32603,
                    "message": "Internal error",
                    "data": {"error": str(e)}
                }
            )
            
            try:
                await self.send_message(format_response(error_response))
            except Exception:
                logger.error("Failed to send internal error response")


class JSONRPCTransport(MCPTransport):
    """
    HTTP-based JSON-RPC transport for MCP server.
    
    Provides HTTP endpoint for MCP communication as alternative to stdio.
    """
    
    def __init__(self, 
                 protocol_handler: MCPProtocolHandler,
                 host: str = "localhost",
                 port: int = 8080):
        """
        Initialize HTTP transport.
        
        Args:
            protocol_handler: MCP protocol handler
            host: Server host address
            port: Server port number
        """
        super().__init__(protocol_handler)
        self.host = host
        self.port = port
        self.server: Optional[asyncio.Server] = None
        
        logger.info("HTTP JSON-RPC transport initialized", 
                   host=host, port=port)
    
    async def start(self):
        """Start HTTP server."""
        if self.running:
            logger.warning("HTTP transport already running")
            return
        
        try:
            # Create HTTP server
            self.server = await asyncio.start_server(
                self._handle_connection,
                self.host,
                self.port
            )
            
            self.running = True
            
            logger.info("HTTP JSON-RPC server started",
                       host=self.host, port=self.port)
            
        except Exception as e:
            logger.error("Failed to start HTTP server", error=str(e))
            raise TransportError(f"Failed to start HTTP server: {e}")
    
    async def stop(self):
        """Stop HTTP server."""
        if not self.running:
            return
        
        self.running = False
        
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        logger.info("HTTP JSON-RPC server stopped")
    
    async def send_message(self, message: str):
        """
        Send message via HTTP response.
        Note: This is handled per-connection in HTTP mode.
        """
        # In HTTP mode, responses are sent directly in connection handler
        pass
    
    async def _handle_connection(self, 
                               reader: asyncio.StreamReader, 
                               writer: asyncio.StreamWriter):
        """
        Handle incoming HTTP connection.
        
        Args:
            reader: Stream reader for incoming data
            writer: Stream writer for responses
        """
        client_addr = writer.get_extra_info('peername')
        logger.debug("HTTP connection established", client=client_addr)
        
        try:
            # Read HTTP request
            request_data = await self._read_http_request(reader)
            
            if not request_data:
                await self._send_http_error(writer, 400, "Bad Request")
                return
            
            # Extract JSON-RPC payload
            content_length = request_data.get('content_length', 0)
            if content_length > 0:
                json_payload = await reader.read(content_length)
                json_message = json_payload.decode('utf-8')
                
                # Process JSON-RPC message
                message_data = parse_message(json_message)
                response = await self.protocol_handler.handle_message(message_data)
                
                if response:
                    response_json = format_response(response)
                    await self._send_http_response(writer, response_json)
                else:
                    # Notification - send empty response
                    await self._send_http_response(writer, '{"result": "ok"}')
            else:
                await self._send_http_error(writer, 400, "Missing JSON payload")
                
        except Exception as e:
            logger.error("HTTP connection error", error=str(e), client=client_addr)
            await self._send_http_error(writer, 500, "Internal Server Error")
        finally:
            writer.close()
            await writer.wait_closed()
            logger.debug("HTTP connection closed", client=client_addr)
    
    async def _read_http_request(self, reader: asyncio.StreamReader) -> Optional[Dict[str, Any]]:
        """Read and parse HTTP request headers."""
        try:
            request_line = await reader.readline()
            if not request_line:
                return None
            
            # Parse request line
            request_parts = request_line.decode('utf-8').strip().split()
            if len(request_parts) != 3 or request_parts[0] != 'POST':
                return None
            
            headers = {}
            content_length = 0
            
            # Read headers
            while True:
                header_line = await reader.readline()
                if not header_line or header_line == b'\r\n':
                    break
                
                header = header_line.decode('utf-8').strip()
                if ':' in header:
                    key, value = header.split(':', 1)
                    headers[key.strip().lower()] = value.strip()
            
            # Extract content length
            if 'content-length' in headers:
                content_length = int(headers['content-length'])
            
            return {
                'method': request_parts[0],
                'path': request_parts[1],
                'headers': headers,
                'content_length': content_length
            }
            
        except Exception as e:
            logger.error("Failed to parse HTTP request", error=str(e))
            return None
    
    async def _send_http_response(self, writer: asyncio.StreamWriter, json_content: str):
        """Send HTTP response with JSON content."""
        response_body = json_content.encode('utf-8')
        
        response_headers = [
            "HTTP/1.1 200 OK",
            "Content-Type: application/json",
            f"Content-Length: {len(response_body)}",
            "Connection: close",
            "",
            ""
        ]
        
        response = "\r\n".join(response_headers).encode('utf-8') + response_body
        
        writer.write(response)
        await writer.drain()
    
    async def _send_http_error(self, writer: asyncio.StreamWriter, status_code: int, message: str):
        """Send HTTP error response."""
        response_body = f'{{"error": "{message}"}}'.encode('utf-8')
        
        response_headers = [
            f"HTTP/1.1 {status_code} {message}",
            "Content-Type: application/json",
            f"Content-Length: {len(response_body)}",
            "Connection: close",
            "",
            ""
        ]
        
        response = "\r\n".join(response_headers).encode('utf-8') + response_body
        
        writer.write(response)
        await writer.drain()


# Transport factory functions

def create_stdio_transport(protocol_handler: MCPProtocolHandler) -> StdioTransport:
    """
    Create STDIO transport instance.
    
    Args:
        protocol_handler: MCP protocol handler
        
    Returns:
        Configured STDIO transport
    """
    return StdioTransport(protocol_handler)


def create_http_transport(protocol_handler: MCPProtocolHandler,
                         host: str = "localhost",
                         port: int = 8080) -> JSONRPCTransport:
    """
    Create HTTP JSON-RPC transport instance.
    
    Args:
        protocol_handler: MCP protocol handler
        host: Server host address
        port: Server port number
        
    Returns:
        Configured HTTP transport
    """
    return JSONRPCTransport(protocol_handler, host, port)