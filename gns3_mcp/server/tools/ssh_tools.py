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
from typing import TYPE_CHECKING, Dict, List, Optional

import httpx
from error_utils import create_error_response, validation_error
from fastmcp import Context
from models import ErrorCode

if TYPE_CHECKING:
    from main import AppContext


# SSH Proxy API URL (defaults to GNS3 host IP)
_gns3_host = os.getenv("GNS3_HOST", "localhost")
SSH_PROXY_URL = os.getenv("SSH_PROXY_URL", f"http://{_gns3_host}:8022")


# ============================================================================
# Proxy URL Resolution
# ============================================================================

def _get_proxy_url_for_node(app: "AppContext", node_name: str) -> str:
    """
    Get proxy URL for a node from stored mapping

    Args:
        app: Application context
        node_name: Node identifier

    Returns:
        Proxy URL for this node (defaults to SSH_PROXY_URL if not mapped)
    """
    return app.ssh_proxy_mapping.get(node_name, SSH_PROXY_URL)


async def _resolve_proxy_url(proxy: str) -> str:
    """
    Resolve proxy parameter to proxy URL

    Args:
        proxy: Either "host" or a proxy_id from registry

    Returns:
        Proxy URL (e.g., "http://192.168.1.20:8022" or "http://localhost:5004")

    Raises:
        ValueError: If proxy_id not found in registry
    """
    # Host proxy is default
    if proxy == "host":
        return SSH_PROXY_URL

    # Look up lab proxy from registry
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{SSH_PROXY_URL}/proxy/registry")

            if response.status_code == 200:
                data = response.json()
                proxies = data.get("proxies", [])

                # Find proxy by proxy_id
                for p in proxies:
                    if p.get("proxy_id") == proxy:
                        proxy_url = p.get("url")

                        # Fix localhost URLs - replace with GNS3 host IP
                        # Registry returns "http://localhost:5004" but from MCP server perspective
                        # we need "http://192.168.1.20:5004" (GNS3 host IP)
                        if proxy_url.startswith("http://localhost:"):
                            port = proxy_url.split(":")[-1]
                            proxy_url = f"http://{_gns3_host}:{port}"

                        return proxy_url

                # Proxy not found
                available_ids = [p.get("proxy_id") for p in proxies]
                raise ValueError(
                    f"Proxy '{proxy}' not found in registry. "
                    f"Available proxies: {available_ids}. "
                    f"Use gns3://proxy/registry resource to list all proxies."
                )
            else:
                raise ValueError(f"Failed to fetch proxy registry: HTTP {response.status_code}")

        except httpx.RequestError as e:
            raise ValueError(f"Failed to connect to proxy registry: {e}")


# ============================================================================
# Local Execution (v0.28.0)
# ============================================================================

async def execute_local_command(
    proxy_url: str,
    command: str | List[str],
    timeout: float = 30.0
) -> str:
    """
    Execute command(s) locally on SSH proxy container

    Args:
        proxy_url: SSH proxy URL
        command: Command string or list of commands
        timeout: Execution timeout in seconds

    Returns:
        JSON with success, output, exit_code, execution_time
    """
    async with httpx.AsyncClient(timeout=timeout + 10) as client:
        try:
            response = await client.post(
                f"{proxy_url}/local/execute",
                json={
                    "command": command,
                    "timeout": int(timeout),
                    "working_dir": "/opt/gns3-ssh-proxy",
                    "shell": True
                }
            )

            if response.status_code == 200:
                return json.dumps(response.json(), indent=2)
            else:
                error_data = response.json()
                return json.dumps({
                    "error": "Local execution failed",
                    "details": error_data.get("detail", str(error_data))
                }, indent=2)

        except Exception as e:
            return json.dumps({
                "error": "Local execution failed",
                "details": str(e),
                "suggestion": "Ensure SSH proxy service supports local execution (v0.2.2+)"
            }, indent=2)


# ============================================================================
# Session Management
# ============================================================================

