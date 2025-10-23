"""Pydantic Data Models for GNS3 MCP Server

Type-safe data models for all GNS3 entities and operations.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Literal, List, Optional, Dict, Any
from datetime import datetime


# Project Models

class ProjectInfo(BaseModel):
    """GNS3 Project information"""
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


# Node Models

class NodeConsole(BaseModel):
    """Node console information"""
    console_type: str
    console: Optional[int] = None
    console_host: Optional[str] = None
    console_auto_start: bool = False


class NodeInfo(BaseModel):
    """GNS3 Node information"""
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
    adapter_a: int = Field(default=0, ge=0, description="Adapter number on node A")
    adapter_b: int = Field(default=0, ge=0, description="Adapter number on node B")

    class Config:
        json_schema_extra = {
            "example": {
                "action": "connect",
                "node_a": "Router1",
                "node_b": "Router2",
                "port_a": 0,
                "port_b": 1,
                "adapter_a": 0,
                "adapter_b": 0
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

class ErrorResponse(BaseModel):
    """Error response"""
    error: str
    details: Optional[str] = None
    field: Optional[str] = None
    operation_index: Optional[int] = None

    class Config:
        json_schema_extra = {
            "example": {
                "error": "Node not found",
                "details": "Node 'Router1' does not exist in current project",
                "field": "node_a",
                "operation_index": 0
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
