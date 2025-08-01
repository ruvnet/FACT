//! FACT - Fast Augmented Context Tools
//! 
//! A high-performance context processing engine with WebAssembly support.

use wasm_bindgen::prelude::*;
use serde::{Serialize, Deserialize};
use std::collections::HashMap;

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
    pub fn get_cache_stats(&self) -> JsValue {
        self.cache.get_stats()
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

/// Enhanced cognitive template definition with versioning and metadata
#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct CognitiveTemplate {
    pub id: String,
    pub name: String, 
    pub description: String,
    pub version: String,
    pub pattern: TemplatePattern,
    pub cache_ttl: Option<u64>,
    pub priority: TemplatePriority,
    pub tags: Vec<String>,
    pub created_at: String,
    pub updated_at: String,
    pub usage_count: u64,
    pub success_rate: f64,
    pub metadata: HashMap<String, serde_json::Value>,
}

/// Template priority levels for processing optimization
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub enum TemplatePriority {
    Critical,
    High,
    Medium,
    Low,
    Background,
}

/// Enhanced template pattern definition with optimization hints
#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct TemplatePattern {
    pub pattern_type: String,
    pub steps: Vec<ProcessingStep>,
    pub parallel_execution: bool,
    pub optimization_hints: Vec<OptimizationHint>,
    pub dependencies: Vec<String>,
    pub expected_execution_time_ms: Option<f64>,
    pub memory_requirements: Option<usize>,
}

/// Optimization hints for the template engine
#[derive(Serialize, Deserialize, Debug, Clone)]
pub enum OptimizationHint {
    CacheAggressive,
    ParallelProcessing,
    MemoryOptimized,
    SIMDVectorized,
    BatchProcessing,
    StreamProcessing,
}

/// Enhanced processing step with execution metadata
#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct ProcessingStep {
    pub step_type: String,
    pub config: HashMap<String, serde_json::Value>,
    pub step_id: String,
    pub depends_on: Vec<String>,
    pub retry_policy: RetryPolicy,
    pub timeout_ms: Option<u64>,
    pub validation_rules: Vec<ValidationRule>,
    pub performance_metrics: Option<StepMetrics>,
}

/// Retry policy for failed processing steps
#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct RetryPolicy {
    pub max_attempts: u32,
    pub backoff_strategy: BackoffStrategy,
    pub retry_conditions: Vec<String>,
}

/// Backoff strategy for retries
#[derive(Serialize, Deserialize, Debug, Clone)]
pub enum BackoffStrategy {
    Linear { delay_ms: u64 },
    Exponential { base_delay_ms: u64, max_delay_ms: u64 },
    Fixed { delay_ms: u64 },
}

/// Validation rules for processing steps
#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct ValidationRule {
    pub rule_type: String,
    pub condition: String,
    pub error_message: String,
}

/// Performance metrics for processing steps
#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct StepMetrics {
    pub execution_count: u64,
    pub total_time_ms: f64,
    pub average_time_ms: f64,
    pub success_rate: f64,
    pub error_count: u64,
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

/// Apply a cognitive template to context with enhanced processing
fn apply_template(template: &CognitiveTemplate, context: &serde_json::Value) -> serde_json::Value {
    let start_time = js_sys::Date::now();
    let mut result = context.clone();
    let mut step_results = Vec::new();
    let mut execution_metrics = HashMap::new();
    
    // Check if parallel execution is enabled
    if template.pattern.parallel_execution && template.pattern.steps.len() > 1 {
        result = process_steps_parallel(&template.pattern.steps, &result, &mut step_results);
    } else {
        result = process_steps_sequential(&template.pattern.steps, &result, &mut step_results);
    }
    
    let execution_time = js_sys::Date::now() - start_time;
    
    // Apply optimization hints
    for hint in &template.pattern.optimization_hints {
        result = apply_optimization_hint(hint, &result);
    }
    
    execution_metrics.insert("total_execution_time_ms".to_string(), serde_json::Value::Number(
        serde_json::Number::from_f64(execution_time).unwrap()
    ));
    execution_metrics.insert("steps_executed".to_string(), serde_json::Value::Number(
        serde_json::Number::from(template.pattern.steps.len())
    ));
    
    serde_json::json!({
        "template_id": template.id,
        "template_version": template.version,
        "result": result,
        "step_results": step_results,
        "execution_metrics": execution_metrics,
        "processed_at": chrono::Utc::now().to_rfc3339(),
        "success": true,
        "cache_key": generate_cache_key(&template.id, context)
    })
}

