"""Pydantic models for batch operations

Defines type-safe structures for batch tool inputs.
Validation currently disabled - models serve as documentation.
"""

from typing import Literal

from pydantic import BaseModel

# ============================================================================
# Console Batch Operations
# ============================================================================

class ConsoleSendOp(BaseModel):
    """Send data to console"""
    operation: Literal["send"] = "send"
    node_name: str
    data: str
    raw: bool = False

class ConsoleSendAndWaitOp(BaseModel):
    """Send command and wait for prompt"""
    operation: Literal["send_and_wait"] = "send_and_wait"
    node_name: str
    command: str
    expect_string: str
    timeout: int = 30

class ConsoleReadOp(BaseModel):
    """Read console output"""
    operation: Literal["read"] = "read"
    node_name: str
    mode: str = "diff"
    pages: int = 1
    pattern: str | None = None
    case_insensitive: bool = False
    invert: bool = False
    before: int = 0
    after: int = 0
    context: int = 0

class ConsoleKeystrokeOp(BaseModel):
    """Send special keystroke"""
    operation: Literal["keystroke"] = "keystroke"
    node_name: str
    key: str

# Union type for all console operations
ConsoleOperation = ConsoleSendOp | ConsoleSendAndWaitOp | ConsoleReadOp | ConsoleKeystrokeOp

# ============================================================================
# SSH Batch Operations
# ============================================================================

class SSHCommandOp(BaseModel):
    """SSH command operation"""
    operation: Literal["command"] = "command"
    node_name: str
    command: str | list[str]
    expect_string: str | None = None
    read_timeout: float = 30.0
    wait_timeout: int = 30

class SSHDisconnectOp(BaseModel):
    """SSH disconnect operation"""
    operation: Literal["disconnect"] = "disconnect"
    node_name: str

# Union type for all SSH operations
SSHOperation = SSHCommandOp | SSHDisconnectOp

# ============================================================================
# Network Connection Operations
# ============================================================================

class ConnectionDef(BaseModel):
    """Network connection definition"""
    action: Literal["create", "delete"]
    node_a: str
    port_a: int
    node_b: str
    port_b: int

# ============================================================================
# Drawing Batch Operations
# ============================================================================

class DrawingDef(BaseModel):
    """Drawing object definition"""
    svg: str
    x: int
    y: int
    z: int = 1
    rotation: int = 0
