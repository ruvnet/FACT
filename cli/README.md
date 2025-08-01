# FACT CLI

**Framework for Autonomous Cognitive Templates** - High-performance CLI with WASM integration

## Features

- 🚀 **High Performance**: WASM-powered cognitive processing engine
- 🧠 **Template System**: Create and manage cognitive templates
- 🔗 **MCP Integration**: Model Context Protocol server for AI integration
- ⚡ **Benchmarking**: Built-in performance testing and profiling
- 🛠️ **Configuration**: Flexible configuration management
- 📊 **Monitoring**: Comprehensive performance metrics and logging

## Installation

### Global Installation
```bash
npm install -g fact-cli
```

### Local Installation
```bash
npm install fact-cli
```

### From Source
```bash
git clone https://github.com/your-org/fact.git
cd fact/cli
npm install
npm run build
npm link
```

## Quick Start

1. **Initialize configuration:**
   ```bash
   fact config init
   ```

2. **List available templates:**
   ```bash
   fact template list
   ```

3. **Process a template:**
   ```bash
   fact process template-id '{"data": "your context"}'
   ```

4. **Start MCP server:**
   ```bash
   fact mcp start
   ```

## Commands

### Core Commands

#### Process Templates
```bash
# Process with template ID
fact process template-id '{"data": "context"}'

# Process with context from file
fact process template-id --file context.json

# Analyze context without processing
fact process analyze '{"data": "context"}' --suggest
```

#### Template Management
```bash
# List templates
fact template list
fact template list --category analysis
fact template list --tag cognitive,automation

# Show template details
fact template show template-id

# Create new template
fact template create --interactive
fact template create --name "My Template" --description "Template description"

# Export template
fact template export template-id --output template.json

# Delete template
fact template delete template-id
```

#### MCP Server
```bash
# Start server
fact mcp start
fact mcp start --port 3001 --host 0.0.0.0

# Check status
fact mcp status

# List available tools
fact mcp tools

# Test connection
fact mcp test --url ws://localhost:3000/mcp
```

#### Benchmarking
```bash
# Run all benchmarks
fact benchmark run

# Run specific benchmark
fact benchmark run --test wasm --iterations 1000

# Profile memory usage
fact benchmark profile --duration 60

# Compare benchmark results
fact benchmark compare results1.json results2.json
```

#### Configuration
```bash
# Show configuration
fact config show
fact config show --key wasm

# Set configuration
fact config set wasm.memoryLimit 512 --save

# Initialize configuration
fact config init

# Validate configuration
fact config validate

# Reset to defaults
fact config reset --save
```

### Global Options

- `-v, --verbose`: Enable verbose logging
- `-c, --config <path>`: Path to configuration file
- `--mcp`: Start in MCP server mode
- `--help`: Show help information
- `--version`: Show version information

## Configuration

FACT CLI uses YAML or JSON configuration files. Default locations:

- `./fact.config.yaml`
- `./fact.config.json`
- `~/.fact/config.yaml`
- `~/.fact/config.json`

### Configuration Example

```yaml
wasm:
  optimizationLevel: "balanced"  # size, speed, balanced
  memoryLimit: 256  # MB

performance:
  enableCaching: true
  cacheSize: 100  # MB
  maxConcurrentTasks: 4
  timeout: 30  # seconds

mcp:
  port: 3000
  host: "localhost"
  enableAuth: false
  maxConnections: 10

logging:
  level: "info"  # error, warn, info, debug
  enableFileLogging: true

security:
  enableSandbox: true
  allowUnsafeOperations: false

templates:
  defaultCategory: "general"
  autoSave: true
  searchPaths:
    - "./templates"
    - "~/.fact/templates"
```

## MCP Integration

FACT CLI includes a built-in MCP (Model Context Protocol) server that provides cognitive processing capabilities to AI systems.

### Available Tools

- `process_template`: Process cognitive templates with context
- `list_templates`: List available templates
- `analyze_context`: Analyze context and suggest templates
- `optimize_performance`: Optimize system performance
- `create_template`: Create new templates
- `get_metrics`: Get performance metrics

### Usage with Claude

1. Start the MCP server:
   ```bash
   fact mcp start
   ```

2. Configure Claude to use the MCP server:
   ```json
   {
     "mcpServers": {
       "fact": {
         "command": "fact",
         "args": ["mcp", "start"]
       }
     }
   }
   ```

## Development

### Build from Source

```bash
# Clone repository
git clone https://github.com/your-org/fact.git
cd fact/cli

# Install dependencies
npm install

# Build TypeScript
npm run build

# Run tests
npm test

# Watch for changes
npm run dev
```

### WASM Integration

The CLI integrates with a Rust-based WASM module for high-performance processing:

```bash
# Build WASM module (from project root)
cd ../wasm
npm run build:wasm

# Copy WASM files to CLI
cd ../cli
npm run copy-wasm
```

### Testing

```bash
# Run all tests
npm test

# Run with coverage
npm run test:coverage

# Run specific test
npm test -- --testNamePattern="ConfigManager"

# Watch mode
npm run test:watch
```

### Linting and Formatting

```bash
# Lint code
npm run lint

# Fix linting issues
npm run lint:fix

# Format code
npm run format

# Check formatting
npm run format:check
```

## Performance

### Benchmarks

FACT CLI includes comprehensive benchmarking tools:

```bash
# Basic benchmark
fact benchmark run --iterations 1000

# Memory profiling
fact benchmark profile --duration 60

# Save results
fact benchmark run --output results.json

# Compare results
fact benchmark compare old-results.json new-results.json
```

### Optimization Tips

1. **WASM Configuration**: Use `balanced` optimization for most cases
2. **Memory Limits**: Set appropriate WASM memory limits based on usage
3. **Caching**: Enable caching for repeated operations
4. **Concurrency**: Adjust `maxConcurrentTasks` based on system resources

## Troubleshooting

### Common Issues

1. **WASM Module Not Found**
   ```bash
   # Build and copy WASM files
   cd ../wasm && npm run build:wasm
   cd ../cli && npm run copy-wasm
   ```

2. **Permission Errors**
   ```bash
   # Fix permissions
   chmod +x bin/fact.js bin/fact-mcp.js
   ```

3. **Port Already in Use**
   ```bash
   # Use different port
   fact mcp start --port 3001
   ```

4. **Memory Issues**
   ```bash
   # Increase WASM memory limit
   fact config set wasm.memoryLimit 512 --save
   ```

### Debug Mode

Enable debug logging:

```bash
export DEBUG=fact:*
fact --verbose [command]
```

### Log Files

Logs are written to:
- `logs/error.log` - Error messages
- `logs/combined.log` - All log messages

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make changes and add tests
4. Run tests: `npm test`
5. Commit changes: `git commit -am 'Add feature'`
6. Push to branch: `git push origin feature-name`
7. Submit a pull request

## License

MIT License - see [LICENSE](../LICENSE) file for details.

## Support

- Documentation: https://github.com/your-org/fact
- Issues: https://github.com/your-org/fact/issues
- Discussions: https://github.com/your-org/fact/discussions

---

**FACT CLI** - Bringing autonomous cognitive processing to your command line. 🚀