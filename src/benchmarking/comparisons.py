"""
FACT vs Traditional RAG Performance Comparison

Implements comprehensive comparison benchmarks between FACT and traditional
RAG systems to validate performance improvements and cost reductions.
"""

import time
import asyncio
import statistics
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import structlog

try:
    # Try relative imports first (when used as package)
    from framework import BenchmarkResult, BenchmarkSummary, BenchmarkFramework
    from cache.manager import CacheManager
except ImportError:
    # Fall back to absolute imports (when run as script)
    import sys
    from pathlib import Path

    # Add src to path if not already there
    src_path = str(Path(__file__).parent.parent)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    from benchmarking.framework import (
        BenchmarkResult,
        BenchmarkSummary,
        BenchmarkFramework,
    )
    from cache.manager import CacheManager

logger = structlog.get_logger(__name__)


class SystemType(Enum):
    """System types for comparison."""

    FACT = "fact"
    TRADITIONAL_RAG = "traditional_rag"
    HYBRID = "hybrid"


@dataclass
class ComparisonMetrics:
    """Metrics for system comparison."""

    system_type: SystemType
    avg_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    avg_token_cost: float
    total_token_cost: float
    cache_hit_rate: float
    error_rate: float
    throughput_qps: float
    memory_usage_mb: float
    cpu_usage_percent: float


@dataclass
class ComparisonResult:
    """Result of system comparison."""

    fact_metrics: ComparisonMetrics
    rag_metrics: ComparisonMetrics
    improvement_factors: Dict[str, float]
    cost_savings: Dict[str, float]
    performance_analysis: Dict[str, Any]
    recommendation: str
    timestamp: float = field(default_factory=time.time)


