"""
FACT System Cache Security

Scans content before it enters the cache (sensitive data, injection payloads,
obfuscated encodings) and sanitizes content on its way out.

Blocking policy for ``validate_input``:
    * content longer than ``max_content_length``  -> ``ValidationError``
    * any CRITICAL threat                           -> ``SecurityError``
    * more than ``MAX_HIGH_THREATS`` HIGH threats   -> ``SecurityError``
    * otherwise the content is accepted (HIGH/MEDIUM threats are logged)

Injection patterns are deliberately shaped like attacks rather than like
ordinary SQL or prose: cached LLM answers routinely contain plain
``SELECT ... FROM`` statements and words such as "delete", so SQL keywords are
matched case-sensitively and only in injection-like combinations.
"""

import base64
import binascii
import re
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Pattern

import structlog

try:
    # Try relative imports first (when used as package)
    from ..core.errors import SecurityError, ValidationError
    from .config import SecurityConfig, load_security_config_from_env
except ImportError:
    # Fall back to absolute imports (when run as script)
    import sys
    from pathlib import Path

    src_path = str(Path(__file__).parent.parent)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    from core.errors import SecurityError, ValidationError  # type: ignore[no-redef]
    from cache.config import (  # type: ignore[no-redef]
        SecurityConfig,
        load_security_config_from_env,
    )


logger = structlog.get_logger(__name__)

MAX_HIGH_THREATS = 2
_SNIPPET_LENGTH = 50
_MAX_BASE64_CANDIDATES = 50
_MAX_BASE64_TOKEN_LENGTH = 8192


