//! Performance benchmarks for WASM module

use criterion::{black_box, criterion_group, criterion_main, Criterion};
use fact_wasm_core::{FastCache, QueryProcessor};
use std::hint::black_box as std_black_box;

fn benchmark_cache_operations(c: &mut Criterion) {
    c.bench_function("cache_set_1000", |b| {
        let mut cache = FastCache::new(1000);
        let mut counter = 0;
        
        b.iter(|| {
            let key = format!("key_{}", counter);
            let value = format!("value_data_{}", counter);
            cache.set(&key, &value, 60000);
            counter += 1;
        })
    });

    c.bench_function("cache_get_1000", |b| {
        let mut cache = FastCache::new(1000);
        
        // Pre-populate cache
        for i in 0..1000 {
            let key = format!("key_{}", i);
            let value = format!("value_data_{}", i);
            cache.set(&key, &value, 60000);
        }
        
        let mut counter = 0;
        b.iter(|| {
            let key = format!("key_{}", counter % 1000);
            let result = cache.get(&key);
            std_black_box(result);
            counter += 1;
        })
    });

    c.bench_function("cache_mixed_operations", |b| {
        let mut cache = FastCache::new(1000);
        let mut counter = 0;
        
        b.iter(|| {
            if counter % 3 == 0 {
                // Set operation
                let key = format!("key_{}", counter);
                let value = format!("value_{}", counter);
                cache.set(&key, &value, 60000);
            } else {
                // Get operation
                let key = format!("key_{}", counter % 100);
                let result = cache.get(&key);
                std_black_box(result);
            }
            counter += 1;
        })
    });
}

fn benchmark_query_processor(c: &mut Criterion) {
    c.bench_function("query_processing", |b| {
        let mut processor = QueryProcessor::new();
        let queries = vec![
            "SELECT * FROM companies",
            "SELECT name, revenue FROM companies WHERE revenue > 1000000",
            "SELECT COUNT(*) FROM financial_records",
            "INSERT INTO companies (name, revenue) VALUES ('Test', 500000)",
        ];
        let mut counter = 0;
        
        b.iter(|| {
            let query = &queries[counter % queries.len()];
            let result = processor.process_query(query);
            std_black_box(result);
            counter += 1;
        })
    });

    c.bench_function("query_cache_hits", |b| {
        let mut processor = QueryProcessor::new();
        let query = "SELECT * FROM companies";
        
        // Warm up cache
        processor.process_query(query);
        
        b.iter(|| {
            let result = processor.process_query(query);
            std_black_box(result);
        })
    });
}

fn benchmark_memory_operations(c: &mut Criterion) {
    c.bench_function("large_cache_operations", |b| {
        let mut cache = FastCache::new(10000);
        let mut counter = 0;
        
        b.iter(|| {
            // Create larger data payloads
            let key = format!("large_key_with_prefix_{}", counter);
            let value = format!("large_value_with_significant_content_payload_data_{}_", counter).repeat(10);
            cache.set(&key, &value, 60000);
            counter += 1;
        })
    });

    c.bench_function("cache_eviction_pressure", |b| {
        let mut cache = FastCache::new(100); // Small cache to force evictions
        let mut counter = 0;
        
        b.iter(|| {
            let key = format!("eviction_test_{}", counter);
            let value = format!("value_{}", counter);
            cache.set(&key, &value, 60000);
            counter += 1;
        })
    });
}

fn benchmark_string_operations(c: &mut Criterion) {
    use fact_wasm_core::utils::{simple_hash, escape_sql_string, format_bytes};
    
    c.bench_function("string_hashing", |b| {
        let test_strings = vec![
            "short",
            "medium_length_string_for_testing",
            "very_long_string_with_lots_of_content_to_hash_including_various_characters_and_symbols_!@#$%^&*()",
        ];
        let mut counter = 0;
        
        b.iter(|| {
            let s = &test_strings[counter % test_strings.len()];
            let hash = simple_hash(s);
            std_black_box(hash);
            counter += 1;
        })
    });

    c.bench_function("sql_escaping", |b| {
        let test_strings = vec![
            "simple string",
            "string with 'quotes'",
            "string with 'multiple' 'quotes' and 'content'",
            "very long string with 'quotes' and lots of content to test performance",
        ];
        let mut counter = 0;
        
        b.iter(|| {
            let s = &test_strings[counter % test_strings.len()];
            let escaped = escape_sql_string(s);
            std_black_box(escaped);
            counter += 1;
        })
    });

    c.bench_function("bytes_formatting", |b| {
        let sizes = vec![1024.0, 1048576.0, 1073741824.0, 1099511627776.0];
        let mut counter = 0;
        
        b.iter(|| {
            let size = sizes[counter % sizes.len()];
            let formatted = format_bytes(size);
            std_black_box(formatted);
            counter += 1;
        })
    });
}

criterion_group!(
    benches,
    benchmark_cache_operations,
    benchmark_query_processor,
    benchmark_memory_operations,
    benchmark_string_operations
);
criterion_main!(benches);