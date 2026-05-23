"""
FACT System Agentic Flow Implementation

This module implements the core FACT (Fast Access Caching Technology) algorithm
for intelligent query processing with cache-optimized LLM interactions.

The FACT algorithm combines:
- Fast cache-first query resolution
- Access pattern optimization
- Caching strategy adaptation
- Token-efficient LLM interactions
"""

import asyncio
import time
import hashlib
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import structlog

from .config import Config, get_config
from .driver import FACTDriver
from .errors import FACTError, CacheError, ToolExecutionError
from ..cache.manager import CacheManager, get_cache_manager, CacheEntry
from ..cache.strategy import CacheOptimizer, CacheStrategy, get_cache_optimizer
from ..monitoring.metrics import get_metrics_collector, ToolExecutionMetric
from ..tools.decorators import get_tool_registry

logger = structlog.get_logger(__name__)


@dataclass
class FACTQueryContext:
    """Context for FACT query processing."""

    query_id: str
    user_query: str
    query_hash: str
    timestamp: float
    cache_mode: str = "read"
    priority: float = 1.0
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class FACTResponse:
    """FACT algorithm response with performance metrics."""

    content: str
    cache_hit: bool
    execution_time_ms: float
    token_count: int
    tool_calls_count: int
    cache_efficiency: float
    strategy_used: str
    query_context: FACTQueryContext
    performance_metrics: Dict[str, Any] = None

    def __post_init__(self):
        if self.performance_metrics is None:
            self.performance_metrics = {}


