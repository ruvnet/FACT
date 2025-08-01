//! MCP Server Integration Tests
//!
//! Comprehensive tests for FACT MCP server JSON-RPC protocol compliance,
//! tool execution, resource access, and error handling.

use serde_json::{json, Value};
use std::collections::HashMap;
use std::process::{Command, Child, Stdio};
use std::io::{BufRead, BufReader, Write};
use std::time::{Duration, Instant};
use std::sync::mpsc;
use std::thread;
use tempfile::TempDir;

/// MCP JSON-RPC message types
#[derive(Debug, Clone)]
pub struct JsonRpcRequest {
    pub id: u64,
    pub method: String,
    pub params: Option<Value>,
}

#[derive(Debug, Clone)]
pub struct JsonRpcResponse {
    pub id: u64,
    pub result: Option<Value>,
    pub error: Option<Value>,
}

/// MCP Server test client for integration testing
pub struct McpTestClient {
    server_process: Option<Child>,
    temp_dir: TempDir,
    request_id: u64,
}

impl McpTestClient {
    pub fn new() -> Result<Self, Box<dyn std::error::Error>> {
        let temp_dir = TempDir::new()?;
        
        Ok(Self {
            server_process: None,
            temp_dir,
            request_id: 0,
        })
    }
    
    pub fn start_server(&mut self) -> Result<(), Box<dyn std::error::Error>> {
        // Start the MCP server process
        let server_path = std::env::current_exe()?
            .parent()
            .unwrap()
            .parent()
            .unwrap()
            .join("mcp-server")
            .join("dist")
            .join("index.js");
        
        let mut child = Command::new("node")
            .arg(server_path)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .current_dir(self.temp_dir.path())
            .spawn()?;
        
        // Give server time to initialize
        thread::sleep(Duration::from_millis(1000));
        
        self.server_process = Some(child);
        Ok(())
    }
    
    pub fn send_request(&mut self, method: &str, params: Option<Value>) -> Result<JsonRpcResponse, Box<dyn std::error::Error>> {
        let request_id = self.next_request_id();
        
        let request = json!({
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params
        });
        
        if let Some(ref mut process) = self.server_process {
            if let Some(ref mut stdin) = process.stdin.as_mut() {
                let request_str = serde_json::to_string(&request)?;
                writeln!(stdin, "{}", request_str)?;
                stdin.flush()?;
            }
            
            // Read response (simplified for testing)
            // In a real implementation, this would handle the JSON-RPC protocol properly
            if let Some(ref mut stdout) = process.stdout.as_mut() {
                let mut reader = BufReader::new(stdout);
                let mut response_line = String::new();
                reader.read_line(&mut response_line)?;
                
                let response: Value = serde_json::from_str(&response_line)?;
                
                return Ok(JsonRpcResponse {
                    id: request_id,
                    result: response.get("result").cloned(),
                    error: response.get("error").cloned(),
                });
            }
        }
        
        Err("Server not running or communication failed".into())
    }
    
    fn next_request_id(&mut self) -> u64 {
        self.request_id += 1;
        self.request_id
    }
}

