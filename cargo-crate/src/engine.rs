//! Core processing engine for FACT

use crate::{FactError, Result, Template, TemplateRegistry};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use std::time::Duration;
use tokio::time::timeout;

/// Configuration for the FACT engine
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EngineConfig {
    /// Maximum processing timeout
    pub timeout: Duration,
    
    /// Enable parallel processing
    pub parallel: bool,
    
    /// Maximum concurrent tasks
    pub max_concurrent: usize,
    
    /// Enable performance monitoring
    pub monitoring: bool,
}

impl Default for EngineConfig {
    fn default() -> Self {
        Self {
            timeout: Duration::from_secs(30),
            parallel: true,
            max_concurrent: num_cpus::get(),
            monitoring: true,
        }
    }
}

/// Processing options for individual requests
#[derive(Debug, Clone, Default)]
pub struct ProcessingOptions {
    /// Override default timeout
    pub timeout: Option<Duration>,
    
    /// Disable caching for this request
    pub no_cache: bool,
    
    /// Processing priority
    pub priority: Priority,
}

/// Processing priority levels
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum Priority {
    Low,
    Normal,
    High,
    Critical,
}

impl Default for Priority {
    fn default() -> Self {
        Self::Normal
    }
}

/// The main FACT processing engine
pub struct FactEngine {
    config: EngineConfig,
    registry: Arc<TemplateRegistry>,
}

impl FactEngine {
    /// Create a new engine with default configuration
    pub fn new() -> Self {
        Self::with_config(EngineConfig::default())
    }
    
    /// Create a new engine with custom configuration
    pub fn with_config(config: EngineConfig) -> Self {
        Self {
            config,
            registry: Arc::new(TemplateRegistry::new()),
        }
    }
    
    /// Process a context using a cognitive template
    pub async fn process(
        &self,
        template_id: &str,
        context: serde_json::Value,
    ) -> Result<serde_json::Value> {
        self.process_with_options(template_id, context, ProcessingOptions::default())
            .await
    }
    
    /// Process with custom options
    pub async fn process_with_options(
        &self,
        template_id: &str,
        context: serde_json::Value,
        options: ProcessingOptions,
    ) -> Result<serde_json::Value> {
        let template = self
            .registry
            .get(template_id)
            .ok_or_else(|| FactError::TemplateNotFound(template_id.to_string()))?;
        
        let timeout_duration = options.timeout.unwrap_or(self.config.timeout);
        
        match timeout(
            timeout_duration,
            self.execute_template(&template, context, &options),
        )
        .await
        {
            Ok(result) => result,
            Err(_) => Err(FactError::Timeout(timeout_duration)),
        }
    }
    
    /// Execute a template
    async fn execute_template(
        &self,
        template: &Template,
        mut context: serde_json::Value,
        options: &ProcessingOptions,
    ) -> Result<serde_json::Value> {
        // Execute each step in the template
        for step in &template.steps {
            context = self.execute_step(&step, context, options).await?;
        }
        
        Ok(serde_json::json!({
            "template_id": template.id,
            "template_name": template.name,
            "result": context,
            "metadata": {
                "processed_at": chrono::Utc::now().to_rfc3339(),
                "priority": format!("{:?}", options.priority),
            }
        }))
    }
    
    /// Execute a single processing step
    async fn execute_step(
        &self,
        step: &ProcessingStep,
        context: serde_json::Value,
        _options: &ProcessingOptions,
    ) -> Result<serde_json::Value> {
        match &step.operation {
            Operation::Transform(transform) => self.apply_transform(transform, context),
            Operation::Analyze(analysis) => self.apply_analysis(analysis, context),
            Operation::Filter(filter) => self.apply_filter(filter, context),
            Operation::Aggregate(aggregation) => self.apply_aggregation(aggregation, context),
        }
    }
    
    fn apply_transform(
        &self,
        transform: &Transform,
        mut context: serde_json::Value,
    ) -> Result<serde_json::Value> {
        match transform {
            Transform::Expand => {
                if let Some(obj) = context.as_object_mut() {
                    obj.insert(
                        "_expanded".to_string(),
                        serde_json::Value::Bool(true),
                    );
                    obj.insert(
                        "_timestamp".to_string(),
                        serde_json::Value::String(chrono::Utc::now().to_rfc3339()),
                    );
                }
            }
            Transform::Compress => {
                if let Some(obj) = context.as_object_mut() {
                    obj.retain(|k, _| !k.starts_with('_'));
                }
            }
            Transform::Normalize => {
                // Normalize the data structure
                context = normalize_json(context);
            }
        }
        
        Ok(context)
    }
    
    fn apply_analysis(
        &self,
        analysis: &Analysis,
        context: serde_json::Value,
    ) -> Result<serde_json::Value> {
        let result = match analysis {
            Analysis::Statistical => {
                serde_json::json!({
                    "original": context,
                    "analysis": {
                        "type": "statistical",
                        "metrics": compute_statistics(&context),
                    }
                })
            }
            Analysis::Pattern => {
                serde_json::json!({
                    "original": context,
                    "analysis": {
                        "type": "pattern",
                        "patterns": detect_patterns(&context),
                    }
                })
            }
            Analysis::Semantic => {
                serde_json::json!({
                    "original": context,
                    "analysis": {
                        "type": "semantic",
                        "entities": extract_entities(&context),
                        "concepts": extract_concepts(&context),
                    }
                })
            }
        };
        
        Ok(result)
    }
    
