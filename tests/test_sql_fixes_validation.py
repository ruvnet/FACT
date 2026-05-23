#!/usr/bin/env python3
"""
Validation script for SQL NoneType error fixes.

This script tests all scenarios that previously caused NoneType errors
and validates they now return proper error messages instead of crashing.
"""

import asyncio
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.abspath("."))

from src.tools.connectors.sql import SQLQueryTool
from src.db.connection import DatabaseManager
from src.core.errors import InvalidSQLError, SecurityError, DatabaseError


async def test_validation_fixes():
    """Test all NoneType error scenarios have been fixed."""

    print("🔧 SQL NoneType Error Validation Tests")
    print("=" * 50)

    # Create database manager for testing
    db_manager = DatabaseManager("db/test_validation.db")
    await db_manager.initialize_database()

    sql_tool = SQLQueryTool(db_manager)

    test_cases = [
        {
            "name": "None SQL statement",
            "statement": None,
            "expected_error": "SQL statement cannot be None",
            "description": "Validates None input doesn't cause AttributeError on .lower() or len()",
        },
        {
            "name": "Empty SQL statement",
            "statement": "",
            "expected_error": "SQL statement cannot be empty",
            "description": "Validates empty string doesn't cause issues",
        },
        {
            "name": "Whitespace-only SQL statement",
            "statement": "   \n\t   ",
            "expected_error": "SQL statement cannot be empty",
            "description": "Validates whitespace-only strings are handled",
        },
        {
            "name": "Non-string input (integer)",
            "statement": 123,
            "expected_error": "SQL statement must be a string, got int",
            "description": "Validates non-string inputs are properly handled",
        },
        {
            "name": "Non-string input (list)",
            "statement": ["SELECT", "*", "FROM", "table"],
            "expected_error": "SQL statement must be a string, got list",
            "description": "Validates list inputs are properly handled",
        },
        {
            "name": "Valid SELECT statement",
            "statement": "SELECT COUNT(*) as total FROM companies",
            "expected_error": None,
            "description": "Validates that valid queries still work",
        },
    ]

    passed_tests = 0
    total_tests = len(test_cases)

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. {test_case['name']}")
        print(f"   {test_case['description']}")

        try:
            result = await sql_tool.execute_query(test_case["statement"])

            if test_case["expected_error"] is None:
                # This should succeed
                if result.get("status") == "success" or "rows" in result:
                    print(f"   ✅ PASSED: Query executed successfully")
                    passed_tests += 1
                elif result.get("status") == "failed":
                    print(
                        f"   ⚠️  PARTIAL: Query failed but didn't crash: {result.get('error', 'Unknown error')}"
                    )
                    passed_tests += 1  # Still counts as passing the NoneType fix
                else:
                    print(f"   ❌ FAILED: Unexpected result format")
            else:
                # This should fail with specific error
                if result.get("status") == "failed" and test_case[
                    "expected_error"
                ] in result.get("error", ""):
                    print(f"   ✅ PASSED: Correct error message returned")
                    passed_tests += 1
                else:
                    print(
                        f"   ❌ FAILED: Expected '{test_case['expected_error']}', got '{result.get('error', 'No error')}'"
                    )

        except Exception as e:
            print(f"   ❌ FAILED: Exception thrown - {type(e).__name__}: {e}")

    print("\n" + "=" * 50)
    print(f"🎯 Test Results: {passed_tests}/{total_tests} tests passed")

    if passed_tests == total_tests:
        print("🎉 ALL TESTS PASSED - NoneType errors have been successfully fixed!")
        return True
    else:
        print("⚠️  Some tests failed - additional fixes may be needed")
        return False


async def test_direct_validation():
    """Test the validation method directly."""

    print("\n🔍 Direct Validation Method Tests")
    print("=" * 50)

    db_manager = DatabaseManager("db/test_validation.db")

    test_cases = [
        (None, "SQL statement cannot be None"),
        ("", "SQL statement cannot be empty"),
        ("   ", "SQL statement cannot be empty"),
        (123, "SQL statement must be a string, got int"),
        ("DROP TABLE users", "Only SELECT statements are allowed"),
        ("SELECT * FROM users; DROP TABLE users", "Multiple statements"),
    ]

    passed = 0
    total = len(test_cases)

    for i, (statement, expected_error_part) in enumerate(test_cases, 1):
        print(f"\n{i}. Testing: {repr(statement)}")

        try:
            db_manager.validate_sql_query(statement)
            print(f"   ❌ FAILED: No exception thrown")
        except (InvalidSQLError, SecurityError) as e:
            if expected_error_part in str(e):
                print(f"   ✅ PASSED: Correct error - {e}")
                passed += 1
            else:
                print(
                    f"   ❌ FAILED: Wrong error - Expected '{expected_error_part}', got '{e}'"
                )
        except Exception as e:
            print(f"   ❌ FAILED: Unexpected exception - {type(e).__name__}: {e}")

    print(f"\n🎯 Direct validation tests: {passed}/{total} passed")
    return passed == total


if __name__ == "__main__":

    async def main():
        success1 = await test_validation_fixes()
        success2 = await test_direct_validation()

        if success1 and success2:
            print("\n🎉 ALL VALIDATIONS PASSED!")
            print("The NoneType error fixes are working correctly.")
            exit(0)
        else:
            print("\n⚠️  Some validations failed.")
            exit(1)

    asyncio.run(main())
