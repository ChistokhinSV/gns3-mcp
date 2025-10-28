"""Pydantic Data Models for GNS3 MCP Server

Type-safe data models for all GNS3 entities and operations.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field

# Project Models

class ProjectSummary(BaseModel):
    """Minimal project information for list_projects (lightweight)"""
    status: str  # opened, closed, etc.
    name: str
    project_id: str = Field(exclude=True)  # Store internally, exclude from output

    @property
    def uri(self) -> str:
        """Return project URI with projects:// prefix"""
        return f"projects://{self.project_id}"

    def model_dump(self, **kwargs):
        """Custom serialization to include uri instead of project_id"""
        data = super().model_dump(**kwargs)
        data['uri'] = self.uri
        return data

    class Config:
        json_schema_extra = {
            "example": {
                "status": "opened",
                "name": "My Network Lab",
                "uri": "projects://a1b2c3d4-e5f6-7890-1234-567890abcdef"
            }
        }


class ProjectInfo(BaseModel):
    """GNS3 Project information (full details)"""
    project_id: str
    name: str
    status: Literal["opened", "closed"]
    path: Optional[str] = None
    filename: Optional[str] = None
    auto_start: bool = False
    auto_close: bool = True
    auto_open: bool = False

    class Config:
        json_schema_extra = {
            "example": {
                "project_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
                "name": "My Network Lab",
                "status": "opened"
            }
        }


class SnapshotInfo(BaseModel):
    """GNS3 Project Snapshot information"""
    snapshot_id: str
    name: str
    created_at: str
    project_id: str

    class Config:
        json_schema_extra = {
            "example": {
                "snapshot_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
                "name": "Before Config Change",
                "created_at": "2025-10-25T14:30:00.000Z",
                "project_id": "proj-123"
            }
        }


# Node Models

class NodeConsole(BaseModel):
    """Node console information"""
    console_type: str
    console: Optional[int] = None
    console_host: Optional[str] = None
    console_auto_start: bool = False


class NodeSummary(BaseModel):
    """Minimal node information for list_nodes (lightweight)"""
    project_id: str = Field(exclude=True)  # Store internally, exclude from output
    node_id: str = Field(exclude=True)  # Store internally, exclude from output
    name: str
    node_type: str
    status: Literal["started", "stopped", "suspended"]
    console_type: Optional[str] = None
    console: Optional[int] = None

    @property
    def uri(self) -> str:
        """Return node URI with nodes:// prefix"""
        return f"nodes://{self.project_id}/{self.node_id}"

    def model_dump(self, **kwargs):
        """Custom serialization to include uri instead of node_id/project_id"""
        data = super().model_dump(**kwargs)
        data['uri'] = self.uri
        return data

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Router1",
                "node_type": "qemu",
                "status": "started",
                "console_type": "telnet",
                "console": 5000,
                "uri": "nodes://project-id/node-id"
            }
        }


class NodeInfo(BaseModel):
    """GNS3 Node information (full details)"""
    node_id: str
    name: str
    node_type: str
    status: Literal["started", "stopped", "suspended"]
    console_type: Optional[str] = None
    console: Optional[int] = None
    console_host: Optional[str] = None
    compute_id: str = "local"
    x: int = 0
    y: int = 0
    z: int = 0
    locked: bool = False

    # Optional fields
    ports: Optional[List[Dict[str, Any]]] = None
    label: Optional[Dict[str, Any]] = None
    symbol: Optional[str] = None

    # Hardware properties (QEMU nodes)
    ram: Optional[int] = None
    cpus: Optional[int] = None
    adapters: Optional[int] = None
    hdd_disk_image: Optional[str] = None
    hda_disk_image: Optional[str] = None

    def to_detail_view(self) -> Dict[str, Any]:
        """Detail view - show all fields"""
        return self.model_dump()

    class Config:
        json_schema_extra = {
            "example": {
                "node_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
                "name": "Router1",
                "node_type": "qemu",
                "status": "started",
                "console_type": "telnet",
                "console": 5000,
                "console_host": "192.168.1.20"
            }
        }


# Link Models

