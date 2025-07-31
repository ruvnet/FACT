# FACT CLI - Fast Augmented Context Tools

A powerful command-line interface for the FACT (Fast Augmented Context Tools) system, providing natural language querying of financial data with intelligent caching and WASM acceleration.

## Installation

### Global Installation via npm

```bash
npm install -g fact-cli
```

### Direct execution via npx

```bash
npx fact-cli --help
```

### Local Installation

```bash
git clone https://github.com/ruvnet/FACT.git
cd FACT
npm install
npm run build
```

## Quick Start

1. **Set your API key:**
   ```bash
   export ANTHROPIC_API_KEY="your-anthropic-api-key"
   ```

2. **Initialize the system:**
   ```bash
   fact init
   ```

3. **Ask your first question:**
   ```bash
   fact query "What companies are in the technology sector?"
   ```

4. **Start interactive mode:**
   ```bash
   fact interactive
   ```

## Commands

### System Management

- `fact init` - Initialize the FACT system
- `fact status` - Show system status and health
- `fact doctor` - Diagnose and fix system issues

### Querying Data

- `fact query <question>` - Ask natural language questions
- `fact interactive` - Start interactive query mode

### Performance & Optimization

- `fact benchmark` - Run performance benchmarks
- `fact cache stats` - Show cache statistics
- `fact cache clear` - Clear cache data

### Tools & Configuration

- `fact tools list` - List available tools
- `fact config show` - Show current configuration
- `fact wasm info` - Show WASM module information

## Examples

### Basic Queries

```bash
# Get company information
fact query "Show me all companies in the database"

# Financial analysis
fact query "What is TechCorp's latest quarterly revenue?"

# Sector comparison
fact query "Compare revenue growth across all sectors"
```

### Interactive Mode

```bash
fact interactive

# Choose from:
# - cli: Direct command-line interaction
# - guided: Step-by-step assistance
# - wizard: Complex query builder
```

### Performance Testing

```bash
# Basic benchmark
fact benchmark

# Detailed benchmark with comparison
fact benchmark --iterations 20 --compare
```

### System Diagnostics

```bash
# Check system health
fact status --detailed

# Diagnose issues
fact doctor

# Auto-fix common problems
fact doctor --fix
```

## Configuration

### Environment Variables

- `ANTHROPIC_API_KEY` - Your Anthropic API key (required)
- `ARCADE_API_KEY` - Arcade.dev API key (optional)
- `FACT_VERBOSE` - Enable verbose logging
- `FACT_NO_COLOR` - Disable colored output
- `FACT_DATABASE_PATH` - Custom database path

### Configuration File

The CLI uses `~/.fact/config.json` for persistent settings:

```json
{
  "cacheEnabled": true,
  "defaultFormat": "plain",
  "verbose": false,
  "colorOutput": true,
  "queryTimeout": 30000
}
```

### Update Configuration

```bash
# View current config
fact config show

# Set a value
fact config set defaultFormat json

# Reset to defaults
fact config reset
```

## Features

### 🚀 Performance
- **Sub-50ms** response times with intelligent caching
- **90%+ cost reduction** through automated query optimization
- **WASM acceleration** for compute-intensive operations

### 🧠 Intelligence
- **Natural language processing** - Ask questions in plain English
- **Context-aware caching** - Smart cache management based on data volatility
- **Automatic optimization** - Self-tuning performance characteristics

### 🛡️ Enterprise Ready
- **Security first** - Read-only database access with comprehensive validation
- **Audit trail** - Complete logging of all operations
- **Error handling** - Graceful degradation and recovery

### 🔧 Developer Friendly
- **Multiple output formats** - JSON, table, or plain text
- **Interactive modes** - CLI, guided, or wizard interfaces
- **Extensible architecture** - Plugin system for custom tools

## Architecture

The FACT CLI consists of several key components:

### Core Components

1. **CLI Interface** (`bin/fact.ts`) - Main entry point and command parsing
2. **Python Bridge** (`lib/python-bridge.ts`) - Interface to FACT Python system
3. **WASM Loader** (`lib/wasm-loader.ts`) - WebAssembly module management
4. **Cache Manager** (`lib/cache-manager.ts`) - Intelligent caching system
5. **Interactive Prompts** (`lib/interactive.ts`) - User interaction modes

### Data Flow

```
User Input → CLI Parser → Command Handler → Python Bridge → FACT System
                                        ↓
Cache Manager ← WASM Acceleration ← Response Processing
```

## Troubleshooting

### Common Issues

**CLI not found after installation:**
```bash
# Check if npm global bin is in PATH
npm config get prefix
export PATH="$(npm config get prefix)/bin:$PATH"
```

**Python dependencies missing:**
```bash
pip install -r requirements.txt
```

**Permission errors:**
```bash
# Fix npm permissions
sudo chown -R $(whoami) $(npm config get prefix)/{lib/node_modules,bin,share}
```

### Getting Help

1. **Check system status:**
   ```bash
   fact status --detailed
   ```

2. **Run diagnostics:**
   ```bash
   fact doctor
   ```

3. **Enable verbose logging:**
   ```bash
   FACT_VERBOSE=true fact query "test query"
   ```

4. **View configuration:**
   ```bash
   fact config show
   ```

## Development

### Building from Source

```bash
git clone https://github.com/ruvnet/FACT.git
cd FACT
npm install
npm run build
```

### Running Tests

```bash
npm test
```

### Local Development

```bash
npm run dev
```

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Support

- **Documentation:** [https://github.com/ruvnet/FACT](https://github.com/ruvnet/FACT)
- **Issues:** [https://github.com/ruvnet/FACT/issues](https://github.com/ruvnet/FACT/issues)
- **Discussions:** [https://github.com/ruvnet/FACT/discussions](https://github.com/ruvnet/FACT/discussions)

---

**FACT CLI v1.0.0** - Fast Augmented Context Tools