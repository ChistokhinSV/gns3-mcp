"""
SSH Proxy Service - FastAPI Application

Provides REST API for SSH automation using Netmiko with dual storage:
- Continuous buffer (real-time stream)
- Command history (per-command audit trail)

Port: 8022 (SSH-like mnemonic)
"""

__version__ = "0.4.0"

import base64
import logging
import os
import subprocess
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from .models import (
    BridgeInfo,
    BufferResponse,
    CleanupRequest,
    CleanupResponse,
    CommandResponse,
    ConfigureSSHRequest,
    ConfigureSSHResponse,
    ErrorResponse,
    HistoryResponse,
    HTTPClientRequest,
    HTTPClientResponse,
    HTTPProxyDevice,
    HTTPProxyRequest,
    HTTPProxyResponse,
    Job,
    LocalExecuteRequest,
    LocalExecuteResponse,
    ReadBufferRequest,
    SendCommandRequest,
    SendConfigSetRequest,
    SessionStatusResponse,
    SSHConnectionError,
    TFTPFile,
    TFTPRequest,
    TFTPResponse,
    TopologyInfo,
    WidgetInfo,
    WidgetRequest,
    WidgetResponse,
)
from .session_manager import SSHSessionManager
from .docker_discovery import DockerProxyDiscovery
from .widget_manager import WidgetManager

# ============================================================================
# Logging Configuration
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(name)s - %(message)s',
    datefmt='%H:%M:%S %d.%m.%Y'
)
logger = logging.getLogger(__name__)

# ============================================================================
# Application Lifecycle
# ============================================================================

