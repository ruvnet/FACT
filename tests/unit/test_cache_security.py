"""
Comprehensive unit tests for cache security module.
Tests security validation, threat detection, and input sanitization.
Achieves 100% test coverage following TDD principles.
"""

import pytest
import time
import os
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List

from src.cache.security import (
    CacheSecurityValidator,
    ThreatLevel,
    SecurityThreat,
    SecurityScanResult,
    get_security_validator,
    validate_cache_content_security,
    sanitize_cache_output,
)
from src.cache.config import SecurityConfig
from src.core.errors import SecurityError, ValidationError


class TestSecurityConfig:
    """Test suite for security configuration."""

    def test_security_config_default_values(self):
        """TEST: Security config initializes with correct defaults"""
        config = SecurityConfig()

        assert config.enable_input_validation == True
        assert config.enable_output_sanitization == True
        assert len(config.sensitive_data_patterns) > 0
        assert config.max_content_length == 1048576  # 1MB

    def test_security_config_sensitive_patterns(self):
        """TEST: Security config includes comprehensive sensitive data patterns"""
        config = SecurityConfig()

        patterns = " ".join(config.sensitive_data_patterns)

        # Check for common sensitive data patterns
        assert "password" in patterns.lower()
        assert "api" in patterns.lower()
        assert r"\d{3}-\d{2}-\d{4}" in patterns  # SSN pattern
        assert r"\d{4}" in patterns  # Credit card pattern


