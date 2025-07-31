# FACT (Fast Augmented Context Tools)

A high-performance cognitive template processing engine written in Rust with WebAssembly support.

## Installation

### As a Rust Crate

```bash
cargo add fact
```

### As a CLI Tool

```bash
cargo install fact --features cli
```

### For WebAssembly

```bash
wasm-pack build --target web
```

## Usage

### Rust Library

```rust
use fact::{FastCache, QueryProcessor};

fn main() {
    // Create a cache instance
    let mut cache = FastCache::new();
    
    // Create a query processor
    let processor = QueryProcessor::new();
    
    // Process a query
    let result = processor.process("your query here");
    
    // Cache the result
    cache.put("your query here".to_string(), result.clone());
    
    // Retrieve from cache
    if let Some(cached) = cache.get(&"your query here".to_string()) {
        println!("Cached result: {}", cached);
    }
}
```

### CLI Usage

```bash
# Process a query
fact query "What is the weather today?"

# Show cache statistics
fact cache stats

# Clear cache
fact cache clear

# Run benchmarks
fact benchmark --iterations 10000

# Show performance statistics
fact stats --detailed
```

### WebAssembly Usage

```javascript
import init, { FastCache, QueryProcessor } from './pkg/fact.js';

async function main() {
    // Initialize WASM module
    await init();
    
    // Create instances
    const cache = new FastCache();
    const processor = new QueryProcessor();
    
    // Process query
    const result = processor.process("your query");
    
    // Use cache
    cache.put("key", "value");
    const cached = cache.get("key");
}

main();
```

## Features

- **High Performance**: Optimized Rust implementation with SIMD support
- **WebAssembly Support**: Run in browsers and Node.js
- **Intelligent Caching**: LRU cache with automatic eviction
- **CLI Tool**: Command-line interface for easy usage
- **Cognitive Templates**: Pre-built templates for common patterns
- **Cross-Platform**: Works on Linux, macOS, and Windows

## Performance

FACT achieves exceptional performance through:

- **Memory-efficient data structures** using `ahash` and `smallvec`
- **SIMD optimizations** for vectorized operations
- **Zero-copy operations** where possible
- **Compile-time optimizations** with LTO and aggressive inlining

Benchmark results:
- Cache operations: 1.9M inserts/sec, 4.0M retrievals/sec
- Query processing: Sub-millisecond latency
- WASM bundle size: <200KB (optimized)

## Building from Source

```bash
# Clone the repository
git clone https://github.com/ruvnet/FACT
cd FACT/wasm

# Build library
cargo build --release

# Build CLI
cargo build --release --features cli

# Build WASM
wasm-pack build --target web
```

## Testing

```bash
# Run unit tests
cargo test

# Run benchmarks
cargo bench

# Run WASM tests
wasm-pack test --headless --firefox
```

## Contributing

Contributions are welcome! Please read our [Contributing Guide](../CONTRIBUTING.md) for details.

## License

MIT License - see [LICENSE](../LICENSE) for details.