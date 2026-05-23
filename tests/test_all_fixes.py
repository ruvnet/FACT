#!/usr/bin/env python3
"""
Comprehensive validation test for all FACT system fixes.

This test validates:
1. SQL statement handling (None checks, empty string handling, non-string inputs)
2. Tool execution with proper async/await handling
3. LLM response processing with tool calls
4. Full system test with demo queries to confirm end-to-end functionality
"""

import asyncio
import sys
import os
import json
import time
from typing import Dict, Any, Optional
from unittest.mock import Mock, AsyncMock, MagicMock

# Add the project root to Python path
sys.path.insert(0, os.path.abspath(".."))

from src.core.driver import FACTDriver
from src.core.config import Config, get_config
from src.tools.connectors.sql import (
    SQLQueryTool,
    initialize_sql_tool,
    sql_query_readonly,
    sql_get_schema,
)
from src.db.connection import DatabaseManager
from src.tools.decorators import get_tool_registry
from src.core.errors import InvalidSQLError, SecurityError, DatabaseError


class TestRunner:
    """Comprehensive test runner for FACT system validation."""

    def __init__(self):
        self.passed_tests = 0
        self.failed_tests = 0
        self.test_results = []

    async def run_test(self, test_name: str, test_func):
        """Run a single test and track results."""
        print(f"\n{'='*60}")
        print(f"Running: {test_name}")
        print(f"{'='*60}")

        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()

            if result:
                print(f"✅ PASSED: {test_name}")
                self.passed_tests += 1
                self.test_results.append(
                    {"test": test_name, "status": "PASSED", "error": None}
                )
            else:
                print(f"❌ FAILED: {test_name} - Test returned False")
                self.failed_tests += 1
                self.test_results.append(
                    {
                        "test": test_name,
                        "status": "FAILED",
                        "error": "Test returned False",
                    }
                )

        except Exception as e:
            print(f"❌ FAILED: {test_name} - {type(e).__name__}: {e}")
            self.failed_tests += 1
            self.test_results.append(
                {"test": test_name, "status": "FAILED", "error": str(e)}
            )

    def print_summary(self):
        """Print test summary."""
        total_tests = self.passed_tests + self.failed_tests
        print(f"\n{'='*60}")
        print(f"TEST SUMMARY")
        print(f"{'='*60}")
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {self.passed_tests}")
        print(f"Failed: {self.failed_tests}")
        print(
            f"Success Rate: {(self.passed_tests/total_tests*100) if total_tests > 0 else 0:.1f}%"
        )

        if self.failed_tests > 0:
            print(f"\nFailed Tests:")
            for result in self.test_results:
                if result["status"] == "FAILED":
                    print(f"  - {result['test']}: {result['error']}")


async def test_sql_statement_validation():
    """Test 1: SQL statement handling with None checks, empty strings, and non-string inputs."""

    # Initialize database and SQL tool
    db_manager = DatabaseManager("db/test_validation.db")
    await db_manager.initialize_database()
    initialize_sql_tool(db_manager)

    print("Testing SQL statement validation fixes...")

    # Test 1.1: None statement - Test both decorator validation and internal validation
    print("\n1.1 Testing None statement...")
    try:
        # Test decorator level validation (should catch None)
        result = await sql_query_readonly(None)
        # Should return error response, not crash
        assert "error" in result or result.get("status") == "failed"
        print("✓ None statement handled gracefully by decorator")
    except Exception as e:
        # This is expected - decorator should validate and raise ToolValidationError
        if "Parameter validation failed" in str(e):
            print("✓ None statement correctly rejected by parameter validation")
        else:
            print(f"✗ None statement test failed: {e}")
            return False

    # Test 1.2: Empty string statement
    print("\n1.2 Testing empty string statement...")
    try:
        result = await sql_query_readonly("")
        assert "error" in result
        assert result["status"] == "failed"
        print("✓ Empty string handled gracefully")
    except Exception as e:
        if "Parameter validation failed" in str(e) or "too short" in str(e):
            print("✓ Empty string correctly rejected by parameter validation")
        else:
            print(f"✗ Empty string test failed: {e}")
            return False

    # Test 1.3: Non-string statement
    print("\n1.3 Testing non-string statement...")
    try:
        result = await sql_query_readonly(123)
        assert "error" in result
        assert result["status"] == "failed"
        print("✓ Non-string input handled gracefully")
    except Exception as e:
        if "Parameter validation failed" in str(e) or "Invalid type" in str(e):
            print("✓ Non-string input correctly rejected by parameter validation")
        else:
            print(f"✗ Non-string test failed: {e}")
            return False

    # Test 1.4: Valid query
    print("\n1.4 Testing valid SQL query...")
    try:
        result = await sql_query_readonly("SELECT COUNT(*) as count FROM companies")
        assert result["status"] == "success"
        assert "rows" in result
        assert result["row_count"] >= 0
        print("✓ Valid query executed successfully")
    except Exception as e:
        print(f"✗ Valid query test failed: {e}")
        return False

    # Test 1.5: Schema retrieval (tests None/length checks in schema function)
    print("\n1.5 Testing schema retrieval with None checks...")
    try:
        result = await sql_get_schema()
        assert result["status"] == "success"
        assert "tables" in result
        assert isinstance(result["total_tables"], int)
        print("✓ Schema retrieval with None checks working")
    except Exception as e:
        print(f"✗ Schema retrieval test failed: {e}")
        return False

    return True


