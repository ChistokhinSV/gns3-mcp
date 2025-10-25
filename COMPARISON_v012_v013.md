# GNS3 MCP: v0.12.4 vs v0.13 Comparison

Quick reference comparing current implementation with proposed architecture.

## High-Level Comparison

| Aspect | v0.12.4 (Current) | v0.13+ (Proposed) | Change |
|--------|-------------------|-------------------|--------|
| **Total Tools** | 30 | 10 | -66% |
| **Resources** | 0 | 15+ URIs | New |
| **Resource Templates** | 0 | 3+ templates | New |
| **Prompts** | 0 | 3+ workflows | New |
| **MCP Features Used** | Tools only | Tools, Resources, Templates, Prompts | Full spectrum |
| **State Queries** | 11 tools | 15+ resources | Better separation |
| **Creation Ops** | 3 tools | 3 templates | Declarative |
| **Tool Naming** | Mixed | Consistent (`category_action`) | Improved |
| **Cognitive Load** | High | Low | Reduced |

## Detailed Feature Comparison

### Project Management

| Feature | v0.12.4 | v0.13+ | Type |
|---------|---------|--------|------|
| List projects | `list_projects()` tool | `gns3://projects/` | Resource |
| Get project details | N/A | `gns3://projects/{id}` | Resource |
| Open project | `open_project(name)` tool | `open_project(name)` tool | Tool (unchanged) |

**Benefits**:
- Projects browsable as resource hierarchy
- Individual project details available
- Unchanged control operation

### Node Management

| Feature | v0.12.4 | v0.13+ | Type |
|---------|---------|--------|------|
| List nodes | `list_nodes()` tool | `gns3://projects/{id}/nodes/` | Resource |
| Get node details | `get_node_details(name)` tool | `gns3://projects/{id}/nodes/{id}` | Resource |
| Set node state/config | `set_node(name, ...)` tool | `set_node(name, ...)` tool | Tool (unchanged) |
| Create node | `create_node(template, x, y)` tool | `gns3://templates/{id}/create` | Template |
| Delete node | `delete_node(name)` tool | `delete_node(name)` tool | Tool (unchanged) |

**Benefits**:
- Node list and details as resources (read-only)
- Declarative node creation via template
- Control operations unchanged

### Console Operations

| Feature | v0.12.4 | v0.13+ | Type |
|---------|---------|--------|------|
| Send data | `send_console(node, data)` tool | `console_send(node, data)` tool | Tool (renamed) |
| Read output | `read_console(node, mode)` tool | `console_read(node, mode)` tool | Tool (renamed) |
| Check status | `get_console_status(node)` tool | `gns3://sessions/console/{node}` | Resource |
| Disconnect | `disconnect_console(node)` tool | `console_disconnect(node)` tool | Tool (renamed) |
| Send+wait | `send_and_wait_console(...)` tool | Use prompt workflow or manual | Removed |
| Send keystroke | `send_keystroke(node, key)` tool | `console_send(node, key, ...)` | Merged |

**Benefits**:
- Consistent naming (`console_*`)
- Session status as resource
- Simplified workflow (manual or prompt-guided)

### SSH Operations

| Feature | v0.12.4 | v0.13+ | Type |
|---------|---------|--------|------|
| Configure session | `configure_ssh(node, dict)` tool | `ssh_configure(node, dict)` tool | Tool (renamed) |
| Send command | `ssh_send_command(node, cmd)` tool | `ssh_command(node, cmd)` tool | Tool (renamed, merged) |
| Send config | `ssh_send_config_set(node, cmds)` tool | `ssh_command(node, cmds)` tool | Tool (merged) |
| Read buffer | `ssh_read_buffer(node, mode)` tool | (use resources or `console_read`) | Removed |
| Get history | `ssh_get_history(node, limit)` tool | `gns3://sessions/ssh/{node}/history` | Resource |
| Get command output | `ssh_get_command_output(node, job)` tool | `gns3://sessions/ssh/{node}/jobs/{id}` | Resource |
| Get status | `ssh_get_status(node)` tool | `gns3://sessions/ssh/{node}` | Resource |
| Cleanup sessions | `ssh_cleanup_sessions(...)` tool | Use explicit `ssh_disconnect` | Removed |
| Get job status | `ssh_get_job_status(job_id)` tool | `gns3://sessions/ssh/{node}/jobs/{id}` | Resource |
| Disconnect | N/A | `ssh_disconnect(node)` tool | Tool (new) |

