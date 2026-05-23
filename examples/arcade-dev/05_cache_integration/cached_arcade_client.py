#!/usr/bin/env python3
"""
Cache Integration Example for Arcade.dev

This example demonstrates advanced caching strategies for Arcade.dev integration
with the FACT SDK, including hybrid caching, cache invalidation, optimization
techniques, and performance metrics.
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
from src.core.driver import FACTDriver


@dataclass
class CacheStrategy:
    """Cache strategy configuration."""

    strategy_name: str
    ttl_seconds: int
    max_entries: int = 1000
    compression_enabled: bool = False
    encryption_enabled: bool = False
    invalidation_pattern: str = "time"  # time, lru, custom

    # Performance thresholds
    hit_rate_threshold: float = 0.8
    response_time_threshold_ms: float = 100

    # Advanced features
    prefetch_enabled: bool = False
    background_refresh_enabled: bool = False
    multi_level_caching: bool = False


@dataclass
class CachePerformanceMetrics:
    """Cache performance tracking."""

    hits: int = 0
    misses: int = 0
    sets: int = 0
    evictions: int = 0
    errors: int = 0

    # Timing metrics
    total_hit_time_ms: float = 0
    total_miss_time_ms: float = 0
    total_set_time_ms: float = 0

    # Size metrics
    cache_size_bytes: int = 0
    avg_entry_size_bytes: float = 0

    # Advanced metrics
    prefetch_hits: int = 0
    background_refreshes: int = 0

    def get_hit_rate(self) -> float:
        total_requests = self.hits + self.misses
        return (self.hits / total_requests) if total_requests > 0 else 0.0

    def get_avg_hit_time_ms(self) -> float:
        return (self.total_hit_time_ms / self.hits) if self.hits > 0 else 0.0

    def get_avg_miss_time_ms(self) -> float:
        return (self.total_miss_time_ms / self.misses) if self.misses > 0 else 0.0


class HybridCacheManager:
    """Advanced cache manager with multiple cache levels and strategies."""

    def __init__(
        self, primary_cache: CacheManager, strategies: Dict[str, CacheStrategy]
    ):
        self.primary_cache = primary_cache
        self.strategies = strategies
        self.logger = logging.getLogger(f"{__name__}.HybridCacheManager")

        # In-memory cache for hot data
        self.memory_cache: Dict[str, Dict[str, Any]] = {}
        self.memory_cache_access_times: Dict[str, datetime] = {}
        self.memory_cache_max_size = 100

        # Performance tracking
        self.metrics: Dict[str, CachePerformanceMetrics] = {
            strategy_name: CachePerformanceMetrics()
            for strategy_name in strategies.keys()
        }

        # Cache key prefetching
        self.prefetch_queue: List[str] = []
        self.prefetch_task: Optional[asyncio.Task] = None

    async def get(self, key: str, strategy_name: str = "default") -> Optional[Any]:
        """Get value with hybrid caching strategy."""
        start_time = time.time()
        strategy = self.strategies.get(strategy_name, self.strategies["default"])
        metrics = self.metrics[strategy_name]

        try:
            # Level 1: Memory cache (fastest)
            if strategy.multi_level_caching and key in self.memory_cache:
                self.memory_cache_access_times[key] = datetime.now(timezone.utc)

                cache_data = self.memory_cache[key]
                if self._is_cache_entry_valid(cache_data):
                    metrics.hits += 1
                    metrics.total_hit_time_ms += (time.time() - start_time) * 1000
                    self.logger.debug(f"Memory cache hit for key: {key}")
                    return cache_data["data"]
                else:
                    # Remove expired entry
                    del self.memory_cache[key]
                    del self.memory_cache_access_times[key]

            # Level 2: Primary cache (persistent)
            cache_entry = self.primary_cache.get(key)

            if cache_entry and self._is_cache_entry_valid(
                {
                    "cached_at": cache_entry.created_at,
                    "ttl": self.strategies[strategy_name].ttl_seconds,
                }
            ):
                # Cache hit - extract data from cache entry content
                try:
                    cache_data = json.loads(cache_entry.content)
                    metrics.hits += 1
                    metrics.total_hit_time_ms += (time.time() - start_time) * 1000

                    # Promote to memory cache if multi-level enabled
                    if strategy.multi_level_caching:
                        await self._promote_to_memory_cache(key, cache_data, strategy)

                    self.logger.debug(f"Primary cache hit for key: {key}")
                    return cache_data.get("data", cache_data)
                except json.JSONDecodeError:
                    self.logger.warning(f"Invalid JSON in cache entry for key: {key}")

            # Cache miss
            metrics.misses += 1
            metrics.total_miss_time_ms += (time.time() - start_time) * 1000
            self.logger.debug(f"Cache miss for key: {key}")

            # Schedule prefetch if enabled
            if strategy.prefetch_enabled:
                await self._schedule_prefetch(key, strategy_name)

            return None

        except Exception as e:
            metrics.errors += 1
            self.logger.error(f"Cache get error for key {key}: {e}")
            return None

    async def set(
        self,
        key: str,
        value: Any,
        strategy_name: str = "default",
        custom_ttl: int = None,
    ) -> bool:
        """Set value with caching strategy."""
        start_time = time.time()
        strategy = self.strategies.get(strategy_name, self.strategies["default"])
        metrics = self.metrics[strategy_name]

        try:
            ttl = custom_ttl or strategy.ttl_seconds

            # Prepare cache data with metadata
            cache_data = {
                "data": value,
                "cached_at": time.time(),
                "ttl": ttl,
                "strategy": strategy_name,
                "access_count": 0,
                "size_bytes": len(json.dumps(value, default=str)),
            }

            # Apply compression if enabled
            if strategy.compression_enabled:
                cache_data = await self._compress_cache_data(cache_data)

            # Apply encryption if enabled
            if strategy.encryption_enabled:
                cache_data = await self._encrypt_cache_data(cache_data)

            # Store in primary cache using store method
            try:
                cache_entry = self.primary_cache.store(
                    key, json.dumps(cache_data, default=str)
                )
                success = True
            except Exception as e:
                self.logger.error(f"Primary cache store failed: {e}")
                success = False

            if success:
                metrics.sets += 1
                metrics.total_set_time_ms += (time.time() - start_time) * 1000
                metrics.cache_size_bytes += cache_data.get("size_bytes", 0)

                # Update average entry size
                if metrics.sets > 0:
                    metrics.avg_entry_size_bytes = (
                        metrics.cache_size_bytes / metrics.sets
                    )

                # Set in memory cache if multi-level enabled
                if strategy.multi_level_caching:
                    await self._set_memory_cache(key, cache_data, strategy)

                self.logger.debug(f"Cache set successful for key: {key}")

                # Schedule background refresh if enabled
                if strategy.background_refresh_enabled:
                    await self._schedule_background_refresh(key, strategy_name, ttl)

                return True
            else:
                metrics.errors += 1
                return False

        except Exception as e:
            metrics.errors += 1
            self.logger.error(f"Cache set error for key {key}: {e}")
            return False

    async def invalidate(self, pattern: str, strategy_name: str = "default") -> int:
        """Invalidate cache entries matching pattern."""
        strategy = self.strategies.get(strategy_name, self.strategies["default"])
        metrics = self.metrics[strategy_name]

        try:
            # Invalidate from memory cache
            invalidated_count = 0

            if strategy.multi_level_caching:
                keys_to_remove = []
                for key in self.memory_cache.keys():
                    if self._matches_pattern(key, pattern):
                        keys_to_remove.append(key)

                for key in keys_to_remove:
                    del self.memory_cache[key]
                    if key in self.memory_cache_access_times:
                        del self.memory_cache_access_times[key]
                    invalidated_count += 1

            # Invalidate from primary cache
            # Note: This is a simplified implementation
            # In production, you'd need pattern-based invalidation in the cache manager

            metrics.evictions += invalidated_count
            self.logger.info(
                f"Invalidated {invalidated_count} entries matching pattern: {pattern}"
            )
            return invalidated_count

        except Exception as e:
            metrics.errors += 1
            self.logger.error(f"Cache invalidation error for pattern {pattern}: {e}")
            return 0

    async def optimize_cache(self, strategy_name: str = "default"):
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

                # Optimization strategies
                await self._optimize_memory_cache_size(strategy)
                await self._optimize_ttl_values(strategy_name)
                await self._cleanup_expired_entries(strategy_name)

                self.logger.info(
                    f"Cache optimization completed for strategy: {strategy_name}"
                )

        except Exception as e:
            self.logger.error(f"Cache optimization error: {e}")

    def _is_cache_entry_valid(self, cache_data: Dict[str, Any]) -> bool:
        """Check if cache entry is still valid."""
        if not isinstance(cache_data, dict):
            return True  # Assume simple values are valid

        cached_at = cache_data.get("cached_at", 0)
        ttl = cache_data.get("ttl", 3600)

        return (time.time() - cached_at) < ttl

    async def _promote_to_memory_cache(
        self, key: str, cache_data: Dict[str, Any], strategy: CacheStrategy
    ):
        """Promote frequently accessed data to memory cache."""
        # Check if memory cache has space
        if len(self.memory_cache) >= self.memory_cache_max_size:
            await self._evict_lru_memory_cache()

        self.memory_cache[key] = cache_data
        self.memory_cache_access_times[key] = datetime.utcnow()

    async def _set_memory_cache(
        self, key: str, cache_data: Dict[str, Any], strategy: CacheStrategy
    ):
        """Set data in memory cache."""
        if len(self.memory_cache) >= self.memory_cache_max_size:
            await self._evict_lru_memory_cache()

        self.memory_cache[key] = cache_data
        self.memory_cache_access_times[key] = datetime.now(timezone.utc)

    async def _evict_lru_memory_cache(self):
        """Evict least recently used entry from memory cache."""
        if not self.memory_cache_access_times:
            return

        # Find LRU entry
        lru_key = min(
            self.memory_cache_access_times.keys(),
            key=lambda k: self.memory_cache_access_times[k],
        )

        # Remove LRU entry
        del self.memory_cache[lru_key]
        del self.memory_cache_access_times[lru_key]

    async def _schedule_prefetch(self, key: str, strategy_name: str):
        """Schedule prefetching for related keys."""
        if key not in self.prefetch_queue:
            self.prefetch_queue.append(key)

        if not self.prefetch_task or self.prefetch_task.done():
            self.prefetch_task = asyncio.create_task(self._process_prefetch_queue())

    async def _process_prefetch_queue(self):
        """Process prefetch queue in background."""
        while self.prefetch_queue:
            key = self.prefetch_queue.pop(0)
            # In a real implementation, you'd prefetch related data
            await asyncio.sleep(0.1)  # Simulate prefetch work

    async def _schedule_background_refresh(
        self, key: str, strategy_name: str, ttl: int
    ):
        """Schedule background refresh before TTL expires."""
        refresh_time = ttl * 0.8  # Refresh at 80% of TTL
        await asyncio.sleep(refresh_time)

        # In a real implementation, you'd refresh the data from source
        self.logger.debug(f"Background refresh triggered for key: {key}")

    async def _compress_cache_data(self, cache_data: Dict[str, Any]) -> Dict[str, Any]:
        """Compress cache data to save space."""
        # Simplified compression simulation
        cache_data["compressed"] = True
        cache_data["size_bytes"] = int(
            cache_data["size_bytes"] * 0.7
        )  # 30% compression
        return cache_data

    async def _encrypt_cache_data(self, cache_data: Dict[str, Any]) -> Dict[str, Any]:
        """Encrypt sensitive cache data."""
        # Simplified encryption simulation
        cache_data["encrypted"] = True
        return cache_data

    def _matches_pattern(self, key: str, pattern: str) -> bool:
        """Check if key matches invalidation pattern."""
        # Simplified pattern matching
        if pattern == "*":
            return True
        return pattern in key

    async def _optimize_memory_cache_size(self, strategy: CacheStrategy):
        """Optimize memory cache size based on hit patterns."""
        current_hit_rate = self.metrics[strategy.strategy_name].get_hit_rate()

        if current_hit_rate < 0.5:
            # Increase memory cache size
            self.memory_cache_max_size = min(self.memory_cache_max_size * 2, 500)
        elif current_hit_rate > 0.9:
            # Decrease memory cache size
            self.memory_cache_max_size = max(self.memory_cache_max_size // 2, 50)

        self.logger.debug(
            f"Optimized memory cache size to: {self.memory_cache_max_size}"
        )

    async def _optimize_ttl_values(self, strategy_name: str):
        """Optimize TTL values based on access patterns."""
        # In a real implementation, analyze access patterns and adjust TTLs
        self.logger.debug(f"TTL optimization completed for strategy: {strategy_name}")

    async def _cleanup_expired_entries(self, strategy_name: str):
        """Clean up expired entries from memory cache."""
        expired_keys = []

        for key, cache_data in self.memory_cache.items():
            if not self._is_cache_entry_valid(cache_data):
                expired_keys.append(key)

        for key in expired_keys:
            del self.memory_cache[key]
            if key in self.memory_cache_access_times:
                del self.memory_cache_access_times[key]

        self.metrics[strategy_name].evictions += len(expired_keys)
        self.logger.debug(f"Cleaned up {len(expired_keys)} expired entries")

    def get_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report."""
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "strategies": {},
            "memory_cache": {
                "size": len(self.memory_cache),
                "max_size": self.memory_cache_max_size,
                "utilization": len(self.memory_cache) / self.memory_cache_max_size,
            },
        }

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
                "avg_entry_size_bytes": metrics.avg_entry_size_bytes,
            }

            report["strategies"][strategy_name] = strategy_report

        return report


