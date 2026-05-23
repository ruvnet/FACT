"""
FACT Performance Optimizer

Real-time performance monitoring and optimization system that automatically
adjusts cache strategies, warming schedules, and system parameters to meet
performance targets.
"""

import time
import asyncio
import threading
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import structlog

try:
    from ..cache.manager import CacheManager, get_cache_manager
    from ..cache.warming import CacheWarmer, get_cache_warmer
    from ..cache.metrics import MetricsCollector, get_metrics_collector
    from ..benchmarking.framework import BenchmarkFramework, BenchmarkConfig
except ImportError:
    import sys
    from pathlib import Path

    src_path = str(Path(__file__).parent.parent)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    from cache.manager import CacheManager, get_cache_manager
    from cache.warming import CacheWarmer, get_cache_warmer
    from cache.metrics import MetricsCollector, get_metrics_collector
    from benchmarking.framework import BenchmarkFramework, BenchmarkConfig

logger = structlog.get_logger(__name__)


class OptimizationStrategy(Enum):
    """Performance optimization strategies."""

    AGGRESSIVE_WARMING = "aggressive_warming"
    CONSERVATIVE_MEMORY = "conservative_memory"
    BALANCED = "balanced"
    LATENCY_FOCUSED = "latency_focused"
    COST_FOCUSED = "cost_focused"


@dataclass
class PerformanceTarget:
    """Performance targets and thresholds."""

    cache_hit_latency_ms: float = 48.0
    cache_miss_latency_ms: float = 140.0
    cache_hit_rate_percent: float = 60.0
    cost_reduction_percent: float = 90.0
    memory_utilization_max: float = 85.0
    error_rate_max: float = 2.0


@dataclass
class OptimizationAction:
    """Represents an optimization action to be taken."""

    action_type: str
    parameters: Dict[str, Any]
    priority: int
    estimated_impact: float
    execution_time: float = field(default_factory=time.time)


