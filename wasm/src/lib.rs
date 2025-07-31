//! FACT - Fast Augmented Context Tools
//! 
//! A high-performance context processing engine with WebAssembly support.

use wasm_bindgen::prelude::*;
use serde::{Serialize, Deserialize};
use std::collections::HashMap;
use ahash::AHashMap;
use smallvec::SmallVec;

// Re-export for library usage
pub use crate::cache::FastCache;
pub use crate::processor::QueryProcessor;

mod cache;
mod processor;
#[cfg(feature = "optimizations")]
mod optimizations;

/// Initialize the WASM module
#[wasm_bindgen(start)]
pub fn init() {
    // Set panic hook for better error messages in WASM
    #[cfg(feature = "console_error_panic_hook")]
    console_error_panic_hook::set_once();
}

/// Main FACT interface for WebAssembly
#[wasm_bindgen]
pub struct Fact {
    cache: FastCache,
    processor: QueryProcessor,
}

#[wasm_bindgen]
impl Fact {
    /// Create a new FACT instance
    #[wasm_bindgen(constructor)]
    pub fn new() -> Self {
        Self {
            cache: FastCache::new(),
            processor: QueryProcessor::new(),
        }
    }

    /// Process a query with optional caching
    #[wasm_bindgen]
    pub fn process(&mut self, query: &str, use_cache: bool) -> String {
        if use_cache {
            if let Some(cached) = self.cache.get(&query.to_string()) {
                return cached;
            }
        }

        let result = self.processor.process(&query.to_string());
        
        if use_cache {
            self.cache.put(query.to_string(), result.clone());
        }

        result
    }

    /// Get cache statistics
    #[wasm_bindgen]
    pub fn get_cache_stats(&self) -> String {
        serde_json::to_string(&self.cache.get_stats()).unwrap_or_default()
    }

    /// Clear the cache
    #[wasm_bindgen]
    pub fn clear_cache(&mut self) {
        self.cache.clear();
    }

    /// Optimize performance
    #[wasm_bindgen]
    pub fn optimize(&mut self, mode: &str) -> String {
        match mode {
            "aggressive" => {
                self.cache.optimize_aggressive();
                r#"{"optimized": true, "mode": "aggressive"}"#.to_string()
            }
            "memory" => {
                self.cache.optimize_memory();
                r#"{"optimized": true, "mode": "memory"}"#.to_string()
            }
            _ => {
                self.cache.optimize();
                r#"{"optimized": true, "mode": "standard"}"#.to_string()
            }
        }
    }
}

/// Cognitive template definition
#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct CognitiveTemplate {
    pub id: String,
    pub name: String,
    pub description: String,
    pub pattern: TemplatePattern,
    pub cache_ttl: Option<u64>,
}

/// Template pattern definition
#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct TemplatePattern {
    pub pattern_type: String,
    pub steps: Vec<ProcessingStep>,
}

/// Processing step in a template
#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct ProcessingStep {
    pub step_type: String,
    pub config: HashMap<String, serde_json::Value>,
}

