"""
FACT System HTTP Connector

This module provides HTTP/API tool implementations for making
external web requests with security validation and rate limiting.
"""

import asyncio
import json
import time
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse
import structlog

# Import aiohttp for async HTTP requests
try:
    import aiohttp

    HTTP_AVAILABLE = True
except ImportError:
    HTTP_AVAILABLE = False
    aiohttp = None

from tools.decorators import Tool
from ...core.errors import ToolExecutionError, SecurityError, ValidationError

logger = structlog.get_logger(__name__)


@Tool(
    name="Web.HTTPRequest",
    description="Make HTTP requests to external APIs with security validation",
    parameters={
        "url": {
            "type": "string",
            "description": "URL to request (must be HTTPS for external APIs)",
            "pattern": r"^https?://.*",
            "maxLength": 2000,
        },
        "method": {
            "type": "string",
            "description": "HTTP method",
            "enum": ["GET", "POST", "PUT", "DELETE"],
            "default": "GET",
        },
        "headers": {
            "type": "object",
            "description": "Request headers",
            "default": {},
            "additionalProperties": {"type": "string"},
        },
        "data": {
            "type": "object",
            "description": "Request body data for POST/PUT requests",
            "default": {},
        },
        "timeout": {
            "type": "number",
            "description": "Request timeout in seconds",
            "default": 30,
            "minimum": 1,
            "maximum": 60,
        },
        "follow_redirects": {
            "type": "boolean",
            "description": "Whether to follow HTTP redirects",
            "default": True,
        },
    },
    requires_auth=False,
    timeout_seconds=60,
)
async def http_request_tool(
    url: str,
    method: str = "GET",
    headers: Dict[str, str] = None,
    data: Dict[str, Any] = None,
    timeout: int = 30,
    follow_redirects: bool = True,
) -> Dict[str, Any]:
    """
    Make HTTP requests to external APIs.

    Args:
        url: URL to request
        method: HTTP method
        headers: Request headers
        data: Request body data
        timeout: Request timeout
        follow_redirects: Whether to follow redirects

    Returns:
        HTTP response data

    Raises:
        ToolExecutionError: If request fails
        SecurityError: If URL is not allowed
    """
    if not HTTP_AVAILABLE:
        raise ToolExecutionError(
            "aiohttp library not available. Install with: pip install aiohttp"
        )

    start_time = time.time()
    request_id = f"req_{int(start_time * 1000)}"

    # Security validation
    _validate_url_security(url)

    # Prepare headers
    if headers is None:
        headers = {}

    # Add default headers
    default_headers = {
        "User-Agent": "FACT-System/1.0",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
    }

    # Merge headers (user headers override defaults)
    request_headers = {**default_headers, **headers}

    try:
        logger.info(
            "Making HTTP request",
            request_id=request_id,
            url=url,
            method=method,
            timeout=timeout,
        )

        # Create HTTP session
        connector = aiohttp.TCPConnector(
            limit=10, limit_per_host=5, ttl_dns_cache=300, use_dns_cache=True
        )

        async with aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=timeout),
            headers={"User-Agent": request_headers["User-Agent"]},
        ) as session:

            # Prepare request kwargs
            request_kwargs = {
                "headers": request_headers,
                "allow_redirects": follow_redirects,
            }

            # Add data for POST/PUT requests
            if method in ["POST", "PUT"] and data:
                request_kwargs["json"] = data

            # Make request
            async with session.request(method, url, **request_kwargs) as response:
                response_time = (time.time() - start_time) * 1000

                # Read response content
                try:
                    if (
                        response.content_type
                        and "application/json" in response.content_type
                    ):
                        response_data = await response.json()
                    else:
                        response_text = await response.text()
                        # Try to parse as JSON, fallback to text
                        try:
                            response_data = json.loads(response_text)
                        except json.JSONDecodeError:
                            response_data = response_text
                except Exception as e:
                    logger.warning("Failed to parse response content", error=str(e))
                    response_data = await response.text()

                # Prepare result
                result = {
                    "request_id": request_id,
                    "url": url,
                    "method": method,
                    "status_code": response.status,
                    "headers": dict(response.headers),
                    "response_time_ms": response_time,
                    "content_length": len(str(response_data)),
                    "content_type": response.content_type,
                    "data": response_data,
                }

                # Check for HTTP errors
                if response.status >= 400:
                    result["success"] = False
                    result["error"] = f"HTTP {response.status} error"
                    logger.warning(
                        "HTTP request returned error status",
                        request_id=request_id,
                        status_code=response.status,
                        url=url,
                    )
                else:
                    result["success"] = True

                logger.info(
                    "HTTP request completed",
                    request_id=request_id,
                    status_code=response.status,
                    response_time_ms=response_time,
                    content_length=result["content_length"],
                )

                return result

    except asyncio.TimeoutError:
        response_time = (time.time() - start_time) * 1000
        logger.error(
            "HTTP request timed out",
            request_id=request_id,
            url=url,
            timeout=timeout,
            response_time_ms=response_time,
        )

        return {
            "request_id": request_id,
            "url": url,
            "method": method,
            "success": False,
            "error": f"Request timed out after {timeout} seconds",
            "response_time_ms": response_time,
            "status": "timeout",
        }

    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        logger.error(
            "HTTP request failed",
            request_id=request_id,
            url=url,
            error=str(e),
            response_time_ms=response_time,
        )

        return {
            "request_id": request_id,
            "url": url,
            "method": method,
            "success": False,
            "error": f"Request failed: {str(e)}",
            "response_time_ms": response_time,
            "status": "error",
        }


