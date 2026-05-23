"""
FACT System Performance Profiler

Advanced profiling tools for identifying bottlenecks, analyzing system performance,
and providing optimization recommendations.
"""

import time
import asyncio
import psutil
import threading
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from contextlib import asynccontextmanager
import structlog

try:
    # Try relative imports first (when used as package)
    from cache.manager import CacheManager
    from monitoring.metrics import get_metrics_collector
except ImportError:
    # Fall back to absolute imports (when run as script)
    import sys
    from pathlib import Path

    # Add src to path if not already there
    src_path = str(Path(__file__).parent.parent)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    from cache.manager import CacheManager
    from monitoring.metrics import get_metrics_collector

logger = structlog.get_logger(__name__)


@dataclass
class ProfilePoint:
    """Individual profiling measurement point."""

    name: str
    start_time: float
    end_time: float
    duration_ms: float
    cpu_percent: float
    memory_mb: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemSnapshot:
    """System resource snapshot."""

    timestamp: float
    cpu_percent: float
    memory_percent: float
    memory_available_mb: float
    disk_io_read_mb: float
    disk_io_write_mb: float
    network_sent_mb: float
    network_recv_mb: float
    process_count: int
    thread_count: int


@dataclass
class BottleneckAnalysis:
    """Analysis of system bottlenecks."""

    component: str
    severity: str  # "low", "medium", "high", "critical"
    impact_percentage: float
    description: str
    recommendations: List[str]
    metrics: Dict[str, Any]


@dataclass
class ProfileResult:
    """Complete profiling result."""

    execution_time_ms: float
    profile_points: List[ProfilePoint]
    system_snapshots: List[SystemSnapshot]
    bottlenecks: List[BottleneckAnalysis]
    performance_summary: Dict[str, Any]
    optimization_recommendations: List[str]
    timestamp: float = field(default_factory=time.time)


