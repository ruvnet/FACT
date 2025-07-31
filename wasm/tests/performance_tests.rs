use wasm_bindgen_test::*;
use fact_wasm_core::*;
use fact_wasm_core::optimizations::*;

wasm_bindgen_test_configure!(run_in_browser);

#[wasm_bindgen_test]
fn test_optimized_cache_performance() {
    let mut cache = OptimizedCache::new(1000);
    
    // Test batch insertions
    let start = js_sys::Date::now();
    for i in 0..1000 {
        let key = format!("key_{}", i);
        let value = format!("value_{}", i);
        cache.set(&key, &value);
    }
    let insert_time = js_sys::Date::now() - start;
    
    // Test batch lookups
    let lookup_start = js_sys::Date::now();
    for i in 0..1000 {
        let key = format!("key_{}", i);
        let _ = cache.get(&key);
    }
    let lookup_time = js_sys::Date::now() - lookup_start;
    
    web_sys::console::log_1(&format!("Insert time: {}ms, Lookup time: {}ms", insert_time, lookup_time).into());
    
    assert!(cache.size() > 0);
    assert!(insert_time < 100.0); // Should be under 100ms
    assert!(lookup_time < 50.0);  // Should be under 50ms
}

#[wasm_bindgen_test]
fn test_simd_processor_performance() {
    let processor = SIMDProcessor::new();
    
    // Test vectorized sum
    let data: Vec<f64> = (0..1000).map(|i| i as f64).collect();
    let start = js_sys::Date::now();
    let sum = processor.vectorized_sum(&data);
    let simd_time = js_sys::Date::now() - start;
    
    // Test fast hash
    let test_string = "The quick brown fox jumps over the lazy dog";
    let hash_start = js_sys::Date::now();
    let _hash = processor.fast_hash(test_string);
    let hash_time = js_sys::Date::now() - hash_start;
    
    web_sys::console::log_1(&format!("SIMD sum time: {}ms, Hash time: {}ms", simd_time, hash_time).into());
    
    assert_eq!(sum, 499500.0); // Sum of 0..1000
    assert!(simd_time < 10.0); // Should be very fast
    assert!(hash_time < 1.0);  // Should be under 1ms
}

#[wasm_bindgen_test]
fn test_memory_pool_efficiency() {
    let mut pool = MemoryPool::new(4096, 10);
    
    let start = js_sys::Date::now();
    
    // Get and return buffers
    let mut buffers = Vec::new();
    for _ in 0..50 {
        if let Some(buffer_id) = pool.get_buffer() {
            buffers.push(buffer_id);
        }
    }
    
    for buffer_id in buffers {
        pool.return_buffer(buffer_id);
    }
    
    let pool_time = js_sys::Date::now() - start;
    
    web_sys::console::log_1(&format!("Memory pool operations time: {}ms", pool_time).into());
    
    assert!(pool_time < 5.0); // Should be very fast
    assert!(pool.available_count() >= 10); // Should have buffers available
}

#[wasm_bindgen_test]
fn test_batch_processor_throughput() {
    let mut processor = BatchProcessor::new(100);
    
    let start = js_sys::Date::now();
    
    // Add operations to batch
    for i in 0..500 {
        processor.add_set(&format!("key_{}", i), &format!("value_{}", i));
    }
    
    let batch_time = js_sys::Date::now() - start;
    
    web_sys::console::log_1(&format!("Batch processing time: {}ms", batch_time).into());
    
    assert!(batch_time < 20.0); // Should be efficient
    assert_eq!(processor.pending_count(), 0); // All should be flushed
}

#[wasm_bindgen_test]
fn test_performance_metrics_accuracy() {
    let mut metrics = PerformanceMetrics::new();
    
    // Record some operations
    metrics.record_operation("cache_get", 1.5);
    metrics.record_operation("cache_get", 2.0);
    metrics.record_operation("cache_get", 1.0);
    metrics.record_operation("cache_set", 3.0);
    
    let stats = metrics.get_stats();
    web_sys::console::log_1(&stats);
    
    // Metrics should be recorded
    assert!(!stats.is_null());
}