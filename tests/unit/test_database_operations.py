"""
Unit tests for database operations in the FACT system.
Tests database connection, query validation, and result formatting.
Following TDD principles - these tests will fail until implementation is complete.
"""

import pytest
import sqlite3
import json
from unittest.mock import Mock, patch, MagicMock
from src.db.connection import DatabaseManager
from src.db.models import QueryResult
from src.core.errors import SecurityError, DatabaseError


class TestDatabaseConnectionPool:
    """Test suite for database connection pool management."""

    def test_pool_initialization_creates_proper_configuration(self, test_database):
        """TEST: Pool initialization creates proper configuration"""
        # Arrange
        max_connections = 5

        # Act
        pool = DatabaseConnectionPool(test_database, max_connections=max_connections)

        # Assert
        assert pool.database_path == test_database
        assert pool.max_connections == max_connections
        assert pool.active_connections == 0
        assert len(pool.pool) == 0

    def test_acquire_connection_returns_valid_connection(self, test_database):
        """TEST: Acquire connection returns valid database connection"""
        # Arrange
        pool = DatabaseConnectionPool(test_database)

        # Act
        connection = pool.acquire_connection()

        # Assert
        assert connection is not None
        assert hasattr(connection, "execute")
        assert hasattr(connection, "commit")
        assert pool.active_connections == 1

    def test_release_connection_returns_connection_to_pool(self, test_database):
        """TEST: Release connection returns connection to pool"""
        # Arrange
        pool = DatabaseConnectionPool(test_database)
        connection = pool.acquire_connection()

        # Act
        pool.release_connection(connection)

        # Assert
        assert pool.active_connections == 0
        assert len(pool.pool) == 1

    def test_pool_exhaustion_blocks_until_connection_available(self, test_database):
        """TEST: Pool exhaustion blocks until connection becomes available"""
        # Arrange
        pool = DatabaseConnectionPool(test_database, max_connections=1)
        connection1 = pool.acquire_connection()

        # Act & Assert
        with pytest.raises(Exception):  # Should timeout or block
            with patch("src.db.connection.time.sleep") as mock_sleep:
                mock_sleep.side_effect = Exception("Pool exhausted")
                pool.acquire_connection()

    def test_connection_validation_rejects_corrupted_connections(self, test_database):
        """TEST: Connection validation rejects corrupted connections"""
        # Arrange
        pool = DatabaseConnectionPool(test_database)
        corrupted_connection = Mock()
        corrupted_connection.execute.side_effect = sqlite3.OperationalError(
            "database is locked"
        )

        # Act & Assert
        with pytest.raises(DatabaseError):
            pool.validate_connection(corrupted_connection)


