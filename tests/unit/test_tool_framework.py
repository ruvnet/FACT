"""
Unit tests for tool framework in the FACT system.
Tests tool registration, execution, and integration with Arcade.dev.
Following TDD principles - these tests will fail until implementation is complete.
"""

import pytest
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from src.tools.decorators import Tool, get_tool_registry
from src.tools.connectors.sql import SQLQueryTool
from src.core.errors import ToolExecutionError, UnauthorizedError, ValidationError


class TestToolDecorator:
    """Test suite for tool registration decorator functionality."""

    def test_tool_decorator_registers_function_with_metadata(self):
        """TEST: Tool decorator registers function with proper metadata"""

        # Arrange & Act
        @tool(
            name="TestTool.Sample",
            description="A sample tool for testing",
            parameters={"input": {"type": "string", "description": "Test input"}},
        )
        def sample_tool(input: str) -> dict:
            return {"result": input.upper()}

        # Assert
        assert hasattr(sample_tool, "_tool_metadata")
        metadata = sample_tool._tool_metadata
        assert metadata["name"] == "TestTool.Sample"
        assert metadata["description"] == "A sample tool for testing"
        assert "parameters" in metadata
        assert metadata["parameters"]["input"]["type"] == "string"

    def test_tool_decorator_preserves_function_behavior(self):
        """TEST: Tool decorator preserves original function behavior"""

        # Arrange
        @tool(name="TestTool.Echo", description="Echo tool")
        def echo_tool(message: str) -> dict:
            return {"echo": message}

        # Act
        result = echo_tool("hello")

        # Assert
        assert result == {"echo": "hello"}
        assert echo_tool.__name__ == "echo_tool"

    def test_tool_decorator_validates_required_metadata(self):
        """TEST: Tool decorator validates required metadata fields"""
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:

            @tool()  # Missing required name
            def invalid_tool():
                pass

        assert "name is required" in str(exc_info.value)

    def test_tool_decorator_generates_arcade_schema(self):
        """TEST: Tool decorator generates proper Arcade.dev schema"""

        # Arrange
        @tool(
            name="TestTool.Calculate",
            description="Calculate values",
            parameters={
                "x": {"type": "number", "description": "First number"},
                "y": {"type": "number", "description": "Second number"},
            },
        )
        def calculate_tool(x: float, y: float) -> dict:
            return {"sum": x + y}

        # Act
        from src.tools.decorators import generate_arcade_schema

        schema = generate_arcade_schema(calculate_tool)

        # Assert
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "TestTool.Calculate"
        assert schema["function"]["description"] == "Calculate values"
        assert "parameters" in schema["function"]
        assert schema["function"]["parameters"]["properties"]["x"]["type"] == "number"


class TestToolRegistration:
    """Test suite for tool registration and discovery."""

    def test_register_tool_adds_to_global_registry(self):
        """TEST: Register tool adds tool to global registry"""

        # Arrange
        @tool(name="TestTool.Registry", description="Registry test")
        def registry_tool():
            return {"status": "registered"}

        # Act
        register_tool(registry_tool)

        # Assert
        from src.tools.decorators import get_registered_tools

        registered_tools = get_registered_tools()
        tool_names = [t._tool_metadata["name"] for t in registered_tools]
        assert "TestTool.Registry" in tool_names

    def test_duplicate_tool_registration_raises_error(self):
        """TEST: Duplicate tool registration raises appropriate error"""

        # Arrange
        @tool(name="TestTool.Duplicate", description="Duplicate test")
        def duplicate_tool():
            return {}

        register_tool(duplicate_tool)

        # Act & Assert
        with pytest.raises(ToolError) as exc_info:
            register_tool(duplicate_tool)

        assert "already registered" in str(exc_info.value)

    def test_tool_discovery_returns_all_registered_tools(self):
        """TEST: Tool discovery returns all registered tools"""

        # Arrange
        @tool(name="TestTool.Discovery1", description="Discovery test 1")
        def discovery_tool_1():
            return {}

        @tool(name="TestTool.Discovery2", description="Discovery test 2")
        def discovery_tool_2():
            return {}

        register_tool(discovery_tool_1)
        register_tool(discovery_tool_2)

        # Act
        from src.tools.decorators import discover_tools

        discovered = discover_tools()

        # Assert
        assert len(discovered) >= 2
        names = [tool._tool_metadata["name"] for tool in discovered]
        assert "TestTool.Discovery1" in names
        assert "TestTool.Discovery2" in names

    def test_tool_schema_export_generates_claude_compatible_format(self):
        """TEST: Tool schema export generates Claude-compatible format"""

        # Arrange
        @tool(
            name="TestTool.Export",
            description="Export test tool",
            parameters={
                "param1": {"type": "string", "description": "Parameter 1"},
                "param2": {
                    "type": "number",
                    "description": "Parameter 2",
                    "optional": True,
                },
            },
        )
        def export_tool(param1: str, param2: float = 0.0):
            return {}

        register_tool(export_tool)

        # Act
        from src.tools.decorators import export_tool_schemas

        schemas = export_tool_schemas()

        # Assert
        test_schema = next(
            s for s in schemas if s["function"]["name"] == "TestTool.Export"
        )
        assert test_schema["type"] == "function"
        assert "parameters" in test_schema["function"]
        assert "param1" in test_schema["function"]["parameters"]["properties"]
        assert "param2" in test_schema["function"]["parameters"]["properties"]


