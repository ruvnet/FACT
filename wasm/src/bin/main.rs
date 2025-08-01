//! FACT CLI - Command-line interface for Fast Augmented Context Tools

#[cfg(feature = "cli")]
use clap::{Parser, Subcommand};
#[cfg(feature = "cli")]
use anyhow::Result;

#[cfg(feature = "cli")]
#[derive(Parser)]
#[command(
    name = "fact",
    version = "1.0.0",
    about = "Fast Autonomous Cognitive Templates CLI",
    long_about = None
)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[cfg(feature = "cli")]
#[derive(Subcommand)]
enum Commands {
    /// Process a query using FACT
    Query {
        /// The query to process
        #[arg(value_name = "QUERY")]
        query: String,
        
        /// Use caching
        #[arg(short, long, default_value_t = true)]
        cache: bool,
        
        /// Output format
        #[arg(short, long, value_enum, default_value = "json")]
        format: OutputFormat,
    },
    
    /// Manage cache
    Cache {
        #[command(subcommand)]
        action: CacheAction,
    },
    
    /// Show performance statistics
    Stats {
        /// Show detailed statistics
        #[arg(short, long)]
        detailed: bool,
    },
    
    /// Run benchmarks
    Benchmark {
        /// Number of iterations
        #[arg(short, long, default_value_t = 1000)]
        iterations: usize,
    },
}

#[cfg(feature = "cli")]
#[derive(Subcommand)]
enum CacheAction {
    /// Clear the cache
    Clear,
    
    /// Show cache statistics
    Stats,
    
    /// Warm up cache with sample data
    Warmup,
}

#[cfg(feature = "cli")]
#[derive(clap::ValueEnum, Clone)]
enum OutputFormat {
    Json,
    Text,
    Yaml,
}

#[cfg(feature = "cli")]
#[tokio::main]
async fn main() -> Result<()> {
    let cli = Cli::parse();
    
    match cli.command {
        Commands::Query { query, cache, format } => {
            process_query(&query, cache, format).await?;
        }
        Commands::Cache { action } => {
            handle_cache_action(action).await?;
        }
        Commands::Stats { detailed } => {
            show_stats(detailed).await?;
        }
        Commands::Benchmark { iterations } => {
            run_benchmark(iterations).await?;
        }
    }
    
    Ok(())
}

#[cfg(feature = "cli")]
async fn process_query(query: &str, use_cache: bool, format: OutputFormat) -> Result<()> {
    use fact::{FastCache, QueryProcessor};
    
    let mut cache = FastCache::new();
    let processor = QueryProcessor::new();
    
    let result = if use_cache {
        // Check cache first
        if let Some(cached) = cache.get(&query.to_string()) {
            cached
        } else {
            let result = processor.process(&query.to_string());
            cache.put(query.to_string(), result.clone());
            result
        }
    } else {
        processor.process(&query.to_string())
    };
    
    match format {
        OutputFormat::Json => {
            println!("{}", serde_json::to_string_pretty(&result)?);
        }
        OutputFormat::Text => {
            println!("Query: {}", query);
            println!("Result: {}", result);
        }
        OutputFormat::Yaml => {
            println!("query: {}", query);
            println!("result: {}", result);
        }
    }
    
    Ok(())
}

#[cfg(feature = "cli")]
async fn handle_cache_action(action: CacheAction) -> Result<()> {
    use fact::FastCache;
    
    let mut cache = FastCache::new();
    
    match action {
        CacheAction::Clear => {
            cache.clear();
            println!("Cache cleared successfully");
        }
        CacheAction::Stats => {
            let stats = cache.get_stats();
            println!("{}", serde_json::to_string_pretty(&stats)?);
        }
        CacheAction::Warmup => {
            // Add sample data to cache
            let samples = vec![
                ("sample query 1", "sample result 1"),
                ("sample query 2", "sample result 2"),
                ("sample query 3", "sample result 3"),
            ];
            
            for (query, result) in samples {
                cache.put(query.to_string(), result.to_string());
            }
            
            println!("Cache warmed up with {} samples", 3);
        }
    }
    
    Ok(())
}

#[cfg(feature = "cli")]
async fn show_stats(detailed: bool) -> Result<()> {
    use fact::FastCache;
    
    let cache = FastCache::new();
    let stats = cache.get_stats();
    
    if detailed {
        println!("{}", serde_json::to_string_pretty(&stats)?);
    } else {
        println!("Cache Statistics:");
        println!("  Size: {} bytes", stats["size"]);
        println!("  Entries: {}", stats["entries"]);
        println!("  Capacity: {} bytes", stats["capacity"]);
    }
    
    Ok(())
}

#[cfg(feature = "cli")]
async fn run_benchmark(iterations: usize) -> Result<()> {
    use fact::{FastCache, QueryProcessor};
    use std::time::Instant;
    
    println!("Running FACT benchmark with {} iterations...", iterations);
    
    let mut cache = FastCache::new();
    let processor = QueryProcessor::new();
    
    // Benchmark cache operations
    let start = Instant::now();
    for i in 0..iterations {
        let key = format!("key_{}", i);
        let value = format!("value_{}", i);
        cache.put(key.clone(), value);
        let _ = cache.get(&key);
    }
    let cache_duration = start.elapsed();
    
    // Benchmark query processing
    let start = Instant::now();
    for i in 0..iterations {
        let query = format!("query_{}", i);
        let _ = processor.process(&query);
    }
    let process_duration = start.elapsed();
    
    println!("\nBenchmark Results:");
    println!("  Cache operations: {} ops/sec", 
        (iterations as f64 * 2.0) / cache_duration.as_secs_f64());
    println!("  Query processing: {} ops/sec", 
        iterations as f64 / process_duration.as_secs_f64());
    println!("  Total time: {:.2}s", 
        (cache_duration + process_duration).as_secs_f64());
    
    Ok(())
}

#[cfg(not(feature = "cli"))]
fn main() {
    eprintln!("FACT CLI requires the 'cli' feature to be enabled");
    eprintln!("Try: cargo install fact --features cli");
    std::process::exit(1);
}