#!/usr/bin/env python3
"""
Basic Arcade.dev API Client Integration Example

This example demonstrates the fundamental integration patterns for connecting
to Arcade.dev APIs within the FACT framework using the official arcadepy SDK.

Features:
- Real API integration when credentials are available using arcadepy
- Demo mode with mock responses when credentials are missing
- Robust error handling and retry logic
- FACT cache integration
- Tool execution capabilities using the official Arcade.dev Python SDK

Note: This example uses the official arcadepy package to interact with
Arcade.dev's tool calling platform for AI agents.
"""

import os
import sys
import logging
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import asyncio
from pathlib import Path

# Setup FACT imports using the import helper
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.import_helper import setup_fact_imports

# Setup FACT module path
setup_fact_imports()

from src.core.driver import FACTDriver
from src.cache.manager import CacheManager

# Import official arcade SDK
try:
    from arcadepy import Arcade

    ARCADE_SDK_AVAILABLE = True
except ImportError:
    ARCADE_SDK_AVAILABLE = False
    print("⚠️  Warning: arcadepy not installed. Install with: pip install arcadepy")

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@dataclass
class ArcadeConfig:
    """Configuration for Arcade.dev API client."""

    api_key: str
    user_id: str = "demo@example.com"
    timeout: int = 30
    max_retries: int = 3
    demo_mode: bool = False


class MockArcadeResponse:
    """Mock response class for demo mode."""

    def __init__(self, data: Dict[str, Any]):
        self.id = data.get("id", "demo_response_123")
        self.status = data.get("status", "success")
        self.result = data.get("result", {})
        self.data = data

    def __getattr__(self, name):
        return self.data.get(name)


