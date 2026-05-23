"""
FACT Benchmarking System

Comprehensive benchmarking, profiling, and performance monitoring
for the FACT implementation.
"""

from .framework import (
    BenchmarkFramework,
    BenchmarkRunner,
    BenchmarkConfig,
    BenchmarkResult,
    BenchmarkSummary,
)

from .comparisons import (
    RAGComparison,
    PerformanceComparison,
    ComparisonResult,
    ComparisonMetrics,
    SystemType,
)

from .profiler import (
    SystemProfiler,
    BottleneckAnalyzer,
    ProfileResult,
    BottleneckAnalysis,
    ProfilePoint,
)

from .monitoring import (
    ContinuousMonitor,
    PerformanceTracker,
    MonitoringConfig,
    PerformanceAlert,
    PerformanceTrend,
)

from .visualization import (
    BenchmarkVisualizer,
    ReportGenerator,
    BenchmarkReport,
    ChartData,
    ReportSection,
)

__all__ = [
    # Framework
    "BenchmarkFramework",
    "BenchmarkRunner",
    "BenchmarkConfig",
    "BenchmarkResult",
    "BenchmarkSummary",
    # Comparisons
    "RAGComparison",
    "PerformanceComparison",
    "ComparisonResult",
    "ComparisonMetrics",
    "SystemType",
    # Profiling
    "SystemProfiler",
    "BottleneckAnalyzer",
    "ProfileResult",
    "BottleneckAnalysis",
    "ProfilePoint",
    # Monitoring
    "ContinuousMonitor",
    "PerformanceTracker",
    "MonitoringConfig",
    "PerformanceAlert",
    "PerformanceTrend",
    # Visualization
    "BenchmarkVisualizer",
    "ReportGenerator",
    "BenchmarkReport",
    "ChartData",
    "ReportSection",
]

# Version info
__version__ = "1.0.0"
__author__ = "FACT Team"
__description__ = "Comprehensive benchmarking system for FACT performance validation"
