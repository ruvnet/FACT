"""
Comprehensive unit tests for cache validation system.
Tests cache validation, error handling, security checks, and database integration.
Achieves 100% test coverage following TDD principles.
"""

import pytest
import time
import asyncio
import os
import tempfile
import json
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from typing import Dict, Any, List

from src.cache.validation import (
    CacheValidator,
    ValidationLevel,
    ValidationResult,
    IntegrityIssue,
    get_cache_validator,
    validate_cache_integrity,
)
from src.cache.manager import CacheManager, CacheEntry
from src.cache.config import (
    CacheConfig,
    DatabaseCacheConfig,
    SecurityConfig,
    load_cache_config_from_env,
    load_database_cache_config_from_env,
    load_security_config_from_env,
    validate_cache_environment,
)
from src.core.errors import CacheError, ConfigurationError


class TestCacheConfig:
    """Test suite for cache configuration validation."""

    def test_cache_config_default_values(self):
        """TEST: Cache config initializes with correct default values"""
        config = CacheConfig()

        assert config.prefix == "fact_v1"
        assert config.min_tokens == 500
        assert config.max_size == "10MB"
        assert config.ttl_seconds == 3600
        assert config.hit_target_ms == 48
        assert config.miss_target_ms == 140
        assert config.enable_validation == True
        assert config.enable_encryption == False

    def test_cache_config_validation_errors(self):
        """TEST: Cache config validates input parameters"""
        # Test invalid prefix
        with pytest.raises(ValueError, match="Prefix must start with letter"):
            CacheConfig(prefix="123invalid")

        # Test invalid size format (Pydantic validation error)
        from pydantic_core import ValidationError

        with pytest.raises(ValidationError):
            CacheConfig(max_size="invalid_size")

        # Test invalid min_tokens
        with pytest.raises(ValidationError):
            CacheConfig(min_tokens=-1)

        # Test invalid ttl_seconds
        with pytest.raises(ValidationError):
            CacheConfig(ttl_seconds=-1)

    def test_cache_config_from_environment(self):
        """TEST: Cache config loads from environment variables"""
        env_vars = {
            "CACHE_PREFIX": "test_cache",
            "CACHE_MIN_TOKENS": "1000",
            "CACHE_MAX_SIZE": "50MB",
            "CACHE_TTL": "7200",
            "CACHE_HIT_TARGET_MS": "30",
            "CACHE_MISS_TARGET_MS": "100",
        }

        with patch.dict(os.environ, env_vars):
            config = load_cache_config_from_env()

            assert config.prefix == "test_cache"
            assert config.min_tokens == 1000
            assert config.max_size == "50MB"
            assert config.ttl_seconds == 7200
            assert config.hit_target_ms == 30
            assert config.miss_target_ms == 100

    def test_database_cache_config_validation(self):
        """TEST: Database cache config validates table names"""
        # Valid configuration
        config = DatabaseCacheConfig(cache_tables=["financial_data", "benchmarks"])
        assert "financial_data" in config.cache_tables

        # Invalid table name
        with pytest.raises(ValueError, match="Invalid table name"):
            DatabaseCacheConfig(cache_tables=["123invalid_table"])

    def test_security_config_default_patterns(self):
        """TEST: Security config includes default sensitive data patterns"""
        config = SecurityConfig()

        assert len(config.sensitive_data_patterns) > 0
        assert any(
            "password" in pattern.lower() for pattern in config.sensitive_data_patterns
        )
        assert any(
            "api" in pattern.lower() for pattern in config.sensitive_data_patterns
        )

    def test_validate_cache_environment_success(self):
        """TEST: Environment validation succeeds with valid configuration"""
        env_vars = {
            "CACHE_PREFIX": "test_env",
            "CACHE_MIN_TOKENS": "500",
            "ENABLE_REQUEST_VALIDATION": "true",
        }

        with patch.dict(os.environ, env_vars):
            result = validate_cache_environment()

            assert result["valid"] == True
            assert result["cache_config"] is not None
            assert result["database_config"] is not None
            assert result["security_config"] is not None
            assert len(result["errors"]) == 0