class LinkEndpoint(BaseModel):
    """Network link endpoint"""
    node_id: str
    node_name: str
    adapter_number: int = Field(ge=0, description="Adapter/interface number")
    port_number: int = Field(ge=0, description="Port number on adapter")
    adapter_type: Optional[str] = None
    port_name: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "node_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
                "node_name": "Router1",
                "adapter_number": 0,
                "port_number": 0,
                "port_name": "Ethernet0"
            }
        }


class LinkInfo(BaseModel):
    """Network link information"""
    link_id: str
    link_type: str = "ethernet"
    node_a: LinkEndpoint
    node_b: LinkEndpoint
    capturing: bool = False
    capture_file_name: Optional[str] = None
    capture_file_path: Optional[str] = None
    capture_compute_id: Optional[str] = None
    suspend: bool = False

    class Config:
        json_schema_extra = {
            "example": {
                "link_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
                "link_type": "ethernet",
                "node_a": {
                    "node_id": "node1-id",
                    "node_name": "Router1",
                    "adapter_number": 0,
                    "port_number": 0
                },
                "node_b": {
                    "node_id": "node2-id",
                    "node_name": "Router2",
                    "adapter_number": 0,
                    "port_number": 1
                }
            }
        }


# Operation Models

class ConnectOperation(BaseModel):
    """Connect two nodes operation"""
    action: Literal["connect"]
    node_a: str = Field(description="Name of first node")
    node_b: str = Field(description="Name of second node")
    port_a: int = Field(ge=0, description="Port number on node A")
    port_b: int = Field(ge=0, description="Port number on node B")
    adapter_a: Union[str, int] = Field(default=0, description="Adapter on node A (name like 'eth0' or number)")
    adapter_b: Union[str, int] = Field(default=0, description="Adapter on node B (name like 'eth0' or number)")

    class Config:
        json_schema_extra = {
            "example": {
                "action": "connect",
                "node_a": "Router1",
                "node_b": "Router2",
                "port_a": 0,
                "port_b": 1,
                "adapter_a": "eth0",
                "adapter_b": "GigabitEthernet0/0"
            }
        }


class DisconnectOperation(BaseModel):
    """Disconnect link operation"""
    action: Literal["disconnect"]
    link_id: str = Field(description="Link ID to disconnect (from get_links)")

    class Config:
        json_schema_extra = {
            "example": {
                "action": "disconnect",
                "link_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef"
            }
        }


# Union type for connection operations
ConnectionOperation = ConnectOperation | DisconnectOperation


class CompletedOperation(BaseModel):
    """Completed operation result"""
    index: int
    action: str
    link_id: Optional[str] = None
    node_a: Optional[str] = None
    node_b: Optional[str] = None
    port_a: Optional[int] = None
    port_b: Optional[int] = None
    adapter_a: Optional[int] = None
    adapter_b: Optional[int] = None
    # Human-readable port names
    port_a_name: Optional[str] = None
    port_b_name: Optional[str] = None


class FailedOperation(BaseModel):
    """Failed operation result"""
    index: int
    action: str
    operation: Dict[str, Any]
    reason: str


class OperationResult(BaseModel):
    """Batch operation result"""
    completed: List[CompletedOperation]
    failed: Optional[FailedOperation] = None

    class Config:
        json_schema_extra = {
            "example": {
                "completed": [
                    {
                        "index": 0,
                        "action": "disconnect",
                        "link_id": "old-link-id"
                    },
                    {
                        "index": 1,
                        "action": "connect",
                        "link_id": "new-link-id",
                        "node_a": "Router1",
                        "node_b": "Router2",
                        "port_a": 0,
                        "port_b": 1
                    }
                ],
                "failed": None
            }
        }


# Template Models

