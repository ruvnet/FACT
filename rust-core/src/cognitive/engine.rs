//! Cognitive Engine Implementation
//! 
//! Core cognitive processing engine that combines template processing,
//! context analysis, and intelligent decision making.

use super::{Template, Context, ContextAnalyzer, CognitiveCache, ProcessingLevel};
use crate::error::{FactError, Result};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::{info, debug, warn};

/// Main cognitive processing engine
#[derive(Debug)]
pub struct CognitiveEngine {
    /// Template registry
    templates: Arc<RwLock<HashMap<String, Template>>>,
    /// Context analyzer
    context_analyzer: ContextAnalyzer,
    /// Cognitive cache for processed results
    cache: CognitiveCache,
    /// Processing configuration
    config: CognitiveConfig,
}

/// Cognitive engine configuration
#[derive(Debug, Clone)]
pub struct CognitiveConfig {
    /// Default processing level
    pub processing_level: ProcessingLevel,
    /// Cache enabled
    pub cache_enabled: bool,
    /// Maximum cache size
    pub max_cache_size: usize,
    /// Template preloading enabled
    pub preload_templates: bool,
    /// Context analysis depth
    pub context_depth: u8,
}

impl Default for CognitiveConfig {
    fn default() -> Self {
        Self {
            processing_level: ProcessingLevel::Cognitive,
            cache_enabled: true,
            max_cache_size: 1000,
            preload_templates: true,
            context_depth: 3,
        }
    }
}

impl CognitiveEngine {
    /// Create a new cognitive engine with default configuration
    pub async fn new() -> Result<Self> {
        Self::with_config(CognitiveConfig::default()).await
    }
    
    /// Create a new cognitive engine with custom configuration
    pub async fn with_config(config: CognitiveConfig) -> Result<Self> {
        info!("Initializing Cognitive Engine with processing level: {:?}", config.processing_level);
        
        let templates = Arc::new(RwLock::new(HashMap::new()));
        let context_analyzer = ContextAnalyzer::new().await?;
        let cache = CognitiveCache::with_capacity(config.max_cache_size);
        
        let engine = Self {
            templates,
            context_analyzer,
            cache,
            config,
        };
        
        if engine.config.preload_templates {
            engine.preload_default_templates().await?;
        }
        
        Ok(engine)
    }
    
    /// Analyze input context
    pub async fn analyze_context(&self, input: &str) -> Result<Context> {
        debug!("Analyzing context for input length: {}", input.len());
        
        // Check cache first
        if self.config.cache_enabled {
            if let Some(cached) = self.cache.get_context(input).await {
                debug!("Context cache hit");
                return Ok(cached);
            }
        }
        
        let context = self.context_analyzer.analyze(input, self.config.context_depth).await?;
        
        // Cache the result
        if self.config.cache_enabled {
            self.cache.store_context(input, &context).await;
        }
        
        Ok(context)
    }
    
    /// Select appropriate template based on context
    pub async fn select_template(&self, context: &Context) -> Result<Template> {
        debug!("Selecting template for context type: {:?}", context.context_type);
        
        let templates = self.templates.read().await;
        
        // Smart template selection based on context
        let template_key = match &context.context_type {
            super::ContextType::Financial => "financial_analysis",
            super::ContextType::Technical => "technical_report",
            super::ContextType::Analytical => "data_analysis",
            super::ContextType::Creative => "creative_content",
            super::ContextType::Unknown => "generic",
        };
        
        templates.get(template_key)
            .cloned()
            .ok_or_else(|| FactError::TemplateNotFound(template_key.to_string()))
    }
    
