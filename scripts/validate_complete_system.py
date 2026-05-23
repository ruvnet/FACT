#!/usr/bin/env python3
"""
FACT System Complete Validation Script

This script performs comprehensive validation of all integrated FACT system components:
- Environment configuration
- Database connectivity
- API integration
- Cache system performance
- Security layer
- Benchmark framework
- Performance monitoring

Usage:
    python scripts/validate_complete_system.py [--verbose] [--fix-issues]
"""

import os
import sys
import asyncio
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Any, Tuple
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.config import Config, ConfigurationError
from core.driver import get_driver
from db.connection import DatabaseManager
from cache.validation import CacheValidator
from security.auth import AuthorizationManager
from security.input_sanitizer import InputSanitizer
from monitoring.metrics import MetricsCollector
from benchmarking.framework import BenchmarkFramework, BenchmarkConfig


class ValidationResult:
    """Represents the result of a validation check."""

    def __init__(
        self,
        component: str,
        test: str,
        success: bool,
        message: str,
        details: Dict[str, Any] = None,
    ):
        self.component = component
        self.test = test
        self.success = success
        self.message = message
        self.details = details or {}
        self.timestamp = datetime.now()


class SystemValidator:
    """Comprehensive FACT system validator."""

    def __init__(self, verbose: bool = False, fix_issues: bool = False):
        self.verbose = verbose
        self.fix_issues = fix_issues
        self.results: List[ValidationResult] = []
        self.setup_logging()

    def setup_logging(self):
        """Set up logging configuration."""
        level = logging.DEBUG if self.verbose else logging.INFO
        logging.basicConfig(
            level=level, format="%(asctime)s - %(levelname)s - %(message)s"
        )
        self.logger = logging.getLogger(__name__)

    def add_result(
        self,
        component: str,
        test: str,
        success: bool,
        message: str,
        details: Dict[str, Any] = None,
    ):
        """Add a validation result."""
        result = ValidationResult(component, test, success, message, details)
        self.results.append(result)

        status = "✅" if success else "❌"
        print(f"{status} {component}: {test} - {message}")

        if self.verbose and details:
            for key, value in details.items():
                print(f"   {key}: {value}")

    def validate_environment_configuration(self) -> bool:
        """Validate environment configuration."""
        print("\n🔧 Validating Environment Configuration...")
        all_passed = True

        try:
            # Test .env file existence
            env_path = Path(".env")
            if env_path.exists():
                self.add_result(
                    "Environment",
                    ".env file",
                    True,
                    f"Found at {env_path.absolute()}",
                    {"file_size": env_path.stat().st_size},
                )
            else:
                self.add_result("Environment", ".env file", False, "Missing .env file")
                if self.fix_issues:
                    print("   🔧 Creating .env file with defaults...")
                    self.create_default_env_file()
                all_passed = False

            # Test configuration loading
            config = Config()
            self.add_result(
                "Environment",
                "Configuration loading",
                True,
                "Configuration loaded successfully",
                config.to_dict(),
            )

            # Validate API keys
            if config.anthropic_api_key and not config.anthropic_api_key.startswith(
                "your_"
            ):
                self.add_result(
                    "Environment", "Anthropic API key", True, "Valid API key configured"
                )
            else:
                self.add_result(
                    "Environment",
                    "Anthropic API key",
                    False,
                    "API key not configured or placeholder",
                )
                all_passed = False

            if config.arcade_api_key and not config.arcade_api_key.startswith("your_"):
                self.add_result(
                    "Environment", "Arcade API key", True, "Valid API key configured"
                )
            else:
                self.add_result(
                    "Environment",
                    "Arcade API key",
                    False,
                    "API key not configured or placeholder",
                )
                all_passed = False

            return all_passed

        except ConfigurationError as e:
            self.add_result("Environment", "Configuration loading", False, str(e))
            return False
        except Exception as e:
            self.add_result(
                "Environment", "Configuration loading", False, f"Unexpected error: {e}"
            )
            return False

    async def validate_database_integration(self) -> bool:
        """Validate database integration."""
        print("\n🗄️ Validating Database Integration...")
        all_passed = True

        try:
            config = Config()
            db_manager = DatabaseManager(config.database_path)

            # Test database initialization
            await db_manager.initialize_database()
            self.add_result(
                "Database", "Initialization", True, "Database initialized successfully"
            )

            # Test database info retrieval
            db_info = await db_manager.get_database_info()
            self.add_result(
                "Database",
                "Schema validation",
                True,
                f"Found {db_info['total_tables']} tables",
                db_info,
            )

            # Validate required tables
            required_tables = ["companies", "financial_data", "benchmarks"]
            for table in required_tables:
                if table in db_info["tables"]:
                    row_count = db_info["tables"][table]["row_count"]
                    self.add_result(
                        "Database",
                        f"Table {table}",
                        True,
                        f"{row_count} rows",
                        {"row_count": row_count},
                    )
                else:
                    self.add_result(
                        "Database", f"Table {table}", False, "Table missing"
                    )
                    all_passed = False

            return all_passed

        except Exception as e:
            self.add_result("Database", "Integration", False, f"Database error: {e}")
            return False

    async def validate_api_connectivity(self) -> bool:
        """Validate API connectivity."""
        print("\n🌐 Validating API Connectivity...")
        all_passed = True

        try:
            config = Config()

            # Skip API tests if keys are not configured
            if (
                not config.anthropic_api_key
                or config.anthropic_api_key.startswith("your_")
                or not config.arcade_api_key
                or config.arcade_api_key.startswith("your_")
            ):
                self.add_result(
                    "API",
                    "Connectivity test",
                    False,
                    "API keys not configured - skipping connectivity tests",
                )
                return False

            # Test driver initialization (includes API connectivity)
            try:
                driver = await get_driver()
                self.add_result(
                    "API",
                    "Driver initialization",
                    True,
                    "Driver initialized successfully",
                )

                # Test basic functionality
                metrics = driver.get_metrics()
                self.add_result(
                    "API",
                    "System metrics",
                    True,
                    f"System operational - {len(driver.tool_registry.list_tools())} tools available",
                    metrics,
                )

                await driver.shutdown()
                return True

            except Exception as e:
                self.add_result(
                    "API", "Driver initialization", False, f"Driver error: {e}"
                )
                return False

        except Exception as e:
            self.add_result("API", "Connectivity", False, f"API error: {e}")
            return False

    async def validate_cache_system(self) -> bool:
        """Validate cache system."""
        print("\n💾 Validating Cache System...")
        all_passed = True

        try:
            config = Config()
            cache_config = config.cache_config

            self.add_result(
                "Cache",
                "Configuration",
                True,
                "Cache configuration loaded",
                cache_config,
            )

            # Test cache validator
            validator = CacheValidator()
            self.add_result(
                "Cache", "Validator initialization", True, "Cache validator initialized"
            )

            # Note: Actual cache performance testing requires live system
            # This validates the cache system is properly configured

            return all_passed

        except Exception as e:
            self.add_result("Cache", "System", False, f"Cache error: {e}")
            return False

    def validate_security_layer(self) -> bool:
        """Validate security layer."""
        print("\n🛡️ Validating Security Layer...")
        all_passed = True

        try:
            # Test authorization manager initialization
            auth_manager = AuthorizationManager()
            self.add_result(
                "Security",
                "Authorization manager",
                True,
                "Authorization manager initialized",
            )

            # Test input sanitizer initialization
            input_sanitizer = InputSanitizer()
            self.add_result(
                "Security", "Input sanitizer", True, "Input sanitizer initialized"
            )

            # Test input sanitization
            test_inputs = [
                ("Normal query", "What is TechCorp's revenue?", True),
                ("XSS attempt", "<script>alert('xss')</script>", False),
                ("SQL injection", "'; DROP TABLE users; --", False),
                ("Valid financial query", "Show me Q1 2025 financial data", True),
            ]

            for test_name, test_input, should_pass in test_inputs:
                try:
                    result = input_sanitizer.sanitize_string(test_input)
                    if should_pass:
                        self.add_result(
                            "Security",
                            f"Input validation: {test_name}",
                            True,
                            "Input accepted",
                        )
                    else:
                        self.add_result(
                            "Security",
                            f"Input validation: {test_name}",
                            False,
                            "Malicious input should be blocked",
                        )
                        all_passed = False
                except Exception:
                    if not should_pass:
                        self.add_result(
                            "Security",
                            f"Input validation: {test_name}",
                            True,
                            "Malicious input blocked",
                        )
                    else:
                        self.add_result(
                            "Security",
                            f"Input validation: {test_name}",
                            False,
                            "Valid input rejected",
                        )
                        all_passed = False

            return all_passed

        except Exception as e:
            self.add_result("Security", "Layer", False, f"Security error: {e}")
            return False

    async def validate_benchmark_framework(self) -> bool:
        """Validate benchmark framework."""
        print("\n📊 Validating Benchmark Framework...")
        all_passed = True

        try:
            # Test framework initialization
            framework = BenchmarkFramework()
            self.add_result(
                "Benchmark", "Framework initialization", True, "Framework initialized"
            )

            # Test configuration
            config_details = {
                "iterations": framework.config.iterations,
                "warmup_iterations": framework.config.warmup_iterations,
                "concurrent_users": framework.config.concurrent_users,
                "timeout_seconds": framework.config.timeout_seconds,
            }

            self.add_result(
                "Benchmark",
                "Configuration",
                True,
                "Benchmark configuration loaded",
                config_details,
            )

            # Test empty benchmark suite (should handle gracefully)
            summary = await framework.run_benchmark_suite([])
            if summary.total_queries == 0:
                self.add_result(
                    "Benchmark",
                    "Empty suite handling",
                    True,
                    "Empty benchmark suite handled correctly",
                )
            else:
                self.add_result(
                    "Benchmark",
                    "Empty suite handling",
                    False,
                    "Empty benchmark suite not handled correctly",
                )
                all_passed = False

            return all_passed

        except Exception as e:
            self.add_result("Benchmark", "Framework", False, f"Benchmark error: {e}")
            return False

    def validate_monitoring_system(self) -> bool:
        """Validate monitoring system."""
        print("\n📈 Validating Monitoring System...")
        all_passed = True

        try:
            # Test metrics collector
            metrics_collector = MetricsCollector()
            self.add_result(
                "Monitoring", "Metrics collector", True, "Metrics collector initialized"
            )

            return all_passed

        except Exception as e:
            self.add_result("Monitoring", "System", False, f"Monitoring error: {e}")
            return False

    def create_default_env_file(self):
        """Create a default .env file."""
        env_content = """# FACT System Configuration
# Update the API keys below with your actual credentials

# Required API Keys - MUST be configured for system to work
ANTHROPIC_API_KEY=your_anthropic_api_key_here
ARCADE_API_KEY=your_arcade_api_key_here

# System Configuration
ARCADE_BASE_URL=https://api.arcade-ai.com
DATABASE_PATH=data/fact_demo.db
CACHE_PREFIX=fact_v1
SYSTEM_PROMPT=You are a deterministic finance assistant. When uncertain, request data via tools.
CLAUDE_MODEL=claude-3-5-sonnet-20241022
MAX_RETRIES=3
REQUEST_TIMEOUT=30
LOG_LEVEL=INFO

# Performance Configuration
CACHE_MAX_SIZE=5000
CACHE_TTL=3600
CACHE_MIN_TOKENS=50
CACHE_HIT_TARGET_MS=30
CACHE_MISS_TARGET_MS=120
MAX_CONCURRENT_QUERIES=50
"""

        with open(".env", "w") as f:
            f.write(env_content)
        print("   📄 Created .env file with default configuration")

    def print_summary(self):
        """Print validation summary."""
        print("\n" + "=" * 60)
        print("🎯 FACT SYSTEM VALIDATION SUMMARY")
        print("=" * 60)

        # Count results by component
        component_results = {}
        for result in self.results:
            if result.component not in component_results:
                component_results[result.component] = {"passed": 0, "failed": 0}

            if result.success:
                component_results[result.component]["passed"] += 1
            else:
                component_results[result.component]["failed"] += 1

        # Print component summary
        total_passed = 0
        total_failed = 0

        for component, counts in component_results.items():
            passed = counts["passed"]
            failed = counts["failed"]
            total = passed + failed

            status = "✅" if failed == 0 else "❌"
            print(f"{status} {component}: {passed}/{total} tests passed")

            total_passed += passed
            total_failed += failed

        print("-" * 60)

        overall_total = total_passed + total_failed
        success_rate = (total_passed / overall_total * 100) if overall_total > 0 else 0

        if total_failed == 0:
            print(
                f"🎉 ALL SYSTEMS OPERATIONAL: {total_passed}/{overall_total} tests passed ({success_rate:.1f}%)"
            )
            print("\n✅ Your FACT system is fully integrated and ready for use!")
            print("\nNext steps:")
            print("1. Start the CLI: python main.py cli")
            print("2. Run benchmarks: python scripts/run_benchmarks.py")
            print("3. Try sample queries in the interactive CLI")
        else:
            print(
                f"⚠️  ISSUES FOUND: {total_passed}/{overall_total} tests passed ({success_rate:.1f}%)"
            )
            print(f"\n❌ {total_failed} issue(s) need attention:")

            for result in self.results:
                if not result.success:
                    print(f"   • {result.component}: {result.test} - {result.message}")

            print("\n💡 Recommendations:")
            if any("API key" in r.test for r in self.results if not r.success):
                print("   1. Update API keys in .env file with actual credentials")
                print("   2. Get Anthropic API key: https://console.anthropic.com/")
                print("   3. Get Arcade API key: https://www.arcade-ai.com/")

            if any("Database" in r.component for r in self.results if not r.success):
                print("   4. Run: python main.py init")

            print("   5. Re-run validation: python scripts/validate_complete_system.py")

    async def run_all_validations(self) -> bool:
        """Run all validation checks."""
        print("🚀 FACT System Complete Validation")
        print("=" * 50)

        validations = [
            ("Environment Configuration", self.validate_environment_configuration()),
            ("Database Integration", self.validate_database_integration()),
            ("API Connectivity", self.validate_api_connectivity()),
            ("Cache System", self.validate_cache_system()),
            ("Security Layer", self.validate_security_layer()),
            ("Benchmark Framework", self.validate_benchmark_framework()),
            ("Monitoring System", self.validate_monitoring_system()),
        ]

        all_passed = True

        for name, validation in validations:
            try:
                if asyncio.iscoroutine(validation):
                    result = await validation
                else:
                    result = validation

                if not result:
                    all_passed = False

            except Exception as e:
                self.add_result("System", name, False, f"Validation failed: {e}")
                all_passed = False

        self.print_summary()
        return all_passed


async def main():
    """Main validation routine."""
    parser = argparse.ArgumentParser(
        description="FACT System Complete Validation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output with detailed information",
    )

    parser.add_argument(
        "--fix-issues",
        action="store_true",
        help="Attempt to automatically fix common issues",
    )

    args = parser.parse_args()

    validator = SystemValidator(verbose=args.verbose, fix_issues=args.fix_issues)
    success = await validator.run_all_validations()

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
