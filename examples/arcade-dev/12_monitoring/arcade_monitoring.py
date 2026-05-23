#!/usr/bin/env python3
"""
Arcade.dev Monitoring and Observability Example

This example demonstrates comprehensive monitoring for Arcade.dev integration,
including performance tracking, error rate monitoring, health checks,
alert mechanisms, and telemetry integration.
"""

import os
import sys
import asyncio
import logging
import time
import psutil
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from collections import defaultdict, deque
import json
import threading
import statistics

# Setup FACT imports using the import helper
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.import_helper import setup_fact_imports

# Setup FACT module path
setup_fact_imports()

from src.monitoring.metrics import MetricsCollector, ToolExecutionMetric, SystemMetrics
from src.monitoring.performance_optimizer import PerformanceOptimizer
from src.core.driver import FACTDriver
from src.cache.manager import CacheManager


@dataclass
class MonitoringConfig:
    """Configuration for monitoring and observability."""

    # Performance monitoring
    enable_performance_tracking: bool = True
    enable_health_checks: bool = True
    enable_alerting: bool = True
    enable_telemetry: bool = True

    # Health check intervals
    health_check_interval_seconds: int = 30
    performance_check_interval_seconds: int = 60

    # Alert thresholds
    error_rate_threshold: float = 0.05  # 5%
    response_time_threshold_ms: float = 5000  # 5 seconds
    cpu_usage_threshold: float = 80.0  # 80%
    memory_usage_threshold: float = 85.0  # 85%

    # Metrics retention
    metrics_retention_hours: int = 24
    detailed_metrics_retention_minutes: int = 60

    # Logging
    metrics_log_file: str = "arcade_metrics.log"
    alerts_log_file: str = "arcade_alerts.log"


@dataclass
class HealthCheckResult:
    """Result of a health check."""

    service: str
    status: str  # healthy, degraded, unhealthy
    response_time_ms: float
    timestamp: datetime
    details: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None


@dataclass
class PerformanceMetric:
    """Performance metric data point."""

    metric_name: str
    value: float
    timestamp: datetime
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class Alert:
    """Alert notification."""

    alert_id: str
    severity: str  # info, warning, critical
    title: str
    message: str
    timestamp: datetime
    service: str
    metric_name: Optional[str] = None
    current_value: Optional[float] = None
    threshold: Optional[float] = None
    resolved: bool = False


class SystemMonitor:
    """Monitors system resources and performance."""

    def __init__(self, config: MonitoringConfig):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.SystemMonitor")

    def get_system_metrics(self) -> Dict[str, float]:
        """Get current system resource metrics."""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")

            # Network I/O
            net_io = psutil.net_io_counters()

            return {
                "cpu_usage_percent": cpu_percent,
                "memory_usage_percent": memory.percent,
                "memory_available_mb": memory.available / (1024 * 1024),
                "disk_usage_percent": disk.percent,
                "network_bytes_sent": net_io.bytes_sent,
                "network_bytes_recv": net_io.bytes_recv,
                "load_average": (
                    os.getloadavg()[0] if hasattr(os, "getloadavg") else 0.0
                ),
            }
        except Exception as e:
            self.logger.error(f"Failed to collect system metrics: {e}")
            return {}

    def check_system_health(self) -> HealthCheckResult:
        """Perform system health check."""
        start_time = time.time()

        try:
            metrics = self.get_system_metrics()
            response_time = (time.time() - start_time) * 1000

            # Determine health status
            status = "healthy"
            issues = []

            if metrics.get("cpu_usage_percent", 0) > self.config.cpu_usage_threshold:
                status = "degraded"
                issues.append(f"High CPU usage: {metrics['cpu_usage_percent']:.1f}%")

            if (
                metrics.get("memory_usage_percent", 0)
                > self.config.memory_usage_threshold
            ):
                status = "degraded"
                issues.append(
                    f"High memory usage: {metrics['memory_usage_percent']:.1f}%"
                )

            if metrics.get("disk_usage_percent", 0) > 90:
                status = "unhealthy"
                issues.append(
                    f"Critical disk usage: {metrics['disk_usage_percent']:.1f}%"
                )

            return HealthCheckResult(
                service="system",
                status=status,
                response_time_ms=response_time,
                timestamp=datetime.now(timezone.utc),
                details={"metrics": metrics, "issues": issues},
            )

        except Exception as e:
            return HealthCheckResult(
                service="system",
                status="unhealthy",
                response_time_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(timezone.utc),
                error_message=str(e),
            )


