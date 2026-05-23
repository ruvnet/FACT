"""
Basic functionality tests for the FACT system.

These tests verify that the core components work correctly together.
"""

import pytest
import asyncio
import os
import tempfile
from pathlib import Path

# Add src to path for testing
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.core.config import Config
from src.core.driver import FACTDriver
from src.db.connection import DatabaseManager
from src.tools.decorators import get_tool_registry
from src.tools.connectors.sql import initialize_sql_tool


@pytest.fixture
async def temp_database():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    # Initialize database
    db_manager = DatabaseManager(db_path)
    await db_manager.initialize_database()

    yield db_manager

    # Cleanup
    os.unlink(db_path)


@pytest.fixture
def test_config(temp_database):
    """Create test configuration with temporary database."""
    config = Config()
    config._config = {
        "database_path": temp_database.database_path,
        "anthropic_api_key": "test_key",
        "arcade_api_key": "test_key",
        "cache_prefix": "test_v1",
        "claude_model": "claude-3-5-sonnet-20241022",
        "system_prompt": "Test prompt",
    }
    return config


class TestDatabaseIntegration:
    """Test database integration and SQL tools."""

    @pytest.mark.asyncio
    async def test_database_initialization(self, temp_database):
        """Test that database initializes with schema and sample data."""
        db_info = await temp_database.get_database_info()

        assert db_info["total_tables"] >= 2
        assert "companies" in db_info["tables"]
        assert "financial_records" in db_info["tables"]
        assert db_info["tables"]["companies"]["row_count"] > 0
        assert db_info["tables"]["financial_records"]["row_count"] > 0

    @pytest.mark.asyncio
    async def test_sql_query_execution(self, temp_database):
        """Test SQL query execution with security validation."""
        # Test valid SELECT query
        result = await temp_database.execute_query(
            "SELECT COUNT(*) as count FROM companies"
        )

        assert result.row_count == 1
        assert "count" in result.columns
        assert result.rows[0]["count"] > 0

    @pytest.mark.asyncio
    async def test_sql_security_validation(self, temp_database):
        """Test that dangerous SQL operations are blocked."""
        dangerous_queries = [
            "DROP TABLE companies",
            "DELETE FROM companies",
            "UPDATE companies SET name = 'hacked'",
            "INSERT INTO companies VALUES (999, 'hack')",
        ]

        for query in dangerous_queries:
            with pytest.raises(Exception):  # Should raise SecurityError
                await temp_database.execute_query(query)


class TestToolFramework:
    """Test tool registration and execution framework."""

    def test_tool_registry_functionality(self):
        """Test tool registry operations."""
        registry = get_tool_registry()

        # Check that SQL tools are registered
        tool_names = registry.list_tools()
        assert len(tool_names) > 0

        # Check schema export
        schemas = registry.export_all_schemas()
        assert len(schemas) > 0
        assert all("function" in schema for schema in schemas)

    @pytest.mark.asyncio
    async def test_sql_tool_integration(self, temp_database):
        """Test SQL tool initialization and execution."""
        # Initialize SQL tool
        initialize_sql_tool(temp_database)

        # Test tool execution through registry
        registry = get_tool_registry()
        sql_tool = registry.get_tool("SQL.QueryReadonly")

        # Execute a test query
        result = await sql_tool.function(statement="SELECT name FROM companies LIMIT 1")

        assert result["status"] == "success"
        assert "rows" in result
        assert len(result["rows"]) > 0


class TestSystemIntegration:
    """Test complete system integration."""

    @pytest.mark.asyncio
    async def test_driver_initialization(self, test_config, temp_database):
        """Test FACT driver initialization."""
        # Note: This test would need mocking for actual API calls
        driver = FACTDriver(test_config)

        # Initialize database component
        driver.database_manager = temp_database
        await driver._initialize_tools()

        # Check that tools are registered
        assert len(driver.tool_registry.list_tools()) > 0

        # Check metrics
        metrics = driver.get_metrics()
        assert "total_queries" in metrics
        assert "cache_hits" in metrics


class TestConfigurationManagement:
    """Test configuration loading and validation."""

    def test_config_creation(self):
        """Test configuration object creation."""
        config = Config()

        # Test property access
        assert hasattr(config, "anthropic_api_key")
        assert hasattr(config, "arcade_api_key")
        assert hasattr(config, "database_path")
        assert hasattr(config, "cache_prefix")

    def test_config_dictionary_export(self):
        """Test configuration export functionality."""
        config = Config()
        config_dict = config.to_dict()

        assert isinstance(config_dict, dict)
        assert "database_path" in config_dict
        assert "cache_prefix" in config_dict
        # Sensitive keys should be masked
        assert config_dict.get("anthropic_api_key") in [None, "***"]


@pytest.mark.asyncio
async def test_end_to_end_workflow(temp_database):
    """Test a complete end-to-end workflow."""
    # Initialize SQL tool
    initialize_sql_tool(temp_database)

    # Get tool registry
    registry = get_tool_registry()

    # Test that we can execute a sample query through the tool
    sql_tool = registry.get_tool("SQL.QueryReadonly")

    # Execute query
    result = await sql_tool.function(
        statement="SELECT name, sector FROM companies WHERE sector = 'Technology'"
    )

    # Verify result structure
    assert result["status"] == "success"
    assert "rows" in result
    assert "columns" in result
    assert "execution_time_ms" in result

    # Verify data content
    if result["rows"]:
        assert "name" in result["rows"][0]
        assert "sector" in result["rows"][0]


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v"])
