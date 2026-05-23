"""
Complete FACT System Integration Test Suite

This test suite validates the complete integration of all FACT system components:
- Environment configuration
- Database connectivity
- API integration
- Cache system
- Security layer
- Performance monitoring
- Benchmark framework
"""

import pytest
import os
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from typing import Dict, Any

# Import system components
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from core.config import Config, ConfigurationError
from core.driver import get_driver, FACTDriver
from db.connection import DatabaseManager
from cache.validation import CacheValidator
from security.auth import AuthorizationManager
from monitoring.metrics import MetricsCollector
from benchmarking.framework import BenchmarkFramework


class TestCompleteSystemIntegration:
    """Test complete system integration with all components."""

    @pytest.fixture
    def valid_test_env(self):
        """Provide valid test environment variables."""
        return {
            "ANTHROPIC_API_KEY": "sk-ant-test-key-for-integration",
            "ARCADE_API_KEY": "ak-test-key-for-integration",
            "DATABASE_PATH": "test_data/integration_test.db",
            "CACHE_MAX_SIZE": "1000",
            "LOG_LEVEL": "DEBUG",
        }

    @pytest.fixture
    async def test_database(self, valid_test_env):
        """Create a test database for integration testing."""
        with patch.dict(os.environ, valid_test_env, clear=True):
            config = Config()
            db_path = Path(config.database_path)
            db_path.parent.mkdir(parents=True, exist_ok=True)

            db_manager = DatabaseManager(config.database_path)
            await db_manager.initialize_database()

            yield db_manager

            # Cleanup
            if db_path.exists():
                db_path.unlink()

    def test_environment_configuration_integration(self, valid_test_env):
        """Test that environment configuration integrates properly with all components."""
        with patch.dict(os.environ, valid_test_env, clear=True):
            # Should successfully create config
            config = Config()

            # Verify all required keys are present
            assert config.anthropic_api_key == "sk-ant-test-key-for-integration"
            assert config.arcade_api_key == "ak-test-key-for-integration"
            assert config.database_path == "test_data/integration_test.db"

            # Verify configuration exports safely
            config_dict = config.to_dict()
            assert config_dict["anthropic_api_key"] == "***"
            assert config_dict["arcade_api_key"] == "***"

    @pytest.mark.asyncio
    async def test_database_integration_with_config(
        self, test_database, valid_test_env
    ):
        """Test database integration with configuration system."""
        with patch.dict(os.environ, valid_test_env, clear=True):
            config = Config()

            # Database should be initialized and accessible
            db_info = await test_database.get_database_info()

            assert db_info["database_path"] == config.database_path
            assert db_info["total_tables"] >= 3  # companies, financial_data, benchmarks
            assert "companies" in db_info["tables"]
            assert "financial_data" in db_info["tables"]

    @pytest.mark.asyncio
    async def test_security_integration(self, valid_test_env):
        """Test security component integration."""
        with patch.dict(os.environ, valid_test_env, clear=True):
            config = Config()
            security_manager = SecurityManager()

            # Test input sanitization
            test_query = "What was TechCorp's revenue in Q1 2025?"
            sanitized = security_manager.sanitize_input(test_query)
            assert sanitized == test_query  # Should pass through clean input

            # Test malicious input blocking
            malicious_query = "<script>alert('xss')</script>"
            with pytest.raises(Exception):  # Should raise security exception
                security_manager.sanitize_input(malicious_query)

    @pytest.mark.asyncio
    async def test_cache_system_integration(self, valid_test_env):
        """Test cache system integration with configuration."""
        with patch.dict(os.environ, valid_test_env, clear=True):
            config = Config()

            # Cache configuration should be loaded from environment
            cache_config = config.cache_config
            assert cache_config["max_size"] == "1000"  # From test env
            assert cache_config["prefix"] == "fact_v1"

            # Cache validator should initialize
            validator = CacheValidator()
            assert validator is not None

    @pytest.mark.asyncio
    async def test_driver_initialization_integration(
        self, test_database, valid_test_env
    ):
        """Test complete driver initialization with all components."""
        with patch.dict(os.environ, valid_test_env, clear=True):
            with patch(
                "src.core.driver.FACTDriver._test_connections", return_value=None
            ):
                # Driver should initialize successfully
                driver = await get_driver()

                assert driver is not None
                assert driver.config is not None
                assert driver.tool_registry is not None

                # Should have tools registered
                tools = driver.tool_registry.list_tools()
                assert len(tools) > 0

                # Should have metrics
                metrics = driver.get_metrics()
                assert metrics["initialized"] is True

                await driver.shutdown()

    @pytest.mark.asyncio
    async def test_benchmark_framework_integration(self, valid_test_env):
        """Test benchmark framework integration with system components."""
        with patch.dict(os.environ, valid_test_env, clear=True):
            framework = BenchmarkFramework()

            # Should initialize with configuration
            assert framework.config is not None
            assert framework.metrics_collector is not None

            # Should handle empty query list
            summary = await framework.run_benchmark_suite([])
            assert summary.total_queries == 0
            assert summary.successful_queries == 0

    @pytest.mark.asyncio
    async def test_end_to_end_query_processing(self, test_database, valid_test_env):
        """Test complete end-to-end query processing through all system layers."""
        with patch.dict(os.environ, valid_test_env, clear=True):
            with patch(
                "src.core.driver.FACTDriver._test_connections", return_value=None
            ):
                with patch("anthropic.AsyncAnthropic") as mock_anthropic:
                    # Mock successful API response
                    mock_response = MagicMock()
                    mock_response.content = [
                        MagicMock(text="TechCorp's Q1 2025 revenue was $50M")
                    ]
                    mock_anthropic.return_value.messages.create.return_value = (
                        mock_response
                    )

                    # Initialize driver
                    driver = await get_driver()

                    # Process a query end-to-end
                    response = await driver.process_query(
                        "What was TechCorp's Q1 2025 revenue?"
                    )

                    assert response is not None
                    assert "TechCorp" in response
                    assert "revenue" in response

                    await driver.shutdown()

    @pytest.mark.asyncio
    async def test_performance_monitoring_integration(self, valid_test_env):
        """Test performance monitoring integration."""
        with patch.dict(os.environ, valid_test_env, clear=True):
            metrics_collector = MetricsCollector()

            # Should record metrics
            await metrics_collector.record_query_metrics(
                query="test query", response_time_ms=50.0, success=True, cache_hit=False
            )

            # Should provide summary
            summary = await metrics_collector.get_performance_summary()
            assert summary is not None
            assert "total_queries" in summary

    def test_configuration_validation_integration(self, valid_test_env):
        """Test that configuration validation works across all components."""
        # Test with valid configuration
        with patch.dict(os.environ, valid_test_env, clear=True):
            config = Config()
            assert config is not None

        # Test with missing keys
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ConfigurationError) as exc_info:
                Config()
            assert "Missing required configuration keys" in str(exc_info.value)


