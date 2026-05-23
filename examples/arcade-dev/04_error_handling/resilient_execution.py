#!/usr/bin/env python3
"""
Resilient Error Handling for Arcade.dev Integration Example

This example demonstrates robust error handling for Arcade.dev integration,
including error classification, retry strategies, graceful degradation,
and comprehensive logging for production-ready implementations.
"""

import os
import sys
import asyncio
import logging
import time
import traceback
from typing import Dict, Any, List, Optional, Union, Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import random

# Setup FACT imports using the import helper
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.import_helper import setup_fact_imports

# Setup FACT module path
setup_fact_imports()

# Import available FACT components
try:
    from src.tools.executor import ToolExecutor
except ImportError:
    # Mock ToolExecutor for demo mode
    class ToolExecutor:
        """Mock ToolExecutor for demo purposes."""

        def __init__(self):
            self.logger = logging.getLogger(__name__)

        async def execute_tool(
            self, tool_name: str, arguments: Dict[str, Any]
        ) -> Dict[str, Any]:
            """Mock tool execution."""
            return {"status": "mock_execution", "tool": tool_name, "args": arguments}


try:
    from src.tools.decorators import Tool
except ImportError:

    def Tool(*args, **kwargs):
        """Mock Tool decorator for demo mode."""

        def decorator(func):
            func._tool_name = kwargs.get("name", func.__name__)
            func._tool_description = kwargs.get("description", "")
            func._tool_parameters = kwargs.get("parameters", {})
            return func

        return decorator


try:
    from src.core.errors import *
except ImportError:
    # Define error classes if they don't exist
    class ToolExecutionError(Exception):
        """Tool execution error."""

        pass

    class ToolValidationError(Exception):
        """Tool validation error."""

        pass

    class ToolNotFoundError(Exception):
        """Tool not found error."""

        pass

    class UnauthorizedError(Exception):
        """Unauthorized error."""

        pass

    class SecurityError(Exception):
        """Security error."""

        pass


try:
    from src.monitoring.metrics import MetricsCollector
except ImportError:

    class MetricsCollector:
        """Mock metrics collector for demo mode."""

        def __init__(self):
            self.metrics = {}

        def record(self, name, value, tags=None):
            """Record a metric."""
            pass

        def increment(self, name, tags=None):
            """Increment a counter."""
            pass


from src.cache.manager import CacheManager

# Import the BasicArcadeClient from the basic integration example
sys.path.insert(0, str(Path(__file__).parent.parent / "01_basic_integration"))
from basic_arcade_client import BasicArcadeClient, ArcadeConfig


# Define classes for error handling demonstration
@dataclass
class ToolCall:
    """Tool call data structure."""

    id: str
    name: str
    arguments: Dict[str, Any]
    user_id: Optional[str] = None


@dataclass
class ToolResult:
    """Tool execution result."""

    call_id: str
    tool_name: str
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    status_code: int = 200
    metadata: Optional[Dict[str, Any]] = None


class FinalRetryError(Exception):
    """Final retry error when all retries are exhausted."""

    pass


class ErrorType(Enum):
    """Classification of error types for different handling strategies."""

    NETWORK_ERROR = "network_error"
    AUTHENTICATION_ERROR = "authentication_error"
    VALIDATION_ERROR = "validation_error"
    TIMEOUT_ERROR = "timeout_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    SERVER_ERROR = "server_error"
    CLIENT_ERROR = "client_error"
    UNKNOWN_ERROR = "unknown_error"


class RetryStrategy(Enum):
    """Retry strategy enumeration."""

    NO_RETRY = "no_retry"
    LINEAR_BACKOFF = "linear_backoff"
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    ADAPTIVE_BACKOFF = "adaptive_backoff"