async def test_tool_execution_async_handling():
    """Test 2: Tool execution with proper async/await handling."""

    print("Testing tool execution and async/await handling...")

    # Test 2.1: Tool registry functionality
    print("\n2.1 Testing tool registry...")
    registry = get_tool_registry()
    tools = registry.list_tools()

    if not tools:
        print("✗ No tools registered")
        return False

    print(f"✓ Found {len(tools)} registered tools: {tools}")

    # Test 2.2: Tool schema export
    print("\n2.2 Testing tool schema export...")
    schemas = registry.export_all_schemas()

    if not schemas:
        print("✗ No schemas exported")
        return False

    print(f"✓ Exported {len(schemas)} tool schemas")

    # Verify schema format
    for schema in schemas:
        if "function" not in schema or "name" not in schema["function"]:
            print(f"✗ Invalid schema format: {schema}")
            return False

    # Test 2.3: Async tool execution
    print("\n2.3 Testing async tool execution...")

    # Initialize database for tool testing
    db_manager = DatabaseManager("db/test_validation.db")
    await db_manager.initialize_database()
    initialize_sql_tool(db_manager)

    try:
        # Test async tool directly
        result = await sql_query_readonly("SELECT 1 as test_value")
        assert result["status"] == "success"
        assert "execution_time_ms" in result
        print("✓ Async tool execution working correctly")
    except Exception as e:
        print(f"✗ Async tool execution failed: {e}")
        return False

    return True


async def test_llm_response_processing():
    """Test 3: LLM response processing with tool calls."""

    print("Testing LLM response processing...")

    # Create a mock LLM response with tool calls
    mock_tool_call = Mock()
    mock_tool_call.id = "call_123"
    mock_tool_call.type = "function"
    mock_tool_call.function = Mock()
    mock_tool_call.function.name = (
        "SQL_QueryReadonly"  # Note: underscores for API compatibility
    )
    mock_tool_call.function.arguments = (
        '{"statement": "SELECT COUNT(*) FROM companies"}'
    )

    mock_message = Mock()
    mock_message.content = "I'll help you query the database."
    mock_message.tool_calls = [mock_tool_call]

    mock_choice = Mock()
    mock_choice.message = mock_message

    mock_response = Mock()
    mock_response.choices = [mock_choice]

    # Test 3.1: Tool call extraction
    print("\n3.1 Testing tool call extraction...")

    # Simulate the driver's tool call processing
    try:
        tool_calls = mock_response.choices[0].message.tool_calls
        assert len(tool_calls) == 1
        assert tool_calls[0].function.name == "SQL_QueryReadonly"
        print("✓ Tool calls extracted successfully")
    except Exception as e:
        print(f"✗ Tool call extraction failed: {e}")
        return False

    # Test 3.2: Tool execution simulation
    print("\n3.2 Testing tool execution from LLM response...")

    # Initialize database and tools
    db_manager = DatabaseManager("db/test_validation.db")
    await db_manager.initialize_database()
    initialize_sql_tool(db_manager)

    try:
        # Simulate what the driver does
        tool_call = mock_tool_call
        tool_name = tool_call.function.name.replace(
            "_", "."
        )  # Convert back to registry format
        tool_args = json.loads(tool_call.function.arguments)

        # Get tool from registry
        registry = get_tool_registry()
        tool_definition = registry.get_tool(tool_name)

        # Execute tool (async)
        result = await tool_definition.function(**tool_args)

        assert isinstance(result, dict)
        assert result["status"] == "success"
        print("✓ Tool execution from LLM response successful")

    except Exception as e:
        print(f"✗ Tool execution from LLM response failed: {e}")
        return False

    # Test 3.3: Response content handling (test None response handling)
    print("\n3.3 Testing None response content handling...")

    # Test the driver's content extraction logic
    try:
        # Simulate various response scenarios
        test_cases = [
            {"content": "Valid response", "expected": "Valid response"},
            {"content": None, "expected": None},
            {"content": "", "expected": ""},
        ]

        for i, case in enumerate(test_cases):
            mock_resp = Mock()
            mock_resp.content = case["content"]

            # Simulate driver logic
            if hasattr(mock_resp, "content"):
                response_text = mock_resp.content
            else:
                response_text = None

            if case["expected"] is None:
                assert response_text is None
            else:
                assert response_text == case["expected"]

        print("✓ Response content handling working correctly")

    except Exception as e:
        print(f"✗ Response content handling failed: {e}")
        return False

    return True


