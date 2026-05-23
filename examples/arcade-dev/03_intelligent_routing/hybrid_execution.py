#!/usr/bin/env python3
"""
Intelligent Routing and Hybrid Execution Example

This example demonstrates advanced routing strategies for tool execution,
allowing dynamic decision-making between local and remote execution modes.
"""

import os
import sys
import asyncio
import logging
import time
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

# Setup FACT imports using the import helper
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.import_helper import setup_fact_imports

# Setup FACT module path
setup_fact_imports()

from src.tools.decorators import Tool
from src.monitoring.metrics import MetricsCollector
from src.cache.manager import CacheManager

# Import Arcade client from basic integration
sys.path.insert(0, str(Path(__file__).parent.parent / "01_basic_integration"))
from basic_arcade_client import BasicArcadeClient, ArcadeConfig

# Create alias for compatibility
ArcadeClient = BasicArcadeClient


# Define classes that might not exist in the actual FACT implementation
@dataclass
class ToolCall:
    """Tool call data structure."""

    id: str
    name: str
    arguments: Dict[str, Any]
    user_id: Optional[str] = None


@dataclass
class ToolResult:
    """Tool execution result."""

    call_id: str
    tool_name: str
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    status_code: int = 200
    metadata: Optional[Dict[str, Any]] = None


# Mock ToolExecutor for this example
class MockToolExecutor:
    """Mock tool executor for local execution."""

    def __init__(self):
        self.registry = {}

    async def execute_tool_call(self, tool_call: ToolCall) -> ToolResult:
        """Execute a tool call locally."""
        start_time = time.time()

        # Check if we have a registered function for this tool
        tool_func = self.registry.get(tool_call.name)
        if not tool_func:
            return ToolResult(
                call_id=tool_call.id,
                tool_name=tool_call.name,
                success=False,
                error=f"Tool '{tool_call.name}' not found",
                execution_time_ms=(time.time() - start_time) * 1000,
                status_code=404,
            )

        try:
            # Execute the tool function
            result = tool_func(**tool_call.arguments)
            execution_time = (time.time() - start_time) * 1000

            return ToolResult(
                call_id=tool_call.id,
                tool_name=tool_call.name,
                success=True,
                data=result,
                execution_time_ms=execution_time,
                status_code=200,
                metadata={"execution_mode": "local"},
            )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            return ToolResult(
                call_id=tool_call.id,
                tool_name=tool_call.name,
                success=False,
                error=str(e),
                execution_time_ms=execution_time,
                status_code=500,
            )

    def register_tool(self, name: str, func):
        """Register a tool function."""
        self.registry[name] = func


# Replace ToolExecutor with our mock
ToolExecutor = MockToolExecutor


class ExecutionMode(Enum):
    """Execution mode enumeration."""

    LOCAL = "local"
    REMOTE = "remote"
    HYBRID = "hybrid"
    AUTO = "auto"


@dataclass
class RoutingRule:
    """Rule for routing tool execution."""

    tool_pattern: str  # Tool name pattern (supports wildcards)
    preferred_mode: ExecutionMode
    conditions: Dict[str, Any]  # Conditions for applying this rule
    priority: int = 0  # Higher priority rules are checked first


@dataclass
class ExecutionMetrics:
    """Metrics for execution performance tracking."""

    mode: ExecutionMode
    execution_time_ms: float
    success: bool
    error_type: Optional[str] = None
    tool_name: str = ""
    timestamp: float = 0.0

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


