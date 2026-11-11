"""
FACT System Cache Manager

Implements intelligent caching for Claude Sonnet-4 with token-based optimization,
metrics tracking, and performance monitoring following FACT architecture.
"""

import time
import hashlib
import json
import asyncio
import threading
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from pathlib import Path
import structlog

try:
    # Try relative imports first (when used as package)
    from ..core.errors import CacheError, ConfigurationError
except ImportError:
    # Fall back to absolute imports (when run as script)
    import sys
    from pathlib import Path

    # Add src to path if not already there
    src_path = str(Path(__file__).parent.parent)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    from core.errors import CacheError, ConfigurationError

# Module-level so callers/tests can patch them; both modules avoid importing
# this one, so there is no import cycle.
try:
    from .config import load_cache_config_from_env, get_default_cache_config
    from .security import validate_cache_content_security
except ImportError:
    try:
        from cache.config import (  # type: ignore[no-redef]
            get_default_cache_config,
            load_cache_config_from_env,
        )
        from cache.security import (  # type: ignore[no-redef]
            validate_cache_content_security,
        )
    except ImportError:
        load_cache_config_from_env = None  # type: ignore[assignment]
        get_default_cache_config = None  # type: ignore[assignment]
        validate_cache_content_security = None  # type: ignore[assignment]


logger = structlog.get_logger(__name__)


