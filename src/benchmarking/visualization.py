"""
FACT Benchmarking Visualization System

Provides comprehensive visualization and reporting tools for benchmark results,
performance analysis, and comparison data.
"""

import json
import time
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import structlog

try:
    # Try relative imports first (when used as package)
    from framework import BenchmarkResult, BenchmarkSummary
    from comparisons import ComparisonResult
    from profiler import ProfileResult, BottleneckAnalysis
    from monitoring import PerformanceAlert, PerformanceTrend
except ImportError:
    # Fall back to absolute imports (when run as script)
    import sys
    from pathlib import Path

    # Add src to path if not already there
    src_path = str(Path(__file__).parent.parent)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    from benchmarking.framework import BenchmarkResult, BenchmarkSummary
    from benchmarking.comparisons import ComparisonResult
    from benchmarking.profiler import ProfileResult, BottleneckAnalysis
    from benchmarking.monitoring import PerformanceAlert, PerformanceTrend

logger = structlog.get_logger(__name__)


@dataclass
class ChartData:
    """Data structure for chart generation."""

    chart_type: str  # "line", "bar", "scatter", "histogram"
    title: str
    x_label: str
    y_label: str
    data_series: List[Dict[str, Any]]
    metadata: Dict[str, Any]


@dataclass
class ReportSection:
    """Individual section of a benchmark report."""

    section_id: str
    title: str
    content_type: str  # "text", "table", "chart", "metrics"
    content: Any
    priority: int = 1  # 1=high, 2=medium, 3=low


@dataclass
class BenchmarkReport:
    """Complete benchmark report structure."""

    report_id: str
    title: str
    generated_at: float
    summary: Dict[str, Any]
    sections: List[ReportSection]
    charts: List[ChartData]
    recommendations: List[str]
    raw_data: Dict[str, Any]


