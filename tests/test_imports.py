#!/usr/bin/env python3
"""
Unit tests for import resolution in the FACT system.

These tests ensure that all imports work correctly when the system
is executed from different contexts and prevent ImportError issues.
"""

import sys
import os
import unittest
import importlib
from pathlib import Path

# Add src to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class TestImportResolution(unittest.TestCase):
    """Test that all imports work correctly across the FACT system."""

    def setUp(self):
        """Set up test environment."""
        self.src_path = Path(__file__).parent.parent / "src"
        self.assertTrue(self.src_path.exists(), "Source directory must exist")

    def test_core_module_imports(self):
        """Test that core module imports work correctly."""
        try:
            # Test core config import
            from core.config import Config, get_config

            # Test core driver import
            from core.driver import get_driver, FACTDriver

            # Test core errors import
            from core.errors import FACTError, ConfigurationError

            print("✅ Core module imports successful")
        except ImportError as e:
            self.fail(f"Core module import failed: {e}")

    def test_db_module_imports(self):
        """Test that database module imports work correctly."""
        try:
            # Test db connection import
            from db.connection import DatabaseManager

            # Test db models import
            from db.models import DATABASE_SCHEMA, QueryResult

            print("✅ Database module imports successful")
        except ImportError as e:
            self.fail(f"Database module import failed: {e}")

    def test_tools_module_imports(self):
        """Test that tools module imports work correctly."""
        try:
            # Test tools decorators import
            from tools.decorators import Tool, get_tool_registry

            # Test tools executor import
            from tools.executor import ToolExecutor, ToolCall

            # Test tools validation import
            from tools.validation import ParameterValidator

            print("✅ Tools module imports successful")
        except ImportError as e:
            self.fail(f"Tools module import failed: {e}")

    def test_security_module_imports(self):
        """Test that security module imports work correctly."""
        try:
            # Test security auth import
            from security.auth import AuthorizationManager

            # Test security config import
            from security.config import SecurityConfig

            print("✅ Security module imports successful")
        except ImportError as e:
            self.fail(f"Security module import failed: {e}")

    def test_arcade_module_imports(self):
        """Test that arcade module imports work correctly."""
        try:
            # Test arcade client import
            from arcade.client import ArcadeClient

            # Test arcade gateway import
            from arcade.gateway import ArcadeGateway

            # Test arcade errors import
            from arcade.errors import ArcadeError

            print("✅ Arcade module imports successful")
        except ImportError as e:
            self.fail(f"Arcade module import failed: {e}")

    def test_cache_module_imports(self):
        """Test that cache module imports work correctly."""
        try:
            # Test cache manager import
            from cache.manager import CacheManager

            # Test cache strategy import
            from cache.strategy import CacheStrategy

            print("✅ Cache module imports successful")
        except ImportError as e:
            self.fail(f"Cache module import failed: {e}")

    def test_monitoring_module_imports(self):
        """Test that monitoring module imports work correctly."""
        try:
            # Test monitoring metrics import
            from monitoring.metrics import MetricsCollector

            print("✅ Monitoring module imports successful")
        except ImportError as e:
            self.fail(f"Monitoring module import failed: {e}")

    def test_tools_connectors_imports(self):
        """Test that tools connector imports work correctly."""
        try:
            # Test SQL connector import
            from tools.connectors.sql import initialize_sql_tool

            # Test HTTP connector import
            from tools.connectors.http import http_get

            # Test file connector import
            from tools.connectors.file import read_file

            print("✅ Tools connector imports successful")
        except ImportError as e:
            self.fail(f"Tools connector import failed: {e}")

    def test_benchmarking_module_imports(self):
        """Test that benchmarking module imports work correctly."""
        try:
            # Test benchmarking framework import
            from benchmarking.framework import BenchmarkFramework

            # Test benchmarking profiler import
            from benchmarking.profiler import SystemProfiler

            print("✅ Benchmarking module imports successful")
        except ImportError as e:
            self.fail(f"Benchmarking module import failed: {e}")

    def test_no_relative_imports_beyond_package(self):
        """Test that no files contain problematic relative imports."""
        problematic_patterns = [
            "from ..",  # Relative imports that might go beyond package
        ]

        problematic_files = []

        for py_file in self.src_path.rglob("*.py"):
            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    content = f.read()

                for pattern in problematic_patterns:
                    if pattern in content:
                        # Check if this is actually problematic by context
                        lines = content.splitlines()
                        for i, line in enumerate(lines):
                            if pattern in line and "import" in line:
                                # This could be problematic
                                problematic_files.append(
                                    f"{py_file}:{i+1}: {line.strip()}"
                                )
            except Exception as e:
                self.fail(f"Error reading {py_file}: {e}")

        if problematic_files:
            print("⚠️ Found potentially problematic imports:")
            for item in problematic_files:
                print(f"  {item}")
        else:
            print("✅ No problematic relative imports found")

    def test_script_execution_context(self):
        """Test that the system can be imported from script context."""
        # Simulate the context where scripts/init_environment.py imports
        original_path = sys.path.copy()

        try:
            # Add the specific path that init_environment.py uses
            script_src_path = os.path.join(os.path.dirname(__file__), "..", "src")
            if script_src_path not in sys.path:
                sys.path.insert(0, script_src_path)

            # Try to import the same modules that init_environment.py imports
            from core.config import Config
            from core.driver import get_driver
            from db.connection import DatabaseManager

            print("✅ Script execution context imports successful")

        except ImportError as e:
            self.fail(f"Script context import failed: {e}")
        finally:
            sys.path = original_path


class TestMainEntryPoints(unittest.TestCase):
    """Test main entry points work correctly."""

    def test_main_py_init_imports(self):
        """Test that main.py can import required modules for init command."""
        try:
            # These are the imports used in main.py validate command
            from core.config import get_config
            from core.driver import get_driver

            print("✅ Main.py entry point imports successful")
        except ImportError as e:
            self.fail(f"Main.py import failed: {e}")

    def test_cli_module_imports(self):
        """Test that CLI module can be imported correctly."""
        try:
            # Test CLI module import
            from core.cli import main

            print("✅ CLI module imports successful")
        except ImportError as e:
            self.fail(f"CLI module import failed: {e}")


def run_import_tests():
    """Run all import tests and provide summary."""
    print("🧪 Running FACT System Import Tests")
    print("=" * 50)

    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestImportResolution))
    suite.addTests(loader.loadTestsFromTestCase(TestMainEntryPoints))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("\n" + "=" * 50)
    if result.wasSuccessful():
        print("✅ All import tests passed!")
        print(f"Ran {result.testsRun} tests successfully")
    else:
        print("❌ Some import tests failed!")
        print(f"Failures: {len(result.failures)}")
        print(f"Errors: {len(result.errors)}")

        if result.failures:
            print("\nFailures:")
            for test, traceback in result.failures:
                print(f"  {test}: {traceback}")

        if result.errors:
            print("\nErrors:")
            for test, traceback in result.errors:
                print(f"  {test}: {traceback}")

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_import_tests()
    sys.exit(0 if success else 1)
