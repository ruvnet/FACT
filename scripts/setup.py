#!/usr/bin/env python3
"""
FACT System Setup Script

This script sets up the FACT system environment, creates necessary directories,
and initializes the database with sample data.
"""

import os
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add src directory to Python path
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

from src.core.config import get_config
from src.db.connection import create_database_manager


async def setup_database():
    """Set up the database with schema and sample data."""
    print("🗄️  Setting up database...")

    try:
        config = get_config()

        # Create data directory if it doesn't exist
        data_dir = Path(config.database_path).parent
        data_dir.mkdir(parents=True, exist_ok=True)
        print(f"✅ Created data directory: {data_dir}")

        # Initialize database
        db_manager = create_database_manager(config.database_path)
        await db_manager.initialize_database()

        # Get database info
        db_info = await db_manager.get_database_info()
        print(f"✅ Database initialized: {config.database_path}")
        print(f"   • File size: {db_info['file_size_bytes']} bytes")
        print(f"   • Tables: {db_info['total_tables']}")

        for table_name, table_info in db_info["tables"].items():
            print(f"   • {table_name}: {table_info['row_count']} rows")

        return True

    except Exception as e:
        print(f"❌ Database setup failed: {e}")
        return False


def setup_directories():
    """Create necessary directories."""
    print("📁 Setting up directories...")

    directories = [
        "data",
        "logs",
        "output",
        "docs/api",
        "docs/deployment",
        "docs/development",
    ]

    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"✅ Created directory: {directory}")


def check_environment():
    """Check environment configuration."""
    print("⚙️  Checking environment configuration...")

    env_file = Path(".env")
    env_example = Path(".env.example")

    if not env_file.exists():
        if env_example.exists():
            print(
                "❌ .env file not found. Please copy .env.example to .env and configure it."
            )
            print("   cp .env.example .env")
            return False
        else:
            print("❌ Neither .env nor .env.example found.")
            return False

    print("✅ .env file found")

    # Check for required environment variables
    required_vars = ["ANTHROPIC_API_KEY", "ARCADE_API_KEY"]
    missing_vars = []

    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)

    if missing_vars:
        print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        print("   Please configure these in your .env file")
        return False

    print("✅ Required environment variables configured")
    return True


def install_dependencies():
    """Check if dependencies are installed."""
    print("📦 Checking dependencies...")

    try:
        # Try importing key dependencies
        import anthropic
        import litellm
        import aiosqlite
        import structlog

        print("✅ Core dependencies installed")
        return True

    except ImportError as e:
        print(f"❌ Missing dependencies: {e}")
        print("   Please install dependencies: pip install -r requirements.txt")
        return False


async def main():
    """Main setup routine."""
    print("🚀 FACT System Setup")
    print("=" * 50)

    success = True

    # Check dependencies
    if not install_dependencies():
        success = False

    # Set up directories
    setup_directories()

    # Check environment
    if not check_environment():
        success = False

    # Set up database (only if environment is configured)
    if success:
        if not await setup_database():
            success = False

    print("\n" + "=" * 50)

    if success:
        print("✅ FACT System setup completed successfully!")
        print("\nNext steps:")
        print("1. Make sure your .env file has valid API keys")
        print("2. Run the system: python driver.py")
        print("3. Try a query: 'What companies are in the Technology sector?'")
    else:
        print("❌ Setup completed with errors. Please resolve the issues above.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