@Tool(
    name="Web.URLHealth",
    description="Check the health and availability of a URL endpoint",
    parameters={
        "url": {
            "type": "string",
            "description": "URL to check",
            "pattern": r"^https?://.*",
        },
        "timeout": {
            "type": "number",
            "description": "Timeout in seconds",
            "default": 10,
            "minimum": 1,
            "maximum": 30,
        },
    },
    requires_auth=False,
    timeout_seconds=30,
)
async def url_health_check_tool(url: str, timeout: int = 10) -> Dict[str, Any]:
    """
    Check the health and availability of a URL endpoint.

    Args:
        url: URL to check
        timeout: Request timeout in seconds

    Returns:
        Health check results
    """
    start_time = time.time()

    # Security validation
    _validate_url_security(url)

    try:
        # Make HEAD request for efficiency
        result = await http_request_tool(
            url=url,
            method="GET",  # Some servers don't support HEAD
            timeout=timeout,
            headers={"Accept": "text/html,application/json,*/*"},
        )

        response_time = (time.time() - start_time) * 1000

        health_result = {
            "url": url,
            "available": result.get("success", False),
            "status_code": result.get("status_code"),
            "response_time_ms": response_time,
            "content_type": result.get("content_type"),
            "server": result.get("headers", {}).get("server"),
            "last_modified": result.get("headers", {}).get("last-modified"),
            "content_length": result.get("content_length"),
        }

        if not result.get("success", False):
            health_result["error"] = result.get("error")

        logger.info(
            "URL health check completed",
            url=url,
            available=health_result["available"],
            response_time_ms=response_time,
        )

        return health_result

    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        logger.error(
            "URL health check failed",
            url=url,
            error=str(e),
            response_time_ms=response_time,
        )

        return {
            "url": url,
            "available": False,
            "error": str(e),
            "response_time_ms": response_time,
        }


def _validate_url_security(url: str) -> None:
    """
    Validate URL for security constraints.

    Args:
        url: URL to validate

    Raises:
        SecurityError: If URL is not allowed
    """
    try:
        parsed_url = urlparse(url)

        # Only allow HTTP and HTTPS
        if parsed_url.scheme not in ["http", "https"]:
            raise SecurityError("Only HTTP and HTTPS URLs are allowed")

        # Block localhost and private IP ranges
        hostname = parsed_url.hostname
        if not hostname:
            raise SecurityError("Invalid hostname in URL")

        hostname_lower = hostname.lower()

        # Block localhost variations
        localhost_patterns = [
            "localhost",
            "127.0.0.1",
            "0.0.0.0",
            "::1",
            "metadata.google.internal",
            "169.254.169.254",
        ]

        if hostname_lower in localhost_patterns:
            raise SecurityError("Access to localhost/internal URLs not allowed")

        # Block private IP ranges (basic check)
        if hostname_lower.startswith(("10.", "172.", "192.168.")):
            raise SecurityError("Access to private IP ranges not allowed")

        # Check for suspicious patterns
        suspicious_patterns = [
            "file://",
            "ftp://",
            "javascript:",
            "data:",
            "gopher://",
            "ldap://",
            "dict://",
        ]

        url_lower = url.lower()
        for pattern in suspicious_patterns:
            if pattern in url_lower:
                raise SecurityError(f"URL contains suspicious pattern: {pattern}")

        # Length check
        if len(url) > 2000:
            raise SecurityError("URL too long")

    except SecurityError:
        raise
    except Exception as e:
        raise SecurityError(f"URL validation failed: {str(e)}")