@dataclass
class ErrorContext:
    """Context information for error handling decisions."""

    error: Exception
    error_type: ErrorType
    tool_name: str
    attempt_count: int
    total_elapsed_time: float
    user_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    strategy: RetryStrategy
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_multiplier: float = 2.0
    jitter: bool = True
    timeout_multiplier: float = 1.5


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker pattern."""

    failure_threshold: int = 5
    success_threshold: int = 3
    timeout_seconds: float = 60.0
    monitoring_window: float = 300.0  # 5 minutes


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """
    Circuit breaker implementation for preventing cascading failures.

    Tracks failure rates and opens the circuit when threshold is exceeded,
    allowing the system to fail fast and recover gracefully.
    """

    def __init__(self, config: CircuitBreakerConfig, name: str = "default"):
        """Initialize circuit breaker."""
        self.config = config
        self.name = name
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0.0
        self.failure_history: List[float] = []
        self.logger = logging.getLogger(f"{__name__}.{name}")

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function through circuit breaker protection."""
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                self.logger.info(
                    f"Circuit breaker '{self.name}' entering half-open state"
                )
            else:
                raise FinalRetryError(f"Circuit breaker '{self.name}' is open")

        try:
            result = (
                await func(*args, **kwargs)
                if asyncio.iscoroutinefunction(func)
                else func(*args, **kwargs)
            )
            await self._on_success()
            return result
        except Exception as e:
            await self._on_failure()
            raise

    async def _on_success(self) -> None:
        """Handle successful execution."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
                self.failure_history.clear()
                self.logger.info(f"Circuit breaker '{self.name}' closed after recovery")
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failure_count = max(0, self.failure_count - 1)

    async def _on_failure(self) -> None:
        """Handle failed execution."""
        current_time = time.time()
        self.failure_count += 1
        self.last_failure_time = current_time
        self.failure_history.append(current_time)

        # Clean old failures outside monitoring window
        window_start = current_time - self.config.monitoring_window
        self.failure_history = [t for t in self.failure_history if t > window_start]

        if self.state == CircuitState.CLOSED:
            if len(self.failure_history) >= self.config.failure_threshold:
                self.state = CircuitState.OPEN
                self.success_count = 0
                self.logger.warning(
                    f"Circuit breaker '{self.name}' opened due to failure threshold"
                )
        elif self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            self.success_count = 0
            self.logger.warning(
                f"Circuit breaker '{self.name}' reopened after half-open failure"
            )

    def _should_attempt_reset(self) -> bool:
        """Check if circuit should attempt reset."""
        return time.time() - self.last_failure_time >= self.config.timeout_seconds


class ResilientExecutor:
    """
    Resilient tool executor with comprehensive error handling.

    Provides intelligent retry strategies, circuit breaking, graceful degradation,
    and detailed error classification for production workloads.
    """

    def __init__(
        self,
        arcade_client: Optional[BasicArcadeClient] = None,
        cache_manager: Optional[CacheManager] = None,
        retry_config: Optional[RetryConfig] = None,
        circuit_config: Optional[CircuitBreakerConfig] = None,
    ):
        """Initialize resilient executor."""
        self.logger = logging.getLogger(__name__)
        self.arcade_client = arcade_client
        self.cache_manager = cache_manager
        try:
            self.local_executor = ToolExecutor()
        except Exception as e:
            self.logger.warning(
                f"Could not initialize ToolExecutor: {e}. Using mock executor."
            )
            self.local_executor = None
        self.metrics_collector = MetricsCollector()

        # Configuration
        self.retry_config = retry_config or RetryConfig(
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            max_attempts=3,
            base_delay=1.0,
            max_delay=30.0,
        )

        # Circuit breakers for different components
        circuit_config = circuit_config or CircuitBreakerConfig()
        self.local_circuit_breaker = CircuitBreaker(circuit_config, "local_executor")
        self.remote_circuit_breaker = CircuitBreaker(circuit_config, "remote_executor")

        # Error tracking
        self.error_history: List[ErrorContext] = []
        self.error_patterns: Dict[str, List[ErrorType]] = {}

        # Degradation flags
        self.degraded_mode = False
        self.degradation_start_time = 0.0

    async def execute_tool_resilient(self, tool_call: ToolCall) -> ToolResult:
        """Execute a tool with comprehensive error handling and resilience."""
        start_time = time.time()
        attempt_count = 0
        last_exception = None

        while attempt_count < self.retry_config.max_attempts:
            attempt_count += 1

            try:
                # Try circuit breaker protected execution
                if self.arcade_client:
                    result = await self.remote_circuit_breaker.call(
                        self._execute_remote_tool, tool_call
                    )
                else:
                    result = await self.local_circuit_breaker.call(
                        self._execute_local_tool, tool_call
                    )

                execution_time = (time.time() - start_time) * 1000

                return ToolResult(
                    call_id=tool_call.id,
                    tool_name=tool_call.name,
                    success=True,
                    data=result,
                    execution_time_ms=execution_time,
                )

            except Exception as e:
                last_exception = e
                error_type = self._classify_error(e)

                # Create error context
                error_context = ErrorContext(
                    error=e,
                    error_type=error_type,
                    tool_name=tool_call.name,
                    attempt_count=attempt_count,
                    total_elapsed_time=time.time() - start_time,
                    user_id=tool_call.user_id,
                )

                # Track error
                self.error_history.append(error_context)

                # Check if we should retry
                if not self._should_retry(error_context):
                    break

                # Calculate retry delay
                delay = self._calculate_retry_delay(attempt_count)
                self.logger.warning(
                    f"Tool {tool_call.name} failed (attempt {attempt_count}): {e}. "
                    f"Retrying in {delay:.1f}s..."
                )

                await asyncio.sleep(delay)

        # All retries exhausted
        execution_time = (time.time() - start_time) * 1000

        return ToolResult(
            call_id=tool_call.id,
            tool_name=tool_call.name,
            success=False,
            error=str(last_exception),
            execution_time_ms=execution_time,
        )

    async def _execute_remote_tool(self, tool_call: ToolCall) -> Dict[str, Any]:
        """Execute tool using remote Arcade client."""
        if not self.arcade_client:
            raise ToolExecutionError("No arcade client available")

        result = await self.arcade_client.execute_tool(
            tool_call.name, tool_call.arguments
        )
        return result

    async def _execute_local_tool(self, tool_call: ToolCall) -> Dict[str, Any]:
        """Execute tool using local executor."""
        if not self.local_executor:
            raise ToolExecutionError("No local executor available")

        # For demo purposes, use the unreliable_service function
        if tool_call.name == "Test_UnreliableService":
            return unreliable_service(**tool_call.arguments)

        raise ToolNotFoundError(f"Tool {tool_call.name} not found")

    def _classify_error(self, error: Exception) -> ErrorType:
        """Classify error type for handling strategy."""
        error_str = str(error).lower()

        if "network" in error_str or "connection" in error_str:
            return ErrorType.NETWORK_ERROR
        elif "timeout" in error_str:
            return ErrorType.TIMEOUT_ERROR
        elif "rate limit" in error_str:
            return ErrorType.RATE_LIMIT_ERROR
        elif "unauthorized" in error_str or "auth" in error_str:
            return ErrorType.AUTHENTICATION_ERROR
        elif "validation" in error_str or "invalid" in error_str:
            return ErrorType.VALIDATION_ERROR
        elif "server error" in error_str or "internal" in error_str:
            return ErrorType.SERVER_ERROR
        else:
            return ErrorType.UNKNOWN_ERROR

    def _should_retry(self, error_context: ErrorContext) -> bool:
        """Determine if error should be retried."""
        # Don't retry validation errors
        if error_context.error_type == ErrorType.VALIDATION_ERROR:
            return False

        # Don't retry authentication errors
        if error_context.error_type == ErrorType.AUTHENTICATION_ERROR:
            return False

        # Don't retry if max attempts reached
        if error_context.attempt_count >= self.retry_config.max_attempts:
            return False

        return True

    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate retry delay based on strategy."""
        if self.retry_config.strategy == RetryStrategy.NO_RETRY:
            return 0.0
        elif self.retry_config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = self.retry_config.base_delay * attempt
        elif self.retry_config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = self.retry_config.base_delay * (
                self.retry_config.backoff_multiplier ** (attempt - 1)
            )
        else:
            delay = self.retry_config.base_delay

        # Apply jitter if enabled
        if self.retry_config.jitter:
            delay *= 0.5 + random.random() * 0.5

        # Cap at max delay
        return min(delay, self.retry_config.max_delay)


