---
name: gns3-lab-automation
description: GNS3 network lab operations including topology management, device configuration via console, and troubleshooting workflows for routers and switches
---

# GNS3 Lab Automation Skill

## Overview

GNS3 (Graphical Network Simulator-3) is a network emulation platform for building complex network topologies. This skill provides knowledge for automating GNS3 lab operations through the MCP server.

## Core Concepts

### MCP Resources (v0.13.0 - NEW)

**MCP resources provide browsable state** via standardized URIs, replacing query tools for better IDE integration.

**Resource Benefits:**
- Browsable in MCP-aware tools (inspectors, IDEs)
- Automatic discovery and autocomplete
- Consistent URI scheme (`gns3://` protocol)
- Better performance with resource subscriptions

**Available Resources:**

**Project Resources:**
- `gns3://projects/` - List all GNS3 projects
- `gns3://projects/{project_id}` - Get project details by ID
- `gns3://projects/{project_id}/nodes/` - List nodes in project (NodeSummary)
- `gns3://projects/{project_id}/nodes/{node_id}` - Get node details (full NodeInfo)
- `gns3://projects/{project_id}/links/` - List network links in project
- `gns3://projects/{project_id}/templates/` - List available templates
- `gns3://projects/{project_id}/drawings/` - List drawing objects

**Console Session Resources:**
- `gns3://sessions/console/` - List all active console sessions
- `gns3://sessions/console/{node_name}` - Get console session status for node

**SSH Session Resources:**
- `gns3://sessions/ssh/` - List all active SSH sessions
- `gns3://sessions/ssh/{node_name}` - Get SSH session status for node
- `gns3://sessions/ssh/{node_name}/history` - Get SSH command history
- `gns3://sessions/ssh/{node_name}/buffer` - Get SSH continuous buffer

**SSH Proxy Resources:**
- `gns3://proxy/status` - Get SSH proxy service status
- `gns3://proxy/sessions` - List all SSH proxy sessions

**Resource vs Tool Usage:**
- **Resources**: Query state (read-only) - use for browsing, monitoring
- **Tools**: Modify state (actions) - use for changes, commands, configuration

**Example Resource Workflow:**
```
# Browse resources (read-only)
1. List all projects: gns3://projects/
2. Pick project ID from list
3. View nodes: gns3://projects/{id}/nodes/
4. Check SSH session: gns3://sessions/ssh/R1

# Use tools to modify (actions)
5. Call configure_ssh() to create SSH session
6. Call ssh_send_command() to execute commands
7. Call set_node() to change node state
```

**Removed in v0.14.0 (use MCP resources instead):**
- `list_projects()` → Use resource `gns3://projects`
- `list_nodes()` → Use resource `gns3://projects/{id}/nodes`
- `get_node_details()` → Use resource `gns3://projects/{id}/nodes/{id}`
- `get_links()` → Use resource `gns3://projects/{id}/links`
- `list_templates()` → Use resource `gns3://projects/{id}/templates`
- `list_drawings()` → Use resource `gns3://projects/{id}/drawings`
- `get_console_status()` → Use resource `gns3://sessions/console/{node}`
- `ssh_get_status()` → Use resource `gns3://sessions/ssh/{node}`
- `ssh_get_history()` → Use resource `gns3://sessions/ssh/{node}/history`
- `ssh_get_command_output()` → Use resource with filtering
- `ssh_read_buffer()` → Use resource `gns3://sessions/ssh/{node}/buffer`

**Final Architecture (v0.20.0):**
- **20 Action Tools**: Modify state (create, delete, configure, execute commands)
- **17 MCP Resources**: Browse state (projects, nodes, sessions, status, snapshots)
- **4 MCP Prompts**: Guided workflows (ssh_setup, topology_discovery, troubleshooting, lab_setup)
- **Clear separation**: Tools change things, Resources view things, Prompts guide workflows

### Projects
- **Projects** are isolated network topologies with their own nodes, links, and configuration
- Projects have status: `opened` or `closed`
- Always ensure a project is opened before working with nodes
- Use `open_project()` to activate a project

### Nodes
- **Nodes** represent network devices (routers, switches, servers, etc.)
- Node types: `qemu` (VMs), `docker` (containers), `ethernet_switch`, `nat`, etc.
- Node status: `started` or `stopped`
- Each node has a unique `node_id` and human-readable `name`