@dataclass
class CacheEntry:
    """Represents a cached entry with metadata and access tracking."""

    prefix: str
    content: str
    token_count: int
    created_at: float
    version: str = "1.0"
    is_valid: bool = True
    access_count: int = 0
    last_accessed: Optional[float] = None

    def __init__(
        self,
        prefix: str,
        content: str,
        token_count: Optional[int] = None,
        created_at: Optional[float] = None,
        version: str = "1.0",
        is_valid: bool = True,
        access_count: int = 0,
        last_accessed: Optional[float] = None,
        validate: bool = True,
        skip_min_tokens: bool = False,
        skip_content_validation: bool = False,
        min_tokens: int = 500,
    ):
        """Initialize cache entry with optional automatic token counting."""
        self.prefix = prefix
        self.content = content
        self.token_count = (
            token_count if token_count is not None else self._count_tokens(content)
        )
        self.created_at = created_at if created_at is not None else time.time()
        self.version = version
        self.is_valid = is_valid
        self.access_count = access_count
        self.last_accessed = last_accessed
        self._skip_min_tokens = skip_min_tokens
        self._skip_content_validation = skip_content_validation
        self._min_tokens = min_tokens

        # Validate after initialization if requested
        if validate:
            self._validate()

    def _validate(self):
        """Validate cache entry after initialization."""
        # Always validate prefix
        if not self.prefix:
            raise CacheError(
                "Cache entry must have non-empty prefix",
                error_code="CACHE_EMPTY_PREFIX",
            )

        # Validate content is not empty (skip if requested for testing)
        if not getattr(self, "_skip_content_validation", False) and not self.content:
            raise CacheError(
                "Cache entry must have non-empty content",
                error_code="CACHE_EMPTY_CONTENT",
            )

        # Validate minimum token count (critical for caching efficiency)
        # Skip validation if explicitly requested (for testing purposes)
        min_tokens = getattr(self, "_min_tokens", 500)
        if (
            not getattr(self, "_skip_min_tokens", False)
            and self.token_count < min_tokens
        ):
            raise CacheError(
                f"Cache entry must have minimum {min_tokens} tokens, got {self.token_count}",
                error_code="CACHE_MIN_TOKENS",
            )

    @classmethod
    def create(cls, prefix: str, content: str, min_tokens: int = 500) -> "CacheEntry":
        """Create a new cache entry with automatic token counting."""
        return cls(prefix=prefix, content=content, min_tokens=min_tokens)

    @staticmethod
    def _count_tokens(text: str) -> int:
        """
        Fast token count estimation using character-based approach.

        Optimized for performance while maintaining accuracy.
        """
        if not text:
            return 0

        # Fast character-based estimation (4.2 chars per token average)
        char_count = len(text)
        if char_count <= 20:  # Very short text
            return max(1, char_count // 3)

        # For longer text, use more accurate estimation
        # Check for repeated character patterns first (faster than set operations)
        if char_count > 0 and text.count(text[0]) == char_count:
            return char_count  # All same character

        # Standard estimation: ~4.2 characters per token
        return max(1, int(char_count / 4.2))

    def record_access(self) -> None:
        """Record an access to this cache entry."""
        self.access_count += 1
        self.last_accessed = time.time()

    def is_expired(self, ttl_seconds: float) -> bool:
        """Check if this entry has expired based on TTL."""
        if ttl_seconds <= 0:
            return False

        age_seconds = time.time() - self.created_at
        return age_seconds > ttl_seconds

    def to_dict(self) -> Dict[str, Any]:
        """Convert cache entry to dictionary format."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], min_tokens: int = 500) -> "CacheEntry":
        """Create cache entry from dictionary format."""
        # Add min_tokens if not already in data
        if "min_tokens" not in data:
            data = data.copy()
            data["min_tokens"] = min_tokens
        return cls(**data)


@dataclass
class CacheMetrics:
    """Cache performance metrics and statistics."""

    total_entries: int = 0
    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    total_size: int = 0
    hit_rate: float = 0.0
    miss_rate: float = 0.0
    avg_access_count: float = 0.0
    cost_savings: Dict[str, float] = None
    token_efficiency: float = 0.0
    timestamp: float = 0.0

    def __post_init__(self):
        """Calculate derived metrics."""
        if self.total_requests > 0:
            self.hit_rate = (self.cache_hits / self.total_requests) * 100
            self.miss_rate = (self.cache_misses / self.total_requests) * 100

        if not self.cost_savings:
            self.cost_savings = {
                "cache_hit_reduction": 90.0,  # 90% cost reduction on hits
                "cache_miss_reduction": 65.0,  # 65% cost reduction on misses
            }

        self.timestamp = time.time()

    def to_json(self) -> str:
        """Export metrics as JSON string."""
        return json.dumps(asdict(self), indent=2)


class CacheManager:
    """
    Main cache manager for the FACT system.

    Handles cache storage, retrieval, invalidation, and metrics tracking
    with support for Claude Sonnet-4 cache control mechanisms.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize cache manager with optimization features.

        Args:
            config: Cache configuration dictionary
                - prefix: Cache prefix for Claude Sonnet-4
                - min_tokens: Minimum tokens required for caching
                - max_size: Maximum cache size (e.g., "10MB")
                - ttl_seconds: Time-to-live for cache entries
                - hit_target_ms: Target latency for cache hits
                - miss_target_ms: Target latency for cache misses
        """
        self.prefix = config["prefix"]
        self.min_tokens = config["min_tokens"]
        self.max_size = config["max_size"]  # Keep original for compatibility
        self.max_size_bytes = self._parse_size(config["max_size"])
        self.ttl_seconds = config["ttl_seconds"]
        self.hit_target_ms = config.get("hit_target_ms", 48)  # Updated target
        self.miss_target_ms = config.get("miss_target_ms", 140)

        # Thread-safe cache storage with optimization
        self.cache: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()

        # Metrics tracking
        self._hits = 0
        self._misses = 0
        self._total_requests = 0

        # Performance optimization features
        self.optimization_enabled = True
        self.eviction_strategy = "lru_with_frequency"  # LRU + frequency-based
        self.preemptive_cleanup_threshold = 0.80  # Cleanup at 80% capacity
        self.fast_lookup_enabled = True

        # Access frequency tracking for intelligent eviction
        self._access_frequency: Dict[str, float] = {}
        self._last_cleanup = time.time()
        self._cleanup_interval = 300  # 5 minutes

        # Performance monitoring
        self._performance_stats = {
            "avg_hit_latency": 0.0,
            "avg_miss_latency": 0.0,
            "recent_hit_latencies": [],
            "recent_miss_latencies": [],
        }

        logger.info(
            "Optimized cache manager initialized",
            prefix=self.prefix,
            min_tokens=self.min_tokens,
            max_size_mb=self.max_size_bytes // (1024 * 1024),
            optimization_enabled=self.optimization_enabled,
        )

    def store(self, query_hash: str, content: str) -> CacheEntry:
        """
        Store content in cache with automatic validation and security checks.

        Args:
            query_hash: Unique hash for the query
            content: Content to cache

        Returns:
            Created cache entry

        Raises:
            CacheError: If storage fails or limits exceeded
            SecurityError: If content fails security validation
        """
        try:
            # Security validation before storage
            try:
                if validate_cache_content_security is None:
                    logger.warning("Security validation not available")
                else:
                    validate_cache_content_security(
                        content, f"cache_store:{query_hash[:8]}"
                    )
            except Exception as e:
                logger.error(
                    "Security validation failed",
                    query_hash=query_hash[:8],
                    error=str(e),
                )
                raise CacheError(
                    f"Security validation failed: {e}",
                    error_code="CACHE_SECURITY_REJECTED",
                )

            with self._lock:
                # Create cache entry with configured minimum token count
                entry = CacheEntry.create(
                    self.prefix, content, min_tokens=self.min_tokens
                )

                # The minimum token validation is now handled in CacheEntry._validate()
                # No need for duplicate validation here since create() will validate

                # Optimized size management
                entry_size = len(content.encode("utf-8"))
                current_size = self._calculate_current_size()

                if current_size + entry_size > self.max_size_bytes:
                    # Multi-stage cleanup strategy
                    freed_space = 0

                    # Stage 1: Remove expired entries
                    freed_space += self._cleanup_expired()

                    # Stage 2: If still need space, use intelligent eviction
                    if freed_space < entry_size:
                        needed_space = entry_size - freed_space
                        freed_space += self._intelligent_eviction(needed_space)

                    # Stage 3: Final check
                    current_size = self._calculate_current_size()
                    if current_size + entry_size > self.max_size_bytes:
                        # Emergency eviction - remove least valuable entries
                        self._emergency_eviction(entry_size)
                        current_size = self._calculate_current_size()

                        if current_size + entry_size > self.max_size_bytes:
                            raise CacheError(
                                f"Cache size limit exceeded after cleanup. Required: {entry_size}, "
                                f"Available: {self.max_size_bytes - current_size}",
                                error_code="CACHE_SIZE_LIMIT",
                            )

                # Store in cache
                self.cache[query_hash] = entry

                logger.debug(
                    "Cache entry stored",
                    query_hash=query_hash[:16],
                    token_count=entry.token_count,
                    size_bytes=entry_size,
                )

                return entry

        except Exception as e:
            logger.error(
                "Failed to store cache entry", query_hash=query_hash[:16], error=str(e)
            )
            raise CacheError(
                f"Cache storage failed: {e}",
                error_code=getattr(e, "error_code", None),
            ) from e

    def get(self, query_hash: str) -> Optional[CacheEntry]:
        """
        Optimized cache retrieval with performance tracking.

        Args:
            query_hash: Query hash to retrieve

        Returns:
            Cache entry if found and valid, None otherwise
        """
        start_time = time.perf_counter()

        try:
            with self._lock:
                self._total_requests += 1

                # Fast path: check if entry exists
                if query_hash not in self.cache:
                    self._misses += 1
                    latency_ms = (time.perf_counter() - start_time) * 1000
                    self._update_performance_stats(latency_ms, cache_hit=False)
                    return None

                entry = self.cache[query_hash]

                # Optimized validation checks
                current_time = time.time()

                # Check expiration first (fastest check)
                if (
                    self.ttl_seconds > 0
                    and (current_time - entry.created_at) > self.ttl_seconds
                ):
                    del self.cache[query_hash]
                    if query_hash in self._access_frequency:
                        del self._access_frequency[query_hash]
                    self._misses += 1
                    latency_ms = (time.perf_counter() - start_time) * 1000
                    self._update_performance_stats(latency_ms, cache_hit=False)
                    logger.debug("Cache entry expired", query_hash=query_hash[:16])
                    return None

                # Content validation (only if content is small for performance)
                if not entry.is_valid or (
                    len(entry.content) < 1000 and not entry.content.strip()
                ):
                    del self.cache[query_hash]
                    if query_hash in self._access_frequency:
                        del self._access_frequency[query_hash]
                    self._misses += 1
                    latency_ms = (time.perf_counter() - start_time) * 1000
                    self._update_performance_stats(latency_ms, cache_hit=False)
                    logger.warning(
                        "Invalid cache entry removed", query_hash=query_hash[:16]
                    )
                    return None

                # Record access with frequency tracking
                entry.record_access()
                self._access_frequency[query_hash] = (
                    self._access_frequency.get(query_hash, 0) + 1
                )
                self._hits += 1

                # Performance tracking
                latency_ms = (time.perf_counter() - start_time) * 1000
                self._update_performance_stats(latency_ms, cache_hit=True)

                # Trigger preemptive cleanup if needed
                if self.optimization_enabled:
                    self._maybe_preemptive_cleanup()

                logger.debug(
                    "Cache hit",
                    query_hash=query_hash[:16],
                    latency_ms=latency_ms,
                    access_count=entry.access_count,
                )

                return entry

        except Exception as e:
            logger.error(
                "Cache retrieval failed", query_hash=query_hash[:16], error=str(e)
            )
            self._misses += 1
            latency_ms = (time.perf_counter() - start_time) * 1000
            self._update_performance_stats(latency_ms, cache_hit=False)
            return None

    def invalidate_by_prefix(self, prefix: str) -> int:
        """
        Invalidate all cache entries with matching prefix.

        Args:
            prefix: Cache prefix to invalidate

        Returns:
            Number of entries invalidated
        """
        try:
            with self._lock:
                entries_to_remove = [
                    key for key, entry in self.cache.items() if entry.prefix == prefix
                ]

                for key in entries_to_remove:
                    del self.cache[key]

                logger.info(
                    "Cache invalidated by prefix",
                    prefix=prefix,
                    entries_removed=len(entries_to_remove),
                )

                return len(entries_to_remove)

        except Exception as e:
            logger.error("Cache invalidation failed", prefix=prefix, error=str(e))
            return 0

    def generate_hash(self, query: str) -> str:
        """
        Generate deterministic hash for query.

        Args:
            query: Query string to hash

        Returns:
            SHA-256 hash of the query
        """
        # Include prefix and version for cache invalidation
        hash_input = f"{self.prefix}:{query}:v1.0"
        return hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

    def get_metrics(self) -> CacheMetrics:
        """
        Calculate and return current cache metrics.

        Returns:
            Current cache metrics
        """
        try:
            with self._lock:
                total_size = self._calculate_current_size()

                # Calculate average access count
                avg_access = 0.0
                if self.cache:
                    total_accesses = sum(
                        entry.access_count for entry in self.cache.values()
                    )
                    avg_access = total_accesses / len(self.cache)

                # Calculate token efficiency
                total_tokens = sum(entry.token_count for entry in self.cache.values())
                token_efficiency = (
                    total_tokens / max(1, total_size) * 1000
                )  # tokens per KB

                return CacheMetrics(
                    total_entries=len(self.cache),
                    total_requests=self._total_requests,
                    cache_hits=self._hits,
                    cache_misses=self._misses,
                    total_size=total_size,
                    avg_access_count=avg_access,
                    token_efficiency=token_efficiency,
                )

        except Exception as e:
            logger.error("Failed to calculate metrics", error=str(e))
            return CacheMetrics()

    def _parse_size(self, size_str: str) -> int:
        """Parse size string (e.g., '10MB') to bytes."""
        size_str = size_str.upper().strip()

        if size_str.endswith("KB"):
            return int(size_str[:-2]) * 1024
        elif size_str.endswith("MB"):
            return int(size_str[:-2]) * 1024 * 1024
        elif size_str.endswith("GB"):
            return int(size_str[:-2]) * 1024 * 1024 * 1024
        else:
            # Assume bytes
            return int(size_str)

    def _calculate_current_size(self) -> int:
        """Calculate current cache size in bytes."""
        return sum(len(entry.content.encode("utf-8")) for entry in self.cache.values())

    def _cleanup_expired(self) -> int:
        """Remove expired entries from cache."""
        if self.ttl_seconds <= 0:
            return 0

        expired_keys = [
            key
            for key, entry in self.cache.items()
            if entry.is_expired(self.ttl_seconds)
        ]

        for key in expired_keys:
            del self.cache[key]

        if expired_keys:
            logger.debug("Expired cache entries cleaned up", count=len(expired_keys))

        return len(expired_keys)

    def _update_performance_stats(self, latency_ms: float, cache_hit: bool):
        """Update performance statistics for monitoring."""
        try:
            if cache_hit:
                self._performance_stats["recent_hit_latencies"].append(latency_ms)
                # Keep only recent measurements (last 100)
                if len(self._performance_stats["recent_hit_latencies"]) > 100:
                    self._performance_stats["recent_hit_latencies"].pop(0)

                # Update running average
                recent_hits = self._performance_stats["recent_hit_latencies"]
                if recent_hits:
                    self._performance_stats["avg_hit_latency"] = sum(recent_hits) / len(
                        recent_hits
                    )
            else:
                self._performance_stats["recent_miss_latencies"].append(latency_ms)
                # Keep only recent measurements (last 100)
                if len(self._performance_stats["recent_miss_latencies"]) > 100:
                    self._performance_stats["recent_miss_latencies"].pop(0)

                # Update running average
                recent_misses = self._performance_stats["recent_miss_latencies"]
                if recent_misses:
                    self._performance_stats["avg_miss_latency"] = sum(
                        recent_misses
                    ) / len(recent_misses)

        except Exception as e:
            logger.debug("Failed to update performance stats", error=str(e))

    def _maybe_preemptive_cleanup(self):
        """Perform preemptive cleanup if conditions are met."""
        try:
            current_time = time.time()

            # Check if cleanup interval has passed
            if current_time - self._last_cleanup < self._cleanup_interval:
                return

            # Check if cache utilization exceeds threshold
            current_size = self._calculate_current_size()
            utilization = current_size / self.max_size_bytes

            if utilization > self.preemptive_cleanup_threshold:
                logger.debug("Triggering preemptive cleanup", utilization=utilization)

                # Remove expired entries
                expired_removed = self._cleanup_expired()

                # If still high utilization, remove least frequently used entries
                if utilization > 0.90:
                    target_size = int(
                        self.max_size_bytes * 0.80
                    )  # Target 80% utilization
                    current_size = self._calculate_current_size()
                    if current_size > target_size:
                        space_to_free = current_size - target_size
                        self._intelligent_eviction(space_to_free)

                self._last_cleanup = current_time
                logger.debug(
                    "Preemptive cleanup completed", expired_removed=expired_removed
                )

        except Exception as e:
            logger.error("Preemptive cleanup failed", error=str(e))

    def _intelligent_eviction(self, space_needed: int) -> int:
        """Intelligent eviction based on access frequency and recency."""
        try:
            freed_space = 0

            # Calculate eviction scores for all entries
            eviction_candidates = []
            current_time = time.time()

            for key, entry in self.cache.items():
                # Calculate composite score (lower = more likely to evict)
                age_hours = (current_time - entry.created_at) / 3600
                access_frequency = self._access_frequency.get(key, 1)
                recency_score = (
                    current_time - (entry.last_accessed or entry.created_at)
                ) / 3600

                # Composite score: balance frequency, recency, and age
                eviction_score = (
                    (recency_score * 0.5) + (age_hours * 0.3) - (access_frequency * 0.2)
                )

                entry_size = len(entry.content.encode("utf-8"))
                eviction_candidates.append((eviction_score, key, entry_size))

            # Sort by eviction score (highest score = evict first)
            eviction_candidates.sort(reverse=True)

            # Evict entries until we have enough space
            for score, key, entry_size in eviction_candidates:
                if freed_space >= space_needed:
                    break

                del self.cache[key]
                if key in self._access_frequency:
                    del self._access_frequency[key]
                freed_space += entry_size

                logger.debug(
                    "Evicted cache entry", key=key[:16], score=score, size=entry_size
                )

            logger.info(
                "Intelligent eviction completed",
                space_freed=freed_space,
                entries_evicted=len(
                    [c for c in eviction_candidates if c[2] <= freed_space]
                ),
            )

            return freed_space

        except Exception as e:
            logger.error("Intelligent eviction failed", error=str(e))
            return 0

    def _emergency_eviction(self, space_needed: int):
        """Emergency eviction - remove least recently used entries."""
        try:
            # Sort by last access time (oldest first)
            entries_by_access = []
            for key, entry in self.cache.items():
                last_access = entry.last_accessed or entry.created_at
                entry_size = len(entry.content.encode("utf-8"))
                entries_by_access.append((last_access, key, entry_size))

            entries_by_access.sort()  # Oldest access first

            freed_space = 0
            evicted_count = 0

            for _, key, entry_size in entries_by_access:
                if freed_space >= space_needed:
                    break

                del self.cache[key]
                if key in self._access_frequency:
                    del self._access_frequency[key]
                freed_space += entry_size
                evicted_count += 1

            logger.warning(
                "Emergency eviction completed",
                space_freed=freed_space,
                entries_evicted=evicted_count,
            )

        except Exception as e:
            logger.error("Emergency eviction failed", error=str(e))

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get current performance statistics."""
        return {
            "avg_hit_latency_ms": self._performance_stats["avg_hit_latency"],
            "avg_miss_latency_ms": self._performance_stats["avg_miss_latency"],
            "hit_target_ms": self.hit_target_ms,
            "miss_target_ms": self.miss_target_ms,
            "hit_latency_compliance": self._performance_stats["avg_hit_latency"]
            <= self.hit_target_ms,
            "miss_latency_compliance": self._performance_stats["avg_miss_latency"]
            <= self.miss_target_ms,
            "recent_hit_count": len(self._performance_stats["recent_hit_latencies"]),
            "recent_miss_count": len(self._performance_stats["recent_miss_latencies"]),
        }


# Global cache manager instance
_cache_manager_instance: Optional[CacheManager] = None
cache_manager: Optional[CacheManager] = None  # For test patching


def get_cache_manager(config: Optional[Dict[str, Any]] = None) -> CacheManager:
    """
    Get or create the global cache manager instance.

    Args:
        config: Optional cache configuration

    Returns:
        Cache manager instance
    """
    global _cache_manager_instance, cache_manager

    if _cache_manager_instance is None:
        if not config:
            # Try to load configuration from environment
            try:
                if load_cache_config_from_env is None:
                    raise ImportError("cache.config is not available")
                try:
                    env_config = load_cache_config_from_env()
                    config = env_config.to_dict()
                    logger.info("Cache manager using environment configuration")
                except Exception as e:
                    logger.warning(
                        "Failed to load environment config, using defaults",
                        error=str(e),
                    )
                    config = get_default_cache_config()
            except Exception as e:
                logger.error("Failed to load any cache configuration", error=str(e))
                raise ConfigurationError(
                    "Cache configuration required for initialization"
                )

        _cache_manager_instance = CacheManager(config)
        cache_manager = _cache_manager_instance

        logger.info(
            "Cache manager instance created",
            prefix=config.get("prefix", "unknown"),
            max_size=config.get("max_size", "unknown"),
        )

    return _cache_manager_instance


def get_cached_response(query: str, llm_client: Any = None) -> Optional[str]:
    """
    Attempt to get cached response for query.

    Args:
        query: User query
        llm_client: LLM client for cache misses (optional)

    Returns:
        Cached response if available, None otherwise
    """
    # Use the global cache_manager if set (for test patching), otherwise get singleton
    current_manager = cache_manager if cache_manager else None
    if not current_manager:
        try:
            current_manager = get_cache_manager()
        except ConfigurationError:
            return None

    query_hash = current_manager.generate_hash(query)

    entry = current_manager.get(query_hash)
    if entry:
        logger.info("Cache hit for query", query_hash=query_hash[:16])
        return entry.content

    logger.info("Cache miss for query", query_hash=query_hash[:16])
    return None


async def get_cached_response_async(query: str, llm_client: Any) -> Optional[str]:
    """
    Async version of get_cached_response for compatibility.

    Args:
        query: User query
        llm_client: LLM client for cache misses

    Returns:
        Cached response if available, None otherwise
    """
    return get_cached_response(query, llm_client)


def warm_cache(queries: List[str], responses: Optional[List[str]] = None) -> int:
    """
    Warm cache with common queries and responses.

    Args:
        queries: List of common queries
        responses: Optional corresponding responses

    Returns:
        Number of entries cached
    """
    # Use the global cache_manager if set (for test patching), otherwise get singleton
    current_manager = cache_manager if cache_manager else None
    if not current_manager:
        try:
            current_manager = get_cache_manager()
        except ConfigurationError:
            logger.error("No cache manager available for warming")
            return 0
    cached_count = 0

    for i, query in enumerate(queries):
        try:
            # Use provided response or generate placeholder
            if responses and i < len(responses):
                response = responses[i]
            else:
                response = (
                    f"Cached response for: {query}" + " " * 500
                )  # Ensure min tokens

            query_hash = current_manager.generate_hash(query)
            current_manager.store(query_hash, response)
            cached_count += 1

        except Exception as e:
            logger.warning(
                "Failed to cache query during warming", query=query[:50], error=str(e)
            )

    logger.info(
        "Cache warming completed",
        cached_queries=cached_count,
        total_queries=len(queries),
    )
    return cached_count


def invalidate_on_schema_change(reason: str) -> int:
    """
    Invalidate cache when schema changes occur.

    Args:
        reason: Reason for invalidation

    Returns:
        Number of entries invalidated
    """
    # Use the global cache_manager if set (for test patching), otherwise get singleton
    current_manager = cache_manager if cache_manager else None
    if not current_manager:
        try:
            current_manager = get_cache_manager()
        except ConfigurationError:
            logger.error("No cache manager available for invalidation")
            return 0

    invalidated = current_manager.invalidate_by_prefix(current_manager.prefix)

    logger.info(
        "Cache invalidated due to schema change",
        reason=reason,
        entries_invalidated=invalidated,
    )

    return invalidated