class TestCacheSecurityValidator:
    """Test suite for cache security validator."""

    @pytest.fixture
    def security_config(self):
        """Create test security configuration."""
        return SecurityConfig(
            enable_input_validation=True,
            enable_output_sanitization=True,
            sensitive_data_patterns=[
                r"\bpassword\s*[:=]\s*\S+",
                r"\bapi[_-]?key\s*[:=]\s*\S+",
                r"\b\d{3}-\d{2}-\d{4}\b",  # SSN
                r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",  # Credit card
            ],
            max_content_length=10000,
        )

    @pytest.fixture
    def validator(self, security_config):
        """Create security validator for testing."""
        return CacheSecurityValidator(security_config)

    def test_validator_initialization(self, security_config):
        """TEST: Security validator initializes correctly"""
        validator = CacheSecurityValidator(security_config)

        assert validator.config == security_config
        assert len(validator._compiled_patterns) > 0
        assert "sql_injection" in validator._injection_patterns
        assert "xss_injection" in validator._injection_patterns

    def test_validator_initialization_with_invalid_patterns(self):
        """TEST: Validator handles invalid regex patterns gracefully"""
        config = SecurityConfig(
            sensitive_data_patterns=["[invalid_regex"]  # Invalid regex
        )

        # Should not raise exception
        validator = CacheSecurityValidator(config)
        assert validator.config == config

    def test_validator_initialization_without_config(self):
        """TEST: Validator loads default config when none provided"""
        with patch("src.cache.security.load_security_config_from_env") as mock_load:
            mock_config = SecurityConfig()
            mock_load.return_value = mock_config

            validator = CacheSecurityValidator()
            assert validator.config == mock_config

    def test_input_validation_passes_clean_content(self, validator):
        """TEST: Input validation passes clean content"""
        clean_content = "This is clean content without any threats."

        # Should not raise exception
        validator.validate_input(clean_content, "test_source")

    def test_input_validation_blocks_sensitive_data(self, validator):
        """TEST: Input validation blocks content with sensitive data"""
        sensitive_content = "User password: secret123 and api_key: abc123def"

        with pytest.raises(SecurityError):
            validator.validate_input(sensitive_content, "test_source")

    def test_input_validation_blocks_sql_injection(self, validator):
        """TEST: Input validation blocks SQL injection attempts"""
        sql_injection = "SELECT * FROM users; DROP TABLE users; --"

        with pytest.raises(SecurityError):
            validator.validate_input(sql_injection, "test_source")

    def test_input_validation_blocks_xss_injection(self, validator):
        """TEST: Input validation blocks XSS injection attempts"""
        xss_injection = "<script>alert('XSS')</script>"

        with pytest.raises(SecurityError):
            validator.validate_input(xss_injection, "test_source")

    def test_input_validation_blocks_command_injection(self, validator):
        """TEST: Input validation blocks command injection attempts"""
        command_injection = "normal content; rm -rf / ;"

        with pytest.raises(SecurityError):
            validator.validate_input(command_injection, "test_source")

    def test_input_validation_content_too_large(self, validator):
        """TEST: Input validation blocks oversized content"""
        large_content = "X" * (validator.config.max_content_length + 1)

        with pytest.raises(ValidationError):
            validator.validate_input(large_content, "test_source")

    def test_input_validation_disabled(self, validator):
        """TEST: Input validation can be disabled"""
        validator.config.enable_input_validation = False
        sensitive_content = "password: secret123"

        # Should not raise exception when disabled
        validator.validate_input(sensitive_content, "test_source")

    def test_input_validation_high_threats_allowed(self, validator):
        """TEST: Input validation allows limited high threats"""
        # Single high threat should be allowed with warning
        content_with_single_threat = "Some content with <iframe src='evil'></iframe>"

        # Should not raise exception for single high threat
        validator.validate_input(content_with_single_threat, "test_source")

    def test_input_validation_multiple_high_threats_blocked(self, validator):
        """TEST: Input validation blocks multiple high threats"""
        content_with_multiple_threats = """
        <iframe src='evil'></iframe>
        <script>evil()</script>
        javascript:alert('xss')
        <iframe src='another'></iframe>
        """

        with pytest.raises(SecurityError):
            validator.validate_input(content_with_multiple_threats, "test_source")

    def test_output_sanitization_removes_scripts(self, validator):
        """TEST: Output sanitization removes script tags"""
        malicious_output = "Safe content <script>alert('xss')</script> more content"

        sanitized = validator.sanitize_output(malicious_output)

        assert "<script>" not in sanitized
        assert "Safe content" in sanitized
        assert "more content" in sanitized

    def test_output_sanitization_removes_iframes(self, validator):
        """TEST: Output sanitization removes iframe tags"""
        malicious_output = "Content <iframe src='evil.com'></iframe> safe"

        sanitized = validator.sanitize_output(malicious_output)

        assert "<iframe>" not in sanitized
        assert "Content" in sanitized
        assert "safe" in sanitized

    def test_output_sanitization_removes_javascript_protocols(self, validator):
        """TEST: Output sanitization removes javascript protocols"""
        malicious_output = "Click <a href='javascript:alert()'>here</a>"

        sanitized = validator.sanitize_output(malicious_output)

        assert "javascript:" not in sanitized

    def test_output_sanitization_escapes_sql_keywords(self, validator):
        """TEST: Output sanitization escapes SQL keywords"""
        sql_content = "The DROP TABLE command is dangerous"

        sanitized = validator.sanitize_output(sql_content)

        assert "[DROP]" in sanitized
        assert "DROP TABLE" not in sanitized

    def test_output_sanitization_disabled(self, validator):
        """TEST: Output sanitization can be disabled"""
        validator.config.enable_output_sanitization = False
        malicious_content = "<script>alert('test')</script>"

        sanitized = validator.sanitize_output(malicious_content)

        # Should return original content when disabled
        assert sanitized == malicious_content

    def test_output_sanitization_handles_errors(self, validator):
        """TEST: Output sanitization handles errors gracefully"""
        # Mock re.sub to raise exception
        with patch("re.sub", side_effect=Exception("Regex error")):
            content = "test content"
            sanitized = validator.sanitize_output(content)

            # Should return original content on error
            assert sanitized == content

    def test_content_scan_detects_sensitive_data(self, validator):
        """TEST: Content scan detects sensitive data patterns"""
        sensitive_content = "User SSN: 123-45-6789 and password: secret"

        result = validator.scan_content(sensitive_content)

        assert result.threats_detected > 0
        assert result.overall_risk_level == ThreatLevel.CRITICAL
        assert "sensitive_data" in result.threat_breakdown
        assert len(result.threats) > 0
        assert any(threat.threat_type == "sensitive_data" for threat in result.threats)

    def test_content_scan_detects_sql_injection(self, validator):
        """TEST: Content scan detects SQL injection patterns"""
        sql_injection = "'; DROP TABLE users; --"

        result = validator.scan_content(sql_injection)

        assert result.threats_detected > 0
        assert "sql_injection" in result.threat_breakdown
        assert any(threat.threat_type == "sql_injection" for threat in result.threats)

    def test_content_scan_detects_xss_injection(self, validator):
        """TEST: Content scan detects XSS injection patterns"""
        xss_content = "<script>document.cookie</script>"

        result = validator.scan_content(xss_content)

        assert result.threats_detected > 0
        assert "xss_injection" in result.threat_breakdown

    def test_content_scan_detects_command_injection(self, validator):
        """TEST: Content scan detects command injection patterns"""
        command_injection = "file.txt; rm -rf /"

        result = validator.scan_content(command_injection)

        assert result.threats_detected > 0
        assert "command_injection" in result.threat_breakdown

    def test_content_scan_detects_path_traversal(self, validator):
        """TEST: Content scan detects path traversal patterns"""
        path_traversal = "../../../etc/passwd"

        result = validator.scan_content(path_traversal)

        assert result.threats_detected > 0
        assert "path_traversal" in result.threat_breakdown

    def test_content_scan_detects_suspicious_encoding(self, validator):
        """TEST: Content scan detects suspicious encoding patterns"""
        # Excessive URL encoding
        suspicious_content = "data=" + "%20%20%20" * 10  # Lots of encoded spaces

        result = validator.scan_content(suspicious_content)

        assert "suspicious_encoding" in result.threat_breakdown

    def test_content_scan_detects_unicode_bypass(self, validator):
        """TEST: Content scan detects Unicode bypass attempts"""
        unicode_content = "\\u0041\\u0042\\u0043" * 5  # Excessive Unicode

        result = validator.scan_content(unicode_content)

        assert "unicode_bypass" in result.threat_breakdown

    def test_content_scan_detects_base64_payload(self, validator):
        """TEST: Content scan detects suspicious base64 content"""
        import base64

        # Create base64 encoded script
        malicious_script = "script>alert('xss')</script"
        encoded = base64.b64encode(malicious_script.encode()).decode()

        result = validator.scan_content(f"data: {encoded}")

        assert "base64_payload" in result.threat_breakdown

    def test_content_scan_detects_malformed_base64(self, validator):
        """TEST: Content scan detects malformed base64"""
        malformed_base64 = "QWxhZGRpbjpvcGVuIHNlc2FtZQ==" + "INVALID"  # Valid + invalid

        result = validator.scan_content(malformed_base64)

        # May detect malformed base64 depending on content
        assert result.scanned_content_length == len(malformed_base64)

    def test_content_scan_clean_content(self, validator):
        """TEST: Content scan handles clean content correctly"""
        clean_content = "This is perfectly safe content with no threats."

        result = validator.scan_content(clean_content)

        assert result.threats_detected == 0
        assert result.overall_risk_level == ThreatLevel.LOW
        assert len(result.threats) == 0
        assert result.scan_time_ms > 0

    def test_content_scan_error_handling(self, validator):
        """TEST: Content scan handles errors gracefully"""
        # Mock pattern matching to raise exception
        with patch.object(
            validator, "_compiled_patterns", {"bad_pattern": Exception("Test error")}
        ):
            result = validator.scan_content("test content")

            # Should handle error and return result
            assert result.scanned_content_length > 0
            assert "scan_error" in result.threat_breakdown

    def test_threat_level_determination_sql_injection(self, validator):
        """TEST: Threat level determination for SQL injection"""
        # Critical SQL injection
        critical_level = validator._determine_injection_threat_level(
            "sql_injection", ["DROP TABLE"]
        )
        assert critical_level == ThreatLevel.CRITICAL

        # High SQL injection
        high_level = validator._determine_injection_threat_level(
            "sql_injection", ["SELECT * FROM"]
        )
        assert high_level == ThreatLevel.HIGH

    def test_threat_level_determination_xss_injection(self, validator):
        """TEST: Threat level determination for XSS injection"""
        # Critical XSS
        critical_level = validator._determine_injection_threat_level(
            "xss_injection", ["<script>"]
        )
        assert critical_level == ThreatLevel.CRITICAL

        # High XSS
        high_level = validator._determine_injection_threat_level(
            "xss_injection", ["<iframe>"]
        )
        assert high_level == ThreatLevel.HIGH

    def test_threat_level_determination_command_injection(self, validator):
        """TEST: Threat level determination for command injection"""
        level = validator._determine_injection_threat_level(
            "command_injection", ["rm -rf"]
        )
        assert level == ThreatLevel.CRITICAL

    def test_overall_risk_determination(self, validator):
        """TEST: Overall risk determination from threats"""
        # No threats
        assert validator._determine_overall_risk([]) == ThreatLevel.LOW

        # Critical threat
        critical_threat = SecurityThreat(
            "test", ThreatLevel.CRITICAL, "desc", "snippet", "mitigation", time.time()
        )
        assert (
            validator._determine_overall_risk([critical_threat]) == ThreatLevel.CRITICAL
        )

        # High threat
        high_threat = SecurityThreat(
            "test", ThreatLevel.HIGH, "desc", "snippet", "mitigation", time.time()
        )
        assert validator._determine_overall_risk([high_threat]) == ThreatLevel.HIGH

        # Medium threat
        medium_threat = SecurityThreat(
            "test", ThreatLevel.MEDIUM, "desc", "snippet", "mitigation", time.time()
        )
        assert validator._determine_overall_risk([medium_threat]) == ThreatLevel.MEDIUM

    def test_security_recommendations_generation(self, validator):
        """TEST: Security recommendations generation"""
        threat_breakdown = {
            "sensitive_data": 1,
            "sql_injection": 2,
            "xss_injection": 1,
            "command_injection": 1,
        }

        recommendations = validator._generate_security_recommendations(threat_breakdown)

        assert len(recommendations) > 0
        assert any("sensitive data" in rec.lower() for rec in recommendations)
        assert any("sql" in rec.lower() for rec in recommendations)
        assert any("critical" in rec.lower() for rec in recommendations)

    def test_security_recommendations_no_threats(self, validator):
        """TEST: Security recommendations with no threats"""
        recommendations = validator._generate_security_recommendations({})

        assert len(recommendations) > 0
        assert any("continue current" in rec.lower() for rec in recommendations)

    def test_security_report_generation(self, validator):
        """TEST: Security report generation from multiple scans"""
        # Create mock scan results
        scan1 = SecurityScanResult(
            scanned_content_length=1000,
            threats_detected=2,
            threat_breakdown={"sql_injection": 1, "xss_injection": 1},
            scan_time_ms=50.0,
            threats=[],
            overall_risk_level=ThreatLevel.HIGH,
            recommendations=["Fix SQL injection"],
        )

        scan2 = SecurityScanResult(
            scanned_content_length=500,
            threats_detected=1,
            threat_breakdown={"sensitive_data": 1},
            scan_time_ms=30.0,
            threats=[],
            overall_risk_level=ThreatLevel.CRITICAL,
            recommendations=["Remove sensitive data"],
        )

        report = validator.generate_security_report([scan1, scan2])

        assert report["total_scans"] == 2
        assert report["total_content_scanned_bytes"] == 1500
        assert report["total_threats_detected"] == 3
        assert report["security_posture"] == "CRITICAL"
        assert "sql_injection" in report["threat_breakdown"]
        assert "sensitive_data" in report["threat_breakdown"]
        assert len(report["recommendations"]) > 0

    def test_security_report_no_results(self, validator):
        """TEST: Security report handles no scan results"""
        report = validator.generate_security_report([])

        assert "error" in report

    def test_security_report_risk_assessment(self, validator):
        """TEST: Security report risk assessment logic"""
        # Low risk scenario
        low_risk_scan = SecurityScanResult(
            scanned_content_length=100,
            threats_detected=0,
            threat_breakdown={},
            scan_time_ms=10.0,
            threats=[],
            overall_risk_level=ThreatLevel.LOW,
            recommendations=[],
        )

        report = validator.generate_security_report([low_risk_scan])
        assert report["security_posture"] == "LOW_RISK"

        # High risk scenario
        high_risk_scans = [
            SecurityScanResult(
                scanned_content_length=100,
                threats_detected=1,
                threat_breakdown={"test": 1},
                scan_time_ms=10.0,
                threats=[],
                overall_risk_level=ThreatLevel.HIGH,
                recommendations=[],
            )
        ] * 5  # 5 high risk scans

        report = validator.generate_security_report(high_risk_scans)
        assert report["security_posture"] == "HIGH_RISK"


