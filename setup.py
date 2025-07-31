#!/usr/bin/env python3
"""
FACT System - Python Package Setup
Fast API Cache Technology for AI Applications
"""

from setuptools import setup, find_packages
from pathlib import Path
import re

# Read version from __init__.py
def get_version():
    init_file = Path(__file__).parent / "src" / "__init__.py"
    if init_file.exists():
        content = init_file.read_text()
        match = re.search(r"__version__ = ['\"]([^'\"]*)['\"]", content)
        if match:
            return match.group(1)
    return "1.0.0"

# Read README for long description
def get_long_description():
    readme_file = Path(__file__).parent / "README.md"
    if readme_file.exists():
        return readme_file.read_text(encoding="utf-8")
    return "FACT System - Fast API Cache Technology for AI Applications"

# Read requirements
def get_requirements():
    req_file = Path(__file__).parent / "requirements.txt"
    if req_file.exists():
        return [line.strip() for line in req_file.read_text().splitlines() 
                if line.strip() and not line.startswith("#")]
    return []

setup(
    name="fact-system",
    version=get_version(),
    author="FACT Team",
    author_email="team@fact-system.org",
    description="Fast API Cache Technology for AI Applications",
    long_description=get_long_description(),
    long_description_content_type="text/markdown",
    url="https://github.com/fact-team/FACT",
    project_urls={
        "Bug Tracker": "https://github.com/fact-team/FACT/issues",
        "Documentation": "https://github.com/fact-team/FACT/docs",
        "Source Code": "https://github.com/fact-team/FACT",
    },
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Database :: Database Engines/Servers",
        "Topic :: Internet :: WWW/HTTP :: HTTP Servers",
        "Topic :: System :: Caching",
    ],
    python_requires=">=3.9",
    install_requires=get_requirements(),
    extras_require={
        "dev": [
            "pytest>=8.0.0",
            "pytest-asyncio>=0.24.0",
            "pytest-cov>=5.0.0",
            "pytest-mock>=3.14.0",
            "black>=24.8.0",
            "flake8>=7.1.0",
            "mypy>=1.11.0",
            "isort>=5.12.0",
        ],
        "security": [
            "cryptography>=41.0.0",
            "bcrypt>=4.0.0",
            "pyjwt>=2.8.0",
        ],
        "monitoring": [
            "prometheus-client>=0.19.0",
            "opentelemetry-api>=1.20.0",
            "opentelemetry-sdk>=1.20.0",
        ],
        "all": [
            "pytest>=8.0.0",
            "pytest-asyncio>=0.24.0", 
            "pytest-cov>=5.0.0",
            "pytest-mock>=3.14.0",
            "black>=24.8.0",
            "flake8>=7.1.0",
            "mypy>=1.11.0",
            "isort>=5.12.0",
            "cryptography>=41.0.0",
            "bcrypt>=4.0.0",
            "pyjwt>=2.8.0",
            "prometheus-client>=0.19.0",
            "opentelemetry-api>=1.20.0",
            "opentelemetry-sdk>=1.20.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "fact=core.cli:main",
            "fact-benchmark=benchmarking.framework:main",
            "fact-cache=cache.manager:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.yaml", "*.yml", "*.json", "*.md", "*.txt"],
    },
    keywords=[
        "ai", "api", "cache", "performance", "anthropic", "arcade", 
        "sqlite", "async", "optimization", "ml", "nlp"
    ],
    zip_safe=False,
)