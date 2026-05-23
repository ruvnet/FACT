"""
FACT System Security Configuration

This module provides centralized security configuration management
for all security components including encryption, authentication,
validation, and monitoring.
"""

import os
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from cryptography.fernet import Fernet
import structlog

from core.errors import ConfigurationError, SecurityError

logger = structlog.get_logger(__name__)


@dataclass
class AuthConfig:
    """Authentication and authorization configuration."""

    # Token settings
    token_lifetime_seconds: int = 3600  # 1 hour
    refresh_token_lifetime_seconds: int = 86400  # 24 hours
    token_entropy_bytes: int = 32  # 256 bits
    max_token_per_user: int = 10

    # OAuth settings
    oauth_client_id: Optional[str] = None
    oauth_client_secret: Optional[str] = None
    oauth_redirect_uri: Optional[str] = None

    # Session settings
    session_timeout_seconds: int = 1800  # 30 minutes
    max_sessions_per_user: int = 5

    # Security settings
    require_https: bool = True
    enforce_csrf_protection: bool = True
    min_password_length: int = 12


@dataclass
class ValidationConfig:
    """Input validation and sanitization configuration."""

    # String limits
    max_string_length: int = 10000
    max_url_length: int = 2000
    max_email_length: int = 254
    max_filename_length: int = 255
    max_path_length: int = 4096

    # List and object limits
    max_list_items: int = 1000
    max_object_properties: int = 100
    max_nesting_depth: int = 10

    # Content validation
    allow_html: bool = False
    allow_javascript: bool = False
    allow_file_uploads: bool = False

    # Encoding settings
    default_encoding: str = "utf-8"
    sanitize_unicode: bool = True


@dataclass
class EncryptionConfig:
    """Encryption configuration for data protection."""

    # Algorithm settings
    encryption_algorithm: str = "Fernet"
    key_derivation_iterations: int = 100000
    hmac_algorithm: str = "sha256"

    # Key management
    encryption_key: Optional[bytes] = None
    key_rotation_interval_days: int = 90

    # Cache encryption
    encrypt_cache_content: bool = True
    cache_encryption_key: Optional[bytes] = None

    # Database encryption
    encrypt_sensitive_fields: bool = True
    sensitive_field_names: List[str] = field(
        default_factory=lambda: [
            "password",
            "token",
            "secret",
            "key",
            "auth",
            "credential",
        ]
    )


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""

    # Global rate limits
    global_requests_per_minute: int = 1000
    global_requests_per_hour: int = 10000

    # Per-user rate limits
    user_requests_per_minute: int = 60
    user_requests_per_hour: int = 1000

    # Tool-specific rate limits
    tool_requests_per_minute: int = 30
    tool_requests_per_hour: int = 500

    # Authentication rate limits
    auth_attempts_per_minute: int = 5
    auth_attempts_per_hour: int = 20

    # Rate limit enforcement
    enable_rate_limiting: bool = True
    rate_limit_storage: str = "memory"  # "memory" or "redis"
    rate_limit_key_prefix: str = "fact_rate_limit"


@dataclass
class SecurityMonitoringConfig:
    """Security monitoring and alerting configuration."""

    # Logging settings
    log_security_events: bool = True
    log_level: str = "INFO"
    log_sensitive_data: bool = False

    # Alert thresholds
    failed_auth_threshold: int = 10
    rate_limit_violation_threshold: int = 5
    suspicious_activity_threshold: int = 3

    # Monitoring features
    enable_intrusion_detection: bool = True
    enable_anomaly_detection: bool = False
    monitor_file_access: bool = True
    monitor_network_requests: bool = True

    # Data retention
    security_log_retention_days: int = 90
    audit_log_retention_days: int = 365


@dataclass
class NetworkSecurityConfig:
    """Network security configuration."""

    # HTTPS settings
    enforce_https: bool = True
    hsts_max_age: int = 31536000  # 1 year

    # CORS settings
    cors_enabled: bool = True
    cors_allowed_origins: List[str] = field(
        default_factory=lambda: ["https://*.example.com"]
    )
    cors_allowed_methods: List[str] = field(
        default_factory=lambda: ["GET", "POST", "PUT", "DELETE"]
    )
    cors_max_age: int = 86400  # 24 hours

    # Request filtering
    block_private_ips: bool = True
    block_localhost: bool = True
    allowed_schemes: List[str] = field(default_factory=lambda: ["https"])

    # Timeout settings
    request_timeout: int = 30
    connection_timeout: int = 10
    read_timeout: int = 30


