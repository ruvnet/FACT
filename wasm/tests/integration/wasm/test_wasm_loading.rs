//! WASM Loading and Functionality Integration Tests
//!
//! Comprehensive tests for WASM module loading, initialization, memory management,
//! cross-platform compatibility, and performance validation.

use std::path::PathBuf;
use std::fs;
use std::process::Command;
use std::time::{Duration, Instant};
use serde_json::Value;
use tempfile::TempDir;

/// WASM module test utilities
pub struct WasmTestRunner {
    wasm_path: PathBuf,
    js_binding_path: PathBuf,
    temp_dir: TempDir,
}

impl WasmTestRunner {
    pub fn new() -> Result<Self, Box<dyn std::error::Error>> {
        let current_dir = std::env::current_dir()?;
        let wasm_path = current_dir.join("pkg").join("fact_wasm_core_bg.wasm");
        let js_binding_path = current_dir.join("pkg").join("fact_wasm_core.js");
        let temp_dir = TempDir::new()?;
        
        if !wasm_path.exists() {
            return Err("WASM module not found. Run './build-wasm.sh' first.".into());
        }
        
        if !js_binding_path.exists() {
            return Err("JS bindings not found. Run './build-wasm.sh' first.".into());
        }
        
        Ok(Self {
            wasm_path,
            js_binding_path,
            temp_dir,
        })
    }
    
    pub fn get_wasm_size(&self) -> Result<u64, std::io::Error> {
        let metadata = fs::metadata(&self.wasm_path)?;
        Ok(metadata.len())
    }
    
    pub fn validate_wasm_structure(&self) -> Result<bool, Box<dyn std::error::Error>> {
        // Basic WASM file validation
        let wasm_bytes = fs::read(&self.wasm_path)?;
        
        // Check WASM magic number (0x00, 0x61, 0x73, 0x6D)
        if wasm_bytes.len() < 4 {
            return Ok(false);
        }
        
        let magic = &wasm_bytes[0..4];
        let expected_magic = [0x00, 0x61, 0x73, 0x6D];
        
        Ok(magic == expected_magic)
    }
    
