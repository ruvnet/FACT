#!/usr/bin/env python3
"""
Setup Verification Script for Arcade.dev Examples

This script verifies that all prerequisites are met for running the
Arcade.dev integration examples.
"""

import os
import sys
import asyncio
import importlib
from pathlib import Path
from typing import List, Tuple, Dict, Any
import logging

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # dotenv not available, skip loading

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


class SetupVerifier:
    """Verifies the setup for Arcade.dev examples."""

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.success: List[str] = []

    def check_python_version(self) -> bool:
        """Check Python version compatibility."""
        required_version = (3, 8)
        current_version = sys.version_info[:2]

        if current_version >= required_version:
            self.success.append(
                f"✅ Python {'.'.join(map(str, current_version))} (>= 3.8)"
            )
            return True
        else:
            self.errors.append(
                f"❌ Python {'.'.join(map(str, current_version))} < 3.8 (required)"
            )
            return False

    def check_required_packages(self) -> bool:
        """Check if required Python packages are installed."""
        # Map package names to their import names
        required_packages = {
            "aiohttp": "aiohttp",
            "asyncio": "asyncio",
            "pydantic": "pydantic",
            "python-dotenv": "dotenv",
            "redis": "redis",
        }

        all_installed = True
        for package_name, import_name in required_packages.items():
            try:
                importlib.import_module(import_name)
                self.success.append(f"✅ Package '{package_name}' is installed")
            except ImportError:
                self.errors.append(f"❌ Package '{package_name}' is not installed")
                all_installed = False

        return all_installed

    def check_environment_variables(self) -> bool:
        """Check required environment variables."""
        required_vars = [
            ("ARCADE_API_KEY", True),
            ("ARCADE_API_URL", False),
            ("ARCADE_TIMEOUT", False),
            ("ARCADE_MAX_RETRIES", False),
            ("FACT_LOG_LEVEL", False),
            ("FACT_CACHE_ENABLED", False),
        ]

        all_set = True
        for var_name, required in required_vars:
            value = os.getenv(var_name)
            if value:
                if var_name == "ARCADE_API_KEY":
                    display_value = f"{value[:8]}..." if len(value) > 8 else "***"
                else:
                    display_value = value
                self.success.append(f"✅ {var_name}={display_value}")
            elif required:
                self.errors.append(
                    f"❌ Required environment variable '{var_name}' is not set"
                )
                all_set = False
            else:
                self.warnings.append(
                    f"⚠️  Optional environment variable '{var_name}' is not set"
                )

        return all_set

    def check_fact_framework(self) -> bool:
        """Check if FACT framework components are accessible."""
        fact_modules = ["src.core.driver", "src.cache.manager"]

        # Add parent directories to path
        project_root = Path(__file__).parent.parent.parent
        sys.path.insert(0, str(project_root))

        all_accessible = True
        for module_name in fact_modules:
            try:
                importlib.import_module(module_name)
                self.success.append(f"✅ FACT module '{module_name}' is accessible")
            except ImportError as e:
                self.errors.append(
                    f"❌ FACT module '{module_name}' is not accessible: {e}"
                )
                all_accessible = False

        return all_accessible

    def check_file_structure(self) -> bool:
        """Check if required files and directories exist."""
        base_dir = Path(__file__).parent
        required_paths = [
            "README.md",
            "requirements.txt",
            "01_basic_integration/basic_arcade_client.py",
            "config",
        ]

        all_exist = True
        for path_str in required_paths:
            path = base_dir / path_str
            if path.exists():
                self.success.append(f"✅ Path '{path_str}' exists")
            else:
                if path_str == "config":
                    self.warnings.append(
                        f"⚠️  Directory '{path_str}' does not exist (will be created)"
                    )
                else:
                    self.errors.append(f"❌ Required path '{path_str}' does not exist")
                    all_exist = False

        return all_exist

    async def check_network_connectivity(self) -> bool:
        """Check network connectivity to Arcade.dev API."""
        try:
            import aiohttp

            api_url = os.getenv("ARCADE_API_URL", "https://api.arcade.dev")

            # List of endpoints to try (in order of preference)
            endpoints_to_try = ["/health", "/v1/health", "/status", "/"]

            async with aiohttp.ClientSession() as session:
                for endpoint in endpoints_to_try:
                    try:
                        async with session.get(
                            f"{api_url}{endpoint}", timeout=10
                        ) as response:
                            if response.status == 200:
                                self.success.append(
                                    f"✅ Network connectivity to {api_url} is working (endpoint: {endpoint})"
                                )
                                return True
                            elif response.status == 404:
                                # 404 is expected for some endpoints, continue trying
                                continue
                            elif response.status in [401, 403]:
                                # Authentication errors indicate the API is reachable
                                self.success.append(
                                    f"✅ Network connectivity to {api_url} is working (authentication required)"
                                )
                                return True
                            else:
                                self.warnings.append(
                                    f"⚠️  {api_url}{endpoint} returned status {response.status}"
                                )
                                continue
                    except asyncio.TimeoutError:
                        continue
                    except Exception as e:
                        continue

                # If we get here, none of the endpoints worked
                self.warnings.append(
                    f"⚠️  Could not verify API connectivity to {api_url} (all endpoints returned 404 or failed)"
                )
                self.warnings.append(
                    f"⚠️  This may be normal if the API requires authentication or has a different endpoint structure"
                )
                return False

        except Exception as e:
            self.warnings.append(f"⚠️  Could not verify network connectivity: {e}")
            return False

    def create_missing_directories(self):
        """Create missing directories."""
        base_dir = Path(__file__).parent
        directories = ["config", "output", "logs"]

        for dir_name in directories:
            dir_path = base_dir / dir_name
            if not dir_path.exists():
                dir_path.mkdir(parents=True, exist_ok=True)
                self.success.append(f"✅ Created directory '{dir_name}'")

    async def run_verification(self) -> bool:
        """Run all verification checks."""
        print("🔍 Verifying Arcade.dev Examples Setup...\n")

        checks = [
            ("Python Version", self.check_python_version),
            ("Required Packages", self.check_required_packages),
            ("Environment Variables", self.check_environment_variables),
            ("FACT Framework", self.check_fact_framework),
            ("File Structure", self.check_file_structure),
        ]

        # Run synchronous checks
        all_passed = True
        for check_name, check_func in checks:
            print(f"Checking {check_name}...")
            passed = check_func()
            all_passed = all_passed and passed

        # Run async checks
        print("Checking Network Connectivity...")
        await self.check_network_connectivity()

        # Create missing directories
        print("Creating Missing Directories...")
        self.create_missing_directories()

        return all_passed

    def print_summary(self):
        """Print verification summary."""
        print("\n" + "=" * 60)
        print("SETUP VERIFICATION SUMMARY")
        print("=" * 60)

        if self.success:
            print("\n✅ PASSED:")
            for item in self.success:
                print(f"  {item}")

        if self.warnings:
            print("\n⚠️  WARNINGS:")
            for item in self.warnings:
                print(f"  {item}")

        if self.errors:
            print("\n❌ ERRORS:")
            for item in self.errors:
                print(f"  {item}")

        print("\n" + "=" * 60)

        if self.errors:
            print("❌ Setup verification FAILED. Please fix the errors above.")
            print("\nNext steps:")
            print("1. Install missing packages: pip install -r requirements.txt")
            print(
                "2. Copy .env.example to .env and configure your environment variables:"
            )
            print("   cp .env.example .env")
            print("   # Then edit .env with your actual API keys and configuration")
            print("3. Ensure FACT framework is properly installed")
            print("4. Set the required ARCADE_API_KEY in your .env file")
            return False
        else:
            print("✅ Setup verification PASSED!")
            if self.warnings:
                print(
                    "Note: There are warnings that should be addressed for optimal functionality."
                )
            print("\nYou can now run the Arcade.dev examples:")
            print("  python 01_basic_integration/basic_arcade_client.py")
            return True


async def main():
    """Main verification function."""
    verifier = SetupVerifier()

    try:
        success = await verifier.run_verification()
        verifier.print_summary()
        return 0 if success else 1

    except KeyboardInterrupt:
        print("\n❌ Verification interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Verification failed with error: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