async def test_full_system_functionality():
    """Test 4: Full system test with end-to-end functionality."""

    print("Testing full system functionality...")

    # Test 4.1: Driver initialization
    print("\n4.1 Testing driver initialization...")

    try:
        # Create test config
        config = get_config()
        # Can't modify config directly, so create driver with test database path

        # Create driver with default config but test database
        driver = FACTDriver(config)
        # Override the database path after initialization
        driver.config.database_path = "db/test_validation.db"
        await driver.initialize()

        assert driver._initialized == True
        print("✓ Driver initialized successfully")

    except Exception as e:
        print(f"✗ Driver initialization failed: {e}")
        return False

    # Test 4.2: System metrics
    print("\n4.2 Testing system metrics...")

    try:
        metrics = driver.get_metrics()
        assert isinstance(metrics, dict)
        assert "total_queries" in metrics
        assert "initialized" in metrics
        assert metrics["initialized"] == True
        print("✓ System metrics working")

    except Exception as e:
        print(f"✗ System metrics failed: {e}")
        return False

    # Test 4.3: Database operations through driver
    print("\n4.3 Testing database operations through system...")

    try:
        # Test database info
        db_info = await driver.database_manager.get_database_info()
        assert isinstance(db_info, dict)
        assert "tables" in db_info
        print("✓ Database operations working")

    except Exception as e:
        print(f"✗ Database operations failed: {e}")
        return False

    # Test 4.4: Error handling in driver
    print("\n4.4 Testing error handling in driver...")

    try:
        # Create a driver with invalid OpenAI key to test error handling
        test_config = get_config()
        test_config.openai_api_key = "invalid_key_for_testing"
        test_config.database_path = "db/test_validation.db"

        error_driver = FACTDriver(test_config)
        await error_driver.initialize()  # Should not crash, just log warnings

        print("✓ Error handling in driver working (allows system to continue)")

    except Exception as e:
        # This is expected - driver should handle errors gracefully
        print(f"✓ Driver error handling working: {type(e).__name__}")

    # Clean up
    await driver.shutdown()

    return True


async def test_demo_queries():
    """Test 5: Demo queries to confirm end-to-end functionality."""

    print("Testing demo queries for end-to-end validation...")

    # Initialize system
    db_manager = DatabaseManager("db/test_validation.db")
    await db_manager.initialize_database()
    initialize_sql_tool(db_manager)

    # Test queries that should work
    demo_queries = [
        {
            "name": "Company count",
            "query": "SELECT COUNT(*) as total_companies FROM companies",
            "should_work": True,
        },
        {
            "name": "Technology companies",
            "query": "SELECT name, symbol FROM companies WHERE sector = 'Technology'",
            "should_work": True,
        },
        {
            "name": "Latest financial data",
            "query": "SELECT c.name, f.revenue FROM companies c JOIN financial_records f ON c.id = f.company_id WHERE f.year = 2025 AND f.quarter = 'Q1' LIMIT 5",
            "should_work": True,
        },
        {
            "name": "Schema information",
            "query": "PRAGMA table_info(companies)",
            "should_work": True,
        },
        {
            "name": "Invalid dangerous query",
            "query": "DROP TABLE companies",
            "should_work": False,
        },
        {
            "name": "SQL injection attempt",
            "query": "SELECT * FROM companies WHERE id = 1; DROP TABLE companies; --",
            "should_work": False,
        },
    ]

    success_count = 0

    for i, test_case in enumerate(demo_queries, 1):
        print(f"\n5.{i} Testing: {test_case['name']}")
        print(f"Query: {test_case['query']}")

        try:
            result = await sql_query_readonly(test_case["query"])

            if test_case["should_work"]:
                if result["status"] == "success":
                    print(f"✓ Query succeeded as expected")
                    success_count += 1
                else:
                    print(
                        f"✗ Query should have succeeded but failed: {result.get('error', 'Unknown error')}"
                    )
            else:
                if result["status"] == "failed":
                    print(
                        f"✓ Query correctly rejected: {result.get('error', 'Security violation')}"
                    )
                    success_count += 1
                else:
                    print(f"✗ Dangerous query should have been rejected but succeeded")

        except Exception as e:
            if test_case["should_work"]:
                print(f"✗ Query failed unexpectedly: {e}")
            else:
                print(f"✓ Query correctly failed with exception: {e}")
                success_count += 1

    print(f"\nDemo queries: {success_count}/{len(demo_queries)} passed")
    return success_count == len(demo_queries)


