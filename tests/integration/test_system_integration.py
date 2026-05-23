"""
Integration tests for the FACT system.
Tests complete end-to-end workflows, component integration, and system behavior.
Following TDD principles - these tests will fail until implementation is complete.
"""

import pytest
import asyncio
import json
import time
from unittest.mock import Mock, AsyncMock, patch
from src.core.driver import FACTDriver, get_driver
from src.cache.manager import CacheManager
from src.tools.connectors.sql import SQLQueryTool
from src.db.connection import DatabaseManager


class TestEndToEndWorkflow:
    """Integration tests for complete FACT workflow."""

    @pytest.mark.integration
    async def test_complete_query_processing_workflow(
        self, test_environment, benchmark_queries
    ):
        """TEST: Complete query from user input to final response"""
        # Arrange
        query = "What was Q1-2025 revenue?"
        expected_revenue = 1234567.89

        # Act
        with test_environment:
            response = await process_user_query(query)

        # Assert
        assert response is not None
        assert str(expected_revenue) in response or "1,234,567.89" in response
        assert "Q1-2025" in response

        # Verify response contains structured financial data
        assert any(
            keyword in response.lower()
            for keyword in ["revenue", "quarter", "financial"]
        )

    @pytest.mark.integration
    async def test_cache_miss_to_tool_execution_workflow(
        self, test_environment, test_database
    ):
        """TEST: Cache miss triggers tool execution and response generation"""
        # Arrange
        unique_query = f"What is the total revenue for 2024? (timestamp: {time.time()})"

        # Configure mock to simulate tool call
        mock_tool_call = Mock()
        mock_tool_call.name = "SQL.QueryReadonly"
        mock_tool_call.id = "test-call-123"
        mock_tool_call.arguments = json.dumps(
            {
                "statement": "SELECT SUM(value) as total FROM revenue WHERE quarter LIKE '%2024%'"
            }
        )

        mock_response = Mock()
        mock_response.content = [
            Mock(text="The total revenue for 2024 was $2,997,419.08")
        ]
        mock_response.tool_calls = [mock_tool_call]

        # Act
        with test_environment as env:
            env["anthropic"].messages.create.return_value = mock_response
            env["arcade"].tools.execute.return_value = {
                "status": "success",
                "data": {"rows": [{"total": 2997419.08}], "row_count": 1},
            }

            response = await process_user_query(unique_query)

        # Assert
        assert response is not None
        assert "2,997,419.08" in response or "2997419.08" in response
        assert "2024" in response

        # Verify tool was executed
        env["arcade"].tools.execute.assert_called_once()
        call_args = env["arcade"].tools.execute.call_args[1]
        assert "SQL.QueryReadonly" in str(call_args)

    @pytest.mark.integration
    async def test_cache_hit_workflow_bypasses_tool_execution(
        self, test_environment, cache_config
    ):
        """TEST: Cache hit bypasses tool execution for faster response"""
        # Arrange
        cache_manager = CacheManager(config=cache_config)
        query = "What was Q1-2025 revenue?"
        cached_response = (
            "Q1-2025 revenue was $1,234,567.89 based on our financial records."
        )

        # Pre-populate cache
        query_hash = cache_manager.generate_hash(query)
        cache_manager.store(query_hash, cached_response)

        # Act
        start_time = time.perf_counter()

        with test_environment as env:
            with patch("src.cache.manager.cache_manager", cache_manager):
                response = await process_user_query(query)

        end_time = time.perf_counter()
        response_time_ms = (end_time - start_time) * 1000

        # Assert
        assert response == cached_response
        assert (
            response_time_ms < 50
        ), f"Cache hit took {response_time_ms:.2f}ms, exceeds 50ms target"

        # Verify tool execution was bypassed
        env["arcade"].tools.execute.assert_not_called()
        env["anthropic"].messages.create.assert_not_called()

    @pytest.mark.integration
    async def test_error_handling_and_recovery_workflow(self, test_environment):
        """TEST: System handles errors gracefully and provides useful feedback"""
        # Arrange
        error_scenarios = [
            {
                "name": "database_connection_error",
                "query": "SELECT * FROM revenue",
                "error": Exception("Database connection failed"),
                "expected_in_response": ["error", "database", "connection"],
            },
            {
                "name": "tool_execution_timeout",
                "query": "Complex analytical query",
                "error": TimeoutError("Tool execution timed out"),
                "expected_in_response": ["timeout", "error"],
            },
            {
                "name": "anthropic_api_error",
                "query": "What is the revenue?",
                "error": Exception("API rate limit exceeded"),
                "expected_in_response": ["error", "api", "temporarily"],
            },
        ]

        # Test each error scenario
        for scenario in error_scenarios:
            # Act
            with test_environment as env:
                if "database" in scenario["name"]:
                    env["arcade"].tools.execute.side_effect = scenario["error"]
                elif "anthropic" in scenario["name"]:
                    env["anthropic"].messages.create.side_effect = scenario["error"]

                response = await process_user_query(scenario["query"])

            # Assert
            assert response is not None
            response_lower = response.lower()

            # Should contain error context
            assert any(
                keyword in response_lower
                for keyword in scenario["expected_in_response"]
            )

            # Should not contain sensitive information
            assert not any(
                sensitive in response_lower
                for sensitive in ["api_key", "token", "secret"]
            )

    @pytest.mark.integration
    def test_system_initialization_and_configuration(self, test_environment):
        """TEST: System initializes properly with all components"""
        # Act
        with test_environment:
            anthropic_client, arcade_client, cache_prefix, system_prompt = (
                initialize_system()
            )

        # Assert
        assert anthropic_client is not None
        assert arcade_client is not None
        assert cache_prefix == "fact_test_v1"
        assert "deterministic" in system_prompt.lower()
        assert (
            "finance" in system_prompt.lower() or "financial" in system_prompt.lower()
        )

    @pytest.mark.integration
    async def test_concurrent_user_sessions(self, test_environment, benchmark_queries):
        """TEST: System handles concurrent user sessions correctly"""

        # Arrange
        async def user_session(user_id: int, queries: list):
            session_results = []
            for query in queries:
                user_query = f"{query} (user {user_id})"
                result = await process_user_query(user_query)
                session_results.append(
                    {
                        "user_id": user_id,
                        "query": user_query,
                        "response": result,
                        "timestamp": time.time(),
                    }
                )
            return session_results

        # Act
        user_count = 5
        queries_per_user = benchmark_queries[:3]  # First 3 queries

        with test_environment:
            concurrent_sessions = await asyncio.gather(
                *[
                    user_session(user_id, queries_per_user)
                    for user_id in range(user_count)
                ]
            )

        # Assert
        assert len(concurrent_sessions) == user_count

        # Verify all sessions completed successfully
        for session in concurrent_sessions:
            assert len(session) == len(queries_per_user)
            for result in session:
                assert result["response"] is not None
                assert len(result["response"]) > 0