### Choosing Between SSH and Console Tools

**IMPORTANT: Always prefer SSH tools when available!**

**Use SSH Tools For:**
- Production automation workflows
- Configuration management
- Command execution on network devices
- Better reliability with automatic prompt detection
- Structured output and error handling
- Available SSH tools: `ssh_send_command()`, `ssh_send_config_set()`, `ssh_read_buffer()`, `ssh_get_history()`

**Use Console Tools Only For:**
- **Initial device configuration** (enabling SSH, creating users, generating keys)
- **Troubleshooting** when SSH is unavailable or broken
- **Devices without SSH support** (VPCS, simple switches)
- Interactive TUI navigation (vim, menu systems)

**Typical Workflow:**
1. Start with console tools to configure SSH access
2. Establish SSH session with `configure_ssh()`
3. Switch to SSH tools for all automation
4. Return to console only if SSH fails

### Error Responses

**All tools return standardized error responses** (v0.20.0) with machine-readable error codes and actionable guidance.

**Error Response Structure:**
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

**Error Code Categories:**

**Resource Not Found (404-style):**
- `PROJECT_NOT_FOUND` - No project open or project doesn't exist
- `NODE_NOT_FOUND` - Node name not found in project
- `LINK_NOT_FOUND` - Link ID doesn't exist
- `TEMPLATE_NOT_FOUND` - Template name not available
- `DRAWING_NOT_FOUND` - Drawing ID not found
- `SNAPSHOT_NOT_FOUND` - Snapshot name doesn't exist

**Validation Errors (400-style):**
- `INVALID_PARAMETER` - Invalid parameter value
- `MISSING_PARAMETER` - Required parameter not provided
- `PORT_IN_USE` - Port already connected to another node
- `NODE_RUNNING` - Operation requires node to be stopped
- `NODE_STOPPED` - Operation requires node to be running
- `INVALID_ADAPTER` - Adapter name/number not valid for node
- `INVALID_PORT` - Port number exceeds adapter capacity

**Connection Errors (503-style):**
- `GNS3_UNREACHABLE` - Cannot connect to GNS3 server
- `GNS3_API_ERROR` - GNS3 server API error
- `CONSOLE_DISCONNECTED` - Console session lost
- `CONSOLE_CONNECTION_FAILED` - Failed to connect to console
- `SSH_CONNECTION_FAILED` - Failed to establish SSH session
- `SSH_DISCONNECTED` - SSH session lost

**Authentication Errors (401-style):**
- `AUTH_FAILED` - Authentication failed
- `TOKEN_EXPIRED` - JWT token expired
- `INVALID_CREDENTIALS` - Wrong username/password

**Internal Errors (500-style):**
- `INTERNAL_ERROR` - Server internal error
- `TIMEOUT` - Operation timed out
- `OPERATION_FAILED` - Generic operation failure

**Example Error Handling:**
```python
# Attempt to start a node
result = set_node("Router1", action="start")

# Check for errors
if "error" in result:
    error = json.loads(result)
    if error["error_code"] == "NODE_NOT_FOUND":
        # Use suggested_action to fix
        print(error["suggested_action"])  # "Use list_nodes() to see all available nodes"
        # Check available nodes from context
        print(error["context"]["available_nodes"])  # ["Router2", "Router3", "Switch1"]
    elif error["error_code"] == "GNS3_UNREACHABLE":
        # Server connection issue
        print(f"Cannot reach GNS3 at {error['context']['host']}:{error['context']['port']}")
```

**Common Error Scenarios:**

1. **No project open**: Most tools require an open project
   - Error: `PROJECT_NOT_FOUND`
   - Fix: `open_project("ProjectName")`

2. **Node not found**: Typo in node name (case-sensitive)
   - Error: `NODE_NOT_FOUND`
   - Fix: Check available_nodes in error context or use resource `gns3://projects/{id}/nodes/`

3. **Port already in use**: Trying to connect already-connected port
   - Error: `PORT_IN_USE`
   - Fix: Disconnect existing link first with `set_connection([{"action": "disconnect", "link_id": "..."}])`

4. **Node must be stopped**: Trying to modify running node properties
   - Error: `NODE_RUNNING`
   - Fix: `set_node("NodeName", action="stop")` then retry

