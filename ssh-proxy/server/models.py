"""
Pydantic models for SSH proxy service

Shared data models for API requests/responses and internal state management.
"""

from datetime import datetime
from typing import Dict, List, Literal, Optional, Any
from pydantic import BaseModel, Field


# ============================================================================
# SSH Device Configuration
# ============================================================================

class SSHDeviceConfig(BaseModel):
    """Netmiko device configuration dictionary"""
    device_type: str = Field(
        ...,
        description="Netmiko device type (cisco_ios, juniper, arista_eos, etc.)"
    )
    host: str = Field(..., description="Device IP address or hostname")
    username: str = Field(..., description="SSH username")
    password: str = Field(..., description="SSH password")
    port: int = Field(default=22, description="SSH port")
    secret: str = Field(default="", description="Enable secret (optional)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "device_type": "cisco_ios",
                "host": "10.10.10.10",
                "username": "admin",
                "password": "cisco123",
                "port": 22,
                "secret": ""
            }
        }
    }


# ============================================================================
# Job Models (Command History)
# ============================================================================

class Job(BaseModel):
    """Command execution job with full output and metadata"""
    job_id: str = Field(..., description="Unique job identifier (UUID)")
    node_name: str = Field(..., description="Node/device name")
    command: str = Field(..., description="Command that was executed")
    output: str = Field(default="", description="Full command output")
    status: Literal["running", "completed", "failed"] = Field(
        ...,
        description="Job execution status"
    )
    error: Optional[str] = Field(default=None, description="Error message if failed")
    started_at: datetime = Field(..., description="Job start timestamp (UTC)")
    completed_at: Optional[datetime] = Field(
        default=None,
        description="Job completion timestamp (UTC)"
    )
    execution_time: Optional[float] = Field(
        default=None,
        description="Execution time in seconds"
    )
    sequence_number: int = Field(..., description="Execution order (0, 1, 2, ...)")


class JobSummary(BaseModel):
    """Abbreviated job info for history listings"""
    job_id: str
    command: str
    status: Literal["running", "completed", "failed"]
    started_at: datetime
    completed_at: Optional[datetime]
    execution_time: Optional[float]
    output_size: int = Field(description="Output size in bytes")


# ============================================================================
# API Request Models
# ============================================================================

class ConfigureSSHRequest(BaseModel):
    """Request to configure SSH session"""
    node_name: str = Field(..., description="Unique node identifier")
    device: SSHDeviceConfig = Field(..., description="SSH device configuration")
    persist: bool = Field(
        default=True,
        description="Store credentials for reconnection"
    )
    force_recreate: bool = Field(
        default=False,
        description="Drop existing session and recreate"
    )


class SendCommandRequest(BaseModel):
    """Request to send command via SSH"""
    node_name: str
    command: str
    expect_string: Optional[str] = Field(
        default=None,
        description="Regex pattern to wait for (overrides prompt detection)"
    )
    read_timeout: float = Field(
        default=30.0,
        description="Max time to wait for output (seconds)"
    )
    wait_timeout: int = Field(
        default=30,
        description="Time to poll before returning job_id (seconds)"
    )
    strip_prompt: bool = Field(default=True, description="Remove trailing prompt")
    strip_command: bool = Field(default=True, description="Remove command echo")


class SendConfigSetRequest(BaseModel):
    """Request to send configuration commands"""
    node_name: str
    config_commands: List[str] = Field(
        ...,
        description="List of configuration commands"
    )
    wait_timeout: int = Field(default=30, description="Adaptive async timeout")
    exit_config_mode: bool = Field(
        default=True,
        description="Exit configuration mode after commands"
    )


class ReadBufferRequest(BaseModel):
    """Request to read SSH buffer with optional grep filtering"""
    node_name: str = Field(..., description="Node identifier")
    mode: str = Field(
        default="diff",
        description="Output mode: diff, last_page, num_pages, all"
    )
    pages: int = Field(
        default=1,
        description="Number of pages (only with mode='num_pages')"
    )
    pattern: Optional[str] = Field(
        default=None,
        description="Regex pattern to filter output (grep-style)"
    )
    case_insensitive: bool = Field(
        default=False,
        description="Ignore case when matching (grep -i)"
    )
    invert: bool = Field(
        default=False,
        description="Return non-matching lines (grep -v)"
    )
    before: int = Field(
        default=0,
        description="Lines of context before match (grep -B)"
    )
    after: int = Field(
        default=0,
        description="Lines of context after match (grep -A)"
    )
    context: int = Field(
        default=0,
        description="Lines of context before AND after (grep -C, overrides before/after)"
    )


