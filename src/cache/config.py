"""
FACT System Cache Configuration

Typed, validated configuration objects for the cache subsystem:

* ``CacheConfig``          - core cache behaviour (prefix, size, TTL, latency targets)
* ``DatabaseCacheConfig``  - which database tables feed cached content
* ``SecurityConfig``       - input validation / output sanitization settings

plus loaders that build them from environment variables and a helper that
validates the whole cache environment in one call.

Environment variables (empty values are treated as unset):

    CACHE_PREFIX, CACHE_MIN_TOKENS, CACHE_MAX_SIZE, CACHE_TTL (or CACHE_TTL_SECONDS),
    CACHE_HIT_TARGET_MS, CACHE_MISS_TARGET_MS, CACHE_ENABLE_VALIDATION,
    CACHE_ENCRYPTION_KEY (presence enables encryption),
    DATABASE_PATH, CACHE_TABLES (comma separated), CACHE_DATABASE_ENABLED,
    CACHE_INVALIDATE_ON_SCHEMA_CHANGE, CACHE_STALE_AFTER_SECONDS,
    ENABLE_REQUEST_VALIDATION, ENABLE_OUTPUT_SANITIZATION, MAX_CACHE_CONTENT_LENGTH
"""

import os
import re
from typing import Any, Callable, Dict, List, Optional, TypeVar

import structlog
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic import ValidationError as PydanticValidationError

try:
    # Try relative imports first (when used as package)
    from ..core.errors import ConfigurationError
except ImportError:
    # Fall back to absolute imports (when run as script)
    import sys
    from pathlib import Path

    src_path = str(Path(__file__).parent.parent)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    from core.errors import ConfigurationError  # type: ignore[no-redef]


logger = structlog.get_logger(__name__)

T = TypeVar("T")

_PREFIX_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_\-]*$")
_SIZE_RE = re.compile(r"^(\d+)(KB|MB|GB|B)?$")
_TABLE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}

DEFAULT_SENSITIVE_DATA_PATTERNS: List[str] = [
    r"\bpassword\s*[:=]\s*\S+",
    r"\bpasswd\s*[:=]\s*\S+",
    r"\bapi[_\s-]?key\s*[:=]\s*\S+",
    r"\bsecret[_\s-]?key\s*[:=]\s*\S+",
    r"\b(?:access|auth|bearer)[_\s-]?token\s*[:=]\s*\S+",
    r"\b\d{3}-\d{2}-\d{4}\b",  # US social security number
    r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",  # payment card number
    r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
]


class CacheConfig(BaseModel):
    """Core cache configuration; ``to_dict()`` is accepted by ``CacheManager``."""

    model_config = ConfigDict(validate_assignment=True)

    prefix: str = Field(default="fact_v1", min_length=1, max_length=50)
    min_tokens: int = Field(default=500, ge=1)
    max_size: str = Field(default="10MB")
    ttl_seconds: int = Field(default=3600, ge=0)
    hit_target_ms: float = Field(default=48, gt=0)
    miss_target_ms: float = Field(default=140, gt=0)
    enable_validation: bool = True
    enable_encryption: bool = False

    @field_validator("prefix")
    @classmethod
    def _validate_prefix(cls, value: str) -> str:
        value = value.strip()
        if not _PREFIX_RE.match(value):
            raise ValueError(
                "Prefix must start with letter and contain only letters, digits, "
                "underscores or hyphens"
            )
        return value

    @field_validator("max_size")
    @classmethod
    def _validate_max_size(cls, value: str) -> str:
        normalized = str(value).strip().upper().replace(" ", "")
        match = _SIZE_RE.match(normalized)
        if not match:
            raise ValueError(
                f"Invalid size format '{value}': expected a number with optional "
                "B/KB/MB/GB unit (e.g. '10MB')"
            )
        number, unit = match.groups()
        if int(number) <= 0:
            raise ValueError("max_size must be greater than zero")
        # CacheManager._parse_size understands KB/MB/GB or plain bytes only.
        return number if unit in (None, "B") else f"{number}{unit}"

    @property
    def max_size_bytes(self) -> int:
        """Return ``max_size`` converted to bytes."""
        match = _SIZE_RE.match(self.max_size)
        if match is None:  # the field validator already rejects this
            raise ValueError(f"Invalid max_size: {self.max_size!r}")
        number, unit = int(match.group(1)), match.group(2)
        multiplier = {"KB": 1024, "MB": 1024**2, "GB": 1024**3}.get(unit, 1)
        return number * multiplier

    def to_dict(self) -> Dict[str, Any]:
        """Return a plain dict suitable for ``CacheManager(config)``."""
        return self.model_dump()


