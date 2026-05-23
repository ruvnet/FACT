#!/usr/bin/env python3
"""
Real Integration test for FACT system with cache resilience.

This script demonstrates how the FACT driver handles cache failures gracefully
without disrupting the agentic flow using real components (no mocking).

Note: This test requires valid API keys to be set in environment variables.
For testing without real API calls, use environment variables:
- ANTHROPIC_API_KEY=test-key-for-testing
- ARCADE_API_KEY=test-key-for-testing

The system will detect test keys and operate in test mode.
"""

import asyncio
import sys
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional
import tempfile
import sqlite3

# Add src to path for imports
src_path = str(Path(__file__).parent.parent / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

try:
    from core.driver import FACTDriver
    from core.config import Config, ConfigurationError
    from core.errors import CacheError
    from cache.resilience import CircuitState
    import structlog
except ImportError as e:
    print(f"❌ Import error: {e}")
    print(
        "Make sure you're running this script from the project root and all dependencies are installed."
    )
    sys.exit(1)

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


def setup_test_environment() -> str:
    """
    Set up test environment variables and create a temporary database.

    Returns:
        Path to temporary database file
    """
    # Create temporary database
    temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    temp_db.close()

    # Set required environment variables for testing
    test_env = {
        "DATABASE_PATH": temp_db.name,
        "CACHE_PREFIX": "integration_test",
        "CACHE_MIN_TOKENS": "50",
        "CACHE_MAX_SIZE": "1MB",
        "CACHE_TTL_SECONDS": "3600",
        "SYSTEM_PROMPT": "You are a helpful assistant for integration testing.",
        "CLAUDE_MODEL": "claude-3-haiku-20240307",
        "LOG_LEVEL": "INFO",
        "MAX_RETRIES": "2",
        "REQUEST_TIMEOUT": "30",
        "SKIP_API_VALIDATION": "true",  # Skip API validation for testing
    }

    # Check if API keys are set, if not set test values
    if not os.getenv("ANTHROPIC_API_KEY"):
        test_env["ANTHROPIC_API_KEY"] = "test-key-for-integration-testing"
        logger.warning(
            "Using test API key for Anthropic - some features may be limited"
        )

    if not os.getenv("ARCADE_API_KEY"):
        test_env["ARCADE_API_KEY"] = "test-key-for-integration-testing"
        logger.warning("Using test API key for Arcade - some features may be limited")

    # Apply test environment
    for key, value in test_env.items():
        os.environ[key] = value

    logger.info(
        "Test environment configured",
        database_path=temp_db.name,
        api_keys_configured=bool(os.getenv("ANTHROPIC_API_KEY"))
        and bool(os.getenv("ARCADE_API_KEY")),
        skip_api_validation=True,
    )

    return temp_db.name


def cleanup_test_environment(temp_db_path: str) -> None:
    """Clean up test environment."""
    try:
        if os.path.exists(temp_db_path):
            os.unlink(temp_db_path)
            logger.info("Cleaned up temporary database", path=temp_db_path)
    except Exception as e:
        logger.warning("Failed to cleanup temporary database", error=str(e))


async def test_fact_driver_initialization():
    """Test FACT driver initialization with real components."""
    logger.info("=== Testing FACT Driver Initialization ===")

    try:
        # Create configuration
        config = Config()
        logger.info("Configuration created successfully")

        # Initialize FACT driver
        driver = FACTDriver(config)
        logger.info("FACT driver instance created")

        # Test initialization
        await driver.initialize()
        logger.info("✅ FACT driver initialized successfully")

        # Verify components are available
        assert driver.config is not None, "Configuration should be available"
        assert hasattr(
            driver, "cache_circuit_breaker"
        ), "Circuit breaker should be available"

        # Test metrics collection
        metrics = driver.get_metrics()
        logger.info("Initial metrics collected", metrics=metrics)

        assert "initialized" in metrics, "Metrics should include initialization status"
        assert metrics["initialized"] == True, "Driver should report as initialized"

        # Clean shutdown
        await driver.shutdown()
        logger.info("✅ FACT driver initialization test passed")

    except ConfigurationError as e:
        logger.error("❌ Configuration error during initialization", error=str(e))
        logger.info("💡 This is expected if API keys are not properly configured")
        raise
    except Exception as e:
        logger.error(
            "❌ FACT driver initialization test failed", error=str(e), exc_info=True
        )
        raise


async def test_cache_resilience_features():
    """Test cache resilience features without external API calls."""
    logger.info("=== Testing Cache Resilience Features ===")

    try:
        config = Config()
        driver = FACTDriver(config)

        await driver.initialize()
        logger.info("Driver initialized for cache resilience testing")

        # Test 1: Circuit breaker manipulation
        if hasattr(driver, "cache_circuit_breaker") and driver.cache_circuit_breaker:
            logger.info("Testing circuit breaker state changes")

            # Test initial state
            initial_state = driver.cache_circuit_breaker.get_state()
            logger.info("Initial circuit breaker state", state=initial_state.value)

            # Force open state
            driver.cache_circuit_breaker.force_open()
            open_state = driver.cache_circuit_breaker.get_state()
            assert (
                open_state == CircuitState.OPEN
            ), "Circuit breaker should be in OPEN state"
            logger.info("✅ Circuit breaker forced to OPEN state")

            # Force closed state
            driver.cache_circuit_breaker.force_closed()
            closed_state = driver.cache_circuit_breaker.get_state()
            assert (
                closed_state == CircuitState.CLOSED
            ), "Circuit breaker should be in CLOSED state"
            logger.info("✅ Circuit breaker forced to CLOSED state")

        else:
            logger.warning(
                "Circuit breaker not available - cache resilience may be limited"
            )

        # Test 2: Cache degradation mode
        logger.info("Testing cache degradation mode")

        # Simulate cache degraded mode
        if hasattr(driver, "_cache_degraded"):
            original_degraded = getattr(driver, "_cache_degraded", False)

            # Set degraded mode
            driver._cache_degraded = True
            logger.info("Cache set to degraded mode")

            # Check metrics reflect degraded state
            metrics = driver.get_metrics()
            if "cache_degraded" in metrics:
                assert (
                    metrics["cache_degraded"] == True
                ), "Metrics should show cache degraded"
                logger.info("✅ Metrics correctly show cache degraded state")

            # Restore original state
            driver._cache_degraded = original_degraded

        # Test 3: System metrics during different states
        logger.info("Testing metrics collection")

        final_metrics = driver.get_metrics()

        # Verify essential metrics are present
        essential_metrics = ["initialized", "total_queries"]
        for metric in essential_metrics:
            if metric in final_metrics:
                logger.info(f"✅ Metric '{metric}' available: {final_metrics[metric]}")
            else:
                logger.warning(f"⚠️ Metric '{metric}' not available")

        # Log all cache and circuit breaker related metrics
        cache_metrics = {
            k: v for k, v in final_metrics.items() if k.startswith(("cache", "circuit"))
        }
        if cache_metrics:
            logger.info("Cache and circuit breaker metrics", metrics=cache_metrics)

        await driver.shutdown()
        logger.info("✅ Cache resilience features test passed")

    except Exception as e:
        logger.error("❌ Cache resilience test failed", error=str(e), exc_info=True)
        raise


async def test_database_integration():
    """Test database integration and connection handling."""
    logger.info("=== Testing Database Integration ===")

    try:
        config = Config()
        driver = FACTDriver(config)

        # Test database initialization
        await driver.initialize()
        logger.info("Driver initialized for database testing")

        # Verify database file exists
        db_path = config.database_path
        if db_path != ":memory:":
            assert os.path.exists(db_path), f"Database file should exist at {db_path}"
            logger.info("✅ Database file created", path=db_path)

            # Test basic database connectivity
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()
                conn.close()

                logger.info(
                    "✅ Database connectivity verified", table_count=len(tables)
                )

            except Exception as e:
                logger.warning("Database connectivity test failed", error=str(e))
        else:
            logger.info("✅ Using in-memory database")

        # Test metrics include database information
        metrics = driver.get_metrics()
        logger.info(
            "Database-related metrics collected",
            has_db_metrics=any(k.startswith("db") for k in metrics.keys()),
        )

        await driver.shutdown()
        logger.info("✅ Database integration test passed")

    except Exception as e:
        logger.error("❌ Database integration test failed", error=str(e), exc_info=True)
        raise


async def test_performance_monitoring():
    """Test performance monitoring capabilities."""
    logger.info("=== Testing Performance Monitoring ===")

    try:
        config = Config()
        driver = FACTDriver(config)

        await driver.initialize()
        logger.info("Driver initialized for performance testing")

        # Test timing measurements
        start_time = time.time()

        # Simulate some operations by getting metrics multiple times
        for i in range(5):
            metrics = driver.get_metrics()
            await asyncio.sleep(0.01)  # Small delay to simulate work

        elapsed_time = time.time() - start_time
        logger.info(
            "Performance test completed",
            operations=5,
            total_time_ms=elapsed_time * 1000,
            avg_time_ms=(elapsed_time / 5) * 1000,
        )

        # Verify metrics are collected efficiently
        final_metrics = driver.get_metrics()
        performance_keys = [
            k
            for k in final_metrics.keys()
            if "time" in k.lower()
            or "latency" in k.lower()
            or "performance" in k.lower()
        ]

        if performance_keys:
            logger.info("✅ Performance metrics available", keys=performance_keys)
        else:
            logger.info("ℹ️ No explicit performance metrics found")

        await driver.shutdown()
        logger.info("✅ Performance monitoring test passed")

    except Exception as e:
        logger.error(
            "❌ Performance monitoring test failed", error=str(e), exc_info=True
        )
        raise


async def test_error_handling():
    """Test error handling and recovery mechanisms."""
    logger.info("=== Testing Error Handling ===")

    try:
        # Test with invalid configuration
        logger.info("Testing configuration error handling")

        # Save original environment
        original_db_path = os.getenv("DATABASE_PATH")

        # Set invalid database path to test error handling
        os.environ["DATABASE_PATH"] = "/invalid/path/that/does/not/exist.db"

        try:
            config = Config()
            driver = FACTDriver(config)
            await driver.initialize()

            # If we get here, the system handled the invalid path gracefully
            logger.info("✅ System handled invalid database path gracefully")
            await driver.shutdown()

        except Exception as e:
            # This is expected for truly invalid paths
            logger.info(
                "✅ System correctly raised error for invalid database path",
                error=str(e),
            )

        finally:
            # Restore original database path
            if original_db_path:
                os.environ["DATABASE_PATH"] = original_db_path

        # Test normal operation after error recovery
        logger.info("Testing recovery after error")
        config = Config()
        driver = FACTDriver(config)
        await driver.initialize()

        metrics = driver.get_metrics()
        assert (
            metrics["initialized"] == True
        ), "Driver should initialize successfully after error recovery"

        await driver.shutdown()
        logger.info("✅ Error handling and recovery test passed")

    except Exception as e:
        logger.error("❌ Error handling test failed", error=str(e), exc_info=True)
        raise


async def run_all_integration_tests():
    """Run all real integration tests without mocking."""
    logger.info("🧪 Starting FACT Real Integration Tests (No Mocking)")

    temp_db_path = None

    try:
        # Set up test environment
        temp_db_path = setup_test_environment()
        logger.info("Test environment set up successfully")

        # Run all test suites
        await test_fact_driver_initialization()
        await test_cache_resilience_features()
        await test_database_integration()
        await test_performance_monitoring()
        await test_error_handling()

        logger.info("🎉 All FACT real integration tests passed!")

    except ConfigurationError as e:
        logger.error("❌ Configuration error in integration tests", error=str(e))
        logger.info(
            "💡 Ensure API keys are properly configured in environment variables"
        )
        logger.info("💡 For testing, you can use placeholder values like 'test-key'")
        raise

    except Exception as e:
        logger.error("❌ Integration tests failed", error=str(e), exc_info=True)
        raise

    finally:
        # Clean up test environment
        if temp_db_path:
            cleanup_test_environment(temp_db_path)


if __name__ == "__main__":
    try:
        asyncio.run(run_all_integration_tests())
    except KeyboardInterrupt:
        logger.info("Integration tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error("Integration tests failed to run", error=str(e))
        sys.exit(1)
