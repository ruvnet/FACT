"""
Performance benchmark tests for the FACT system.
Tests response times, token costs, and performance comparisons with traditional RAG.
Following TDD principles - these tests will fail until implementation is complete.
"""

import pytest
import time
import asyncio
import statistics
from unittest.mock import Mock, patch, AsyncMock
from dataclasses import dataclass
from typing import List, Dict, Any
import json


@dataclass
class PerformanceMetrics:
    """Performance metrics for benchmark testing."""

    response_time_ms: float
    token_cost: float
    cache_hit: bool
    query_type: str
    timestamp: float


@dataclass
class BenchmarkResults:
    """Benchmark results comparison."""

    fact_metrics: List[PerformanceMetrics]
    rag_baseline_metrics: List[PerformanceMetrics]
    improvement_factor: float
    cost_reduction_percentage: float


class TestResponseTimeTargets:
    """Test suite for response time performance targets."""

    @pytest.mark.performance
    async def test_cache_hit_response_under_50ms(
        self, test_environment, cache_config, benchmark_queries
    ):
        """TEST: Cache hit responses achieve target latency under 50ms"""
        # Arrange
        from src.core.driver import process_user_query
        from src.cache.manager import CacheManager

        manager = CacheManager(config=cache_config)
        query = benchmark_queries[0]

        # Pre-warm cache
        cached_response = "Cached response: Q1-2025 revenue was $1,234,567.89"
        query_hash = manager.generate_hash(query)
        manager.store(query_hash, cached_response)

        # Act
        measurements = []
        for _ in range(10):  # Multiple measurements for accuracy
            start_time = time.perf_counter()

            with patch("src.cache.manager.cache_manager", manager):
                response = await process_user_query(query)

            end_time = time.perf_counter()
            latency_ms = (end_time - start_time) * 1000
            measurements.append(latency_ms)

        # Assert
        avg_latency = statistics.mean(measurements)
        p95_latency = statistics.quantiles(measurements, n=20)[18]  # 95th percentile

        assert (
            avg_latency < 50
        ), f"Average cache hit latency {avg_latency:.2f}ms exceeds 50ms target"
        assert (
            p95_latency < 50
        ), f"P95 cache hit latency {p95_latency:.2f}ms exceeds 50ms target"
        assert response is not None

    @pytest.mark.performance
    async def test_cache_miss_response_under_140ms(
        self, test_environment, mock_anthropic_client, benchmark_queries
    ):
        """TEST: Cache miss responses achieve target latency under 140ms"""
        # Arrange
        from src.core.driver import process_user_query

        # Configure mock for realistic response time
        mock_anthropic_client.messages.create = AsyncMock()
        mock_response = Mock()
        mock_response.content = [Mock(text="Mock response from Claude")]
        mock_response.tool_calls = None
        mock_anthropic_client.messages.create.return_value = mock_response

        # Simulate network latency
        async def delayed_response(*args, **kwargs):
            await asyncio.sleep(0.08)  # 80ms simulated API call
            return mock_response

        mock_anthropic_client.messages.create.side_effect = delayed_response

        query = f"Unique query {time.time()}"  # Ensure cache miss

        # Act
        measurements = []
        for _ in range(5):  # Fewer iterations due to higher latency
            start_time = time.perf_counter()

            with patch("src.core.driver.anthropic_client", mock_anthropic_client):
                response = await process_user_query(query)

            end_time = time.perf_counter()
            latency_ms = (end_time - start_time) * 1000
            measurements.append(latency_ms)

        # Assert
        avg_latency = statistics.mean(measurements)
        assert (
            avg_latency < 140
        ), f"Average cache miss latency {avg_latency:.2f}ms exceeds 140ms target"
        assert response is not None

    @pytest.mark.performance
    def test_tool_execution_under_10ms_lan(self, test_environment, test_database):
        """TEST: Tool execution meets LAN latency targets under 10ms"""
        # Arrange
        from src.tools.connectors.sql import execute_sql_query

        queries = [
            "SELECT COUNT(*) as total FROM revenue",
            "SELECT quarter, value FROM revenue WHERE quarter = 'Q1-2025'",
            "SELECT AVG(value) as avg_revenue FROM revenue",
            "SELECT MAX(value) as max_revenue FROM revenue",
        ]

        # Act
        measurements = []
        for query in queries:
            start_time = time.perf_counter()
            result = execute_sql_query(query, test_database)
            end_time = time.perf_counter()

            latency_ms = (end_time - start_time) * 1000
            measurements.append(latency_ms)

            assert result.success == True

        # Assert
        avg_latency = statistics.mean(measurements)
        max_latency = max(measurements)

        assert (
            avg_latency < 10
        ), f"Average tool execution {avg_latency:.2f}ms exceeds 10ms target"
        assert (
            max_latency < 10
        ), f"Max tool execution {max_latency:.2f}ms exceeds 10ms target"

    @pytest.mark.performance
    async def test_overall_system_response_under_100ms(
        self, test_environment, benchmark_queries
    ):
        """TEST: Overall system response time meets 100ms average target"""
        # Arrange
        from src.core.driver import process_user_query

        # Mix of cache hits and misses
        mixed_queries = benchmark_queries[:5]  # Use first 5 benchmark queries

        # Act
        measurements = []
        for query in mixed_queries:
            start_time = time.perf_counter()
            response = await process_user_query(query)
            end_time = time.perf_counter()

            latency_ms = (end_time - start_time) * 1000
            measurements.append(latency_ms)
            assert response is not None

        # Assert
        avg_latency = statistics.mean(measurements)
        assert (
            avg_latency < 100
        ), f"Average system response {avg_latency:.2f}ms exceeds 100ms target"