class TestToolIntegration:
    """Integration tests for tool registration and execution."""

    @pytest.mark.integration
    def test_tool_registration_and_discovery_flow(
        self, test_environment, mock_arcade_client
    ):
        """TEST: Tool registration and subsequent discovery workflow"""
        # Arrange
        from src.tools.decorators import tool, register_tool, discover_tools

        @tool(
            name="TestTool.Integration",
            description="Integration test tool",
            parameters={"input": {"type": "string", "description": "Test input"}},
        )
        def integration_test_tool(input: str) -> dict:
            return {"processed": input.upper(), "timestamp": time.time()}

        # Act
        register_tool(integration_test_tool)
        discovered_tools = discover_tools()

        # Assert
        tool_names = [t._tool_metadata["name"] for t in discovered_tools]
        assert "TestTool.Integration" in tool_names

        # Verify tool can be executed
        from src.tools.decorators import execute_tool

        result = execute_tool("TestTool.Integration", {"input": "test_value"})

        assert result["success"] == True
        assert result["data"]["processed"] == "TEST_VALUE"

    @pytest.mark.integration
    def test_sql_tool_end_to_end_execution(self, test_environment, test_database):
        """TEST: SQL tool end-to-end execution workflow"""
        # Arrange
        sql_tool = SQLQueryTool(database_path=test_database)
        test_query = "SELECT quarter, value FROM revenue WHERE value > 1000000 ORDER BY value DESC"

        # Act
        result = sql_tool.execute({"statement": test_query})

        # Assert
        assert result["success"] == True
        assert "data" in result
        assert "rows" in result["data"]
        assert len(result["data"]["rows"]) > 0

        # Verify results are properly formatted
        first_row = result["data"]["rows"][0]
        assert "quarter" in first_row
        assert "value" in first_row
        assert isinstance(first_row["value"], (int, float))
        assert first_row["value"] > 1000000

    @pytest.mark.integration
    async def test_tool_call_via_arcade_integration(
        self, test_environment, mock_arcade_client
    ):
        """TEST: Tool execution via Arcade.dev integration"""
        # Arrange
        from src.tools.decorators import execute_tool_via_arcade

        # Configure successful tool execution
        mock_arcade_client.tools.execute.return_value = {
            "status": "success",
            "data": {
                "rows": [{"quarter": "Q1-2025", "value": 1234567.89}],
                "row_count": 1,
                "execution_time_ms": 8,
            },
        }

        tool_call_data = {
            "name": "SQL.QueryReadonly",
            "arguments": {
                "statement": "SELECT quarter, value FROM revenue WHERE quarter = 'Q1-2025'"
            },
        }

        # Act
        result = await execute_tool_via_arcade(
            tool_call_data["name"], tool_call_data["arguments"], mock_arcade_client
        )

        # Assert
        assert result["success"] == True
        assert result["data"]["row_count"] == 1
        assert result["data"]["rows"][0]["quarter"] == "Q1-2025"
        assert result["data"]["execution_time_ms"] < 10

        # Verify Arcade client was called correctly
        mock_arcade_client.tools.execute.assert_called_once()

    @pytest.mark.integration
    def test_tool_authorization_integration(self, test_environment):
        """TEST: Tool authorization integration with security framework"""
        # Arrange
        from src.tools.decorators import tool, register_tool, execute_tool_with_auth
        from src.core.errors import AuthorizationError

        @tool(
            name="TestTool.Protected",
            description="Protected tool requiring admin access",
            required_scopes=["admin", "write"],
        )
        def protected_tool() -> dict:
            return {"message": "Admin operation completed"}

        register_tool(protected_tool)

        # Test insufficient permissions
        with pytest.raises(AuthorizationError):
            execute_tool_with_auth(
                "TestTool.Protected",
                {},
                user_scopes=["read"],
                user_id="test@example.com",
            )

        # Test sufficient permissions
        result = execute_tool_with_auth(
            "TestTool.Protected",
            {},
            user_scopes=["admin", "write", "read"],
            user_id="admin@example.com",
        )

        # Assert
        assert result["success"] == True
        assert result["data"]["message"] == "Admin operation completed"


