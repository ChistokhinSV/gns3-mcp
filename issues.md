# GNS3 MCP - Known Issues and Improvements

This file tracks issues, bugs, and improvement opportunities for the GNS3 MCP server and SSH proxy.

## Active Issues

_(No active issues)_

---

---

## Resolved Issues

### [RESOLVED] Auto-Connect to Opened Projects (v0.28.1)
**Discovered**: 2025-10-27
**Affects**: MCP Server v0.1.0+
**Severity**: Medium - UX issue, commands fail unnecessarily
**Resolved**: 2025-10-27

#### Problem
Commands fail with "No project opened" even when a project is open in GNS3, because:
- MCP server only detects opened projects at **startup**
- If project is opened in GNS3 GUI **after** MCP starts, tools don't auto-connect
- Users must manually call `open_project()` even though project is already opened

#### Symptoms
```json
{
  "error": "No project opened",
  "details": "Use open_project() to open a project first",
  "suggested_action": "Call list_projects() to see available projects, then open_project(project_name)"
}
```

#### Root Cause
Disconnect between two states:
- **GNS3 "opened" status**: Project is open in GNS3 server (visible in GUI)
- **MCP "connected" state**: MCP session has stored `current_project_id`

The `validate_current_project()` function only checked `app.current_project_id` and failed if None, without attempting to auto-detect opened projects.

#### Resolution
Enhanced `validate_current_project()` to auto-connect:
1. If `current_project_id` is None, query GNS3 for opened projects
2. If project(s) found with status="opened", auto-connect to first one
3. Log auto-connection with project name and ID
4. Warn if multiple projects are opened
5. Updated error messages to distinguish "no projects in GNS3" vs "multiple opened"

**Benefits:**
- ✅ Seamless UX - works with projects opened in GUI
- ✅ No breaking changes - existing code continues to work
- ✅ Clear error messages if no projects are opened
- ✅ Matches user expectations

#### Files Changed
- `mcp-server/server/main.py`: Modified `validate_current_project()` function (lines 463-526)

#### Testing Scenarios
1. ✅ Start MCP with no opened projects → tools fail with clear error
2. ✅ Open project in GNS3 GUI → tools auto-connect and work
3. ✅ Open project via `open_project()` → continues to work as before
4. ✅ Close project in GNS3 → tools detect and give clear error

---

### [RESOLVED] configure_node_network Tool: ErrorCode.INVALID_OPERATION + Wrong Node Type (v0.27.0)
**Discovered**: 2025-10-26
**Affects**: MCP Server v0.27.0
**Severity**: High - Breaks network configuration for QEMU nodes
**Resolved**: 2025-10-26 in v0.27.0

#### Problem
Two issues found in file operation tools (`get_node_file`, `write_node_file`, `configure_node_network`):
1. Referenced non-existent `ErrorCode.INVALID_OPERATION` (should be `ErrorCode.OPERATION_FAILED`)
2. Only allowed Docker nodes, but VPCS nodes also support file operations
3. Error messages didn't clarify QEMU nodes are unsupported (by design)

#### Error Message
```json
{
  "error": "Failed to configure network on node 'A-CLIENT'",
  "error_code": "OPERATION_FAILED",
  "details": "type object 'ErrorCode' has no attribute 'INVALID_OPERATION'",
  "exception": "type object 'ErrorCode' has no attribute 'INVALID_OPERATION'"
}
```

#### Root Cause
- Code used `ErrorCode.INVALID_OPERATION.value` which doesn't exist in ErrorCode enum
- Node type check was `node['node_type'] != 'docker'` instead of checking for both docker and vpcs
- Error messages didn't explain why QEMU is unsupported

#### Resolution
**All 3 tools fixed:**
1. Changed `ErrorCode.INVALID_OPERATION` → `ErrorCode.OPERATION_FAILED`
2. Changed validation from `!= 'docker'` → `not in ('docker', 'vpcs')`
3. Updated error messages to clarify supported types and why QEMU doesn't work:
   - "Network configuration only supported for Docker and VPCS nodes (not qemu)"
   - "QEMU nodes don't support this tool - configure manually via console/SSH"
   - Added `supported_types: ["docker", "vpcs"]` to error context

#### Files Changed
- `mcp-server/server/tools/node_tools.py`: Fixed 3 error codes, updated 3 validation checks, improved error messages

---

### [RESOLVED] create_node Tool: Missing properties Parameter (v0.24.2)
**Discovered**: 2025-10-26
**Affects**: MCP Server v0.22.0+
**Severity**: High - Tool completely non-functional

#### Problem
The `create_node` MCP tool in main.py accepts a `properties` parameter and passes it to `create_node_impl()`, but the implementation function in node_tools.py didn't have the parameter in its signature. This caused "takes from 4 to 6 positional arguments but 7 were given" error on every call.

#### Error Message
```
Error executing tool create_node: create_node_impl() takes from 4 to 6 positional arguments but 7 were given
```

#### Root Cause
Signature mismatch between tool declaration and implementation:
- Tool: `create_node(..., properties: Optional[Dict[str, Any]] = None)`
- Impl: `create_node_impl(app, template_name, x, y, node_name, compute_id)` ← missing properties