class TestToolExecution:
    """Test suite for tool execution and error handling."""

    def test_tool_execution_handles_success_cases(self, mock_arcade_client):
        """TEST: Tool execution handles successful execution cases"""

        # Arrange
        @tool(name="TestTool.Success", description="Success test")
        def success_tool(input_value: str):
            return {"result": f"processed_{input_value}"}

        register_tool(success_tool)

        # Act
        from src.tools.decorators import execute_tool

        result = execute_tool("TestTool.Success", {"input_value": "test"})

        # Assert
        assert result["success"] == True
        assert result["data"]["result"] == "processed_test"
        assert "execution_time_ms" in result

    def test_tool_execution_handles_parameter_validation(self):
        """TEST: Tool execution validates parameters correctly"""

        # Arrange
        @tool(
            name="TestTool.Validation",
            description="Validation test",
            parameters={
                "required_param": {
                    "type": "string",
                    "description": "Required parameter",
                }
            },
        )
        def validation_tool(required_param: str):
            return {"value": required_param}

        register_tool(validation_tool)

        # Act & Assert
        from src.tools.decorators import execute_tool

        # Test missing required parameter
        with pytest.raises(ValidationError) as exc_info:
            execute_tool("TestTool.Validation", {})

        assert "required_param" in str(exc_info.value)

    def test_tool_execution_handles_runtime_errors_gracefully(self):
        """TEST: Tool execution handles runtime errors gracefully"""

        # Arrange
        @tool(name="TestTool.Error", description="Error test")
        def error_tool():
            raise Exception("Simulated tool error")

        register_tool(error_tool)

        # Act
        from src.tools.decorators import execute_tool

        result = execute_tool("TestTool.Error", {})

        # Assert
        assert result["success"] == False
        assert "error" in result
        assert "Simulated tool error" in result["error"]
        assert "execution_time_ms" in result

    def test_tool_execution_enforces_timeout_limits(self):
        """TEST: Tool execution enforces timeout limits"""
        # Arrange
        import time

        @tool(name="TestTool.Timeout", description="Timeout test", timeout_seconds=0.1)
        def timeout_tool():
            time.sleep(0.2)  # Sleep longer than timeout
            return {}

        register_tool(timeout_tool)

        # Act & Assert
        from src.tools.decorators import execute_tool

        with pytest.raises(ToolError) as exc_info:
            execute_tool("TestTool.Timeout", {})

        assert "timeout" in str(exc_info.value).lower()

    def test_tool_execution_logs_performance_metrics(self):
        """TEST: Tool execution logs performance metrics"""

        # Arrange
        @tool(name="TestTool.Metrics", description="Metrics test")
        def metrics_tool():
            return {"processed": True}

        register_tool(metrics_tool)

        # Act
        with patch("src.tools.decorators.logger") as mock_logger:
            from src.tools.decorators import execute_tool

            result = execute_tool("TestTool.Metrics", {})

        # Assert
        assert result["success"] == True
        assert "execution_time_ms" in result
        mock_logger.info.assert_called()
        # Check that performance metrics were logged
        log_calls = [call[0][0] for call in mock_logger.info.call_args_list]
        assert any("execution_time" in call for call in log_calls)


class TestSQLQueryTool:
    """Test suite for SQL query tool implementation."""

    def test_sql_tool_initialization_sets_proper_metadata(self):
        """TEST: SQL tool initialization sets proper metadata"""
        # Act
        sql_tool = SQLQueryTool()

        # Assert
        assert sql_tool.name == "SQL.QueryReadonly"
        assert "read-only SQL queries" in sql_tool.description.lower()
        assert "statement" in sql_tool.parameters
        assert sql_tool.parameters["statement"]["type"] == "string"

    def test_sql_tool_validates_readonly_queries(self, security_test_data):
        """TEST: SQL tool validates read-only queries"""
        # Arrange
        sql_tool = SQLQueryTool()
        dangerous_queries = [
            "DROP TABLE revenue",
            "INSERT INTO revenue VALUES ('hack', 0)",
            "UPDATE revenue SET value = 0",
            "DELETE FROM revenue",
        ]

        # Act & Assert
        for query in dangerous_queries:
            with pytest.raises(ValidationError) as exc_info:
                sql_tool.validate_parameters({"statement": query})

            assert (
                "read-only" in str(exc_info.value).lower()
                or "not allowed" in str(exc_info.value).lower()
            )

    def test_sql_tool_executes_valid_queries(self, test_database):
        """TEST: SQL tool executes valid queries correctly"""
        # Arrange
        sql_tool = SQLQueryTool(database_path=test_database)
        query = "SELECT quarter, value FROM revenue WHERE quarter = 'Q1-2025'"

        # Act
        result = sql_tool.execute({"statement": query})

        # Assert
        assert result["success"] == True
        assert "rows" in result["data"]
        assert len(result["data"]["rows"]) == 1
        assert result["data"]["rows"][0]["quarter"] == "Q1-2025"
        assert result["data"]["execution_time_ms"] < 100  # Should be fast

    def test_sql_tool_handles_database_errors(self):
        """TEST: SQL tool handles database connection errors"""
        # Arrange
        sql_tool = SQLQueryTool(database_path="/invalid/path/database.db")
        query = "SELECT * FROM revenue"

        # Act & Assert
        result = sql_tool.execute({"statement": query})

        assert result["success"] == False
        assert "error" in result
        assert (
            "connection" in result["error"].lower()
            or "database" in result["error"].lower()
        )

    def test_sql_tool_arcade_registration(self, mock_arcade_client):
        """TEST: SQL tool registers properly with Arcade.dev"""
        # Arrange
        sql_tool = SQLQueryTool()

        # Act
        with patch("src.tools.connectors.sql.arcade_client", mock_arcade_client):
            sql_tool.register_with_arcade()

        # Assert
        mock_arcade_client.tools.upload.assert_called_once()
        upload_args = mock_arcade_client.tools.upload.call_args[0][0]
        assert upload_args["name"] == "SQL.QueryReadonly"
        assert "description" in upload_args
        assert "parameters" in upload_args


