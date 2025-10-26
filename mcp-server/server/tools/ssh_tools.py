"""
SSH Proxy Tools for MCP Server

MCP tools that call the SSH proxy service API.
SSH proxy runs on port 8022 (separate container).

Workflow:
1. Use console tools to configure SSH access on device
2. Call configure_ssh() to establish SSH session
3. Use ssh_send_command() / ssh_send_config_set() for automation
4. Review history with ssh_get_history() and ssh_get_command_output()
"""

import json
import os
from typing import Dict, List, Optional, TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from main import AppContext


# SSH Proxy API URL (defaults to GNS3 host IP)
_gns3_host = os.getenv("GNS3_HOST", "localhost")
SSH_PROXY_URL = os.getenv("SSH_PROXY_URL", f"http://{_gns3_host}:8022")


# ============================================================================
# Session Management
# ============================================================================

async def configure_ssh_impl(
    app: "AppContext",
    node_name: str,
    device_dict: Dict,
    persist: bool = True,
    force: bool = False
) -> str:
    """
    Configure SSH session for network device

    IMPORTANT: Use console tools to enable SSH first!

    Example workflow:
    1. Access device via console:
       send_console('R1', 'configure terminal\\n')
       send_console('R1', 'username admin privilege 15 secret cisco123\\n')
       send_console('R1', 'crypto key generate rsa modulus 2048\\n')
       send_console('R1', 'ip ssh version 2\\n')
       send_console('R1', 'line vty 0 4\\n')
       send_console('R1', 'transport input ssh\\n')
       send_console('R1', 'end\\n')

    2. Then configure SSH session:
       configure_ssh('R1', {
           'device_type': 'cisco_ios',
           'host': '10.10.10.1',
           'username': 'admin',
           'password': 'cisco123'
       })

    Args:
        node_name: Node identifier
        device_dict: Netmiko device configuration dict
        persist: Store credentials for reconnection
        force: Force recreation even if session exists (v0.1.6)

    Returns:
        JSON with session_id, connected, device_type
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{SSH_PROXY_URL}/ssh/configure",
                json={
                    "node_name": node_name,
                    "device": device_dict,
                    "persist": persist,
                    "force_recreate": force  # v0.1.6: Allow forced recreation
                }
            )

            # Success - SSH connection established
            if response.status_code == 200:
                return json.dumps(response.json(), indent=2)

            # SSH connection error (400) or server error (500)
            try:
                error_data = response.json()
            except Exception:
                # JSON parsing failed - return raw response
                return json.dumps({
                    "error": f"HTTP {response.status_code}",
                    "details": response.text,
                    "suggestion": "Unexpected response format from SSH proxy"
                }, indent=2)

            # Extract error details from FastAPI HTTPException response
            detail = error_data.get("detail", {})

            # Handle structured error response
            if isinstance(detail, dict):
                return json.dumps({
                    "error": detail.get("error", f"HTTP {response.status_code} error"),
                    "details": detail.get("details"),
                    "ssh_connection_error": detail.get("ssh_connection_error")
                }, indent=2)
            else:
                # detail is a string or other type
                return json.dumps({
                    "error": f"HTTP {response.status_code} error",
                    "details": str(detail)
                }, indent=2)

        except httpx.RequestError as e:
            # Network/connection errors
            return json.dumps({
                "error": "Failed to connect to SSH proxy service",
                "details": str(e),
                "suggestion": "Ensure SSH proxy service is running: docker ps | grep gns3-ssh-proxy"
            }, indent=2)

        except Exception as e:
            # Unexpected errors
            return json.dumps({
                "error": "Unexpected error",
                "details": str(e),
                "suggestion": "Check SSH proxy logs for details"
            }, indent=2)


# ============================================================================
# Command Execution
# ============================================================================

async def ssh_send_command_impl(
    app: "AppContext",
    node_name: str,
    command: str,
    expect_string: Optional[str] = None,
    read_timeout: float = 30.0,
    wait_timeout: int = 30
) -> str:
    """
    Execute show command via SSH with adaptive async

    Creates Job immediately, polls for wait_timeout seconds.
    Returns output if completes, else returns job_id for polling.

    For long-running commands (e.g., 15-minute installations):
    - Set read_timeout=900 (or higher)
    - Set wait_timeout=0 to return job_id immediately
    - Poll with: ssh_get_job_status(job_id)

    For interactive prompts:
    - Use expect_string parameter
    - Example: expect_string=r"Delete filename.*?"

    Args:
        node_name: Node identifier
        command: Command to execute
        expect_string: Regex pattern to wait for (overrides prompt detection)
        read_timeout: Max time to wait for output (seconds)
        wait_timeout: Time to poll before returning job_id (seconds)

    Returns:
        JSON with completed, job_id, output, execution_time
    """
    async with httpx.AsyncClient(timeout=read_timeout + wait_timeout + 10) as client:
        try:
            response = await client.post(
                f"{SSH_PROXY_URL}/ssh/send_command",
                json={
                    "node_name": node_name,
                    "command": command,
                    "expect_string": expect_string,
                    "read_timeout": read_timeout,
                    "wait_timeout": wait_timeout,
                    "strip_prompt": True,
                    "strip_command": True
                }
            )

            if response.status_code == 200:
                return json.dumps(response.json(), indent=2)
            else:
                error_data = response.json()
                return json.dumps({
                    "error": error_data.get("detail", {}).get("error", "Command failed"),
                    "details": error_data.get("detail", {}).get("details")
                }, indent=2)

        except Exception as e:
            return json.dumps({
                "error": "SSH command failed",
                "details": str(e)
            }, indent=2)


async def ssh_send_config_set_impl(
    app: "AppContext",
    node_name: str,
    config_commands: List[str],
    wait_timeout: int = 30
) -> str:
    """
    Send configuration commands via SSH

    Creates Job immediately, uses adaptive async pattern.

    Args:
        node_name: Node identifier
        config_commands: List of configuration commands
        wait_timeout: Time to poll before returning job_id (seconds)

    Returns:
        JSON with completed, job_id, output, execution_time

    Example:
        ssh_send_config_set('R1', [
            'interface GigabitEthernet0/0',
            'ip address 192.168.1.1 255.255.255.0',
            'no shutdown'
        ])
    """
    async with httpx.AsyncClient(timeout=wait_timeout + 60) as client:
        try:
            response = await client.post(
                f"{SSH_PROXY_URL}/ssh/send_config_set",
                json={
                    "node_name": node_name,
                    "config_commands": config_commands,
                    "wait_timeout": wait_timeout,
                    "exit_config_mode": True
                }
            )

            if response.status_code == 200:
                return json.dumps(response.json(), indent=2)
            else:
                error_data = response.json()
                return json.dumps({
                    "error": error_data.get("detail", {}).get("error", "Config failed"),
                    "details": error_data.get("detail", {}).get("details")
                }, indent=2)

        except Exception as e:
            return json.dumps({
                "error": "SSH config failed",
                "details": str(e)
            }, indent=2)


# ============================================================================
# Buffer Reading (Storage System 1)
# ============================================================================

async def ssh_read_buffer_impl(
    app: "AppContext",
    node_name: str,
    mode: str = "diff",
    pages: int = 1
) -> str:
    """
    Read continuous buffer (all commands combined)

    Modes:
    - diff: New output since last read (default)
    - last_page: Last ~25 lines
    - num_pages: Last N pages (~25 lines per page)
    - all: Entire buffer (WARNING: May be very large!)

    Args:
        node_name: Node identifier
        mode: Output mode
        pages: Number of pages (only valid with mode='num_pages')

    Returns:
        JSON with output and buffer_size
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
                "error": "Buffer read failed",
                "details": str(e)
            }, indent=2)