### Tool Annotations (v0.19.0)

**MCP tool annotations** provide metadata to IDE/MCP clients for better UX and safety.

**destructive** (3 tools):
- `delete_node`, `restore_snapshot`, `delete_drawing`
- IDE may show warnings or require confirmation
- These operations delete data or make irreversible changes
- **Always create backups before using destructive tools**

**idempotent** (9 tools):
- `open_project`, `create_project`, `close_project`, `set_node`
- `console_disconnect`, `ssh_configure`, `ssh_disconnect`
- `update_drawing`, `export_topology_diagram`
- Safe to retry - same operation produces same result
- Example: Opening already-opened project is safe

**read_only** (1 tool):
- `console_read`
- Tool only reads data, makes no state changes
- May be cached by MCP clients

**creates_resource** (5 tools):
- `create_project`, `create_node`, `create_snapshot`
- `export_topology_diagram`, `create_drawing`
- Tool creates new resources (in GNS3 or filesystem)

**modifies_topology** (3 tools):
- `set_connection`, `create_node`, `delete_node`
- Tool changes network topology structure
- May require project reload in GNS3 GUI

### Console Access
- Nodes have **console** ports for CLI access
- Console types:
  - `telnet`: CLI access (most routers/switches) - currently supported
  - `vnc`: Graphical access (desktops/servers) - not yet supported
  - `spice+agent`: Enhanced graphical - not yet supported
  - `none`: No console
- **Auto-connect workflow** (v0.2.0):
  1. Just use `send_console(node_name, command)` - automatically connects if needed
  2. Read output with `read_console(node_name)` - returns new output since last read (diff mode, default since v0.9.0)
  3. Or use `read_console(node_name, mode="last_page")` for last ~25 lines
  4. Or use `read_console(node_name, mode="all")` for full buffer
  5. Disconnect with `disconnect_console(node_name)` when done
- Sessions are managed automatically by node name
- Session timeout: 30 minutes of inactivity

### Coordinate System and Topology Layout

GNS3 uses a specific coordinate system for positioning elements:

**Node Positioning:**
- Node coordinates (x, y) represent the **top-left corner** of the node icon
- Icon sizes:
  - **PNG images**: 78×78 pixels (custom device icons)
  - **SVG/internal icons**: 58×58 pixels (built-in icons)
- Node center is at `(x + icon_size/2, y + icon_size/2)`
- Example: Node at (100, 100) with PNG icon has center at (139, 139)

**Label Positioning:**
- Node labels are stored as **offsets from node top-left to label box top-left**
- GNS3 API returns: `label: {x: -10, y: -25, text: "Router1", rotation: 0, style: "..."}`
- The offset (x, y) represents: node_top_left → label_box_top_left
- Label box contains text that is **right-aligned and vertically centered** within the box
- Text alignment: `text-anchor: end; dominant-baseline: central`

**Link Connections:**
- Links connect to the **center** of nodes, not the top-left corner
- Connection point: `(node_x + icon_size/2, node_y + icon_size/2)`
- When using `set_connection()`, specify which adapter and port on each node

**Drawing Objects (v0.8.0 - Unified create_drawing):**
- Create drawings with `create_drawing(drawing_type, x, y, ...)` where type is "rectangle", "ellipse", "line", or "text"
- All drawing coordinates (x, y) represent the **top-left corner** of bounding box
- **Rectangle**: `create_drawing("rectangle", x, y, width=W, height=H, fill_color="#fff", border_color="#000")`
- **Ellipse**: `create_drawing("ellipse", x, y, rx=50, ry=30, fill_color="#fff", border_color="#000")`
- **Line**: `create_drawing("line", x, y, x2=100, y2=50, border_color="#000", border_width=2)` - ends at (x+x2, y+y2)
- **Text**: `create_drawing("text", x, y, text="Label", font_size=10, color="#000", font_weight="normal")`
- Z-order: 0 = behind nodes (backgrounds), 1 = in front of nodes (labels)

**Topology Export:**
- Use `export_topology_diagram()` to create SVG/PNG screenshots
- Renders nodes with actual icons, links, drawings, and labels
- All positioning respects the coordinate system above
- Output includes:
  - Visual status indicators on nodes (started=green, stopped=red)
  - Port status indicators on links (active=green circles, shutdown=red circles)
  - Preserved fonts and styling from GNS3