class TestDatabaseIntegration:
    """Integration tests for database operations and connection management."""

    @pytest.mark.database
    def test_database_connection_pool_under_load(self, test_database):
        """TEST: Database connection pool handles concurrent load"""
        # Arrange
        pool = DatabaseConnectionPool(test_database, max_connections=3)
        import threading
        import queue

        results_queue = queue.Queue()

        def database_worker(worker_id: int):
            try:
                connection = pool.acquire_connection()
                cursor = connection.execute("SELECT COUNT(*) as count FROM revenue")
                result = cursor.fetchone()
                pool.release_connection(connection)
                results_queue.put(
                    {"worker_id": worker_id, "count": result[0], "success": True}
                )
            except Exception as e:
                results_queue.put(
                    {"worker_id": worker_id, "error": str(e), "success": False}
                )

        # Act
        workers = []
        for i in range(5):  # More workers than pool size
            worker = threading.Thread(target=database_worker, args=(i,))
            workers.append(worker)
            worker.start()

        # Wait for all workers to complete
        for worker in workers:
            worker.join(timeout=5.0)

        # Collect results
        results = []
        while not results_queue.empty():
            results.append(results_queue.get())

        # Assert
        assert len(results) == 5
        successful_results = [r for r in results if r["success"]]
        assert len(successful_results) == 5  # All should succeed

        # Verify correct data
        for result in successful_results:
            assert result["count"] == 4  # Test database has 4 revenue records

    @pytest.mark.database
    def test_database_transaction_integrity(self, test_database):
        """TEST: Database maintains transaction integrity"""
        # Arrange
        from src.tools.connectors.sql import execute_sql_query

        # Verify initial state
        initial_result = execute_sql_query(
            "SELECT COUNT(*) as count FROM revenue", test_database
        )
        initial_count = initial_result.rows[0]["count"]

        # Act - Try to execute multiple queries
        queries = [
            "SELECT * FROM revenue WHERE quarter = 'Q1-2025'",
            "SELECT AVG(value) as avg_value FROM revenue",
            "SELECT quarter, value FROM revenue ORDER BY value DESC LIMIT 2",
        ]

        results = []
        for query in queries:
            result = execute_sql_query(query, test_database)
            results.append(result)

        # Verify final state
        final_result = execute_sql_query(
            "SELECT COUNT(*) as count FROM revenue", test_database
        )
        final_count = final_result.rows[0]["count"]

        # Assert
        assert all(r.success for r in results)
        assert initial_count == final_count  # No data should be modified
        assert initial_count == 4  # Original test data intact

    @pytest.mark.database
    def test_database_error_recovery(self, test_database):
        """TEST: Database error recovery and connection resilience"""
        # Arrange
        from src.tools.connectors.sql import execute_sql_query
        from src.core.errors import DatabaseError

        # Test invalid query handling
        invalid_queries = [
            "SELECT * FROM non_existent_table",
            "SELECT invalid_column FROM revenue",
            "SELECT * FROM revenue WHERE invalid_syntax =",
        ]

        # Act & Assert
        for invalid_query in invalid_queries:
            with pytest.raises(DatabaseError):
                execute_sql_query(invalid_query, test_database)

        # Verify database is still functional after errors
        recovery_result = execute_sql_query(
            "SELECT COUNT(*) as count FROM revenue", test_database
        )
        assert recovery_result.success == True
        assert recovery_result.rows[0]["count"] == 4