class TestToolAuthorization:
    """Test suite for tool authorization and security."""

    def test_tool_authorization_validates_user_permissions(self):
        """TEST: Tool authorization validates user permissions"""

        # Arrange
        @tool(
            name="TestTool.Protected",
            description="Protected tool",
            required_scopes=["admin", "write"],
        )
        def protected_tool():
            return {}

        register_tool(protected_tool)

        # Act & Assert
        from src.tools.decorators import execute_tool_with_auth

        # Test insufficient permissions
        with pytest.raises(AuthorizationError) as exc_info:
            execute_tool_with_auth("TestTool.Protected", {}, user_scopes=["read"])

        assert "insufficient" in str(exc_info.value).lower()

    def test_tool_authorization_allows_sufficient_permissions(self):
        """TEST: Tool authorization allows execution with sufficient permissions"""

        # Arrange
        @tool(
            name="TestTool.AuthSuccess",
            description="Auth success tool",
            required_scopes=["read"],
        )
        def auth_success_tool():
            return {"authorized": True}

        register_tool(auth_success_tool)

        # Act
        from src.tools.decorators import execute_tool_with_auth

        result = execute_tool_with_auth(
            "TestTool.AuthSuccess", {}, user_scopes=["read", "write"]
        )

        # Assert
        assert result["success"] == True
        assert result["data"]["authorized"] == True

    def test_tool_authorization_logs_security_events(self):
        """TEST: Tool authorization logs security events"""

        # Arrange
        @tool(
            name="TestTool.SecurityLog",
            description="Security logging test",
            required_scopes=["admin"],
        )
        def security_log_tool():
            return {}

        register_tool(security_log_tool)

        # Act
        with patch("src.tools.decorators.security_logger") as mock_logger:
            from src.tools.decorators import execute_tool_with_auth

            try:
                execute_tool_with_auth(
                    "TestTool.SecurityLog",
                    {},
                    user_scopes=["read"],
                    user_id="test@example.com",
                )
            except AuthorizationError:
                pass

        # Assert
        mock_logger.log_authorization_failure.assert_called_once()
        args = mock_logger.log_authorization_failure.call_args[1]
        assert args["tool_name"] == "TestTool.SecurityLog"
        assert args["user_id"] == "test@example.com"


@pytest.mark.integration
class TestToolIntegration:
    """Integration tests for tool framework with external systems."""

    async def test_tool_execution_with_arcade_integration(self, mock_arcade_client):
        """TEST: Tool execution integrates properly with Arcade.dev"""
        # Arrange
        mock_arcade_client.tools.execute.return_value = {
            "status": "success",
            "data": {"result": "executed"},
            "execution_time_ms": 15,
        }

        # Act
        from src.tools.decorators import execute_tool_via_arcade

        result = await execute_tool_via_arcade(
            "SQL.QueryReadonly", {"statement": "SELECT 1"}, mock_arcade_client
        )

        # Assert
        assert result["success"] == True
        assert result["data"]["result"] == "executed"
        mock_arcade_client.tools.execute.assert_called_once()

    def test_tool_registration_uploads_to_arcade(self, mock_arcade_client):
        """TEST: Tool registration uploads properly to Arcade.dev"""

        # Arrange
        @tool(name="TestTool.Upload", description="Upload test")
        def upload_tool():
            return {}

        # Act
        from src.tools.decorators import upload_tool_to_arcade

        upload_tool_to_arcade(upload_tool, mock_arcade_client)

        # Assert
        mock_arcade_client.tools.upload.assert_called_once()
        upload_data = mock_arcade_client.tools.upload.call_args[0][0]
        assert upload_data["name"] == "TestTool.Upload"
        assert upload_data["description"] == "Upload test"
