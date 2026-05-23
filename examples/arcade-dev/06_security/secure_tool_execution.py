#!/usr/bin/env python3
"""
Secure Arcade.dev Tool Execution Example

This example demonstrates security best practices for Arcade.dev integration,
including secure credential management, input validation, permission management,
audit logging, and secure data handling.
"""

import os
import sys
import asyncio
import logging
import hashlib
import hmac
import secrets
import re
from pathlib import Path
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import json
import uuid

# Setup FACT imports using the import helper
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.import_helper import setup_fact_imports

# Setup FACT module path
setup_fact_imports()

# Import FACT modules with demo fallbacks
try:
    from src.security.auth import AuthorizationManager
    from src.security.input_sanitizer import InputSanitizer
    from src.security.token_manager import TokenManager
    from src.core.driver import FACTDriver
    from src.cache.manager import CacheManager

    FACT_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  FACT modules not fully available: {e}")
    print("🔄 Running in demo mode with mock implementations")
    FACT_AVAILABLE = False

    # Create mock classes for demo
    class MockAuthorizationManager:
        def __init__(self, *args, **kwargs):
            pass

    class MockInputSanitizer:
        def __init__(self, *args, **kwargs):
            pass

    class MockTokenManager:
        def __init__(self, *args, **kwargs):
            pass

    AuthorizationManager = MockAuthorizationManager
    InputSanitizer = MockInputSanitizer
    TokenManager = MockTokenManager


@dataclass
class SecurityConfig:
    """Security configuration for Arcade.dev integration."""

    enable_input_validation: bool = True
    enable_audit_logging: bool = True
    enable_rate_limiting: bool = True
    enable_data_encryption: bool = True

    # Rate limiting
    max_requests_per_minute: int = 60
    max_requests_per_hour: int = 1000

    # Input validation
    max_input_size: int = 1024 * 1024  # 1MB
    allowed_file_types: Set[str] = field(
        default_factory=lambda: {".py", ".js", ".ts", ".java", ".cpp"}
    )

    # Audit settings
    audit_log_file: str = "arcade_security_audit.log"
    log_sensitive_data: bool = False

    # Token settings
    token_expiry_minutes: int = 60
    refresh_token_expiry_days: int = 7


@dataclass
class UserPermissions:
    """User permission model."""

    user_id: str
    scopes: Set[str]
    max_daily_requests: int = 1000
    allowed_operations: Set[str] = field(default_factory=set)
    ip_whitelist: Set[str] = field(default_factory=set)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: Optional[datetime] = None


@dataclass
class AuditLogEntry:
    """Audit log entry for security tracking."""

    timestamp: datetime
    user_id: str
    operation: str
    status: str  # success, failure, blocked
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    metadata: Dict[str, Any] = field(default_factory=dict)
    risk_score: float = 0.0


class SecureCredentialManager:
    """Manages secure storage and retrieval of API credentials."""

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.CredentialManager")
        self._credentials: Dict[str, str] = {}
        self._demo_mode = not FACT_AVAILABLE

        if self._demo_mode:
            self.logger.info(
                "Running in demo mode - using simplified credential storage"
            )
            self._encryption_key = b"demo_key_for_testing_only_not_secure"
        else:
            self._encryption_key = self._get_or_create_encryption_key()

    def _get_or_create_encryption_key(self) -> bytes:
        """Get or create encryption key for credential storage."""
        # In demo mode, use a simple key
        if self._demo_mode:
            return b"demo_key_for_testing_only_not_secure"

        key_file = Path.home() / ".fact" / "encryption.key"

        if key_file.exists():
            with open(key_file, "rb") as f:
                return f.read()
        else:
            # Create new key
            key_file.parent.mkdir(exist_ok=True)
            key = secrets.token_bytes(32)
            with open(key_file, "wb") as f:
                f.write(key)
            key_file.chmod(0o600)  # Read only for owner
            return key

    def store_credential(self, service: str, credential: str) -> bool:
        """Securely store a credential."""
        try:
            # In production, use proper encryption
            credential_hash = hashlib.sha256(credential.encode()).hexdigest()
            self._credentials[service] = credential_hash
            self.logger.info(f"Credential stored for service: {service}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to store credential for {service}: {e}")
            return False

    def get_credential(self, service: str) -> Optional[str]:
        """Retrieve a credential securely."""
        if self._demo_mode:
            # In demo mode, return a mock credential if no env var is set
            env_key = f"{service.upper()}_API_KEY"
            credential = os.getenv(env_key)

            if not credential:
                # Return demo credential for testing
                credential = f"demo_key_for_{service}_testing_only"
                self.logger.info(f"Using demo credential for service: {service}")
            else:
                self.logger.info(f"Using environment credential for service: {service}")

            return credential
        else:
            # In production, implement proper decryption
            # For now, use environment variables
            env_key = f"{service.upper()}_API_KEY"
            credential = os.getenv(env_key)

            if not credential:
                self.logger.warning(f"No credential found for service: {service}")

            return credential


