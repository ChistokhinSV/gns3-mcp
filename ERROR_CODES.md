# Error Codes Reference

**GNS3 MCP Server v0.20.0** - Complete error code reference for standardized error responses.

All tools return structured JSON error responses with machine-readable error codes, actionable guidance, and debugging context.

## Error Response Format

```json
{
  "error": "Human-readable error message",
  "error_code": "MACHINE_READABLE_CODE",
  "details": "Additional error details",
  "suggested_action": "How to fix the error",
  "context": {
    "parameter": "value",
    "debugging_info": "..."
  },
  "server_version": "0.20.0",
  "timestamp": "2025-10-25T14:30:00.000Z"
}
```

## Error Code Categories

### Resource Not Found (404-style)

Errors when requested resources don't exist or cannot be found.

#### `PROJECT_NOT_FOUND`
**When**: No project is currently open OR project doesn't exist
**Example**:
```json
{
  "error": "No project currently open",
  "error_code": "PROJECT_NOT_FOUND",
  "suggested_action": "Use open_project() to open a project first"
}
```
**How to fix**: Open a project with `open_project("ProjectName")` or verify project name spelling

---

#### `NODE_NOT_FOUND`
**When**: Node name not found in current project (case-sensitive)
**Example**:
```json
{
  "error": "Node 'Router1' not found in project",
  "error_code": "NODE_NOT_FOUND",
  "details": "Available nodes: Router2, Router3, Switch1",
  "suggested_action": "Use list_nodes() to see all available nodes in the project",
  "context": {
    "node_name": "Router1",
    "available_nodes": ["Router2", "Router3", "Switch1"]
  }
}
```
**How to fix**: Check node name spelling (case-sensitive) or use resource `projects://{id}/nodes/` to see available nodes

---

#### `LINK_NOT_FOUND`
**When**: Link ID doesn't exist in project
**Example**:
```json
{
  "error": "Link 'abc-123' not found in project",
  "error_code": "LINK_NOT_FOUND",
  "suggested_action": "Use get_links() to see available link IDs"
}
```
**How to fix**: Verify link ID using resource `projects://{id}/links/`

---

#### `TEMPLATE_NOT_FOUND`
**When**: Template name not available in GNS3
**Example**:
```json
{
  "error": "Template 'Cisco IOSv' not found",
  "error_code": "TEMPLATE_NOT_FOUND",
  "details": "Available templates: Alpine Linux, Ethernet switch, ...",
  "suggested_action": "Use list_templates() to see all available templates",
  "context": {
    "template_name": "Cisco IOSv",
    "available_templates": ["Alpine Linux", "Ethernet switch"]
  }
}
```
**How to fix**: Check template name spelling or use resource `projects://{id}/templates/` to see available templates

---

#### `DRAWING_NOT_FOUND`
**When**: Drawing ID doesn't exist in project
**Example**:
```json
{
  "error": "Drawing 'draw-123' not found in project",
  "error_code": "DRAWING_NOT_FOUND",
  "details": "Available drawing IDs: draw-456, draw-789",
  "suggested_action": "Use list_drawings() or resource projects://{id}/drawings/ to see available drawings"
}
```
**How to fix**: Verify drawing ID using resource `projects://{id}/drawings/`

---

#### `SNAPSHOT_NOT_FOUND`
**When**: Snapshot name doesn't exist in project
**Example**:
```json
{
  "error": "Snapshot 'Before Config' not found in project",
  "error_code": "SNAPSHOT_NOT_FOUND",
  "details": "Available snapshots: Initial Setup, After OSPF",
  "suggested_action": "Use resource projects://{id}/snapshots/ to see available snapshots"
}
```
**How to fix**: Check snapshot name or use resource `projects://{id}/snapshots/` to list snapshots

---

### Validation Errors (400-style)

Errors due to invalid or missing parameters.

#### `INVALID_PARAMETER`
**When**: Parameter value is invalid
**Example**:
```json
{
  "error": "Invalid action 'restart'",
  "error_code": "INVALID_PARAMETER",
  "details": "Invalid value 'restart' for parameter 'action'. Valid values: start, stop, suspend, reload",
  "suggested_action": "Check the 'action' parameter and try again",
  "context": {
    "parameter": "action",
    "value": "restart",
    "valid_values": ["start", "stop", "suspend", "reload"]
  }
}
```
**How to fix**: Use one of the valid values listed in the error

---

#### `MISSING_PARAMETER`
**When**: Required parameter not provided
**Example**:
```json
{
  "error": "Missing required parameters for rectangle",
  "error_code": "MISSING_PARAMETER",
  "details": "Rectangle requires 'width' and 'height' parameters",
  "suggested_action": "Provide width and height parameters"
}
```
**How to fix**: Provide all required parameters as specified in the error

---

#### `PORT_IN_USE`
**When**: Port already connected to another node
**Example**:
```json
{
  "error": "Port R1 adapter 0 port 0 is already connected to R2",
  "error_code": "PORT_IN_USE",
  "suggested_action": "Disconnect the existing link first using set_connection with action='disconnect'",
  "context": {
    "node_name": "R1",
    "adapter": 0,
    "port": 0,
    "connected_to": "R2"
  }
}
```
**How to fix**: Disconnect existing link first with `set_connection([{"action": "disconnect", "link_id": "..."}])`

