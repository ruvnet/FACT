"""
Unit tests for cache mechanism in the FACT system.
Tests cache operations, performance targets, and cost optimization.
Following TDD principles - these tests will fail until implementation is complete.
"""

import pytest
import time
import json
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
from src.cache.manager import CacheManager, CacheEntry, CacheMetrics
from src.core.errors import CacheError, ConfigurationError


class TestCacheEntry:
    """Test suite for cache entry functionality."""

    def test_cache_entry_initialization_sets_proper_attributes(self):
        """TEST: Cache entry initialization sets proper attributes"""
        # Arrange
        prefix = "fact_v1"
        content = "A" * 500  # Minimum 500 tokens

        # Act
        entry = CacheEntry(prefix=prefix, content=content)

        # Assert
        assert entry.prefix == prefix
        assert entry.content == content
        assert entry.token_count >= 500
        assert entry.created_at is not None
        assert entry.version == "1.0"
        assert entry.is_valid == True
        assert entry.access_count == 0
        assert entry.last_accessed is None

    def test_cache_entry_calculates_token_count_accurately(self):
        """TEST: Cache entry calculates token count accurately"""
        # Arrange
        test_cases = [
            ("Hello world", 2),
            ("A" * 100, 100),  # Single character tokens
            ("The quick brown fox jumps over the lazy dog", 9),
            ("" * 1000, 0),  # Empty content
        ]

        # Act & Assert
        for content, expected_tokens in test_cases:
            entry = CacheEntry(
                prefix="test",
                content=content,
                skip_min_tokens=True,
                skip_content_validation=True,
            )
            # Allow for reasonable token counting variations
            assert abs(entry.token_count - expected_tokens) <= expected_tokens * 0.1

    def test_cache_entry_validates_minimum_token_requirement(self):
        """TEST: Cache entry validates minimum token requirement"""
        # Arrange
        short_content = "A" * 10  # Less than 500 tokens

        # Act & Assert
        with pytest.raises(CacheError) as exc_info:
            CacheEntry(prefix="test", content=short_content)

        assert "minimum 500 tokens" in str(exc_info.value)

    def test_cache_entry_tracks_access_patterns(self):
        """TEST: Cache entry tracks access patterns correctly"""
        # Arrange
        entry = CacheEntry(prefix="test", content="A" * 500)

        # Act
        entry.record_access()
        time.sleep(0.001)  # Small delay to ensure different timestamp
        entry.record_access()

        # Assert
        assert entry.access_count == 2
        assert entry.last_accessed is not None
        assert entry.last_accessed > entry.created_at

    def test_cache_entry_serialization_to_dict(self):
        """TEST: Cache entry serialization to dictionary format"""
        # Arrange
        entry = CacheEntry(
            prefix="test", content="Test content " * 100, skip_min_tokens=True
        )
        entry.record_access()

        # Act
        entry_dict = entry.to_dict()

        # Assert
        assert entry_dict["prefix"] == "test"
        assert entry_dict["content"] == "Test content " * 100
        assert entry_dict["token_count"] > 0
        assert entry_dict["access_count"] == 1
        assert "created_at" in entry_dict
        assert "last_accessed" in entry_dict


