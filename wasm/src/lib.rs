//! FACT WASM Core Module
//! 
//! High-performance WebAssembly bindings for the FACT system.
//! Provides accelerated query processing, caching, and data operations.

pub mod utils;

use wasm_bindgen::prelude::*;
use js_sys::Array;
use web_sys::console;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use smallvec::SmallVec;

// Optional: Use wee_alloc as the global allocator for smaller WASM size
#[cfg(feature = "wee_alloc")]
#[global_allocator]
static ALLOC: wee_alloc::WeeAlloc = wee_alloc::WeeAlloc::INIT;

// Set up panic hook for better error messages in development
#[cfg(feature = "console_error_panic_hook")]
#[wasm_bindgen(start)]
pub fn main() {
    console_error_panic_hook::set_once();
}

/// Log to browser console (for debugging)
macro_rules! log {
    ( $( $t:tt )* ) => {
        console::log_1(&format!( $( $t )* ).into());
    }
}

/// High-performance query result structure
#[wasm_bindgen]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QueryResult {
    #[wasm_bindgen(readonly)]
    pub success: bool,
    #[wasm_bindgen(readonly)]
    pub execution_time_ms: f64,
    #[wasm_bindgen(readonly)]
    pub cache_hit: bool,
    data: String, // JSON serialized data
}

#[wasm_bindgen]
impl QueryResult {
    #[wasm_bindgen(constructor)]
    pub fn new(success: bool, execution_time_ms: f64, cache_hit: bool, data: &str) -> QueryResult {
        QueryResult {
            success,
            execution_time_ms,
            cache_hit,
            data: data.to_string(),
        }
    }

    #[wasm_bindgen(getter)]
    pub fn data(&self) -> String {
        self.data.clone()
    }

    #[wasm_bindgen(setter)]
    pub fn set_data(&mut self, data: &str) {
        self.data = data.to_string();
    }
}

/// High-performance cache with optimized hash maps
#[wasm_bindgen]
pub struct FastCache {
    cache: HashMap<String, CacheEntry>,
    max_size: usize,
    hit_count: u64,
    miss_count: u64,
}

#[derive(Debug, Clone)]
struct CacheEntry {
    data: String,
    timestamp: f64,
    access_count: u32,
    ttl_ms: u64,
}

#[wasm_bindgen]
impl FastCache {
    #[wasm_bindgen(constructor)]
    pub fn new(max_size: usize) -> FastCache {
        log!("Initializing FastCache with max_size: {}", max_size);
        FastCache {
            cache: HashMap::with_capacity(max_size),
            max_size,
            hit_count: 0,
            miss_count: 0,
        }
    }

    /// Store data in cache with TTL
    #[wasm_bindgen]
    pub fn set(&mut self, key: &str, data: &str, ttl_ms: u64) -> bool {
        let now = js_sys::Date::now();
        
        // Evict expired entries if cache is full
        if self.cache.len() >= self.max_size {
            self.evict_expired(now);
            
            // If still full, evict least recently used
            if self.cache.len() >= self.max_size {
                self.evict_lru();
            }
        }

        let entry = CacheEntry {
            data: data.to_string(),
            timestamp: now,
            access_count: 1,
            ttl_ms,
        };

        self.cache.insert(key.to_string(), entry);
        true
    }

    /// Retrieve data from cache
    #[wasm_bindgen]
    pub fn get(&mut self, key: &str) -> Option<String> {
        let now = js_sys::Date::now();
        
        if let Some(entry) = self.cache.get_mut(key) {
            // Check if expired
            if now - entry.timestamp > entry.ttl_ms as f64 {
                self.cache.remove(key);
                self.miss_count += 1;
                return None;
            }
            
            // Update access statistics
            entry.access_count += 1;
            entry.timestamp = now; // Update for LRU
            self.hit_count += 1;
            
            Some(entry.data.clone())
        } else {
            self.miss_count += 1;
            None
        }
    }

    /// Get cache statistics
    #[wasm_bindgen]
    pub fn stats(&self) -> JsValue {
        let stats = serde_json::json!({
            "size": self.cache.len(),
            "max_size": self.max_size,
            "hit_count": self.hit_count,
            "miss_count": self.miss_count,
            "hit_rate": if self.hit_count + self.miss_count > 0 {
                self.hit_count as f64 / (self.hit_count + self.miss_count) as f64
            } else {
                0.0
            }
        });
        
        serde_wasm_bindgen::to_value(&stats).unwrap_or(JsValue::NULL)
    }

    /// Clear cache
    #[wasm_bindgen]
    pub fn clear(&mut self) {
        self.cache.clear();
        self.hit_count = 0;
        self.miss_count = 0;
    }

    /// Remove expired entries
    fn evict_expired(&mut self, now: f64) {
        let expired_keys: SmallVec<[String; 16]> = self.cache
            .iter()
            .filter_map(|(key, entry)| {
                if now - entry.timestamp > entry.ttl_ms as f64 {
                    Some(key.clone())
                } else {
                    None
                }
            })
            .collect();

        for key in expired_keys {
            self.cache.remove(&key);
        }
    }

    /// Evict least recently used entry
    fn evict_lru(&mut self) {
        if let Some((lru_key, _)) = self.cache
            .iter()
            .min_by_key(|(_, entry)| (entry.timestamp as u64, entry.access_count))
            .map(|(k, v)| (k.clone(), v.clone()))
        {
            self.cache.remove(&lru_key);
        }
    }
}