class ArcadeAPIMonitor:
    """Monitors Arcade.dev API performance and health."""

    def __init__(self, config: MonitoringConfig):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.ArcadeAPIMonitor")
        self.api_key = os.getenv("ARCADE_API_KEY")
        self.demo_mode = (
            self.api_key is None or self.api_key == "" or self.api_key == "demo_key"
        )

        if self.demo_mode:
            self.logger.info("Running in demo mode - API calls will be simulated")
        else:
            self.logger.info("Running with real API credentials")

    async def check_api_health(self) -> HealthCheckResult:
        """Check Arcade.dev API health."""
        start_time = time.time()

        try:
            if self.demo_mode:
                # Demo mode: simulate API health check
                await asyncio.sleep(0.1)  # Simulate network call
                response_time = (time.time() - start_time) * 1000

                # Mock API response analysis
                status = "healthy"
                if response_time > self.config.response_time_threshold_ms:
                    status = "degraded"

                return HealthCheckResult(
                    service="arcade_api",
                    status=status,
                    response_time_ms=response_time,
                    timestamp=datetime.now(timezone.utc),
                    details={
                        "endpoint": "https://api.arcade.dev/health (simulated)",
                        "api_version": "v1",
                        "demo_mode": True,
                        "response_time_threshold_ms": self.config.response_time_threshold_ms,
                    },
                )
            else:
                # Real API mode: would make actual API call here
                # For now, simulate since we don't have real API implementation
                await asyncio.sleep(0.1)  # Simulate network call
                response_time = (time.time() - start_time) * 1000

                status = "healthy"
                if response_time > self.config.response_time_threshold_ms:
                    status = "degraded"

                return HealthCheckResult(
                    service="arcade_api",
                    status=status,
                    response_time_ms=response_time,
                    timestamp=datetime.now(timezone.utc),
                    details={
                        "endpoint": "https://api.arcade.dev/health",
                        "api_version": "v1",
                        "demo_mode": False,
                        "response_time_threshold_ms": self.config.response_time_threshold_ms,
                    },
                )

        except Exception as e:
            return HealthCheckResult(
                service="arcade_api",
                status="unhealthy",
                response_time_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(timezone.utc),
                error_message=str(e),
            )

    async def test_api_operations(self) -> Dict[str, HealthCheckResult]:
        """Test various API operations for monitoring."""
        operations = {
            "code_analysis": self._test_code_analysis,
            "test_generation": self._test_generation,
            "documentation": self._test_documentation,
        }

        results = {}
        for operation_name, test_func in operations.items():
            try:
                result = await test_func()
                results[operation_name] = result
            except Exception as e:
                results[operation_name] = HealthCheckResult(
                    service=f"arcade_api_{operation_name}",
                    status="unhealthy",
                    response_time_ms=0,
                    timestamp=datetime.now(timezone.utc),
                    error_message=str(e),
                )

        return results

    async def _test_code_analysis(self) -> HealthCheckResult:
        """Test code analysis endpoint."""
        start_time = time.time()

        # Simulate API call (demo or real mode)
        await asyncio.sleep(0.2)

        response_time = (time.time() - start_time) * 1000

        return HealthCheckResult(
            service="arcade_api_code_analysis",
            status="healthy" if response_time < 1000 else "degraded",
            response_time_ms=response_time,
            timestamp=datetime.now(timezone.utc),
            details={"test_code_lines": 10, "demo_mode": self.demo_mode},
        )

    async def _test_generation(self) -> HealthCheckResult:
        """Test test generation endpoint."""
        start_time = time.time()

        # Simulate API call (demo or real mode)
        await asyncio.sleep(0.3)

        response_time = (time.time() - start_time) * 1000

        return HealthCheckResult(
            service="arcade_api_test_generation",
            status="healthy" if response_time < 1500 else "degraded",
            response_time_ms=response_time,
            timestamp=datetime.now(timezone.utc),
            details={"generated_tests": 5, "demo_mode": self.demo_mode},
        )

    async def _test_documentation(self) -> HealthCheckResult:
        """Test documentation endpoint."""
        start_time = time.time()

        # Simulate API call (demo or real mode)
        await asyncio.sleep(0.15)

        response_time = (time.time() - start_time) * 1000

        return HealthCheckResult(
            service="arcade_api_documentation",
            status="healthy" if response_time < 800 else "degraded",
            response_time_ms=response_time,
            timestamp=datetime.now(timezone.utc),
            details={"doc_sections": 4, "demo_mode": self.demo_mode},
        )