class TestQueryValidator:
    """Test suite for SQL query validation and security."""

    def test_select_query_validation_allows_safe_queries(self):
        """TEST: SELECT query validation allows safe queries"""
        # Arrange
        validator = QueryValidator()
        safe_queries = [
            "SELECT * FROM revenue",
            "SELECT quarter, value FROM revenue WHERE quarter = 'Q1-2025'",
            "SELECT COUNT(*) FROM revenue",
            "SELECT AVG(value) FROM revenue GROUP BY category",
        ]

        # Act & Assert
        for query in safe_queries:
            result = validator.validate_sql_query(query)
            assert result.is_valid == True
            assert result.query_type == "SELECT"

    def test_dangerous_query_validation_prevents_write_operations(
        self, security_test_data
    ):
        """TEST: Dangerous query validation prevents write operations"""
        # Arrange
        validator = QueryValidator()
        dangerous_queries = [
            "DROP TABLE revenue",
            "INSERT INTO revenue VALUES ('hack', 0)",
            "UPDATE revenue SET value = 0",
            "DELETE FROM revenue",
            "ALTER TABLE revenue ADD COLUMN hack TEXT",
        ]

        # Act & Assert
        for query in dangerous_queries:
            with pytest.raises(SecurityError) as exc_info:
                validator.validate_sql_query(query)

            assert "not allowed" in str(exc_info.value).lower()

    def test_sql_injection_prevention_blocks_malicious_input(self, security_test_data):
        """TEST: SQL injection prevention blocks malicious input"""
        # Arrange
        validator = QueryValidator()
        injection_attempts = security_test_data["sql_injection_attempts"]

        # Act & Assert
        for malicious_query in injection_attempts:
            with pytest.raises(SecurityError) as exc_info:
                validator.validate_sql_query(malicious_query)

            assert (
                "injection" in str(exc_info.value).lower()
                or "dangerous" in str(exc_info.value).lower()
            )

    def test_query_complexity_validation_prevents_resource_exhaustion(self):
        """TEST: Query complexity validation prevents resource exhaustion"""
        # Arrange
        validator = QueryValidator()
        complex_query = """
        SELECT r1.*, r2.*, r3.*
        FROM revenue r1
        CROSS JOIN revenue r2
        CROSS JOIN revenue r3
        WHERE r1.value > (SELECT AVG(value) FROM revenue)
        """

        # Act & Assert
        with pytest.raises(SecurityError) as exc_info:
            validator.validate_sql_query(complex_query)

        assert (
            "complex" in str(exc_info.value).lower()
            or "resource" in str(exc_info.value).lower()
        )


class TestQueryExecution:
    """Test suite for SQL query execution and result formatting."""

    def test_query_execution_returns_structured_results(self, test_database):
        """TEST: Query execution returns structured results"""
        # Arrange
        from src.tools.connectors.sql import execute_sql_query

        query = "SELECT quarter, value FROM revenue WHERE quarter = 'Q1-2025'"

        # Act
        result = execute_sql_query(query, test_database)

        # Assert
        assert isinstance(result, QueryResult)
        assert result.success == True
        assert len(result.rows) == 1
        assert result.rows[0]["quarter"] == "Q1-2025"
        assert result.rows[0]["value"] == 1234567.89
        assert result.row_count == 1
        assert len(result.columns) == 2

    def test_query_execution_handles_empty_results(self, test_database):
        """TEST: Query execution handles empty results gracefully"""
        # Arrange
        from src.tools.connectors.sql import execute_sql_query

        query = (
            "SELECT * FROM revenue WHERE quarter = 'Q5-2025'"  # Non-existent quarter
        )

        # Act
        result = execute_sql_query(query, test_database)

        # Assert
        assert isinstance(result, QueryResult)
        assert result.success == True
        assert len(result.rows) == 0
        assert result.row_count == 0
        assert len(result.columns) > 0  # Columns should still be present

    def test_query_execution_measures_performance_accurately(
        self, test_database, performance_timer
    ):
        """TEST: Query execution measures performance accurately"""
        # Arrange
        from src.tools.connectors.sql import execute_sql_query

        query = "SELECT COUNT(*) as total FROM revenue"

        # Act
        with performance_timer() as timer:
            result = execute_sql_query(query, test_database)

        # Assert
        assert result.success == True
        assert result.execution_time_ms > 0
        assert result.execution_time_ms < 100  # Should be very fast for test DB
        assert timer.duration_ms >= result.execution_time_ms

    def test_connection_error_handling_provides_useful_diagnostics(self):
        """TEST: Connection error handling provides useful diagnostics"""
        # Arrange
        from src.tools.connectors.sql import execute_sql_query

        invalid_database = "/path/that/does/not/exist.db"
        query = "SELECT * FROM revenue"

        # Act & Assert
        with pytest.raises(DatabaseError) as exc_info:
            execute_sql_query(query, invalid_database)

        assert "connection" in str(exc_info.value).lower()
        assert invalid_database in str(exc_info.value)

    def test_transaction_rollback_on_query_failure(self, test_database):
        """TEST: Transaction rollback occurs on query failure"""
        # Arrange
        from src.tools.connectors.sql import execute_sql_query

        invalid_query = "SELECT * FROM non_existent_table"

        # Act & Assert
        with pytest.raises(DatabaseError) as exc_info:
            execute_sql_query(invalid_query, test_database)

        # Verify database state is unchanged
        valid_result = execute_sql_query(
            "SELECT COUNT(*) as count FROM revenue", test_database
        )
        assert valid_result.success == True
        assert valid_result.rows[0]["count"] == 4  # Original test data intact