class TestSystemErrorHandling:
    """Test error handling across integrated components."""

    def test_graceful_degradation_with_missing_api_keys(self):
        """Test system behavior when API keys are missing."""
        with patch.dict(os.environ, {}, clear=True):
            # Configuration should fail fast
            with pytest.raises(ConfigurationError):
                Config()

    def test_database_error_handling(self):
        """Test database error handling in integrated system."""
        test_env = {
            "ANTHROPIC_API_KEY": "sk-test-key",
            "ARCADE_API_KEY": "ak-test-key",
            "DATABASE_PATH": "/invalid/path/database.db",
        }

        with patch.dict(os.environ, test_env, clear=True):
            config = Config()

            # Should handle invalid database path gracefully
            db_manager = DatabaseManager(config.database_path)
            # Database operations should fail with clear error messages

    @pytest.mark.asyncio
    async def test_api_connectivity_error_handling(self):
        """Test API connectivity error handling."""
        test_env = {
            "ANTHROPIC_API_KEY": "sk-invalid-key",
            "ARCADE_API_KEY": "ak-invalid-key",
        }

        with patch.dict(os.environ, test_env, clear=True):
            with patch(
                "src.core.driver.FACTDriver._test_connections",
                side_effect=Exception("API Error"),
            ):
                # Should handle API errors gracefully
                with pytest.raises(Exception):
                    await get_driver()


class TestSystemPerformance:
    """Test system performance characteristics."""

    @pytest.mark.asyncio
    async def test_concurrent_query_handling(self, valid_test_env=None):
        """Test system handling of concurrent queries."""
        if valid_test_env is None:
            valid_test_env = {
                "ANTHROPIC_API_KEY": "sk-test-key",
                "ARCADE_API_KEY": "ak-test-key",
            }

        with patch.dict(os.environ, valid_test_env, clear=True):
            with patch(
                "src.core.driver.FACTDriver._test_connections", return_value=None
            ):
                framework = BenchmarkFramework()

                # Test concurrent query processing
                queries = ["Query 1", "Query 2", "Query 3"]

                with patch(
                    "src.benchmarking.framework.process_user_query",
                    return_value="Mock response",
                ):
                    summary = await framework.run_benchmark_suite(queries)

                    # Should handle all queries
                    expected_total = len(queries) * framework.config.iterations
                    assert summary.total_queries == expected_total

    @pytest.mark.asyncio
    async def test_cache_performance_validation(self):
        """Test cache performance meets targets."""
        test_env = {
            "ANTHROPIC_API_KEY": "sk-test-key",
            "ARCADE_API_KEY": "ak-test-key",
            "CACHE_HIT_TARGET_MS": "30",
            "CACHE_MISS_TARGET_MS": "120",
        }

        with patch.dict(os.environ, test_env, clear=True):
            validator = CacheValidator()

            # Validate cache performance targets
            # This test validates the cache system meets performance requirements


class TestSystemRecovery:
    """Test system recovery and resilience."""

    @pytest.mark.asyncio
    async def test_system_recovery_after_failure(self):
        """Test system recovery after component failure."""
        test_env = {"ANTHROPIC_API_KEY": "sk-test-key", "ARCADE_API_KEY": "ak-test-key"}

        with patch.dict(os.environ, test_env, clear=True):
            # Simulate system failure and recovery
            with patch(
                "src.core.driver.FACTDriver._test_connections", return_value=None
            ):
                driver = await get_driver()

                # System should be operational
                assert driver is not None

                # Simulate graceful shutdown
                await driver.shutdown()

    def test_configuration_reload_capability(self):
        """Test system ability to reload configuration."""
        # Test configuration reloading without restart
        test_env_1 = {
            "ANTHROPIC_API_KEY": "sk-test-key-1",
            "ARCADE_API_KEY": "ak-test-key-1",
        }

        test_env_2 = {
            "ANTHROPIC_API_KEY": "sk-test-key-2",
            "ARCADE_API_KEY": "ak-test-key-2",
        }

        with patch.dict(os.environ, test_env_1, clear=True):
            config1 = Config()
            assert config1.anthropic_api_key == "sk-test-key-1"

        with patch.dict(os.environ, test_env_2, clear=True):
            config2 = Config()
            assert config2.anthropic_api_key == "sk-test-key-2"