# Additional HTTP utility tools


@Tool(
    name="Web.ParseJSON",
    description="Parse and validate JSON data from text",
    parameters={
        "json_text": {
            "type": "string",
            "description": "JSON text to parse",
            "maxLength": 100000,
        },
        "validate_schema": {
            "type": "boolean",
            "description": "Whether to validate against a schema",
            "default": False,
        },
    },
    requires_auth=False,
    timeout_seconds=10,
)
def parse_json_tool(json_text: str, validate_schema: bool = False) -> Dict[str, Any]:
    """
    Parse and validate JSON data from text.

    Args:
        json_text: JSON text to parse
        validate_schema: Whether to validate schema

    Returns:
        Parsed JSON data with validation results
    """
    try:
        # Parse JSON
        parsed_data = json.loads(json_text)

        result = {
            "success": True,
            "data": parsed_data,
            "type": type(parsed_data).__name__,
            "size_bytes": len(json_text),
        }

        # Basic structure analysis
        if isinstance(parsed_data, dict):
            result["keys"] = list(parsed_data.keys())
            result["key_count"] = len(parsed_data)
        elif isinstance(parsed_data, list):
            result["item_count"] = len(parsed_data)
            if parsed_data and isinstance(parsed_data[0], dict):
                result["sample_keys"] = list(parsed_data[0].keys())

        logger.debug(
            "JSON parsed successfully",
            type=result["type"],
            size_bytes=result["size_bytes"],
        )

        return result

    except json.JSONDecodeError as e:
        logger.warning(
            "JSON parsing failed",
            error=str(e),
            line=getattr(e, "lineno", None),
            column=getattr(e, "colno", None),
        )

        return {
            "success": False,
            "error": f"JSON parsing failed: {str(e)}",
            "line": getattr(e, "lineno", None),
            "column": getattr(e, "colno", None),
            "size_bytes": len(json_text),
        }

    except Exception as e:
        logger.error("Unexpected error parsing JSON", error=str(e))

        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "size_bytes": len(json_text),
        }


@Tool(
    name="Web.ExtractURLs",
    description="Extract URLs from text content",
    parameters={
        "text": {
            "type": "string",
            "description": "Text content to extract URLs from",
            "maxLength": 50000,
        },
        "schemes": {
            "type": "array",
            "description": "URL schemes to extract",
            "items": {"type": "string"},
            "default": ["http", "https"],
        },
    },
    requires_auth=False,
    timeout_seconds=10,
)
def extract_urls_tool(text: str, schemes: List[str] = None) -> Dict[str, Any]:
    """
    Extract URLs from text content.

    Args:
        text: Text content to extract URLs from
        schemes: URL schemes to look for

    Returns:
        Extracted URLs with metadata
    """
    import re

    if schemes is None:
        schemes = ["http", "https"]

    try:
        # Create regex pattern for URL extraction
        scheme_pattern = "|".join(re.escape(scheme) for scheme in schemes)
        url_pattern = rf'\b(?:{scheme_pattern})://[^\s<>"{{}}|\\^`\[\]]*'

        # Find all URLs
        urls = re.findall(url_pattern, text, re.IGNORECASE)

        # Remove duplicates while preserving order
        unique_urls = []
        seen = set()
        for url in urls:
            if url not in seen:
                unique_urls.append(url)
                seen.add(url)

        # Analyze URLs
        url_analysis = []
        for url in unique_urls:
            try:
                parsed = urlparse(url)
                analysis = {
                    "url": url,
                    "scheme": parsed.scheme,
                    "hostname": parsed.hostname,
                    "path": parsed.path,
                    "has_query": bool(parsed.query),
                    "has_fragment": bool(parsed.fragment),
                }
                url_analysis.append(analysis)
            except Exception as e:
                logger.warning("Failed to parse extracted URL", url=url, error=str(e))
                url_analysis.append({"url": url, "error": f"Parse error: {str(e)}"})

        result = {
            "success": True,
            "urls": unique_urls,
            "url_count": len(unique_urls),
            "total_matches": len(urls),
            "schemes_found": list(
                set(
                    analysis.get("scheme")
                    for analysis in url_analysis
                    if "scheme" in analysis
                )
            ),
            "analysis": url_analysis,
            "text_length": len(text),
        }

        logger.debug(
            "URLs extracted successfully",
            url_count=result["url_count"],
            text_length=len(text),
        )

        return result

    except Exception as e:
        logger.error("URL extraction failed", error=str(e))

        return {
            "success": False,
            "error": f"URL extraction failed: {str(e)}",
            "text_length": len(text),
        }
