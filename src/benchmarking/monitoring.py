"""
FACT Continuous Performance Monitoring

Implements continuous performance monitoring, alerting, and trend analysis
for production FACT systems.
"""

import time
import asyncio
import json
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field, asdict
from collections import deque
from datetime import datetime, timedelta
import structlog

try:
    # Try relative imports first (when used as package)
    from framework import BenchmarkFramework, BenchmarkResult
    from profiler import SystemProfiler, BottleneckAnalyzer
    from cache.manager import CacheManager
    from cache.metrics import get_metrics_collector
except ImportError:
    # Fall back to absolute imports (when run as script)
    import sys
    from pathlib import Path

    # Add src to path if not already there
    src_path = str(Path(__file__).parent.parent)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    from benchmarking.framework import BenchmarkFramework, BenchmarkResult
    from benchmarking.profiler import SystemProfiler, BottleneckAnalyzer
    from cache.manager import CacheManager
    from cache.metrics import get_metrics_collector

logger = structlog.get_logger(__name__)


@dataclass
class PerformanceAlert:
    """Performance alert definition."""

    alert_id: str
    severity: str  # "info", "warning", "critical"
    component: str
    metric_name: str
    threshold_value: float
    actual_value: float
    message: str
    timestamp: float = field(default_factory=time.time)
    resolved: bool = False
    resolution_time: Optional[float] = None


@dataclass
class PerformanceTrend:
    """Performance trend analysis."""

    metric_name: str
    time_period: str
    direction: str  # "improving", "stable", "degrading"
    change_percentage: float
    significance: float  # 0-1 confidence score
    data_points: List[Tuple[float, float]]  # (timestamp, value) pairs
    analysis: str


@dataclass
class MonitoringConfig:
    """Configuration for continuous monitoring."""

    monitoring_interval_seconds: int = 60
    alert_check_interval_seconds: int = 30
    trend_analysis_hours: int = 24
    max_alerts_per_hour: int = 10
    alert_cooldown_minutes: int = 15

    # Performance thresholds
    response_time_warning_ms: float = 80.0
    response_time_critical_ms: float = 120.0
    cache_hit_rate_warning: float = 50.0
    cache_hit_rate_critical: float = 40.0
    error_rate_warning: float = 5.0
    error_rate_critical: float = 10.0
    cost_increase_warning: float = 20.0
    cost_increase_critical: float = 50.0


