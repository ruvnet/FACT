//! Fast cache implementation for FACT
//! 
//! High-performance caching with LRU eviction, TTL support, and optimizations.

use wasm_bindgen::prelude::*;
use serde::{Serialize, Deserialize};
use rustc_hash::FxHashMap;
use smallvec::SmallVec;
use std::collections::{VecDeque, HashMap};

/// Cache priority levels
#[derive(Clone, Copy, Debug, PartialEq, PartialOrd, Eq, Ord)]
enum CachePriority {
    Critical,
    High,
    Medium,
    Low,
    Disposable,
}

/// Access pattern tracking
#[derive(Clone, Debug)]
struct AccessPattern {
    frequency_score: f64,
    recency_score: f64,
    seasonal_pattern: bool,
    burst_access: bool,
    access_intervals: SmallVec<[f64; 8]>,
}

/// Access pattern statistics
#[derive(Serialize, Deserialize, Debug, Clone, Default)]
struct AccessPatternStats {
    avg_interval: f64,
    peak_hours: Vec<u8>,
    pattern_type: String,
}

/// Cache entry with metadata
#[derive(Clone, Debug)]
pub struct CacheEntry {
    pub value: String,
    pub timestamp: f64,
    pub ttl: Option<u64>,
    pub access_count: u32,
    pub size: usize,
    pub priority: CachePriority,
    pub tags: SmallVec<[String; 4]>,
    pub compression_ratio: f32,
    pub last_modified: f64,
    pub access_pattern: AccessPattern,
    pub validation_hash: u64,
}