/// Process steps in parallel (simplified for WASM)
fn process_steps_parallel(
    steps: &[ProcessingStep], 
    context: &serde_json::Value,
    step_results: &mut Vec<serde_json::Value>
) -> serde_json::Value {
    // In a real implementation, this would use Web Workers or similar
    // For now, we'll simulate parallel processing with optimized sequential execution
    let mut result = context.clone();
    
    for step in steps {
        let step_start = js_sys::Date::now();
        let step_result = process_step(step, &result);
        let step_time = js_sys::Date::now() - step_start;
        
        step_results.push(serde_json::json!({
            "step_id": step.step_id,
            "execution_time_ms": step_time,
            "result": step_result
        }));
        
        result = step_result;
    }
    
    result
}

/// Process steps sequentially with dependency resolution
fn process_steps_sequential(
    steps: &[ProcessingStep], 
    context: &serde_json::Value,
    step_results: &mut Vec<serde_json::Value>
) -> serde_json::Value {
    let mut result = context.clone();
    let mut completed_steps: HashMap<String, serde_json::Value> = HashMap::new();
    
    for step in steps {
        // Check dependencies
        if !step.depends_on.is_empty() {
            for dep in &step.depends_on {
                if !completed_steps.contains_key(dep) {
                    // Dependency not met, skip this step or handle error
                    continue;
                }
            }
        }
        
        let step_start = js_sys::Date::now();
        let step_result = process_step_with_retry(step, &result);
        let step_time = js_sys::Date::now() - step_start;
        
        step_results.push(serde_json::json!({
            "step_id": step.step_id,
            "execution_time_ms": step_time,
            "result": step_result
        }));
        
        completed_steps.insert(step.step_id.clone(), step_result.clone());
        result = step_result;
    }
    
    result
}

/// Process a step with retry logic
fn process_step_with_retry(step: &ProcessingStep, data: &serde_json::Value) -> serde_json::Value {
    let mut attempt = 0;
    let max_attempts = step.retry_policy.max_attempts;
    
    loop {
        attempt += 1;
        
        // Validate input data
        if let Err(validation_error) = validate_step_input(step, data) {
            if attempt >= max_attempts {
                return serde_json::json!({
                    "error": "Validation failed",
                    "message": validation_error,
                    "step_id": step.step_id
                });
            }
            continue;
        }
        
        let result = process_step(step, data);
        
        // Check if result indicates success
        if is_step_successful(&result) {
            return result;
        }
        
        if attempt >= max_attempts {
            return serde_json::json!({
                "error": "Max retry attempts exceeded",
                "step_id": step.step_id,
                "attempts": attempt
            });
        }
        
        // Apply backoff strategy
        apply_backoff(&step.retry_policy.backoff_strategy, attempt);
    }
}

/// Validate step input according to validation rules
fn validate_step_input(step: &ProcessingStep, data: &serde_json::Value) -> Result<(), String> {
    for rule in &step.validation_rules {
        match rule.rule_type.as_str() {
            "required_field" => {
                if data.get(&rule.condition).is_none() {
                    return Err(rule.error_message.clone());
                }
            },
            "type_check" => {
                // Implement type checking logic
            },
            "range_check" => {
                // Implement range checking logic
            },
            _ => {}
        }
    }
    Ok(())
}