**Layout Best Practices:**
- **Minimum spacing** to avoid overlaps:
  - Horizontal: 150-200px between node icons
  - Vertical: 100-150px between node icons
  - Site rectangles: 250-350px wide, 200-300px tall
  - Padding around elements: 50px minimum
- **Site organization**:
  - Place background rectangles at z=0 (behind nodes)
  - Place site labels at z=1 (in front of rectangles)
  - Position site labels 30px above rectangle top edge
  - Center nodes within site rectangles for clean layout
- **Node positioning**:
  - PNG icons (78×78): Need more spacing than SVG icons (58×58)
  - Account for label width when positioning adjacent nodes
  - Estimated label width: `text_length * font_size * 0.6`
- **Connection planning**:
  - Consider link paths when positioning nodes
  - Avoid crossing links where possible for clarity
  - Star topologies: Central node with radial connections
  - Mesh topologies: Triangular or grid layouts work best

## Common Workflows

### Starting a Lab Environment

```
1. List projects to find your lab
2. Open the target project
3. List nodes to see topology
4. Start nodes in order (usually: core switches → routers → endpoints)
5. Wait ~30-60s for devices to boot
6. Verify status with list_nodes
```

### Configuring a Router via Console

```
1. Ensure node is started (use set_node if needed)
2. Send initial newline to wake console: send_console("Router1", "\n")
3. Read output to see prompt: read_console("Router1")
4. Send configuration commands one at a time
5. Always read output after each command to verify
6. Default behavior (v0.8.0): returns only new output since last read
7. Disconnect when done: disconnect_console("Router1")
```

**Example:**
```
send_console("R1", "\n")
read_console("R1")  # See prompt (diff mode default since v0.9.0)
send_console("R1", "show ip interface brief\n")
read_console("R1")  # See command output (only new lines)
disconnect_console("R1")  # Clean up when done
```

### Using send_and_wait_console for Automation

For automated workflows, `send_and_wait_console()` simplifies command execution by waiting for specific prompts:

```
Workflow:
1. First, identify the prompt pattern
   - Send \n and read output to see what prompt looks like
   - Note the exact prompt: "Router#", "[admin@MikroTik] >", "switch>", etc.

2. Use the prompt pattern in automated commands
   - send_and_wait_console(node, command, wait_pattern=<prompt>)
   - Tool waits until prompt appears, then returns all output

3. No need to manually wait or read - tool handles timing
```

**Example - Automated configuration:**
```
# Step 1: Identify the prompt
send_console("R1", "\n")
output = read_console("R1")  # Output shows "Router#"

# Step 2: Use prompt pattern for automation
result = send_and_wait_console("R1",
    "show ip interface brief\n",
    wait_pattern="Router#",
    timeout=10)
# Returns when "Router#" appears - command is complete

# Step 3: Continue with more commands
result = send_and_wait_console("R1",
    "configure terminal\n",
    wait_pattern="Router\\(config\\)#",  # Prompt changes in config mode
    timeout=10)
```

**When to use send_and_wait_console:**
- Automated scripts where you know the expected prompts
- Long-running commands that need completion confirmation
- Interactive menus where you need to wait for specific text

**When to use send_console + read_console:**
- Interactive troubleshooting where prompts may vary
- Exploring unknown device states
- When you need fine-grained control over timing

### Console Best Practices

