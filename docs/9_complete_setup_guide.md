# FACT System - Complete Setup and Configuration Guide

## Overview

This comprehensive guide provides step-by-step instructions for setting up, configuring, and optimizing the FACT (Fast Augmented Context Tools) benchmark system. Follow this guide to get your system running correctly with optimal performance.

## Table of Contents

1. [Quick Start Setup](#quick-start-setup)
2. [API Key Configuration](#api-key-configuration)
3. [Performance Optimization](#performance-optimization)
4. [System Validation](#system-validation)
5. [Troubleshooting Common Issues](#troubleshooting-common-issues)
6. [Advanced Configuration](#advanced-configuration)

## Quick Start Setup

### Prerequisites Verification

Before beginning, verify your system meets these requirements:

```bash
# Check Python version (must be 3.8+, recommended 3.11+)
python --version

# Check available disk space (minimum 2GB)
df -h .

# Check memory (minimum 2GB available)
free -h
```

### Automated Installation

The fastest way to get FACT running:

```bash
# 1. Clone and enter directory
git clone https://github.com/your-org/fact-system.git
cd fact-system

# 2. Run automated setup
chmod +x scripts/setup.sh
./scripts/setup.sh

# 3. The script will prompt for API keys - have them ready
```

The setup script automatically:
- Creates Python virtual environment
- Installs all dependencies
- Generates configuration template
- Initializes database with sample data
- Performs basic system validation

### Manual Installation

If you prefer manual control or the automated setup fails:

```bash
# 1. Clone repository
git clone https://github.com/your-org/fact-system.git
cd fact-system

# 2. Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows

# 3. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .

# 4. Initialize configuration
cp .env.example .env
```

## API Key Configuration

### Required API Keys

FACT requires two API keys for operation:

#### 1. Anthropic API Key (Required)

**Purpose**: Access to Claude Sonnet-4 for natural language processing

**Setup Steps**:
1. Visit [console.anthropic.com](https://console.anthropic.com)
2. Sign in or create account
3. Navigate to "API Keys" section
4. Click "Create Key" and copy the generated key
5. Ensure billing is set up for production use

**Testing**:
```bash
# Test Anthropic API connection
python -c "
import os
from anthropic import Anthropic
try:
    client = Anthropic(api_key='your_key_here')
    print('✅ Anthropic API: Connected successfully')
except Exception as e:
    print(f'❌ Anthropic API Error: {e}')
"
```

#### 2. Arcade API Key (Required)

**Purpose**: Tool execution and database access

**Setup Steps**:
1. Visit [arcade.dev](https://arcade.dev)
2. Create account and new project
3. Navigate to "API Keys" and generate key
4. Free tier available for development

**Testing**:
```bash
# Test Arcade API connection
python -c "
from arcade import Arcade
try:
    client = Arcade(api_key='your_key_here')
    print('✅ Arcade API: Connected successfully')
except Exception as e:
    print(f'❌ Arcade API Error: {e}')
"
```

### Configuration File Setup

Edit your `.env` file with the following configuration:

```bash
# API Keys (REQUIRED)
ANTHROPIC_API_KEY=your_anthropic_api_key_here
ARCADE_API_KEY=your_arcade_api_key_here

# Database Configuration
DATABASE_PATH=data/fact_demo.db

# Claude Model Configuration
CLAUDE_MODEL=claude-3-5-sonnet-20241022

# Cache Configuration (Performance Critical)
CACHE_PREFIX=fact_v1
CACHE_TTL=3600
CACHE_MAX_SIZE=5000
CACHE_WARMING_ENABLED=true

# Performance Configuration
MAX_RETRIES=3
REQUEST_TIMEOUT=30
MAX_CONCURRENT_QUERIES=50
QUERY_TIMEOUT=30

# Logging Configuration
LOG_LEVEL=INFO
LOG_FILE=logs/fact.log
```

### Environment Variables Validation

Validate your configuration:

```bash
# Quick validation
python main.py validate

# Detailed validation
python -c "
from src.core.config import load_config
try:
    config = load_config()
    print('✅ Configuration loaded successfully')
    print(f'Database: {config.database_path}')
    print(f'Cache prefix: {config.cache_prefix}')
    print(f'Claude model: {config.claude_model}')
except Exception as e:
    print(f'❌ Configuration error: {e}')
"
```

## Performance Optimization

### Database Initialization

Initialize the database with optimized settings:

```bash
# Initialize with sample data
python main.py init

# Verify database setup
sqlite3 data/fact_demo.db "
SELECT 'Companies: ' || COUNT(*) FROM companies;
SELECT 'Financial records: ' || COUNT(*) FROM financial_records;
"
```

### Cache Optimization

Configure cache for optimal performance:

```bash
# Advanced cache settings for .env file
CACHE_MAX_SIZE=5000                    # Increase for better hit rates
CACHE_TTL=7200                        # 2 hours for stable data
CACHE_WARMING_ENABLED=true            # Enable automatic warming
CACHE_WARMING_QUERIES=["What is Q1 revenue?", "Show me company list", "What are the key financial metrics?"]

# Memory pressure settings
CACHE_MEMORY_PRESSURE_THRESHOLD=0.8   # Start cleanup at 80% utilization
CACHE_EMERGENCY_CLEANUP_RATIO=0.3     # Emergency cleanup removes 30%
```

### Performance Tuning Parameters

Optimize for your hardware and usage patterns:

```bash
# For high-performance systems
CONNECTION_POOL_SIZE=20
CONCURRENT_QUERIES_LIMIT=100
QUERY_TIMEOUT=60

# For resource-constrained systems
CONNECTION_POOL_SIZE=5
CONCURRENT_QUERIES_LIMIT=20
QUERY_TIMEOUT=30

# Enable performance monitoring
METRICS_ENABLED=true
METRICS_RETENTION_DAYS=30
HEALTH_CHECK_INTERVAL=60
```

### Cache Warming Strategy

Implement intelligent cache warming:

```python
# Manual cache warming for common queries
from src.cache.warming import get_cache_warmer
import asyncio

async def warm_cache():
    warmer = get_cache_warmer()
    common_queries = [
        "What companies are in the technology sector?",
        "Show me Q1 2025 revenue for all companies", 
        "What are the top performing companies?",
        "Calculate year-over-year growth",
        "What is the average profit margin?"
    ]
    
    result = await warmer.warm_cache_with_queries(
        common_queries, 
        concurrent=True
    )
    print(f"Cache warming completed: {result['successful_queries']} queries cached")

# Run cache warming
asyncio.run(warm_cache())
```

## System Validation

### Comprehensive System Check

Run the complete validation suite:

```bash
# Full system validation
python main.py validate
```

Expected output:
```
✅ Environment configuration: Valid
✅ API keys: Connected and functional
✅ Database: Initialized and populated
✅ Tools: Registered and available
✅ Cache: Configured and operational
✅ System: Ready for use
```

### Performance Benchmark

Test system performance against targets:

```bash
# Run performance benchmarks
python scripts/run_benchmarks.py --iterations 10

# Expected targets:
# Cache Hit Latency: ≤ 48ms
# Cache Miss Latency: ≤ 140ms
# Cache Hit Rate: ≥ 60%
# Cost Reduction: ≥ 90%
```

### Individual Component Testing

Test each component separately:

```bash
# Test database connection
python -c "
from src.db.connection import get_connection
try:
    conn = get_connection()
    cursor = conn.execute('SELECT COUNT(*) FROM companies')
    count = cursor.fetchone()[0]
    print(f'✅ Database: {count} companies loaded')
    conn.close()
except Exception as e:
    print(f'❌ Database error: {e}')
"

# Test tool registration
python -c "
from src.tools.registry import get_tool_registry
registry = get_tool_registry()
tools = registry.list_tools()
print(f'✅ Tools registered: {len(tools)}')
for tool in tools:
    print(f'  - {tool}')
"

# Test cache functionality
python -c "
from src.cache.manager import CacheManager
cache = CacheManager()
print('✅ Cache: Operational')
metrics = cache.get_metrics()
print(f'Cache size: {metrics.total_size} bytes')
print(f'Hit rate: {metrics.hit_rate:.1f}%')
"
```

## Troubleshooting Common Issues

### API Key Issues

**Symptoms**: Authentication failed, 401 errors, invalid API key messages

**Solutions**:
```bash
# 1. Verify keys are set correctly
grep API_KEY .env

# 2. Check for common formatting issues
python -c "
import os
anthropic_key = os.getenv('ANTHROPIC_API_KEY', '')
arcade_key = os.getenv('ARCADE_API_KEY', '')
print(f'Anthropic key length: {len(anthropic_key)}')
print(f'Arcade key length: {len(arcade_key)}')
print(f'Anthropic key starts with: {anthropic_key[:10]}...')
print(f'Arcade key starts with: {arcade_key[:10]}...')
"

# 3. Test API connectivity
python -c "
import asyncio
from src.core.driver import test_api_connections
asyncio.run(test_api_connections())
"
```

### Database Issues

**Symptoms**: Database locked, connection failures, missing data

**Solutions**:
```bash
# 1. Check database file permissions
ls -la data/fact_demo.db

# 2. Test database integrity
sqlite3 data/fact_demo.db "PRAGMA integrity_check;"

# 3. Reset database if corrupted
cp data/fact_demo.db data/fact_demo.db.backup
rm data/fact_demo.db
python main.py init
```

### Performance Issues

**Symptoms**: Slow responses, low cache hit rates, high latency

**Solutions**:
```bash
# 1. Check current performance metrics
python main.py cli
# Then in CLI: metrics

# 2. Warm cache with common queries
python -c "
import asyncio
from src.cache.warming import get_cache_warmer

async def emergency_warming():
    warmer = get_cache_warmer()
    result = await warmer.warm_cache_intelligently(max_queries=50)
    print(f'Warming completed: {result[\"cache_entries_created\"]} entries')

asyncio.run(emergency_warming())
"

# 3. Clear and rebuild cache if needed
python main.py --clear-cache
python main.py cli
```

### Memory Issues

**Symptoms**: High memory usage, out of memory errors, system slowdown

**Solutions**:
```bash
# 1. Monitor current memory usage
python -c "
import psutil
import os
process = psutil.Process(os.getpid())
memory_mb = process.memory_info().rss / 1024 / 1024
print(f'Current memory usage: {memory_mb:.1f} MB')
"

# 2. Reduce cache size (edit .env)
CACHE_MAX_SIZE=1000
CACHE_MEMORY_PRESSURE_THRESHOLD=0.7

# 3. Force cache cleanup
python -c "
from src.cache.manager import CacheManager
cache = CacheManager()
cache.cleanup_expired()
cache.evict_lru(keep_count=500)
print('Cache cleanup completed')
"
```

## Advanced Configuration

### Production Deployment Settings

For production environments:

```bash
# Production .env settings
LOG_LEVEL=WARNING
METRICS_ENABLED=true
HEALTH_CHECK_INTERVAL=30

# Security settings
ENABLE_QUERY_VALIDATION=true
MAX_QUERY_LENGTH=1000
ALLOWED_SQL_OPERATIONS=["SELECT"]

# High-availability settings
CONNECTION_POOL_SIZE=50
CONCURRENT_QUERIES_LIMIT=200
REQUEST_TIMEOUT=60
```

### Monitoring and Alerting

Set up comprehensive monitoring:

```python
# Start performance monitoring
from src.monitoring.performance_optimizer import start_performance_optimization
import asyncio

async def start_monitoring():
    print("Starting performance optimization...")
    await start_performance_optimization()

# Run in background
asyncio.create_task(start_monitoring())
```

### Custom Tool Configuration

Register custom tools for specific use cases:

```python
# Example custom tool registration
from src.tools.decorators import Tool

@Tool(
    name="custom_analytics",
    description="Custom analytics for specific business metrics"
)
def custom_analytics_tool(metric_type: str) -> dict:
    """Custom analytics implementation"""
    # Your custom logic here
    return {"result": "custom_data"}
```

### Security Configuration

Implement security best practices:

```bash
# Security-focused .env settings
ENABLE_AUDIT_LOGGING=true
QUERY_SANITIZATION=true
MAX_QUERY_COMPLEXITY=100
API_RATE_LIMITING=true
SECURE_HEADERS=true
```

## System Architecture Overview

Understanding FACT's architecture helps with troubleshooting:

```
User Query → FACT Driver → Claude Sonnet-4 → Tool Calls → Arcade Gateway → Database
     ↑                                                                        ↓
Cache ←←←←←←←←←←←←←←←←←←← Response ←←←←←←←←←←←←←←←←←←← Structured Data
```

**Key Components**:
- **FACT Driver**: Central orchestrator managing cache and queries
- **Cache Management**: Intelligent caching for sub-48ms responses
- **Tool Registry**: Dynamic tool discovery and execution
- **Arcade Gateway**: Secure tool execution environment
- **Database Layer**: SQLite (demo) or production databases

## Support and Resources

- **Documentation**: Complete guides in [`docs/`](.) directory
- **Examples**: Sample implementations in [`examples/`](../examples/) directory
- **Logs**: Check `logs/fact.log` for detailed error information
- **Validation**: Use `python main.py validate` for health checks
- **Metrics**: Use CLI `metrics` command for performance data

For additional help, see the [Troubleshooting Guide](8_troubleshooting_guide.md) or contact support with your system information and log files.

---

**Setup Complete!** Your FACT system should now be running optimally. Continue to the [User Guide](4_user_guide.md) to start using the system.