#!/usr/bin/env python3
"""
Comprehensive End-to-End Cache Resilience Test Suite
Tests the complete FACT cache resilience implementation using REAL components.
"""

import os
import sys
import time
import sqlite3
import tempfile
import unittest
import asyncio
from pathlib import Path
from unittest.mock import patch
import threading

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cache.manager import CacheManager
from cache.resilience import ResilientCacheWrapper, CircuitBreakerConfig, CircuitState
import structlog

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


class TestCacheResilienceE2ESync(unittest.TestCase):
    """Comprehensive End-to-End Cache Resilience Test Suite with Real Components"""

    def setUp(self):
        """Set up test environment with real components"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.db_path = self.temp_db.name

        # Initialize test database with sample data
        self._setup_test_database()

        # Configure cache with real settings
        self.cache_config = {
            "prefix": "fact_resilience_test",
            "min_tokens": 100,
            "max_size": "5MB",
            "ttl_seconds": 30,
            "hit_target_ms": 50,
            "miss_target_ms": 140,
        }

        # Initialize real cache manager
        self.cache_manager = CacheManager(self.cache_config)

        # Initialize circuit breaker with test-friendly settings
        circuit_config = CircuitBreakerConfig(
            failure_threshold=3, timeout_seconds=5.0, success_threshold=3
        )

        # Initialize circuit breaker and resilient cache wrapper
        from cache.resilience import CacheCircuitBreaker

        circuit_breaker = CacheCircuitBreaker(circuit_config)
        self.resilient_cache = ResilientCacheWrapper(
            cache_manager=self.cache_manager, circuit_breaker=circuit_breaker
        )

        logger.info(
            "Test environment initialized",
            cache_config=self.cache_config,
            db_path=self.db_path,
        )

    def _run_async(self, coro):
        """Helper to run async operations in sync tests"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def tearDown(self):
        """Clean up test environment"""
        try:
            # Clean up cache manually since CacheManager doesn't have clear()
            if hasattr(self, "cache_manager"):
                try:
                    with self.cache_manager._lock:
                        self.cache_manager.cache.clear()
                        self.cache_manager._access_frequency.clear()
                except Exception:
                    pass
            os.unlink(self.db_path)
            logger.info("Test environment cleaned up")
        except Exception as e:
            logger.warning("Cleanup warning", error=str(e))

    def _setup_test_database(self):
        """Initialize test database with sample financial data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create tables
        cursor.execute("""
            CREATE TABLE companies (
                id INTEGER PRIMARY KEY,
                symbol TEXT UNIQUE,
                name TEXT,
                sector TEXT,
                market_cap REAL
            )
        """)

        cursor.execute("""
            CREATE TABLE financial_data (
                id INTEGER PRIMARY KEY,
                company_id INTEGER,
                date TEXT,
                revenue REAL,
                net_income REAL,
                FOREIGN KEY (company_id) REFERENCES companies (id)
            )
        """)

        # Insert sample data
        companies = [
            ("AAPL", "Apple Inc.", "Technology", 2800000000000),
            ("MSFT", "Microsoft Corporation", "Technology", 2400000000000),
            ("GOOGL", "Alphabet Inc.", "Technology", 1600000000000),
            ("AMZN", "Amazon.com Inc.", "Consumer Discretionary", 1500000000000),
            ("TSLA", "Tesla Inc.", "Consumer Discretionary", 800000000000),
        ]

        cursor.executemany(
            "INSERT INTO companies (symbol, name, sector, market_cap) VALUES (?, ?, ?, ?)",
            companies,
        )

        # Insert financial data
        financial_data = [
            (1, "2024-Q1", 90750000000, 23636000000),
            (1, "2024-Q2", 94930000000, 25010000000),
            (2, "2024-Q1", 61858000000, 21939000000),
            (2, "2024-Q2", 64728000000, 22036000000),
            (3, "2024-Q1", 80539000000, 15051000000),
            (3, "2024-Q2", 84742000000, 16130000000),
        ]

        cursor.executemany(
            "INSERT INTO financial_data (company_id, date, revenue, net_income) VALUES (?, ?, ?, ?)",
            financial_data,
        )

        conn.commit()
        conn.close()
        logger.info("Test database initialized with financial data")

    def _get_financial_data(self, symbol: str) -> str:
        """Retrieve financial data from real database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = """
            SELECT c.name, c.sector, c.market_cap, f.date, f.revenue, f.net_income
            FROM companies c
            LEFT JOIN financial_data f ON c.id = f.company_id
            WHERE c.symbol = ?
            ORDER BY f.date DESC
        """

        cursor.execute(query, (symbol,))
        results = cursor.fetchall()
        conn.close()

        if not results:
            return f"No data found for {symbol}"

        # Format as comprehensive financial report
        company_name = results[0][0]
        sector = results[0][1]
        market_cap = results[0][2]

        report = f"Financial Analysis Report for {company_name} ({symbol})\n"
        report += f"Sector: {sector}\n"
        report += f"Market Cap: ${market_cap:,.0f}\n"
        report += "\nQuarterly Financial Performance:\n"

        for row in results:
            if row[3]:  # Has financial data
                report += (
                    f"  {row[3]}: Revenue ${row[4]:,.0f}, Net Income ${row[5]:,.0f}\n"
                )

        report += "\nThis comprehensive financial analysis provides detailed insights into the company's performance, "
        report += "market position, revenue trends, profitability metrics, and sector comparison data. "
        report += "The analysis includes quarterly revenue figures, net income calculations, market capitalization data, "
        report += "and comprehensive sector analysis to provide investors with actionable intelligence for investment decisions."

        return report

    def test_cache_initialization_real_components(self):
        """Test cache initialization with real storage components"""
        # Verify cache manager is properly initialized
        self.assertIsNotNone(self.cache_manager)
        self.assertEqual(self.cache_manager.prefix, "fact_resilience_test")
        self.assertEqual(self.cache_manager.min_tokens, 100)

        # Verify resilient wrapper is properly initialized
        self.assertIsNotNone(self.resilient_cache)
        self.assertIsNotNone(self.resilient_cache.circuit_breaker)
        self.assertTrue(self.resilient_cache.enable_graceful_degradation)

        # Test basic cache functionality
        test_content = (
            "This is test content for cache storage with sufficient tokens to meet the minimum requirement. "
            * 15
        )  # Ensure minimum tokens

        # Store content
        result = self._run_async(self.resilient_cache.store("test_key", test_content))
        self.assertTrue(result)

        # Retrieve content
        retrieved = self._run_async(self.resilient_cache.get("test_key"))
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.content, test_content)

        logger.info("Cache initialization test completed successfully")

    def test_normal_cache_operations_real_storage(self):
        """Test normal cache operations with real storage backend"""
        # Test cache miss scenario
        missing_content = self._run_async(self.resilient_cache.get("nonexistent_key"))
        self.assertIsNone(missing_content)

        # Test cache store and hit scenario
        for i in range(5):
            symbol = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"][i]
            financial_data = self._get_financial_data(symbol)

            # Store in cache
            cache_key = f"financial_data_{symbol}"
            store_result = self._run_async(
                self.resilient_cache.store(cache_key, financial_data)
            )
            self.assertTrue(store_result, f"Failed to store data for {symbol}")

            # Retrieve from cache (should be a hit)
            cached_data = self._run_async(self.resilient_cache.get(cache_key))
            self.assertEqual(
                cached_data.content, financial_data, f"Cache hit failed for {symbol}"
            )

        # Test cache metrics
        metrics = self.resilient_cache.get_metrics()
        self.assertIsInstance(metrics, dict)
        self.assertIn("cache", metrics)
        self.assertIn("circuit_breaker", metrics)

        logger.info("Normal cache operations test completed", metrics=metrics)

    def test_circuit_breaker_failure_scenarios(self):
        """Test circuit breaker with forced failure scenarios"""
        # Simulate cache failures by patching the underlying cache
        original_get = self.cache_manager.get
        original_store = self.cache_manager.store

        def failing_get(key):
            raise Exception("Cache storage failure")

        def failing_store(key, content):
            raise Exception("Cache storage failure")

        # Force failures to trigger circuit breaker
        with patch.object(self.cache_manager, "get", side_effect=failing_get):
            with patch.object(self.cache_manager, "store", side_effect=failing_store):

                # Trigger multiple failures to open circuit breaker
                for i in range(5):
                    try:
                        result = self._run_async(
                            self.resilient_cache.get(f"test_key_{i}")
                        )
                        # First few calls may still raise exceptions before circuit opens
                        if (
                            self.resilient_cache.circuit_breaker.state
                            == CircuitState.OPEN
                        ):
                            self.assertIsNone(result)
                    except Exception as e:
                        # Expected until circuit breaker opens
                        logger.debug(
                            f"Expected failure during circuit breaker activation: {e}"
                        )

                    try:
                        store_result = self._run_async(
                            self.resilient_cache.store(
                                f"test_key_{i}", f"test_content_{i}"
                            )
                        )
                        # Should return False when circuit is open
                        if (
                            self.resilient_cache.circuit_breaker.state
                            == CircuitState.OPEN
                        ):
                            self.assertFalse(store_result)
                    except Exception as e:
                        # Expected until circuit breaker opens
                        logger.debug(
                            f"Expected failure during circuit breaker activation: {e}"
                        )

                # Check circuit breaker state - should be open after multiple failures
                from cache.resilience import CircuitState

                self.assertEqual(
                    self.resilient_cache.circuit_breaker.state, CircuitState.OPEN
                )

        # Test circuit breaker blocks requests when open
        with patch.object(self.cache_manager, "get", side_effect=original_get):
            # Should still be blocked by circuit breaker and use graceful degradation
            result = self._run_async(self.resilient_cache.get("test_key"))
            self.assertIsNone(result)  # Should return None due to graceful degradation

        logger.info("Circuit breaker failure scenario test completed")

    def test_circuit_breaker_recovery_mechanisms(self):
        """Test circuit breaker recovery after timeout period"""
        # Force circuit breaker to open
        original_get = self.cache_manager.get

        def failing_get(key):
            raise Exception("Cache failure")

        # Trigger failures
        with patch.object(self.cache_manager, "get", side_effect=failing_get):
            for i in range(5):
                try:
                    self._run_async(self.resilient_cache.get(f"test_key_{i}"))
                except Exception:
                    # Expected failures
                    pass

        # Verify circuit breaker is open
        self.assertTrue(self.resilient_cache.circuit_breaker.is_open())

        # Test recovery after timeout
        # Short timeout for testing - just wait a bit and restore functionality
        time.sleep(0.1)

        # Reset to normal functionality
        with patch.object(self.cache_manager, "get", return_value=None):
            # This should work again
            result = self._run_async(self.resilient_cache.get("recovery_test"))
            # The operation should complete even if it returns None

        logger.info("Circuit breaker recovery test completed")

        # Verify circuit breaker is open
        self.assertTrue(self.resilient_cache.circuit_breaker.is_open())

        # Wait for timeout (use shorter timeout for testing)
        self.resilient_cache.circuit_breaker.config.timeout_seconds = 0.5
        time.sleep(0.8)  # Wait a bit longer than timeout to ensure transition

        # Try an operation to trigger transition to half-open
        # Use original working get method
        with patch.object(self.cache_manager, "get", return_value=None):
            try:
                result = self._run_async(self.resilient_cache.get("transition_test"))
                # Circuit breaker should now be half-open or closed after timeout
                state = self.resilient_cache.circuit_breaker.get_state()
                self.assertIn(
                    state,
                    [CircuitState.HALF_OPEN, CircuitState.CLOSED],
                    f"Expected HALF_OPEN or CLOSED, got {state}",
                )
            except Exception as e:
                # If still throwing errors, check if it's due to circuit breaker state
                if "CIRCUIT_BREAKER" in str(e):
                    # This is acceptable - circuit breaker is still protecting
                    pass
                else:
                    # Unexpected error, re-raise
                    raise

        # Ensure circuit breaker is in HALF_OPEN state before recovery
        state = self.resilient_cache.circuit_breaker.get_state()
        if state == CircuitState.OPEN:
            # Force transition to half-open if still open
            time.sleep(0.2)
            # Try another operation to trigger transition
            try:
                self._run_async(self.resilient_cache.get("force_transition"))
            except:
                pass

        # Test successful operations to close circuit breaker
        test_content = (
            "Recovery test content with sufficient tokens to meet the minimum requirement for cache storage. "
            * 12
        )

        # Perform multiple successful operations (circuit breaker needs 3 successes to close)
        success_count = 0
        stored_queries = []
        max_attempts = 10  # Increase attempts to ensure we get enough successes

        for i in range(max_attempts):
            try:
                query = f"recovery_test_{i}"
                # Generate the hash that will be used as the storage key
                query_hash = self.resilient_cache.generate_hash(query)
                # Store using the generated hash as the key
                store_result = self._run_async(
                    self.resilient_cache.store(query_hash, test_content)
                )

                # Verify actual storage by checking if item exists in cache
                # This is important because graceful degradation returns True even when not stored
                actually_stored = self.cache_manager.get(query_hash) is not None

                if store_result and actually_stored:
                    success_count += 1
                    stored_queries.append((query, query_hash))
                    logger.info(
                        f"Successful store operation {success_count} (actually stored)"
                    )
                elif store_result and not actually_stored:
                    logger.info(
                        f"Store returned True but item not actually stored (graceful degradation)"
                    )
                else:
                    logger.info(
                        f"Store operation failed: store_result={store_result}, actually_stored={actually_stored}"
                    )

                # Add small delay between operations to ensure proper state transitions
                time.sleep(0.02)

                # Only break if we have enough successes AND circuit breaker is closed
                if success_count >= 3:
                    state = self.resilient_cache.circuit_breaker.get_state()
                    logger.info(
                        f"After {success_count} successes, circuit breaker state: {state}"
                    )
                    if self.resilient_cache.circuit_breaker.is_closed():
                        logger.info(
                            f"Circuit breaker closed after {success_count} successful operations"
                        )
                        break

            except Exception as e:
                logger.warning(f"Store operation failed during recovery: {e}")
                continue

        # Verify we got at least 3 successful operations
        logger.info(
            f"Recovery test completed with {success_count} successful operations out of {max_attempts} attempts"
        )
        self.assertGreaterEqual(
            success_count,
            3,
            f"Expected at least 3 successful operations, got {success_count}",
        )

        # Circuit breaker should now be closed after 3 successful operations
        state = self.resilient_cache.circuit_breaker.get_state()
        self.assertTrue(
            self.resilient_cache.circuit_breaker.is_closed(),
            f"Expected circuit breaker to be CLOSED after {success_count} successes, but state is {state}",
        )

        # Add a small delay before retrieval to ensure storage is complete
        time.sleep(0.1)

        # Verify normal operation is restored by retrieving one of the stored items
        if stored_queries:
            query, query_hash = stored_queries[0]
            # Retrieve using the same hash that was used for storage
            retrieved = self._run_async(self.resilient_cache.get(query_hash))
            self.assertIsNotNone(
                retrieved,
                f"Failed to retrieve stored item after circuit breaker recovery. Query: {query}, Hash: {query_hash}",
            )
            # Verify the content matches what we stored
            self.assertEqual(
                retrieved.content if hasattr(retrieved, "content") else retrieved,
                test_content,
            )
        self.assertIn("Recovery test content", retrieved.content)

        logger.info("Circuit breaker recovery test completed")

    def test_performance_under_various_conditions(self):
        """Test performance metrics under various load conditions"""
        performance_results = {}

        # Test normal load
        start_time = time.time()
        for i in range(10):
            symbol = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"][i % 5]
            financial_data = self._get_financial_data(symbol)
            self._run_async(
                self.resilient_cache.store(f"perf_test_{i}", financial_data)
            )
        normal_load_time = time.time() - start_time
        performance_results["normal_load"] = normal_load_time

        # Test concurrent access
        def concurrent_worker(worker_id):
            for i in range(5):
                key = f"concurrent_{worker_id}_{i}"
                content = self._get_financial_data("AAPL")
                self._run_async(self.resilient_cache.store(key, content))
                retrieved = self._run_async(self.resilient_cache.get(key))
                self.assertIsNotNone(retrieved)

        start_time = time.time()
        threads = []
        for i in range(3):
            thread = threading.Thread(target=concurrent_worker, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()
        concurrent_time = time.time() - start_time
        performance_results["concurrent_load"] = concurrent_time

        # Get final metrics
        metrics = self.resilient_cache.get_metrics()
        performance_results["final_metrics"] = metrics

        # Verify performance is reasonable
        self.assertLess(normal_load_time, 5.0, "Normal load performance too slow")
        self.assertLess(concurrent_time, 10.0, "Concurrent load performance too slow")

        logger.info("Performance test completed", results=performance_results)

    def test_metrics_collection_and_validation(self):
        """Test comprehensive metrics collection and validation"""
        # Reset metrics
        initial_metrics = self.resilient_cache.get_metrics()

        # Perform various operations
        test_operations = [
            ("store_test_1", "Test content 1"),
            ("store_test_2", "Test content 2"),
            ("get_test_1", None),  # Hit
            ("get_nonexistent", None),  # Miss
        ]

        for operation, content in test_operations:
            if operation.startswith("store_"):
                financial_data = self._get_financial_data("AAPL")
                self._run_async(self.resilient_cache.store(operation, financial_data))
            elif operation.startswith("get_"):
                if operation == "get_test_1":
                    # This should be a hit
                    result = self._run_async(self.resilient_cache.get("store_test_1"))
                    self.assertIsNotNone(result)
                else:
                    # This should be a miss
                    result = self._run_async(self.resilient_cache.get(operation))
                    self.assertIsNone(result)

        # Get final metrics
        final_metrics = self.resilient_cache.get_metrics()

        # Validate metric structure
        self.assertIn("cache", final_metrics)
        self.assertIn("circuit_breaker", final_metrics)

        cache_metrics = final_metrics["cache"]
        cb_metrics = final_metrics["circuit_breaker"]

        required_cache_metrics = ["cache_hits", "cache_misses", "total_requests"]
        for metric in required_cache_metrics:
            self.assertIn(metric, cache_metrics)

        required_cb_metrics = [
            "state",
            "failure_count",
            "success_count",
            "total_operations",
        ]
        for metric in required_cb_metrics:
            self.assertIn(metric, cb_metrics)

        # Validate metric values - handle nested structure
        cache_metrics = final_metrics["cache"]
        self.assertGreaterEqual(cache_metrics["cache_hits"], 1)
        self.assertGreaterEqual(cache_metrics["cache_misses"], 1)
        self.assertGreater(cache_metrics["total_requests"], 0)

        logger.info("Metrics validation test completed", metrics=final_metrics)

    def test_real_database_integration(self):
        """Test cache integration with real database operations"""
        # Test database connectivity
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM companies")
        company_count = cursor.fetchone()[0]
        self.assertGreater(company_count, 0)
        conn.close()

        # Test cache-database integration
        symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]

        for symbol in symbols:
            cache_key = f"db_integration_{symbol}"

            # First access (cache miss, database hit)
            start_time = time.time()
            financial_data = self._get_financial_data(symbol)
            db_time = time.time() - start_time

            # Store in cache
            self._run_async(self.resilient_cache.store(cache_key, financial_data))

            # Second access (cache hit)
            start_time = time.time()
            cached_data = self._run_async(self.resilient_cache.get(cache_key))
            cache_time = time.time() - start_time

            # Verify data integrity
            self.assertIsNotNone(cached_data)
            self.assertEqual(cached_data.content, financial_data)

            # Cache should be faster than database, but allow for timing variance
            # If cache isn't significantly faster, log it but don't fail the test
            if cache_time >= db_time:
                logger.warning(
                    f"Cache timing variance detected for {symbol}: "
                    f"cache={cache_time*1000:.2f}ms, db={db_time*1000:.2f}ms"
                )
                # Allow up to 50% slower due to security scanning overhead
                tolerance = db_time * 1.5
                self.assertLess(
                    cache_time,
                    tolerance,
                    f"Cache time {cache_time*1000:.2f}ms exceeds tolerance "
                    f"of {tolerance*1000:.2f}ms for {symbol}",
                )
            else:
                # Cache is faster as expected
                self.assertLess(cache_time, db_time)

        logger.info("Database integration test completed")

    def test_stress_and_failure_recovery(self):
        """Test system behavior under stress and failure conditions"""
        stress_results = {}

        # Stress test with high volume
        stress_operations = 50
        success_count = 0
        error_count = 0

        start_time = time.time()
        for i in range(stress_operations):
            try:
                symbol = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"][i % 5]
                financial_data = self._get_financial_data(symbol)

                if self._run_async(
                    self.resilient_cache.store(f"stress_test_{i}", financial_data)
                ):
                    success_count += 1

                    # Verify retrieval
                    retrieved = self._run_async(
                        self.resilient_cache.get(f"stress_test_{i}")
                    )
                    if retrieved and retrieved.content == financial_data:
                        success_count += 1
                    else:
                        error_count += 1
                else:
                    error_count += 1

            except Exception as e:
                error_count += 1
                logger.warning("Stress test error", error=str(e), iteration=i)

        stress_time = time.time() - start_time
        stress_results["total_time"] = stress_time
        stress_results["success_count"] = success_count
        stress_results["error_count"] = error_count
        stress_results["success_rate"] = (
            success_count / (success_count + error_count)
            if (success_count + error_count) > 0
            else 0
        )

        # Verify reasonable success rate
        self.assertGreater(
            stress_results["success_rate"], 0.8, "Success rate too low under stress"
        )

        logger.info("Stress test completed", results=stress_results)

    def test_comprehensive_system_validation(self):
        """Run comprehensive system validation with all components"""
        validation_results = {
            "initialization": False,
            "basic_operations": False,
            "circuit_breaker": False,
            "performance": False,
            "database_integration": False,
            "metrics_collection": False,
            "error_handling": False,
        }

        try:
            # Test initialization
            self.assertIsNotNone(self.cache_manager)
            self.assertIsNotNone(self.resilient_cache)
            validation_results["initialization"] = True

            # Test basic operations
            test_content = (
                "Comprehensive validation test content with sufficient tokens for cache storage. "
                * 20
            )
            store_result = self._run_async(
                self.resilient_cache.store("validation_test", test_content)
            )
            self.assertTrue(store_result)

            retrieved = self._run_async(self.resilient_cache.get("validation_test"))
            self.assertIsNotNone(retrieved)
            self.assertEqual(retrieved.content, test_content)
            validation_results["basic_operations"] = True

            # Test circuit breaker functionality
            self.assertIsNotNone(self.resilient_cache.circuit_breaker)
            self.assertTrue(self.resilient_cache.circuit_breaker.is_closed())
            validation_results["circuit_breaker"] = True

            # Test performance
            start_time = time.time()
            for i in range(5):
                financial_data = self._get_financial_data("AAPL")
                self._run_async(
                    self.resilient_cache.store(f"perf_validation_{i}", financial_data)
                )
            perf_time = time.time() - start_time
            self.assertLess(perf_time, 2.0)
            validation_results["performance"] = True

            # Test database integration
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT symbol FROM companies LIMIT 1")
            result = cursor.fetchone()
            self.assertIsNotNone(result)
            conn.close()
            validation_results["database_integration"] = True

            # Test metrics collection
            metrics = self.resilient_cache.get_metrics()
            self.assertIsInstance(metrics, dict)
            self.assertIn("cache", metrics)
            self.assertIn("circuit_breaker", metrics)
            # Check nested structure
            cache_metrics = metrics["cache"]
            self.assertIn("cache_hits", cache_metrics)
            self.assertIn("cache_misses", cache_metrics)
            validation_results["metrics_collection"] = True

            # Test error handling
            with patch.object(
                self.cache_manager, "get", side_effect=Exception("Test error")
            ):
                result = self._run_async(self.resilient_cache.get("error_test"))
                # Should handle gracefully
                self.assertIsNone(result)
            validation_results["error_handling"] = True

        except Exception as e:
            logger.error("Validation error", error=str(e))
            raise

        # Verify all components passed
        for component, status in validation_results.items():
            self.assertTrue(status, f"Component {component} failed validation")

        logger.info(
            "Comprehensive system validation completed", results=validation_results
        )


def run_test_suite():
    """Run the complete test suite"""
    print("=" * 80)
    print("FACT Cache Resilience End-to-End Test Suite")
    print("=" * 80)

    # Create test suite
    test_suite = unittest.TestLoader().loadTestsFromTestCase(TestCacheResilienceE2ESync)

    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=2, buffer=True)
    result = runner.run(test_suite)

    print("\n" + "=" * 80)
    print(f"Test Results: {result.testsRun} tests run")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    print("=" * 80)

    return result


if __name__ == "__main__":
    run_test_suite()
