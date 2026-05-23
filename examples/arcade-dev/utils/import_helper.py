#!/usr/bin/env python3
"""
Import Helper Utility for FACT Arcade Examples

This module provides utilities to correctly set up Python paths for importing
FACT modules from examples, regardless of their nested directory structure.
"""

import sys
import os
from pathlib import Path
from typing import Optional

# Try to import python-dotenv if available
try:
    from dotenv import load_dotenv

    _DOTENV_AVAILABLE = True
except ImportError:
    _DOTENV_AVAILABLE = False


def setup_fact_imports() -> Path:
    """
    Set up Python path to allow importing FACT modules from any example location.

    This function finds the project root (directory containing 'src') and adds it
    to sys.path if it's not already there.

    Returns:
        Path to the project root directory

    Raises:
        ImportError: If the FACT project root cannot be found
    """
    # Start from the current file's directory and work upward
    current_path = Path(__file__).resolve()

    # Look for the project root by finding the directory containing 'src'
    for parent in current_path.parents:
        src_dir = parent / "src"
        if src_dir.exists() and src_dir.is_dir():
            project_root = parent
            break
    else:
        raise ImportError(
            "Could not find FACT project root. "
            "Please ensure this script is within the FACT project directory structure."
        )

    # Add project root to Python path if not already present
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)

    # Load environment variables from root .env file
    env_file = project_root / ".env"
    if env_file.exists() and _DOTENV_AVAILABLE:
        load_dotenv(env_file)

    return project_root


def verify_fact_imports() -> bool:
    """
    Verify that essential FACT modules can be imported.

    Returns:
        True if all essential modules can be imported, False otherwise
    """
    try:
        # Test importing core FACT modules
        from src.core.driver import FACTDriver
        from src.cache.manager import CacheManager

        return True
    except ImportError as e:
        print(f"Failed to import FACT modules: {e}")
        return False


def get_fact_module_path(module_name: str) -> Optional[Path]:
    """
    Get the full path to a FACT module.

    Args:
        module_name: Name of the module (e.g., 'core.driver', 'cache.manager')

    Returns:
        Path to the module file if found, None otherwise
    """
    try:
        project_root = setup_fact_imports()
        module_parts = module_name.split(".")
        module_path = project_root / "src"

        for part in module_parts:
            module_path = module_path / part

        # Try both .py file and directory with __init__.py
        py_file = module_path.with_suffix(".py")
        if py_file.exists():
            return py_file

        init_file = module_path / "__init__.py"
        if init_file.exists():
            return module_path

        return None
    except Exception:
        return None


def print_fact_module_info():
    """Print information about available FACT modules."""
    try:
        project_root = setup_fact_imports()
        src_dir = project_root / "src"

        print("🔍 FACT Module Information:")
        print(f"  Project Root: {project_root}")
        print(f"  Source Directory: {src_dir}")

        # List available modules
        print("\n📦 Available Modules:")
        for item in src_dir.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                print(f"  📁 {item.name}/")
                # List key files in each module
                for subitem in item.iterdir():
                    if (
                        subitem.is_file()
                        and subitem.suffix == ".py"
                        and subitem.name != "__init__.py"
                    ):
                        print(f"    📄 {subitem.name}")

        # Test imports
        print("\n✅ Import Test:")
        if verify_fact_imports():
            print("  All essential FACT modules can be imported successfully!")
        else:
            print("  ❌ Some FACT modules failed to import")

    except Exception as e:
        print(f"❌ Error getting module info: {e}")


# Auto-setup when module is imported
if __name__ != "__main__":
    setup_fact_imports()


if __name__ == "__main__":
    # When run directly, display module information
    print_fact_module_info()
