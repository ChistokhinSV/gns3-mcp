# GNS3 MCP Server Instructions

Network lab automation server with console access and SSH capabilities.

## Node Timing Requirements

**Critical**: Nodes require 30-60 seconds startup time after start command.

- **ALWAYS** wait for node status "started" before attempting console connection
- Use `set_node_properties()` with `action="start"` and wait for completion
- Attempting console access too early will fail with connection refused errors
- Progress notifications show startup progress (12 steps over 60 seconds) (v0.39.0)

**Example workflow**:
```
1. set_node_properties("R1", action="start")  # Wait for "started" status
2. Wait 5-10 additional seconds for console services to initialize
3. send_console_data("R1", "\n")  # Wake console
4. read_console_output("R1", mode="last_page")  # Check prompt
```

## Console Buffer Management

Console buffers accumulate **all output** since connection establishment.

**Best Practices**:
- Use `mode="diff"` in `read_console_output()` to get only new output since last read
- Use `mode="last_page"` to see current prompt without re-reading command history
- Use `mode="all"` sparingly - only when you need full command history
- Prevents AI from re-processing old command outputs and reduces token usage

**Buffer Modes**:
- `diff`: New output since last read (most efficient)
- `last_page`: Last 50 lines (good for checking prompts)
- `num_pages=N`: Last N pages of 50 lines each
- `all`: Entire buffer (expensive, use rarely)

**Example**:
```
send_console_data("R1", "show version\n")
# Wait 2 seconds
read_console_output("R1", mode="diff")  # Only shows command output
```

## Connection Management (v0.38.0)

Server implements non-blocking authentication with background reconnection.

**Key Behaviors**:
- Server starts in 3 seconds even when GNS3 unavailable
- Background task authenticates with exponential backoff (5s → 10s → 30s → 60s → 300s max)
- All 29 tools available immediately (will fail gracefully if GNS3 disconnected)

**Connection Tools**:
- `check_gns3_connection()` - Check connection status, error details, last attempt time
- `retry_gns3_connection()` - Force immediate reconnection (bypasses backoff timer)

**Error Handling**:
- Tool failures return clear error messages with connection status
- Check connection before operations if previous operations failed
- Connection auto-recovers when GNS3 becomes available

## SSH Proxy Routing

Multi-proxy architecture enables isolated network access through lab-internal proxies.

**Routing Strategies**:
- **Auto-routing** (default): Use `node_name` only, server routes to correct proxy
- **Manual routing**: Specify `proxy` parameter for explicit control
- **Main proxy**: Use `proxy="host"` for host-level SSH proxy (default)
- **Lab proxies**: Use `proxy=proxy_id` for intra-lab proxies (discover via resources)

**Prerequisites**:
- SSH must be enabled on device first (use console to configure)
- Proxy must have network connectivity to target device
- Device must be started and SSH service running

**Configuration Steps**:
1. Enable SSH on device via console
2. Configure SSH session: `configure_ssh_session("R1", device_dict)`
3. Execute commands: `execute_ssh_command("R1", "show version")`

## Project State Management

**Requirements**:
- Most tools require an active opened project
- Server auto-detects opened projects on GNS3 connection
- Only one project can be opened at a time in GNS3

**Project Operations**:
- `open_project(project_name)` - Open project by name (auto-closes current)
- `create_project(name)` - Create new project (auto-opens)
- `close_project()` - Close current project

**Error Recovery**:
- If tools fail with "No opened project" error
- Check GNS3 connection: `check_gns3_connection()`
- Open required project: `open_project("My Lab")`
- Retry operation

## Device-Specific Behaviors

### Cisco IOS/IOS-XE
- Use `\n` for newlines in console commands
- Wait for `#` prompt (privileged mode) or `>` (user mode)
- Commands may take 2-5 seconds to complete
- Use `send_and_wait_console()` with appropriate prompt patterns

### Cisco NX-OS
- Similar to IOS but with different command syntax
- Prompts: `switch#` or `switch(config)#`
- Configuration mode requires `configure terminal`

### MikroTik RouterOS
- Console may show ANSI escape codes
- Use `raw=True` parameter to preserve formatting
- Prompts: `[admin@MikroTik] >` or similar
- Commands return immediately

### Juniper Junos
- Use `>` for operational mode, `#` for configuration mode
- Requires `commit` to apply configuration changes
- Use `| display set` for configuration display

### Arista EOS
- Similar to Cisco IOS syntax
- Prompts: `switch#` or `switch(config)#`
- Supports `bash` shell access

### Linux (Alpine, Debian, Ubuntu)
- SSH strongly preferred over console for automation
- Console may have getty login prompt (requires credentials)
- Use standard bash commands
- Watch for password prompts on sudo

## Long-Running Operations

Some operations take extended time to complete:

**Node Operations**:
- Node startup: 30-60 seconds (progress notifications available, v0.39.0)
- Node shutdown: 10-30 seconds
- Firmware upgrades: 10-20 minutes (via SSH commands)

**SSH Operations**:
- Show commands: 1-10 seconds
- Configuration commands: 2-30 seconds (progress notifications for wait_timeout > 10s, v0.39.0)
- File transfers: 10+ seconds per MB
- Firmware/backup operations: 5-20 minutes (progress notifications available, v0.39.0)

**Best Practices**:
- Use `wait_timeout` parameter for long SSH operations
- Monitor progress via notifications for node start and SSH commands (v0.39.0)
- For multi-step operations, check status between steps
- Allow extra time for first command after session creation

## Performance Optimization

**Caching** (v0.3.0):
- Project/node/link data cached with 30-second TTL
- Reduces redundant API calls in batch operations
- Automatic cache invalidation on modifications

**Batch Operations**:
- Use batch tools for multiple operations (10×+ faster)
- Two-phase validation prevents partial failures
- Examples: `console_batch_operations()`, `ssh_batch_operations()`, `create_drawings_batch()`

**Resource Efficiency**:
- Close unused console sessions: `disconnect_console()`
- Clean up SSH sessions: `disconnect_ssh_session()`
- Periodic cleanup runs every 5 minutes automatically

## Troubleshooting Common Issues

**Console Connection Fails**:
1. Verify node is started: check status in node list
2. Wait 30-60s after start command
3. Check console type is "telnet" (not vnc/spice)
4. Try waking console: `send_console_data("node", "\n")`

**SSH Connection Fails**:
1. Verify SSH is enabled on device (check via console)
2. Verify device is reachable from proxy
3. Check proxy is running and accessible
4. Verify credentials in device_dict match device configuration

**Commands Return No Output**:
1. Check if device is at prompt (read console buffer)
2. Verify command syntax is correct for device type
3. Try sending newline to wake device: `send_console_data("node", "\n")`
4. Check if command requires privilege escalation

**GNS3 Connection Lost**:
1. Use `check_gns3_connection()` to verify status
2. Check error details in connection_error field
3. Use `retry_gns3_connection()` to reconnect manually
4. Verify GNS3 server is running and accessible

## Resource Discovery

Use MCP resources to discover lab topology and state:

**Projects**: `projects://` - List all projects
**Nodes**: `nodes://{project_id}/` - List nodes in project
**Links**: `links://{project_id}/` - Network topology
**Templates**: `templates://` - Available node templates
**Console Sessions**: `sessions://console/` - Active console connections
**SSH Sessions**: `sessions://ssh/` - Active SSH connections
**Proxies**: `proxies://` - Lab proxy registry

Resources provide read-only views of current state. Use tools to modify state.