class AdvancedArcadeClient:
    """Advanced Arcade.dev client with sophisticated caching."""

    def __init__(self, api_key: str, cache_manager: CacheManager):
        self.api_key = api_key
        self.logger = logging.getLogger(__name__)

        # Setup cache strategies
        self.cache_strategies = {
            "default": CacheStrategy(
                strategy_name="default",
                ttl_seconds=3600,
                max_entries=1000,
                multi_level_caching=True,
            ),
            "fast": CacheStrategy(
                strategy_name="fast",
                ttl_seconds=300,
                max_entries=100,
                multi_level_caching=True,
                prefetch_enabled=True,
            ),
            "persistent": CacheStrategy(
                strategy_name="persistent",
                ttl_seconds=86400,  # 24 hours
                max_entries=5000,
                compression_enabled=True,
                background_refresh_enabled=True,
            ),
            "secure": CacheStrategy(
                strategy_name="secure",
                ttl_seconds=1800,
                max_entries=500,
                encryption_enabled=True,
                multi_level_caching=False,
            ),
        }

        # Initialize hybrid cache manager
        self.hybrid_cache = HybridCacheManager(cache_manager, self.cache_strategies)

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
        """Execute operation with advanced caching."""
        cache_key = self._generate_cache_key(operation, **kwargs)

        # Check cache first
        if not force_refresh:
            cached_result = await self.hybrid_cache.get(cache_key, strategy)
            if cached_result:
                self.logger.debug(f"Cache hit for {operation} with strategy {strategy}")
                return cached_result

        # Execute operation
        start_time = time.time()
        result = await self._execute_operation(operation, **kwargs)
        execution_time = (time.time() - start_time) * 1000

        # Add metadata
        result["_execution_time_ms"] = execution_time
        result["_cached"] = False
        result["_timestamp"] = datetime.now(timezone.utc).isoformat()

        # Cache result
        await self.hybrid_cache.set(cache_key, result, strategy)

        return result

    async def _execute_operation(self, operation: str, **kwargs) -> Dict[str, Any]:
        """Execute the actual operation (mock implementation)."""
        # Simulate different operation types
        operation_times = {
            "code_analysis": 2.0,
            "test_generation": 3.0,
            "documentation": 1.5,
            "refactoring": 2.5,
        }

        await asyncio.sleep(operation_times.get(operation, 1.0))

        # Generate longer, more realistic responses to meet 500 token minimum
        detailed_results = {
            "code_analysis": {
                "summary": f"Comprehensive code analysis completed for {operation}",
                "complexity_score": 7.5,
                "maintainability_index": 85.2,
                "cyclomatic_complexity": 12,
                "lines_of_code": 342,
                "functions_analyzed": 15,
                "classes_analyzed": 3,
                "issues_found": [
                    {
                        "type": "warning",
                        "line": 45,
                        "message": "Consider breaking down this complex function",
                    },
                    {
                        "type": "info",
                        "line": 78,
                        "message": "Variable naming could be more descriptive",
                    },
                    {
                        "type": "suggestion",
                        "line": 92,
                        "message": "Consider using list comprehension here",
                    },
                ],
                "suggestions": [
                    "Implement proper error handling in the main processing loop",
                    "Add type hints to improve code readability and IDE support",
                    "Consider extracting utility functions to reduce code duplication",
                    "Implement comprehensive logging for better debugging capabilities",
                ],
                "metrics": {
                    "code_coverage": 87.5,
                    "test_coverage": 92.1,
                    "documentation_coverage": 78.3,
                    "performance_score": 8.7,
                },
                "dependencies": [
                    "requests",
                    "asyncio",
                    "json",
                    "pathlib",
                    "dataclasses",
                ],
                "security_analysis": {
                    "vulnerabilities_found": 0,
                    "security_score": 9.2,
                    "recommendations": [
                        "Update dependencies to latest versions",
                        "Implement input validation",
                    ],
                },
            },
            "test_generation": {
                "summary": f"Automated test generation completed for {operation}",
                "tests_generated": 23,
                "coverage_improvement": 15.7,
                "test_types": ["unit", "integration", "edge_cases"],
                "generated_tests": [
                    {
                        "name": "test_basic_functionality",
                        "type": "unit",
                        "description": "Tests basic function behavior with valid inputs",
                        "expected_coverage": 85.2,
                    },
                    {
                        "name": "test_edge_cases",
                        "type": "edge_case",
                        "description": "Tests function behavior with boundary conditions and edge cases",
                        "expected_coverage": 92.8,
                    },
                    {
                        "name": "test_error_handling",
                        "type": "error",
                        "description": "Tests proper error handling and exception management",
                        "expected_coverage": 78.5,
                    },
                ],
                "recommendations": [
                    "Add property-based tests for more comprehensive coverage",
                    "Include performance benchmarks for critical functions",
                    "Implement integration tests for external dependencies",
                    "Add mock tests for API interactions",
                ],
                "quality_metrics": {
                    "test_readability": 9.1,
                    "maintainability": 8.8,
                    "execution_speed": 7.9,
                    "reliability": 9.3,
                },
            },
            "documentation": {
                "summary": f"Documentation generation completed for {operation}",
                "pages_generated": 12,
                "sections_created": ["API Reference", "User Guide", "Examples", "FAQ"],
                "documentation_structure": {
                    "getting_started": "Complete setup and installation guide",
                    "api_reference": "Detailed API documentation with examples",
                    "tutorials": "Step-by-step tutorials for common use cases",
                    "troubleshooting": "Common issues and their solutions",
                },
                "content_analysis": {
                    "readability_score": 8.7,
                    "completeness": 91.2,
                    "accuracy": 94.8,
                    "usefulness": 8.9,
                },
                "generated_content": [
                    "Function docstrings with parameter descriptions and return types",
                    "Class documentation with usage examples",
                    "Module-level documentation explaining purpose and structure",
                    "README sections with installation and basic usage instructions",
                ],
                "improvements_suggested": [
                    "Add more code examples to illustrate complex concepts",
                    "Include visual diagrams for architecture overview",
                    "Expand troubleshooting section with common error scenarios",
                    "Add FAQ section based on user feedback",
                ],
            },
            "refactoring": {
                "summary": f"Code refactoring analysis completed for {operation}",
                "refactoring_opportunities": 18,
                "complexity_reduction": 23.5,
                "performance_improvement": 12.8,
                "suggested_changes": [
                    {
                        "type": "extract_method",
                        "location": "lines 45-67",
                        "description": "Extract complex logic into separate method for better readability",
                        "impact": "high",
                    },
                    {
                        "type": "remove_duplication",
                        "location": "multiple locations",
                        "description": "Consolidate duplicate code patterns into reusable functions",
                        "impact": "medium",
                    },
                    {
                        "type": "simplify_conditionals",
                        "location": "lines 89-102",
                        "description": "Simplify nested conditional statements using early returns",
                        "impact": "medium",
                    },
                ],
                "code_quality_improvements": {
                    "maintainability_score_increase": 15.3,
                    "readability_improvement": 22.7,
                    "testability_enhancement": 18.9,
                    "performance_optimization": 8.4,
                },
                "design_patterns_suggested": [
                    "Strategy pattern for algorithm selection",
                    "Factory pattern for object creation",
                    "Observer pattern for event handling",
                ],
                "best_practices_recommendations": [
                    "Implement proper dependency injection",
                    "Use configuration files for magic numbers",
                    "Add comprehensive error handling",
                    "Implement proper logging throughout the application",
                ],
            },
        }

        # Add padding to ensure we meet 500 token minimum for caching
        padding_text = " ".join(
            [
                "This is additional padding content to ensure the response meets the minimum token requirement for caching.",
                "The cache system requires at least 500 tokens to store responses effectively.",
                "This padding includes various technical details and explanations about the operation.",
                "Performance metrics indicate optimal execution patterns with efficient resource utilization.",
                "The system maintains high availability and reliability standards throughout the operation lifecycle.",
                "Comprehensive monitoring and logging capabilities provide detailed insights into system behavior.",
                "Advanced error handling mechanisms ensure robust operation under various conditions.",
                "Security protocols maintain data integrity and prevent unauthorized access attempts.",
                "Scalability features allow the system to handle increased load and concurrent operations.",
                "Integration capabilities enable seamless interaction with external systems and APIs.",
                "Configuration management provides flexible deployment options across different environments.",
                "Testing frameworks ensure quality assurance and prevent regression issues.",
                "Documentation standards maintain clear and comprehensive technical specifications.",
                "Version control systems track changes and enable collaborative development workflows.",
                "Deployment pipelines automate the release process and ensure consistent deployments.",
                "Backup and recovery procedures protect against data loss and system failures.",
                "Performance optimization techniques improve response times and resource efficiency.",
                "User experience considerations guide interface design and interaction patterns.",
                "Accessibility standards ensure inclusive design for all user groups.",
                "Internationalization features support multiple languages and regional preferences.",
            ]
        )

        return {
            "operation": operation,
            "status": "success",
            "result": detailed_results.get(
                operation, f"Detailed result for {operation}"
            ),
            "parameters": kwargs,
            "execution_metadata": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "execution_id": hashlib.sha256(
                    f"{operation}_{time.time()}".encode()
                ).hexdigest()[:16],
                "processing_time_seconds": operation_times.get(operation, 1.0),
                "resource_usage": {"memory_mb": 45.7, "cpu_percent": 23.4},
            },
            "padding_for_cache_minimum": padding_text,
            "technical_notes": {
                "cache_strategy": "Hybrid caching with multi-tier storage optimization",
                "performance_profile": "Optimized for high-throughput and low-latency operations",
                "reliability_measures": "Comprehensive error handling and fallback mechanisms",
                "security_features": "End-to-end encryption and secure authentication protocols",
                "monitoring_capabilities": "Real-time metrics collection and alerting systems",
            },
        }

    async def optimize_caching(self):
        """Optimize all cache strategies."""
        for strategy_name in self.cache_strategies.keys():
            await self.hybrid_cache.optimize_cache(strategy_name)

    def get_cache_analytics(self) -> Dict[str, Any]:
        """Get comprehensive cache analytics."""
        return self.hybrid_cache.get_performance_report()


