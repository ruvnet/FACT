"""
FACT System Main Driver

This module implements the central orchestrator for the FACT system,
managing cache, queries, and tool execution following the architecture specification.
"""

import asyncio
import time
import os
from typing import Dict, List, Any, Optional
import structlog

# Import Anthropic SDK directly (LiteLLM has compatibility issues)
import anthropic

from .config import Config, get_config, validate_configuration
from .errors import (
    FACTError,
    ConfigurationError,
    ConnectionError,
    ToolExecutionError,
    classify_error,
    create_user_friendly_message,
    log_error_with_context,
    provide_graceful_degradation,
    CacheError,
)

try:
    # Try relative imports first (when used as package)
    from ..db.connection import DatabaseManager
    from ..tools.decorators import get_tool_registry
    from ..tools.connectors.sql import initialize_sql_tool
    from ..monitoring.metrics import get_metrics_collector
    from ..cache import initialize_cache_system, get_cache_system, FACTCacheSystem
    from ..cache.resilience import ResilientCacheWrapper, CacheCircuitBreaker
except ImportError:
    # Fall back to absolute imports (when run as script)
    import sys
    from pathlib import Path

    # Add src to path if not already there
    src_path = str(Path(__file__).parent.parent)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    from db.connection import DatabaseManager
    from tools.decorators import get_tool_registry
    from tools.connectors.sql import initialize_sql_tool
    from monitoring.metrics import get_metrics_collector
    from cache import initialize_cache_system, get_cache_system, FACTCacheSystem
    from cache.resilience import ResilientCacheWrapper, CacheCircuitBreaker


logger = structlog.get_logger(__name__)