async def configure_ssh_impl(
    app: "AppContext",
    node_name: str,
    device_dict: Dict,
    persist: bool = True,
    force: bool = False,
    proxy: str = "host",
    session_timeout: int = 14400
) -> str:
    """
    Configure SSH session for network device

    Multi-Proxy Support (v0.26.0):
    - Proxy routing: Use 'proxy' parameter to route through specific proxy
    - Default: proxy="host" routes through main proxy on GNS3 host:8022
    - Lab proxy: proxy="<proxy_id>" routes through discovered lab proxy
    - Discovery: Use gns3://proxy/registry resource to list available proxies

    Session Timeout (v0.27.0):
    - Default: 4 hours (14400 seconds)
    - Sessions auto-expire after timeout period of inactivity
    - Can be customized per session

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

    3. For isolated networks, use lab proxy:
       # First, discover lab proxies
       proxies = get_proxy_registry()  # gns3://proxy/registry

       # Then configure SSH through lab proxy
       configure_ssh('A-CLIENT', {
           'device_type': 'linux',
           'host': '10.199.0.20',
           'username': 'alpine',
           'password': 'alpine'
       }, proxy='3f3a56de-19d3-40c3-9806-76bee4fe96d4')  # A-PROXY proxy_id

    Args:
        node_name: Node identifier
        device_dict: Netmiko device configuration dict
        persist: Store credentials for reconnection
        force: Force recreation even if session exists (v0.1.6)
        proxy: Proxy to route through - "host" (default) or proxy_id from registry (v0.26.0)
        session_timeout: Session timeout in seconds (default: 4 hours = 14400) (v0.27.0)

    Returns:
        JSON with session_id, connected, device_type, proxy_url
    """
    # Resolve proxy URL from proxy parameter
    try:
        proxy_url = await _resolve_proxy_url(proxy)
    except ValueError as e:
        return json.dumps({
            "error": "Proxy resolution failed",
            "details": str(e),
            "suggestion": "Check gns3://proxy/registry for available proxies"
        }, indent=2)

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{proxy_url}/ssh/configure",
                json={
                    "node_name": node_name,
                    "device": device_dict,
                    "persist": persist,
                    "force_recreate": force,  # v0.1.6: Allow forced recreation
                    "session_timeout": session_timeout  # v0.27.0: Per-session timeout
                }
            )

            # Success - SSH connection established
            if response.status_code == 200:
                # Store proxy URL mapping for ssh_command routing (v0.26.0)
                app.ssh_proxy_mapping[node_name] = proxy_url

                # Add proxy info to response
                result = response.json()
                result["proxy_url"] = proxy_url
                result["proxy"] = proxy

                return json.dumps(result, indent=2)

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
    wait_timeout: int = 30,
    ctx: Optional[Context] = None
) -> str:
    """
    Execute show command via SSH with adaptive async

    Local Execution (v0.28.0):
    - Use node_name="@" to execute command on SSH proxy container
    - No ssh_configure() needed for local execution
    - Access to diagnostic tools: ping, traceroute, dig, curl, ansible
    - Working directory: /opt/gns3-ssh-proxy

    Creates Job immediately, polls for wait_timeout seconds.
    Returns output if completes, else returns job_id for polling.

    Multi-Proxy Support (v0.26.0):
    - Routes command to the proxy used during ssh_configure()
    - Automatically uses correct proxy for isolated networks

    For long-running commands (e.g., 15-minute installations):
    - Set read_timeout=900 (or higher)
    - Set wait_timeout=0 to return job_id immediately
    - Poll with: ssh_get_job_status(job_id)

    For interactive prompts:
    - Use expect_string parameter
    - Example: expect_string=r"Delete filename.*?"

    Args:
        node_name: Node identifier (or "@" for local execution)
        command: Command to execute
        expect_string: Regex pattern to wait for (overrides prompt detection)
        read_timeout: Max time to wait for output (seconds)
        wait_timeout: Time to poll before returning job_id (seconds)

    Returns:
        JSON with completed, job_id, output, execution_time
    """
    # Local execution mode (v0.28.0)
    if node_name == "@":
        return await execute_local_command(SSH_PROXY_URL, command, read_timeout)

    # Get proxy URL for this node (v0.26.0)
    proxy_url = _get_proxy_url_for_node(app, node_name)

    # Progress notification for long commands (v0.39.0)
    if ctx and wait_timeout > 10:
        await ctx.report_progress(
            progress=0,
            total=wait_timeout,
            message=f"Executing SSH command (timeout: {wait_timeout}s)..."
        )

    async with httpx.AsyncClient(timeout=read_timeout + wait_timeout + 10) as client:
        try:
            response = await client.post(
                f"{proxy_url}/ssh/send_command",
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
                result = response.json()
                # Progress notification for completion (v0.39.0)
                if ctx and wait_timeout > 10:
                    await ctx.report_progress(
                        progress=wait_timeout,
                        total=wait_timeout,
                        message="SSH command completed"
                    )
                return json.dumps(result, indent=2)
            else:
                error_data = response.json()
                # Progress notification for error (v0.39.0)
                if ctx and wait_timeout > 10:
                    await ctx.report_progress(
                        progress=wait_timeout,
                        total=wait_timeout,
                        message="SSH command failed"
                    )
                return json.dumps({
                    "error": error_data.get("detail", {}).get("error", "Command failed"),
                    "details": error_data.get("detail", {}).get("details")
                }, indent=2)

        except Exception as e:
            # Progress notification for exception (v0.39.0)
            if ctx and wait_timeout > 10:
                await ctx.report_progress(
                    progress=wait_timeout,
                    total=wait_timeout,
                    message="SSH command failed (exception)"
                )
            return json.dumps({
                "error": "SSH command failed",
                "details": str(e)
            }, indent=2)


async def ssh_send_config_set_impl(
    app: "AppContext",
    node_name: str,
    config_commands: List[str],
    wait_timeout: int = 30,
    ctx: Optional[Context] = None
) -> str:
    """
    Send configuration commands via SSH

    Local Execution (v0.28.0):
    - Use node_name="@" to execute commands as bash script on SSH proxy container
    - Commands joined with "&&" for sequential execution
    - Working directory: /opt/gns3-ssh-proxy

    Creates Job immediately, uses adaptive async pattern.

    Multi-Proxy Support (v0.26.0):
    - Routes command to the proxy used during ssh_configure()
    - Automatically uses correct proxy for isolated networks

    Args:
        node_name: Node identifier (or "@" for local execution)
        config_commands: List of configuration commands (or bash commands for local)
        wait_timeout: Time to poll before returning job_id (seconds)

    Returns:
        JSON with completed, job_id, output, execution_time

    Example:
        ssh_send_config_set('R1', [
            'interface GigabitEthernet0/0',
            'ip address 192.168.1.1 255.255.255.0',
            'no shutdown'
        ])

        # Local execution example
        ssh_send_config_set('@', [
            'cd /opt/gns3-ssh-proxy',
            'python3 backup_configs.py',
            'ls -la backups/'
        ])
    """
    # Local execution mode (v0.28.0)
    if node_name == "@":
        return await execute_local_command(SSH_PROXY_URL, config_commands, wait_timeout)

    # Get proxy URL for this node (v0.26.0)
    proxy_url = _get_proxy_url_for_node(app, node_name)

    # Progress notification for long operations (v0.39.0)
    if ctx and wait_timeout > 10:
        await ctx.report_progress(
            progress=0,
            total=wait_timeout,
            message=f"Executing SSH config commands (timeout: {wait_timeout}s)..."
        )

    async with httpx.AsyncClient(timeout=wait_timeout + 60) as client:
        try:
            response = await client.post(
                f"{proxy_url}/ssh/send_config_set",
                json={
                    "node_name": node_name,
                    "config_commands": config_commands,
                    "wait_timeout": wait_timeout,
                    "exit_config_mode": True
                }
            )

            if response.status_code == 200:
                result = response.json()
                # Progress notification for completion (v0.39.0)
                if ctx and wait_timeout > 10:
                    await ctx.report_progress(
                        progress=wait_timeout,
                        total=wait_timeout,
                        message="SSH config commands completed"
                    )
                return json.dumps(result, indent=2)
            else:
                error_data = response.json()
                # Progress notification for error (v0.39.0)
                if ctx and wait_timeout > 10:
                    await ctx.report_progress(
                        progress=wait_timeout,
                        total=wait_timeout,
                        message="SSH config commands failed"
                    )
                return json.dumps({
                    "error": error_data.get("detail", {}).get("error", "Config failed"),
                    "details": error_data.get("detail", {}).get("details")
                }, indent=2)

        except Exception as e:
            # Progress notification for exception (v0.39.0)
            if ctx and wait_timeout > 10:
                await ctx.report_progress(
                    progress=wait_timeout,
                    total=wait_timeout,
                    message="SSH config commands failed (exception)"
                )
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
    # Get proxy URL for this node (v0.26.0)
    proxy_url = _get_proxy_url_for_node(app, node_name)

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"{proxy_url}/ssh/buffer/{node_name}",
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
    # Get proxy URL for this node (v0.26.0)
    proxy_url = _get_proxy_url_for_node(app, node_name)

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            params = {"limit": limit}
            if search:
                params["search"] = search

            response = await client.get(
                f"{proxy_url}/ssh/history/{node_name}",
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
    # Get proxy URL for this node (v0.26.0)
    proxy_url = _get_proxy_url_for_node(app, node_name)

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"{proxy_url}/ssh/history/{node_name}/{job_id}"
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
    # Get proxy URL for this node (v0.26.0)
    proxy_url = _get_proxy_url_for_node(app, node_name)

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"{proxy_url}/ssh/status/{node_name}"
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
    # Get proxy URL for this node (v0.26.0)
    proxy_url = _get_proxy_url_for_node(app, node_name)

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Use cleanup endpoint to disconnect specific node
            # Keep all nodes EXCEPT the one we want to disconnect
            response = await client.delete(
                f"{proxy_url}/ssh/session/{node_name}"
            )

            if response.status_code == 200:
                # Clean up proxy mapping (v0.26.0)
                app.ssh_proxy_mapping.pop(node_name, None)

                return json.dumps({
                    "status": "success",
                    "message": f"Disconnected SSH session for {node_name}"
                }, indent=2)
            elif response.status_code == 404:
                # Clean up proxy mapping even if session not found (v0.26.0)
                app.ssh_proxy_mapping.pop(node_name, None)

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


# ============================================================================
# Batch SSH Operations
# ============================================================================

async def ssh_batch_impl(app: "AppContext", operations: list[dict]) -> str:
    """Execute multiple SSH operations in batch with validation

    Two-phase execution:
    1. VALIDATE ALL operations (check required params, valid types)
    2. EXECUTE ALL operations (only if all valid, sequential execution)

    Args:
        app: Application context
        operations: List of operation dicts, each containing:
            {
                "type": "send_command" | "send_config_set" | "read_buffer",
                "node_name": "NodeName",
                ...other parameters specific to operation type
            }

            Operation types and their parameters:

            - "send_command": Execute show command
                node_name (str): Node name
                command (str): Command to execute
                expect_string (str, optional): Regex pattern to wait for
                read_timeout (float, optional): Max time to wait (default: 30.0)
                wait_timeout (int, optional): Polling timeout (default: 30)
                strip_prompt (bool, optional): Remove trailing prompt (default: True)
                strip_command (bool, optional): Remove command echo (default: True)
                proxy (str, optional): Proxy ID (default: "host")

            - "send_config_set": Send configuration commands
                node_name (str): Node name
                config_commands (list): List of configuration commands
                wait_timeout (int, optional): Polling timeout (default: 30)
                exit_config_mode (bool, optional): Exit config mode (default: True)
                proxy (str, optional): Proxy ID (default: "host")

            - "read_buffer": Read SSH buffer with optional grep
                node_name (str): Node name
                mode (str, optional): "diff" (default), "last_page", "num_pages", "all"
                pages (int, optional): Number of pages (only with mode="num_pages")
                pattern (str, optional): Grep regex pattern
                case_insensitive (bool, optional): Case insensitive grep
                invert (bool, optional): Invert grep match
                before (int, optional): Context lines before match
                after (int, optional): Context lines after match
                context (int, optional): Context lines before AND after
                proxy (str, optional): Proxy ID (default: "host")

    Returns:
        JSON with execution results:
        {
            "completed": [0, 1, 2],  // Indices of successful operations
            "failed": [3],  // Indices of failed operations
            "results": [
                {
                    "operation_index": 0,
                    "success": true,
                    "operation_type": "send_command",
                    "node_name": "R1",
                    "result": {...}  // Operation-specific result
                },
                ...
            ],
            "total_operations": 4,
            "execution_time": 5.3
        }

    Examples:
        # Multiple commands on one node:
        ssh_batch([
            {"type": "send_command", "node_name": "R1", "command": "show version"},
            {"type": "send_command", "node_name": "R1", "command": "show ip route"}
        ])

        # Same command on multiple nodes:
        ssh_batch([
            {"type": "send_command", "node_name": "R1", "command": "show ip int brief"},
            {"type": "send_command", "node_name": "R2", "command": "show ip int brief"},
            {"type": "send_command", "node_name": "R3", "command": "show ip int brief"}
        ])

        # Configuration commands:
        ssh_batch([
            {
                "type": "send_config_set",
                "node_name": "R1",
                "config_commands": [
                    "interface GigabitEthernet0/0",
                    "ip address 10.1.1.1 255.255.255.0",
                    "no shutdown"
                ]
            }
        ])
    """
    import time
    start_time = time.time()

    # Validation: Check all operations first
    VALID_TYPES = {"send_command", "send_config_set", "read_buffer"}

    for idx, op in enumerate(operations):
        # Check required fields
        if "type" not in op:
            return validation_error(
                parameter="operations",
                details=f"Operation {idx} missing required field 'type'",
                valid_values=list(VALID_TYPES)
            )

        if op["type"] not in VALID_TYPES:
            return validation_error(
                parameter=f"operations[{idx}].type",
                details=f"Invalid operation type: {op['type']}",
                valid_values=list(VALID_TYPES)
            )

        if "node_name" not in op:
            return create_error_response(
                error=f"Operation {idx} missing required field 'node_name'",
                error_code=ErrorCode.INVALID_PARAMETER.value,
                details="All operations must specify 'node_name'",
                suggested_action="Add 'node_name' field to operation",
                context={"operation_index": idx, "operation": op}
            )

        # Type-specific validation
        op_type = op["type"]
        node_name = op["node_name"]

        if op_type == "send_command":
            if "command" not in op:
                return create_error_response(
                    error=f"Operation {idx} (type='send_command') missing required parameter 'command'",
                    error_code=ErrorCode.INVALID_PARAMETER.value,
                    details="send_command operations require 'command' parameter",
                    suggested_action="Add 'command' field to operation",
                    context={"operation_index": idx, "node_name": node_name}
                )

        elif op_type == "send_config_set":
            if "config_commands" not in op:
                return create_error_response(
                    error=f"Operation {idx} (type='send_config_set') missing required parameter 'config_commands'",
                    error_code=ErrorCode.INVALID_PARAMETER.value,
                    details="send_config_set operations require 'config_commands' parameter (list of strings)",
                    suggested_action="Add 'config_commands' field to operation",
                    context={"operation_index": idx, "node_name": node_name}
                )
            if not isinstance(op["config_commands"], list):
                return create_error_response(
                    error=f"Operation {idx} (type='send_config_set') 'config_commands' must be a list",
                    error_code=ErrorCode.INVALID_PARAMETER.value,
                    details=f"Expected list, got {type(op['config_commands']).__name__}",
                    suggested_action="Provide config_commands as a list of strings",
                    context={"operation_index": idx, "node_name": node_name}
                )

    # Validation passed - execute all operations sequentially
    results = []
    completed_indices = []
    failed_indices = []

    for idx, op in enumerate(operations):
        op_type = op["type"]
        node_name = op["node_name"]

        try:
            # Execute operation based on type
            if op_type == "send_command":
                result = await ssh_send_command_impl(
                    app,
                    node_name,
                    op["command"],
                    op.get("expect_string"),
                    op.get("read_timeout", 30.0),
                    op.get("wait_timeout", 30),
                    op.get("strip_prompt", True),
                    op.get("strip_command", True),
                    op.get("proxy", "host")
                )

            elif op_type == "send_config_set":
                result = await ssh_send_config_set_impl(
                    app,
                    node_name,
                    op["config_commands"],
                    op.get("wait_timeout", 30),
                    op.get("exit_config_mode", True),
                    op.get("proxy", "host")
                )

            elif op_type == "read_buffer":
                result = await ssh_read_buffer_impl(
                    app,
                    node_name,
                    op.get("mode", "diff"),
                    op.get("pages", 1),
                    op.get("pattern"),
                    op.get("case_insensitive", False),
                    op.get("invert", False),
                    op.get("before", 0),
                    op.get("after", 0),
                    op.get("context", 0),
                    op.get("proxy", "host")
                )

            # Operation succeeded
            results.append({
                "operation_index": idx,
                "success": True,
                "operation_type": op_type,
                "node_name": node_name,
                "result": json.loads(result) if isinstance(result, str) else result
            })
            completed_indices.append(idx)

        except Exception as e:
            # Operation failed
            results.append({
                "operation_index": idx,
                "success": False,
                "operation_type": op_type,
                "node_name": node_name,
                "error": str(e)
            })
            failed_indices.append(idx)

    execution_time = time.time() - start_time

    return json.dumps({
        "completed": completed_indices,
        "failed": failed_indices,
        "results": results,
        "total_operations": len(operations),
        "execution_time": round(execution_time, 2)
    }, indent=2)