class SendCommandTimingRequest(BaseModel):
    """Request to send command with timing-based detection"""
    node_name: str
    command: str
    last_read: float = Field(
        default=2.0,
        description="Time to wait after last data received (seconds)"
    )
    read_timeout: float = Field(
        default=120.0,
        description="Absolute timeout for reading (seconds)"
    )
    wait_timeout: int = Field(default=30, description="Adaptive async timeout")


class CleanupRequest(BaseModel):
    """Request to cleanup SSH sessions"""
    keep_nodes: List[str] = Field(
        default=[],
        description="Node names to preserve"
    )
    clean_all: bool = Field(
        default=False,
        description="Clean all sessions (ignores keep_nodes)"
    )


# ============================================================================
# API Response Models
# ============================================================================

class ConfigureSSHResponse(BaseModel):
    """Response from SSH configuration"""
    session_id: str
    node_name: str
    connected: bool
    device_type: str
    host: str
    version: str = Field(description="SSH proxy service version")


class CommandResponse(BaseModel):
    """Response from command execution (adaptive async)"""
    completed: bool = Field(description="Whether command finished in wait_timeout")
    job_id: str = Field(description="Job ID for history/polling")
    output: str = Field(default="", description="Command output (if completed)")
    execution_time: Optional[float] = Field(
        default=None,
        description="Execution time in seconds (if completed)"
    )
    started_at: datetime = Field(description="When command started")
    completed_at: Optional[datetime] = Field(
        default=None,
        description="When command completed (if finished)"
    )
    message: Optional[str] = Field(
        default=None,
        description="Message if not completed (e.g., polling instructions)"
    )


class BufferResponse(BaseModel):
    """Response from buffer read"""
    output: str = Field(description="Buffer content (based on mode)")
    buffer_size: int = Field(description="Total buffer size in bytes")


class HistoryResponse(BaseModel):
    """Response from command history listing"""
    node_name: str
    total_commands: int = Field(description="Total commands executed")
    jobs: List[JobSummary] = Field(description="Job summaries in execution order")


class SessionStatusResponse(BaseModel):
    """Response from session status check"""
    connected: bool
    node_name: str
    session_id: Optional[str]
    device_type: Optional[str]
    host: Optional[str]
    buffer_size: int
    total_commands: int
    created_at: Optional[datetime]
    persist: bool


class CleanupResponse(BaseModel):
    """Response from session cleanup"""
    cleaned: List[str] = Field(description="Nodes whose sessions were cleaned")
    kept: List[str] = Field(description="Nodes whose sessions were preserved")


# ============================================================================
# Error Models
# ============================================================================

class SSHConnectionError(BaseModel):
    """Detailed SSH connection error information"""
    error_type: Literal[
        "authentication_failed",
        "connection_refused",
        "timeout",
        "host_unreachable",
        "unknown"
    ]
    error: str = Field(description="Error message")
    details: Optional[str] = Field(
        default=None,
        description="Additional error details"
    )
    suggestion: str = Field(description="Suggested fix for the error")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "error_type": "authentication_failed",
                    "error": "Authentication failed",
                    "details": "Permission denied (publickey,password)",
                    "suggestion": "Verify username/password. You can use console tools to configure SSH access first: send_console('R1', 'configure terminal'), send_console('R1', 'username admin privilege 15 secret cisco'), send_console('R1', 'crypto key generate rsa modulus 2048')"
                },
                {
                    "error_type": "connection_refused",
                    "error": "Connection refused",
                    "details": "[Errno 10061] No connection could be made",
                    "suggestion": "SSH server may not be running. Use console tools to enable SSH: send_console('R1', 'ip ssh version 2')"
                },
                {
                    "error_type": "timeout",
                    "error": "Connection timeout",
                    "details": "Timed out trying to connect to 10.10.10.10:22",
                    "suggestion": "Check network connectivity. Verify IP address is correct and device is reachable."
                }
            ]
        }
    }


class ErrorResponse(BaseModel):
    """Generic error response"""
    error: str
    details: Optional[str] = None
    ssh_connection_error: Optional[SSHConnectionError] = None


# ============================================================================
# Internal Session State
# ============================================================================

class SessionInfo(BaseModel):
    """Internal session state (not exposed in API)"""
    session_id: str
    node_name: str
    device_config: SSHDeviceConfig
    persist: bool
    created_at: datetime
    buffer: str = ""
    buffer_read_pos: int = 0
    jobs: List[Job] = []
    sequence_counter: int = 0

    model_config = {"arbitrary_types_allowed": True}
