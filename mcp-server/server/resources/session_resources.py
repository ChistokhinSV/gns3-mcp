"""
Session-related MCP Resources

Handles resources for console and SSH sessions, including history and buffers.
"""

import json
import os
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from main import AppContext


# SSH Proxy API URL (same as ssh_tools.py)
_gns3_host = os.getenv("GNS3_HOST", "localhost")
SSH_PROXY_URL = os.getenv("SSH_PROXY_URL", f"http://{_gns3_host}:8022")


async def list_console_sessions_impl(app: "AppContext", project_id: str) -> str:
    """
    List all active console sessions for nodes in a project

    Resource URI: gns3://projects/{project_id}/sessions/console

    Args:
        project_id: Project ID to filter sessions by

    Returns:
        JSON array of console session information for project nodes
    """
    try:
        # Get nodes in the project to filter sessions
        nodes_data = await app.gns3.get_nodes(project_id)
        project_node_names = {node["name"] for node in nodes_data}

        # Filter sessions to only include nodes in this project
        sessions = []
        for node_name, session_info in app.console.sessions.items():
            if node_name in project_node_names:
                sessions.append({
                    "node_name": node_name,
                    "connected": session_info.connected,
                    "session_id": session_info.session_id,
                    "host": session_info.host,
                    "port": session_info.port,
                    "buffer_size": len(session_info.buffer),
                    "created_at": session_info.created_at.isoformat() if session_info.created_at else None
                })

        return json.dumps(sessions, indent=2)
    except Exception as e:
        return json.dumps({
            "error": "Failed to list console sessions",
            "details": str(e)
        }, indent=2)


async def get_console_session_impl(app: "AppContext", node_name: str) -> str:
    """
    Get console session status for a specific node

    Resource URI: gns3://sessions/console/{node_name}

    Args:
        node_name: Name of the node

    Returns:
        JSON object with console session status
    """
    try:
        session_info = app.console.sessions.get(node_name)

        if not session_info:
            return json.dumps({
                "connected": False,
                "node_name": node_name,
                "session_id": None,
                "host": None,
                "port": None,
                "buffer_size": 0,
                "created_at": None
            }, indent=2)

        return json.dumps({
            "connected": session_info.connected,
            "node_name": node_name,
            "session_id": session_info.session_id,
            "host": session_info.host,
            "port": session_info.port,
            "buffer_size": len(session_info.buffer),
            "created_at": session_info.created_at.isoformat() if session_info.created_at else None
        }, indent=2)
    except Exception as e:
        return json.dumps({
            "error": "Failed to get console session",
            "node_name": node_name,
            "details": str(e)
        }, indent=2)


async def list_ssh_sessions_impl(app: "AppContext", project_id: str) -> str:
    """
    List all active SSH sessions for nodes in a project

    Resource URI: gns3://projects/{project_id}/sessions/ssh

    Args:
        project_id: Project ID to filter sessions by

    Returns:
        JSON array of SSH session information for project nodes
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Get nodes in the project
            nodes_data = await app.gns3.get_nodes(project_id)

            # Check SSH status for each node
            sessions = []
            for node in nodes_data:
                node_name = node["name"]
                try:
                    response = await client.get(f"{SSH_PROXY_URL}/ssh/status/{node_name}")
                    if response.status_code == 200:
                        status = response.json()
                        # Only include if connected
                        if status.get("connected", False):
                            sessions.append(status)
                except Exception:
                    # Skip nodes that fail status check
                    continue

            return json.dumps(sessions, indent=2)

        except Exception as e:
            return json.dumps({
                "error": "Failed to list SSH sessions",
                "details": str(e),
                "suggestion": "Ensure SSH proxy service is running: docker ps | grep gns3-ssh-proxy"
            }, indent=2)


async def get_ssh_session_impl(app: "AppContext", node_name: str) -> str:
    """
    Get SSH session status for a specific node

    Resource URI: gns3://sessions/ssh/{node_name}

    Args:
        node_name: Name of the node

    Returns:
        JSON object with SSH session status
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(f"{SSH_PROXY_URL}/ssh/status/{node_name}")

            if response.status_code == 200:
                return json.dumps(response.json(), indent=2)
            else:
                # Should not happen, but handle gracefully
                return json.dumps({
                    "connected": False,
                    "node_name": node_name,
                    "error": "Status check failed"
                }, indent=2)

        except Exception as e:
            return json.dumps({
                "error": "Failed to get SSH session status",
                "node_name": node_name,
                "details": str(e)
            }, indent=2)


