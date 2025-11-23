"""
HTTP Client Tools

CRUD-style tool for making HTTP/HTTPS requests to lab devices.
Useful for checking device APIs, health endpoints, retrieving data.

**Reverse HTTP/HTTPS proxy available** at http://proxy:8022/http-proxy/
for external device web UI access without SSH tunnel.
"""

import httpx
import json
import logging
from typing import Literal

from ..interfaces import IAppContext

logger = logging.getLogger(__name__)

# SSH Proxy API URL (defaults to GNS3 host IP)
import os
_gns3_host = os.getenv("GNS3_HOST", "localhost")
SSH_PROXY_URL = os.getenv("SSH_PROXY_URL", f"http://{_gns3_host}:8022")


async def http_client_impl(
    app: "IAppContext",
    action: Literal["get", "status"],
    url: str,
    timeout: int = 10,
    verify_ssl: bool = False,
    headers: dict | None = None,
) -> str:
    """
    HTTP client implementation

    Args:
        app: Application context
        action: HTTP action to perform (get, status)
        url: Target URL (http:// or https://)
        timeout: Request timeout in seconds
        verify_ssl: Verify SSL certificates
        headers: Optional custom headers

    Returns:
        JSON response from SSH proxy HTTP client endpoint
    """
    try:
        # Prepare request
        request_data = {
            "action": action,
            "url": url,
            "timeout": timeout,
            "verify_ssl": verify_ssl
        }

        if headers:
            request_data["headers"] = headers

        # Make request to SSH proxy
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{SSH_PROXY_URL}/http-client",
                json=request_data
            )
            response.raise_for_status()
            return json.dumps(response.json(), indent=2)

    except httpx.HTTPStatusError as e:
        error_detail = e.response.text
        logger.error(f"[HTTP-CLIENT] HTTP error {e.response.status_code}: {error_detail}")
        return json.dumps({
            "success": False,
            "action": action,
            "error": f"HTTP {e.response.status_code}: {error_detail}"
        }, indent=2)

    except Exception as e:
        logger.error(f"[HTTP-CLIENT] Error in {action}: {e}")
        return json.dumps({
            "success": False,
            "action": action,
            "error": str(e)
        }, indent=2)
