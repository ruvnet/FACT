//! High-performance caching implementation for FACT

use ahash::AHashMap;
use parking_lot::RwLock;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use std::time::Instant;

/// Statistics for cache performance
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CacheStats {
    pub entries: usize,
    pub size_bytes: usize,
    pub hits: u64,
    pub misses: u64,
    pub evictions: u64,
    pub hit_rate: f64,
}

/// Entry in the cache
#[derive(Debug, Clone)]
struct CacheEntry {
    value: serde_json::Value,
    size: usize,
    created_at: Instant,
    last_accessed: Instant,
    access_count: u64,
}

/// High-performance cache with LRU eviction
pub struct Cache {
    entries: AHashMap<String, CacheEntry>,
    max_size: usize,
    current_size: usize,
    hits: u64,
    misses: u64,
    evictions: u64,
}

impl Cache {
    /// Create a new cache with default size (100MB)
    pub fn new() -> Self {
        Self::with_capacity(100 * 1024 * 1024)
    }
    
    /// Create a new cache with specified capacity
    pub fn with_capacity(max_size: usize) -> Self {
        Self {
            entries: AHashMap::new(),
            max_size,
            current_size: 0,
            hits: 0,
            misses: 0,
            evictions: 0,
        }
    }
    
    /// Get a value from the cache
    pub fn get(&mut self, key: &str) -> Option<serde_json::Value> {
        if let Some(entry) = self.entries.get_mut(key) {
            entry.last_accessed = Instant::now();
            entry.access_count += 1;
            self.hits += 1;
            Some(entry.value.clone())
        } else {
            self.misses += 1;
            None
        }
    }
    
    /// Put a value in the cache
    pub fn put(&mut self, key: String, value: serde_json::Value) {
        let size = estimate_size(&value);
        
        // Evict entries if needed
        while self.current_size + size > self.max_size && !self.entries.is_empty() {
            self.evict_lru();
        }
        
        let entry = CacheEntry {
            value,
            size,
            created_at: Instant::now(),
            last_accessed: Instant::now(),
            access_count: 1,
        };
        
        // Remove old entry if exists
        if let Some(old_entry) = self.entries.remove(&key) {
            self.current_size -= old_entry.size;
        }
        
        self.current_size += size;
        self.entries.insert(key, entry);
    }
    
    /// Clear all entries from the cache
    pub fn clear(&mut self) {
        self.entries.clear();
        self.current_size = 0;
        self.hits = 0;
        self.misses = 0;
        self.evictions = 0;
    }
    
    /// Get cache statistics
    pub fn stats(&self) -> CacheStats {
        let total = self.hits + self.misses;
        let hit_rate = if total > 0 {
            self.hits as f64 / total as f64
        } else {
            0.0
        };
        
        CacheStats {
            entries: self.entries.len(),
            size_bytes: self.current_size,
            hits: self.hits,
            misses: self.misses,
            evictions: self.evictions,
            hit_rate,
        }
    }
    
    /// Evict the least recently used entry
    fn evict_lru(&mut self) {
        if let Some((key, _)) = self
            .entries
            .iter()
            .min_by_key(|(_, entry)| entry.last_accessed)
            .map(|(k, v)| (k.clone(), v.clone()))
        {
            if let Some(entry) = self.entries.remove(&key) {
                self.current_size -= entry.size;
                self.evictions += 1;
            }
        }
    }
}

impl Default for Cache {
    fn default() -> Self {
        Self::new()
    }
}

/// Estimate the memory size of a JSON value
fn estimate_size(value: &serde_json::Value) -> usize {
    match value {
        serde_json::Value::Null => 8,
        serde_json::Value::Bool(_) => 8,
        serde_json::Value::Number(_) => 16,
        serde_json::Value::String(s) => 24 + s.len() * 2,
        serde_json::Value::Array(arr) => {
            24 + arr.iter().map(estimate_size).sum::<usize>()
        }
        serde_json::Value::Object(map) => {
            24 + map
                .iter()
                .map(|(k, v)| 24 + k.len() * 2 + estimate_size(v))
                .sum::<usize>()
        }
    }
}

/// Thread-safe cache wrapper
pub struct ThreadSafeCache {
    inner: Arc<RwLock<Cache>>,
}

impl ThreadSafeCache {
    pub fn new() -> Self {
        Self {
            inner: Arc::new(RwLock::new(Cache::new())),
        }
    }
    
    pub fn get(&self, key: &str) -> Option<serde_json::Value> {
        self.inner.write().get(key)
    }
    
    pub fn put(&self, key: String, value: serde_json::Value) {
        self.inner.write().put(key, value);
    }
    
    pub fn stats(&self) -> CacheStats {
        self.inner.read().stats()
    }
    
    pub fn clear(&self) {
        self.inner.write().clear();
    }
}

impl Default for ThreadSafeCache {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_cache_basic_operations() {
        let mut cache = Cache::with_capacity(1024);
        
        // Test put and get
        cache.put("key1".to_string(), serde_json::json!({"test": "value"}));
        assert!(cache.get("key1").is_some());
        assert!(cache.get("key2").is_none());
        
        // Check stats
        let stats = cache.stats();
        assert_eq!(stats.entries, 1);
        assert_eq!(stats.hits, 1);
        assert_eq!(stats.misses, 1);
    }
    
    #[test]
    fn test_cache_eviction() {
        let mut cache = Cache::with_capacity(100); // Very small cache
        
        // Fill cache with entries
        for i in 0..10 {
            cache.put(
                format!("key{}", i),
                serde_json::json!({"data": format!("value{}", i)}),
            );
        }
        
        // Should have evicted some entries
        assert!(cache.entries.len() < 10);
        assert!(cache.evictions > 0);
    }
}