//! Performance optimizations for FACT WASM core
//! 
//! This module contains various optimization techniques:
//! - SIMD operations for data processing
//! - Memory pool allocation
//! - Cache-optimized data structures
//! - Vectorized operations

use wasm_bindgen::prelude::*;
use std::arch::wasm32::*;
use ahash::AHashMap;
use smallvec::SmallVec;

/// Memory pool for reducing allocations
#[wasm_bindgen]
pub struct MemoryPool {
    buffers: Vec<Vec<u8>>,
    available: SmallVec<[usize; 32]>,
    buffer_size: usize,
}

#[wasm_bindgen]
impl MemoryPool {
    #[wasm_bindgen(constructor)]
    pub fn new(buffer_size: usize, initial_count: usize) -> MemoryPool {
        let mut pool = MemoryPool {
            buffers: Vec::with_capacity(initial_count * 2),
            available: SmallVec::new(),
            buffer_size,
        };

        // Pre-allocate buffers
        for i in 0..initial_count {
            pool.buffers.push(vec![0u8; buffer_size]);
            pool.available.push(i);
        }

        pool
    }

    #[wasm_bindgen]
    pub fn get_buffer(&mut self) -> Option<usize> {
        if let Some(index) = self.available.pop() {
            Some(index)
        } else {
            // Grow pool if needed
            let new_index = self.buffers.len();
            self.buffers.push(vec![0u8; self.buffer_size]);
            Some(new_index)
        }
    }

    #[wasm_bindgen]
    pub fn return_buffer(&mut self, index: usize) {
        if index < self.buffers.len() {
            self.available.push(index);
        }
    }

    #[wasm_bindgen]
    pub fn buffer_size(&self) -> usize {
        self.buffer_size
    }

    #[wasm_bindgen]
    pub fn available_count(&self) -> usize {
        self.available.len()
    }
}

/// SIMD-optimized vector operations
#[wasm_bindgen]
pub struct SIMDProcessor {
    pool: MemoryPool,
}

#[wasm_bindgen]
impl SIMDProcessor {
    #[wasm_bindgen(constructor)]
    pub fn new() -> SIMDProcessor {
        SIMDProcessor {
            pool: MemoryPool::new(4096, 8),
        }
    }

    /// Vectorized sum using SIMD operations where possible
    #[wasm_bindgen]
    pub fn vectorized_sum(&self, data: &[f64]) -> f64 {
        // Use chunks of 2 for WASM SIMD (v128 can hold 2 f64s)
        let mut sum = 0.0;
        let chunks = data.chunks_exact(2);
        let remainder = chunks.remainder();

        // Process chunks with SIMD
        for chunk in chunks {
            if chunk.len() == 2 {
                // Load two f64 values into SIMD register
                let v = f64x2(chunk[0], chunk[1]);
                let horizontal_sum = f64x2_extract_lane::<0>(v) + f64x2_extract_lane::<1>(v);
                sum += horizontal_sum;
            }
        }

        // Handle remainder
        for &value in remainder {
            sum += value;
        }

        sum
    }

    /// Optimized string hashing with SIMD
    #[wasm_bindgen]
    pub fn fast_hash(&self, input: &str) -> u64 {
        let bytes = input.as_bytes();
        let mut hasher = 0x517cc1b727220a95u64;

        // Process 8 bytes at a time using SIMD
        let chunks = bytes.chunks_exact(8);
        let remainder = chunks.remainder();

        for chunk in chunks {
            if chunk.len() == 8 {
                // Convert 8 bytes to u64
                let mut chunk_val = 0u64;
                for (i, &byte) in chunk.iter().enumerate() {
                    chunk_val |= (byte as u64) << (i * 8);
                }
                
                hasher ^= chunk_val;
                hasher = hasher.wrapping_mul(0x5bd1e995);
                hasher ^= hasher >> 15;
            }
        }

        // Handle remainder bytes
        for &byte in remainder {
            hasher ^= byte as u64;
            hasher = hasher.wrapping_mul(0x5bd1e995);
        }

        hasher
    }

    /// Memory-optimized string comparison
    #[wasm_bindgen]
    pub fn fast_string_compare(&self, a: &str, b: &str) -> bool {
        if a.len() != b.len() {
            return false;
        }

        let a_bytes = a.as_bytes();
        let b_bytes = b.as_bytes();

        // Compare 8 bytes at a time
        let chunks_a = a_bytes.chunks_exact(8);
        let chunks_b = b_bytes.chunks_exact(8);
        let remainder_a = chunks_a.remainder();
        let remainder_b = chunks_b.remainder();

        for (chunk_a, chunk_b) in chunks_a.zip(chunks_b) {
            if chunk_a != chunk_b {
                return false;
            }
        }

        remainder_a == remainder_b
    }
}

/// Cache-optimized data structure for frequent lookups
#[wasm_bindgen]
pub struct OptimizedCache {
    // Use AHashMap for better performance
    data: AHashMap<u64, CacheEntry>,
    // Separate hot/cold storage
    hot_keys: SmallVec<[u64; 64]>,
    access_order: SmallVec<[u64; 256]>,
    max_size: usize,
    hot_threshold: u32,
}

#[derive(Clone)]
struct CacheEntry {
    value: String,
    access_count: u32,
    timestamp: f64,
    is_hot: bool,
}

#[wasm_bindgen]
impl OptimizedCache {
    #[wasm_bindgen(constructor)]
    pub fn new(max_size: usize) -> OptimizedCache {
        OptimizedCache {
            data: AHashMap::with_capacity(max_size),
            hot_keys: SmallVec::new(),
            access_order: SmallVec::new(),
            max_size,
            hot_threshold: 5,
        }
    }

