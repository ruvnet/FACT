//! Cognitive Template Engine
//! 
//! Advanced template processing system with AI-driven context analysis
//! and intelligent decision making capabilities.

pub mod engine;
pub mod template;
pub mod context;
pub mod cache;

pub use engine::CognitiveEngine;
pub use template::{Template, TemplateType, TemplateMetadata};
pub use context::{Context, ContextAnalyzer, ContextType};
pub use cache::{CognitiveCache, CacheEntry};

use crate::error::{FactError, Result};

/// Cognitive processing capabilities
#[derive(Debug, Clone, PartialEq)]
pub enum CognitiveCapability {
    /// Natural language understanding
    LanguageProcessing,
    /// Pattern-based reasoning
    PatternReasoning,
    /// Context-aware decision making
    ContextualDecisions,
    /// Template generation and processing
    TemplateProcessing,
    /// Autonomous task execution
    AutonomousExecution,
}

/// Cognitive processing levels
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum ProcessingLevel {
    /// Basic template substitution
    Basic = 1,
    /// Context-aware processing
    Contextual = 2,
    /// Pattern-enhanced processing
    Enhanced = 3,
    /// Full cognitive processing with reasoning
    Cognitive = 4,
    /// Autonomous decision-making
    Autonomous = 5,
}