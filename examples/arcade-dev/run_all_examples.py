#!/usr/bin/env python3
"""
Run All Arcade.dev Examples

This script executes all available examples in sequence, providing
a comprehensive demonstration of the Arcade.dev integration capabilities.
"""

import os
import sys
import asyncio
import subprocess
from pathlib import Path
from typing import List, Dict, Any
import time
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class ExampleRunner:
    """Manages execution of all Arcade.dev examples."""

    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.examples = self._discover_examples()
        self.results: List[Dict[str, Any]] = []

    def _discover_examples(self) -> List[Dict[str, str]]:
        """Discover all runnable examples."""
        examples = []

        # Known examples
        known_examples = [
            {
                "name": "Basic Integration",
                "script": "01_basic_integration/basic_arcade_client.py",
                "description": "Basic API client integration",
            },
            {
                "name": "Tool Registration",
                "script": "02_tool_registration/register_fact_tools.py",
                "description": "Register FACT tools with Arcade.dev",
            },
            {
                "name": "Intelligent Routing",
                "script": "03_intelligent_routing/hybrid_execution.py",
                "description": "Hybrid execution with intelligent routing",
            },
            {
                "name": "Error Handling",
                "script": "04_error_handling/resilient_execution.py",
                "description": "Resilient execution with error handling",
            },
            {
                "name": "Cache Integration (Enhanced)",
                "script": "05_cache_integration/cached_arcade_client_enhanced.py",
                "description": "Enhanced cached API client",
            },
            {
                "name": "Security",
                "script": "06_security/secure_tool_execution.py",
                "description": "Secure tool execution with validation",
            },
            {
                "name": "Cache Integration",
                "script": "07_cache_integration/cached_arcade_client.py",
                "description": "Cached API client with performance optimization",
            },
            {
                "name": "Advanced Tools",
                "script": "08_advanced_tools/advanced_tool_usage.py",
                "description": "Advanced tool usage patterns",
            },
            {
                "name": "Testing",
                "script": "09_testing/arcade_integration_tests.py",
                "description": "Integration testing framework",
            },
            {
                "name": "Production Deployment",
                "script": "10_deployment/production_deployment.py",
                "description": "Production deployment configuration",
            },
            {
                "name": "Monitoring",
                "script": "12_monitoring/arcade_monitoring.py",
                "description": "Monitoring and observability",
            },
        ]

        # Filter to only include existing scripts
        for example in known_examples:
            script_path = self.base_dir / example["script"]
            if script_path.exists():
                examples.append(example)

        return examples

    async def run_example(self, example: Dict[str, str]) -> Dict[str, Any]:
        """Run a single example and collect results."""
        print(f"\n{'='*60}")
        print(f"🚀 Running: {example['name']}")
        print(f"📁 Script: {example['script']}")
        print(f"📝 Description: {example['description']}")
        print("=" * 60)

        script_path = self.base_dir / example["script"]
        start_time = time.time()

        try:
            # Run the example
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                str(script_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(script_path.parent),
            )

            stdout, stderr = await process.communicate()
            duration = time.time() - start_time

            result = {
                "name": example["name"],
                "script": example["script"],
                "duration": duration,
                "success": process.returncode == 0,
                "return_code": process.returncode,
                "stdout": stdout.decode() if stdout else "",
                "stderr": stderr.decode() if stderr else "",
            }

            if result["success"]:
                print(f"✅ {example['name']} completed successfully ({duration:.2f}s)")
            else:
                print(
                    f"❌ {example['name']} failed (return code: {process.returncode})"
                )

            # Show output/errors
            if result["stdout"]:
                print("\n📄 Output:")
                print("-" * 40)
                print(result["stdout"])

            if result["stderr"]:
                print("\n⚠️  Errors/Warnings:")
                print("-" * 40)
                print(result["stderr"])

            return result

        except Exception as e:
            duration = time.time() - start_time
            print(f"❌ {example['name']} failed with exception: {e}")

            return {
                "name": example["name"],
                "script": example["script"],
                "duration": duration,
                "success": False,
                "return_code": -1,
                "stdout": "",
                "stderr": str(e),
            }

    def print_summary(self):
        """Print execution summary."""
        print("\n" + "=" * 80)
        print("📊 EXECUTION SUMMARY")
        print("=" * 80)

        total_examples = len(self.results)
        successful = sum(1 for r in self.results if r["success"])
        failed = total_examples - successful
        total_duration = sum(r["duration"] for r in self.results)

        print(f"Total Examples: {total_examples}")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        print(f"Total Duration: {total_duration:.2f}s")
        print(f"Average Duration: {total_duration/total_examples:.2f}s")

        print("\n📋 Individual Results:")
        print("-" * 80)
        for result in self.results:
            status = "✅" if result["success"] else "❌"
            print(f"{status} {result['name']:<30} {result['duration']:>8.2f}s")

        if failed > 0:
            print("\n❌ Failed Examples:")
            print("-" * 40)
            for result in self.results:
                if not result["success"]:
                    print(f"• {result['name']}: {result['stderr'][:100]}...")

        print("\n" + "=" * 80)

    async def run_all(self):
        """Run all examples in sequence."""
        print("🎮 Running All Arcade.dev Examples")
        print("=" * 50)

        if not self.examples:
            print("❌ No runnable examples found!")
            return False

        print(f"Found {len(self.examples)} examples to run")

        for example in self.examples:
            result = await self.run_example(example)
            self.results.append(result)

            # Small delay between examples
            await asyncio.sleep(1)

        self.print_summary()

        # Return True if all examples succeeded
        return all(r["success"] for r in self.results)


async def main():
    """Main function."""
    print("🎮 Arcade.dev Examples - Batch Runner")
    print("=" * 50)

    # Check prerequisites
    if not os.getenv("ARCADE_API_KEY"):
        print("❌ ARCADE_API_KEY environment variable not set")
        print("Please copy .env.example to .env and configure your API key")
        return 1

    runner = ExampleRunner()

    try:
        success = await runner.run_all()

        if success:
            print("\n🎉 All examples completed successfully!")
            return 0
        else:
            print("\n⚠️  Some examples failed. Check the summary above.")
            return 1

    except KeyboardInterrupt:
        print("\n❌ Execution interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Execution failed: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
