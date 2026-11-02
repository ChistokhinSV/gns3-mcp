# GNS3 MCP - Known Issues and Improvements

This file tracks issues, bugs, and improvement opportunities for the GNS3 MCP server and SSH proxy.

## Active Issues

_(No active issues)_

---

## Not Bugs (Expected Behavior)

### [NOT A BUG] Grep Error on Project Paths (Windows + Linux GNS3 Server)
**Reported**: 2025-10-27
**Affects**: Windows clients with GNS3 server on Linux
**Severity**: Low - Not an MCP server issue

#### Problem
When using Claude Code on Windows with GNS3 server on Linux, grep operations fail with:
```
Grep error: The directory name is invalid. (os error 267)
```

#### Root Cause
This is **expected behavior** when Claude Code tries to use local Grep tool on Linux paths:
- GNS3 server returns Linux paths: `/opt/gns3/projects/{id}`
- Windows cannot access Linux paths directly
- Error occurs when Claude tries to `Grep` the project directory

#### Not an MCP Server Bug
- MCP server correctly returns project paths from GNS3 API
- Project paths are meant for GNS3 server, not client filesystem access
- MCP tools use HTTP API (not filesystem) - they work correctly
- Issue is Claude Code trying to use Grep on server paths

#### Workaround
Use MCP resources and tools instead of local file operations:
- ✅ Read README: `projects://{id}/readme` resource
- ✅ Get nodes: `projects://{id}/nodes` resource
- ✅ File operations: Use Docker node tools (get_node_file, write_node_file)
- ❌ Don't use local Grep/Read on GNS3 project paths from Windows

---

## Resolved Issues

### [RESOLVED v0.55.0] CLI HTTP mode had no API key auth and no /health (GM-90, 2026-11-02)
Found while refreshing README. `gns3-mcp --transport http` (Docker on 0.0.0.0:8000, uvx, `server.cmd install`)
skipped the `MCP_API_KEY` middleware that only `python -m gns3_mcp.server.main` had; `/health` was 404 so
docker-compose marked containers unhealthy; `--transport sse` crashed on FastMCP 3 (`sse_app()` removed).
**Fix:** shared `build_http_app()` in main.py for both entry points (HTTP + SSE), `MCP_API_KEY` required
(exit if missing), `GET /health` open. Tests: `tests/unit/test_http_app.py`; verified live on :8101 (CLI) and :8100 (service).

---

### [RESOLVED v0.55.0] node create ignores `properties`; node set cannot change disk/cdrom images (2026-10-19, from 119.snow_fwupgrades)

**Repro**
1. `node(action="create", template_name="Ubuntu Cloud Guest", node_name="ops1", properties={"ram": 12288, "cpus": 6, "adapters": 2, "hda_disk_image": "ops1-ubuntu2404-60G.qcow2", "cdrom_image": "ops1-seed.iso"})` -> "Node created successfully".
2. `query_resource("nodes://<pid>/<nid>")` -> ram 1024, cpus 1, adapters 1, hda_disk_image = template default. All overrides silently dropped.
3. `node(action="set", node_name="ops1", hda_disk_image="...")` -> pydantic "Unexpected keyword argument". The schema exposes `hdd_disk_image` (4th disk, QEMU `hdd`) while the docstring says "HDD disk image path" — easy to set the wrong disk. No way to set `hda_disk_image`, `cdrom_image`, `hdb_disk_image`, `adapter_type`, `mac_address`, `options`.

**Expected**
- `create` applies `properties` (or fails loudly listing unsupported keys).
- `set` supports at least `hda_disk_image`, `hdb_disk_image`, `cdrom_image`, `options` for QEMU nodes.

**Workaround used**: set ram/cpus/adapters via `set`; resized linked-clone overlay with `qemu-img resize` on the GNS3 VM; used template default cloud-init ISO.

**Task**: fix create-properties passthrough in node tool; add disk/cdrom params to `set`; add test.

### [RESOLVED v0.55.0] `project(action="close")` reports failure although the project closed (2026-10-19, from 119.snow_fwupgrades)

`project(action="close")` -> `{"error": "Failed to close project", "details": "Expecting value: line 1 column 1 (char 0)"}`, but `project(action="list")` right after shows the project `closed`. Looks like the close call gets an empty body (204) and the client tries `response.json()`. Fix: treat 2xx with empty body as success.

