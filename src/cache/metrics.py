"""
FACT System Cache Metrics Collection

Implements comprehensive metrics collection, analysis, and reporting
for cache performance optimization and monitoring.
"""

import time
import asyncio
import json
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
from threading import Lock
import structlog

try:
    # Try relative imports first (when used as package)
    from .manager import CacheManager, CacheMetrics
    from ..core.errors import CacheError
except ImportError:
    # Fall back to absolute imports (when run as script)
    import sys
    from pathlib import Path

    # Add src to path if not already there
    src_path = str(Path(__file__).parent.parent)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    from cache.manager import CacheManager, CacheMetrics
    from core.errors import CacheError


logger = structlog.get_logger(__name__)


@dataclass
class PerformanceMetric:
    """Individual performance measurement."""

    operation: str
    latency_ms: float
    timestamp: float
    success: bool
    cache_hit: Optional[bool] = None
    token_count: Optional[int] = None
    entry_size_bytes: Optional[int] = None


@dataclass
class CostAnalysis:
    """Cost analysis for cache operations."""

    total_requests: int
    cache_hits: int
    cache_misses: int
    estimated_savings_usd: float
    token_cost_reduction_percent: float
    avg_tokens_per_hit: float
    avg_tokens_per_miss: float
    cost_per_token_usd: float = 0.000003  # Approximate Claude cost


@dataclass
class LatencyAnalysis:
    """Latency analysis for cache operations."""

    avg_hit_latency_ms: float
    avg_miss_latency_ms: float
    p50_hit_latency_ms: float
    p95_hit_latency_ms: float
    p99_hit_latency_ms: float
    target_hit_latency_ms: float = 50.0
    target_miss_latency_ms: float = 140.0
    hit_sla_compliance_percent: float = 0.0
    miss_sla_compliance_percent: float = 0.0


@dataclass
class CacheHealthMetrics:
    """Overall cache health and performance metrics."""

    timestamp: float
    hit_rate_percent: float
    miss_rate_percent: float
    efficiency_score: float  # 0-100
    memory_utilization_percent: float
    token_efficiency_score: float
    latency_score: float
    cost_efficiency_score: float
    overall_health_score: float


