//! # FACT Core - Rust Implementation
//! 
//! A high-performance cognitive template engine and pattern recognition system
//! designed for autonomous execution and intelligent decision making.
//! 
//! ## Features
//! 
//! - **Cognitive Templates**: Advanced template engine with AI-driven content generation
//! - **Pattern Recognition**: ML-powered pattern detection and analysis
//! - **Autonomous Execution**: Self-managing execution engine with error recovery
//! - **Performance Optimized**: Built for sub-millisecond response times
//! 
//! ## Architecture
//! 
//! ```text
//! ┌─────────────────────────────────────────────────────────────┐
//! │                     FACT Core Architecture                  │
//! ├─────────────────────────────────────────────────────────────┤
//! │  Cognitive Engine    │  Pattern System  │  Execution Engine │
//! │  ─────────────────   │  ─────────────    │  ─────────────── │
//! │  • Template Processing │  • ML Models    │  • Task Management│
//! │  • Context Analysis    │  • Recognition   │  • Error Recovery │
//! │  • Decision Making     │  • Prediction    │  • Performance   │
//! └─────────────────────────────────────────────────────────────┘
//! ```

pub mod cognitive;
pub mod pattern;
pub mod execution;
pub mod error;

// Re-export main types
pub use cognitive::{CognitiveEngine, Template, Context};
pub use pattern::{PatternRecognizer, Pattern, RecognitionResult};
pub use execution::{ExecutionEngine, Task, TaskResult};
pub use error::{FactError, Result};

/// FACT Core version
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

/// Initialize the FACT Core system with default configuration
pub async fn init() -> Result<FactCore> {
    FactCore::new().await
}

/// Main FACT Core system coordinator
#[derive(Debug)]
pub struct FactCore {
    pub cognitive: CognitiveEngine,
    pub pattern: PatternRecognizer,
    pub execution: ExecutionEngine,
}

impl FactCore {
    /// Create a new FACT Core instance
    pub async fn new() -> Result<Self> {
        tracing::info!("Initializing FACT Core v{}", VERSION);
        
        let cognitive = CognitiveEngine::new().await?;
        let pattern = PatternRecognizer::new().await?;
        let execution = ExecutionEngine::new().await?;
        
        Ok(Self {
            cognitive,
            pattern,
            execution,
        })
    }
    
    /// Process a cognitive task end-to-end
    pub async fn process_task(&mut self, input: &str) -> Result<TaskResult> {
        // 1. Cognitive analysis and template processing
        let context = self.cognitive.analyze_context(input).await?;
        let template = self.cognitive.select_template(&context).await?;
        let processed = self.cognitive.process_template(&template, &context).await?;
        
        // 2. Pattern recognition and enhancement
        let patterns = self.pattern.recognize(&processed).await?;
        let enhanced = self.pattern.enhance_with_patterns(&processed, &patterns).await?;
        
        // 3. Autonomous execution
        let task = Task::new(&enhanced);
        let result = self.execution.execute(task).await?;
        
        Ok(result)
    }
    
    /// Get system performance metrics
    pub async fn metrics(&self) -> Result<SystemMetrics> {
        Ok(SystemMetrics {
            cognitive_cache_size: self.cognitive.cache_size(),
            pattern_models_loaded: self.pattern.models_count(),
            execution_tasks_active: self.execution.active_tasks(),
            memory_usage_mb: self.memory_usage_mb(),
        })
    }
    
    /// Shutdown the system gracefully
    pub async fn shutdown(self) -> Result<()> {
        tracing::info!("Shutting down FACT Core");
        
        self.execution.shutdown().await?;
        self.pattern.shutdown().await?;
        self.cognitive.shutdown().await?;
        
        Ok(())
    }
    
    fn memory_usage_mb(&self) -> f64 {
        // Placeholder for memory usage calculation
        // In a real implementation, this would use system APIs
        std::mem::size_of::<Self>() as f64 / 1024.0 / 1024.0
    }
}

/// System performance metrics
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct SystemMetrics {
    pub cognitive_cache_size: usize,
    pub pattern_models_loaded: usize,
    pub execution_tasks_active: usize,
    pub memory_usage_mb: f64,
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[tokio::test]
    async fn test_fact_core_initialization() {
        let core = FactCore::new().await;
        assert!(core.is_ok());
    }
    
    #[tokio::test]
    async fn test_process_task() {
        let mut core = FactCore::new().await.unwrap();
        let result = core.process_task("analyze financial data").await;
        assert!(result.is_ok());
    }
}