class TestQueryResult:
    """Test suite for query result object functionality."""

    def test_query_result_serialization_to_json(self):
        """TEST: Query result serialization to JSON format"""
        # Arrange
        result = QueryResult(
            success=True,
            rows=[{"quarter": "Q1-2025", "value": 1234567.89}],
            columns=["quarter", "value"],
            row_count=1,
            execution_time_ms=15.5,
        )

        # Act
        json_result = result.to_json()
        parsed_result = json.loads(json_result)

        # Assert
        assert parsed_result["success"] == True
        assert parsed_result["row_count"] == 1
        assert parsed_result["execution_time_ms"] == 15.5
        assert len(parsed_result["rows"]) == 1
        assert parsed_result["rows"][0]["quarter"] == "Q1-2025"

    def test_query_result_handles_datetime_serialization(self):
        """TEST: Query result handles datetime serialization properly"""
        # Arrange
        from datetime import datetime

        result = QueryResult(
            success=True,
            rows=[{"created_at": datetime.now(), "value": 123.45}],
            columns=["created_at", "value"],
            row_count=1,
        )

        # Act
        json_result = result.to_json()
        parsed_result = json.loads(json_result)

        # Assert
        assert "created_at" in parsed_result["rows"][0]
        # Should convert datetime to ISO format string
        assert isinstance(parsed_result["rows"][0]["created_at"], str)

    def test_query_result_error_formatting(self):
        """TEST: Query result error formatting provides clear information"""
        # Arrange
        error_message = "Table 'revenue' doesn't exist"
        result = QueryResult(
            success=False, error=error_message, rows=[], columns=[], row_count=0
        )

        # Act
        json_result = result.to_json()
        parsed_result = json.loads(json_result)

        # Assert
        assert parsed_result["success"] == False
        assert parsed_result["error"] == error_message
        assert parsed_result["rows"] == []
        assert parsed_result["row_count"] == 0


@pytest.mark.database
class TestDatabaseIntegration:
    """Integration tests for database operations."""

    def test_end_to_end_query_processing(self, test_database):
        """TEST: End-to-end query processing from validation to results"""
        # Arrange
        from src.tools.connectors.sql import process_sql_request

        request = {
            "statement": "SELECT quarter, value FROM revenue ORDER BY value DESC LIMIT 2",
            "database": test_database,
        }

        # Act
        response = process_sql_request(request)

        # Assert
        assert response["success"] == True
        assert len(response["rows"]) == 2
        # Should be ordered by value DESC
        assert response["rows"][0]["value"] >= response["rows"][1]["value"]

    def test_concurrent_database_access_handling(self, test_database):
        """TEST: Concurrent database access is handled properly"""
        # Arrange
        from src.tools.connectors.sql import execute_sql_query
        import asyncio

        async def concurrent_query(query_id):
            query = f"SELECT '{query_id}' as query_id, COUNT(*) as count FROM revenue"
            return execute_sql_query(query, test_database)

        # Act
        async def run_concurrent_queries():
            tasks = [concurrent_query(f"query_{i}") for i in range(5)]
            return await asyncio.gather(*tasks)

        results = asyncio.run(run_concurrent_queries())

        # Assert
        assert len(results) == 5
        for i, result in enumerate(results):
            assert result.success == True
            assert result.rows[0]["query_id"] == f"query_{i}"
            assert result.rows[0]["count"] == 4  # All should see same data