class TestCacheIntegration:
    """Integration tests for cache system integration."""

    @pytest.mark.cache
    async def test_cache_integration_with_query_processing(
        self, test_environment, cache_config
    ):
        """TEST: Cache integration with complete query processing workflow"""
        # Arrange
        cache_manager = CacheManager(config=cache_config)
        query = "What was Q1-2025 revenue and how does it compare to previous quarters?"

        # First request (cache miss)
        with test_environment as env:
            with patch("src.cache.manager.cache_manager", cache_manager):
                # Act - First request
                first_response = await process_user_query(query)

                # Verify cache miss behavior
                assert first_response is not None
                env["anthropic"].messages.create.assert_called()

                # Act - Second request (should be cache hit)
                env["anthropic"].messages.create.reset_mock()
                second_response = await process_user_query(query)

        # Assert
        assert second_response is not None
        # Second request should hit cache and not call Anthropic
        env["anthropic"].messages.create.assert_not_called()

        # Verify cache metrics
        metrics = cache_manager.get_metrics()
        assert metrics.total_requests >= 2
        assert metrics.cache_hits >= 1

    @pytest.mark.cache
    def test_cache_invalidation_integration(self, test_environment, cache_config):
        """TEST: Cache invalidation integration with system updates"""
        # Arrange
        cache_manager = CacheManager(config=cache_config)

        # Populate cache with multiple entries
        test_queries = [
            "What is Q1-2025 revenue?",
            "Show quarterly summary",
            "Calculate total 2024 revenue",
        ]

        for query in test_queries:
            content = f"Cached response for: {query}"
            query_hash = cache_manager.generate_hash(query)
            cache_manager.store(query_hash, content)

        # Verify cache is populated
        assert cache_manager.get_metrics().total_entries == 3

        # Act - Trigger cache invalidation (e.g., due to schema change)
        from src.cache.manager import invalidate_on_schema_change

        with patch("src.cache.manager.cache_manager", cache_manager):
            invalidated_count = invalidate_on_schema_change("Database schema updated")

        # Assert
        assert invalidated_count == 3
        assert cache_manager.get_metrics().total_entries == 0

        # Verify all queries now result in cache misses
        for query in test_queries:
            query_hash = cache_manager.generate_hash(query)
            assert cache_manager.get(query_hash) is None


