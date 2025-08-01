//! Template Management System
//! 
//! Advanced template system with metadata, versioning, and intelligent processing.

use crate::error::{FactError, Result};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use chrono::{DateTime, Utc};

/// Template structure with metadata
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Template {
    /// Unique template identifier
    pub id: String,
    /// Human-readable template name
    pub name: String,
    /// Template type classification
    pub template_type: TemplateType,
    /// Template content (Handlebars format)
    pub content: String,
    /// Template metadata
    pub metadata: TemplateMetadata,
}

/// Template type classification
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum TemplateType {
    /// Financial analysis templates
    Financial,
    /// Technical documentation templates
    Technical,
    /// Data analysis templates
    Analysis,
    /// Report generation templates
    Report,
    /// Creative content templates
    Creative,
    /// Generic/utility templates
    Generic,
    /// Custom user-defined templates
    Custom,
}

/// Template metadata
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TemplateMetadata {
    /// Template version
    pub version: String,
    /// Creation timestamp
    pub created_at: DateTime<Utc>,
    /// Last modification timestamp
    pub updated_at: DateTime<Utc>,
    /// Template author
    pub author: String,
    /// Template description
    pub description: String,
    /// Supported context types
    pub supported_contexts: Vec<String>,
    /// Performance metrics
    pub performance: TemplatePerformance,
    /// Usage statistics
    pub usage_stats: UsageStats,
}

/// Template performance metrics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TemplatePerformance {
    /// Average processing time in milliseconds
    pub avg_processing_time_ms: f64,
    /// Success rate (0.0 to 1.0)
    pub success_rate: f64,
    /// Cache hit rate (0.0 to 1.0)
    pub cache_hit_rate: f64,
    /// Memory usage in bytes
    pub memory_usage_bytes: usize,
}

/// Template usage statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UsageStats {
    /// Total number of times used
    pub total_uses: u64,
    /// Number of successful executions
    pub successful_uses: u64,
    /// Last used timestamp
    pub last_used: Option<DateTime<Utc>>,
    /// Average user rating (1.0 to 5.0)
    pub avg_rating: f32,
}

impl Default for TemplateMetadata {
    fn default() -> Self {
        let now = Utc::now();
        Self {
            version: "1.0.0".to_string(),
            created_at: now,
            updated_at: now,
            author: "FACT Core".to_string(),
            description: "Default template".to_string(),
            supported_contexts: vec!["all".to_string()],
            performance: TemplatePerformance::default(),
            usage_stats: UsageStats::default(),
        }
    }
}

impl Default for TemplatePerformance {
    fn default() -> Self {
        Self {
            avg_processing_time_ms: 0.0,
            success_rate: 1.0,
            cache_hit_rate: 0.0,
            memory_usage_bytes: 0,
        }
    }
}

impl Default for UsageStats {
    fn default() -> Self {
        Self {
            total_uses: 0,
            successful_uses: 0,
            last_used: None,
            avg_rating: 5.0,
        }
    }
}

impl Template {
    /// Create a new template
    pub fn new(
        id: String,
        name: String,
        template_type: TemplateType,
        content: String,
    ) -> Self {
        Self {
            id,
            name,
            template_type,
            content,
            metadata: TemplateMetadata::default(),
        }
    }
    
    /// Create a template with custom metadata
    pub fn with_metadata(
        id: String,
        name: String,
        template_type: TemplateType,
        content: String,
        metadata: TemplateMetadata,
    ) -> Self {
        Self {
            id,
            name,
            template_type,
            content,
            metadata,
        }
    }
    
    /// Validate template content
    pub fn validate(&self) -> Result<()> {
        if self.id.is_empty() {
            return Err(FactError::InvalidTemplate("Template ID cannot be empty".to_string()));
        }
        
        if self.name.is_empty() {
            return Err(FactError::InvalidTemplate("Template name cannot be empty".to_string()));
        }
        
        if self.content.is_empty() {
            return Err(FactError::InvalidTemplate("Template content cannot be empty".to_string()));
        }
        
        // Validate Handlebars syntax
        let handlebars = handlebars::Handlebars::new();
        handlebars.render_template(&self.content, &serde_json::json!({}))
            .map_err(|e| FactError::InvalidTemplate(format!("Invalid Handlebars syntax: {}", e)))?;
        
        Ok(())
    }
    
    /// Update template usage statistics
    pub fn record_usage(&mut self, success: bool, processing_time_ms: f64) {
        self.metadata.usage_stats.total_uses += 1;
        if success {
            self.metadata.usage_stats.successful_uses += 1;
        }
        self.metadata.usage_stats.last_used = Some(Utc::now());
        
        // Update performance metrics (running average)
        let total = self.metadata.usage_stats.total_uses as f64;
        let current_avg = self.metadata.performance.avg_processing_time_ms;
        self.metadata.performance.avg_processing_time_ms = 
            (current_avg * (total - 1.0) + processing_time_ms) / total;
        
        self.metadata.performance.success_rate = 
            self.metadata.usage_stats.successful_uses as f64 / total;
        
        self.metadata.updated_at = Utc::now();
    }
    
