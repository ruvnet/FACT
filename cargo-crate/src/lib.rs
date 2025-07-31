//! # FACT - Fast Augmented Context Tools
//! 
//! A high-performance context processing engine for Rust.
//! 
//! ## Features
//! 
//! - **High Performance**: Optimized data structures and algorithms
//! - **Intelligent Caching**: Multi-tier caching with LRU eviction
//! - **Cognitive Templates**: Pre-built templates for common patterns
//! - **Async Support**: Full async/await support with Tokio
//! - **Cross-Platform**: Works on Linux, macOS, and Windows
//! 
//! ## Example
//! 
//! ```rust
//! use fact::{FactEngine, Template};
//! 
//! # async fn example() -> Result<(), Box<dyn std::error::Error>> {
//! // Create a new FACT engine
//! let mut engine = FactEngine::new();
//! 
//! // Process with a template
//! let result = engine.process(
//!     "analysis-basic",
//!     serde_json::json!({
//!         "data": [1, 2, 3, 4, 5],
//!         "operation": "sum"
//!     })
//! ).await?;
//! 
//! println!("Result: {}", result);
//! # Ok(())
//! # }
//! ```

use parking_lot::RwLock;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use std::time::Duration;
use thiserror::Error;

pub mod cache;
pub mod engine;
pub mod processor;
pub mod templates;

pub use cache::{Cache, CacheStats};
pub use engine::{FactEngine, ProcessingOptions};
pub use processor::QueryProcessor;
pub use templates::{Template, TemplateRegistry};

/// Result type for FACT operations
pub type Result<T> = std::result::Result<T, FactError>;

/// Errors that can occur in FACT operations
#[derive(Error, Debug)]
pub enum FactError {
    #[error("Template not found: {0}")]
    TemplateNotFound(String),
    
    #[error("Processing error: {0}")]
    ProcessingError(String),
    
    #[error("Serialization error: {0}")]
    SerializationError(#[from] serde_json::Error),
    
    #[error("IO error: {0}")]
    IoError(#[from] std::io::Error),
    
    #[error("Cache error: {0}")]
    CacheError(String),
    
    #[error("Timeout exceeded: {0:?}")]
    Timeout(Duration),
}

/// Main entry point for FACT functionality
pub struct Fact {
    engine: FactEngine,
    cache: Arc<RwLock<Cache>>,
}

impl Fact {
    /// Create a new FACT instance
    pub fn new() -> Self {
        Self {
            engine: FactEngine::new(),
            cache: Arc::new(RwLock::new(Cache::new())),
        }
    }
    
    /// Create a new FACT instance with custom configuration
    pub fn with_config(config: FactConfig) -> Self {
        Self {
            engine: FactEngine::with_config(config.engine_config),
            cache: Arc::new(RwLock::new(Cache::with_capacity(config.cache_size))),
        }
    }
    
    /// Process a query using a cognitive template
    pub async fn process(
        &self,
        template_id: &str,
        context: serde_json::Value,
    ) -> Result<serde_json::Value> {
        // Check cache first
        let cache_key = self.generate_cache_key(template_id, &context);
        
        // Need to use write lock for get() since it updates access stats
        if let Some(cached) = self.cache.write().get(&cache_key) {
            return Ok(cached.clone());
        }
        
        // Process with engine
        let result = self.engine.process(template_id, context).await?;
        
        // Cache the result
        self.cache.write().put(cache_key, result.clone());
        
        Ok(result)
    }
    
    /// Get cache statistics
    pub fn cache_stats(&self) -> CacheStats {
        self.cache.read().stats()
    }
    
    /// Clear the cache
    pub fn clear_cache(&self) {
        self.cache.write().clear();
    }
    
    fn generate_cache_key(&self, template_id: &str, context: &serde_json::Value) -> String {
        use std::collections::hash_map::DefaultHasher;
        use std::hash::{Hash, Hasher};
        
        let mut hasher = DefaultHasher::new();
        template_id.hash(&mut hasher);
        context.to_string().hash(&mut hasher);
        
        format!("fact:{}:{:x}", template_id, hasher.finish())
    }
}

impl Default for Fact {
    fn default() -> Self {
        Self::new()
    }
}

/// Configuration for FACT
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FactConfig {
    /// Engine configuration
    pub engine_config: engine::EngineConfig,
    
    /// Cache size in bytes
    pub cache_size: usize,
    
    /// Enable performance monitoring
    pub enable_monitoring: bool,
    
    /// Maximum processing timeout
    pub timeout: Option<Duration>,
}

impl Default for FactConfig {
    fn default() -> Self {
        Self {
            engine_config: Default::default(),
            cache_size: 100 * 1024 * 1024, // 100MB
            enable_monitoring: true,
            timeout: Some(Duration::from_secs(30)),
        }
    }
}

/// Performance metrics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Metrics {
    pub total_requests: u64,
    pub cache_hits: u64,
    pub cache_misses: u64,
    pub avg_processing_time_ms: f64,
    pub error_count: u64,
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[tokio::test]
    async fn test_fact_creation() {
        let fact = Fact::new();
        let stats = fact.cache_stats();
        assert_eq!(stats.entries, 0);
    }
    
    #[tokio::test]
    async fn test_basic_processing() {
        let fact = Fact::new();
        let context = serde_json::json!({
            "data": [1, 2, 3, 4, 5],
            "operation": "sum"
        });
        
        // This will use a mock template since we haven't loaded real ones
        match fact.process("test-template", context).await {
            Ok(_) => {
                // Template found and processed
            }
            Err(FactError::TemplateNotFound(_)) => {
                // Expected if template not loaded
            }
            Err(e) => panic!("Unexpected error: {}", e),
        }
    }
}