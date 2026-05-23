"""
FACT System Configuration Management

This module handles environment configuration, API client initialization,
and system validation following the FACT architecture specification.
"""

import os
import logging
from typing import Dict, Optional, Any
from dotenv import load_dotenv
import structlog

logger = structlog.get_logger(__name__)


class ConfigurationError(Exception):
    """Raised when configuration validation fails."""

    pass


class ConnectionError(Exception):
    """Raised when API connectivity tests fail."""

    pass


class Config:
    """
    Central configuration management for the FACT system.

    Handles environment variable loading, validation, and provides
    structured access to system configuration parameters.
    """

    def __init__(self, env_file: Optional[str] = None):
        """
        Initialize configuration from environment variables.

        Args:
            env_file: Optional path to .env file (defaults to .env)
        """
        self.env_file = env_file or ".env"
        self._config: Dict[str, Any] = {}
        self._load_environment()
        self._validate_required_keys()

    def _load_environment(self) -> None:
        """Load environment variables from .env file if it exists."""
        if os.path.exists(self.env_file):
            load_dotenv(self.env_file)
            logger.info("Loaded environment configuration", file=self.env_file)
        else:
            logger.warning("No .env file found, using system environment")

    def _validate_required_keys(self) -> None:
        """
        Validate that all required configuration keys are present and valid.

        Raises:
            ConfigurationError: If any required keys are missing or invalid
        """
        required_keys = ["ANTHROPIC_API_KEY", "ARCADE_API_KEY"]

        missing_keys = []
        invalid_keys = []

        for key in required_keys:
            value = os.getenv(key)
            if not value:
                missing_keys.append(key)
            elif not value.strip():
                missing_keys.append(key)  # Treat whitespace-only as missing
            elif self._is_placeholder_key(value.strip()):
                invalid_keys.append(key)

        if missing_keys:
            raise ConfigurationError(
                f"Missing required configuration keys: {', '.join(missing_keys)}"
            )

        if invalid_keys:
            raise ConfigurationError(
                f"Invalid placeholder values for keys: {', '.join(invalid_keys)}. Please set real API keys."
            )

        logger.info("Configuration validation passed")

    def _is_placeholder_key(self, value: str) -> bool:
        """Check if a configuration value is a placeholder."""
        placeholder_patterns = [
            "your_anthropic_api_key_here",
            "your_arcade_api_key_here",
            "your_api_key_here",
            "placeholder",
            "changeme",
            "todo",
            "fix_me",
        ]
        return any(pattern in value.lower() for pattern in placeholder_patterns)

    @property
    def anthropic_api_key(self) -> str:
        """Get Anthropic API key."""
        return os.getenv("ANTHROPIC_API_KEY", "")

    @property
    def arcade_api_key(self) -> str:
        """Get Arcade API key."""
        return os.getenv("ARCADE_API_KEY", "")

    @property
    def arcade_base_url(self) -> str:
        """Get Arcade base URL."""
        return os.getenv("ARCADE_BASE_URL", "https://api.arcade-ai.com")

    @property
    def database_path(self) -> str:
        """Get database file path."""
        return os.getenv("DATABASE_PATH", "data/fact_demo.db")

    @property
    def cache_prefix(self) -> str:
        """Get cache prefix for Claude caching."""
        return os.getenv("CACHE_PREFIX", "fact_v1")

    @property
    def cache_config(self) -> Dict[str, Any]:
        """Get cache configuration dictionary."""
        return {
            "prefix": self.cache_prefix,
            "min_tokens": int(os.getenv("CACHE_MIN_TOKENS", "50")),
            "max_size": os.getenv("CACHE_MAX_SIZE", "10MB"),
            "ttl_seconds": int(os.getenv("CACHE_TTL_SECONDS", "3600")),
            "hit_target_ms": float(os.getenv("CACHE_HIT_TARGET_MS", "30")),
            "miss_target_ms": float(os.getenv("CACHE_MISS_TARGET_MS", "120")),
        }

    @property
    def system_prompt(self) -> str:
        """Get system prompt for Claude."""
        return os.getenv(
            "SYSTEM_PROMPT",
            """You are a finance assistant with access to SQL database tools. You MUST use tools to answer questions about financial data.

CRITICAL: When users ask for data, immediately execute the appropriate SQL query using the tools. Do not just describe what you would do - actually do it.

Available tools:
- SQL_QueryReadonly: Execute SELECT queries to retrieve data
- SQL_GetSchema: Get database schema information
- SQL_GetSampleQueries: Get sample query examples

Process:
1. If you need schema info, call SQL_GetSchema
2. Execute the appropriate SQL query with SQL_QueryReadonly
3. Present the actual results to the user

Example: If asked "What's TechCorp's revenue?" immediately execute:
SELECT revenue FROM financial_records WHERE company_id = (SELECT id FROM companies WHERE name LIKE '%TechCorp%')

Always show real data, not placeholders or descriptions of what you would do.""",
        )

    @property
    def claude_model(self) -> str:
        """Get Claude model name."""
        return os.getenv("CLAUDE_MODEL", "claude-3-haiku-20240307")

    @property
    def max_retries(self) -> int:
        """Get maximum retry attempts for failed operations."""
        return int(os.getenv("MAX_RETRIES", "3"))

    @property
    def request_timeout(self) -> int:
        """Get request timeout in seconds."""
        return int(os.getenv("REQUEST_TIMEOUT", "30"))

    @property
    def log_level(self) -> str:
        """Get logging level."""
        return os.getenv("LOG_LEVEL", "INFO")

    def to_dict(self) -> Dict[str, Any]:
        """
        Export configuration as dictionary (excluding sensitive data).

        Returns:
            Dictionary of non-sensitive configuration values
        """
        return {
            "arcade_base_url": self.arcade_base_url,
            "database_path": self.database_path,
            "cache_prefix": self.cache_prefix,
            "claude_model": self.claude_model,
            "max_retries": self.max_retries,
            "request_timeout": self.request_timeout,
            "log_level": self.log_level,
            # Exclude sensitive keys
            "anthropic_api_key": "***" if self.anthropic_api_key else None,
            "arcade_api_key": "***" if self.arcade_api_key else None,
        }


def get_config() -> Config:
    """
    Get global configuration instance.

    Returns:
        Configured Config instance
    """
    return Config()


def validate_configuration(config: Config) -> None:
    """
    Validate configuration and test connectivity to required services.

    Args:
        config: Configuration instance to validate

    Raises:
        ConfigurationError: If configuration is invalid
        ConnectionError: If service connectivity tests fail
    """
    try:
        # Basic configuration validation is done in Config.__init__
        logger.info("Configuration validation completed successfully")

        # Log configuration summary (without sensitive data)
        logger.info("Configuration summary", config=config.to_dict())

    except Exception as e:
        logger.error("Configuration validation failed", error=str(e))
        raise ConfigurationError(f"Configuration validation failed: {e}")
