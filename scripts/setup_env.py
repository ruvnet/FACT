#!/usr/bin/env python3
"""
FACT Environment Setup Script

Interactive script to help users configure their FACT environment with proper API keys
and settings. This script guides users through the configuration process step-by-step.

Usage:
    python scripts/setup_env.py
    python scripts/setup_env.py --force    # Overwrite existing .env
    python scripts/setup_env.py --minimal  # Minimal configuration only
"""

import os
import sys
import re
import argparse
from pathlib import Path
from typing import Dict, Optional, List

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class EnvironmentSetup:
    """Interactive environment setup for FACT system."""

    API_KEY_PATTERNS = {
        "ANTHROPIC_API_KEY": r"^sk-ant-api03-[A-Za-z0-9_-]+$",
        "ARCADE_API_KEY": r"^arc_[A-Za-z0-9_-]+$",
        "OPENAI_API_KEY": r"^sk-proj-[A-Za-z0-9_-]+$",
    }

    def __init__(self, force: bool = False, minimal: bool = False):
        self.force = force
        self.minimal = minimal
        self.config: Dict[str, str] = {}

    def print_header(self):
        """Print setup script header."""
        print("🚀 FACT Environment Configuration Setup")
        print("=" * 50)
        print("This script will help you configure your FACT system environment.")
        print("You'll need API keys from Anthropic and Arcade AI to proceed.")
        print()

    def check_existing_env(self) -> bool:
        """Check if .env file already exists."""
        env_path = Path(".env")

        if env_path.exists() and not self.force:
            print("⚠️  A .env file already exists!")
            print(f"📄 Path: {env_path.absolute()}")
            print()

            choice = (
                input(
                    "Do you want to:\n"
                    "  [u] Update existing file\n"
                    "  [o] Overwrite completely\n"
                    "  [c] Cancel setup\n"
                    "Choice (u/o/c): "
                )
                .lower()
                .strip()
            )

            if choice == "c":
                print("❌ Setup cancelled.")
                return False
            elif choice == "o":
                self.force = True
            elif choice == "u":
                # Load existing configuration
                self.load_existing_config()
            else:
                print("❌ Invalid choice. Setup cancelled.")
                return False

        return True

    def load_existing_config(self):
        """Load existing .env configuration."""
        try:
            with open(".env", "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        self.config[key] = value
            print(f"✅ Loaded {len(self.config)} existing configuration items")
        except Exception as e:
            print(f"⚠️  Could not load existing config: {e}")

    def get_api_key(
        self,
        service: str,
        key_name: str,
        pattern: str,
        description: str,
        url: str,
        required: bool = True,
    ) -> Optional[str]:
        """Get API key from user with validation."""

        # Check if key already exists
        existing_key = self.config.get(key_name, "")
        if existing_key and existing_key != f"your_{key_name.lower()}_here":
            print(f"📋 {service} API Key: Already configured")
            keep = input(f"   Keep existing key? [Y/n]: ").lower().strip()
            if keep != "n":
                return existing_key

        print(f"\n🔑 {service} API Key Configuration")
        print(f"   Description: {description}")
        print(f"   Get your key: {url}")
        print(f"   Format: {pattern}")

        if not required:
            skip = input(f"   Skip {service} configuration? [y/N]: ").lower().strip()
            if skip == "y":
                return None

        while True:
            key = input(f"   Enter your {service} API key: ").strip()

            if not key:
                if required:
                    print("   ❌ This key is required. Please enter a valid key.")
                    continue
                else:
                    return None

            # Validate format
            if re.match(self.API_KEY_PATTERNS[key_name], key):
                print(f"   ✅ Valid {service} API key format")
                return key
            else:
                print(f"   ❌ Invalid key format. Expected: {pattern}")
                print(f"   💡 Make sure you copied the full key correctly")

                retry = input("   Try again? [Y/n]: ").lower().strip()
                if retry == "n":
                    if required:
                        print("   ❌ This key is required to continue.")
                        continue
                    else:
                        return None

    def configure_required_keys(self) -> bool:
        """Configure required API keys."""
        print("\n📋 REQUIRED API KEYS")
        print("-" * 30)

        # Anthropic API Key
        anthropic_key = self.get_api_key(
            service="Anthropic Claude",
            key_name="ANTHROPIC_API_KEY",
            pattern="sk-ant-api03-*",
            description="Claude API for LLM capabilities",
            url="https://console.anthropic.com/",
            required=True,
        )

        if not anthropic_key:
            print("❌ Anthropic API key is required. Setup cannot continue.")
            return False

        self.config["ANTHROPIC_API_KEY"] = anthropic_key

        # Arcade API Key
        arcade_key = self.get_api_key(
            service="Arcade AI",
            key_name="ARCADE_API_KEY",
            pattern="arc_*",
            description="Arcade AI for tool execution",
            url="https://arcade-ai.com/dashboard",
            required=True,
        )

        if not arcade_key:
            print("❌ Arcade AI API key is required. Setup cannot continue.")
            return False

        self.config["ARCADE_API_KEY"] = arcade_key

        return True

    def configure_optional_keys(self) -> bool:
        """Configure optional API keys."""
        if self.minimal:
            return True

        print("\n📋 OPTIONAL API KEYS")
        print("-" * 30)

        # OpenAI API Key
        openai_key = self.get_api_key(
            service="OpenAI",
            key_name="OPENAI_API_KEY",
            pattern="sk-proj-*",
            description="OpenAI API for extended LLM capabilities",
            url="https://platform.openai.com/api-keys",
            required=False,
        )

        if openai_key:
            self.config["OPENAI_API_KEY"] = openai_key

        return True

    def configure_system_settings(self):
        """Configure system settings."""
        if self.minimal:
            # Set minimal required settings
            defaults = {
                "ARCADE_BASE_URL": "https://api.arcade-ai.com",
                "DATABASE_PATH": "data/fact_demo.db",
                "CLAUDE_MODEL": "claude-3-5-sonnet-20241022",
                "LOG_LEVEL": "INFO",
            }

            for key, value in defaults.items():
                if key not in self.config:
                    self.config[key] = value

            return

        print("\n📋 SYSTEM CONFIGURATION")
        print("-" * 30)

        # Claude Model Selection
        models = [
            "claude-3-5-sonnet-20241022",
            "claude-3-haiku-20240307",
            "claude-3-opus-20240229",
        ]

        current_model = self.config.get("CLAUDE_MODEL", models[0])
        print(f"🤖 Claude Model (current: {current_model})")
        print("   Available models:")
        for i, model in enumerate(models, 1):
            marker = " (recommended)" if model == models[0] else ""
            print(f"     {i}. {model}{marker}")

        choice = input(
            f"   Select model [1-{len(models)}] or press Enter for current: "
        ).strip()
        if choice.isdigit() and 1 <= int(choice) <= len(models):
            self.config["CLAUDE_MODEL"] = models[int(choice) - 1]
        elif not choice:
            self.config["CLAUDE_MODEL"] = current_model

        # Log Level
        log_levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
        current_log = self.config.get("LOG_LEVEL", "INFO")
        print(f"\n📊 Log Level (current: {current_log})")
        print("   Available levels:")
        for i, level in enumerate(log_levels, 1):
            marker = " (recommended)" if level == "INFO" else ""
            print(f"     {i}. {level}{marker}")

        choice = input(
            f"   Select level [1-{len(log_levels)}] or press Enter for current: "
        ).strip()
        if choice.isdigit() and 1 <= int(choice) <= len(log_levels):
            self.config["LOG_LEVEL"] = log_levels[int(choice) - 1]
        elif not choice:
            self.config["LOG_LEVEL"] = current_log

        # Set other defaults
        defaults = {
            "ARCADE_BASE_URL": "https://api.arcade-ai.com",
            "DATABASE_PATH": "data/fact_demo.db",
            "SYSTEM_PROMPT": "You are a deterministic finance assistant. When uncertain, request data via tools.",
            "MAX_RETRIES": "3",
            "REQUEST_TIMEOUT": "30",
        }

        for key, value in defaults.items():
            if key not in self.config:
                self.config[key] = value

    def configure_security_settings(self):
        """Configure security settings."""
        if self.minimal:
            # Set secure defaults for minimal setup
            security_defaults = {
                "STRICT_MODE": "true",
                "DEBUG_MODE": "false",
                "ENFORCE_HTTPS": "true",
                "RATE_LIMITING_ENABLED": "true",
            }

            for key, value in security_defaults.items():
                if key not in self.config:
                    self.config[key] = value

            return

        print("\n🔒 SECURITY CONFIGURATION")
        print("-" * 30)

        # Environment type
        env_types = {
            "production": {
                "STRICT_MODE": "true",
                "DEBUG_MODE": "false",
                "ENFORCE_HTTPS": "true",
                "RATE_LIMITING_ENABLED": "true",
                "LOG_SECURITY_EVENTS": "true",
            },
            "development": {
                "STRICT_MODE": "false",
                "DEBUG_MODE": "true",
                "ENFORCE_HTTPS": "false",
                "RATE_LIMITING_ENABLED": "false",
                "LOG_SECURITY_EVENTS": "false",
            },
        }

        print("🏗️  Environment Type:")
        print("   1. Production (strict security)")
        print("   2. Development (relaxed security)")

        choice = input("   Select environment [1-2]: ").strip()

        if choice == "1":
            env_config = env_types["production"]
            print("   ✅ Production security settings applied")
        elif choice == "2":
            env_config = env_types["development"]
            print("   ✅ Development security settings applied")
        else:
            env_config = env_types["production"]
            print("   ✅ Default (production) security settings applied")

        # Apply security settings
        for key, value in env_config.items():
            if key not in self.config:
                self.config[key] = value

    def write_env_file(self) -> bool:
        """Write configuration to .env file."""
        try:
            # Create data directory if it doesn't exist
            data_dir = Path("data")
            data_dir.mkdir(exist_ok=True)

            # Generate .env content
            env_content = self.generate_env_content()

            # Write to file
            with open(".env", "w") as f:
                f.write(env_content)

            print(f"✅ Configuration saved to .env")
            return True

        except Exception as e:
            print(f"❌ Failed to write .env file: {e}")
            return False

    def generate_env_content(self) -> str:
        """Generate .env file content with proper formatting."""
        content = [
            "# FACT System Environment Configuration",
            "# Generated by setup script",
            "# Do not commit this file to version control!",
            "",
            "# =============================================================================",
            "# REQUIRED API KEYS",
            "# =============================================================================",
            "",
        ]

        # Required API keys
        required_keys = ["ANTHROPIC_API_KEY", "ARCADE_API_KEY"]
        for key in required_keys:
            if key in self.config:
                content.append(f"{key}={self.config[key]}")

        content.extend(
            [
                "",
                "# =============================================================================",
                "# OPTIONAL API KEYS",
                "# =============================================================================",
                "",
            ]
        )

        # Optional API keys
        optional_keys = ["OPENAI_API_KEY", "ENCRYPTION_KEY", "CACHE_ENCRYPTION_KEY"]
        for key in optional_keys:
            if key in self.config:
                content.append(f"{key}={self.config[key]}")
            else:
                content.append(f"# {key}=your_{key.lower()}_here")

        content.extend(
            [
                "",
                "# =============================================================================",
                "# SYSTEM CONFIGURATION",
                "# =============================================================================",
                "",
            ]
        )

        # System configuration
        system_keys = [
            "ARCADE_BASE_URL",
            "DATABASE_PATH",
            "CLAUDE_MODEL",
            "SYSTEM_PROMPT",
            "MAX_RETRIES",
            "REQUEST_TIMEOUT",
            "LOG_LEVEL",
        ]

        for key in system_keys:
            if key in self.config:
                content.append(f"{key}={self.config[key]}")

        content.extend(
            [
                "",
                "# =============================================================================",
                "# SECURITY CONFIGURATION",
                "# =============================================================================",
                "",
            ]
        )

        # Security configuration
        security_keys = [
            "STRICT_MODE",
            "DEBUG_MODE",
            "ENFORCE_HTTPS",
            "RATE_LIMITING_ENABLED",
            "LOG_SECURITY_EVENTS",
        ]

        for key in security_keys:
            if key in self.config:
                content.append(f"{key}={self.config[key]}")

        content.extend(
            [
                "",
                "# =============================================================================",
                "# CACHE CONFIGURATION (Defaults will be used if not specified)",
                "# =============================================================================",
                "",
                "# CACHE_PREFIX=fact_v1",
                "# CACHE_MIN_TOKENS=50",
                "# CACHE_MAX_SIZE=100MB",
                "# CACHE_TTL_SECONDS=3600",
                "",
                "# For more configuration options, see:",
                "# - docs/environment-configuration-guide.md",
                "# - .env.template",
                "",
            ]
        )

        return "\n".join(content)

    def run_validation(self) -> bool:
        """Run configuration validation."""
        print("\n🔍 VALIDATING CONFIGURATION")
        print("-" * 30)

        try:
            # Import and run validation
            from pathlib import Path
            import subprocess

            result = subprocess.run(
                [sys.executable, "scripts/validate_env.py", "--verbose"],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                print("✅ Configuration validation passed!")
                return True
            else:
                print("❌ Configuration validation failed:")
                print(result.stdout)
                print(result.stderr)
                return False

        except Exception as e:
            print(f"⚠️  Could not run validation: {e}")
            print("💡 You can manually validate later with:")
            print("   python scripts/validate_env.py --verbose")
            return True

    def print_next_steps(self):
        """Print next steps for the user."""
        print("\n🎉 SETUP COMPLETE!")
        print("=" * 50)
        print("Your FACT environment is now configured.")
        print()
        print("📋 Next Steps:")
        print("1. Validate your configuration:")
        print("   python scripts/validate_env.py --verbose")
        print()
        print("2. Test system connectivity:")
        print("   python scripts/validate_env.py --check-connectivity")
        print()
        print("3. Initialize the system:")
        print("   python scripts/init_environment.py")
        print()
        print("4. Start using FACT:")
        print("   python -m src.core.cli")
        print()
        print("📚 Additional Resources:")
        print("• Configuration Guide: docs/environment-configuration-guide.md")
        print("• Installation Guide: docs/2_installation_setup.md")
        print("• Troubleshooting: README.md")
        print()
        print("🔒 Security Reminder:")
        print("• Never commit .env files to version control")
        print("• Rotate your API keys regularly")
        print("• Use different keys for different environments")

    def run_setup(self) -> bool:
        """Run the complete setup process."""
        self.print_header()

        # Check existing environment
        if not self.check_existing_env():
            return False

        # Configure required API keys
        if not self.configure_required_keys():
            return False

        # Configure optional API keys
        if not self.configure_optional_keys():
            return False

        # Configure system settings
        self.configure_system_settings()

        # Configure security settings
        self.configure_security_settings()

        # Write configuration file
        if not self.write_env_file():
            return False

        # Validate configuration
        validation_success = self.run_validation()

        # Print next steps
        self.print_next_steps()

        return validation_success


def main():
    """Main setup entry point."""
    parser = argparse.ArgumentParser(
        description="Interactive FACT environment setup",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/setup_env.py              # Interactive setup
  python scripts/setup_env.py --force      # Overwrite existing .env
  python scripts/setup_env.py --minimal    # Minimal configuration only

This script will guide you through configuring your FACT environment
with the required API keys and optimal settings.
        """,
    )

    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Overwrite existing .env file without prompting",
    )

    parser.add_argument(
        "--minimal",
        "-m",
        action="store_true",
        help="Set up minimal configuration with defaults",
    )

    args = parser.parse_args()

    # Run setup
    setup = EnvironmentSetup(force=args.force, minimal=args.minimal)
    success = setup.run_setup()

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
