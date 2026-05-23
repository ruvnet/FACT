#!/usr/bin/env python3
"""
Comprehensive script to fix imports in the FACT system.

This script fixes both relative imports and local imports to ensure
proper module resolution when scripts are executed from different contexts.
"""

import os
import re
import sys
from pathlib import Path


def fix_all_imports(src_dir):
    """Fix all import issues in Python files within src_dir."""
    src_path = Path(src_dir)

    if not src_path.exists():
        print(f"Error: Source directory {src_dir} does not exist")
        return False

    # Patterns to fix imports
    patterns = [
        # Convert relative imports to absolute imports (from .. -> from module)
        (r"from \.\.([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)", r"from \1"),
        # Fix local imports in __init__.py files (from module -> from .module)
        # This pattern will be applied only in __init__.py files
        (r"^from ([a-zA-Z_][a-zA-Z0-9_]*) import", r"from .\1 import"),
    ]

    files_fixed = 0
    total_replacements = 0

    # Walk through all Python files
    for py_file in src_path.rglob("*.py"):
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                content = f.read()
                lines = content.splitlines()

            original_content = content
            file_replacements = 0

            # Apply relative import fixes
            new_content, count = re.subn(patterns[0][0], patterns[0][1], content)
            content = new_content
            file_replacements += count

            # Apply local import fixes only for __init__.py files and some specific patterns
            if py_file.name == "__init__.py" or py_file.name in [
                "client.py",
                "gateway.py",
            ]:
                # Fix specific patterns for local imports
                lines = content.splitlines()
                for i, line in enumerate(lines):
                    # Fix common local import patterns
                    if (
                        line.strip().startswith("from ")
                        and " import " in line
                        and not line.strip().startswith("from .")
                        and not line.strip().startswith("from core")
                        and not line.strip().startswith("from db")
                        and not line.strip().startswith("from tools")
                        and not line.strip().startswith("from security")
                        and not line.strip().startswith("from arcade")
                        and not line.strip().startswith("from cache")
                        and not line.strip().startswith("from monitoring")
                        and not line.strip().startswith("from benchmarking")
                    ):
                        # Extract module name
                        match = re.match(
                            r"from ([a-zA-Z_][a-zA-Z0-9_]*) import", line.strip()
                        )
                        if match:
                            module_name = match.group(1)
                            # Check if this is a local module (exists in same directory)
                            module_file = py_file.parent / f"{module_name}.py"
                            if module_file.exists():
                                lines[i] = line.replace(
                                    f"from {module_name} import",
                                    f"from .{module_name} import",
                                )
                                file_replacements += 1

                content = "\n".join(lines)

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

    print("🔧 Comprehensive import fixing for FACT system...")
    print(f"Source directory: {src_dir}")
    print("-" * 50)

    success = fix_all_imports(str(src_dir))

    if success:
        print("\n✅ Import fixing completed successfully!")
        print("\nNext step: Test the system with 'python main.py init'")
    else:
        print("\n❌ Import fixing failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