class FACTAlgorithm:
    """
    Core FACT Algorithm Implementation

    Implements the Fast Access Caching Technology algorithm that optimizes
    LLM interactions through intelligent caching, access pattern analysis,
    and adaptive strategy selection.

    Key Components:
    1. Cache-First Query Resolution
    2. Token-Efficient Content Processing
    3. Adaptive Caching Strategies
    4. Performance Monitoring and Optimization
    """

    def __init__(self, config: Optional[Config] = None):
        """
        Initialize FACT algorithm with configuration.

        Args:
            config: Optional configuration instance
        """
        self.config = config or get_config()
        self.cache_manager: Optional[CacheManager] = None
        self.cache_optimizer: Optional[CacheOptimizer] = None
        self.metrics_collector = get_metrics_collector()
        self.tool_registry = get_tool_registry()
        self._initialized = False

        # FACT algorithm parameters
        self.cache_hit_target_ms = 50  # Target latency for cache hits
        self.cache_miss_target_ms = 140  # Target latency for cache misses
        self.min_cache_tokens = 500  # Minimum tokens for caching
        self.token_efficiency_target = 100.0  # Tokens per KB target

        logger.info("FACT algorithm initialized")

    async def initialize(self) -> None:
        """Initialize FACT algorithm components."""
        if self._initialized:
            return

        try:
            # Initialize cache manager with FACT-specific configuration
            cache_config = {
                "prefix": self.config.cache_prefix,
                "min_tokens": self.min_cache_tokens,
                "max_size": "10MB",
                "ttl_seconds": 3600,  # 1 hour TTL
                "hit_target_ms": self.cache_hit_target_ms,
                "miss_target_ms": self.cache_miss_target_ms,
            }

            self.cache_manager = get_cache_manager(cache_config)

            # Initialize cache optimizer with adaptive strategy
            self.cache_optimizer = get_cache_optimizer(CacheStrategy.ADAPTIVE)

            # Start background optimization
            asyncio.create_task(self._run_background_optimization())

            self._initialized = True
            logger.info("FACT algorithm initialization completed")

        except Exception as e:
            logger.error("FACT algorithm initialization failed", error=str(e))
            raise FACTError(f"FACT initialization failed: {e}")

    async def process_query(
        self, user_query: str, context: Optional[Dict[str, Any]] = None
    ) -> FACTResponse:
        """
        Process query using FACT algorithm.

        This is the main entry point for the FACT algorithm, implementing:
        1. Query normalization and hashing
        2. Cache-first lookup with performance tracking
        3. LLM fallback with tool integration
        4. Response caching with strategy optimization
        5. Performance metrics collection

        Args:
            user_query: User's natural language query
            context: Optional context for query processing

        Returns:
            FACTResponse with content and performance metrics
        """
        if not self._initialized:
            await self.initialize()

        start_time = time.perf_counter()

        # Create query context
        query_context = self._create_query_context(user_query, context)

        try:
            logger.info(
                "FACT query processing started",
                query_id=query_context.query_id,
                query_hash=query_context.query_hash[:16],
            )

            # Phase 1: Cache-first lookup
            cached_response = await self._cache_lookup_phase(query_context)
            if cached_response:
                return cached_response

            # Phase 2: LLM processing with tool integration
            llm_response = await self._llm_processing_phase(query_context)

            # Phase 3: Cache storage and optimization
            await self._cache_storage_phase(query_context, llm_response)

            # Record performance metrics
            execution_time = (time.perf_counter() - start_time) * 1000
            self._record_query_metrics(query_context, llm_response, execution_time)

            return llm_response

        except Exception as e:
            execution_time = (time.perf_counter() - start_time) * 1000
            logger.error(
                "FACT query processing failed",
                query_id=query_context.query_id,
                error=str(e),
                execution_time_ms=execution_time,
            )

            # Record failure metrics
            self.metrics_collector.record_tool_execution(
                tool_name="fact_algorithm",
                success=False,
                execution_time=execution_time,
                error_type=type(e).__name__,
                metadata={"query_id": query_context.query_id},
            )

            raise FACTError(f"FACT query processing failed: {e}")

    def _create_query_context(
        self, user_query: str, context: Optional[Dict[str, Any]]
    ) -> FACTQueryContext:
        """Create query context with normalization and hashing."""
        # Normalize query for consistent hashing
        normalized_query = user_query.strip().lower()

        # Generate deterministic hash
        query_hash = self.cache_manager.generate_hash(normalized_query)

        # Create unique query ID
        query_id = f"fact_{int(time.time() * 1000)}_{query_hash[:8]}"

        return FACTQueryContext(
            query_id=query_id,
            user_query=user_query,
            query_hash=query_hash,
            timestamp=time.time(),
            metadata=context or {},
        )

    async def _cache_lookup_phase(
        self, query_context: FACTQueryContext
    ) -> Optional[FACTResponse]:
        """
        Phase 1: Cache-first lookup with performance tracking.

        Implements fast cache lookup with:
        - Performance monitoring
        - Cache hit optimization
        - Access pattern tracking
        """
        cache_start = time.perf_counter()

        try:
            # Attempt cache lookup
            cached_entry = self.cache_manager.get(query_context.query_hash)

            cache_latency = (time.perf_counter() - cache_start) * 1000

            if cached_entry:
                logger.info(
                    "FACT cache hit",
                    query_id=query_context.query_id,
                    cache_latency_ms=cache_latency,
                    access_count=cached_entry.access_count,
                )

                # Create cache hit response
                response = FACTResponse(
                    content=cached_entry.content,
                    cache_hit=True,
                    execution_time_ms=cache_latency,
                    token_count=cached_entry.token_count,
                    tool_calls_count=0,
                    cache_efficiency=self._calculate_cache_efficiency(cached_entry),
                    strategy_used="cache_hit",
                    query_context=query_context,
                    performance_metrics={
                        "cache_latency_ms": cache_latency,
                        "access_count": cached_entry.access_count,
                        "cache_age_seconds": time.time() - cached_entry.created_at,
                    },
                )

                # Record cache hit metrics
                self.metrics_collector.record_tool_execution(
                    tool_name="fact_cache_hit",
                    success=True,
                    execution_time=cache_latency,
                    metadata={
                        "query_id": query_context.query_id,
                        "token_count": cached_entry.token_count,
                        "access_count": cached_entry.access_count,
                    },
                )

                return response
            else:
                logger.info(
                    "FACT cache miss",
                    query_id=query_context.query_id,
                    cache_latency_ms=cache_latency,
                )

                # Record cache miss metrics
                self.metrics_collector.record_tool_execution(
                    tool_name="fact_cache_miss",
                    success=True,
                    execution_time=cache_latency,
                    metadata={"query_id": query_context.query_id},
                )

                return None

        except Exception as e:
            cache_latency = (time.perf_counter() - cache_start) * 1000
            logger.warning(
                "Cache lookup failed",
                query_id=query_context.query_id,
                error=str(e),
                cache_latency_ms=cache_latency,
            )
            return None

    async def _llm_processing_phase(
        self, query_context: FACTQueryContext
    ) -> FACTResponse:
        """
        Phase 2: LLM processing with tool integration.

        Implements intelligent LLM interaction with:
        - Tool execution optimization
        - Token efficiency monitoring
        - Response quality assessment
        """
        llm_start = time.perf_counter()

        try:
            # Get FACT driver for LLM processing
            from .driver import get_driver

            driver = await get_driver(self.config)

            # Process query through driver
            response_content = await driver.process_query(query_context.user_query)

            llm_latency = (time.perf_counter() - llm_start) * 1000

            # Calculate token count and efficiency
            token_count = CacheEntry._count_tokens(response_content)
            cache_efficiency = self._calculate_content_efficiency(response_content)

            # Create LLM response
            response = FACTResponse(
                content=response_content,
                cache_hit=False,
                execution_time_ms=llm_latency,
                token_count=token_count,
                tool_calls_count=self._count_tool_calls(response_content),
                cache_efficiency=cache_efficiency,
                strategy_used="llm_processing",
                query_context=query_context,
                performance_metrics={
                    "llm_latency_ms": llm_latency,
                    "token_count": token_count,
                    "cache_efficiency": cache_efficiency,
                },
            )

            logger.info(
                "FACT LLM processing completed",
                query_id=query_context.query_id,
                llm_latency_ms=llm_latency,
                token_count=token_count,
                cache_efficiency=cache_efficiency,
            )

            return response

        except Exception as e:
            llm_latency = (time.perf_counter() - llm_start) * 1000
            logger.error(
                "LLM processing failed",
                query_id=query_context.query_id,
                error=str(e),
                llm_latency_ms=llm_latency,
            )
            raise ToolExecutionError(f"LLM processing failed: {e}")

    async def _cache_storage_phase(
        self, query_context: FACTQueryContext, response: FACTResponse
    ) -> None:
        """
        Phase 3: Cache storage with strategy optimization.

        Implements intelligent caching with:
        - Content quality assessment
        - Storage strategy optimization
        - Cache efficiency monitoring
        """
        if not response.content or response.token_count < self.min_cache_tokens:
            logger.debug(
                "Content not cached - insufficient tokens",
                query_id=query_context.query_id,
                token_count=response.token_count,
            )
            return

        storage_start = time.perf_counter()

        try:
            # Check if content should be cached based on strategy
            should_cache = self.cache_optimizer.should_cache_content(
                response.content,
                {
                    "query": query_context.user_query,
                    "token_count": response.token_count,
                    "execution_time": response.execution_time_ms,
                },
            )

            if should_cache:
                # Store in cache
                cache_entry = self.cache_manager.store(
                    query_context.query_hash, response.content
                )

                storage_latency = (time.perf_counter() - storage_start) * 1000

                logger.info(
                    "Content cached successfully",
                    query_id=query_context.query_id,
                    token_count=cache_entry.token_count,
                    storage_latency_ms=storage_latency,
                )

                # Record cache storage metrics
                self.metrics_collector.record_tool_execution(
                    tool_name="fact_cache_store",
                    success=True,
                    execution_time=storage_latency,
                    metadata={
                        "query_id": query_context.query_id,
                        "token_count": cache_entry.token_count,
                    },
                )
            else:
                logger.debug(
                    "Content not cached - strategy decision",
                    query_id=query_context.query_id,
                )

        except CacheError as e:
            storage_latency = (time.perf_counter() - storage_start) * 1000
            logger.warning(
                "Cache storage failed",
                query_id=query_context.query_id,
                error=str(e),
                storage_latency_ms=storage_latency,
            )

    def _calculate_cache_efficiency(self, cache_entry: CacheEntry) -> float:
        """Calculate cache efficiency score for an entry."""
        content_size_kb = len(cache_entry.content.encode("utf-8")) / 1024
        return cache_entry.token_count / content_size_kb if content_size_kb > 0 else 0.0

    def _calculate_content_efficiency(self, content: str) -> float:
        """Calculate content efficiency for new content."""
        if not content:
            return 0.0

        token_count = CacheEntry._count_tokens(content)
        content_size_kb = len(content.encode("utf-8")) / 1024
        return token_count / content_size_kb if content_size_kb > 0 else 0.0

    def _count_tool_calls(self, content: str) -> int:
        """Estimate number of tool calls from response content."""
        # Simple heuristic - count mentions of tool execution patterns
        tool_indicators = ["executed", "query", "result", "data"]
        return sum(
            1 for indicator in tool_indicators if indicator.lower() in content.lower()
        )

    def _record_query_metrics(
        self,
        query_context: FACTQueryContext,
        response: FACTResponse,
        execution_time: float,
    ) -> None:
        """Record comprehensive query processing metrics."""
        self.metrics_collector.record_tool_execution(
            tool_name="fact_query_complete",
            success=True,
            execution_time=execution_time,
            metadata={
                "query_id": query_context.query_id,
                "cache_hit": response.cache_hit,
                "token_count": response.token_count,
                "cache_efficiency": response.cache_efficiency,
                "strategy_used": response.strategy_used,
                "tool_calls_count": response.tool_calls_count,
            },
        )

    async def _run_background_optimization(self) -> None:
        """Run background cache optimization."""
        logger.info("Starting FACT background optimization")

        while True:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes

                if self.cache_manager and self.cache_optimizer:
                    optimization_results = await self.cache_optimizer.optimize_cache(
                        self.cache_manager
                    )

                    logger.debug(
                        "Background optimization completed", **optimization_results
                    )

            except asyncio.CancelledError:
                logger.info("Background optimization cancelled")
                break
            except Exception as e:
                logger.error("Background optimization failed", error=str(e))
                # Continue running despite errors

    def get_algorithm_metrics(self) -> Dict[str, Any]:
        """Get FACT algorithm performance metrics."""
        if not self.cache_manager:
            return {}

        # Get cache metrics
        cache_metrics = self.cache_manager.get_metrics()

        # Get system metrics
        system_metrics = self.metrics_collector.get_system_metrics()

        # Calculate FACT-specific metrics
        fact_metrics = {
            "algorithm": "FACT",
            "version": "1.0",
            "initialized": self._initialized,
            "cache_hit_rate": cache_metrics.hit_rate,
            "cache_efficiency": cache_metrics.token_efficiency,
            "avg_execution_time": system_metrics.average_execution_time,
            "total_queries": system_metrics.total_executions,
            "error_rate": system_metrics.error_rate,
            "cache_size_entries": cache_metrics.total_entries,
            "cache_size_bytes": cache_metrics.total_size,
            "performance_targets": {
                "cache_hit_target_ms": self.cache_hit_target_ms,
                "cache_miss_target_ms": self.cache_miss_target_ms,
                "min_cache_tokens": self.min_cache_tokens,
                "token_efficiency_target": self.token_efficiency_target,
            },
        }

        return fact_metrics


# Global FACT algorithm instance
_fact_algorithm: Optional[FACTAlgorithm] = None


async def get_fact_algorithm(config: Optional[Config] = None) -> FACTAlgorithm:
    """
    Get or create the global FACT algorithm instance.

    Args:
        config: Optional configuration

    Returns:
        Initialized FACT algorithm instance
    """
    global _fact_algorithm

    if _fact_algorithm is None:
        _fact_algorithm = FACTAlgorithm(config)
        await _fact_algorithm.initialize()

    return _fact_algorithm


async def process_fact_query(
    user_query: str, context: Optional[Dict[str, Any]] = None
) -> FACTResponse:
    """
    Process a query using the FACT algorithm.

    Args:
        user_query: User's natural language query
        context: Optional query context

    Returns:
        FACT response with performance metrics
    """
    algorithm = await get_fact_algorithm()
    return await algorithm.process_query(user_query, context)