class SystemProfiler:
    """
    Advanced system profiler for performance analysis.

    Provides detailed profiling of system components, resource usage,
    and performance bottleneck identification.
    """

    def __init__(self, sampling_interval: float = 0.1):
        """
        Initialize system profiler.

        Args:
            sampling_interval: Resource sampling interval in seconds
        """
        self.sampling_interval = sampling_interval
        self.profile_points: List[ProfilePoint] = []
        self.system_snapshots: List[SystemSnapshot] = []
        self.active_profiles: Dict[str, float] = {}
        self._monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None

        # Performance thresholds
        self.thresholds = {
            "cpu_percent": 80.0,
            "memory_percent": 85.0,
            "response_time_ms": 100.0,
            "cache_latency_ms": 50.0,
            "db_latency_ms": 10.0,
        }

        logger.info("System profiler initialized", sampling_interval=sampling_interval)

    @asynccontextmanager
    async def profile_operation(self, operation_name: str, **metadata):
        """
        Context manager for profiling operations.

        Args:
            operation_name: Name of the operation being profiled
            **metadata: Additional metadata to include
        """
        start_time = time.perf_counter()
        start_cpu = psutil.cpu_percent()
        start_memory = psutil.virtual_memory().used / (1024 * 1024)

        try:
            yield
        finally:
            end_time = time.perf_counter()
            end_cpu = psutil.cpu_percent()
            end_memory = psutil.virtual_memory().used / (1024 * 1024)

            duration_ms = (end_time - start_time) * 1000
            avg_cpu = (start_cpu + end_cpu) / 2
            avg_memory = (start_memory + end_memory) / 2

            profile_point = ProfilePoint(
                name=operation_name,
                start_time=start_time,
                end_time=end_time,
                duration_ms=duration_ms,
                cpu_percent=avg_cpu,
                memory_mb=avg_memory,
                metadata=metadata,
            )

            self.profile_points.append(profile_point)

            logger.debug(
                "Operation profiled",
                operation=operation_name,
                duration_ms=duration_ms,
                cpu_percent=avg_cpu,
            )

    async def start_continuous_monitoring(self):
        """Start continuous system resource monitoring."""
        if self._monitoring:
            return

        self._monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_resources())

        logger.info("Started continuous monitoring")

    async def stop_continuous_monitoring(self):
        """Stop continuous system resource monitoring."""
        self._monitoring = False

        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        logger.info("Stopped continuous monitoring")

    async def _monitor_resources(self):
        """Monitor system resources continuously."""
        while self._monitoring:
            try:
                snapshot = self._take_system_snapshot()
                self.system_snapshots.append(snapshot)

                # Keep only recent snapshots (last 1000)
                if len(self.system_snapshots) > 1000:
                    self.system_snapshots = self.system_snapshots[-1000:]

                await asyncio.sleep(self.sampling_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error monitoring resources", error=str(e))
                await asyncio.sleep(1.0)

    def _take_system_snapshot(self) -> SystemSnapshot:
        """Take a snapshot of current system resources."""
        try:
            memory = psutil.virtual_memory()
            disk_io = psutil.disk_io_counters()
            network_io = psutil.net_io_counters()

            return SystemSnapshot(
                timestamp=time.time(),
                cpu_percent=psutil.cpu_percent(),
                memory_percent=memory.percent,
                memory_available_mb=memory.available / (1024 * 1024),
                disk_io_read_mb=disk_io.read_bytes / (1024 * 1024) if disk_io else 0,
                disk_io_write_mb=disk_io.write_bytes / (1024 * 1024) if disk_io else 0,
                network_sent_mb=(
                    network_io.bytes_sent / (1024 * 1024) if network_io else 0
                ),
                network_recv_mb=(
                    network_io.bytes_recv / (1024 * 1024) if network_io else 0
                ),
                process_count=len(psutil.pids()),
                thread_count=threading.active_count(),
            )
        except Exception as e:
            logger.error("Error taking system snapshot", error=str(e))
            return SystemSnapshot(
                timestamp=time.time(),
                cpu_percent=0,
                memory_percent=0,
                memory_available_mb=0,
                disk_io_read_mb=0,
                disk_io_write_mb=0,
                network_sent_mb=0,
                network_recv_mb=0,
                process_count=0,
                thread_count=0,
            )

    async def profile_complete_operation(
        self, operation: Callable, operation_name: str, *args, **kwargs
    ) -> Tuple[Any, ProfileResult]:
        """
        Profile a complete operation with detailed analysis.

        Args:
            operation: Async operation to profile
            operation_name: Name for the operation
            *args, **kwargs: Arguments for the operation

        Returns:
            Tuple of (operation_result, profile_result)
        """
        # Clear previous profiling data
        self.profile_points.clear()
        self.system_snapshots.clear()

        # Start monitoring
        await self.start_continuous_monitoring()

        start_time = time.perf_counter()

        try:
            # Execute operation with profiling
            async with self.profile_operation(operation_name):
                result = await operation(*args, **kwargs)

            end_time = time.perf_counter()
            execution_time_ms = (end_time - start_time) * 1000

            # Stop monitoring
            await self.stop_continuous_monitoring()

            # Analyze results
            bottlenecks = self._analyze_bottlenecks()
            performance_summary = self._generate_performance_summary()
            recommendations = self._generate_optimization_recommendations(bottlenecks)

            profile_result = ProfileResult(
                execution_time_ms=execution_time_ms,
                profile_points=self.profile_points.copy(),
                system_snapshots=self.system_snapshots.copy(),
                bottlenecks=bottlenecks,
                performance_summary=performance_summary,
                optimization_recommendations=recommendations,
            )

            logger.info(
                "Operation profiling completed",
                operation=operation_name,
                execution_time_ms=execution_time_ms,
                bottlenecks_found=len(bottlenecks),
            )

            return result, profile_result

        except Exception as e:
            await self.stop_continuous_monitoring()
            logger.error("Error during profiling", error=str(e))
            raise

    def _analyze_bottlenecks(self) -> List[BottleneckAnalysis]:
        """Analyze profiling data to identify bottlenecks."""
        bottlenecks = []

        # Analyze CPU bottlenecks
        cpu_bottlenecks = self._analyze_cpu_bottlenecks()
        bottlenecks.extend(cpu_bottlenecks)

        # Analyze memory bottlenecks
        memory_bottlenecks = self._analyze_memory_bottlenecks()
        bottlenecks.extend(memory_bottlenecks)

        # Analyze operation latency bottlenecks
        latency_bottlenecks = self._analyze_latency_bottlenecks()
        bottlenecks.extend(latency_bottlenecks)

        # Analyze I/O bottlenecks
        io_bottlenecks = self._analyze_io_bottlenecks()
        bottlenecks.extend(io_bottlenecks)

        # Sort by severity and impact
        bottlenecks.sort(
            key=lambda x: (
                {"critical": 4, "high": 3, "medium": 2, "low": 1}[x.severity],
                x.impact_percentage,
            ),
            reverse=True,
        )

        return bottlenecks

    def _analyze_cpu_bottlenecks(self) -> List[BottleneckAnalysis]:
        """Analyze CPU usage patterns for bottlenecks."""
        bottlenecks = []

        if not self.system_snapshots:
            return bottlenecks

        cpu_values = [s.cpu_percent for s in self.system_snapshots]
        avg_cpu = sum(cpu_values) / len(cpu_values)
        max_cpu = max(cpu_values)

        if avg_cpu > self.thresholds["cpu_percent"]:
            severity = (
                "critical" if avg_cpu > 95 else "high" if avg_cpu > 85 else "medium"
            )

            bottlenecks.append(
                BottleneckAnalysis(
                    component="CPU",
                    severity=severity,
                    impact_percentage=avg_cpu,
                    description=f"High CPU utilization averaging {avg_cpu:.1f}%",
                    recommendations=[
                        "Consider optimizing CPU-intensive operations",
                        "Implement asynchronous processing where possible",
                        "Review algorithm efficiency",
                        "Scale horizontally if sustained high load",
                    ],
                    metrics={"avg_cpu": avg_cpu, "max_cpu": max_cpu},
                )
            )

        return bottlenecks

    def _analyze_memory_bottlenecks(self) -> List[BottleneckAnalysis]:
        """Analyze memory usage patterns for bottlenecks."""
        bottlenecks = []

        if not self.system_snapshots:
            return bottlenecks

        memory_values = [s.memory_percent for s in self.system_snapshots]
        avg_memory = sum(memory_values) / len(memory_values)
        max_memory = max(memory_values)

        if avg_memory > self.thresholds["memory_percent"]:
            severity = (
                "critical"
                if avg_memory > 95
                else "high" if avg_memory > 90 else "medium"
            )

            bottlenecks.append(
                BottleneckAnalysis(
                    component="Memory",
                    severity=severity,
                    impact_percentage=avg_memory,
                    description=f"High memory utilization averaging {avg_memory:.1f}%",
                    recommendations=[
                        "Review cache size configuration",
                        "Implement memory-efficient data structures",
                        "Consider garbage collection tuning",
                        "Monitor for memory leaks",
                    ],
                    metrics={"avg_memory": avg_memory, "max_memory": max_memory},
                )
            )

        return bottlenecks

    def _analyze_latency_bottlenecks(self) -> List[BottleneckAnalysis]:
        """Analyze operation latency for bottlenecks."""
        bottlenecks = []

        if not self.profile_points:
            return bottlenecks

        # Group by operation type
        operation_groups = {}
        for point in self.profile_points:
            op_type = point.name
            if op_type not in operation_groups:
                operation_groups[op_type] = []
            operation_groups[op_type].append(point.duration_ms)

        for op_type, durations in operation_groups.items():
            avg_duration = sum(durations) / len(durations)
            max_duration = max(durations)

            # Check against thresholds
            threshold = self.thresholds.get(
                f"{op_type.lower()}_latency_ms", self.thresholds["response_time_ms"]
            )

            if avg_duration > threshold:
                severity = "critical" if avg_duration > threshold * 2 else "high"
                impact = min(100, (avg_duration / threshold - 1) * 100)

                bottlenecks.append(
                    BottleneckAnalysis(
                        component=f"{op_type} Latency",
                        severity=severity,
                        impact_percentage=impact,
                        description=f"{op_type} operations averaging {avg_duration:.1f}ms (threshold: {threshold}ms)",
                        recommendations=[
                            f"Optimize {op_type.lower()} operations",
                            "Review database query efficiency",
                            "Consider caching frequently accessed data",
                            "Implement connection pooling",
                        ],
                        metrics={
                            "avg_duration": avg_duration,
                            "max_duration": max_duration,
                            "threshold": threshold,
                        },
                    )
                )

        return bottlenecks

    def _analyze_io_bottlenecks(self) -> List[BottleneckAnalysis]:
        """Analyze I/O patterns for bottlenecks."""
        bottlenecks = []

        if len(self.system_snapshots) < 2:
            return bottlenecks

        # Calculate I/O rates
        first_snapshot = self.system_snapshots[0]
        last_snapshot = self.system_snapshots[-1]
        time_diff = last_snapshot.timestamp - first_snapshot.timestamp

        if time_diff <= 0:
            return bottlenecks

        disk_read_rate = (
            last_snapshot.disk_io_read_mb - first_snapshot.disk_io_read_mb
        ) / time_diff
        disk_write_rate = (
            last_snapshot.disk_io_write_mb - first_snapshot.disk_io_write_mb
        ) / time_diff

        # High disk I/O threshold (MB/s)
        high_io_threshold = 50.0

        if disk_read_rate > high_io_threshold:
            bottlenecks.append(
                BottleneckAnalysis(
                    component="Disk I/O Read",
                    severity="medium",
                    impact_percentage=min(
                        100, disk_read_rate / high_io_threshold * 100
                    ),
                    description=f"High disk read rate: {disk_read_rate:.1f} MB/s",
                    recommendations=[
                        "Consider SSD storage for better performance",
                        "Implement read caching",
                        "Optimize database queries to reduce disk reads",
                        "Review file access patterns",
                    ],
                    metrics={"read_rate_mbs": disk_read_rate},
                )
            )

        if disk_write_rate > high_io_threshold:
            bottlenecks.append(
                BottleneckAnalysis(
                    component="Disk I/O Write",
                    severity="medium",
                    impact_percentage=min(
                        100, disk_write_rate / high_io_threshold * 100
                    ),
                    description=f"High disk write rate: {disk_write_rate:.1f} MB/s",
                    recommendations=[
                        "Implement write batching",
                        "Consider asynchronous writes",
                        "Review logging levels and output",
                        "Optimize cache write-back policies",
                    ],
                    metrics={"write_rate_mbs": disk_write_rate},
                )
            )

        return bottlenecks

    def _generate_performance_summary(self) -> Dict[str, Any]:
        """Generate performance summary from profiling data."""
        summary = {}

        # Operation performance
        if self.profile_points:
            durations = [p.duration_ms for p in self.profile_points]
            summary["operations"] = {
                "total_operations": len(self.profile_points),
                "avg_duration_ms": sum(durations) / len(durations),
                "min_duration_ms": min(durations),
                "max_duration_ms": max(durations),
                "total_duration_ms": sum(durations),
            }

        # Resource utilization
        if self.system_snapshots:
            cpu_values = [s.cpu_percent for s in self.system_snapshots]
            memory_values = [s.memory_percent for s in self.system_snapshots]

            summary["resources"] = {
                "avg_cpu_percent": sum(cpu_values) / len(cpu_values),
                "max_cpu_percent": max(cpu_values),
                "avg_memory_percent": sum(memory_values) / len(memory_values),
                "max_memory_percent": max(memory_values),
                "monitoring_duration_seconds": self.system_snapshots[-1].timestamp
                - self.system_snapshots[0].timestamp,
            }

        return summary

    def _generate_optimization_recommendations(
        self, bottlenecks: List[BottleneckAnalysis]
    ) -> List[str]:
        """Generate optimization recommendations based on bottlenecks."""
        recommendations = []

        # High-priority recommendations based on critical bottlenecks
        critical_bottlenecks = [b for b in bottlenecks if b.severity == "critical"]
        if critical_bottlenecks:
            recommendations.append(
                "Address critical performance bottlenecks immediately"
            )
            for bottleneck in critical_bottlenecks:
                recommendations.extend(
                    bottleneck.recommendations[:2]
                )  # Top 2 recommendations

        # General optimization recommendations
        recommendations.extend(
            [
                "Implement comprehensive monitoring and alerting",
                "Consider performance testing under various load conditions",
                "Review and optimize database queries and indexes",
                "Implement efficient caching strategies",
                "Consider horizontal scaling for high-load scenarios",
            ]
        )

        # Remove duplicates while preserving order
        seen = set()
        unique_recommendations = []
        for rec in recommendations:
            if rec not in seen:
                seen.add(rec)
                unique_recommendations.append(rec)

        return unique_recommendations[:10]  # Return top 10 recommendations


class BottleneckAnalyzer:
    """
    Specialized analyzer for identifying and categorizing bottlenecks.

    Provides advanced analysis of system bottlenecks with actionable
    optimization recommendations.
    """

    def __init__(self):
        """Initialize bottleneck analyzer."""
        self.analysis_history: List[BottleneckAnalysis] = []
        logger.info("Bottleneck analyzer initialized")

    def analyze_cache_performance(
        self, cache_manager: CacheManager
    ) -> List[BottleneckAnalysis]:
        """Analyze cache performance for bottlenecks."""
        bottlenecks = []

        try:
            metrics = cache_manager.get_metrics()

            # Cache hit rate analysis
            if metrics.hit_rate < 60.0:  # Below target
                severity = "high" if metrics.hit_rate < 40 else "medium"

                bottlenecks.append(
                    BottleneckAnalysis(
                        component="Cache Hit Rate",
                        severity=severity,
                        impact_percentage=100 - metrics.hit_rate,
                        description=f"Cache hit rate {metrics.hit_rate:.1f}% below optimal",
                        recommendations=[
                            "Review cache warming strategies",
                            "Increase cache size if memory allows",
                            "Optimize cache eviction policies",
                            "Analyze query patterns for better caching",
                        ],
                        metrics={"hit_rate": metrics.hit_rate, "target": 60.0},
                    )
                )

            # Cache memory utilization
            if metrics.total_size > cache_manager.max_size_bytes * 0.9:
                bottlenecks.append(
                    BottleneckAnalysis(
                        component="Cache Memory",
                        severity="medium",
                        impact_percentage=90.0,
                        description="Cache approaching memory limit",
                        recommendations=[
                            "Increase cache size allocation",
                            "Implement more aggressive eviction",
                            "Review cached content for optimization",
                            "Consider distributed caching",
                        ],
                        metrics={
                            "utilization": metrics.total_size
                            / cache_manager.max_size_bytes
                        },
                    )
                )

        except Exception as e:
            logger.error("Error analyzing cache performance", error=str(e))

        return bottlenecks

    def analyze_query_patterns(
        self, recent_queries: List[str]
    ) -> List[BottleneckAnalysis]:
        """Analyze query patterns for potential bottlenecks."""
        bottlenecks = []

        if not recent_queries:
            return bottlenecks

        # Analyze query complexity
        complex_queries = [q for q in recent_queries if len(q) > 200]
        if len(complex_queries) > len(recent_queries) * 0.3:  # >30% complex queries
            bottlenecks.append(
                BottleneckAnalysis(
                    component="Query Complexity",
                    severity="medium",
                    impact_percentage=len(complex_queries) / len(recent_queries) * 100,
                    description=f"{len(complex_queries)} of {len(recent_queries)} queries are complex",
                    recommendations=[
                        "Break down complex queries into simpler components",
                        "Implement query preprocessing and optimization",
                        "Consider query result caching",
                        "Review query construction patterns",
                    ],
                    metrics={
                        "complex_ratio": len(complex_queries) / len(recent_queries)
                    },
                )
            )

        return bottlenecks

    def generate_bottleneck_report(
        self, bottlenecks: List[BottleneckAnalysis]
    ) -> Dict[str, Any]:
        """Generate comprehensive bottleneck analysis report."""
        if not bottlenecks:
            return {
                "summary": "No significant bottlenecks detected",
                "total_bottlenecks": 0,
                "severity_breakdown": {},
                "recommendations": ["Continue monitoring for performance trends"],
            }

        # Severity breakdown
        severity_counts = {}
        for bottleneck in bottlenecks:
            severity_counts[bottleneck.severity] = (
                severity_counts.get(bottleneck.severity, 0) + 1
            )

        # Top recommendations
        all_recommendations = []
        for bottleneck in bottlenecks:
            all_recommendations.extend(bottleneck.recommendations)

        # Remove duplicates and prioritize
        unique_recommendations = list(dict.fromkeys(all_recommendations))

        report = {
            "timestamp": time.time(),
            "summary": f"Identified {len(bottlenecks)} performance bottlenecks",
            "total_bottlenecks": len(bottlenecks),
            "severity_breakdown": severity_counts,
            "critical_components": [
                b.component for b in bottlenecks if b.severity == "critical"
            ],
            "high_impact_components": [
                b.component for b in bottlenecks if b.impact_percentage > 70
            ],
            "recommendations": unique_recommendations[:10],
            "detailed_analysis": [
                {
                    "component": b.component,
                    "severity": b.severity,
                    "impact": b.impact_percentage,
                    "description": b.description,
                    "top_recommendations": b.recommendations[:3],
                }
                for b in bottlenecks
            ],
        }

        return report