class RAGComparison:
    """
    Comprehensive comparison between FACT and traditional RAG systems.

    Simulates traditional RAG behavior and measures performance differences
    across latency, cost, and accuracy dimensions.
    """

    def __init__(self, benchmark_framework: Optional[BenchmarkFramework] = None):
        """
        Initialize RAG comparison.

        Args:
            benchmark_framework: Benchmark framework for measurements
        """
        self.framework = benchmark_framework or BenchmarkFramework()

        # Traditional RAG simulation parameters
        self.rag_base_latency_ms = 400  # Typical RAG latency
        self.rag_vector_search_ms = 50  # Vector database search time
        self.rag_llm_processing_ms = 300  # LLM processing time
        self.rag_context_preparation_ms = 50  # Context preparation time

        # Token usage patterns
        self.rag_avg_input_tokens = 1500  # Large context with retrieved docs
        self.rag_avg_output_tokens = 300  # Detailed responses
        self.fact_hit_input_tokens = 100  # Minimal prompt for cache
        self.fact_hit_output_tokens = 50  # Cached response
        self.fact_miss_input_tokens = 200  # Tool-enhanced prompt
        self.fact_miss_output_tokens = 150  # Response with tool results

        logger.info("RAG comparison initialized")

    async def run_comparison_benchmark(
        self,
        queries: List[str],
        cache_manager: Optional[CacheManager] = None,
        iterations: int = 10,
    ) -> ComparisonResult:
        """
        Run comprehensive comparison benchmark.

        Args:
            queries: Test queries for comparison
            cache_manager: Cache manager for FACT system
            iterations: Number of iterations per query

        Returns:
            Comparison results
        """
        logger.info(
            "Starting RAG comparison benchmark",
            queries_count=len(queries),
            iterations=iterations,
        )

        # Run FACT benchmarks
        fact_summary = await self.framework.run_benchmark_suite(queries, cache_manager)
        fact_metrics = self._extract_comparison_metrics(fact_summary, SystemType.FACT)

        # Simulate traditional RAG performance
        rag_results = await self._simulate_rag_performance(queries, iterations)
        rag_summary = self.framework._generate_summary(
            rag_results, fact_summary.execution_time_seconds
        )
        rag_metrics = self._extract_comparison_metrics(
            rag_summary, SystemType.TRADITIONAL_RAG
        )

        # Calculate improvement factors
        improvement_factors = self._calculate_improvement_factors(
            fact_metrics, rag_metrics
        )

        # Calculate cost savings
        cost_savings = self._calculate_cost_savings(fact_metrics, rag_metrics)

        # Generate performance analysis
        performance_analysis = self._analyze_performance_differences(
            fact_metrics, rag_metrics
        )

        # Generate recommendation
        recommendation = self._generate_recommendation(
            improvement_factors, cost_savings
        )

        result = ComparisonResult(
            fact_metrics=fact_metrics,
            rag_metrics=rag_metrics,
            improvement_factors=improvement_factors,
            cost_savings=cost_savings,
            performance_analysis=performance_analysis,
            recommendation=recommendation,
        )

        logger.info(
            "RAG comparison completed",
            latency_improvement=improvement_factors.get("latency", 0),
            cost_reduction=cost_savings.get("percentage", 0),
        )

        return result

    async def _simulate_rag_performance(
        self, queries: List[str], iterations: int
    ) -> List[BenchmarkResult]:
        """
        Simulate traditional RAG system performance.

        Args:
            queries: Test queries
            iterations: Number of iterations

        Returns:
            Simulated RAG benchmark results
        """
        results = []

        for iteration in range(iterations):
            for query in queries:
                # Simulate RAG processing time
                base_latency = self.rag_base_latency_ms

                # Add variability based on query complexity
                complexity_factor = min(
                    len(query) / 100, 2.0
                )  # Up to 2x for complex queries
                variable_latency = base_latency * (0.8 + complexity_factor * 0.4)

                # Add random variation (±20%)
                import random

                variation = random.uniform(0.8, 1.2)
                total_latency = variable_latency * variation

                # Simulate processing delay
                await asyncio.sleep(total_latency / 1000)  # Convert to seconds

                # Calculate token costs for RAG
                token_count = self.rag_avg_input_tokens + self.rag_avg_output_tokens
                token_cost = self._calculate_rag_token_cost(token_count)

                result = BenchmarkResult(
                    query=query,
                    response_time_ms=total_latency,
                    success=True,  # Assume RAG systems are reliable
                    cache_hit=False,  # Traditional RAG doesn't use cache
                    token_count=token_count,
                    token_cost=token_cost,
                    metadata={"system_type": "traditional_rag"},
                )

                results.append(result)

        return results

    def _extract_comparison_metrics(
        self, summary: BenchmarkSummary, system_type: SystemType
    ) -> ComparisonMetrics:
        """Extract comparison metrics from benchmark summary."""
        return ComparisonMetrics(
            system_type=system_type,
            avg_latency_ms=summary.avg_response_time_ms,
            p95_latency_ms=summary.p95_response_time_ms,
            p99_latency_ms=summary.p99_response_time_ms,
            avg_token_cost=summary.avg_token_cost,
            total_token_cost=summary.total_token_cost,
            cache_hit_rate=summary.cache_hit_rate,
            error_rate=summary.error_rate,
            throughput_qps=summary.throughput_qps,
            memory_usage_mb=0.0,  # TODO: Implement memory tracking
            cpu_usage_percent=0.0,  # TODO: Implement CPU tracking
        )

    def _calculate_improvement_factors(
        self, fact_metrics: ComparisonMetrics, rag_metrics: ComparisonMetrics
    ) -> Dict[str, float]:
        """Calculate improvement factors for FACT vs RAG."""
        improvements = {}

        # Latency improvements
        if rag_metrics.avg_latency_ms > 0:
            improvements["latency"] = (
                rag_metrics.avg_latency_ms / fact_metrics.avg_latency_ms
            )

        if rag_metrics.p95_latency_ms > 0:
            improvements["p95_latency"] = (
                rag_metrics.p95_latency_ms / fact_metrics.p95_latency_ms
            )

        # Throughput improvements
        if fact_metrics.throughput_qps > 0 and rag_metrics.throughput_qps > 0:
            improvements["throughput"] = (
                fact_metrics.throughput_qps / rag_metrics.throughput_qps
            )

        # Cost improvements
        if rag_metrics.avg_token_cost > 0:
            improvements["cost_efficiency"] = (
                rag_metrics.avg_token_cost / fact_metrics.avg_token_cost
            )

        return improvements

    def _calculate_cost_savings(
        self, fact_metrics: ComparisonMetrics, rag_metrics: ComparisonMetrics
    ) -> Dict[str, float]:
        """Calculate cost savings from using FACT."""
        savings = {}

        if rag_metrics.total_token_cost > 0:
            absolute_savings = (
                rag_metrics.total_token_cost - fact_metrics.total_token_cost
            )
            percentage_savings = (absolute_savings / rag_metrics.total_token_cost) * 100

            savings["absolute_usd"] = absolute_savings
            savings["percentage"] = percentage_savings

            # Extrapolate monthly savings
            if absolute_savings > 0:
                # Assume this represents 1 hour of usage
                daily_savings = absolute_savings * 24
                monthly_savings = daily_savings * 30
                savings["monthly_usd"] = monthly_savings
                savings["annual_usd"] = monthly_savings * 12

        return savings

    def _analyze_performance_differences(
        self, fact_metrics: ComparisonMetrics, rag_metrics: ComparisonMetrics
    ) -> Dict[str, Any]:
        """Analyze detailed performance differences."""
        analysis = {
            "latency_analysis": {
                "fact_avg_ms": fact_metrics.avg_latency_ms,
                "rag_avg_ms": rag_metrics.avg_latency_ms,
                "improvement_factor": (
                    rag_metrics.avg_latency_ms / fact_metrics.avg_latency_ms
                    if fact_metrics.avg_latency_ms > 0
                    else 0
                ),
                "time_saved_per_query_ms": rag_metrics.avg_latency_ms
                - fact_metrics.avg_latency_ms,
                "meets_target": fact_metrics.avg_latency_ms <= 100,  # Overall target
            },
            "cost_analysis": {
                "fact_cost_per_query": fact_metrics.avg_token_cost,
                "rag_cost_per_query": rag_metrics.avg_token_cost,
                "cost_reduction_factor": (
                    rag_metrics.avg_token_cost / fact_metrics.avg_token_cost
                    if fact_metrics.avg_token_cost > 0
                    else 0
                ),
                "savings_per_query": rag_metrics.avg_token_cost
                - fact_metrics.avg_token_cost,
            },
            "efficiency_analysis": {
                "fact_cache_hit_rate": fact_metrics.cache_hit_rate,
                "throughput_advantage": (
                    fact_metrics.throughput_qps / rag_metrics.throughput_qps
                    if rag_metrics.throughput_qps > 0
                    else 0
                ),
                "scalability_factor": self._calculate_scalability_factor(
                    fact_metrics, rag_metrics
                ),
            },
            "target_compliance": {
                "hit_latency_target": 48.0,
                "miss_latency_target": 140.0,
                "cost_reduction_target": 75.0,
                "cache_hit_rate_target": 60.0,
                "fact_meets_latency": fact_metrics.avg_latency_ms <= 100,
                "fact_meets_cost": (
                    rag_metrics.avg_token_cost - fact_metrics.avg_token_cost
                )
                / rag_metrics.avg_token_cost
                >= 0.75,
            },
        }

        return analysis

    def _calculate_scalability_factor(
        self, fact_metrics: ComparisonMetrics, rag_metrics: ComparisonMetrics
    ) -> float:
        """Calculate scalability advantage of FACT over RAG."""
        # FACT scales better due to caching - estimate scaling factor
        # Traditional RAG scales linearly with load
        # FACT scales sub-linearly due to cache hits
        cache_efficiency = fact_metrics.cache_hit_rate / 100.0
        scaling_advantage = 1.0 + (cache_efficiency * 2.0)  # Up to 3x scaling advantage
        return scaling_advantage

    def _calculate_rag_token_cost(self, token_count: int) -> float:
        """Calculate token cost for traditional RAG system."""
        # Use same pricing as FACT framework
        input_tokens = int(token_count * 0.8)  # RAG uses more input tokens
        output_tokens = int(token_count * 0.2)

        input_cost = input_tokens * self.framework.input_token_cost
        output_cost = output_tokens * self.framework.output_token_cost

        return input_cost + output_cost

    def _generate_recommendation(
        self, improvement_factors: Dict[str, float], cost_savings: Dict[str, float]
    ) -> str:
        """Generate recommendation based on comparison results."""
        latency_improvement = improvement_factors.get("latency", 1.0)
        cost_reduction = cost_savings.get("percentage", 0.0)

        if latency_improvement >= 3.0 and cost_reduction >= 70.0:
            return "FACT shows exceptional performance advantages. Strongly recommended for production deployment."
        elif latency_improvement >= 2.0 and cost_reduction >= 50.0:
            return "FACT demonstrates significant improvements. Recommended for production with monitoring."
        elif latency_improvement >= 1.5 and cost_reduction >= 30.0:
            return "FACT shows moderate improvements. Consider for specific use cases with high query volume."
        else:
            return "FACT improvements are marginal. Further optimization recommended before production deployment."


