#!/usr/bin/env python3
"""
Enhanced FACT Benchmark Runner with Performance Optimization

Executes comprehensive performance validation with automatic optimization,
real-time monitoring, and detailed reporting to validate the enhanced
caching system performance.
"""

import asyncio
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime
import json

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from benchmarking.framework import BenchmarkFramework, BenchmarkConfig, BenchmarkRunner
from cache.manager import CacheManager, get_cache_manager
from cache.warming import get_cache_warmer, warm_cache_startup
from cache.metrics import get_metrics_collector
from monitoring.performance_optimizer import (
    get_performance_optimizer,
    start_performance_optimization,
)
from core.config import get_config


def create_optimized_logs_directory(base_dir: str = "./logs") -> Path:
    """Create timestamped logs directory for optimized benchmark results."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    logs_dir = Path(base_dir) / f"optimized_benchmark_{timestamp}"
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Create subdirectories for organized output
    (logs_dir / "reports").mkdir(exist_ok=True)
    (logs_dir / "charts").mkdir(exist_ok=True)
    (logs_dir / "raw_data").mkdir(exist_ok=True)
    (logs_dir / "optimization_logs").mkdir(exist_ok=True)

    return logs_dir


def display_benchmark_targets():
    """Display the benchmark targets we're trying to achieve."""
    print("\n📊 FACT System Performance Targets:")
    print("   ┌─────────────────────────────────────────────────────────┐")
    print("   │ Metric                    │ Target      │ Status        │")
    print("   ├─────────────────────────────────────────────────────────┤")
    print("   │ Cache Hit Latency         │ ≤ 48.0ms    │ Optimizing... │")
    print("   │ Cache Miss Latency        │ ≤ 140.0ms   │ Optimizing... │")
    print("   │ Cost Reduction            │ ≥ 90.0%     │ Optimizing... │")
    print("   │ Cache Hit Rate            │ ≥ 60.0%     │ Optimizing... │")
    print("   └─────────────────────────────────────────────────────────┘")


