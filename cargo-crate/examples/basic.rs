//! Basic example of using FACT (Fast Augmented Context Tools)

use fact_tools::Fact;
use serde_json::json;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Create a new FACT instance with default configuration
    let fact = Fact::new();
    
    // Example 1: Basic analysis
    println!("Example 1: Basic Analysis");
    println!("-------------------------");
    
    let data = json!({
        "values": [10, 25, 30, 45, 50, 65, 70, 85, 90, 100],
        "metadata": {
            "source": "sensor_data",
            "timestamp": "2024-01-01T12:00:00Z"
        }
    });
    
    let result = fact.process("analysis-basic", data).await?;
    println!("Analysis result: {}", serde_json::to_string_pretty(&result)?);
    
    // Example 2: Pattern detection
    println!("\nExample 2: Pattern Detection");
    println!("----------------------------");
    
    let pattern_data = json!({
        "query": "What patterns exist in the sales data?",
        "data": {
            "monthly_sales": [1000, 1200, 1100, 1400, 1600, 1500],
            "categories": ["electronics", "clothing", "food", "electronics", "clothing", "electronics"]
        }
    });
    
    let pattern_result = fact.process("pattern-detection", pattern_data).await?;
    println!("Pattern result: {}", serde_json::to_string_pretty(&pattern_result)?);
    
    // Example 3: Data aggregation
    println!("\nExample 3: Data Aggregation");
    println!("---------------------------");
    
    let numbers = json!({
        "dataset": [5.5, 10.2, 15.7, 20.1, 25.9, 30.3, 35.8, 40.2, 45.6, 50.0],
        "operation": "statistical_summary"
    });
    
    let agg_result = fact.process("data-aggregation", numbers).await?;
    println!("Aggregation result: {}", serde_json::to_string_pretty(&agg_result)?);
    
    // Show cache statistics
    println!("\nCache Statistics");
    println!("----------------");
    let stats = fact.cache_stats();
    println!("Cache entries: {}", stats.entries);
    println!("Cache hit rate: {:.2}%", stats.hit_rate * 100.0);
    println!("Total hits: {}", stats.hits);
    println!("Total misses: {}", stats.misses);
    
    Ok(())
}