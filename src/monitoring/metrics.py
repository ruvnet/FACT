"""
FACT System Performance Metrics Collection

This module provides metrics collection and monitoring capabilities
for tool execution performance and system health.
"""

import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from collections import defaultdict, deque
import threading
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ToolExecutionMetric:
    """Represents a single tool execution metric."""

    tool_name: str
    success: bool
    execution_time_ms: float
    timestamp: float
    user_id: Optional[str] = None
    error_type: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemMetrics:
    """Aggregated system metrics."""

    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    average_execution_time: float = 0.0
    min_execution_time: float = float("inf")
    max_execution_time: float = 0.0
    error_rate: float = 0.0
    executions_per_minute: float = 0.0
    top_tools: List[Dict[str, Any]] = field(default_factory=list)
    recent_errors: List[Dict[str, Any]] = field(default_factory=list)


class MetricsCollector:
    """
    Collects and aggregates performance metrics for the FACT system.

    Provides real-time metrics collection, aggregation, and reporting
    for tool execution performance and system health monitoring.
    """

    def __init__(self, max_history: int = 10000):
        """
        Initialize metrics collector.

        Args:
            max_history: Maximum number of metrics to keep in memory
        """
        self.max_history = max_history
        self.metrics_history: deque = deque(maxlen=max_history)
        self.tool_stats: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "count": 0,
                "success_count": 0,
                "total_time": 0.0,
                "min_time": float("inf"),
                "max_time": 0.0,
                "recent_executions": deque(maxlen=100),
            }
        )

        # Thread safety
        self._lock = threading.RLock()

        # Start time for rate calculations
        self._start_time = time.time()

        logger.info("MetricsCollector initialized", max_history=max_history)

    def record_tool_execution(
        self,
        tool_name: str,
        success: bool,
        execution_time: float,
        user_id: Optional[str] = None,
        error_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Record a tool execution metric.

        Args:
            tool_name: Name of the executed tool
            success: Whether execution was successful
            execution_time: Execution time in milliseconds
            user_id: Optional user identifier
            error_type: Type of error if execution failed
            metadata: Additional metadata
        """
        with self._lock:
            timestamp = time.time()

            # Create metric record
            metric = ToolExecutionMetric(
                tool_name=tool_name,
                success=success,
                execution_time_ms=execution_time,
                timestamp=timestamp,
                user_id=user_id,
                error_type=error_type,
                metadata=metadata or {},
            )

            # Add to history
            self.metrics_history.append(metric)

            # Update tool-specific stats
            tool_stat = self.tool_stats[tool_name]
            tool_stat["count"] += 1
            tool_stat["total_time"] += execution_time
            tool_stat["recent_executions"].append(
                {
                    "timestamp": timestamp,
                    "success": success,
                    "execution_time": execution_time,
                }
            )

            if success:
                tool_stat["success_count"] += 1

            # Update min/max times
            tool_stat["min_time"] = min(tool_stat["min_time"], execution_time)
            tool_stat["max_time"] = max(tool_stat["max_time"], execution_time)

            logger.debug(
                "Tool execution metric recorded",
                tool_name=tool_name,
                success=success,
                execution_time_ms=execution_time,
                user_id=user_id,
            )

    def get_system_metrics(self, time_window_minutes: int = 60) -> SystemMetrics:
        """
        Get aggregated system metrics.

        Args:
            time_window_minutes: Time window for calculations in minutes

        Returns:
            SystemMetrics object with aggregated data
        """
        with self._lock:
            current_time = time.time()
            cutoff_time = current_time - (time_window_minutes * 60)

            # Filter metrics within time window
            recent_metrics = [
                metric
                for metric in self.metrics_history
                if metric.timestamp >= cutoff_time
            ]

            if not recent_metrics:
                return SystemMetrics()

            # Calculate basic stats
            total_executions = len(recent_metrics)
            successful_executions = sum(1 for m in recent_metrics if m.success)
            failed_executions = total_executions - successful_executions

            execution_times = [m.execution_time_ms for m in recent_metrics]
            average_execution_time = sum(execution_times) / len(execution_times)
            min_execution_time = min(execution_times)
            max_execution_time = max(execution_times)

            error_rate = (
                (failed_executions / total_executions) * 100
                if total_executions > 0
                else 0
            )
            executions_per_minute = total_executions / time_window_minutes

            # Get top tools by usage
            tool_counts = defaultdict(int)
            for metric in recent_metrics:
                tool_counts[metric.tool_name] += 1

            top_tools = [
                {"tool_name": tool, "count": count}
                for tool, count in sorted(
                    tool_counts.items(), key=lambda x: x[1], reverse=True
                )[:10]
            ]

            # Get recent errors
            recent_errors = [
                {
                    "tool_name": m.tool_name,
                    "error_type": m.error_type,
                    "timestamp": m.timestamp,
                    "execution_time_ms": m.execution_time_ms,
                    "user_id": m.user_id,
                }
                for m in recent_metrics
                if not m.success
            ][
                -10:
            ]  # Last 10 errors

            return SystemMetrics(
                total_executions=total_executions,
                successful_executions=successful_executions,
                failed_executions=failed_executions,
                average_execution_time=average_execution_time,
                min_execution_time=min_execution_time,
                max_execution_time=max_execution_time,
                error_rate=error_rate,
                executions_per_minute=executions_per_minute,
                top_tools=top_tools,
                recent_errors=recent_errors,
            )

    def get_tool_metrics(self, tool_name: str) -> Dict[str, Any]:
        """
        Get detailed metrics for a specific tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Tool-specific metrics
        """
        with self._lock:
            if tool_name not in self.tool_stats:
                return {
                    "tool_name": tool_name,
                    "total_executions": 0,
                    "success_rate": 0.0,
                    "average_execution_time": 0.0,
                    "min_execution_time": 0.0,
                    "max_execution_time": 0.0,
                }

            stats = self.tool_stats[tool_name]

            # Calculate derived metrics
            success_rate = (
                (stats["success_count"] / stats["count"]) * 100
                if stats["count"] > 0
                else 0
            )
            average_time = (
                stats["total_time"] / stats["count"] if stats["count"] > 0 else 0
            )

            # Recent performance (last 24 hours)
            current_time = time.time()
            cutoff_time = current_time - (24 * 60 * 60)  # 24 hours ago

            recent_executions = [
                exec
                for exec in stats["recent_executions"]
                if exec["timestamp"] >= cutoff_time
            ]

            recent_success_rate = 0.0
            recent_avg_time = 0.0

            if recent_executions:
                recent_successes = sum(
                    1 for exec in recent_executions if exec["success"]
                )
                recent_success_rate = (recent_successes / len(recent_executions)) * 100
                recent_avg_time = sum(
                    exec["execution_time"] for exec in recent_executions
                ) / len(recent_executions)

            return {
                "tool_name": tool_name,
                "total_executions": stats["count"],
                "successful_executions": stats["success_count"],
                "failed_executions": stats["count"] - stats["success_count"],
                "success_rate": success_rate,
                "average_execution_time": average_time,
                "min_execution_time": (
                    stats["min_time"] if stats["min_time"] != float("inf") else 0
                ),
                "max_execution_time": stats["max_time"],
                "recent_24h": {
                    "executions": len(recent_executions),
                    "success_rate": recent_success_rate,
                    "average_execution_time": recent_avg_time,
                },
            }

    def get_user_metrics(
        self, user_id: str, time_window_minutes: int = 60
    ) -> Dict[str, Any]:
        """
        Get metrics for a specific user.

        Args:
            user_id: User identifier
            time_window_minutes: Time window in minutes

        Returns:
            User-specific metrics
        """
        with self._lock:
            current_time = time.time()
            cutoff_time = current_time - (time_window_minutes * 60)

            # Filter metrics for this user within time window
            user_metrics = [
                metric
                for metric in self.metrics_history
                if metric.user_id == user_id and metric.timestamp >= cutoff_time
            ]

            if not user_metrics:
                return {
                    "user_id": user_id,
                    "total_executions": 0,
                    "success_rate": 0.0,
                    "tools_used": [],
                    "average_execution_time": 0.0,
                }

            # Calculate user stats
            total_executions = len(user_metrics)
            successful_executions = sum(1 for m in user_metrics if m.success)
            success_rate = (successful_executions / total_executions) * 100

            execution_times = [m.execution_time_ms for m in user_metrics]
            average_execution_time = sum(execution_times) / len(execution_times)

            # Tools used by this user
            tool_usage = defaultdict(int)
            for metric in user_metrics:
                tool_usage[metric.tool_name] += 1

            tools_used = [
                {"tool_name": tool, "count": count}
                for tool, count in sorted(
                    tool_usage.items(), key=lambda x: x[1], reverse=True
                )
            ]

            return {
                "user_id": user_id,
                "time_window_minutes": time_window_minutes,
                "total_executions": total_executions,
                "successful_executions": successful_executions,
                "failed_executions": total_executions - successful_executions,
                "success_rate": success_rate,
                "average_execution_time": average_execution_time,
                "tools_used": tools_used,
            }

    def get_performance_trends(
        self, time_window_hours: int = 24, bucket_minutes: int = 60
    ) -> Dict[str, Any]:
        """
        Get performance trends over time.

        Args:
            time_window_hours: Time window in hours
            bucket_minutes: Time bucket size in minutes

        Returns:
            Performance trend data
        """
        with self._lock:
            current_time = time.time()
            cutoff_time = current_time - (time_window_hours * 60 * 60)
            bucket_size = bucket_minutes * 60

            # Filter metrics within time window
            recent_metrics = [
                metric
                for metric in self.metrics_history
                if metric.timestamp >= cutoff_time
            ]

            if not recent_metrics:
                return {"buckets": [], "summary": {}}

            # Create time buckets
            start_time = cutoff_time
            buckets = []

            while start_time < current_time:
                bucket_end = start_time + bucket_size
                bucket_metrics = [
                    m for m in recent_metrics if start_time <= m.timestamp < bucket_end
                ]

                if bucket_metrics:
                    total = len(bucket_metrics)
                    successful = sum(1 for m in bucket_metrics if m.success)
                    execution_times = [m.execution_time_ms for m in bucket_metrics]

                    bucket_data = {
                        "timestamp": start_time,
                        "total_executions": total,
                        "successful_executions": successful,
                        "failed_executions": total - successful,
                        "success_rate": (successful / total) * 100,
                        "average_execution_time": sum(execution_times)
                        / len(execution_times),
                        "min_execution_time": min(execution_times),
                        "max_execution_time": max(execution_times),
                    }
                else:
                    bucket_data = {
                        "timestamp": start_time,
                        "total_executions": 0,
                        "successful_executions": 0,
                        "failed_executions": 0,
                        "success_rate": 0.0,
                        "average_execution_time": 0.0,
                        "min_execution_time": 0.0,
                        "max_execution_time": 0.0,
                    }

                buckets.append(bucket_data)
                start_time = bucket_end

            # Calculate summary
            if recent_metrics:
                total_executions = len(recent_metrics)
                successful_executions = sum(1 for m in recent_metrics if m.success)
                all_execution_times = [m.execution_time_ms for m in recent_metrics]

                summary = {
                    "time_window_hours": time_window_hours,
                    "bucket_minutes": bucket_minutes,
                    "total_executions": total_executions,
                    "success_rate": (successful_executions / total_executions) * 100,
                    "average_execution_time": sum(all_execution_times)
                    / len(all_execution_times),
                    "min_execution_time": min(all_execution_times),
                    "max_execution_time": max(all_execution_times),
                }
            else:
                summary = {}

            return {"buckets": buckets, "summary": summary}

    def export_metrics(self, format: str = "json") -> str:
        """
        Export metrics in specified format.

        Args:
            format: Export format ("json" or "csv")

        Returns:
            Exported metrics as string
        """
        with self._lock:
            if format.lower() == "json":
                import json

                export_data = {
                    "system_metrics": self.get_system_metrics().__dict__,
                    "tool_metrics": {
                        tool_name: self.get_tool_metrics(tool_name)
                        for tool_name in self.tool_stats.keys()
                    },
                    "performance_trends": self.get_performance_trends(),
                    "export_timestamp": time.time(),
                    "total_metrics_count": len(self.metrics_history),
                }

                return json.dumps(export_data, indent=2)

            elif format.lower() == "csv":
                import csv
                import io

                output = io.StringIO()
                writer = csv.writer(output)

                # Write header
                writer.writerow(
                    [
                        "timestamp",
                        "tool_name",
                        "success",
                        "execution_time_ms",
                        "user_id",
                        "error_type",
                    ]
                )

                # Write metrics
                for metric in self.metrics_history:
                    writer.writerow(
                        [
                            metric.timestamp,
                            metric.tool_name,
                            metric.success,
                            metric.execution_time_ms,
                            metric.user_id or "",
                            metric.error_type or "",
                        ]
                    )

                return output.getvalue()

            else:
                raise ValueError(f"Unsupported export format: {format}")

    def clear_metrics(self, older_than_hours: Optional[int] = None) -> int:
        """
        Clear metrics from memory.

        Args:
            older_than_hours: Only clear metrics older than this many hours

        Returns:
            Number of metrics cleared
        """
        with self._lock:
            if older_than_hours is None:
                # Clear all metrics
                cleared_count = len(self.metrics_history)
                self.metrics_history.clear()
                self.tool_stats.clear()
                logger.info("All metrics cleared", cleared_count=cleared_count)
                return cleared_count
            else:
                # Clear only old metrics
                cutoff_time = time.time() - (older_than_hours * 60 * 60)

                original_count = len(self.metrics_history)
                self.metrics_history = deque(
                    (
                        metric
                        for metric in self.metrics_history
                        if metric.timestamp >= cutoff_time
                    ),
                    maxlen=self.max_history,
                )

                cleared_count = original_count - len(self.metrics_history)
                logger.info(
                    "Old metrics cleared",
                    cleared_count=cleared_count,
                    older_than_hours=older_than_hours,
                )
                return cleared_count


# Global metrics collector instance
_metrics_collector = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance."""
    return _metrics_collector