class PerformanceOptimizer:
    """
    Real-time performance optimizer for the FACT system.

    Monitors system performance and automatically applies optimizations
    to meet performance targets.
    """

    def __init__(
        self,
        cache_manager: Optional[CacheManager] = None,
        targets: Optional[PerformanceTarget] = None,
    ):
        """
        Initialize performance optimizer.

        Args:
            cache_manager: Cache manager instance
            targets: Performance targets
        """
        self.cache_manager = cache_manager or get_cache_manager()
        self.cache_warmer = get_cache_warmer(self.cache_manager)
        self.metrics_collector = get_metrics_collector()
        self.benchmark_framework = BenchmarkFramework()

        self.targets = targets or PerformanceTarget()
        self.strategy = OptimizationStrategy.BALANCED

        # Optimization state
        self.optimization_enabled = True
        self.optimization_interval = 300  # 5 minutes
        self.last_optimization = 0.0
        self.optimization_history: List[OptimizationAction] = []

        # Performance tracking
        self.performance_windows = {
            "short": [],  # Last 10 measurements
            "medium": [],  # Last 50 measurements
            "long": [],  # Last 200 measurements
        }

        # Optimization thresholds
        self.thresholds = {
            "hit_rate_critical": 40.0,
            "latency_critical": 200.0,
            "memory_critical": 95.0,
            "cost_efficiency_critical": 50.0,
        }

        # Thread safety
        self._lock = threading.RLock()
        self._optimization_task: Optional[asyncio.Task] = None

        logger.info(
            "Performance optimizer initialized",
            strategy=self.strategy.value,
            targets=self.targets,
        )

    async def start_optimization_loop(self):
        """Start the continuous optimization loop."""
        if self._optimization_task and not self._optimization_task.done():
            logger.warning("Optimization loop already running")
            return

        self._optimization_task = asyncio.create_task(self._optimization_loop())
        logger.info("Performance optimization loop started")

    async def stop_optimization_loop(self):
        """Stop the continuous optimization loop."""
        if self._optimization_task:
            self._optimization_task.cancel()
            try:
                await self._optimization_task
            except asyncio.CancelledError:
                pass
            self._optimization_task = None

        logger.info("Performance optimization loop stopped")

    async def _optimization_loop(self):
        """Main optimization loop."""
        while True:
            try:
                await asyncio.sleep(self.optimization_interval)

                if self.optimization_enabled:
                    await self.optimize_performance()

            except asyncio.CancelledError:
                logger.info("Optimization loop cancelled")
                break
            except Exception as e:
                logger.error("Optimization loop error", error=str(e))
                await asyncio.sleep(30)  # Brief pause before retry

    async def optimize_performance(self) -> List[OptimizationAction]:
        """
        Analyze current performance and apply optimizations.

        Returns:
            List of optimization actions taken
        """
        try:
            with self._lock:
                logger.info("Starting performance optimization cycle")

                # Collect current metrics
                current_metrics = self._collect_performance_metrics()

                # Update performance windows
                self._update_performance_windows(current_metrics)

                # Analyze performance issues
                issues = self._analyze_performance_issues(current_metrics)

                # Generate optimization actions
                actions = self._generate_optimization_actions(issues, current_metrics)

                # Execute high-priority actions
                executed_actions = []
                for action in sorted(actions, key=lambda x: x.priority, reverse=True):
                    if await self._execute_optimization_action(action):
                        executed_actions.append(action)
                        self.optimization_history.append(action)

                # Log optimization results
                self._log_optimization_results(executed_actions, current_metrics)

                self.last_optimization = time.time()

                return executed_actions

        except Exception as e:
            logger.error("Performance optimization failed", error=str(e))
            return []

    def _collect_performance_metrics(self) -> Dict[str, Any]:
        """Collect comprehensive performance metrics."""
        try:
            # Cache metrics
            cache_metrics = self.cache_manager.get_metrics()
            cache_perf_stats = self.cache_manager.get_performance_stats()

            # Cache health
            health_metrics = self.metrics_collector.get_cache_health_score(
                self.cache_manager
            )

            # Optimization metrics
            opt_metrics = self.metrics_collector.track_optimization_metrics(
                self.cache_manager
            )

            # System metrics
            current_time = time.time()
            memory_utilization = (
                cache_metrics.total_size / self.cache_manager.max_size_bytes * 100
            )

            return {
                "timestamp": current_time,
                "cache_metrics": cache_metrics,
                "performance_stats": cache_perf_stats,
                "health_metrics": health_metrics,
                "optimization_metrics": opt_metrics,
                "memory_utilization": memory_utilization,
                "hit_rate_percent": cache_metrics.hit_rate,
                "avg_hit_latency_ms": cache_perf_stats.get("avg_hit_latency_ms", 0),
                "avg_miss_latency_ms": cache_perf_stats.get("avg_miss_latency_ms", 0),
            }

        except Exception as e:
            logger.error("Failed to collect performance metrics", error=str(e))
            return {"timestamp": time.time(), "error": str(e)}

    def _update_performance_windows(self, metrics: Dict[str, Any]):
        """Update rolling performance windows."""
        try:
            # Add to all windows
            for window_name, window in self.performance_windows.items():
                window.append(metrics)

            # Trim windows to size
            if len(self.performance_windows["short"]) > 10:
                self.performance_windows["short"].pop(0)
            if len(self.performance_windows["medium"]) > 50:
                self.performance_windows["medium"].pop(0)
            if len(self.performance_windows["long"]) > 200:
                self.performance_windows["long"].pop(0)

        except Exception as e:
            logger.debug("Failed to update performance windows", error=str(e))

    def _analyze_performance_issues(self, current_metrics: Dict[str, Any]) -> List[str]:
        """Analyze current performance and identify issues."""
        issues = []

        try:
            # Cache hit rate analysis
            hit_rate = current_metrics.get("hit_rate_percent", 0)
            if hit_rate < self.targets.cache_hit_rate_percent:
                severity = (
                    "critical"
                    if hit_rate < self.thresholds["hit_rate_critical"]
                    else "moderate"
                )
                issues.append(f"low_hit_rate_{severity}")

            # Latency analysis
            hit_latency = current_metrics.get("avg_hit_latency_ms", 0)
            miss_latency = current_metrics.get("avg_miss_latency_ms", 0)

            if hit_latency > self.targets.cache_hit_latency_ms:
                issues.append("high_hit_latency")
            if miss_latency > self.targets.cache_miss_latency_ms:
                issues.append("high_miss_latency")

            # Memory utilization
            memory_util = current_metrics.get("memory_utilization", 0)
            if memory_util > self.targets.memory_utilization_max:
                severity = (
                    "critical"
                    if memory_util > self.thresholds["memory_critical"]
                    else "moderate"
                )
                issues.append(f"high_memory_usage_{severity}")

            # Cost efficiency
            opt_metrics = current_metrics.get("optimization_metrics", {})
            warming_efficiency = opt_metrics.get("cache_warming_efficiency", 0)
            if warming_efficiency < 50:
                issues.append("low_warming_efficiency")

            # Trend analysis
            if len(self.performance_windows["medium"]) >= 10:
                recent_hit_rates = [
                    m.get("hit_rate_percent", 0)
                    for m in self.performance_windows["medium"][-10:]
                ]
                if len(recent_hit_rates) >= 5:
                    trend = (recent_hit_rates[-1] - recent_hit_rates[0]) / len(
                        recent_hit_rates
                    )
                    if trend < -2:  # Declining hit rate
                        issues.append("declining_hit_rate")

        except Exception as e:
            logger.error("Performance analysis failed", error=str(e))
            issues.append("analysis_error")

        return issues

    def _generate_optimization_actions(
        self, issues: List[str], metrics: Dict[str, Any]
    ) -> List[OptimizationAction]:
        """Generate optimization actions based on identified issues."""
        actions = []

        try:
            # Cache warming optimizations
            if "low_hit_rate_critical" in issues or "declining_hit_rate" in issues:
                actions.append(
                    OptimizationAction(
                        action_type="aggressive_cache_warming",
                        parameters={"max_queries": 50, "concurrent": True},
                        priority=9,
                        estimated_impact=15.0,
                    )
                )
            elif "low_hit_rate_moderate" in issues:
                actions.append(
                    OptimizationAction(
                        action_type="moderate_cache_warming",
                        parameters={"max_queries": 30, "concurrent": True},
                        priority=7,
                        estimated_impact=10.0,
                    )
                )

            # Memory optimization
            if "high_memory_usage_critical" in issues:
                actions.append(
                    OptimizationAction(
                        action_type="emergency_memory_cleanup",
                        parameters={"target_utilization": 70.0},
                        priority=10,
                        estimated_impact=20.0,
                    )
                )
            elif "high_memory_usage_moderate" in issues:
                actions.append(
                    OptimizationAction(
                        action_type="preemptive_cleanup",
                        parameters={"target_utilization": 80.0},
                        priority=6,
                        estimated_impact=8.0,
                    )
                )

            # Latency optimizations
            if "high_hit_latency" in issues:
                actions.append(
                    OptimizationAction(
                        action_type="optimize_cache_access",
                        parameters={"enable_fast_lookup": True},
                        priority=8,
                        estimated_impact=12.0,
                    )
                )

            # Warming efficiency improvements
            if "low_warming_efficiency" in issues:
                actions.append(
                    OptimizationAction(
                        action_type="optimize_warming_strategy",
                        parameters={"strategy": "intelligent_prioritization"},
                        priority=5,
                        estimated_impact=7.0,
                    )
                )

            # Strategy adjustments
            current_hit_rate = metrics.get("hit_rate_percent", 0)
            if (
                current_hit_rate < 40
                and self.strategy != OptimizationStrategy.AGGRESSIVE_WARMING
            ):
                actions.append(
                    OptimizationAction(
                        action_type="change_strategy",
                        parameters={
                            "new_strategy": OptimizationStrategy.AGGRESSIVE_WARMING.value
                        },
                        priority=4,
                        estimated_impact=5.0,
                    )
                )

        except Exception as e:
            logger.error("Failed to generate optimization actions", error=str(e))

        return actions

    async def _execute_optimization_action(self, action: OptimizationAction) -> bool:
        """Execute a specific optimization action."""
        try:
            logger.info(
                "Executing optimization action",
                action_type=action.action_type,
                priority=action.priority,
                parameters=action.parameters,
            )

            if action.action_type == "aggressive_cache_warming":
                await self.cache_warmer.warm_cache_intelligently(
                    max_queries=action.parameters.get("max_queries", 50)
                )
                return True

            elif action.action_type == "moderate_cache_warming":
                await self.cache_warmer.warm_cache_intelligently(
                    max_queries=action.parameters.get("max_queries", 30)
                )
                return True

            elif action.action_type == "emergency_memory_cleanup":
                target_util = action.parameters.get("target_utilization", 70.0)
                current_size = self.cache_manager._calculate_current_size()
                target_size = int(self.cache_manager.max_size_bytes * target_util / 100)

                if current_size > target_size:
                    space_to_free = current_size - target_size
                    self.cache_manager._intelligent_eviction(space_to_free)
                return True

            elif action.action_type == "preemptive_cleanup":
                self.cache_manager._maybe_preemptive_cleanup()
                return True

            elif action.action_type == "optimize_cache_access":
                # Enable performance optimizations
                self.cache_manager.optimization_enabled = True
                self.cache_manager.fast_lookup_enabled = action.parameters.get(
                    "enable_fast_lookup", True
                )
                return True

            elif action.action_type == "optimize_warming_strategy":
                # Update warming strategy
                strategy = action.parameters.get(
                    "strategy", "intelligent_prioritization"
                )
                self.cache_warmer.optimization_config["adaptive_priorities"] = True
                self.cache_warmer.optimization_config["concurrent_warming"] = True
                return True

            elif action.action_type == "change_strategy":
                new_strategy = action.parameters.get("new_strategy")
                if new_strategy:
                    self.strategy = OptimizationStrategy(new_strategy)
                    logger.info("Strategy changed", new_strategy=new_strategy)
                return True

            else:
                logger.warning(
                    "Unknown optimization action", action_type=action.action_type
                )
                return False

        except Exception as e:
            logger.error(
                "Failed to execute optimization action",
                action_type=action.action_type,
                error=str(e),
            )
            return False

    def _log_optimization_results(
        self, actions: List[OptimizationAction], metrics: Dict[str, Any]
    ):
        """Log optimization results and impact."""
        try:
            if actions:
                action_types = [a.action_type for a in actions]
                total_impact = sum(a.estimated_impact for a in actions)

                logger.info(
                    "Optimization cycle completed",
                    actions_taken=len(actions),
                    action_types=action_types,
                    estimated_total_impact=total_impact,
                    current_hit_rate=metrics.get("hit_rate_percent", 0),
                    memory_utilization=metrics.get("memory_utilization", 0),
                )
            else:
                logger.info(
                    "Optimization cycle completed - no actions needed",
                    current_hit_rate=metrics.get("hit_rate_percent", 0),
                    memory_utilization=metrics.get("memory_utilization", 0),
                )

        except Exception as e:
            logger.debug("Failed to log optimization results", error=str(e))

    def get_optimization_status(self) -> Dict[str, Any]:
        """Get current optimization status and statistics."""
        try:
            recent_actions = (
                self.optimization_history[-10:] if self.optimization_history else []
            )

            return {
                "optimization_enabled": self.optimization_enabled,
                "current_strategy": self.strategy.value,
                "last_optimization": self.last_optimization,
                "optimization_interval": self.optimization_interval,
                "total_optimizations": len(self.optimization_history),
                "recent_actions": [
                    {
                        "action_type": a.action_type,
                        "execution_time": a.execution_time,
                        "estimated_impact": a.estimated_impact,
                    }
                    for a in recent_actions
                ],
                "performance_targets": {
                    "cache_hit_latency_ms": self.targets.cache_hit_latency_ms,
                    "cache_miss_latency_ms": self.targets.cache_miss_latency_ms,
                    "cache_hit_rate_percent": self.targets.cache_hit_rate_percent,
                    "cost_reduction_percent": self.targets.cost_reduction_percent,
                },
            }

        except Exception as e:
            logger.error("Failed to get optimization status", error=str(e))
            return {"error": str(e)}


# Global optimizer instance
_performance_optimizer: Optional[PerformanceOptimizer] = None


def get_performance_optimizer(
    cache_manager: Optional[CacheManager] = None,
) -> PerformanceOptimizer:
    """Get or create global performance optimizer instance."""
    global _performance_optimizer

    if _performance_optimizer is None:
        _performance_optimizer = PerformanceOptimizer(cache_manager)

    return _performance_optimizer


async def start_performance_optimization(cache_manager: Optional[CacheManager] = None):
    """Start performance optimization with automatic monitoring."""
    optimizer = get_performance_optimizer(cache_manager)
    await optimizer.start_optimization_loop()
    logger.info("Performance optimization started")


async def stop_performance_optimization():
    """Stop performance optimization."""
    optimizer = get_performance_optimizer()
    await optimizer.stop_optimization_loop()
    logger.info("Performance optimization stopped")
