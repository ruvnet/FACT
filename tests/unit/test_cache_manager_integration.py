"""
Integration tests for cache manager with validation and security.
Tests the complete cache management system integration.
"""

import pytest
import time
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock

from src.cache.manager import CacheManager, get_cache_manager, CacheEntry
from src.cache.validation import CacheValidator, ValidationLevel
from src.cache.security import CacheSecurityValidator
from src.cache.config import CacheConfig
from src.core.errors import CacheError, SecurityError, ConfigurationError


class TestCacheManagerIntegration:
    """Test suite for integrated cache manager functionality."""

    @pytest.fixture
    def cache_config(self):
        """Provide cache configuration for tests."""
        return {
            "prefix": "test_integration",
            "min_tokens": 100,  # Lower for testing
            "max_size": "1MB",
            "ttl_seconds": 3600,
            "hit_target_ms": 50,
            "miss_target_ms": 150,
        }

    @pytest.fixture
    def cache_manager(self, cache_config):
        """Create cache manager for testing."""
        return CacheManager(cache_config)

    def test_cache_manager_with_security_validation(self, cache_manager):
        """TEST: Cache manager integrates with security validation"""
        # Store clean content - should succeed
        clean_content = "This is clean, safe content " * 50  # Meet min tokens
        entry = cache_manager.store("clean_query", clean_content)

        assert entry.content == clean_content
        assert entry.token_count >= cache_manager.min_tokens

    def test_cache_manager_blocks_malicious_content(self, cache_manager):
        """TEST: Cache manager blocks malicious content via security validation"""
        malicious_content = (
            "password: secret123 " * 50
        )  # Meet min tokens but include sensitive data

        with pytest.raises(CacheError):
            cache_manager.store("malicious_query", malicious_content)

    def test_cache_manager_handles_security_validation_failure(self, cache_manager):
        """TEST: Cache manager handles security validation failures gracefully"""
        # Mock security validation to fail
        with patch(
            "src.cache.manager.validate_cache_content_security",
            side_effect=SecurityError("Test security error"),
        ):
            content = "Safe content " * 50

            with pytest.raises(CacheError):
                cache_manager.store("test_query", content)

    def test_cache_manager_validation_integration(self, cache_manager):
        """TEST: Cache manager works with cache validation"""
        # Add several entries
        for i in range(5):
            content = f"Test content {i} " * 100
            cache_manager.store(f"query_{i}", content)

        # Create validator and validate
        validator = CacheValidator(cache_manager=cache_manager)

        # Should work without errors
        assert validator.cache_manager == cache_manager
        assert len(validator.thresholds) > 0

    @pytest.mark.asyncio
    async def test_end_to_end_cache_validation(self, cache_manager):
        """TEST: End-to-end cache validation workflow"""
        # Add test entries with different characteristics

        # Valid entry
        valid_content = "Valid business content " * 100
        cache_manager.store("valid_query", valid_content)

        # Entry that will become stale
        old_entry = CacheEntry.create(cache_manager.prefix, "Old content " * 100)
        old_entry.created_at = time.time() - 7200  # 2 hours old
        cache_manager.cache["old_query"] = old_entry

        # Create validator and run validation
        validator = CacheValidator(cache_manager=cache_manager)
        result = await validator.validate_cache(ValidationLevel.COMPREHENSIVE)

        assert result.total_entries_checked == 2
        assert result.overall_health in ["healthy", "warning", "critical"]
        assert len(result.recommendations) >= 0

    def test_get_cache_manager_singleton(self, cache_config):
        """TEST: get_cache_manager returns singleton instance"""
        manager1 = get_cache_manager(cache_config)
        manager2 = get_cache_manager()  # Should return same instance

        assert manager1 is manager2

    def test_get_cache_manager_environment_config(self):
        """TEST: get_cache_manager loads from environment"""
        env_vars = {
            "CACHE_PREFIX": "env_test",
            "CACHE_MIN_TOKENS": "1000",
            "CACHE_MAX_SIZE": "5MB",
        }

        with patch.dict(os.environ, env_vars):
            with patch("src.cache.manager.load_cache_config_from_env") as mock_load:
                mock_config = CacheConfig(
                    prefix="env_test", min_tokens=1000, max_size="5MB"
                )
                mock_load.return_value = mock_config

                # Clear singleton for test
                import src.cache.manager

                src.cache.manager._cache_manager_instance = None

                manager = get_cache_manager()

                assert manager is not None
                mock_load.assert_called_once()

    def test_cache_manager_error_handling(self, cache_config):
        """TEST: Cache manager handles various error conditions"""
        manager = CacheManager(cache_config)

        # Test content too small
        small_content = "Too small"
        with pytest.raises(CacheError):
            manager.store("small_query", small_content)

        # Test cache size limits
        very_large_content = "X" * (2 * 1024 * 1024)  # 2MB, exceeds 1MB limit
        with pytest.raises(CacheError):
            manager.store("large_query", very_large_content)

    @pytest.mark.asyncio
    async def test_cache_auto_repair_integration(self, cache_manager):
        """TEST: Cache auto-repair integration with validation"""
        # Add some problematic entries

        # Corrupted entry (empty content)
        corrupted_entry = CacheEntry(
            prefix=cache_manager.prefix, content="", token_count=0, validate=False
        )
        cache_manager.cache["corrupted"] = corrupted_entry

        # Expired entry
        expired_entry = CacheEntry(
            prefix=cache_manager.prefix,
            content="Expired content " * 100,
            token_count=500,
            created_at=time.time() - 7200,  # 2 hours old
            validate=False,
        )
        cache_manager.cache["expired"] = expired_entry

        # Valid entry
        valid_content = "Valid content " * 100
        cache_manager.store("valid", valid_content)

        # Run validation and auto-repair
        validator = CacheValidator(cache_manager=cache_manager)
        validation_result = await validator.validate_cache(
            ValidationLevel.COMPREHENSIVE
        )

        # Should find issues
        assert (
            validation_result.invalid_entries > 0
            or validation_result.expired_entries > 0
        )

        # Run auto-repair
        repair_summary = await validator.auto_repair_cache(validation_result)

        # Should have removed problematic entries
        assert repair_summary["entries_removed"] > 0
        assert "valid" in cache_manager.cache  # Valid entry should remain

    def test_cache_metrics_integration(self, cache_manager):
        """TEST: Cache metrics integration with validation"""
        # Add entries and access them
        for i in range(3):
            content = f"Content {i} " * 100
            cache_manager.store(f"query_{i}", content)

        # Access some entries to generate hit metrics
        cache_manager.get("query_0")
        cache_manager.get("query_1")
        cache_manager.get("nonexistent")  # Miss

        metrics = cache_manager.get_metrics()

        assert metrics.total_entries == 3
        assert metrics.cache_hits >= 2
        assert metrics.cache_misses >= 1
        assert metrics.hit_rate > 0

    @pytest.mark.asyncio
    async def test_database_integration_validation(self):
        """TEST: Database integration with cache validation"""
        # Create temporary database file
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_db:
            db_path = temp_db.name

        try:
            config = {
                "prefix": "db_test",
                "min_tokens": 100,  # Lower for testing
                "max_size": "1MB",
                "ttl_seconds": 3600,
                "database_path": db_path,
            }

            manager = CacheManager(
                {
                    "prefix": "db_test",
                    "min_tokens": 100,  # Lower for testing
                    "max_size": "1MB",
                    "ttl_seconds": 3600,
                    "hit_target_ms": 50,
                    "miss_target_ms": 150,
                }
            )

            # Add database-related cache entries
            sql_query = "SELECT * FROM financial_data WHERE quarter='Q1' " * 50
            manager.store("db_query_1", sql_query)

            # Create validator with database config
            validator = CacheValidator(cache_manager=manager, config=config)

            # Run database cache validation
            db_result = await validator.validate_database_cache_integrity()

            # Should handle database validation (even if DB doesn't exist)
            assert "database_validation" in db_result

        finally:
            # Cleanup
            if os.path.exists(db_path):
                os.unlink(db_path)

    @pytest.mark.asyncio
    async def test_comprehensive_security_scan(self, cache_manager):
        """TEST: Comprehensive security scanning of cache"""
        # Add entries with various security characteristics

        # Safe content
        safe_content = "Safe business content about financial analysis " * 50
        cache_manager.store("safe_query", safe_content)

        # Add entry with potential issues (bypassing security for test)
        with patch("src.cache.manager.validate_cache_content_security"):
            suspicious_content = "Content with api_key=secret123 " * 50
            cache_manager.store("suspicious_query", suspicious_content)

        # Create security validator and scan
        from src.cache.security import CacheSecurityValidator

        security_validator = CacheSecurityValidator()

        scan_results = []
        for entry_key, entry in cache_manager.cache.items():
            scan_result = security_validator.scan_content(entry.content)
            scan_results.append(scan_result)

        # Generate security report
        report = security_validator.generate_security_report(scan_results)

        assert report["total_scans"] >= 2
        assert report["total_content_scanned_bytes"] > 0
        assert "security_posture" in report

    def test_cache_manager_configuration_validation(self):
        """TEST: Cache manager validates configuration properly"""
        # Invalid configuration should raise error
        invalid_config = {
            "prefix": "123invalid",  # Invalid prefix
            "min_tokens": -1,  # Invalid min_tokens
            "max_size": "invalid",  # Invalid size format
        }

        with pytest.raises((CacheError, ConfigurationError, ValueError)):
            CacheManager(invalid_config)

    def test_cache_manager_thread_safety(self, cache_manager):
        """TEST: Cache manager thread safety with concurrent operations"""
        import threading
        import time

        results = []
        errors = []

        def store_content(thread_id):
            try:
                content = f"Thread {thread_id} content " * 100
                entry = cache_manager.store(f"thread_{thread_id}", content)
                results.append(entry)
            except Exception as e:
                errors.append(e)

        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=store_content, args=(i,))
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # Check results
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 5
        assert len(cache_manager.cache) >= 5

    @pytest.mark.asyncio
    async def test_performance_monitoring_integration(self, cache_manager):
        """TEST: Performance monitoring integration"""
        # Add entries and perform operations
        for i in range(10):
            content = f"Performance test content {i} " * 100
            start_time = time.perf_counter()
            cache_manager.store(f"perf_query_{i}", content)
            store_time = (time.perf_counter() - start_time) * 1000

            # Verify store time is reasonable (should be fast)
            assert store_time < 100  # Less than 100ms

        # Test retrieval performance
        for i in range(5):
            start_time = time.perf_counter()
            result = cache_manager.get(f"perf_query_{i}")
            get_time = (time.perf_counter() - start_time) * 1000

            assert result is not None
            assert get_time < 50  # Less than 50ms for cache hit

        # Get performance metrics
        metrics = cache_manager.get_metrics()

        assert metrics.total_entries == 10
        assert metrics.cache_hits >= 5
        assert metrics.hit_rate > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=src.cache", "--cov-report=term-missing"])