#### Resolution
- Added `properties` parameter to `create_node_impl()` signature
- Added `properties` handling in payload construction
- Added `Dict, Any` imports to typing imports
- Updated docstring to document properties parameter

#### Files Changed
- `mcp-server/server/tools/node_tools.py`: Function signature, imports, payload handling

---

### [RESOLVED] MCP Resources: Missing Resource Registrations (v0.23.0)
**Discovered**: 2025-10-26
**Affects**: MCP Server v0.18.0+
**Severity**: Medium - Resources implemented but not accessible

#### Problem
Snapshot resources (v0.18.0) and new template resources (v0.23.0) were implemented in resource_manager.py with URI patterns but never registered in main.py with @mcp.resource decorators, making them inaccessible via MCP protocol.

#### Missing Resources
- `gns3://projects/{id}/snapshots/` - List project snapshots
- `gns3://projects/{id}/snapshots/{id}` - Get snapshot details
- `gns3://templates/{id}` - Get template with usage notes (v0.23.0)
- `gns3://projects/{id}/nodes/{id}/template` - Get node's template usage (v0.23.0)

#### Resolution
Added @mcp.resource decorators in main.py for all four missing resources (lines 547-571). Total MCP resources now correctly registered: 20 (was showing 0 in ListMcpResources).

#### Files Changed
- `mcp-server/server/main.py`: Added 4 resource registrations

---

### [RESOLVED] SSH Proxy: Stale Session Management
**Discovered**: 2025-10-25
**Affects**: SSH Proxy v0.1.5
**Severity**: High - Breaks all SSH functionality after lab restart
**Resolved**: 2025-10-26 in SSH Proxy v0.1.6

#### Problem
SSH sessions persist in memory with closed sockets after lab restart, causing all SSH commands to fail with "Socket is closed" error. Sessions are not automatically cleaned up when underlying connections die.

#### Symptoms
- `ssh_command()` returns `completed: false` with empty output
- Execution time exactly ~1 second (timeout)
- Logs show: `ERROR - Command failed: Socket is closed`
- Same session_id reused even for "new" connections
- Prompt detection fails: `Pattern not detected: '[\$\#]'`

#### Root Cause
1. SSH proxy maintains `_sessions` dict mapping `node_name → session_id`
2. When lab restarts, SSH connections close but sessions persist in dict
3. `ssh_configure()` finds existing session and returns it (reuses stale session)
4. `ssh_command()` attempts to use closed socket → fails immediately
5. No automatic detection or cleanup of dead sessions

#### Resolution (v0.1.6)
All 5 proposed fixes implemented:

**✅ Fix 1: Session Health Check**
- `_is_session_healthy()` method checks connection before reuse
- Uses Netmiko `is_alive()` if available (4.0+), fallback to empty command test
- Stale sessions automatically detected and recreated in `create_session()`

**✅ Fix 2: Automatic Cleanup on Failure**
- Exception handlers in `send_command_adaptive()` and `send_config_set_adaptive()` detect socket errors
- Stale sessions immediately removed from session manager
- Jobs marked as failed with execution time tracking

**✅ Fix 3: Session TTL/Expiry**
- 30-minute TTL implemented with `last_activity` timestamp
- Activity tracked on: ssh_send_command, ssh_send_config_set, get_buffer, session reuse
- `_is_session_expired()` and `_update_activity()` methods manage lifecycle
- Expired sessions automatically detected and recreated

**✅ Fix 4: Force Recreation Parameter**
- `force` parameter added to `ssh_configure()` MCP tool
- Allows manual override to create fresh session
- Example: `ssh_configure("A-DIST1", device_dict, force=True)`

**✅ Fix 5: Better Error Messages**
- Structured error responses with `error_code` and `suggested_action` fields
- Error codes: `SSH_DISCONNECTED`, `TIMEOUT`, `COMMAND_FAILED`
- Each error includes actionable guidance for resolution
- Example response:
  ```json
  {
    "completed": false,
    "error": "SSH session closed for A-DIST1...",
    "error_code": "SSH_DISCONNECTED",
    "suggested_action": "Session was stale and has been removed. Reconnect with ssh_configure()..."
  }
  ```

#### Files Changed (v0.1.6)
- `ssh-proxy/server/models.py`: Added last_activity to SessionInfo, error fields to CommandResponse
- `ssh-proxy/server/session_manager.py`: Implemented TTL, health checks, auto-cleanup, structured errors
- `ssh-proxy/server/main.py`: Version 0.1.5→0.1.6
- `ssh-proxy/README.md`: Added Session Management documentation
- `mcp-server/server/main.py`: Updated ssh_configure tool with force parameter
- `mcp-server/server/tools/ssh_tools.py`: Updated configure_ssh_impl
- `skill/SKILL.md`: Added Session Management section
- `CLAUDE.md`: Added v0.1.6 version entry

#### Testing Results
✅ All proposed tests passed:
1. ✅ Start lab, configure SSH sessions - sessions created successfully
2. ✅ Restart lab - stale sessions detected via health check
3. ✅ Old sessions detected as dead - `_is_session_healthy()` returns False
4. ✅ New sessions created automatically - `create_session()` recreates on health check failure
5. ✅ Commands work after restart - SSH automation functional post-restart
6. ✅ Error messages informative - structured errors with suggested actions

---

## Future Enhancements

_(Add more issues as discovered)_
