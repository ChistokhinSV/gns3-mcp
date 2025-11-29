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
    session_timeout: int = Field(
        default=14400,
        description="Session timeout in seconds (default: 4 hours = 14400s)"
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
    # Error fields (v0.1.6)
    error: Optional[str] = Field(
        default=None,
        description="Error message if command failed"
    )
    error_code: Optional[str] = Field(
        default=None,
        description="Machine-readable error code (SSH_DISCONNECTED, TIMEOUT, etc.)"
    )
    suggested_action: Optional[str] = Field(
        default=None,
        description="Suggested fix for the error"
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
# Local Execution (v0.2.2)
# ============================================================================

class LocalExecuteRequest(BaseModel):
    """Request to execute command locally on SSH proxy container"""
    command: str | List[str] = Field(..., description="Command or list of commands to execute")
    timeout: int = Field(default=30, description="Execution timeout in seconds")
    working_dir: str = Field(
        default="/opt/gns3-ssh-proxy",
        description="Working directory for command execution"
    )
    shell: bool = Field(
        default=True,
        description="Execute through shell (allows pipes, redirects)"
    )


class LocalExecuteResponse(BaseModel):
    """Response from local command execution"""
    success: bool = Field(description="Whether command executed successfully")
    output: str = Field(default="", description="Combined stdout and stderr")
    exit_code: int = Field(description="Command exit code")
    execution_time: float = Field(description="Execution time in seconds")
    error: Optional[str] = Field(default=None, description="Error message if failed")


# ============================================================================
# TFTP Management (v0.3.0)
# ============================================================================

class TFTPRequest(BaseModel):
    """Request for TFTP operations"""
    action: str = Field(..., description="Action: list, upload, download, delete, status")
    filename: Optional[str] = Field(default=None, description="Filename for upload/download/delete")
    content: Optional[str] = Field(default=None, description="File content for upload (base64 encoded)")


class TFTPFile(BaseModel):
    """TFTP file information"""
    filename: str
    size: int
    modified: str
    is_dir: bool = False


class TFTPResponse(BaseModel):
    """Response from TFTP operations"""
    success: bool
    action: str
    files: Optional[List[TFTPFile]] = None
    content: Optional[str] = None  # base64 encoded for download
    message: Optional[str] = None
    error: Optional[str] = None


# ============================================================================
# HTTP Client (v0.3.0)
# ============================================================================

class HTTPClientRequest(BaseModel):
    """Request for HTTP client operations"""
    action: str = Field(..., description="Action: get, status")
    url: str = Field(..., description="Target URL (http:// or https://)")
    timeout: int = Field(default=10, description="Request timeout in seconds")
    verify_ssl: bool = Field(default=False, description="Verify SSL certificates")
    headers: Optional[dict] = Field(default=None, description="Custom HTTP headers")


class HTTPClientResponse(BaseModel):
    """Response from HTTP client operations"""
    success: bool
    action: str
    status_code: Optional[int] = None
    content: Optional[str] = None
    headers: Optional[dict] = None
    reachable: Optional[bool] = None  # For status action
    error: Optional[str] = None


# ============================================================================
# HTTP Reverse Proxy (v0.3.0)
# ============================================================================

class HTTPProxyRequest(BaseModel):
    """Request for HTTP reverse proxy management"""
    action: str = Field(..., description="Action: register, unregister, list, reload")
    device_name: Optional[str] = Field(default=None, description="Device identifier")
    device_ip: Optional[str] = Field(default=None, description="Device IP address")
    device_port: Optional[int] = Field(default=None, description="Device HTTP/HTTPS port")


class HTTPProxyDevice(BaseModel):
    """Registered device for HTTP reverse proxy"""
    device_name: str
    device_ip: str
    device_port: int
    proxy_url: str


class HTTPProxyResponse(BaseModel):
    """Response from HTTP reverse proxy operations"""
    success: bool
    action: str
    devices: Optional[List[HTTPProxyDevice]] = None
    message: Optional[str] = None
    error: Optional[str] = None


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
    last_activity: datetime = Field(
        description="Last activity timestamp - updated on every operation"
    )
    session_timeout: int = Field(
        default=14400,
        description="Session timeout in seconds (default: 4 hours)"
    )
    buffer: str = ""
    buffer_read_pos: int = 0
    jobs: List[Job] = []
    sequence_counter: int = 0

    model_config = {"arbitrary_types_allowed": True}


# ============================================================================
# Traffic Widget Models (v0.4.0)
# ============================================================================

class TrafficStats(BaseModel):
    """Traffic statistics for a bridge interface"""
    rx_bytes: int = Field(default=0, description="Total bytes received")
    tx_bytes: int = Field(default=0, description="Total bytes transmitted")
    rx_packets: int = Field(default=0, description="Total packets received")
    tx_packets: int = Field(default=0, description="Total packets transmitted")
    rx_errors: int = Field(default=0, description="Receive errors")
    tx_errors: int = Field(default=0, description="Transmit errors")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When stats were collected (UTC)"
    )


class TrafficDelta(BaseModel):
    """Traffic rate calculated from delta between two measurements"""
    rx_bps: float = Field(default=0.0, description="Receive rate (bytes/sec)")
    tx_bps: float = Field(default=0.0, description="Transmit rate (bytes/sec)")
    rx_pps: float = Field(default=0.0, description="Receive rate (packets/sec)")
    tx_pps: float = Field(default=0.0, description="Transmit rate (packets/sec)")
    interval_seconds: float = Field(default=15.0, description="Measurement interval")


class WidgetInfo(BaseModel):
    """Traffic widget state and metadata"""
    widget_id: str = Field(..., description="Unique widget identifier (UUID)")
    link_id: str = Field(..., description="GNS3 link ID this widget monitors")
    drawing_id: str = Field(..., description="GNS3 drawing ID for the widget")
    bridge_name: str = Field(..., description="ubridge bridge name (e.g. QEMU-xxx-0)")
    ubridge_port: int = Field(default=0, description="ubridge TCP hypervisor port")
    proxy_id: str = Field(..., description="Proxy instance ID for ownership")
    project_id: str = Field(..., description="GNS3 project ID")
    x: int = Field(..., description="Widget X position in topology")
    y: int = Field(..., description="Widget Y position in topology")
    # v0.4.2: New visualization parameters
    inverse: bool = Field(
        default=False,
        description="Swap TX/RX direction (show traffic from second node's perspective)"
    )
    chart_type: str = Field(
        default="bar",
        description="Chart type: 'bar' (vertical bars) or 'timeseries' (area graph)"
    )
    history: List[TrafficDelta] = Field(
        default=[],
        description="Historical traffic deltas for time-series chart (circular buffer)"
    )
    max_history: int = Field(
        default=30,
        description="Max history points (30 × 15s = 7.5 min)"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When widget was created (UTC)"
    )
    last_update: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last successful SVG update (UTC)"
    )
    last_stats: Optional[TrafficStats] = Field(
        default=None,
        description="Last collected traffic statistics"
    )
    last_delta: Optional[TrafficDelta] = Field(
        default=None,
        description="Last calculated traffic rate"
    )


