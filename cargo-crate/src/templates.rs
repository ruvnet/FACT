//! Cognitive template system for FACT

use crate::engine::{Operation, ProcessingStep, Transform, Analysis, Filter, Aggregation};
use ahash::AHashMap;
use serde::{Deserialize, Serialize};
use parking_lot::RwLock;
use std::sync::Arc;

/// A cognitive template for processing
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Template {
    /// Unique template identifier
    pub id: String,
    
    /// Human-readable name
    pub name: String,
    
    /// Template description
    pub description: String,
    
    /// Processing steps
    pub steps: Vec<ProcessingStep>,
    
    /// Template metadata
    pub metadata: TemplateMetadata,
}

/// Template metadata
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TemplateMetadata {
    /// Template version
    pub version: String,
    
    /// Template author
    pub author: String,
    
    /// Creation date
    pub created_at: String,
    
    /// Last modified date
    pub updated_at: String,
    
    /// Tags for categorization
    pub tags: Vec<String>,
    
    /// Performance characteristics
    pub performance: PerformanceProfile,
}

/// Performance profile for a template
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PerformanceProfile {
    /// Average execution time in milliseconds
    pub avg_execution_time_ms: f64,
    
    /// Memory usage in bytes
    pub memory_usage_bytes: usize,
    
    /// Complexity rating (1-10)
    pub complexity: u8,
}

/// Registry for managing templates
pub struct TemplateRegistry {
    templates: Arc<RwLock<AHashMap<String, Template>>>,
}

impl TemplateRegistry {
    /// Create a new template registry
    pub fn new() -> Self {
        let registry = Self {
            templates: Arc::new(RwLock::new(AHashMap::new())),
        };
        
        // Load default templates
        registry.load_default_templates();
        
        registry
    }
    
    /// Register a template
    pub fn register(&self, template: Template) {
        self.templates.write().insert(template.id.clone(), template);
    }
    
    /// Get a template by ID
    pub fn get(&self, id: &str) -> Option<Template> {
        self.templates.read().get(id).cloned()
    }
    
    /// List all template IDs
    pub fn list(&self) -> Vec<String> {
        self.templates.read().keys().cloned().collect()
    }
    
    /// Remove a template
    pub fn remove(&self, id: &str) -> Option<Template> {
        self.templates.write().remove(id)
    }
    
    /// Load default templates
    fn load_default_templates(&self) {
        // Analysis template
        self.register(Template {
            id: "analysis-basic".to_string(),
            name: "Basic Analysis".to_string(),
            description: "Performs basic statistical and pattern analysis".to_string(),
            steps: vec![
                ProcessingStep {
                    name: "normalize".to_string(),
                    operation: Operation::Transform(Transform::Normalize),
                },
                ProcessingStep {
                    name: "analyze".to_string(),
                    operation: Operation::Analyze(Analysis::Statistical),
                },
                ProcessingStep {
                    name: "expand".to_string(),
                    operation: Operation::Transform(Transform::Expand),
                },
            ],
            metadata: TemplateMetadata {
                version: "1.0.0".to_string(),
                author: "FACT Team".to_string(),
                created_at: chrono::Utc::now().to_rfc3339(),
                updated_at: chrono::Utc::now().to_rfc3339(),
                tags: vec!["analysis".to_string(), "statistics".to_string()],
                performance: PerformanceProfile {
                    avg_execution_time_ms: 50.0,
                    memory_usage_bytes: 1024 * 1024, // 1MB
                    complexity: 3,
                },
            },
        });
        
        // Pattern detection template
        self.register(Template {
            id: "pattern-detection".to_string(),
            name: "Pattern Detection".to_string(),
            description: "Detects patterns in structured data".to_string(),
            steps: vec![
                ProcessingStep {
                    name: "normalize".to_string(),
                    operation: Operation::Transform(Transform::Normalize),
                },
                ProcessingStep {
                    name: "pattern-analysis".to_string(),
                    operation: Operation::Analyze(Analysis::Pattern),
                },
                ProcessingStep {
                    name: "semantic-enrichment".to_string(),
                    operation: Operation::Analyze(Analysis::Semantic),
                },
            ],
            metadata: TemplateMetadata {
                version: "1.0.0".to_string(),
                author: "FACT Team".to_string(),
                created_at: chrono::Utc::now().to_rfc3339(),
                updated_at: chrono::Utc::now().to_rfc3339(),
                tags: vec!["pattern".to_string(), "detection".to_string(), "ai".to_string()],
                performance: PerformanceProfile {
                    avg_execution_time_ms: 75.0,
                    memory_usage_bytes: 2 * 1024 * 1024, // 2MB
                    complexity: 5,
                },
            },
        });
        
        // Data aggregation template
        self.register(Template {
            id: "data-aggregation".to_string(),
            name: "Data Aggregation".to_string(),
            description: "Aggregates numerical data with various operations".to_string(),
            steps: vec![
                ProcessingStep {
                    name: "filter-numbers".to_string(),
                    operation: Operation::Filter(Filter::Range { min: 0.0, max: 1000000.0 }),
                },
                ProcessingStep {
                    name: "sum".to_string(),
                    operation: Operation::Aggregate(Aggregation::Sum),
                },
                ProcessingStep {
                    name: "average".to_string(),
                    operation: Operation::Aggregate(Aggregation::Average),
                },
                ProcessingStep {
                    name: "count".to_string(),
                    operation: Operation::Aggregate(Aggregation::Count),
                },
            ],
            metadata: TemplateMetadata {
                version: "1.0.0".to_string(),
                author: "FACT Team".to_string(),
                created_at: chrono::Utc::now().to_rfc3339(),
                updated_at: chrono::Utc::now().to_rfc3339(),
                tags: vec!["aggregation".to_string(), "numerical".to_string(), "statistics".to_string()],
                performance: PerformanceProfile {
                    avg_execution_time_ms: 25.0,
                    memory_usage_bytes: 512 * 1024, // 512KB
                    complexity: 2,
                },
            },
        });
        
        // Quick transform template
        self.register(Template {
            id: "quick-transform".to_string(),
            name: "Quick Transform".to_string(),
            description: "Fast data transformation for caching".to_string(),
            steps: vec![
                ProcessingStep {
                    name: "compress".to_string(),
                    operation: Operation::Transform(Transform::Compress),
                },
                ProcessingStep {
                    name: "normalize".to_string(),
                    operation: Operation::Transform(Transform::Normalize),
                },
            ],
            metadata: TemplateMetadata {
                version: "1.0.0".to_string(),
                author: "FACT Team".to_string(),
                created_at: chrono::Utc::now().to_rfc3339(),
                updated_at: chrono::Utc::now().to_rfc3339(),
                tags: vec!["transform".to_string(), "fast".to_string(), "cache".to_string()],
                performance: PerformanceProfile {
                    avg_execution_time_ms: 10.0,
                    memory_usage_bytes: 256 * 1024, // 256KB
                    complexity: 1,
                },
            },
        });
    }
    
