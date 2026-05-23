#!/usr/bin/env python3
"""
Test script for cache resilience and circuit breaker functionality.

This script demonstrates how the circuit breaker pattern prevents cascading
failures when cache operations fail, and how graceful degradation ensures
the system continues to function.
"""

import asyncio
import time
import sys
import os
from pathlib import Path
from typing import Dict, Any

# Add src to path for imports
src_path = str(Path(__file__).parent.parent / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from cache.resilience import (
    CacheCircuitBreaker,
    CircuitBreakerConfig,
    ResilientCacheWrapper,
    CircuitState,
    FailureRecord,
)
from cache.manager import CacheManager
from core.errors import CacheError
import structlog

# Configure logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="ISO"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.PrintLoggerFactory(),
    wrapper_class=structlog.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


class FailingCacheManager:
    """Mock cache manager that can be configured to fail."""

    def __init__(self, failure_rate: float = 0.0, failure_after: int = 0):
        """
        Initialize failing cache manager.

        Args:
            failure_rate: Probability of failure (0.0 = never fail, 1.0 = always fail)
            failure_after: Fail after this many successful operations
        """
        self.failure_rate = failure_rate
        self.failure_after = failure_after
        self.operation_count = 0
        self.cache = {}

    def set_failure_rate(self, rate: float):
        """Set new failure rate."""
        self.failure_rate = rate
        logger.info("Cache failure rate changed", rate=rate)

    def set_failure_after(self, count: int):
        """Set to fail after specific number of operations."""
        self.failure_after = count
        self.operation_count = 0
        logger.info("Cache set to fail after operations", count=count)

    def _should_fail(self) -> bool:
        """Determine if this operation should fail."""
        self.operation_count += 1

        if self.failure_after > 0 and self.operation_count > self.failure_after:
            return True

        import random

        return random.random() < self.failure_rate

    async def store(self, query_hash: str, content: str):
        """Store with potential failure."""
        if self._should_fail():
            raise CacheError(
                "Simulated cache store failure", error_code="CACHE_STORE_FAILED"
            )

        self.cache[query_hash] = {"content": content, "timestamp": time.time()}
        return True

    async def get(self, query_hash: str):
        """Get with potential failure."""
        if self._should_fail():
            raise CacheError(
                "Simulated cache get failure", error_code="CACHE_GET_FAILED"
            )

        if query_hash in self.cache:
            return type(
                "CacheEntry",
                (),
                {
                    "content": self.cache[query_hash]["content"],
                    "timestamp": self.cache[query_hash]["timestamp"],
                },
            )()
        return None

    async def invalidate_by_prefix(self, prefix: str) -> int:
        """Invalidate with potential failure."""
        if self._should_fail():
            raise CacheError(
                "Simulated cache invalidate failure",
                error_code="CACHE_INVALIDATE_FAILED",
            )

        # Simulate invalidation
        return len(self.cache)

    def generate_hash(self, query: str) -> str:
        """Generate hash (no failure simulation for local operation)."""
        import hashlib

        return hashlib.sha256(query.encode()).hexdigest()


async def test_circuit_breaker_states():
    """Test circuit breaker state transitions."""
    logger.info("=== Testing Circuit Breaker State Transitions ===")

    # Configure circuit breaker for fast testing
    config = CircuitBreakerConfig(
        failure_threshold=3,  # Open after 3 failures
        success_threshold=2,  # Close after 2 successes
        timeout_seconds=2.0,  # Fast timeout for testing
        rolling_window_seconds=60.0,
        gradual_recovery=True,
        recovery_factor=0.5,
    )

    circuit_breaker = CacheCircuitBreaker(config)
    failing_cache = FailingCacheManager(failure_rate=0.0)  # Start with no failures
    resilient_cache = ResilientCacheWrapper(failing_cache, circuit_breaker)

    # Test normal operation (CLOSED state)
    logger.info("Testing CLOSED state - normal operations")
    assert circuit_breaker.get_state() == CircuitState.CLOSED

    for i in range(3):
        result = await resilient_cache.store(f"test_key_{i}", f"test_content_{i}")
        assert result == True

    metrics = circuit_breaker.get_metrics()
    logger.info(
        "CLOSED state metrics",
        state=metrics.state.value,
        success_count=metrics.success_count,
        failure_count=metrics.failure_count,
    )

    # Introduce failures to trigger OPEN state
    logger.info("Introducing failures to trigger OPEN state")
    failing_cache.set_failure_rate(1.0)  # 100% failure rate

    failure_count = 0
    for i in range(5):
        try:
            await resilient_cache.store(f"fail_key_{i}", f"fail_content_{i}")
        except CacheError as e:
            failure_count += 1
            if "CIRCUIT_BREAKER_OPEN" in str(e.error_code):
                logger.info("Circuit breaker opened successfully")
                break

    assert circuit_breaker.get_state() == CircuitState.OPEN

    # Test that operations use graceful degradation when OPEN
    logger.info("Testing OPEN state - operations should use graceful degradation")

    # With graceful degradation enabled, operations should return fallback values
    result = await resilient_cache.get("test_key")
    assert result is None, "Expected fallback response (None) from graceful degradation"

    # Test store operation also returns fallback
    result = await resilient_cache.store("test_key", "test_content")
    assert result == True, "Expected fallback response (True) from graceful degradation"

    # Disable graceful degradation to test actual circuit breaker exceptions
    resilient_cache.enable_graceful_degradation = False

    try:
        await resilient_cache.get("test_key")
        assert (
            False
        ), "Expected circuit breaker to raise exception when graceful degradation disabled"
    except CacheError as e:
        assert "CIRCUIT_BREAKER_OPEN" in str(e.error_code)
        logger.info(
            "Circuit breaker correctly raised exception when graceful degradation disabled"
        )

    # Re-enable graceful degradation for remaining tests
    resilient_cache.enable_graceful_degradation = True

    # Wait for timeout and test HALF_OPEN transition
    logger.info("Waiting for timeout to test HALF_OPEN transition")
    await asyncio.sleep(2.5)  # Wait longer than timeout

    # Fix the cache and try operation to trigger HALF_OPEN
    failing_cache.set_failure_rate(0.0)  # Fix the cache

    # This should transition to HALF_OPEN and succeed
    result = await resilient_cache.store("recovery_test", "recovery_content")
    assert result == True

    # Circuit should be HALF_OPEN or CLOSED now
    state = circuit_breaker.get_state()
    logger.info("State after recovery attempt", state=state.value)

    # Continue with successful operations to close circuit
    for i in range(3):
        await resilient_cache.store(f"recovery_key_{i}", f"recovery_content_{i}")

    final_state = circuit_breaker.get_state()
    logger.info("Final state after recovery", state=final_state.value)

    metrics = circuit_breaker.get_metrics()
    logger.info(
        "Final metrics",
        state=metrics.state.value,
        success_count=metrics.success_count,
        failure_count=metrics.failure_count,
        failure_rate=metrics.failure_rate,
        state_changes=metrics.state_changes,
    )

    logger.info("✅ Circuit breaker state transitions test passed")


async def test_graceful_degradation():
    """Test graceful degradation when cache fails."""
    logger.info("=== Testing Graceful Degradation ===")

    # Configure circuit breaker
    config = CircuitBreakerConfig(
        failure_threshold=2,
        success_threshold=2,
        timeout_seconds=1.0,
        gradual_recovery=True,
    )

    circuit_breaker = CacheCircuitBreaker(config)
    failing_cache = FailingCacheManager(failure_rate=1.0)  # Always fail
    resilient_cache = ResilientCacheWrapper(failing_cache, circuit_breaker)

    # Enable graceful degradation
    resilient_cache.enable_graceful_degradation = True

    # First, trigger circuit breaker to open
    logger.info("Triggering circuit breaker to open state")

    for i in range(3):  # Exceed failure threshold
        try:
            await resilient_cache.store(f"fail_key_{i}", "content")
        except CacheError:
            pass  # Expected failures

    # Verify circuit is open
    assert circuit_breaker.get_state() == CircuitState.OPEN
    logger.info("Circuit breaker is now OPEN")

    logger.info("Testing cache operations with graceful degradation")

    # Test store operation - should return graceful response
    result = await resilient_cache.store("test_key", "test_content")
    logger.info("Store operation result", result=result)
    assert result == True  # Graceful fallback

    # Test get operation - should return None (cache miss)
    result = await resilient_cache.get("test_key")
    logger.info("Get operation result", result=result)
    assert result is None

    # Test invalidate operation - should return 0
    result = await resilient_cache.invalidate_by_prefix("test_")
    logger.info("Invalidate operation result", result=result)
    assert result == 0

    # Check circuit breaker state
    state = circuit_breaker.get_state()
    logger.info("Circuit breaker state", state=state.value)

    logger.info("✅ Graceful degradation test passed")


async def test_performance_under_failures():
    """Test performance characteristics under various failure scenarios."""
    logger.info("=== Testing Performance Under Failures ===")

    config = CircuitBreakerConfig(
        failure_threshold=5, success_threshold=3, timeout_seconds=1.0
    )

    circuit_breaker = CacheCircuitBreaker(config)
    failing_cache = FailingCacheManager(failure_rate=0.3)  # 30% failure rate
    resilient_cache = ResilientCacheWrapper(failing_cache, circuit_breaker)

    # Test with mixed success/failure pattern
    operation_count = 50
    success_count = 0
    failure_count = 0
    total_time = 0

    logger.info("Running performance test with 30% failure rate")

    for i in range(operation_count):
        start_time = time.time()
        try:
            await resilient_cache.store(f"perf_key_{i}", f"perf_content_{i}")
            success_count += 1
        except CacheError:
            failure_count += 1

        end_time = time.time()
        total_time += end_time - start_time

    avg_latency = (total_time / operation_count) * 1000  # Convert to ms

    metrics = circuit_breaker.get_metrics()

    logger.info(
        "Performance test results",
        total_operations=operation_count,
        successes=success_count,
        failures=failure_count,
        avg_latency_ms=avg_latency,
        circuit_state=metrics.state.value,
        circuit_failure_rate=metrics.failure_rate,
        state_changes=metrics.state_changes,
    )

    logger.info("✅ Performance test completed")


async def test_circuit_breaker_metrics():
    """Test circuit breaker metrics collection."""
    logger.info("=== Testing Circuit Breaker Metrics ===")

    config = CircuitBreakerConfig(
        failure_threshold=3, success_threshold=2, timeout_seconds=1.0
    )

    circuit_breaker = CacheCircuitBreaker(config)
    failing_cache = FailingCacheManager()
    resilient_cache = ResilientCacheWrapper(failing_cache, circuit_breaker)

    # Generate some operations
    logger.info("Generating operations for metrics")

    # Successful operations
    for i in range(5):
        await resilient_cache.store(f"metrics_key_{i}", f"metrics_content_{i}")

    # Failed operations
    failing_cache.set_failure_rate(1.0)
    for i in range(3):
        try:
            await resilient_cache.store(f"fail_key_{i}", f"fail_content_{i}")
        except CacheError:
            pass

    # Get comprehensive metrics
    metrics = circuit_breaker.get_metrics()
    cache_metrics = resilient_cache.get_metrics()

    logger.info(
        "Circuit breaker metrics",
        state=metrics.state.value,
        total_operations=metrics.total_operations,
        success_count=metrics.success_count,
        failure_count=metrics.failure_count,
        failure_rate=metrics.failure_rate,
        state_changes=metrics.state_changes,
        recent_failures_count=len(metrics.recent_failures),
    )

    logger.info(
        "Combined metrics structure", cache_metrics_keys=list(cache_metrics.keys())
    )

    logger.info("✅ Metrics test completed")


async def test_recovery_scenarios():
    """Test various recovery scenarios."""
    logger.info("=== Testing Recovery Scenarios ===")

    config = CircuitBreakerConfig(
        failure_threshold=2,
        success_threshold=3,
        timeout_seconds=1.0,
        gradual_recovery=True,
        recovery_factor=0.5,
    )

    circuit_breaker = CacheCircuitBreaker(config)
    failing_cache = FailingCacheManager()
    resilient_cache = ResilientCacheWrapper(failing_cache, circuit_breaker)

    # Test scenario 1: Complete failure and recovery
    logger.info("Scenario 1: Complete failure and recovery")

    # Cause circuit to open
    failing_cache.set_failure_rate(1.0)
    for i in range(3):
        try:
            await resilient_cache.store(f"fail_{i}", "content")
        except CacheError:
            pass

    assert circuit_breaker.get_state() == CircuitState.OPEN
    logger.info("Circuit opened successfully")

    # Wait for timeout
    await asyncio.sleep(1.5)

    # Fix cache and recover
    failing_cache.set_failure_rate(0.0)

    # Gradual recovery
    recovery_attempts = 10
    success_count = 0
    for i in range(recovery_attempts):
        try:
            await resilient_cache.store(f"recovery_{i}", "content")
            success_count += 1
        except CacheError as e:
            if "THROTTLING" in str(e.error_code):
                logger.debug("Request throttled during recovery")

    final_state = circuit_breaker.get_state()
    logger.info(
        "Recovery scenario completed",
        final_state=final_state.value,
        recovery_success_rate=success_count / recovery_attempts,
    )

    logger.info("✅ Recovery scenarios test completed")


async def run_all_tests():
    """Run all circuit breaker and resilience tests."""
    logger.info("🧪 Starting Cache Resilience Tests")

    try:
        await test_circuit_breaker_states()
        await test_graceful_degradation()
        await test_performance_under_failures()
        await test_circuit_breaker_metrics()
        await test_recovery_scenarios()

        logger.info("🎉 All cache resilience tests passed!")

    except Exception as e:
        logger.error("❌ Test failed", error=str(e), exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(run_all_tests())
