# GNS3 MCP Tools Optimization - Progress Tracker

## Current Status: Phase 3 In Progress (Console Tools)

### Completed Phases

#### ✅ Phase 1: GNS3Client API Methods (COMPLETED)
**Added to `mcp-server/server/gns3_client.py`:**
- `suspend_node()` - POST /v3/projects/{id}/nodes/{id}/suspend
- `reload_node()` - POST /v3/projects/{id}/nodes/{id}/reload
- `update_node(properties)` - PUT /v3/projects/{id}/nodes/{id}
- `create_link(link_spec)` - POST /v3/projects/{id}/links
- `delete_link(link_id)` - DELETE /v3/projects/{id}/links/{id}

#### ✅ Phase 2: ConsoleManager Node-Name Tracking (COMPLETED)
**Updated `mcp-server/server/console_manager.py`:**
- Added `_node_sessions` dict for node_name → session_id mapping
- Updated `connect()` to track node_name mapping
- Updated `disconnect()` to clean up node_name mapping
- Added node-name based convenience methods:
  - `get_session_id(node_name)`
  - `has_session(node_name)`
  - `send_by_node(node_name, data)`
  - `get_output_by_node(node_name)`
  - `get_diff_by_node(node_name)`
  - `disconnect_by_node(node_name)`

### In Progress

None - Moving to Phase 4

### Completed Phases (continued)

#### ✅ Phase 3: Rewrite main.py MCP Tools (COMPLETED)
**Status:** All tool rewrites complete

**Changes made:**

1. **Console Tools** ✅
   - ✅ Added json and typing imports to main.py
   - ✅ Updated `send_console(node_name, data)` - auto-connect
   - ✅ Updated `read_console(node_name, diff=False)` - merged read_console_diff
   - ✅ Updated `disconnect_console(node_name)`
   - ✅ Removed: `connect_console`, `read_console_diff`, `list_console_sessions`

2. **Node Control Tools** ✅
   - ✅ Created `set_node(node_name, action, x, y, z, locked, ports)`
   - ✅ Implemented restart logic: 3 retries × 5s = 15s max
   - ✅ Removed: `start_node`, `stop_node`

3. **Connection Management Tools** ✅
   - ✅ Created `set_connection(connections)` for batch link operations
   - ✅ Sequential execution with predictable state
   - ✅ Returns: `{"completed": [...], "failed": {...}}`

### Pending Phases

#### ⏳ Phase 4: Test Script for Port Field
- Create test to verify `port_number` vs `adapter_number`
- Test with actual GNS3 links
- Adjust set_connection if needed

#### ⏳ Phase 5: Update Skill Documentation
**File: `skill/SKILL.md`**
- Update Console Access section (remove session_id references)
- Update Common Workflows (use new tool signatures)
- Update Console Best Practices
- Update Multi-Node Operations
- Add "Managing Network Connections" section
- Add "Node Positioning & Configuration" section

#### ⏳ Phase 6: Update README and Migration Guide
**Files: `README.md`, `CLAUDE.md`**
- Update tool examples
- Add migration guide (old → new tool names)
- Update quick reference

#### ⏳ Phase 7: Version Update and Testing
- Update version: 0.1.4 → 0.2.0 (breaking changes)
- Update manifest.json
- Repackage .mcpb extension
- Test all new features:
  - Console auto-connect
  - Node restart with retries
  - Link management
  - Port configuration

## Implementation Details

### Restart Logic (for set_node)
```python
async def restart_node(project_id, node_id):
    # Stop node
    await gns3.stop_node(project_id, node_id)

    # Poll status with retries
    for attempt in range(3):
        await asyncio.sleep(5)
        nodes = await gns3.get_nodes(project_id)
        node = find_node_by_id(nodes, node_id)
        if node['status'] == 'stopped':
            break

    # Start node
    await gns3.start_node(project_id, node_id)
```

### Connection Batch Format
```json
{
  "connections": [
    {"action": "disconnect", "link_id": "abc123"},
    {"action": "connect", "node_a": "R1", "port_a": 0,
     "node_b": "R2", "port_b": 1}
  ]
}
```

### Port Field Decision
- Use `port_number` (from API research)
- Verify with test script in Phase 4
- Adjust if needed based on actual behavior

## Notes
- Session timeout: 30 minutes (confirmed)
- Tool names changing: This is v0.2.0 with breaking changes
- All old tool names will be removed
- Migration guide will help users transition
