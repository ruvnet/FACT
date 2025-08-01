//! Fast cache implementation for FACT
//! 
//! High-performance caching with LRU eviction, TTL support, and optimizations.

use wasm_bindgen::prelude::*;
use serde::{Serialize, Deserialize};
use rustc_hash::FxHashMap;
use smallvec::SmallVec;
use std::collections::VecDeque;

/// Cache entry with metadata
#[derive(Clone, Debug)]
pub struct CacheEntry {
    pub value: String,
    pub timestamp: f64,
    pub ttl: Option<u64>,
    pub access_count: u32,
    pub size: usize,
}

impl CacheEntry {
    pub fn new(value: String, ttl: Option<u64>) -> Self {
        Self {
            size: value.len(),
            value,
            timestamp: js_sys::Date::now(),
            ttl,
            access_count: 1,
        }
    }

    pub fn is_expired(&self) -> bool {
        if let Some(ttl) = self.ttl {
            js_sys::Date::now() - self.timestamp > ttl as f64
        } else {
            false
        }
    }

    pub fn access(&mut self) {
        self.access_count += 1;
        self.timestamp = js_sys::Date::now();
    }
}

/// High-performance cache statistics
#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct CacheStats {
    pub size: usize,
    pub entries: usize,
    pub capacity: usize,
    pub hit_rate: f64,
    pub miss_rate: f64,
    pub evictions: u64,
    pub expired_entries: u64,
    pub total_requests: u64,
    pub cache_hits: u64,
    pub cache_misses: u64,
}

impl Default for CacheStats {
    fn default() -> Self {
        Self {
            size: 0,
            entries: 0,
            capacity: 10 * 1024 * 1024, // 10MB default
            hit_rate: 0.0,
            miss_rate: 0.0,
            evictions: 0,
            expired_entries: 0,
            total_requests: 0,
            cache_hits: 0,
            cache_misses: 0,
        }
    }
}

/// Fast cache with LRU eviction and TTL support
#[wasm_bindgen]
pub struct FastCache {
    data: FxHashMap<String, CacheEntry>,
    access_order: VecDeque<String>,
    hot_keys: SmallVec<[String; 32]>,
    stats: CacheStats,
    max_size: usize,
    max_entries: usize,
    hot_threshold: u32,
}

#[wasm_bindgen]
impl FastCache {
    /// Create a new cache with default capacity (10MB)
    #[wasm_bindgen(constructor)]
    pub fn new() -> FastCache {
        Self::with_capacity(10 * 1024 * 1024)
    }

    /// Create a new cache with specified capacity in bytes
    #[wasm_bindgen]
    pub fn with_capacity(max_size: usize) -> FastCache {
        let max_entries = (max_size / 100).max(1000); // Estimate ~100 bytes per entry average
        
        FastCache {
            data: FxHashMap::default(),
            access_order: VecDeque::with_capacity(max_entries / 4),
            hot_keys: SmallVec::new(),
            stats: CacheStats {
                capacity: max_size,
                ..Default::default()
            },
            max_size,
            max_entries,
            hot_threshold: 5,
        }
    }

    /// Get a value from the cache
    #[wasm_bindgen]
    pub fn get(&mut self, key: &str) -> Option<String> {
        self.stats.total_requests += 1;

        // Check if key exists and is not expired
        let result = if let Some(entry) = self.data.get(key) {
            if entry.is_expired() {
                None // Will be removed below
            } else {
                Some(entry.value.clone())
            }
        } else {
            None
        };

        // Handle the result
        if let Some(value) = result {
            // Update entry access info
            if let Some(entry) = self.data.get_mut(key) {
                entry.access();
            }
            self.promote_hot_key(key);
            self.update_access_order(key);
            self.stats.cache_hits += 1;
            self.update_rates();
            Some(value)
        } else {
            // Check if expired and remove
            if let Some(entry) = self.data.get(key) {
                if entry.is_expired() {
                    self.remove_internal(key);
                    self.stats.expired_entries += 1;
                }
            }
            self.stats.cache_misses += 1;
            self.update_rates();
            None
        }
    }