Related to the `set` gap above: QEMU `options` (e.g. `-cpu host`) cannot be set via MCP. Needed because the default `qemu64` CPU lacks x86-64-v2 and modern images (postgres 15 / glibc 2.34+ builds) crash with "Fatal glibc error: CPU does not support x86-64-v2". Workaround used: close project, edit `<project>.gns3` JSON on the GNS3 VM, reopen.

### [RESOLVED v0.55.0] `link(action="batch")` connect result reports the wrong switch port name (2026-10-20, from 119.snow_fwupgrades)

`link(action="batch", connections=[{"action":"connect","node_a":"FGT-SITE002","node_b":"SW-MGMT","adapter_a":0,"port_a":0,"adapter_b":0,"port_b":2}, ... port_b 3])`
-> result lists `"port_b": 2, "port_b_name": "Ethernet0"` (and `port_b 3` -> `"Ethernet0"`). The links are created correctly:
`link(action="list")` shows `port_number 2 / "Ethernet2"` and `3 / "Ethernet3"` on SW-MGMT. For an ethernet_switch
the name seems to be derived from `adapter_b` instead of `port_b`.

**Expected**: `port_b_name` = name of the port actually used (`Ethernet2`, `Ethernet3`).
**Impact**: misleading - looks like both links landed on the port already used by ops1.
**Task**: build port names from the node's `ports[]` matched by (adapter_number, port_number); add a test with a switch port > 0.

### [RESOLVED v0.55.0] `console` `send_and_wait` wait-only mode fails with INTERNAL_ERROR `'command'` (2026-11-02, from 123.Ansible_Studio_VSCODE)

The tool description says `command` is optional for `send_and_wait` (v0.49.0 wait-only mode: omit `command` to just wait for a pattern). Omitting it fails:

`console(operations=[{"type":"send","node_name":"ops1","data":"\n"}, {"type":"send_and_wait","node_name":"ops1","wait_pattern":"(login:|\$ |# )","timeout":15}])`
-> op 1: `{"error": "'command'", "error_code": "INTERNAL_ERROR", "details": "Unexpected error executing send_and_wait operation"}` (a `KeyError` on `op["command"]`, it seems).
The same op with `"command": "\n"` works (`pattern_found: true`, `wait_only: false`).

**Expected**: no `command` -> wait for `wait_pattern` without sending (`wait_only: true`), as documented.
**Task**: read `command` with `.get()` in the batch dispatcher for `send_and_wait` and pass `None` through; add a test for the wait-only batch op.

#### Resolution (v0.55.0, 2026-11-02) - GM-86, GM-87, GM-88, GM-89
- **GM-86**: template endpoint (`TemplateUsage`) only accepts x/y/name/compute_id. `create` now applies
  `properties` (+ explicit ram/cpus/adapters/console_type/disk params) via follow-up `PUT /nodes/{id}`
  and reads back; dropped keys -> `unapplied_properties`. `set` gained `hda_disk_image`, `hdb_disk_image`,
  `cdrom_image`, `options` and a `properties` passthrough. Read-back also exposed two silent drops,
  fixed too: `console_type` (QEMU etc., was nested) and switch `ports` (was top-level). GNS3 error
  reasons (e.g. missing image) now surfaced.
- **GM-87**: `close_project()` treats 204/empty body as success.
- **GM-88**: `resolve_adapter_identifier()` takes the port number; named adapters drive the link's port.
- **GM-89**: batch dispatcher uses `op.get("command")`.
- Verified live on GNS3 3.0.6 (throwaway project `mcp_test_GM86`, deleted after); unit tests in
  `tests/unit/test_tool_fixes.py`, `test_link_validator.py`, `test_gns3_client.py`.

---

### [RESOLVED] SSH Configure Documentation - Parameter Confusion (v0.28.4)
**Discovered**: 2025-10-27
**Affects**: MCP Server v0.1.0+
**Severity**: Medium - UX issue, AI agents confused about parameters
**Resolved**: 2025-10-27

#### Problem
AI agents were unclear that `ssh_configure()` configures SSH **to the network device**, not to the proxy. Specifically:
- `node_name` parameter is the GNS3 node name (e.g., "Router1")
- `device_dict['host']` is the IP address of the **target device** you want to SSH to
- `proxy` parameter is which proxy to **route through**, not the target

#### Symptoms
AI agents would try to configure SSH sessions with proxy IPs instead of device IPs, or get confused about what credentials to provide.

