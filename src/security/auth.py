"""
FACT System Authentication and Authorization

This module provides authentication and authorization management
for tool access control and user permission validation.
"""

import time
import asyncio
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass
import structlog

try:
    # Try relative imports first (when used as package)
    from ..core.errors import AuthenticationError, UnauthorizedError, ValidationError
except ImportError:
    # Fall back to absolute imports (when run as script)
    import sys
    from pathlib import Path

    # Add src to path if not already there
    src_path = str(Path(__file__).parent.parent)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    from core.errors import AuthenticationError, UnauthorizedError, ValidationError


logger = structlog.get_logger(__name__)


@dataclass
class Authorization:
    """Represents an authorization grant for a user and tool."""

    user_id: str
    tool_name: str
    scopes: List[str]
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_at: Optional[float] = None
    created_at: float = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()

    def is_expired(self) -> bool:
        """Check if authorization is expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    def has_scope(self, scope: str) -> bool:
        """Check if authorization includes a specific scope."""
        return scope in self.scopes

    def has_all_scopes(self, required_scopes: List[str]) -> bool:
        """Check if authorization includes all required scopes."""
        return all(scope in self.scopes for scope in required_scopes)


@dataclass
class AuthFlow:
    """Represents an ongoing OAuth authorization flow."""

    flow_id: str
    user_id: str
    tool_name: str
    scopes: List[str]
    auth_url: str
    status: str = "pending"
    created_at: float = None
    expires_at: float = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()
        if self.expires_at is None:
            self.expires_at = self.created_at + 600  # 10 minutes

    def is_expired(self) -> bool:
        """Check if authorization flow is expired."""
        return time.time() > self.expires_at


class AuthorizationManager:
    """
    Manages user authorization for tool access.

    Provides OAuth integration, scope validation, and session management
    for secure tool execution.
    """

    def __init__(
        self,
        oauth_client_id: Optional[str] = None,
        oauth_client_secret: Optional[str] = None,
        oauth_redirect_uri: Optional[str] = None,
    ):
        """
        Initialize authorization manager.

        Args:
            oauth_client_id: OAuth client ID
            oauth_client_secret: OAuth client secret
            oauth_redirect_uri: OAuth redirect URI
        """
        self.oauth_client_id = oauth_client_id
        self.oauth_client_secret = oauth_client_secret
        self.oauth_redirect_uri = oauth_redirect_uri

        # In-memory storage for demo (use persistent storage in production)
        self.active_authorizations: Dict[str, Authorization] = {}
        self.pending_flows: Dict[str, AuthFlow] = {}

        # Scope definitions
        self.available_scopes = {
            "read": "Read access to data and tools",
            "write": "Write access to modify data",
            "admin": "Administrative access to system functions",
            "sql": "Execute SQL queries",
            "file": "Access file system operations",
            "web": "Make external web requests",
        }

        logger.info(
            "AuthorizationManager initialized", oauth_enabled=bool(oauth_client_id)
        )

    async def validate_authorization(
        self, user_id: str, tool_name: str, required_scopes: Optional[List[str]] = None
    ) -> Authorization:
        """
        Validate user authorization for tool access.

        Args:
            user_id: User identifier
            tool_name: Tool name requiring authorization
            required_scopes: Optional list of required scopes

        Returns:
            Valid Authorization object

        Raises:
            UnauthorizedError: If authorization is invalid or insufficient
        """
        try:
            auth_key = f"{user_id}:{tool_name}"

            # Check if authorization exists
            if auth_key not in self.active_authorizations:
                logger.warning(
                    "No authorization found", user_id=user_id, tool_name=tool_name
                )
                raise UnauthorizedError(
                    f"No authorization found for user {user_id} and tool {tool_name}"
                )

            authorization = self.active_authorizations[auth_key]

            # Check if authorization is expired
            if authorization.is_expired():
                logger.warning(
                    "Authorization expired",
                    user_id=user_id,
                    tool_name=tool_name,
                    expires_at=authorization.expires_at,
                )

                # Try to refresh token if available
                if authorization.refresh_token:
                    try:
                        refreshed_auth = await self._refresh_authorization(
                            authorization
                        )
                        self.active_authorizations[auth_key] = refreshed_auth
                        authorization = refreshed_auth
                    except Exception as e:
                        logger.error(
                            "Failed to refresh authorization",
                            user_id=user_id,
                            tool_name=tool_name,
                            error=str(e),
                        )
                        del self.active_authorizations[auth_key]
                        raise UnauthorizedError(
                            "Authorization expired and refresh failed"
                        )
                else:
                    del self.active_authorizations[auth_key]
                    raise UnauthorizedError("Authorization expired")

            # Check required scopes
            if required_scopes:
                if not authorization.has_all_scopes(required_scopes):
                    missing_scopes = [
                        scope
                        for scope in required_scopes
                        if not authorization.has_scope(scope)
                    ]
                    logger.warning(
                        "Insufficient scopes",
                        user_id=user_id,
                        tool_name=tool_name,
                        required_scopes=required_scopes,
                        user_scopes=authorization.scopes,
                        missing_scopes=missing_scopes,
                    )
                    raise UnauthorizedError(
                        f"Insufficient permissions. Missing scopes: {missing_scopes}"
                    )

            logger.debug(
                "Authorization validated successfully",
                user_id=user_id,
                tool_name=tool_name,
                scopes=authorization.scopes,
            )

            return authorization

        except UnauthorizedError:
            raise
        except Exception as e:
            logger.error(
                "Authorization validation failed",
                user_id=user_id,
                tool_name=tool_name,
                error=str(e),
            )
            raise UnauthorizedError(f"Authorization validation failed: {str(e)}")

    def initiate_authorization(
        self, user_id: str, tool_name: str, scopes: List[str]
    ) -> AuthFlow:
        """
        Initiate OAuth authorization flow.

        Args:
            user_id: User identifier
            tool_name: Tool name requiring authorization
            scopes: List of requested scopes

        Returns:
            AuthFlow instance with authorization URL

        Raises:
            ValidationError: If parameters are invalid
        """
        try:
            # Validate inputs
            if not user_id or not tool_name:
                raise ValidationError("User ID and tool name are required")

            if not scopes:
                raise ValidationError("At least one scope is required")

            # Validate scopes
            invalid_scopes = [
                scope for scope in scopes if scope not in self.available_scopes
            ]
            if invalid_scopes:
                raise ValidationError(f"Invalid scopes: {invalid_scopes}")

            # Generate flow ID
            import uuid

            flow_id = str(uuid.uuid4())

            # Create authorization URL
            auth_url = self._create_auth_url(flow_id, scopes)

            # Create auth flow
            auth_flow = AuthFlow(
                flow_id=flow_id,
                user_id=user_id,
                tool_name=tool_name,
                scopes=scopes,
                auth_url=auth_url,
            )

            # Store pending flow
            self.pending_flows[flow_id] = auth_flow

            logger.info(
                "Authorization flow initiated",
                flow_id=flow_id,
                user_id=user_id,
                tool_name=tool_name,
                scopes=scopes,
            )

            return auth_flow

        except ValidationError:
            raise
        except Exception as e:
            logger.error(
                "Failed to initiate authorization",
                user_id=user_id,
                tool_name=tool_name,
                error=str(e),
            )
            raise ValidationError(f"Failed to initiate authorization: {str(e)}")

    async def complete_authorization(
        self, flow_id: str, authorization_code: Optional[str] = None
    ) -> Authorization:
        """
        Complete OAuth authorization flow.

        Args:
            flow_id: Authorization flow identifier
            authorization_code: OAuth authorization code

        Returns:
            Authorization object

        Raises:
            UnauthorizedError: If flow is invalid or expired
        """
        try:
            # Get pending flow
            if flow_id not in self.pending_flows:
                raise UnauthorizedError("Invalid or expired authorization flow")

            auth_flow = self.pending_flows[flow_id]

            # Check if flow is expired
            if auth_flow.is_expired():
                del self.pending_flows[flow_id]
                raise UnauthorizedError("Authorization flow expired")

            # For demo purposes, create authorization without actual OAuth
            # In production, exchange authorization_code for access token
            authorization = Authorization(
                user_id=auth_flow.user_id,
                tool_name=auth_flow.tool_name,
                scopes=auth_flow.scopes,
                access_token=f"demo_token_{flow_id}",
                expires_at=time.time() + 3600,  # 1 hour
            )

            # Store authorization
            auth_key = f"{auth_flow.user_id}:{auth_flow.tool_name}"
            self.active_authorizations[auth_key] = authorization

            # Clean up pending flow
            del self.pending_flows[flow_id]

            logger.info(
                "Authorization completed successfully",
                flow_id=flow_id,
                user_id=auth_flow.user_id,
                tool_name=auth_flow.tool_name,
            )

            return authorization

        except UnauthorizedError:
            raise
        except Exception as e:
            logger.error(
                "Failed to complete authorization", flow_id=flow_id, error=str(e)
            )
            raise UnauthorizedError(f"Failed to complete authorization: {str(e)}")

    def revoke_authorization(self, user_id: str, tool_name: str) -> bool:
        """
        Revoke user authorization for a tool.

        Args:
            user_id: User identifier
            tool_name: Tool name

        Returns:
            True if authorization was revoked
        """
        auth_key = f"{user_id}:{tool_name}"

        if auth_key in self.active_authorizations:
            del self.active_authorizations[auth_key]
            logger.info("Authorization revoked", user_id=user_id, tool_name=tool_name)
            return True

        return False

    def get_user_authorizations(self, user_id: str) -> List[Authorization]:
        """
        Get all authorizations for a user.

        Args:
            user_id: User identifier

        Returns:
            List of user authorizations
        """
        user_auths = []

        for auth_key, authorization in self.active_authorizations.items():
            if authorization.user_id == user_id:
                user_auths.append(authorization)

        return user_auths

    def cleanup_expired_authorizations(self) -> int:
        """
        Clean up expired authorizations and flows.

        Returns:
            Number of items cleaned up
        """
        cleaned_count = 0
        current_time = time.time()

        # Clean up expired authorizations
        expired_auths = []
        for auth_key, authorization in self.active_authorizations.items():
            if authorization.is_expired():
                expired_auths.append(auth_key)

        for auth_key in expired_auths:
            del self.active_authorizations[auth_key]
            cleaned_count += 1

        # Clean up expired flows
        expired_flows = []
        for flow_id, auth_flow in self.pending_flows.items():
            if auth_flow.is_expired():
                expired_flows.append(flow_id)

        for flow_id in expired_flows:
            del self.pending_flows[flow_id]
            cleaned_count += 1

        if cleaned_count > 0:
            logger.info(
                "Cleaned up expired items",
                count=cleaned_count,
                authorizations=len(expired_auths),
                flows=len(expired_flows),
            )

        return cleaned_count

    def get_available_scopes(self) -> Dict[str, str]:
        """Get available authorization scopes."""
        return self.available_scopes.copy()

    async def _refresh_authorization(
        self, authorization: Authorization
    ) -> Authorization:
        """
        Refresh an expired authorization using refresh token.

        Args:
            authorization: Authorization to refresh

        Returns:
            Refreshed authorization

        Raises:
            UnauthorizedError: If refresh fails
        """
        try:
            # In production, make actual OAuth refresh token request
            # For demo, just extend expiration
            refreshed_auth = Authorization(
                user_id=authorization.user_id,
                tool_name=authorization.tool_name,
                scopes=authorization.scopes,
                access_token=f"refreshed_{authorization.access_token}",
                refresh_token=authorization.refresh_token,
                expires_at=time.time() + 3600,  # 1 hour
                created_at=authorization.created_at,
            )

            logger.info(
                "Authorization refreshed",
                user_id=authorization.user_id,
                tool_name=authorization.tool_name,
            )

            return refreshed_auth

        except Exception as e:
            logger.error(
                "Failed to refresh authorization",
                user_id=authorization.user_id,
                tool_name=authorization.tool_name,
                error=str(e),
            )
            raise UnauthorizedError(f"Failed to refresh authorization: {str(e)}")

    def _create_auth_url(self, flow_id: str, scopes: List[str]) -> str:
        """Create OAuth authorization URL."""
        if not self.oauth_client_id or not self.oauth_redirect_uri:
            # Return demo URL if OAuth not configured
            return f"https://demo-oauth.example.com/authorize?flow_id={flow_id}&scopes={','.join(scopes)}"

        # In production, create actual OAuth URL
        scope_string = " ".join(scopes)
        auth_url = (
            f"https://oauth.provider.com/authorize"
            f"?client_id={self.oauth_client_id}"
            f"&redirect_uri={self.oauth_redirect_uri}"
            f"&scope={scope_string}"
            f"&state={flow_id}"
            f"&response_type=code"
        )

        return auth_url


# Utility functions for authorization


def create_authorization_manager(
    oauth_client_id: Optional[str] = None,
    oauth_client_secret: Optional[str] = None,
    oauth_redirect_uri: Optional[str] = None,
) -> AuthorizationManager:
    """
    Create and configure an authorization manager.

    Args:
        oauth_client_id: OAuth client ID
        oauth_client_secret: OAuth client secret
        oauth_redirect_uri: OAuth redirect URI

    Returns:
        Configured AuthorizationManager instance
    """
    return AuthorizationManager(
        oauth_client_id=oauth_client_id,
        oauth_client_secret=oauth_client_secret,
        oauth_redirect_uri=oauth_redirect_uri,
    )


def extract_required_scopes(tool_definition: Dict[str, Any]) -> List[str]:
    """
    Extract required scopes from tool definition.

    Args:
        tool_definition: Tool definition dictionary

    Returns:
        List of required scopes
    """
    return tool_definition.get("required_scopes", [])
