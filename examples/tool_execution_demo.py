"""
FACT System Tool Execution Framework Demo

This script demonstrates how to use the FACT system's tool execution
framework with Arcade.dev integration, security validation, and monitoring.
"""

import asyncio
import json
import time
import sys
import os
from typing import Dict, Any

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Import FACT system components
from src.tools.executor import ToolExecutor, create_tool_call
from src.tools.decorators import Tool, get_tool_registry
from src.arcade.client import ArcadeClient
from src.security.auth import AuthorizationManager
from src.monitoring.metrics import get_metrics_collector


# Register some demo tools
@Tool(
    name="Demo.Calculator",
    description="Perform basic mathematical calculations",
    parameters={
        "operation": {
            "type": "string",
            "description": "Mathematical operation",
            "enum": ["add", "subtract", "multiply", "divide"],
        },
        "a": {"type": "number", "description": "First number"},
        "b": {"type": "number", "description": "Second number"},
    },
    requires_auth=False,
    timeout_seconds=10,
)
def calculator_tool(operation: str, a: float, b: float) -> Dict[str, Any]:
    """Perform basic mathematical calculations."""
    operations = {
        "add": lambda x, y: x + y,
        "subtract": lambda x, y: x - y,
        "multiply": lambda x, y: x * y,
        "divide": lambda x, y: x / y if y != 0 else None,
    }

    if operation not in operations:
        return {"error": f"Unknown operation: {operation}"}

    if operation == "divide" and b == 0:
        return {"error": "Division by zero"}

    result = operations[operation](a, b)

    return {
        "operation": operation,
        "operands": [a, b],
        "result": result,
        "expression": f"{a} {operation} {b} = {result}",
    }


@Tool(
    name="Demo.TextProcessor",
    description="Process and analyze text content",
    parameters={
        "text": {"type": "string", "description": "Text to process", "maxLength": 1000},
        "operations": {
            "type": "array",
            "description": "Operations to perform",
            "items": {
                "type": "string",
                "enum": [
                    "uppercase",
                    "lowercase",
                    "reverse",
                    "word_count",
                    "char_count",
                ],
            },
            "default": ["word_count"],
        },
    },
    requires_auth=False,
    timeout_seconds=15,
)
def text_processor_tool(text: str, operations: list = None) -> Dict[str, Any]:
    """Process and analyze text content."""
    if operations is None:
        operations = ["word_count"]

    results = {"original_text": text, "processed": {}}

    for operation in operations:
        if operation == "uppercase":
            results["processed"]["uppercase"] = text.upper()
        elif operation == "lowercase":
            results["processed"]["lowercase"] = text.lower()
        elif operation == "reverse":
            results["processed"]["reverse"] = text[::-1]
        elif operation == "word_count":
            results["processed"]["word_count"] = len(text.split())
        elif operation == "char_count":
            results["processed"]["char_count"] = len(text)

    return results


@Tool(
    name="Demo.DataGenerator",
    description="Generate sample data sets for testing",
    parameters={
        "data_type": {
            "type": "string",
            "description": "Type of data to generate",
            "enum": ["numbers", "names", "emails", "dates"],
        },
        "count": {
            "type": "integer",
            "description": "Number of items to generate",
            "minimum": 1,
            "maximum": 100,
            "default": 10,
        },
        "format": {
            "type": "string",
            "description": "Output format",
            "enum": ["list", "json", "csv"],
            "default": "list",
        },
    },
    requires_auth=False,
    timeout_seconds=20,
)
def data_generator_tool(
    data_type: str, count: int = 10, format: str = "list"
) -> Dict[str, Any]:
    """Generate sample data sets for testing."""
    import random
    import string
    from datetime import datetime, timedelta

    generators = {
        "numbers": lambda: [random.randint(1, 1000) for _ in range(count)],
        "names": lambda: [f"User_{i+1}" for i in range(count)],
        "emails": lambda: [f"user{i+1}@example.com" for i in range(count)],
        "dates": lambda: [
            (datetime.now() - timedelta(days=random.randint(0, 365))).isoformat()
            for _ in range(count)
        ],
    }

    if data_type not in generators:
        return {"error": f"Unknown data type: {data_type}"}

    data = generators[data_type]()

    result = {"data_type": data_type, "count": len(data), "format": format}

    if format == "list":
        result["data"] = data
    elif format == "json":
        result["data"] = json.dumps(data, indent=2)
    elif format == "csv":
        if data_type == "numbers":
            result["data"] = "value\n" + "\n".join(map(str, data))
        else:
            result["data"] = f"{data_type}\n" + "\n".join(map(str, data))

    return result