#### Resolution
Enhanced `ssh_configure()` docstring in main.py to clearly explain:
1. Added prominent note: "This configures SSH to the NETWORK DEVICE (router/switch/host), NOT to the proxy"
2. Added "PARAMETERS EXPLAINED" section showing what each parameter actually means
3. Clarified in Args documentation that device_dict is for TARGET DEVICE, not proxy
4. Added clear example showing Router1 at IP 10.1.0.1

#### Files Changed
- `mcp-server/server/main.py`: Enhanced ssh_configure docstring (lines 1925-1981)
- `mcp-server/manifest.json`: Updated to v0.28.4

---

### [RESOLVED] MCP Server Hangs on Startup (Resource Not Found) (v0.28.3)
**Discovered**: 2025-10-27
**Affects**: MCP Server v0.27.1+
**Severity**: Critical - Server becomes unusable on agent restart if GNS3 unavailable
**Resolved**: 2025-10-27

#### Problem
MCP server hangs during initialization when GNS3 server is temporarily unavailable, causing "resource not found" errors even though resources are registered.

**Symptoms**:
- Resources fail with "MCP server resource not found"
- Happens on AI agent 3rd+ restart
- Server appears running but doesn't respond
- All resource URIs fail (e.g., `projects://{id}`)

#### Root Cause
**Blocking authentication during startup** (main.py:410):
```python
await gns3.authenticate(retry=True, retry_interval=30)  # BLOCKS FOREVER
```

**Sequence**:
1. AI agent restarts → triggers MCP server restart
2. MCP starts initialization
3. Tries to authenticate with GNS3 (retry=True, no max_retries)
4. If GNS3 slow/unavailable → **blocks forever** in retry loop
5. Lifespan never completes → resources never become available
6. Tools fail with "resource not found"

#### Resolution
**1. Non-blocking startup** (main.py:415-433):
```python
try:
    # Max 3 attempts during startup, then continue
    await gns3.authenticate(retry=True, retry_interval=5, max_retries=3)
    logger.info("Successfully authenticated")
    # Auto-detect project...
except Exception as e:
    logger.warning(f"Initial auth failed: {e}")
    logger.warning("Server will continue - tools retry auth as needed")
    current_project_id = None
```

**2. Lazy authentication** (gns3_client.py:75-81):
```python
async def _ensure_authenticated(self) -> None:
    """Ensure we have valid token, authenticate if needed"""
    if not self.token:
        success = await self.authenticate(retry=True, retry_interval=5, max_retries=3)
        if not success:
            raise RuntimeError("Failed to authenticate after multiple attempts")
```

Added to `get_projects()` and other API calls - tools auto-retry auth even if startup failed.

#### Benefits
- ✅ Server starts quickly even if GNS3 unavailable
- ✅ Resources always available
- ✅ Tools auto-retry authentication as needed
- ✅ No indefinite hangs
- ✅ Clear error messages when GNS3 is down

#### Files Changed
- `mcp-server/server/main.py`: Non-blocking startup with try/except (lines 409-433)
- `mcp-server/server/gns3_client.py`: Added `_ensure_authenticated()` (lines 75-81), used in `get_projects()` (line 113)

---

### [RESOLVED] Export Topology: Float Infinity Error on Empty Projects (v0.28.2)
**Discovered**: 2025-10-27
**Affects**: MCP Server v0.9.1+
**Severity**: Medium - Breaks export functionality for empty projects
**Resolved**: 2025-10-27

#### Problem
`export_topology_diagram()` fails with "cannot convert float infinity to integer" when called on empty projects (no nodes, no drawings).

#### Error Message
```json
{
  "error": "Failed to export topology diagram",
  "details": "cannot convert float infinity to integer"
}
```

#### Root Cause
Bounds calculation initializes with `float('inf')` and `float('-inf')`:
```python
min_x = min_y = float('inf')
max_x = max_y = float('-inf')
```

When project is empty, these values remain infinity. Later conversion to int fails:
```python
crop_x = int(min_x - padding)  # Crashes if min_x is infinity
```

#### Resolution
Added empty project check before bounds calculation:
```python
if not nodes and not drawings:
    return error("Cannot export empty project",
                 "Add nodes first before exporting")
```

Clear error message guides user to create content first.

#### Files Changed
- `mcp-server/server/export_tools.py`: Added empty project check (lines 203-209)

---

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
- `projects://{id}/snapshots/` - List project snapshots
- `projects://{id}/snapshots/{id}` - Get snapshot details
- `gns3://templates/{id}` - Get template with usage notes (v0.23.0)
- `projects://{id}/nodes/{id}/template` - Get node's template usage (v0.23.0)

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