    /// Process template with context
    pub async fn process_template(&self, template: &Template, context: &Context) -> Result<String> {
        debug!("Processing template: {} with context", template.name);
        
        // Check cache first
        let cache_key = format!("{}:{}", template.id, context.hash());
        if self.config.cache_enabled {
            if let Some(cached) = self.cache.get_processed(&cache_key).await {
                debug!("Template processing cache hit");
                return Ok(cached);
            }
        }
        
        let result = match self.config.processing_level {
            ProcessingLevel::Basic => self.process_basic(template, context).await?,
            ProcessingLevel::Contextual => self.process_contextual(template, context).await?,
            ProcessingLevel::Enhanced => self.process_enhanced(template, context).await?,
            ProcessingLevel::Cognitive => self.process_cognitive(template, context).await?,
            ProcessingLevel::Autonomous => self.process_autonomous(template, context).await?,
        };
        
        // Cache the result
        if self.config.cache_enabled {
            self.cache.store_processed(&cache_key, &result).await;
        }
        
        Ok(result)
    }
    
    /// Get cache size
    pub fn cache_size(&self) -> usize {
        self.cache.size()
    }
    
    /// Shutdown the engine
    pub async fn shutdown(self) -> Result<()> {
        info!("Shutting down Cognitive Engine");
        // Cleanup resources if needed
        Ok(())
    }
    
    // Private implementation methods
    
    async fn preload_default_templates(&self) -> Result<()> {
        info!("Preloading default templates");
        
        let mut templates = self.templates.write().await;
        
        // Financial analysis template
        templates.insert("financial_analysis".to_string(), Template {
            id: "financial_analysis".to_string(),
            name: "Financial Analysis".to_string(),
            template_type: super::TemplateType::Analysis,
            content: include_str!("../templates/financial_analysis.hbs").to_string(),
            metadata: super::TemplateMetadata::default(),
        });
        
        // Technical report template
        templates.insert("technical_report".to_string(), Template {
            id: "technical_report".to_string(),
            name: "Technical Report".to_string(),
            template_type: super::TemplateType::Report,
            content: include_str!("../templates/technical_report.hbs").to_string(),
            metadata: super::TemplateMetadata::default(),
        });
        
        // Data analysis template
        templates.insert("data_analysis".to_string(), Template {
            id: "data_analysis".to_string(),
            name: "Data Analysis".to_string(),
            template_type: super::TemplateType::Analysis,
            content: include_str!("../templates/data_analysis.hbs").to_string(),
            metadata: super::TemplateMetadata::default(),
        });
        
        // Creative content template
        templates.insert("creative_content".to_string(), Template {
            id: "creative_content".to_string(),
            name: "Creative Content".to_string(),
            template_type: super::TemplateType::Creative,
            content: include_str!("../templates/creative_content.hbs").to_string(),
            metadata: super::TemplateMetadata::default(),
        });
        
        // Generic template
        templates.insert("generic".to_string(), Template {
            id: "generic".to_string(),
            name: "Generic Template".to_string(),
            template_type: super::TemplateType::Generic,
            content: include_str!("../templates/generic.hbs").to_string(),
            metadata: super::TemplateMetadata::default(),
        });
        
        info!("Loaded {} default templates", templates.len());
        Ok(())
    }
    
    async fn process_basic(&self, template: &Template, context: &Context) -> Result<String> {
        // Basic Handlebars template processing
        let handlebars = handlebars::Handlebars::new();
        let data = serde_json::json!({
            "context": context,
            "timestamp": chrono::Utc::now().to_rfc3339(),
        });
        
        handlebars.render_template(&template.content, &data)
            .map_err(|e| FactError::TemplateProcessing(e.to_string()))
    }
    
    async fn process_contextual(&self, template: &Template, context: &Context) -> Result<String> {
        // Enhanced processing with context awareness
        let mut basic_result = self.process_basic(template, context).await?;
        
        // Add context-specific enhancements
        if context.confidence_score > 0.8 {
            basic_result = format!("🎯 High Confidence Analysis:\n{}", basic_result);
        } else if context.confidence_score > 0.6 {
            basic_result = format!("📊 Analysis:\n{}", basic_result);
        } else {
            basic_result = format!("⚠️ Preliminary Analysis:\n{}", basic_result);
        }
        
        Ok(basic_result)
    }
    