async def demo_basic_tool_execution():
    """Demonstrate basic tool execution without Arcade."""
    print("\n=== Demo: Basic Tool Execution ===")

    # Create tool executor (local execution only)
    executor = ToolExecutor(
        arcade_client=None, enable_rate_limiting=True, max_calls_per_minute=60
    )

    # Test calculator tool
    print("\n1. Testing Calculator Tool:")
    calc_call = create_tool_call(
        "Demo.Calculator", {"operation": "multiply", "a": 15, "b": 7}
    )

    result = await executor.execute_tool_call(calc_call)
    print(f"   Result: {result.data}")
    print(f"   Execution time: {result.execution_time_ms:.2f}ms")

    # Test text processor tool
    print("\n2. Testing Text Processor Tool:")
    text_call = create_tool_call(
        "Demo.TextProcessor",
        {
            "text": "Hello World! This is a test.",
            "operations": ["uppercase", "word_count", "char_count"],
        },
    )

    result = await executor.execute_tool_call(text_call)
    print(f"   Original: {result.data['original_text']}")
    print(f"   Processed: {json.dumps(result.data['processed'], indent=2)}")

    # Test data generator tool
    print("\n3. Testing Data Generator Tool:")
    data_call = create_tool_call(
        "Demo.DataGenerator", {"data_type": "emails", "count": 5, "format": "list"}
    )

    result = await executor.execute_tool_call(data_call)
    print(f"   Generated {result.data['count']} {result.data['data_type']}:")
    for email in result.data["data"]:
        print(f"     - {email}")


async def demo_error_handling():
    """Demonstrate error handling in tool execution."""
    print("\n=== Demo: Error Handling ===")

    executor = ToolExecutor(arcade_client=None)

    # Test division by zero
    print("\n1. Testing Division by Zero:")
    error_call = create_tool_call(
        "Demo.Calculator", {"operation": "divide", "a": 10, "b": 0}
    )

    result = await executor.execute_tool_call(error_call)
    if result.success:
        print(f"   Error message: {result.data['error']}")
    else:
        print(f"   Execution failed: {result.error}")

    # Test invalid tool
    print("\n2. Testing Invalid Tool:")
    invalid_call = create_tool_call("NonExistent.Tool", {"param": "value"})

    result = await executor.execute_tool_call(invalid_call)
    print(f"   Error: {result.error}")
    print(f"   Status: {result.status_code}")


async def demo_concurrent_execution():
    """Demonstrate concurrent tool execution."""
    print("\n=== Demo: Concurrent Execution ===")

    executor = ToolExecutor(arcade_client=None)

    # Create multiple tool calls
    tool_calls = [
        create_tool_call("Demo.Calculator", {"operation": "add", "a": i, "b": i * 2})
        for i in range(1, 6)
    ]

    print(f"\nExecuting {len(tool_calls)} calculator operations concurrently...")

    start_time = time.time()
    results = await executor.execute_tool_calls(tool_calls)
    execution_time = (time.time() - start_time) * 1000

    print(f"Total execution time: {execution_time:.2f}ms")
    print("Results:")
    for i, result in enumerate(results):
        if result.success:
            expr = result.data["expression"]
            print(f"   {i+1}. {expr} (took {result.execution_time_ms:.1f}ms)")
        else:
            print(f"   {i+1}. Error: {result.error}")


async def demo_rate_limiting():
    """Demonstrate rate limiting functionality."""
    print("\n=== Demo: Rate Limiting ===")

    # Create executor with low rate limit
    executor = ToolExecutor(
        arcade_client=None,
        enable_rate_limiting=True,
        max_calls_per_minute=3,  # Very low limit for demo
    )

    print("\nTesting rate limiting (max 3 calls per minute):")

    for i in range(5):
        call = create_tool_call("Demo.Calculator", {"operation": "add", "a": i, "b": 1})

        result = await executor.execute_tool_call(call)

        if result.success:
            print(f"   Call {i+1}: Success - {result.data['result']}")
        else:
            print(f"   Call {i+1}: Blocked - {result.error}")