impl CacheEntry {
    pub fn new(value: String, ttl: Option<u64>) -> Self {
        use std::collections::hash_map::DefaultHasher;
        use std::hash::{Hash, Hasher};
        
        let mut hasher = DefaultHasher::new();
        value.hash(&mut hasher);
        let hash = hasher.finish();
        
        Self {
            size: value.len(),
            value,
            timestamp: js_sys::Date::now(),
            ttl,
            access_count: 1,
            priority: CachePriority::Medium,
            tags: SmallVec::new(),
            compression_ratio: 1.0,
            last_modified: js_sys::Date::now(),
            access_pattern: AccessPattern {
                frequency_score: 1.0,
                recency_score: 1.0,
                seasonal_pattern: false,
                burst_access: false,
                access_intervals: SmallVec::new(),
            },
            validation_hash: hash,
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
    pub compression_savings: u64,
    pub memory_efficiency: f64,
    pub avg_access_time_ms: f64,
    pub hot_entries: u64,
    pub cold_entries: u64,
    pub fragmentation_ratio: f64,
    pub gc_runs: u64,
    pub gc_time_ms: f64,
    pub priority_distribution: HashMap<String, u64>,
    pub access_pattern_stats: AccessPatternStats,
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
            compression_savings: 0,
            memory_efficiency: 0.0,
            avg_access_time_ms: 0.0,
            hot_entries: 0,
            cold_entries: 0,
            fragmentation_ratio: 0.0,
            gc_runs: 0,
            gc_time_ms: 0.0,
            priority_distribution: HashMap::new(),
            access_pattern_stats: AccessPatternStats::default(),
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

    /// Set a value in the cache with optional TTL and priority
    #[wasm_bindgen]
    pub fn set(&mut self, key: &str, value: &str, ttl_ms: u64) -> bool {
        let ttl = if ttl_ms > 0 { Some(ttl_ms) } else { None };
        self.put_with_ttl_and_priority(key.to_string(), value.to_string(), ttl, CachePriority::Medium)
    }
    
    /// Set a value with custom priority
    #[wasm_bindgen]
    pub fn set_with_priority(&mut self, key: &str, value: &str, ttl_ms: u64, priority: u8) -> bool {
        let ttl = if ttl_ms > 0 { Some(ttl_ms) } else { None };
        let cache_priority = match priority {
            4 => CachePriority::Critical,
            3 => CachePriority::High,
            2 => CachePriority::Medium,
            1 => CachePriority::Low,
            _ => CachePriority::Disposable,
        };
        self.put_with_ttl_and_priority(key.to_string(), value.to_string(), ttl, cache_priority)
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

    /// Memory-focused optimization with garbage collection
    #[wasm_bindgen]
    pub fn optimize_memory(&mut self) {
        let gc_start = js_sys::Date::now();
        
        self.cleanup_expired();
        self.compress_entries();
        self.defragment_advanced();
        
        // Shrink collections if they're over-allocated
        if self.data.capacity() > self.data.len() * 2 {
            self.data.shrink_to_fit();
        }
        
        self.access_order.shrink_to_fit();
        self.hot_keys.shrink_to_fit();
        
        let gc_time = js_sys::Date::now() - gc_start;
        self.stats.gc_runs += 1;
        self.stats.gc_time_ms += gc_time;
        
        // Update fragmentation ratio
        self.update_fragmentation_ratio();
    }
    
    /// Advanced batch operations for better performance
    #[wasm_bindgen]
    pub fn batch_set(&mut self, keys_values: &JsValue) -> u32 {
        let mut inserted = 0;
        
        if let Ok(batch) = serde_wasm_bindgen::from_value::<Vec<(String, String, Option<u64>)>>(keys_values.clone()) {
            for (key, value, ttl) in batch {
                if self.put_with_ttl_and_priority(key, value, ttl, CachePriority::Medium) {
                    inserted += 1;
                }
            }
        }
        
        inserted
    }
    
    /// Batch get operations
    #[wasm_bindgen]
    pub fn batch_get(&mut self, keys: &JsValue) -> JsValue {
        let mut results = HashMap::new();
        
        if let Ok(key_list) = serde_wasm_bindgen::from_value::<Vec<String>>(keys.clone()) {
            for key in key_list {
                if let Some(value) = self.get(&key) {
                    results.insert(key, value);
                }
            }
        }
        
        serde_wasm_bindgen::to_value(&results).unwrap_or(JsValue::NULL)
    }
    
    /// Get cache health metrics
    #[wasm_bindgen]
    pub fn get_health_metrics(&self) -> JsValue {
        let health = serde_json::json!({
            "overall_health": self.calculate_health_score(),
            "memory_pressure": self.calculate_memory_pressure(),
            "hit_rate_health": if self.stats.hit_rate > 0.8 { "excellent" } else if self.stats.hit_rate > 0.6 { "good" } else { "poor" },
            "fragmentation_health": if self.stats.fragmentation_ratio < 0.2 { "excellent" } else if self.stats.fragmentation_ratio < 0.4 { "good" } else { "poor" },
            "recommendations": self.generate_recommendations()
        });
        
        serde_wasm_bindgen::to_value(&health).unwrap_or(JsValue::NULL)
    }
}

impl FastCache {
    // Add missing method implementations to prevent compilation errors
    fn put_with_ttl_and_priority(&mut self, key: String, value: String, ttl: Option<u64>, priority: CachePriority) -> bool {
        // Compress value if beneficial
        let (compressed_value, compression_ratio) = Self::maybe_compress(&value);
        let entry = self.create_enhanced_entry(compressed_value, ttl, priority, compression_ratio);
        let entry_size = entry.size + key.len();

        // Check capacity constraints
        if self.data.len() >= self.max_entries || 
           self.stats.size + entry_size > self.max_size {
            if !self.evict_entries_intelligent(entry_size, &priority) {
                return false;
            }
        }

        // Remove existing entry if present
        self.remove_internal(&key);

        // Insert new entry
        self.stats.size += entry_size;
        self.stats.entries += 1;
        self.data.insert(key.clone(), entry);
        self.access_order.push_back(key.clone());
        
        // Update priority distribution stats
        let priority_key = format!("{:?}", priority);
        *self.stats.priority_distribution.entry(priority_key).or_insert(0) += 1;

        true
    }
    
    fn create_enhanced_entry(&self, value: String, ttl: Option<u64>, priority: CachePriority, compression_ratio: f32) -> CacheEntry {
        CacheEntry {
            size: value.len(),
            value: value.clone(),
            timestamp: js_sys::Date::now(),
            ttl,
            access_count: 1,
            priority,
            tags: SmallVec::new(),
            compression_ratio,
            last_modified: js_sys::Date::now(),
            access_pattern: AccessPattern {
                frequency_score: 1.0,
                recency_score: 1.0,
                seasonal_pattern: false,
                burst_access: false,
                access_intervals: SmallVec::new(),
            },
            validation_hash: self.calculate_hash(&value),
        }
    }
    
    fn maybe_compress(value: &str) -> (String, f32) {
        // Simple compression heuristic - in a real implementation, use proper compression
        if value.len() > 1000 {
            // Simulate compression by removing redundant whitespace
            let compressed = value.split_whitespace().collect::<Vec<_>>().join(" ");
            let ratio = compressed.len() as f32 / value.len() as f32;
            (compressed, ratio)
        } else {
            (value.to_string(), 1.0)
        }
    }
    
    fn calculate_hash(&self, value: &str) -> u64 {
        use std::collections::hash_map::DefaultHasher;
        use std::hash::{Hash, Hasher};
        
        let mut hasher = DefaultHasher::new();
        value.hash(&mut hasher);
        hasher.finish()
    }
    
    fn evict_entries_intelligent(&mut self, needed_space: usize, incoming_priority: &CachePriority) -> bool {
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
                self.stats.compression_savings += (entry.size as f32 * (1.0 - entry.compression_ratio)) as u64;
            }
            self.remove_internal(&key);
            self.stats.expired_entries += 1;
        }

        // If not enough space, use intelligent eviction based on priority and access patterns
        let mut eviction_candidates: Vec<(String, f64)> = self.data
            .iter()
            .filter(|(_, entry)| entry.priority < *incoming_priority || 
                   (entry.priority == *incoming_priority && entry.access_count < 2))
            .map(|(key, entry)| {
                let eviction_score = self.calculate_eviction_score(entry);
                (key.clone(), eviction_score)
            })
            .collect();
        
        // Sort by eviction score (higher score = more likely to evict)
        eviction_candidates.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap());
        
        for (key, _) in eviction_candidates {
            if freed_space >= needed_space {
                break;
            }
            
            if let Some(entry) = self.data.get(&key) {
                freed_space += entry.size + key.len();
                self.stats.compression_savings += (entry.size as f32 * (1.0 - entry.compression_ratio)) as u64;
            }
            self.remove_internal(&key);
            evicted_count += 1;
        }
        
        // Fallback to LRU if still not enough space
        while freed_space < needed_space && !self.access_order.is_empty() {
            if let Some(lru_key) = self.access_order.pop_front() {
                if let Some(entry) = self.data.get(&lru_key) {
                    freed_space += entry.size + lru_key.len();
                    self.stats.compression_savings += (entry.size as f32 * (1.0 - entry.compression_ratio)) as u64;
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
    
    fn calculate_eviction_score(&self, entry: &CacheEntry) -> f64 {
        let age_factor = (js_sys::Date::now() - entry.timestamp) / 1000.0; // seconds
        let access_factor = 1.0 / (entry.access_count as f64).max(1.0);
        let priority_factor = match entry.priority {
            CachePriority::Critical => 0.1,
            CachePriority::High => 0.3,
            CachePriority::Medium => 0.5,
            CachePriority::Low => 0.8,
            CachePriority::Disposable => 1.0,
        };
        let size_factor = (entry.size as f64).log2() / 20.0; // Prefer evicting larger items
        
        age_factor * access_factor * priority_factor + size_factor
    }
    
    fn compress_entries(&mut self) {
        // Compress entries that haven't been accessed recently
        let threshold_time = js_sys::Date::now() - 300000.0; // 5 minutes
        
        // Collect keys that need compression to avoid borrow conflicts
        let keys_to_compress: Vec<String> = self.data
            .iter()
            .filter(|(_, entry)| entry.timestamp < threshold_time && entry.compression_ratio > 0.8)
            .map(|(key, _)| key.clone())
            .collect();
        
        for key in keys_to_compress {
            if let Some(entry) = self.data.get_mut(&key) {
                let value_clone = entry.value.clone();
                let (compressed, ratio) = Self::maybe_compress(&value_clone);
                if ratio < entry.compression_ratio {
                    let old_size = entry.size;
                    entry.value = compressed;
                    entry.size = entry.value.len();
                    entry.compression_ratio = ratio;
                    
                    self.stats.size -= old_size;
                    self.stats.size += entry.size;
                    self.stats.compression_savings += (old_size - entry.size) as u64;
                }
            }
        }
    }
    
    fn defragment_advanced(&mut self) {
        // Rebuild access order based on actual access patterns and recency
        let mut weighted_keys: Vec<(String, f64)> = self.data
            .iter()
            .map(|(key, entry)| {
                let recency_weight = 1.0 / ((js_sys::Date::now() - entry.timestamp) / 1000.0 + 1.0);
                let frequency_weight = (entry.access_count as f64).log2();
                let priority_weight = match entry.priority {
                    CachePriority::Critical => 10.0,
                    CachePriority::High => 7.0,
                    CachePriority::Medium => 5.0,
                    CachePriority::Low => 3.0,
                    CachePriority::Disposable => 1.0,
                };
                
                let total_weight = recency_weight + frequency_weight + priority_weight;
                (key.clone(), total_weight)
            })
            .collect();

        weighted_keys.sort_by(|a, b| a.1.partial_cmp(&b.1).unwrap());
        
        self.access_order.clear();
        for (key, _) in weighted_keys {
            self.access_order.push_back(key);
        }
        
        // Update hot/cold entry counts
        self.update_hot_cold_counts();
    }
    
    fn update_hot_cold_counts(&mut self) {
        let (mut hot, mut cold) = (0, 0);
        
        for entry in self.data.values() {
            if entry.access_count >= self.hot_threshold {
                hot += 1;
            } else {
                cold += 1;
            }
        }
        
        self.stats.hot_entries = hot;
        self.stats.cold_entries = cold;
    }
    
    fn update_fragmentation_ratio(&mut self) {
        // Calculate fragmentation based on memory usage patterns
        let ideal_size = self.stats.entries * 100; // Assume 100 bytes average per entry
        self.stats.fragmentation_ratio = if ideal_size > 0 {
            (self.stats.size as f64 - ideal_size as f64).abs() / ideal_size as f64
        } else {
            0.0
        };
    }
    
    fn calculate_health_score(&self) -> f64 {
        let hit_rate_score = self.stats.hit_rate * 0.4;
        let memory_efficiency_score = (1.0 - self.stats.fragmentation_ratio).max(0.0) * 0.3;
        let eviction_score = if self.stats.total_requests > 0 {
            (1.0 - (self.stats.evictions as f64 / self.stats.total_requests as f64)).max(0.0) * 0.3
        } else {
            1.0 * 0.3
        };
        
        (hit_rate_score + memory_efficiency_score + eviction_score).min(1.0)
    }
    
    fn calculate_memory_pressure(&self) -> f64 {
        self.stats.size as f64 / self.max_size as f64
    }
    
    fn generate_recommendations(&self) -> Vec<String> {
        let mut recommendations = Vec::new();
        
        if self.stats.hit_rate < 0.6 {
            recommendations.push("Consider increasing cache size or improving cache key strategies".to_string());
        }
        
        if self.stats.fragmentation_ratio > 0.4 {
            recommendations.push("Run memory optimization to reduce fragmentation".to_string());
        }
        
        if self.calculate_memory_pressure() > 0.9 {
            recommendations.push("Cache is near capacity - consider eviction policy tuning".to_string());
        }
        
        if self.stats.evictions > self.stats.total_requests / 4 {
            recommendations.push("High eviction rate detected - consider larger cache size".to_string());
        }
        
        recommendations
    }
    
    fn put_with_ttl(&mut self, key: String, value: String, ttl: Option<u64>) -> bool {
        self.put_with_ttl_and_priority(key, value, ttl, CachePriority::Medium)
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