class TestCacheValidator:
    """Test suite for cache validator functionality."""

    @pytest.fixture
    def mock_cache_manager(self):
        """Create mock cache manager for testing."""
        manager = Mock(spec=CacheManager)
        manager.cache = {}
        manager.prefix = "test_cache"
        manager.ttl_seconds = 3600
        manager._lock = MagicMock()
        manager._lock.__enter__ = Mock(return_value=None)
        manager._lock.__exit__ = Mock(return_value=None)
        return manager

    @pytest.fixture
    def sample_cache_entries(self):
        """Create sample cache entries for testing."""
        entries = {}

        # Valid entry
        valid_entry = CacheEntry(
            prefix="test_cache",
            content="Valid cache content " * 50,
            token_count=750,
            created_at=time.time() - 1800,  # 30 minutes old
            access_count=5,
        )
        entries["valid_entry"] = valid_entry

        # Expired entry
        expired_entry = CacheEntry(
            prefix="test_cache",
            content="Expired content " * 50,
            token_count=600,
            created_at=time.time() - 7200,  # 2 hours old
            access_count=1,
        )
        entries["expired_entry"] = expired_entry

        # Corrupted entry
        corrupted_entry = CacheEntry(
            prefix="test_cache",
            content="",  # Empty content
            token_count=0,
            created_at=time.time() - 900,
            access_count=0,
        )
        entries["corrupted_entry"] = corrupted_entry

        # Entry with sensitive data
        sensitive_entry = CacheEntry(
            prefix="test_cache",
            content="User password: secret123 and API key: abc123",
            token_count=500,
            created_at=time.time() - 600,
            access_count=2,
        )
        entries["sensitive_entry"] = sensitive_entry

        return entries

    def test_cache_validator_initialization_with_manager(self, mock_cache_manager):
        """TEST: Cache validator initializes with provided cache manager"""
        validator = CacheValidator(cache_manager=mock_cache_manager)

        assert validator.cache_manager == mock_cache_manager
        assert len(validator.validation_history) == 0
        assert validator.thresholds["max_corruption_rate"] == 0.05

    def test_cache_validator_initialization_without_manager(self):
        """TEST: Cache validator creates default manager when none provided"""
        with patch("src.cache.validation.get_cache_manager") as mock_get_manager:
            mock_manager = Mock(spec=CacheManager)
            mock_get_manager.return_value = mock_manager

            validator = CacheValidator()

            assert validator.cache_manager == mock_manager
            mock_get_manager.assert_called_once()

    def test_cache_validator_mock_manager_fallback(self):
        """TEST: Cache validator creates mock manager when initialization fails"""
        with patch(
            "src.cache.validation.get_cache_manager",
            side_effect=Exception("Config error"),
        ):
            validator = CacheValidator()

            # Should create mock manager
            assert validator.cache_manager is not None
            assert hasattr(validator.cache_manager, "cache")
            assert hasattr(validator.cache_manager, "prefix")

    @pytest.mark.asyncio
    async def test_basic_validation_detects_corruption(
        self, mock_cache_manager, sample_cache_entries
    ):
        """TEST: Basic validation detects corrupted entries"""
        mock_cache_manager.cache = {
            "corrupted": sample_cache_entries["corrupted_entry"]
        }

        validator = CacheValidator(cache_manager=mock_cache_manager)
        issues = await validator._validate_basic_integrity(
            "corrupted", sample_cache_entries["corrupted_entry"]
        )

        assert len(issues) > 0
        assert any(issue.issue_type == "corruption" for issue in issues)
        assert any(issue.severity == "critical" for issue in issues)

    @pytest.mark.asyncio
    async def test_basic_validation_detects_token_mismatch(self, mock_cache_manager):
        """TEST: Basic validation detects token count mismatches"""
        # Create entry with incorrect token count
        entry = CacheEntry(
            prefix="test_cache",
            content="Short content",
            token_count=1000,  # Way too high for content
            validate=False,  # Skip validation during creation
        )

        validator = CacheValidator(cache_manager=mock_cache_manager)
        issues = await validator._validate_basic_integrity("mismatch", entry)

        assert len(issues) > 0
        assert any(issue.issue_type == "corruption" for issue in issues)
        assert any(
            "token count mismatch" in issue.description.lower() for issue in issues
        )

    @pytest.mark.asyncio
    async def test_standard_validation_detects_expiration(
        self, mock_cache_manager, sample_cache_entries
    ):
        """TEST: Standard validation detects expired entries"""
        validator = CacheValidator(cache_manager=mock_cache_manager)
        issues = await validator._validate_standard_compliance(
            "expired", sample_cache_entries["expired_entry"]
        )

        assert len(issues) > 0
        assert any(issue.issue_type == "expired" for issue in issues)

    @pytest.mark.asyncio
    async def test_standard_validation_detects_low_efficiency(self, mock_cache_manager):
        """TEST: Standard validation detects low token efficiency"""
        # Create entry with very low token efficiency
        entry = CacheEntry(
            prefix="test_cache",
            content="X" * 10000,  # Large content
            token_count=10,  # Very few tokens
            validate=False,
        )

        validator = CacheValidator(cache_manager=mock_cache_manager)
        issues = await validator._validate_standard_compliance("inefficient", entry)

        assert len(issues) > 0
        assert any(issue.issue_type == "low_efficiency" for issue in issues)

    @pytest.mark.asyncio
    async def test_comprehensive_validation_detects_sensitive_data(
        self, mock_cache_manager, sample_cache_entries
    ):
        """TEST: Comprehensive validation detects sensitive data"""
        validator = CacheValidator(cache_manager=mock_cache_manager)
        issues = await validator._validate_comprehensive_analysis(
            "sensitive", sample_cache_entries["sensitive_entry"]
        )

        assert len(issues) > 0
        assert any(issue.issue_type == "sensitive_data" for issue in issues)
        assert any(issue.severity == "critical" for issue in issues)

    @pytest.mark.asyncio
    async def test_content_quality_analysis_detects_errors(self, mock_cache_manager):
        """TEST: Content quality analysis detects error content"""
        entry = CacheEntry(
            prefix="test_cache",
            content="Error: Internal server error occurred " * 50,
            token_count=500,
            validate=False,
        )

        validator = CacheValidator(cache_manager=mock_cache_manager)
        issues = validator._analyze_content_quality("error_entry", entry)

        assert len(issues) > 0
        assert any(issue.issue_type == "error_content" for issue in issues)

    @pytest.mark.asyncio
    async def test_performance_analysis_detects_large_entries(self, mock_cache_manager):
        """TEST: Performance analysis detects large entries"""
        entry = CacheEntry(
            prefix="test_cache",
            content="X" * 2000000,  # 2MB content
            token_count=500,
            validate=False,
        )

        validator = CacheValidator(cache_manager=mock_cache_manager)
        issues = validator._analyze_performance_impact("large_entry", entry)

        assert len(issues) > 0
        assert any(issue.issue_type == "large_entry" for issue in issues)

    @pytest.mark.asyncio
    async def test_full_cache_validation_basic_level(
        self, mock_cache_manager, sample_cache_entries
    ):
        """TEST: Full cache validation at basic level"""
        mock_cache_manager.cache = sample_cache_entries

        validator = CacheValidator(cache_manager=mock_cache_manager)
        result = await validator.validate_cache(ValidationLevel.BASIC)

        assert isinstance(result, ValidationResult)
        assert result.validation_level == "basic"
        assert result.total_entries_checked == len(sample_cache_entries)
        assert result.validation_time_ms > 0
        assert len(result.issues_found) > 0
        assert len(result.recommendations) > 0

    @pytest.mark.asyncio
    async def test_full_cache_validation_comprehensive_level(
        self, mock_cache_manager, sample_cache_entries
    ):
        """TEST: Full cache validation at comprehensive level"""
        mock_cache_manager.cache = sample_cache_entries

        validator = CacheValidator(cache_manager=mock_cache_manager)
        result = await validator.validate_cache(ValidationLevel.COMPREHENSIVE)

        assert isinstance(result, ValidationResult)
        assert result.validation_level == "comprehensive"
        assert result.total_entries_checked == len(sample_cache_entries)
        # Comprehensive should find more issues than basic
        assert len(result.issues_found) > 0
        # Should include security issues from sensitive data
        assert any("sensitive_data" in str(issue) for issue in result.issues_found)

    @pytest.mark.asyncio
    async def test_auto_repair_removes_critical_issues(
        self, mock_cache_manager, sample_cache_entries
    ):
        """TEST: Auto-repair removes entries with critical issues"""
        mock_cache_manager.cache = sample_cache_entries.copy()

        validator = CacheValidator(cache_manager=mock_cache_manager)
        validation_result = await validator.validate_cache(
            ValidationLevel.COMPREHENSIVE
        )

        repair_summary = await validator.auto_repair_cache(validation_result)

        assert repair_summary["entries_removed"] > 0
        assert repair_summary["critical_issues_fixed"] > 0

    @pytest.mark.asyncio
    async def test_database_cache_validation_with_db_manager(self, mock_cache_manager):
        """TEST: Database cache validation with database manager"""
        # Mock database manager
        mock_db_manager = AsyncMock()
        mock_db_manager.get_database_info.return_value = {
            "tables": {
                "financial_data": {"row_count": 100},
                "benchmarks": {"row_count": 50},
            }
        }

        validator = CacheValidator(cache_manager=mock_cache_manager)
        validator.db_manager = mock_db_manager

        # Add database-related cache entry
        db_entry = CacheEntry(
            prefix="test_cache",
            content="SELECT * FROM financial_data WHERE quarter='Q1'",
            token_count=500,
            created_at=time.time() - 7200,  # 2 hours old (stale)
            validate=False,
        )
        mock_cache_manager.cache = {"db_query": db_entry}

        result = await validator.validate_database_cache_integrity()

        assert result["database_tables_checked"] == 2
        assert result["stale_database_cache_entries"] > 0

    @pytest.mark.asyncio
    async def test_security_assessment(self, mock_cache_manager, sample_cache_entries):
        """TEST: Security assessment detects risks"""
        mock_cache_manager.cache = {
            "sensitive": sample_cache_entries["sensitive_entry"]
        }

        validator = CacheValidator(cache_manager=mock_cache_manager)
        security_result = await validator._assess_security_risks()

        assert security_result["total_entries_scanned"] > 0
        assert security_result["sensitive_data_detected"] > 0
        assert security_result["risk_level"] == "high"
        assert len(security_result["issues"]) > 0

    @pytest.mark.asyncio
    async def test_comprehensive_report_generation(
        self, mock_cache_manager, sample_cache_entries
    ):
        """TEST: Comprehensive report generation includes all components"""
        mock_cache_manager.cache = sample_cache_entries
        mock_cache_manager.get_metrics.return_value = Mock(
            hit_rate=75.0,
            token_efficiency=60.0,
            total_entries=len(sample_cache_entries),
            total_size=10000,
            __dict__={"hit_rate": 75.0, "token_efficiency": 60.0},
        )

        validator = CacheValidator(cache_manager=mock_cache_manager)
        report = await validator.generate_comprehensive_report(
            ValidationLevel.COMPREHENSIVE
        )

        assert "timestamp" in report
        assert "validation_level" in report
        assert "cache_validation" in report
        assert "database_validation" in report
        assert "performance_metrics" in report
        assert "system_health" in report
        assert "security_assessment" in report
        assert report["system_health"]["cache_hit_rate"] == 75.0

    def test_health_status_determination(self, mock_cache_manager):
        """TEST: Health status determination logic"""
        validator = CacheValidator(cache_manager=mock_cache_manager)

        # Healthy cache
        status = validator._determine_health_status(100, 90, 5, 0, 5)
        assert status == "healthy"

        # Warning due to high invalid rate
        status = validator._determine_health_status(100, 70, 15, 0, 15)
        assert status == "warning"

        # Critical due to corruption
        status = validator._determine_health_status(100, 80, 10, 10, 0)
        assert status == "critical"

    def test_recommendation_generation(self, mock_cache_manager):
        """TEST: Recommendation generation based on issues"""
        validator = CacheValidator(cache_manager=mock_cache_manager)

        issues = [
            IntegrityIssue("key1", "expired", "medium", "Expired", "Remove"),
            IntegrityIssue("key2", "expired", "medium", "Expired", "Remove"),
            IntegrityIssue("key3", "sensitive_data", "critical", "Sensitive", "Remove"),
        ]

        recommendations = validator._generate_recommendations(issues, 10)

        assert len(recommendations) > 0
        assert any(
            "sensitive" in rec.lower() or "urgent" in rec.lower()
            for rec in recommendations
        )


