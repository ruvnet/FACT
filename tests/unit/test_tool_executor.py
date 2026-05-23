"""
Unit tests for the FACT system tool execution framework.
Tests tool execution, security validation, rate limiting, and Arcade integration.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any

from src.tools.executor import (
    ToolExecutor,
    ToolCall,
    ToolResult,
    RateLimiter,
    create_tool_call,
    format_tool_result_for_llm,
)
from src.tools.validation import ParameterValidator, SecurityValidator
from src.arcade.client import ArcadeClient
from src.security.auth import AuthorizationManager
from src.monitoring.metrics import MetricsCollector
from src.core.errors import (
    ToolExecutionError,
    ToolValidationError,
    UnauthorizedError,
    SecurityError,
)


class TestToolCall:
    """Test suite for ToolCall data class."""

    def test_tool_call_creation_with_defaults(self):
        """TEST: ToolCall creation sets default timestamp"""
        # Arrange & Act
        call = ToolCall(
            id="test-call-1", name="TestTool.Sample", arguments={"param": "value"}
        )

        # Assert
        assert call.id == "test-call-1"
        assert call.name == "TestTool.Sample"
        assert call.arguments == {"param": "value"}
        assert call.timestamp is not None
        assert isinstance(call.timestamp, float)
        assert call.user_id is None
        assert call.session_id is None

    def test_tool_call_creation_with_all_fields(self):
        """TEST: ToolCall creation with all fields"""
        # Arrange
        timestamp = time.time()

        # Act
        call = ToolCall(
            id="test-call-2",
            name="TestTool.Complete",
            arguments={"param1": "value1", "param2": 42},
            user_id="user123",
            session_id="session456",
            timestamp=timestamp,
        )

        # Assert
        assert call.id == "test-call-2"
        assert call.name == "TestTool.Complete"
        assert call.arguments == {"param1": "value1", "param2": 42}
        assert call.user_id == "user123"
        assert call.session_id == "session456"
        assert call.timestamp == timestamp


class TestToolResult:
    """Test suite for ToolResult data class."""

    def test_successful_tool_result(self):
        """TEST: Successful tool result creation and serialization"""
        # Arrange & Act
        result = ToolResult(
            call_id="test-call-1",
            tool_name="TestTool.Sample",
            success=True,
            data={"result": "success", "value": 42},
            execution_time_ms=150.5,
        )

        # Assert
        assert result.call_id == "test-call-1"
        assert result.tool_name == "TestTool.Sample"
        assert result.success is True
        assert result.data == {"result": "success", "value": 42}
        assert result.execution_time_ms == 150.5
        assert result.status_code == 200
        assert result.error is None

    def test_failed_tool_result(self):
        """TEST: Failed tool result creation and serialization"""
        # Arrange & Act
        result = ToolResult(
            call_id="test-call-2",
            tool_name="TestTool.Failed",
            success=False,
            error="Tool execution failed",
            execution_time_ms=75.2,
            status_code=500,
        )

        # Assert
        assert result.success is False
        assert result.error == "Tool execution failed"
        assert result.status_code == 500
        assert result.data is None

    def test_tool_result_to_dict(self):
        """TEST: ToolResult to_dict method"""
        # Arrange
        result = ToolResult(
            call_id="test-call-3",
            tool_name="TestTool.Dict",
            success=True,
            data={"output": "test"},
            execution_time_ms=100.0,
            metadata={"user_id": "user123"},
        )

        # Act
        result_dict = result.to_dict()

        # Assert
        assert result_dict["call_id"] == "test-call-3"
        assert result_dict["tool_name"] == "TestTool.Dict"
        assert result_dict["success"] is True
        assert result_dict["data"] == {"output": "test"}
        assert result_dict["execution_time_ms"] == 100.0
        assert result_dict["metadata"] == {"user_id": "user123"}
        assert "error" not in result_dict


class TestRateLimiter:
    """Test suite for rate limiting functionality."""

    def test_rate_limiter_allows_under_limit(self):
        """TEST: Rate limiter allows calls under the limit"""
        # Arrange
        limiter = RateLimiter(max_calls_per_minute=10)

        # Act & Assert
        for i in range(5):
            assert limiter.can_execute() is True
            limiter.record_call()

    def test_rate_limiter_blocks_over_limit(self):
        """TEST: Rate limiter blocks calls over the limit"""
        # Arrange
        limiter = RateLimiter(max_calls_per_minute=3)

        # Act - Fill up the limit
        for i in range(3):
            assert limiter.can_execute() is True
            limiter.record_call()

        # Assert - Should block next call
        assert limiter.can_execute() is False

    def test_rate_limiter_resets_after_time_window(self):
        """TEST: Rate limiter resets after time window"""
        # Arrange
        limiter = RateLimiter(max_calls_per_minute=2)

        # Act - Fill up the limit
        limiter.record_call()
        limiter.record_call()
        assert limiter.can_execute() is False

        # Simulate time passage by manipulating the calls list
        old_time = time.time() - 70  # 70 seconds ago
        limiter.calls = [old_time, old_time]

        # Assert - Should allow calls again
        assert limiter.can_execute() is True


class TestToolExecutor:
    """Test suite for ToolExecutor main functionality."""

    @pytest.fixture
    def mock_tool_registry(self):
        """Mock tool registry with sample tools."""
        registry = Mock()
        registry.get_tool.return_value = Mock(
            name="TestTool.Sample",
            description="Sample test tool",
            parameters={"param": {"type": "string"}},
            function=Mock(return_value={"result": "success"}),
            requires_auth=False,
            timeout_seconds=30,
        )
        registry.export_all_schemas.return_value = [
            {
                "type": "function",
                "function": {
                    "name": "TestTool.Sample",
                    "description": "Sample test tool",
                    "parameters": {
                        "type": "object",
                        "properties": {"param": {"type": "string"}},
                    },
                },
            }
        ]
        return registry

    @pytest.fixture
    def mock_arcade_client(self):
        """Mock Arcade client."""
        client = AsyncMock()
        client.execute_tool.return_value = {"result": "arcade_success"}
        return client

    @pytest.fixture
    def tool_executor(self, mock_arcade_client):
        """Tool executor instance with mocked dependencies."""
        with patch("src.tools.executor.get_tool_registry") as mock_registry, patch(
            "src.tools.executor.ParameterValidator"
        ) as mock_validator, patch(
            "src.tools.executor.SecurityValidator"
        ) as mock_security, patch(
            "src.tools.executor.AuthorizationManager"
        ) as mock_auth, patch(
            "src.tools.executor.MetricsCollector"
        ) as mock_metrics:

            # Configure mocks
            mock_registry.return_value = self.mock_tool_registry()
            mock_validator.return_value.validate = Mock()
            mock_security.return_value.validate_tool_call = AsyncMock()
            mock_auth.return_value.validate_authorization = AsyncMock()
            mock_metrics.return_value.record_tool_execution = Mock()

            executor = ToolExecutor(
                arcade_client=mock_arcade_client,
                enable_rate_limiting=True,
                max_calls_per_minute=100,
            )

            return executor

    @pytest.mark.asyncio
    async def test_successful_tool_execution_local(self, tool_executor):
        """TEST: Successful tool execution without Arcade"""
        # Arrange
        tool_executor.arcade_client = None  # Force local execution
        tool_call = ToolCall(
            id="test-1", name="TestTool.Sample", arguments={"param": "test_value"}
        )

        # Act
        result = await tool_executor.execute_tool_call(tool_call)

        # Assert
        assert result.success is True
        assert result.call_id == "test-1"
        assert result.tool_name == "TestTool.Sample"
        assert result.execution_time_ms > 0
        assert result.data is not None

    @pytest.mark.asyncio
    async def test_successful_tool_execution_arcade(
        self, tool_executor, mock_arcade_client
    ):
        """TEST: Successful tool execution via Arcade"""
        # Arrange
        tool_call = ToolCall(
            id="test-2", name="TestTool.Sample", arguments={"param": "test_value"}
        )

        # Act
        result = await tool_executor.execute_tool_call(tool_call)

        # Assert
        assert result.success is True
        assert result.call_id == "test-2"
        mock_arcade_client.execute_tool.assert_called_once()

    @pytest.mark.asyncio
    async def test_tool_execution_rate_limiting(self, tool_executor):
        """TEST: Tool execution respects rate limiting"""
        # Arrange
        tool_executor.rate_limiter.max_calls = 1
        tool_executor.rate_limiter.calls = [time.time()]  # Already at limit

        tool_call = ToolCall(
            id="test-3", name="TestTool.Sample", arguments={"param": "test_value"}
        )

        # Act
        result = await tool_executor.execute_tool_call(tool_call)

        # Assert
        assert result.success is False
        assert "rate limit" in result.error.lower()

    @pytest.mark.asyncio
    async def test_tool_execution_validation_error(self, tool_executor):
        """TEST: Tool execution handles validation errors"""
        # Arrange
        tool_executor.parameter_validator.validate.side_effect = ToolValidationError(
            "Invalid parameter"
        )

        tool_call = ToolCall(
            id="test-4", name="TestTool.Sample", arguments={"invalid_param": "value"}
        )

        # Act
        result = await tool_executor.execute_tool_call(tool_call)

        # Assert
        assert result.success is False
        assert "validation failed" in result.error.lower()
        assert result.status_code == 400

    @pytest.mark.asyncio
    async def test_tool_execution_security_error(self, tool_executor):
        """TEST: Tool execution handles security violations"""
        # Arrange
        tool_executor.security_validator.validate_tool_call.side_effect = SecurityError(
            "Security violation"
        )

        tool_call = ToolCall(
            id="test-5", name="TestTool.Sample", arguments={"param": "malicious_value"}
        )

        # Act
        result = await tool_executor.execute_tool_call(tool_call)

        # Assert
        assert result.success is False
        assert "security" in result.error.lower()
        assert result.status_code == 403

    @pytest.mark.asyncio
    async def test_tool_execution_authorization_error(self, tool_executor):
        """TEST: Tool execution handles authorization failures"""
        # Arrange
        tool_executor.tool_registry.get_tool.return_value.requires_auth = True
        tool_executor.auth_manager.validate_authorization.side_effect = (
            UnauthorizedError("No authorization")
        )

        tool_call = ToolCall(
            id="test-6",
            name="TestTool.Sample",
            arguments={"param": "value"},
            user_id="unauthorized_user",
        )

        # Act
        result = await tool_executor.execute_tool_call(tool_call)

        # Assert
        assert result.success is False
        assert "authorization" in result.error.lower()
        assert result.status_code == 401

    @pytest.mark.asyncio
    async def test_multiple_tool_execution(self, tool_executor):
        """TEST: Executor handles multiple concurrent tool calls"""
        # Arrange
        tool_calls = [
            ToolCall(
                id=f"test-{i}",
                name="TestTool.Sample",
                arguments={"param": f"value_{i}"},
            )
            for i in range(3)
        ]

        # Act
        results = await tool_executor.execute_tool_calls(tool_calls)

        # Assert
        assert len(results) == 3
        for i, result in enumerate(results):
            assert result.call_id == f"test-{i}"
            assert result.tool_name == "TestTool.Sample"

    def test_get_available_tools(self, tool_executor):
        """TEST: Get available tools returns schema list"""
        # Act
        tools = tool_executor.get_available_tools()

        # Assert
        assert isinstance(tools, list)
        assert len(tools) > 0
        assert tools[0]["type"] == "function"

    def test_get_tool_info(self, tool_executor):
        """TEST: Get tool info returns detailed information"""
        # Act
        info = tool_executor.get_tool_info("TestTool.Sample")

        # Assert
        assert info["name"] == "TestTool.Sample"
        assert "description" in info
        assert "parameters" in info
        assert "version" in info


class TestUtilityFunctions:
    """Test suite for utility functions."""

    def test_create_tool_call_with_defaults(self):
        """TEST: create_tool_call generates proper ToolCall"""
        # Act
        call = create_tool_call("TestTool.Utility", {"param": "value"})

        # Assert
        assert call.name == "TestTool.Utility"
        assert call.arguments == {"param": "value"}
        assert call.id is not None
        assert call.user_id is None

    def test_create_tool_call_with_custom_id(self):
        """TEST: create_tool_call respects custom call_id"""
        # Act
        call = create_tool_call(
            "TestTool.Custom",
            {"param": "value"},
            call_id="custom-id-123",
            user_id="user456",
        )

        # Assert
        assert call.id == "custom-id-123"
        assert call.user_id == "user456"

    def test_format_tool_result_for_llm_success(self):
        """TEST: format_tool_result_for_llm handles successful results"""
        # Arrange
        result = ToolResult(
            call_id="test-format-1",
            tool_name="TestTool.Format",
            success=True,
            data={"output": "formatted_result"},
        )

        # Act
        formatted = format_tool_result_for_llm(result)

        # Assert
        assert formatted["role"] == "tool"
        assert formatted["tool_call_id"] == "test-format-1"
        assert formatted["name"] == "TestTool.Format"
        assert "output" in formatted["content"]
        assert "formatted_result" in formatted["content"]

    def test_format_tool_result_for_llm_error(self):
        """TEST: format_tool_result_for_llm handles error results"""
        # Arrange
        result = ToolResult(
            call_id="test-format-2",
            tool_name="TestTool.Error",
            success=False,
            error="Something went wrong",
            execution_time_ms=100.0,
        )

        # Act
        formatted = format_tool_result_for_llm(result)

        # Assert
        assert formatted["role"] == "tool"
        assert formatted["tool_call_id"] == "test-format-2"
        assert "error" in formatted["content"]
        assert "Something went wrong" in formatted["content"]


@pytest.mark.integration
class TestToolExecutorIntegration:
    """Integration tests for tool executor with real dependencies."""

    @pytest.mark.asyncio
    async def test_end_to_end_tool_execution(self):
        """TEST: End-to-end tool execution without mocks"""
        # This test would require actual tool registration and execution
        # For now, we'll skip it to avoid dependency issues
        pytest.skip("Integration test requires full system setup")

    @pytest.mark.asyncio
    async def test_arcade_integration(self):
        """TEST: Integration with actual Arcade client"""
        # This test would require actual Arcade.dev connection
        # For now, we'll skip it to avoid external dependencies
        pytest.skip("Integration test requires Arcade.dev connection")


@pytest.fixture
def sample_tool_call():
    """Fixture providing a sample tool call for testing."""
    return ToolCall(
        id="sample-call-123",
        name="TestTool.Sample",
        arguments={"input": "test_input", "count": 5},
        user_id="test_user_123",
    )


@pytest.fixture
def sample_tool_result():
    """Fixture providing a sample tool result for testing."""
    return ToolResult(
        call_id="sample-call-123",
        tool_name="TestTool.Sample",
        success=True,
        data={"output": "processed_result", "count": 5},
        execution_time_ms=125.7,
        metadata={"version": "1.0.0"},
    )