class FACTDriver:
    """

    Manages cache control, query processing, tool execution, and system coordination
    following the FACT architecture principles.
    """

    def __init__(self, config: Optional[Config] = None):
        """
        Initialize FACT driver with configuration.

        Args:
            config: Optional configuration instance (creates default if None)
        """
        self.config = config or get_config()
        self.database_manager: Optional[DatabaseManager] = None
        self.tool_registry = get_tool_registry()
        self.cache_system: Optional[FACTCacheSystem] = None
        self._initialized = False

        # Monitoring and metrics
        self.metrics_collector = get_metrics_collector()

        # Cache resilience components
        self.cache_circuit_breaker: Optional[CacheCircuitBreaker] = None
        self.resilient_cache: Optional[ResilientCacheWrapper] = None
        self._cache_degraded = False

    async def initialize(self) -> None:
        """
        Initialize the FACT system components.

        Raises:
            ConfigurationError: If configuration is invalid
            ConnectionError: If service connections fail
        """
        if self._initialized:
            logger.info("FACT driver already initialized")
            return

        try:
            logger.info("Initializing FACT system")

            # Validate configuration
            validate_configuration(self.config)

            # Initialize database
            await self._initialize_database()

            # Initialize cache system
            await self._initialize_cache()

            # Initialize tools
            await self._initialize_tools()

            # Test connections
            await self._test_connections()

            self._initialized = True
            logger.info("FACT system initialized successfully")

        except Exception as e:
            logger.error("FACT system initialization failed", error=str(e))
            raise ConfigurationError(f"System initialization failed: {e}")

    async def process_query(self, user_input: str) -> str:
        """
        Process a user query through the FACT pipeline.

        Args:
            user_input: Natural language query from user

        Returns:
            Generated response string

        Raises:
            FACTError: If query processing fails
        """
        if not self._initialized:
            await self.initialize()

        query_id = f"query_{int(time.time() * 1000)}"
        start_time = time.time()

        try:
            logger.info(
                "Processing user query", query_id=query_id, query=user_input[:100]
            )

            # Step 1: Check cache first (cache-first pattern) with resilience
            cached_response = None
            if not self._cache_degraded:
                try:
                    if self.resilient_cache:
                        # Use resilient cache with circuit breaker
                        query_hash = self.resilient_cache.generate_hash(user_input)
                        cache_entry = await self.resilient_cache.get(query_hash)
                        if cache_entry:
                            cached_response = cache_entry.content
                    elif self.cache_system:
                        # Fallback to direct cache system
                        cached_response = await self.cache_system.get_cached_response(
                            user_input
                        )

                except CacheError as e:
                    if "CIRCUIT_BREAKER" in str(e.error_code):
                        logger.info(
                            "Cache circuit breaker active - proceeding without cache",
                            query_id=query_id,
                            circuit_state=(
                                self.cache_circuit_breaker.get_state().value
                                if self.cache_circuit_breaker
                                else "unknown"
                            ),
                        )
                    else:
                        logger.warning(
                            "Cache operation failed - continuing without cache",
                            query_id=query_id,
                            error=str(e),
                        )
                except Exception as e:
                    logger.warning(
                        "Unexpected cache error - continuing without cache",
                        query_id=query_id,
                        error=str(e),
                    )

            if cached_response:
                # Cache hit - return cached response
                end_time = time.time()
                latency = (end_time - start_time) * 1000

                logger.info(
                    "Cache hit - returning cached response",
                    query_id=query_id,
                    latency_ms=latency,
                )

                return cached_response

            # Step 2: Cache miss - process query normally
            logger.info("Cache miss - processing query with LLM", query_id=query_id)

            # Prepare messages for LLM
            messages = [{"role": "user", "content": user_input}]

            # Get tool schemas for LLM
            tool_schemas = self.tool_registry.export_all_schemas()

            # Make initial LLM call with cache control
            response = await self._call_llm_with_cache(
                messages=messages, tools=tool_schemas, cache_mode="read"
            )

            # Handle tool calls if present (Anthropic format)
            tool_use_blocks = []
            if hasattr(response, "content") and response.content:
                for block in response.content:
                    if hasattr(block, "type") and block.type == "tool_use":
                        tool_use_blocks.append(block)

            if tool_use_blocks:
                logger.info("Processing tool calls", count=len(tool_use_blocks))

                # Add assistant message with tool_use blocks to conversation
                assistant_message = {"role": "assistant", "content": response.content}
                messages.append(assistant_message)

                # Execute tool calls
                tool_results = await self._execute_tool_calls(tool_use_blocks)

                # Add tool results to message history
                messages.extend(tool_results)

                # Get final response with tool results
                response = await self._call_llm_with_cache(
                    messages=messages, tools=tool_schemas, cache_mode="read"
                )

                # Check if the final response also has tool calls
                final_tool_blocks = []
                if hasattr(response, "content") and response.content:
                    for block in response.content:
                        if hasattr(block, "type") and block.type == "tool_use":
                            final_tool_blocks.append(block)

                # Execute any final tool calls and continue until we get text response
                max_iterations = 5  # Prevent infinite loops
                iteration = 0

                while final_tool_blocks and iteration < max_iterations:
                    logger.info(
                        "Processing final tool calls",
                        count=len(final_tool_blocks),
                        iteration=iteration,
                    )

                    # Add assistant message with tool_use blocks
                    assistant_message = {
                        "role": "assistant",
                        "content": response.content,
                    }
                    messages.append(assistant_message)

                    # Execute final tool calls
                    final_tool_results = await self._execute_tool_calls(
                        final_tool_blocks
                    )

                    # Add final tool results
                    messages.extend(final_tool_results)

                    # Get final response
                    response = await self._call_llm_with_cache(
                        messages=messages, tools=tool_schemas, cache_mode="read"
                    )

                    # Check if this response also has tool calls
                    final_tool_blocks = []
                    if hasattr(response, "content") and response.content:
                        for block in response.content:
                            if hasattr(block, "type") and block.type == "tool_use":
                                final_tool_blocks.append(block)

                    iteration += 1

            # Extract response content from Anthropic SDK response
            response_text = ""
            if hasattr(response, "content") and response.content:
                for block in response.content:
                    if hasattr(block, "type") and block.type == "text":
                        response_text += block.text

            # If no text content found, provide informative message
            if not response_text:
                logger.warning("No text response received from LLM", query_id=query_id)
                response_text = "I apologize, but I was unable to generate a proper response. Please try rephrasing your question."

            # Step 3: Store response in cache for future use with resilience
            if not self._cache_degraded and response_text:
                try:
                    if self.resilient_cache:
                        # Use resilient cache with circuit breaker
                        query_hash = self.resilient_cache.generate_hash(user_input)
                        cache_entry = await self.resilient_cache.store(
                            query_hash, response_text
                        )
                        if cache_entry:
                            logger.debug("Response stored in cache", query_id=query_id)
                        else:
                            logger.debug(
                                "Response not suitable for caching", query_id=query_id
                            )
                    elif self.cache_system:
                        # Fallback to direct cache system
                        cache_stored = await self.cache_system.store_response(
                            user_input, response_text
                        )
                        if cache_stored:
                            logger.debug("Response stored in cache", query_id=query_id)
                        else:
                            logger.debug(
                                "Response not suitable for caching", query_id=query_id
                            )

                except CacheError as e:
                    if "CIRCUIT_BREAKER" in str(e.error_code):
                        logger.debug(
                            "Cache storage skipped - circuit breaker active",
                            query_id=query_id,
                        )
                    else:
                        logger.warning(
                            "Cache storage failed - continuing without cache storage",
                            query_id=query_id,
                            error=str(e),
                        )
                except Exception as e:
                    logger.warning(
                        "Unexpected cache storage error",
                        query_id=query_id,
                        error=str(e),
                    )

            # Log performance metrics
            end_time = time.time()
            latency = (end_time - start_time) * 1000

            logger.info(
                "Query processed successfully",
                query_id=query_id,
                latency_ms=latency,
                response_length=len(response_text),
            )

            return response_text

        except Exception as e:
            end_time = time.time()
            latency = (end_time - start_time) * 1000

            # Record error in metrics collector
            self.metrics_collector.record_tool_execution(
                tool_name="fact_query",
                success=False,
                execution_time=latency,
                error_type=type(e).__name__,
                metadata={"query_id": query_id},
            )

            # Log error with context
            log_error_with_context(
                e,
                {
                    "query_id": query_id,
                    "user_input": user_input[:100],
                    "latency_ms": latency,
                },
            )

            # Handle error with graceful degradation
            error_category = classify_error(e)

            if error_category in ["connectivity", "tool_execution"]:
                return provide_graceful_degradation(error_category)
            else:
                return create_user_friendly_message(e)

    async def _initialize_database(self) -> None:
        """Initialize database connection and schema."""
        try:
            self.database_manager = DatabaseManager(self.config.database_path)
            await self.database_manager.initialize_database()
            logger.info("Database initialized successfully")

        except Exception as e:
            logger.error("Database initialization failed", error=str(e))
            raise ConfigurationError(f"Database initialization failed: {e}")

    async def _initialize_cache(self) -> None:
        """Initialize cache system with resilience and circuit breaker protection."""
        try:
            cache_config = self.config.cache_config

            # Initialize base cache system
            self.cache_system = await initialize_cache_system(
                config=cache_config, enable_background_tasks=True
            )

            # Initialize circuit breaker for cache resilience
            from ..cache.resilience import CircuitBreakerConfig

            circuit_config = CircuitBreakerConfig(
                failure_threshold=5,  # Open after 5 failures
                success_threshold=3,  # Close after 3 successes
                timeout_seconds=60.0,  # Wait 60s before retry
                rolling_window_seconds=300.0,  # 5-minute window
                gradual_recovery=True,
                recovery_factor=0.5,  # 50% of requests during recovery
            )

            self.cache_circuit_breaker = CacheCircuitBreaker(circuit_config)

            # Wrap cache system with resilient wrapper
            if hasattr(self.cache_system, "cache_manager"):
                self.resilient_cache = ResilientCacheWrapper(
                    self.cache_system.cache_manager, self.cache_circuit_breaker
                )

                # Start health monitoring
                await self.resilient_cache.start_monitoring()

            logger.info(
                "Cache system with resilience initialized successfully",
                prefix=cache_config["prefix"],
                max_size=cache_config["max_size"],
                circuit_breaker_enabled=True,
            )

        except Exception as e:
            logger.error("Cache system initialization failed", error=str(e))
            # Enable graceful degradation - continue without cache
            self._cache_degraded = True
            logger.warning("Continuing with cache degradation mode")

    async def _initialize_tools(self) -> None:
        """Initialize and register system tools."""
        try:
            # Initialize SQL tool with database manager
            initialize_sql_tool(self.database_manager)

            # Log registered tools
            tool_info = self.tool_registry.get_tool_info()
            logger.info("Tools initialized", **tool_info)

        except Exception as e:
            logger.error("Tool initialization failed", error=str(e))
            raise ConfigurationError(f"Tool initialization failed: {e}")

    async def _test_connections(self) -> None:
        """Test connections to external services."""
        # Skip API validation if configured for testing
        if os.getenv("SKIP_API_VALIDATION", "false").lower() == "true":
            logger.info("Skipping API validation for testing environment")
            return

        try:
            # Test database connection
            if self.database_manager:
                await self.database_manager.get_database_info()
                logger.info("Database connection test passed")

            # Test LLM connection with direct Anthropic SDK
            client = anthropic.Anthropic(api_key=self.config.anthropic_api_key)
            test_response = client.messages.create(
                model=self.config.claude_model,
                messages=[{"role": "user", "content": "Test"}],
                max_tokens=10,
            )

            if test_response:
                logger.info("LLM connection test passed")

        except Exception as e:
            logger.error("Connection test failed", error=str(e))
            raise ConnectionError(f"Service connection test failed: {e}")

    async def _call_llm_with_cache(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        cache_mode: str = "read",
    ) -> Any:
        """
        Call LLM with cache control and tool support.

        Args:
            messages: Message history for LLM
            tools: Available tools for LLM
            cache_mode: Cache mode ('read' or 'write')

        Returns:
            LLM response object
        """
        try:
            # Configure cache control
            cache_control = {"mode": cache_mode, "prefix": self.config.cache_prefix}

            # Track cache behavior
            # Cache hits/misses can be tracked via tool execution metadata if needed

            # Make LLM call with direct Anthropic SDK
            client = anthropic.Anthropic(api_key=self.config.anthropic_api_key)

            # Anthropic API requires system prompt as separate parameter, not in messages
            response = client.messages.create(
                model=self.config.claude_model,
                system=self.config.system_prompt,
                messages=messages,
                max_tokens=4096,
                timeout=self.config.request_timeout,
                tools=tools if tools else None,
                tool_choice={"type": "any"} if tools else None,
            )

            return response

        except Exception as e:
            logger.error("LLM call failed", error=str(e), cache_mode=cache_mode)
            raise ConnectionError(f"LLM call failed: {e}")

    async def _execute_tool_calls(self, tool_calls: List[Any]) -> List[Dict[str, Any]]:
        """
        Execute tool calls and format results as messages.

        Args:
            tool_calls: List of tool calls from LLM

        Returns:
            List of tool result messages
        """
        tool_messages = []

        for call in tool_calls:
            try:
                # Record tool execution in metrics_collector

                # Extract tool information (Anthropic format)
                tool_name = call.name
                tool_args = call.input

                # tool_args should already be a dict in Anthropic format
                if isinstance(tool_args, str):
                    import json

                    tool_args = json.loads(tool_args)
                # Get tool definition
                tool_definition = self.tool_registry.get_tool(tool_name)

                # Execute tool with proper async handling
                if asyncio.iscoroutinefunction(tool_definition.function):
                    result = await tool_definition.function(**tool_args)
                else:
                    result = tool_definition.function(**tool_args)

                # Format as tool message (Anthropic format)
                tool_message = {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": call.id,
                            "content": (
                                str(result) if not isinstance(result, str) else result
                            ),
                        }
                    ],
                }

                logger.info(
                    "Tool executed successfully",
                    tool_name=tool_name,
                    execution_time=result.get("execution_time_ms", 0),
                )
                self.metrics_collector.record_tool_execution(
                    tool_name=tool_name,
                    success=True,
                    execution_time=result.get("execution_time_ms", 0),
                    metadata={"args": tool_args},
                )

            except Exception as e:
                logger.error("Tool execution failed", tool_name=tool_name, error=str(e))
                self.metrics_collector.record_tool_execution(
                    tool_name=tool_name,
                    success=False,
                    execution_time=0,
                    error_type=str(e),
                    metadata={"args": tool_args},
                )

                # Format error as tool message (Anthropic format)
                tool_message = {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": call.id,
                            "content": str(
                                {
                                    "error": "Tool execution failed",
                                    "details": str(e),
                                    "status": "failed",
                                }
                            ),
                        }
                    ],
                }

            tool_messages.append(tool_message)

        return tool_messages

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get system performance metrics.

        Returns:
            Dictionary containing performance metrics
        """
        # Use the unified metrics collector for system metrics
        sys_metrics = self.metrics_collector.get_system_metrics()

        # Get cache metrics including circuit breaker metrics
        cache_metrics = {}
        if not self._cache_degraded:
            try:
                if self.resilient_cache:
                    # Get comprehensive metrics from resilient cache
                    resilient_metrics = self.resilient_cache.get_metrics()

                    # Extract cache metrics
                    cache_data = resilient_metrics.get("cache", {})
                    circuit_data = resilient_metrics.get("circuit_breaker", {})

                    cache_metrics = {
                        "cache_hit_rate": cache_data.get("hit_rate", 0),
                        "cache_hits": cache_data.get("cache_hits", 0),
                        "cache_misses": cache_data.get("cache_misses", 0),
                        "cache_total_entries": cache_data.get("total_entries", 0),
                        "cache_total_size": cache_data.get("total_size", 0),
                        "cache_token_efficiency": cache_data.get("token_efficiency", 0),
                        # Circuit breaker metrics
                        "circuit_breaker_state": circuit_data.get("state", "unknown"),
                        "circuit_breaker_failures": circuit_data.get(
                            "failure_count", 0
                        ),
                        "circuit_breaker_successes": circuit_data.get(
                            "success_count", 0
                        ),
                        "circuit_breaker_failure_rate": circuit_data.get(
                            "failure_rate", 0
                        ),
                        "circuit_breaker_state_changes": circuit_data.get(
                            "state_changes", 0
                        ),
                    }
                elif self.cache_system:
                    # Fallback to basic cache metrics
                    basic_cache_metrics = self.cache_system.cache_manager.get_metrics()
                    cache_metrics = {
                        "cache_hit_rate": basic_cache_metrics.hit_rate,
                        "cache_hits": basic_cache_metrics.cache_hits,
                        "cache_misses": basic_cache_metrics.cache_misses,
                        "cache_total_entries": basic_cache_metrics.total_entries,
                        "cache_total_size": basic_cache_metrics.total_size,
                        "cache_token_efficiency": basic_cache_metrics.token_efficiency,
                        "circuit_breaker_state": "disabled",
                    }
            except Exception as e:
                logger.warning("Failed to get cache metrics", error=str(e))
                cache_metrics = {
                    "cache_hit_rate": 0,
                    "cache_hits": 0,
                    "cache_misses": 0,
                    "circuit_breaker_state": "error",
                }
        else:
            cache_metrics = {
                "cache_hit_rate": 0,
                "cache_hits": 0,
                "cache_misses": 0,
                "cache_degraded": True,
                "circuit_breaker_state": "degraded",
            }

        return {
            "total_queries": sys_metrics.total_executions,
            "tool_executions": sys_metrics.total_executions,
            "error_rate": sys_metrics.error_rate,
            "initialized": self._initialized,
            **cache_metrics,
        }

    async def shutdown(self) -> None:
        """Gracefully shutdown the FACT system."""
        logger.info("Shutting down FACT system")

        # Shutdown resilient cache monitoring
        if self.resilient_cache:
            try:
                await self.resilient_cache.stop_monitoring()
                self.resilient_cache = None
            except Exception as e:
                logger.warning("Error stopping cache monitoring", error=str(e))

        # Shutdown cache circuit breaker
        if self.cache_circuit_breaker:
            try:
                await self.cache_circuit_breaker.stop_health_monitoring()
                self.cache_circuit_breaker = None
            except Exception as e:
                logger.warning("Error stopping circuit breaker", error=str(e))

        # Shutdown cache system
        if self.cache_system:
            await self.cache_system.shutdown()
            self.cache_system = None

        # Close database connections
        if self.database_manager:
            # Database manager handles its own cleanup
            pass

        self._initialized = False
        self._cache_degraded = False
        logger.info("FACT system shutdown complete")


# Global driver instance
_driver_instance: Optional[FACTDriver] = None


async def get_driver(config: Optional[Config] = None) -> FACTDriver:
    """
    Get or create the global FACT driver instance.

    Args:
        config: Optional configuration (only used for first creation)

    Returns:
        Initialized FACTDriver instance
    """
    global _driver_instance

    if _driver_instance is None:
        _driver_instance = FACTDriver(config)
        await _driver_instance.initialize()

    return _driver_instance


async def shutdown_driver() -> None:
    """Shutdown the global driver instance."""
    global _driver_instance

    if _driver_instance:
        await _driver_instance.shutdown()
        _driver_instance = None


async def process_user_query(query: str) -> str:
    """
    Process user query using the global driver instance.

    This is a compatibility wrapper for the benchmarking framework.

    Args:
        query: User query string

    Returns:
        Response string
    """
    driver = await get_driver()
    return await driver.process_query(query)
