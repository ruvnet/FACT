//! FACT CLI - Fast Augmented Context Tools Command Line Interface

use anyhow::Result;
use clap::{Parser, Subcommand};
use fact_tools::{Fact, FactConfig};
use fact_tools::templates::TemplateBuilder;
use serde_json::json;
use std::path::PathBuf;
use std::time::Instant;
use tracing::{error, info};
use tracing_subscriber::EnvFilter;

#[derive(Parser)]
#[command(name = "fact")]
#[command(author, version, about = "FACT (Fast Augmented Context Tools) - High-performance context processing", long_about = None)]
struct Cli {
    /// Enable verbose output
    #[arg(short, long, global = true)]
    verbose: bool,

    /// Configuration file path
    #[arg(short, long, global = true)]
    config: Option<PathBuf>,

    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Process data using a template
    Process {
        /// Template ID to use
        #[arg(short, long)]
        template: String,

        /// Input data (JSON string or file path)
        #[arg(short, long)]
        input: String,

        /// Output file path (optional)
        #[arg(short, long)]
        output: Option<PathBuf>,

        /// Disable caching
        #[arg(long)]
        no_cache: bool,
    },

    /// List available templates
    Templates {
        /// Filter by tag
        #[arg(short, long)]
        tag: Option<String>,

        /// Show detailed information
        #[arg(short, long)]
        detailed: bool,
    },

    /// Show cache statistics
    Cache {
        /// Clear the cache
        #[arg(long)]
        clear: bool,
    },

    /// Benchmark performance
    Benchmark {
        /// Number of iterations
        #[arg(short, long, default_value = "100")]
        iterations: usize,

        /// Template to benchmark
        #[arg(short, long)]
        template: Option<String>,
    },

    /// Initialize FACT configuration
    Init {
        /// Force overwrite existing configuration
        #[arg(short, long)]
        force: bool,
    },
}

#[tokio::main]
async fn main() -> Result<()> {
    let cli = Cli::parse();

    // Initialize logging
    let filter = if cli.verbose {
        EnvFilter::new("debug")
    } else {
        EnvFilter::new("info")
    };
    
    tracing_subscriber::fmt()
        .with_env_filter(filter)
        .init();

    // Load configuration
    let config = if let Some(config_path) = cli.config {
        info!("Loading configuration from: {:?}", config_path);
        let config_str = std::fs::read_to_string(config_path)?;
        serde_json::from_str(&config_str)?
    } else {
        FactConfig::default()
    };

    // Create FACT instance
    let fact = Fact::with_config(config);

    // Execute command
    match cli.command {
        Commands::Process {
            template,
            input,
            output,
            no_cache,
        } => {
            process_command(fact, template, input, output, no_cache).await?;
        }
        Commands::Templates { tag, detailed } => {
            templates_command(tag, detailed)?;
        }
        Commands::Cache { clear } => {
            cache_command(fact, clear)?;
        }
        Commands::Benchmark {
            iterations,
            template,
        } => {
            benchmark_command(fact, iterations, template).await?;
        }
        Commands::Init { force } => {
            init_command(force)?;
        }
    }

    Ok(())
}

async fn process_command(
    fact: Fact,
    template: String,
    input: String,
    output: Option<PathBuf>,
    no_cache: bool,
) -> Result<()> {
    info!("Processing with template: {}", template);

    // Parse input data
    let context = if input.starts_with('{') || input.starts_with('[') {
        // Direct JSON input
        serde_json::from_str(&input)?
    } else if PathBuf::from(&input).exists() {
        // File input
        let content = std::fs::read_to_string(&input)?;
        serde_json::from_str(&content)?
    } else {
        // Treat as string data
        json!({ "data": input })
    };

    // Process with timing
    let start = Instant::now();
    let result = fact.process(&template, context).await?;
    let duration = start.elapsed();

    info!("Processing completed in {:?}", duration);

    // Output result
    let formatted = serde_json::to_string_pretty(&result)?;
    
    if let Some(output_path) = output {
        std::fs::write(output_path, &formatted)?;
        info!("Result written to file");
    } else {
        println!("{}", formatted);
    }

    // Show cache stats if not disabled
    if !no_cache {
        let stats = fact.cache_stats();
        info!(
            "Cache stats - Hit rate: {:.2}%, Entries: {}, Size: {} bytes",
            stats.hit_rate * 100.0,
            stats.entries,
            stats.size_bytes
        );
    }

    Ok(())
}