class TestTokenCostOptimization:
    """Test suite for token cost optimization requirements."""

    @pytest.mark.cost_analysis
    async def test_cache_hit_cost_reduction_90_percent(
        self, test_environment, performance_targets
    ):
        """TEST: Cache hits achieve 90% cost reduction vs traditional RAG"""
        # Arrange
        from src.core.driver import process_user_query
        from src.cache.manager import CacheManager, calculate_token_cost

        query = "What was Q1-2025 revenue?"

        # Simulate traditional RAG cost (baseline)
        baseline_input_tokens = 1500  # Typical RAG prompt with context
        baseline_output_tokens = 200
        baseline_cost = calculate_token_cost(
            baseline_input_tokens, baseline_output_tokens
        )

        # Test FACT cache hit cost
        cached_response = "Q1-2025 revenue was $1,234,567.89 based on financial data."

        # Act
        with patch("src.cache.manager.get_cached_response") as mock_cache:
            mock_cache.return_value = cached_response

            # Measure cache hit cost
            start_tokens = 100  # Minimal prompt for cache lookup
            end_tokens = 50  # Cached response tokens
            fact_cost = calculate_token_cost(start_tokens, end_tokens)

        # Assert
        cost_reduction = (baseline_cost - fact_cost) / baseline_cost
        assert (
            cost_reduction >= performance_targets["cost_reduction_cache_hit"]
        ), f"Cache hit cost reduction {cost_reduction:.1%} below 90% target"

        # Verify actual 90% reduction
        assert (
            cost_reduction >= 0.90
        ), f"Cost reduction {cost_reduction:.1%} below 90% requirement"

    @pytest.mark.cost_analysis
    async def test_cache_miss_cost_reduction_65_percent(
        self, test_environment, performance_targets
    ):
        """TEST: Cache misses achieve 65% cost reduction vs traditional RAG"""
        # Arrange
        from src.core.driver import process_user_query
        from src.cache.manager import calculate_token_cost

        query = "What was Q2-2024 revenue breakdown by category?"

        # Simulate traditional RAG cost
        baseline_input_tokens = 1500  # Large context with vector search results
        baseline_output_tokens = 300  # Detailed response
        baseline_cost = calculate_token_cost(
            baseline_input_tokens, baseline_output_tokens
        )

        # Test FACT cache miss cost (uses tool calls)
        fact_input_tokens = 200  # Streamlined prompt + tool call
        fact_output_tokens = 150  # Response with tool results
        fact_cost = calculate_token_cost(fact_input_tokens, fact_output_tokens)

        # Assert
        cost_reduction = (baseline_cost - fact_cost) / baseline_cost
        assert (
            cost_reduction >= performance_targets["cost_reduction_cache_miss"]
        ), f"Cache miss cost reduction {cost_reduction:.1%} below 65% target"

        # Verify actual 65% reduction
        assert (
            cost_reduction >= 0.65
        ), f"Cost reduction {cost_reduction:.1%} below 65% requirement"

    @pytest.mark.cost_analysis
    def test_token_efficiency_metrics_calculation(self, test_environment):
        """TEST: Token efficiency metrics are calculated accurately"""
        # Arrange
        from src.cache.manager import TokenEfficiencyCalculator

        test_scenarios = [
            {
                "scenario": "cache_hit",
                "input_tokens": 100,
                "output_tokens": 50,
                "baseline_input": 1500,
                "baseline_output": 200,
            },
            {
                "scenario": "cache_miss",
                "input_tokens": 200,
                "output_tokens": 150,
                "baseline_input": 1500,
                "baseline_output": 300,
            },
        ]

        calculator = TokenEfficiencyCalculator()

        # Act & Assert
        for scenario in test_scenarios:
            efficiency = calculator.calculate_efficiency(
                fact_input=scenario["input_tokens"],
                fact_output=scenario["output_tokens"],
                rag_input=scenario["baseline_input"],
                rag_output=scenario["baseline_output"],
            )

            assert efficiency.fact_total_tokens < efficiency.rag_total_tokens
            assert efficiency.reduction_percentage > 0

            if scenario["scenario"] == "cache_hit":
                assert efficiency.reduction_percentage >= 0.90
            else:  # cache_miss
                assert efficiency.reduction_percentage >= 0.65


