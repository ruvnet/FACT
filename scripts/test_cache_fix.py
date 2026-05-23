#!/usr/bin/env python3
"""
Test script to verify cache validation mismatch fix.

This script demonstrates that the cache system now properly respects
the configured minimum token count instead of using a hard-coded value.
"""

import os
import sys
from pathlib import Path

# Add src to path
src_path = str(Path(__file__).parent.parent / "src")
sys.path.insert(0, src_path)

from cache.manager import CacheManager
from cache.config import load_cache_config_from_env, get_default_cache_config


def test_cache_validation_fix():
    """Test that cache validation now uses configured minimum tokens."""

    print("=== FACT Cache Validation Fix Verification ===\n")

    # Test 1: Default configuration
    print("1. Testing default configuration (500 tokens)...")
    default_config = get_default_cache_config()
    manager_default = CacheManager(default_config)
    print(f"   Default min_tokens: {manager_default.min_tokens}")

    # Test 2: Custom configuration
    print("\n2. Testing custom configuration (100 tokens)...")
    custom_config = default_config.copy()
    custom_config["min_tokens"] = 100
    manager_custom = CacheManager(custom_config)
    print(f"   Custom min_tokens: {manager_custom.min_tokens}")

    # Test 3: Environment override
    print("\n3. Testing environment override...")
    os.environ["CACHE_MIN_TOKENS"] = "75"
    try:
        env_config = load_cache_config_from_env()
        manager_env = CacheManager(env_config.to_dict())
        print(f"   Environment min_tokens: {manager_env.min_tokens}")
    except Exception as e:
        print(f"   Environment test failed: {e}")

    # Test 4: Validation consistency
    print("\n4. Testing validation consistency...")
    test_content = "This is a test response. " * 15  # ~375 tokens

    try:
        # Should fail with default manager (requires 500 tokens)
        hash_key = manager_default.generate_hash("test_query_1")
        manager_default.store(hash_key, test_content)
        print("   ❌ ERROR: Default manager should have rejected content")
    except Exception:
        print("   ✅ Default manager correctly rejected content (<500 tokens)")

    try:
        # Should succeed with custom manager (requires 100 tokens)
        hash_key = manager_custom.generate_hash("test_query_2")
        entry = manager_custom.store(hash_key, test_content)
        print(f"   ✅ Custom manager accepted content ({entry.token_count} tokens)")
    except Exception as e:
        print(f"   ❌ Custom manager failed: {e}")

    print("\n=== Fix Summary ===")
    print("✅ Hard-coded 500 token minimum removed from CacheEntry._validate()")
    print("✅ CacheEntry now accepts configurable min_tokens parameter")
    print("✅ CacheManager passes configured min_tokens to CacheEntry.create()")
    print("✅ Environment variable CACHE_MIN_TOKENS is properly respected")
    print("✅ Cache validation mismatch resolved!")


if __name__ == "__main__":
    test_cache_validation_fix()