async def get_ssh_history_impl(app: "AppContext", node_name: str, limit: int = 50, search: str = None) -> str:
    """
    Get SSH command history for a specific node

    Resource URI: gns3://sessions/ssh/{node_name}/history

    Args:
        node_name: Name of the node
        limit: Maximum number of commands to return (default: 50)
        search: Optional search filter for command text

    Returns:
        JSON object with command history
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            params = {"limit": limit}
            if search:
                params["search"] = search

            response = await client.get(
                f"{SSH_PROXY_URL}/ssh/history/{node_name}",
                params=params
            )

            if response.status_code == 200:
                return json.dumps(response.json(), indent=2)
            else:
                error_data = response.json()
                return json.dumps({
                    "error": error_data.get("detail", {}).get("error", "History retrieval failed"),
                    "details": error_data.get("detail", {}).get("details")
                }, indent=2)

        except Exception as e:
            return json.dumps({
                "error": "Failed to get SSH command history",
                "node_name": node_name,
                "details": str(e)
            }, indent=2)


async def get_ssh_buffer_impl(app: "AppContext", node_name: str, mode: str = "diff", pages: int = 1) -> str:
    """
    Get SSH continuous buffer for a specific node

    Resource URI: gns3://sessions/ssh/{node_name}/buffer

    Args:
        node_name: Name of the node
        mode: Output mode (diff/last_page/num_pages/all)
        pages: Number of pages for num_pages mode

    Returns:
        JSON object with buffer output
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"{SSH_PROXY_URL}/ssh/buffer/{node_name}",
                params={"mode": mode, "pages": pages}
            )

            if response.status_code == 200:
                return json.dumps(response.json(), indent=2)
            else:
                error_data = response.json()
                return json.dumps({
                    "error": error_data.get("detail", {}).get("error", "Buffer read failed"),
                    "details": error_data.get("detail", {}).get("details")
                }, indent=2)

        except Exception as e:
            return json.dumps({
                "error": "Failed to read SSH buffer",
                "node_name": node_name,
                "details": str(e)
            }, indent=2)


async def get_proxy_status_impl(app: "AppContext") -> str:
    """
    Get SSH proxy service status

    Resource URI: gns3://proxy/status

    Returns:
        JSON object with proxy service status
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{SSH_PROXY_URL}/health")

            if response.status_code == 200:
                data = response.json()
                return json.dumps({
                    "status": "running",
                    "url": SSH_PROXY_URL,
                    "version": data.get("version", "unknown"),
                    "health": "healthy"
                }, indent=2)
            else:
                return json.dumps({
                    "status": "unhealthy",
                    "url": SSH_PROXY_URL,
                    "error": "Non-200 response from health check"
                }, indent=2)

        except Exception as e:
            return json.dumps({
                "status": "unreachable",
                "url": SSH_PROXY_URL,
                "error": str(e),
                "suggestion": "Ensure SSH proxy service is running: docker ps | grep gns3-ssh-proxy"
            }, indent=2)


async def get_proxy_registry_impl(app: "AppContext") -> str:
    """
    Get proxy registry (discovered lab proxies via Docker API)

    Resource URI: gns3://proxy/registry

    Returns:
        JSON object with discovered proxy information including:
        - available: Whether discovery is enabled (Docker socket mounted)
        - proxies: Array of discovered lab proxies with details
        - count: Number of proxies found
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{SSH_PROXY_URL}/proxy/registry")

            if response.status_code == 200:
                data = response.json()
                return json.dumps(data, indent=2)
            else:
                return json.dumps({
                    "available": False,
                    "proxies": [],
                    "count": 0,
                    "error": f"HTTP {response.status_code} from proxy registry endpoint"
                }, indent=2)

        except Exception as e:
            return json.dumps({
                "available": False,
                "proxies": [],
                "count": 0,
                "error": str(e),
                "suggestion": "Ensure SSH proxy service is running with Docker socket mounted"
            }, indent=2)


async def list_proxy_sessions_impl(app: "AppContext") -> str:
    """
    List all SSH proxy sessions (same as list_ssh_sessions)

    Resource URI: gns3://proxy/sessions

    Returns:
        JSON array of all SSH sessions
    """
    # Delegate to list_ssh_sessions_impl
    return await list_ssh_sessions_impl(app)


async def list_proxies_impl(app: "AppContext") -> str:
    """
    List all discovered proxies (template-style resource)

    Resource URI: gns3://proxies

    Returns:
        JSON array of proxy summaries suitable for selection/browsing
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{SSH_PROXY_URL}/proxy/registry")

            if response.status_code == 200:
                data = response.json()
                # Return just the proxies array for template-style browsing
                return json.dumps(data.get("proxies", []), indent=2)
            else:
                return json.dumps([], indent=2)

        except Exception:
            return json.dumps([], indent=2)


async def get_proxy_impl(app: "AppContext", proxy_id: str) -> str:
    """
    Get specific proxy details by proxy_id

    Resource URI: gns3://proxy/{proxy_id}

    Args:
        proxy_id: GNS3 node_id of the proxy

    Returns:
        JSON object with full proxy details
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{SSH_PROXY_URL}/proxy/registry")

            if response.status_code == 200:
                data = response.json()
                proxies = data.get("proxies", [])

                # Find proxy by proxy_id
                for proxy in proxies:
                    if proxy.get("proxy_id") == proxy_id:
                        return json.dumps(proxy, indent=2)

                # Proxy not found
                return json.dumps({
                    "error": f"Proxy not found: {proxy_id}",
                    "available_proxies": [p.get("proxy_id") for p in proxies]
                }, indent=2)
            else:
                return json.dumps({
                    "error": "Failed to fetch proxy registry"
                }, indent=2)

        except Exception as e:
            return json.dumps({
                "error": str(e)
            }, indent=2)
