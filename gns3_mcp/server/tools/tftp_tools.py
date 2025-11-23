"""
TFTP Management Tools

CRUD-style tool for managing files on SSH proxy TFTP server.
TFTP server runs on port 69/udp with root directory /opt/gns3-ssh-proxy/tftp.
"""

import base64
import httpx
import json
import logging
from typing import Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from interfaces import IAppContext

logger = logging.getLogger(__name__)

# SSH Proxy API URL (defaults to GNS3 host IP)
import os
_gns3_host = os.getenv("GNS3_HOST", "localhost")
SSH_PROXY_URL = os.getenv("SSH_PROXY_URL", f"http://{_gns3_host}:8022")


async def tftp_impl(
    app: "IAppContext",
    action: Literal["list", "upload", "download", "delete", "status"],
    filename: str | None = None,
    content: bytes | None = None,
) -> str:
    """
    TFTP management implementation

    Args:
        app: Application context
        action: TFTP action to perform
        filename: Filename for upload/download/delete
        content: File content for upload (raw bytes)

    Returns:
        JSON response from SSH proxy TFTP endpoint
    """
    try:
        # Prepare request
        request_data = {"action": action}

        if filename:
            request_data["filename"] = filename

        if content:
            # Encode content as base64
            content_b64 = base64.b64encode(content).decode('utf-8')
            request_data["content"] = content_b64

        # Make request to SSH proxy
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{SSH_PROXY_URL}/tftp",
                json=request_data
            )
            response.raise_for_status()
            return json.dumps(response.json(), indent=2)

    except httpx.HTTPStatusError as e:
        error_detail = e.response.text
        logger.error(f"[TFTP] HTTP error {e.response.status_code}: {error_detail}")
        return json.dumps({
            "success": False,
            "action": action,
            "error": f"HTTP {e.response.status_code}: {error_detail}"
        }, indent=2)

    except Exception as e:
        logger.error(f"[TFTP] Error in {action}: {e}")
        return json.dumps({
            "success": False,
            "action": action,
            "error": str(e)
        }, indent=2)