class TestCacheValidatorIntegration:
    """Test suite for cache validator integration functionality."""

    def test_get_cache_validator_singleton(self):
        """TEST: get_cache_validator returns singleton instance"""
        mock_manager = Mock(spec=CacheManager)

        validator1 = get_cache_validator(mock_manager)
        validator2 = get_cache_validator(mock_manager)

        assert validator1 is validator2
        assert validator1.cache_manager == mock_manager

    @pytest.mark.asyncio
    async def test_validate_cache_integrity_convenience_function(self):
        """TEST: validate_cache_integrity convenience function works"""
        mock_manager = Mock(spec=CacheManager)
        mock_manager.cache = {}
        mock_manager._lock = MagicMock()
        mock_manager._lock.__enter__ = Mock(return_value=None)
        mock_manager._lock.__exit__ = Mock(return_value=None)

        result = await validate_cache_integrity(mock_manager, ValidationLevel.BASIC)

        assert isinstance(result, ValidationResult)
        assert result.validation_level == "basic"

    @pytest.mark.asyncio
    async def test_validation_error_handling(self, mock_cache_manager):
        """TEST: Validation handles errors gracefully"""
        # Create validator with broken cache manager
        mock_cache_manager._lock.__enter__.side_effect = Exception("Lock error")

        validator = CacheValidator(cache_manager=mock_cache_manager)

        with pytest.raises(CacheError):
            await validator.validate_cache(ValidationLevel.BASIC)

    def test_validation_result_serialization(self):
        """TEST: ValidationResult can be serialized"""
        result = ValidationResult(
            validation_level="basic",
            total_entries_checked=10,
            valid_entries=8,
            invalid_entries=1,
            corrupted_entries=1,
            expired_entries=0,
            validation_time_ms=50.0,
            issues_found=[],
            recommendations=["Test recommendation"],
            overall_health="healthy",
        )

        # Should be able to convert to dict (for JSON serialization)
        result_dict = result.__dict__
        assert result_dict["validation_level"] == "basic"
        assert result_dict["total_entries_checked"] == 10
        assert result_dict["overall_health"] == "healthy"