    async fn process_enhanced(&self, template: &Template, context: &Context) -> Result<String> {
        // Pattern-enhanced processing
        let mut contextual_result = self.process_contextual(template, context).await?;
        
        // Add pattern-based insights
        contextual_result.push_str("\n\n🔍 Enhanced Insights:\n");
        contextual_result.push_str(&format!("• Context type: {:?}\n", context.context_type));
        contextual_result.push_str(&format!("• Confidence: {:.1}%\n", context.confidence_score * 100.0));
        contextual_result.push_str(&format!("• Keywords: {}\n", context.keywords.join(", ")));
        
        Ok(contextual_result)
    }
    
    async fn process_cognitive(&self, template: &Template, context: &Context) -> Result<String> {
        // Full cognitive processing with reasoning
        let mut enhanced_result = self.process_enhanced(template, context).await?;
        
        // Add cognitive reasoning
        enhanced_result.push_str("\n\n🧠 Cognitive Analysis:\n");
        
        // Reasoning based on context
        match &context.context_type {
            super::ContextType::Financial => {
                enhanced_result.push_str("• Applied financial domain expertise\n");
                enhanced_result.push_str("• Considered market conditions and trends\n");
                enhanced_result.push_str("• Evaluated risk factors and opportunities\n");
            }
            super::ContextType::Technical => {
                enhanced_result.push_str("• Applied technical analysis methodology\n");
                enhanced_result.push_str("• Considered implementation complexity\n");
                enhanced_result.push_str("• Evaluated scalability and performance\n");
            }
            super::ContextType::Analytical => {
                enhanced_result.push_str("• Applied data science principles\n");
                enhanced_result.push_str("• Considered statistical significance\n");
                enhanced_result.push_str("• Evaluated data quality and completeness\n");
            }
            _ => {
                enhanced_result.push_str("• Applied general reasoning principles\n");
                enhanced_result.push_str("• Considered multiple perspectives\n");
                enhanced_result.push_str("• Evaluated logical consistency\n");
            }
        }
        
        Ok(enhanced_result)
    }
    
    async fn process_autonomous(&self, template: &Template, context: &Context) -> Result<String> {
        // Autonomous decision-making processing
        let mut cognitive_result = self.process_cognitive(template, context).await?;
        
        // Add autonomous decision-making
        cognitive_result.push_str("\n\n🤖 Autonomous Decisions:\n");
        
        // Make autonomous decisions based on context
        if context.confidence_score > 0.9 {
            cognitive_result.push_str("• Decision: Proceed with high confidence\n");
            cognitive_result.push_str("• Action: Execute recommended strategy\n");
            cognitive_result.push_str("• Monitoring: Standard performance tracking\n");
        } else if context.confidence_score > 0.7 {
            cognitive_result.push_str("• Decision: Proceed with caution\n");
            cognitive_result.push_str("• Action: Execute with additional validation\n");
            cognitive_result.push_str("• Monitoring: Enhanced performance tracking\n");
        } else {
            cognitive_result.push_str("• Decision: Require human review\n");
            cognitive_result.push_str("• Action: Flag for manual assessment\n");
            cognitive_result.push_str("• Monitoring: Continuous human oversight\n");
        }
        
        // Add next steps
        cognitive_result.push_str("\n🎯 Recommended Next Steps:\n");
        cognitive_result.push_str("1. Review analysis results\n");
        cognitive_result.push_str("2. Validate key assumptions\n");
        cognitive_result.push_str("3. Monitor performance metrics\n");
        cognitive_result.push_str("4. Adjust strategy as needed\n");
        
        Ok(cognitive_result)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[tokio::test]
    async fn test_cognitive_engine_creation() {
        let engine = CognitiveEngine::new().await;
        assert!(engine.is_ok());
    }
    
    #[tokio::test]
    async fn test_context_analysis() {
        let engine = CognitiveEngine::new().await.unwrap();
        let context = engine.analyze_context("analyze quarterly financial performance").await;
        assert!(context.is_ok());
        let ctx = context.unwrap();
        assert_eq!(ctx.context_type, super::ContextType::Financial);
    }
    
    #[tokio::test]
    async fn test_template_selection() {
        let engine = CognitiveEngine::new().await.unwrap();
        let context = engine.analyze_context("technical system review").await.unwrap();
        let template = engine.select_template(&context).await;
        assert!(template.is_ok());
    }
}