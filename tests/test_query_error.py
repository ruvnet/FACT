#!/usr/bin/env python3
"""
Test script to reproduce the TypeError in query processing
"""

import os
import sys
import asyncio

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from src.core.driver import get_driver
from src.core.config import get_config


async def test_query_processing():
    """Test query processing to reproduce the TypeError."""
    try:
        print("🔧 Initializing FACT system...")
        driver = await get_driver()
        print("✅ System initialized")

        # Test queries that might trigger the TypeError
        test_queries = [
            "Show me all companies",
            "What is the database schema?",
            "Get sample queries",
        ]

        for i, query in enumerate(test_queries, 1):
            print(f"\n📋 Test Query {i}: {query}")
            try:
                response = await driver.process_query(query)
                print(f"✅ Response: {response[:100]}...")
            except Exception as e:
                print(f"❌ Error: {e}")
                print(f"Error type: {type(e).__name__}")

                # Print the full traceback for debugging
                import traceback

                traceback.print_exc()

    except Exception as e:
        print(f"❌ System initialization failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_query_processing())