---

#### `NODE_RUNNING`
**When**: Operation requires node to be stopped
**Example**:
```json
{
  "error": "Operation 'change properties: name' requires node 'Router1' to be stopped",
  "error_code": "NODE_RUNNING",
  "details": "Node is currently running",
  "suggested_action": "Stop the node first with set_node('Router1', action='stop'), then retry"
}
```
**How to fix**: Stop the node first with `set_node("NodeName", action="stop")`

---

#### `NODE_STOPPED`
**When**: Operation requires node to be running
**Example**:
```json
{
  "error": "Operation 'console access' requires node 'Router1' to be running",
  "error_code": "NODE_STOPPED",
  "details": "Node is currently stopped",
  "suggested_action": "Start the node first with set_node('Router1', action='start'), then retry"
}
```
**How to fix**: Start the node first with `set_node("NodeName", action="start")`

---

#### `INVALID_ADAPTER`
**When**: Adapter name/number not valid for this node
**Example**:
```json
{
  "error": "Failed to resolve adapter for Router1",
  "error_code": "INVALID_ADAPTER",
  "details": "Adapter 'eth5' not found on node. Available: eth0, eth1, eth2",
  "suggested_action": "Use valid adapter name (e.g., 'eth0', 'GigabitEthernet0/0') or adapter number (0, 1, 2, ...)"
}
```
**How to fix**: Check available adapters on the node or use numeric adapter index

---

#### `INVALID_PORT`
**When**: Port number exceeds adapter capacity
**Example**:
```json
{
  "error": "Port number 5 exceeds adapter capacity",
  "error_code": "INVALID_PORT",
  "details": "Adapter 0 only has 4 ports (0-3)",
  "suggested_action": "Use port number 0-3 for this adapter"
}
```
**How to fix**: Use valid port number within adapter's range

---

### Connection Errors (503-style)

Errors related to network/service connectivity.

#### `GNS3_UNREACHABLE`
**When**: Cannot connect to GNS3 server
**Example**:
```json
{
  "error": "Cannot connect to GNS3 server at 192.168.1.20:80",
  "error_code": "GNS3_UNREACHABLE",
  "details": "Connection refused",
  "suggested_action": "Check that GNS3 server is running and accessible at the configured host and port",
  "context": {
    "host": "192.168.1.20",
    "port": 80
  }
}
```
**How to fix**: Verify GNS3 server is running, check host/port configuration, verify network connectivity

---

#### `GNS3_API_ERROR`
**When**: GNS3 server returned an API error
**Example**:
```json
{
  "error": "Failed to list nodes",
  "error_code": "GNS3_API_ERROR",
  "details": "HTTP 500 from /v3/projects/abc123/nodes",
  "suggested_action": "Check that GNS3 server is running and a project is currently open",
  "context": {
    "project_id": "abc123",
    "exception": "HTTP 500 Internal Server Error"
  }
}
```
**How to fix**: Check GNS3 server logs, verify project is accessible, restart GNS3 server if needed

---

#### `CONSOLE_DISCONNECTED`
**When**: Console session lost or failed to send
**Example**:
```json
{
  "error": "Failed to send data to console for node 'Router1'",
  "error_code": "CONSOLE_DISCONNECTED",
  "details": "Console session may have been disconnected",
  "suggested_action": "Check console connection with get_console_status(), or use disconnect_console() and retry"
}
```
**How to fix**: Disconnect and reconnect console session, verify node is still running

---

#### `CONSOLE_CONNECTION_FAILED`
**When**: Failed to connect to console
**Example**:
```json
{
  "error": "Failed to connect to console for node 'Router1'",
  "error_code": "CONSOLE_CONNECTION_FAILED",
  "details": "Connection timeout",
  "suggested_action": "Verify node 'Router1' is started and console port 5000 is correct",
  "context": {
    "node_name": "Router1",
    "host": "192.168.1.20",
    "port": 5000
  }
}
```
**How to fix**: Verify node is started, check console port, verify telnet access

---

#### `SSH_CONNECTION_FAILED`
**When**: Failed to establish SSH session
**Example**:
```json
{
  "error": "SSH connection failed for node 'Router1'",
  "error_code": "SSH_CONNECTION_FAILED",
  "details": "Authentication failed",
  "suggested_action": "Configure SSH on device first using console tools"
}
```
**How to fix**: Use console tools to enable SSH, create user, generate keys

---

#### `SSH_DISCONNECTED`
**When**: SSH session lost
**Example**:
```json
{
  "error": "SSH session disconnected for node 'Router1'",
  "error_code": "SSH_DISCONNECTED",
  "details": "Connection reset by peer",
  "suggested_action": "Reconnect SSH session with ssh_configure()"
}
```
**How to fix**: Reconnect SSH session, verify node is still running

---

### Authentication Errors (401-style)

