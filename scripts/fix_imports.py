#!/usr/bin/env python3
"""
Script to fix relative imports in the FACT system.

This script converts all relative imports (from .., from .) to absolute imports
to fix ImportError issues when modules are executed outside of package context.
"""

import os
import re
import sys
from pathlib import Path


def fix_relative_imports(src_dir):
    """Fix all relative imports in Python files within src_dir."""
    src_path = Path(src_dir)

    if not src_path.exists():
        print(f"Error: Source directory {src_dir} does not exist")
        return False

    # Pattern to match relative imports
    patterns = [
        (
            r"from \.\.([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)",
            r"from \1",
        ),  # from ..module
        (
            r"from \.([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)",
            r"from \1",
        ),  # from .module
    ]

    files_fixed = 0
    total_replacements = 0

    # Walk through all Python files
    for py_file in src_path.rglob("*.py"):
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                content = f.read()

            original_content = content
            file_replacements = 0

            # Apply each pattern
            for pattern, replacement in patterns:
                new_content, count = re.subn(pattern, replacement, content)
                content = new_content
                file_replacements += count

            # Write back if changes were made
            if content != original_content:
                with open(py_file, "w", encoding="utf-8") as f:
                    f.write(content)
                files_fixed += 1
                total_replacements += file_replacements
                print(f"Fixed {file_replacements} imports in {py_file}")

        except Exception as e:
            print(f"Error processing {py_file}: {e}")

    print(f"\nSummary:")
    print(f"Files fixed: {files_fixed}")
    print(f"Total replacements: {total_replacements}")

    return True


def main():
    """Main function."""
    script_dir = Path(__file__).parent
    src_dir = script_dir.parent / "src"

    print("🔧 Fixing relative imports in FACT system...")
    print(f"Source directory: {src_dir}")
    print("-" * 50)

    success = fix_relative_imports(str(src_dir))

    if success:
        print("\n✅ Import fixing completed successfully!")
        print("\nNext step: Test the system with 'python main.py init'")
    else:
        print("\n❌ Import fixing failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