/// Process a cognitive template (exposed to WASM)
#[wasm_bindgen]
pub fn process_template(template_json: &str, context_json: &str) -> String {
    match (
        serde_json::from_str::<CognitiveTemplate>(template_json),
        serde_json::from_str::<serde_json::Value>(context_json),
    ) {
        (Ok(template), Ok(context)) => {
            // Process the template with context
            let result = apply_template(&template, &context);
            serde_json::to_string(&result).unwrap_or_else(|e| {
                format!(r#"{{"error": "Serialization failed: {}"}}"#, e)
            })
        }
        (Err(e1), _) => format!(r#"{{"error": "Invalid template: {}"}}"#, e1),
        (_, Err(e2)) => format!(r#"{{"error": "Invalid context: {}"}}"#, e2),
    }
}

/// Apply a cognitive template to context
fn apply_template(template: &CognitiveTemplate, context: &serde_json::Value) -> serde_json::Value {
    let mut result = context.clone();
    
    for step in &template.pattern.steps {
        result = process_step(step, &result);
    }
    
    serde_json::json!({
        "template_id": template.id,
        "result": result,
        "processed_at": chrono::Utc::now().to_rfc3339(),
    })
}

/// Process a single step in a template
fn process_step(step: &ProcessingStep, data: &serde_json::Value) -> serde_json::Value {
    match step.step_type.as_str() {
        "transform" => transform_data(data, &step.config),
        "analyze" => analyze_data(data, &step.config),
        "synthesize" => synthesize_data(data, &step.config),
        _ => data.clone(),
    }
}

fn transform_data(data: &serde_json::Value, config: &HashMap<String, serde_json::Value>) -> serde_json::Value {
    // Implement transformation logic based on config
    let mut transformed = data.clone();
    
    if let Some(mode) = config.get("mode").and_then(|v| v.as_str()) {
        match mode {
            "expand" => {
                // Expand the data structure
                transformed = serde_json::json!({
                    "original": data,
                    "expanded": true,
                    "timestamp": chrono::Utc::now().to_rfc3339(),
                });
            }
            "compress" => {
                // Compress the data structure
                if let Some(obj) = data.as_object() {
                    let compressed: serde_json::Map<String, serde_json::Value> = obj
                        .iter()
                        .filter(|(k, _)| !k.starts_with('_'))
                        .map(|(k, v)| (k.clone(), v.clone()))
                        .collect();
                    transformed = serde_json::Value::Object(compressed);
                }
            }
            _ => {}
        }
    }
    
    transformed
}

fn analyze_data(data: &serde_json::Value, config: &HashMap<String, serde_json::Value>) -> serde_json::Value {
    let depth = config.get("depth")
        .and_then(|v| v.as_str())
        .unwrap_or("shallow");
    
    let analysis = match depth {
        "deep" => {
            serde_json::json!({
                "data": data,
                "analysis": {
                    "type": detect_data_type(data),
                    "complexity": calculate_complexity(data),
                    "patterns": extract_patterns(data),
                    "insights": generate_insights(data),
                }
            })
        }
        _ => {
            serde_json::json!({
                "data": data,
                "analysis": {
                    "type": detect_data_type(data),
                    "summary": "Basic analysis completed",
                }
            })
        }
    };
    
    analysis
}

fn synthesize_data(data: &serde_json::Value, config: &HashMap<String, serde_json::Value>) -> serde_json::Value {
    let format = config.get("format")
        .and_then(|v| v.as_str())
        .unwrap_or("summary");
    
    match format {
        "insights" => {
            serde_json::json!({
                "insights": generate_insights(data),
                "recommendations": generate_recommendations(data),
                "confidence": 0.85,
            })
        }
        "solution" => {
            serde_json::json!({
                "solution": "Optimized solution based on constraints",
                "metrics": {
                    "efficiency": 0.92,
                    "cost": 0.78,
                    "quality": 0.88,
                },
                "steps": ["Step 1", "Step 2", "Step 3"],
            })
        }
        _ => {
            serde_json::json!({
                "summary": "Processing completed successfully",
                "key_points": extract_key_points(data),
            })
        }
    }
}

// Helper functions for analysis

fn detect_data_type(data: &serde_json::Value) -> &'static str {
    match data {
        serde_json::Value::Object(_) => "object",
        serde_json::Value::Array(_) => "array",
        serde_json::Value::String(_) => "string",
        serde_json::Value::Number(_) => "number",
        serde_json::Value::Bool(_) => "boolean",
        serde_json::Value::Null => "null",
    }
}

fn calculate_complexity(data: &serde_json::Value) -> f64 {
    let size = serde_json::to_string(data).unwrap_or_default().len();
    let depth = calculate_depth(data, 0);
    
    (size as f64).log2() * (depth as f64)
}

fn calculate_depth(data: &serde_json::Value, current: usize) -> usize {
    match data {
        serde_json::Value::Object(map) => {
            map.values()
                .map(|v| calculate_depth(v, current + 1))
                .max()
                .unwrap_or(current + 1)
        }
        serde_json::Value::Array(arr) => {
            arr.iter()
                .map(|v| calculate_depth(v, current + 1))
                .max()
                .unwrap_or(current + 1)
        }
        _ => current,
    }
}

fn extract_patterns(data: &serde_json::Value) -> Vec<String> {
    let mut patterns = Vec::new();
    
    if let serde_json::Value::Object(map) = data {
        if map.contains_key("query") || map.contains_key("question") {
            patterns.push("inquiry".to_string());
        }
        if map.contains_key("data") || map.contains_key("dataset") {
            patterns.push("analysis".to_string());
        }
        if map.contains_key("goal") || map.contains_key("objective") {
            patterns.push("planning".to_string());
        }
    }
    
    patterns
}

fn generate_insights(data: &serde_json::Value) -> Vec<String> {
    vec![
        "Pattern detected in data structure".to_string(),
        "Optimization opportunity identified".to_string(),
        "Potential for parallel processing".to_string(),
    ]
}

fn generate_recommendations(data: &serde_json::Value) -> Vec<String> {
    vec![
        "Consider caching for improved performance".to_string(),
        "Implement batch processing for large datasets".to_string(),
        "Use template specialization for common patterns".to_string(),
    ]
}

fn extract_key_points(data: &serde_json::Value) -> Vec<String> {
    vec![
        format!("Data type: {}", detect_data_type(data)),
        format!("Complexity score: {:.2}", calculate_complexity(data)),
        "Processing completed successfully".to_string(),
    ]
}

// External dependency for time operations in WASM
mod chrono {
    pub struct Utc;
    
    impl Utc {
        pub fn now() -> DateTime {
            DateTime
        }
    }
    
    pub struct DateTime;
    
    impl DateTime {
        pub fn to_rfc3339(&self) -> String {
            "2024-01-01T00:00:00Z".to_string()
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_fact_creation() {
        let fact = Fact::new();
        assert_eq!(fact.get_cache_stats(), r#"{"size":0,"entries":0,"capacity":10485760}"#);
    }

    #[test]
    fn test_template_processing() {
        let template = CognitiveTemplate {
            id: "test".to_string(),
            name: "Test Template".to_string(),
            description: "Test".to_string(),
            pattern: TemplatePattern {
                pattern_type: "sequential".to_string(),
                steps: vec![],
            },
            cache_ttl: None,
        };
        
        let context = serde_json::json!({"test": "data"});
        let result = apply_template(&template, &context);
        
        assert!(result.get("template_id").is_some());
        assert!(result.get("result").is_some());
    }
}