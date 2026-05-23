#!/usr/bin/env python3
"""
Advanced Tool Usage Example for Arcade.dev Integration

This example demonstrates sophisticated tool calling patterns including:
- Chained tool executions
- Conditional tool branching
- Tool orchestration patterns
- Dynamic tool generation
- Result aggregation and transformation
"""

import os
import sys
import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass, field
from pathlib import Path
from functools import wraps
import json
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

# Setup FACT imports using the import helper
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.import_helper import setup_fact_imports

# Setup FACT module path
setup_fact_imports()

from src.core.driver import FACTDriver
from src.cache.manager import CacheManager
from src.tools.executor import ToolExecutor
from src.tools.decorators import get_tool_registry
from src.monitoring.metrics import MetricsCollector
from src.core.errors import ToolExecutionError


# Define mock ArcadeClient for demo mode
class MockArcadeClient:
    def __init__(self, api_key: str = None, **kwargs):
        self.api_key = api_key
        self._demo_mode = True

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def execute_tool(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        # Mock response for demo
        tool_name = payload.get("tool", "unknown")
        return {
            "result": {
                "success": True,
                "data": f"Mock result from {tool_name}",
                "execution_time": 0.1,
            }
        }


# Try to import real ArcadeClient, fall back to mock
try:
    from src.arcade.client import ArcadeClient as RealArcadeClient

    REAL_ARCADE_AVAILABLE = True
except ImportError:
    REAL_ARCADE_AVAILABLE = False


# Create a wrapper that tries real client first, falls back to mock
class ArcadeClient:
    def __new__(cls, api_key: str = None, **kwargs):
        # Check if we should use demo mode
        demo_mode = api_key == "demo" or not api_key or not REAL_ARCADE_AVAILABLE

        if demo_mode:
            return MockArcadeClient(api_key, **kwargs)
        else:
            # Try to create real client, fall back to mock if it fails
            try:
                return RealArcadeClient(api_key, **kwargs)
            except ImportError:
                print("🎯 Falling back to demo mode due to missing dependencies")
                return MockArcadeClient(api_key, **kwargs)


ARCADE_AVAILABLE = REAL_ARCADE_AVAILABLE


# Mock classes for demo mode
class MockToolExecutor:
    """Mock tool executor for demo mode."""

    async def execute(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        await asyncio.sleep(0.1)  # Simulate processing
        return {
            "success": True,
            "data": f"Mock execution result for {tool_name}",
            "execution_time": 0.1,
        }


class MockMetricsCollector:
    """Mock metrics collector for demo mode."""

    async def record_gauge(self, name: str, value: float, tags: Dict[str, str] = None):
        pass

    async def record_counter(self, name: str, value: int = 1):
        pass


@dataclass
class ToolChainStep:
    """Represents a single step in a tool execution chain."""

    tool_name: str
    params: Dict[str, Any]
    condition: Optional[Callable[[Dict[str, Any]], bool]] = None
    transform: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None
    retry_count: int = 3
    timeout: float = 30.0


@dataclass
class ToolOrchestrationResult:
    """Result of tool orchestration execution."""

    success: bool
    results: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    execution_time: float = 0.0
    steps_completed: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class AdvancedToolOrchestrator:
    """Advanced tool orchestration system with chaining and conditional execution."""

    def __init__(self, arcade_client: ArcadeClient, cache_manager: CacheManager):
        self.arcade_client = arcade_client
        self.cache_manager = cache_manager

        # Create demo-compatible tool executor
        try:
            self.tool_executor = ToolExecutor(arcade_client=arcade_client)
        except Exception:
            # Create minimal mock executor for demo
            self.tool_executor = MockToolExecutor()

        try:
            self.metrics = MetricsCollector()
        except Exception:
            # Create minimal mock metrics collector
            self.metrics = MockMetricsCollector()

        self.logger = logging.getLogger(__name__)
        self.thread_pool = ThreadPoolExecutor(max_workers=4)

        # Dynamic tool registry
        self.dynamic_tools: Dict[str, Callable] = {}

    async def __aenter__(self):
        """Async context manager entry."""
        await self.arcade_client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.arcade_client.__aexit__(exc_type, exc_val, exc_tb)
        self.thread_pool.shutdown(wait=True)

    def register_dynamic_tool(self, name: str, func: Callable):
        """Register a dynamically created tool."""
        self.dynamic_tools[name] = func
        self.logger.info(f"Registered dynamic tool: {name}")

    async def execute_tool_chain(
        self,
        steps: List[ToolChainStep],
        parallel: bool = False,
        aggregate_results: bool = True,
    ) -> ToolOrchestrationResult:
        """Execute a chain of tools with conditional branching and result aggregation."""
        start_time = time.time()
        result = ToolOrchestrationResult(success=True)

        try:
            if parallel:
                # Execute steps in parallel where possible
                result = await self._execute_parallel_chain(steps, result)
            else:
                # Execute steps sequentially
                result = await self._execute_sequential_chain(steps, result)

            if aggregate_results:
                result.metadata["aggregated_data"] = await self._aggregate_results(
                    result.results
                )

        except Exception as e:
            result.success = False
            result.errors.append(f"Chain execution failed: {str(e)}")
            self.logger.error(f"Tool chain execution error: {e}")

        finally:
            result.execution_time = time.time() - start_time
            await self._record_metrics(result)

        return result

    async def _execute_sequential_chain(
        self, steps: List[ToolChainStep], result: ToolOrchestrationResult
    ) -> ToolOrchestrationResult:
        """Execute tool chain sequentially."""
        context = {}

        for i, step in enumerate(steps):
            try:
                # Check condition if provided
                if step.condition and not step.condition(context):
                    self.logger.info(f"Skipping step {i}: condition not met")
                    continue

                # Execute tool with retries
                step_result = await self._execute_tool_with_retry(step, context)

                # Transform result if transform function provided
                if step.transform:
                    step_result = step.transform(step_result)

                # Update context and results
                context.update(step_result)
                result.results.append(step_result)
                result.steps_completed += 1

                self.logger.info(f"Completed step {i}: {step.tool_name}")

            except Exception as e:
                error_msg = f"Step {i} ({step.tool_name}) failed: {str(e)}"
                result.errors.append(error_msg)
                self.logger.error(error_msg)

                # Decide whether to continue or abort chain
                if not self._should_continue_on_error(step, e):
                    result.success = False
                    break

        return result

    async def _execute_parallel_chain(
        self, steps: List[ToolChainStep], result: ToolOrchestrationResult
    ) -> ToolOrchestrationResult:
        """Execute independent tool steps in parallel."""
        # Group steps by dependencies (simplified: assume all independent for now)
        tasks = []

        for step in steps:
            task = asyncio.create_task(self._execute_tool_with_retry(step, {}))
            tasks.append((step, task))

        # Wait for all tasks to complete
        for step, task in tasks:
            try:
                step_result = await task
                if step.transform:
                    step_result = step.transform(step_result)

                result.results.append(step_result)
                result.steps_completed += 1

            except Exception as e:
                error_msg = f"Parallel step ({step.tool_name}) failed: {str(e)}"
                result.errors.append(error_msg)
                self.logger.error(error_msg)

        return result

    async def _execute_tool_with_retry(
        self, step: ToolChainStep, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a single tool with retry logic."""
        last_error = None

        for attempt in range(step.retry_count):
            try:
                # Merge step params with context
                merged_params = {**step.params, **context}

                # Check if it's a dynamic tool
                if step.tool_name in self.dynamic_tools:
                    return await self._execute_dynamic_tool(
                        step.tool_name, merged_params
                    )

                # Execute via Arcade.dev or local executor
                if step.tool_name.startswith("arcade:"):
                    tool_name = step.tool_name[7:]  # Remove 'arcade:' prefix
                    return await self._execute_arcade_tool(tool_name, merged_params)
                else:
                    return await self._execute_local_tool(step.tool_name, merged_params)

            except Exception as e:
                last_error = e
                if attempt < step.retry_count - 1:
                    wait_time = 2**attempt
                    self.logger.warning(
                        f"Tool {step.tool_name} attempt {attempt + 1} failed, retrying in {wait_time}s"
                    )
                    await asyncio.sleep(wait_time)

        raise last_error

    async def _execute_arcade_tool(
        self, tool_name: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute tool via Arcade.dev API."""
        payload = {
            "tool": tool_name,
            "parameters": params,
            "context": {"source": "fact_sdk", "timestamp": time.time()},
        }

        response = await self.arcade_client.execute_tool(payload)
        return response.get("result", {})

    async def _execute_local_tool(
        self, tool_name: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute tool locally using FACT executor."""
        return await self.tool_executor.execute(tool_name, params)

    async def _execute_dynamic_tool(
        self, tool_name: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute dynamically registered tool."""
        tool_func = self.dynamic_tools[tool_name]

        # Run in thread pool if not async
        if asyncio.iscoroutinefunction(tool_func):
            return await tool_func(**params)
        else:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                self.thread_pool, lambda: tool_func(**params)
            )

    def _should_continue_on_error(self, step: ToolChainStep, error: Exception) -> bool:
        """Determine if chain should continue after an error."""
        # Custom logic based on error type and step configuration
        if isinstance(error, ToolExecutionError) and error.is_recoverable:
            return True
        return False

    async def _aggregate_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate results from multiple tool executions."""
        aggregated = {
            "total_results": len(results),
            "success_count": sum(1 for r in results if r.get("success", True)),
            "combined_data": {},
            "metrics": {
                "execution_times": [r.get("execution_time", 0) for r in results],
                "data_sizes": [len(str(r)) for r in results],
            },
        }

        # Merge data from all results
        for result in results:
            if "data" in result:
                aggregated["combined_data"].update(result["data"])

        return aggregated

    async def _record_metrics(self, result: ToolOrchestrationResult):
        """Record execution metrics."""
        # Use the correct MetricsCollector method
        self.metrics.record_tool_execution(
            tool_name="tool_chain",
            success=result.success,
            execution_time=result.execution_time * 1000,  # Convert to milliseconds
            metadata={"steps_completed": result.steps_completed},
        )

        if result.errors:
            # Record error metrics using the correct method signature
            self.metrics.record_tool_execution(
                tool_name="tool_chain_errors",
                success=False,
                execution_time=0,
                metadata={"error_count": len(result.errors)},
            )

    async def create_conditional_branch(
        self,
        condition_tool: str,
        true_branch: List[ToolChainStep],
        false_branch: List[ToolChainStep],
    ) -> ToolOrchestrationResult:
        """Create conditional execution branches based on tool result."""
        # Execute condition tool
        condition_step = ToolChainStep(tool_name=condition_tool, params={})

        condition_result = await self._execute_tool_with_retry(condition_step, {})
        branch_condition = condition_result.get("condition_met", False)

        # Execute appropriate branch
        if branch_condition:
            self.logger.info("Executing true branch")
            return await self.execute_tool_chain(true_branch)
        else:
            self.logger.info("Executing false branch")
            return await self.execute_tool_chain(false_branch)

    def generate_dynamic_tool(
        self, name: str, template: str, parameters: Dict[str, Any]
    ) -> Callable:
        """Generate a dynamic tool from a template."""

        def dynamic_tool(**kwargs):
            # Simple template substitution for demonstration
            code = template.format(**parameters, **kwargs)

            # Execute the generated code (in a real implementation, use safer execution)
            local_vars = {}
            exec(code, {"__builtins__": {}}, local_vars)

            return local_vars.get("result", {})

        self.register_dynamic_tool(name, dynamic_tool)
        return dynamic_tool


# Example tool implementations for demonstration
def create_sample_tools(orchestrator: AdvancedToolOrchestrator):
    """Create sample dynamic tools for demonstration."""

    # Data validation tool
    def validate_data(
        data: Dict[str, Any] = None, schema: Dict[str, Any] = None, **kwargs
    ) -> Dict[str, Any]:
        """Validate data against schema."""
        # Use provided parameters or defaults from kwargs
        if data is None:
            data = kwargs.get("data", {"name": "Demo", "age": 25})
        if schema is None:
            schema = kwargs.get("schema", {"name": str, "age": int})

        errors = []
        for field, field_type in schema.items():
            if field not in data:
                errors.append(f"Missing field: {field}")
            elif not isinstance(data[field], field_type):
                errors.append(
                    f"Invalid type for {field}: expected {field_type.__name__}"
                )

        return {"valid": len(errors) == 0, "errors": errors, "data": data}

    # Data transformation tool
    def transform_data(
        transformations: List[str] = None, data: Dict[str, Any] = None, **kwargs
    ) -> Dict[str, Any]:
        """Apply transformations to data."""
        # Handle context from previous steps
        if data is None and "data" in kwargs:
            data = kwargs["data"]
        elif data is None:
            data = kwargs.get("context", {})

        if transformations is None:
            transformations = kwargs.get("transformations", ["add_timestamp"])

        result = data.copy() if data else {}

        for transform in transformations:
            if transform == "uppercase_strings":
                for key, value in result.items():
                    if isinstance(value, str):
                        result[key] = value.upper()
            elif transform == "add_timestamp":
                result["timestamp"] = time.time()

        return {"transformed_data": result}

    # Analysis tool
    async def analyze_results(
        results: List[Dict[str, Any]] = None, **kwargs
    ) -> Dict[str, Any]:
        """Analyze aggregated results."""
        await asyncio.sleep(0.1)  # Simulate async processing

        # Handle context from previous steps
        if results is None:
            results = kwargs.get("results", [])

        # If no results provided, create demo analysis
        if not results:
            results = [{"execution_time": 0.1, "success": True}]

        return {
            "analysis": {
                "total_items": len(results),
                "avg_processing_time": (
                    sum(r.get("execution_time", 0) for r in results) / len(results)
                    if results
                    else 0
                ),
                "error_rate": (
                    sum(1 for r in results if "error" in r) / len(results)
                    if results
                    else 0
                ),
            }
        }

    # Register tools
    orchestrator.register_dynamic_tool("validate_data", validate_data)
    orchestrator.register_dynamic_tool("transform_data", transform_data)
    orchestrator.register_dynamic_tool("analyze_results", analyze_results)


async def demonstrate_tool_chaining():
    """Demonstrate basic tool chaining."""
    print("🔗 Demonstrating Tool Chaining")

    # Create mock arcade client and cache manager with proper config
    arcade_client = ArcadeClient(api_key=os.getenv("ARCADE_API_KEY", "demo"))

    # Create cache config for demo
    cache_config = {
        "prefix": "demo_cache",
        "min_tokens": 100,
        "max_size": "50MB",
        "ttl_seconds": 3600,
        "hit_target_ms": 48,
        "miss_target_ms": 140,
    }
    cache_manager = CacheManager(cache_config)

    async with AdvancedToolOrchestrator(arcade_client, cache_manager) as orchestrator:
        # Create sample tools
        create_sample_tools(orchestrator)

        # Define tool chain
        steps = [
            ToolChainStep(
                tool_name="validate_data",
                params={
                    "data": {"name": "John", "age": 30},
                    "schema": {"name": str, "age": int},
                },
            ),
            ToolChainStep(
                tool_name="transform_data",
                params={"transformations": ["uppercase_strings", "add_timestamp"]},
                condition=lambda ctx: ctx.get(
                    "valid", False
                ),  # Only if validation passed
            ),
            ToolChainStep(tool_name="analyze_results", params={}),
        ]

        # Execute chain
        result = await orchestrator.execute_tool_chain(steps)

        print(f"✅ Chain completed: {result.steps_completed} steps")
        print(f"⏱️  Execution time: {result.execution_time:.2f}s")
        if result.errors:
            print(f"❌ Errors: {len(result.errors)}")


async def demonstrate_conditional_branching():
    """Demonstrate conditional tool branching."""
    print("\n🌿 Demonstrating Conditional Branching")

    arcade_client = ArcadeClient(api_key=os.getenv("ARCADE_API_KEY", "demo"))

    # Create cache config for demo
    cache_config = {
        "prefix": "demo_cache",
        "min_tokens": 100,
        "max_size": "50MB",
        "ttl_seconds": 3600,
        "hit_target_ms": 48,
        "miss_target_ms": 140,
    }
    cache_manager = CacheManager(cache_config)

    async with AdvancedToolOrchestrator(arcade_client, cache_manager) as orchestrator:
        create_sample_tools(orchestrator)

        # Create condition tool
        def check_condition(threshold: float = 0.5) -> Dict[str, Any]:
            import random

            value = random.random()
            return {"condition_met": value > threshold, "value": value}

        orchestrator.register_dynamic_tool("check_condition", check_condition)

        # Define branches
        true_branch = [
            ToolChainStep(
                tool_name="transform_data",
                params={
                    "data": {"status": "success"},
                    "transformations": ["add_timestamp"],
                },
            )
        ]

        false_branch = [
            ToolChainStep(
                tool_name="validate_data",
                params={"data": {"status": "failure"}, "schema": {"status": str}},
            )
        ]

        # Execute conditional branch
        result = await orchestrator.create_conditional_branch(
            "check_condition", true_branch, false_branch
        )

        print(f"✅ Branch completed: {result.success}")
        print(f"📊 Results: {len(result.results)} items")


async def demonstrate_dynamic_tool_generation():
    """Demonstrate dynamic tool generation."""
    print("\n🛠️ Demonstrating Dynamic Tool Generation")

    arcade_client = ArcadeClient(api_key=os.getenv("ARCADE_API_KEY", "demo"))

    # Create cache config for demo
    cache_config = {
        "prefix": "demo_cache",
        "min_tokens": 100,
        "max_size": "50MB",
        "ttl_seconds": 3600,
        "hit_target_ms": 48,
        "miss_target_ms": 140,
    }
    cache_manager = CacheManager(cache_config)

    async with AdvancedToolOrchestrator(arcade_client, cache_manager) as orchestrator:
        # Generate dynamic tool from template
        template = """
def calculate_{operation}(a, b):
    if '{operation}' == 'add':
        result = a + b
    elif '{operation}' == 'multiply':
        result = a * b
    else:
        result = 0
    return {{'result': result, 'operation': '{operation}'}}

result = calculate_{operation}({a}, {b})
"""

        # Generate calculator tool
        orchestrator.generate_dynamic_tool(
            "calculator", template, {"operation": "add", "a": 10, "b": 20}
        )

        # Execute generated tool
        steps = [ToolChainStep(tool_name="calculator", params={})]

        result = await orchestrator.execute_tool_chain(steps)

        print(f"✅ Dynamic tool executed: {result.success}")
        if result.results:
            print(f"🔢 Calculation result: {result.results[0]}")


async def main():
    """Main demonstration function."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Check for demo mode
    api_key = os.getenv("ARCADE_API_KEY", "demo")
    demo_mode = api_key == "demo" or not api_key or not REAL_ARCADE_AVAILABLE

    print("🚀 Advanced Tool Usage Example")
    print("=" * 50)

    if demo_mode:
        print("🎯 Running in DEMO MODE")
        print("   - Using mock Arcade client")
        print("   - No real API calls will be made")
        print("   - Set ARCADE_API_KEY environment variable for real API integration")
        print()
    else:
        print("🔗 Connected to Arcade.dev API")
        print(f"   - API Key: {api_key[:8]}...")
        print()

    try:
        # Run demonstrations
        await demonstrate_tool_chaining()
        await demonstrate_conditional_branching()
        await demonstrate_dynamic_tool_generation()

        print("\n🎉 All advanced tool usage examples completed successfully!")
        if demo_mode:
            print(
                "💡 To run with real API integration, set the ARCADE_API_KEY environment variable"
            )
        return 0

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