async def run_optimized_benchmark_suite(args):
    """Run comprehensive optimized benchmark suite."""
    print("🚀 Starting FACT Optimized Benchmark Suite")
    print("   Enhanced with intelligent cache warming, latency optimization,")
    print("   and real-time performance monitoring\n")

    display_benchmark_targets()

    # Create timestamped logs directory
    logs_dir = create_optimized_logs_directory()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    try:
        # Initialize optimized configuration
        print("\n🔧 Initializing optimized FACT system...")

        # Enhanced cache configuration for optimization
        cache_config = {
            "prefix": "fact_optimized_benchmark",
            "min_tokens": 50,  # Reduced for better caching
            "max_size": "15MB",  # Increased cache size
            "ttl_seconds": 7200,  # 2 hours
            "hit_target_ms": 48.0,  # Updated target
            "miss_target_ms": 140.0,
        }

        # Initialize cache manager with optimizations
        cache_manager = CacheManager(cache_config)

        # Initialize performance optimizer
        optimizer = get_performance_optimizer(cache_manager)

        # Start optimization monitoring
        print("🎯 Starting performance optimization monitoring...")
        await start_performance_optimization(cache_manager)

        # Intelligent cache warming
        print("🔥 Performing intelligent cache warming...")
        cache_warmer = get_cache_warmer(cache_manager)

        # Pre-warm with optimized queries
        warmup_result = await cache_warmer.warm_cache_intelligently(
            max_queries=args.warmup_queries
        )
        print(
            f"   ✓ Warmed {warmup_result.queries_successful}/{warmup_result.queries_attempted} queries"
        )
        print(f"   ✓ Cached {warmup_result.total_tokens_cached} tokens")
        print(f"   ✓ Warming completed in {warmup_result.total_time_ms:.1f}ms")

        # Wait for optimization to take effect
        print("\n⏳ Allowing optimization system to analyze and adjust...")
        await asyncio.sleep(5)

        # Initialize benchmark framework with optimized settings
        benchmark_config = BenchmarkConfig(
            iterations=args.iterations,
            warmup_iterations=args.warmup,
            concurrent_users=args.concurrent_users,
            timeout_seconds=60,
            target_cache_hit_rate=0.60,
            target_hit_latency_ms=48.0,
            target_miss_latency_ms=140.0,
            target_cost_reduction_hit=0.90,
        )

        framework = BenchmarkFramework(benchmark_config)
        runner = BenchmarkRunner(framework)

        # Enhanced test queries for comprehensive evaluation
        enhanced_queries = [
            "What was the Q1-2025 revenue?",
            "Show me quarterly revenue summary for 2024",
            "Calculate year-over-year growth rate",
            "What is the total revenue for 2024?",
            "Compare Q1-2025 vs Q1-2024 revenue",
            "Show revenue by product category",
            "What was the highest revenue quarter in 2024?",
            "Analyze customer acquisition trends",
            "Show operational efficiency metrics",
            "Calculate cost per acquisition",
            "What are the top performing products?",
            "Show customer satisfaction scores",
            "Analyze market performance by region",
            "What is current profit margin?",
            "Show predictive revenue forecasts",
        ]

        # Run performance validation
        print("\n📈 Running optimized performance validation...")
        print(f"   • Testing {len(enhanced_queries)} diverse queries")
        print(
            f"   • {args.iterations} iterations with {args.concurrent_users} concurrent users"
        )
        print(f"   • Real-time optimization monitoring active")

        # Execute benchmarks with enhanced monitoring
        start_time = time.time()

        # Run enhanced benchmark suite
        summary = await framework.run_benchmark_suite(enhanced_queries, cache_manager)

        execution_time = time.time() - start_time

        # Get optimization status
        opt_status = optimizer.get_optimization_status()

        # Collect comprehensive metrics
        final_metrics = cache_manager.get_metrics()
        performance_stats = cache_manager.get_performance_stats()

        # Generate validation results
        validation_results = {
            "timestamp": time.time(),
            "execution_time_seconds": execution_time,
            "benchmark_summary": {
                "total_queries": summary.total_queries,
                "successful_queries": summary.successful_queries,
                "cache_hits": summary.cache_hits,
                "cache_misses": summary.cache_misses,
                "cache_hit_rate": summary.cache_hit_rate * 100,  # Convert to percentage
                "avg_hit_latency_ms": summary.avg_hit_latency_ms,
                "avg_miss_latency_ms": summary.avg_miss_latency_ms,
                "avg_response_time_ms": summary.avg_response_time_ms,
                "cost_reduction_percentage": summary.cost_reduction_percentage,
                "error_rate": summary.error_rate,
                "throughput_qps": summary.throughput_qps,
            },
            "target_validation": {
                "cache_hit_latency": {
                    "target_ms": 48.0,
                    "actual_ms": summary.avg_hit_latency_ms,
                    "met": summary.avg_hit_latency_ms <= 48.0,
                    "status": "PASS" if summary.avg_hit_latency_ms <= 48.0 else "FAIL",
                },
                "cache_miss_latency": {
                    "target_ms": 140.0,
                    "actual_ms": summary.avg_miss_latency_ms,
                    "met": summary.avg_miss_latency_ms <= 140.0,
                    "status": (
                        "PASS" if summary.avg_miss_latency_ms <= 140.0 else "FAIL"
                    ),
                },
                "cost_reduction": {
                    "target_percent": 90.0,
                    "actual_percent": summary.cost_reduction_percentage,
                    "met": summary.cost_reduction_percentage >= 90.0,
                    "status": (
                        "PASS" if summary.cost_reduction_percentage >= 90.0 else "FAIL"
                    ),
                },
                "cache_hit_rate": {
                    "target_percent": 60.0,
                    "actual_percent": summary.cache_hit_rate * 100,
                    "met": (summary.cache_hit_rate * 100) >= 60.0,
                    "status": (
                        "PASS" if (summary.cache_hit_rate * 100) >= 60.0 else "FAIL"
                    ),
                },
            },
            "optimization_status": opt_status,
            "cache_metrics": {
                "total_entries": final_metrics.total_entries,
                "memory_utilization_percent": (
                    final_metrics.total_size / cache_manager.max_size_bytes * 100
                ),
                "hit_rate_percent": final_metrics.hit_rate,
                "token_efficiency": final_metrics.token_efficiency,
            },
            "performance_improvements": {
                "warming_result": {
                    "queries_warmed": warmup_result.queries_successful,
                    "tokens_cached": warmup_result.total_tokens_cached,
                    "warming_time_ms": warmup_result.total_time_ms,
                },
                "optimization_actions": len(opt_status.get("recent_actions", [])),
                "strategy": opt_status.get("current_strategy", "unknown"),
            },
        }

        # Calculate overall pass status
        targets = validation_results["target_validation"]
        validation_results["overall_pass"] = all(
            [
                targets["cache_hit_latency"]["met"],
                targets["cache_miss_latency"]["met"],
                targets["cost_reduction"]["met"],
                targets["cache_hit_rate"]["met"],
            ]
        )

        # Save comprehensive results
        await save_benchmark_results(validation_results, logs_dir, timestamp)

        # Display results
        display_optimization_results(validation_results, logs_dir)

        # Stop optimization monitoring
        from monitoring.performance_optimizer import stop_performance_optimization

        await stop_performance_optimization()

        return validation_results["overall_pass"]

    except Exception as e:
        print(f"\n❌ Benchmark execution failed: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


async def save_benchmark_results(results: dict, logs_dir: Path, timestamp: str):
    """Save comprehensive benchmark results."""

    # Save JSON report
    json_report_path = (
        logs_dir / "reports" / f"optimized_benchmark_report_{timestamp}.json"
    )
    with open(json_report_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    # Save text summary
    text_report_path = (
        logs_dir / "reports" / f"optimized_benchmark_summary_{timestamp}.txt"
    )
    with open(text_report_path, "w") as f:
        f.write("FACT Optimized Benchmark Results\n")
        f.write("=" * 50 + "\n\n")

        f.write(f"Execution Time: {results['execution_time_seconds']:.2f} seconds\n")
        f.write(f"Timestamp: {datetime.fromtimestamp(results['timestamp'])}\n\n")

        f.write("Performance Targets:\n")
        for metric, data in results["target_validation"].items():
            status = "✅ PASS" if data["met"] else "❌ FAIL"
            f.write(
                f"  {metric}: {status} - Target: {data.get('target_ms', data.get('target_percent', 'N/A'))}, "
                f"Actual: {data.get('actual_ms', data.get('actual_percent', 'N/A'))}\n"
            )

        f.write(
            f"\nOverall Result: {'✅ PASS' if results['overall_pass'] else '❌ FAIL'}\n\n"
        )

        summary = results["benchmark_summary"]
        f.write("Benchmark Summary:\n")
        f.write(f"  Total Queries: {summary['total_queries']}\n")
        f.write(f"  Cache Hit Rate: {summary['cache_hit_rate']:.1f}%\n")
        f.write(f"  Average Hit Latency: {summary['avg_hit_latency_ms']:.1f}ms\n")
        f.write(f"  Average Miss Latency: {summary['avg_miss_latency_ms']:.1f}ms\n")
        f.write(f"  Cost Reduction: {summary['cost_reduction_percentage']:.1f}%\n")
        f.write(f"  Throughput: {summary['throughput_qps']:.1f} QPS\n")

    # Save raw data
    raw_data_path = logs_dir / "raw_data" / f"benchmark_data_{timestamp}.json"
    with open(raw_data_path, "w") as f:
        json.dump(
            {
                "benchmark_summary": results["benchmark_summary"],
                "cache_metrics": results["cache_metrics"],
                "optimization_status": results["optimization_status"],
            },
            f,
            indent=2,
            default=str,
        )


def display_optimization_results(results: dict, logs_dir: Path):
    """Display comprehensive optimization results."""

    print("\n" + "=" * 80)
    print("🎯 FACT OPTIMIZATION BENCHMARK RESULTS")
    print("=" * 80)

    # Performance targets validation
    print("\n📊 Performance Target Validation:")
    targets = results["target_validation"]

    for metric_name, data in targets.items():
        status_icon = "✅" if data["met"] else "❌"
        metric_display = metric_name.replace("_", " ").title()

        if "latency" in metric_name:
            print(
                f"   {status_icon} {metric_display:<25} {data['actual_ms']:>8.1f}ms    Target: ≤{data['target_ms']}ms"
            )
        else:
            print(
                f"   {status_icon} {metric_display:<25} {data['actual_percent']:>8.1f}%     Target: ≥{data['target_percent']}%"
            )

    # Overall result
    overall_status = (
        "🎉 SUCCESS" if results["overall_pass"] else "⚠️  NEEDS IMPROVEMENT"
    )
    print(f"\n🏆 Overall Result: {overall_status}")

    # Performance summary
    summary = results["benchmark_summary"]
    print(f"\n📈 Performance Summary:")
    print(f"   • Total Queries Processed: {summary['total_queries']}")
    print(f"   • Cache Hit Rate: {summary['cache_hit_rate']:.1f}%")
    print(f"   • Average Response Time: {summary['avg_response_time_ms']:.1f}ms")
    print(f"   • System Throughput: {summary['throughput_qps']:.1f} QPS")
    print(f"   • Error Rate: {summary['error_rate']:.1f}%")

    # Optimization impact
    improvements = results["performance_improvements"]
    print(f"\n⚡ Optimization Impact:")
    print(
        f"   • Cache Entries Warmed: {improvements['warming_result']['queries_warmed']}"
    )
    print(
        f"   • Tokens Pre-cached: {improvements['warming_result']['tokens_cached']:,}"
    )
    print(f"   • Optimization Actions: {improvements['optimization_actions']}")
    print(f"   • Strategy: {improvements['strategy']}")

    # Cost efficiency
    print(f"\n💰 Cost Efficiency:")
    print(f"   • Cost Reduction Achieved: {summary['cost_reduction_percentage']:.1f}%")
    print(
        f"   • Cache Memory Utilization: {results['cache_metrics']['memory_utilization_percent']:.1f}%"
    )
    print(
        f"   • Token Efficiency: {results['cache_metrics']['token_efficiency']:.1f} tokens/KB"
    )

    # Results location
    print(f"\n📁 Detailed Results Saved To:")
    print(f"   {logs_dir}")
    print(f"   ├── reports/optimized_benchmark_report_*.json")
    print(f"   ├── reports/optimized_benchmark_summary_*.txt")
    print(f"   └── raw_data/benchmark_data_*.json")

    if results["overall_pass"]:
        print(
            f"\n🎉 Optimization successful! FACT system is performing within all targets."
        )
        print(f"   The enhanced caching system with intelligent warming and real-time")
        print(f"   optimization has achieved the required performance benchmarks.")
    else:
        print(f"\n📋 Next Steps for Further Optimization:")
        if not targets["cache_hit_rate"]["met"]:
            print(f"   • Increase cache warming frequency and scope")
            print(f"   • Analyze query patterns for better prediction")
        if not targets["cache_hit_latency"]["met"]:
            print(f"   • Enable additional cache access optimizations")
            print(f"   • Consider memory layout improvements")
        if not targets["cost_reduction"]["met"]:
            print(f"   • Review token estimation algorithms")
            print(f"   • Optimize query processing efficiency")


def main():
    """Main entry point for optimized benchmark runner."""
    parser = argparse.ArgumentParser(
        description="FACT Optimized Benchmark Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic optimized benchmark
  python scripts/run_optimized_benchmarks.py

  # Intensive optimization test
  python scripts/run_optimized_benchmarks.py --iterations 20 --warmup-queries 50

  # Load testing with optimization
  python scripts/run_optimized_benchmarks.py --concurrent-users 10 --iterations 15
        """,
    )

    # Benchmark configuration
    parser.add_argument(
        "--iterations",
        type=int,
        default=15,
        help="Number of benchmark iterations (default: 15)",
    )
    parser.add_argument(
        "--warmup", type=int, default=3, help="Number of warmup iterations (default: 3)"
    )
    parser.add_argument(
        "--warmup-queries",
        type=int,
        default=40,
        help="Number of queries to warm before benchmarking (default: 40)",
    )
    parser.add_argument(
        "--concurrent-users",
        type=int,
        default=5,
        help="Number of concurrent users for load testing (default: 5)",
    )

    # Output configuration
    parser.add_argument(
        "--output-dir",
        default="./logs",
        help="Output directory for results (default: ./logs)",
    )

    args = parser.parse_args()

    # Run optimized benchmark
    success = asyncio.run(run_optimized_benchmark_suite(args))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
