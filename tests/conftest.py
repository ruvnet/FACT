"""
Test configuration and fixtures for FACT system testing.
Provides comprehensive test environment setup for unit, integration, performance, and security tests.
"""

import pytest
import asyncio
import tempfile
import os
import sqlite3
import time
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path
from typing import Dict, Any, Generator
import json


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_database() -> Generator[str, None, None]:
    """Create a temporary test database with sample data."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    # Initialize test database with financial data
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE revenue (
            quarter TEXT PRIMARY KEY,
            value REAL,
            category TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Insert test data matching requirements
    test_data = [
        ("Q1-2025", 1234567.89, "Product Sales"),
        ("Q4-2024", 1133221.55, "Product Sales"),
        ("Q3-2024", 987654.32, "Service Revenue"),
        ("Q2-2024", 876543.21, "Product Sales"),
    ]

    for quarter, value, category in test_data:
        conn.execute(
            "INSERT INTO revenue (quarter, value, category) VALUES (?, ?, ?)",
            (quarter, value, category),
        )

    conn.commit()
    conn.close()

    yield db_path

    # Cleanup
    os.unlink(db_path)


@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic client for testing cache behavior."""
    client = AsyncMock()

    # Configure default response
    mock_response = Mock()
    mock_response.content = [Mock(text="Test response from Claude")]
    mock_response.tool_calls = None
    mock_response.usage = Mock(input_tokens=100, output_tokens=50)

    client.messages.create.return_value = mock_response

    return client


@pytest.fixture
def mock_arcade_client():
    """Mock Arcade client for testing tool execution."""
    client = Mock()

    # Configure successful tool execution
    client.tools.execute.return_value = {
        "status": "success",
        "data": {"rows": [], "row_count": 0},
        "execution_time_ms": 5,
    }

    # Configure tool schema export
    client.tools.export_schema.return_value = [
        {
            "type": "function",
            "function": {
                "name": "SQL.QueryReadonly",
                "description": "Execute read-only SQL queries",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "statement": {
                            "type": "string",
                            "description": "SQL SELECT statement",
                        }
                    },
                    "required": ["statement"],
                },
            },
        }
    ]

    return client


@pytest.fixture
def test_environment(test_database, mock_anthropic_client, mock_arcade_client):
    """Complete test environment setup with all necessary mocks."""
    env_vars = {
        "ANTHROPIC_API_KEY": "test-anthropic-key-12345",
        "ARCADE_API_KEY": "test-arcade-key-67890",
        "ARCADE_URL": "http://localhost:9099",
        "FACT_DB": test_database,
        "FACT_CACHE_PREFIX": "fact_test_v1",
        "FACT_LOG_LEVEL": "DEBUG",
    }

    with patch.dict(os.environ, env_vars):
        yield {
            "database": test_database,
            "anthropic": mock_anthropic_client,
            "arcade": mock_arcade_client,
            "env": env_vars,
        }


@pytest.fixture
def cache_config():
    """Cache configuration for testing cache behavior."""
    return {
        "prefix": "fact_test_v1",
        "min_tokens": 500,
        "max_size": "10MB",
        "ttl_seconds": 3600,
        "hit_target_ms": 50,
        "miss_target_ms": 140,
    }


@pytest.fixture
def performance_targets():
    """Performance targets from requirements for benchmark testing."""
    return {
        "cache_hit_latency_ms": 50,
        "cache_miss_latency_ms": 140,
        "tool_execution_lan_ms": 10,
        "overall_response_ms": 100,
        "cost_reduction_cache_hit": 0.90,  # 90% reduction
        "cost_reduction_cache_miss": 0.65,  # 65% reduction
    }


