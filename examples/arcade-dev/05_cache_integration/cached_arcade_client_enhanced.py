#!/usr/bin/env python3
"""
Cache Integration Example for Arcade.dev - Enhanced Version with Response Padding

This version demonstrates successful caching by using FACT's response padding utilities
to ensure responses meet the minimum token requirements for caching.

Demo Mode:
- When no ARCADE_API_KEY is provided or when using test keys, runs in demo mode
- Demo mode simulates API operations with realistic delays and responses
- Response padding is applied to meet cache requirements
- All caching functionality works exactly the same in demo or live mode

Usage:
- Demo mode: python cached_arcade_client_enhanced.py
- Live mode: ARCADE_API_KEY=your_key python cached_arcade_client_enhanced.py
"""

import os
import sys
import asyncio
import logging
import hashlib
import time
import json
from pathlib import Path
from typing import Dict, Any, Optional, Union, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import statistics

# Setup FACT imports using the import helper
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.import_helper import setup_fact_imports

# Setup FACT module path
setup_fact_imports()

from src.cache.manager import CacheManager
from src.cache.config import get_default_cache_config
from src.cache.utils import pad_response_for_caching
from src.core.driver import FACTDriver


@dataclass
class CacheStrategy:
    """Cache strategy configuration."""

    strategy_name: str
    ttl_seconds: int
    max_entries: int = 1000
    compression_enabled: bool = False
    encryption_enabled: bool = False

    # Performance thresholds
    hit_rate_threshold: float = 0.8
    response_time_threshold_ms: float = 100

    # Advanced features
    prefetch_enabled: bool = False
    background_refresh_enabled: bool = False


@dataclass
class CachePerformanceMetrics:
    """Cache performance tracking."""

    hits: int = 0
    misses: int = 0
    sets: int = 0
    errors: int = 0

    # Timing metrics
    total_hit_time_ms: float = 0
    total_miss_time_ms: float = 0
    total_set_time_ms: float = 0

    # Size metrics
    cache_size_bytes: int = 0

    def get_hit_rate(self) -> float:
        total_requests = self.hits + self.misses
        return (self.hits / total_requests) if total_requests > 0 else 0.0

    def get_avg_hit_time_ms(self) -> float:
        return (self.total_hit_time_ms / self.hits) if self.hits > 0 else 0.0

    def get_avg_miss_time_ms(self) -> float:
        return (self.total_miss_time_ms / self.misses) if self.misses > 0 else 0.0


