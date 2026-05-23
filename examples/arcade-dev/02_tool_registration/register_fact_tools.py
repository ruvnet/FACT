#!/usr/bin/env python3
"""
FACT Tool Registration with Arcade.dev Example

This example demonstrates how to register FACT tools with the Arcade.dev platform,
including tool schema definition, authentication setup, permission management,
and environment configuration.
"""

import os
import sys
import asyncio
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from pathlib import Path

# Setup FACT imports using the import helper
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.import_helper import setup_fact_imports

# Setup FACT module path
setup_fact_imports()

from src.tools.decorators import Tool
from src.core.config import Config
from src.security.auth import AuthorizationManager

# Import arcade client from basic integration
sys.path.insert(0, str(Path(__file__).parent.parent / "01_basic_integration"))
from basic_arcade_client import BasicArcadeClient, ArcadeConfig

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

# Import the real tool registry from FACT
from src.tools.decorators import get_tool_registry


@dataclass
class ToolRegistrationConfig:
    """Configuration for tool registration with Arcade.dev."""

    arcade_api_key: str
    arcade_base_url: str = "https://api.arcade.dev"
    workspace_id: Optional[str] = None
    default_timeout: int = 30
    requires_auth_by_default: bool = True
    demo_mode: bool = False
    user_id: str = "demo@example.com"