    /// Set a value in the cache with optional TTL
    #[wasm_bindgen]
    pub fn set(&mut self, key: &str, value: &str, ttl_ms: u64) -> bool {
        let ttl = if ttl_ms > 0 { Some(ttl_ms) } else { None };
        self.put_with_ttl(key.to_string(), value.to_string(), ttl)
    }

    /// Put a value in the cache
    #[wasm_bindgen]
    pub fn put(&mut self, key: String, value: String) -> bool {
        self.put_with_ttl(key, value, None)
    }

    /// Remove a value from the cache
    #[wasm_bindgen]
    pub fn remove(&mut self, key: &str) -> bool {
        self.remove_internal(key)
    }

    /// Clear all entries from the cache
    #[wasm_bindgen]
    pub fn clear(&mut self) {
        self.data.clear();
        self.access_order.clear();
        self.hot_keys.clear();
        self.stats.size = 0;
        self.stats.entries = 0;
        self.stats.evictions = 0;
        self.stats.expired_entries = 0;
    }

    /// Get cache statistics as JSON string
    #[wasm_bindgen]
    pub fn get_stats(&self) -> JsValue {
        serde_wasm_bindgen::to_value(&self.stats).unwrap_or(JsValue::NULL)
    }

    /// Check if a key exists (without updating access)
    #[wasm_bindgen]
    pub fn contains(&self, key: &str) -> bool {
        if let Some(entry) = self.data.get(key) {
            !entry.is_expired()
        } else {
            false
        }
    }

    /// Get the number of entries in the cache
    #[wasm_bindgen]
    pub fn size(&self) -> usize {
        self.data.len()
    }

    /// Get memory usage in bytes
    #[wasm_bindgen]
    pub fn memory_usage(&self) -> usize {
        self.stats.size
    }

    /// Optimize cache performance
    #[wasm_bindgen]
    pub fn optimize(&mut self) {
        self.cleanup_expired();
        self.optimize_hot_keys();
    }

    /// Aggressive optimization (more expensive)
    #[wasm_bindgen]
    pub fn optimize_aggressive(&mut self) {
        self.cleanup_expired();
        self.optimize_hot_keys();
        self.defragment();
    }

    /// Memory-focused optimization
    #[wasm_bindgen]
    pub fn optimize_memory(&mut self) {
        self.cleanup_expired();
        
        // Shrink collections if they're over-allocated
        if self.data.capacity() > self.data.len() * 2 {
            self.data.shrink_to_fit();
        }
        
        self.access_order.shrink_to_fit();
    }
}

impl FastCache {
    fn put_with_ttl(&mut self, key: String, value: String, ttl: Option<u64>) -> bool {
        let entry = CacheEntry::new(value, ttl);
        let entry_size = entry.size + key.len();

        // Check capacity constraints
        if self.data.len() >= self.max_entries || 
           self.stats.size + entry_size > self.max_size {
            if !self.evict_entries(entry_size) {
                return false;
            }
        }

        // Remove existing entry if present
        self.remove_internal(&key);

        // Insert new entry
        self.stats.size += entry_size;
        self.stats.entries += 1;
        self.data.insert(key.clone(), entry);
        self.access_order.push_back(key);

        true
    }

    fn remove_internal(&mut self, key: &str) -> bool {
        if let Some(entry) = self.data.remove(key) {
            self.stats.size -= entry.size + key.len();
            self.stats.entries -= 1;

            // Remove from access order
            if let Some(pos) = self.access_order.iter().position(|k| k == key) {
                self.access_order.remove(pos);
            }

            // Remove from hot keys
            if let Some(pos) = self.hot_keys.iter().position(|k| k == key) {
                self.hot_keys.remove(pos);
            }

            true
        } else {
            false
        }
    }

