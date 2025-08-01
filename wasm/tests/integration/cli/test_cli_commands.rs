//! CLI Integration Tests
//! 
//! Comprehensive tests for FACT CLI command execution, output validation,
//! and error handling scenarios.

use std::process::{Command, Output};
use std::path::PathBuf;
use std::env;
use std::fs;
use tempfile::TempDir;
use serde_json::Value;

/// Test utilities for CLI integration testing
pub struct CliTestRunner {
    binary_path: PathBuf,
    temp_dir: TempDir,
}

impl CliTestRunner {
    pub fn new() -> Result<Self, Box<dyn std::error::Error>> {
        let binary_path = env::current_exe()?
            .parent()
            .unwrap()
            .parent()
            .unwrap()
            .join("target")
            .join("debug")
            .join("fact");
            
        let temp_dir = TempDir::new()?;
        
        Ok(Self {
            binary_path,
            temp_dir,
        })
    }
    
    pub fn run_command(&self, args: &[&str]) -> Result<Output, std::io::Error> {
        Command::new(&self.binary_path)
            .args(args)
            .current_dir(self.temp_dir.path())
            .output()
    }
    
    pub fn run_command_with_input(&self, args: &[&str], input: &str) -> Result<Output, std::io::Error> {
        use std::process::Stdio;
        use std::io::Write;
        
        let mut child = Command::new(&self.binary_path)
            .args(args)
            .current_dir(self.temp_dir.path())
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()?;
            
        if let Some(mut stdin) = child.stdin.take() {
            stdin.write_all(input.as_bytes())?;
        }
        
        let output = child.wait_with_output()?;
        Ok(output)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_cli_basic_query() {
        let runner = CliTestRunner::new().expect("Failed to create test runner");
        
        let output = runner.run_command(&["query", "SELECT * FROM test"])
            .expect("Failed to execute query command");
        
        assert!(output.status.success(), "Query command should succeed");
        
        let stdout = String::from_utf8(output.stdout).expect("Invalid UTF-8 output");
        assert!(!stdout.is_empty(), "Query should produce output");
        
        // Validate JSON output format
        let result: Result<Value, _> = serde_json::from_str(&stdout);
        assert!(result.is_ok(), "Output should be valid JSON");
        
        let json = result.unwrap();
        assert!(json.get("success").is_some(), "Response should have success field");
        assert!(json.get("execution_time_ms").is_some(), "Response should have timing info");
    }
    
    #[test]
    fn test_cli_cache_operations() {
        let runner = CliTestRunner::new().expect("Failed to create test runner");
        
        // Test cache stats
        let output = runner.run_command(&["cache", "stats"])
            .expect("Failed to execute cache stats command");
        
        assert!(output.status.success(), "Cache stats command should succeed");
        
        let stdout = String::from_utf8(output.stdout).expect("Invalid UTF-8 output");
        let result: Value = serde_json::from_str(&stdout)
            .expect("Cache stats output should be valid JSON");
        
        assert!(result.get("size").is_some(), "Cache stats should include size");
        assert!(result.get("entries").is_some(), "Cache stats should include entry count");
        assert!(result.get("capacity").is_some(), "Cache stats should include capacity");
        
        // Test cache warmup
        let output = runner.run_command(&["cache", "warmup"])
            .expect("Failed to execute cache warmup command");
        
        assert!(output.status.success(), "Cache warmup should succeed");
        
        // Test cache clear
        let output = runner.run_command(&["cache", "clear"])
            .expect("Failed to execute cache clear command");
        
        assert!(output.status.success(), "Cache clear should succeed");
        
        let stdout = String::from_utf8(output.stdout).expect("Invalid UTF-8 output");
        assert!(stdout.contains("cleared"), "Clear command should confirm action");
    }
    
    #[test]
    fn test_cli_stats_command() {
        let runner = CliTestRunner::new().expect("Failed to create test runner");
        
        // Test basic stats
        let output = runner.run_command(&["stats"])
            .expect("Failed to execute stats command");
        
        assert!(output.status.success(), "Stats command should succeed");
        
        let stdout = String::from_utf8(output.stdout).expect("Invalid UTF-8 output");
        assert!(stdout.contains("Cache Statistics"), "Stats should include cache info");
        
        // Test detailed stats
        let output = runner.run_command(&["stats", "--detailed"])
            .expect("Failed to execute detailed stats command");
        
        assert!(output.status.success(), "Detailed stats command should succeed");
        
        let stdout = String::from_utf8(output.stdout).expect("Invalid UTF-8 output");
        let result: Value = serde_json::from_str(&stdout)
            .expect("Detailed stats should be valid JSON");
        
        assert!(result.is_object(), "Detailed stats should be JSON object");
    }
    
    #[test]
    fn test_cli_benchmark_command() {
        let runner = CliTestRunner::new().expect("Failed to create test runner");
        
        // Test benchmark with default iterations
        let output = runner.run_command(&["benchmark"])
            .expect("Failed to execute benchmark command");
        
        assert!(output.status.success(), "Benchmark command should succeed");
        
        let stdout = String::from_utf8(output.stdout).expect("Invalid UTF-8 output");
        assert!(stdout.contains("Benchmark Results"), "Benchmark should show results");
        assert!(stdout.contains("ops/sec"), "Benchmark should show performance metrics");
        
        // Test benchmark with custom iterations
        let output = runner.run_command(&["benchmark", "--iterations", "100"])
            .expect("Failed to execute benchmark command with custom iterations");
        
        assert!(output.status.success(), "Custom benchmark command should succeed");
        
        let stdout = String::from_utf8(output.stdout).expect("Invalid UTF-8 output");
        assert!(stdout.contains("100 iterations"), "Benchmark should use custom iterations");
    }
    
    #[test]
    fn test_cli_output_formats() {
        let runner = CliTestRunner::new().expect("Failed to create test runner");
        
        // Test JSON format (default)
        let output = runner.run_command(&["query", "SELECT 1", "--format", "json"])
            .expect("Failed to execute query with JSON format");
        
        assert!(output.status.success(), "JSON format query should succeed");
        
        let stdout = String::from_utf8(output.stdout).expect("Invalid UTF-8 output");
        let _: Value = serde_json::from_str(&stdout)
            .expect("JSON format output should be valid JSON");
        
        // Test text format
        let output = runner.run_command(&["query", "SELECT 1", "--format", "text"])
            .expect("Failed to execute query with text format");
        
        assert!(output.status.success(), "Text format query should succeed");
        
        let stdout = String::from_utf8(output.stdout).expect("Invalid UTF-8 output");
        assert!(stdout.contains("Query:"), "Text format should include query");
        assert!(stdout.contains("Result:"), "Text format should include result");
        
        // Test YAML format
        let output = runner.run_command(&["query", "SELECT 1", "--format", "yaml"])
            .expect("Failed to execute query with YAML format");
        
        assert!(output.status.success(), "YAML format query should succeed");
        
        let stdout = String::from_utf8(output.stdout).expect("Invalid UTF-8 output");
        assert!(stdout.contains("query:"), "YAML format should include query field");
        assert!(stdout.contains("result:"), "YAML format should include result field");
    }
    
    #[test]
    fn test_cli_cache_toggle() {
        let runner = CliTestRunner::new().expect("Failed to create test runner");
        
        // Test with cache enabled (default)
        let output = runner.run_command(&["query", "SELECT * FROM cache_test", "--cache"])
            .expect("Failed to execute cached query");
        
        assert!(output.status.success(), "Cached query should succeed");
        
        // Test with cache disabled
        let output = runner.run_command(&["query", "SELECT * FROM cache_test", "--no-cache"])
            .expect("Failed to execute non-cached query");
        
        assert!(output.status.success(), "Non-cached query should succeed");
        
        let stdout = String::from_utf8(output.stdout).expect("Invalid UTF-8 output");
        let result: Value = serde_json::from_str(&stdout)
            .expect("Output should be valid JSON");
        
        // Cache should be disabled, so cache_hit should be false
        if let Some(cache_hit) = result.get("cache_hit") {
            assert_eq!(cache_hit, &Value::Bool(false), "Cache should be disabled");
        }
    }
    
    #[test]
    fn test_cli_error_handling() {
        let runner = CliTestRunner::new().expect("Failed to create test runner");
        
        // Test invalid command
        let output = runner.run_command(&["invalid-command"])
            .expect("Command execution should complete");
        
        assert!(!output.status.success(), "Invalid command should fail");
        
        let stderr = String::from_utf8(output.stderr).expect("Invalid UTF-8 error output");
        assert!(!stderr.is_empty(), "Error should produce stderr output");
        
        // Test invalid format
        let output = runner.run_command(&["query", "SELECT 1", "--format", "invalid"])
            .expect("Command execution should complete");
        
        assert!(!output.status.success(), "Invalid format should fail");
        
        // Test missing required argument
        let output = runner.run_command(&["query"])
            .expect("Command execution should complete");
        
        assert!(!output.status.success(), "Missing query argument should fail");
    }
    
    #[test]
    fn test_cli_help_output() {
        let runner = CliTestRunner::new().expect("Failed to create test runner");
        
        // Test main help
        let output = runner.run_command(&["--help"])
            .expect("Failed to execute help command");
        
        assert!(output.status.success(), "Help command should succeed");
        
        let stdout = String::from_utf8(output.stdout).expect("Invalid UTF-8 output");
        assert!(stdout.contains("Fast Autonomous Cognitive Templates"), "Help should show description");
        assert!(stdout.contains("query"), "Help should list query command");
        assert!(stdout.contains("cache"), "Help should list cache command");
        assert!(stdout.contains("stats"), "Help should list stats command");
        assert!(stdout.contains("benchmark"), "Help should list benchmark command");
        
        // Test subcommand help
        let output = runner.run_command(&["query", "--help"])
            .expect("Failed to execute query help command");
        
        assert!(output.status.success(), "Query help should succeed");
        
        let stdout = String::from_utf8(output.stdout).expect("Invalid UTF-8 output");
        assert!(stdout.contains("QUERY"), "Query help should show usage");
        assert!(stdout.contains("cache"), "Query help should show cache option");
        assert!(stdout.contains("format"), "Query help should show format option");
    }
    
    #[test]
    fn test_cli_version_output() {
        let runner = CliTestRunner::new().expect("Failed to create test runner");
        
        let output = runner.run_command(&["--version"])
            .expect("Failed to execute version command");
        
        assert!(output.status.success(), "Version command should succeed");
        
        let stdout = String::from_utf8(output.stdout).expect("Invalid UTF-8 output");
        assert!(stdout.contains("1.0.0"), "Version should show version number");
    }
    
    #[test]
    fn test_cli_concurrent_operations() {
        use std::thread;
        use std::sync::Arc;
        
        let runner = Arc::new(CliTestRunner::new().expect("Failed to create test runner"));
        let mut handles = vec![];
        
        // Run multiple CLI commands concurrently
        for i in 0..5 {
            let runner_clone = Arc::clone(&runner);
            let handle = thread::spawn(move || {
                let query = format!("SELECT {} as test_value", i);
                let output = runner_clone.run_command(&["query", &query])
                    .expect("Concurrent command should execute");
                
                assert!(output.status.success(), "Concurrent command should succeed");
                
                let stdout = String::from_utf8(output.stdout).expect("Invalid UTF-8 output");
                let result: Value = serde_json::from_str(&stdout)
                    .expect("Concurrent output should be valid JSON");
                
                assert!(result.get("success").is_some(), "Concurrent query should succeed");
            });
            
            handles.push(handle);
        }
        
        // Wait for all threads to complete
        for handle in handles {
            handle.join().expect("Thread should complete successfully");
        }
    }
    
    #[test]
    fn test_cli_environment_variables() {
        let runner = CliTestRunner::new().expect("Failed to create test runner");
        
        // Set environment variable for configuration
        env::set_var("FACT_DEBUG", "1");
        
        let output = runner.run_command(&["query", "SELECT 1"])
            .expect("Failed to execute query with debug env");
        
        assert!(output.status.success(), "Debug query should succeed");
        
        // Clean up environment
        env::remove_var("FACT_DEBUG");
    }
    
    #[test]
    fn test_cli_large_query_handling() {
        let runner = CliTestRunner::new().expect("Failed to create test runner");
        
        // Create a large query string
        let large_query = "SELECT ".to_string() + &"'test_data', ".repeat(1000) + "1";
        
        let output = runner.run_command(&["query", &large_query])
            .expect("Failed to execute large query");
        
        assert!(output.status.success(), "Large query should succeed");
        
        let stdout = String::from_utf8(output.stdout).expect("Invalid UTF-8 output");
        let result: Value = serde_json::from_str(&stdout)
            .expect("Large query output should be valid JSON");
        
        assert!(result.get("success").is_some(), "Large query should complete successfully");
    }
}

#[cfg(test)]
mod performance_tests {
    use super::*;
    use std::time::Instant;
    