class SecurityValidator:
    """Validates and sanitizes inputs for security."""

    def __init__(self, config: SecurityConfig):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.SecurityValidator")

        # Dangerous patterns to detect
        self.dangerous_patterns = [
            r"eval\s*\(",
            r"exec\s*\(",
            r"import\s+os",
            r"import\s+subprocess",
            r"__import__",
            r"open\s*\(",
            r"file\s*\(",
            r"input\s*\(",
            r"raw_input\s*\(",
        ]

    def validate_code_input(
        self, code: str, language: str = "python"
    ) -> Dict[str, Any]:
        """Validate code input for security risks."""
        validation_result = {
            "is_safe": True,
            "warnings": [],
            "blocked_patterns": [],
            "sanitized_code": code,
        }

        if not self.config.enable_input_validation:
            return validation_result

        # Size check
        if len(code) > self.config.max_input_size:
            validation_result["is_safe"] = False
            validation_result["warnings"].append(
                f"Code exceeds maximum size limit: {self.config.max_input_size}"
            )

        # Pattern detection
        for pattern in self.dangerous_patterns:
            if re.search(pattern, code, re.IGNORECASE):
                validation_result["blocked_patterns"].append(pattern)
                validation_result["warnings"].append(
                    f"Potentially dangerous pattern detected: {pattern}"
                )

        # If dangerous patterns found, mark as unsafe
        if validation_result["blocked_patterns"]:
            validation_result["is_safe"] = False

        return validation_result


class AuditLogger:
    """Handles security audit logging."""

    def __init__(self, config: SecurityConfig):
        self.config = config
        self.audit_file = Path(config.audit_log_file)
        self.logger = logging.getLogger(f"{__name__}.AuditLogger")

        # Setup audit log file
        self._setup_audit_logging()

    def _setup_audit_logging(self):
        """Setup secure audit logging."""
        if self.config.enable_audit_logging:
            # Create audit log directory
            self.audit_file.parent.mkdir(exist_ok=True)

            # Setup file permissions (read/write for owner only)
            if self.audit_file.exists():
                self.audit_file.chmod(0o600)

    def log_event(self, entry: AuditLogEntry):
        """Log a security audit event."""
        if not self.config.enable_audit_logging:
            return

        try:
            log_data = {
                "timestamp": entry.timestamp.isoformat(),
                "request_id": entry.request_id,
                "user_id": (
                    entry.user_id
                    if not self.config.log_sensitive_data
                    else self._hash_user_id(entry.user_id)
                ),
                "operation": entry.operation,
                "status": entry.status,
                "ip_address": (
                    entry.ip_address
                    if not self.config.log_sensitive_data
                    else self._hash_ip(entry.ip_address)
                ),
                "risk_score": entry.risk_score,
                "metadata": entry.metadata,
            }

            with open(self.audit_file, "a") as f:
                f.write(json.dumps(log_data) + "\n")

            self.logger.debug(f"Audit event logged: {entry.operation} - {entry.status}")

        except Exception as e:
            self.logger.error(f"Failed to log audit event: {e}")

    def _hash_user_id(self, user_id: str) -> str:
        """Hash user ID for privacy."""
        return hashlib.sha256(user_id.encode()).hexdigest()[:16]

    def _hash_ip(self, ip_address: Optional[str]) -> Optional[str]:
        """Hash IP address for privacy."""
        if not ip_address:
            return None
        return hashlib.sha256(ip_address.encode()).hexdigest()[:16]