    fn evict_entries(&mut self, needed_space: usize) -> bool {
        let mut freed_space = 0;
        let mut evicted_count = 0;

        // First, remove expired entries
        let expired_keys: Vec<String> = self.data
            .iter()
            .filter(|(_, entry)| entry.is_expired())
            .map(|(key, _)| key.clone())
            .collect();

        for key in expired_keys {
            if let Some(entry) = self.data.get(&key) {
                freed_space += entry.size + key.len();
            }
            self.remove_internal(&key);
            self.stats.expired_entries += 1;
        }

        // If not enough space, use LRU eviction
        while freed_space < needed_space && !self.access_order.is_empty() {
            if let Some(lru_key) = self.access_order.pop_front() {
                if let Some(entry) = self.data.get(&lru_key) {
                    freed_space += entry.size + lru_key.len();
                }
                self.remove_internal(&lru_key);
                evicted_count += 1;
            } else {
                break;
            }
        }

        self.stats.evictions += evicted_count;
        freed_space >= needed_space
    }

    fn promote_hot_key(&mut self, key: &str) {
        if let Some(entry) = self.data.get(key) {
            if entry.access_count >= self.hot_threshold && 
               !self.hot_keys.contains(&key.to_string()) &&
               self.hot_keys.len() < self.hot_keys.capacity() {
                self.hot_keys.push(key.to_string());
            }
        }
    }

    fn update_access_order(&mut self, key: &str) {
        // Remove from current position
        if let Some(pos) = self.access_order.iter().position(|k| k == key) {
            self.access_order.remove(pos);
        }
        // Add to end (most recently used)
        self.access_order.push_back(key.to_string());
    }

    fn cleanup_expired(&mut self) {
        let expired_keys: Vec<String> = self.data
            .iter()
            .filter(|(_, entry)| entry.is_expired())
            .map(|(key, _)| key.clone())
            .collect();

        for key in expired_keys {
            self.remove_internal(&key);
            self.stats.expired_entries += 1;
        }
    }

    fn optimize_hot_keys(&mut self) {
        // Remove hot keys that are no longer frequently accessed
        self.hot_keys.retain(|key| {
            if let Some(entry) = self.data.get(key) {
                entry.access_count >= self.hot_threshold
            } else {
                false
            }
        });
    }

    fn defragment(&mut self) {
        // Rebuild access order based on actual access patterns
        let mut ordered_keys: Vec<(String, f64)> = self.data
            .iter()
            .map(|(key, entry)| (key.clone(), entry.timestamp))
            .collect();

        ordered_keys.sort_by(|a, b| a.1.partial_cmp(&b.1).unwrap());
        
        self.access_order.clear();
        for (key, _) in ordered_keys {
            self.access_order.push_back(key);
        }
    }

    fn update_rates(&mut self) {
        if self.stats.total_requests > 0 {
            self.stats.hit_rate = self.stats.cache_hits as f64 / self.stats.total_requests as f64;
            self.stats.miss_rate = self.stats.cache_misses as f64 / self.stats.total_requests as f64;
        }
    }
}

impl Default for FastCache {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_cache_basic_operations() {
        let mut cache = FastCache::new();
        
        // Test put and get
        assert!(cache.put("key1".to_string(), "value1".to_string()));
        assert_eq!(cache.get("key1"), Some("value1".to_string()));
        
        // Test non-existent key
        assert_eq!(cache.get("key2"), None);
        
        // Test remove
        assert!(cache.remove("key1"));
        assert_eq!(cache.get("key1"), None);
    }

    #[test]
    fn test_cache_stats() {
        let mut cache = FastCache::new();
        cache.put("key1".to_string(), "value1".to_string());
        
        let _ = cache.get("key1"); // Hit
        let _ = cache.get("key2"); // Miss
        
        assert_eq!(cache.stats.cache_hits, 1);
        assert_eq!(cache.stats.cache_misses, 1);
        assert_eq!(cache.stats.total_requests, 2);
    }

    #[test]
    fn test_cache_capacity() {
        let mut cache = FastCache::with_capacity(100);
        
        // Fill beyond capacity
        for i in 0..50 {
            cache.put(format!("key{}", i), format!("value{}", i));
        }
        
        // Should have evicted some entries
        assert!(cache.size() <= cache.max_entries);
        assert!(cache.memory_usage() <= cache.max_size);
    }
}