class ContinuousMonitor:
    """
    Continuous performance monitoring system.

    Provides real-time monitoring, alerting, and trend analysis
    for FACT system performance.
    """

    def __init__(self, config: Optional[MonitoringConfig] = None):
        """
        Initialize continuous monitor.

        Args:
            config: Monitoring configuration
        """
        self.config = config or MonitoringConfig()
        self.benchmark_framework = BenchmarkFramework()
        self.profiler = SystemProfiler()
        self.bottleneck_analyzer = BottleneckAnalyzer()

        # Monitoring state
        self.monitoring_active = False
        self.monitor_task: Optional[asyncio.Task] = None
        self.alert_task: Optional[asyncio.Task] = None

        # Data storage
        self.performance_history: deque = deque(maxlen=10000)
        self.active_alerts: Dict[str, PerformanceAlert] = {}
        self.alert_history: deque = deque(maxlen=1000)
        self.trends: Dict[str, PerformanceTrend] = {}

        # Alert callbacks
        self.alert_callbacks: List[Callable[[PerformanceAlert], None]] = []

        # Test queries for monitoring
        self.monitoring_queries = [
            "What is the current system status?",
            "Generate a quick performance summary",
            "Check recent metrics",
        ]

        logger.info("Continuous monitor initialized")

    async def start_monitoring(self, cache_manager: Optional[CacheManager] = None):
        """
        Start continuous performance monitoring.

        Args:
            cache_manager: Cache manager to monitor
        """
        if self.monitoring_active:
            logger.warning("Monitoring already active")
            return

        self.monitoring_active = True

        # Start profiler monitoring
        await self.profiler.start_continuous_monitoring()

        # Start monitoring tasks
        self.monitor_task = asyncio.create_task(self._monitoring_loop(cache_manager))
        self.alert_task = asyncio.create_task(self._alert_checking_loop(cache_manager))

        logger.info(
            "Continuous monitoring started",
            interval_seconds=self.config.monitoring_interval_seconds,
        )

    async def stop_monitoring(self):
        """Stop continuous performance monitoring."""
        self.monitoring_active = False

        # Stop profiler monitoring
        await self.profiler.stop_continuous_monitoring()

        # Cancel monitoring tasks
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass

        if self.alert_task:
            self.alert_task.cancel()
            try:
                await self.alert_task
            except asyncio.CancelledError:
                pass

        logger.info("Continuous monitoring stopped")

    async def _monitoring_loop(self, cache_manager: Optional[CacheManager]):
        """Main monitoring loop."""
        query_index = 0

        while self.monitoring_active:
            try:
                # Run performance measurement
                query = self.monitoring_queries[
                    query_index % len(self.monitoring_queries)
                ]

                start_time = time.perf_counter()
                result = await self.benchmark_framework.run_single_benchmark(
                    query, cache_manager
                )

                # Store performance data
                self.performance_history.append(result)

                # Update trends
                await self._update_performance_trends()

                query_index += 1

                logger.debug(
                    "Monitoring measurement completed",
                    response_time_ms=result.response_time_ms,
                    cache_hit=result.cache_hit,
                )

                await asyncio.sleep(self.config.monitoring_interval_seconds)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in monitoring loop", error=str(e))
                await asyncio.sleep(5.0)  # Brief pause before retry

    async def _alert_checking_loop(self, cache_manager: Optional[CacheManager]):
        """Alert checking loop."""
        while self.monitoring_active:
            try:
                # Check for performance alerts
                await self._check_performance_alerts(cache_manager)

                # Check for trend alerts
                await self._check_trend_alerts()

                # Clean up resolved alerts
                self._cleanup_resolved_alerts()

                await asyncio.sleep(self.config.alert_check_interval_seconds)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in alert checking loop", error=str(e))
                await asyncio.sleep(5.0)

    async def _check_performance_alerts(self, cache_manager: Optional[CacheManager]):
        """Check for performance threshold violations."""
        if not self.performance_history:
            return

        # Get recent performance data
        recent_results = list(self.performance_history)[-10:]  # Last 10 measurements

        if not recent_results:
            return

        # Calculate current metrics
        response_times = [r.response_time_ms for r in recent_results if r.success]
        cache_hits = sum(1 for r in recent_results if r.cache_hit)
        total_requests = len(recent_results)
        errors = sum(1 for r in recent_results if not r.success)

        if not response_times:
            return

        avg_response_time = sum(response_times) / len(response_times)
        cache_hit_rate = (
            (cache_hits / total_requests * 100) if total_requests > 0 else 0
        )
        error_rate = (errors / total_requests * 100) if total_requests > 0 else 0

        # Check response time alerts
        await self._check_response_time_alert(avg_response_time)

        # Check cache hit rate alerts
        await self._check_cache_hit_rate_alert(cache_hit_rate)

        # Check error rate alerts
        await self._check_error_rate_alert(error_rate)

        # Check cache-specific alerts
        if cache_manager:
            await self._check_cache_alerts(cache_manager)

    async def _check_response_time_alert(self, avg_response_time: float):
        """Check response time threshold alerts."""
        alert_id = "response_time"

        if avg_response_time >= self.config.response_time_critical_ms:
            severity = "critical"
            threshold = self.config.response_time_critical_ms
        elif avg_response_time >= self.config.response_time_warning_ms:
            severity = "warning"
            threshold = self.config.response_time_warning_ms
        else:
            # Response time is acceptable, resolve any existing alert
            if alert_id in self.active_alerts:
                await self._resolve_alert(alert_id)
            return

        # Create or update alert
        if alert_id not in self.active_alerts:
            alert = PerformanceAlert(
                alert_id=alert_id,
                severity=severity,
                component="Response Time",
                metric_name="avg_response_time_ms",
                threshold_value=threshold,
                actual_value=avg_response_time,
                message=f"Average response time {avg_response_time:.1f}ms exceeds {severity} threshold {threshold}ms",
            )

            await self._trigger_alert(alert)

    async def _check_cache_hit_rate_alert(self, cache_hit_rate: float):
        """Check cache hit rate threshold alerts."""
        alert_id = "cache_hit_rate"

        if cache_hit_rate <= self.config.cache_hit_rate_critical:
            severity = "critical"
            threshold = self.config.cache_hit_rate_critical
        elif cache_hit_rate <= self.config.cache_hit_rate_warning:
            severity = "warning"
            threshold = self.config.cache_hit_rate_warning
        else:
            # Cache hit rate is acceptable
            if alert_id in self.active_alerts:
                await self._resolve_alert(alert_id)
            return

        if alert_id not in self.active_alerts:
            alert = PerformanceAlert(
                alert_id=alert_id,
                severity=severity,
                component="Cache Performance",
                metric_name="cache_hit_rate",
                threshold_value=threshold,
                actual_value=cache_hit_rate,
                message=f"Cache hit rate {cache_hit_rate:.1f}% below {severity} threshold {threshold}%",
            )

            await self._trigger_alert(alert)

    async def _check_error_rate_alert(self, error_rate: float):
        """Check error rate threshold alerts."""
        alert_id = "error_rate"

        if error_rate >= self.config.error_rate_critical:
            severity = "critical"
            threshold = self.config.error_rate_critical
        elif error_rate >= self.config.error_rate_warning:
            severity = "warning"
            threshold = self.config.error_rate_warning
        else:
            # Error rate is acceptable
            if alert_id in self.active_alerts:
                await self._resolve_alert(alert_id)
            return

        if alert_id not in self.active_alerts:
            alert = PerformanceAlert(
                alert_id=alert_id,
                severity=severity,
                component="System Reliability",
                metric_name="error_rate",
                threshold_value=threshold,
                actual_value=error_rate,
                message=f"Error rate {error_rate:.1f}% exceeds {severity} threshold {threshold}%",
            )

            await self._trigger_alert(alert)

    async def _check_cache_alerts(self, cache_manager: CacheManager):
        """Check cache-specific alerts."""
        try:
            metrics = cache_manager.get_metrics()

            # Memory utilization alert
            memory_util = metrics.total_size / cache_manager.max_size_bytes * 100
            if memory_util > 90:
                alert_id = "cache_memory"
                if alert_id not in self.active_alerts:
                    alert = PerformanceAlert(
                        alert_id=alert_id,
                        severity="warning",
                        component="Cache Memory",
                        metric_name="memory_utilization",
                        threshold_value=90.0,
                        actual_value=memory_util,
                        message=f"Cache memory utilization {memory_util:.1f}% approaching limit",
                    )
                    await self._trigger_alert(alert)

        except Exception as e:
            logger.error("Error checking cache alerts", error=str(e))

    async def _check_trend_alerts(self):
        """Check for concerning performance trends."""
        for metric_name, trend in self.trends.items():
            if trend.direction == "degrading" and trend.significance > 0.7:
                alert_id = f"trend_{metric_name}"

                if alert_id not in self.active_alerts:
                    alert = PerformanceAlert(
                        alert_id=alert_id,
                        severity="warning",
                        component="Performance Trend",
                        metric_name=metric_name,
                        threshold_value=0.0,  # Trend-based, no fixed threshold
                        actual_value=trend.change_percentage,
                        message=f"{metric_name} showing degrading trend: {trend.change_percentage:.1f}% change",
                    )

                    await self._trigger_alert(alert)

    async def _trigger_alert(self, alert: PerformanceAlert):
        """Trigger a performance alert."""
        self.active_alerts[alert.alert_id] = alert
        self.alert_history.append(alert)

        logger.warning(
            "Performance alert triggered",
            alert_id=alert.alert_id,
            severity=alert.severity,
            component=alert.component,
            message=alert.message,
        )

        # Call alert callbacks
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error("Error in alert callback", error=str(e))

    async def _resolve_alert(self, alert_id: str):
        """Resolve an active alert."""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.resolved = True
            alert.resolution_time = time.time()

            del self.active_alerts[alert_id]

            logger.info(
                "Performance alert resolved",
                alert_id=alert_id,
                component=alert.component,
            )

    def _cleanup_resolved_alerts(self):
        """Clean up old resolved alerts from history."""
        cutoff_time = time.time() - (24 * 60 * 60)  # 24 hours ago

        # Keep only recent alerts
        recent_alerts = deque()
        for alert in self.alert_history:
            if alert.timestamp >= cutoff_time:
                recent_alerts.append(alert)

        self.alert_history = recent_alerts

    async def _update_performance_trends(self):
        """Update performance trend analysis."""
        if len(self.performance_history) < 10:
            return

        # Analyze trends for key metrics
        metrics_to_analyze = [
            ("response_time", lambda r: r.response_time_ms),
            ("cache_hit_rate", lambda r: 1.0 if r.cache_hit else 0.0),
            ("success_rate", lambda r: 1.0 if r.success else 0.0),
        ]

        for metric_name, extractor in metrics_to_analyze:
            trend = self._calculate_trend(metric_name, extractor)
            if trend:
                self.trends[metric_name] = trend

    def _calculate_trend(
        self, metric_name: str, value_extractor: Callable
    ) -> Optional[PerformanceTrend]:
        """Calculate trend for a specific metric."""
        try:
            # Get recent data points
            recent_data = list(self.performance_history)[-100:]  # Last 100 measurements

            if len(recent_data) < 10:
                return None

            # Extract values and timestamps
            data_points = [
                (result.timestamp, value_extractor(result)) for result in recent_data
            ]

            # Simple linear trend analysis
            timestamps = [p[0] for p in data_points]
            values = [p[1] for p in data_points]

            if not values or all(v == values[0] for v in values):
                return PerformanceTrend(
                    metric_name=metric_name,
                    time_period="recent",
                    direction="stable",
                    change_percentage=0.0,
                    significance=1.0,
                    data_points=data_points,
                    analysis="No significant variation detected",
                )

            # Calculate slope (trend direction)
            n = len(values)
            sum_x = sum(range(n))
            sum_y = sum(values)
            sum_xy = sum(i * v for i, v in enumerate(values))
            sum_x2 = sum(i * i for i in range(n))

            slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)

            # Calculate percentage change
            first_avg = sum(values[:5]) / 5 if len(values) >= 5 else values[0]
            last_avg = sum(values[-5:]) / 5 if len(values) >= 5 else values[-1]

            if first_avg != 0:
                change_percentage = ((last_avg - first_avg) / first_avg) * 100
            else:
                change_percentage = 0.0

            # Determine trend direction
            if abs(change_percentage) < 5.0:
                direction = "stable"
            elif change_percentage > 0:
                direction = (
                    "improving" if metric_name != "response_time" else "degrading"
                )
            else:
                direction = (
                    "degrading" if metric_name != "response_time" else "improving"
                )

            # Calculate significance (correlation strength)
            significance = min(1.0, abs(slope) * 10)  # Simple significance measure

            return PerformanceTrend(
                metric_name=metric_name,
                time_period="recent",
                direction=direction,
                change_percentage=abs(change_percentage),
                significance=significance,
                data_points=data_points[-20:],  # Keep last 20 points
                analysis=f"Trend shows {direction} pattern with {change_percentage:.1f}% change",
            )

        except Exception as e:
            logger.error("Error calculating trend", metric=metric_name, error=str(e))
            return None

    def add_alert_callback(self, callback: Callable[[PerformanceAlert], None]):
        """Add callback function for alert notifications."""
        self.alert_callbacks.append(callback)

    def get_monitoring_status(self) -> Dict[str, Any]:
        """Get current monitoring status."""
        return {
            "monitoring_active": self.monitoring_active,
            "active_alerts": len(self.active_alerts),
            "alert_summary": {
                severity: len(
                    [a for a in self.active_alerts.values() if a.severity == severity]
                )
                for severity in ["info", "warning", "critical"]
            },
            "performance_history_size": len(self.performance_history),
            "trends_tracked": len(self.trends),
            "config": asdict(self.config),
        }

    def export_monitoring_report(self) -> Dict[str, Any]:
        """Export comprehensive monitoring report."""
        # Recent performance summary
        recent_results = list(self.performance_history)[-50:]

        if recent_results:
            successful_results = [r for r in recent_results if r.success]
            response_times = [r.response_time_ms for r in successful_results]
            cache_hits = sum(1 for r in recent_results if r.cache_hit)

            performance_summary = {
                "total_measurements": len(recent_results),
                "successful_measurements": len(successful_results),
                "avg_response_time_ms": (
                    sum(response_times) / len(response_times) if response_times else 0
                ),
                "cache_hit_rate": (
                    (cache_hits / len(recent_results) * 100) if recent_results else 0
                ),
                "error_rate": (
                    (
                        (len(recent_results) - len(successful_results))
                        / len(recent_results)
                        * 100
                    )
                    if recent_results
                    else 0
                ),
            }
        else:
            performance_summary = {}

        return {
            "timestamp": time.time(),
            "monitoring_period": "recent",
            "status": self.get_monitoring_status(),
            "performance_summary": performance_summary,
            "active_alerts": [asdict(alert) for alert in self.active_alerts.values()],
            "recent_alert_history": [
                asdict(alert) for alert in list(self.alert_history)[-10:]
            ],
            "trends": {name: asdict(trend) for name, trend in self.trends.items()},
            "recommendations": self._generate_monitoring_recommendations(),
        }

    def _generate_monitoring_recommendations(self) -> List[str]:
        """Generate recommendations based on monitoring data."""
        recommendations = []

        # Check for active critical alerts
        critical_alerts = [
            a for a in self.active_alerts.values() if a.severity == "critical"
        ]
        if critical_alerts:
            recommendations.append("Address critical performance alerts immediately")

        # Check for degrading trends
        degrading_trends = [
            t for t in self.trends.values() if t.direction == "degrading"
        ]
        if degrading_trends:
            recommendations.append("Investigate degrading performance trends")

        # General recommendations
        if len(self.performance_history) < 100:
            recommendations.append("Allow more time for comprehensive trend analysis")

        if not recommendations:
            recommendations.append("Performance monitoring shows healthy system status")

        return recommendations