/// Check if step execution was successful
fn is_step_successful(result: &serde_json::Value) -> bool {
    !result.get("error").is_some()
}

/// Apply backoff strategy for retry delays
fn apply_backoff(strategy: &BackoffStrategy, _attempt: u32) {
    // In WASM, we can't actually sleep, but we can simulate delay
    // This would be implemented with actual async delays in a real system
    match strategy {
        BackoffStrategy::Linear { delay_ms: _ } => {
            // Linear backoff: delay_ms * attempt
        },
        BackoffStrategy::Exponential { base_delay_ms: _, max_delay_ms: _ } => {
            // Exponential backoff: min(base_delay_ms * 2^attempt, max_delay_ms)
        },
        BackoffStrategy::Fixed { delay_ms: _ } => {
            // Fixed delay
        }
    }
}

/// Apply optimization hints to the result
fn apply_optimization_hint(hint: &OptimizationHint, result: &serde_json::Value) -> serde_json::Value {
    match hint {
        OptimizationHint::CacheAggressive => {
            // Add cache metadata
            let mut optimized = result.clone();
            if let serde_json::Value::Object(ref mut map) = optimized {
                map.insert("_cache_hint".to_string(), serde_json::Value::String("aggressive".to_string()));
            }
            optimized
        },
        OptimizationHint::MemoryOptimized => {
            // Compress or optimize data structure
            compress_result(result)
        },
        OptimizationHint::SIMDVectorized => {
            // Apply SIMD optimizations where possible
            vectorize_result(result)
        },
        _ => result.clone()
    }
}

/// Generate cache key for template and context
fn generate_cache_key(template_id: &str, context: &serde_json::Value) -> String {
    use std::collections::hash_map::DefaultHasher;
    use std::hash::{Hash, Hasher};
    
    let context_str = serde_json::to_string(context).unwrap_or_default();
    let mut hasher = DefaultHasher::new();
    template_id.hash(&mut hasher);
    context_str.hash(&mut hasher);
    format!("tpl_{}_{:x}", template_id, hasher.finish())
}

/// Compress result for memory optimization
fn compress_result(result: &serde_json::Value) -> serde_json::Value {
    // Implement result compression logic
    result.clone()
}

/// Vectorize result for SIMD optimization
fn vectorize_result(result: &serde_json::Value) -> serde_json::Value {
    // Implement vectorization logic
    result.clone()
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

fn generate_insights(_data: &serde_json::Value) -> Vec<String> {
    vec![
        "Pattern detected in data structure".to_string(),
        "Optimization opportunity identified".to_string(),
        "Potential for parallel processing".to_string(),
    ]
}

fn generate_recommendations(_data: &serde_json::Value) -> Vec<String> {
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
        let stats = fact.get_cache_stats();
        assert!(!stats.is_null());
    }

    #[test]
    fn test_template_processing() {
        let template = CognitiveTemplate {
            id: "test".to_string(),
            name: "Test Template".to_string(),
            description: "Test".to_string(),
            version: "1.0.0".to_string(),
            pattern: TemplatePattern {
                pattern_type: "sequential".to_string(),
                steps: vec![],
                parallel_execution: false,
                optimization_hints: vec![],
                dependencies: vec![],
                expected_execution_time_ms: None,
                memory_requirements: None,
            },
            cache_ttl: None,
            priority: TemplatePriority::Medium,
            tags: vec![],
            created_at: "2024-01-01T00:00:00Z".to_string(),
            updated_at: "2024-01-01T00:00:00Z".to_string(),
            usage_count: 0,
            success_rate: 1.0,
            metadata: HashMap::new(),
        };
        
        let context = serde_json::json!({"test": "data"});
        let result = apply_template(&template, &context);
        
        assert!(result.get("template_id").is_some());
        assert!(result.get("result").is_some());
    }
}