- **Always** read console output after sending commands
- **Wait** 1-2 seconds between commands for device processing
- **Send** `\n` (newline) first to wake up console
- **Look for** prompts (>, #) in output to confirm device is ready
- **Default behavior** (v0.9.0): `read_console()` returns only new output since last read (diff mode)
- **Last page mode**: Use `read_console(node, mode="last_page")` for last ~25 lines
- **Full buffer**: Use `read_console(node, mode="all")` for entire console history
- **Before using send_and_wait_console()**: First check what the prompt looks like with `read_console()`
  - Different devices have different prompts: `Router#`, `[admin@MikroTik] >`, `switch>`, etc.
  - Use the exact prompt pattern in `wait_pattern` parameter to ensure command completion
  - Example: Send `\n`, read output to see `Router#`, then use `wait_pattern="Router#"` for commands
  - This prevents missing output or waiting for wrong prompt
- **No need** to manually connect - auto-connects on first send/read
- **Disconnect** when done to free resources (30min timeout otherwise)
- For RouterOS (MikroTik): default user `admin`, empty password
- For Arista vEOS: default user `admin`, no password

### Troubleshooting Connectivity

```
1. Check node status (all started?)
2. Verify console access (can you connect?)
3. Check interfaces: send "show ip interface brief" or equivalent
4. Check routing: send "show ip route"
5. Test ping: send "ping <target_ip>"
6. Read output after each command
```

## MCP Prompts - Guided Workflows (v0.17.0)

**MCP prompts** provide step-by-step guidance for complex multi-step operations.

### Available Prompts

**ssh_setup** - Device-Specific SSH Configuration
- Covers 6 device types: Cisco IOS, NX-OS, MikroTik, Juniper, Arista, Linux
- Step-by-step instructions from console configuration to SSH session establishment
- Device-specific commands with parameter placeholders
- Troubleshooting guidance for common SSH issues

Usage:
```
Call the ssh_setup prompt with device_type parameter
Example: ssh_setup(device_type="cisco_ios", node_name="R1")
```

**topology_discovery** - Network Topology Discovery and Visualization
- Guides through using MCP resources to browse projects/nodes/links
- Instructions for `export_topology_diagram` tool usage
- Topology pattern analysis (hub-and-spoke, mesh, tiered, etc.)
- Common topology questions to answer during discovery

Usage:
```
Call the topology_discovery prompt to start guided discovery
The prompt walks through resource browsing and diagram export
```

**troubleshooting** - OSI Model-Based Systematic Troubleshooting
- Layer 1-7 troubleshooting methodology
- Common issues and resolutions for each layer
- Console and SSH troubleshooting workflows
- Performance analysis and log collection

Usage:
```
Call the troubleshooting prompt for systematic diagnosis
Example: troubleshooting(node_name="R1", issue="connectivity")
```

**lab_setup** - Automated Topology Creation (v0.18.0)
- Creates complete topologies with single command
- 6 topology types: star, mesh, linear, ring, OSPF, BGP
- Automatic node positioning using layout algorithms
- IP addressing schemes

Topology types:
- **star**: Hub-and-spoke (parameter: spoke_count)
- **mesh**: Full mesh (parameter: router_count)
- **linear**: Chain topology (parameter: router_count)
- **ring**: Circular topology (parameter: router_count)
- **ospf**: Multi-area OSPF (parameter: area_count, 3 routers per area)
- **bgp**: Multiple AS (parameter: AS_count, 2 routers per AS)

Usage:
```
Call the lab_setup prompt with topology_type and device_count
Example: lab_setup(topology_type="ospf", device_count=3)
```

## SSH Automation (v0.12.0)

SSH automation via Netmiko for advanced device management. Requires SSH proxy container deployed to GNS3 host.

### Prerequisites

SSH must be enabled on device first using console tools:

**Cisco IOS:**
```
send_console('R1', 'configure terminal\n')
send_console('R1', 'username admin privilege 15 secret cisco123\n')
send_console('R1', 'crypto key generate rsa modulus 2048\n')
send_console('R1', 'ip ssh version 2\n')
send_console('R1', 'line vty 0 4\n')
send_console('R1', 'login local\n')
send_console('R1', 'transport input ssh\n')
send_console('R1', 'end\n')
```

**MikroTik RouterOS:**
```
send_console('MT1', '/user add name=admin password=admin123 group=full\n')
send_console('MT1', '/ip service enable ssh\n')
```

### Basic SSH Workflow

**1. Configure SSH Session:**
```
configure_ssh('R1', {
    'device_type': 'cisco_ios',
    'host': '10.10.10.1',
    'username': 'admin',
    'password': 'cisco123'
})
```

**2. Execute Commands:**
```
# Show commands
ssh_send_command('R1', 'show ip interface brief')
ssh_send_command('R1', 'show running-config')

# Configuration commands
ssh_send_config_set('R1', [
    'interface GigabitEthernet0/0',
    'ip address 192.168.1.1 255.255.255.0',
    'no shutdown'
])
```

**3. Review History:**
```
# List recent commands
ssh_get_history('R1', limit=10)

# Search history
ssh_get_history('R1', search='interface')

# Get specific command output
ssh_get_command_output('R1', job_id='...')
```

### Adaptive Async for Long Commands

For long-running operations (firmware upgrades, backups):

```
# Start command, return job_id immediately
result = ssh_send_command('R1', 'copy running-config tftp:', wait_timeout=0)
job_id = result['job_id']

# Poll for completion
status = ssh_get_job_status(job_id)
# Returns: {completed, output, execution_time}

# For 15+ minute commands:
ssh_send_command('R1', 'upgrade firmware', read_timeout=900, wait_timeout=0)
```

### Supported Device Types

200+ device types via Netmiko:
- **cisco_ios** - Cisco IOS/IOS-XE
- **cisco_nxos** - Cisco Nexus
- **juniper** - Juniper JunOS
- **arista_eos** - Arista EOS
- **mikrotik_routeros** - MikroTik RouterOS
- **linux** - Linux/Alpine
- See Netmiko documentation for complete list

### SSH Best Practices

- **Enable SSH first** using console tools
- **Use job history** for audit trails and debugging
- **Set wait_timeout=0** for long commands to avoid blocking
- **Poll with ssh_get_job_status()** for async operations
- **Review ssh_get_history()** to verify command execution
- **Clean sessions** with ssh_cleanup_sessions() when changing lab topology
- **Check status** with ssh_get_status() to verify connection before commands

## Device-Specific Commands

### MikroTik RouterOS
- Login prompt: `Login:` → send `admin\n`
- Password: just press enter (empty)
- Prompt: `[admin@MikroTik] >`
- Show interfaces: `/interface print`
- Show IP addresses: `/ip address print`
- Show routes: `/ip route print`

### Arista vEOS
- Login: `admin` (no password)
- Prompt: `switch>`
- Enable mode: `enable` → `switch#`
- Show interfaces: `show interfaces status`
- Show IP: `show ip interface brief`
- Config mode: `configure terminal`

### Cisco IOS (CSR1000v, IOSv)
- Prompt: `Router>` (user mode), `Router#` (privileged)
- Enable: `enable`
- Show interfaces: `show ip interface brief`
- Show routes: `show ip route`
- Config: `configure terminal`

## Error Handling

### Node Won't Start
- Check node details for errors
- Verify compute resources available
- Some nodes (Windows) take 5+ minutes to boot

### Console Not Responding
- Check node is actually started
- Try sending `\n` or `\r\n` to wake console
- Some consoles have startup delay (30-60s after node start)

### Session Timeout
- Console sessions expire after 30 minutes of inactivity
- Always disconnect when done to free resources
- Sessions managed by node_name (no manual tracking needed)

## Multi-Node Operations

When working with multiple nodes:
1. Start nodes using `set_node(node_name, action='start')` or batch operations
2. Console sessions identified by node_name (no manual tracking needed)
3. Configure one device at a time, verify before moving on
4. Read output to get only new lines (diff mode default since v0.8.0) - avoids confusion between devices
5. Disconnect sessions when done: `disconnect_console(node_name)`

**Example - Configure multiple routers:**
```
# Start all routers
set_node("R1", action="start")
set_node("R2", action="start")

# Configure R1
send_console("R1", "\n")
read_console("R1")  # Diff mode default - only new output
send_console("R1", "configure terminal\n")
read_console("R1")  # Only new output since last read
# ... more commands ...
disconnect_console("R1")

# Configure R2 (same pattern)
send_console("R2", "\n")
# ... configure R2 ...
disconnect_console("R2")
```

## Managing Network Connections

### Link Management with set_connection

Use `set_connection(connections)` for batch link operations. Operations execute sequentially (top-to-bottom) with predictable state on failure.

**Connection Format:**
```python
connections = [
    # Disconnect a link
    {"action": "disconnect", "link_id": "abc123"},

    # Connect two nodes (using adapter names - recommended)
    {"action": "connect",
     "node_a": "R1", "adapter_a": "eth0", "port_a": 0,
     "node_b": "R2", "adapter_b": "GigabitEthernet0/0", "port_b": 1},

    # Or using adapter numbers (legacy)
    {"action": "connect",
     "node_a": "R1", "adapter_a": 0, "port_a": 0,
     "node_b": "R2", "adapter_b": 0, "port_b": 1}
]
```

**Adapter Names vs Numbers:**
- **Adapter names** (recommended): Use port names like "eth0", "GigabitEthernet0/0", "Ethernet0"
- **Adapter numbers** (legacy): Use numeric adapter index (0, 1, 2, ...)
- Response always shows **both**: `"adapter_a": 0, "port_a_name": "eth0"`

**Returns:**
```json
{
  "completed": [
    {"index": 0, "action": "disconnect", "link_id": "abc123"},
    {"index": 1, "action": "connect", "link_id": "new-id",
     "node_a": "R1", "node_b": "R2",
     "adapter_a": 0, "port_a": 0, "port_a_name": "eth0",
     "adapter_b": 0, "port_b": 1, "port_b_name": "GigabitEthernet0/0"}
  ],
  "failed": null
}
```

**Best Practices:**
- **Always** call `get_links()` first to check current topology and see port names
- Use **adapter names** for readability (e.g., "eth0" instead of 0)
- Get link IDs from output (in brackets) for disconnection
- Disconnect existing links before connecting to occupied ports
- Operations stop at first failure for predictable state

**Example - Rewire topology:**
```python
# 1. Check current topology
get_links()
# Output shows port names: eth0, GigabitEthernet0/0, etc.

# 2. Disconnect old link and create new one (using port names)
set_connection([
    {"action": "disconnect", "link_id": "abc-123"},
    {"action": "connect",
     "node_a": "R1", "adapter_a": "eth0", "port_a": 0,
     "node_b": "Switch1", "adapter_b": "Ethernet3", "port_b": 3}
])
```

## Node Positioning & Configuration

### Unified Node Control with set_node

Use `set_node(node_name, ...)` for both control and configuration:

**Control Actions:**
- `action="start"` - Start the node
- `action="stop"` - Stop the node
- `action="suspend"` - Suspend node (VM only)
- `action="reload"` - Reload node
- `action="restart"` - Stop, wait (3 retries × 5s), then start

**Configuration Properties:**
- `x`, `y` - Position on canvas
- `z` - Z-order (layer) for overlapping nodes
- `locked` - Lock position (True/False)
- `ports` - Number of ports (ethernet switches only)

**Examples:**
```python
# Start a node
set_node("R1", action="start")

# Restart with retry logic
set_node("R1", action="restart")  # Waits for clean stop

# Move and lock position
set_node("R1", x=100, y=200, locked=True)

# Configure switch ports
set_node("Switch1", ports=16)

# Combined operation
set_node("R1", action="start", x=150, y=300)
```

**Restart Behavior:**
- Stops node and polls status (3 attempts × 5 seconds)
- Waits for confirmed stop before starting
- Returns all retry attempts in result
- Use for nodes that need clean restart

## Snapshot Management (v0.18.0)

Snapshots capture complete project state for version control and rollback.

### Creating Snapshots

Before major changes, create a snapshot for safe rollback:

**Workflow:**
1. Stop all running nodes (optional but recommended for consistency)
2. Create snapshot with descriptive name
3. Make your changes
4. If issues occur, restore to snapshot

**Example:**
```
create_snapshot("Before OSPF Configuration",
                "Working baseline before adding OSPF")
```

**Best Practices:**
- Use descriptive names with dates: "2025-10-26 Working OSPF Config"
- Stop nodes before snapshot for consistent state
- Document what each snapshot represents
- Create snapshots at major milestones

### Restoring Snapshots

Rollback to previous state (⚠️ **DESTRUCTIVE** - all changes since snapshot are lost):

**Restore Process:**
1. Call `restore_snapshot("snapshot_name")`
2. Tool automatically:
   - Stops all running nodes
   - Disconnects all console sessions
   - Restores project to snapshot state
3. All changes since snapshot are permanently lost

**Example:**
```
restore_snapshot("Before OSPF Configuration")
```

**Warning:** Destructive operation - creates backup before testing restore procedure.

### Browsing Snapshots

List available snapshots via resource:
```
gns3://projects/{project_id}/snapshots/
```

View snapshot details:
```
gns3://projects/{project_id}/snapshots/{snapshot_id}
```

## Lab Setup Automation (v0.18.0)

Use `lab_setup` prompt to create complete topologies automatically.

### Creating a Lab

The lab_setup prompt creates:
- Nodes positioned using layout algorithms
- Network links between nodes
- IP addressing schemes
- Complete topology diagrams

### Topology Types

**Star Topology** (Hub-and-Spoke):
```
lab_setup(topology_type="star", device_count=4)
```
- Creates: 1 hub router + 4 spoke routers
- Links: Hub-to-each-spoke
- IP: 10.0.{spoke}.0/24 per link

**Mesh Topology** (Full Mesh):
```
lab_setup(topology_type="mesh", device_count=4)
```
- Creates: 4 routers, all interconnected
- Links: N*(N-1)/2 point-to-point links
- IP: 10.0.{subnet}.0/30 per link

**Linear Topology** (Chain):
```
lab_setup(topology_type="linear", device_count=4)
```
- Creates: 4 routers in series (R1-R2-R3-R4)
- Links: Sequential connections
- IP: 10.0.{link}.0/30

**Ring Topology** (Circular):
```
lab_setup(topology_type="ring", device_count=4)
```
- Creates: 4 routers in a ring
- Links: Each router connects to two neighbors
- Closes the loop for redundancy

**OSPF Topology** (Multi-Area):
```
lab_setup(topology_type="ospf", device_count=3)
```
- Creates: 3 areas with Area 0 backbone
- Nodes: 3 routers per area + ABRs
- IP: 10.{area}.0.{router}/32 loopbacks

**BGP Topology** (Multiple AS):
```
lab_setup(topology_type="bgp", device_count=3)
```
- Creates: 3 autonomous systems
- Nodes: 2 routers per AS (iBGP peering)
- Links: eBGP between adjacent AS
- IP: 10.{AS}.1.0/30 (iBGP), 172.16.{link}.0/30 (eBGP)

### Customizing Labs

**Parameters:**
- `topology_type`: Required topology type (star/mesh/linear/ring/ospf/bgp)
- `device_count`: Number of devices/areas/AS (topology-specific)
- `template_name`: Device template (default: "Alpine Linux")
- `project_name`: Target project (uses current if not specified)

**Example:**
```
lab_setup("ospf", device_count=2,
          template_name="Cisco IOSv",
          project_name="OSPF Lab")
```

## Drawing Tools (v0.19.0 - Hybrid Architecture)

Create visual annotations on topology diagrams using drawing tools.

**Hybrid Pattern:**
- **READ**: Browse drawings via resource `gns3://projects/{id}/drawings/`
- **WRITE**: Modify drawings via tools (create_drawing, update_drawing, delete_drawing)

### Available Drawing Types

**Rectangle** - For site boundaries, network segments
```
create_drawing("rectangle", x=100, y=100, width=300, height=200,
               fill_color="#f0f0f0", border_color="#000000", z=0)
```

**Ellipse** - For cloud/WAN representations, circles
```
create_drawing("ellipse", x=200, y=200, rx=50, ry=50,
               fill_color="#ffffff", border_color="#0000ff", z=0)
```

**Line** - For connections, arrows, dividers
```
create_drawing("line", x=100, y=100, x2=200, y2=150,
               color="#ff0000", border_width=3, z=1)
```

**Text** - For labels, site names, annotations
```
create_drawing("text", x=150, y=50, text="Data Center A",
               font_size=14, font_weight="bold", color="#000000", z=1)
```

### Updating Drawings

Modify drawing properties:
```
update_drawing(drawing_id="abc123", x=120, y=80, rotation=45)
```

### Deleting Drawings

Remove drawing (⚠️ **DESTRUCTIVE**):
```
delete_drawing(drawing_id="abc123")
```

### Z-order Layers

- `z=0`: Background shapes (behind nodes)
- `z=1`: Foreground labels and annotations
- Higher z values appear in front

## Automation Tips

- **Always check status** before operations (is node started? is project open?)
- **Read before write** to console (check current state first)
- **Verify each step** before proceeding (don't assume success)
- **Handle errors gracefully** (node might not start immediately)
- **Clean up** console sessions when done
- **Use set_node** for node lifecycle operations (replaces start/stop)
- **Use set_connection** for topology changes (batch operations)

## Example Workflows

See `examples/` folder for:
- `ospf_lab.md` - Setting up OSPF routing between routers
- `bgp_lab.md` - Configuring BGP peering
- Common troubleshooting procedures
