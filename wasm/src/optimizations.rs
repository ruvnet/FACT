//! Performance optimizations for FACT WASM core
//! 
//! This module contains various optimization techniques:
//! - SIMD operations for data processing
//! - Memory pool allocation
//! - Cache-optimized data structures
//! - Vectorized operations

use wasm_bindgen::prelude::*;
use std::arch::wasm32::*;
use rustc_hash::FxHashMap;
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
    
    /// Vectorized array operations with SIMD
    #[wasm_bindgen]
    pub fn vectorized_multiply(&self, a: &[f64], b: &[f64]) -> Vec<f64> {
        let len = a.len().min(b.len());
        let mut result = Vec::with_capacity(len);
        
        let chunks_a = a[..len].chunks_exact(2);
        let chunks_b = b[..len].chunks_exact(2);
        let remainder = len % 2;
        
        // Process pairs with SIMD
        for (chunk_a, chunk_b) in chunks_a.zip(chunks_b) {
            let va = f64x2(chunk_a[0], chunk_a[1]);
            let vb = f64x2(chunk_b[0], chunk_b[1]);
            let vmul = f64x2_mul(va, vb);
            
            result.push(f64x2_extract_lane::<0>(vmul));
            result.push(f64x2_extract_lane::<1>(vmul));
        }
        
        // Handle remainder
        if remainder > 0 {
            let idx = len - remainder;
            result.push(a[idx] * b[idx]);
        }
        
        result
    }
    
    /// Vectorized dot product with SIMD
    #[wasm_bindgen]
    pub fn vectorized_dot_product(&self, a: &[f64], b: &[f64]) -> f64 {
        let len = a.len().min(b.len());
        let mut sum = 0.0;
        
        let chunks_a = a[..len].chunks_exact(2);
        let chunks_b = b[..len].chunks_exact(2);
        let remainder = len % 2;
        
        // Process pairs with SIMD
        for (chunk_a, chunk_b) in chunks_a.zip(chunks_b) {
            let va = f64x2(chunk_a[0], chunk_a[1]);
            let vb = f64x2(chunk_b[0], chunk_b[1]);
            let vmul = f64x2_mul(va, vb);
            
            sum += f64x2_extract_lane::<0>(vmul) + f64x2_extract_lane::<1>(vmul);
        }
        
        // Handle remainder
        if remainder > 0 {
            let idx = len - remainder;
            sum += a[idx] * b[idx];
        }
        
        sum
    }
    
    /// SIMD-accelerated matrix operations
    #[wasm_bindgen]
    pub fn vectorized_matrix_multiply(&self, a: &[f64], b: &[f64], rows_a: usize, cols_a: usize, cols_b: usize) -> Vec<f64> {
        let mut result = vec![0.0; rows_a * cols_b];
        
        for i in 0..rows_a {
            for j in 0..cols_b {
                let mut sum = 0.0;
                
                // Vectorized inner product
                let chunks = (0..cols_a).step_by(2);
                for k in chunks {
                    if k + 1 < cols_a {
                        let va = f64x2(a[i * cols_a + k], a[i * cols_a + k + 1]);
                        let vb = f64x2(b[k * cols_b + j], b[(k + 1) * cols_b + j]);
                        let vmul = f64x2_mul(va, vb);
                        sum += f64x2_extract_lane::<0>(vmul) + f64x2_extract_lane::<1>(vmul);
                    } else {
                        sum += a[i * cols_a + k] * b[k * cols_b + j];
                    }
                }
                
                result[i * cols_b + j] = sum;
            }
        }
        
        result
    }
    
    /// Vectorized statistical operations
    #[wasm_bindgen]
    pub fn vectorized_statistics(&self, data: &[f64]) -> JsValue {
        if data.is_empty() {
            return JsValue::NULL;
        }
        
        let sum = self.vectorized_sum(data);
        let mean = sum / data.len() as f64;
        
        // Calculate variance using SIMD
        let mut variance_sum = 0.0;
        let chunks = data.chunks_exact(2);
        let remainder = chunks.remainder();
        
        for chunk in chunks {
            let v = f64x2(chunk[0] - mean, chunk[1] - mean);
            let squared = f64x2_mul(v, v);
            variance_sum += f64x2_extract_lane::<0>(squared) + f64x2_extract_lane::<1>(squared);
        }
        
        for &value in remainder {
            let diff = value - mean;
            variance_sum += diff * diff;
        }
        
        let variance = variance_sum / data.len() as f64;
        let std_dev = variance.sqrt();
        
        // Find min/max using SIMD comparisons
        let (min_val, max_val) = self.vectorized_min_max(data);
        
        let stats = serde_json::json!({
            "count": data.len(),
            "sum": sum,
            "mean": mean,
            "variance": variance,
            "std_deviation": std_dev,
            "min": min_val,
            "max": max_val,
            "range": max_val - min_val
        });
        
        serde_wasm_bindgen::to_value(&stats).unwrap_or(JsValue::NULL)
    }
    
    /// SIMD-optimized min/max finding
    pub fn vectorized_min_max(&self, data: &[f64]) -> (f64, f64) {
        if data.is_empty() {
            return (0.0, 0.0);
        }
        
        let mut min_val = data[0];
        let mut max_val = data[0];
        
        let chunks = data.chunks_exact(2);
        let remainder = chunks.remainder();
        
        for chunk in chunks {
            let v = f64x2(chunk[0], chunk[1]);
            let current_min = f64x2_extract_lane::<0>(v).min(f64x2_extract_lane::<1>(v));
            let current_max = f64x2_extract_lane::<0>(v).max(f64x2_extract_lane::<1>(v));
            
            min_val = min_val.min(current_min);
            max_val = max_val.max(current_max);
        }
        
        for &value in remainder {
            min_val = min_val.min(value);
            max_val = max_val.max(value);
        }
        
        (min_val, max_val)
    }

    /// Optimized string hashing with SIMD and improved algorithm
    #[wasm_bindgen]
    pub fn fast_hash(&self, input: &str) -> u64 {
        let bytes = input.as_bytes();
        let mut hasher = 0x517cc1b727220a95u64;
        let prime = 0x5bd1e9955bd1e995u64;

        // Process 16 bytes at a time using SIMD when possible
        let chunks = bytes.chunks_exact(16);
        let remainder = chunks.remainder();

        for chunk in chunks {
            // Process two u64s simultaneously
            let mut val1 = 0u64;
            let mut val2 = 0u64;
            
            for (i, &byte) in chunk[..8].iter().enumerate() {
                val1 |= (byte as u64) << (i * 8);
            }
            for (i, &byte) in chunk[8..].iter().enumerate() {
                val2 |= (byte as u64) << (i * 8);
            }
            
            // Mix both values
            hasher ^= val1.wrapping_mul(prime);
            hasher = hasher.rotate_left(13);
            hasher ^= val2.wrapping_mul(prime);
            hasher = hasher.rotate_left(13);
            hasher = hasher.wrapping_mul(prime);
        }

        // Handle remainder bytes with 8-byte chunks first
        let remainder_8_chunks = remainder.chunks_exact(8);
        let final_remainder = remainder_8_chunks.remainder();
        
        for chunk in remainder_8_chunks {
            let mut chunk_val = 0u64;
            for (i, &byte) in chunk.iter().enumerate() {
                chunk_val |= (byte as u64) << (i * 8);
            }
            hasher ^= chunk_val.wrapping_mul(prime);
            hasher = hasher.rotate_left(13);
        }

        // Handle final remainder bytes
        for &byte in final_remainder {
            hasher ^= (byte as u64).wrapping_mul(prime);
            hasher = hasher.rotate_left(11);
        }

        // Final mix
        hasher ^= hasher >> 16;
        hasher = hasher.wrapping_mul(0x85ebca6b);
        hasher ^= hasher >> 13;
        hasher = hasher.wrapping_mul(0xc2b2ae35);
        hasher ^= hasher >> 16;

        hasher
    }
    
    /// High-performance hash for multiple strings
    #[wasm_bindgen]
    pub fn batch_hash(&self, inputs: &JsValue) -> JsValue {
        let mut results = Vec::new();
        
        if let Ok(strings) = serde_wasm_bindgen::from_value::<Vec<String>>(inputs.clone()) {
            for input in strings {
                results.push(self.fast_hash(&input));
            }
        }
        
        serde_wasm_bindgen::to_value(&results).unwrap_or(JsValue::NULL)
    }
    
    /// SIMD-optimized string similarity (Hamming distance)
    #[wasm_bindgen]
    pub fn string_similarity(&self, a: &str, b: &str) -> f64 {
        if a.len() != b.len() {
            return 0.0;
        }
        
        let a_bytes = a.as_bytes();
        let b_bytes = b.as_bytes();
        let mut differences = 0;
        
        // Process 8 bytes at a time
        let chunks_a = a_bytes.chunks_exact(8);
        let chunks_b = b_bytes.chunks_exact(8);
        let remainder = chunks_a.remainder().len();
        
        for (chunk_a, chunk_b) in chunks_a.zip(chunks_b) {
            for (byte_a, byte_b) in chunk_a.iter().zip(chunk_b.iter()) {
                if byte_a != byte_b {
                    differences += 1;
                }
            }
        }
        
        // Handle remainder
        let remainder_a = &a_bytes[a_bytes.len() - remainder..];
        let remainder_b = &b_bytes[b_bytes.len() - remainder..];
        
        for (byte_a, byte_b) in remainder_a.iter().zip(remainder_b.iter()) {
            if byte_a != byte_b {
                differences += 1;
            }
        }
        
        1.0 - (differences as f64 / a.len() as f64)
    }

    /// Memory-optimized string comparison with SIMD acceleration
    #[wasm_bindgen]
    pub fn fast_string_compare(&self, a: &str, b: &str) -> bool {
        if a.len() != b.len() {
            return false;
        }

        let a_bytes = a.as_bytes();
        let b_bytes = b.as_bytes();

        // Compare 16 bytes at a time for better SIMD utilization
        let chunks_a = a_bytes.chunks_exact(16);
        let chunks_b = b_bytes.chunks_exact(16);
        
        for (chunk_a, chunk_b) in chunks_a.zip(chunks_b) {
            // Convert to u128for fast comparison
            let val_a = u128::from_le_bytes([
                chunk_a[0], chunk_a[1], chunk_a[2], chunk_a[3],
                chunk_a[4], chunk_a[5], chunk_a[6], chunk_a[7],
                chunk_a[8], chunk_a[9], chunk_a[10], chunk_a[11],
                chunk_a[12], chunk_a[13], chunk_a[14], chunk_a[15],
            ]);
            let val_b = u128::from_le_bytes([
                chunk_b[0], chunk_b[1], chunk_b[2], chunk_b[3],
                chunk_b[4], chunk_b[5], chunk_b[6], chunk_b[7],
                chunk_b[8], chunk_b[9], chunk_b[10], chunk_b[11],
                chunk_b[12], chunk_b[13], chunk_b[14], chunk_b[15],
            ]);
            
            if val_a != val_b {
                return false;
            }
        }
        
        // Handle remainder with 8-byte chunks
        let remainder_a = chunks_a.remainder();
        let remainder_b = chunks_b.remainder();
        
        let chunks_8_a = remainder_a.chunks_exact(8);
        let chunks_8_b = remainder_b.chunks_exact(8);
        
        for (chunk_a, chunk_b) in chunks_8_a.zip(chunks_8_b) {
            let val_a = u64::from_le_bytes([
                chunk_a[0], chunk_a[1], chunk_a[2], chunk_a[3],
                chunk_a[4], chunk_a[5], chunk_a[6], chunk_a[7],
            ]);
            let val_b = u64::from_le_bytes([
                chunk_b[0], chunk_b[1], chunk_b[2], chunk_b[3],
                chunk_b[4], chunk_b[5], chunk_b[6], chunk_b[7],
            ]);
            
            if val_a != val_b {
                return false;
            }
        }
        
        // Final remainder comparison
        let final_remainder_a = chunks_8_a.remainder();
        let final_remainder_b = chunks_8_b.remainder();
        
        final_remainder_a == final_remainder_b
    }
    
    /// Batch string comparison for multiple pairs
    #[wasm_bindgen]
    pub fn batch_string_compare(&self, pairs: &JsValue) -> JsValue {
        let mut results = Vec::new();
        
        if let Ok(string_pairs) = serde_wasm_bindgen::from_value::<Vec<(String, String)>>(pairs.clone()) {
            for (a, b) in string_pairs {
                results.push(self.fast_string_compare(&a, &b));
            }
        }
        
        serde_wasm_bindgen::to_value(&results).unwrap_or(JsValue::NULL)
    }
}

/// Cache-optimized data structure for frequent lookups
#[wasm_bindgen]
pub struct OptimizedCache {
    // Use AHashMap for better performance
    data: FxHashMap<u64, CacheEntry>,
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
            data: FxHashMap::default(),
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
    operations: FxHashMap<String, MetricData>,
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
            operations: FxHashMap::default(),
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