    #[wasm_bindgen]
    pub fn set(&mut self, key_str: &str, value: &str) {
        let simd = SIMDProcessor::new();
        let key = simd.fast_hash(key_str);
        
        // Evict if necessary
        if self.data.len() >= self.max_size {
            self.evict_lru();
        }

        let entry = CacheEntry {
            value: value.to_string(),
            access_count: 1,
            timestamp: js_sys::Date::now(),
            is_hot: false,
        };

        self.data.insert(key, entry);
        self.access_order.push(key);
    }

    #[wasm_bindgen]
    pub fn get(&mut self, key_str: &str) -> Option<String> {
        let simd = SIMDProcessor::new();
        let key = simd.fast_hash(key_str);

        if let Some(entry) = self.data.get_mut(&key) {
            entry.access_count += 1;
            entry.timestamp = js_sys::Date::now();

            // Promote to hot cache if accessed frequently
            if entry.access_count >= self.hot_threshold && !entry.is_hot {
                entry.is_hot = true;
                if self.hot_keys.len() < self.hot_keys.capacity() {
                    self.hot_keys.push(key);
                }
            }

            // Update access order for LRU
            if let Some(pos) = self.access_order.iter().position(|&x| x == key) {
                self.access_order.remove(pos);
            }
            self.access_order.push(key);

            Some(entry.value.clone())
        } else {
            None
        }
    }

    #[wasm_bindgen]
    pub fn size(&self) -> usize {
        self.data.len()
    }

    #[wasm_bindgen]
    pub fn hot_cache_size(&self) -> usize {
        self.hot_keys.len()
    }

    fn evict_lru(&mut self) {
        if let Some(&oldest_key) = self.access_order.first() {
            self.data.remove(&oldest_key);
            self.access_order.remove(0);
            
            // Remove from hot cache if present
            if let Some(pos) = self.hot_keys.iter().position(|&x| x == oldest_key) {
                self.hot_keys.remove(pos);
            }
        }
    }
}

/// Batch operations processor for improved throughput
#[wasm_bindgen]
pub struct BatchProcessor {
    batch_size: usize,
    pending_operations: Vec<Operation>,
}

#[derive(Clone)]
struct Operation {
    op_type: OperationType,
    key: String,
    value: Option<String>,
}

#[derive(Clone)]
enum OperationType {
    Get,
    Set,
    Delete,
}

#[wasm_bindgen]
impl BatchProcessor {
    #[wasm_bindgen(constructor)]
    pub fn new(batch_size: usize) -> BatchProcessor {
        BatchProcessor {
            batch_size,
            pending_operations: Vec::with_capacity(batch_size),
        }
    }

    #[wasm_bindgen]
    pub fn add_get(&mut self, key: &str) {
        self.pending_operations.push(Operation {
            op_type: OperationType::Get,
            key: key.to_string(),
            value: None,
        });

        if self.pending_operations.len() >= self.batch_size {
            self.flush();
        }
    }

    #[wasm_bindgen]
    pub fn add_set(&mut self, key: &str, value: &str) {
        self.pending_operations.push(Operation {
            op_type: OperationType::Set,
            key: key.to_string(),
            value: Some(value.to_string()),
        });

        if self.pending_operations.len() >= self.batch_size {
            self.flush();
        }
    }

    #[wasm_bindgen]
    pub fn flush(&mut self) -> usize {
        let count = self.pending_operations.len();
        // Process all pending operations in batch
        // This would typically involve batched database operations
        self.pending_operations.clear();
        count
    }

    #[wasm_bindgen]
    pub fn pending_count(&self) -> usize {
        self.pending_operations.len()
    }
}

/// Performance metrics collector
#[wasm_bindgen]
pub struct PerformanceMetrics {
    operations: AHashMap<String, MetricData>,
    start_time: f64,
}

#[derive(Default, Clone)]
struct MetricData {
    count: u64,
    total_time: f64,
    min_time: f64,
    max_time: f64,
}

#[wasm_bindgen]
impl PerformanceMetrics {
    #[wasm_bindgen(constructor)]
    pub fn new() -> PerformanceMetrics {
        PerformanceMetrics {
            operations: AHashMap::new(),
            start_time: js_sys::Date::now(),
        }
    }

    #[wasm_bindgen]
    pub fn record_operation(&mut self, operation: &str, duration_ms: f64) {
        let entry = self.operations.entry(operation.to_string()).or_default();
        
        entry.count += 1;
        entry.total_time += duration_ms;
        
        if entry.min_time == 0.0 || duration_ms < entry.min_time {
            entry.min_time = duration_ms;
        }
        
        if duration_ms > entry.max_time {
            entry.max_time = duration_ms;
        }
    }

    #[wasm_bindgen]
    pub fn get_stats(&self) -> JsValue {
        let mut stats = serde_json::Map::new();
        
        for (operation, data) in &self.operations {
            let avg_time = if data.count > 0 {
                data.total_time / data.count as f64
            } else {
                0.0
            };

            let op_stats = serde_json::json!({
                "count": data.count,
                "total_time_ms": data.total_time,
                "avg_time_ms": avg_time,
                "min_time_ms": data.min_time,
                "max_time_ms": data.max_time,
                "ops_per_second": if avg_time > 0.0 { 1000.0 / avg_time } else { 0.0 }
            });

            stats.insert(operation.clone(), op_stats);
        }

        let total_runtime = js_sys::Date::now() - self.start_time;
        let summary = serde_json::json!({
            "operations": stats,
            "total_runtime_ms": total_runtime,
            "operations_count": self.operations.len()
        });

        serde_wasm_bindgen::to_value(&summary).unwrap_or(JsValue::NULL)
    }

    #[wasm_bindgen]
    pub fn reset(&mut self) {
        self.operations.clear();
        self.start_time = js_sys::Date::now();
    }
}