    #[test]
    fn test_cli_response_time() {
        let runner = CliTestRunner::new().expect("Failed to create test runner");
        
        let start = Instant::now();
        let output = runner.run_command(&["query", "SELECT 1"])
            .expect("Failed to execute timed query");
        let duration = start.elapsed();
        
        assert!(output.status.success(), "Timed query should succeed");
        assert!(duration.as_millis() < 5000, "Query should complete within 5 seconds");
    }
    
    #[test]
    fn test_cli_memory_usage() {
        let runner = CliTestRunner::new().expect("Failed to create test runner");
        
        // Run multiple queries to test memory usage
        for i in 0..100 {
            let query = format!("SELECT {} as iteration", i);
            let output = runner.run_command(&["query", &query])
                .expect("Memory test query should execute");
            
            assert!(output.status.success(), "Memory test query should succeed");
        }
        
        // Verify cache stats show reasonable memory usage
        let output = runner.run_command(&["cache", "stats"])
            .expect("Failed to get cache stats");
        
        assert!(output.status.success(), "Cache stats should succeed");
        
        let stdout = String::from_utf8(output.stdout).expect("Invalid UTF-8 output");
        let result: Value = serde_json::from_str(&stdout)
            .expect("Cache stats should be valid JSON");
        
        // Memory usage should be reasonable (less than 100MB for test)
        if let Some(size) = result.get("size") {
            if let Some(size_val) = size.as_u64() {
                assert!(size_val < 100_000_000, "Memory usage should be reasonable");
            }
        }
    }
}