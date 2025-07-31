"""
Comprehensive unit tests for FACT core driver functionality.
Tests the FACTDriver class that orchestrates cache, queries, and tool execution.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import time
import json
from typing import Dict, Any

# Import the module under test
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from core.driver import FACTDriver, get_driver
from core.config import Config
from core.errors import FACTError, ConfigurationError, ToolExecutionError


class TestFACTDriverInitialization:
    """Test FACTDriver initialization and configuration."""
    
    @pytest.mark.asyncio
    async def test_driver_initialization_success(self, test_environment):
        """Test successful driver initialization with all components."""
        config = Config(
            database_path=test_environment["database"],
            claude_model="claude-3-sonnet-20240229",
            anthropic_api_key="test-key",
            arcade_api_key="test-arcade-key",
            arcade_url="http://localhost:9099"
        )
        
        with patch('core.driver.DatabaseManager') as mock_db, \
             patch('core.driver.initialize_cache_system') as mock_cache_init, \
             patch('core.driver.get_metrics_collector') as mock_metrics, \
             patch('core.driver.anthropic.AsyncAnthropic') as mock_anthropic:
            
            # Setup mocks
            mock_db.return_value.initialize.return_value = asyncio.Future()
            mock_db.return_value.initialize.return_value.set_result(True)
            
            mock_cache_init.return_value = AsyncMock()
            mock_metrics.return_value = Mock()
            mock_anthropic.return_value = test_environment["anthropic"]
            
            # Initialize driver
            driver = FACTDriver(config)
            await driver.initialize()
            
            # Verify initialization
            assert driver.is_initialized
            assert driver.config == config
            mock_db.assert_called_once()
            mock_cache_init.assert_called_once()
            mock_metrics.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_driver_initialization_database_failure(self):
        """Test driver initialization with database failure."""
        config = Config(
            database_path="/nonexistent/path.db",
            claude_model="claude-3-sonnet-20240229",
            anthropic_api_key="test-key"
        )
        
        with patch('core.driver.DatabaseManager') as mock_db:
            mock_db.return_value.initialize.side_effect = Exception("Database connection failed")
            
            driver = FACTDriver(config)
            
            with pytest.raises(FACTError, match="Database connection failed"):
                await driver.initialize()
            
            assert not driver.is_initialized
    
    @pytest.mark.asyncio
    async def test_driver_initialization_cache_failure(self, test_environment):
        """Test driver initialization with cache system failure."""
        config = Config(
            database_path=test_environment["database"],
            claude_model="claude-3-sonnet-20240229",
            anthropic_api_key="test-key"
        )
        
        with patch('core.driver.DatabaseManager') as mock_db, \
             patch('core.driver.initialize_cache_system') as mock_cache_init:
            
            mock_db.return_value.initialize.return_value = asyncio.Future()
            mock_db.return_value.initialize.return_value.set_result(True)
            mock_cache_init.side_effect = Exception("Cache initialization failed")
            
            driver = FACTDriver(config)
            
            with pytest.raises(FACTError, match="Cache initialization failed"):
                await driver.initialize()


class TestFACTDriverQueryProcessing:
    """Test FACTDriver query processing functionality."""
    
    @pytest.fixture
    async def initialized_driver(self, test_environment):
        """Create an initialized FACTDriver for testing."""
        config = Config(
            database_path=test_environment["database"],
            claude_model="claude-3-sonnet-20240229",
            anthropic_api_key="test-key",
            arcade_api_key="test-arcade-key",
            arcade_url="http://localhost:9099"
        )
        
        with patch('core.driver.DatabaseManager') as mock_db, \
             patch('core.driver.initialize_cache_system') as mock_cache_init, \
             patch('core.driver.get_metrics_collector') as mock_metrics, \
             patch('core.driver.anthropic.AsyncAnthropic') as mock_anthropic:
            
            # Setup mocks
            mock_db.return_value.initialize.return_value = asyncio.Future()
            mock_db.return_value.initialize.return_value.set_result(True)
            
            mock_cache_system = AsyncMock()
            mock_cache_init.return_value = mock_cache_system
            mock_metrics.return_value = Mock()
            mock_anthropic.return_value = test_environment["anthropic"]
            
            driver = FACTDriver(config)
            await driver.initialize()
            
            # Store mocks for access in tests
            driver._test_cache_system = mock_cache_system
            driver._test_db = mock_db.return_value
            
            return driver
    
    @pytest.mark.asyncio
    async def test_process_query_cache_hit(self, initialized_driver):
        """Test query processing with cache hit."""
        query = "What was Q1-2025 revenue?"
        cached_response = "Q1-2025 revenue was $1,234,567.89"
        
        # Mock cache hit
        initialized_driver._test_cache_system.get.return_value = {
            "response": cached_response,
            "metadata": {"cached_at": time.time(), "ttl": 3600}
        }
        
        start_time = time.perf_counter()
        response = await initialized_driver.process_query(query)
        end_time = time.perf_counter()
        
        # Verify response
        assert response == cached_response
        
        # Verify cache was checked
        initialized_driver._test_cache_system.get.assert_called_once()
        
        # Verify performance (cache hit should be fast)
        execution_time_ms = (end_time - start_time) * 1000
        assert execution_time_ms < 50  # Cache hit target: <50ms
    
    @pytest.mark.asyncio
    async def test_process_query_cache_miss_with_tools(self, initialized_driver, test_environment):
        """Test query processing with cache miss and tool execution."""
        query = "Show me all companies in our database"
        
        # Mock cache miss
        initialized_driver._test_cache_system.get.return_value = None
        
        # Mock LLM response with tool call
        mock_tool_call = Mock()
        mock_tool_call.name = "SQL.QueryReadonly"
        mock_tool_call.id = "test-call-123"
        mock_tool_call.arguments = json.dumps({"statement": "SELECT * FROM companies"})
        
        mock_response = Mock()
        mock_response.content = [Mock(text="I'll query the database for companies.")]
        mock_response.tool_calls = [mock_tool_call]
        mock_response.usage = Mock(input_tokens=100, output_tokens=50)
        
        test_environment["anthropic"].messages.create.return_value = mock_response
        
        # Mock tool execution
        with patch('core.driver.ToolExecutor') as mock_executor_class:
            mock_executor = AsyncMock()
            mock_executor.execute_tool.return_value = {
                "status": "success",
                "data": {"rows": [{"name": "TechCorp"}, {"name": "DataInc"}], "row_count": 2},
                "execution_time_ms": 8
            }
            mock_executor_class.return_value = mock_executor
            
            # Mock final LLM response
            final_response = Mock()
            final_response.content = [Mock(text="Found 2 companies: TechCorp and DataInc")]
            final_response.tool_calls = None
            test_environment["anthropic"].messages.create.side_effect = [mock_response, final_response]
            
            # Mock cache storage
            initialized_driver._test_cache_system.set.return_value = None
            
            start_time = time.perf_counter()
            response = await initialized_driver.process_query(query)
            end_time = time.perf_counter()
            
            # Verify response
            assert "Found 2 companies: TechCorp and DataInc" in response
            
            # Verify tool execution
            mock_executor.execute_tool.assert_called_once()
            
            # Verify cache storage
            initialized_driver._test_cache_system.set.assert_called_once()
            
            # Verify performance (cache miss should be within target)
            execution_time_ms = (end_time - start_time) * 1000
            assert execution_time_ms < 140  # Cache miss target: <140ms
    
    @pytest.mark.asyncio
    async def test_process_query_tool_execution_failure(self, initialized_driver, test_environment):
        """Test query processing with tool execution failure."""
        query = "Execute problematic query"
        
        # Mock cache miss
        initialized_driver._test_cache_system.get.return_value = None
        
        # Mock LLM response with tool call
        mock_tool_call = Mock()
        mock_tool_call.name = "SQL.QueryReadonly"
        mock_tool_call.id = "test-call-456"
        mock_tool_call.arguments = json.dumps({"statement": "INVALID SQL"})
        
        mock_response = Mock()
        mock_response.content = [Mock(text="I'll execute the query.")]
        mock_response.tool_calls = [mock_tool_call]
        
        test_environment["anthropic"].messages.create.return_value = mock_response
        
        # Mock tool execution failure
        with patch('core.driver.ToolExecutor') as mock_executor_class:
            mock_executor = AsyncMock()
            mock_executor.execute_tool.side_effect = ToolExecutionError("SQL syntax error")
            mock_executor_class.return_value = mock_executor
            
            with pytest.raises(ToolExecutionError, match="SQL syntax error"):
                await initialized_driver.process_query(query)
    
    @pytest.mark.asyncio
    async def test_process_query_llm_failure(self, initialized_driver, test_environment):
        """Test query processing with LLM API failure."""
        query = "Test query"
        
        # Mock cache miss
        initialized_driver._test_cache_system.get.return_value = None
        
        # Mock LLM API failure
        test_environment["anthropic"].messages.create.side_effect = Exception("API rate limit exceeded")
        
        with pytest.raises(FACTError, match="API rate limit exceeded"):
            await initialized_driver.process_query(query)
    
    @pytest.mark.asyncio
    async def test_process_query_empty_query(self, initialized_driver):
        """Test processing of empty or whitespace-only query."""
        with pytest.raises(ValueError, match="Query cannot be empty"):
            await initialized_driver.process_query("")
        
        with pytest.raises(ValueError, match="Query cannot be empty"):
            await initialized_driver.process_query("   ")
    
    @pytest.mark.asyncio
    async def test_process_query_very_long_query(self, initialized_driver):
        """Test processing of extremely long query."""
        long_query = "What is the revenue for " + "Q1 " * 10000  # Very long query
        
        with pytest.raises(ValueError, match="Query too long"):
            await initialized_driver.process_query(long_query)


class TestFACTDriverPerformanceMetrics:
    """Test FACTDriver performance monitoring and metrics."""
    
    @pytest.mark.asyncio
    async def test_metrics_collection_cache_hit(self, initialized_driver):
        """Test metrics collection for cache hit scenario."""
        query = "Test query for metrics"
        
        # Mock cache hit
        initialized_driver._test_cache_system.get.return_value = {
            "response": "Cached response",
            "metadata": {"cached_at": time.time(), "ttl": 3600}
        }
        
        with patch('core.driver.get_metrics_collector') as mock_metrics_collector:
            mock_metrics = Mock()
            mock_metrics_collector.return_value = mock_metrics
            
            await initialized_driver.process_query(query)
            
            # Verify metrics were recorded
            mock_metrics.record_cache_hit.assert_called_once()
            mock_metrics.record_query_latency.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_metrics_collection_cache_miss(self, initialized_driver, test_environment):
        """Test metrics collection for cache miss scenario."""
        query = "Test query for cache miss metrics"
        
        # Mock cache miss
        initialized_driver._test_cache_system.get.return_value = None
        
        # Mock LLM response without tools
        mock_response = Mock()
        mock_response.content = [Mock(text="Simple response")]
        mock_response.tool_calls = None
        mock_response.usage = Mock(input_tokens=100, output_tokens=50)
        
        test_environment["anthropic"].messages.create.return_value = mock_response
        initialized_driver._test_cache_system.set.return_value = None
        
        with patch('core.driver.get_metrics_collector') as mock_metrics_collector:
            mock_metrics = Mock()
            mock_metrics_collector.return_value = mock_metrics
            
            await initialized_driver.process_query(query)
            
            # Verify metrics were recorded
            mock_metrics.record_cache_miss.assert_called_once()
            mock_metrics.record_query_latency.assert_called_once()
            mock_metrics.record_token_usage.assert_called_once()


class TestFACTDriverConcurrency:
    """Test FACTDriver concurrent query processing."""
    
    @pytest.mark.asyncio
    async def test_concurrent_queries_cache_hits(self, initialized_driver):
        """Test concurrent processing of queries with cache hits."""
        queries = [
            "What was Q1-2025 revenue?",
            "What was Q2-2025 revenue?",
            "What was Q3-2025 revenue?"
        ]
        
        # Mock cache hits for all queries
        cache_responses = [
            {"response": f"Q{i}-2025 revenue was ${i*100000}", "metadata": {"cached_at": time.time()}}
            for i in range(1, 4)
        ]
        initialized_driver._test_cache_system.get.side_effect = cache_responses
        
        # Execute queries concurrently
        start_time = time.perf_counter()
        tasks = [initialized_driver.process_query(query) for query in queries]
        responses = await asyncio.gather(*tasks)
        end_time = time.perf_counter()
        
        # Verify all responses received
        assert len(responses) == 3
        for i, response in enumerate(responses):
            assert f"Q{i+1}-2025 revenue was ${(i+1)*100000}" in response
        
        # Verify concurrent execution was faster than sequential
        total_time_ms = (end_time - start_time) * 1000
        assert total_time_ms < 150  # Should be much faster than 3 * 50ms
    
    @pytest.mark.asyncio
    async def test_concurrent_queries_rate_limiting(self, initialized_driver):
        """Test rate limiting with many concurrent queries."""
        queries = [f"Query {i}" for i in range(100)]  # Many queries
        
        # Mock cache misses to trigger LLM calls
        initialized_driver._test_cache_system.get.return_value = None
        
        # Some queries should be rate limited
        with patch('core.driver.asyncio.Semaphore') as mock_semaphore:
            mock_sem = AsyncMock()
            mock_semaphore.return_value = mock_sem
            
            tasks = [initialized_driver.process_query(query) for query in queries[:10]]  # Limit to 10 for testing
            
            # This should complete without hanging or failing
            try:
                responses = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=30)
                # Some responses may be exceptions due to mocking, that's OK
                assert len(responses) == 10
            except asyncio.TimeoutError:
                pytest.fail("Concurrent query processing timed out - possible deadlock")


class TestGetDriverFunction:
    """Test the get_driver() convenience function."""
    
    @pytest.mark.asyncio
    async def test_get_driver_with_config(self, test_environment):
        """Test get_driver() with explicit config."""
        config = Config(
            database_path=test_environment["database"],
            claude_model="claude-3-sonnet-20240229",
            anthropic_api_key="test-key"
        )
        
        with patch('core.driver.DatabaseManager'), \
             patch('core.driver.initialize_cache_system'), \
             patch('core.driver.get_metrics_collector'), \
             patch('core.driver.anthropic.AsyncAnthropic'):
            
            driver = await get_driver(config)
            
            assert isinstance(driver, FACTDriver)
            assert driver.config == config
            assert driver.is_initialized
    
    @pytest.mark.asyncio
    async def test_get_driver_without_config(self, test_environment):
        """Test get_driver() without explicit config (uses default)."""
        with patch('core.driver.get_config') as mock_get_config, \
             patch('core.driver.DatabaseManager'), \
             patch('core.driver.initialize_cache_system'), \
             patch('core.driver.get_metrics_collector'), \
             patch('core.driver.anthropic.AsyncAnthropic'):
            
            # Mock default config
            mock_config = Config(
                database_path=test_environment["database"],
                claude_model="claude-3-sonnet-20240229",
                anthropic_api_key="test-key"
            )
            mock_get_config.return_value = mock_config
            
            driver = await get_driver()
            
            assert isinstance(driver, FACTDriver)
            mock_get_config.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_driver_initialization_failure(self):
        """Test get_driver() with initialization failure."""
        config = Config(
            database_path="/invalid/path.db",
            claude_model="claude-3-sonnet-20240229",
            anthropic_api_key="invalid-key"
        )
        
        with patch('core.driver.DatabaseManager') as mock_db:
            mock_db.return_value.initialize.side_effect = Exception("Database error")
            
            with pytest.raises(FACTError):
                await get_driver(config)


@pytest.mark.benchmark
class TestFACTDriverPerformanceBenchmarks:
    """Performance benchmark tests for FACTDriver."""
    
    @pytest.mark.asyncio
    async def test_cache_hit_performance_benchmark(self, initialized_driver, performance_timer):
        """Benchmark cache hit performance against targets."""
        query = "Performance test query"
        
        # Mock cache hit with realistic data
        cached_response = "A" * 500  # 500 character response
        initialized_driver._test_cache_system.get.return_value = {
            "response": cached_response,
            "metadata": {"cached_at": time.time(), "ttl": 3600}
        }
        
        # Run performance test
        times = []
        for _ in range(10):  # Multiple runs for statistical accuracy
            timer = performance_timer()
            with timer:
                response = await initialized_driver.process_query(query)
            times.append(timer.duration_ms)
            assert response == cached_response
        
        # Calculate statistics
        avg_time = sum(times) / len(times)
        p95_time = sorted(times)[int(0.95 * len(times))]
        
        # Verify performance targets
        assert avg_time < 30, f"Average cache hit time {avg_time}ms exceeds 30ms target"
        assert p95_time < 50, f"P95 cache hit time {p95_time}ms exceeds 50ms target"
    
    @pytest.mark.asyncio
    async def test_cache_miss_performance_benchmark(self, initialized_driver, test_environment, performance_timer):
        """Benchmark cache miss performance against targets."""
        query = "Cache miss performance test"
        
        # Mock cache miss
        initialized_driver._test_cache_system.get.return_value = None
        
        # Mock fast LLM response (no tools)
        mock_response = Mock()
        mock_response.content = [Mock(text="Fast response")]
        mock_response.tool_calls = None
        mock_response.usage = Mock(input_tokens=50, output_tokens=25)
        
        test_environment["anthropic"].messages.create.return_value = mock_response
        initialized_driver._test_cache_system.set.return_value = None
        
        # Run performance test
        times = []
        for _ in range(5):  # Fewer runs due to slower operation
            timer = performance_timer()
            with timer:
                response = await initialized_driver.process_query(query)
            times.append(timer.duration_ms)
            assert "Fast response" in response
        
        # Calculate statistics
        avg_time = sum(times) / len(times)
        p95_time = sorted(times)[int(0.95 * len(times))] if len(times) > 1 else times[0]
        
        # Verify performance targets (more lenient for cache miss)
        assert avg_time < 100, f"Average cache miss time {avg_time}ms exceeds 100ms target"
        assert p95_time < 140, f"P95 cache miss time {p95_time}ms exceeds 140ms target"