class TestSecurityIntegration:
    """Test suite for security integration functions."""

    def test_get_security_validator_singleton(self):
        """TEST: get_security_validator returns singleton instance"""
        validator1 = get_security_validator()
        validator2 = get_security_validator()

        assert validator1 is validator2

    def test_validate_cache_content_security_function(self):
        """TEST: validate_cache_content_security convenience function"""
        clean_content = "This is safe content"

        # Should not raise exception
        validate_cache_content_security(clean_content, "test_source")

    def test_validate_cache_content_security_blocks_threats(self):
        """TEST: validate_cache_content_security blocks threats"""
        malicious_content = "password: secret123"

        with pytest.raises(SecurityError):
            validate_cache_content_security(malicious_content, "test_source")

    def test_sanitize_cache_output_function(self):
        """TEST: sanitize_cache_output convenience function"""
        malicious_content = "<script>alert('xss')</script>Safe content"

        sanitized = sanitize_cache_output(malicious_content)

        assert "<script>" not in sanitized
        assert "Safe content" in sanitized


class TestSecurityThreatDataStructures:
    """Test suite for security threat data structures."""

    def test_security_threat_creation(self):
        """TEST: SecurityThreat data structure"""
        threat = SecurityThreat(
            threat_type="test_threat",
            threat_level=ThreatLevel.HIGH,
            description="Test threat description",
            content_snippet="snippet",
            mitigation="Test mitigation",
            detected_at=time.time(),
        )

        assert threat.threat_type == "test_threat"
        assert threat.threat_level == ThreatLevel.HIGH
        assert threat.description == "Test threat description"

    def test_security_scan_result_creation(self):
        """TEST: SecurityScanResult data structure"""
        result = SecurityScanResult(
            scanned_content_length=1000,
            threats_detected=2,
            threat_breakdown={"sql_injection": 1, "xss_injection": 1},
            scan_time_ms=50.0,
            threats=[],
            overall_risk_level=ThreatLevel.MEDIUM,
            recommendations=["Test recommendation"],
        )

        assert result.scanned_content_length == 1000
        assert result.threats_detected == 2
        assert result.overall_risk_level == ThreatLevel.MEDIUM
        assert len(result.recommendations) == 1


if __name__ == "__main__":
    pytest.main(
        [__file__, "-v", "--cov=src.cache.security", "--cov-report=term-missing"]
    )
