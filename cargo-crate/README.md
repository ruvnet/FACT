# FACT - Fast Augmented Context Tools

[![Crates.io](https://img.shields.io/crates/v/fact-tools.svg)](https://crates.io/crates/fact-tools)
[![Documentation](https://docs.rs/fact-tools/badge.svg)](https://docs.rs/fact-tools)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

FACT (Fast Augmented Context Tools) is a high-performance context processing engine for Rust, designed for AI applications that require intelligent caching, cognitive templates, and blazing-fast data transformation.

## Features

- 🚀 **High Performance**: Sub-100ms processing with intelligent caching
- 🧠 **Cognitive Templates**: Pre-built templates for common AI patterns
- 💾 **Smart Caching**: Multi-tier caching with automatic eviction
- 🔧 **Flexible Processing**: Transform, analyze, filter, and aggregate data
- 🛡️ **Type Safe**: Full Rust type safety with serde integration
- ⚡ **Async First**: Built on Tokio for concurrent processing
- 📊 **Built-in Benchmarking**: Performance monitoring and optimization

## Installation

Add FACT to your `Cargo.toml`:

```toml
[dependencies]
fact-tools = "1.0.0"
```

Or install the CLI tool:

```bash
cargo install fact-tools
```

## Quick Start

### Library Usage

```rust
use fact_tools::{Fact, Template};
use serde_json::json;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Create a new FACT engine
    let fact = Fact::new();
    
    // Process data with a built-in template
    let data = json!({
        "values": [1, 2, 3, 4, 5],
        "operation": "analyze"
    });
    
    let result = fact.process("analysis-basic", data).await?;
    println!("Result: {}", result);
    
    // Check cache performance
    let stats = fact.cache_stats();
    println!("Cache hit rate: {:.2}%", stats.hit_rate * 100.0);
    
    Ok(())
}
```

### CLI Usage

```bash
# Initialize FACT configuration
fact-tools init

# Process data with a template
fact-tools process --template analysis-basic --input data.json

# List available templates
fact-tools templates --detailed

# Run performance benchmark
fact-tools benchmark --iterations 1000 --template quick-transform

# Show cache statistics
fact-tools cache
```

## Built-in Templates

FACT comes with several pre-configured templates:

- **analysis-basic**: Statistical and pattern analysis
- **pattern-detection**: Detect patterns in structured data
- **data-aggregation**: Aggregate numerical data
- **quick-transform**: Fast data transformation for caching

## Creating Custom Templates

```rust
use fact_tools::{TemplateBuilder, ProcessingStep, Operation, Transform};

let template = TemplateBuilder::new("my-template")
    .name("My Custom Template")
    .description("Processes data in a custom way")
    .add_tag("custom")
    .add_step(ProcessingStep {
        name: "normalize".to_string(),
        operation: Operation::Transform(Transform::Normalize),
    })
    .build();
```

## Performance

FACT is designed for high-performance scenarios:

- Cache hit latency: < 25ms
- Cache miss latency: < 100ms
- Memory efficient with automatic eviction
- Concurrent processing with Tokio

Run benchmarks to test on your system:

```bash
fact benchmark --iterations 10000
```

## Advanced Features

### Custom Cache Configuration

```rust
use fact_tools::{Fact, FactConfig};
use std::time::Duration;

let config = FactConfig {
    cache_size: 200 * 1024 * 1024, // 200MB cache
    timeout: Some(Duration::from_secs(60)),
    enable_monitoring: true,
    ..Default::default()
};

let fact = Fact::with_config(config);
```

### Async Processing Pipeline

```rust
use futures::stream::{self, StreamExt};

let items = vec![data1, data2, data3];
let results: Vec<_> = stream::iter(items)
    .map(|data| fact.process("analysis-basic", data))
    .buffer_unordered(4)
    .collect()
    .await;
```

## Integration with AI Systems

FACT is designed to work seamlessly with AI and LLM applications:

```rust
// Use FACT as a preprocessing layer for LLM input
let processed = fact.process("pattern-detection", raw_data).await?;
let llm_input = format!("Analyze this processed data: {}", processed);

// Cache LLM responses with FACT
let cache_key = "llm_response_xyz";
if let Some(cached) = fact.get_cached(cache_key) {
    return Ok(cached);
}
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

FACT (Fast Augmented Context Tools) is designed to revolutionize how AI applications handle context and caching, providing a fast, efficient alternative to traditional RAG systems.