fn templates_command(tag: Option<String>, detailed: bool) -> Result<()> {
    // Create a temporary registry to list templates
    let registry = fact_tools::templates::TemplateRegistry::new();
    
    let templates = if let Some(tag) = tag {
        registry.search_by_tags(&[tag])
    } else {
        registry.list()
            .into_iter()
            .filter_map(|id| registry.get(&id))
            .collect()
    };

    if detailed {
        for template in templates {
            println!("Template: {} ({})", template.name, template.id);
            println!("  Description: {}", template.description);
            println!("  Version: {}", template.metadata.version);
            println!("  Tags: {}", template.metadata.tags.join(", "));
            println!("  Steps: {}", template.steps.len());
            println!(
                "  Performance: {:.0}ms avg, {}KB memory, complexity {}",
                template.metadata.performance.avg_execution_time_ms,
                template.metadata.performance.memory_usage_bytes / 1024,
                template.metadata.performance.complexity
            );
            println!();
        }
    } else {
        println!("Available templates:");
        for template in templates {
            println!("  {} - {}", template.id, template.name);
        }
    }

    Ok(())
}

fn cache_command(fact: Fact, clear: bool) -> Result<()> {
    if clear {
        fact.clear_cache();
        info!("Cache cleared");
    }

    let stats = fact.cache_stats();
    println!("Cache Statistics:");
    println!("  Entries: {}", stats.entries);
    println!("  Size: {} KB", stats.size_bytes / 1024);
    println!("  Hits: {}", stats.hits);
    println!("  Misses: {}", stats.misses);
    println!("  Hit Rate: {:.2}%", stats.hit_rate * 100.0);
    println!("  Evictions: {}", stats.evictions);

    Ok(())
}

async fn benchmark_command(
    fact: Fact,
    iterations: usize,
    template: Option<String>,
) -> Result<()> {
    let template_id = template.unwrap_or_else(|| "quick-transform".to_string());
    
    info!("Running benchmark with template: {}", template_id);
    info!("Iterations: {}", iterations);

    // Sample data for benchmarking
    let test_data = json!({
        "data": (0..100).collect::<Vec<_>>(),
        "metadata": {
            "source": "benchmark",
            "timestamp": chrono::Utc::now().to_rfc3339(),
        }
    });

    let mut total_duration = std::time::Duration::ZERO;
    let mut min_duration = std::time::Duration::MAX;
    let mut max_duration = std::time::Duration::ZERO;

    // Warm up
    for _ in 0..10 {
        let _ = fact.process(&template_id, test_data.clone()).await?;
    }

    // Clear cache for fair comparison
    fact.clear_cache();

    // Run benchmark
    for i in 0..iterations {
        let start = Instant::now();
        let _ = fact.process(&template_id, test_data.clone()).await?;
        let duration = start.elapsed();

        total_duration += duration;
        min_duration = min_duration.min(duration);
        max_duration = max_duration.max(duration);

        if (i + 1) % 10 == 0 {
            info!("Progress: {}/{}", i + 1, iterations);
        }
    }

    let avg_duration = total_duration / iterations as u32;
    let stats = fact.cache_stats();

    println!("\nBenchmark Results:");
    println!("  Template: {}", template_id);
    println!("  Iterations: {}", iterations);
    println!("  Average: {:?}", avg_duration);
    println!("  Min: {:?}", min_duration);
    println!("  Max: {:?}", max_duration);
    println!("  Cache Hit Rate: {:.2}%", stats.hit_rate * 100.0);
    println!("  Throughput: {:.2} ops/sec", 1000.0 / avg_duration.as_millis() as f64);

    Ok(())
}

fn init_command(force: bool) -> Result<()> {
    let config_path = PathBuf::from("fact.json");
    
    if config_path.exists() && !force {
        error!("Configuration file already exists. Use --force to overwrite.");
        return Ok(());
    }

    let default_config = FactConfig::default();
    let config_str = serde_json::to_string_pretty(&default_config)?;
    
    std::fs::write(&config_path, config_str)?;
    info!("Created configuration file: {:?}", config_path);

    // Create example template file
    let template_path = PathBuf::from("custom_template.json");
    if !template_path.exists() || force {
        let example_template = TemplateBuilder::new("custom-example")
            .name("Custom Example Template")
            .description("An example template for custom processing")
            .add_tag("custom")
            .add_tag("example")
            .build();
        
        let template_str = serde_json::to_string_pretty(&example_template)?;
        std::fs::write(&template_path, template_str)?;
        info!("Created example template: {:?}", template_path);
    }

    println!("\nFACT initialized successfully!");
    println!("Configuration file: fact.json");
    println!("Example template: custom_template.json");
    println!("\nGet started with:");
    println!("  fact process --template analysis-basic --input '{{\"data\": [1,2,3,4,5]}}'");

    Ok(())
}

// Performance note: In production, you might want to add:
// - Async processing pipeline
// - Streaming support for large files
// - Multi-threaded template execution
// - Real-time progress reporting
// - Integration with external services