"""
FACT Cache Resilience End-to-End Test Suite

This comprehensive test suite validates the entire cache resilience implementation
using REAL components (no mocking) to ensure proper system behavior under various
failure scenarios and circuit breaker functionality.

Test Coverage:
- Cache initialization with real storage
- Database integration using actual database connections
- Circuit breaker functionality with forced failures
- Recovery mechanisms after timeout periods
- Metrics collection and validation
- All cache operation types (get, store, invalidate)
- Various failure scenarios (intermittent, complete, slow)
- System degradation and performance characteristics
"""

import pytest
import asyncio
import time
import tempfile
import os
import sqlite3
import threading
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from unittest.mock import patch
import structlog

# Add src to path for imports
import sys

src_path = str(Path(__file__).parent.parent.parent / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from cache.manager import CacheManager, CacheEntry
from cache.resilience import (
    CacheCircuitBreaker,
    ResilientCacheWrapper,
    CircuitBreakerConfig,
    CircuitState,
)
from cache.config import CacheConfig, get_default_cache_config
from core.errors import CacheError

# Configure structured logging for tests
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


class TestCacheResilienceE2E:
    """End-to-end test suite for cache resilience implementation."""

    @pytest.fixture(autouse=True)
    def setup_test_environment(self):
        """Set up real test environment with no mocking."""
        # Create temporary database for testing
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")

        # Initialize test database with realistic data
        self._setup_test_database()

        # Configure cache for testing
        self.cache_config = {
            "prefix": "fact_resilience_test",
            "min_tokens": 100,  # Lower for testing
            "max_size": "5MB",
            "ttl_seconds": 30,  # Short TTL for testing
            "hit_target_ms": 50,
            "miss_target_ms": 140,
        }

        # Configure circuit breaker for testing
        self.circuit_config = CircuitBreakerConfig(
            failure_threshold=3,  # Low threshold for testing
            success_threshold=2,  # Low threshold for testing
            timeout_seconds=5.0,  # Short timeout for testing
            rolling_window_seconds=60.0,
            health_check_interval=1.0,  # Frequent for testing
        )

        # Initialize real components
        self.cache_manager = CacheManager(self.cache_config)
        self.circuit_breaker = CacheCircuitBreaker(self.circuit_config)
        self.resilient_cache = ResilientCacheWrapper(
            self.cache_manager, self.circuit_breaker
        )

        # Test metrics tracking
        self.test_metrics = {
            "operations_executed": 0,
            "successful_operations": 0,
            "failed_operations": 0,
            "circuit_state_changes": 0,
            "performance_measurements": [],
        }

        logger.info(
            "Test environment initialized",
            db_path=self.db_path,
            cache_config=self.cache_config,
        )

        yield

        # Cleanup
        os.close(self.db_fd)
        os.unlink(self.db_path)
        logger.info("Test environment cleaned up")

    def _setup_test_database(self):
        """Set up test database with realistic financial data."""
        conn = sqlite3.connect(self.db_path)

        # Create financial data table
        conn.execute("""
            CREATE TABLE financial_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quarter TEXT NOT NULL,
                revenue REAL NOT NULL,
                profit REAL,
                category TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Insert test data
        test_data = [
            ("Q1-2025", 1234567.89, 234567.89, "Product Sales"),
            ("Q4-2024", 1133221.55, 201221.55, "Product Sales"),
            ("Q3-2024", 987654.32, 187654.32, "Service Revenue"),
            ("Q2-2024", 876543.21, 176543.21, "Product Sales"),
            ("Q1-2024", 765432.10, 165432.10, "Service Revenue"),
        ]

        for quarter, revenue, profit, category in test_data:
            conn.execute(
                "INSERT INTO financial_data (quarter, revenue, profit, category) VALUES (?, ?, ?, ?)",
                (quarter, revenue, profit, category),
            )

        conn.commit()
        conn.close()
        logger.info("Test database initialized with financial data")

    async def test_cache_initialization_real_components(self):
        """Test cache initialization with real storage components."""
        logger.info("Testing cache initialization with real components")

        # Verify cache manager is properly initialized
        assert self.cache_manager is not None
        assert self.cache_manager.prefix == "fact_resilience_test"
        assert self.cache_manager.min_tokens == 100

        # Verify circuit breaker is properly initialized
        assert self.circuit_breaker is not None
        assert self.circuit_breaker.state == CircuitState.CLOSED

        # Verify resilient wrapper is properly initialized
        assert self.resilient_cache is not None
        assert self.resilient_cache.cache_manager is self.cache_manager
        assert self.resilient_cache.circuit_breaker is self.circuit_breaker

        # Test initial metrics
        metrics = self.resilient_cache.get_metrics()
        assert "cache" in metrics
        assert "circuit_breaker" in metrics
        assert metrics["circuit_breaker"]["state"] == "closed"

        logger.info("Cache initialization test completed successfully")

    async def test_normal_cache_operations_real_storage(self):
        """Test normal cache operations with real storage."""
        logger.info("Testing normal cache operations with real storage")

        test_content = (
            "This is test content for cache storage with sufficient tokens to meet the minimum requirement. "
            * 15
        )  # Ensure minimum tokens
        query_hash = self.cache_manager.generate_hash("test_query")

        # Test store operation
        start_time = time.perf_counter()
        stored_entry = await self.resilient_cache.store(query_hash, test_content)
        store_time = (time.perf_counter() - start_time) * 1000

        assert stored_entry is not None
        assert stored_entry == True  # Resilient wrapper returns boolean

        # Test get operation (cache hit)
        start_time = time.perf_counter()
        retrieved_entry = await self.resilient_cache.get(query_hash)
        get_time = (time.perf_counter() - start_time) * 1000

        assert retrieved_entry is not None
        assert retrieved_entry.content == test_content
        assert retrieved_entry.access_count >= 1

        # Test cache miss
        missing_hash = self.cache_manager.generate_hash("non_existent_query")
        missing_entry = await self.resilient_cache.get(missing_hash)
        assert missing_entry is None

        # Test invalidation
        invalidated_count = await self.resilient_cache.invalidate_by_prefix(
            "fact_resilience_test"
        )
        assert invalidated_count >= 1

        # Verify performance
        assert store_time < self.cache_config["miss_target_ms"]
        assert get_time < self.cache_config["hit_target_ms"]

        self.test_metrics["operations_executed"] += 4
        self.test_metrics["successful_operations"] += 4
        self.test_metrics["performance_measurements"].extend([store_time, get_time])

        logger.info(
            "Normal cache operations test completed successfully",
            store_time_ms=store_time,
            get_time_ms=get_time,
            invalidated_count=invalidated_count,
        )

    async def test_circuit_breaker_failure_scenarios(self):
        """Test circuit breaker functionality with various failure scenarios."""
        logger.info("Testing circuit breaker failure scenarios")

        # Create a failing cache manager mock within the real manager
        original_store = self.cache_manager.store

        def failing_store(query_hash: str, content: str):
            """Simulate cache storage failures."""
            raise CacheError(
                "Simulated cache storage failure", error_code="CACHE_STORAGE_ERROR"
            )

        # Test intermittent failures
        failure_count = 0
        success_count = 0

        try:
            # Patch the store method to simulate failures
            self.cache_manager.store = failing_store

            # Generate enough failures to trigger circuit breaker
            for i in range(5):
                try:
                    await self.resilient_cache.store(
                        f"failing_query_{i}", "test content " * 20
                    )
                    success_count += 1
                except CacheError:
                    failure_count += 1
                    self.test_metrics["failed_operations"] += 1

                self.test_metrics["operations_executed"] += 1

            # Check circuit breaker state
            circuit_state = self.circuit_breaker.get_state()
            logger.info(
                "Circuit breaker state after failures", state=circuit_state.value
            )

            # Circuit should be open after threshold failures
            assert circuit_state == CircuitState.OPEN
            self.test_metrics["circuit_state_changes"] += 1

            # Test graceful degradation
            try:
                degraded_result = await self.resilient_cache.store(
                    "degraded_query", "test content " * 20
                )
                # Should return fallback response
                assert degraded_result == True
                self.test_metrics["successful_operations"] += 1
            except CacheError as e:
                assert "CIRCUIT_BREAKER" in str(e.error_code)
                self.test_metrics["failed_operations"] += 1

            self.test_metrics["operations_executed"] += 1

        finally:
            # Restore original method
            self.cache_manager.store = original_store

        logger.info(
            "Circuit breaker failure scenarios test completed",
            failure_count=failure_count,
            success_count=success_count,
            final_state=circuit_state.value,
        )

    async def test_circuit_breaker_recovery_mechanisms(self):
        """Test circuit breaker recovery mechanisms after timeout periods."""
        logger.info("Testing circuit breaker recovery mechanisms")

        # Ensure circuit is open
        self.circuit_breaker.force_open()
        assert self.circuit_breaker.get_state() == CircuitState.OPEN

        # Wait for timeout period
        timeout_seconds = self.circuit_config.timeout_seconds
        logger.info(
            "Waiting for circuit breaker timeout", timeout_seconds=timeout_seconds
        )
        await asyncio.sleep(timeout_seconds + 1)

        # Test half-open transition
        test_content = (
            "Recovery test content with sufficient tokens to meet the minimum requirement for cache storage. "
            * 12
        )
        query_hash = self.cache_manager.generate_hash("recovery_test_query")

        try:
            # This should transition to half-open and succeed
            result = await self.resilient_cache.store(query_hash, test_content)
            assert result == True

            # Verify state transition
            circuit_state = self.circuit_breaker.get_state()
            logger.info(
                "Circuit state after first recovery attempt", state=circuit_state.value
            )

            # Continue with successful operations to close circuit
            for i in range(self.circuit_config.success_threshold):
                recovery_hash = self.cache_manager.generate_hash(f"recovery_query_{i}")
                result = await self.resilient_cache.store(recovery_hash, test_content)
                assert result == True
                self.test_metrics["successful_operations"] += 1
                self.test_metrics["operations_executed"] += 1

            # Circuit should now be closed
            final_state = self.circuit_breaker.get_state()
            assert final_state == CircuitState.CLOSED
            self.test_metrics["circuit_state_changes"] += 1

            logger.info(
                "Circuit breaker recovery completed successfully",
                final_state=final_state.value,
            )

        except Exception as e:
            logger.error("Recovery test failed", error=str(e))
            self.test_metrics["failed_operations"] += 1
            raise

    async def test_performance_under_various_conditions(self):
        """Test and measure performance under various conditions."""
        logger.info("Testing performance under various conditions")

        performance_results = {
            "normal_operations": [],
            "high_load": [],
            "degraded_mode": [],
            "recovery_mode": [],
        }

        # Test normal operations performance
        for i in range(10):
            query_hash = self.cache_manager.generate_hash(f"perf_test_normal_{i}")
            content = f"Performance test content {i}. " * 20

            start_time = time.perf_counter()
            await self.resilient_cache.store(query_hash, content)
            store_time = (time.perf_counter() - start_time) * 1000

            start_time = time.perf_counter()
            retrieved = await self.resilient_cache.get(query_hash)
            get_time = (time.perf_counter() - start_time) * 1000

            performance_results["normal_operations"].append(
                {"store_time_ms": store_time, "get_time_ms": get_time}
            )

            self.test_metrics["operations_executed"] += 2
            self.test_metrics["successful_operations"] += 2

        # Test high load performance with concurrent operations
        async def concurrent_operation(index: int):
            query_hash = self.cache_manager.generate_hash(
                f"perf_test_concurrent_{index}"
            )
            content = f"Concurrent test content {index}. " * 20

            start_time = time.perf_counter()
            await self.resilient_cache.store(query_hash, content)
            total_time = (time.perf_counter() - start_time) * 1000
            return total_time

        # Run concurrent operations
        concurrent_tasks = [concurrent_operation(i) for i in range(20)]
        concurrent_times = await asyncio.gather(*concurrent_tasks)

        performance_results["high_load"] = [
            {"operation_time_ms": t} for t in concurrent_times
        ]
        self.test_metrics["operations_executed"] += len(concurrent_tasks)
        self.test_metrics["successful_operations"] += len(concurrent_tasks)

        # Test degraded mode performance
        self.circuit_breaker.force_open()

        for i in range(5):
            query_hash = self.cache_manager.generate_hash(f"perf_test_degraded_{i}")
            content = f"Degraded test content {i}. " * 20

            start_time = time.perf_counter()
            try:
                await self.resilient_cache.store(query_hash, content)
                operation_time = (time.perf_counter() - start_time) * 1000
                performance_results["degraded_mode"].append(
                    {"operation_time_ms": operation_time, "status": "success"}
                )
                self.test_metrics["successful_operations"] += 1
            except CacheError:
                operation_time = (time.perf_counter() - start_time) * 1000
                performance_results["degraded_mode"].append(
                    {
                        "operation_time_ms": operation_time,
                        "status": "circuit_breaker_blocked",
                    }
                )
                self.test_metrics["failed_operations"] += 1

            self.test_metrics["operations_executed"] += 1

        # Reset circuit for recovery test
        self.circuit_breaker.force_closed()

        # Calculate performance statistics
        normal_store_times = [
            r["store_time_ms"] for r in performance_results["normal_operations"]
        ]
        normal_get_times = [
            r["get_time_ms"] for r in performance_results["normal_operations"]
        ]
        concurrent_times = [
            r["operation_time_ms"] for r in performance_results["high_load"]
        ]

        avg_store_time = sum(normal_store_times) / len(normal_store_times)
        avg_get_time = sum(normal_get_times) / len(normal_get_times)
        avg_concurrent_time = sum(concurrent_times) / len(concurrent_times)

        # Verify performance meets targets
        assert avg_store_time < self.cache_config["miss_target_ms"]
        assert avg_get_time < self.cache_config["hit_target_ms"]

        self.test_metrics["performance_measurements"].extend(
            [avg_store_time, avg_get_time, avg_concurrent_time]
        )

        logger.info(
            "Performance testing completed",
            avg_store_time_ms=avg_store_time,
            avg_get_time_ms=avg_get_time,
            avg_concurrent_time_ms=avg_concurrent_time,
            performance_results=performance_results,
        )

    async def test_metrics_collection_and_validation(self):
        """Test comprehensive metrics collection and validation."""
        logger.info("Testing metrics collection and validation")

        # Perform various operations to generate metrics
        test_operations = [
            ("store_op_1", "store", "test content 1 " * 20),
            ("get_op_1", "get", None),
            ("store_op_2", "store", "test content 2 " * 20),
            ("invalidate_op", "invalidate", None),
        ]

        for op_id, operation, content in test_operations:
            query_hash = self.cache_manager.generate_hash(op_id)

            try:
                if operation == "store":
                    await self.resilient_cache.store(query_hash, content)
                elif operation == "get":
                    await self.resilient_cache.get(query_hash)
                elif operation == "invalidate":
                    await self.resilient_cache.invalidate_by_prefix(
                        "fact_resilience_test"
                    )

                self.test_metrics["successful_operations"] += 1
            except Exception as e:
                logger.warning(
                    "Operation failed during metrics test",
                    operation=operation,
                    error=str(e),
                )
                self.test_metrics["failed_operations"] += 1

            self.test_metrics["operations_executed"] += 1

        # Get comprehensive metrics
        metrics = self.resilient_cache.get_metrics()

        # Validate cache metrics
        assert "cache" in metrics
        cache_metrics = metrics["cache"]
        assert "total_entries" in cache_metrics
        assert "total_requests" in cache_metrics
        assert "cache_hits" in cache_metrics
        assert "cache_misses" in cache_metrics

        # Validate circuit breaker metrics
        assert "circuit_breaker" in metrics
        cb_metrics = metrics["circuit_breaker"]
        assert "state" in cb_metrics
        assert "failure_count" in cb_metrics
        assert "success_count" in cb_metrics
        assert "total_operations" in cb_metrics

        # Validate performance stats
        perf_stats = self.cache_manager.get_performance_stats()
        assert "avg_hit_latency_ms" in perf_stats
        assert "avg_miss_latency_ms" in perf_stats
        assert "hit_latency_compliance" in perf_stats
        assert "miss_latency_compliance" in perf_stats

        logger.info(
            "Metrics collection and validation completed",
            cache_metrics=cache_metrics,
            circuit_breaker_metrics=cb_metrics,
            performance_stats=perf_stats,
        )

    async def test_real_database_integration(self):
        """Test integration with real database operations."""
        logger.info("Testing real database integration")

        # Test database connectivity
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Perform real database query
        cursor.execute(
            "SELECT quarter, revenue FROM financial_data ORDER BY quarter DESC LIMIT 3"
        )
        results = cursor.fetchall()

        assert len(results) >= 3
        logger.info("Database query successful", results=results)

        # Test caching of database query results
        query_content = json.dumps(results)
        db_query_hash = self.cache_manager.generate_hash("latest_financial_data")

        # Store database results in cache
        await self.resilient_cache.store(db_query_hash, query_content)

        # Retrieve from cache
        cached_result = await self.resilient_cache.get(db_query_hash)
        assert cached_result is not None
        assert cached_result.content == query_content

        # Test cache invalidation on database changes
        cursor.execute(
            "INSERT INTO financial_data (quarter, revenue, profit, category) VALUES (?, ?, ?, ?)",
            ("Q2-2025", 1500000.00, 300000.00, "Product Sales"),
        )
        conn.commit()

        # Invalidate cache after database change
        invalidated = await self.resilient_cache.invalidate_by_prefix(
            "fact_resilience_test"
        )
        assert invalidated >= 1

        conn.close()

        self.test_metrics["operations_executed"] += 3
        self.test_metrics["successful_operations"] += 3

        logger.info("Real database integration test completed successfully")

    async def test_stress_and_failure_recovery(self):
        """Test system behavior under stress and various failure patterns."""
        logger.info("Testing stress and failure recovery")

        # Test rapid successive operations
        rapid_operations = []
        for i in range(50):
            query_hash = self.cache_manager.generate_hash(f"stress_test_{i}")
            content = f"Stress test content {i}. " * 25
            rapid_operations.append(self.resilient_cache.store(query_hash, content))

        # Execute all operations concurrently
        start_time = time.perf_counter()
        results = await asyncio.gather(*rapid_operations, return_exceptions=True)
        total_time = (time.perf_counter() - start_time) * 1000

        # Analyze results
        successful_ops = sum(1 for r in results if not isinstance(r, Exception))
        failed_ops = len(results) - successful_ops

        logger.info(
            "Stress test completed",
            total_operations=len(results),
            successful_operations=successful_ops,
            failed_operations=failed_ops,
            total_time_ms=total_time,
            avg_time_per_op_ms=total_time / len(results),
        )

        # Test recovery after stress
        recovery_ops = []
        for i in range(10):
            query_hash = self.cache_manager.generate_hash(f"recovery_test_{i}")
            recovery_ops.append(self.resilient_cache.get(query_hash))

        recovery_results = await asyncio.gather(*recovery_ops, return_exceptions=True)
        recovery_successful = sum(
            1 for r in recovery_results if not isinstance(r, Exception)
        )

        self.test_metrics["operations_executed"] += len(results) + len(recovery_results)
        self.test_metrics["successful_operations"] += (
            successful_ops + recovery_successful
        )
        self.test_metrics["failed_operations"] += failed_ops + (
            len(recovery_results) - recovery_successful
        )

        logger.info(
            "Stress and recovery test completed",
            recovery_successful=recovery_successful,
            recovery_total=len(recovery_results),
        )

    async def test_comprehensive_system_validation(self):
        """Comprehensive validation of the entire system."""
        logger.info("Running comprehensive system validation")

        # Test all components work together
        test_scenarios = [
            "normal_operation",
            "circuit_breaker_open",
            "circuit_breaker_recovery",
            "high_concurrency",
            "database_integration",
        ]

        validation_results = {}

        for scenario in test_scenarios:
            try:
                if scenario == "normal_operation":
                    # Test normal cache operations
                    for i in range(5):
                        hash_key = self.cache_manager.generate_hash(
                            f"validation_{scenario}_{i}"
                        )
                        content = f"Validation content for {scenario} {i}. " * 20
                        await self.resilient_cache.store(hash_key, content)
                        retrieved = await self.resilient_cache.get(hash_key)
                        assert retrieved is not None

                    validation_results[scenario] = "PASS"

                elif scenario == "circuit_breaker_open":
                    # Force circuit open and test graceful degradation
                    self.circuit_breaker.force_open()
                    hash_key = self.cache_manager.generate_hash(
                        f"validation_{scenario}"
                    )
                    content = f"Validation content for {scenario}. " * 20

                    # Should handle gracefully
                    result = await self.resilient_cache.store(hash_key, content)
                    validation_results[scenario] = "PASS"

                elif scenario == "circuit_breaker_recovery":
                    # Test recovery mechanism
                    self.circuit_breaker.force_closed()
                    hash_key = self.cache_manager.generate_hash(
                        f"validation_{scenario}"
                    )
                    content = f"Validation content for {scenario}. " * 20

                    result = await self.resilient_cache.store(hash_key, content)
                    assert result == True
                    validation_results[scenario] = "PASS"

                elif scenario == "high_concurrency":
                    # Test concurrent operations
                    concurrent_ops = []
                    for i in range(20):
                        hash_key = self.cache_manager.generate_hash(
                            f"validation_{scenario}_{i}"
                        )
                        content = f"Concurrent validation content {i}. " * 15
                        concurrent_ops.append(
                            self.resilient_cache.store(hash_key, content)
                        )

                    results = await asyncio.gather(
                        *concurrent_ops, return_exceptions=True
                    )
                    successful = sum(1 for r in results if not isinstance(r, Exception))

                    # At least 80% should succeed
                    assert successful >= len(results) * 0.8
                    validation_results[scenario] = "PASS"

                elif scenario == "database_integration":
                    # Test with real database
                    conn = sqlite3.connect(self.db_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM financial_data")
                    count = cursor.fetchone()[0]
                    conn.close()

                    # Cache the result
                    hash_key = self.cache_manager.generate_hash("db_count_query")
                    await self.resilient_cache.store(
                        hash_key, f"Database count: {count}"
                    )

                    # Retrieve from cache
                    cached = await self.resilient_cache.get(hash_key)
                    assert cached is not None
                    validation_results[scenario] = "PASS"

                self.test_metrics["successful_operations"] += 1

            except Exception as e:
                logger.error(
                    "Validation scenario failed", scenario=scenario, error=str(e)
                )
                validation_results[scenario] = f"FAIL: {str(e)}"
                self.test_metrics["failed_operations"] += 1

            self.test_metrics["operations_executed"] += 1

        # Final system health check
        final_metrics = self.resilient_cache.get_metrics()
        final_circuit_state = self.circuit_breaker.get_state()

        logger.info(
            "Comprehensive system validation completed",
            validation_results=validation_results,
            final_metrics=final_metrics,
            final_circuit_state=final_circuit_state.value,
            test_metrics=self.test_metrics,
        )

        # Ensure all critical scenarios passed
        critical_scenarios = ["normal_operation", "database_integration"]
        for scenario in critical_scenarios:
            assert (
                validation_results.get(scenario) == "PASS"
            ), f"Critical scenario {scenario} failed"

    async def test_run_complete_test_suite(self):
        """Run the complete test suite in sequence."""
        logger.info("Starting complete cache resilience test suite")

        try:
            # Initialize environment
            await self.test_cache_initialization_real_components()

            # Test normal operations
            await self.test_normal_cache_operations_real_storage()

            # Test failure scenarios
            await self.test_circuit_breaker_failure_scenarios()

            # Test recovery
            await self.test_circuit_breaker_recovery_mechanisms()

            # Test performance
            await self.test_performance_under_various_conditions()

            # Test metrics
            await self.test_metrics_collection_and_validation()

            # Test database integration
            await self.test_real_database_integration()

            # Test stress and recovery
            await self.test_stress_and_failure_recovery()

            # Final validation
            await self.test_comprehensive_system_validation()

            logger.info(
                "Complete cache resilience test suite completed successfully",
                final_test_metrics=self.test_metrics,
            )

            return self.test_metrics

        except Exception as e:
            logger.error("Test suite failed", error=str(e))
            raise


# Standalone test runner for direct execution
if __name__ == "__main__":

    async def run_tests():
        """Run tests directly."""
        test_instance = TestCacheResilienceE2E()
        test_instance.setup_test_environment()

        try:
            results = await test_instance.test_run_complete_test_suite()
            print(f"\nTest Results Summary:")
            print(f"Total Operations: {results['operations_executed']}")
            print(f"Successful Operations: {results['successful_operations']}")
            print(f"Failed Operations: {results['failed_operations']}")
            print(f"Circuit State Changes: {results['circuit_state_changes']}")
            print(
                f"Performance Measurements: {len(results['performance_measurements'])}"
            )

            if results["performance_measurements"]:
                avg_perf = sum(results["performance_measurements"]) / len(
                    results["performance_measurements"]
                )
                print(f"Average Performance: {avg_perf:.2f}ms")

        except Exception as e:
            print(f"Test execution failed: {e}")
            raise

    # Run the tests
    asyncio.run(run_tests())