# ============================================================================
# Command History (Storage System 2)
# ============================================================================

async def ssh_get_history_impl(
    app: "AppContext",
    node_name: str,
    limit: int = 50,
    search: Optional[str] = None
) -> str:
    """
    List command history in execution order

    Returns job summaries with abbreviated info.

    Args:
        node_name: Node identifier
        limit: Max number of jobs to return (default: 50, max: 1000)
        search: Filter by command text (case-insensitive)

    Returns:
        JSON with total_commands and jobs list

    Example:
        # Get last 10 commands
        ssh_get_history('R1', limit=10)

        # Search for interface commands
        ssh_get_history('R1', search='interface')
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
                "error": "History retrieval failed",
                "details": str(e)
            }, indent=2)


async def ssh_get_command_output_impl(
    app: "AppContext",
    node_name: str,
    job_id: str
) -> str:
    """
    Get specific command's full output

    Use ssh_get_history() to find job_id, then get full output.

    Args:
        node_name: Node identifier
        job_id: Job ID from history

    Returns:
        JSON with full Job details (command, output, timestamps, etc.)

    Example:
        # 1. Get history
        history = ssh_get_history('R1', limit=10)

        # 2. Find job_id of interest

        # 3. Get full output
        ssh_get_command_output('R1', 'abc123-def456...')
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"{SSH_PROXY_URL}/ssh/history/{node_name}/{job_id}"
            )

            if response.status_code == 200:
                return json.dumps(response.json(), indent=2)
            else:
                error_data = response.json()
                return json.dumps({
                    "error": error_data.get("detail", {}).get("error", "Job not found"),
                    "details": error_data.get("detail", {}).get("details")
                }, indent=2)

        except Exception as e:
            return json.dumps({
                "error": "Job retrieval failed",
                "details": str(e)
            }, indent=2)