class MetricsCollector:
    """Collects and analyzes cache performance metrics."""

    def __init__(self, history_size: int = 10000):
        self.history_size = history_size
        self.performance_history: deque = deque(maxlen=history_size)
        self.latency_history: Dict[str, deque] = {
            "hit": deque(maxlen=1000),
            "miss": deque(maxlen=1000),
            "store": deque(maxlen=1000),
        }
        self.hourly_stats: Dict[int, Dict[str, Any]] = {}
        self._lock = Lock()

        # Performance targets from requirements
        self.targets = {
            "hit_latency_ms": 48.0,  # Updated to match benchmark targets
            "miss_latency_ms": 140.0,
            "hit_rate_percent": 60.0,
            "cost_reduction_hit": 90.0,
            "cost_reduction_miss": 65.0,
        }

        # Performance optimization tracking
        self.optimization_metrics = {
            "cache_warming_efficiency": 0.0,
            "memory_pressure_score": 0.0,
            "eviction_rate": 0.0,
            "fragmentation_ratio": 0.0,
        }

        logger.info("Metrics collector initialized", history_size=history_size)

    def record_cache_operation(
        self,
        operation: str,
        latency_ms: float,
        success: bool,
        cache_hit: Optional[bool] = None,
        token_count: Optional[int] = None,
        entry_size_bytes: Optional[int] = None,
    ) -> None:
        """
        Record a cache operation for metrics analysis.

        Args:
            operation: Type of operation (get, store, invalidate)
            latency_ms: Operation latency in milliseconds
            success: Whether operation succeeded
            cache_hit: Whether this was a cache hit (for get operations)
            token_count: Number of tokens involved
            entry_size_bytes: Size of cache entry in bytes
        """
        try:
            with self._lock:
                metric = PerformanceMetric(
                    operation=operation,
                    latency_ms=latency_ms,
                    timestamp=time.time(),
                    success=success,
                    cache_hit=cache_hit,
                    token_count=token_count,
                    entry_size_bytes=entry_size_bytes,
                )

                self.performance_history.append(metric)

                # Update latency history by operation type
                if operation == "get":
                    if cache_hit:
                        self.latency_history["hit"].append(latency_ms)
                    else:
                        self.latency_history["miss"].append(latency_ms)
                elif operation == "store":
                    self.latency_history["store"].append(latency_ms)

                # Update hourly statistics
                hour = int(time.time() // 3600)
                if hour not in self.hourly_stats:
                    self.hourly_stats[hour] = {
                        "operations": 0,
                        "hits": 0,
                        "misses": 0,
                        "total_latency": 0.0,
                        "errors": 0,
                    }

                stats = self.hourly_stats[hour]
                stats["operations"] += 1
                stats["total_latency"] += latency_ms

                if not success:
                    stats["errors"] += 1
                elif operation == "get":
                    if cache_hit:
                        stats["hits"] += 1
                    else:
                        stats["misses"] += 1

                logger.debug(
                    "Cache operation recorded",
                    operation=operation,
                    latency_ms=latency_ms,
                    cache_hit=cache_hit,
                )

        except Exception as e:
            logger.error("Failed to record cache metric", error=str(e))

    def get_latency_analysis(self) -> LatencyAnalysis:
        """
        Analyze latency performance across operations.

        Returns:
            Detailed latency analysis
        """
        try:
            with self._lock:
                hit_latencies = list(self.latency_history["hit"])
                miss_latencies = list(self.latency_history["miss"])

                # Calculate averages
                avg_hit = (
                    sum(hit_latencies) / len(hit_latencies) if hit_latencies else 0.0
                )
                avg_miss = (
                    sum(miss_latencies) / len(miss_latencies) if miss_latencies else 0.0
                )

                # Calculate percentiles for hits
                hit_p50 = (
                    self._calculate_percentile(hit_latencies, 50)
                    if hit_latencies
                    else 0.0
                )
                hit_p95 = (
                    self._calculate_percentile(hit_latencies, 95)
                    if hit_latencies
                    else 0.0
                )
                hit_p99 = (
                    self._calculate_percentile(hit_latencies, 99)
                    if hit_latencies
                    else 0.0
                )

                # Calculate SLA compliance
                hit_sla_compliant = sum(
                    1 for lat in hit_latencies if lat <= self.targets["hit_latency_ms"]
                )
                hit_sla_percent = (
                    (hit_sla_compliant / len(hit_latencies) * 100)
                    if hit_latencies
                    else 0.0
                )

                miss_sla_compliant = sum(
                    1
                    for lat in miss_latencies
                    if lat <= self.targets["miss_latency_ms"]
                )
                miss_sla_percent = (
                    (miss_sla_compliant / len(miss_latencies) * 100)
                    if miss_latencies
                    else 0.0
                )

                return LatencyAnalysis(
                    avg_hit_latency_ms=avg_hit,
                    avg_miss_latency_ms=avg_miss,
                    p50_hit_latency_ms=hit_p50,
                    p95_hit_latency_ms=hit_p95,
                    p99_hit_latency_ms=hit_p99,
                    hit_sla_compliance_percent=hit_sla_percent,
                    miss_sla_compliance_percent=miss_sla_percent,
                )

        except Exception as e:
            logger.error("Failed to analyze latency", error=str(e))
            return LatencyAnalysis(0.0, 0.0, 0.0, 0.0, 0.0)

    def get_cost_analysis(self, cache_manager: CacheManager) -> CostAnalysis:
        """
        Analyze cost savings from cache usage.

        Args:
            cache_manager: Cache manager for current metrics

        Returns:
            Cost analysis results
        """
        try:
            metrics = cache_manager.get_metrics()

            # Calculate token metrics
            total_hits = metrics.cache_hits
            total_misses = metrics.cache_misses
            total_requests = total_hits + total_misses

            if total_requests == 0:
                return CostAnalysis(0, 0, 0, 0.0, 0.0, 0.0, 0.0)

            # Estimate tokens per operation
            avg_tokens_hit = self._estimate_avg_tokens("hit")
            avg_tokens_miss = self._estimate_avg_tokens("miss")

            # Calculate cost savings
            # Improved cost calculation with realistic baseline
            baseline_tokens_per_request = 1500  # Conservative estimate for RAG systems

            # Cache hits save ~95% of token processing costs (optimized)
            # Cache misses save ~70% due to cached system prompts and optimized queries
            hit_cost_savings = (
                total_hits * avg_tokens_hit * 0.95 * CostAnalysis.cost_per_token_usd
            )
            miss_cost_savings = (
                total_misses * avg_tokens_miss * 0.70 * CostAnalysis.cost_per_token_usd
            )
            total_savings = hit_cost_savings + miss_cost_savings

            # More realistic baseline comparison with traditional RAG
            baseline_cost = (
                total_requests
                * baseline_tokens_per_request
                * CostAnalysis.cost_per_token_usd
            )
            actual_cost = (
                total_requests
                * ((avg_tokens_hit + avg_tokens_miss) / 2)
                * CostAnalysis.cost_per_token_usd
            )
            reduction_percent = (
                ((baseline_cost - actual_cost) / baseline_cost * 100)
                if baseline_cost > 0
                else 0.0
            )

            return CostAnalysis(
                total_requests=total_requests,
                cache_hits=total_hits,
                cache_misses=total_misses,
                estimated_savings_usd=total_savings,
                token_cost_reduction_percent=reduction_percent,
                avg_tokens_per_hit=avg_tokens_hit,
                avg_tokens_per_miss=avg_tokens_miss,
            )

        except Exception as e:
            logger.error("Failed to analyze costs", error=str(e))
            return CostAnalysis(0, 0, 0, 0.0, 0.0, 0.0, 0.0)

    def get_cache_health_score(self, cache_manager: CacheManager) -> CacheHealthMetrics:
        """
        Calculate overall cache health score.

        Args:
            cache_manager: Cache manager for current state

        Returns:
            Cache health metrics
        """
        try:
            metrics = cache_manager.get_metrics()
            latency_analysis = self.get_latency_analysis()
            cost_analysis = self.get_cost_analysis(cache_manager)

            # Calculate component scores (0-100)
            hit_rate_score = min(
                metrics.hit_rate / self.targets["hit_rate_percent"] * 100, 100
            )

            # Latency score based on SLA compliance
            latency_score = (
                latency_analysis.hit_sla_compliance_percent
                + latency_analysis.miss_sla_compliance_percent
            ) / 2

            # Token efficiency score
            target_efficiency = 100.0  # tokens per KB
            efficiency_score = min(
                metrics.token_efficiency / target_efficiency * 100, 100
            )

            # Memory utilization score (optimal around 70-80%)
            memory_util = metrics.total_size / cache_manager.max_size_bytes * 100
            if memory_util <= 80:
                memory_score = memory_util / 80 * 100
            else:
                memory_score = max(0, 100 - (memory_util - 80) * 2)

            # Cost efficiency score
            cost_score = min(cost_analysis.token_cost_reduction_percent / 75 * 100, 100)

            # Overall health score (weighted average)
            overall_score = (
                hit_rate_score * 0.3
                + latency_score * 0.25
                + efficiency_score * 0.2
                + memory_score * 0.15
                + cost_score * 0.1
            )

            return CacheHealthMetrics(
                timestamp=time.time(),
                hit_rate_percent=metrics.hit_rate,
                miss_rate_percent=metrics.miss_rate,
                efficiency_score=efficiency_score,
                memory_utilization_percent=memory_util,
                token_efficiency_score=efficiency_score,
                latency_score=latency_score,
                cost_efficiency_score=cost_score,
                overall_health_score=overall_score,
            )

        except Exception as e:
            logger.error("Failed to calculate health score", error=str(e))
            return CacheHealthMetrics(
                timestamp=time.time(),
                hit_rate_percent=0.0,
                miss_rate_percent=100.0,
                efficiency_score=0.0,
                memory_utilization_percent=0.0,
                token_efficiency_score=0.0,
                latency_score=0.0,
                cost_efficiency_score=0.0,
                overall_health_score=0.0,
            )

    def export_metrics_report(self, cache_manager: CacheManager) -> Dict[str, Any]:
        """
        Export comprehensive metrics report.

        Args:
            cache_manager: Cache manager for current state

        Returns:
            Complete metrics report
        """
        try:
            basic_metrics = cache_manager.get_metrics()
            latency_analysis = self.get_latency_analysis()
            cost_analysis = self.get_cost_analysis(cache_manager)
            health_metrics = self.get_cache_health_score(cache_manager)

            # Recent performance trends
            recent_metrics = list(self.performance_history)[
                -100:
            ]  # Last 100 operations

            report = {
                "timestamp": time.time(),
                "basic_metrics": asdict(basic_metrics),
                "latency_analysis": asdict(latency_analysis),
                "cost_analysis": asdict(cost_analysis),
                "health_metrics": asdict(health_metrics),
                "performance_trends": {
                    "recent_operations": len(recent_metrics),
                    "avg_recent_latency": (
                        sum(m.latency_ms for m in recent_metrics) / len(recent_metrics)
                        if recent_metrics
                        else 0.0
                    ),
                    "recent_success_rate": (
                        sum(1 for m in recent_metrics if m.success)
                        / len(recent_metrics)
                        * 100
                        if recent_metrics
                        else 0.0
                    ),
                },
                "targets": self.targets,
                "alerts": self._generate_alerts(health_metrics, latency_analysis),
            }

            logger.info(
                "Metrics report generated",
                overall_health=health_metrics.overall_health_score,
                hit_rate=basic_metrics.hit_rate,
            )

            return report

        except Exception as e:
            logger.error("Failed to export metrics report", error=str(e))
            return {"error": str(e), "timestamp": time.time()}

    def _calculate_percentile(self, values: List[float], percentile: int) -> float:
        """Calculate percentile from list of values."""
        if not values:
            return 0.0

        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        index = min(index, len(sorted_values) - 1)
        return sorted_values[index]

    def _estimate_avg_tokens(self, operation_type: str) -> float:
        """Estimate average tokens for operation type."""
        with self._lock:
            recent_metrics = [
                m
                for m in list(self.performance_history)[-1000:]
                if m.token_count is not None
                and (
                    (operation_type == "hit" and m.cache_hit is True)
                    or (operation_type == "miss" and m.cache_hit is False)
                )
            ]

            if recent_metrics:
                return sum(m.token_count for m in recent_metrics) / len(recent_metrics)

            # Default estimates based on typical FACT usage
            return 750.0 if operation_type == "hit" else 500.0

    def _generate_alerts(
        self, health: CacheHealthMetrics, latency: LatencyAnalysis
    ) -> List[Dict[str, str]]:
        """Generate alerts based on performance metrics."""
        alerts = []

        # Performance alerts
        if health.hit_rate_percent < self.targets["hit_rate_percent"]:
            alerts.append(
                {
                    "level": "warning",
                    "message": f"Hit rate {health.hit_rate_percent:.1f}% below target {self.targets['hit_rate_percent']}%",
                }
            )

        if latency.avg_hit_latency_ms > self.targets["hit_latency_ms"]:
            alerts.append(
                {
                    "level": "critical",
                    "message": f"Hit latency {latency.avg_hit_latency_ms:.1f}ms exceeds target {self.targets['hit_latency_ms']}ms",
                }
            )

        if health.memory_utilization_percent > 90:
            alerts.append(
                {
                    "level": "critical",
                    "message": f"Memory utilization {health.memory_utilization_percent:.1f}% critically high",
                }
            )

        if health.overall_health_score < 60:
            alerts.append(
                {
                    "level": "warning",
                    "message": f"Overall cache health score {health.overall_health_score:.1f} below acceptable threshold",
                }
            )

        return alerts

    def track_optimization_metrics(self, cache_manager) -> Dict[str, float]:
        """Track optimization-specific metrics for performance tuning."""
        try:
            with self._lock:
                metrics = cache_manager.get_metrics()
                current_size = cache_manager._calculate_current_size()

                # Cache warming efficiency
                recent_hits = len(
                    [m for m in list(self.performance_history)[-100:] if m.cache_hit]
                )
                warming_efficiency = (
                    (recent_hits / 100 * 100) if recent_hits > 0 else 0.0
                )

                # Memory pressure score
                memory_utilization = current_size / cache_manager.max_size_bytes * 100
                memory_pressure = max(
                    0, (memory_utilization - 70) / 30 * 100
                )  # Pressure starts at 70%

                # Eviction rate (entries removed due to size limits)
                total_operations = len(self.performance_history)
                eviction_rate = metrics.cache_misses / max(1, total_operations) * 100

                # Fragmentation ratio (measure of cache efficiency)
                if metrics.total_entries > 0:
                    avg_entry_size = current_size / metrics.total_entries
                    optimal_entry_size = 2048  # 2KB optimal
                    fragmentation = (
                        abs(avg_entry_size - optimal_entry_size)
                        / optimal_entry_size
                        * 100
                    )
                else:
                    fragmentation = 0.0

                self.optimization_metrics.update(
                    {
                        "cache_warming_efficiency": warming_efficiency,
                        "memory_pressure_score": memory_pressure,
                        "eviction_rate": eviction_rate,
                        "fragmentation_ratio": fragmentation,
                    }
                )

                return self.optimization_metrics

        except Exception as e:
            logger.error("Failed to track optimization metrics", error=str(e))
            return self.optimization_metrics


# Global metrics collector
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get or create the global metrics collector."""
    global _metrics_collector

    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()

    return _metrics_collector


async def start_metrics_monitoring(
    cache_manager: CacheManager, report_interval: int = 300
) -> None:
    """
    Start continuous metrics monitoring and reporting.

    Args:
        cache_manager: Cache manager to monitor
        report_interval: Reporting interval in seconds
    """
    metrics_collector = get_metrics_collector()

    logger.info("Starting metrics monitoring", report_interval=report_interval)

    while True:
        try:
            await asyncio.sleep(report_interval)

            # Generate health report
            health = metrics_collector.get_cache_health_score(cache_manager)

            logger.info(
                "Cache health report",
                overall_score=health.overall_health_score,
                hit_rate=health.hit_rate_percent,
                memory_util=health.memory_utilization_percent,
            )

            # Log alerts if any
            report = metrics_collector.export_metrics_report(cache_manager)
            alerts = report.get("alerts", [])

            for alert in alerts:
                if alert["level"] == "critical":
                    logger.error("Cache alert", message=alert["message"])
                else:
                    logger.warning("Cache alert", message=alert["message"])

        except asyncio.CancelledError:
            logger.info("Metrics monitoring cancelled")
            break
        except Exception as e:
            logger.error("Metrics monitoring error", error=str(e))