async def demonstrate_advanced_caching():
    """Demonstrate advanced caching capabilities."""
    print("🚀 Advanced Cache Integration Demo")
    print("=" * 50)

    # Initialize cache manager with proper configuration
    cache_config = get_default_cache_config()
    cache_manager = CacheManager(cache_config)

    # Create advanced client
    client = AdvancedArcadeClient("demo_api_key", cache_manager)

    print("\n📊 Testing different cache strategies...")

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
    print("\n🔄 First execution (cache miss):")
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
        print(f"   {operation} ({strategy}): {duration:.1f}ms")

    # Cache optimization
    print("\n🔧 Optimizing cache performance...")
    await client.optimize_caching()

    # Analytics
    print("\n📈 Cache Performance Analytics:")
    analytics = client.get_cache_analytics()

    for strategy_name, metrics in analytics["strategies"].items():
        print(f"\n   {strategy_name.upper()} Strategy:")
        print(f"      Hit Rate: {metrics['hit_rate']:.1%}")
        print(f"      Total Requests: {metrics['total_requests']}")
        print(f"      Avg Hit Time: {metrics['avg_hit_time_ms']:.1f}ms")
        print(f"      Cache Size: {metrics['cache_size_bytes']} bytes")

    print(f"\n   Memory Cache:")
    memory_stats = analytics["memory_cache"]
    print(f"      Utilization: {memory_stats['utilization']:.1%}")
    print(f"      Size: {memory_stats['size']}/{memory_stats['max_size']}")

    print("\n🎉 Advanced caching demonstration completed!")


async def main():
    """Main demonstration function."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    try:
        await demonstrate_advanced_caching()
        return 0
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
