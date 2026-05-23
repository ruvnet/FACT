"""
FACT System Secure Token Management

This module provides secure token generation, encryption, and storage
for authentication and authorization management.
"""

import os
import time
import hmac
import hashlib
import secrets
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
import base64
import json
import structlog

from core.errors import SecurityError, AuthenticationError

logger = structlog.get_logger(__name__)


@dataclass
class SecureToken:
    """Represents a securely encrypted token with metadata."""

    token_id: str
    user_id: str
    tool_name: str
    scopes: List[str]
    created_at: float
    expires_at: float
    token_hash: str
    encrypted_data: str
    is_revoked: bool = False
    last_used: Optional[float] = None
    use_count: int = 0

    def is_expired(self) -> bool:
        """Check if token is expired."""
        return time.time() > self.expires_at

    def is_valid(self) -> bool:
        """Check if token is valid and usable."""
        return not self.is_revoked and not self.is_expired()

    def record_use(self) -> None:
        """Record token usage."""
        self.last_used = time.time()
        self.use_count += 1


class SecureTokenManager:
    """
    Secure token manager with encryption, proper storage, and validation.

    Provides cryptographically secure token generation, storage, and management
    with protection against token manipulation and replay attacks.
    """

    def __init__(self, encryption_key: Optional[bytes] = None):
        """
        Initialize secure token manager.

        Args:
            encryption_key: Optional encryption key (generates if not provided)
        """
        self.encryption_key = encryption_key or self._generate_encryption_key()
        self.cipher_suite = Fernet(self.encryption_key)

        # Secure token storage (in production, use encrypted database)
        self.tokens: Dict[str, SecureToken] = {}

        # Token validation settings
        self.max_token_lifetime = 3600  # 1 hour
        self.max_refresh_lifetime = 86400  # 24 hours
        self.token_entropy_bytes = 32  # 256 bits

        logger.info("SecureTokenManager initialized with encryption")

    def generate_access_token(
        self,
        user_id: str,
        tool_name: str,
        scopes: List[str],
        lifetime_seconds: int = None,
    ) -> str:
        """
        Generate a cryptographically secure access token.

        Args:
            user_id: User identifier
            tool_name: Tool name for authorization
            scopes: List of authorized scopes
            lifetime_seconds: Token lifetime (default: 1 hour)

        Returns:
            Secure access token string

        Raises:
            SecurityError: If token generation fails
        """
        try:
            # Validate inputs
            self._validate_token_inputs(user_id, tool_name, scopes)

            # Set token lifetime
            if lifetime_seconds is None:
                lifetime_seconds = self.max_token_lifetime
            elif lifetime_seconds > self.max_token_lifetime:
                raise SecurityError(
                    f"Token lifetime cannot exceed {self.max_token_lifetime} seconds"
                )

            # Generate secure token components
            token_id = self._generate_token_id()
            raw_token = self._generate_raw_token()

            # Create token data
            current_time = time.time()
            token_data = {
                "token_id": token_id,
                "user_id": user_id,
                "tool_name": tool_name,
                "scopes": scopes,
                "created_at": current_time,
                "expires_at": current_time + lifetime_seconds,
                "raw_token": raw_token,
            }

            # Encrypt token data
            encrypted_data = self._encrypt_token_data(token_data)

            # Create token hash for validation
            token_hash = self._create_token_hash(raw_token, user_id)

            # Store secure token
            secure_token = SecureToken(
                token_id=token_id,
                user_id=user_id,
                tool_name=tool_name,
                scopes=scopes,
                created_at=current_time,
                expires_at=current_time + lifetime_seconds,
                token_hash=token_hash,
                encrypted_data=encrypted_data,
            )

            self.tokens[token_id] = secure_token

            # Create final token (format: tokenId.encryptedData.hash)
            final_token = f"{token_id}.{encrypted_data}.{token_hash}"

            logger.info(
                "Access token generated",
                token_id=token_id,
                user_id=user_id,
                tool_name=tool_name,
                scopes=scopes,
                expires_at=secure_token.expires_at,
            )

            return final_token

        except Exception as e:
            logger.error(
                "Token generation failed",
                user_id=user_id,
                tool_name=tool_name,
                error=str(e),
            )
            raise SecurityError(f"Failed to generate access token: {str(e)}")

    def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validate and decrypt an access token.

        Args:
            token: Access token to validate

        Returns:
            Token data if valid

        Raises:
            AuthenticationError: If token is invalid
        """
        try:
            # Parse token components
            token_parts = token.split(".")
            if len(token_parts) != 3:
                raise AuthenticationError("Invalid token format")

            token_id, encrypted_data, provided_hash = token_parts

            # Check if token exists
            if token_id not in self.tokens:
                raise AuthenticationError("Token not found")

            secure_token = self.tokens[token_id]

            # Check token validity
            if not secure_token.is_valid():
                if secure_token.is_revoked:
                    raise AuthenticationError("Token has been revoked")
                else:
                    raise AuthenticationError("Token has expired")

            # Validate token hash
            if not self._verify_token_hash(provided_hash, secure_token.token_hash):
                raise AuthenticationError("Token integrity check failed")

            # Decrypt token data
            token_data = self._decrypt_token_data(encrypted_data)

            # Additional validation
            if token_data["token_id"] != token_id:
                raise AuthenticationError("Token ID mismatch")

            if token_data["expires_at"] < time.time():
                raise AuthenticationError("Token expired")

            # Record token usage
            secure_token.record_use()

            logger.debug(
                "Token validated successfully",
                token_id=token_id,
                user_id=token_data["user_id"],
                use_count=secure_token.use_count,
            )

            return {
                "user_id": token_data["user_id"],
                "tool_name": token_data["tool_name"],
                "scopes": token_data["scopes"],
                "created_at": token_data["created_at"],
                "expires_at": token_data["expires_at"],
            }

        except AuthenticationError:
            raise
        except Exception as e:
            logger.error("Token validation failed", error=str(e))
            raise AuthenticationError(f"Token validation failed: {str(e)}")

    def revoke_token(self, token_id: str) -> bool:
        """
        Revoke a specific token.

        Args:
            token_id: Token ID to revoke

        Returns:
            True if token was revoked
        """
        if token_id in self.tokens:
            self.tokens[token_id].is_revoked = True
            logger.info("Token revoked", token_id=token_id)
            return True
        return False

    def revoke_user_tokens(self, user_id: str, tool_name: Optional[str] = None) -> int:
        """
        Revoke all tokens for a user or user-tool combination.

        Args:
            user_id: User identifier
            tool_name: Optional tool name filter

        Returns:
            Number of tokens revoked
        """
        revoked_count = 0

        for token in self.tokens.values():
            if (
                token.user_id == user_id
                and (tool_name is None or token.tool_name == tool_name)
                and not token.is_revoked
            ):
                token.is_revoked = True
                revoked_count += 1

        logger.info(
            "User tokens revoked",
            user_id=user_id,
            tool_name=tool_name,
            count=revoked_count,
        )

        return revoked_count

    def cleanup_expired_tokens(self) -> int:
        """
        Remove expired tokens from storage.

        Returns:
            Number of tokens cleaned up
        """
        current_time = time.time()
        expired_tokens = [
            token_id
            for token_id, token in self.tokens.items()
            if token.expires_at < current_time
        ]

        for token_id in expired_tokens:
            del self.tokens[token_id]

        if expired_tokens:
            logger.info("Expired tokens cleaned up", count=len(expired_tokens))

        return len(expired_tokens)

    def get_token_stats(self) -> Dict[str, Any]:
        """Get token statistics for monitoring."""
        current_time = time.time()

        active_tokens = sum(1 for token in self.tokens.values() if token.is_valid())
        expired_tokens = sum(1 for token in self.tokens.values() if token.is_expired())
        revoked_tokens = sum(1 for token in self.tokens.values() if token.is_revoked)

        return {
            "total_tokens": len(self.tokens),
            "active_tokens": active_tokens,
            "expired_tokens": expired_tokens,
            "revoked_tokens": revoked_tokens,
            "cleanup_needed": expired_tokens > 0,
        }

    def _generate_encryption_key(self) -> bytes:
        """Generate a secure encryption key."""
        # In production, this should be loaded from secure key management
        password = os.urandom(32)
        salt = os.urandom(16)

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend(),
        )

        key = base64.urlsafe_b64encode(kdf.derive(password))
        return key

    def _generate_token_id(self) -> str:
        """Generate a unique token identifier."""
        return secrets.token_urlsafe(16)

    def _generate_raw_token(self) -> str:
        """Generate a cryptographically secure raw token."""
        return secrets.token_urlsafe(self.token_entropy_bytes)

    def _create_token_hash(self, raw_token: str, user_id: str) -> str:
        """Create a secure hash of the token for validation."""
        # Use HMAC for secure hashing
        message = f"{raw_token}:{user_id}".encode("utf-8")
        signature = hmac.new(self.encryption_key, message, hashlib.sha256).hexdigest()
        return signature

    def _verify_token_hash(self, provided_hash: str, stored_hash: str) -> bool:
        """Verify token hash using constant-time comparison."""
        return hmac.compare_digest(provided_hash, stored_hash)

    def _encrypt_token_data(self, token_data: Dict[str, Any]) -> str:
        """Encrypt token data using Fernet encryption."""
        data_bytes = json.dumps(token_data).encode("utf-8")
        encrypted_data = self.cipher_suite.encrypt(data_bytes)
        return base64.urlsafe_b64encode(encrypted_data).decode("utf-8")

    def _decrypt_token_data(self, encrypted_data: str) -> Dict[str, Any]:
        """Decrypt token data using Fernet encryption."""
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode("utf-8"))
        decrypted_data = self.cipher_suite.decrypt(encrypted_bytes)
        return json.loads(decrypted_data.decode("utf-8"))

    def _validate_token_inputs(
        self, user_id: str, tool_name: str, scopes: List[str]
    ) -> None:
        """Validate token generation inputs."""
        if not user_id or not isinstance(user_id, str):
            raise SecurityError("Invalid user_id")

        if not tool_name or not isinstance(tool_name, str):
            raise SecurityError("Invalid tool_name")

        if not scopes or not isinstance(scopes, list):
            raise SecurityError("Invalid scopes")

        if len(user_id) > 100:
            raise SecurityError("user_id too long")

        if len(tool_name) > 100:
            raise SecurityError("tool_name too long")

        if len(scopes) > 20:
            raise SecurityError("Too many scopes")


def create_secure_token_manager(
    encryption_key: Optional[bytes] = None,
) -> SecureTokenManager:
    """
    Create a configured secure token manager.

    Args:
        encryption_key: Optional encryption key

    Returns:
        SecureTokenManager instance
    """
    return SecureTokenManager(encryption_key)