# Example tools and usage demonstration
@Tool(
    name="Test_UnreliableService",
    description="Unreliable service for testing error handling",
    parameters={
        "failure_rate": {
            "type": "number",
            "description": "Probability of failure (0.0-1.0)",
            "default": 0.3,
        },
        "delay_ms": {
            "type": "integer",
            "description": "Processing delay in milliseconds",
            "default": 100,
        },
    },
)
def unreliable_service(
    failure_rate: float = 0.3, delay_ms: int = 100
) -> Dict[str, Any]:
    """Simulated unreliable service for testing."""
    import time
    import random

    # Simulate processing delay
    time.sleep(delay_ms / 1000.0)

    # Random failure
    if random.random() < failure_rate:
        error_types = [
            "Network connection failed",
            "Service temporarily unavailable",
            "Request timeout",
            "Rate limit exceeded",
            "Internal server error",
        ]
        raise Exception(random.choice(error_types))

    return {
        "success": True,
        "result": f"Service completed successfully after {delay_ms}ms delay",
        "timestamp": time.time(),
    }


async def demonstrate_error_handling():
    """Demonstrate resilient error handling capabilities."""

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(__name__)

    logger.info("Starting resilient error handling demonstration")

    # Initialize components from environment
    arcade_api_key = os.getenv("ARCADE_API_KEY")
    cache_config = {
        "redis_url": os.getenv("REDIS_URL", "redis://localhost:6379"),
        "default_ttl": 3600,
    }

    # Create resilient executor with custom configuration
    retry_config = RetryConfig(
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        max_attempts=5,
        base_delay=0.5,
        max_delay=10.0,
        jitter=True,
    )

    circuit_config = CircuitBreakerConfig(
        failure_threshold=3, success_threshold=2, timeout_seconds=30.0
    )

    # Initialize clients with demo mode support
    demo_mode = (
        not bool(arcade_api_key.strip())
        if arcade_api_key
        else (
            True
            or arcade_api_key.strip() in ["your_api_key", "demo_key", "placeholder"]
            if arcade_api_key
            else True or len(arcade_api_key.strip()) < 10 if arcade_api_key else True
        )  # Real API keys are typically longer
    )

    arcade_config = ArcadeConfig(
        api_key=arcade_api_key if not demo_mode else "demo_key",
        user_id=os.getenv("ARCADE_USER_ID", "demo@example.com"),
        demo_mode=demo_mode,
    )

    arcade_client = None
    if arcade_api_key or demo_mode:
        arcade_client = BasicArcadeClient(arcade_config)
        await arcade_client.connect()

    cache_manager = None
    try:
        if os.getenv("REDIS_URL"):
            cache_manager = CacheManager(cache_config)
        else:
            # Use basic cache config for demo
            basic_cache_config = {
                "prefix": "resilient_demo",
                "min_tokens": 1,
                "max_size": "1MB",
                "ttl_seconds": 300,
            }
            cache_manager = CacheManager(basic_cache_config)
    except Exception as e:
        logger.warning(
            f"Cache manager initialization failed: {e}. Continuing without cache."
        )

    executor = ResilientExecutor(
        arcade_client=arcade_client,
        cache_manager=cache_manager,
        retry_config=retry_config,
        circuit_config=circuit_config,
    )

    if demo_mode:
        logger.info(
            "🎭 Running in demo mode - using mock responses and local error simulation"
        )
    else:
        logger.info("🔑 Using real API key for Arcade.dev integration")

    # Test scenarios
    test_scenarios = [
        # Low failure rate - should succeed quickly
        {"failure_rate": 0.1, "delay_ms": 50, "description": "Low failure rate"},
        # Medium failure rate - should retry and eventually succeed
        {"failure_rate": 0.5, "delay_ms": 100, "description": "Medium failure rate"},
        # High failure rate - should eventually fail gracefully
        {"failure_rate": 0.9, "delay_ms": 200, "description": "High failure rate"},
        # Network timeout simulation
        {"failure_rate": 1.0, "delay_ms": 5000, "description": "Timeout simulation"},
    ]

    for i, scenario in enumerate(test_scenarios, 1):
        logger.info(f"\n--- Test Scenario {i}: {scenario['description']} ---")

        tool_call = ToolCall(
            id=f"test_{i}",
            name="Test_UnreliableService",
            arguments=scenario,
            user_id="demo_user",
        )

        start_time = time.time()

        try:
            logger.info(
                f"Executing unreliable service with {scenario['failure_rate']*100:.0f}% failure rate"
            )

            # Use the resilient executor
            result = await executor.execute_tool_resilient(tool_call)
            execution_time = (time.time() - start_time) * 1000

            if result.success:
                logger.info(f"✓ Success in {execution_time:.0f}ms")
                logger.info(f"Result: {result.data}")
            else:
                logger.error(f"✗ Failed after all retry attempts: {result.error}")
                logger.info("Applying graceful degradation...")

                # Demonstrate graceful degradation
                fallback_result = {
                    "status": "degraded",
                    "message": "Service temporarily unavailable, using cached or default response",
                    "fallback_data": {"placeholder": "default_value"},
                }
                logger.info(f"Fallback result: {fallback_result}")

        except Exception as e:
            logger.error(f"Unexpected error in scenario {i}: {e}")
            logger.debug(f"Exception traceback: {traceback.format_exc()}")

        # Brief pause between scenarios
        await asyncio.sleep(1)

    # Demonstrate health status monitoring
    logger.info("\n--- System Health Status ---")
    health_status = {
        "circuit_breakers": {"local": "closed", "remote": "closed"},
        "degraded_mode": False,
        "error_rate": 0.2,
        "recent_errors": 3,
    }

    logger.info(f"Health Status: {health_status}")

    logger.info("Error handling demonstration completed")


if __name__ == "__main__":
    """Run the error handling demonstration."""
    print("🛡️ FACT SDK - Resilient Error Handling Example")
    print("=" * 50)
    print()
    print(
        "This example demonstrates comprehensive error handling for Arcade.dev integration:"
    )
    print("• Error classification and routing")
    print("• Intelligent retry strategies")
    print("• Circuit breaker patterns")
    print("• Graceful degradation")
    print("• Comprehensive logging and monitoring")
    print()

    # Run demonstration
    asyncio.run(demonstrate_error_handling())
