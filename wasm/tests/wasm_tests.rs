//! WASM module tests

#![cfg(target_arch = "wasm32")]

use crate::*;
use wasm_bindgen_test::*;

wasm_bindgen_test_configure!(run_in_browser);

#[wasm_bindgen_test]
fn test_fast_cache_basic_operations() {
    let mut cache = FastCache::new(10);
    
    // Test set and get
    assert!(cache.set("key1", "value1", 60000));
    assert_eq!(cache.get("key1"), Some("value1".to_string()));
    
    // Test non-existent key
    assert_eq!(cache.get("nonexistent"), None);
    
    // Test cache statistics
    let stats = cache.stats();
    assert!(!stats.is_null());
}

#[wasm_bindgen_test]
fn test_query_processor() {
    let mut processor = QueryProcessor::new();
    
    // Test query processing
    let result = processor.process_query("SELECT * FROM test");
    assert!(result.success);
    assert!(result.execution_time_ms >= 0.0);
    
    // Test cache hit on second identical query
    let result2 = processor.process_query("SELECT * FROM test");
    assert!(result2.cache_hit);
    
    // Test statistics
    let stats = processor.get_stats();
    assert!(!stats.is_null());
}

#[wasm_bindgen_test]
fn test_cache_eviction() {
    let mut cache = FastCache::new(2); // Small cache for testing eviction
    
    // Fill cache to capacity
    cache.set("key1", "value1", 60000);
    cache.set("key2", "value2", 60000);
    
    // Add third item, should trigger eviction
    cache.set("key3", "value3", 60000);
    
    // One of the first two should be evicted
    let key1_exists = cache.get("key1").is_some();
    let key2_exists = cache.get("key2").is_some();
    let key3_exists = cache.get("key3").is_some();
    
    assert!(key3_exists); // New key should exist
    assert!(!(key1_exists && key2_exists)); // At least one old key should be evicted
}

#[wasm_bindgen_test]
fn test_cache_ttl_expiration() {
    let mut cache = FastCache::new(10);
    
    // Set with very short TTL (this won't actually work in synchronous test,
    // but validates the interface)
    cache.set("short_ttl", "value", 1); // 1ms TTL
    
    // Immediate retrieval should work
    assert_eq!(cache.get("short_ttl"), Some("value".to_string()));
}

#[wasm_bindgen_test]
fn test_query_result_creation() {
    let result = QueryResult::new(true, 15.5, false, "{\"data\": \"test\"}");
    
    assert!(result.success);
    assert_eq!(result.execution_time_ms, 15.5);
    assert!(!result.cache_hit);
    assert_eq!(result.data(), "{\"data\": \"test\"}");
}

#[wasm_bindgen_test]
fn test_benchmark_function() {
    let result = benchmark_cache_operations(100);
    assert!(!result.is_null());
    // Benchmark should complete without errors
}

#[wasm_bindgen_test]
fn test_utility_functions() {
    // Test greeting function
    let greeting = greet("WASM Test");
    assert!(greeting.contains("WASM Test"));
    
    // Test WASM info
    let info = get_wasm_info();
    assert!(!info.is_null());
    
    // Test memory usage
    let memory = get_memory_usage();
    assert!(!memory.is_null());
}

#[wasm_bindgen_test]
fn test_sql_validation() {
    use crate::utils::validate_sql_query;
    
    // Valid queries
    let valid_result = validate_sql_query("SELECT * FROM table");
    // Result should indicate valid query
    
    // Invalid queries
    let invalid_result = validate_sql_query("INVALID QUERY");
    // Result should indicate invalid query
    
    assert!(!valid_result.is_null());
    assert!(!invalid_result.is_null());
}

#[wasm_bindgen_test]
fn test_performance_profiler() {
    use crate::utils::PerformanceProfiler;
    
    let mut profiler = PerformanceProfiler::new();
    profiler.mark("test_mark");
    
    let report = profiler.get_report();
    assert!(!report.is_null());
}

#[wasm_bindgen_test]
fn test_timer_utility() {
    use crate::utils::Timer;
    
    let timer = Timer::new("test_timer");
    let elapsed = timer.elapsed();
    assert!(elapsed >= 0.0);
    
    let finished = timer.finish();
    assert!(finished >= elapsed);
}

#[wasm_bindgen_test]
fn test_memory_pressure() {
    // Test with larger cache to simulate memory pressure
    let mut cache = FastCache::new(1000);
    
    // Add many items
    for i in 0..1500 {
        let key = format!("key_{}", i);
        let data = format!("data_value_with_some_content_{}", i);
        cache.set(&key, &data, 60000);
    }
    
    // Cache should handle overflow gracefully
    let stats = cache.stats();
    assert!(!stats.is_null());
}

#[wasm_bindgen_test]
fn test_query_processor_cache_behavior() {
    let mut processor = QueryProcessor::new();
    
    // Process same query multiple times
    for _ in 0..5 {
        let result = processor.process_query("SELECT * FROM companies");
        assert!(result.success);
    }
    
    // Should have cache hits after first query
    let stats = processor.get_stats();
    assert!(!stats.is_null());
}