# FACT MCP Server

A high-performance Model Context Protocol (MCP) server implementation with WebAssembly integration for cognitive template processing.

## Overview

The FACT MCP Server provides advanced cognitive template processing capabilities through the Model Context Protocol, featuring:

- **WASM Integration**: High-performance processing using WebAssembly
- **Cognitive Templates**: Pre-built templates for common AI tasks
- **Real-time Analytics**: Performance metrics and monitoring
- **Resource Management**: Template and system resource access
- **Fallback Support**: JavaScript fallback when WASM is unavailable

## Quick Start

### Installation

```bash
# Install dependencies
npm install

# Build WASM module and MCP server
npm run build:all

# Test the server
npm run test:mcp
```

### Claude Code Integration

Add the MCP server to Claude Code:

```bash
# Using npm script
npm run install:claude

# Or manually
claude mcp add fact-mcp node src/mcp-server.js
```

### Verify Installation

```bash
# List MCP servers in Claude Code
claude mcp list

# Test the server
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | node src/mcp-server.js
```

## MCP Tools

### Core Tools

#### `process_template`
Process a cognitive template with given context.

```javascript
{
  "template_id": "data-analysis",
  "context": {
    "data": [1, 2, 3, 4, 5],
    "query": "analyze this dataset"
  },
  "options": {
    "cache": true,
    "priority": "high"
  }
}
```

#### `list_templates`
List available cognitive templates with optional filtering.

```javascript
{
  "category": "analysis",  // Optional: filter by category
  "tags": ["data", "ml"]   // Optional: filter by tags
}
```

#### `analyze_context`
Analyze context and suggest appropriate templates using pattern recognition.

```javascript
{
  "context": {
    "query": "How do I optimize my database queries?",
    "type": "performance"
  },
  "suggest_templates": true
}
```

#### `optimize_performance`
Optimize FACT performance (cache, memory, processing).

```javascript
{
  "operation": "cache",  // cache, memory, or processing
  "aggressive": false    // Use aggressive optimization
}
```

#### `get_metrics`
Get performance metrics and system statistics.

```javascript
{}  // No parameters required
```

#### `create_template`
Create a new cognitive template.

```javascript
{
  "name": "Custom Analysis",
  "description": "Custom data analysis template",
  "pattern": {
    "pattern_type": "sequential",
    "steps": [
      {"step_type": "analyze", "config": {"depth": "deep"}},
      {"step_type": "synthesize", "config": {"format": "insights"}}
    ]
  },
  "category": "analysis",
  "tags": ["custom", "analysis"]
}
```

## Cognitive Templates

### Built-in Templates

1. **data-analysis**: Analyze data patterns and extract insights
2. **problem-solving**: Systematic approach to problem resolution
3. **code-generation**: Generate code based on specifications
4. **optimization**: Optimize system performance and resource usage
5. **learning**: Learn from patterns and adapt behavior

### Template Structure

```javascript
{
  "id": "template-id",
  "name": "Template Name",
  "description": "Template description",
  "category": "analysis",
  "tags": ["tag1", "tag2"],
  "pattern": {
    "pattern_type": "sequential",  // sequential, parallel, adaptive, etc.
    "steps": [
      {
        "step_type": "transform",
        "config": {"mode": "expand"}
      },
      {
        "step_type": "analyze", 
        "config": {"depth": "deep"}
      },
      {
        "step_type": "synthesize",
        "config": {"format": "insights"}
      }
    ]
  },
  "cache_ttl": 300
}
```

## Resources

The MCP server provides several resources:

### Template Resources
- `template://data-analysis` - Data analysis template definition
- `template://problem-solving` - Problem solving template definition
- `template://code-generation` - Code generation template definition
- `template://optimization` - Performance optimization template definition
- `template://learning` - Adaptive learning template definition

### System Resources
- `metrics://performance` - Real-time performance metrics
- `system://status` - Current system status and health information

## Performance Features

### WASM Acceleration
- High-performance template processing
- Optimized memory management
- SIMD acceleration support (when available)
- Automatic fallback to JavaScript

### Caching
- Intelligent result caching
- Configurable TTL per template
- Cache hit rate monitoring
- Memory-efficient storage

### Monitoring
- Real-time performance metrics
- Request/response tracking
- Error rate monitoring
- Resource usage statistics

## Error Handling

The server provides comprehensive error handling with:

- JSON-RPC 2.0 compliant error responses
- Detailed error messages and codes
- Graceful WASM fallback
- Request timeout protection
- Input validation

### Common Error Codes

- `-32600`: Invalid Request
- `-32601`: Method not found
- `-32602`: Invalid params
- `-32603`: Internal error
- `-32700`: Parse error

## Development

### Testing

```bash
# Run comprehensive tests
node tests/mcp_server_tests.js

# Test specific functionality
npm run test:mcp

# Debug mode
npm run dev:mcp
```

### Building

```bash
# Build WASM module only
npm run build:wasm

# Build MCP server configuration
npm run build:mcp

# Build everything
npm run build:all
```

### Configuration

The server can be configured through environment variables:

- `FACT_DEBUG=1`: Enable debug logging
- `FACT_WASM_DISABLED=1`: Disable WASM acceleration
- `FACT_CACHE_SIZE=1000`: Set cache size limit

## Integration Examples

### Basic Template Processing

```javascript
// Send via Claude Code MCP
const result = await mcp.call('process_template', {
  template_id: 'data-analysis',
  context: {
    data: myDataset,
    query: 'find patterns and anomalies'
  }
});

console.log(result.insights);
```

### Context Analysis

```javascript
// Analyze user query and get template suggestions
const analysis = await mcp.call('analyze_context', {
  context: {
    query: 'How can I improve API performance?',
    domain: 'backend'
  },
  suggest_templates: true
});

// Use suggested template
const optimization = await mcp.call('process_template', {
  template_id: analysis.suggested_templates[0].template_id,
  context: analysis.context
});
```

### Performance Monitoring

```javascript
// Get current performance metrics
const metrics = await mcp.call('get_metrics');
console.log(`Cache hit rate: ${metrics.cacheHitRate}%`);
console.log(`Average response time: ${metrics.averageResponseTime}ms`);

// Optimize if needed
if (metrics.cacheHitRate < 0.8) {
  await mcp.call('optimize_performance', {
    operation: 'cache',
    aggressive: true
  });
}
```

## Troubleshooting

### WASM Issues
- Ensure Node.js version >= 16.0.0
- Check if `pkg/` directory contains WASM files
- Run `npm run build:wasm` to rebuild

### Server Startup Issues
- Verify executable permissions: `chmod +x src/mcp-server.js`
- Check Node.js path in shebang
- Review error messages in stderr

### Performance Issues
- Monitor metrics with `get_metrics` tool
- Use `optimize_performance` tool
- Consider increasing cache size
- Enable aggressive optimization mode

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Claude Code   │    │   MCP Server     │    │   WASM Core     │
│                 │◄──►│                  │◄──►│                 │
│  JSON-RPC 2.0   │    │  stdio transport │    │  Template       │
│  Tool Calls     │    │  Resource Mgmt   │    │  Processing     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │  JavaScript      │
                       │  Fallback        │
                       │  Implementation  │
                       └──────────────────┘
```

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## Support

For issues and questions:
- Check the troubleshooting section
- Run diagnostic tests
- Review error messages
- Open an issue on GitHub