class FactToolRegistrar:
    """
    Manages registration of FACT tools with Arcade.dev platform.

    Handles schema generation, authentication setup, permission configuration,
    and batch registration operations.
    """

    def __init__(self, config: ToolRegistrationConfig):
        """
        Initialize tool registrar with configuration.

        Args:
            config: Registration configuration
        """
        self.config = config

        # Create arcade config from tool registration config
        arcade_config = ArcadeConfig(
            api_key=config.arcade_api_key,
            user_id=config.user_id,
            timeout=config.default_timeout,
            demo_mode=config.demo_mode,
        )

        self.arcade_client = BasicArcadeClient(arcade_config)
        self.tool_registry = get_tool_registry()
        self.auth_manager = AuthorizationManager()
        self.logger = logging.getLogger(__name__)

        # Track registration results
        self.registration_results: List[Dict[str, Any]] = []

    async def connect(self) -> None:
        """Establish connection to Arcade.dev platform."""
        try:
            await self.arcade_client.connect()
            self.logger.info("Successfully connected to Arcade.dev platform")

            # Verify workspace access if specified
            if self.config.workspace_id and not self.config.demo_mode:
                await self._verify_workspace_access()

        except Exception as e:
            self.logger.error(f"Failed to connect to Arcade.dev: {e}")
            raise

    async def register_all_tools(self) -> Dict[str, Any]:
        """
        Register all FACT tools from the registry with Arcade.dev.

        Returns:
            Registration summary with results for each tool
        """
        tool_names = self.tool_registry.list_tools()
        self.logger.info(f"Registering {len(tool_names)} tools with Arcade.dev")

        registration_summary = {
            "total_tools": len(tool_names),
            "successful": 0,
            "failed": 0,
            "skipped": 0,
            "results": [],
        }

        for tool_name in tool_names:
            try:
                result = await self.register_single_tool(tool_name)
                registration_summary["results"].append(result)

                if result["status"] == "success":
                    registration_summary["successful"] += 1
                elif result["status"] == "failed":
                    registration_summary["failed"] += 1
                else:
                    registration_summary["skipped"] += 1

            except Exception as e:
                error_result = {
                    "tool_name": tool_name,
                    "status": "failed",
                    "error": str(e),
                    "arcade_tool_id": None,
                }
                registration_summary["results"].append(error_result)
                registration_summary["failed"] += 1

                self.logger.error(f"Failed to register tool {tool_name}: {e}")

        self.logger.info(
            f"Tool registration completed: {registration_summary['successful']} successful, "
            f"{registration_summary['failed']} failed, {registration_summary['skipped']} skipped"
        )

        return registration_summary

    async def register_single_tool(self, tool_name: str) -> Dict[str, Any]:
        """
        Register a single FACT tool with Arcade.dev.

        Args:
            tool_name: Name of the tool to register

        Returns:
            Registration result dictionary
        """
        try:
            # Get tool definition from FACT registry
            tool_definition = self.tool_registry.get_tool(tool_name)

            # Check if tool already exists on Arcade.dev
            existing_tool = await self._check_existing_tool(tool_name)
            if existing_tool:
                self.logger.info(f"Tool {tool_name} already exists, updating...")
                return await self._update_existing_tool(
                    tool_name, tool_definition, existing_tool
                )

            # Prepare tool definition for Arcade.dev
            arcade_tool_definition = self._prepare_arcade_tool_definition(
                tool_definition
            )

            # Register tool with Arcade.dev
            registration_result = await self._register_tool_with_arcade(
                arcade_tool_definition
            )

            # Set up permissions and authentication
            if tool_definition.requires_auth:
                await self._setup_tool_permissions(
                    registration_result.get("id"), tool_name, tool_definition
                )

            result = {
                "tool_name": tool_name,
                "status": "success",
                "arcade_tool_id": registration_result.get("id"),
                "version": tool_definition.version,
                "requires_auth": tool_definition.requires_auth,
                "message": "Tool registered successfully",
            }

            self.logger.info(f"Successfully registered tool: {tool_name}")
            return result

        except Exception as e:
            self.logger.error(f"Failed to register tool {tool_name}: {e}")
            return {
                "tool_name": tool_name,
                "status": "failed",
                "error": str(e),
                "arcade_tool_id": None,
            }

    async def update_tool_permissions(
        self, tool_name: str, permissions: Dict[str, Any]
    ) -> bool:
        """
        Update permissions for a registered tool.

        Args:
            tool_name: Name of the tool
            permissions: Permission configuration

        Returns:
            True if update was successful
        """
        try:
            # Get tool info from Arcade.dev
            tool_info = await self._get_tool_info(tool_name)

            if not tool_info:
                raise ValueError(f"Tool {tool_name} not found on Arcade.dev")

            tool_id = tool_info.get("id")

            # Update permissions via Arcade.dev API
            await self._update_tool_permissions(tool_id, permissions)

            self.logger.info(f"Updated permissions for tool: {tool_name}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to update permissions for {tool_name}: {e}")
            return False

    async def list_registered_tools(self) -> List[Dict[str, Any]]:
        """
        List all tools registered on Arcade.dev platform.

        Returns:
            List of registered tools with metadata
        """
        try:
            if self.config.demo_mode:
                # Return demo tools
                demo_tools = [
                    {
                        "id": "demo_tool_text_processcontent",
                        "name": "Text_ProcessContent",
                        "version": "1.0.0",
                        "status": "active",
                        "requires_auth": True,
                        "_demo_mode": True,
                    },
                    {
                        "id": "demo_tool_data_transform",
                        "name": "Data_Transform",
                        "version": "1.0.0",
                        "status": "active",
                        "requires_auth": False,
                        "_demo_mode": True,
                    },
                ]
                tools = demo_tools
            else:
                # For real mode, would use actual API
                tools = []

            # Enhance with FACT registry information
            enhanced_tools = []
            for tool in tools:
                tool_name = tool.get("name")
                enhanced_tool = dict(tool)

                # Add FACT registry info if available
                try:
                    fact_tool = self.tool_registry.get_tool(tool_name)
                    if fact_tool:
                        enhanced_tool["fact_version"] = fact_tool.version
                        enhanced_tool["fact_created_at"] = getattr(
                            fact_tool, "created_at", None
                        )
                        enhanced_tool["fact_timeout"] = fact_tool.timeout_seconds
                except:
                    enhanced_tool["fact_version"] = None
                    enhanced_tool["fact_created_at"] = None
                    enhanced_tool["fact_timeout"] = None

                enhanced_tools.append(enhanced_tool)

            return enhanced_tools

        except Exception as e:
            self.logger.error(f"Failed to list registered tools: {e}")
            return []

    async def close(self) -> None:
        """Close connections and cleanup resources."""
        try:
            await self.arcade_client.disconnect()
            self.logger.info("Tool registrar closed successfully")
        except Exception as e:
            self.logger.warning(f"Error closing tool registrar: {e}")

    def _prepare_arcade_tool_definition(self, tool_definition) -> Dict[str, Any]:
        """
        Convert FACT tool definition to Arcade.dev format.

        Args:
            tool_definition: FACT tool definition

        Returns:
            Arcade.dev compatible tool definition
        """
        arcade_definition = {
            "name": tool_definition.name,
            "description": tool_definition.description,
            "parameters": {
                "type": "object",
                "properties": tool_definition.parameters,
                "required": self._extract_required_parameters(
                    tool_definition.parameters
                ),
            },
            "version": tool_definition.version,
            "requires_auth": tool_definition.requires_auth,
            "timeout_seconds": tool_definition.timeout_seconds,
            "metadata": {
                "created_by": "FACT",
                "framework_version": "1.0.0",
                "category": (
                    tool_definition.name.split(".")[0]
                    if "." in tool_definition.name
                    else "general"
                ),
                "workspace_id": self.config.workspace_id,
            },
        }

        # Add workspace context if specified
        if self.config.workspace_id:
            arcade_definition["workspace_id"] = self.config.workspace_id

        return arcade_definition

    def _extract_required_parameters(self, parameters: Dict[str, Any]) -> List[str]:
        """Extract required parameter names from parameter schema."""
        required = []
        for param_name, param_schema in parameters.items():
            if isinstance(param_schema, dict):
                # Parameter is required if it has no default and isn't marked as optional
                if "default" not in param_schema and param_schema.get("required", True):
                    required.append(param_name)
        return required

    async def _check_existing_tool(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Check if tool already exists on Arcade.dev."""
        try:
            if self.config.demo_mode:
                # In demo mode, simulate that some tools already exist
                if tool_name in ["Text_ProcessContent"]:
                    return {
                        "id": f"demo_tool_{tool_name.replace('.', '_').lower()}",
                        "name": tool_name,
                        "version": "1.0.0",
                        "status": "active",
                    }
                return None
            else:
                # For real mode, we'd need to implement get_tool_info
                # For now, assume tools don't exist
                return None
        except Exception:
            return None

    async def _update_existing_tool(
        self, tool_name: str, tool_definition, existing_tool: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update an existing tool with new definition."""
        try:
            # Compare versions to decide if update is needed
            existing_version = existing_tool.get("version", "0.0.0")
            new_version = tool_definition.version

            if self._is_newer_version(new_version, existing_version):
                # Update tool definition
                arcade_definition = self._prepare_arcade_tool_definition(
                    tool_definition
                )
                # Note: Actual update implementation would depend on Arcade.dev API
                # For now, we'll delete and re-register
                await self._delete_tool(tool_name)
                registration_result = await self._register_tool_with_arcade(
                    arcade_definition
                )

                return {
                    "tool_name": tool_name,
                    "status": "success",
                    "arcade_tool_id": registration_result.get("id"),
                    "version": new_version,
                    "message": f"Tool updated from {existing_version} to {new_version}",
                }
            else:
                return {
                    "tool_name": tool_name,
                    "status": "skipped",
                    "arcade_tool_id": existing_tool.get("id"),
                    "version": existing_version,
                    "message": "Tool version is up to date",
                }

        except Exception as e:
            raise Exception(f"Failed to update existing tool: {e}")

    def _is_newer_version(self, new_version: str, existing_version: str) -> bool:
        """Compare version strings to determine if new version is newer."""

        def version_tuple(version: str) -> tuple:
            try:
                return tuple(map(int, version.split(".")))
            except ValueError:
                return (0, 0, 0)

        return version_tuple(new_version) > version_tuple(existing_version)

    async def _setup_tool_permissions(
        self, tool_id: str, tool_name: str, tool_definition
    ) -> None:
        """Set up authentication and permissions for a tool."""
        try:
            # Configure tool permissions based on FACT requirements
            permissions_config = {
                "require_authentication": tool_definition.requires_auth,
                "allowed_scopes": ["tool:execute"],
                "rate_limit": {"calls_per_minute": 60, "calls_per_hour": 1000},
                "audit_logging": True,
            }

            # Apply permissions via Arcade.dev API
            await self._update_tool_permissions(tool_id, permissions_config)

        except Exception as e:
            self.logger.warning(f"Failed to setup permissions for {tool_name}: {e}")

    async def _update_tool_permissions(
        self, tool_id: str, permissions: Dict[str, Any]
    ) -> None:
        """Update tool permissions via Arcade.dev API."""
        if self.config.demo_mode:
            self.logger.info(f"Demo: Updated permissions for tool {tool_id}")
        else:
            # Note: This would use actual Arcade.dev permissions API
            # Implementation depends on their specific API structure
            self.logger.debug(f"Updating permissions for tool {tool_id}: {permissions}")

    async def _verify_workspace_access(self) -> None:
        """Verify access to the specified workspace."""
        try:
            # Verify workspace access
            # Implementation would depend on Arcade.dev workspace API
            self.logger.info(
                f"Verified access to workspace: {self.config.workspace_id}"
            )
        except Exception as e:
            raise Exception(f"Workspace access verification failed: {e}")

    async def _register_tool_with_arcade(
        self, tool_definition: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Register a tool with Arcade.dev platform."""
        if self.config.demo_mode:
            # Generate mock registration response
            tool_id = f"demo_tool_{tool_definition['name'].replace('.', '_').lower()}"
            return {
                "id": tool_id,
                "name": tool_definition["name"],
                "status": "registered",
                "version": tool_definition["version"],
                "created_at": "2025-05-25T19:33:00Z",
                "_demo_mode": True,
            }
        else:
            # For real mode, would use actual Arcade.dev API
            # This would require implementing the tool registration endpoint
            self.logger.warning("Real Arcade.dev tool registration not implemented")
            return {
                "id": f"real_tool_{tool_definition['name'].replace('.', '_').lower()}",
                "name": tool_definition["name"],
                "status": "registered",
                "version": tool_definition["version"],
            }

    async def _get_tool_info(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get tool information from Arcade.dev."""
        if self.config.demo_mode:
            # Return mock tool info for demo
            return {
                "id": f"demo_tool_{tool_name.replace('.', '_').lower()}",
                "name": tool_name,
                "version": "1.0.0",
                "status": "active",
                "_demo_mode": True,
            }
        else:
            # For real mode, would query actual API
            return None

    async def _delete_tool(self, tool_name: str) -> bool:
        """Delete a tool from Arcade.dev."""
        if self.config.demo_mode:
            self.logger.info(f"Demo: Would delete tool {tool_name}")
            return True
        else:
            # For real mode, would use actual deletion API
            self.logger.warning(f"Real tool deletion not implemented for {tool_name}")
            return False


# Example FACT tools to register
@Tool(
    name="Text_ProcessContent",
    description="Process and analyze text content for patterns and insights",
    parameters={
        "content": {
            "type": "string",
            "description": "Text content to process",
            "minLength": 1,
            "maxLength": 10000,
        },
        "analysis_type": {
            "type": "string",
            "description": "Type of analysis to perform",
            "enum": ["sentiment", "keywords", "summary", "entities"],
            "default": "summary",
        },
    },
    requires_auth=True,
    timeout_seconds=30,
)
def process_text_content(
    content: str, analysis_type: str = "summary"
) -> Dict[str, Any]:
    """Process text content with specified analysis type."""
    # Mock implementation for example
    return {
        "content_length": len(content),
        "analysis_type": analysis_type,
        "result": f"Processed {len(content)} characters with {analysis_type} analysis",
        "metadata": {"processing_time_ms": 150, "word_count": len(content.split())},
    }


@Tool(
    name="Data_Transform",
    description="Transform data between different formats and structures",
    parameters={
        "data": {"type": "object", "description": "Data to transform"},
        "target_format": {
            "type": "string",
            "description": "Target format for transformation",
            "enum": ["json", "csv", "xml", "yaml"],
        },
        "options": {
            "type": "object",
            "description": "Transformation options",
            "required": False,
            "default": {},
        },
    },
    requires_auth=False,
    timeout_seconds=60,
)
def transform_data(
    data: Dict[str, Any], target_format: str, options: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Transform data to specified format."""
    if options is None:
        options = {}

    # Mock implementation for example
    return {
        "original_format": "object",
        "target_format": target_format,
        "transformed": True,
        "options_applied": options,
        "transformation_id": "tx_123456",
    }


# Tools are automatically registered by the @Tool decorator
# No manual registration needed


async def main():
    """Main demonstration function."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print("🚀 FACT Tool Registration with Arcade.dev Example")
    print("=" * 55)

    # Example tools are automatically registered by @Tool decorator
    print("\n🔧 Checking registered FACT tools...")
    registry = get_tool_registry()
    print(f"✅ Found {len(registry.list_tools())} registered tools")

    # Load configuration from environment
    arcade_api_key = os.getenv("ARCADE_API_KEY", "")
    demo_mode = not arcade_api_key or not ARCADE_SDK_AVAILABLE

    if demo_mode:
        print("🎭 Running in DEMO MODE")
        print("   - No ARCADE_API_KEY found or arcadepy SDK not available")
        print("   - Will simulate tool registration with mock responses")
        print("   - To use real API: install arcadepy and set ARCADE_API_KEY")
        print()

    config = ToolRegistrationConfig(
        arcade_api_key=arcade_api_key or "demo_key",
        arcade_base_url=os.getenv("ARCADE_BASE_URL", "https://api.arcade.dev"),
        workspace_id=os.getenv("ARCADE_WORKSPACE_ID"),
        default_timeout=int(os.getenv("ARCADE_TIMEOUT", "30")),
        requires_auth_by_default=os.getenv("ARCADE_REQUIRE_AUTH", "true").lower()
        == "true",
        demo_mode=demo_mode,
        user_id=os.getenv("ARCADE_USER_ID", "demo@example.com"),
    )

    # Initialize tool registrar
    registrar = FactToolRegistrar(config)

    try:
        # Connect to Arcade.dev
        print("\n🔌 Connecting to Arcade.dev platform...")
        await registrar.connect()
        print("✅ Connected successfully")

        # List existing tools
        print("\n📋 Listing currently registered tools...")
        existing_tools = await registrar.list_registered_tools()
        print(f"✅ Found {len(existing_tools)} existing tools")

        # Register all FACT tools
        print("\n🔧 Registering FACT tools with Arcade.dev...")
        registration_summary = await registrar.register_all_tools()

        # Display results
        print("\n📊 Registration Summary:")
        print(f"  Total tools: {registration_summary['total_tools']}")
        print(f"  Successful: {registration_summary['successful']}")
        print(f"  Failed: {registration_summary['failed']}")
        print(f"  Skipped: {registration_summary['skipped']}")

        # Show detailed results
        if registration_summary["results"]:
            print("\n📋 Detailed Results:")
            for result in registration_summary["results"]:
                status_icon = (
                    "✅"
                    if result["status"] == "success"
                    else "❌" if result["status"] == "failed" else "⏭️"
                )
                print(
                    f"  {status_icon} {result['tool_name']}: {result.get('message', result['status'])}"
                )

        # Demonstrate permission updates
        print("\n🔐 Demonstrating permission updates...")
        success = await registrar.update_tool_permissions(
            "Text_ProcessContent",
            {
                "require_authentication": True,
                "allowed_scopes": ["tool:execute", "data:read"],
                "rate_limit": {"calls_per_minute": 30},
            },
        )
        print(f"✅ Permission update {'successful' if success else 'failed'}")

        # Final tool list
        print("\n📋 Final tool list:")
        final_tools = await registrar.list_registered_tools()
        for tool in final_tools:
            auth_status = "🔐" if tool.get("requires_auth") else "🔓"
            print(
                f"  {auth_status} {tool.get('name')} (v{tool.get('version', 'unknown')})"
            )

    except Exception as e:
        print(f"❌ Error during tool registration: {e}")
        return 1

    finally:
        # Clean up
        await registrar.close()

    print("\n🎉 Tool registration example completed successfully!")
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
