#!/usr/bin/env python3
"""
FACT Hello World MCP Server

A basic FastMCP server implementation demonstrating:
- Simple "hello" tool
- "greet" tool with name parameter
- Server information resource
- Proper FastMCP patterns and structure

Based on FastMCP documentation patterns and FACT Memory research.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime

try:
    from fastmcp import FastMCP, Context
except ImportError:
    print("FastMCP not available. Install with: pip install fastmcp")
    import sys

    sys.exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP(
    name="FACT Hello World Server",
    instructions="""
    This is a Hello World demonstration server for the FACT Memory System.
    
    Available tools:
    - hello(): Returns a simple hello message
    - greet(name): Returns a personalized greeting with the provided name
    
    Available resources:
    - server_info: Provides information about this MCP server
    
    This server demonstrates FastMCP best practices and integration patterns.
    """,
)


@mcp.tool()
async def hello(ctx: Context = None) -> Dict[str, Any]:
    """
    Simple hello world tool that returns a greeting message.

    Args:
        ctx: FastMCP context for logging and resource access

    Returns:
        Dictionary containing a simple hello message and timestamp
    """
    if ctx:
        await ctx.info("Executing hello tool")

    result = {
        "message": "Hello from FACT Memory MCP Server!",
        "timestamp": datetime.now().isoformat(),
        "server": "FACT Hello World Server",
        "status": "active",
    }

    if ctx:
        await ctx.info("Hello tool executed successfully")

    return result


@mcp.tool()
async def greet(name: str, ctx: Context = None) -> Dict[str, Any]:
    """
    Personalized greeting tool that takes a name parameter.

    Args:
        name: The name to include in the greeting
        ctx: FastMCP context for logging and resource access

    Returns:
        Dictionary containing a personalized greeting message
    """
    if ctx:
        await ctx.info(f"Executing greet tool for name: {name}")

    # Validate input
    if not name or not name.strip():
        if ctx:
            await ctx.error("Empty name provided to greet tool")
        return {
            "error": "Name parameter is required and cannot be empty",
            "status": "error",
        }

    # Clean the name input
    clean_name = name.strip().title()

    result = {
        "message": f"Hello, {clean_name}! Welcome to the FACT Memory System.",
        "greeting_for": clean_name,
        "timestamp": datetime.now().isoformat(),
        "server": "FACT Hello World Server",
        "status": "success",
    }

    if ctx:
        await ctx.info(f"Greet tool executed successfully for: {clean_name}")

    return result


@mcp.resource("fact://server_info")
async def get_server_info() -> Dict[str, Any]:
    """
    Provide comprehensive information about this MCP server.

    Returns:
        Dictionary containing server metadata, capabilities, and status
    """
    return {
        "name": "FACT Hello World Server",
        "version": "1.0.0",
        "description": "A demonstration MCP server for the FACT Memory System",
        "framework": "FastMCP",
        "capabilities": {
            "tools": [
                {
                    "name": "hello",
                    "description": "Returns a simple hello message",
                    "parameters": [],
                },
                {
                    "name": "greet",
                    "description": "Returns a personalized greeting",
                    "parameters": [
                        {
                            "name": "name",
                            "type": "string",
                            "required": True,
                            "description": "Name to include in greeting",
                        }
                    ],
                },
            ],
            "resources": [
                {
                    "name": "server_info",
                    "description": "Server information and metadata",
                }
            ],
        },
        "status": {
            "running": True,
            "uptime_start": datetime.now().isoformat(),
            "health": "healthy",
        },
        "integration": {
            "fact_memory_compatible": True,
            "mcp_version": "1.0",
            "transport": "stdio",
        },
        "contact": {
            "documentation": "fact-memory/docs/",
            "repository": "FACT Memory System",
        },
    }


class HelloWorldMCPServer:
    """
    Hello World MCP Server class for advanced configuration and lifecycle management.
    """

    def __init__(self, name: str = "FACT Hello World Server", debug: bool = False):
        self.name = name
        self.debug = debug
        self.mcp = mcp
        self._setup_logging()

    def _setup_logging(self):
        """Configure logging based on debug setting."""
        level = logging.DEBUG if self.debug else logging.INFO
        logging.getLogger().setLevel(level)

        if self.debug:
            logger.info(f"Debug mode enabled for {self.name}")

    def start_http(self, host: str = "localhost", port: int = 8080):
        """
        Start the MCP server with HTTP transport.

        Args:
            host: Server host address
            port: Server port number
        """
        logger.info(f"Starting {self.name} on {host}:{port}")
        try:
            self.mcp.run(transport="streamable-http", host=host, port=port)
        except Exception as e:
            logger.error(f"Failed to start HTTP server: {e}")
            raise

    def run_stdio(self):
        """
        Run server with STDIO transport for CLI integration.
        This is the standard MCP transport method.
        """
        logger.info(f"Starting {self.name} with STDIO transport")
        try:
            self.mcp.run()  # Default STDIO transport
        except Exception as e:
            logger.error(f"Failed to start STDIO server: {e}")
            raise

    async def test_tools(self):
        """
        Test all available tools for development and debugging.
        """
        logger.info("Testing MCP tools...")

        try:
            # Test hello tool
            hello_result = await hello()
            logger.info(f"Hello tool result: {hello_result}")

            # Test greet tool
            greet_result = await greet("FastMCP Developer")
            logger.info(f"Greet tool result: {greet_result}")

            # Test resource
            server_info = await get_server_info()
            logger.info(f"Server info: {server_info}")

            logger.info("All tools tested successfully!")
            return True

        except Exception as e:
            logger.error(f"Tool testing failed: {e}")
            return False


def main():
    """
    Main entry point for the Hello World MCP Server.
    Supports both STDIO and HTTP modes based on command line arguments.
    """
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="FACT Hello World MCP Server")
    parser.add_argument(
        "--mode",
        choices=["stdio", "http", "test"],
        default="stdio",
        help="Server mode: stdio (default), http, or test",
    )
    parser.add_argument(
        "--host",
        default="localhost",
        help="Host address for HTTP mode (default: localhost)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port number for HTTP mode (default: 8080)",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    # Create server instance
    server = HelloWorldMCPServer(debug=args.debug)

    if args.mode == "stdio":
        logger.info("Running in STDIO mode for MCP client integration")
        server.run_stdio()

    elif args.mode == "http":
        logger.info(f"Running in HTTP mode on {args.host}:{args.port}")
        server.start_http(args.host, args.port)

    elif args.mode == "test":
        logger.info("Running in test mode")
        success = asyncio.run(server.test_tools())
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