/// High-performance SQL query parser and optimizer
#[wasm_bindgen]
pub struct QueryProcessor {
    query_cache: HashMap<String, String>,
    execution_stats: ExecutionStats,
}

#[derive(Default)]
struct ExecutionStats {
    total_queries: u64,
    cache_hits: u64,
    avg_execution_time: f64,
}

#[wasm_bindgen]
impl QueryProcessor {
    #[wasm_bindgen(constructor)]
    pub fn new() -> QueryProcessor {
        log!("Initializing QueryProcessor");
        QueryProcessor {
            query_cache: HashMap::new(),   
            execution_stats: ExecutionStats::default(),
        }
    }

    /// Process and optimize SQL query
    #[wasm_bindgen]
    pub fn process_query(&mut self, query: &str) -> QueryResult {
        let start_time = js_sys::Date::now();
        self.execution_stats.total_queries += 1;

        // Check query cache first
        let cache_key = self.generate_cache_key(query);
        let mut cache_hit = false;

        if let Some(cached_result) = self.query_cache.get(&cache_key) {
            self.execution_stats.cache_hits += 1;
            cache_hit = true;
            let execution_time = js_sys::Date::now() - start_time;
            
            return QueryResult::new(true, execution_time, cache_hit, cached_result);
        }

        // Process query (simplified for demo)
        let optimized_query = self.optimize_query(query);
        let result = self.execute_query(&optimized_query);

        // Cache the result
        self.query_cache.insert(cache_key, result.clone());

        let execution_time = js_sys::Date::now() - start_time;
        self.update_avg_execution_time(execution_time);

        QueryResult::new(true, execution_time, cache_hit, &result)
    }

    /// Get processor statistics
    #[wasm_bindgen]
    pub fn get_stats(&self) -> JsValue {
        let stats = serde_json::json!({
            "total_queries": self.execution_stats.total_queries,
            "cache_hits": self.execution_stats.cache_hits,
            "cache_hit_rate": if self.execution_stats.total_queries > 0 {
                self.execution_stats.cache_hits as f64 / self.execution_stats.total_queries as f64
            } else {
                0.0
            },
            "avg_execution_time_ms": self.execution_stats.avg_execution_time,
            "cached_queries": self.query_cache.len()
        });

        serde_wasm_bindgen::to_value(&stats).unwrap_or(JsValue::NULL)
    }

    /// Clear query cache
    #[wasm_bindgen]
    pub fn clear_cache(&mut self) {
        self.query_cache.clear();
    }

    fn generate_cache_key(&self, query: &str) -> String {
        // Simple hash-based cache key (in production, use proper hashing)
        format!("query_{}", query.len())
    }

    fn optimize_query(&self, query: &str) -> String {
        // Basic query optimization (placeholder)
        query.trim().to_lowercase()
    }

    fn execute_query(&self, _query: &str) -> String {
        // Placeholder query execution
        serde_json::json!({
            "status": "success",
            "rows": [],
            "metadata": {
                "processed_by": "wasm",
                "version": "0.1.0"
            }
        }).to_string()
    }

    fn update_avg_execution_time(&mut self, execution_time: f64) {
        let total = self.execution_stats.total_queries as f64;
        let current_avg = self.execution_stats.avg_execution_time;
        self.execution_stats.avg_execution_time = 
            (current_avg * (total - 1.0) + execution_time) / total;
    }
}

/// Utility functions for JavaScript interop
#[wasm_bindgen]
pub fn greet(name: &str) -> String {
    format!("Hello, {}! FACT WASM is ready.", name)
}

/// Get WASM module information
#[wasm_bindgen]
pub fn get_wasm_info() -> JsValue {
    let info = serde_json::json!({
        "name": "fact-wasm-core",
        "version": "0.1.0",
        "features": ["performance", "cache", "query-processing"],
        "build_info": {
            "opt_level": "s",
            "lto": "fat",
            "panic": "abort"
        }
    });

    serde_wasm_bindgen::to_value(&info).unwrap_or(JsValue::NULL)
}

/// Performance benchmark function
#[wasm_bindgen]
pub fn benchmark_cache_operations(iterations: u32) -> JsValue {
    let start_time = js_sys::Date::now();
    let mut cache = FastCache::new(1000);

    // Benchmark cache insertions
    for i in 0..iterations {
        let key = format!("key_{}", i);
        let data = format!("data_value_{}", i);
        cache.set(&key, &data, 60000); // 1 minute TTL
    }

    let insert_time = js_sys::Date::now() - start_time;

    // Benchmark cache retrievals
    let retrieval_start = js_sys::Date::now();
    for i in 0..iterations {
        let key = format!("key_{}", i);
        cache.get(&key);
    }
    let retrieval_time = js_sys::Date::now() - retrieval_start;

    let benchmark_result = serde_json::json!({
        "iterations": iterations,
        "insert_time_ms": insert_time,
        "retrieval_time_ms": retrieval_time,
        "total_time_ms": insert_time + retrieval_time,
        "ops_per_second": {
            "inserts": (iterations as f64) / (insert_time / 1000.0),
            "retrievals": (iterations as f64) / (retrieval_time / 1000.0)
        }
    });

    serde_wasm_bindgen::to_value(&benchmark_result).unwrap_or(JsValue::NULL)  
}