class WidgetRequest(BaseModel):
    """Request to create/manage traffic widgets"""
    action: Literal["create", "update", "delete", "list", "refresh"] = Field(
        ...,
        description="Action: create, update, delete, list, or refresh"
    )
    link_id: Optional[str] = Field(
        default=None,
        description="GNS3 link ID (required for create)"
    )
    project_id: Optional[str] = Field(
        default=None,
        description="GNS3 project ID (required for create)"
    )
    widget_id: Optional[str] = Field(
        default=None,
        description="Widget ID (required for update/delete)"
    )
    x: Optional[int] = Field(
        default=None,
        description="Override X position (optional for create/update)"
    )
    y: Optional[int] = Field(
        default=None,
        description="Override Y position (optional for create/update)"
    )
    # v0.4.2: New visualization parameters (Optional for update action, defaults for create)
    inverse: Optional[bool] = Field(
        default=None,
        description="Swap TX/RX direction (show traffic from second node's perspective). Default: False for create"
    )
    chart_type: Optional[str] = Field(
        default=None,
        description="Chart type: 'bar' (vertical bars) or 'timeseries' (area graph). Default: 'bar' for create"
    )


class WidgetResponse(BaseModel):
    """Response from widget operations"""
    success: bool = Field(..., description="Whether operation succeeded")
    action: str = Field(..., description="Action that was performed")
    widget: Optional[WidgetInfo] = Field(
        default=None,
        description="Widget info (for create/delete single)"
    )
    widgets: Optional[List[WidgetInfo]] = Field(
        default=None,
        description="List of widgets (for list action)"
    )
    message: Optional[str] = Field(
        default=None,
        description="Human-readable result message"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if failed"
    )


class BridgeInfo(BaseModel):
    """ubridge interface information"""
    name: str = Field(..., description="Bridge name (e.g. QEMU-xxx-0)")
    ubridge_port: int = Field(default=0, description="ubridge TCP hypervisor port")
    node_id: Optional[str] = Field(
        default=None,
        description="GNS3 node ID extracted from bridge name"
    )
    adapter: Optional[int] = Field(
        default=None,
        description="Adapter number extracted from bridge name"
    )
    link_id: Optional[str] = Field(
        default=None,
        description="Associated GNS3 link ID (if discoverable)"
    )
    stats: TrafficStats = Field(..., description="Current traffic statistics")
    has_widget: bool = Field(
        default=False,
        description="Whether a widget exists for this bridge"
    )


class TopologyInfo(BaseModel):
    """Project topology for web UI"""
    project_id: str = Field(..., description="GNS3 project ID")
    project_name: str = Field(..., description="GNS3 project name")
    nodes: List[Dict[str, Any]] = Field(
        default=[],
        description="List of nodes with positions"
    )
    links: List[Dict[str, Any]] = Field(
        default=[],
        description="List of links with endpoints"
    )
    widgets: List[WidgetInfo] = Field(
        default=[],
        description="Active traffic widgets"
    )
