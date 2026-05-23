#!/usr/bin/env python3
"""
Test client for FACT Hello World MCP Server

Demonstrates how to interact with the FastMCP server programmatically.
This script shows examples of calling tools and accessing resources.
"""

import asyncio
import json
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_server_directly():
    """
    Test the server by importing and calling functions directly.
    This simulates what would happen when the server receives MCP calls.
    """
    logger.info("Testing server functions directly...")

    # Import the server functions
    from hello_mcp_server import hello, greet, get_server_info

    try:
        # Test hello tool
        logger.info("Testing hello tool...")
        hello_result = await hello()
        logger.info(f"Hello result: {json.dumps(hello_result, indent=2)}")

        # Test greet tool with valid input
        logger.info("Testing greet tool with valid input...")
        greet_result = await greet("FastMCP Developer")
        logger.info(f"Greet result: {json.dumps(greet_result, indent=2)}")

        # Test greet tool with empty input (error case)
        logger.info("Testing greet tool with empty input...")
        error_result = await greet("")
        logger.info(f"Error result: {json.dumps(error_result, indent=2)}")

        # Test server info resource
        logger.info("Testing server info resource...")
        server_info = await get_server_info()
        logger.info(f"Server info: {json.dumps(server_info, indent=2)}")

        logger.info("✅ All direct tests passed!")
        return True

    except Exception as e:
        logger.error(f"❌ Direct testing failed: {e}")
        return False


async def test_with_fastmcp_client():
    """
    Test using FastMCP client (if available).
    This demonstrates the proper way to interact with MCP servers.
    """
    logger.info("Testing with FastMCP client...")

    try:
        from fastmcp import Client
        from hello_mcp_server import mcp

        # Create client and connect to our server
        async with Client(mcp) as client:
            # Test hello tool
            logger.info("Calling hello tool via MCP client...")
            hello_response = await client.call_tool("hello", {})
            logger.info(f"Hello response: {hello_response}")

            # Test greet tool
            logger.info("Calling greet tool via MCP client...")
            greet_response = await client.call_tool("greet", {"name": "MCP Client"})
            logger.info(f"Greet response: {greet_response}")

            # Test resource access (Note: Resource access may not be available in all FastMCP client versions)
            logger.info(
                "Skipping resource access test - method varies by FastMCP version"
            )
            # resource_response = await client.read_resource("fact://server_info")
            # logger.info(f"Resource response: {resource_response}")

        logger.info("✅ FastMCP client tests passed!")
        return True

    except ImportError:
        logger.warning("FastMCP client not available for testing")
        return False
    except Exception as e:
        logger.error(f"❌ FastMCP client testing failed: {e}")
        return False


async def benchmark_performance():
    """
    Simple performance benchmark for the server tools.
    """
    logger.info("Running performance benchmark...")

    from hello_mcp_server import hello, greet
    import time

    # Benchmark hello tool
    start_time = time.time()
    iterations = 1000

    for i in range(iterations):
        await hello()

    hello_duration = time.time() - start_time
    hello_avg = (hello_duration / iterations) * 1000  # ms per call

    # Benchmark greet tool
    start_time = time.time()

    for i in range(iterations):
        await greet(f"User{i}")

    greet_duration = time.time() - start_time
    greet_avg = (greet_duration / iterations) * 1000  # ms per call

    logger.info(f"Performance Results ({iterations} iterations):")
    logger.info(f"  Hello tool: {hello_avg:.2f}ms per call")
    logger.info(f"  Greet tool: {greet_avg:.2f}ms per call")
    logger.info(f"  Total time: {hello_duration + greet_duration:.2f}s")


def validate_server_structure():
    """
    Validate that the server follows FastMCP best practices.
    """
    logger.info("Validating server structure...")

    from hello_mcp_server import mcp, HelloWorldMCPServer

    # Check server instance
    assert mcp.name == "FACT Hello World Server", "Server name mismatch"
    assert mcp.instructions, "Server instructions missing"

    # Check tools are registered
    tools = mcp._tool_manager._tools
    assert "hello" in tools, "Hello tool not registered"
    assert "greet" in tools, "Greet tool not registered"

    # Check resources are registered
    resources = mcp._resource_manager._resources
    assert any(
        "server_info" in str(uri) for uri in resources
    ), "Server info resource not registered"

    # Check server class
    server = HelloWorldMCPServer()
    assert server.name == "FACT Hello World Server", "Server class name mismatch"
    assert hasattr(server, "run_stdio"), "STDIO method missing"
    assert hasattr(server, "start_http"), "HTTP method missing"
    assert hasattr(server, "test_tools"), "Test method missing"

    logger.info("✅ Server structure validation passed!")


async def main():
    """
    Main test runner that executes all test scenarios.
    """
    logger.info("🚀 Starting FACT Hello World MCP Server Tests")
    logger.info("=" * 60)

    tests_passed = 0
    total_tests = 0

    # Test 1: Direct function calls
    total_tests += 1
    if await test_server_directly():
        tests_passed += 1

    # Test 2: FastMCP client integration
    total_tests += 1
    if await test_with_fastmcp_client():
        tests_passed += 1

    # Test 3: Server structure validation
    total_tests += 1
    try:
        validate_server_structure()
        tests_passed += 1
        logger.info("✅ Structure validation passed!")
    except Exception as e:
        logger.error(f"❌ Structure validation failed: {e}")

    # Test 4: Performance benchmark
    total_tests += 1
    try:
        await benchmark_performance()
        tests_passed += 1
        logger.info("✅ Performance benchmark completed!")
    except Exception as e:
        logger.error(f"❌ Performance benchmark failed: {e}")

    # Summary
    logger.info("=" * 60)
    logger.info(f"🏁 Test Summary: {tests_passed}/{total_tests} tests passed")

    if tests_passed == total_tests:
        logger.info("🎉 All tests passed! Server is ready for use.")
        return True
    else:
        logger.warning(f"⚠️  {total_tests - tests_passed} tests failed.")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