class AlertManager:
    """Manages alerts and notifications."""

    def __init__(self, config: MonitoringConfig):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.AlertManager")
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self.alert_callbacks: List[Callable[[Alert], None]] = []
        self.suppressed_alerts: Dict[str, datetime] = (
            {}
        )  # Track alerts to prevent duplicates

    def register_alert_callback(self, callback: Callable[[Alert], None]):
        """Register a callback for alert notifications."""
        self.alert_callbacks.append(callback)

    def create_alert(
        self,
        severity: str,
        title: str,
        message: str,
        service: str,
        metric_name: str = None,
        current_value: float = None,
        threshold: float = None,
    ) -> Optional[Alert]:
        """Create a new alert, with duplicate suppression."""
        # Create unique key for this type of alert
        alert_key = (
            f"{service}_{metric_name}_{title}" if metric_name else f"{service}_{title}"
        )

        # Check if we've recently created this type of alert (suppress duplicates for 5 minutes)
        now = datetime.now(timezone.utc)
        if alert_key in self.suppressed_alerts:
            time_since_last = now - self.suppressed_alerts[alert_key]
            if time_since_last < timedelta(minutes=5):
                return None  # Suppress duplicate alert

        # Update suppression tracker
        self.suppressed_alerts[alert_key] = now

        alert_id = (
            f"{service}_{metric_name}_{int(time.time())}"
            if metric_name
            else f"{service}_{int(time.time())}"
        )

        alert = Alert(
            alert_id=alert_id,
            severity=severity,
            title=title,
            message=message,
            timestamp=now,
            service=service,
            metric_name=metric_name,
            current_value=current_value,
            threshold=threshold,
        )

        self.active_alerts[alert_id] = alert
        self.alert_history.append(alert)

        # Trigger callbacks
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                self.logger.error(f"Alert callback failed: {e}")

        self.logger.warning(f"Alert created: {alert.title} - {alert.message}")
        return alert

    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an active alert."""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.resolved = True
            del self.active_alerts[alert_id]

            self.logger.info(f"Alert resolved: {alert.title}")
            return True

        return False

    def check_metric_thresholds(self, metrics: Dict[str, float], service: str):
        """Check metrics against thresholds and create alerts if needed."""
        if not self.config.enable_alerting:
            return

        # CPU usage alert
        cpu_usage = metrics.get("cpu_usage_percent", 0)
        if cpu_usage > self.config.cpu_usage_threshold:
            self.create_alert(
                severity="warning",
                title="High CPU Usage",
                message=f"CPU usage is {cpu_usage:.1f}%, above threshold of {self.config.cpu_usage_threshold}%",
                service=service,
                metric_name="cpu_usage_percent",
                current_value=cpu_usage,
                threshold=self.config.cpu_usage_threshold,
            )

        # Memory usage alert
        memory_usage = metrics.get("memory_usage_percent", 0)
        if memory_usage > self.config.memory_usage_threshold:
            self.create_alert(
                severity="warning",
                title="High Memory Usage",
                message=f"Memory usage is {memory_usage:.1f}%, above threshold of {self.config.memory_usage_threshold}%",
                service=service,
                metric_name="memory_usage_percent",
                current_value=memory_usage,
                threshold=self.config.memory_usage_threshold,
            )

    def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts."""
        return list(self.active_alerts.values())

    def get_alert_summary(self) -> Dict[str, Any]:
        """Get alert summary statistics."""
        now = datetime.now(timezone.utc)
        last_hour = now - timedelta(hours=1)
        last_day = now - timedelta(days=1)

        recent_alerts = [a for a in self.alert_history if a.timestamp > last_hour]
        daily_alerts = [a for a in self.alert_history if a.timestamp > last_day]

        return {
            "active_alerts": len(self.active_alerts),
            "alerts_last_hour": len(recent_alerts),
            "alerts_last_day": len(daily_alerts),
            "total_alerts": len(self.alert_history),
            "severity_breakdown": {
                "critical": len([a for a in recent_alerts if a.severity == "critical"]),
                "warning": len([a for a in recent_alerts if a.severity == "warning"]),
                "info": len([a for a in recent_alerts if a.severity == "info"]),
            },
        }