class TestCacheManager:
    """Test suite for cache manager functionality."""

    def test_cache_manager_initialization_loads_configuration(self, cache_config):
        """TEST: Cache manager initialization loads configuration"""
        # Act
        manager = CacheManager(config=cache_config)

        # Assert
        assert manager.prefix == cache_config["prefix"]
        assert manager.min_tokens == cache_config["min_tokens"]
        assert manager.max_size == cache_config["max_size"]
        assert manager.ttl_seconds == cache_config["ttl_seconds"]
        assert len(manager.cache) == 0

    def test_cache_manager_stores_entries_correctly(self, cache_config):
        """TEST: Cache manager stores cache entries correctly"""
        # Arrange
        manager = CacheManager(config=cache_config)
        content = "Sample cache content " * 50  # Ensure > 500 tokens
        query_hash = "test_query_hash_123"

        # Act
        entry = manager.store(query_hash, content)

        # Assert
        assert entry.prefix == cache_config["prefix"]
        assert entry.content == content
        assert query_hash in manager.cache
        assert manager.cache[query_hash] == entry

    def test_cache_manager_retrieves_entries_correctly(self, cache_config):
        """TEST: Cache manager retrieves cache entries correctly"""
        # Arrange
        manager = CacheManager(config=cache_config)
        content = "Retrievable content " * 50
        query_hash = "retrieve_test_hash"
        stored_entry = manager.store(query_hash, content)

        # Act
        retrieved_entry = manager.get(query_hash)

        # Assert
        assert retrieved_entry is not None
        assert retrieved_entry == stored_entry
        assert retrieved_entry.access_count == 1
        assert retrieved_entry.last_accessed is not None

    def test_cache_manager_handles_cache_misses(self, cache_config):
        """TEST: Cache manager handles cache misses gracefully"""
        # Arrange
        manager = CacheManager(config=cache_config)

        # Act
        result = manager.get("nonexistent_hash")

        # Assert
        assert result is None

    def test_cache_manager_enforces_size_limits(self, cache_config):
        """TEST: Cache manager enforces size limits"""
        # Arrange
        small_config = cache_config.copy()
        small_config["max_size"] = "1KB"  # Very small limit
        manager = CacheManager(config=small_config)

        # Act
        large_content = "X" * 2000  # 2KB content

        with pytest.raises(CacheError) as exc_info:
            manager.store("large_hash", large_content)

        # Assert
        assert "size limit" in str(exc_info.value).lower()

    def test_cache_manager_implements_ttl_expiration(self, cache_config):
        """TEST: Cache manager implements TTL expiration"""
        # Arrange
        short_ttl_config = cache_config.copy()
        short_ttl_config["ttl_seconds"] = 0.1  # 100ms TTL
        manager = CacheManager(config=short_ttl_config)

        content = "Expiring content " * 50
        query_hash = "expiring_hash"

        # Act
        manager.store(query_hash, content)
        time.sleep(0.2)  # Wait for expiration

        # Assert
        assert manager.get(query_hash) is None

    def test_cache_manager_invalidates_entries_by_prefix(self, cache_config):
        """TEST: Cache manager invalidates entries by prefix"""
        # Arrange
        manager = CacheManager(config=cache_config)

        # Store multiple entries
        for i in range(3):
            content = f"Content {i} " * 50
            manager.store(f"hash_{i}", content)

        # Act
        invalidated_count = manager.invalidate_by_prefix(cache_config["prefix"])

        # Assert
        assert invalidated_count == 3
        assert len(manager.cache) == 0

    def test_cache_manager_calculates_metrics_accurately(self, cache_config):
        """TEST: Cache manager calculates metrics accurately"""
        # Arrange
        manager = CacheManager(config=cache_config)

        # Create test scenario
        content = "Metrics test content " * 50
        manager.store("hash_1", content)
        manager.store("hash_2", content)

        # Access one entry to create hit/miss data
        manager.get("hash_1")
        manager.get("nonexistent")  # Miss

        # Act
        metrics = manager.get_metrics()

        # Assert
        assert isinstance(metrics, CacheMetrics)
        assert metrics.total_entries == 2
        assert metrics.total_requests >= 2
        assert metrics.hit_rate > 0
        assert metrics.miss_rate > 0
        assert metrics.total_size > 0


class TestCachePerformance:
    """Test suite for cache performance requirements."""

    @pytest.mark.performance
    def test_cache_hit_latency_under_50ms(self, cache_config, performance_timer):
        """TEST: Cache hits achieve target latency under 50ms"""
        # Arrange
        manager = CacheManager(config=cache_config)
        content = "Performance test content " * 100
        query_hash = "perf_test_hash"
        manager.store(query_hash, content)

        # Act
        with performance_timer() as timer:
            result = manager.get(query_hash)

        # Assert
        assert result is not None
        assert (
            timer.duration_ms < 50
        ), f"Cache hit took {timer.duration_ms}ms, exceeds 50ms target"

    @pytest.mark.performance
    def test_cache_storage_performance_under_10ms(
        self, cache_config, performance_timer
    ):
        """TEST: Cache storage operations complete under 10ms"""
        # Arrange
        manager = CacheManager(config=cache_config)
        content = "Storage performance test " * 100
        query_hash = "storage_perf_hash"

        # Act
        with performance_timer() as timer:
            entry = manager.store(query_hash, content)

        # Assert
        assert entry is not None
        assert (
            timer.duration_ms < 10
        ), f"Cache storage took {timer.duration_ms}ms, exceeds 10ms target"

    @pytest.mark.performance
    def test_concurrent_cache_access_performance(self, cache_config):
        """TEST: Concurrent cache access maintains performance"""
        # Arrange
        import asyncio

        manager = CacheManager(config=cache_config)

        # Pre-populate cache
        for i in range(10):
            content = f"Concurrent test content {i} " * 50
            manager.store(f"concurrent_hash_{i}", content)

        async def concurrent_access(hash_id):
            start_time = time.perf_counter()
            result = manager.get(f"concurrent_hash_{hash_id}")
            end_time = time.perf_counter()
            return result, (end_time - start_time) * 1000

        # Act
        async def run_concurrent_tests():
            tasks = [concurrent_access(i % 10) for i in range(50)]
            return await asyncio.gather(*tasks)

        results = asyncio.run(run_concurrent_tests())

        # Assert
        for result, latency_ms in results:
            assert result is not None
            assert latency_ms < 50, f"Concurrent access took {latency_ms}ms"

    @pytest.mark.performance
    def test_cache_memory_efficiency(self, cache_config):
        """TEST: Cache maintains memory efficiency"""
        # Arrange
        manager = CacheManager(config=cache_config)
        import sys

        # Measure baseline memory
        baseline_size = sys.getsizeof(manager)

        # Add many entries
        content = "Memory efficiency test " * 50
        for i in range(100):
            manager.store(f"memory_hash_{i}", content)

        # Act
        current_size = sys.getsizeof(manager)
        size_per_entry = (current_size - baseline_size) / 100

        # Assert
        # Each entry should be reasonably sized (less than 10KB overhead)
        assert (
            size_per_entry < 10240
        ), f"Cache overhead {size_per_entry} bytes per entry too high"