    fn apply_filter(
        &self,
        filter: &Filter,
        context: serde_json::Value,
    ) -> Result<serde_json::Value> {
        match filter {
            Filter::Type(type_name) => {
                // Filter by type
                if context.get("type").and_then(|v| v.as_str()) == Some(type_name) {
                    Ok(context)
                } else {
                    Ok(serde_json::Value::Null)
                }
            }
            Filter::Range { min, max } => {
                // Filter by numeric range
                if let Some(value) = context.as_f64() {
                    if value >= *min && value <= *max {
                        Ok(context)
                    } else {
                        Ok(serde_json::Value::Null)
                    }
                } else {
                    Ok(context)
                }
            }
            Filter::Custom(expr) => {
                // Apply custom filter expression
                // This is a simplified implementation
                if expr.contains("true") {
                    Ok(context)
                } else {
                    Ok(serde_json::Value::Null)
                }
            }
        }
    }
    
    fn apply_aggregation(
        &self,
        aggregation: &Aggregation,
        context: serde_json::Value,
    ) -> Result<serde_json::Value> {
        match aggregation {
            Aggregation::Sum => {
                let sum = sum_numeric_values(&context);
                Ok(serde_json::json!({ "sum": sum }))
            }
            Aggregation::Average => {
                let (sum, count) = sum_and_count_numeric_values(&context);
                let avg = if count > 0 { sum / count as f64 } else { 0.0 };
                Ok(serde_json::json!({ "average": avg }))
            }
            Aggregation::Count => {
                let count = count_values(&context);
                Ok(serde_json::json!({ "count": count }))
            }
        }
    }
}

impl Default for FactEngine {
    fn default() -> Self {
        Self::new()
    }
}

/// Processing step in a template
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProcessingStep {
    pub name: String,
    pub operation: Operation,
}

/// Available operations
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "lowercase")]
pub enum Operation {
    Transform(Transform),
    Analyze(Analysis),
    Filter(Filter),
    Aggregate(Aggregation),
}

/// Transform operations
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Transform {
    Expand,
    Compress,
    Normalize,
}

/// Analysis operations
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Analysis {
    Statistical,
    Pattern,
    Semantic,
}

/// Filter operations
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "lowercase")]
pub enum Filter {
    Type(String),
    Range { min: f64, max: f64 },
    Custom(String),
}

/// Aggregation operations
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Aggregation {
    Sum,
    Average,
    Count,
}

// Helper functions

fn normalize_json(value: serde_json::Value) -> serde_json::Value {
    match value {
        serde_json::Value::Object(map) => {
            let normalized: serde_json::Map<String, serde_json::Value> = map
                .into_iter()
                .map(|(k, v)| (k.to_lowercase(), normalize_json(v)))
                .collect();
            serde_json::Value::Object(normalized)
        }
        serde_json::Value::Array(arr) => {
            serde_json::Value::Array(arr.into_iter().map(normalize_json).collect())
        }
        other => other,
    }
}

fn compute_statistics(value: &serde_json::Value) -> serde_json::Value {
    let numbers = extract_numbers(value);
    
    if numbers.is_empty() {
        return serde_json::json!({});
    }
    
    let sum: f64 = numbers.iter().sum();
    let count = numbers.len() as f64;
    let mean = sum / count;
    
    let variance = numbers.iter().map(|n| (n - mean).powi(2)).sum::<f64>() / count;
    let std_dev = variance.sqrt();
    
    serde_json::json!({
        "count": count,
        "sum": sum,
        "mean": mean,
        "std_dev": std_dev,
        "min": numbers.iter().cloned().fold(f64::INFINITY, f64::min),
        "max": numbers.iter().cloned().fold(f64::NEG_INFINITY, f64::max),
    })
}

fn extract_numbers(value: &serde_json::Value) -> Vec<f64> {
    let mut numbers = Vec::new();
    
    match value {
        serde_json::Value::Number(n) => {
            if let Some(f) = n.as_f64() {
                numbers.push(f);
            }
        }
        serde_json::Value::Array(arr) => {
            for v in arr {
                numbers.extend(extract_numbers(v));
            }
        }
        serde_json::Value::Object(map) => {
            for v in map.values() {
                numbers.extend(extract_numbers(v));
            }
        }
        _ => {}
    }
    
    numbers
}

fn detect_patterns(value: &serde_json::Value) -> Vec<String> {
    let mut patterns = Vec::new();
    
    if let Some(obj) = value.as_object() {
        if obj.contains_key("query") || obj.contains_key("question") {
            patterns.push("inquiry".to_string());
        }
        if obj.contains_key("data") || obj.contains_key("dataset") {
            patterns.push("data-driven".to_string());
        }
        if obj.contains_key("rules") || obj.contains_key("constraints") {
            patterns.push("rule-based".to_string());
        }
    }
    
    patterns
}

fn extract_entities(value: &serde_json::Value) -> Vec<String> {
    // Simplified entity extraction
    let text = serde_json::to_string(value).unwrap_or_default();
    
    // Extract capitalized words as potential entities
    text.split_whitespace()
        .filter(|word| word.chars().next().map_or(false, |c| c.is_uppercase()))
        .take(10)
        .map(|s| s.to_string())
        .collect()
}

fn extract_concepts(_value: &serde_json::Value) -> Vec<String> {
    // Simplified concept extraction
    vec![
        "processing".to_string(),
        "analysis".to_string(),
        "transformation".to_string(),
    ]
}

fn sum_numeric_values(value: &serde_json::Value) -> f64 {
    extract_numbers(value).iter().sum()
}

fn sum_and_count_numeric_values(value: &serde_json::Value) -> (f64, usize) {
    let numbers = extract_numbers(value);
    (numbers.iter().sum(), numbers.len())
}

fn count_values(value: &serde_json::Value) -> usize {
    match value {
        serde_json::Value::Array(arr) => arr.len(),
        serde_json::Value::Object(map) => map.len(),
        _ => 1,
    }
}

