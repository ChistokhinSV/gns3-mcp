---
name: gns3-lab-automation
description: GNS3 network lab operations including topology management, device configuration via console, and troubleshooting workflows for routers and switches
---

# GNS3 Lab Automation Skill

## Overview

GNS3 (Graphical Network Simulator-3) is a network emulation platform for building complex network topologies. This skill provides knowledge for automating GNS3 lab operations through the MCP server.

## Core Concepts

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

### Console Access
- Nodes have **console** ports for CLI access
- Console types:
  - `telnet`: CLI access (most routers/switches) - currently supported
  - `vnc`: Graphical access (desktops/servers) - not yet supported
  - `spice+agent`: Enhanced graphical - not yet supported
  - `none`: No console
- **Auto-connect workflow** (v0.2.0):
  1. Just use `send_console(node_name, command)` - automatically connects if needed
  2. Read output with `read_console(node_name)` for full buffer
  3. Or use `read_console(node_name, diff=True)` for new output only
  4. Disconnect with `disconnect_console(node_name)` when done
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

**Drawing Objects (Rectangles, Text, Ellipses):**
- All drawing coordinates (x, y) represent the **top-left corner** of bounding box
- Rectangle at (100, 100) with 200×100 size: top-left at (100, 100), bottom-right at (300, 200)
- Ellipse at (100, 100) with rx=50, ry=30: bounding box top-left at (100, 100), center at (150, 130)
- Text at (100, 100): starts rendering from that point
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
3. Read output to see prompt: read_console("Router1", diff=True)
4. Send configuration commands one at a time
5. Always read output after each command to verify
6. Use diff=True to see only new output
7. Disconnect when done: disconnect_console("Router1")
```

**Example:**
```
send_console("R1", "\n")
read_console("R1", diff=True)  # See prompt
send_console("R1", "show ip interface brief\n")
read_console("R1", diff=True)  # See command output
disconnect_console("R1")  # Clean up when done
```

### Console Best Practices

- **Always** read console output after sending commands
- **Wait** 1-2 seconds between commands for device processing
- **Send** `\n` (newline) first to wake up console
- **Look for** prompts (>, #) in output to confirm device is ready
- **Use** `diff=True` parameter to see only new output since last read
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
4. Read output with `diff=True` to avoid confusion between devices
5. Disconnect sessions when done: `disconnect_console(node_name)`

**Example - Configure multiple routers:**
```
# Start all routers
set_node("R1", action="start")
set_node("R2", action="start")

# Configure R1
send_console("R1", "\n")
read_console("R1", diff=True)
send_console("R1", "configure terminal\n")
read_console("R1", diff=True)
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

    # Connect two nodes
    {"action": "connect", "node_a": "R1", "port_a": 0,
     "node_b": "R2", "port_b": 1}
]
```

**Returns:**
```json
{
  "completed": [
    {"index": 0, "action": "disconnect", "link_id": "abc123"},
    {"index": 1, "action": "connect", "link_id": "new-id",
     "node_a": "R1", "port_a": 0, "node_b": "R2", "port_b": 1}
  ],
  "failed": {
    "index": 2,
    "action": "connect",
    "reason": "Port already in use"
  }
}
```

**Best Practices:**
- **Always** call `get_links()` first to check current topology
- Get link IDs from output (in brackets) for disconnection
- Disconnect existing links before connecting to occupied ports
- Operations stop at first failure for predictable state
- Adapter 0 is used by default (suitable for most devices)

**Example - Rewire topology:**
```python
# 1. Check current topology
get_links()
# Output: Link [abc-123]: R1 port 0 <-> NAT1 port 0 (ethernet)
#         Link [def-456]: R2 port 0 <-> Switch1 port 1 (ethernet)

# 2. Disconnect old link and create new one
set_connection([
    {"action": "disconnect", "link_id": "abc-123"},
    {"action": "connect", "node_a": "R1", "port_a": 0,
     "node_b": "Switch1", "port_b": 3}
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