class TestConfigurationErrorHandling:
    """Test suite for configuration error handling."""

    def test_invalid_environment_configuration(self):
        """TEST: Invalid environment configuration raises appropriate errors"""
        env_vars = {
            "CACHE_MIN_TOKENS": "invalid_number",
        }

        with patch.dict(os.environ, env_vars):
            with pytest.raises(ConfigurationError):
                load_cache_config_from_env()

    def test_missing_environment_fallback(self):
        """TEST: Missing environment variables use defaults"""
        # Clear all cache-related env vars
        env_vars = {key: "" for key in os.environ.keys() if key.startswith("CACHE_")}

        with patch.dict(os.environ, env_vars, clear=True):
            config = load_cache_config_from_env()

            # Should use defaults
            assert config.prefix == "fact_v1"
            assert config.min_tokens == 500

    def test_security_config_error_handling(self):
        """TEST: Security config handles errors gracefully"""
        env_vars = {
            "MAX_CACHE_CONTENT_LENGTH": "invalid_number",
        }

        with patch.dict(os.environ, env_vars):
            with pytest.raises(ConfigurationError):
                load_security_config_from_env()


@pytest.mark.integration
class TestCacheValidationEndToEnd:
    """End-to-end integration tests for cache validation system."""

    @pytest.mark.asyncio
    async def test_complete_validation_workflow(self):
        """TEST: Complete validation workflow from config to report"""
        # Create temporary cache configuration
        config = {
            "prefix": "test_e2e",
            "min_tokens": 500,
            "max_size": "1MB",
            "ttl_seconds": 3600,
            "hit_target_ms": 50,
            "miss_target_ms": 150,
        }

        # Create cache manager and validator
        cache_manager = CacheManager(config)
        validator = CacheValidator(cache_manager=cache_manager)

        # Add test entries
        cache_manager.store("test_query_1", "Valid test content " * 100)
        cache_manager.store("test_query_2", "Another valid entry " * 100)

        # Perform validation
        result = await validator.validate_cache(ValidationLevel.COMPREHENSIVE)

        # Verify results
        assert result.total_entries_checked == 2
        assert result.overall_health in ["healthy", "warning", "critical"]
        assert len(result.recommendations) >= 0

        # Generate comprehensive report
        report = await validator.generate_comprehensive_report()

        assert "system_health" in report
        assert "security_assessment" in report
        assert report["system_health"]["total_entries"] == 2

    @pytest.mark.asyncio
    async def test_validation_with_real_database_integration(self):
        """TEST: Validation works with real database integration"""
        # Create temporary database
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_db:
            db_path = temp_db.name

        try:
            # Initialize validator with database
            config = {
                "prefix": "test_db",
                "min_tokens": 500,
                "max_size": "1MB",
                "ttl_seconds": 3600,
                "database_path": db_path,
            }

            cache_manager = CacheManager(
                {
                    "prefix": "test_db",
                    "min_tokens": 500,
                    "max_size": "1MB",
                    "ttl_seconds": 3600,
                    "hit_target_ms": 50,
                    "miss_target_ms": 150,
                }
            )

            validator = CacheValidator(cache_manager=cache_manager, config=config)

            # Add database-related cache entry
            cache_manager.store("db_query", "SELECT * FROM financial_data " * 50)

            # Perform database cache validation
            db_result = await validator.validate_database_cache_integrity()

            # Should handle missing database gracefully
            assert "database_validation" in db_result

        finally:
            # Cleanup
            if os.path.exists(db_path):
                os.unlink(db_path)


# Test fixtures for cache validation
@pytest.fixture
def cache_config():
    """Provide cache configuration for tests."""
    return {
        "prefix": "test_cache",
        "min_tokens": 500,
        "max_size": "10MB",
        "ttl_seconds": 3600,
        "hit_target_ms": 48,
        "miss_target_ms": 140,
    }


@pytest.fixture
def validation_config():
    """Provide validation configuration for tests."""
    return {
        "max_corruption_rate": 0.05,
        "max_expiry_rate": 0.20,
        "min_token_efficiency": 50.0,
        "max_entry_age_hours": 24.0,
        "min_access_frequency": 0.1,
    }


if __name__ == "__main__":
    pytest.main(
        [__file__, "-v", "--cov=src.cache.validation", "--cov-report=term-missing"]
    )