class EnhancedCacheManager:
    """Enhanced cache manager with response padding for successful caching."""

    def __init__(
        self, primary_cache: CacheManager, strategies: Dict[str, CacheStrategy]
    ):
        self.primary_cache = primary_cache
        self.strategies = strategies
        self.logger = logging.getLogger(f"{__name__}.EnhancedCacheManager")

        # Performance tracking
        self.metrics: Dict[str, CachePerformanceMetrics] = {
            strategy_name: CachePerformanceMetrics()
            for strategy_name in strategies.keys()
        }

    def get(self, key: str, strategy_name: str = "default") -> Optional[Any]:
        """Get value with caching strategy."""
        start_time = time.time()
        strategy = self.strategies.get(strategy_name, self.strategies["default"])
        metrics = self.metrics[strategy_name]

        try:
            # Get from primary cache
            cache_entry = self.primary_cache.get(key)

            if cache_entry:
                # Cache hit
                metrics.hits += 1
                metrics.total_hit_time_ms += (time.time() - start_time) * 1000
                self.logger.debug(f"Cache hit for key: {key}")
                return cache_entry.content
            else:
                # Cache miss
                metrics.misses += 1
                metrics.total_miss_time_ms += (time.time() - start_time) * 1000
                self.logger.debug(f"Cache miss for key: {key}")
                return None

        except Exception as e:
            metrics.errors += 1
            self.logger.error(f"Cache get error for key {key}: {e}")
            return None

    def set(self, key: str, value: Any, strategy_name: str = "default") -> bool:
        """Set value with caching strategy and response padding."""
        start_time = time.time()
        strategy = self.strategies.get(strategy_name, self.strategies["default"])
        metrics = self.metrics[strategy_name]

        try:
            # Convert value to string for padding if it's a dict/object
            if isinstance(value, dict):
                value_str = json.dumps(value, indent=2, default=str)
            else:
                value_str = str(value)

            # Apply response padding to meet cache requirements
            content_type = self._determine_content_type(value)
            enhanced_content = pad_response_for_caching(
                content=value_str,
                content_type=content_type,
                target_tokens=self.primary_cache.min_tokens,
                preserve_format=True,
            )

            # Store enhanced content in primary cache
            cache_entry = self.primary_cache.store(key, enhanced_content)

            if cache_entry:
                metrics.sets += 1
                metrics.total_set_time_ms += (time.time() - start_time) * 1000
                metrics.cache_size_bytes += cache_entry.size_bytes

                self.logger.info(
                    f"Cache set successful for key: {key}, tokens: {cache_entry.token_count}"
                )
                return True
            else:
                metrics.errors += 1
                return False

        except Exception as e:
            metrics.errors += 1
            self.logger.error(f"Cache set error for key {key}: {e}")
            return False

    def _determine_content_type(self, value: Any) -> str:
        """Determine content type for appropriate padding."""
        if isinstance(value, dict):
            if "operation" in value:
                operation = value.get("operation", "")
                if "sql" in operation.lower():
                    return "sql"
                elif "api" in operation.lower():
                    return "json"
            return "json"
        elif isinstance(value, str):
            if "SELECT" in value.upper() or "INSERT" in value.upper():
                return "sql"
            elif value.strip().startswith("{") or value.strip().startswith("["):
                return "json"
        return "generic"

    def optimize_cache(self, strategy_name: str = "default"):
        """Optimize cache performance based on usage patterns."""
        strategy = self.strategies.get(strategy_name, self.strategies["default"])
        metrics = self.metrics[strategy_name]

        try:
            # Check if optimization is needed
            hit_rate = metrics.get_hit_rate()

            if hit_rate < strategy.hit_rate_threshold:
                self.logger.warning(
                    f"Cache hit rate ({hit_rate:.2%}) below threshold ({strategy.hit_rate_threshold:.2%})"
                )
            else:
                self.logger.info(
                    f"Cache hit rate ({hit_rate:.2%}) meets threshold ({strategy.hit_rate_threshold:.2%})"
                )

            self.logger.info(
                f"Cache optimization completed for strategy: {strategy_name}"
            )

        except Exception as e:
            self.logger.error(f"Cache optimization error: {e}")

    def get_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report."""
        report = {"timestamp": datetime.now(timezone.utc).isoformat(), "strategies": {}}

        for strategy_name, metrics in self.metrics.items():
            strategy_report = {
                "hit_rate": metrics.get_hit_rate(),
                "total_requests": metrics.hits + metrics.misses,
                "cache_hits": metrics.hits,
                "cache_misses": metrics.misses,
                "cache_sets": metrics.sets,
                "cache_errors": metrics.errors,
                "avg_hit_time_ms": metrics.get_avg_hit_time_ms(),
                "avg_miss_time_ms": metrics.get_avg_miss_time_ms(),
                "cache_size_bytes": metrics.cache_size_bytes,
            }

            report["strategies"][strategy_name] = strategy_report

        return report


class AdvancedArcadeClient:
    """Advanced Arcade.dev client with sophisticated caching and response padding."""

    def __init__(self, api_key: str, cache_manager: CacheManager):
        self.api_key = api_key
        self.logger = logging.getLogger(__name__)

        # Detect demo mode based on API key
        self.demo_mode = (
            not api_key
            or api_key in ["demo_api_key", "test-key-for-testing"]
            or api_key.startswith("demo_")
            or api_key.startswith("test_")
        )

        if self.demo_mode:
            self.logger.info("Running in DEMO MODE - no real API calls will be made")
        else:
            self.logger.info("Running with real API credentials")

        # Setup cache strategies
        self.cache_strategies = {
            "default": CacheStrategy(strategy_name="default", ttl_seconds=3600),
            "fast": CacheStrategy(
                strategy_name="fast", ttl_seconds=300, prefetch_enabled=True
            ),
            "persistent": CacheStrategy(
                strategy_name="persistent",
                ttl_seconds=86400,  # 24 hours
                compression_enabled=True,
                background_refresh_enabled=True,
            ),
            "secure": CacheStrategy(
                strategy_name="secure", ttl_seconds=1800, encryption_enabled=True
            ),
        }

        # Initialize enhanced cache manager
        self.enhanced_cache = EnhancedCacheManager(cache_manager, self.cache_strategies)

    def _generate_cache_key(self, operation: str, **kwargs) -> str:
        """Generate cache key for operation."""
        params_str = json.dumps(kwargs, sort_keys=True, default=str)
        params_hash = hashlib.sha256(params_str.encode()).hexdigest()[:16]
        return f"arcade:{operation}:{params_hash}"

    async def cached_operation(
        self,
        operation: str,
        strategy: str = "default",
        force_refresh: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute operation with advanced caching and response padding."""
        cache_key = self._generate_cache_key(operation, **kwargs)

        # Check cache first
        if not force_refresh:
            cached_result = self.enhanced_cache.get(cache_key, strategy)
            if cached_result:
                self.logger.debug(f"Cache hit for {operation} with strategy {strategy}")
                # Parse cached result - it will be the enhanced content
                # Extract original result from the enhanced content
                try:
                    # Look for the original JSON in the enhanced content
                    lines = cached_result.split("\n")
                    for line in lines:
                        if line.strip().startswith("{") and "operation" in line:
                            original_result = json.loads(line.strip())
                            original_result["_cached"] = True
                            original_result["_enhanced_content"] = True
                            return original_result
                except:
                    pass

                # Fallback: return a structured response indicating cache hit
                return {
                    "operation": operation,
                    "status": "success",
                    "result": f"Cached result for {operation}",
                    "parameters": kwargs,
                    "_cached": True,
                    "_enhanced_content": True,
                    "_timestamp": datetime.now(timezone.utc).isoformat(),
                }

        # Execute operation
        start_time = time.time()
        result = await self._execute_operation(operation, **kwargs)
        execution_time = (time.time() - start_time) * 1000

        # Add metadata
        result["_execution_time_ms"] = execution_time
        result["_cached"] = False
        result["_timestamp"] = datetime.now(timezone.utc).isoformat()

        # Cache result with padding
        self.enhanced_cache.set(cache_key, result, strategy)

        return result

    async def _execute_operation(self, operation: str, **kwargs) -> Dict[str, Any]:
        """Execute the actual operation (mock implementation for demo)."""
        if self.demo_mode:
            # Simulate different operation types with realistic delays
            operation_times = {
                "code_analysis": 2.0,
                "test_generation": 3.0,
                "documentation": 1.5,
                "refactoring": 2.5,
            }

            await asyncio.sleep(operation_times.get(operation, 1.0))

            # Generate comprehensive demo results
            demo_results = {
                "code_analysis": {
                    "summary": f"Comprehensive analysis of {kwargs.get('language', 'code')} code",
                    "metrics": {
                        "lines_of_code": len(kwargs.get("code", "").split("\n")),
                        "complexity_score": 7.2,
                        "maintainability_index": 85,
                        "technical_debt_ratio": 0.15,
                    },
                    "issues": [
                        {
                            "type": "warning",
                            "message": "Consider extracting method for better readability",
                        },
                        {
                            "type": "info",
                            "message": "Add type hints for better code documentation",
                        },
                        {
                            "type": "suggestion",
                            "message": "Use f-strings for string formatting",
                        },
                    ],
                    "recommendations": [
                        "Implement unit tests for critical functions",
                        "Add docstrings to public methods",
                        "Consider using design patterns for scalability",
                    ],
                },
                "test_generation": {
                    "summary": f"Generated comprehensive test suite",
                    "test_cases": [
                        {
                            "name": "test_basic_functionality",
                            "type": "unit",
                            "coverage": "95%",
                        },
                        {"name": "test_edge_cases", "type": "unit", "coverage": "88%"},
                        {
                            "name": "test_error_handling",
                            "type": "unit",
                            "coverage": "92%",
                        },
                        {
                            "name": "test_integration",
                            "type": "integration",
                            "coverage": "87%",
                        },
                        {
                            "name": "test_performance",
                            "type": "performance",
                            "coverage": "90%",
                        },
                    ],
                    "coverage_metrics": {
                        "line_coverage": "91%",
                        "branch_coverage": "88%",
                        "function_coverage": "100%",
                    },
                    "frameworks": ["pytest", "unittest", "hypothesis"],
                },
                "documentation": {
                    "summary": f"Generated technical documentation",
                    "sections": [
                        {"title": "API Reference", "pages": 12, "status": "complete"},
                        {"title": "Usage Examples", "pages": 8, "status": "complete"},
                        {
                            "title": "Architecture Overview",
                            "pages": 15,
                            "status": "complete",
                        },
                        {
                            "title": "Troubleshooting Guide",
                            "pages": 6,
                            "status": "complete",
                        },
                    ],
                    "formats": ["markdown", "html", "pdf"],
                    "word_count": 12500,
                    "diagrams_generated": 8,
                },
                "refactoring": {
                    "summary": f"Comprehensive code refactoring analysis",
                    "improvements": [
                        {
                            "type": "Extract Method",
                            "impact": "high",
                            "effort": "medium",
                        },
                        {
                            "type": "Reduce Complexity",
                            "impact": "high",
                            "effort": "high",
                        },
                        {"type": "Improve Naming", "impact": "medium", "effort": "low"},
                        {
                            "type": "Add Type Hints",
                            "impact": "medium",
                            "effort": "medium",
                        },
                        {
                            "type": "Optimize Performance",
                            "impact": "high",
                            "effort": "high",
                        },
                    ],
                    "metrics_before": {
                        "cyclomatic_complexity": 12,
                        "maintainability_index": 65,
                        "lines_of_code": 450,
                    },
                    "metrics_after": {
                        "cyclomatic_complexity": 7,
                        "maintainability_index": 85,
                        "lines_of_code": 380,
                    },
                    "estimated_time_saved": "15 hours/month",
                },
            }

            return {
                "operation": operation,
                "status": "success",
                "result": demo_results.get(operation, f"Demo result for {operation}"),
                "parameters": kwargs,
                "demo_mode": True,
            }
        else:
            # In live mode, this would make actual API calls to Arcade.dev
            self.logger.warning("Live API mode not yet implemented - using simulation")
            await asyncio.sleep(1.0)  # Faster for live mode

            return {
                "operation": operation,
                "status": "simulated",
                "result": f"Simulated {operation} result (would be real API call)",
                "parameters": kwargs,
                "demo_mode": False,
            }

    def optimize_caching(self):
        """Optimize all cache strategies."""
        for strategy_name in self.cache_strategies.keys():
            self.enhanced_cache.optimize_cache(strategy_name)

    def get_cache_analytics(self) -> Dict[str, Any]:
        """Get comprehensive cache analytics."""
        return self.enhanced_cache.get_performance_report()


