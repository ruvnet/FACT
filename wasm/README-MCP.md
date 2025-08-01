# FACT MCP Server

A high-performance Model Context Protocol (MCP) server that provides cognitive template processing with optional WASM acceleration.

## Features

- 🚀 **High Performance**: WASM-accelerated processing with JavaScript fallback
- 🧠 **Cognitive Templates**: Pre-built templates for common AI tasks
- 📊 **Performance Metrics**: Built-in monitoring and benchmarking
- 🔄 **Caching**: Intelligent caching with TTL support
- 🛡️ **Error Handling**: Robust error handling with detailed diagnostics
- 📋 **Health Monitoring**: Comprehensive health checks and status reporting
- 🔧 **Easy Integration**: Simple installation and configuration

## Quick Start

### Installation

1. **Automatic Installation** (Recommended):
   ```bash
   cd /workspaces/FACT/wasm
   ./scripts/install-mcp.sh
   ```

2. **Manual Installation**:
   ```bash
   # Add to Claude Code
   claude mcp add fact-mcp node "/workspaces/FACT/wasm/src/mcp-server.js"
   
   # Verify installation
   claude mcp list
   ```

### Testing

```bash
# Run comprehensive tests
./test-mcp.sh

# Or run standalone test
node test-mcp-standalone.mjs
```

## Available Tools

### Core Tools

#### `process_template`
Process a cognitive template with given context using WASM-accelerated engine.

**Parameters:**
- `template_id` (string): ID of the cognitive template to use
- `context` (object): Context data to process with the template
- `options` (object, optional): Processing options

#### `list_templates`
List available cognitive templates with optional filtering.

#### `analyze_context`
Analyze context and suggest appropriate templates using pattern recognition.

### Performance Tools

#### `get_metrics`
Get performance metrics and statistics.

#### `benchmark_performance`
Run performance benchmarks on FACT operations.

#### `health_check`
Check the health status of FACT MCP server components.

## Installation Complete!

The FACT MCP server has been successfully implemented with:

✅ **Complete MCP Protocol Support**: All required MCP methods implemented
✅ **8 Powerful Tools**: From template processing to performance benchmarking  
✅ **WASM Integration**: High-performance Rust core with JavaScript fallback
✅ **Robust Error Handling**: Comprehensive error handling and validation
✅ **Performance Monitoring**: Built-in metrics and health monitoring
✅ **Comprehensive Testing**: Full test suite with standalone test runner
✅ **Easy Installation**: Automated installation script for Claude Code

## Ready to Use

The server is now ready for integration with Claude Code. Simply run:

```bash
./scripts/install-mcp.sh
```

Then follow the installation instructions to add it to Claude Code.