class TestCacheIntegration:
    """Test suite for cache integration with other components."""

    def test_cache_integration_with_anthropic_client(
        self, mock_anthropic_client, cache_config
    ):
        """TEST: Cache integrates properly with Anthropic client"""
        # Arrange
        manager = CacheManager(config=cache_config)
        query = "What is Q1-2025 revenue?"
        query_hash = manager.generate_hash(query)

        # Mock cached response
        cached_content = "Cached response: Q1-2025 revenue was $1,234,567.89"
        manager.store(query_hash, cached_content)

        # Act
        from src.cache.manager import get_cached_response

        with patch("src.cache.manager.cache_manager", manager):
            response = get_cached_response(query, mock_anthropic_client)

        # Assert
        assert response is not None
        assert "1,234,567.89" in response
        # Anthropic client should not be called for cache hit
        mock_anthropic_client.messages.create.assert_not_called()

    def test_cache_warming_improves_performance(self, cache_config, benchmark_queries):
        """TEST: Cache warming improves subsequent performance"""
        # Arrange
        manager = CacheManager(config=cache_config)

        # Act - Warm cache
        from src.cache.manager import warm_cache

        with patch("src.cache.manager.cache_manager", manager):
            warm_cache(benchmark_queries[:5])

        # Measure performance after warming
        warmed_times = []
        for query in benchmark_queries[:5]:
            start_time = time.perf_counter()
            query_hash = manager.generate_hash(query)
            result = manager.get(query_hash)
            end_time = time.perf_counter()

            if result:  # Cache hit
                warmed_times.append((end_time - start_time) * 1000)

        # Assert
        assert len(warmed_times) > 0, "Cache warming should create cached entries"
        avg_warmed_time = sum(warmed_times) / len(warmed_times)
        assert (
            avg_warmed_time < 50
        ), f"Warmed cache average {avg_warmed_time}ms exceeds target"

    def test_cache_invalidation_on_schema_changes(self, cache_config):
        """TEST: Cache invalidation occurs on schema changes"""
        # Arrange
        manager = CacheManager(config=cache_config)

        # Store entries with old schema version
        old_content = "Old schema content " * 50
        manager.store("schema_hash_1", old_content)
        manager.store("schema_hash_2", old_content)

        # Act - Simulate schema change
        from src.cache.manager import invalidate_on_schema_change

        with patch("src.cache.manager.cache_manager", manager):
            invalidated_count = invalidate_on_schema_change("Database schema updated")

        # Assert
        assert invalidated_count == 2
        assert manager.get("schema_hash_1") is None
        assert manager.get("schema_hash_2") is None