class TemplateInfo(BaseModel):
    """GNS3 Template information"""
    template_id: str
    name: str
    category: str
    node_type: Optional[str] = None
    compute_id: Optional[str] = "local"
    builtin: bool = False
    symbol: Optional[str] = None
    usage: Optional[str] = None  # Template usage notes (credentials, setup instructions)

    @property
    def uri(self) -> str:
        """Return template URI with templates:// prefix"""
        return f"templates://{self.template_id}"

    def to_list_view(self) -> Dict[str, Any]:
        """List view - hide compute_id, symbol, template_id, usage; show uri"""
        data = self.model_dump(exclude={'template_id', 'compute_id', 'symbol', 'usage'})
        data['uri'] = self.uri
        return data

    def to_detail_view(self) -> Dict[str, Any]:
        """Detail view - show all fields"""
        return self.model_dump()

    class Config:
        json_schema_extra = {
            "example": {
                "template_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
                "name": "Ethernet switch",
                "category": "switch",
                "node_type": "ethernet_switch",
                "builtin": True,
                "usage": "Default credentials: admin/admin"
            }
        }


# Network Configuration Models

class NetworkInterfaceStatic(BaseModel):
    """Static IP network interface configuration"""
    name: str = Field(description="Interface name (eth0, eth1, etc.)")
    mode: Literal["static"] = "static"
    address: str = Field(description="IP address")
    netmask: str = Field(description="Network mask")
    gateway: Optional[str] = Field(default=None, description="Default gateway IP")
    dns: Optional[str] = Field(default="8.8.8.8", description="DNS server IP")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "eth0",
                "mode": "static",
                "address": "10.199.0.254",
                "netmask": "255.255.255.0",
                "gateway": "10.199.0.1",
                "dns": "8.8.8.8"
            }
        }


class NetworkInterfaceDHCP(BaseModel):
    """DHCP network interface configuration"""
    name: str = Field(description="Interface name (eth0, eth1, etc.)")
    mode: Literal["dhcp"] = "dhcp"
    dns: Optional[str] = Field(default="8.8.8.8", description="DNS server IP")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "eth0",
                "mode": "dhcp",
                "dns": "8.8.8.8"
            }
        }


NetworkInterface = Union[NetworkInterfaceStatic, NetworkInterfaceDHCP]


class NetworkConfig(BaseModel):
    """Multi-interface network configuration for Docker nodes"""
    interfaces: List[NetworkInterface] = Field(description="List of network interfaces to configure")

    def to_debian_interfaces(self) -> str:
        """Generate /etc/network/interfaces file content

        Returns:
            Debian-style interfaces configuration file content
        """
        lines = []
        for iface in self.interfaces:
            lines.append(f"auto {iface.name}")

            if iface.mode == "static":
                lines.append(f"iface {iface.name} inet static")
                lines.append(f"    address {iface.address}")
                lines.append(f"    netmask {iface.netmask}")
                if iface.gateway:
                    lines.append(f"    gateway {iface.gateway}")
            else:  # dhcp
                lines.append(f"iface {iface.name} inet dhcp")

            if iface.dns:
                lines.append(f"    up echo nameserver {iface.dns} > /etc/resolv.conf")
            lines.append("")

        return "\n".join(lines)

    class Config:
        json_schema_extra = {
            "example": {
                "interfaces": [
                    {
                        "name": "eth0",
                        "mode": "static",
                        "address": "10.199.0.254",
                        "netmask": "255.255.255.0",
                        "gateway": "10.199.0.1",
                        "dns": "8.8.8.8"
                    },
                    {
                        "name": "eth1",
                        "mode": "dhcp",
                        "dns": "8.8.8.8"
                    }
                ]
            }
        }


# Drawing Models

class DrawingInfo(BaseModel):
    """GNS3 Drawing object information"""
    drawing_id: str
    project_id: str
    x: int
    y: int
    z: int = 0
    rotation: int = 0
    svg: str
    locked: bool = False

    class Config:
        json_schema_extra = {
            "example": {
                "drawing_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
                "project_id": "proj-123",
                "x": 100,
                "y": 200,
                "z": 0,
                "svg": "<svg>...</svg>"
            }
        }


# Console Models

class ConsoleStatus(BaseModel):
    """Console connection status"""
    connected: bool
    node_name: str
    session_id: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    buffer_size: Optional[int] = None
    created_at: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "connected": True,
                "node_name": "Router1",
                "session_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
                "host": "192.168.1.20",
                "port": 5000,
                "buffer_size": 1024,
                "created_at": "2025-10-23T10:30:00"
            }
        }


# Error Models