Errors related to authentication and authorization.

#### `AUTH_FAILED`
**When**: Authentication to GNS3 server failed
**Example**:
```json
{
  "error": "Authentication failed",
  "error_code": "AUTH_FAILED",
  "details": "Invalid username or password",
  "suggested_action": "Check GNS3 credentials in configuration"
}
```
**How to fix**: Verify username and password in MCP server configuration

---

#### `TOKEN_EXPIRED`
**When**: JWT token expired (auto-renewed)
**Example**:
```json
{
  "error": "JWT token expired",
  "error_code": "TOKEN_EXPIRED",
  "suggested_action": "Token will be automatically renewed on next request"
}
```
**How to fix**: Usually auto-recovered, retry operation

---

#### `INVALID_CREDENTIALS`
**When**: Wrong username/password provided
**Example**:
```json
{
  "error": "Invalid credentials",
  "error_code": "INVALID_CREDENTIALS",
  "details": "Authentication rejected by GNS3 server",
  "suggested_action": "Verify username and password are correct"
}
```
**How to fix**: Correct username/password in configuration

---

### Internal Errors (500-style)

Server-side errors and generic failures.

#### `INTERNAL_ERROR`
**When**: Unexpected server error
**Example**:
```json
{
  "error": "Internal server error",
  "error_code": "INTERNAL_ERROR",
  "details": "Unexpected exception: ...",
  "suggested_action": "Check server logs for details",
  "server_version": "0.20.0"
}
```
**How to fix**: Check MCP server logs, report issue if reproducible

---

#### `TIMEOUT`
**When**: Operation timed out
**Example**:
```json
{
  "error": "Operation timed out",
  "error_code": "TIMEOUT",
  "details": "Request exceeded 30 second timeout",
  "suggested_action": "Retry operation or increase timeout"
}
```
**How to fix**: Retry operation, check GNS3 server performance

---

#### `OPERATION_FAILED`
**When**: Generic operation failure
**Example**:
```json
{
  "error": "Failed to create node from template 'Cisco IOSv'",
  "error_code": "OPERATION_FAILED",
  "details": "Template instantiation failed: insufficient resources",
  "suggested_action": "Verify template exists, GNS3 server is accessible, and position coordinates are valid",
  "context": {
    "template_name": "Cisco IOSv",
    "x": 100,
    "y": 200,
    "exception": "insufficient resources"
  }
}
```
**How to fix**: Check error details and context for specific cause, verify GNS3 server resources

---

## Error Handling Best Practices

### 1. Always Check for Errors

```python
result = tool_call()
if "error" in result:
    error = json.loads(result)
    print(f"Error: {error['error']}")
    print(f"Code: {error['error_code']}")
    print(f"Fix: {error['suggested_action']}")
```

### 2. Use Error Codes for Logic

```python
if error["error_code"] == "NODE_NOT_FOUND":
    # Try creating the node
    available = error["context"]["available_nodes"]
elif error["error_code"] == "PORT_IN_USE":
    # Disconnect existing link first
    link_id = error["context"].get("link_id")
```

### 3. Leverage Context for Debugging

```python
# Context provides debugging information
context = error["context"]
print(f"Project ID: {context.get('project_id')}")
print(f"Node name: {context.get('node_name')}")
print(f"Available options: {context.get('available_nodes')}")
```

### 4. Follow Suggested Actions

```python
# suggested_action provides actionable fix
print(error["suggested_action"])
# "Use list_nodes() to see all available nodes in the project"
```

### 5. Version Tracking

```python
# server_version helps with compatibility
if error["server_version"] != "0.20.0":
    print("Warning: Server version mismatch")
```

## Common Error Workflows

### Workflow 1: Creating a Link

```python
# 1. Check if port is already in use
result = set_connection([{"action": "connect", ...}])
if "error" in result:
    error = json.loads(result)
    if error["error_code"] == "PORT_IN_USE":
        # 2. Disconnect existing link
        link_id = error["context"]["link_id"]
        set_connection([{"action": "disconnect", "link_id": link_id}])
        # 3. Retry connection
        result = set_connection([{"action": "connect", ...}])
```

### Workflow 2: Modifying Node Properties

```python
# 1. Try to modify node
result = set_node("Router1", name="NewName")
if "error" in result:
    error = json.loads(result)
    if error["error_code"] == "NODE_RUNNING":
        # 2. Stop node first
        set_node("Router1", action="stop")
        # 3. Modify properties
        set_node("Router1", name="NewName")
        # 4. Restart node
        set_node("Router1", action="start")
```

### Workflow 3: Finding Available Resources

```python
# 1. Try operation
result = create_node("Wrong Template", x=100, y=100)
if "error" in result:
    error = json.loads(result)
    if error["error_code"] == "TEMPLATE_NOT_FOUND":
        # 2. Check available templates from context
        available = error["context"]["available_templates"]
        print(f"Available: {', '.join(available)}")
        # 3. Use correct template
        create_node(available[0], x=100, y=100)
```

---

**Version**: 0.20.0
**Date**: 2025-10-25
**Total Error Codes**: 26
