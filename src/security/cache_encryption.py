"""
FACT System Cache Encryption

This module provides secure encryption for cached data to prevent
information leakage and unauthorized access to sensitive content.
"""

import os
import json
import time
import hashlib
import hmac
from typing import Any, Dict, Optional, Union
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
import base64
import structlog

from core.errors import CacheError, SecurityError

logger = structlog.get_logger(__name__)


class CacheEncryption:
    """
    Secure encryption for cache data with integrity protection.

    Provides encryption, decryption, and integrity validation for cached
    content to prevent data tampering and unauthorized access.
    """

    def __init__(self, encryption_key: Optional[bytes] = None):
        """
        Initialize cache encryption.

        Args:
            encryption_key: Optional encryption key (generated if not provided)
        """
        self.encryption_key = encryption_key or self._generate_encryption_key()
        self.cipher_suite = Fernet(self.encryption_key)

        # HMAC key for integrity verification (derived from encryption key)
        self.hmac_key = self._derive_hmac_key(self.encryption_key)

        # Metadata for cache entries
        self.version = "1.0"
        self.algorithm = "Fernet"

        logger.info(
            "Cache encryption initialized",
            algorithm=self.algorithm,
            version=self.version,
        )

    def encrypt_cache_entry(
        self, content: str, metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Encrypt cache content with metadata and integrity protection.

        Args:
            content: Content to encrypt
            metadata: Optional metadata to include

        Returns:
            Encrypted cache entry with metadata

        Raises:
            CacheError: If encryption fails
        """
        try:
            # Validate input
            if not isinstance(content, str):
                raise CacheError("Content must be a string")

            if len(content) > 10 * 1024 * 1024:  # 10MB limit
                raise CacheError("Content too large for encryption")

            # Prepare cache entry data
            cache_data = {
                "content": content,
                "metadata": metadata or {},
                "encrypted_at": time.time(),
                "version": self.version,
            }

            # Serialize data
            data_bytes = json.dumps(cache_data).encode("utf-8")

            # Encrypt data
            encrypted_data = self.cipher_suite.encrypt(data_bytes)

            # Create integrity hash
            integrity_hash = self._create_integrity_hash(encrypted_data)

            # Prepare final encrypted entry
            encrypted_entry = {
                "encrypted_content": base64.urlsafe_b64encode(encrypted_data).decode(
                    "utf-8"
                ),
                "integrity_hash": integrity_hash,
                "algorithm": self.algorithm,
                "version": self.version,
                "created_at": time.time(),
            }

            logger.debug(
                "Cache entry encrypted successfully",
                content_length=len(content),
                metadata_keys=list(metadata.keys()) if metadata else [],
            )

            return encrypted_entry

        except Exception as e:
            logger.error("Cache encryption failed", error=str(e))
            raise CacheError(f"Failed to encrypt cache entry: {str(e)}")

    def decrypt_cache_entry(self, encrypted_entry: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decrypt and validate cache entry.

        Args:
            encrypted_entry: Encrypted cache entry

        Returns:
            Decrypted cache data with content and metadata

        Raises:
            CacheError: If decryption or validation fails
        """
        try:
            # Validate encrypted entry structure
            required_fields = [
                "encrypted_content",
                "integrity_hash",
                "algorithm",
                "version",
            ]
            for field in required_fields:
                if field not in encrypted_entry:
                    raise CacheError(f"Missing required field: {field}")

            # Check version compatibility
            if encrypted_entry["version"] != self.version:
                raise CacheError(
                    f"Incompatible cache entry version: {encrypted_entry['version']}"
                )

            # Check algorithm
            if encrypted_entry["algorithm"] != self.algorithm:
                raise CacheError(
                    f"Unsupported encryption algorithm: {encrypted_entry['algorithm']}"
                )

            # Decode encrypted content
            try:
                encrypted_data = base64.urlsafe_b64decode(
                    encrypted_entry["encrypted_content"].encode("utf-8")
                )
            except Exception:
                raise CacheError("Invalid encrypted content encoding")

            # Verify integrity
            expected_hash = encrypted_entry["integrity_hash"]
            actual_hash = self._create_integrity_hash(encrypted_data)

            if not hmac.compare_digest(expected_hash, actual_hash):
                raise CacheError(
                    "Cache entry integrity check failed - possible tampering"
                )

            # Decrypt data
            try:
                decrypted_data = self.cipher_suite.decrypt(encrypted_data)
            except Exception:
                raise CacheError(
                    "Failed to decrypt cache entry - invalid key or corrupted data"
                )

            # Parse decrypted content
            try:
                cache_data = json.loads(decrypted_data.decode("utf-8"))
            except Exception:
                raise CacheError("Failed to parse decrypted cache data")

            # Validate decrypted data structure
            if not isinstance(cache_data, dict) or "content" not in cache_data:
                raise CacheError("Invalid decrypted cache data structure")

            logger.debug(
                "Cache entry decrypted successfully",
                content_length=len(cache_data.get("content", "")),
                has_metadata=bool(cache_data.get("metadata")),
            )

            return cache_data

        except CacheError:
            raise
        except Exception as e:
            logger.error("Cache decryption failed", error=str(e))
            raise CacheError(f"Failed to decrypt cache entry: {str(e)}")

    def encrypt_sensitive_fields(
        self, data: Dict[str, Any], sensitive_fields: set
    ) -> Dict[str, Any]:
        """
        Encrypt specific sensitive fields in a dictionary.

        Args:
            data: Dictionary containing data
            sensitive_fields: Set of field names to encrypt

        Returns:
            Dictionary with sensitive fields encrypted
        """
        if not isinstance(data, dict):
            raise CacheError("Data must be a dictionary")

        encrypted_data = data.copy()

        for field_name in sensitive_fields:
            if field_name in data:
                field_value = data[field_name]

                if isinstance(field_value, str):
                    # Encrypt string field
                    encrypted_field = self._encrypt_field(field_value)
                    encrypted_data[f"_encrypted_{field_name}"] = encrypted_field
                    del encrypted_data[field_name]

                elif isinstance(field_value, dict):
                    # Recursively encrypt nested dictionaries
                    encrypted_field = self._encrypt_field(json.dumps(field_value))
                    encrypted_data[f"_encrypted_{field_name}"] = encrypted_field
                    del encrypted_data[field_name]

        return encrypted_data

    def decrypt_sensitive_fields(
        self, data: Dict[str, Any], sensitive_fields: set
    ) -> Dict[str, Any]:
        """
        Decrypt sensitive fields in a dictionary.

        Args:
            data: Dictionary with encrypted fields
            sensitive_fields: Set of original field names

        Returns:
            Dictionary with sensitive fields decrypted
        """
        if not isinstance(data, dict):
            raise CacheError("Data must be a dictionary")

        decrypted_data = data.copy()

        for field_name in sensitive_fields:
            encrypted_field_name = f"_encrypted_{field_name}"

            if encrypted_field_name in data:
                encrypted_field = data[encrypted_field_name]

                try:
                    # Decrypt field
                    decrypted_value = self._decrypt_field(encrypted_field)

                    # Try to parse as JSON for complex types
                    try:
                        parsed_value = json.loads(decrypted_value)
                        decrypted_data[field_name] = parsed_value
                    except json.JSONDecodeError:
                        # Keep as string if not valid JSON
                        decrypted_data[field_name] = decrypted_value

                    # Remove encrypted field
                    del decrypted_data[encrypted_field_name]

                except Exception as e:
                    logger.warning(
                        "Failed to decrypt sensitive field",
                        field_name=field_name,
                        error=str(e),
                    )
                    # Keep encrypted field if decryption fails

        return decrypted_data

    def is_cache_entry_valid(self, encrypted_entry: Dict[str, Any]) -> bool:
        """
        Check if a cache entry is valid without decrypting it.

        Args:
            encrypted_entry: Encrypted cache entry to validate

        Returns:
            True if entry appears valid
        """
        try:
            # Check required fields
            required_fields = [
                "encrypted_content",
                "integrity_hash",
                "algorithm",
                "version",
            ]
            for field in required_fields:
                if field not in encrypted_entry:
                    return False

            # Check version and algorithm
            if (
                encrypted_entry["version"] != self.version
                or encrypted_entry["algorithm"] != self.algorithm
            ):
                return False

            # Validate base64 encoding
            try:
                base64.urlsafe_b64decode(encrypted_entry["encrypted_content"])
            except Exception:
                return False

            return True

        except Exception:
            return False

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

    def _derive_hmac_key(self, encryption_key: bytes) -> bytes:
        """Derive HMAC key from encryption key."""
        # Use PBKDF2 to derive a separate HMAC key
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"hmac_derivation_salt",
            iterations=10000,
            backend=default_backend(),
        )

        return kdf.derive(encryption_key)

    def _create_integrity_hash(self, data: bytes) -> str:
        """Create HMAC hash for integrity verification."""
        signature = hmac.new(self.hmac_key, data, hashlib.sha256).hexdigest()

        return signature

    def _encrypt_field(self, value: str) -> str:
        """Encrypt a single field value."""
        encrypted_data = self.cipher_suite.encrypt(value.encode("utf-8"))
        return base64.urlsafe_b64encode(encrypted_data).decode("utf-8")

    def _decrypt_field(self, encrypted_value: str) -> str:
        """Decrypt a single field value."""
        encrypted_data = base64.urlsafe_b64decode(encrypted_value.encode("utf-8"))
        decrypted_data = self.cipher_suite.decrypt(encrypted_data)
        return decrypted_data.decode("utf-8")


def create_cache_encryption(encryption_key: Optional[bytes] = None) -> CacheEncryption:
    """
    Create a configured cache encryption instance.

    Args:
        encryption_key: Optional encryption key

    Returns:
        CacheEncryption instance
    """
    return CacheEncryption(encryption_key)


# Global cache encryption instance
_cache_encryption_instance: Optional[CacheEncryption] = None


def get_cache_encryption() -> CacheEncryption:
    """Get global cache encryption instance."""
    global _cache_encryption_instance

    if _cache_encryption_instance is None:
        _cache_encryption_instance = create_cache_encryption()

    return _cache_encryption_instance


def encrypt_cache_data(
    content: str, metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Convenience function to encrypt cache data.

    Args:
        content: Content to encrypt
        metadata: Optional metadata

    Returns:
        Encrypted cache entry
    """
    cache_encryption = get_cache_encryption()
    return cache_encryption.encrypt_cache_entry(content, metadata)


def decrypt_cache_data(encrypted_entry: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function to decrypt cache data.

    Args:
        encrypted_entry: Encrypted cache entry

    Returns:
        Decrypted cache data
    """
    cache_encryption = get_cache_encryption()
    return cache_encryption.decrypt_cache_entry(encrypted_entry)