class TelemetryCollector:
    """Collects and exports telemetry data."""

    def __init__(self, config: MonitoringConfig):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.TelemetryCollector")
        self.metrics_buffer: List[PerformanceMetric] = []
        self.buffer_lock = threading.Lock()

    def record_metric(
        self, metric_name: str, value: float, tags: Dict[str, str] = None
    ):
        """Record a performance metric."""
        if not self.config.enable_telemetry:
            return

        metric = PerformanceMetric(
            metric_name=metric_name,
            value=value,
            timestamp=datetime.now(timezone.utc),
            tags=tags or {},
        )

        with self.buffer_lock:
            self.metrics_buffer.append(metric)

            # Keep buffer size manageable
            if len(self.metrics_buffer) > 1000:
                self.metrics_buffer = self.metrics_buffer[-500:]

    def get_metrics(
        self, metric_name: str = None, last_minutes: int = 10
    ) -> List[PerformanceMetric]:
        """Get metrics from buffer."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=last_minutes)

        with self.buffer_lock:
            filtered_metrics = [
                m
                for m in self.metrics_buffer
                if m.timestamp > cutoff_time
                and (metric_name is None or m.metric_name == metric_name)
            ]

        return filtered_metrics

    def export_metrics(self, format_type: str = "json") -> str:
        """Export metrics in specified format."""
        with self.buffer_lock:
            metrics_data = [
                {
                    "metric_name": m.metric_name,
                    "value": m.value,
                    "timestamp": m.timestamp.isoformat(),
                    "tags": m.tags,
                }
                for m in self.metrics_buffer
            ]

        if format_type == "json":
            return json.dumps(metrics_data, indent=2)
        else:
            return str(metrics_data)


class ArcadeMonitoringDashboard:
    """Main monitoring dashboard orchestrating all monitoring components."""

    def __init__(self, config: MonitoringConfig = None):
        self.config = config or MonitoringConfig()
        self.logger = logging.getLogger(__name__)

        # Initialize components
        self.system_monitor = SystemMonitor(self.config)
        self.api_monitor = ArcadeAPIMonitor(self.config)
        self.alert_manager = AlertManager(self.config)
        self.telemetry = TelemetryCollector(self.config)
        self.metrics_collector = MetricsCollector()

        # Register alert callback
        self.alert_manager.register_alert_callback(self._handle_alert)

        # Monitoring state
        self.monitoring_active = False
        self.monitoring_task: Optional[asyncio.Task] = None

    def _handle_alert(self, alert: Alert):
        """Handle alert notifications."""
        # Log alert
        alert_data = {
            "alert_id": alert.alert_id,
            "severity": alert.severity,
            "title": alert.title,
            "message": alert.message,
            "service": alert.service,
            "timestamp": alert.timestamp.isoformat(),
        }

        # Write to alerts log
        alerts_log = Path(self.config.alerts_log_file)
        alerts_log.parent.mkdir(exist_ok=True)

        with open(alerts_log, "a") as f:
            f.write(json.dumps(alert_data) + "\n")

        # In production, send to notification system (email, Slack, etc.)
        print(f"🚨 ALERT [{alert.severity.upper()}]: {alert.title}")
        print(f"   Service: {alert.service}")
        print(f"   Message: {alert.message}")

    async def start_monitoring(self):
        """Start continuous monitoring."""
        if self.monitoring_active:
            self.logger.warning("Monitoring already active")
            return

        self.monitoring_active = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        self.logger.info("Monitoring started")

    async def stop_monitoring(self):
        """Stop monitoring."""
        self.monitoring_active = False

        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass

        self.logger.info("Monitoring stopped")

    async def _monitoring_loop(self):
        """Main monitoring loop."""
        while self.monitoring_active:
            try:
                # System health check
                system_health = self.system_monitor.check_system_health()
                self.telemetry.record_metric(
                    "system_health_response_time_ms",
                    system_health.response_time_ms,
                    {"service": "system", "status": system_health.status},
                )

                # Check system metrics against thresholds
                if system_health.details and "metrics" in system_health.details:
                    self.alert_manager.check_metric_thresholds(
                        system_health.details["metrics"], "system"
                    )

                # API health checks
                api_health = await self.api_monitor.check_api_health()
                self.telemetry.record_metric(
                    "api_health_response_time_ms",
                    api_health.response_time_ms,
                    {"service": "arcade_api", "status": api_health.status},
                )

                # Test API operations
                operation_results = await self.api_monitor.test_api_operations()
                for operation, result in operation_results.items():
                    self.telemetry.record_metric(
                        f"api_operation_response_time_ms",
                        result.response_time_ms,
                        {"operation": operation, "status": result.status},
                    )

                    # Check for slow operations
                    if result.response_time_ms > self.config.response_time_threshold_ms:
                        self.alert_manager.create_alert(
                            severity="warning",
                            title=f"Slow API Operation: {operation}",
                            message=f"Operation took {result.response_time_ms:.1f}ms, above threshold",
                            service="arcade_api",
                            metric_name="response_time_ms",
                            current_value=result.response_time_ms,
                            threshold=self.config.response_time_threshold_ms,
                        )

                await asyncio.sleep(self.config.health_check_interval_seconds)

            except Exception as e:
                self.logger.error(f"Monitoring loop error: {e}")
                await asyncio.sleep(5)  # Wait before retrying

    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get comprehensive dashboard data."""
        # System metrics
        system_metrics = self.system_monitor.get_system_metrics()

        # Recent performance metrics
        recent_metrics = {
            "system_response_times": [
                m.value
                for m in self.telemetry.get_metrics(
                    "system_health_response_time_ms", 10
                )
            ],
            "api_response_times": [
                m.value
                for m in self.telemetry.get_metrics("api_health_response_time_ms", 10)
            ],
        }

        # Calculate averages
        if recent_metrics["system_response_times"]:
            recent_metrics["avg_system_response_time"] = statistics.mean(
                recent_metrics["system_response_times"]
            )
        else:
            recent_metrics["avg_system_response_time"] = 0

        if recent_metrics["api_response_times"]:
            recent_metrics["avg_api_response_time"] = statistics.mean(
                recent_metrics["api_response_times"]
            )
        else:
            recent_metrics["avg_api_response_time"] = 0

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "monitoring_active": self.monitoring_active,
            "system_metrics": system_metrics,
            "performance_metrics": recent_metrics,
            "alerts": self.alert_manager.get_alert_summary(),
            "active_alerts": [
                {
                    "id": alert.alert_id,
                    "severity": alert.severity,
                    "title": alert.title,
                    "service": alert.service,
                    "timestamp": alert.timestamp.isoformat(),
                }
                for alert in self.alert_manager.get_active_alerts()
            ],
        }

    def print_dashboard(self):
        """Print monitoring dashboard to console."""
        dashboard_data = self.get_dashboard_data()

        print("\n" + "=" * 60)
        print("🖥️  ARCADE.DEV MONITORING DASHBOARD")
        print("=" * 60)

        # Demo mode indicator
        if hasattr(self, "api_monitor") and self.api_monitor.demo_mode:
            print("🔧 Running in DEMO MODE (simulated API calls)")

        # System Status
        print(f"\n📊 System Metrics:")
        system_metrics = dashboard_data["system_metrics"]
        if system_metrics:
            print(f"   CPU Usage: {system_metrics.get('cpu_usage_percent', 0):.1f}%")
            print(
                f"   Memory Usage: {system_metrics.get('memory_usage_percent', 0):.1f}%"
            )
            print(f"   Disk Usage: {system_metrics.get('disk_usage_percent', 0):.1f}%")
            print(f"   Load Average: {system_metrics.get('load_average', 0):.2f}")

        # Performance
        print(f"\n⚡ Performance:")
        perf_metrics = dashboard_data["performance_metrics"]
        print(
            f"   Avg System Response: {perf_metrics['avg_system_response_time']:.1f}ms"
        )
        print(f"   Avg API Response: {perf_metrics['avg_api_response_time']:.1f}ms")

        # Alerts
        print(f"\n🚨 Alerts:")
        alert_summary = dashboard_data["alerts"]
        print(f"   Active: {alert_summary['active_alerts']}")
        print(f"   Last Hour: {alert_summary['alerts_last_hour']}")
        print(f"   Last Day: {alert_summary['alerts_last_day']}")

        # Active Alerts
        active_alerts = dashboard_data["active_alerts"]
        if active_alerts:
            print(f"\n⚠️  Active Alerts:")
            for alert in active_alerts[:5]:  # Show first 5
                print(
                    f"   [{alert['severity'].upper()}] {alert['title']} ({alert['service']})"
                )

        print("\n" + "=" * 60)