**Benefits**:
- Consistent naming (`ssh_*`)
- Command type auto-detection (show vs config)
- Session state and history as resources
- Explicit disconnect operation

### Topology Management

| Feature | v0.12.4 | v0.13+ | Type |
|---------|---------|--------|------|
| List links | `get_links()` tool | `gns3://projects/{id}/links/` | Resource |
| Manage connections | `set_connection(ops)` tool | `set_connection(ops)` tool | Tool (unchanged) |
| List templates | `list_templates()` tool | `gns3://templates/` | Resource |
| List drawings | `list_drawings()` tool | `gns3://projects/{id}/drawings/` | Resource |
| Create drawing | `create_drawing(type, ...)` tool | `gns3://drawings/create/{type}` | Template |
| Delete drawing | `delete_drawing(id)` tool | (use GNS3 GUI) | Removed |
| Export topology | `export_topology_diagram(...)` tool | `gns3://projects/{id}/export` | Template |

**Benefits**:
- Topology state as resources
- Templates as resources (browsable)
- Declarative creation via templates
- Export as template operation

### Workflow Guidance

| Feature | v0.12.4 | v0.13+ | Type |
|---------|---------|--------|------|
| SSH setup | Documentation only | `setup_ssh` prompt | Prompt |
| Topology discovery | Documentation only | `discover_topology` prompt | Prompt |
| Troubleshooting | Documentation only | `troubleshoot_connectivity` prompt | Prompt |

**Benefits**:
- Interactive step-by-step workflows
- Device-specific instructions
- Reduced user errors
- Better onboarding experience

## Tool Count by Category

| Category | v0.12.4 | v0.13+ | Change |
|----------|---------|--------|--------|
| Project | 2 | 1 | -50% |
| Node | 5 | 2 | -60% |
| Console | 6 | 3 | -50% |
| SSH | 9 | 3 | -67% |
| Topology | 5 | 1 | -80% |
| Drawings | 3 | 0 | -100% |
| **TOTAL** | **30** | **10** | **-66%** |

## User Experience Improvements

### Before (v0.12.4)

```python
# Scenario: Check node status and console session

# Step 1: List all nodes (tool call)
nodes = await list_nodes()  # Returns JSON array

# Step 2: Get detailed info (tool call)
details = await get_node_details("Router1")  # Returns JSON

# Step 3: Check console status (tool call)
console_status = await get_console_status("Router1")  # Returns JSON

# Step 4: Check SSH status (tool call)
ssh_status = await ssh_get_status("Router1")  # Returns JSON

# Step 5: Get SSH history (tool call)
history = await ssh_get_history("Router1", limit=10)  # Returns JSON
```

**Issues**:
- 5 tool calls for read-only state
- No browsable hierarchy
- Tool names inconsistent
- Mixed purpose (read vs write)

### After (v0.13+)

```python
# Scenario: Check node status and console session

# Step 1: Browse node list (resource)
nodes = read_resource("gns3://projects/{id}/nodes/")

# Step 2: Get detailed info (resource)
details = read_resource("gns3://projects/{id}/nodes/{node_id}")

# Step 3: Check console status (resource)
console_status = read_resource("gns3://sessions/console/Router1")

# Step 4: Check SSH status (resource)
ssh_status = read_resource("gns3://sessions/ssh/Router1")

# Step 5: Get SSH history (resource)
history = read_resource("gns3://sessions/ssh/Router1/history")
```

**Benefits**:
- Browsable URI hierarchy
- Consistent resource pattern
- Clear read-only semantics
- Future: resource subscriptions

## SSH Setup Workflow Comparison

### Before (v0.12.4)

User reads documentation, manually executes 10+ tool calls:

```python
# 1. Check documentation for device type
# 2. Manually send console commands
send_console("R1", "configure terminal\n")
send_console("R1", "username admin privilege 15 secret cisco\n")
# ... 8 more console commands ...

# 3. Read output to find IP
output = read_console("R1")
# Manual parsing for IP address

# 4. Configure SSH
configure_ssh("R1", {
    "device_type": "cisco_ios",
    "host": "10.10.10.1",  # From step 3
    "username": "admin",
    "password": "cisco"
})

# 5. Test SSH
ssh_send_command("R1", "show version")
```

