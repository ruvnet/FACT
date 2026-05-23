#!/usr/bin/env python3
"""
Comprehensive test for SQL connector NoneType fixes
"""

import asyncio
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.abspath(".."))

from src.tools.connectors.sql import (
    SQLQueryTool,
    initialize_sql_tool,
    get_sql_tool,
    sql_get_schema,
)
from src.db.connection import DatabaseManager


async def test_comprehensive_fixes():
    """Test all NoneType fixes comprehensively"""

    # Initialize database manager and database
    db_manager = DatabaseManager("db/test_sql_fixes.db")
    await db_manager.initialize_database()

    # Initialize SQL tool
    initialize_sql_tool(db_manager)
    sql_tool = get_sql_tool()

    print("=== Comprehensive SQL NoneType Fix Tests ===")

    # Test 1: None statement (should handle gracefully now)
    print("\n1. Testing None statement (fixed)...")
    try:
        result = await sql_tool.execute_query(None)
        print(f"✓ Result: {result}")
    except Exception as e:
        print(f"✗ Error: {type(e).__name__}: {e}")

    # Test 2: Empty string statement
    print("\n2. Testing empty statement...")
    try:
        result = await sql_tool.execute_query("")
        print(f"✓ Result: {result}")
    except Exception as e:
        print(f"✓ Expected error: {type(e).__name__}: {e}")

    # Test 3: Non-string statement
    print("\n3. Testing non-string statement...")
    try:
        result = await sql_tool.execute_query(123)
        print(f"✓ Result: {result}")
    except Exception as e:
        print(f"✓ Expected error: {type(e).__name__}: {e}")

    # Test 4: Valid query with results
    print("\n4. Testing valid query...")
    try:
        result = await sql_tool.execute_query("SELECT COUNT(*) as count FROM companies")
        print(f"✓ Result: {result}")
    except Exception as e:
        print(f"✗ Error: {type(e).__name__}: {e}")

    # Test 5: Query that returns no results (empty result set)
    print("\n5. Testing query with no results...")
    try:
        result = await sql_tool.execute_query("SELECT * FROM companies WHERE id = -999")
        print(f"✓ Result: {result}")
    except Exception as e:
        print(f"✗ Error: {type(e).__name__}: {e}")

    # Test 6: Schema retrieval (tests the len() fixes in schema function)
    print("\n6. Testing schema retrieval...")
    try:
        result = await sql_get_schema()
        print(f"✓ Schema result status: {result.get('status', 'unknown')}")
        print(f"✓ Total tables: {result.get('total_tables', 0)}")
    except Exception as e:
        print(f"✗ Error: {type(e).__name__}: {e}")

    # Test 7: Very long statement (tests truncation logic)
    print("\n7. Testing long statement truncation...")
    try:
        long_statement = "SELECT COUNT(*) as count FROM companies" + " -- " + "x" * 200
        result = await sql_tool.execute_query(long_statement)
        print(f"✓ Result: {result}")
    except Exception as e:
        print(f"✗ Error: {type(e).__name__}: {e}")

    print("\n=== All tests completed ===")


if __name__ == "__main__":
    asyncio.run(test_comprehensive_fixes())