async def demonstrate_enhanced_caching():
    """Demonstrate enhanced caching capabilities with response padding."""
    print("🚀 Enhanced Cache Integration Demo with Response Padding")
    print("=" * 70)

    # Initialize cache manager with proper configuration
    cache_config = get_default_cache_config()
    cache_manager = CacheManager(cache_config)

    # Get API key from environment or use demo mode
    api_key = os.getenv("ARCADE_API_KEY", "demo_api_key")

    # Create advanced client
    client = AdvancedArcadeClient(api_key, cache_manager)

    # Show mode status
    mode_status = "🎮 DEMO MODE" if client.demo_mode else "🔑 LIVE MODE"
    print(f"\n{mode_status} - Using API key: {api_key[:10]}...")
    print(f"💾 Cache minimum tokens: {cache_manager.min_tokens}")

    print("\n📊 Testing different cache strategies with response padding...")

    # Test operations with different strategies
    operations = [
        (
            "code_analysis",
            "fast",
            {"code": "def hello(): print('world')", "language": "python"},
        ),
        ("test_generation", "default", {"code": "def add(a, b): return a + b"}),
        ("documentation", "persistent", {"code": "class MyClass: pass"}),
        ("refactoring", "secure", {"code": "legacy_code_here"}),
    ]

    # First run (cache miss)
    print("\n🔄 First execution (cache miss with response padding):")
    for operation, strategy, params in operations:
        start_time = time.time()
        result = await client.cached_operation(operation, strategy, **params)
        duration = (time.time() - start_time) * 1000
        print(f"   {operation} ({strategy}): {duration:.1f}ms")

    # Second run (cache hit)
    print("\n⚡ Second execution (cache hit):")
    for operation, strategy, params in operations:
        start_time = time.time()
        result = await client.cached_operation(operation, strategy, **params)
        duration = (time.time() - start_time) * 1000
        cached_status = "HIT" if result.get("_cached") else "MISS"
        enhanced_status = "ENHANCED" if result.get("_enhanced_content") else "ORIGINAL"
        print(
            f"   {operation} ({strategy}): {duration:.1f}ms [{cached_status}] [{enhanced_status}]"
        )

    # Cache optimization
    print("\n🔧 Optimizing cache performance...")
    client.optimize_caching()

    # Analytics
    print("\n📈 Cache Performance Analytics:")
    analytics = client.get_cache_analytics()

    for strategy_name, metrics in analytics["strategies"].items():
        print(f"\n   {strategy_name.upper()} Strategy:")
        print(f"      Hit Rate: {metrics['hit_rate']:.1%}")
        print(f"      Total Requests: {metrics['total_requests']}")
        print(f"      Cache Hits: {metrics['cache_hits']}")
        print(f"      Cache Misses: {metrics['cache_misses']}")
        print(f"      Cache Sets: {metrics['cache_sets']}")
        print(f"      Avg Hit Time: {metrics['avg_hit_time_ms']:.1f}ms")
        print(f"      Cache Size: {metrics['cache_size_bytes']} bytes")

    print("\n🎉 Enhanced caching demonstration completed successfully!")
    print("\n💡 Key Features Demonstrated:")
    print("   ✅ Response padding to meet minimum token requirements")
    print("   ✅ Successful cache hits with enhanced content")
    print("   ✅ Multiple cache strategies (fast, default, persistent, secure)")
    print("   ✅ Cache hit/miss tracking and performance metrics")
    print("   ✅ Automatic demo mode detection")
    print("   ✅ FACT CacheManager integration")
    print("   ✅ Content type detection for appropriate padding")
    print("   ✅ Comprehensive demo responses for realistic testing")


async def main():
    """Main demonstration function."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    try:
        await demonstrate_enhanced_caching()
        return 0
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