class BenchmarkVisualizer:
    """
    Comprehensive visualization system for benchmark data.

    Generates charts, tables, and visual reports for performance analysis.
    """

    def __init__(self):
        """Initialize benchmark visualizer."""
        self.color_scheme = {
            "fact": "#2E8B57",  # Sea Green
            "rag": "#CD5C5C",  # Indian Red
            "cache_hit": "#32CD32",  # Lime Green
            "cache_miss": "#FF6347",  # Tomato
            "warning": "#FFD700",  # Gold
            "critical": "#DC143C",  # Crimson
            "success": "#228B22",  # Forest Green
            "neutral": "#708090",  # Slate Gray
        }

        logger.info("Benchmark visualizer initialized")

    def create_latency_comparison_chart(
        self, fact_results: List[BenchmarkResult], rag_results: List[BenchmarkResult]
    ) -> ChartData:
        """Create latency comparison chart between FACT and RAG."""
        # Extract latency data
        fact_latencies = [r.response_time_ms for r in fact_results if r.success]
        rag_latencies = [r.response_time_ms for r in rag_results if r.success]

        # Create comparison data
        data_series = [
            {
                "name": "FACT System",
                "data": fact_latencies,
                "color": self.color_scheme["fact"],
                "type": "box_plot",
            },
            {
                "name": "Traditional RAG",
                "data": rag_latencies,
                "color": self.color_scheme["rag"],
                "type": "box_plot",
            },
        ]

        return ChartData(
            chart_type="box_plot",
            title="Response Time Comparison: FACT vs Traditional RAG",
            x_label="System Type",
            y_label="Response Time (ms)",
            data_series=data_series,
            metadata={
                "fact_avg": (
                    sum(fact_latencies) / len(fact_latencies) if fact_latencies else 0
                ),
                "rag_avg": (
                    sum(rag_latencies) / len(rag_latencies) if rag_latencies else 0
                ),
                "improvement_factor": (
                    (sum(rag_latencies) / len(rag_latencies))
                    / (sum(fact_latencies) / len(fact_latencies))
                    if fact_latencies and rag_latencies
                    else 0
                ),
            },
        )

    def create_cache_performance_chart(self, benchmark_summary) -> ChartData:
        """Create cache hit/miss performance visualization."""
        # Handle both BenchmarkSummary and List[BenchmarkResult]
        if hasattr(benchmark_summary, "avg_hit_latency_ms"):
            # BenchmarkSummary object
            hit_latencies = (
                [benchmark_summary.avg_hit_latency_ms]
                if benchmark_summary.cache_hits > 0
                else []
            )
            miss_latencies = (
                [benchmark_summary.avg_miss_latency_ms]
                if benchmark_summary.cache_misses > 0
                else []
            )
        else:
            # List of BenchmarkResult objects
            hit_latencies = [
                r.response_time_ms
                for r in benchmark_summary
                if r.success and r.cache_hit
            ]
            miss_latencies = [
                r.response_time_ms
                for r in benchmark_summary
                if r.success and not r.cache_hit
            ]

        data_series = [
            {
                "name": "Cache Hits",
                "data": hit_latencies,
                "color": self.color_scheme["cache_hit"],
                "type": "histogram",
            },
            {
                "name": "Cache Misses",
                "data": miss_latencies,
                "color": self.color_scheme["cache_miss"],
                "type": "histogram",
            },
        ]

        return ChartData(
            chart_type="histogram",
            title="Response Time Distribution: Cache Hits vs Misses",
            x_label="Response Time (ms)",
            y_label="Frequency",
            data_series=data_series,
            metadata={
                "hit_avg": (
                    sum(hit_latencies) / len(hit_latencies) if hit_latencies else 0
                ),
                "miss_avg": (
                    sum(miss_latencies) / len(miss_latencies) if miss_latencies else 0
                ),
                "hit_count": len(hit_latencies),
                "miss_count": len(miss_latencies),
                "cache_hit_rate": (
                    len(hit_latencies)
                    / (len(hit_latencies) + len(miss_latencies))
                    * 100
                    if (len(hit_latencies) + len(miss_latencies)) > 0
                    else 0
                ),
            },
        )

    def create_performance_timeline_chart(
        self, results: List[BenchmarkResult]
    ) -> ChartData:
        """Create performance over time timeline chart."""
        # Sort results by timestamp
        sorted_results = sorted(results, key=lambda r: r.timestamp)

        # Create time series data
        timestamps = [r.timestamp for r in sorted_results]
        response_times = [r.response_time_ms for r in sorted_results]
        cache_hits = [1 if r.cache_hit else 0 for r in sorted_results]

        data_series = [
            {
                "name": "Response Time",
                "data": list(zip(timestamps, response_times)),
                "color": self.color_scheme["fact"],
                "type": "line",
                "y_axis": "left",
            },
            {
                "name": "Cache Hit Rate",
                "data": list(
                    zip(timestamps, self._calculate_rolling_cache_hit_rate(cache_hits))
                ),
                "color": self.color_scheme["cache_hit"],
                "type": "line",
                "y_axis": "right",
            },
        ]

        return ChartData(
            chart_type="line",
            title="Performance Timeline",
            x_label="Time",
            y_label="Response Time (ms) / Cache Hit Rate (%)",
            data_series=data_series,
            metadata={
                "total_measurements": len(results),
                "time_span_hours": (
                    (max(timestamps) - min(timestamps)) / 3600 if timestamps else 0
                ),
            },
        )

    def create_cost_comparison_chart(
        self, comparison_result: ComparisonResult
    ) -> ChartData:
        """Create cost comparison visualization."""
        fact_cost = comparison_result.fact_metrics.avg_token_cost
        rag_cost = comparison_result.rag_metrics.avg_token_cost

        data_series = [
            {
                "name": "Cost Comparison",
                "data": [
                    {
                        "category": "FACT System",
                        "value": fact_cost,
                        "color": self.color_scheme["fact"],
                    },
                    {
                        "category": "Traditional RAG",
                        "value": rag_cost,
                        "color": self.color_scheme["rag"],
                    },
                ],
                "type": "bar",
            }
        ]

        savings = rag_cost - fact_cost if rag_cost > fact_cost else 0
        savings_percentage = (savings / rag_cost * 100) if rag_cost > 0 else 0

        return ChartData(
            chart_type="bar",
            title="Token Cost Comparison per Query",
            x_label="System Type",
            y_label="Token Cost (USD)",
            data_series=data_series,
            metadata={
                "fact_cost": fact_cost,
                "rag_cost": rag_cost,
                "absolute_savings": savings,
                "percentage_savings": savings_percentage,
            },
        )

    def create_bottleneck_analysis_chart(
        self, bottlenecks: List[BottleneckAnalysis]
    ) -> ChartData:
        """Create bottleneck analysis visualization."""
        if not bottlenecks:
            return ChartData(
                chart_type="bar",
                title="Bottleneck Analysis - No Issues Detected",
                x_label="Components",
                y_label="Impact (%)",
                data_series=[],
                metadata={"status": "healthy"},
            )

        # Sort bottlenecks by impact
        sorted_bottlenecks = sorted(
            bottlenecks, key=lambda b: b.impact_percentage, reverse=True
        )

        # Create severity color mapping
        severity_colors = {
            "critical": self.color_scheme["critical"],
            "high": "#FF8C00",  # Dark Orange
            "medium": self.color_scheme["warning"],
            "low": "#90EE90",  # Light Green
        }

        data_series = [
            {
                "name": "Bottleneck Impact",
                "data": [
                    {
                        "category": b.component,
                        "value": b.impact_percentage,
                        "color": severity_colors.get(
                            b.severity, self.color_scheme["neutral"]
                        ),
                        "severity": b.severity,
                    }
                    for b in sorted_bottlenecks[:10]  # Top 10 bottlenecks
                ],
                "type": "bar",
            }
        ]

        return ChartData(
            chart_type="bar",
            title="Performance Bottleneck Analysis",
            x_label="System Component",
            y_label="Impact Percentage (%)",
            data_series=data_series,
            metadata={
                "total_bottlenecks": len(bottlenecks),
                "critical_count": sum(
                    1 for b in bottlenecks if b.severity == "critical"
                ),
                "high_count": sum(1 for b in bottlenecks if b.severity == "high"),
            },
        )

    def _calculate_rolling_cache_hit_rate(
        self, cache_hits: List[int], window_size: int = 10
    ) -> List[float]:
        """Calculate rolling cache hit rate."""
        rolling_rates = []

        for i in range(len(cache_hits)):
            start_idx = max(0, i - window_size + 1)
            window_data = cache_hits[start_idx : i + 1]
            hit_rate = sum(window_data) / len(window_data) * 100
            rolling_rates.append(hit_rate)

        return rolling_rates

    def export_chart_data_json(self, chart: ChartData) -> str:
        """Export chart data as JSON for external visualization tools."""
        return json.dumps(asdict(chart), indent=2, default=str)