async def demonstrate_monitoring():
    """Demonstrate monitoring capabilities."""
    print("📊 Arcade.dev Monitoring Demo")
    print("=" * 50)

    try:
        # Create monitoring dashboard
        config = MonitoringConfig(
            health_check_interval_seconds=5,  # Faster for demo
            cpu_usage_threshold=50.0,  # Lower threshold for demo alerts
            memory_usage_threshold=60.0,
        )

        dashboard = ArcadeMonitoringDashboard(config)

        # Check demo mode status
        demo_status = (
            "🔧 DEMO MODE" if dashboard.api_monitor.demo_mode else "🌐 LIVE MODE"
        )
        print(f"\nMode: {demo_status}")
        print(
            f"API Key Available: {'❌ No' if dashboard.api_monitor.demo_mode else '✅ Yes'}"
        )

        print("\n🚀 Starting monitoring...")
        await dashboard.start_monitoring()

        # Let it run for a bit and collect data
        print("⏳ Collecting metrics for 30 seconds...")

        for i in range(6):  # 6 iterations of 5 seconds each
            await asyncio.sleep(5)
            dashboard.print_dashboard()

            # Simulate some load to trigger alerts
            if i == 2:
                print("\n🔥 Simulating high load...")
                # This would trigger alerts in a real scenario

        print("\n🛑 Stopping monitoring...")
        await dashboard.stop_monitoring()

        # Final summary
        print("\n📋 Final Monitoring Summary:")
        dashboard.print_dashboard()

        # Export metrics for review
        metrics_export = dashboard.telemetry.export_metrics()
        print(
            f"\n📄 Exported {len(dashboard.telemetry.metrics_buffer)} metrics to JSON"
        )

        print("\n🎉 Monitoring demonstration completed!")
        return dashboard

    except Exception as e:
        print(f"\n❌ Error during monitoring demo: {e}")
        raise


async def main():
    """Main demonstration function."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    try:
        await demonstrate_monitoring()
        return 0
    except KeyboardInterrupt:
        print("\n👋 Monitoring demo interrupted by user")
        return 0
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