**Issues**:
- Manual workflow, error-prone
- No device-specific guidance
- User must remember all steps
- Easy to miss configuration

### After (v0.13+)

Use prompt for guided workflow:

```python
# 1. Invoke SSH setup prompt
prompt = get_prompt("setup_ssh", {
    "node_name": "R1",
    "device_type": "cisco_ios",
    "username": "admin",
    "password": "cisco"
})

# Prompt provides step-by-step instructions:
# - Cisco IOS-specific commands
# - How to find IP address
# - How to configure SSH session
# - How to verify access

# 2. Follow prompt instructions (copy-paste ready)
# 3. SSH configured and verified
```

**Benefits**:
- Guided step-by-step workflow
- Device-specific instructions
- Copy-paste ready commands
- Verification steps included
- Reduced user errors

## Node Creation Comparison

### Before (v0.12.4)

```python
# 1. List templates to find ID
templates = list_templates()
# Manual search for template

# 2. Create node
node = create_node(
    template_name="Cisco IOSv",
    x=100,
    y=200,
    node_name="R1"
)
```

**Issues**:
- Template discovery via tool call
- Parameters not discoverable upfront
- No parameter validation preview

### After (v0.13+)

```python
# 1. Browse templates (resource)
templates = read_resource("gns3://templates/")
# Or browse by category: gns3://templates/categories/router

# 2. Create via template (parameter schema available)
node = create_from_template("gns3://templates/{id}/create", {
    "x": 100,
    "y": 200,
    "node_name": "R1",
    "compute_id": "local"
})
```

**Benefits**:
- Templates browsable by category
- Parameter schema discoverable
- Type-safe parameter validation
- Declarative creation

## Migration Effort

| User Type | Migration Effort | Timeline |
|-----------|-----------------|----------|
| **New users** | None (start with v0.13+) | Immediate |
| **Light users** (< 10 tool calls/day) | Low (update tool names) | 1-2 hours |
| **Heavy users** (automation scripts) | Medium (resources + renames) | 1-2 days |
| **Integration developers** | Medium-High (resources + templates) | 3-5 days |

### Migration Steps

**v0.13.x (non-breaking)**:
1. Install v0.13.x (all old tools still work)
2. Start using resources for read operations
3. Try resource templates for creation
4. Experiment with prompts
5. Update code to use new tool names (optional)

**v0.14.0 (breaking)**:
1. Read MIGRATION_v0.14.md guide
2. Replace deprecated tool calls with resources
3. Rename tools (`console_*`, `ssh_*`)
4. Update creation calls to templates
5. Test all workflows
6. Deploy v0.14.0

## Performance Comparison

| Operation | v0.12.4 | v0.13+ | Impact |
|-----------|---------|--------|--------|
| List nodes | Tool call (async) | Resource (async) | Same |
| Get node details | Tool call | Resource | Same |
| Create node | Tool call | Template | Same |
| Check status | Tool call | Resource | Same |
| Browse hierarchy | N/A | Resource URIs | **New capability** |
| Watch for changes | N/A | Subscriptions (future) | **New capability** |

**Note**: No performance degradation. Resources use same underlying API calls as tools.

## Backward Compatibility

| Version | Breaking Changes | Migration Required | Support |
|---------|------------------|-------------------|---------|
| v0.13.0 | None | No | Full |
| v0.13.1 | None | No | Full |
| v0.13.2 | None | No | Full |
| v0.14.0 | **Yes** (11 tools removed, 6 renamed) | **Yes** | Migration guide |

## Summary

The v0.13 architecture proposal represents a **fundamental redesign** of the GNS3 MCP server to leverage MCP protocol features:

**Quantitative Improvements**:
- 66% reduction in tool count (30 → 10)
- 15+ resources for browsable state
- 3+ resource templates for declarative creation
- 3+ prompts for workflow guidance

**Qualitative Improvements**:
- Clear separation: Resources = read, Tools = write, Prompts = guide
- Consistent naming conventions
- Reduced cognitive load
- Better discoverability
- Future-proof for subscriptions and sampling

**Migration Path**:
- Non-breaking in v0.13.x series
- Deprecation warnings guide users
- Breaking changes in v0.14.0 with comprehensive migration guide
- Estimated migration effort: 1-5 days depending on usage

**Recommendation**: Approve phased implementation starting with v0.13.0 (Resources) and monitor user feedback during v0.13.x series before executing breaking changes in v0.14.0.