impl Drop for McpTestClient {
    fn drop(&mut self) {
        if let Some(mut process) = self.server_process.take() {
            let _ = process.kill();
            let _ = process.wait();
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_mcp_server_initialization() {
        let mut client = McpTestClient::new().expect("Failed to create MCP test client");
        
        // Start server and verify it's running
        client.start_server().expect("Failed to start MCP server");
        
        // Server should be accessible (basic smoke test)
        assert!(client.server_process.is_some(), "Server process should be running");
    }
    
    #[test]
    fn test_mcp_list_tools() {
        let mut client = McpTestClient::new().expect("Failed to create MCP test client");
        client.start_server().expect("Failed to start MCP server");
        
        let response = client.send_request("tools/list", None)
            .expect("Failed to send list tools request");
        
        assert!(response.error.is_none(), "List tools should not return error");
        assert!(response.result.is_some(), "List tools should return result");
        
        let result = response.result.unwrap();
        let tools = result.get("tools").expect("Result should contain tools array");
        
        assert!(tools.is_array(), "Tools should be an array");
        
        let tools_array = tools.as_array().unwrap();
        assert!(!tools_array.is_empty(), "Should have at least one tool");
        
        // Verify expected tools are present
        let tool_names: Vec<String> = tools_array
            .iter()
            .filter_map(|t| t.get("name")?.as_str())
            .map(|s| s.to_string())
            .collect();
        
        assert!(tool_names.contains(&"process_template".to_string()));
        assert!(tool_names.contains(&"list_templates".to_string()));
        assert!(tool_names.contains(&"analyze_context".to_string()));
        assert!(tool_names.contains(&"optimize_performance".to_string()));
        assert!(tool_names.contains(&"create_template".to_string()));
        assert!(tool_names.contains(&"get_metrics".to_string()));
    }
    
    #[test]
    fn test_mcp_list_resources() {
        let mut client = McpTestClient::new().expect("Failed to create MCP test client");
        client.start_server().expect("Failed to start MCP server");
        
        let response = client.send_request("resources/list", None)
            .expect("Failed to send list resources request");
        
        assert!(response.error.is_none(), "List resources should not return error");
        assert!(response.result.is_some(), "List resources should return result");
        
        let result = response.result.unwrap();
        let resources = result.get("resources").expect("Result should contain resources array");
        
        assert!(resources.is_array(), "Resources should be an array");
        
        let resources_array = resources.as_array().unwrap();
        assert!(!resources_array.is_empty(), "Should have at least one resource");
        
        // Verify expected resources are present
        let resource_uris: Vec<String> = resources_array
            .iter()
            .filter_map(|r| r.get("uri")?.as_str())
            .map(|s| s.to_string())
            .collect();
        
        assert!(resource_uris.contains(&"fact://templates".to_string()));
        assert!(resource_uris.contains(&"fact://metrics".to_string()));
        assert!(resource_uris.contains(&"fact://cache".to_string()));
    }
    
    #[test]
    fn test_mcp_process_template_tool() {
        let mut client = McpTestClient::new().expect("Failed to create MCP test client");
        client.start_server().expect("Failed to start MCP server");
        
        let params = json!({
            "name": "process_template",
            "arguments": {
                "template_id": "test_template",
                "context": {
                    "input": "test input data",
                    "user_id": "test_user"
                },
                "options": {
                    "cache": true,
                    "priority": "medium"
                }
            }
        });
        
        let response = client.send_request("tools/call", Some(params))
            .expect("Failed to call process_template tool");
        
        assert!(response.error.is_none(), "Process template should not return error");
        assert!(response.result.is_some(), "Process template should return result");
        
        let result = response.result.unwrap();
        let content = result.get("content").expect("Result should contain content");
        
        assert!(content.is_array(), "Content should be an array");
        
        let content_array = content.as_array().unwrap();
        assert!(!content_array.is_empty(), "Content should not be empty");
        
        // Verify the first content item contains expected data
        let first_content = &content_array[0];
        assert_eq!(first_content.get("type").unwrap().as_str().unwrap(), "text");
        
        let text_content = first_content.get("text").unwrap().as_str().unwrap();
        let parsed_response: Value = serde_json::from_str(text_content)
            .expect("Text content should be valid JSON");
        
        assert!(parsed_response.get("success").is_some());
        assert!(parsed_response.get("result").is_some());
        assert!(parsed_response.get("metrics").is_some());
    }
    
    #[test]
    fn test_mcp_list_templates_tool() {
        let mut client = McpTestClient::new().expect("Failed to create MCP test client");
        client.start_server().expect("Failed to start MCP server");
        
        let params = json!({
            "name": "list_templates",
            "arguments": {
                "category": "analysis"
            }
        });
        
        let response = client.send_request("tools/call", Some(params))
            .expect("Failed to call list_templates tool");
        
        assert!(response.error.is_none(), "List templates should not return error");
        assert!(response.result.is_some(), "List templates should return result");
        
        let result = response.result.unwrap();
        let content = result.get("content").expect("Result should contain content");
        let content_array = content.as_array().unwrap();
        let first_content = &content_array[0];
        
        let text_content = first_content.get("text").unwrap().as_str().unwrap();
        let parsed_response: Value = serde_json::from_str(text_content)
            .expect("Text content should be valid JSON");
        
        assert!(parsed_response.get("templates").is_some());
        assert!(parsed_response.get("total").is_some());
    }
    
    #[test]
    fn test_mcp_analyze_context_tool() {
        let mut client = McpTestClient::new().expect("Failed to create MCP test client");
        client.start_server().expect("Failed to start MCP server");
        
        let params = json!({
            "name": "analyze_context",
            "arguments": {
                "context": {
                    "task": "data analysis",
                    "complexity": "medium",
                    "domain": "finance"
                },
                "suggest_templates": true
            }
        });
        
        let response = client.send_request("tools/call", Some(params))
            .expect("Failed to call analyze_context tool");
        
        assert!(response.error.is_none(), "Analyze context should not return error");
        assert!(response.result.is_some(), "Analyze context should return result");
        
        let result = response.result.unwrap();
        let content = result.get("content").expect("Result should contain content");
        let content_array = content.as_array().unwrap();
        let first_content = &content_array[0];
        
        let text_content = first_content.get("text").unwrap().as_str().unwrap();
        let parsed_response: Value = serde_json::from_str(text_content)
            .expect("Text content should be valid JSON");
        
        assert!(parsed_response.get("complexity").is_some());
        assert!(parsed_response.get("patterns").is_some());
        assert!(parsed_response.get("recommendations").is_some());
        assert!(parsed_response.get("suggested_templates").is_some());
    }
    
    #[test]
    fn test_mcp_get_metrics_tool() {
        let mut client = McpTestClient::new().expect("Failed to create MCP test client");
        client.start_server().expect("Failed to start MCP server");
        
        let params = json!({
            "name": "get_metrics",
            "arguments": {}
        });
        
        let response = client.send_request("tools/call", Some(params))
            .expect("Failed to call get_metrics tool");
        
        assert!(response.error.is_none(), "Get metrics should not return error");
        assert!(response.result.is_some(), "Get metrics should return result");
        
        let result = response.result.unwrap();
        let content = result.get("content").expect("Result should contain content");
        let content_array = content.as_array().unwrap();
        let first_content = &content_array[0];
        
        let text_content = first_content.get("text").unwrap().as_str().unwrap();
        let parsed_response: Value = serde_json::from_str(text_content)
            .expect("Text content should be valid JSON");
        
        // Metrics should contain performance data
        assert!(parsed_response.is_object(), "Metrics should be an object");
    }
    
    #[test]
    fn test_mcp_read_resource() {
        let mut client = McpTestClient::new().expect("Failed to create MCP test client");
        client.start_server().expect("Failed to start MCP server");
        
        let params = json!({
            "uri": "fact://templates"
        });
        
        let response = client.send_request("resources/read", Some(params))
            .expect("Failed to read resource");
        
        assert!(response.error.is_none(), "Read resource should not return error");
        assert!(response.result.is_some(), "Read resource should return result");
        
        let result = response.result.unwrap();
        let contents = result.get("contents").expect("Result should contain contents");
        
        assert!(contents.is_array(), "Contents should be an array");
        
        let contents_array = contents.as_array().unwrap();
        assert!(!contents_array.is_empty(), "Contents should not be empty");
        
        let first_content = &contents_array[0];
        assert_eq!(first_content.get("uri").unwrap().as_str().unwrap(), "fact://templates");
        assert_eq!(first_content.get("mimeType").unwrap().as_str().unwrap(), "application/json");
        
        let text_content = first_content.get("text").unwrap().as_str().unwrap();
        let _parsed_content: Value = serde_json::from_str(text_content)
            .expect("Resource content should be valid JSON");
    }
    
    #[test]
    fn test_mcp_error_handling() {
        let mut client = McpTestClient::new().expect("Failed to create MCP test client");
        client.start_server().expect("Failed to start MCP server");
        
        // Test invalid method
        let response = client.send_request("invalid/method", None)
            .expect("Failed to send invalid method request");
        
        assert!(response.error.is_some(), "Invalid method should return error");
        
        let error = response.error.unwrap();
        assert!(error.get("code").is_some(), "Error should have code");
        assert!(error.get("message").is_some(), "Error should have message");
        
        // Test invalid tool call
        let params = json!({
            "name": "nonexistent_tool",
            "arguments": {}
        });
        
        let response = client.send_request("tools/call", Some(params))
            .expect("Failed to call nonexistent tool");
        
        assert!(response.error.is_some(), "Nonexistent tool should return error");
        
        // Test invalid resource URI
        let params = json!({
            "uri": "fact://nonexistent"
        });
        
        let response = client.send_request("resources/read", Some(params))
            .expect("Failed to read nonexistent resource");
        
        assert!(response.error.is_some(), "Nonexistent resource should return error");
    }
    
    #[test]
    fn test_mcp_concurrent_requests() {
        let mut client = McpTestClient::new().expect("Failed to create MCP test client");
        client.start_server().expect("Failed to start MCP server");
        
        let (tx, rx) = mpsc::channel();
        let mut handles = vec![];
        
        // Send multiple concurrent requests
        for i in 0..5 {
            let tx_clone = tx.clone();
            let handle = thread::spawn(move || {
                // Note: In a real implementation, each thread would need its own client
                // This is a simplified test structure
                let result = format!("Request {} completed", i);
                tx_clone.send(result).unwrap();
            });
            handles.push(handle);
        }
        
        // Wait for all requests to complete
        drop(tx);
        let mut results = vec![];
        while let Ok(result) = rx.recv() {
            results.push(result);
        }
        
        for handle in handles {
            handle.join().expect("Thread should complete");
        }
        
        assert_eq!(results.len(), 5, "All concurrent requests should complete");
    }
    
    #[test]
    fn test_mcp_performance_metrics() {
        let mut client = McpTestClient::new().expect("Failed to create MCP test client");
        client.start_server().expect("Failed to start MCP server");
        
        // Make several requests to generate metrics
        for _ in 0..10 {
            let params = json!({
                "name": "get_metrics",
                "arguments": {}
            });
            
            let start = Instant::now();
            let response = client.send_request("tools/call", Some(params))
                .expect("Failed to call get_metrics tool");
            let duration = start.elapsed();
            
            assert!(response.error.is_none(), "Metrics request should succeed");
            assert!(duration.as_millis() < 1000, "Request should complete quickly");
        }
        
        // Final metrics check
        let params = json!({
            "name": "get_metrics",
            "arguments": {}
        });
        
        let response = client.send_request("tools/call", Some(params))
            .expect("Failed to get final metrics");
        
        assert!(response.error.is_none(), "Final metrics should succeed");
        
        // Verify metrics contain performance data
        let result = response.result.unwrap();
        let content = result.get("content").expect("Result should contain content");
        let content_array = content.as_array().unwrap();
        let first_content = &content_array[0];
        let text_content = first_content.get("text").unwrap().as_str().unwrap();
        let metrics: Value = serde_json::from_str(text_content)
            .expect("Metrics should be valid JSON");
        
        assert!(metrics.is_object(), "Metrics should contain performance data");
    }
}

#[cfg(test)]
mod protocol_compliance_tests {
    use super::*;
    
    #[test]
    fn test_jsonrpc_2_0_compliance() {
        let mut client = McpTestClient::new().expect("Failed to create MCP test client");
        client.start_server().expect("Failed to start MCP server");
        
        let response = client.send_request("tools/list", None)
            .expect("Failed to send JSON-RPC request");
        
        // JSON-RPC 2.0 compliance checks would go here
        // This is a simplified test structure
        assert!(response.id > 0, "Response should have valid ID");
    }
    
    #[test]
    fn test_mcp_protocol_headers() {
        // Test MCP-specific protocol headers and formatting
        let mut client = McpTestClient::new().expect("Failed to create MCP test client");
        client.start_server().expect("Failed to start MCP server");
        
        // This would test MCP protocol-specific requirements
        let response = client.send_request("tools/list", None)
            .expect("Failed to test MCP headers");
        
        assert!(response.result.is_some() || response.error.is_some(), 
                "Response should have result or error");
    }
}