class DatabaseCacheConfig(BaseModel):
    """Configuration for caching content derived from database tables."""

    model_config = ConfigDict(validate_assignment=True)

    enabled: bool = True
    database_path: str = "data/fact_demo.db"
    cache_tables: List[str] = Field(
        default_factory=lambda: [
            "companies",
            "financial_records",
            "financial_data",
            "benchmarks",
        ]
    )
    invalidate_on_schema_change: bool = True
    stale_after_seconds: int = Field(default=3600, ge=0)

    @field_validator("cache_tables")
    @classmethod
    def _validate_tables(cls, tables: List[str]) -> List[str]:
        cleaned = []
        for table in tables:
            name = str(table).strip()
            if not _TABLE_RE.match(name):
                raise ValueError(f"Invalid table name: '{table}'")
            cleaned.append(name)
        return cleaned

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class SecurityConfig(BaseModel):
    """
    Security settings for cached content.

    ``sensitive_data_patterns`` are regular expression strings; they are
    compiled (and invalid ones skipped) by the security validator, not here.
    """

    model_config = ConfigDict(validate_assignment=True)

    enable_input_validation: bool = True
    enable_output_sanitization: bool = True
    sensitive_data_patterns: List[str] = Field(
        default_factory=lambda: list(DEFAULT_SENSITIVE_DATA_PATTERNS)
    )
    max_content_length: int = Field(default=1048576, gt=0)  # 1MB

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------


def _env_raw(*names: str) -> Optional[str]:
    """Return the first non-empty value among ``names`` (empty means unset)."""
    for name in names:
        value = os.environ.get(name)
        if value is not None and value.strip() != "":
            return value.strip()
    return None


def _parse_bool(value: str) -> bool:
    lowered = value.lower()
    if lowered in _TRUE_VALUES:
        return True
    if lowered in _FALSE_VALUES:
        return False
    raise ValueError(f"'{value}' is not a boolean")


def _parse_int(value: str) -> int:
    return int(value)


def _parse_float(value: str) -> float:
    return float(value)


def _collect_env(
    kwargs: Dict[str, Any], field: str, parser: Callable[[str], T], *names: str
) -> None:
    """Parse the first set env var among ``names`` into ``kwargs[field]``."""
    raw = _env_raw(*names)
    if raw is None:
        return
    try:
        kwargs[field] = parser(raw)
    except (TypeError, ValueError) as e:
        raise ConfigurationError(
            f"Invalid value for {names[0]}: '{raw}' ({e})",
            error_code="INVALID_CACHE_CONFIGURATION",
            context={"variable": names[0], "value": raw},
        )


def _build(model: Callable[..., T], kwargs: Dict[str, Any], label: str) -> T:
    try:
        return model(**kwargs)
    except PydanticValidationError as e:
        raise ConfigurationError(
            f"Invalid {label} configuration: {e}",
            error_code="INVALID_CACHE_CONFIGURATION",
            context={"errors": e.errors(include_url=False)},
        )


# ---------------------------------------------------------------------------
# Public loaders
# ---------------------------------------------------------------------------