class ThreatLevel(Enum):
    """Severity of a detected threat, ordered LOW < MEDIUM < HIGH < CRITICAL."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        return _THREAT_RANK[self]


_THREAT_RANK = {
    ThreatLevel.LOW: 0,
    ThreatLevel.MEDIUM: 1,
    ThreatLevel.HIGH: 2,
    ThreatLevel.CRITICAL: 3,
}


@dataclass
class SecurityThreat:
    """A single threat found in scanned content."""

    threat_type: str
    threat_level: ThreatLevel
    description: str
    content_snippet: str
    mitigation: str
    detected_at: float = field(default_factory=time.time)


@dataclass
class SecurityScanResult:
    """Outcome of scanning one piece of content."""

    scanned_content_length: int
    threats_detected: int
    threat_breakdown: Dict[str, int]
    scan_time_ms: float
    threats: List[SecurityThreat]
    overall_risk_level: ThreatLevel
    recommendations: List[str]


# Injection signatures. SQL keywords are case-sensitive on purpose (see module doc).
_INJECTION_SIGNATURES: Dict[str, List[tuple]] = {
    "sql_injection": [
        (r";\s*(?:DROP|DELETE|TRUNCATE|ALTER|INSERT|UPDATE|EXEC)\b", 0),
        (r"\bUNION\s+(?:ALL\s+)?SELECT\b", re.IGNORECASE),
        (r"'\s*(?:OR|AND)\s+'?\w+'?\s*=\s*'?\w+", re.IGNORECASE),
        (r"\bDROP\s+(?:TABLE|DATABASE)\b[^;\n]*;\s*--", 0),
        (r"\b(?:xp_cmdshell|sp_executesql)\b", re.IGNORECASE),
        (r"'\s*;\s*--", 0),
    ],
    "xss_injection": [
        (r"<\s*script\b", re.IGNORECASE),
        (r"\bjavascript\s*:", re.IGNORECASE),
        (r"<\s*iframe\b", re.IGNORECASE),
        (r"<[^>]+\son(?:error|load|click|mouseover|focus)\s*=", re.IGNORECASE),
        (r"<\s*(?:object|embed)\b", re.IGNORECASE),
    ],
    "command_injection": [
        (
            r"(?:;|&&|\|\|)\s*(?:rm|wget|curl|nc|bash|sh|chmod|chown|mkfs|dd|shutdown|reboot)\b",
            0,
        ),
        (r"\|\s*(?:ba)?sh\b", 0),
        (r"\brm\s+-[rf]{1,2}\s+/", 0),
    ],
    "path_traversal": [
        (r"(?:\.\./|\.\.\\){2,}", 0),
        (r"(?:%2e%2e(?:%2f|/)){2,}", re.IGNORECASE),
        (r"/etc/(?:passwd|shadow)\b", 0),
    ],
}

_CRITICAL_MARKERS = {
    "sql_injection": (
        "drop table",
        "drop database",
        "delete from",
        "truncate",
        "union",
        "xp_cmdshell",
        "; drop",
        ";drop",
        "--",
    ),
    "xss_injection": ("<script", "javascript:", "onerror", "onload", "document.cookie"),
    "command_injection": ("rm -", "rm ", "mkfs", "dd ", "wget", "curl", "sh"),
    "path_traversal": ("/etc/passwd", "/etc/shadow"),
}

_MITIGATIONS = {
    "sensitive_data": "Remove credentials and personal data before caching",
    "sql_injection": "Reject the content and use parameterized queries upstream",
    "xss_injection": "Strip or escape HTML/JavaScript before caching or rendering",
    "command_injection": "Reject the content; never pass cached text to a shell",
    "path_traversal": "Normalize and confine file paths before use",
    "suspicious_encoding": "Decode and re-scan encoded content",
    "unicode_bypass": "Normalize Unicode escapes and re-scan the content",
    "base64_payload": "Decode embedded base64 and reject executable payloads",
}

_BASE64_TOKEN = re.compile(r"[A-Za-z0-9+/]{20,}={0,2}")
_URL_ESCAPE = re.compile(r"%[0-9A-Fa-f]{2}")
_UNICODE_ESCAPE = re.compile(r"\\u[0-9A-Fa-f]{4}|\\x[0-9A-Fa-f]{2}")
_BASE64_DANGER = (
    "<script",
    "script>",
    "javascript:",
    "alert(",
    "eval(",
    "exec(",
    "<iframe",
    "/bin/sh",
    "rm -rf",
    "drop table",
)


def _snippet(text: str) -> str:
    text = text.replace("\n", " ")
    return text if len(text) <= _SNIPPET_LENGTH else text[:_SNIPPET_LENGTH] + "..."


def _mask(text: str) -> str:
    """Mask a sensitive match so it is never logged verbatim."""
    if len(text) <= 4:
        return "*" * len(text)
    return text[:2] + "*" * (min(len(text), _SNIPPET_LENGTH) - 4) + text[-2:]


class CacheSecurityValidator:
    """Validates content entering the cache and sanitizes content leaving it."""

    def __init__(self, config: Optional[SecurityConfig] = None):
        self.config = config if config is not None else load_security_config_from_env()
        self._compiled_patterns: Dict[str, Pattern] = {}
        for pattern in self.config.sensitive_data_patterns:
            try:
                self._compiled_patterns[pattern] = re.compile(pattern, re.IGNORECASE)
            except re.error as e:
                logger.warning(
                    "Skipping invalid sensitive data pattern",
                    pattern=pattern,
                    error=str(e),
                )
        self._injection_patterns: Dict[str, List[Pattern]] = {
            category: [re.compile(p, flags) for p, flags in signatures]
            for category, signatures in _INJECTION_SIGNATURES.items()
        }

    # ------------------------------------------------------------------ input

    def validate_input(
        self, content: str, source: str = "unknown"
    ) -> Optional[SecurityScanResult]:
        """
        Validate content before it is cached.

        Raises:
            ValidationError: content is not a string or exceeds the size limit
            SecurityError: content carries a critical threat or too many high threats
        """
        if not self.config.enable_input_validation:
            return None
        if not isinstance(content, str):
            raise ValidationError(
                f"Cache content must be a string, got {type(content).__name__}",
                error_code="CACHE_INVALID_CONTENT_TYPE",
                context={"source": source},
            )
        if len(content) > self.config.max_content_length:
            raise ValidationError(
                f"Content length {len(content)} exceeds maximum "
                f"{self.config.max_content_length}",
                error_code="CACHE_CONTENT_LENGTH",
                context={"source": source, "length": len(content)},
            )

        result = self.scan_content(content)
        critical = [t for t in result.threats if t.threat_level == ThreatLevel.CRITICAL]
        high = [t for t in result.threats if t.threat_level == ThreatLevel.HIGH]

        if critical or len(high) > MAX_HIGH_THREATS:
            blocking = critical or high
            types = sorted({t.threat_type for t in blocking})
            logger.warning(
                "Cache content blocked by security validation",
                source=source,
                threat_types=types,
                critical=len(critical),
                high=len(high),
            )
            raise SecurityError(
                f"Content from {source} failed security validation: {', '.join(types)}",
                error_code="SECURITY_THREAT_DETECTED",
                context={
                    "source": source,
                    "threat_types": types,
                    "risk_level": result.overall_risk_level.value,
                },
            )
        if result.threats:
            logger.info(
                "Cache content accepted with low-severity findings",
                source=source,
                threat_breakdown=result.threat_breakdown,
            )
        return result

    # ----------------------------------------------------------------- output

    def sanitize_output(self, content: str) -> str:
        """Strip active content and neutralize destructive SQL in cached output."""
        if not self.config.enable_output_sanitization or not content:
            return content
        try:
            text = re.sub(
                r"<\s*script\b[^>]*>.*?<\s*/\s*script\s*>",
                "",
                content,
                flags=re.IGNORECASE | re.DOTALL,
            )
            text = re.sub(r"<\s*/?\s*script\b[^>]*>", "", text, flags=re.IGNORECASE)
            text = re.sub(
                r"<\s*iframe\b[^>]*>.*?<\s*/\s*iframe\s*>",
                "",
                text,
                flags=re.IGNORECASE | re.DOTALL,
            )
            text = re.sub(
                r"<\s*/?\s*(?:iframe|object|embed)\b[^>]*>",
                "",
                text,
                flags=re.IGNORECASE,
            )
            text = re.sub(
                r"\son\w+\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+)",
                "",
                text,
                flags=re.IGNORECASE,
            )
            text = re.sub(r"javascript\s*:", "", text, flags=re.IGNORECASE)
            text = re.sub(
                r"\b(DROP|TRUNCATE|ALTER)(?=\s+(?:TABLE|DATABASE|INDEX|VIEW)\b)"
                r"|\b(DELETE)(?=\s+FROM\b)|\b(UNION)(?=\s+(?:ALL\s+)?SELECT\b)",
                lambda m: f"[{m.group(0)}]",
                text,
            )
            return text
        except Exception as e:
            logger.error(
                "Output sanitization failed; returning content unchanged", error=str(e)
            )
            return content

    # ------------------------------------------------------------------- scan

    def scan_content(self, content: str) -> SecurityScanResult:
        """Scan content and report every threat found (never raises)."""
        start = time.perf_counter()
        threats: List[SecurityThreat] = []
        scan_error: Optional[str] = None
        try:
            threats.extend(self._scan_sensitive_data(content))
            threats.extend(self._scan_injections(content))
            threats.extend(self._scan_encodings(content))
        except Exception as e:
            scan_error = str(e)
            logger.error("Security scan failed", error=scan_error)

        breakdown: Dict[str, int] = {}
        for threat in threats:
            breakdown[threat.threat_type] = breakdown.get(threat.threat_type, 0) + 1
        overall = self._determine_overall_risk(threats)
        if scan_error is not None:
            breakdown["scan_error"] = 1
            # An incomplete scan cannot vouch for the content.
            if overall.rank < ThreatLevel.MEDIUM.rank:
                overall = ThreatLevel.MEDIUM

        scan_time_ms = max((time.perf_counter() - start) * 1000, 1e-6)
        return SecurityScanResult(
            scanned_content_length=len(content),
            threats_detected=len(threats),
            threat_breakdown=breakdown,
            scan_time_ms=scan_time_ms,
            threats=threats,
            overall_risk_level=overall,
            recommendations=self._generate_security_recommendations(breakdown),
        )

    def _scan_sensitive_data(self, content: str) -> List[SecurityThreat]:
        threats = []
        for pattern_text, pattern in self._compiled_patterns.items():
            match = pattern.search(content)
            if match:
                threats.append(
                    self._threat(
                        "sensitive_data",
                        ThreatLevel.CRITICAL,
                        "Sensitive data pattern matched",
                        _mask(match.group(0)),
                    )
                )
        return threats

    def _scan_injections(self, content: str) -> List[SecurityThreat]:
        threats = []
        for category, patterns in self._injection_patterns.items():
            matches = [m.group(0) for p in patterns for m in [p.search(content)] if m]
            if matches:
                level = self._determine_injection_threat_level(category, matches)
                threats.append(
                    self._threat(
                        category,
                        level,
                        f"{category.replace('_', ' ').capitalize()} pattern detected",
                        _snippet(matches[0]),
                    )
                )
        return threats

    def _scan_encodings(self, content: str) -> List[SecurityThreat]:
        threats = []
        url_escapes = _URL_ESCAPE.findall(content)
        if len(url_escapes) >= 10:
            threats.append(
                self._threat(
                    "suspicious_encoding",
                    ThreatLevel.MEDIUM,
                    f"Excessive URL encoding ({len(url_escapes)} escapes)",
                    _snippet("".join(url_escapes)),
                )
            )
        unicode_escapes = _UNICODE_ESCAPE.findall(content)
        if len(unicode_escapes) >= 5:
            threats.append(
                self._threat(
                    "unicode_bypass",
                    ThreatLevel.MEDIUM,
                    f"Excessive escaped Unicode sequences ({len(unicode_escapes)})",
                    _snippet("".join(unicode_escapes)),
                )
            )
        payload = self._find_base64_payload(content)
        if payload is not None:
            threats.append(
                self._threat(
                    "base64_payload",
                    ThreatLevel.HIGH,
                    "Base64 content decodes to an executable payload",
                    _snippet(payload),
                )
            )
        return threats

    @staticmethod
    def _find_base64_payload(content: str) -> Optional[str]:
        for index, match in enumerate(_BASE64_TOKEN.finditer(content)):
            if index >= _MAX_BASE64_CANDIDATES:
                break
            token = match.group(0)
            if len(token) > _MAX_BASE64_TOKEN_LENGTH:
                continue
            try:
                padded = token + "=" * (-len(token) % 4)
                decoded = base64.b64decode(padded, validate=True).decode(
                    "utf-8", "ignore"
                )
            except (binascii.Error, ValueError):
                continue
            lowered = decoded.lower()
            if any(marker in lowered for marker in _BASE64_DANGER):
                return token
        return None

    @staticmethod
    def _threat(
        threat_type: str, level: ThreatLevel, description: str, snippet: str
    ) -> SecurityThreat:
        return SecurityThreat(
            threat_type=threat_type,
            threat_level=level,
            description=description,
            content_snippet=snippet,
            mitigation=_MITIGATIONS.get(threat_type, "Review the content manually"),
            detected_at=time.time(),
        )

    # ------------------------------------------------------------- severities

    def _determine_injection_threat_level(
        self, injection_type: str, matches: List[str]
    ) -> ThreatLevel:
        """Classify an injection finding from the text that matched."""
        markers = _CRITICAL_MARKERS.get(injection_type)
        if markers is None:
            return ThreatLevel.MEDIUM
        joined = " ".join(matches).lower()
        if any(marker in joined for marker in markers):
            return ThreatLevel.CRITICAL
        return ThreatLevel.HIGH

    def _determine_overall_risk(self, threats: List[SecurityThreat]) -> ThreatLevel:
        if not threats:
            return ThreatLevel.LOW
        return max((t.threat_level for t in threats), key=lambda level: level.rank)

    def _generate_security_recommendations(
        self, threat_breakdown: Dict[str, int]
    ) -> List[str]:
        if not threat_breakdown:
            return ["No threats detected - continue current security practices"]
        recommendations = []
        if threat_breakdown.get("sensitive_data"):
            recommendations.append(
                "CRITICAL: Remove sensitive data (credentials, personal data) before caching"
            )
        if threat_breakdown.get("sql_injection"):
            recommendations.append(
                "Block SQL injection payloads and use parameterized queries upstream"
            )
        if threat_breakdown.get("xss_injection"):
            recommendations.append(
                "Strip or escape HTML/JavaScript to prevent XSS from cached output"
            )
        if threat_breakdown.get("command_injection"):
            recommendations.append(
                "CRITICAL: Command injection detected - reject content and audit its source"
            )
        if threat_breakdown.get("path_traversal"):
            recommendations.append(
                "Normalize and confine file paths referenced in content"
            )
        if any(
            threat_breakdown.get(k)
            for k in ("suspicious_encoding", "unicode_bypass", "base64_payload")
        ):
            recommendations.append(
                "Decode obfuscated content and re-scan before caching"
            )
        if threat_breakdown.get("scan_error"):
            recommendations.append(
                "Investigate security scanner errors; scan was incomplete"
            )
        if not recommendations:
            recommendations.append("Review flagged content manually")
        return recommendations

    # ---------------------------------------------------------------- reports

    def generate_security_report(
        self, scan_results: List[SecurityScanResult]
    ) -> Dict[str, Any]:
        """Aggregate several scan results into a security posture report."""
        if not scan_results:
            return {"error": "No scan results provided"}

        breakdown: Dict[str, int] = {}
        risk_distribution = {level.value: 0 for level in ThreatLevel}
        for result in scan_results:
            risk_distribution[result.overall_risk_level.value] += 1
            for threat_type, count in result.threat_breakdown.items():
                breakdown[threat_type] = breakdown.get(threat_type, 0) + count

        if risk_distribution["critical"]:
            posture = "CRITICAL"
        elif risk_distribution["high"]:
            posture = "HIGH_RISK"
        elif risk_distribution["medium"]:
            posture = "MEDIUM_RISK"
        else:
            posture = "LOW_RISK"

        recommendations = self._generate_security_recommendations(breakdown)
        for result in scan_results:
            for rec in result.recommendations:
                if rec not in recommendations:
                    recommendations.append(rec)

        return {
            "generated_at": time.time(),
            "total_scans": len(scan_results),
            "total_content_scanned_bytes": sum(
                r.scanned_content_length for r in scan_results
            ),
            "total_threats_detected": sum(r.threats_detected for r in scan_results),
            "threat_breakdown": breakdown,
            "risk_distribution": risk_distribution,
            "average_scan_time_ms": sum(r.scan_time_ms for r in scan_results)
            / len(scan_results),
            "security_posture": posture,
            "recommendations": recommendations,
        }


# Global validator instance
_security_validator: Optional[CacheSecurityValidator] = None
_security_validator_lock = threading.Lock()


def get_security_validator() -> CacheSecurityValidator:
    """Return the process-wide security validator (configured from the environment)."""
    global _security_validator
    if _security_validator is None:
        with _security_validator_lock:
            if _security_validator is None:
                _security_validator = CacheSecurityValidator()
    return _security_validator


def validate_cache_content_security(
    content: str, context: str = "cache"
) -> Optional[SecurityScanResult]:
    """Validate content before caching; raises SecurityError/ValidationError on rejection."""
    return get_security_validator().validate_input(content, context)


def sanitize_cache_output(content: str) -> str:
    """Sanitize cached content before it is returned to a caller."""
    return get_security_validator().sanitize_output(content)