    /// Search templates by tags
    pub fn search_by_tags(&self, tags: &[String]) -> Vec<Template> {
        self.templates
            .read()
            .values()
            .filter(|template| {
                tags.iter().any(|tag| template.metadata.tags.contains(tag))
            })
            .cloned()
            .collect()
    }
    
    /// Get templates sorted by performance
    pub fn get_by_performance(&self, max_complexity: u8) -> Vec<Template> {
        let mut templates: Vec<_> = self.templates
            .read()
            .values()
            .filter(|t| t.metadata.performance.complexity <= max_complexity)
            .cloned()
            .collect();
            
        templates.sort_by(|a, b| {
            a.metadata.performance.avg_execution_time_ms
                .partial_cmp(&b.metadata.performance.avg_execution_time_ms)
                .unwrap()
        });
        
        templates
    }
}

impl Default for TemplateRegistry {
    fn default() -> Self {
        Self::new()
    }
}

/// Builder for creating templates
pub struct TemplateBuilder {
    id: String,
    name: String,
    description: String,
    steps: Vec<ProcessingStep>,
    tags: Vec<String>,
}

impl TemplateBuilder {
    /// Create a new template builder
    pub fn new(id: impl Into<String>) -> Self {
        Self {
            id: id.into(),
            name: String::new(),
            description: String::new(),
            steps: Vec::new(),
            tags: Vec::new(),
        }
    }
    
    /// Set the template name
    pub fn name(mut self, name: impl Into<String>) -> Self {
        self.name = name.into();
        self
    }
    
    /// Set the template description
    pub fn description(mut self, description: impl Into<String>) -> Self {
        self.description = description.into();
        self
    }
    
    /// Add a processing step
    pub fn add_step(mut self, step: ProcessingStep) -> Self {
        self.steps.push(step);
        self
    }
    
    /// Add a tag
    pub fn add_tag(mut self, tag: impl Into<String>) -> Self {
        self.tags.push(tag.into());
        self
    }
    
    /// Build the template
    pub fn build(self) -> Template {
        Template {
            id: self.id,
            name: self.name,
            description: self.description,
            steps: self.steps,
            metadata: TemplateMetadata {
                version: "1.0.0".to_string(),
                author: "Custom".to_string(),
                created_at: chrono::Utc::now().to_rfc3339(),
                updated_at: chrono::Utc::now().to_rfc3339(),
                tags: self.tags,
                performance: PerformanceProfile {
                    avg_execution_time_ms: 0.0,
                    memory_usage_bytes: 0,
                    complexity: 5,
                },
            },
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_template_registry() {
        let registry = TemplateRegistry::new();
        
        // Check default templates are loaded
        assert!(registry.get("analysis-basic").is_some());
        assert!(registry.get("pattern-detection").is_some());
        assert!(registry.get("data-aggregation").is_some());
        assert!(registry.get("quick-transform").is_some());
        
        // Test listing
        let templates = registry.list();
        assert!(templates.len() >= 4);
    }
    
    #[test]
    fn test_template_builder() {
        let template = TemplateBuilder::new("custom-template")
            .name("Custom Template")
            .description("A custom template for testing")
            .add_tag("custom")
            .add_tag("test")
            .add_step(ProcessingStep {
                name: "normalize".to_string(),
                operation: Operation::Transform(Transform::Normalize),
            })
            .build();
        
        assert_eq!(template.id, "custom-template");
        assert_eq!(template.name, "Custom Template");
        assert_eq!(template.steps.len(), 1);
        assert_eq!(template.metadata.tags.len(), 2);
    }
    
    #[test]
    fn test_search_by_tags() {
        let registry = TemplateRegistry::new();
        
        let analysis_templates = registry.search_by_tags(&[String::from("analysis")]);
        assert!(!analysis_templates.is_empty());
        
        let pattern_templates = registry.search_by_tags(&[String::from("pattern")]);
        assert!(!pattern_templates.is_empty());
    }
}