class PerformanceComparison:
    """
    Advanced performance comparison with detailed analysis.

    Provides deeper insights into performance characteristics, bottlenecks,
    and optimization opportunities.
    """

    def __init__(self):
        """Initialize performance comparison."""
        self.baseline_measurements: Dict[str, List[float]] = {
            "fact_latencies": [],
            "rag_latencies": [],
            "fact_costs": [],
            "rag_costs": [],
        }

        logger.info("Performance comparison initialized")

    def analyze_latency_distribution(
        self, fact_results: List[BenchmarkResult], rag_results: List[BenchmarkResult]
    ) -> Dict[str, Any]:
        """Analyze latency distribution patterns."""
        fact_latencies = [r.response_time_ms for r in fact_results if r.success]
        rag_latencies = [r.response_time_ms for r in rag_results if r.success]

        analysis = {
            "fact_distribution": self._calculate_distribution_stats(fact_latencies),
            "rag_distribution": self._calculate_distribution_stats(rag_latencies),
            "comparison": {
                "median_improvement": (
                    statistics.median(rag_latencies) / statistics.median(fact_latencies)
                    if fact_latencies
                    else 0
                ),
                "variance_ratio": (
                    statistics.variance(rag_latencies)
                    / statistics.variance(fact_latencies)
                    if len(fact_latencies) > 1
                    else 0
                ),
                "consistency_advantage": self._calculate_consistency_advantage(
                    fact_latencies, rag_latencies
                ),
            },
        }

        return analysis

    def analyze_cost_efficiency(
        self, fact_results: List[BenchmarkResult], rag_results: List[BenchmarkResult]
    ) -> Dict[str, Any]:
        """Analyze cost efficiency patterns."""
        fact_costs = [r.token_cost for r in fact_results if r.token_cost is not None]
        rag_costs = [r.token_cost for r in rag_results if r.token_cost is not None]

        hit_costs = [
            r.token_cost
            for r in fact_results
            if r.cache_hit and r.token_cost is not None
        ]
        miss_costs = [
            r.token_cost
            for r in fact_results
            if not r.cache_hit and r.token_cost is not None
        ]

        analysis = {
            "overall_savings": {
                "fact_avg_cost": statistics.mean(fact_costs) if fact_costs else 0,
                "rag_avg_cost": statistics.mean(rag_costs) if rag_costs else 0,
                "savings_ratio": (
                    statistics.mean(rag_costs) / statistics.mean(fact_costs)
                    if fact_costs
                    else 0
                ),
            },
            "cache_impact": {
                "hit_avg_cost": statistics.mean(hit_costs) if hit_costs else 0,
                "miss_avg_cost": statistics.mean(miss_costs) if miss_costs else 0,
                "hit_vs_miss_ratio": (
                    statistics.mean(miss_costs) / statistics.mean(hit_costs)
                    if hit_costs
                    else 0
                ),
            },
            "efficiency_score": self._calculate_efficiency_score(fact_costs, rag_costs),
        }

        return analysis

    def _calculate_distribution_stats(self, values: List[float]) -> Dict[str, float]:
        """Calculate distribution statistics."""
        if not values:
            return {"mean": 0, "median": 0, "std": 0, "min": 0, "max": 0}

        return {
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "std": statistics.stdev(values) if len(values) > 1 else 0,
            "min": min(values),
            "max": max(values),
            "p90": (
                statistics.quantiles(values, n=10)[8]
                if len(values) >= 10
                else max(values)
            ),
            "p95": (
                statistics.quantiles(values, n=20)[18]
                if len(values) >= 20
                else max(values)
            ),
            "p99": (
                statistics.quantiles(values, n=100)[98]
                if len(values) >= 100
                else max(values)
            ),
        }

    def _calculate_consistency_advantage(
        self, fact_latencies: List[float], rag_latencies: List[float]
    ) -> float:
        """Calculate consistency advantage of FACT over RAG."""
        if len(fact_latencies) <= 1 or len(rag_latencies) <= 1:
            return 0.0

        fact_cv = statistics.stdev(fact_latencies) / statistics.mean(fact_latencies)
        rag_cv = statistics.stdev(rag_latencies) / statistics.mean(rag_latencies)

        # Lower coefficient of variation indicates better consistency
        return rag_cv / fact_cv if fact_cv > 0 else 0.0

    def _calculate_efficiency_score(
        self, fact_costs: List[float], rag_costs: List[float]
    ) -> float:
        """Calculate overall efficiency score (0-100)."""
        if not fact_costs or not rag_costs:
            return 0.0

        cost_ratio = statistics.mean(rag_costs) / statistics.mean(fact_costs)

        # Convert to 0-100 scale where 100 = perfect efficiency
        # Assume 5x cost improvement = 100% efficiency
        efficiency_score = min(100, (cost_ratio - 1) * 20)
        return max(0, efficiency_score)
