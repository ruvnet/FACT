#!/usr/bin/env python3
"""
Debug SQL validation issues
"""

import sys
import os
import re

sys.path.insert(0, os.path.abspath(".."))

from src.db.connection import DatabaseManager


def test_injection_patterns():
    """Test specific injection patterns"""

    # The problematic query
    query = "SELECT name as table_name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    normalized = query.lower()

    print(f"Testing query: {query}")
    print(f"Normalized: {normalized}")

    # Test each injection pattern individually
    injection_patterns = [
        (
            r";\s*(?:drop|delete|insert|update|create|alter)",
            "Multiple dangerous statements",
        ),
        (r"\bunion\s+(?:all\s+)?select\b", "Union injection attempts"),
        (r'\bor\s+[\'"]?1[\'"]?\s*=\s*[\'"]?1[\'"]?\b', "Always true OR conditions"),
        (r'\band\s+[\'"]?1[\'"]?\s*=\s*[\'"]?1[\'"]?\b', "Always true AND conditions"),
        (r"\'[^\']*\'[^\']*\'[^\']*\'", "Multiple quotes suggesting injection"),
        (r"\\x[0-9a-f]{2}", "Hex encoding"),
        (r"--.*(?:union|drop|delete|insert|update|create)", "Dangerous comments"),
        (r'\bor\s+[\'"]?\w+[\'"]?\s*=\s*[\'"]?\w+[\'"]?\s+or\b', "OR chain injections"),
    ]

    print("\n=== Testing Injection Patterns ===")
    for pattern, description in injection_patterns:
        match = re.search(pattern, normalized, re.IGNORECASE)
        if match:
            print(f"✗ MATCHED: {description}")
            print(f"   Pattern: {pattern}")
            print(f"   Match: '{match.group()}'")
        else:
            print(f"✓ No match: {description}")


def test_sql_validation():
    """Test specific SQL queries to find validation issues"""

    db_manager = DatabaseManager("db/test_debug.db")

    # Test queries that should be valid
    test_queries = [
        "SELECT name as table_name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name",
        "SELECT * FROM companies",
        "SELECT COUNT(*) FROM companies",
        "PRAGMA table_info(companies)",
        "SELECT name, revenue FROM companies WHERE sector = 'Technology'",
        "SELECT c.name, f.revenue FROM companies c JOIN financial_records f ON c.id = f.company_id WHERE f.year = 2024",
    ]

    print("\n=== SQL Validation Debug Tests ===")

    for i, query in enumerate(test_queries, 1):
        print(f"\n{i}. Testing query: {query[:50]}...")
        try:
            db_manager.validate_sql_query(query)
            print(f"✓ PASSED")
        except Exception as e:
            print(f"✗ FAILED: {type(e).__name__}: {e}")


if __name__ == "__main__":
    test_injection_patterns()
    test_sql_validation()