class IntelligentRouter:
    """
    Intelligent router for deciding between local and remote tool execution.

    Makes routing decisions based on tool characteristics, performance history,
    network conditions, and configurable rules.
    """

    def __init__(
        self,
        arcade_client: Optional[ArcadeClient] = None,
        cache_manager: Optional[CacheManager] = None,
    ):
        """
        Initialize intelligent router.

        Args:
            arcade_client: Arcade.dev client for remote execution
            cache_manager: Cache manager for performance data
        """
        self.arcade_client = arcade_client
        self.cache_manager = cache_manager
        self.local_executor = ToolExecutor()
        self.metrics_collector = MetricsCollector()
        self.logger = logging.getLogger(__name__)

        # Routing configuration
        self.routing_rules: List[RoutingRule] = []
        self.execution_history: List[ExecutionMetrics] = []
        self.performance_cache: Dict[str, Dict[str, float]] = {}

        # Performance thresholds
        self.local_timeout_threshold = 5.0  # seconds
        self.remote_timeout_threshold = 30.0  # seconds
        self.network_latency_threshold = 2.0  # seconds

        # Initialize default routing rules
        self._setup_default_routing_rules()

    def add_routing_rule(self, rule: RoutingRule) -> None:
        """
        Add a routing rule to the decision engine.

        Args:
            rule: Routing rule to add
        """
        self.routing_rules.append(rule)
        # Sort by priority (highest first)
        self.routing_rules.sort(key=lambda r: r.priority, reverse=True)

        self.logger.info(
            f"Added routing rule for pattern '{rule.tool_pattern}' "
            f"with mode {rule.preferred_mode.value}"
        )

    async def execute_tool(self, tool_call: ToolCall) -> ToolResult:
        """
        Execute tool with intelligent routing decision.

        Args:
            tool_call: Tool call to execute

        Returns:
            Tool execution result
        """
        start_time = time.time()

        try:
            # Determine optimal execution mode
            execution_mode = await self._determine_execution_mode(tool_call)

            self.logger.info(
                f"Executing tool '{tool_call.name}' using {execution_mode.value} mode"
            )

            # Execute based on determined mode
            if execution_mode == ExecutionMode.LOCAL:
                result = await self._execute_locally(tool_call)
            elif execution_mode == ExecutionMode.REMOTE:
                result = await self._execute_remotely(tool_call)
            elif execution_mode == ExecutionMode.HYBRID:
                result = await self._execute_hybrid(tool_call)
            else:  # AUTO mode
                result = await self._execute_auto(tool_call)

            # Record successful execution metrics
            execution_time = (time.time() - start_time) * 1000
            metrics = ExecutionMetrics(
                mode=execution_mode,
                execution_time_ms=execution_time,
                success=result.success,
                tool_name=tool_call.name,
            )

            await self._record_execution_metrics(metrics)

            return result

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000

            # Record failed execution metrics
            metrics = ExecutionMetrics(
                mode=(
                    execution_mode
                    if "execution_mode" in locals()
                    else ExecutionMode.LOCAL
                ),
                execution_time_ms=execution_time,
                success=False,
                error_type=type(e).__name__,
                tool_name=tool_call.name,
            )

            await self._record_execution_metrics(metrics)

            # Create error result
            return ToolResult(
                call_id=tool_call.id,
                tool_name=tool_call.name,
                success=False,
                error=str(e),
                execution_time_ms=execution_time,
                status_code=500,
            )

    async def _determine_execution_mode(self, tool_call: ToolCall) -> ExecutionMode:
        """
        Determine the optimal execution mode for a tool call.

        Args:
            tool_call: Tool call to analyze

        Returns:
            Optimal execution mode
        """
        # Check routing rules first
        for rule in self.routing_rules:
            if self._matches_rule(tool_call.name, rule):
                if await self._evaluate_rule_conditions(tool_call, rule):
                    self.logger.debug(
                        f"Tool '{tool_call.name}' matched rule: {rule.preferred_mode.value}"
                    )
                    return rule.preferred_mode

        # Performance-based decision
        performance_score = await self._calculate_performance_score(tool_call.name)

        # Network condition check
        network_latency = await self._check_network_latency()

        # Tool complexity analysis
        complexity_score = self._analyze_tool_complexity(tool_call)

        # Make decision based on weighted factors
        decision_score = (
            performance_score * 0.4
            + (1.0 - min(network_latency / self.network_latency_threshold, 1.0)) * 0.3
            + complexity_score * 0.3
        )

        self.logger.debug(
            f"Decision score for '{tool_call.name}': {decision_score:.3f}"
        )

        # Decision thresholds
        if decision_score > 0.7:
            return ExecutionMode.LOCAL
        elif decision_score < 0.3:
            return ExecutionMode.REMOTE
        else:
            return ExecutionMode.HYBRID

    async def _execute_locally(self, tool_call: ToolCall) -> ToolResult:
        """Execute tool locally using FACT executor."""
        try:
            return await self.local_executor.execute_tool_call(tool_call)
        except Exception as e:
            self.logger.warning(f"Local execution failed for '{tool_call.name}': {e}")
            # Fallback to remote if available
            if self.arcade_client:
                self.logger.info("Falling back to remote execution")
                return await self._execute_remotely(tool_call)
            raise

    async def _execute_remotely(self, tool_call: ToolCall) -> ToolResult:
        """Execute tool remotely via Arcade.dev."""
        if not self.arcade_client:
            raise RuntimeError(
                "Remote execution not available: Arcade client not configured"
            )

        try:
            start_time = time.time()

            # Execute via Arcade.dev
            arcade_result = await self.arcade_client.execute_tool(
                tool_name=tool_call.name, tool_input=tool_call.arguments
            )

            execution_time = (time.time() - start_time) * 1000

            # Convert Arcade result to ToolResult format
            success = arcade_result.get("status") != "failed"
            return ToolResult(
                call_id=tool_call.id,
                tool_name=tool_call.name,
                success=success,
                data=arcade_result.get("result"),
                error=arcade_result.get("error"),
                execution_time_ms=execution_time,
                status_code=200 if success else 500,
                metadata={
                    "execution_mode": "remote",
                    "arcade_execution_time": arcade_result.get("execution_time_ms"),
                    "user_id": tool_call.user_id,
                },
            )

        except Exception as e:
            self.logger.warning(f"Remote execution failed for '{tool_call.name}': {e}")
            # Fallback to local if possible
            self.logger.info("Falling back to local execution")
            return await self._execute_locally(tool_call)

    async def _execute_hybrid(self, tool_call: ToolCall) -> ToolResult:
        """
        Execute tool using hybrid approach (race between local and remote).

        Returns the first successful result, cancels the other.
        """
        self.logger.info(f"Executing '{tool_call.name}' in hybrid mode")

        # Create tasks for both execution modes
        local_task = asyncio.create_task(self._execute_locally(tool_call))
        remote_task = asyncio.create_task(self._execute_remotely(tool_call))

        try:
            # Wait for first completion
            done, pending = await asyncio.wait(
                [local_task, remote_task], return_when=asyncio.FIRST_COMPLETED
            )

            # Cancel pending tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            # Get result from completed task
            completed_task = done.pop()
            result = await completed_task

            # Determine which mode completed first
            winning_mode = "local" if completed_task == local_task else "remote"

            # Add hybrid execution metadata
            if result.metadata is None:
                result.metadata = {}
            result.metadata["execution_mode"] = "hybrid"
            result.metadata["winning_mode"] = winning_mode

            self.logger.info(f"Hybrid execution completed: {winning_mode} mode won")

            return result

        except Exception as e:
            # Cancel any remaining tasks
            for task in [local_task, remote_task]:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

            raise RuntimeError(f"Hybrid execution failed: {e}")

    async def _execute_auto(self, tool_call: ToolCall) -> ToolResult:
        """
        Execute tool in auto mode with intelligent retry and fallback.
        """
        # Start with performance-based decision
        performance_data = await self._get_performance_data(tool_call.name)

        if performance_data:
            # Use historical performance to decide
            local_avg = performance_data.get("local_avg_ms", float("inf"))
            remote_avg = performance_data.get("remote_avg_ms", float("inf"))

            if local_avg < remote_avg * 1.5:  # Local is significantly faster
                primary_mode = ExecutionMode.LOCAL
                fallback_mode = ExecutionMode.REMOTE
            else:
                primary_mode = ExecutionMode.REMOTE
                fallback_mode = ExecutionMode.LOCAL
        else:
            # No historical data, default to local first
            primary_mode = ExecutionMode.LOCAL
            fallback_mode = ExecutionMode.REMOTE

        # Try primary mode first
        try:
            if primary_mode == ExecutionMode.LOCAL:
                return await self._execute_locally(tool_call)
            else:
                return await self._execute_remotely(tool_call)
        except Exception as e:
            self.logger.warning(f"Primary mode ({primary_mode.value}) failed: {e}")

            # Try fallback mode
            try:
                if fallback_mode == ExecutionMode.LOCAL:
                    return await self._execute_locally(tool_call)
                else:
                    return await self._execute_remotely(tool_call)
            except Exception as fallback_error:
                self.logger.error(
                    f"Fallback mode ({fallback_mode.value}) also failed: {fallback_error}"
                )
                raise RuntimeError(
                    f"Both execution modes failed: {e}, {fallback_error}"
                )

    def _matches_rule(self, tool_name: str, rule: RoutingRule) -> bool:
        """Check if tool name matches routing rule pattern."""
        import fnmatch

        return fnmatch.fnmatch(tool_name, rule.tool_pattern)

    async def _evaluate_rule_conditions(
        self, tool_call: ToolCall, rule: RoutingRule
    ) -> bool:
        """Evaluate whether rule conditions are met."""
        conditions = rule.conditions

        # Check user-based conditions
        if "user_id" in conditions:
            allowed_users = conditions["user_id"]
            if isinstance(allowed_users, list):
                if tool_call.user_id not in allowed_users:
                    return False
            elif tool_call.user_id != allowed_users:
                return False

        # Check argument-based conditions
        if "argument_size" in conditions:
            max_size = conditions["argument_size"]
            args_size = len(str(tool_call.arguments))
            if args_size > max_size:
                return False

        # Check time-based conditions
        if "time_window" in conditions:
            import datetime

            time_window = conditions["time_window"]
            current_hour = datetime.datetime.now().hour

            if isinstance(time_window, dict):
                start_hour = time_window.get("start", 0)
                end_hour = time_window.get("end", 23)
                if not (start_hour <= current_hour <= end_hour):
                    return False

        return True

    async def _calculate_performance_score(self, tool_name: str) -> float:
        """Calculate performance score for a tool (0.0 to 1.0, higher is better for local)."""
        if tool_name in self.performance_cache:
            data = self.performance_cache[tool_name]
            local_avg = data.get("local_avg_ms", 1000)
            remote_avg = data.get("remote_avg_ms", 2000)

            # Score based on relative performance
            if remote_avg > 0:
                return min(remote_avg / (local_avg + remote_avg), 1.0)

        # Default score if no performance data
        return 0.5

    async def _check_network_latency(self) -> float:
        """Check current network latency to Arcade.dev."""
        if not self.arcade_client:
            return float("inf")

        try:
            start_time = time.time()
            # Simple ping-like check - use health check instead
            await self.arcade_client.health_check()
            return time.time() - start_time
        except:
            return float("inf")

    def _analyze_tool_complexity(self, tool_call: ToolCall) -> float:
        """Analyze tool complexity to inform routing decision."""
        complexity_score = 0.0

        # Argument complexity
        args_str = str(tool_call.arguments)
        if len(args_str) > 1000:
            complexity_score += 0.3
        elif len(args_str) > 100:
            complexity_score += 0.1

        # Tool name patterns indicating complexity
        complex_patterns = ["AI.", "ML.", "Analysis.", "Transform."]
        simple_patterns = ["Util.", "Helper.", "Cache."]

        for pattern in complex_patterns:
            if tool_call.name.startswith(pattern):
                complexity_score += 0.4
                break

        for pattern in simple_patterns:
            if tool_call.name.startswith(pattern):
                complexity_score -= 0.2
                break

        return max(0.0, min(1.0, complexity_score))

    async def _record_execution_metrics(self, metrics: ExecutionMetrics) -> None:
        """Record execution metrics for future routing decisions."""
        self.execution_history.append(metrics)

        # Update performance cache
        tool_name = metrics.tool_name
        if tool_name not in self.performance_cache:
            self.performance_cache[tool_name] = {
                "local_avg_ms": 0.0,
                "remote_avg_ms": 0.0,
                "local_count": 0,
                "remote_count": 0,
            }

        cache_data = self.performance_cache[tool_name]

        if metrics.mode == ExecutionMode.LOCAL and metrics.success:
            count = cache_data["local_count"]
            avg = cache_data["local_avg_ms"]
            cache_data["local_avg_ms"] = (avg * count + metrics.execution_time_ms) / (
                count + 1
            )
            cache_data["local_count"] = count + 1
        elif metrics.mode == ExecutionMode.REMOTE and metrics.success:
            count = cache_data["remote_count"]
            avg = cache_data["remote_avg_ms"]
            cache_data["remote_avg_ms"] = (avg * count + metrics.execution_time_ms) / (
                count + 1
            )
            cache_data["remote_count"] = count + 1

        # Record with metrics collector
        self.metrics_collector.record_tool_execution(
            tool_name=metrics.tool_name,
            success=metrics.success,
            execution_time=metrics.execution_time_ms,
            metadata={"execution_mode": metrics.mode.value},
        )

        # Cache performance data if cache manager available
        if self.cache_manager:
            cache_key = f"routing:performance:{tool_name}"
            # CacheManager uses store method, not set
            try:
                import json

                self.cache_manager.store(cache_key, json.dumps(cache_data))
            except Exception as e:
                import structlog

                logger = structlog.get_logger(__name__)
                logger.warning(f"Failed to cache performance data: {e}")

    async def _get_performance_data(self, tool_name: str) -> Optional[Dict[str, float]]:
        """Get cached performance data for a tool."""
        if tool_name in self.performance_cache:
            return self.performance_cache[tool_name]

        if self.cache_manager:
            cache_key = f"routing:performance:{tool_name}"
            try:
                # CacheManager uses retrieve method, not get
                cached_entry = self.cache_manager.retrieve(cache_key)
                if cached_entry:
                    import json

                    cached_data = json.loads(cached_entry.content)
                    self.performance_cache[tool_name] = cached_data
                    return cached_data
            except Exception as e:
                import structlog

                logger = structlog.get_logger(__name__)
                logger.warning(f"Failed to retrieve cached performance data: {e}")

        return None

    def _setup_default_routing_rules(self) -> None:
        """Set up default routing rules."""
        # High-performance tools should run locally
        self.add_routing_rule(
            RoutingRule(
                tool_pattern="Cache.*",
                preferred_mode=ExecutionMode.LOCAL,
                conditions={"argument_size": 1000},  # Small arguments only
                priority=100,
            )
        )

        # AI/ML tools prefer remote execution (more resources)
        self.add_routing_rule(
            RoutingRule(
                tool_pattern="AI.*",
                preferred_mode=ExecutionMode.REMOTE,
                conditions={},
                priority=90,
            )
        )

        # Analysis tools use hybrid approach
        self.add_routing_rule(
            RoutingRule(
                tool_pattern="Analysis.*",
                preferred_mode=ExecutionMode.HYBRID,
                conditions={},
                priority=80,
            )
        )

        # Utility tools run locally
        self.add_routing_rule(
            RoutingRule(
                tool_pattern="Util.*",
                preferred_mode=ExecutionMode.LOCAL,
                conditions={},
                priority=70,
            )
        )

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary for all tools."""
        summary = {
            "total_executions": len(self.execution_history),
            "tools_tracked": len(self.performance_cache),
            "mode_distribution": {},
            "average_execution_times": {},
            "success_rates": {},
        }

        # Calculate mode distribution
        mode_counts = {}
        for metrics in self.execution_history:
            mode = metrics.mode.value
            mode_counts[mode] = mode_counts.get(mode, 0) + 1

        total_executions = len(self.execution_history)
        if total_executions > 0:
            for mode, count in mode_counts.items():
                summary["mode_distribution"][mode] = count / total_executions

        # Calculate average execution times and success rates
        for tool_name, cache_data in self.performance_cache.items():
            summary["average_execution_times"][tool_name] = {
                "local_ms": cache_data.get("local_avg_ms", 0),
                "remote_ms": cache_data.get("remote_avg_ms", 0),
            }

        return summary


# Example tools for testing routing
@Tool(
    name="Cache_FastLookup",
    description="Fast cache lookup operation",
    parameters={"key": {"type": "string", "description": "Cache key to lookup"}},
    timeout_seconds=5,
)
def fast_cache_lookup(key: str) -> Dict[str, Any]:
    """Fast local cache operation."""
    time.sleep(0.1)  # Simulate fast operation
    return {"key": key, "value": f"cached_value_{key}", "hit": True}


@Tool(
    name="AI_ComplexAnalysis",
    description="Complex AI analysis requiring significant resources",
    parameters={
        "data": {"type": "object", "description": "Data to analyze"},
        "model_type": {"type": "string", "description": "AI model to use"},
    },
    timeout_seconds=60,
)
def complex_ai_analysis(data: Dict[str, Any], model_type: str) -> Dict[str, Any]:
    """Complex AI analysis operation."""
    time.sleep(2.0)  # Simulate complex processing
    return {
        "analysis_result": f"AI analysis with {model_type}",
        "processed_items": len(data.get("items", [])),
        "confidence": 0.95,
    }


@Tool(
    name="Util_StringHelper",
    description="Simple string utility function",
    parameters={"text": {"type": "string", "description": "Text to process"}},
    timeout_seconds=10,
)
def string_helper(text: str) -> Dict[str, Any]:
    """Simple string processing utility."""
    return {
        "length": len(text),
        "word_count": len(text.split()),
        "uppercase": text.upper(),
    }


async def main():
    """Main demonstration function."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print("🧠 Intelligent Routing and Hybrid Execution Example")
    print("=" * 53)

    # Initialize components
    cache_config = {
        "prefix": "intelligent_routing",
        "min_tokens": 500,
        "max_size": "10MB",
        "ttl_seconds": 3600,
        "hit_target_ms": 48,
        "miss_target_ms": 140,
    }
    cache_manager = CacheManager(cache_config)

    # Initialize Arcade client if configured
    arcade_client = None
    arcade_api_key = os.getenv("ARCADE_API_KEY")
    if arcade_api_key:
        config = ArcadeConfig(
            api_key=arcade_api_key,
            user_id=os.getenv("ARCADE_USER_ID", "demo@example.com"),
            demo_mode=False,
        )
        arcade_client = ArcadeClient(config, cache_manager)
        try:
            await arcade_client.connect()
            print("✅ Connected to Arcade.dev for remote execution")
        except Exception as e:
            print(f"⚠️  Arcade.dev connection failed: {e}")
            print("   Continuing with local-only execution")
            arcade_client = None
    else:
        print("ℹ️  No Arcade API key configured, using demo mode")
        # Create a demo mode client for testing
        config = ArcadeConfig(
            api_key="demo_key", user_id="demo@example.com", demo_mode=True
        )
        arcade_client = ArcadeClient(config, cache_manager)
        await arcade_client.connect()
        print("✅ Using demo mode for testing intelligent routing")

    # Initialize intelligent router
    router = IntelligentRouter(arcade_client, cache_manager)

    # Register tools with the local executor
    router.local_executor.register_tool("Cache_FastLookup", fast_cache_lookup)
    router.local_executor.register_tool("AI_ComplexAnalysis", complex_ai_analysis)
    router.local_executor.register_tool("Util_StringHelper", string_helper)

    # Add custom routing rules
    print("\n📋 Setting up custom routing rules...")

    router.add_routing_rule(
        RoutingRule(
            tool_pattern="Cache.*",
            preferred_mode=ExecutionMode.LOCAL,
            conditions={"argument_size": 500},
            priority=100,
        )
    )

    router.add_routing_rule(
        RoutingRule(
            tool_pattern="AI.*",
            preferred_mode=(
                ExecutionMode.REMOTE if arcade_client else ExecutionMode.LOCAL
            ),
            conditions={},
            priority=90,
        )
    )

    print("✅ Custom routing rules configured")

    # Test different execution scenarios
    test_cases = [
        {
            "name": "Fast cache lookup",
            "tool_call": ToolCall(
                id="test_1", name="Cache_FastLookup", arguments={"key": "user_123"}
            ),
        },
        {
            "name": "Complex AI analysis",
            "tool_call": ToolCall(
                id="test_2",
                name="AI_ComplexAnalysis",
                arguments={
                    "data": {"items": list(range(100))},
                    "model_type": "neural_network",
                },
            ),
        },
        {
            "name": "Simple string utility",
            "tool_call": ToolCall(
                id="test_3",
                name="Util_StringHelper",
                arguments={"text": "Hello, intelligent routing world!"},
            ),
        },
    ]

    print("\n🚀 Executing test cases with intelligent routing...")

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. {test_case['name']}")
        print("-" * (len(test_case["name"]) + 3))

        try:
            start_time = time.time()
            result = await router.execute_tool(test_case["tool_call"])
            total_time = (time.time() - start_time) * 1000

            if result.success:
                execution_mode = result.metadata.get("execution_mode", "unknown")
                winning_mode = result.metadata.get("winning_mode", "")

                print(
                    f"✅ Success ({execution_mode} mode{f', {winning_mode} won' if winning_mode else ''})"
                )
                print(
                    f"   Execution time: {result.execution_time_ms:.1f}ms (total: {total_time:.1f}ms)"
                )

                if result.data:
                    data_preview = str(result.data)[:100]
                    if len(str(result.data)) > 100:
                        data_preview += "..."
                    print(f"   Result: {data_preview}")
            else:
                print(f"❌ Failed: {result.error}")

        except Exception as e:
            print(f"❌ Error: {e}")

    # Performance summary
    print("\n📊 Performance Summary")
    print("-" * 20)

    summary = router.get_performance_summary()
    print(f"Total executions: {summary['total_executions']}")
    print(f"Tools tracked: {summary['tools_tracked']}")

    if summary["mode_distribution"]:
        print("\nExecution mode distribution:")
        for mode, percentage in summary["mode_distribution"].items():
            print(f"  {mode}: {percentage:.1%}")

    if summary["average_execution_times"]:
        print("\nAverage execution times by tool:")
        for tool_name, times in summary["average_execution_times"].items():
            local_time = times["local_ms"]
            remote_time = times["remote_ms"]
            print(f"  {tool_name}:")
            if local_time > 0:
                print(f"    Local: {local_time:.1f}ms")
            if remote_time > 0:
                print(f"    Remote: {remote_time:.1f}ms")

    # Cleanup
    if arcade_client:
        await arcade_client.disconnect()

    print("\n🎉 Intelligent routing example completed successfully!")
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
