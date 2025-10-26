"""
SSH Proxy Service - FastAPI Application

Provides REST API for SSH automation using Netmiko with dual storage:
- Continuous buffer (real-time stream)
- Command history (per-command audit trail)

Port: 8022 (SSH-like mnemonic)
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from .models import (
    BufferResponse,
    CleanupRequest,
    CleanupResponse,
    CommandResponse,
    ConfigureSSHRequest,
    ConfigureSSHResponse,
    ErrorResponse,
    HistoryResponse,
    Job,
    ReadBufferRequest,
    SendCommandRequest,
    SendConfigSetRequest,
    SessionStatusResponse,
    SSHConnectionError
)
from .session_manager import SSHSessionManager
from .docker_discovery import DockerProxyDiscovery

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup resources"""
    global session_manager, proxy_discovery

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

    logger.info(f"SSH Proxy Service ready on port {os.getenv('API_PORT', 8022)}")

    yield

    # Cleanup on shutdown
    logger.info("SSH Proxy Service shutting down...")
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
    description="SSH automation proxy for GNS3 network labs with Netmiko and proxy discovery",
    version="0.2.0",
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
        "version": "0.2.0"
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
        "version": "0.2.0",
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
            force_recreate=request.force_recreate
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
    Get registry of all discovered lab proxies

    Discovers lab proxies via Docker API (only works on main proxy with
    /var/run/docker.sock mounted).

    Returns:
        JSON object with:
        - available: bool - Docker API availability
        - proxies: list - Discovered lab proxies
        - count: int - Number of proxies found

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
            "count": 1
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

        return {
            "available": True,
            "proxies": [p.to_dict() for p in proxies],
            "count": len(proxies)
        }

    except Exception as e:
        logger.error(f"Error discovering proxies: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(error="Proxy discovery failed", details=str(e)).model_dump()
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
