//! FACT Core CLI Application
//! 
//! Command-line interface for the FACT cognitive template engine

use clap::{Arg, Command};
use fact_core::{init, FactCore};
use std::io::{self, Write};
use tracing::{info, error};

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // Initialize tracing
    tracing_subscriber::fmt()
        .with_env_filter("fact_core=info")
        .init();
    
    let matches = Command::new("FACT Core")
        .version(fact_core::VERSION)
        .about("Cognitive Template Engine and Pattern Recognition System")
        .arg(
            Arg::new("mode")
                .short('m')
                .long("mode")
                .value_name("MODE")
                .help("Operation mode: interactive, batch, benchmark")
                .default_value("interactive")
        )
        .arg(
            Arg::new("input")
                .short('i')
                .long("input")
                .value_name("INPUT")
                .help("Input text or file path")
        )
        .arg(
            Arg::new("verbose")
                .short('v')
                .long("verbose")
                .action(clap::ArgAction::SetTrue)
                .help("Enable verbose output")
        )
        .get_matches();
    
    let mode = matches.get_one::<String>("mode").unwrap();
    let verbose = matches.get_flag("verbose");
    
    if verbose {
        info!("Starting FACT Core v{}", fact_core::VERSION);
    }
    
    let mut core = init().await?;
    
    match mode.as_str() {
        "interactive" => run_interactive_mode(&mut core).await?,
        "batch" => {
            if let Some(input) = matches.get_one::<String>("input") {
                run_batch_mode(&mut core, input).await?;
            } else {
                eprintln!("Error: Batch mode requires --input parameter");
                std::process::exit(1);
            }
        }
        "benchmark" => run_benchmark_mode(&mut core).await?,
        _ => {
            eprintln!("Error: Unknown mode '{}'", mode);
            std::process::exit(1);
        }
    }
    
    core.shutdown().await?;
    Ok(())
}

async fn run_interactive_mode(core: &mut FactCore) -> anyhow::Result<()> {
    println!("🧠 FACT Core Interactive Mode");
    println!("Type 'help' for commands, 'quit' to exit\n");
    
    loop {
        print!("FACT> ");
        io::stdout().flush()?;
        
        let mut input = String::new();
        io::stdin().read_line(&mut input)?;
        let input = input.trim();
        
        if input.is_empty() {
            continue;
        }
        
        match input {
            "quit" | "exit" => break,
            "help" => print_help(),
            "metrics" => {
                match core.metrics().await {
                    Ok(metrics) => println!("📊 System Metrics: {:#?}", metrics),
                    Err(e) => error!("Failed to get metrics: {}", e),
                }
            }
            _ => {
                let start = std::time::Instant::now();
                match core.process_task(input).await {
                    Ok(result) => {
                        let duration = start.elapsed();
                        println!("✅ Result: {}", result.output);
                        println!("⚡ Duration: {:?}", duration);
                        if !result.patterns.is_empty() {
                            println!("🔍 Patterns: {:?}", result.patterns);
                        }
                    }
                    Err(e) => error!("❌ Error: {}", e),
                }
            }
        }
        println!();
    }
    
    Ok(())
}

async fn run_batch_mode(core: &mut FactCore, input: &str) -> anyhow::Result<()> {
    info!("Running batch mode with input: {}", input);
    
    let start = std::time::Instant::now();
    match core.process_task(input).await {
        Ok(result) => {
            let duration = start.elapsed();
            println!("Result: {}", result.output);
            println!("Duration: {:?}", duration);
            println!("Patterns: {:?}", result.patterns);
        }
        Err(e) => {
            error!("Batch processing failed: {}", e);
            std::process::exit(1);
        }
    }
    
    Ok(())
}

async fn run_benchmark_mode(core: &mut FactCore) -> anyhow::Result<()> {
    println!("🚀 Running FACT Core Benchmarks\n");
    
    let test_inputs = vec![
        "analyze financial trends",
        "generate report template",
        "pattern recognition test",
        "complex cognitive processing",
        "multi-step autonomous task",
    ];
    
    let mut total_duration = std::time::Duration::new(0, 0);
    let mut successful_tasks = 0;
    
    for (i, input) in test_inputs.iter().enumerate() {
        print!("Test {}: {} ... ", i + 1, input);
        io::stdout().flush()?;
        
        let start = std::time::Instant::now();
        match core.process_task(input).await {
            Ok(_) => {
                let duration = start.elapsed();
                total_duration += duration;
                successful_tasks += 1;
                println!("✅ {:?}", duration);
            }
            Err(e) => {
                println!("❌ {}", e);
            }
        }
    }
    
    println!("\n📊 Benchmark Results:");
    println!("  Total tasks: {}", test_inputs.len());
    println!("  Successful: {}", successful_tasks);
    println!("  Failed: {}", test_inputs.len() - successful_tasks);
    if successful_tasks > 0 {
        println!("  Average duration: {:?}", total_duration / successful_tasks as u32);
    }
    println!("  Total duration: {:?}", total_duration);
    
    // Display system metrics
    if let Ok(metrics) = core.metrics().await {
        println!("\n🔧 System Metrics:");
        println!("  Cognitive cache: {} entries", metrics.cognitive_cache_size);
        println!("  Pattern models: {}", metrics.pattern_models_loaded);
        println!("  Active tasks: {}", metrics.execution_tasks_active);
        println!("  Memory usage: {:.2} MB", metrics.memory_usage_mb);
    }
    
    Ok(())
}

fn print_help() {
    println!("📚 FACT Core Commands:");
    println!("  help      - Show this help message");
    println!("  metrics   - Display system metrics"); 
    println!("  quit/exit - Exit the application");
    println!("  <text>    - Process text through cognitive engine");
}