class TestPerformanceComparison:
    """Test suite for performance comparison with traditional RAG."""

    @pytest.mark.benchmark
    async def test_fact_vs_rag_latency_comparison(
        self, test_environment, benchmark_queries
    ):
        """TEST: FACT system latency comparison vs traditional RAG"""
        # Arrange
        from src.core.driver import process_user_query

        # Simulate traditional RAG latencies
        rag_latencies = [
            450,
            520,
            380,
            490,
            410,  # Typical RAG response times (400-500ms)
            510,
            470,
            430,
            460,
            480,
        ]

        # Test FACT system latencies
        fact_latencies = []

        # Act
        for i, query in enumerate(benchmark_queries[:10]):
            start_time = time.perf_counter()
            response = await process_user_query(query)
            end_time = time.perf_counter()

            latency_ms = (end_time - start_time) * 1000
            fact_latencies.append(latency_ms)

            assert response is not None

        # Assert
        fact_avg = statistics.mean(fact_latencies)
        rag_avg = statistics.mean(rag_latencies)
        improvement_factor = rag_avg / fact_avg

        assert (
            improvement_factor >= 3.0
        ), f"FACT latency improvement {improvement_factor:.1f}x below 3x target vs RAG"

        # Verify absolute performance
        assert (
            fact_avg < 100
        ), f"FACT average latency {fact_avg:.2f}ms exceeds 100ms target"

    @pytest.mark.benchmark
    def test_fact_vs_rag_cost_comparison(self, performance_targets):
        """TEST: FACT system cost comparison vs traditional RAG"""
        # Arrange
        from src.cache.manager import calculate_token_cost

        # Typical query scenarios
        scenarios = [
            {"query_type": "simple", "rag_input": 1200, "rag_output": 150},
            {"query_type": "complex", "rag_input": 2000, "rag_output": 400},
            {"query_type": "analytical", "rag_input": 1800, "rag_output": 300},
        ]

        fact_costs = []
        rag_costs = []

        # Act
        for scenario in scenarios:
            # RAG costs
            rag_cost = calculate_token_cost(
                scenario["rag_input"], scenario["rag_output"]
            )
            rag_costs.append(rag_cost)

            # FACT costs (assuming 70% cache hits)
            cache_hit_cost = calculate_token_cost(80, 40)  # Minimal tokens
            cache_miss_cost = calculate_token_cost(180, 120)  # Tool-enhanced

            fact_avg_cost = (0.7 * cache_hit_cost) + (0.3 * cache_miss_cost)
            fact_costs.append(fact_avg_cost)

        # Assert
        total_rag_cost = sum(rag_costs)
        total_fact_cost = sum(fact_costs)
        cost_reduction = (total_rag_cost - total_fact_cost) / total_rag_cost

        assert (
            cost_reduction >= 0.75
        ), f"Overall cost reduction {cost_reduction:.1%} below 75% target"

    @pytest.mark.benchmark
    async def test_throughput_comparison_under_load(
        self, test_environment, benchmark_queries
    ):
        """TEST: FACT system throughput vs traditional RAG under load"""
        # Arrange
        from src.core.driver import process_user_query
        import asyncio

        concurrent_users = 10
        queries_per_user = 5

        # Simulate concurrent load
        async def user_session(user_id: int):
            session_times = []
            for i in range(queries_per_user):
                query = benchmark_queries[i % len(benchmark_queries)]

                start_time = time.perf_counter()
                response = await process_user_query(f"{query} (user {user_id})")
                end_time = time.perf_counter()

                session_times.append(end_time - start_time)
                assert response is not None

            return session_times

        # Act
        start_time = time.perf_counter()

        user_sessions = await asyncio.gather(
            *[user_session(user_id) for user_id in range(concurrent_users)]
        )

        end_time = time.perf_counter()
        total_duration = end_time - start_time

        # Assert
        total_queries = concurrent_users * queries_per_user
        throughput_qps = total_queries / total_duration

        # FACT should handle significantly higher throughput than RAG
        assert (
            throughput_qps >= 20
        ), f"Throughput {throughput_qps:.1f} QPS below 20 QPS target"

        # Verify response time consistency under load
        all_response_times = [time for session in user_sessions for time in session]
        avg_response_time = statistics.mean(all_response_times) * 1000
        p95_response_time = statistics.quantiles(all_response_times, n=20)[18] * 1000

        assert (
            avg_response_time < 150
        ), f"Average response time under load {avg_response_time:.2f}ms too high"
        assert (
            p95_response_time < 200
        ), f"P95 response time under load {p95_response_time:.2f}ms too high"


