"""
FACT System Cache Strategy Implementation

Implements various caching strategies for optimizing cache hit rates
and token efficiency in the FACT system.
"""

import time
import asyncio
from typing import Dict, List, Any, Optional, Tuple, Protocol
from dataclasses import dataclass
from enum import Enum
import structlog

try:
    # Try relative imports first (when used as package)
    from .manager import CacheManager, CacheEntry, CacheMetrics
    from ..core.errors import CacheError
except ImportError:
    # Fall back to absolute imports (when run as script)
    import sys
    from pathlib import Path

    # Add src to path if not already there
    src_path = str(Path(__file__).parent.parent)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    from cache.manager import CacheManager, CacheEntry, CacheMetrics
    from core.errors import CacheError


logger = structlog.get_logger(__name__)


class CacheStrategy(Enum):
    """Available cache strategies."""

    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    TTL_BASED = "ttl_based"  # Time-to-Live based
    ADAPTIVE = "adaptive"  # Adaptive based on metrics
    TOKEN_OPTIMIZED = "token_optimized"  # Optimized for token efficiency


@dataclass
class StrategyMetrics:
    """Metrics for evaluating strategy performance."""

    strategy_name: str
    hit_rate: float
    miss_rate: float
    token_efficiency: float
    avg_latency_ms: float
    eviction_count: int
    memory_usage_bytes: int
    timestamp: float


class CacheStrategyInterface(Protocol):
    """Interface for cache strategy implementations."""

    def should_evict(self, cache_manager: CacheManager) -> List[str]:
        """Determine which entries should be evicted."""
        ...

    def should_cache(self, content: str, context: Dict[str, Any]) -> bool:
        """Determine if content should be cached."""
        ...

    def get_priority_score(self, entry: CacheEntry, context: Dict[str, Any]) -> float:
        """Calculate priority score for cache entry."""
        ...


class LRUStrategy:
    """Least Recently Used cache strategy."""

    def __init__(self, max_entries: int = 1000):
        self.max_entries = max_entries
        self.name = "LRU"

    def should_evict(self, cache_manager: CacheManager) -> List[str]:
        """Evict least recently used entries when over limit."""
        if len(cache_manager.cache) <= self.max_entries:
            return []

        # Sort by last accessed time (oldest first)
        sorted_entries = sorted(
            cache_manager.cache.items(), key=lambda x: x[1].last_accessed or 0
        )

        # Evict oldest entries
        to_evict = len(cache_manager.cache) - self.max_entries
        return [key for key, _ in sorted_entries[:to_evict]]

    def should_cache(self, content: str, context: Dict[str, Any]) -> bool:
        """Cache everything that meets minimum requirements."""
        token_count = CacheEntry._count_tokens(content)
        min_tokens = context.get(
            "min_tokens", 50
        )  # Use context minimum or 50 as fallback
        return token_count >= min_tokens

    def get_priority_score(self, entry: CacheEntry, context: Dict[str, Any]) -> float:
        """Higher score for more recently accessed entries."""
        if entry.last_accessed is None:
            return 0.0

        age_seconds = time.time() - entry.last_accessed
        return 1.0 / (age_seconds + 1)  # Higher score for recent access


class LFUStrategy:
    """Least Frequently Used cache strategy."""

    def __init__(self, max_entries: int = 1000):
        self.max_entries = max_entries
        self.name = "LFU"

    def should_evict(self, cache_manager: CacheManager) -> List[str]:
        """Evict least frequently used entries when over limit."""
        if len(cache_manager.cache) <= self.max_entries:
            return []

        # Sort by access count (lowest first)
        sorted_entries = sorted(
            cache_manager.cache.items(), key=lambda x: x[1].access_count
        )

        # Evict least accessed entries
        to_evict = len(cache_manager.cache) - self.max_entries
        return [key for key, _ in sorted_entries[:to_evict]]

    def should_cache(self, content: str, context: Dict[str, Any]) -> bool:
        """Cache content with high reuse potential."""
        token_count = CacheEntry._count_tokens(content)
        min_tokens = context.get(
            "min_tokens", 50
        )  # Use context minimum or 50 as fallback
        if token_count < min_tokens:
            return False

        # Check if this is a common query pattern
        query = context.get("query", "")
        common_patterns = ["revenue", "Q1", "Q2", "Q3", "Q4", "total", "summary"]

        return any(pattern.lower() in query.lower() for pattern in common_patterns)

    def get_priority_score(self, entry: CacheEntry, context: Dict[str, Any]) -> float:
        """Higher score for more frequently accessed entries."""
        return entry.access_count