def load_cache_config_from_env() -> CacheConfig:
    """Build a ``CacheConfig`` from ``CACHE_*`` environment variables."""
    kwargs: Dict[str, Any] = {}
    _collect_env(kwargs, "prefix", str, "CACHE_PREFIX")
    _collect_env(kwargs, "min_tokens", _parse_int, "CACHE_MIN_TOKENS")
    _collect_env(kwargs, "max_size", str, "CACHE_MAX_SIZE")
    _collect_env(kwargs, "ttl_seconds", _parse_int, "CACHE_TTL", "CACHE_TTL_SECONDS")
    _collect_env(kwargs, "hit_target_ms", _parse_float, "CACHE_HIT_TARGET_MS")
    _collect_env(kwargs, "miss_target_ms", _parse_float, "CACHE_MISS_TARGET_MS")
    _collect_env(kwargs, "enable_validation", _parse_bool, "CACHE_ENABLE_VALIDATION")
    if _env_raw("CACHE_ENCRYPTION_KEY") is not None:
        kwargs["enable_encryption"] = True

    config = _build(CacheConfig, kwargs, "cache")
    logger.debug("Cache configuration loaded from environment", prefix=config.prefix)
    return config


def load_database_cache_config_from_env() -> DatabaseCacheConfig:
    """Build a ``DatabaseCacheConfig`` from environment variables."""
    kwargs: Dict[str, Any] = {}
    _collect_env(kwargs, "enabled", _parse_bool, "CACHE_DATABASE_ENABLED")
    _collect_env(kwargs, "database_path", str, "DATABASE_PATH")
    _collect_env(
        kwargs,
        "cache_tables",
        lambda raw: [t.strip() for t in raw.split(",") if t.strip()],
        "CACHE_TABLES",
    )
    _collect_env(
        kwargs,
        "invalidate_on_schema_change",
        _parse_bool,
        "CACHE_INVALIDATE_ON_SCHEMA_CHANGE",
    )
    _collect_env(kwargs, "stale_after_seconds", _parse_int, "CACHE_STALE_AFTER_SECONDS")
    return _build(DatabaseCacheConfig, kwargs, "database cache")


def load_security_config_from_env() -> SecurityConfig:
    """Build a ``SecurityConfig`` from environment variables."""
    kwargs: Dict[str, Any] = {}
    _collect_env(
        kwargs, "enable_input_validation", _parse_bool, "ENABLE_REQUEST_VALIDATION"
    )
    _collect_env(
        kwargs, "enable_output_sanitization", _parse_bool, "ENABLE_OUTPUT_SANITIZATION"
    )
    _collect_env(kwargs, "max_content_length", _parse_int, "MAX_CACHE_CONTENT_LENGTH")
    return _build(SecurityConfig, kwargs, "security")


def get_default_cache_config() -> Dict[str, Any]:
    """Return a fresh default cache configuration dict for ``CacheManager``."""
    return CacheConfig().to_dict()


def validate_cache_environment() -> Dict[str, Any]:
    """
    Load and validate every cache-related configuration from the environment.

    Returns:
        Dict with ``valid``, ``cache_config``, ``database_config``,
        ``security_config`` (plain dicts, or None when loading failed),
        ``errors`` and ``warnings``.
    """
    result: Dict[str, Any] = {
        "valid": True,
        "cache_config": None,
        "database_config": None,
        "security_config": None,
        "errors": [],
        "warnings": [],
    }

    loaders = (
        ("cache_config", load_cache_config_from_env),
        ("database_config", load_database_cache_config_from_env),
        ("security_config", load_security_config_from_env),
    )
    loaded: Dict[str, Any] = {}
    for key, loader in loaders:
        try:
            loaded[key] = loader()
            result[key] = loaded[key].to_dict()
        except ConfigurationError as e:
            result["errors"].append(f"{key}: {e.message}")

    cache_config = loaded.get("cache_config")
    if cache_config is not None:
        if cache_config.hit_target_ms >= cache_config.miss_target_ms:
            result["warnings"].append(
                "hit_target_ms should be lower than miss_target_ms"
            )
        if cache_config.ttl_seconds == 0:
            result["warnings"].append("ttl_seconds is 0: cache entries never expire")

    security_config = loaded.get("security_config")
    if security_config is not None and not security_config.enable_input_validation:
        result["warnings"].append("Cache input validation is disabled")

    result["valid"] = not result["errors"]
    if result["valid"]:
        logger.info("Cache environment validated", warnings=len(result["warnings"]))
    else:
        logger.error("Cache environment validation failed", errors=result["errors"])
    return result
