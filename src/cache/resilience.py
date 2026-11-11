"""
FACT cache resilience: circuit breaker and resilient cache wrapper.

The circuit breaker protects callers from a failing cache backend:

* CLOSED    - normal operation; failures inside the rolling window are counted.
* OPEN      - the backend is considered unhealthy; operations are blocked and
              either degrade gracefully (fallback values) or raise
              ``CacheError(error_code="CIRCUIT_BREAKER_OPEN")``.
* HALF_OPEN - after ``timeout_seconds`` the breaker lets a fraction of the
              requests through (``recovery_factor`` when ``gradual_recovery``
              is enabled). ``success_threshold`` successes close the circuit,
              a single failure re-opens it.

``ResilientCacheWrapper`` keeps the interface of the wrapped cache manager
(``store``/``get``/``invalidate_by_prefix``/``generate_hash``/``get_metrics``)
but exposes async methods and works with both sync and async managers.
"""

import asyncio
import hashlib
import inspect
import math
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from typing import Any, Callable, Deque, Dict, List, Optional

import structlog

try:
    from ..core.errors import CacheError
except ImportError:  # pragma: no cover - script-style imports (src on sys.path)
    from core.errors import CacheError  # type: ignore[no-redef]

logger = structlog.get_logger(__name__)

CIRCUIT_BREAKER_OPEN = "CIRCUIT_BREAKER_OPEN"
CIRCUIT_BREAKER_THROTTLING = "CIRCUIT_BREAKER_THROTTLING"