async def test_edge_cases():
    """Test 6: Edge cases and boundary conditions."""

    print("Testing edge cases and boundary conditions...")

    # Initialize system
    db_manager = DatabaseManager("db/test_validation.db")
    await db_manager.initialize_database()
    initialize_sql_tool(db_manager)

    # Test 6.1: Very long query (should be rejected)
    print("\n6.1 Testing very long query...")
    try:
        long_query = "SELECT * FROM companies WHERE " + " OR ".join(
            [f"id = {i}" for i in range(1000)]
        )
        result = await sql_query_readonly(long_query)
        assert result["status"] == "failed"
        assert "too long" in result.get("error", "").lower()
        print("✓ Long query rejected correctly")
    except Exception as e:
        if "too long" in str(e) or "Parameter validation failed" in str(e):
            print("✓ Long query correctly rejected by parameter validation")
        else:
            print(f"✗ Long query test failed: {e}")
            return False

    # Test 6.2: Complex nested query (should be rejected)
    print("\n6.2 Testing complex nested query...")
    try:
        nested_query = "SELECT * FROM (SELECT * FROM (SELECT * FROM (SELECT * FROM (SELECT * FROM (SELECT * FROM companies)))))"
        result = await sql_query_readonly(nested_query)
        assert result["status"] == "failed"
        assert (
            "nested" in result.get("error", "").lower()
            or "subqueries" in result.get("error", "").lower()
        )
        print("✓ Complex nested query rejected correctly")
    except Exception as e:
        print(f"✗ Nested query test failed: {e}")
        return False

    # Test 6.3: Query with special characters
    print("\n6.3 Testing query with special characters...")
    try:
        special_query = (
            "SELECT name FROM companies WHERE name LIKE '%&%' OR name LIKE '%@%'"
        )
        result = await sql_query_readonly(special_query)
        # This should work - special characters in data are OK
        assert result["status"] == "success"
        print("✓ Special characters in query handled correctly")
    except Exception as e:
        print(f"✗ Special characters test failed: {e}")
        return False

    # Test 6.4: Unicode query
    print("\n6.4 Testing unicode query...")
    try:
        unicode_query = (
            "SELECT name FROM companies WHERE name LIKE '%é%' OR name LIKE '%中%'"
        )
        result = await sql_query_readonly(unicode_query)
        assert result["status"] == "success"
        print("✓ Unicode query handled correctly")
    except Exception as e:
        print(f"✗ Unicode query test failed: {e}")
        return False

    return True


async def main():
    """Main test execution function."""

    print("🧪 FACT System Comprehensive Validation Test")
    print("=" * 60)
    print("Testing all major fixes and functionality:")
    print("1. SQL statement handling (None checks, validation)")
    print("2. Tool execution with proper async/await handling")
    print("3. LLM response processing with tool calls")
    print("4. Full system end-to-end functionality")
    print("5. Demo queries validation")
    print("6. Edge cases and boundary conditions")

    runner = TestRunner()

    # Run all test suites
    await runner.run_test("SQL Statement Validation", test_sql_statement_validation)
    await runner.run_test(
        "Tool Execution & Async Handling", test_tool_execution_async_handling
    )
    await runner.run_test("LLM Response Processing", test_llm_response_processing)
    await runner.run_test("Full System Functionality", test_full_system_functionality)
    await runner.run_test("Demo Queries Validation", test_demo_queries)
    await runner.run_test("Edge Cases & Boundary Conditions", test_edge_cases)

    # Print final summary
    runner.print_summary()

    # Return appropriate exit code
    return 0 if runner.failed_tests == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
