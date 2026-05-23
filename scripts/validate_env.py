#!/usr/bin/env python3
"""
FACT Environment Configuration Validator

This script validates the environment configuration against the specification
requirements defined in docs/configuration-requirements-specification.md

Usage:
    python scripts/validate_env.py
    python scripts/validate_env.py --verbose
    python scripts/validate_env.py --check-connectivity
"""

import os
import sys
import re
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

try:
    from dotenv import load_dotenv
except ImportError:
    print(
        "Warning: python-dotenv not installed. Install with: pip install python-dotenv"
    )
    load_dotenv = None


class ConfigurationValidator:
    """Validates FACT system configuration against requirements."""

    # API Key validation patterns from specification
    API_KEY_PATTERNS = {
        "ANTHROPIC_API_KEY": r"^sk-ant-api03-[A-Za-z0-9_-]+$",
        "ARCADE_API_KEY": r"^arc_[A-Za-z0-9_-]+$",
        "OPENAI_API_KEY": r"^sk-proj-[A-Za-z0-9_-]+$",
    }

    # Required configuration keys
    REQUIRED_KEYS = ["ANTHROPIC_API_KEY", "ARCADE_API_KEY"]

    # Parameter validation rules
    PARAMETER_RULES = {
        "MAX_RETRIES": {"type": int, "min": 1, "max": 10, "default": 3},
        "REQUEST_TIMEOUT": {"type": int, "min": 5, "max": 300, "default": 30},
        "CACHE_TTL_SECONDS": {"type": int, "min": 60, "max": 86400, "default": 3600},
        "CACHE_MIN_TOKENS": {"type": int, "min": 1, "max": 1000, "default": 50},
        "VALIDATION_MAX_STRING_LENGTH": {
            "type": int,
            "min": 1,
            "max": 100000,
            "default": 10000,
        },
        "LOG_LEVEL": {
            "type": str,
            "choices": ["DEBUG", "INFO", "WARNING", "ERROR"],
            "default": "INFO",
        },
        "CLAUDE_MODEL": {
            "type": str,
            "pattern": r"^claude-3-",
            "default": "claude-3-5-sonnet-20241022",
        },
        "CACHE_PREFIX": {
            "type": str,
            "pattern": r"^[A-Za-z0-9_]+$",
            "min_length": 1,
            "max_length": 50,
            "default": "fact_v1",
        },
    }

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.config: Dict[str, Any] = {}

    def load_environment(self) -> bool:
        """Load environment configuration from .env file and system environment."""
        try:
            # Load .env file if it exists
            env_path = Path(".env")
            if env_path.exists():
                if load_dotenv:
                    load_dotenv(env_path)
                    self.log_info(f"✅ Loaded configuration from {env_path}")
                else:
                    self.log_warning(
                        "⚠️  python-dotenv not available, using system environment only"
                    )
            else:
                self.log_warning(
                    "⚠️  No .env file found, using system environment variables"
                )

            # Load all environment variables
            self.config = dict(os.environ)
            return True

        except Exception as e:
            self.errors.append(f"Failed to load environment: {e}")
            return False

    def validate_required_keys(self) -> bool:
        """Validate that all required API keys are present."""
        missing_keys = []
        invalid_keys = []

        for key in self.REQUIRED_KEYS:
            value = self.config.get(key, "").strip()

            if not value or value == f"your_{key.lower()}_here":
                missing_keys.append(key)
                continue

            # Validate format
            pattern = self.API_KEY_PATTERNS.get(key)
            if pattern and not re.match(pattern, value):
                invalid_keys.append(f"{key} (format: {pattern})")

        if missing_keys:
            self.errors.append(
                f"Missing required configuration keys: {', '.join(missing_keys)}"
            )

        if invalid_keys:
            self.errors.append(f"Invalid API key format: {', '.join(invalid_keys)}")

        return len(missing_keys) == 0 and len(invalid_keys) == 0

    def validate_optional_keys(self) -> bool:
        """Validate optional API keys if present."""
        invalid_keys = []

        for key, pattern in self.API_KEY_PATTERNS.items():
            if key in self.REQUIRED_KEYS:
                continue

            value = self.config.get(key, "").strip()
            if value and value != f"your_{key.lower()}_here":
                if not re.match(pattern, value):
                    invalid_keys.append(f"{key} (format: {pattern})")

        if invalid_keys:
            self.errors.append(
                f"Invalid optional API key format: {', '.join(invalid_keys)}"
            )

        return len(invalid_keys) == 0

    def validate_parameters(self) -> bool:
        """Validate configuration parameters against rules."""
        parameter_errors = []

        for param, rules in self.PARAMETER_RULES.items():
            value = self.config.get(param)

            if value is None:
                if self.verbose:
                    self.log_info(
                        f"📋 {param}: Using default value ({rules.get('default')})"
                    )
                continue

            # Type validation
            if rules["type"] == int:
                try:
                    int_value = int(value)
                    if "min" in rules and int_value < rules["min"]:
                        parameter_errors.append(
                            f"{param}={value} below minimum {rules['min']}"
                        )
                    elif "max" in rules and int_value > rules["max"]:
                        parameter_errors.append(
                            f"{param}={value} above maximum {rules['max']}"
                        )
                except ValueError:
                    parameter_errors.append(f"{param}={value} is not a valid integer")

            elif rules["type"] == str:
                if "choices" in rules and value not in rules["choices"]:
                    parameter_errors.append(
                        f"{param}={value} not in {rules['choices']}"
                    )
                elif "pattern" in rules and not re.match(rules["pattern"], value):
                    parameter_errors.append(
                        f"{param}={value} doesn't match pattern {rules['pattern']}"
                    )
                elif "min_length" in rules and len(value) < rules["min_length"]:
                    parameter_errors.append(
                        f"{param}={value} too short (min: {rules['min_length']})"
                    )
                elif "max_length" in rules and len(value) > rules["max_length"]:
                    parameter_errors.append(
                        f"{param}={value} too long (max: {rules['max_length']})"
                    )

        if parameter_errors:
            self.errors.extend(parameter_errors)

        return len(parameter_errors) == 0

    def validate_cache_size(self) -> bool:
        """Validate cache size parameter format."""
        cache_size = self.config.get("CACHE_MAX_SIZE", "").strip()

        if not cache_size:
            if self.verbose:
                self.log_info("📋 CACHE_MAX_SIZE: Using default value (100MB)")
            return True

        # Validate cache size format
        cache_pattern = r"^(\d+)(K|M|G|T)?B$"
        match = re.match(cache_pattern, cache_size.upper())

        if not match:
            self.errors.append(
                f"CACHE_MAX_SIZE={cache_size} invalid format (expected: [number][KMGT]B)"
            )
            return False

        # Convert to bytes for range validation
        size_value = int(match.group(1))
        unit = match.group(2) or ""

        multipliers = {"": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}
        bytes_value = size_value * multipliers[unit]

        min_bytes = 1024**2  # 1MB
        max_bytes = 10 * 1024**3  # 10GB

        if bytes_value < min_bytes:
            self.errors.append(f"CACHE_MAX_SIZE={cache_size} below minimum 1MB")
            return False
        elif bytes_value > max_bytes:
            self.errors.append(f"CACHE_MAX_SIZE={cache_size} above maximum 10GB")
            return False

        return True

    def validate_file_paths(self) -> bool:
        """Validate file path configurations."""
        path_errors = []

        # Check database path
        db_path = self.config.get("DATABASE_PATH", "data/fact_demo.db")
        db_dir = Path(db_path).parent

        if not db_dir.exists():
            try:
                db_dir.mkdir(parents=True, exist_ok=True)
                self.log_info(f"✅ Created database directory: {db_dir}")
            except Exception as e:
                path_errors.append(f"Cannot create database directory {db_dir}: {e}")

        if path_errors:
            self.errors.extend(path_errors)

        return len(path_errors) == 0

    def check_connectivity(self) -> bool:
        """Test connectivity to configured services (optional)."""
        if not self.config.get("ANTHROPIC_API_KEY") or not self.config.get(
            "ARCADE_API_KEY"
        ):
            self.warnings.append(
                "⚠️  Skipping connectivity tests - API keys not configured"
            )
            return True

        connectivity_results = []

        # Test Anthropic API
        try:
            import requests

            response = requests.get("https://api.anthropic.com", timeout=10)
            connectivity_results.append(
                f"✅ Anthropic API reachable (status: {response.status_code})"
            )
        except Exception as e:
            connectivity_results.append(f"❌ Anthropic API unreachable: {e}")

        # Test Arcade API
        arcade_url = self.config.get("ARCADE_BASE_URL", "https://api.arcade-ai.com")
        try:
            import requests

            response = requests.get(arcade_url, timeout=10)
            connectivity_results.append(
                f"✅ Arcade API reachable (status: {response.status_code})"
            )
        except Exception as e:
            connectivity_results.append(f"❌ Arcade API unreachable: {e}")

        if self.verbose:
            for result in connectivity_results:
                print(result)

        return True

    def generate_recommendations(self) -> List[str]:
        """Generate configuration recommendations."""
        recommendations = []

        # Check for optimal settings
        if (
            not self.config.get("STRICT_MODE")
            or self.config.get("STRICT_MODE").lower() != "true"
        ):
            recommendations.append("Enable STRICT_MODE=true for production security")

        if (
            not self.config.get("RATE_LIMITING_ENABLED")
            or self.config.get("RATE_LIMITING_ENABLED").lower() != "true"
        ):
            recommendations.append("Enable RATE_LIMITING_ENABLED=true for production")

        if self.config.get("DEBUG_MODE", "").lower() == "true":
            recommendations.append("Disable DEBUG_MODE=false for production")

        if self.config.get("LOG_LEVEL", "").upper() == "DEBUG":
            recommendations.append("Use LOG_LEVEL=INFO or higher for production")

        return recommendations

    def run_validation(self, check_connectivity: bool = False) -> bool:
        """Run complete validation suite."""
        self.log_info("🔍 FACT Environment Configuration Validation")
        self.log_info("=" * 50)

        # Step 1: Load environment
        if not self.load_environment():
            return False

        # Step 2: Validate required keys
        self.log_info("\n📋 Validating required API keys...")
        self.validate_required_keys()

        # Step 3: Validate optional keys
        self.log_info("📋 Validating optional API keys...")
        self.validate_optional_keys()

        # Step 4: Validate parameters
        self.log_info("📋 Validating configuration parameters...")
        self.validate_parameters()

        # Step 5: Validate cache size
        self.log_info("📋 Validating cache configuration...")
        self.validate_cache_size()

        # Step 6: Validate file paths
        self.log_info("📋 Validating file paths...")
        self.validate_file_paths()

        # Step 7: Connectivity check (optional)
        if check_connectivity:
            self.log_info("📋 Testing service connectivity...")
            self.check_connectivity()

        # Step 8: Generate recommendations
        recommendations = self.generate_recommendations()

        # Report results
        self.print_results(recommendations)

        return len(self.errors) == 0

    def print_results(self, recommendations: List[str]):
        """Print validation results."""
        print(f"\n{'=' * 50}")
        print("📊 VALIDATION RESULTS")
        print(f"{'=' * 50}")

        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)}):")
            for error in self.errors:
                print(f"   • {error}")

        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"   • {warning}")

        if recommendations:
            print(f"\n💡 RECOMMENDATIONS ({len(recommendations)}):")
            for rec in recommendations:
                print(f"   • {rec}")

        if not self.errors and not self.warnings:
            print("\n✅ Configuration validation passed!")
            print("🎉 Your FACT system is ready to use!")
        elif not self.errors:
            print(
                f"\n✅ Configuration validation passed with {len(self.warnings)} warnings"
            )
        else:
            print(
                f"\n❌ Configuration validation failed with {len(self.errors)} errors"
            )
            print("\n🔧 RECOVERY SUGGESTIONS:")
            print("   1. Update your .env file with correct API keys")
            print("   2. Verify parameter values are within allowed ranges")
            print("   3. Check file paths and permissions")
            print("   4. Run: python scripts/validate_env.py --verbose")

    def log_info(self, message: str):
        """Log info message if verbose mode is enabled."""
        if self.verbose:
            print(message)

    def log_warning(self, message: str):
        """Log warning message."""
        self.warnings.append(message)
        if self.verbose:
            print(message)


def main():
    """Main validation entry point."""
    parser = argparse.ArgumentParser(
        description="Validate FACT environment configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/validate_env.py                    # Basic validation
  python scripts/validate_env.py --verbose          # Detailed output
  python scripts/validate_env.py --check-connectivity  # Include connectivity tests

Exit codes:
  0 = Validation passed
  1 = Validation failed
        """,
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose output"
    )

    parser.add_argument(
        "--check-connectivity",
        "-c",
        action="store_true",
        help="Test connectivity to external services",
    )

    args = parser.parse_args()

    # Run validation
    validator = ConfigurationValidator(verbose=args.verbose)
    success = validator.run_validation(check_connectivity=args.check_connectivity)

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