    /// Get template complexity score (0.0 to 1.0)
    pub fn complexity_score(&self) -> f32 {
        let content_len = self.content.len() as f32;
        let helper_count = self.content.matches("{{").count() as f32;
        let conditional_count = self.content.matches("{{#if").count() as f32;
        let loop_count = self.content.matches("{{#each").count() as f32;
        
        // Normalize and combine factors
        let length_factor = (content_len / 1000.0).min(1.0);
        let helper_factor = (helper_count / 20.0).min(1.0);
        let logic_factor = ((conditional_count + loop_count * 2.0) / 10.0).min(1.0);
        
        (length_factor + helper_factor + logic_factor) / 3.0
    }
    
    /// Check if template supports a specific context type
    pub fn supports_context(&self, context_type: &str) -> bool {
        self.metadata.supported_contexts.contains(&"all".to_string()) ||
        self.metadata.supported_contexts.contains(&context_type.to_string())
    }
}

/// Template registry for managing multiple templates
#[derive(Debug)]
pub struct TemplateRegistry {
    templates: HashMap<String, Template>,
}

impl TemplateRegistry {
    /// Create a new template registry
    pub fn new() -> Self {
        Self {
            templates: HashMap::new(),
        }
    }
    
    /// Register a new template
    pub fn register(&mut self, template: Template) -> Result<()> {
        template.validate()?;
        self.templates.insert(template.id.clone(), template);
        Ok(())
    }
    
    /// Get a template by ID
    pub fn get(&self, id: &str) -> Option<&Template> {
        self.templates.get(id)
    }
    
    /// Get a mutable reference to a template
    pub fn get_mut(&mut self, id: &str) -> Option<&mut Template> {
        self.templates.get_mut(id)
    }
    
    /// Remove a template
    pub fn remove(&mut self, id: &str) -> Option<Template> {
        self.templates.remove(id)
    }
    
    /// List all template IDs
    pub fn list_ids(&self) -> Vec<String> {
        self.templates.keys().cloned().collect()
    }
    
    /// Find templates by type
    pub fn find_by_type(&self, template_type: &TemplateType) -> Vec<&Template> {
        self.templates
            .values()
            .filter(|t| &t.template_type == template_type)
            .collect()
    }
    
    /// Find templates supporting a context type
    pub fn find_by_context(&self, context_type: &str) -> Vec<&Template> {
        self.templates
            .values()
            .filter(|t| t.supports_context(context_type))
            .collect()
    }
    
    /// Get registry statistics
    pub fn stats(&self) -> RegistryStats {
        let total_templates = self.templates.len();
        let total_uses: u64 = self.templates.values()
            .map(|t| t.metadata.usage_stats.total_uses)
            .sum();
        let avg_success_rate: f32 = self.templates.values()
            .map(|t| t.metadata.performance.success_rate as f32)
            .sum::<f32>() / total_templates.max(1) as f32;
        let avg_complexity: f32 = self.templates.values()
            .map(|t| t.complexity_score())
            .sum::<f32>() / total_templates.max(1) as f32;
        
        RegistryStats {
            total_templates,
            total_uses,
            avg_success_rate,
            avg_complexity,
        }
    }
}

impl Default for TemplateRegistry {
    fn default() -> Self {
        Self::new()
    }
}

/// Template registry statistics
#[derive(Debug, Clone, Serialize)]
pub struct RegistryStats {
    pub total_templates: usize,
    pub total_uses: u64,
    pub avg_success_rate: f32,
    pub avg_complexity: f32,
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_template_creation() {
        let template = Template::new(
            "test".to_string(),
            "Test Template".to_string(),
            TemplateType::Generic,
            "Hello {{name}}!".to_string(),
        );
        
        assert_eq!(template.id, "test");
        assert_eq!(template.name, "Test Template");
        assert_eq!(template.template_type, TemplateType::Generic);
    }
    
    #[test]
    fn test_template_validation() {
        let valid_template = Template::new(
            "valid".to_string(),
            "Valid Template".to_string(),
            TemplateType::Generic,
            "Hello {{name}}!".to_string(),
        );
        assert!(valid_template.validate().is_ok());
        
        let empty_id_template = Template::new(
            "".to_string(),
            "Invalid Template".to_string(),
            TemplateType::Generic,
            "Hello!".to_string(),
        );
        assert!(empty_id_template.validate().is_err());
    }
    
    #[test]
    fn test_template_registry() {
        let mut registry = TemplateRegistry::new();
        
        let template = Template::new(
            "test".to_string(),
            "Test Template".to_string(),
            TemplateType::Generic,
            "Hello {{name}}!".to_string(),
        );
        
        assert!(registry.register(template).is_ok());
        assert!(registry.get("test").is_some());
        assert_eq!(registry.list_ids(), vec!["test"]);
    }
    
    #[test]
    fn test_complexity_score() {
        let simple_template = Template::new(
            "simple".to_string(),
            "Simple".to_string(),
            TemplateType::Generic,
            "Hello World".to_string(),
        );
        assert!(simple_template.complexity_score() < 0.2);
        
        let complex_template = Template::new(
            "complex".to_string(),
            "Complex".to_string(),
            TemplateType::Generic,
            "{{#each items}}{{#if show}}{{name}}: {{value}}{{/if}}{{/each}}".to_string(),
        );
        assert!(complex_template.complexity_score() > 0.3);
    }
}