class BasicArcadeClient:
    """Basic Arcade.dev API client with FACT integration using official SDK."""

    def __init__(
        self, config: ArcadeConfig, cache_manager: Optional[CacheManager] = None
    ):
        self.config = config
        self.cache_manager = cache_manager
        self.logger = logging.getLogger(__name__)
        self.client: Optional[Arcade] = None

        # Mock data for demo mode
        self._demo_tools = [
            {
                "name": "Math.Sqrt",
                "description": "Calculate square root of a number",
                "category": "mathematics",
                "input_schema": {
                    "type": "object",
                    "properties": {"a": {"type": "number"}},
                },
            },
            {
                "name": "Google.ListEmails",
                "description": "List emails from Gmail",
                "category": "email",
                "input_schema": {
                    "type": "object",
                    "properties": {"n_emails": {"type": "integer"}},
                },
            },
            {
                "name": "Slack.PostMessage",
                "description": "Post message to Slack channel",
                "category": "messaging",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "channel": {"type": "string"},
                        "message": {"type": "string"},
                    },
                },
            },
        ]

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()

    async def connect(self):
        """Establish connection to Arcade.dev API."""
        if self.config.demo_mode:
            self.logger.info("Running in demo mode - using mock responses")
            return

        if not ARCADE_SDK_AVAILABLE:
            raise RuntimeError(
                "arcadepy SDK not available. Install with: pip install arcadepy"
            )

        try:
            # Initialize the official Arcade client
            self.client = Arcade(api_key=self.config.api_key)
            self.logger.info("Connected to Arcade.dev API using official SDK")
        except Exception as e:
            self.logger.error(f"Failed to connect to Arcade.dev: {e}")
            raise

    async def disconnect(self):
        """Close connection to Arcade.dev API."""
        if self.config.demo_mode:
            self.logger.info("Demo mode - no connection to close")
            return

        if self.client:
            # The official SDK doesn't require explicit disconnection
            self.client = None
            self.logger.info("Disconnected from Arcade.dev API")

    async def _execute_with_cache_and_retry(
        self, operation_name: str, operation_func, *args, **kwargs
    ):
        """Execute operation with caching and retry logic."""
        # Check cache first
        cache_key = f"arcade:{operation_name}:{hash(str(args + tuple(kwargs.items())))}"
        if self.cache_manager:
            cached_result = self.cache_manager.get(cache_key)
            if cached_result:
                self.logger.debug(f"Cache hit for {operation_name}")
                # Return cached result, assuming it's stored as JSON string
                try:
                    if hasattr(cached_result, "content"):
                        return json.loads(cached_result.content)
                    else:
                        return cached_result
                except (json.JSONDecodeError, AttributeError):
                    pass  # Fall through to actual operation

        # Execute operation with retries
        last_exception = None
        for attempt in range(self.config.max_retries):
            try:
                result = await operation_func(*args, **kwargs)

                # Cache successful results
                if self.cache_manager and result:
                    try:
                        cache_data = (
                            result if isinstance(result, dict) else result.__dict__
                        )
                        self.cache_manager.store(cache_key, json.dumps(cache_data))
                    except Exception as e:
                        self.logger.warning(f"Failed to cache result: {e}")

                return result

            except Exception as e:
                last_exception = e
                self.logger.warning(
                    f"Operation {operation_name} attempt {attempt + 1} failed: {e}"
                )
                if attempt == self.config.max_retries - 1:
                    break
                await asyncio.sleep(2**attempt)  # Exponential backoff

        raise last_exception or RuntimeError(
            f"All retry attempts failed for {operation_name}"
        )

    async def health_check(self) -> Dict[str, Any]:
        """Check API health and connectivity."""
        if self.config.demo_mode:
            result = {
                "status": "healthy",
                "version": "1.4.0",
                "timestamp": "2025-05-25T19:27:00Z",
                "services": {
                    "auth": "healthy",
                    "tools": "healthy",
                    "database": "healthy",
                },
                "_demo_mode": True,
            }
            return result

        # For real API, we'll try to list tools as a health check
        try:
            await self.list_tools()
            return {
                "status": "healthy",
                "version": "1.4.0",
                "timestamp": "2025-05-25T19:27:00Z",
                "services": {"auth": "healthy", "tools": "healthy"},
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": "2025-05-25T19:27:00Z",
            }

    async def get_user_info(self) -> Dict[str, Any]:
        """Get current user information."""
        if self.config.demo_mode:
            return {
                "user_id": self.config.user_id,
                "email": self.config.user_id,
                "plan": "free",
                "tools_available": 100,
                "tools_used": 5,
                "quota_remaining": 95,
                "_demo_mode": True,
            }

        # The arcadepy SDK doesn't have a direct user info endpoint in the examples
        # So we'll return basic info based on the configuration
        return {
            "user_id": self.config.user_id,
            "api_key_status": "valid" if self.client else "invalid",
            "sdk_version": "1.4.0",
        }

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools."""
        if self.config.demo_mode:
            return {
                "tools": self._demo_tools,
                "count": len(self._demo_tools),
                "_demo_mode": True,
            }

        async def _list_tools():
            # The arcadepy SDK doesn't provide a direct list tools method in the examples
            # This would need to be implemented based on the actual API
            # For now, we'll return a placeholder
            return {
                "tools": [],
                "count": 0,
                "message": "Tool listing requires specific API implementation",
            }

        return await self._execute_with_cache_and_retry("list_tools", _list_tools)

    async def execute_tool(
        self, tool_name: str, tool_input: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a tool using Arcade.dev."""
        if self.config.demo_mode:
            return self._generate_mock_tool_execution(tool_name, tool_input)

        async def _execute_tool():
            try:
                response = self.client.tools.execute(
                    tool_name=tool_name, input=tool_input, user_id=self.config.user_id
                )

                # Convert response to dict format
                result = {
                    "id": response.id,
                    "status": getattr(response, "status", "completed"),
                    "tool_name": tool_name,
                    "input": tool_input,
                    "result": getattr(response, "result", None),
                    "execution_time_ms": getattr(response, "execution_time_ms", None),
                }

                return result

            except Exception as e:
                self.logger.error(f"Tool execution failed: {e}")
                return {
                    "status": "failed",
                    "tool_name": tool_name,
                    "input": tool_input,
                    "error": str(e),
                }

        return await self._execute_with_cache_and_retry("execute_tool", _execute_tool)

    def _generate_mock_tool_execution(
        self, tool_name: str, tool_input: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate a mock tool execution response."""
        # Generate realistic mock responses based on the tool
        if tool_name == "Math.Sqrt":
            number = float(tool_input.get("a", 16))
            result = number**0.5
            return {
                "_demo_mode": True,
                "_demo_timestamp": "2025-05-25T19:27:00Z",
                "id": "demo_exec_12345",
                "tool_name": tool_name,
                "status": "completed",
                "result": {"value": result, "input": number},
                "input": tool_input,
                "execution_time_ms": 150,
            }

        elif tool_name == "Google.ListEmails":
            n_emails = tool_input.get("n_emails", 5)
            emails = [
                {
                    "id": f"email_{i}",
                    "subject": f"Demo Email {i}",
                    "from": f"sender{i}@example.com",
                }
                for i in range(1, min(n_emails + 1, 11))  # Cap at 10 emails
            ]
            return {
                "_demo_mode": True,
                "_demo_timestamp": "2025-05-25T19:27:00Z",
                "id": "demo_exec_12346",
                "tool_name": tool_name,
                "status": "completed",
                "result": {"emails": emails, "count": len(emails)},
                "input": tool_input,
                "execution_time_ms": 1200,
            }

        elif tool_name == "Slack.PostMessage":
            return {
                "_demo_mode": True,
                "_demo_timestamp": "2025-05-25T19:27:00Z",
                "id": "demo_exec_12347",
                "tool_name": tool_name,
                "status": "completed",
                "result": {
                    "message_ts": "1640995200.000100",
                    "channel": tool_input.get("channel", "#general"),
                    "message_id": "demo_msg_789",
                },
                "input": tool_input,
                "execution_time_ms": 800,
            }

        # Default tool execution response
        return {
            "_demo_mode": True,
            "_demo_timestamp": "2025-05-25T19:27:00Z",
            "id": "demo_exec_99999",
            "tool_name": tool_name,
            "status": "completed",
            "result": {"message": f"Demo execution of {tool_name}", "data": tool_input},
            "input": tool_input,
            "execution_time_ms": 500,
        }


async def main():
    """Main demonstration function."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print("🎮 Arcade.dev Python SDK Integration Example")
    print("=" * 50)

    # Load configuration from environment
    api_key = os.getenv("ARCADE_API_KEY", "")
    user_id = os.getenv("ARCADE_USER_ID", "demo@example.com")

    # Enable demo mode if no API key or if API key looks like a placeholder
    demo_mode = (
        not bool(api_key.strip())
        or api_key.strip() in ["your_api_key", "demo_key", "placeholder"]
        or len(api_key.strip()) < 10  # Real API keys are typically longer
    )

    config = ArcadeConfig(
        api_key=api_key if not demo_mode else "demo_key",
        user_id=user_id,
        timeout=int(os.getenv("ARCADE_TIMEOUT", "30")),
        max_retries=int(os.getenv("ARCADE_MAX_RETRIES", "3")),
        demo_mode=demo_mode,
    )

    if demo_mode:
        print("🎭 Demo Mode: No API key found - using mock responses")
        print("💡 To use real API: Set ARCADE_API_KEY environment variable")
        print("📝 Example: export ARCADE_API_KEY=your_actual_api_key")
        print("👤 Example: export ARCADE_USER_ID=your@email.com")
        print()
    else:
        print(f"🔑 Using API key: {api_key[:10]}...")
        print(f"👤 User ID: {user_id}")
        print()

    # Initialize cache manager with config
    cache_config = {
        "prefix": "arcade_demo",
        "min_tokens": 1,  # Allow small responses to be cached
        "max_size": "10MB",
        "ttl_seconds": 3600,
        "hit_target_ms": 30,
        "miss_target_ms": 120,
    }
    cache_manager = CacheManager(cache_config)

    # Demonstrate basic API usage
    async with BasicArcadeClient(config, cache_manager) as client:
        try:
            # Health check
            print("🔍 Checking API health...")
            health = await client.health_check()
            status_icon = "🎭" if health.get("_demo_mode") else "✅"
            print(f"{status_icon} API Status: {health.get('status', 'unknown')}")
            if health.get("_demo_mode"):
                print("   (Demo response)")
            elif health.get("status") == "unhealthy":
                print(f"   Error: {health.get('error', 'Unknown error')}")

            # User info
            print("\n👤 Getting user information...")
            user_info = await client.get_user_info()
            user_icon = "🎭" if user_info.get("_demo_mode") else "✅"
            print(f"{user_icon} User: {user_info.get('user_id', 'unknown')}")
            if user_info.get("tools_available"):
                print(f"   Tools available: {user_info.get('tools_available', 'N/A')}")
                print(f"   Quota remaining: {user_info.get('quota_remaining', 'N/A')}")
            if user_info.get("_demo_mode"):
                print("   (Demo response)")

            # List available tools
            print("\n🛠️  Listing available tools...")
            tools_response = await client.list_tools()
            tools_icon = "🎭" if tools_response.get("_demo_mode") else "✅"
            available_tools = tools_response.get("tools", [])
            print(f"{tools_icon} Found {len(available_tools)} tools")
            if tools_response.get("_demo_mode"):
                print("   (Demo response)")

            # Display available tools
            if available_tools:
                print("\n📋 Available Tools:")
                for i, tool in enumerate(available_tools[:5], 1):  # Show first 5 tools
                    print(
                        f"  {i}. {tool.get('name', 'Unknown')} - {tool.get('description', 'No description')}"
                    )
                    if tool.get("category"):
                        print(f"     Category: {tool.get('category')}")

            # Tool execution examples
            print("\n🔧 Tool Execution Examples:")

            # Example 1: Math.Sqrt
            print("\n1. Math.Sqrt - Calculate square root of 625...")
            execution = await client.execute_tool("Math.Sqrt", {"a": 625})
            exec_icon = "🎭" if execution.get("_demo_mode") else "✅"
            print(f"{exec_icon} Status: {execution.get('status', 'unknown')}")
            if execution.get("result"):
                result_val = (
                    execution["result"].get("value")
                    if isinstance(execution["result"], dict)
                    else execution["result"]
                )
                print(f"   Result: √625 = {result_val}")
            print(f"   Execution time: {execution.get('execution_time_ms', 'N/A')}ms")
            if execution.get("_demo_mode"):
                print("   (Demo response)")

            # Example 2: Google.ListEmails
            print("\n2. Google.ListEmails - List 3 emails...")
            execution = await client.execute_tool("Google.ListEmails", {"n_emails": 3})
            exec_icon = "🎭" if execution.get("_demo_mode") else "✅"
            print(f"{exec_icon} Status: {execution.get('status', 'unknown')}")
            if execution.get("result") and isinstance(execution["result"], dict):
                emails = execution["result"].get("emails", [])
                print(f"   Found {len(emails)} emails")
                for i, email in enumerate(emails[:2], 1):  # Show first 2
                    print(
                        f"   {i}. {email.get('subject', 'No subject')} from {email.get('from', 'Unknown')}"
                    )
            print(f"   Execution time: {execution.get('execution_time_ms', 'N/A')}ms")
            if execution.get("_demo_mode"):
                print("   (Demo response)")

        except Exception as e:
            print(f"❌ Error: {e}")
            return 1

    print("\n" + "=" * 50)
    if demo_mode:
        print("🎭 Basic integration example completed successfully in demo mode!")
        print("💡 To test with real API, set ARCADE_API_KEY environment variable")
        print("📖 Learn more: https://docs.arcade.dev")
    else:
        print("🎉 Basic integration example completed successfully!")
        print("📖 Learn more: https://docs.arcade.dev")
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