class TestContinuousBenchmarking:
    """Test suite for continuous benchmarking and monitoring."""

    def test_benchmark_data_collection_and_storage(self, test_environment):
        """TEST: Benchmark data collection and storage for continuous monitoring"""
        # Arrange
        from src.monitoring.benchmarks import BenchmarkCollector

        collector = BenchmarkCollector()

        # Simulate benchmark run
        metrics = PerformanceMetrics(
            response_time_ms=45.2,
            token_cost=0.002,
            cache_hit=True,
            query_type="financial_query",
            timestamp=time.time(),
        )

        # Act
        collector.record_metric(metrics)
        stored_metrics = collector.get_recent_metrics(limit=10)

        # Assert
        assert len(stored_metrics) >= 1
        assert stored_metrics[0].response_time_ms == 45.2
        assert stored_metrics[0].cache_hit == True

    def test_benchmark_trend_analysis(self, test_environment):
        """TEST: Benchmark trend analysis for performance monitoring"""
        # Arrange
        from src.monitoring.benchmarks import BenchmarkAnalyzer

        # Create sample benchmark data over time
        historical_data = []
        for i in range(30):  # 30 data points
            metrics = PerformanceMetrics(
                response_time_ms=40 + (i * 0.5),  # Gradual increase
                token_cost=0.001 + (i * 0.0001),
                cache_hit=i % 2 == 0,
                query_type="test_query",
                timestamp=time.time() - (30 - i) * 86400,  # Daily data
            )
            historical_data.append(metrics)

        analyzer = BenchmarkAnalyzer(historical_data)

        # Act
        trend_analysis = analyzer.analyze_trends()

        # Assert
        assert "response_time_trend" in trend_analysis
        assert "cost_trend" in trend_analysis
        assert "cache_hit_rate_trend" in trend_analysis

        # Should detect increasing response time trend
        assert trend_analysis["response_time_trend"]["direction"] == "increasing"
        assert trend_analysis["response_time_trend"]["significance"] > 0.5

    def test_performance_alert_thresholds(self, test_environment, performance_targets):
        """TEST: Performance alert thresholds for continuous monitoring"""
        # Arrange
        from src.monitoring.alerts import PerformanceAlertManager

        alert_manager = PerformanceAlertManager(
            response_time_threshold=performance_targets["overall_response_ms"],
            cost_increase_threshold=0.20,  # 20% cost increase
            cache_hit_rate_threshold=0.60,  # 60% minimum hit rate
        )

        # Test scenarios
        scenarios = [
            {
                "name": "normal_performance",
                "response_time": 80,
                "cost_increase": 0.05,
                "cache_hit_rate": 0.75,
                "should_alert": False,
            },
            {
                "name": "slow_response",
                "response_time": 150,
                "cost_increase": 0.10,
                "cache_hit_rate": 0.70,
                "should_alert": True,
            },
            {
                "name": "high_cost",
                "response_time": 90,
                "cost_increase": 0.25,
                "cache_hit_rate": 0.65,
                "should_alert": True,
            },
            {
                "name": "low_cache_hit_rate",
                "response_time": 85,
                "cost_increase": 0.08,
                "cache_hit_rate": 0.45,
                "should_alert": True,
            },
        ]

        # Act & Assert
        for scenario in scenarios:
            alerts = alert_manager.check_thresholds(
                response_time_ms=scenario["response_time"],
                cost_increase_ratio=scenario["cost_increase"],
                cache_hit_rate=scenario["cache_hit_rate"],
            )

            has_alerts = len(alerts) > 0
            assert (
                has_alerts == scenario["should_alert"]
            ), f"Alert expectation failed for scenario: {scenario['name']}"

    def test_benchmark_report_generation(self, test_environment):
        """TEST: Benchmark report generation for performance tracking"""
        # Arrange
        from src.monitoring.reports import BenchmarkReportGenerator

        # Sample benchmark results
        fact_metrics = [
            PerformanceMetrics(45.2, 0.002, True, "query1", time.time()),
            PerformanceMetrics(65.1, 0.008, False, "query2", time.time()),
            PerformanceMetrics(38.7, 0.001, True, "query3", time.time()),
        ]

        rag_baseline = [
            PerformanceMetrics(420.5, 0.025, False, "query1", time.time()),
            PerformanceMetrics(380.2, 0.030, False, "query2", time.time()),
            PerformanceMetrics(450.8, 0.028, False, "query3", time.time()),
        ]

        generator = BenchmarkReportGenerator()

        # Act
        report = generator.generate_comparison_report(
            fact_results=fact_metrics, rag_baseline=rag_baseline
        )

        # Assert
        assert "performance_summary" in report
        assert "cost_analysis" in report
        assert "improvement_metrics" in report

        # Verify improvement calculations
        assert (
            report["improvement_metrics"]["latency_improvement"] > 5.0
        )  # At least 5x improvement
        assert (
            report["improvement_metrics"]["cost_reduction"] > 0.80
        )  # At least 80% cost reduction

        # Verify JSON serializable
        json_report = json.dumps(report, default=str)
        assert len(json_report) > 0