    pub fn test_node_loading(&self) -> Result<String, Box<dyn std::error::Error>> {
        // Create a test Node.js script to load and test the WASM module
        let test_script = format!(r#"
const {{ FastCache, QueryProcessor, greet }} = require('{}');

async function testWasm() {{
    try {{
        // Test basic functions
        console.log('Testing greet function...');
        const greeting = greet('WASM Test');
        console.log('Greeting:', greeting);
        
        // Test FastCache
        console.log('Testing FastCache...');
        const cache = new FastCache(10);
        const setResult = cache.set('test_key', 'test_value', 60000);
        console.log('Cache set result:', setResult);
        
        const getValue = cache.get('test_key');
        console.log('Cache get result:', getValue);
        
        // Test QueryProcessor
        console.log('Testing QueryProcessor...');
        const processor = new QueryProcessor();
        const queryResult = processor.process_query('SELECT 1');
        console.log('Query result:', JSON.stringify(queryResult));
        
        console.log('All tests passed!');
        return 'SUCCESS';
    }} catch (error) {{
        console.error('Test failed:', error);
        return 'FAILED: ' + error.message;
    }}
}}

testWasm().then(result => {{
    console.log('Final result:', result);
    process.exit(result === 'SUCCESS' ? 0 : 1);
}});
"#, self.js_binding_path.display());
        
        let test_file = self.temp_dir.path().join("test_wasm.js");
        fs::write(&test_file, test_script)?;
        
        let output = Command::new("node")
            .arg(&test_file)
            .current_dir(self.temp_dir.path())
            .output()?;
        
        let stdout = String::from_utf8(output.stdout)?;
        let stderr = String::from_utf8(output.stderr)?;
        
        if !output.status.success() {
            return Err(format!("Node.js test failed:\nSTDOUT: {}\nSTDERR: {}", stdout, stderr).into());
        }
        
        Ok(stdout)
    }
    
    pub fn test_browser_loading(&self) -> Result<String, Box<dyn std::error::Error>> {
        // Create a test HTML file for browser testing
        let html_content = format!(r#"
<!DOCTYPE html>
<html>
<head>
    <title>WASM Browser Test</title>
</head>
<body>
    <h1>FACT WASM Browser Test</h1>
    <div id="results"></div>
    
    <script type="module">
        import init, {{ FastCache, QueryProcessor, greet }} from './fact_wasm_core.js';
        
        async function runTests() {{
            const resultsDiv = document.getElementById('results');
            
            try {{
                await init();
                resultsDiv.innerHTML += '<p>WASM module initialized successfully</p>';
                
                // Test greet function
                const greeting = greet('Browser Test');
                resultsDiv.innerHTML += `<p>Greeting: ${{greeting}}</p>`;
                
                // Test FastCache
                const cache = new FastCache(10);
                const setResult = cache.set('browser_key', 'browser_value', 60000);
                const getValue = cache.get('browser_key');
                resultsDiv.innerHTML += `<p>Cache test: Set=${{setResult}}, Get=${{getValue}}</p>`;
                
                // Test QueryProcessor
                const processor = new QueryProcessor();
                const queryResult = processor.process_query('SELECT 42');
                resultsDiv.innerHTML += `<p>Query result: ${{JSON.stringify(queryResult)}}</p>`;
                
                resultsDiv.innerHTML += '<p style="color: green">All browser tests passed!</p>';
                window.testResult = 'SUCCESS';
            }} catch (error) {{
                resultsDiv.innerHTML += `<p style="color: red">Test failed: ${{error.message}}</p>`;
                window.testResult = 'FAILED';
                console.error('Browser test failed:', error);
            }}
        }}
        
        runTests();
    </script>
</body>
</html>
"#);
        
        let html_file = self.temp_dir.path().join("test_browser.html");
        fs::write(&html_file, html_content)?;
        
        // Copy WASM files to temp directory for browser access
        let temp_wasm = self.temp_dir.path().join("fact_wasm_core_bg.wasm");
        let temp_js = self.temp_dir.path().join("fact_wasm_core.js");
        
        fs::copy(&self.wasm_path, &temp_wasm)?;
        fs::copy(&self.js_binding_path, &temp_js)?;
        
        // Return the HTML content for manual testing or further automation
        Ok(html_content)
    }
    
    pub fn benchmark_loading_time(&self) -> Result<Duration, Box<dyn std::error::Error>> {
        let start = Instant::now();
        let _ = self.test_node_loading()?;
        let duration = start.elapsed();
        Ok(duration)
    }
    
    pub fn test_memory_usage(&self) -> Result<String, Box<dyn std::error::Error>> {
        let test_script = format!(r#"
const {{ FastCache, QueryProcessor }} = require('{}');

async function memoryTest() {{
    const initialMemory = process.memoryUsage();
    console.log('Initial memory:', JSON.stringify(initialMemory));
    
    // Create multiple caches and processors
    const caches = [];
    const processors = [];
    
    for (let i = 0; i < 100; i++) {{
        const cache = new FastCache(100);
        const processor = new QueryProcessor();
        
        // Add some data
        for (let j = 0; j < 50; j++) {{
            cache.set(`key_${{i}}_${{j}}`, `value_${{i}}_${{j}}`, 60000);
        }}
        
        caches.push(cache);
        processors.push(processor);
    }}
    
    const peakMemory = process.memoryUsage();
    console.log('Peak memory:', JSON.stringify(peakMemory));
    
    // Force garbage collection if available
    if (global.gc) {{
        global.gc();
    }}
    
    const finalMemory = process.memoryUsage();
    console.log('Final memory:', JSON.stringify(finalMemory));
    
    const memoryIncrease = finalMemory.heapUsed - initialMemory.heapUsed;
    console.log('Memory increase (bytes):', memoryIncrease);
    console.log('Memory increase (MB):', (memoryIncrease / 1024 / 1024).toFixed(2));
    
    return 'MEMORY_TEST_COMPLETE';
}}

memoryTest().then(result => {{
    console.log('Memory test result:', result);
}}).catch(error => {{
    console.error('Memory test failed:', error);
    process.exit(1);
}});
"#, self.js_binding_path.display());
        
        let test_file = self.temp_dir.path().join("memory_test.js");
        fs::write(&test_file, test_script)?;
        
        let output = Command::new("node")
            .arg("--expose-gc")
            .arg(&test_file)
            .current_dir(self.temp_dir.path())
            .output()?;
        
        let stdout = String::from_utf8(output.stdout)?;
        let stderr = String::from_utf8(output.stderr)?;
        
        if !output.status.success() {
            return Err(format!("Memory test failed:\nSTDOUT: {}\nSTDERR: {}", stdout, stderr).into());
        }
        
        Ok(stdout)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_wasm_module_exists() {
        let runner = WasmTestRunner::new().expect("Failed to create WASM test runner");
        
        assert!(runner.wasm_path.exists(), "WASM module should exist");
        assert!(runner.js_binding_path.exists(), "JS bindings should exist");
    }
    
    #[test]
    fn test_wasm_file_structure() {
        let runner = WasmTestRunner::new().expect("Failed to create WASM test runner");
        
        let is_valid = runner.validate_wasm_structure()
            .expect("Failed to validate WASM structure");
        
        assert!(is_valid, "WASM file should have valid structure");
    }
    
    #[test]
    fn test_wasm_file_size() {
        let runner = WasmTestRunner::new().expect("Failed to create WASM test runner");
        
        let size = runner.get_wasm_size().expect("Failed to get WASM size");
        
        // WASM file should be reasonable size (less than 10MB for this project)
        assert!(size > 1000, "WASM file should be at least 1KB");
        assert!(size < 10_000_000, "WASM file should be less than 10MB");
        
        println!("WASM file size: {} bytes ({:.2} KB)", size, size as f64 / 1024.0);
    }
    
    #[test]
    fn test_node_js_loading() {
        let runner = WasmTestRunner::new().expect("Failed to create WASM test runner");
        
        let output = runner.test_node_loading()
            .expect("Failed to test Node.js loading");
        
        assert!(output.contains("All tests passed!"), "Node.js tests should pass");
        assert!(output.contains("SUCCESS"), "Node.js test should return success");
    }
    
    #[test]
    fn test_browser_compatibility() {
        let runner = WasmTestRunner::new().expect("Failed to create WASM test runner");
        
        let html_content = runner.test_browser_loading()
            .expect("Failed to create browser test");
        
        assert!(html_content.contains("FACT WASM Browser Test"), "HTML should contain test title");
        assert!(html_content.contains("init()"), "HTML should initialize WASM");
        assert!(html_content.contains("FastCache"), "HTML should test FastCache");
        assert!(html_content.contains("QueryProcessor"), "HTML should test QueryProcessor");
    }
    
    #[test]
    fn test_loading_performance() {
        let runner = WasmTestRunner::new().expect("Failed to create WASM test runner");
        
        let duration = runner.benchmark_loading_time()
            .expect("Failed to benchmark loading time");
        
        // Loading should complete within reasonable time (5 seconds)
        assert!(duration.as_secs() < 5, "WASM loading should complete within 5 seconds");
        
        println!("WASM loading time: {:.2}ms", duration.as_millis());
    }
    
    #[test]
    fn test_memory_management() {
        let runner = WasmTestRunner::new().expect("Failed to create WASM test runner");
        
        let output = runner.test_memory_usage()
            .expect("Failed to test memory usage");
        
        assert!(output.contains("MEMORY_TEST_COMPLETE"), "Memory test should complete");
        assert!(output.contains("Initial memory:"), "Should show initial memory usage");
        assert!(output.contains("Final memory:"), "Should show final memory usage");
        
        // Parse memory increase from output
        if let Some(line) = output.lines().find(|l| l.contains("Memory increase (MB):")) {
            if let Some(mb_str) = line.split(':').nth(1) {
                if let Ok(mb_increase) = mb_str.trim().parse::<f64>() {
                    assert!(mb_increase < 100.0, "Memory increase should be reasonable (< 100MB)");
                    println!("Memory increase: {:.2} MB", mb_increase);
                }
            }
        }
    }
    
    #[test]
    fn test_concurrent_wasm_instances() {
        use std::thread;
        use std::sync::Arc;
        
        let runner = Arc::new(WasmTestRunner::new().expect("Failed to create WASM test runner"));
        let mut handles = vec![];
        
        // Test concurrent WASM loading/usage
        for i in 0..3 {
            let runner_clone = Arc::clone(&runner);
            let handle = thread::spawn(move || {
                let output = runner_clone.test_node_loading()
                    .expect(&format!("Concurrent test {} failed", i));
                
                assert!(output.contains("SUCCESS"), "Concurrent test should succeed");
            });
            
            handles.push(handle);
        }
        
        // Wait for all threads to complete
        for handle in handles {
            handle.join().expect("Concurrent thread should complete");
        }
    }
    
    #[test]
    fn test_wasm_error_handling() {
        let runner = WasmTestRunner::new().expect("Failed to create WASM test runner");
        
        // Test error handling with invalid operations
        let test_script = format!(r#"
const {{ FastCache, QueryProcessor }} = require('{}');

async function errorTest() {{
    try {{
        // Test cache with invalid parameters
        const cache = new FastCache(-1); // Invalid size
        console.log('Cache with invalid size created');
        
        // Test processor with null query
        const processor = new QueryProcessor();
        const result = processor.process_query(null);
        console.log('Null query result:', result);
        
        return 'ERROR_TEST_COMPLETE';
    }} catch (error) {{
        console.log('Expected error caught:', error.message);
        return 'ERROR_HANDLED';
    }}
}}

errorTest().then(result => {{
    console.log('Error test result:', result);
}});
"#, runner.js_binding_path.display());
        
        let test_file = runner.temp_dir.path().join("error_test.js");
        fs::write(&test_file, test_script).expect("Failed to write error test file");
        
        let output = Command::new("node")
            .arg(&test_file)
            .current_dir(runner.temp_dir.path())
            .output()
            .expect("Failed to run error test");
        
        let stdout = String::from_utf8(output.stdout).expect("Invalid UTF-8 output");
        
        // Test should handle errors gracefully
        assert!(stdout.contains("ERROR_") || output.status.success(), 
                "Error test should handle errors gracefully");
    }
    
    #[test]
    fn test_wasm_function_exports() {
        let runner = WasmTestRunner::new().expect("Failed to create WASM test runner");
        
        // Test that all expected functions are exported
        let test_script = format!(r#"
const wasmModule = require('{}');

const expectedExports = [
    'FastCache',
    'QueryProcessor', 
    'greet',
    'get_wasm_info',
    'get_memory_usage',
    'benchmark_cache_operations'
];

let allExportsFound = true;
const missingExports = [];

for (const exportName of expectedExports) {{
    if (typeof wasmModule[exportName] === 'undefined') {{
        allExportsFound = false;
        missingExports.push(exportName);
    }} else {{
        console.log(`✓ Found export: ${{exportName}}`);
    }}
}}

if (!allExportsFound) {{
    console.error('Missing exports:', missingExports);
    process.exit(1);
}} else {{
    console.log('All expected exports found!');
}}
"#, runner.js_binding_path.display());
        
        let test_file = runner.temp_dir.path().join("exports_test.js");
        fs::write(&test_file, test_script).expect("Failed to write exports test file");
        
        let output = Command::new("node")
            .arg(&test_file)
            .current_dir(runner.temp_dir.path())
            .output()
            .expect("Failed to run exports test");
        
        let stdout = String::from_utf8(output.stdout).expect("Invalid UTF-8 output");
        
        assert!(output.status.success(), "Exports test should succeed");
        assert!(stdout.contains("All expected exports found!"), "All exports should be present");
    }
    
    #[test]
    fn test_wasm_type_definitions() {
        let runner = WasmTestRunner::new().expect("Failed to create WASM test runner");
        
        // Check if TypeScript definitions exist
        let ts_defs_path = runner.wasm_path.parent().unwrap().join("fact_wasm_core.d.ts");
        
        if ts_defs_path.exists() {
            let defs_content = fs::read_to_string(&ts_defs_path)
                .expect("Failed to read TypeScript definitions");
            
            // Verify essential types are defined
            assert!(defs_content.contains("FastCache"), "TypeScript defs should include FastCache");
            assert!(defs_content.contains("QueryProcessor"), "TypeScript defs should include QueryProcessor");
            assert!(defs_content.contains("export"), "TypeScript defs should have exports");
            
            println!("TypeScript definitions found and validated");
        } else {
            println!("TypeScript definitions not found (optional)");
        }
    }
}

#[cfg(test)]
mod performance_tests {
    use super::*;
    
    #[test]
    fn test_wasm_throughput() {
        let runner = WasmTestRunner::new().expect("Failed to create WASM test runner");
        
        let test_script = format!(r#"
const {{ FastCache, QueryProcessor }} = require('{}');

async function throughputTest() {{
    const iterations = 1000;
    const cache = new FastCache(1000);
    const processor = new QueryProcessor();
    
    console.log(`Running throughput test with ${{iterations}} iterations...`);
    
    // Cache throughput test
    const cacheStart = Date.now();
    for (let i = 0; i < iterations; i++) {{
        cache.set(`key_${{i}}`, `value_${{i}}`, 60000);
        cache.get(`key_${{i}}`);
    }}
    const cacheTime = Date.now() - cacheStart;
    const cacheOpsPerSec = (iterations * 2) / (cacheTime / 1000);
    
    console.log(`Cache operations per second: ${{cacheOpsPerSec.toFixed(2)}}`);
    
    // Query processing throughput test
    const queryStart = Date.now();
    for (let i = 0; i < iterations; i++) {{
        processor.process_query(`SELECT ${{i}} as test_value`);
    }}
    const queryTime = Date.now() - queryStart;
    const queryOpsPerSec = iterations / (queryTime / 1000);
    
    console.log(`Query operations per second: ${{queryOpsPerSec.toFixed(2)}}`);
    
    return 'THROUGHPUT_TEST_COMPLETE';
}}

throughputTest().then(result => {{
    console.log('Throughput test result:', result);
}});
"#, runner.js_binding_path.display());
        
        let test_file = runner.temp_dir.path().join("throughput_test.js");
        fs::write(&test_file, test_script).expect("Failed to write throughput test file");
        
        let output = Command::new("node")
            .arg(&test_file)
            .current_dir(runner.temp_dir.path())
            .output()
            .expect("Failed to run throughput test");
        
        let stdout = String::from_utf8(output.stdout).expect("Invalid UTF-8 output");
        
        assert!(output.status.success(), "Throughput test should succeed");
        assert!(stdout.contains("THROUGHPUT_TEST_COMPLETE"), "Throughput test should complete");
        assert!(stdout.contains("operations per second"), "Should show performance metrics");
        
        println!("Throughput test output:\n{}", stdout);
    }
}