async def demo_metrics_collection():
    """Demonstrate metrics collection and reporting."""
    print("\n=== Demo: Metrics Collection ===")

    executor = ToolExecutor(arcade_client=None)
    metrics_collector = get_metrics_collector()

    # Execute several tools to generate metrics
    print("\nExecuting tools to generate metrics...")

    operations = [
        {"operation": "add", "a": 10, "b": 5},
        {"operation": "multiply", "a": 3, "b": 7},
        {"operation": "subtract", "a": 20, "b": 8},
        {"operation": "divide", "a": 15, "b": 3},
    ]

    for op in operations:
        call = create_tool_call("Demo.Calculator", op)
        result = await executor.execute_tool_call(call)

        # Metrics are automatically collected by the executor
        print(
            f"   {op['operation']}: {result.data.get('result') if result.success else 'Error'}"
        )

    # Get system metrics
    print("\nSystem Metrics:")
    system_metrics = metrics_collector.get_system_metrics(time_window_minutes=5)
    print(f"   Total executions: {system_metrics.total_executions}")
    print(f"   Success rate: {100 - system_metrics.error_rate:.1f}%")
    print(f"   Average execution time: {system_metrics.average_execution_time:.2f}ms")

    # Get tool-specific metrics
    print("\nCalculator Tool Metrics:")
    tool_metrics = metrics_collector.get_tool_metrics("Demo.Calculator")
    print(f"   Executions: {tool_metrics['total_executions']}")
    print(f"   Success rate: {tool_metrics['success_rate']:.1f}%")
    print(f"   Average time: {tool_metrics['average_execution_time']:.2f}ms")


async def demo_available_tools():
    """Demonstrate tool discovery and information retrieval."""
    print("\n=== Demo: Tool Discovery ===")

    executor = ToolExecutor(arcade_client=None)

    # Get list of available tools
    tools = executor.get_available_tools()

    print(f"\nFound {len(tools)} available tools:")
    for tool in tools:
        function_info = tool["function"]
        print(f"\n  Tool: {function_info['name']}")
        print(f"  Description: {function_info['description']}")

        # Show parameters
        params = function_info.get("parameters", {}).get("properties", {})
        if params:
            print("  Parameters:")
            for param_name, param_info in params.items():
                param_type = param_info.get("type", "unknown")
                param_desc = param_info.get("description", "No description")
                print(f"    - {param_name} ({param_type}): {param_desc}")


async def demo_arcade_integration():
    """Demonstrate Arcade.dev integration (simulated)."""
    print("\n=== Demo: Arcade.dev Integration (Simulated) ===")

    # Note: This would require actual Arcade.dev credentials
    print("\nSimulating Arcade.dev integration...")
    print("(In production, this would connect to actual Arcade.dev platform)")

    # Create mock Arcade client for demo
    class MockArcadeClient:
        async def execute_tool(self, tool_name, arguments, **kwargs):
            await asyncio.sleep(0.1)  # Simulate network delay
            return {
                "success": True,
                "data": f"Arcade executed {tool_name} with {arguments}",
                "execution_environment": "secure_container",
                "execution_id": f"arcade_exec_{int(time.time())}",
            }

    mock_client = MockArcadeClient()
    executor = ToolExecutor(arcade_client=mock_client)

    # Execute tool via "Arcade"
    call = create_tool_call(
        "Demo.Calculator", {"operation": "multiply", "a": 6, "b": 9}
    )

    result = await executor.execute_tool_call(call)
    print(f"   Arcade execution result: {result.data}")
    print(f"   Execution time: {result.execution_time_ms:.2f}ms")


async def main():
    """Run all demonstrations."""
    print("FACT System Tool Execution Framework Demo")
    print("=" * 50)

    try:
        await demo_basic_tool_execution()
        await demo_error_handling()
        await demo_concurrent_execution()
        await demo_rate_limiting()
        await demo_metrics_collection()
        await demo_available_tools()
        await demo_arcade_integration()

        print("\n" + "=" * 50)
        print("All demos completed successfully!")

    except Exception as e:
        print(f"\nDemo failed with error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    # Run the demo
    asyncio.run(main())
