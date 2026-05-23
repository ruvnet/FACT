"""
FACT System Monitoring and Observability

This package provides monitoring, metrics collection, and observability
functionality for the FACT system.
"""

# Use try/except to handle both relative and absolute imports
try:
    from .metrics import (
        MetricsCollector,
        get_metrics_collector,
        SystemMetrics,
        ToolExecutionMetric,
    )
except ImportError:
    # Fallback to absolute imports when called from scripts
    from monitoring.metrics import (
        MetricsCollector,
        get_metrics_collector,
        SystemMetrics,
        ToolExecutionMetric,
    )

__all__ = [
    "MetricsCollector",
    "get_metrics_collector",
    "SystemMetrics",
    "ToolExecutionMetric",
]
