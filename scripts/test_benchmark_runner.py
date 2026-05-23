#!/usr/bin/env python3
"""
Test script for the FACT benchmark runner.
This script validates that the benchmark runner can be executed successfully.
"""

import sys
import subprocess
from pathlib import Path


def test_benchmark_runner():
    """Test the benchmark runner script."""
    script_path = Path(__file__).parent / "run_benchmarks.py"

    print("🧪 Testing FACT Benchmark Runner")
    print("=" * 50)

    # Test 1: Check if script can be imported
    print("Test 1: Import validation...")
    try:
        # Add src to Python path
        src_path = str(Path(__file__).parent.parent / "src")
        if src_path not in sys.path:
            sys.path.insert(0, src_path)

        # Test basic imports that don't require relative imports
        print("  Testing basic module structure...")

        # Check if benchmarking module exists
        import benchmarking

        print("  ✅ Benchmarking module found")

        # Check if cache module exists
        import cache

        print("  ✅ Cache module found")

        print("✅ Core modules accessible")
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

    # Test 2: Check command line help
    print("\nTest 2: Command line interface...")
    try:
        result = subprocess.run(
            [sys.executable, str(script_path), "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            print("✅ CLI help works correctly")
        else:
            print(f"❌ CLI help failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ CLI test failed: {e}")
        return False

    # Test 3: Directory creation functionality
    print("\nTest 3: Directory creation...")
    try:
        # Import our enhanced functions
        sys.path.insert(0, str(Path(__file__).parent))
        import run_benchmarks

        # Test directory creation
        test_dir = run_benchmarks.create_logs_directory("test_logs")
        if test_dir.exists():
            print(f"✅ Directory created: {test_dir}")

            # Clean up
            import shutil

            shutil.rmtree(test_dir.parent)
            print("✅ Cleanup successful")
        else:
            print("❌ Directory creation failed")
            return False
    except Exception as e:
        print(f"❌ Directory test failed: {e}")
        return False

    print("\n🎉 All tests passed! Benchmark runner is ready to use.")
    print("\nTo run benchmarks:")
    print(f"  python {script_path}")
    print(f"  python {script_path} --include-rag-comparison")
    print(f"  python {script_path} --include-profiling --include-load-test")

    return True


if __name__ == "__main__":
    success = test_benchmark_runner()
    sys.exit(0 if success else 1)