class TokenOptimizedStrategy:
    """Strategy optimized for token efficiency and cost reduction."""

    def __init__(self, target_efficiency: float = 10.0):
        self.target_efficiency = target_efficiency  # tokens per KB
        self.name = "TokenOptimized"

    def should_evict(self, cache_manager: CacheManager) -> List[str]:
        """Evict entries with poor token efficiency."""
        # Calculate efficiency for each entry
        efficiency_scores = []

        for key, entry in cache_manager.cache.items():
            content_size = len(entry.content.encode("utf-8"))
            efficiency = entry.token_count / (content_size / 1024)  # tokens per KB

            # Combine efficiency with access patterns
            access_factor = min(entry.access_count / 10.0, 1.0)  # Cap at 1.0
            score = efficiency * (0.7 + 0.3 * access_factor)

            efficiency_scores.append((key, score))

        # Sort by efficiency (lowest first for eviction)
        efficiency_scores.sort(key=lambda x: x[1])

        # Evict bottom 20% if over memory pressure
        current_size = cache_manager._calculate_current_size()
        if current_size > cache_manager.max_size_bytes * 0.8:
            evict_count = max(1, len(efficiency_scores) // 5)
            return [key for key, _ in efficiency_scores[:evict_count]]

        return []

    def should_cache(self, content: str, context: Dict[str, Any]) -> bool:
        """Cache content with high token efficiency."""
        token_count = CacheEntry._count_tokens(content)
        min_tokens = context.get("min_tokens", 50)

        if token_count < min_tokens:
            return False

        # Calculate token efficiency
        content_size_kb = len(content.encode("utf-8")) / 1024
        efficiency = token_count / content_size_kb if content_size_kb > 0 else 0

        return efficiency >= self.target_efficiency

    def get_priority_score(self, entry: CacheEntry, context: Dict[str, Any]) -> float:
        """Score based on token efficiency and access patterns."""
        content_size_kb = len(entry.content.encode("utf-8")) / 1024
        efficiency = entry.token_count / content_size_kb

        # Combine efficiency with usage
        usage_factor = min(entry.access_count / 5.0, 2.0)
        return efficiency * usage_factor


class AdaptiveStrategy:
    """Adaptive strategy that switches based on performance metrics."""

    def __init__(self):
        self.name = "Adaptive"
        self.strategies = [LRUStrategy(), LFUStrategy(), TokenOptimizedStrategy()]
        self.current_strategy = self.strategies[0]
        self.strategy_metrics: Dict[str, List[StrategyMetrics]] = {}
        self.evaluation_interval = 300  # 5 minutes
        self.last_evaluation = time.time()

    def _evaluate_strategies(self, cache_manager: CacheManager) -> None:
        """Evaluate all strategies and select the best performing one."""
        current_time = time.time()

        if current_time - self.last_evaluation < self.evaluation_interval:
            return

        self.last_evaluation = current_time

        # Get current metrics
        metrics = cache_manager.get_metrics()

        # Record metrics for current strategy
        strategy_metric = StrategyMetrics(
            strategy_name=self.current_strategy.name,
            hit_rate=metrics.hit_rate,
            miss_rate=metrics.miss_rate,
            token_efficiency=metrics.token_efficiency,
            avg_latency_ms=50.0,  # Would be measured from actual performance
            eviction_count=0,  # Would track evictions
            memory_usage_bytes=metrics.total_size,
            timestamp=current_time,
        )

        if self.current_strategy.name not in self.strategy_metrics:
            self.strategy_metrics[self.current_strategy.name] = []

        self.strategy_metrics[self.current_strategy.name].append(strategy_metric)

        # Select best strategy based on performance
        best_strategy = self._select_best_strategy()
        if best_strategy != self.current_strategy:
            logger.info(
                "Switching cache strategy",
                old_strategy=self.current_strategy.name,
                new_strategy=best_strategy.name,
            )
            self.current_strategy = best_strategy

    def _select_best_strategy(self) -> Any:
        """Select the best performing strategy based on metrics."""
        if not self.strategy_metrics:
            return self.current_strategy

        # Calculate weighted scores for each strategy
        strategy_scores = {}

        for strategy_name, metrics_list in self.strategy_metrics.items():
            if not metrics_list:
                continue

            # Use recent metrics (last 3 evaluations)
            recent_metrics = metrics_list[-3:]

            # Calculate weighted score
            avg_hit_rate = sum(m.hit_rate for m in recent_metrics) / len(recent_metrics)
            avg_efficiency = sum(m.token_efficiency for m in recent_metrics) / len(
                recent_metrics
            )
            avg_memory = sum(m.memory_usage_bytes for m in recent_metrics) / len(
                recent_metrics
            )

            # Weighted score: 50% hit rate, 30% efficiency, 20% memory usage
            score = (
                avg_hit_rate * 0.5
                + avg_efficiency * 0.3
                + (1.0 - min(avg_memory / (10 * 1024 * 1024), 1.0)) * 0.2
            )

            strategy_scores[strategy_name] = score

        # Find strategy with highest score
        if strategy_scores:
            best_name = max(strategy_scores.keys(), key=lambda k: strategy_scores[k])
            for strategy in self.strategies:
                if strategy.name == best_name:
                    return strategy

        return self.current_strategy

    def should_evict(self, cache_manager: CacheManager) -> List[str]:
        """Delegate to current strategy after evaluation."""
        self._evaluate_strategies(cache_manager)
        return self.current_strategy.should_evict(cache_manager)

    def should_cache(self, content: str, context: Dict[str, Any]) -> bool:
        """Delegate to current strategy."""
        return self.current_strategy.should_cache(content, context)

    def get_priority_score(self, entry: CacheEntry, context: Dict[str, Any]) -> float:
        """Delegate to current strategy."""
        return self.current_strategy.get_priority_score(entry, context)


class CacheOptimizer:
    """Main cache optimization controller."""

    def __init__(self, strategy: CacheStrategy = CacheStrategy.ADAPTIVE):
        self.strategy_impl = self._create_strategy(strategy)

    def _create_strategy(self, strategy: CacheStrategy) -> Any:
        """Create strategy implementation instance."""
        strategy_map = {
            CacheStrategy.LRU: LRUStrategy,
            CacheStrategy.LFU: LFUStrategy,
            CacheStrategy.TOKEN_OPTIMIZED: TokenOptimizedStrategy,
            CacheStrategy.ADAPTIVE: AdaptiveStrategy,
            CacheStrategy.TTL_BASED: LRUStrategy,  # Use LRU for TTL-based for now
        }

        strategy_class = strategy_map.get(strategy, AdaptiveStrategy)
        return strategy_class()

    async def optimize_cache(self, cache_manager: CacheManager) -> Dict[str, Any]:
        """
        Optimize cache based on current strategy.

        Args:
            cache_manager: Cache manager to optimize

        Returns:
            Optimization results
        """
        start_time = time.perf_counter()

        try:
            # Get entries to evict
            to_evict = self.strategy_impl.should_evict(cache_manager)

            # Perform eviction
            evicted_count = 0
            with cache_manager._lock:
                for key in to_evict:
                    if key in cache_manager.cache:
                        del cache_manager.cache[key]
                        evicted_count += 1

            # Clean up expired entries
            expired_count = cache_manager._cleanup_expired()

            # Calculate optimization results
            optimization_time = (time.perf_counter() - start_time) * 1000

            results = {
                "strategy": self.strategy_impl.name,
                "evicted_entries": evicted_count,
                "expired_entries": expired_count,
                "total_optimized": evicted_count + expired_count,
                "optimization_time_ms": optimization_time,
                "cache_size_after": len(cache_manager.cache),
            }

            logger.info("Cache optimization completed", **results)
            return results

        except Exception as e:
            logger.error("Cache optimization failed", error=str(e))
            raise CacheError(f"Cache optimization failed: {e}")

    def should_cache_content(self, content: str, context: Dict[str, Any]) -> bool:
        """
        Determine if content should be cached based on strategy.

        Args:
            content: Content to evaluate
            context: Additional context for decision

        Returns:
            True if content should be cached
        """
        try:
            result = self.strategy_impl.should_cache(content, context)
            return result
        except Exception as e:
            logger.warning("Cache strategy evaluation failed", error=str(e))
            # Default: cache if meets minimum requirements
            min_tokens = context.get("min_tokens", 50)
            return CacheEntry._count_tokens(content) >= min_tokens

    def get_cache_priority(self, entry: CacheEntry, context: Dict[str, Any]) -> float:
        """
        Get priority score for cache entry.

        Args:
            entry: Cache entry to score
            context: Additional context

        Returns:
            Priority score (higher = more important)
        """
        try:
            return self.strategy_impl.get_priority_score(entry, context)
        except Exception as e:
            logger.warning("Priority score calculation failed", error=str(e))
            return 1.0  # Default medium priority


# Global optimizer instance
_cache_optimizer: Optional[CacheOptimizer] = None


def get_cache_optimizer(
    strategy: CacheStrategy = CacheStrategy.ADAPTIVE,
) -> CacheOptimizer:
    """
    Get or create the global cache optimizer.

    Args:
        strategy: Cache strategy to use

    Returns:
        Cache optimizer instance
    """
    global _cache_optimizer

    if _cache_optimizer is None:
        _cache_optimizer = CacheOptimizer(strategy)

    return _cache_optimizer


async def optimize_cache_automatically(
    cache_manager: CacheManager, interval_seconds: int = 300
) -> None:
    """
    Run automatic cache optimization in background.

    Args:
        cache_manager: Cache manager to optimize
        interval_seconds: Optimization interval in seconds
    """
    optimizer = get_cache_optimizer()

    logger.info(
        "Starting automatic cache optimization", interval_seconds=interval_seconds
    )

    while True:
        try:
            await asyncio.sleep(interval_seconds)
            await optimizer.optimize_cache(cache_manager)

        except asyncio.CancelledError:
            logger.info("Cache optimization task cancelled")
            break
        except Exception as e:
            logger.error("Automatic cache optimization failed", error=str(e))
            # Continue running despite errors
