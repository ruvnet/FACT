# FACT MCP Server

Model Context Protocol server for Fast Autonomous Cognitive Templates (FACT).

## Installation

```bash
npm install -g @fact/mcp-server
```

Or use directly with npx:

```bash
npx @fact/mcp-server
```

## Usage with Claude

Add the FACT MCP server to Claude:

```bash
claude mcp add fact-mcp npx @fact/mcp-server
```

## Available Tools

### `process_template`
Process a cognitive template with given context.

```typescript
{
  template_id: string;
  context: object;
  options?: {
    cache?: boolean;
    timeout?: number;
    priority?: 'low' | 'medium' | 'high';
  };
}
```

### `list_templates`
List available cognitive templates.

```typescript
{
  category?: string;
  tags?: string[];
}
```

### `analyze_context`
Analyze context and suggest appropriate templates.

```typescript
{
  context: object;
  suggest_templates?: boolean;
}
```

### `optimize_performance`
Optimize FACT performance.

```typescript
{
  operation: 'cache' | 'memory' | 'processing';
  aggressive?: boolean;
}
```

### `create_template`
Create a new cognitive template.

```typescript
{
  name: string;
  description: string;
  pattern: object;
  category?: string;
  tags?: string[];
}
```

### `get_metrics`
Get performance metrics and statistics.

## Resources

The server provides access to these resources:

- `fact://templates` - Available cognitive templates
- `fact://metrics` - Performance metrics
- `fact://cache` - Cache statistics

## Cognitive Templates

FACT includes several built-in cognitive templates:

1. **Basic Analysis** - Simple data analysis and summarization
2. **Advanced Inquiry** - Deep inquiry with multi-step reasoning
3. **Optimization Solver** - Constraint-based optimization
4. **Creative Synthesis** - Generate creative solutions
5. **Decision Support** - Multi-criteria decision analysis

## Performance

FACT leverages WebAssembly for high-performance processing:

- Sub-50ms response times for cached queries
- Intelligent caching with LRU eviction
- Performance monitoring and optimization
- SIMD optimizations when available

## Development

```bash
# Install dependencies
npm install

# Build TypeScript
npm run build

# Run in development mode
npm run dev

# Run tests
npm test
```

## Environment Variables

- `LOG_LEVEL` - Logging level (debug, info, warn, error)
- `NODE_ENV` - Environment (development, production)
- `FACT_CACHE_SIZE` - Maximum cache size in MB (default: 100)

## License

MIT