class SecureArcadeClient:
    """Secure Arcade.dev client with comprehensive security measures."""

    def __init__(self, config: SecurityConfig):
        self.config = config
        self.credential_manager = SecureCredentialManager()
        self.validator = SecurityValidator(config)
        self.audit_logger = AuditLogger(config)
        self.logger = logging.getLogger(__name__)

        # User permission storage (in production, use database)
        self.user_permissions: Dict[str, UserPermissions] = {}

        # Active sessions
        self.active_sessions: Dict[str, Dict[str, Any]] = {}

    def register_user(
        self, user_id: str, scopes: Set[str], allowed_operations: Set[str] = None
    ) -> bool:
        """Register a user with specific permissions."""
        try:
            if allowed_operations is None:
                allowed_operations = {
                    "code_analysis",
                    "test_generation",
                    "documentation",
                }

            permissions = UserPermissions(
                user_id=user_id, scopes=scopes, allowed_operations=allowed_operations
            )

            self.user_permissions[user_id] = permissions

            audit_entry = AuditLogEntry(
                timestamp=datetime.now(timezone.utc),
                user_id=user_id,
                operation="user_registration",
                status="success",
                metadata={
                    "scopes": list(scopes),
                    "operations": list(allowed_operations),
                },
            )
            self.audit_logger.log_event(audit_entry)

            self.logger.info(f"User registered: {user_id}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to register user {user_id}: {e}")
            return False

    def authenticate_user(
        self, user_id: str, api_key: str, ip_address: str = None
    ) -> Dict[str, Any]:
        """Authenticate user and create secure session."""
        auth_result = {
            "authenticated": False,
            "session_token": None,
            "permissions": None,
            "error": None,
        }

        try:
            # Check if user exists
            if user_id not in self.user_permissions:
                audit_entry = AuditLogEntry(
                    timestamp=datetime.now(timezone.utc),
                    user_id=user_id,
                    operation="authentication",
                    status="failure",
                    ip_address=ip_address,
                    metadata={"reason": "User not found"},
                    risk_score=7.0,
                )
                self.audit_logger.log_event(audit_entry)
                auth_result["error"] = "User not found"
                return auth_result

            # Create session token
            session_token = secrets.token_urlsafe(32)
            user_perms = self.user_permissions[user_id]
            session_data = {
                "user_id": user_id,
                "created_at": datetime.now(timezone.utc),
                "expires_at": datetime.now(timezone.utc)
                + timedelta(minutes=self.config.token_expiry_minutes),
                "ip_address": ip_address,
                "permissions": user_perms,
            }

            self.active_sessions[session_token] = session_data

            audit_entry = AuditLogEntry(
                timestamp=datetime.now(timezone.utc),
                user_id=user_id,
                operation="authentication",
                status="success",
                ip_address=ip_address,
            )
            self.audit_logger.log_event(audit_entry)

            auth_result.update(
                {
                    "authenticated": True,
                    "session_token": session_token,
                    "permissions": {
                        "scopes": list(user_perms.scopes),
                        "operations": list(user_perms.allowed_operations),
                        "expires_at": session_data["expires_at"].isoformat(),
                    },
                }
            )

            return auth_result

        except Exception as e:
            self.logger.error(f"Authentication error for {user_id}: {e}")
            auth_result["error"] = "Authentication failed"
            return auth_result

    async def secure_code_analysis(
        self, session_token: str, code: str, language: str = "python"
    ) -> Dict[str, Any]:
        """Perform secure code analysis with full security validation."""
        # Validate session
        if session_token not in self.active_sessions:
            return {"error": "Invalid session", "status": "unauthorized"}

        session = self.active_sessions[session_token]
        user_id = session["user_id"]

        # Input validation
        validation_result = self.validator.validate_code_input(code, language)
        if not validation_result["is_safe"]:
            return {
                "error": "Input validation failed",
                "warnings": validation_result["warnings"],
                "status": "invalid_input",
            }

        # Mock analysis result
        return {
            "status": "success",
            "analysis": {
                "score": 8.5,
                "suggestions": ["Use type hints", "Add error handling"],
                "security_check_passed": True,
            },
        }


async def demonstrate_security():
    """Demonstrate security features."""
    print("🔒 Secure Arcade.dev Integration Demo")
    print("=" * 50)

    # Configure security (ensure logs directory exists)
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    config = SecurityConfig(
        enable_input_validation=True,
        enable_audit_logging=True,
        audit_log_file="logs/arcade_security_audit.log",
    )

    # Create secure client
    client = SecureArcadeClient(config)

    # Register user
    client.register_user(
        user_id="demo_user",
        scopes={"read", "write"},
        allowed_operations={"code_analysis", "test_generation"},
    )

    # Authenticate
    auth_result = client.authenticate_user(
        user_id="demo_user", api_key="demo_key", ip_address="127.0.0.1"
    )

    if auth_result["authenticated"]:
        print("✅ User authenticated successfully")
        session_token = auth_result["session_token"]

        # Test safe code
        safe_code = "def hello_world():\n    print('Hello, World!')"
        result = await client.secure_code_analysis(session_token, safe_code)
        print(f"✅ Safe code analysis: {result['status']}")

        # Test dangerous code
        dangerous_code = "import os\nos.system('rm -rf /')"
        result = await client.secure_code_analysis(session_token, dangerous_code)
        print(f"🛡️ Dangerous code blocked: {result['status']}")

    print("\n🎉 Security demonstration completed!")


async def main():
    """Main demonstration function."""
    logging.basicConfig(level=logging.INFO)

    try:
        await demonstrate_security()
        return 0
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