@dataclass
class SecurityConfig:
    """Main security configuration container."""

    auth: AuthConfig = field(default_factory=AuthConfig)
    validation: ValidationConfig = field(default_factory=ValidationConfig)
    encryption: EncryptionConfig = field(default_factory=EncryptionConfig)
    rate_limiting: RateLimitConfig = field(default_factory=RateLimitConfig)
    monitoring: SecurityMonitoringConfig = field(
        default_factory=SecurityMonitoringConfig
    )
    network: NetworkSecurityConfig = field(default_factory=NetworkSecurityConfig)

    # Global security settings
    debug_mode: bool = False
    strict_mode: bool = True
    security_headers_enabled: bool = True

    def __post_init__(self):
        """Validate configuration after initialization."""
        self._validate_config()
        self._setup_encryption_keys()

    def _validate_config(self):
        """Validate security configuration."""
        # Validate auth config
        if self.auth.token_lifetime_seconds < 300:  # 5 minutes minimum
            raise ConfigurationError("Token lifetime must be at least 5 minutes")

        if self.auth.token_lifetime_seconds > 86400:  # 24 hours maximum
            raise ConfigurationError("Token lifetime cannot exceed 24 hours")

        # Validate validation config
        if self.validation.max_string_length > 100 * 1024 * 1024:  # 100MB
            raise ConfigurationError("Maximum string length too large")

        # Validate rate limiting
        if (
            self.rate_limiting.user_requests_per_minute
            > self.rate_limiting.global_requests_per_minute
        ):
            raise ConfigurationError("User rate limit cannot exceed global rate limit")

        # Validate encryption
        if self.encryption.key_derivation_iterations < 10000:
            raise ConfigurationError("Key derivation iterations too low")

        logger.info("Security configuration validated successfully")

    def _setup_encryption_keys(self):
        """Setup encryption keys if not provided."""
        if self.encryption.encryption_key is None:
            self.encryption.encryption_key = Fernet.generate_key()
            logger.info("Generated new encryption key")

        if self.encryption.cache_encryption_key is None:
            self.encryption.cache_encryption_key = Fernet.generate_key()
            logger.info("Generated new cache encryption key")

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary (excluding sensitive data)."""
        config_dict = {
            "auth": {
                "token_lifetime_seconds": self.auth.token_lifetime_seconds,
                "session_timeout_seconds": self.auth.session_timeout_seconds,
                "require_https": self.auth.require_https,
                "enforce_csrf_protection": self.auth.enforce_csrf_protection,
                "min_password_length": self.auth.min_password_length,
                "oauth_configured": bool(self.auth.oauth_client_id),
            },
            "validation": {
                "max_string_length": self.validation.max_string_length,
                "max_list_items": self.validation.max_list_items,
                "max_nesting_depth": self.validation.max_nesting_depth,
                "allow_html": self.validation.allow_html,
                "allow_javascript": self.validation.allow_javascript,
            },
            "encryption": {
                "encryption_algorithm": self.encryption.encryption_algorithm,
                "encrypt_cache_content": self.encryption.encrypt_cache_content,
                "encrypt_sensitive_fields": self.encryption.encrypt_sensitive_fields,
                "key_rotation_interval_days": self.encryption.key_rotation_interval_days,
            },
            "rate_limiting": {
                "enable_rate_limiting": self.rate_limiting.enable_rate_limiting,
                "user_requests_per_minute": self.rate_limiting.user_requests_per_minute,
                "tool_requests_per_minute": self.rate_limiting.tool_requests_per_minute,
            },
            "monitoring": {
                "log_security_events": self.monitoring.log_security_events,
                "enable_intrusion_detection": self.monitoring.enable_intrusion_detection,
                "security_log_retention_days": self.monitoring.security_log_retention_days,
            },
            "network": {
                "enforce_https": self.network.enforce_https,
                "cors_enabled": self.network.cors_enabled,
                "block_private_ips": self.network.block_private_ips,
                "request_timeout": self.network.request_timeout,
            },
            "global": {
                "debug_mode": self.debug_mode,
                "strict_mode": self.strict_mode,
                "security_headers_enabled": self.security_headers_enabled,
            },
        }

        return config_dict


def load_security_config_from_env() -> SecurityConfig:
    """Load security configuration from environment variables."""
    config = SecurityConfig()

    # Auth configuration
    config.auth.token_lifetime_seconds = int(
        os.getenv("AUTH_TOKEN_LIFETIME", config.auth.token_lifetime_seconds)
    )
    config.auth.oauth_client_id = os.getenv("OAUTH_CLIENT_ID")
    config.auth.oauth_client_secret = os.getenv("OAUTH_CLIENT_SECRET")
    config.auth.oauth_redirect_uri = os.getenv("OAUTH_REDIRECT_URI")

    # Validation configuration
    config.validation.max_string_length = int(
        os.getenv("VALIDATION_MAX_STRING_LENGTH", config.validation.max_string_length)
    )
    config.validation.allow_html = (
        os.getenv("VALIDATION_ALLOW_HTML", "false").lower() == "true"
    )

    # Encryption configuration
    encryption_key_b64 = os.getenv("ENCRYPTION_KEY")
    if encryption_key_b64:
        try:
            import base64

            config.encryption.encryption_key = base64.urlsafe_b64decode(
                encryption_key_b64
            )
        except Exception as e:
            logger.warning(
                "Failed to decode encryption key from environment", error=str(e)
            )

    # Rate limiting configuration
    config.rate_limiting.enable_rate_limiting = (
        os.getenv("RATE_LIMITING_ENABLED", "true").lower() == "true"
    )
    config.rate_limiting.user_requests_per_minute = int(
        os.getenv(
            "RATE_LIMIT_USER_PER_MINUTE", config.rate_limiting.user_requests_per_minute
        )
    )

    # Monitoring configuration
    config.monitoring.log_security_events = (
        os.getenv("LOG_SECURITY_EVENTS", "true").lower() == "true"
    )
    config.monitoring.log_level = os.getenv(
        "SECURITY_LOG_LEVEL", config.monitoring.log_level
    )

    # Network configuration
    config.network.enforce_https = os.getenv("ENFORCE_HTTPS", "true").lower() == "true"

    # Global settings
    config.debug_mode = os.getenv("DEBUG_MODE", "false").lower() == "true"
    config.strict_mode = os.getenv("STRICT_MODE", "true").lower() == "true"

    logger.info("Security configuration loaded from environment")
    return config


def create_security_config(**overrides) -> SecurityConfig:
    """
    Create security configuration with optional overrides.

    Args:
        **overrides: Configuration overrides

    Returns:
        SecurityConfig instance
    """
    # Start with environment-based config
    config = load_security_config_from_env()

    # Apply overrides
    for key, value in overrides.items():
        if hasattr(config, key):
            setattr(config, key, value)
        else:
            logger.warning("Unknown security config override", key=key)

    return config


# Global security configuration instance
_security_config_instance: Optional[SecurityConfig] = None


def get_security_config() -> SecurityConfig:
    """Get global security configuration instance."""
    global _security_config_instance

    if _security_config_instance is None:
        _security_config_instance = load_security_config_from_env()

    return _security_config_instance


def update_security_config(config: SecurityConfig) -> None:
    """Update global security configuration."""
    global _security_config_instance
    _security_config_instance = config
    logger.info("Security configuration updated")


def get_security_headers() -> Dict[str, str]:
    """Get recommended security headers."""
    config = get_security_config()

    headers = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Content-Security-Policy": (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "connect-src 'self' https:; "
            "font-src 'self'; "
            "object-src 'none'; "
            "media-src 'self'; "
            "frame-src 'none';"
        ),
    }

    if config.network.enforce_https:
        headers["Strict-Transport-Security"] = (
            f"max-age={config.network.hsts_max_age}; includeSubDomains"
        )

    return headers


def validate_security_config(config: SecurityConfig) -> List[str]:
    """
    Validate security configuration and return warnings.

    Args:
        config: Security configuration to validate

    Returns:
        List of validation warnings
    """
    warnings = []

    # Check for insecure settings
    if config.debug_mode:
        warnings.append("Debug mode is enabled - disable in production")

    if not config.auth.require_https:
        warnings.append("HTTPS is not required - enable for production")

    if not config.rate_limiting.enable_rate_limiting:
        warnings.append("Rate limiting is disabled - enable for production")

    if not config.encryption.encrypt_cache_content:
        warnings.append("Cache encryption is disabled")

    if config.validation.allow_html:
        warnings.append("HTML input is allowed - potential XSS risk")

    if config.validation.allow_javascript:
        warnings.append("JavaScript input is allowed - high XSS risk")

    # Check for weak settings
    if config.auth.token_lifetime_seconds > 7200:  # 2 hours
        warnings.append("Token lifetime is longer than recommended (>2 hours)")

    if config.rate_limiting.user_requests_per_minute > 120:
        warnings.append("User rate limit is higher than recommended (>120/min)")

    if config.validation.max_string_length > 1024 * 1024:  # 1MB
        warnings.append("Maximum string length is very large (>1MB)")

    return warnings