# Error codes for content the cache refused. The backend answered, so these
# say nothing about its health and must not trip the breaker.
CONTENT_REJECTION_CODES = frozenset(
    {
        "CACHE_MIN_TOKENS",
        "CACHE_EMPTY_CONTENT",
        "CACHE_EMPTY_PREFIX",
        "CACHE_SECURITY_REJECTED",
    }
)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker tuning parameters."""

    failure_threshold: int = 5
    success_threshold: int = 3
    timeout_seconds: float = 60.0
    rolling_window_seconds: float = 300.0
    gradual_recovery: bool = True
    recovery_factor: float = 0.5
    health_check_interval: float = 30.0
    max_failure_records: int = 100

    def __post_init__(self) -> None:
        if self.failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        if self.success_threshold < 1:
            raise ValueError("success_threshold must be >= 1")
        if self.timeout_seconds < 0:
            raise ValueError("timeout_seconds must be >= 0")
        if self.rolling_window_seconds <= 0:
            raise ValueError("rolling_window_seconds must be > 0")
        if not 0.0 < self.recovery_factor <= 1.0:
            raise ValueError("recovery_factor must be in (0, 1]")
        if self.health_check_interval <= 0:
            raise ValueError("health_check_interval must be > 0")


@dataclass
class FailureRecord:
    """A single recorded cache failure."""

    timestamp: float
    error_type: str
    error_message: str
    operation: str


@dataclass
class CircuitBreakerMetrics:
    """Snapshot of circuit breaker health."""

    state: CircuitState
    failure_count: int
    success_count: int
    total_operations: int
    blocked_operations: int
    failure_rate: float
    state_changes: int
    time_in_current_state: float
    recent_failures_count: int
    recent_failures: List[FailureRecord] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["state"] = self.state.value
        return data


class CacheCircuitBreaker:
    """Thread-safe circuit breaker for cache operations."""

    def __init__(self, config: Optional[CircuitBreakerConfig] = None):
        self.config = config or CircuitBreakerConfig()
        self._lock = threading.RLock()
        self._state = CircuitState.CLOSED
        self._state_changed_at = time.time()
        self._state_changes = 0
        self._failure_times: Deque[float] = deque()
        self._failures: Deque[FailureRecord] = deque(
            maxlen=self.config.max_failure_records
        )
        self._half_open_successes = 0
        self._half_open_requests = 0
        self._half_open_admitted = 0
        self.failure_count = 0
        self.success_count = 0
        self.total_operations = 0
        self.blocked_operations = 0
        self._health_task: Optional["asyncio.Task[None]"] = None

    # -- state -----------------------------------------------------------
    @property
    def state(self) -> CircuitState:
        return self.get_state()

    def get_state(self) -> CircuitState:
        """Return the current state, moving OPEN -> HALF_OPEN after the timeout."""
        with self._lock:
            if (
                self._state is CircuitState.OPEN
                and time.time() - self._state_changed_at >= self.config.timeout_seconds
            ):
                self._transition(CircuitState.HALF_OPEN)
            return self._state

    def is_closed(self) -> bool:
        return self.get_state() is CircuitState.CLOSED

    def is_open(self) -> bool:
        return self.get_state() is CircuitState.OPEN

    def is_half_open(self) -> bool:
        return self.get_state() is CircuitState.HALF_OPEN

    def _transition(self, new_state: CircuitState) -> None:
        if new_state is self._state:
            return
        old_state = self._state
        self._state = new_state
        self._state_changed_at = time.time()
        self._state_changes += 1
        self._half_open_successes = 0
        self._half_open_requests = 0
        self._half_open_admitted = 0
        if new_state is CircuitState.CLOSED:
            self._failure_times.clear()
        logger.info(
            "Cache circuit breaker state change",
            old_state=old_state.value,
            new_state=new_state.value,
        )

    def force_open(self) -> None:
        with self._lock:
            self._transition(CircuitState.OPEN)
            self._state_changed_at = time.time()

    def force_closed(self) -> None:
        with self._lock:
            self._transition(CircuitState.CLOSED)

    def reset(self) -> None:
        """Close the circuit and clear all counters."""
        with self._lock:
            self._transition(CircuitState.CLOSED)
            self._failures.clear()
            self.failure_count = 0
            self.success_count = 0
            self.total_operations = 0
            self.blocked_operations = 0

    # -- admission and recording ----------------------------------------
    def allow_request(self) -> bool:
        """Decide whether an operation may reach the cache backend."""
        with self._lock:
            state = self.get_state()
            if state is CircuitState.CLOSED:
                return True
            if state is CircuitState.OPEN:
                self.blocked_operations += 1
                return False
            # HALF_OPEN: admit a deterministic fraction of requests.
            self._half_open_requests += 1
            if not self.config.gradual_recovery:
                allowed = True
            else:
                quota = math.ceil(
                    self._half_open_requests * self.config.recovery_factor
                )
                allowed = self._half_open_admitted < quota
            if allowed:
                self._half_open_admitted += 1
            else:
                self.blocked_operations += 1
            return allowed

    def record_success(self) -> None:
        with self._lock:
            self.success_count += 1
            self.total_operations += 1
            if self._state is CircuitState.HALF_OPEN:
                self._half_open_successes += 1
                if self._half_open_successes >= self.config.success_threshold:
                    self._transition(CircuitState.CLOSED)

    def record_failure(self, error: BaseException, operation: str = "unknown") -> None:
        with self._lock:
            now = time.time()
            self.failure_count += 1
            self.total_operations += 1
            self._failures.append(
                FailureRecord(now, type(error).__name__, str(error)[:500], operation)
            )
            if self._state is CircuitState.HALF_OPEN:
                self._transition(CircuitState.OPEN)
                return
            self._failure_times.append(now)
            window_start = now - self.config.rolling_window_seconds
            while self._failure_times and self._failure_times[0] < window_start:
                self._failure_times.popleft()
            if (
                self._state is CircuitState.CLOSED
                and len(self._failure_times) >= self.config.failure_threshold
            ):
                self._transition(CircuitState.OPEN)

    def get_metrics(self) -> CircuitBreakerMetrics:
        with self._lock:
            state = self.get_state()
            total = self.total_operations
            return CircuitBreakerMetrics(
                state=state,
                failure_count=self.failure_count,
                success_count=self.success_count,
                total_operations=total,
                blocked_operations=self.blocked_operations,
                failure_rate=(self.failure_count / total) if total else 0.0,
                state_changes=self._state_changes,
                time_in_current_state=time.time() - self._state_changed_at,
                recent_failures_count=len(self._failure_times),
                recent_failures=list(self._failures)[-10:],
            )

    # -- health monitoring ----------------------------------------------
    async def start_health_monitoring(
        self, probe: Optional[Callable[[], Any]] = None
    ) -> None:
        """Periodically re-evaluate the state (and run an optional probe)."""
        if self._health_task and not self._health_task.done():
            return

        async def _loop() -> None:
            while True:
                await asyncio.sleep(self.config.health_check_interval)
                state = self.get_state()
                if probe is not None and state is not CircuitState.OPEN:
                    try:
                        result = probe()
                        if inspect.isawaitable(result):
                            await result
                    except Exception as exc:  # pragma: no cover - logged only
                        logger.warning("Cache health probe failed", error=str(exc))

        self._health_task = asyncio.create_task(_loop())

    async def stop_health_monitoring(self) -> None:
        task, self._health_task = self._health_task, None
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


class ResilientCacheWrapper:
    """Wraps a cache manager with a circuit breaker and graceful degradation."""

    def __init__(
        self,
        cache_manager: Any,
        circuit_breaker: Optional[CacheCircuitBreaker] = None,
        enable_graceful_degradation: bool = True,
    ):
        self.cache_manager = cache_manager
        self.circuit_breaker = circuit_breaker or CacheCircuitBreaker()
        self.enable_graceful_degradation = enable_graceful_degradation
        self.fallback_responses: Dict[str, Any] = {
            "store": True,
            "get": None,
            "invalidate_by_prefix": 0,
        }

    async def _execute(self, operation: str, *args: Any) -> Any:
        if not self.circuit_breaker.allow_request():
            if self.enable_graceful_degradation:
                logger.debug("Cache operation degraded", operation=operation)
                return self.fallback_responses[operation]
            half_open = self.circuit_breaker.get_state() is CircuitState.HALF_OPEN
            raise CacheError(
                f"Cache {operation} blocked by circuit breaker",
                error_code=(
                    CIRCUIT_BREAKER_THROTTLING if half_open else CIRCUIT_BREAKER_OPEN
                ),
                context={"operation": operation},
            )
        try:
            result = getattr(self.cache_manager, operation)(*args)
            if inspect.isawaitable(result):
                result = await result
        except CacheError as exc:
            if exc.error_code not in CONTENT_REJECTION_CODES:
                return self._handle_failure(operation, exc)
            self.circuit_breaker.record_success()
            if self.enable_graceful_degradation and operation == "store":
                logger.debug("Content not cacheable", error_code=exc.error_code)
                return False
            raise
        except Exception as exc:
            return self._handle_failure(operation, exc)
        self.circuit_breaker.record_success()
        return result

    def _handle_failure(self, operation: str, exc: Exception) -> Any:
        """Record a backend failure, then degrade or raise."""
        self.circuit_breaker.record_failure(exc, operation)
        if self.enable_graceful_degradation:
            logger.warning(
                "Cache operation failed, degrading",
                operation=operation,
                error=str(exc),
            )
            return self.fallback_responses[operation]
        if isinstance(exc, CacheError):
            raise exc
        raise CacheError(
            f"Cache {operation} failed: {exc}",
            error_code="CACHE_OPERATION_FAILED",
            context={"operation": operation},
        ) from exc

    async def store(self, query_hash: str, content: str) -> bool:
        """Store content; returns True when stored (or degraded)."""
        result = await self._execute("store", query_hash, content)
        return bool(result)

    async def get(self, query_hash: str) -> Any:
        """Return the cache entry, or None on a miss or degraded operation."""
        return await self._execute("get", query_hash)

    async def invalidate_by_prefix(self, prefix: str) -> int:
        return int(await self._execute("invalidate_by_prefix", prefix))

    def generate_hash(self, query: str) -> str:
        generator = getattr(self.cache_manager, "generate_hash", None)
        if callable(generator):
            return str(generator(query))
        return hashlib.sha256(query.encode("utf-8")).hexdigest()

    def get_metrics(self) -> Dict[str, Any]:
        cache_metrics: Dict[str, Any] = {}
        getter = getattr(self.cache_manager, "get_metrics", None)
        if callable(getter):
            try:
                raw = getter()
                if is_dataclass(raw) and not isinstance(raw, type):
                    cache_metrics = asdict(raw)
                elif isinstance(raw, dict):
                    cache_metrics = dict(raw)
            except Exception as exc:
                logger.warning("Failed to collect cache metrics", error=str(exc))
                cache_metrics = {"error": str(exc)}
        return {
            "cache": cache_metrics,
            "circuit_breaker": self.circuit_breaker.get_metrics().to_dict(),
            "graceful_degradation": self.enable_graceful_degradation,
        }

    async def start_monitoring(self) -> None:
        await self.circuit_breaker.start_health_monitoring()

    async def stop_monitoring(self) -> None:
        await self.circuit_breaker.stop_health_monitoring()