session_manager: Optional[SSHSessionManager] = None
proxy_discovery: Optional[DockerProxyDiscovery] = None
widget_manager: Optional[WidgetManager] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup resources"""
    global session_manager, proxy_discovery, widget_manager

    logger.info("SSH Proxy Service starting...")
    session_manager = SSHSessionManager()

    # Initialize proxy discovery (requires Docker socket and GNS3 credentials)
    gns3_host = os.getenv("GNS3_HOST", "localhost")
    gns3_port = int(os.getenv("GNS3_PORT", "80"))
    gns3_user = os.getenv("GNS3_USERNAME", "admin")
    gns3_pass = os.getenv("GNS3_PASSWORD", "")

    proxy_discovery = DockerProxyDiscovery(
        gns3_host=gns3_host,
        gns3_port=gns3_port,
        gns3_username=gns3_user,
        gns3_password=gns3_pass
    )

    # Initialize widget manager (v0.4.0)
    widget_manager = WidgetManager(
        gns3_host=gns3_host,
        gns3_port=gns3_port,
        gns3_username=gns3_user,
        gns3_password=gns3_pass,
        proxy_id=os.getenv("PROXY_ID", "main")
    )
    try:
        await widget_manager.initialize()
        logger.info("Widget manager initialized")
    except Exception as e:
        logger.warning(f"Widget manager init failed (non-fatal): {e}")

    logger.info(f"SSH Proxy Service ready on port {os.getenv('API_PORT', 8022)}")

    yield

    # Cleanup on shutdown
    logger.info("SSH Proxy Service shutting down...")

    # Shutdown widget manager first (deletes widgets from GNS3)
    if widget_manager:
        try:
            await widget_manager.shutdown()
        except Exception as e:
            logger.warning(f"Widget manager shutdown failed: {e}")

    if session_manager:
        # Close all sessions
        await session_manager.cleanup_sessions(keep_nodes=[], clean_all=True)
    if proxy_discovery:
        proxy_discovery.close()
    logger.info("SSH Proxy Service stopped")


# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(
    title="GNS3 SSH Proxy",
    description="SSH automation proxy for GNS3 network labs with Netmiko, TFTP, and HTTP reverse proxy",
    version=__version__,
    lifespan=lifespan
)


# ============================================================================
# Endpoints
# ============================================================================

@app.get("/health")
async def health_check():
    """
    Health check endpoint

    Returns service health status, name, and version.
    """
    return {
        "status": "healthy",
        "service": "gns3-ssh-proxy",
        "version": app.version
    }


@app.get("/version")
async def get_version():
    """
    Get service version

    Returns the SSH proxy service version number.
    Useful for tracking deployed versions and compatibility checking.

    Returns:
        Version information (version string and service name)
    """
    return {
        "version": app.version,
        "service": "gns3-ssh-proxy",
        "features": ["ssh_automation", "proxy_discovery"]
    }


@app.post("/ssh/configure", response_model=ConfigureSSHResponse)
async def configure_ssh(request: ConfigureSSHRequest):
    """
    Create or recreate SSH session

    If session exists for node_name, it will be dropped and recreated.
    This handles IP address changes when project changes.

    Workflow:
    1. Use console tools to configure SSH access first:
       - send_console('NodeName', 'configure terminal\\n')
       - send_console('NodeName', 'username admin privilege 15 secret password\\n')
       - send_console('NodeName', 'crypto key generate rsa modulus 2048\\n')
       - send_console('NodeName', 'ip ssh version 2\\n')
    2. Then call this endpoint to establish SSH session

    Returns:
        Session info if successful

    Raises:
        HTTPException 400: SSH connection failed (with detailed error)
    """
    try:
        session_id, error = await session_manager.create_session(
            node_name=request.node_name,
            device_config=request.device,
            persist=request.persist,
            force_recreate=request.force_recreate,
            session_timeout=request.session_timeout  # Per-session timeout (v0.27.0)
        )

        if error:
            # SSH connection failed
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse(
                    error=error.error,
                    details=error.details,
                    ssh_connection_error=error
                ).model_dump()
            )

        # Success
        return ConfigureSSHResponse(
            session_id=session_id,
            node_name=request.node_name,
            connected=True,
            device_type=request.device.device_type,
            host=request.device.host,
            version=app.version
        )

    except Exception as e:
        logger.error(f"Error in configure_ssh: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(error="Internal server error", details=str(e)).model_dump()
        )


@app.post("/ssh/send_command", response_model=CommandResponse)
async def send_command(request: SendCommandRequest):
    """
    Execute show command with adaptive async

    Creates Job immediately, polls for wait_timeout seconds.
    Returns output if completes, else returns job_id for polling.

    For long-running commands (e.g., 15-minute installations):
    - Set read_timeout=900 (or higher)
    - Set wait_timeout=0 to return job_id immediately
    - Poll GET /ssh/job/{job_id} for status

    Returns:
        CommandResponse with completed=True/False, job_id, output

    Raises:
        HTTPException 404: No session for node_name
    """
    if not session_manager.has_session(request.node_name):
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error=f"No SSH session for {request.node_name}",
                details="Call POST /ssh/configure first"
            ).model_dump()
        )

    try:
        result = await session_manager.send_command_adaptive(
            node_name=request.node_name,
            command=request.command,
            wait_timeout=request.wait_timeout,
            expect_string=request.expect_string,
            read_timeout=request.read_timeout,
            strip_prompt=request.strip_prompt,
            strip_command=request.strip_command
        )

        return CommandResponse(**result)

    except Exception as e:
        logger.error(f"Error in send_command: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(error="Command execution failed", details=str(e)).model_dump()
        )


@app.post("/ssh/send_config_set", response_model=CommandResponse)
async def send_config_set(request: SendConfigSetRequest):
    """
    Send configuration commands

    Creates Job immediately, uses adaptive async pattern.

    Returns:
        CommandResponse with job_id and output
    """
    if not session_manager.has_session(request.node_name):
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error=f"No SSH session for {request.node_name}",
                details="Call POST /ssh/configure first"
            ).model_dump()
        )

    try:
        result = await session_manager.send_config_set_adaptive(
            node_name=request.node_name,
            config_commands=request.config_commands,
            wait_timeout=request.wait_timeout,
            exit_config_mode=request.exit_config_mode
        )

        return CommandResponse(**result)

    except Exception as e:
        logger.error(f"Error in send_config_set: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(error="Config commands failed", details=str(e)).model_dump()
        )


@app.post("/ssh/read_buffer", response_model=BufferResponse)
async def read_buffer(request: ReadBufferRequest):
    """
    Read continuous buffer with optional grep filtering

    Modes:
    - diff: New output since last read (default)
    - last_page: Last ~25 lines
    - num_pages: Last N pages (~25 lines per page)
    - all: Entire buffer (WARNING: May be very large!)

    Grep Parameters (optional):
    - pattern: Regex pattern to filter output
    - case_insensitive: Ignore case (grep -i)
    - invert: Return non-matching lines (grep -v)
    - before/after/context: Context lines (grep -B/-A/-C)

    Returns:
        BufferResponse with output (filtered if pattern provided) and buffer_size
    """
    if not session_manager.has_session(request.node_name):
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error=f"No SSH session for {request.node_name}",
                details="Call POST /ssh/configure first"
            ).model_dump()
        )

    # Validate pages parameter
    if request.pages != 1 and request.mode != "num_pages":
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(
                error="Invalid parameters",
                details="'pages' parameter can only be used with mode='num_pages'"
            ).model_dump()
        )

    try:
        output = session_manager.get_buffer(
            request.node_name,
            request.mode,
            request.pages,
            pattern=request.pattern,
            case_insensitive=request.case_insensitive,
            invert=request.invert,
            before=request.before,
            after=request.after,
            context=request.context
        )
        session_info = session_manager.get_session_info(request.node_name)

        return BufferResponse(
            output=output,
            buffer_size=len(session_info.buffer)
        )

    except Exception as e:
        logger.error(f"Error in read_buffer: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(error="Buffer read failed", details=str(e)).model_dump()
        )


@app.get("/ssh/history/{node_name}", response_model=HistoryResponse)
async def get_history(
    node_name: str,
    limit: int = Query(default=50, ge=1, le=1000),
    search: Optional[str] = Query(default=None)
):
    """
    List command history in execution order

    Returns:
        HistoryResponse with job summaries

    Query Parameters:
    - limit: Max number of jobs to return (default: 50, max: 1000)
    - search: Filter by command text (case-insensitive)
    """
    if not session_manager.has_session(node_name):
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error=f"No SSH session for {node_name}",
                details="Call POST /ssh/configure first"
            ).model_dump()
        )

    try:
        jobs = session_manager.get_history(node_name, limit, search)
        session_info = session_manager.get_session_info(node_name)

        return HistoryResponse(
            node_name=node_name,
            total_commands=len(session_info.jobs),
            jobs=jobs
        )

    except Exception as e:
        logger.error(f"Error in get_history: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(error="History retrieval failed", details=str(e)).model_dump()
        )


@app.get("/ssh/history/{node_name}/{job_id}", response_model=Job)
async def get_job_output(node_name: str, job_id: str):
    """
    Get specific command's full output

    Returns:
        Job with full output and metadata
    """
    if not session_manager.has_session(node_name):
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error=f"No SSH session for {node_name}",
                details="Call POST /ssh/configure first"
            ).model_dump()
        )

    try:
        job = session_manager.get_job(node_name, job_id)

        if not job:
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse(
                    error=f"Job {job_id} not found",
                    details=f"No job with ID {job_id} in session {node_name}"
                ).model_dump()
            )

        return job

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_job_output: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(error="Job retrieval failed", details=str(e)).model_dump()
        )


@app.get("/ssh/status/{node_name}", response_model=SessionStatusResponse)
async def get_status(node_name: str):
    """
    Check SSH session status

    Returns:
        SessionStatusResponse with connection info
    """
    if not session_manager.has_session(node_name):
        # Return disconnected status
        return SessionStatusResponse(
            connected=False,
            node_name=node_name,
            session_id=None,
            device_type=None,
            host=None,
            buffer_size=0,
            total_commands=0,
            created_at=None,
            persist=False
        )

    try:
        session_info = session_manager.get_session_info(node_name)

        return SessionStatusResponse(
            connected=True,
            node_name=node_name,
            session_id=session_info.session_id,
            device_type=session_info.device_config.device_type,
            host=session_info.device_config.host,
            buffer_size=len(session_info.buffer),
            total_commands=len(session_info.jobs),
            created_at=session_info.created_at,
            persist=session_info.persist
        )

    except Exception as e:
        logger.error(f"Error in get_status: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(error="Status check failed", details=str(e)).model_dump()
        )


@app.get("/ssh/job/{job_id}", response_model=Job)
async def get_job_status(job_id: str):
    """
    Check job status by job_id (for async polling)

    Searches all sessions for the job.

    Returns:
        Job with status and output
    """
    # Search all sessions for job
    for node_name, session_info in session_manager.sessions.items():
        job = next((j for j in session_info.jobs if j.job_id == job_id), None)
        if job:
            return job

    # Job not found
    raise HTTPException(
        status_code=404,
        detail=ErrorResponse(
            error=f"Job {job_id} not found",
            details="Job may have been cleaned up or doesn't exist"
        ).model_dump()
    )


@app.post("/ssh/cleanup", response_model=CleanupResponse)
async def cleanup_sessions(request: CleanupRequest):
    """
    Clean orphaned/all SSH sessions

    Useful when project changes (different IP addresses on same node names).

    Returns:
        CleanupResponse with cleaned and kept nodes
    """
    try:
        cleaned, kept = await session_manager.cleanup_sessions(
            keep_nodes=request.keep_nodes,
            clean_all=request.clean_all
        )

        return CleanupResponse(
            cleaned=cleaned,
            kept=kept
        )

    except Exception as e:
        logger.error(f"Error in cleanup_sessions: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(error="Cleanup failed", details=str(e)).model_dump()
        )


# ============================================================================
# Proxy Discovery Endpoints
# ============================================================================

@app.get("/proxy/registry")
async def get_proxy_registry():
    """
    Get registry of all discovered lab proxies with TFTP and HTTP proxy status (v0.3.0)

    Discovers lab proxies via Docker API (only works on main proxy with
    /var/run/docker.sock mounted). Includes TFTP server and HTTP reverse proxy information.

    Returns:
        JSON object with:
        - available: bool - Docker API availability
        - proxies: list - Discovered lab proxies
        - count: int - Number of proxies found
        - tftp_enabled: bool - TFTP server status (v0.3.0)
        - tftp_port: int - TFTP server port (69)
        - tftp_root: str - TFTP directory path
        - http_proxy_enabled: bool - HTTP reverse proxy status (v0.3.0)
        - http_proxy_devices: list - Registered devices for reverse proxy

    Example response:
        {
            "available": true,
            "proxies": [
                {
                    "proxy_id": "7217fd86-302f-460b-b764-5b96c9310f67",
                    "hostname": "A-PROXY",
                    "project_id": "2de2a4cc-0418-4280-880b-e283051f7d9d",
                    "url": "http://192.168.1.20:5005",
                    "console_port": 5005,
                    "image": "chistokhinsv/gns3-ssh-proxy:latest",
                    "discovered_via": "docker_api"
                }
            ],
            "count": 1,
            "tftp_enabled": true,
            "tftp_port": 69,
            "tftp_root": "/opt/gns3-ssh-proxy/tftp",
            "http_proxy_enabled": true,
            "http_proxy_devices": [...]
        }

    Notes:
        - Only works on main proxy (with Docker socket mounted)
        - Lab proxies will return {"available": false, "proxies": [], "count": 0}
        - Proxy IDs are persistent GNS3 node UUIDs (survive container recreation)
    """
    if not proxy_discovery or not proxy_discovery.docker_available:
        return {
            "available": False,
            "proxies": [],
            "count": 0,
            "message": "Docker API not available. Mount /var/run/docker.sock to enable discovery."
        }

    try:
        proxies = await proxy_discovery.discover_proxies()

        # Check TFTP server status (v0.3.0)
        tftp_enabled = False
        try:
            result = subprocess.run(
                ["pgrep", "-f", "in.tftpd"],
                capture_output=True,
                timeout=2
            )
            tftp_enabled = result.returncode == 0
        except Exception:
            pass

        # Check nginx reverse proxy status (v0.3.0)
        http_proxy_enabled = False
        try:
            result = subprocess.run(
                ["pgrep", "-f", "nginx"],
                capture_output=True,
                timeout=2
            )
            http_proxy_enabled = result.returncode == 0
        except Exception:
            pass

        return {
            "available": True,
            "proxies": [p.to_dict() for p in proxies],
            "count": len(proxies),
            "tftp_enabled": tftp_enabled,
            "tftp_port": 69,
            "tftp_root": str(TFTP_ROOT),
            "http_proxy_enabled": http_proxy_enabled,
            "http_proxy_devices": list(http_proxy_devices.values())
        }

    except Exception as e:
        logger.error(f"Error discovering proxies: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(error="Proxy discovery failed", details=str(e)).model_dump()
        )


# ============================================================================
# Local Execution (v0.2.2)
# ============================================================================

@app.post("/local/execute", response_model=LocalExecuteResponse)
async def local_execute(request: LocalExecuteRequest):
    """
    Execute command(s) locally on SSH proxy container

    Use for:
    - Ansible playbooks from /opt/gns3-ssh-proxy mount
    - Network diagnostics (ping, traceroute, dig)
    - Custom scripts and automation

    Commands execute in /opt/gns3-ssh-proxy by default.

    Args:
        request: LocalExecuteRequest with command, timeout, working_dir

    Returns:
        LocalExecuteResponse with success, output, exit_code, execution_time

    Examples:
        # Single command
        POST /local/execute {"command": "ping -c 3 8.8.8.8"}

        # Multiple commands (list = shell script)
        POST /local/execute {"command": ["cd /opt/gns3-ssh-proxy", "ls -la"]}

        # Ansible playbook
        POST /local/execute {"command": "ansible-playbook /opt/gns3-ssh-proxy/backup.yml"}
    """
    start_time = time.time()

    try:
        # Handle list of commands - join with && for sequential execution
        if isinstance(request.command, list):
            command_str = " && ".join(request.command)
        else:
            command_str = request.command

        logger.info(f"[LOCAL] Executing: {command_str[:100]}...")

        # Execute command with subprocess
        result = subprocess.run(
            command_str,
            shell=request.shell,
            cwd=request.working_dir,
            capture_output=True,
            text=True,
            timeout=request.timeout
        )

        execution_time = time.time() - start_time

        # Combine stdout and stderr
        output = result.stdout
        if result.stderr:
            output += "\n" + result.stderr

        success = (result.returncode == 0)
        error_msg = None if success else f"Command exited with code {result.returncode}"

        logger.info(f"[LOCAL] Completed in {execution_time:.2f}s, exit_code={result.returncode}")

        return LocalExecuteResponse(
            success=success,
            output=output.strip() if output else "",
            exit_code=result.returncode,
            execution_time=round(execution_time, 3),
            error=error_msg
        )

    except subprocess.TimeoutExpired:
        execution_time = time.time() - start_time
        logger.error(f"[LOCAL] Command timed out after {request.timeout}s")
        return LocalExecuteResponse(
            success=False,
            output="",
            exit_code=-1,
            execution_time=round(execution_time, 3),
            error=f"Command timed out after {request.timeout} seconds"
        )

    except Exception as e:
        execution_time = time.time() - start_time
        logger.error(f"[LOCAL] Command failed: {e}")
        return LocalExecuteResponse(
            success=False,
            output="",
            exit_code=-1,
            execution_time=round(execution_time, 3),
            error=f"Command execution failed: {str(e)}"
        )


# ============================================================================
# TFTP Management (v0.3.0)
# ============================================================================

TFTP_ROOT = Path("/opt/gns3-ssh-proxy/tftp")

@app.post("/tftp", response_model=TFTPResponse)
async def tftp_management(request: TFTPRequest):
    """
    Manage TFTP server files (CRUD-style with action parameter)

    TFTP server runs on port 69/udp with root directory /opt/gns3-ssh-proxy/tftp.
    Devices can upload/download firmware, configs, backups.

    Actions:
        - list: List files in TFTP directory
        - upload: Upload file to TFTP (content is base64 encoded)
        - download: Download file from TFTP (returns base64 encoded content)
        - delete: Delete file from TFTP
        - status: TFTP server status

    Args:
        request: TFTPRequest with action and optional filename/content

    Returns:
        TFTPResponse with success status, files list, or content

    Examples:
        # List files
        POST /tftp {"action": "list"}

        # Upload file
        POST /tftp {"action": "upload", "filename": "config.txt", "content": "Y29uZmlnIGRhdGE="}

        # Download file
        POST /tftp {"action": "download", "filename": "config.txt"}

        # Delete file
        POST /tftp {"action": "delete", "filename": "old-firmware.bin"}
    """
    try:
        if request.action == "list":
            # List files in TFTP directory
            if not TFTP_ROOT.exists():
                TFTP_ROOT.mkdir(parents=True, exist_ok=True)

            files = []
            for item in TFTP_ROOT.iterdir():
                stat = item.stat()
                files.append(TFTPFile(
                    filename=item.name,
                    size=stat.st_size,
                    modified=datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                    is_dir=item.is_dir()
                ))

            return TFTPResponse(
                success=True,
                action="list",
                files=sorted(files, key=lambda f: f.filename)
            )

        elif request.action == "upload":
            if not request.filename or not request.content:
                raise HTTPException(status_code=400, detail="filename and content required for upload")

            # Decode base64 content and write to file
            try:
                file_data = base64.b64decode(request.content)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid base64 content: {e}")

            file_path = TFTP_ROOT / request.filename
            file_path.write_bytes(file_data)

            return TFTPResponse(
                success=True,
                action="upload",
                message=f"Uploaded {request.filename} ({len(file_data)} bytes)"
            )

        elif request.action == "download":
            if not request.filename:
                raise HTTPException(status_code=400, detail="filename required for download")

            file_path = TFTP_ROOT / request.filename
            if not file_path.exists():
                raise HTTPException(status_code=404, detail=f"File not found: {request.filename}")

            # Read file and encode as base64
            file_data = file_path.read_bytes()
            content_b64 = base64.b64encode(file_data).decode('utf-8')

            return TFTPResponse(
                success=True,
                action="download",
                content=content_b64,
                message=f"Downloaded {request.filename} ({len(file_data)} bytes)"
            )

        elif request.action == "delete":
            if not request.filename:
                raise HTTPException(status_code=400, detail="filename required for delete")

            file_path = TFTP_ROOT / request.filename
            if not file_path.exists():
                raise HTTPException(status_code=404, detail=f"File not found: {request.filename}")

            file_path.unlink()

            return TFTPResponse(
                success=True,
                action="delete",
                message=f"Deleted {request.filename}"
            )

        elif request.action == "status":
            # Check TFTP server status
            try:
                result = subprocess.run(
                    ["pgrep", "-f", "in.tftpd"],
                    capture_output=True,
                    timeout=5
                )
                running = result.returncode == 0

                return TFTPResponse(
                    success=True,
                    action="status",
                    message=f"TFTP server: {'running' if running else 'stopped'}"
                )
            except Exception as e:
                return TFTPResponse(
                    success=False,
                    action="status",
                    error=f"Failed to check TFTP status: {e}"
                )

        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {request.action}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[TFTP] Error in {request.action}: {e}")
        return TFTPResponse(
            success=False,
            action=request.action,
            error=str(e)
        )


# ============================================================================
# HTTP Client (v0.3.0)
# ============================================================================

@app.post("/http-client", response_model=HTTPClientResponse)
async def http_client(request: HTTPClientRequest):
    """
    Make HTTP/HTTPS requests to lab devices (CRUD-style with action parameter)

    Useful for checking device APIs, health endpoints, retrieving data.
    **Reverse HTTP/HTTPS proxy available** at http://proxy:8022/http-proxy/
    for external device web UI access without SSH tunnel.

    Actions:
        - get: Make HTTP GET request to device URL
        - status: Check if URL is reachable

    Args:
        request: HTTPClientRequest with action, url, timeout, verify_ssl, headers

    Returns:
        HTTPClientResponse with status_code, content, headers, or reachability

    Examples:
        # GET request
        POST /http-client {"action": "get", "url": "http://10.1.1.1/api/health"}

        # Check reachability
        POST /http-client {"action": "status", "url": "https://10.1.1.1:443"}

        # Custom headers
        POST /http-client {
            "action": "get",
            "url": "http://10.1.1.1/api/data",
            "headers": {"Authorization": "Bearer token123"}
        }
    """
    try:
        if request.action == "get":
            async with httpx.AsyncClient(verify=request.verify_ssl, timeout=request.timeout) as client:
                response = await client.get(request.url, headers=request.headers or {})

                return HTTPClientResponse(
                    success=True,
                    action="get",
                    status_code=response.status_code,
                    content=response.text,
                    headers=dict(response.headers)
                )

        elif request.action == "status":
            try:
                async with httpx.AsyncClient(verify=request.verify_ssl, timeout=request.timeout) as client:
                    response = await client.head(request.url, headers=request.headers or {})
                    reachable = 200 <= response.status_code < 500  # 4xx counts as reachable

                    return HTTPClientResponse(
                        success=True,
                        action="status",
                        reachable=reachable,
                        status_code=response.status_code
                    )
            except Exception:
                return HTTPClientResponse(
                    success=True,
                    action="status",
                    reachable=False
                )

        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {request.action}")

    except HTTPException:
        raise
    except httpx.TimeoutException:
        return HTTPClientResponse(
            success=False,
            action=request.action,
            error=f"Request timed out after {request.timeout}s"
        )
    except Exception as e:
        logger.error(f"[HTTP-CLIENT] Error in {request.action}: {e}")
        return HTTPClientResponse(
            success=False,
            action=request.action,
            error=str(e)
        )


# ============================================================================
# HTTP Reverse Proxy (v0.3.0)
# ============================================================================

# Simple in-memory device registry (would be persistent in production)
http_proxy_devices: dict = {}

@app.post("/http-proxy", response_model=HTTPProxyResponse)
async def http_proxy_management(request: HTTPProxyRequest):
    """
    Manage HTTP/HTTPS reverse proxy (CRUD-style with action parameter)

    Nginx reverse proxy exposes device web UIs through SSH proxy port 8023.
    Access devices at: http://proxy-host:8023/http-proxy/{device_ip}:{port}/path

    Actions:
        - register: Register device for proxying
        - unregister: Remove device from proxy
        - list: List registered devices
        - reload: Reload nginx configuration (automatic on register/unregister)

    Args:
        request: HTTPProxyRequest with action and device details

    Returns:
        HTTPProxyResponse with devices list or operation status

    Examples:
        # Register device
        POST /http-proxy {
            "action": "register",
            "device_name": "Router1",
            "device_ip": "10.1.1.1",
            "device_port": 443
        }

        # List devices
        POST /http-proxy {"action": "list"}

        # Unregister device
        POST /http-proxy {"action": "unregister", "device_name": "Router1"}

        # Then access: http://192.168.1.20:8023/http-proxy/10.1.1.1:443/
    """
    try:
        if request.action == "register":
            if not all([request.device_name, request.device_ip, request.device_port]):
                raise HTTPException(
                    status_code=400,
                    detail="device_name, device_ip, and device_port required for register"
                )

            # Get proxy host from environment or use localhost
            proxy_host = os.getenv("GNS3_HOST", "localhost")
            proxy_url = f"http://{proxy_host}:8023/http-proxy/{request.device_ip}:{request.device_port}/"

            http_proxy_devices[request.device_name] = {
                "device_name": request.device_name,
                "device_ip": request.device_ip,
                "device_port": request.device_port,
                "proxy_url": proxy_url
            }

            return HTTPProxyResponse(
                success=True,
                action="register",
                message=f"Registered {request.device_name} at {proxy_url}"
            )

        elif request.action == "unregister":
            if not request.device_name:
                raise HTTPException(status_code=400, detail="device_name required for unregister")

            if request.device_name in http_proxy_devices:
                del http_proxy_devices[request.device_name]
                return HTTPProxyResponse(
                    success=True,
                    action="unregister",
                    message=f"Unregistered {request.device_name}"
                )
            else:
                raise HTTPException(status_code=404, detail=f"Device not found: {request.device_name}")

        elif request.action == "list":
            devices = [HTTPProxyDevice(**d) for d in http_proxy_devices.values()]

            return HTTPProxyResponse(
                success=True,
                action="list",
                devices=devices
            )

        elif request.action == "reload":
            # Reload nginx configuration
            try:
                result = subprocess.run(
                    ["nginx", "-s", "reload"],
                    capture_output=True,
                    timeout=5
                )

                if result.returncode == 0:
                    return HTTPProxyResponse(
                        success=True,
                        action="reload",
                        message="Nginx configuration reloaded"
                    )
                else:
                    return HTTPProxyResponse(
                        success=False,
                        action="reload",
                        error=f"Nginx reload failed: {result.stderr.decode()}"
                    )
            except Exception as e:
                return HTTPProxyResponse(
                    success=False,
                    action="reload",
                    error=str(e)
                )

        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {request.action}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[HTTP-PROXY] Error in {request.action}: {e}")
        return HTTPProxyResponse(
            success=False,
            action=request.action,
            error=str(e)
        )


# ============================================================================
# Traffic Widget Endpoints (v0.4.0)
# ============================================================================

@app.post("/api/widgets", response_model=WidgetResponse)
async def manage_widgets(request: WidgetRequest):
    """
    Manage traffic graph widgets (CRUD-style with action parameter)

    Widgets display real-time traffic statistics as mini bar charts
    embedded in GNS3 topology via the Drawing API.

    Actions:
        - create: Create widget for a link (requires link_id, project_id)
        - delete: Delete widget by ID (requires widget_id)
        - list: List all widgets managed by this proxy
        - refresh: Force immediate update of all widgets

    Args:
        request: WidgetRequest with action and parameters

    Returns:
        WidgetResponse with widget info or operation status

    Examples:
        # Create widget for a link
        POST /api/widgets {
            "action": "create",
            "link_id": "abc-123",
            "project_id": "def-456"
        }

        # List widgets
        POST /api/widgets {"action": "list"}

        # Delete widget
        POST /api/widgets {"action": "delete", "widget_id": "widget-uuid"}

        # Force refresh
        POST /api/widgets {"action": "refresh"}
    """
    if not widget_manager:
        raise HTTPException(
            status_code=503,
            detail="Widget manager not initialized"
        )

    try:
        if request.action == "create":
            if not request.link_id or not request.project_id:
                raise HTTPException(
                    status_code=400,
                    detail="link_id and project_id required for create"
                )

            widget = await widget_manager.create_widget(
                link_id=request.link_id,
                project_id=request.project_id,
                x=request.x,
                y=request.y
            )

            return WidgetResponse(
                success=True,
                action="create",
                widget=widget,
                message=f"Created widget for link {request.link_id}"
            )

        elif request.action == "delete":
            if not request.widget_id:
                raise HTTPException(
                    status_code=400,
                    detail="widget_id required for delete"
                )

            widget = await widget_manager.delete_widget(request.widget_id)

            return WidgetResponse(
                success=True,
                action="delete",
                widget=widget,
                message=f"Deleted widget {request.widget_id}"
            )

        elif request.action == "list":
            widgets = widget_manager.list_widgets()

            return WidgetResponse(
                success=True,
                action="list",
                widgets=widgets,
                message=f"Found {len(widgets)} widgets"
            )

        elif request.action == "refresh":
            count = await widget_manager.refresh_widgets()

            return WidgetResponse(
                success=True,
                action="refresh",
                message=f"Refreshed {count} widgets"
            )

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown action: {request.action}"
            )

    except ValueError as e:
        return WidgetResponse(
            success=False,
            action=request.action,
            error=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[WIDGET] Error in {request.action}: {e}")
        return WidgetResponse(
            success=False,
            action=request.action,
            error=str(e)
        )


@app.get("/api/widgets", response_model=WidgetResponse)
async def get_widgets():
    """
    List all traffic widgets

    Returns:
        WidgetResponse with list of widgets
    """
    if not widget_manager:
        raise HTTPException(
            status_code=503,
            detail="Widget manager not initialized"
        )

    widgets = widget_manager.list_widgets()

    return WidgetResponse(
        success=True,
        action="list",
        widgets=widgets,
        message=f"Found {len(widgets)} widgets"
    )


@app.get("/api/widgets/{widget_id}")
async def get_widget(widget_id: str):
    """
    Get specific widget details

    Returns:
        WidgetInfo for the requested widget
    """
    if not widget_manager:
        raise HTTPException(
            status_code=503,
            detail="Widget manager not initialized"
        )

    widgets = widget_manager.list_widgets()
    widget = next((w for w in widgets if w.widget_id == widget_id), None)

    if not widget:
        raise HTTPException(
            status_code=404,
            detail=f"Widget {widget_id} not found"
        )

    return widget


@app.get("/api/bridges")
async def list_bridges():
    """
    List available Linux bridges with traffic statistics

    Returns:
        List of BridgeInfo with stats and widget status
    """
    if not widget_manager:
        raise HTTPException(
            status_code=503,
            detail="Widget manager not initialized"
        )

    bridges = widget_manager.list_bridges()

    return {
        "success": True,
        "bridges": [b.model_dump() for b in bridges],
        "count": len(bridges)
    }


@app.get("/api/topology/{project_id}", response_model=TopologyInfo)
async def get_topology(project_id: str):
    """
    Get project topology for web UI

    Returns nodes, links, and active widgets for rendering.

    Returns:
        TopologyInfo with nodes, links, and widgets
    """
    if not widget_manager:
        raise HTTPException(
            status_code=503,
            detail="Widget manager not initialized"
        )

    try:
        topology = await widget_manager.get_topology(project_id)
        return topology
    except Exception as e:
        logger.error(f"[TOPOLOGY] Error getting topology: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get topology: {e}"
        )


@app.get("/api/projects")
async def get_projects():
    """
    List GNS3 projects for web UI

    Returns:
        List of projects with id, name, status
    """
    if not widget_manager:
        raise HTTPException(
            status_code=503,
            detail="Widget manager not initialized"
        )

    try:
        projects = await widget_manager.get_projects()
        return {
            "success": True,
            "projects": projects,
            "count": len(projects)
        }
    except Exception as e:
        logger.error(f"[PROJECTS] Error listing projects: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list projects: {e}"
        )


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("API_PORT", 8022))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
