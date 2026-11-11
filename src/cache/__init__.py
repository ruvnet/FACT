"""
FACT System Cache Module

Provides comprehensive caching functionality for the FACT system including:
- Token-based cache management for Claude Sonnet-4
- Intelligent caching strategies and optimization
- Performance metrics and monitoring
- Cache warming and validation
- Sub-50ms cache hit performance

This module implements the caching requirements specified in the FACT architecture.
"""

from .manager import (
    CacheManager,
    CacheEntry,
    CacheMetrics,
    get_cache_manager,
    get_cached_response,
    warm_cache,
    invalidate_on_schema_change,
)

from .strategy import (
    CacheStrategy,
    CacheOptimizer,
    get_cache_optimizer,
    optimize_cache_automatically,
)

from .metrics import (
    MetricsCollector,
    PerformanceMetric,
    CostAnalysis,
    LatencyAnalysis,
    CacheHealthMetrics,
    get_metrics_collector,
    start_metrics_monitoring,
)

from .warming import (
    CacheWarmer,
    WarmupQuery,
    WarmupResult,
    QueryPatternAnalyzer,
    get_cache_warmer,
    warm_cache_startup,
)

from .validation import (
    CacheValidator,
    ValidationLevel,
    ValidationResult,
    IntegrityIssue,
    get_cache_validator,
    validate_cache_integrity,
)

try:
    # Try relative imports first (when used as package)
    from ..core.errors import CacheError
except ImportError:
    # Fall back to absolute imports (when run as script)
    import sys
    from pathlib import Path

    # Add src to path if not already there
    src_path = str(Path(__file__).parent.parent)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    from core.errors import CacheError

import asyncio
import time
from typing import Dict, List, Any, Optional
import structlog

logger = structlog.get_logger(__name__)


