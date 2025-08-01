//! Query processing implementation

use ahash::AHashMap;

/// Query processor for FACT
#[derive(Debug, Clone)]
pub struct QueryProcessor {
    /// Processing strategies
    strategies: AHashMap<String, ProcessingStrategy>,
}

impl QueryProcessor {
    /// Create a new query processor
    pub fn new() -> Self {
        let mut processor = Self {
            strategies: AHashMap::new(),
        };
        
        // Register default strategies
        processor.register_default_strategies();
        
        processor
    }
    
    /// Process a query
    pub fn process(&self, query: &str) -> serde_json::Value {
        // Analyze query to determine strategy
        let strategy_name = self.analyze_query(query);
        
        if let Some(strategy) = self.strategies.get(&strategy_name) {
            self.apply_strategy(strategy, query)
        } else {
            // Default processing
            serde_json::json!({
                "query": query,
                "result": "Processed with default strategy",
                "metadata": {
                    "strategy": "default",
                    "confidence": 0.5,
                }
            })
        }
    }
    
    /// Register a custom processing strategy
    pub fn register_strategy(&mut self, name: String, strategy: ProcessingStrategy) {
        self.strategies.insert(name, strategy);
    }
    
    fn register_default_strategies(&mut self) {
        // Question answering strategy
        self.strategies.insert(
            "question".to_string(),
            ProcessingStrategy {
                name: "question".to_string(),
                pattern: r"^(what|who|where|when|why|how)".to_string(),
                handler: StrategyHandler::Question,
            },
        );
        
        // Command strategy
        self.strategies.insert(
            "command".to_string(),
            ProcessingStrategy {
                name: "command".to_string(),
                pattern: r"^(do|create|make|build|generate)".to_string(),
                handler: StrategyHandler::Command,
            },
        );
        
        // Analysis strategy
        self.strategies.insert(
            "analysis".to_string(),
            ProcessingStrategy {
                name: "analysis".to_string(),
                pattern: r"(analyze|examine|investigate|study)".to_string(),
                handler: StrategyHandler::Analysis,
            },
        );
    }
    
    fn analyze_query(&self, query: &str) -> String {
        let lower_query = query.to_lowercase();
        
        for (name, strategy) in &self.strategies {
            if regex_lite::Regex::new(&strategy.pattern)
                .ok()
                .map_or(false, |re| re.is_match(&lower_query))
            {
                return name.clone();
            }
        }
        
        "default".to_string()
    }
    
    fn apply_strategy(&self, strategy: &ProcessingStrategy, query: &str) -> serde_json::Value {
        match &strategy.handler {
            StrategyHandler::Question => {
                serde_json::json!({
                    "query": query,
                    "type": "question",
                    "answer": "This is a question that requires an answer.",
                    "confidence": 0.85,
                    "sources": ["knowledge_base", "context"],
                })
            }
            StrategyHandler::Command => {
                serde_json::json!({
                    "query": query,
                    "type": "command",
                    "action": "execute",
                    "steps": [
                        "Parse command",
                        "Validate parameters",
                        "Execute action",
                        "Return results",
                    ],
                    "status": "ready",
                })
            }
            StrategyHandler::Analysis => {
                serde_json::json!({
                    "query": query,
                    "type": "analysis",
                    "findings": {
                        "summary": "Analysis request detected",
                        "key_points": [
                            "Data gathering required",
                            "Pattern analysis needed",
                            "Insights generation",
                        ],
                    },
                    "recommendations": [
                        "Collect relevant data",
                        "Apply analytical framework",
                        "Generate insights report",
                    ],
                })
            }
            StrategyHandler::Custom(handler) => {
                // Apply custom handler
                handler(query)
            }
        }
    }
}

impl Default for QueryProcessor {
    fn default() -> Self {
        Self::new()
    }
}

/// Processing strategy definition
#[derive(Debug, Clone)]
pub struct ProcessingStrategy {
    /// Strategy name
    pub name: String,
    
    /// Pattern to match queries
    pub pattern: String,
    
    /// Handler for this strategy
    pub handler: StrategyHandler,
}

/// Strategy handler types
#[derive(Debug, Clone)]
pub enum StrategyHandler {
    Question,
    Command,
    Analysis,
    Custom(fn(&str) -> serde_json::Value),
}

// Simple regex implementation for pattern matching
mod regex_lite {
    pub struct Regex {
        pattern: String,
    }
    
    impl Regex {
        pub fn new(pattern: &str) -> Result<Self, ()> {
            Ok(Self {
                pattern: pattern.to_string(),
            })
        }
        
        pub fn is_match(&self, text: &str) -> bool {
            // Simplified pattern matching for specific patterns
            let cleaned_pattern = self.pattern.trim_start_matches('^').trim_end_matches('$');
            
            // Handle patterns with alternatives like (what|who|where|when|why|how)
            if cleaned_pattern.starts_with('(') && cleaned_pattern.ends_with(')') {
                let alternatives = cleaned_pattern
                    .trim_start_matches('(')
                    .trim_end_matches(')')
                    .split('|');
                
                for alt in alternatives {
                    if self.pattern.starts_with('^') {
                        if text.starts_with(alt) {
                            return true;
                        }
                    } else if text.contains(alt) {
                        return true;
                    }
                }
                false
            } else if self.pattern.starts_with('^') {
                text.starts_with(cleaned_pattern)
            } else {
                text.contains(cleaned_pattern)
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_query_processor() {
        let processor = QueryProcessor::new();
        
        // Test question processing
        let result = processor.process("What is the weather today?");
        assert_eq!(result["type"], "question");
        
        // Test command processing
        let result = processor.process("Create a new document");
        assert_eq!(result["type"], "command");
        
        // Test analysis processing
        let result = processor.process("Analyze the sales data");
        assert_eq!(result["type"], "analysis");
    }
}