class TestCacheMetrics:
    """Test suite for cache metrics and monitoring."""

    def test_cache_metrics_calculation_accuracy(self, cache_config):
        """TEST: Cache metrics calculation is accurate"""
        # Arrange
        manager = CacheManager(config=cache_config)

        # Create test scenario
        content = "Metrics calculation test " * 50

        # Store 5 entries
        for i in range(5):
            manager.store(f"metrics_hash_{i}", content)

        # Access 3 entries (hits) and 2 non-existent (misses)
        for i in range(3):
            manager.get(f"metrics_hash_{i}")

        for i in range(2):
            manager.get(f"nonexistent_hash_{i}")

        # Act
        metrics = manager.get_metrics()

        # Assert
        assert metrics.total_entries == 5
        assert metrics.cache_hits == 3
        assert metrics.cache_misses == 2
        assert metrics.total_requests == 5
        assert abs(metrics.hit_rate - 60.0) < 0.1  # 3/5 = 60%
        assert abs(metrics.miss_rate - 40.0) < 0.1  # 2/5 = 40%

    def test_cache_metrics_cost_calculation(self, cache_config, performance_targets):
        """TEST: Cache metrics calculate cost savings accurately"""
        # Arrange
        manager = CacheManager(config=cache_config)
        content = "Cost calculation test " * 100

        # Store and access entries
        manager.store("cost_hash", content)
        manager.get("cost_hash")  # Hit
        manager.get("miss_hash")  # Miss

        # Act
        metrics = manager.get_metrics()

        # Assert
        assert hasattr(metrics, "cost_savings")
        assert hasattr(metrics, "token_efficiency")
        # Verify cost reduction meets targets
        expected_hit_savings = performance_targets["cost_reduction_cache_hit"]
        expected_miss_savings = performance_targets["cost_reduction_cache_miss"]

        assert metrics.cost_savings["cache_hit_reduction"] >= expected_hit_savings
        assert metrics.cost_savings["cache_miss_reduction"] >= expected_miss_savings

    def test_cache_metrics_export_to_json(self, cache_config):
        """TEST: Cache metrics export to JSON format"""
        # Arrange
        manager = CacheManager(config=cache_config)
        content = "JSON export test " * 50
        manager.store("json_hash", content)
        manager.get("json_hash")

        # Act
        metrics = manager.get_metrics()
        json_metrics = metrics.to_json()
        parsed_metrics = json.loads(json_metrics)

        # Assert
        assert "total_entries" in parsed_metrics
        assert "hit_rate" in parsed_metrics
        assert "miss_rate" in parsed_metrics
        assert "cost_savings" in parsed_metrics
        assert "timestamp" in parsed_metrics
        assert isinstance(parsed_metrics["total_entries"], int)
        assert isinstance(parsed_metrics["hit_rate"], float)


@pytest.mark.cache
class TestCacheEdgeCases:
    """Test suite for cache edge cases and error conditions."""

    def test_cache_handles_corrupted_entries(self, cache_config):
        """TEST: Cache handles corrupted entries gracefully"""
        # Arrange
        manager = CacheManager(config=cache_config)

        # Manually corrupt a cache entry
        corrupted_entry = CacheEntry(prefix="test", content="Valid content " * 50)
        corrupted_entry.content = None  # Corrupt the content
        manager.cache["corrupted_hash"] = corrupted_entry

        # Act
        result = manager.get("corrupted_hash")

        # Assert
        assert result is None  # Should handle corruption gracefully
        assert "corrupted_hash" not in manager.cache  # Should remove corrupted entry

    def test_cache_handles_memory_pressure(self, cache_config):
        """TEST: Cache handles memory pressure situations"""
        # Arrange
        tight_config = cache_config.copy()
        tight_config["max_size"] = "100KB"  # Small limit
        manager = CacheManager(config=tight_config)

        # Act - Try to store many large entries
        large_content = "X" * 1000  # 1KB each
        stored_count = 0

        for i in range(200):  # Try to store 200KB
            try:
                manager.store(f"pressure_hash_{i}", large_content)
                stored_count += 1
            except CacheError:
                break

        # Assert
        assert stored_count < 200  # Should hit limit before storing all
        assert stored_count > 0  # Should store some entries

        # Verify cache is still functional
        metrics = manager.get_metrics()
        assert metrics.total_entries == stored_count

    def test_cache_handles_concurrent_invalidation(self, cache_config):
        """TEST: Cache handles concurrent invalidation safely"""
        # Arrange
        import threading

        manager = CacheManager(config=cache_config)

        # Store test entries
        content = "Concurrent invalidation test " * 50
        for i in range(10):
            manager.store(f"concurrent_hash_{i}", content)

        # Act - Concurrent access and invalidation
        results = []

        def access_cache():
            for i in range(10):
                result = manager.get(f"concurrent_hash_{i}")
                results.append(result is not None)

        def invalidate_cache():
            manager.invalidate_by_prefix(cache_config["prefix"])

        access_thread = threading.Thread(target=access_cache)
        invalidate_thread = threading.Thread(target=invalidate_cache)

        access_thread.start()
        invalidate_thread.start()

        access_thread.join()
        invalidate_thread.join()

        # Assert
        # Should not crash, results may vary due to race conditions
        assert len(results) == 10
        assert len(manager.cache) == 0  # All entries should be invalidated
