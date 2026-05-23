#!/usr/bin/env python3
"""
Test script to reproduce the TypeError: object of type 'NoneType' has no len() error
"""

import asyncio
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.abspath(".."))

from src.tools.connectors.sql import SQLQueryTool, initialize_sql_tool, get_sql_tool
from src.db.connection import DatabaseManager


async def test_nonetype_scenarios():
    """Test various scenarios that could trigger the NoneType len() error"""

    # Initialize database manager and database
    db_manager = DatabaseManager("db/test_fact.db")
    await db_manager.initialize_database()

    # Initialize SQL tool
    initialize_sql_tool(db_manager)
    sql_tool = get_sql_tool()

    print("=== Testing NoneType scenarios ===")

    # Test 1: None statement (this should trigger the AttributeError)
    print("\n1. Testing None statement...")
    try:
        result = await sql_tool.execute_query(None)
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")

    # Test 1b: Test len() error by simulating a None statement in error response
    print("\n1b. Testing len() error scenario...")
    try:
        # This will fail validation but should not crash on len()
        result = await sql_tool.execute_query(None)
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")

    # Test 2: Empty statement
    print("\n2. Testing empty statement...")
    try:
        result = await sql_tool.execute_query("")
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")

    # Test 3: Query that returns no results (valid syntax)
    print("\n3. Testing query with no results...")
    try:
        result = await sql_tool.execute_query("SELECT * FROM companies WHERE id = -999")
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")

    # Test 4: Normal valid query (for comparison)
    print("\n4. Testing valid query...")
    try:
        result = await sql_tool.execute_query("SELECT COUNT(*) as count FROM companies")
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(test_nonetype_scenarios())