@pytest.fixture
def security_test_data():
    """Security test data for injection and validation testing."""
    return {
        "sql_injection_attempts": [
            "SELECT * FROM revenue; DROP TABLE revenue; --",
            "SELECT * FROM revenue WHERE 1=1 OR 1=1",
            "SELECT * FROM revenue UNION SELECT * FROM users",
            "'; EXEC xp_cmdshell('dir'); --",
            "SELECT * FROM revenue WHERE quarter = 'Q1' OR '1'='1'",
            "SELECT * FROM revenue; INSERT INTO revenue VALUES ('hack', 0); --",
        ],
        "path_traversal_attempts": [
            "../../../etc/passwd",
            "..\\..\\windows\\system32\\config\\sam",
            "/etc/shadow",
            "~/.ssh/id_rsa",
            "../../../../proc/self/environ",
        ],
        "dangerous_urls": [
            "http://localhost:80/admin",
            "http://127.0.0.1:8080/status",
            "http://169.254.169.254/metadata",
            "http://10.0.0.1/internal",
            "file:///etc/passwd",
            "ftp://internal.server/data",
        ],
    }


@pytest.fixture
def benchmark_queries():
    """Standard queries for performance benchmarking."""
    return [
        "What was Q1-2025 revenue?",
        "Show me quarterly revenue summary",
        "What is the total revenue for 2024?",
        "Compare Q1-2025 vs Q1-2024 revenue",
        "Show revenue by category",
        "What was the highest revenue quarter?",
        "Calculate year-over-year growth",
        "Show revenue trends",
        "What is average quarterly revenue?",
        "Find revenue outliers",
    ]


@pytest.fixture
def mock_time():
    """Mock time for consistent performance testing."""
    with patch("time.perf_counter") as mock_perf:
        # Simulate realistic timing
        mock_perf.side_effect = [0.000, 0.045]  # 45ms execution
        yield mock_perf


class PerformanceTimer:
    """Helper class for measuring performance in tests."""

    def __init__(self):
        self.start_time = None
        self.end_time = None

    def start(self):
        """Start timing."""
        self.start_time = time.perf_counter()
        return self

    def stop(self):
        """Stop timing and return duration in milliseconds."""
        self.end_time = time.perf_counter()
        return self.duration_ms

    @property
    def duration_ms(self) -> float:
        """Get duration in milliseconds."""
        if self.start_time is None or self.end_time is None:
            return 0.0
        return (self.end_time - self.start_time) * 1000

    def __enter__(self):
        return self.start()

    def __exit__(self, *args):
        self.stop()


@pytest.fixture
def performance_timer():
    """Performance timer fixture for measuring test execution times."""
    return PerformanceTimer


class TestDataFactory:
    """Factory for creating test data."""

    @staticmethod
    def create_tool_call(
        name: str = "SQL.QueryReadonly", statement: str = "SELECT * FROM revenue"
    ) -> Mock:
        """Create a mock tool call object."""
        tool_call = Mock()
        tool_call.name = name
        tool_call.id = f"test-call-{hash(statement) % 10000}"
        tool_call.arguments = json.dumps({"statement": statement})
        return tool_call

    @staticmethod
    def create_cache_entry(
        prefix: str = "fact_test_v1", content: str = None
    ) -> Dict[str, Any]:
        """Create a cache entry for testing."""
        if content is None:
            content = "A" * 500  # Minimum cache size

        return {
            "prefix": prefix,
            "content": content,
            "token_count": len(content.split()),
            "created_at": time.time(),
            "version": "1.0",
            "is_valid": True,
            "access_count": 0,
            "last_accessed": None,
        }

    @staticmethod
    def create_authorization(
        user_id: str = "test@example.com", scopes: list = None
    ) -> Dict[str, Any]:
        """Create an authorization object for testing."""
        if scopes is None:
            scopes = ["read"]

        return {
            "user_id": user_id,
            "scopes": scopes,
            "token": f"test_token_{hash(user_id) % 10000}",
            "expires_at": time.time() + 3600,
            "created_at": time.time(),
        }


@pytest.fixture
def test_factory():
    """Test data factory fixture."""
    return TestDataFactory


# Test markers for organizing test execution
pytestmark = [pytest.mark.asyncio]


def pytest_configure(config):
    """Configure pytest with custom markers and settings."""
    config.addinivalue_line("markers", "benchmark: Performance benchmark tests")
    config.addinivalue_line("markers", "cost_analysis: Token cost analysis tests")