class FACTCacheSystem:
    """
    Main FACT cache system coordinator.

    Integrates all cache components and provides a unified interface
    for cache operations, monitoring, and maintenance.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the FACT cache system.

        Args:
            config: Cache configuration dictionary
        """
        self.config = config
        self.cache_manager = CacheManager(config)
        self.cache_optimizer = get_cache_optimizer()
        self.metrics_collector = get_metrics_collector()
        self.cache_warmer = get_cache_warmer(self.cache_manager)
        self.cache_validator = get_cache_validator(self.cache_manager)

        self._background_tasks: List[asyncio.Task] = []
        self._initialized = False

        logger.info("FACT cache system initialized", prefix=config["prefix"])

    async def initialize(self, enable_background_tasks: bool = True) -> None:
        """
        Initialize the cache system and start background tasks.

        Args:
            enable_background_tasks: Whether to start monitoring and optimization tasks
        """
        if self._initialized:
            logger.info("Cache system already initialized")
            return

        try:
            # Perform initial cache warming
            logger.info("Performing initial cache warming")
            warmup_result = await self.cache_warmer.warm_cache_intelligently(
                max_queries=10
            )

            logger.info(
                "Initial cache warming completed",
                successful=warmup_result.queries_successful,
                failed=warmup_result.queries_failed,
            )

            # Start background tasks if enabled
            if enable_background_tasks:
                await self._start_background_tasks()

            self._initialized = True
            logger.info("FACT cache system fully initialized")

        except Exception as e:
            logger.error("Cache system initialization failed", error=str(e))
            raise CacheError(f"Cache system initialization failed: {e}")

    async def get_cached_response(self, query: str) -> Optional[str]:
        """
        Get cached response for query with performance tracking.

        Args:
            query: User query

        Returns:
            Cached response if available, None otherwise
        """
        start_time = time.perf_counter()

        try:
            query_hash = self.cache_manager.generate_hash(query)
            entry = self.cache_manager.get(query_hash)

            latency_ms = (time.perf_counter() - start_time) * 1000

            # Record metrics
            self.metrics_collector.record_cache_operation(
                operation="get",
                latency_ms=latency_ms,
                success=True,
                cache_hit=entry is not None,
                token_count=entry.token_count if entry else None,
                entry_size_bytes=len(entry.content.encode("utf-8")) if entry else None,
            )

            if entry:
                logger.debug(
                    "Cache hit",
                    query_hash=query_hash[:16],
                    latency_ms=latency_ms,
                    tokens=entry.token_count,
                )
                return entry.content
            else:
                logger.debug(
                    "Cache miss", query_hash=query_hash[:16], latency_ms=latency_ms
                )
                return None

        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000

            # Record error
            self.metrics_collector.record_cache_operation(
                operation="get", latency_ms=latency_ms, success=False
            )

            logger.error("Cache retrieval failed", query=query[:50], error=str(e))
            return None

    async def store_response(self, query: str, response: str) -> bool:
        """
        Store response in cache with validation and optimization.

        Args:
            query: User query
            response: Response to cache

        Returns:
            True if stored successfully, False otherwise
        """
        start_time = time.perf_counter()

        try:
            # Check if content should be cached
            context = {"query": query, "min_tokens": self.config.get("min_tokens", 50)}
            should_cache = self.cache_optimizer.should_cache_content(response, context)

            if not should_cache:
                logger.debug("Content not suitable for caching", query=query[:50])
                return False

            # Store in cache
            query_hash = self.cache_manager.generate_hash(query)
            entry = self.cache_manager.store(query_hash, response)

            latency_ms = (time.perf_counter() - start_time) * 1000

            # Record metrics
            self.metrics_collector.record_cache_operation(
                operation="store",
                latency_ms=latency_ms,
                success=True,
                token_count=entry.token_count,
                entry_size_bytes=len(entry.content.encode("utf-8")),
            )

            logger.debug(
                "Response cached",
                query_hash=query_hash[:16],
                latency_ms=latency_ms,
                tokens=entry.token_count,
            )

            return True

        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000

            # Record error
            self.metrics_collector.record_cache_operation(
                operation="store", latency_ms=latency_ms, success=False
            )

            logger.error("Cache storage failed", query=query[:50], error=str(e))
            return False

    async def invalidate_cache(self, reason: str = "Manual invalidation") -> int:
        """
        Invalidate cache entries with tracking.

        Args:
            reason: Reason for invalidation

        Returns:
            Number of entries invalidated
        """
        try:
            invalidated = self.cache_manager.invalidate_by_prefix(
                self.cache_manager.prefix
            )

            logger.info(
                "Cache invalidated", reason=reason, entries_invalidated=invalidated
            )

            return invalidated

        except Exception as e:
            logger.error("Cache invalidation failed", reason=reason, error=str(e))
            return 0

    async def get_health_report(self) -> Dict[str, Any]:
        """
        Get comprehensive cache health report.

        Returns:
            Complete health and performance report
        """
        try:
            # Get metrics from all components
            basic_metrics = self.cache_manager.get_metrics()
            health_metrics = self.metrics_collector.get_cache_health_score(
                self.cache_manager
            )
            latency_analysis = self.metrics_collector.get_latency_analysis()
            cost_analysis = self.metrics_collector.get_cost_analysis(self.cache_manager)

            # Perform quick validation
            validation_result = await self.cache_validator.validate_cache(
                ValidationLevel.BASIC
            )

            return {
                "timestamp": time.time(),
                "overall_health": health_metrics.overall_health_score,
                "basic_metrics": (
                    basic_metrics.__dict__
                    if hasattr(basic_metrics, "__dict__")
                    else basic_metrics
                ),
                "health_metrics": health_metrics.__dict__,
                "latency_analysis": latency_analysis.__dict__,
                "cost_analysis": cost_analysis.__dict__,
                "validation_summary": {
                    "total_entries": validation_result.total_entries_checked,
                    "valid_entries": validation_result.valid_entries,
                    "issues_found": len(validation_result.issues_found),
                    "overall_health": validation_result.overall_health,
                },
                "performance_status": self._get_performance_status(latency_analysis),
                "recommendations": validation_result.recommendations,
            }

        except Exception as e:
            logger.error("Failed to generate health report", error=str(e))
            return {"timestamp": time.time(), "error": str(e), "overall_health": 0.0}

    async def optimize_cache(self) -> Dict[str, Any]:
        """
        Optimize cache performance and cleanup.

        Returns:
            Optimization results
        """
        try:
            # Run cache optimization
            optimization_result = await self.cache_optimizer.optimize_cache(
                self.cache_manager
            )

            # Validate cache after optimization
            validation_result = await self.cache_validator.validate_cache(
                ValidationLevel.STANDARD
            )

            return {
                "optimization": optimization_result,
                "validation": {
                    "total_entries": validation_result.total_entries_checked,
                    "valid_entries": validation_result.valid_entries,
                    "overall_health": validation_result.overall_health,
                },
            }

        except Exception as e:
            logger.error("Cache optimization failed", error=str(e))
            raise CacheError(f"Cache optimization failed: {e}")

    async def warm_cache(self, queries: Optional[List[str]] = None) -> WarmupResult:
        """
        Warm cache with specified or intelligent query selection.

        Args:
            queries: Optional list of queries to warm

        Returns:
            Warmup operation result
        """
        try:
            if queries:
                return await self.cache_warmer.warm_cache_from_queries(queries)
            else:
                return await self.cache_warmer.warm_cache_intelligently(max_queries=20)

        except Exception as e:
            logger.error("Cache warming failed", error=str(e))
            raise CacheError(f"Cache warming failed: {e}")

    async def shutdown(self) -> None:
        """Gracefully shutdown the cache system."""
        logger.info("Shutting down FACT cache system")

        # Cancel background tasks
        for task in self._background_tasks:
            task.cancel()

        # Wait for tasks to complete
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)

        self._background_tasks.clear()
        self._initialized = False

        logger.info("FACT cache system shutdown complete")

    async def _start_background_tasks(self) -> None:
        """Start background monitoring and optimization tasks."""
        try:
            # Start metrics monitoring
            metrics_task = asyncio.create_task(
                start_metrics_monitoring(self.cache_manager, report_interval=300)
            )
            self._background_tasks.append(metrics_task)

            # Start automatic optimization
            optimization_task = asyncio.create_task(
                optimize_cache_automatically(self.cache_manager, interval_seconds=900)
            )
            self._background_tasks.append(optimization_task)

            # Start scheduled warming
            warming_task = asyncio.create_task(
                self.cache_warmer.scheduled_warming(interval_hours=6)
            )
            self._background_tasks.append(warming_task)

            logger.info("Background cache tasks started")

        except Exception as e:
            logger.error("Failed to start background tasks", error=str(e))
            raise CacheError(f"Background tasks startup failed: {e}")

    def _get_performance_status(self, latency_analysis: LatencyAnalysis) -> str:
        """Determine performance status based on latency analysis."""
        if (
            latency_analysis.avg_hit_latency_ms <= 50
            and latency_analysis.hit_sla_compliance_percent >= 95
        ):
            return "excellent"
        elif (
            latency_analysis.avg_hit_latency_ms <= 75
            and latency_analysis.hit_sla_compliance_percent >= 90
        ):
            return "good"
        elif (
            latency_analysis.avg_hit_latency_ms <= 100
            and latency_analysis.hit_sla_compliance_percent >= 80
        ):
            return "acceptable"
        else:
            return "poor"