@pytest.mark.integration
class TestSystemStability:
    """Integration tests for system stability and reliability."""

    async def test_memory_usage_under_sustained_load(
        self, test_environment, benchmark_queries
    ):
        """TEST: Memory usage remains stable under sustained load"""
        # Arrange
        import psutil
        import os

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Act - Sustained load test
        query_count = 0
        max_queries = 100

        with test_environment:
            while query_count < max_queries:
                query = benchmark_queries[query_count % len(benchmark_queries)]
                response = await process_user_query(query)

                assert response is not None
                query_count += 1

                # Check memory every 10 queries
                if query_count % 10 == 0:
                    current_memory = process.memory_info().rss / 1024 / 1024
                    memory_growth = current_memory - initial_memory

                    # Memory growth should be reasonable (< 50MB for 100 queries)
                    assert (
                        memory_growth < 50
                    ), f"Memory growth {memory_growth:.1f}MB too high"

        # Final memory check
        final_memory = process.memory_info().rss / 1024 / 1024
        total_growth = final_memory - initial_memory

        # Assert
        assert (
            total_growth < 100
        ), f"Total memory growth {total_growth:.1f}MB exceeds limit"

    async def test_error_rate_under_normal_operation(
        self, test_environment, benchmark_queries
    ):
        """TEST: Error rate remains low under normal operation"""
        # Arrange
        total_requests = 50
        error_count = 0

        # Act
        with test_environment:
            for i in range(total_requests):
                query = benchmark_queries[i % len(benchmark_queries)]

                try:
                    response = await process_user_query(query)
                    assert response is not None
                except Exception as e:
                    error_count += 1
                    # Log error for debugging
                    print(f"Query {i} failed: {str(e)}")

        # Assert
        error_rate = error_count / total_requests
        assert error_rate < 0.01, f"Error rate {error_rate:.1%} exceeds 1% threshold"

    def test_configuration_validation_and_recovery(self, test_environment):
        """TEST: System validates configuration and recovers from invalid configs"""
        # Arrange
        from src.core.config import validate_configuration, ConfigurationError

        invalid_configs = [
            {},  # Empty config
            {"ANTHROPIC_API_KEY": ""},  # Empty API key
            {"ANTHROPIC_API_KEY": "valid", "ARCADE_URL": "invalid-url"},  # Invalid URL
            {
                "ANTHROPIC_API_KEY": "valid",
                "ARCADE_URL": "http://localhost:9099",
                "ARCADE_API_KEY": "",
            },  # Empty Arcade key
        ]

        # Test invalid configurations
        for config in invalid_configs:
            with patch.dict("os.environ", config, clear=True):
                with pytest.raises(ConfigurationError):
                    validate_configuration()

        # Test valid configuration recovery
        valid_config = {
            "ANTHROPIC_API_KEY": "test-anthropic-key",
            "ARCADE_API_KEY": "test-arcade-key",
            "ARCADE_URL": "http://localhost:9099",
        }

        with patch.dict("os.environ", valid_config):
            # Should not raise exception
            validate_configuration()