# ============================================================================
# Session Status
# ============================================================================

async def ssh_get_status_impl(
    app: "AppContext",
    node_name: str
) -> str:
    """
    Check SSH session status

    Returns:
        JSON with connected, session_id, device_type, buffer_size, total_commands
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"{SSH_PROXY_URL}/ssh/status/{node_name}"
            )

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
                "error": "Status check failed",
                "details": str(e)
            }, indent=2)


# ============================================================================
# Session Cleanup
# ============================================================================

async def ssh_disconnect_impl(
    app: "AppContext",
    node_name: str
) -> str:
    """
    Disconnect SSH session for specific node

    Args:
        node_name: Node identifier to disconnect

    Returns:
        JSON with status

    Example:
        ssh_disconnect('R1')
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Use cleanup endpoint to disconnect specific node
            # Keep all nodes EXCEPT the one we want to disconnect
            response = await client.delete(
                f"{SSH_PROXY_URL}/ssh/session/{node_name}"
            )

            if response.status_code == 200:
                return json.dumps({
                    "status": "success",
                    "message": f"Disconnected SSH session for {node_name}"
                }, indent=2)
            elif response.status_code == 404:
                return json.dumps({
                    "status": "success",
                    "message": f"No active SSH session for {node_name}"
                }, indent=2)
            else:
                error_data = response.json()
                return json.dumps({
                    "error": error_data.get("detail", {}).get("error", "Disconnect failed"),
                    "details": error_data.get("detail", {}).get("details")
                }, indent=2)

        except Exception as e:
            return json.dumps({
                "error": "Disconnect failed",
                "details": str(e)
            }, indent=2)


async def ssh_cleanup_sessions_impl(
    app: "AppContext",
    keep_nodes: List[str] = None,
    clean_all: bool = False
) -> str:
    """
    Clean orphaned/all SSH sessions

    Useful when project changes (different IP addresses on same node names).

    Args:
        keep_nodes: Node names to preserve (default: [])
        clean_all: Clean all sessions, ignoring keep_nodes (default: False)

    Returns:
        JSON with cleaned and kept node lists

    Example:
        # Clean all except R1 and R2
        ssh_cleanup_sessions(keep_nodes=['R1', 'R2'])

        # Clean all sessions
        ssh_cleanup_sessions(clean_all=True)
    """
    if keep_nodes is None:
        keep_nodes = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{SSH_PROXY_URL}/ssh/cleanup",
                json={
                    "keep_nodes": keep_nodes,
                    "clean_all": clean_all
                }
            )

            if response.status_code == 200:
                return json.dumps(response.json(), indent=2)
            else:
                error_data = response.json()
                return json.dumps({
                    "error": error_data.get("detail", {}).get("error", "Cleanup failed"),
                    "details": error_data.get("detail", {}).get("details")
                }, indent=2)

        except Exception as e:
            return json.dumps({
                "error": "Cleanup failed",
                "details": str(e)
            }, indent=2)


# ============================================================================
# Job Status (for async polling)
# ============================================================================

async def ssh_get_job_status_impl(
    app: "AppContext",
    job_id: str
) -> str:
    """
    Check job status by job_id (for async polling)

    Use this to poll long-running commands that returned job_id.

    Args:
        job_id: Job ID from ssh_send_command or ssh_send_config_set

    Returns:
        JSON with job status, output, execution_time

    Example:
        # 1. Start long-running command
        result = ssh_send_command('R1', 'copy running startup', wait_timeout=0)
        job_id = result['job_id']

        # 2. Poll for completion
        status = ssh_get_job_status(job_id)
        # Check status['status'] == 'completed'
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"{SSH_PROXY_URL}/ssh/job/{job_id}"
            )

            if response.status_code == 200:
                return json.dumps(response.json(), indent=2)
            else:
                error_data = response.json()
                return json.dumps({
                    "error": error_data.get("detail", {}).get("error", "Job not found"),
                    "details": error_data.get("detail", {}).get("details")
                }, indent=2)

        except Exception as e:
            return json.dumps({
                "error": "Job status check failed",
                "details": str(e)
            }, indent=2)