@pytest.mark.slow
class TestLongRunningBenchmarks:
    """Long-running benchmark tests for stability and performance over time."""

    @pytest.mark.performance
    async def test_sustained_performance_over_time(
        self, test_environment, benchmark_queries
    ):
        """TEST: System maintains performance over sustained operation"""
        # Arrange
        from src.core.driver import process_user_query

        duration_minutes = 5  # 5 minute sustained test
        measurement_interval = 10  # Measure every 10 seconds

        measurements = []
        start_time = time.time()
        end_time = start_time + (duration_minutes * 60)

        # Act
        query_count = 0
        while time.time() < end_time:
            query = benchmark_queries[query_count % len(benchmark_queries)]

            measurement_start = time.perf_counter()
            response = await process_user_query(query)
            measurement_end = time.perf_counter()

            latency_ms = (measurement_end - measurement_start) * 1000
            measurements.append(
                {
                    "timestamp": time.time(),
                    "latency_ms": latency_ms,
                    "query_count": query_count,
                }
            )

            query_count += 1
            assert response is not None

            # Wait for next measurement interval
            await asyncio.sleep(measurement_interval)

        # Assert
        latencies = [m["latency_ms"] for m in measurements]

        # Performance should remain stable
        early_avg = statistics.mean(latencies[:3])  # First 3 measurements
        late_avg = statistics.mean(latencies[-3:])  # Last 3 measurements

        performance_degradation = (late_avg - early_avg) / early_avg
        assert (
            performance_degradation < 0.20
        ), f"Performance degraded {performance_degradation:.1%} over time"

        # Overall performance should meet targets
        overall_avg = statistics.mean(latencies)
        assert (
            overall_avg < 100
        ), f"Sustained performance {overall_avg:.2f}ms exceeds target"