# Global cache system instance
_cache_system: Optional[FACTCacheSystem] = None


async def initialize_cache_system(
    config: Dict[str, Any], enable_background_tasks: bool = True
) -> FACTCacheSystem:
    """
    Initialize the global FACT cache system.

    Args:
        config: Cache configuration
        enable_background_tasks: Whether to start background tasks

    Returns:
        Initialized cache system
    """
    global _cache_system

    if _cache_system is None:
        _cache_system = FACTCacheSystem(config)
        await _cache_system.initialize(enable_background_tasks)

    return _cache_system


def get_cache_system() -> Optional[FACTCacheSystem]:
    """Get the global cache system instance."""
    return _cache_system


async def shutdown_cache_system() -> None:
    """Shutdown the global cache system."""
    global _cache_system

    if _cache_system:
        await _cache_system.shutdown()
        _cache_system = None


# Export main classes and functions
__all__ = [
    # Main system
    "FACTCacheSystem",
    "initialize_cache_system",
    "get_cache_system",
    "shutdown_cache_system",
    # Core components
    "CacheManager",
    "CacheEntry",
    "CacheMetrics",
    "CacheError",
    # Strategy and optimization
    "CacheStrategy",
    "CacheOptimizer",
    # Metrics and monitoring
    "MetricsCollector",
    "PerformanceMetric",
    "CostAnalysis",
    "LatencyAnalysis",
    "CacheHealthMetrics",
    # Warming
    "CacheWarmer",
    "WarmupQuery",
    "WarmupResult",
    "QueryPatternAnalyzer",
    # Validation
    "CacheValidator",
    "ValidationLevel",
    "ValidationResult",
    "IntegrityIssue",
    # Utility functions
    "get_cache_manager",
    "get_cached_response",
    "warm_cache",
    "invalidate_on_schema_change",
    "validate_cache_integrity",
]
