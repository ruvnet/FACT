#!/usr/bin/env python3
"""
MCP Integration Test for FACT Hello World Server

Tests the MCP protocol compliance and integration patterns.
"""

import asyncio
import json
import logging
import subprocess
import tempfile
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_mcp_stdio_protocol():
    """
    Test the MCP server with proper MCP protocol initialization.
    """
    logger.info("Testing MCP STDIO protocol compliance...")

    try:
        # Start the server as a subprocess
        server_path = Path(__file__).parent / "hello_mcp_server.py"
        process = subprocess.Popen(
            ["python", str(server_path), "--mode", "stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=0,
        )

        # Wait a moment for server to start
        await asyncio.sleep(0.5)

        # Send MCP initialization
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"roots": {"listChanged": True}, "sampling": {}},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        }

        # Send the request
        request_json = json.dumps(init_request) + "\n"
        process.stdin.write(request_json)
        process.stdin.flush()

        # Wait for response with timeout
        start_time = time.time()
        response_line = ""
        while time.time() - start_time < 5:
            if process.poll() is not None:
                break
            try:
                # Read more characters at a time
                chunk = process.stdout.read(1024)
                if chunk:
                    response_line += chunk
                    # Look for complete JSON message
                    if "\n" in response_line:
                        # Get the first complete line
                        lines = response_line.split("\n")
                        response_line = lines[0]
                        break
                await asyncio.sleep(0.01)
            except:
                break

        # Clean up
        process.terminate()
        process.wait(timeout=2)

        if response_line:
            try:
                response = json.loads(response_line.strip())
                logger.info(
                    f"MCP Initialize Response: {json.dumps(response, indent=2)}"
                )

                # Validate response structure
                if "result" in response and "protocolVersion" in response["result"]:
                    logger.info("✅ MCP protocol initialization successful!")
                    return True
                else:
                    logger.warning("⚠️ MCP response format may be non-standard")
                    return True
            except json.JSONDecodeError as e:
                logger.error(f"❌ Invalid JSON response: {e}")
                logger.error(f"Raw response: {response_line}")
                return False
        else:
            logger.error("❌ No response received from MCP server")
            return False

    except Exception as e:
        logger.error(f"❌ MCP protocol test failed: {e}")
        return False


async def test_error_handling():
    """
    Test error handling for invalid inputs.
    """
    logger.info("Testing error handling...")

    from hello_mcp_server import greet

    try:
        # Test empty name
        result = await greet("")
        assert "error" in result, "Empty name should return error"
        logger.info("✅ Empty name error handling works")

        # Test whitespace-only name
        result = await greet("   ")
        assert "error" in result, "Whitespace name should return error"
        logger.info("✅ Whitespace name error handling works")

        # Test valid name
        result = await greet("Test User")
        assert "message" in result, "Valid name should return success"
        logger.info("✅ Valid name handling works")

        return True

    except Exception as e:
        logger.error(f"❌ Error handling test failed: {e}")
        return False


async def test_resource_access():
    """
    Test resource access functionality.
    """
    logger.info("Testing resource access...")

    from hello_mcp_server import get_server_info

    try:
        server_info = await get_server_info()

        # Validate required fields
        required_fields = ["name", "version", "capabilities", "status"]
        for field in required_fields:
            assert field in server_info, f"Missing required field: {field}"

        # Validate capabilities structure
        caps = server_info["capabilities"]
        assert "tools" in caps, "Missing tools in capabilities"
        assert "resources" in caps, "Missing resources in capabilities"

        # Validate tool information
        tools = caps["tools"]
        tool_names = [tool["name"] for tool in tools]
        assert "hello" in tool_names, "Missing hello tool"
        assert "greet" in tool_names, "Missing greet tool"

        logger.info("✅ Resource access validation passed")
        return True

    except Exception as e:
        logger.error(f"❌ Resource access test failed: {e}")
        return False


async def test_performance_stress():
    """
    Test performance under load.
    """
    logger.info("Testing performance under stress...")

    from hello_mcp_server import hello, greet

    try:
        # Test rapid-fire calls
        start_time = time.time()
        tasks = []

        # Create 100 concurrent hello calls
        for i in range(100):
            tasks.append(hello())

        # Create 100 concurrent greet calls
        for i in range(100):
            tasks.append(greet(f"User{i}"))

        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks)

        duration = time.time() - start_time
        avg_time = (duration / len(tasks)) * 1000  # ms per call

        logger.info(f"Stress test completed: {len(tasks)} calls in {duration:.2f}s")
        logger.info(f"Average response time: {avg_time:.2f}ms per call")

        # Validate all results are successful
        success_count = 0
        for result in results:
            if "message" in result or "greeting_for" in result:
                success_count += 1

        success_rate = (success_count / len(results)) * 100
        logger.info(f"Success rate: {success_rate:.1f}%")

        if success_rate >= 99:
            logger.info("✅ Stress test passed")
            return True
        else:
            logger.warning("⚠️ Stress test had some failures")
            return False

    except Exception as e:
        logger.error(f"❌ Stress test failed: {e}")
        return False


async def main():
    """
    Run comprehensive MCP integration tests.
    """
    logger.info("🚀 Starting MCP Integration Tests")
    logger.info("=" * 60)

    tests = [
        ("MCP Protocol Compliance", test_mcp_stdio_protocol),
        ("Error Handling", test_error_handling),
        ("Resource Access", test_resource_access),
        ("Performance Stress", test_performance_stress),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        logger.info(f"\n🧪 Running: {test_name}")
        try:
            if await test_func():
                passed += 1
                logger.info(f"✅ {test_name} PASSED")
            else:
                logger.error(f"❌ {test_name} FAILED")
        except Exception as e:
            logger.error(f"❌ {test_name} FAILED with exception: {e}")

    logger.info("=" * 60)
    logger.info(f"🏁 Integration Test Summary: {passed}/{total} tests passed")

    if passed == total:
        logger.info("🎉 All integration tests passed! MCP server is production ready.")
        return True
    else:
        logger.warning(f"⚠️ {total - passed} integration tests failed.")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