class PerformanceTracker:
    """
    Lightweight performance tracking for specific operations.

    Provides focused tracking for specific performance metrics
    without full continuous monitoring overhead.
    """

    def __init__(self):
        """Initialize performance tracker."""
        self.tracked_operations: Dict[str, List[float]] = {}
        self.operation_metadata: Dict[str, Dict[str, Any]] = {}

        logger.info("Performance tracker initialized")

    def track_operation(self, operation_name: str, duration_ms: float, **metadata):
        """
        Track a single operation performance.

        Args:
            operation_name: Name of the operation
            duration_ms: Operation duration in milliseconds
            **metadata: Additional metadata
        """
        if operation_name not in self.tracked_operations:
            self.tracked_operations[operation_name] = []
            self.operation_metadata[operation_name] = {}

        self.tracked_operations[operation_name].append(duration_ms)

        # Update metadata
        for key, value in metadata.items():
            if key not in self.operation_metadata[operation_name]:
                self.operation_metadata[operation_name][key] = []
            self.operation_metadata[operation_name][key].append(value)

        # Keep only recent measurements (last 1000)
        if len(self.tracked_operations[operation_name]) > 1000:
            self.tracked_operations[operation_name] = self.tracked_operations[
                operation_name
            ][-1000:]

            # Also trim metadata
            for key in self.operation_metadata[operation_name]:
                if len(self.operation_metadata[operation_name][key]) > 1000:
                    self.operation_metadata[operation_name][key] = (
                        self.operation_metadata[operation_name][key][-1000:]
                    )

    def get_operation_stats(self, operation_name: str) -> Dict[str, Any]:
        """Get statistics for a tracked operation."""
        if operation_name not in self.tracked_operations:
            return {"error": "Operation not tracked"}

        durations = self.tracked_operations[operation_name]

        if not durations:
            return {"error": "No data available"}

        import statistics

        stats = {
            "operation_name": operation_name,
            "total_executions": len(durations),
            "avg_duration_ms": statistics.mean(durations),
            "min_duration_ms": min(durations),
            "max_duration_ms": max(durations),
            "median_duration_ms": statistics.median(durations),
            "std_deviation": statistics.stdev(durations) if len(durations) > 1 else 0,
        }

        # Add percentiles if enough data
        if len(durations) >= 10:
            stats.update(
                {
                    "p90_duration_ms": statistics.quantiles(durations, n=10)[8],
                    "p95_duration_ms": statistics.quantiles(durations, n=20)[18],
                    "p99_duration_ms": (
                        statistics.quantiles(durations, n=100)[98]
                        if len(durations) >= 100
                        else max(durations)
                    ),
                }
            )

        return stats

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all tracked operations."""
        return {
            operation: self.get_operation_stats(operation)
            for operation in self.tracked_operations.keys()
        }

    def clear_tracking(self, operation_name: Optional[str] = None):
        """Clear tracking data for specific operation or all operations."""
        if operation_name:
            self.tracked_operations.pop(operation_name, None)
            self.operation_metadata.pop(operation_name, None)
        else:
            self.tracked_operations.clear()
            self.operation_metadata.clear()

        logger.info("Tracking data cleared", operation=operation_name or "all")