class ErrorCode(str, Enum):
    """Standardized error codes for all MCP tools"""

    # Resource Not Found (404-style)
    PROJECT_NOT_FOUND = "PROJECT_NOT_FOUND"
    NODE_NOT_FOUND = "NODE_NOT_FOUND"
    LINK_NOT_FOUND = "LINK_NOT_FOUND"
    TEMPLATE_NOT_FOUND = "TEMPLATE_NOT_FOUND"
    DRAWING_NOT_FOUND = "DRAWING_NOT_FOUND"
    SNAPSHOT_NOT_FOUND = "SNAPSHOT_NOT_FOUND"
    PROXY_NOT_FOUND = "PROXY_NOT_FOUND"

    # Validation Errors (400-style)
    INVALID_PARAMETER = "INVALID_PARAMETER"
    MISSING_PARAMETER = "MISSING_PARAMETER"
    PORT_IN_USE = "PORT_IN_USE"
    NODE_RUNNING = "NODE_RUNNING"
    NODE_STOPPED = "NODE_STOPPED"
    INVALID_NODE_STATE = "INVALID_NODE_STATE"
    INVALID_ADAPTER = "INVALID_ADAPTER"
    INVALID_PORT = "INVALID_PORT"

    # Connection Errors (503-style)
    GNS3_UNREACHABLE = "GNS3_UNREACHABLE"
    GNS3_API_ERROR = "GNS3_API_ERROR"
    CONSOLE_DISCONNECTED = "CONSOLE_DISCONNECTED"
    CONSOLE_CONNECTION_FAILED = "CONSOLE_CONNECTION_FAILED"
    SSH_CONNECTION_FAILED = "SSH_CONNECTION_FAILED"
    SSH_DISCONNECTED = "SSH_DISCONNECTED"
    PROXY_SERVICE_UNREACHABLE = "PROXY_SERVICE_UNREACHABLE"

    # Authentication Errors (401-style)
    AUTH_FAILED = "AUTH_FAILED"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"

    # Internal Errors (500-style)
    INTERNAL_ERROR = "INTERNAL_ERROR"
    TIMEOUT = "TIMEOUT"
    OPERATION_FAILED = "OPERATION_FAILED"


class ErrorResponse(BaseModel):
    """Standardized error response for all tools"""
    error: str = Field(description="Human-readable error message")
    error_code: Optional[str] = Field(default=None, description="Machine-readable error code from ErrorCode enum")
    details: Optional[str] = Field(default=None, description="Additional error details")
    suggested_action: Optional[str] = Field(default=None, description="How to fix the error")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Error context for debugging")
    # Legacy fields for backward compatibility
    field: Optional[str] = None
    operation_index: Optional[int] = None
    # Version tracking
    server_version: str = Field(default="unknown", description="Server version that produced this error")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="Error timestamp (ISO 8601 UTC)")

    class Config:
        json_schema_extra = {
            "example": {
                "error": "Node 'Router1' not found in project 'Lab1'",
                "error_code": "NODE_NOT_FOUND",
                "details": "Available nodes: Router2, Router3, Switch1",
                "suggested_action": "Use list_nodes() to see all available nodes in the project",
                "context": {
                    "project_id": "abc123",
                    "node_name": "Router1",
                    "available_nodes": ["Router2", "Router3", "Switch1"]
                },
                "server_version": "0.20.0",
                "timestamp": "2025-10-25T14:30:00.000Z"
            }
        }


# Validation Helper

def validate_connection_operations(operations: List[Dict[str, Any]]) -> tuple[List[ConnectionOperation], Optional[str]]:
    """Validate and parse connection operations

    Args:
        operations: List of raw operation dictionaries

    Returns:
        Tuple of (parsed operations, error message)
        If error message is not None, validation failed
    """
    parsed_ops: List[ConnectionOperation] = []

    for idx, op in enumerate(operations):
        try:
            action = op.get("action", "").lower()

            if action == "connect":
                parsed_ops.append(ConnectOperation(**op))
            elif action == "disconnect":
                parsed_ops.append(DisconnectOperation(**op))
            else:
                return ([], f"Invalid action '{action}' at index {idx}. Valid actions: connect, disconnect")

        except Exception as e:
            return ([], f"Validation error at index {idx}: {str(e)}")

    return (parsed_ops, None)
