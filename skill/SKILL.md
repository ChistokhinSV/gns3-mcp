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
  - `telnet`: CLI access (most routers/switches)
  - `vnc`: Graphical access (desktops/servers)
  - `spice+agent`: Enhanced graphical
  - `none`: No console
- Console workflow:
  1. Connect using `connect_console(node_name)` → get session_id
  2. Send commands with `send_console(session_id, command)`
  3. Read output with `read_console_diff(session_id)` for new output only
  4. Disconnect with `disconnect_console(session_id)`

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
1. Ensure node is started
2. Connect to console: connect_console("Router1")
3. Send initial command: send_console(session_id, "\n")
4. Read output to see prompt: read_console_diff(session_id)
5. Send configuration commands one at a time
6. Always read output after each command to verify
7. Disconnect when done
```

### Console Best Practices

- **Always** read console output after sending commands
- **Wait** 1-2 seconds between commands for device processing
- **Send** `\n` (newline) first to wake up console
- **Look for** prompts (>, #) in output to confirm device is ready
- **Use** `read_console_diff()` to avoid re-reading old output
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
- List sessions to see active connections

## Multi-Node Operations

When working with multiple nodes:
1. Start nodes in logical order
2. Use separate console sessions per device
3. Track session IDs carefully (store in conversation)
4. Configure one device at a time, verify before moving on
5. Disconnect sessions when done

## Automation Tips

- **Always check status** before operations (is node started? is project open?)
- **Read before write** to console (check current state first)
- **Verify each step** before proceeding (don't assume success)
- **Handle errors gracefully** (node might not start immediately)
- **Clean up** console sessions when done

## Example Workflows

See `examples/` folder for:
- `ospf_lab.md` - Setting up OSPF routing between routers
- `bgp_lab.md` - Configuring BGP peering
- Common troubleshooting procedures