class ReportGenerator:
    """
    Comprehensive report generation system.

    Creates detailed HTML, JSON, and text reports from benchmark data.
    """

    def __init__(self, visualizer: Optional[BenchmarkVisualizer] = None):
        """
        Initialize report generator.

        Args:
            visualizer: Benchmark visualizer instance
        """
        self.visualizer = visualizer or BenchmarkVisualizer()

        logger.info("Report generator initialized")

    def generate_comprehensive_report(
        self,
        benchmark_summary: BenchmarkSummary,
        comparison_result: Optional[ComparisonResult] = None,
        profile_result: Optional[ProfileResult] = None,
        alerts: Optional[List[PerformanceAlert]] = None,
    ) -> BenchmarkReport:
        """
        Generate comprehensive benchmark report.

        Args:
            benchmark_summary: Main benchmark results
            comparison_result: Optional comparison with RAG
            profile_result: Optional profiling results
            alerts: Optional performance alerts

        Returns:
            Complete benchmark report
        """
        report_id = f"fact_benchmark_{int(time.time())}"

        # Generate report sections
        sections = []
        charts = []

        # Executive Summary
        sections.append(
            self._create_executive_summary_section(benchmark_summary, comparison_result)
        )

        # Performance Metrics Section
        sections.append(self._create_performance_metrics_section(benchmark_summary))

        # Target Compliance Section
        sections.append(self._create_target_compliance_section(benchmark_summary))

        # Comparison Analysis (if available)
        if comparison_result:
            sections.append(self._create_comparison_analysis_section(comparison_result))
            charts.append(
                self.visualizer.create_cost_comparison_chart(comparison_result)
            )

        # Bottleneck Analysis (if available)
        if profile_result:
            sections.append(self._create_bottleneck_analysis_section(profile_result))
            charts.append(
                self.visualizer.create_bottleneck_analysis_chart(
                    profile_result.bottlenecks
                )
            )

        # Alerts Section (if available)
        if alerts:
            sections.append(self._create_alerts_section(alerts))

        # Recommendations Section
        sections.append(
            self._create_recommendations_section(
                benchmark_summary, comparison_result, profile_result
            )
        )

        # Generate overall recommendations
        recommendations = self._generate_overall_recommendations(
            benchmark_summary, comparison_result, profile_result, alerts
        )

        # Create summary
        summary = self._create_report_summary(
            benchmark_summary, comparison_result, profile_result
        )

        return BenchmarkReport(
            report_id=report_id,
            title="FACT System Performance Benchmark Report",
            generated_at=time.time(),
            summary=summary,
            sections=sections,
            charts=charts,
            recommendations=recommendations,
            raw_data={
                "benchmark_summary": asdict(benchmark_summary),
                "comparison_result": (
                    asdict(comparison_result) if comparison_result else None
                ),
                "profile_result": asdict(profile_result) if profile_result else None,
                "alerts": [asdict(alert) for alert in alerts] if alerts else None,
            },
        )

    def _create_executive_summary_section(
        self,
        benchmark_summary: BenchmarkSummary,
        comparison_result: Optional[ComparisonResult],
    ) -> ReportSection:
        """Create executive summary section."""
        # Calculate key metrics
        overall_performance = (
            "EXCELLENT"
            if benchmark_summary.avg_response_time_ms < 50
            else (
                "GOOD"
                if benchmark_summary.avg_response_time_ms < 100
                else "NEEDS_IMPROVEMENT"
            )
        )

        cache_performance = (
            "EXCELLENT"
            if benchmark_summary.cache_hit_rate > 70
            else (
                "GOOD" if benchmark_summary.cache_hit_rate > 50 else "NEEDS_IMPROVEMENT"
            )
        )

        content = {
            "overall_assessment": overall_performance,
            "cache_assessment": cache_performance,
            "key_metrics": {
                "avg_response_time_ms": benchmark_summary.avg_response_time_ms,
                "cache_hit_rate": benchmark_summary.cache_hit_rate,
                "error_rate": benchmark_summary.error_rate,
                "throughput_qps": benchmark_summary.throughput_qps,
            },
            "target_compliance": {
                "hit_latency_target_met": benchmark_summary.hit_latency_target_met,
                "miss_latency_target_met": benchmark_summary.miss_latency_target_met,
                "cost_reduction_target_met": benchmark_summary.cost_reduction_target_met,
                "cache_hit_rate_target_met": benchmark_summary.cache_hit_rate_target_met,
            },
        }

        if comparison_result:
            content["improvement_summary"] = {
                "latency_improvement": comparison_result.improvement_factors.get(
                    "latency", 1.0
                ),
                "cost_savings_percentage": comparison_result.cost_savings.get(
                    "percentage", 0.0
                ),
                "recommendation": comparison_result.recommendation,
            }

        return ReportSection(
            section_id="executive_summary",
            title="Executive Summary",
            content_type="metrics",
            content=content,
            priority=1,
        )

    def _create_performance_metrics_section(
        self, benchmark_summary: BenchmarkSummary
    ) -> ReportSection:
        """Create detailed performance metrics section."""
        content = {
            "latency_metrics": {
                "average_ms": benchmark_summary.avg_response_time_ms,
                "minimum_ms": benchmark_summary.min_response_time_ms,
                "maximum_ms": benchmark_summary.max_response_time_ms,
                "p50_ms": benchmark_summary.p50_response_time_ms,
                "p95_ms": benchmark_summary.p95_response_time_ms,
                "p99_ms": benchmark_summary.p99_response_time_ms,
            },
            "cache_metrics": {
                "hit_rate_percent": benchmark_summary.cache_hit_rate,
                "hit_count": benchmark_summary.cache_hits,
                "miss_count": benchmark_summary.cache_misses,
                "avg_hit_latency_ms": benchmark_summary.avg_hit_latency_ms,
                "avg_miss_latency_ms": benchmark_summary.avg_miss_latency_ms,
            },
            "reliability_metrics": {
                "success_rate_percent": (
                    (
                        benchmark_summary.successful_queries
                        / benchmark_summary.total_queries
                        * 100
                    )
                    if benchmark_summary.total_queries > 0
                    else 0
                ),
                "error_rate_percent": benchmark_summary.error_rate,
                "total_queries": benchmark_summary.total_queries,
                "failed_queries": benchmark_summary.failed_queries,
            },
            "cost_metrics": {
                "total_cost_usd": benchmark_summary.total_token_cost,
                "avg_cost_per_query_usd": benchmark_summary.avg_token_cost,
                "estimated_savings_usd": benchmark_summary.estimated_savings,
                "cost_reduction_percentage": benchmark_summary.cost_reduction_percentage,
            },
        }

        return ReportSection(
            section_id="performance_metrics",
            title="Detailed Performance Metrics",
            content_type="table",
            content=content,
            priority=1,
        )

    def _create_target_compliance_section(
        self, benchmark_summary: BenchmarkSummary
    ) -> ReportSection:
        """Create target compliance analysis section."""
        targets = {
            "cache_hit_latency": {
                "target_ms": 48.0,
                "actual_ms": benchmark_summary.avg_hit_latency_ms,
                "met": benchmark_summary.hit_latency_target_met,
                "status": (
                    "PASS" if benchmark_summary.hit_latency_target_met else "FAIL"
                ),
            },
            "cache_miss_latency": {
                "target_ms": 140.0,
                "actual_ms": benchmark_summary.avg_miss_latency_ms,
                "met": benchmark_summary.miss_latency_target_met,
                "status": (
                    "PASS" if benchmark_summary.miss_latency_target_met else "FAIL"
                ),
            },
            "cost_reduction": {
                "target_percent": 75.0,
                "actual_percent": benchmark_summary.cost_reduction_percentage,
                "met": benchmark_summary.cost_reduction_target_met,
                "status": (
                    "PASS" if benchmark_summary.cost_reduction_target_met else "FAIL"
                ),
            },
            "cache_hit_rate": {
                "target_percent": 60.0,
                "actual_percent": benchmark_summary.cache_hit_rate,
                "met": benchmark_summary.cache_hit_rate_target_met,
                "status": (
                    "PASS" if benchmark_summary.cache_hit_rate_target_met else "FAIL"
                ),
            },
        }

        overall_compliance = all(target["met"] for target in targets.values())

        content = {
            "overall_compliance": overall_compliance,
            "overall_status": "PASS" if overall_compliance else "FAIL",
            "target_details": targets,
            "compliance_score": sum(1 for target in targets.values() if target["met"])
            / len(targets)
            * 100,
        }

        return ReportSection(
            section_id="target_compliance",
            title="Performance Target Compliance",
            content_type="table",
            content=content,
            priority=1,
        )

    def _create_comparison_analysis_section(
        self, comparison_result: ComparisonResult
    ) -> ReportSection:
        """Create RAG comparison analysis section."""
        content = {
            "performance_improvements": comparison_result.improvement_factors,
            "cost_savings": comparison_result.cost_savings,
            "fact_metrics": asdict(comparison_result.fact_metrics),
            "rag_metrics": asdict(comparison_result.rag_metrics),
            "detailed_analysis": comparison_result.performance_analysis,
            "recommendation": comparison_result.recommendation,
        }

        return ReportSection(
            section_id="comparison_analysis",
            title="FACT vs Traditional RAG Comparison",
            content_type="table",
            content=content,
            priority=1,
        )

    def _create_bottleneck_analysis_section(
        self, profile_result: ProfileResult
    ) -> ReportSection:
        """Create bottleneck analysis section."""
        critical_bottlenecks = [
            b for b in profile_result.bottlenecks if b.severity == "critical"
        ]
        high_bottlenecks = [
            b for b in profile_result.bottlenecks if b.severity == "high"
        ]

        content = {
            "total_bottlenecks": len(profile_result.bottlenecks),
            "critical_count": len(critical_bottlenecks),
            "high_count": len(high_bottlenecks),
            "bottleneck_details": [asdict(b) for b in profile_result.bottlenecks],
            "performance_summary": profile_result.performance_summary,
            "optimization_recommendations": profile_result.optimization_recommendations,
        }

        return ReportSection(
            section_id="bottleneck_analysis",
            title="Performance Bottleneck Analysis",
            content_type="table",
            content=content,
            priority=2,
        )

    def _create_alerts_section(self, alerts: List[PerformanceAlert]) -> ReportSection:
        """Create performance alerts section."""
        critical_alerts = [a for a in alerts if a.severity == "critical"]
        warning_alerts = [a for a in alerts if a.severity == "warning"]

        content = {
            "total_alerts": len(alerts),
            "critical_count": len(critical_alerts),
            "warning_count": len(warning_alerts),
            "alert_details": [asdict(alert) for alert in alerts],
            "urgent_actions_required": len(critical_alerts) > 0,
        }

        return ReportSection(
            section_id="performance_alerts",
            title="Performance Alerts",
            content_type="table",
            content=content,
            priority=1 if critical_alerts else 2,
        )

    def _create_recommendations_section(
        self,
        benchmark_summary: BenchmarkSummary,
        comparison_result: Optional[ComparisonResult],
        profile_result: Optional[ProfileResult],
    ) -> ReportSection:
        """Create recommendations section."""
        recommendations = []

        # Performance-based recommendations
        if benchmark_summary.avg_response_time_ms > 100:
            recommendations.append(
                "Investigate high response times - consider caching optimization"
            )

        if benchmark_summary.cache_hit_rate < 60:
            recommendations.append(
                "Improve cache hit rate through better warming strategies"
            )

        if benchmark_summary.error_rate > 5:
            recommendations.append(
                "Address system reliability issues - high error rate detected"
            )

        # Comparison-based recommendations
        if (
            comparison_result
            and comparison_result.improvement_factors.get("latency", 1) < 2
        ):
            recommendations.append(
                "Consider additional optimization - latency improvement below target"
            )

        # Bottleneck-based recommendations
        if profile_result:
            recommendations.extend(profile_result.optimization_recommendations[:3])

        content = {
            "priority_recommendations": recommendations[:5],
            "all_recommendations": recommendations,
            "implementation_priority": (
                "HIGH" if benchmark_summary.error_rate > 10 else "MEDIUM"
            ),
        }

        return ReportSection(
            section_id="recommendations",
            title="Optimization Recommendations",
            content_type="text",
            content=content,
            priority=1,
        )

    def _create_report_summary(
        self,
        benchmark_summary: BenchmarkSummary,
        comparison_result: Optional[ComparisonResult],
        profile_result: Optional[ProfileResult],
    ) -> Dict[str, Any]:
        """Create overall report summary."""
        summary = {
            "benchmark_execution": {
                "total_queries": benchmark_summary.total_queries,
                "execution_time_seconds": benchmark_summary.execution_time_seconds,
                "success_rate": (
                    (
                        benchmark_summary.successful_queries
                        / benchmark_summary.total_queries
                        * 100
                    )
                    if benchmark_summary.total_queries > 0
                    else 0
                ),
            },
            "performance_grade": self._calculate_performance_grade(benchmark_summary),
            "key_findings": self._extract_key_findings(
                benchmark_summary, comparison_result, profile_result
            ),
            "action_required": self._determine_action_required(
                benchmark_summary, profile_result
            ),
        }

        return summary

    def _calculate_performance_grade(self, benchmark_summary: BenchmarkSummary) -> str:
        """Calculate overall performance grade."""
        score = 0

        # Latency score (40% weight)
        if benchmark_summary.avg_response_time_ms <= 50:
            score += 40
        elif benchmark_summary.avg_response_time_ms <= 100:
            score += 30
        elif benchmark_summary.avg_response_time_ms <= 150:
            score += 20
        else:
            score += 10

        # Cache hit rate score (30% weight)
        if benchmark_summary.cache_hit_rate >= 70:
            score += 30
        elif benchmark_summary.cache_hit_rate >= 60:
            score += 25
        elif benchmark_summary.cache_hit_rate >= 50:
            score += 20
        else:
            score += 10

        # Error rate score (20% weight)
        if benchmark_summary.error_rate <= 1:
            score += 20
        elif benchmark_summary.error_rate <= 5:
            score += 15
        elif benchmark_summary.error_rate <= 10:
            score += 10
        else:
            score += 5

        # Cost efficiency score (10% weight)
        if benchmark_summary.cost_reduction_percentage >= 80:
            score += 10
        elif benchmark_summary.cost_reduction_percentage >= 60:
            score += 8
        elif benchmark_summary.cost_reduction_percentage >= 40:
            score += 6
        else:
            score += 3

        # Convert to grade
        if score >= 90:
            return "A+"
        elif score >= 85:
            return "A"
        elif score >= 80:
            return "B+"
        elif score >= 75:
            return "B"
        elif score >= 70:
            return "C+"
        elif score >= 65:
            return "C"
        else:
            return "D"

    def _extract_key_findings(
        self,
        benchmark_summary: BenchmarkSummary,
        comparison_result: Optional[ComparisonResult],
        profile_result: Optional[ProfileResult],
    ) -> List[str]:
        """Extract key findings from benchmark results."""
        findings = []

        # Performance findings
        if benchmark_summary.avg_response_time_ms <= 48:
            findings.append("Excellent response time performance achieved")
        elif benchmark_summary.avg_response_time_ms <= 100:
            findings.append("Good response time performance within targets")
        else:
            findings.append("Response time performance needs improvement")

        # Cache findings
        if benchmark_summary.cache_hit_rate >= 70:
            findings.append("Cache performance excellent with high hit rates")
        elif benchmark_summary.cache_hit_rate >= 60:
            findings.append("Cache performance good, meeting minimum targets")
        else:
            findings.append("Cache performance below optimal, requires attention")

        # Cost findings
        if benchmark_summary.cost_reduction_percentage >= 80:
            findings.append(
                "Significant cost savings achieved compared to traditional methods"
            )
        elif benchmark_summary.cost_reduction_percentage >= 60:
            findings.append("Good cost efficiency with substantial savings")
        else:
            findings.append("Cost efficiency below expectations")

        # Comparison findings
        if comparison_result:
            latency_improvement = comparison_result.improvement_factors.get(
                "latency", 1.0
            )
            if latency_improvement >= 4.0:
                findings.append("Outstanding latency improvement over traditional RAG")
            elif latency_improvement >= 2.0:
                findings.append("Significant latency improvement demonstrated")
            else:
                findings.append("Latency improvement present but below expectations")

        return findings[:5]  # Return top 5 findings

    def _determine_action_required(
        self,
        benchmark_summary: BenchmarkSummary,
        profile_result: Optional[ProfileResult],
    ) -> str:
        """Determine required actions based on results."""
        critical_issues = []

        if benchmark_summary.error_rate > 10:
            critical_issues.append("High error rate")

        if benchmark_summary.avg_response_time_ms > 200:
            critical_issues.append("Poor response times")

        if benchmark_summary.cache_hit_rate < 40:
            critical_issues.append("Low cache efficiency")

        if profile_result:
            critical_bottlenecks = [
                b for b in profile_result.bottlenecks if b.severity == "critical"
            ]
            if critical_bottlenecks:
                critical_issues.append("Critical performance bottlenecks")

        if critical_issues:
            return f"IMMEDIATE ACTION REQUIRED: {', '.join(critical_issues)}"
        elif (
            benchmark_summary.avg_response_time_ms > 100
            or benchmark_summary.cache_hit_rate < 60
        ):
            return "OPTIMIZATION RECOMMENDED: Performance improvements needed"
        else:
            return "MONITORING: System performing within acceptable parameters"

    def _generate_overall_recommendations(
        self,
        benchmark_summary: BenchmarkSummary,
        comparison_result: Optional[ComparisonResult],
        profile_result: Optional[ProfileResult],
        alerts: Optional[List[PerformanceAlert]],
    ) -> List[str]:
        """Generate overall optimization recommendations."""
        recommendations = []

        # Critical alerts take priority
        if alerts:
            critical_alerts = [a for a in alerts if a.severity == "critical"]
            if critical_alerts:
                recommendations.append(
                    "Address critical performance alerts immediately"
                )

        # Performance-based recommendations
        if benchmark_summary.avg_response_time_ms > 100:
            recommendations.append(
                "Optimize response time through caching and query optimization"
            )

        if benchmark_summary.cache_hit_rate < 60:
            recommendations.append(
                "Implement cache warming and improve hit rate strategies"
            )

        if benchmark_summary.error_rate > 5:
            recommendations.append("Investigate and resolve system reliability issues")

        # Bottleneck recommendations
        if profile_result and profile_result.bottlenecks:
            top_bottleneck = max(
                profile_result.bottlenecks, key=lambda b: b.impact_percentage
            )
            recommendations.append(
                f"Address {top_bottleneck.component.lower()} bottleneck"
            )

        # Cost optimization
        if benchmark_summary.cost_reduction_percentage < 70:
            recommendations.append(
                "Improve cost efficiency through better caching strategies"
            )

        # General recommendations
        recommendations.extend(
            [
                "Implement continuous performance monitoring",
                "Establish performance regression testing",
                "Document optimization strategies and results",
            ]
        )

        return recommendations[:8]  # Return top 8 recommendations

    def export_report_json(self, report: BenchmarkReport) -> str:
        """Export report as JSON."""
        return json.dumps(asdict(report), indent=2, default=str)

    def export_report_summary_text(self, report: BenchmarkReport) -> str:
        """Export report summary as text."""
        lines = []
        lines.append("=" * 50)
        lines.append(f"FACT PERFORMANCE BENCHMARK REPORT")
        lines.append("=" * 50)
        lines.append(f"Generated: {datetime.fromtimestamp(report.generated_at)}")
        lines.append(f"Report ID: {report.report_id}")
        lines.append("")

        # Executive Summary
        exec_summary = next(
            (s for s in report.sections if s.section_id == "executive_summary"), None
        )
        if exec_summary:
            lines.append("EXECUTIVE SUMMARY")
            lines.append("-" * 20)
            content = exec_summary.content
            lines.append(f"Overall Performance: {content['overall_assessment']}")
            lines.append(f"Cache Performance: {content['cache_assessment']}")
            lines.append(
                f"Average Response Time: {content['key_metrics']['avg_response_time_ms']:.1f}ms"
            )
            lines.append(
                f"Cache Hit Rate: {content['key_metrics']['cache_hit_rate']:.1f}%"
            )
            lines.append("")

        # Key Recommendations
        if report.recommendations:
            lines.append("KEY RECOMMENDATIONS")
            lines.append("-" * 20)
            for i, rec in enumerate(report.recommendations[:5], 1):
                lines.append(f"{i}. {rec}")
            lines.append("")

        # Performance Grade
        if "performance_grade" in report.summary:
            lines.append(f"PERFORMANCE GRADE: {report.summary['performance_grade']}")
            lines.append("")

        return "\n".join(lines)
