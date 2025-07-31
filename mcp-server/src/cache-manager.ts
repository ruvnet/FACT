import { logger } from './logger.js';

interface CacheEntry {
  key: string;
  value: any;
  expires_at: number;
  created_at: number;
  access_count: number;
  last_accessed: number;
  size: number;
}

export interface CacheStats {
  entries: number;
  total_size: number;
  hit_rate: number;
  evictions: number;
  avg_access_time_ms: number;
}

export class CacheManager {
  private cache: Map<string, CacheEntry> = new Map();
  private maxSize: number = 100 * 1024 * 1024; // 100MB default
  private currentSize: number = 0;
  private hits: number = 0;
  private misses: number = 0;
  private evictions: number = 0;
  private accessTimes: number[] = [];

  constructor(maxSize?: number) {
    if (maxSize) {
      this.maxSize = maxSize;
    }
    
    // Start cleanup interval
    this.startCleanupInterval();
  }

  async get(key: string): Promise<any> {
    const startTime = Date.now();
    const entry = this.cache.get(key);

    if (!entry) {
      this.misses++;
      this.recordAccessTime(Date.now() - startTime);
      return null;
    }

    // Check expiration
    if (entry.expires_at < Date.now()) {
      this.cache.delete(key);
      this.currentSize -= entry.size;
      this.misses++;
      this.recordAccessTime(Date.now() - startTime);
      return null;
    }

    // Update access info
    entry.access_count++;
    entry.last_accessed = Date.now();
    this.hits++;
    this.recordAccessTime(Date.now() - startTime);

    return entry.value;
  }

  async set(key: string, value: any, ttl: number = 3600): Promise<void> {
    const size = this.calculateSize(value);
    
    // Check if we need to evict entries
    while (this.currentSize + size > this.maxSize && this.cache.size > 0) {
      this.evictLRU();
    }

    const entry: CacheEntry = {
      key,
      value,
      expires_at: Date.now() + (ttl * 1000),
      created_at: Date.now(),
      access_count: 0,
      last_accessed: Date.now(),
      size,
    };

    // Remove old entry if exists
    const oldEntry = this.cache.get(key);
    if (oldEntry) {
      this.currentSize -= oldEntry.size;
    }

    this.cache.set(key, entry);
    this.currentSize += size;
  }

  async delete(key: string): Promise<boolean> {
    const entry = this.cache.get(key);
    if (entry) {
      this.currentSize -= entry.size;
      return this.cache.delete(key);
    }
    return false;
  }

  async clear(): Promise<void> {
    this.cache.clear();
    this.currentSize = 0;
    this.hits = 0;
    this.misses = 0;
    this.evictions = 0;
    this.accessTimes = [];
  }

  async flush(): Promise<void> {
    // Save cache stats before clearing
    const stats = this.getStats();
    logger.info('Cache flush stats:', stats);
    await this.clear();
  }

  getStats(): CacheStats {
    const total = this.hits + this.misses;
    const hitRate = total > 0 ? this.hits / total : 0;
    
    const avgAccessTime = this.accessTimes.length > 0
      ? this.accessTimes.reduce((a, b) => a + b, 0) / this.accessTimes.length
      : 0;

    return {
      entries: this.cache.size,
      total_size: this.currentSize,
      hit_rate: hitRate,
      evictions: this.evictions,
      avg_access_time_ms: avgAccessTime,
    };
  }

  private evictLRU(): void {
    let oldestKey: string | null = null;
    let oldestTime = Date.now();

    // Find least recently used entry
    for (const [key, entry] of this.cache.entries()) {
      if (entry.last_accessed < oldestTime) {
        oldestTime = entry.last_accessed;
        oldestKey = key;
      }
    }

    if (oldestKey) {
      const entry = this.cache.get(oldestKey)!;
      this.cache.delete(oldestKey);
      this.currentSize -= entry.size;
      this.evictions++;
      logger.debug(`Evicted cache entry: ${oldestKey}`);
    }
  }

  private calculateSize(value: any): number {
    // Rough estimate of object size in bytes
    const str = JSON.stringify(value);
    return str.length * 2; // 2 bytes per character (UTF-16)
  }

  private recordAccessTime(timeMs: number): void {
    this.accessTimes.push(timeMs);
    
    // Keep only last 1000 access times
    if (this.accessTimes.length > 1000) {
      this.accessTimes.shift();
    }
  }

  private startCleanupInterval(): void {
    // Clean up expired entries every minute
    setInterval(() => {
      const now = Date.now();
      let cleaned = 0;

      for (const [key, entry] of this.cache.entries()) {
        if (entry.expires_at < now) {
          this.cache.delete(key);
          this.currentSize -= entry.size;
          cleaned++;
        }
      }

      if (cleaned > 0) {
        logger.debug(`Cleaned up ${cleaned} expired cache entries`);
      }
    }, 60000);
  }

  // Advanced cache features

  async warmUp(entries: Array<{ key: string; value: any; ttl?: number }>): Promise<void> {
    logger.info(`Warming up cache with ${entries.length} entries`);
    
    for (const entry of entries) {
      await this.set(entry.key, entry.value, entry.ttl);
    }
  }

  async getOrCompute<T>(
    key: string,
    compute: () => Promise<T>,
    ttl: number = 3600
  ): Promise<T> {
    const cached = await this.get(key);
    if (cached !== null) {
      return cached as T;
    }

    const value = await compute();
    await this.set(key, value, ttl);
    return value;
  }

  getHotKeys(limit: number = 10): Array<{ key: string; access_count: number }> {
    const entries = Array.from(this.cache.entries())
      .map(([key, entry]) => ({ key, access_count: entry.access_count }))
      .sort((a, b) => b.access_count - a.access_count)
      .slice(0, limit);

    return entries;
  }

  async preload(patterns: string[]): Promise<void> {
    // Preload entries matching patterns
    // This is a placeholder for more sophisticated preloading logic
    logger.info(`Preloading cache entries matching patterns: ${patterns.join(', ')}`);
  }
}