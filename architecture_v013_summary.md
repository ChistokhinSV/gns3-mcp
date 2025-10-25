# GNS3 MCP v0.13 Architecture Summary

Quick reference for the proposed architecture redesign.

## Tool Count Reduction

```
v0.12.4: 30 tools (overwhelming)
         ↓
v0.13.x: 10 tools + Resources + Templates + Prompts (focused)
         ↓
v0.14.0: Breaking change - deprecations removed
```

## Component Breakdown

### Resources (15+ URIs)

**Purpose**: Browsable, read-only state

```
Projects:
  gns3://projects/
  gns3://projects/{id}
  gns3://projects/{id}/nodes/
  gns3://projects/{id}/nodes/{node_id}
  gns3://projects/{id}/links/
  gns3://projects/{id}/drawings/
  gns3://projects/{id}/topology.svg

Templates:
  gns3://templates/
  gns3://templates/{id}
  gns3://templates/categories/{category}

Sessions:
  gns3://sessions/console/
  gns3://sessions/console/{node_name}
  gns3://sessions/ssh/
  gns3://sessions/ssh/{node_name}
  gns3://sessions/ssh/{node_name}/history
  gns3://sessions/ssh/{node_name}/jobs/{job_id}
```

### Resource Templates (3+ Templates)

**Purpose**: Declarative creation with parameter validation

```
Node Creation:
  gns3://templates/{template_id}/create
  Parameters: x, y, node_name?, compute_id?

Drawing Creation:
  gns3://drawings/create/{type}
  Types: rectangle, ellipse, line, text
  Parameters: vary by type

Topology Export:
  gns3://projects/{project_id}/export
  Parameters: output_path, format, crop_*?
```

### Prompts (3+ Workflows)

**Purpose**: Step-by-step workflow guidance

```
setup_ssh:
  - Configure SSH on device (console)
  - Get device IP
  - Establish SSH session
  - Verify access

discover_topology:
  - List projects
  - List nodes and links
  - Export topology diagram

troubleshoot_connectivity:
  - Check node status
  - Verify interfaces
  - Test connectivity
  - Review routing
```

### Tools (10 Core Actions)

**Purpose**: Actions that modify state

```
Project Control (1):
  1. open_project(project_name)

Node Control (2):
  2. set_node(node_name, ...)
  3. delete_node(node_name)

Console Operations (3):
  4. console_send(node_name, data, raw=False)
  5. console_read(node_name, mode="diff", pattern=None, ...)
  6. console_disconnect(node_name)

SSH Operations (3):
  7. ssh_configure(node_name, device_dict, persist=True)
  8. ssh_command(node_name, command, ...)
  9. ssh_disconnect(node_name)

Topology Operations (1):
  10. set_connection(connections)
```

## Migration Mapping

### Tools Converted to Resources

| Old Tool | New Resource | Notes |
|----------|--------------|-------|
| `list_projects` | `gns3://projects/` | Browse all projects |
| `list_nodes` | `gns3://projects/{id}/nodes/` | List nodes in project |
| `get_node_details` | `gns3://projects/{id}/nodes/{node_id}` | Individual node |
| `get_links` | `gns3://projects/{id}/links/` | Network topology |
| `get_console_status` | `gns3://sessions/console/{node_name}` | Console session state |
| `list_templates` | `gns3://templates/` | Available templates |
| `list_drawings` | `gns3://projects/{id}/drawings/` | Drawing objects |
| `ssh_get_status` | `gns3://sessions/ssh/{node_name}` | SSH session state |
| `ssh_get_history` | `gns3://sessions/ssh/{node_name}/history` | Command history |
| `ssh_get_command_output` | `gns3://sessions/ssh/{node_name}/jobs/{id}` | Job output |
| `ssh_get_job_status` | `gns3://sessions/ssh/{node_name}/jobs/{id}` | Job status |

### Tools Converted to Resource Templates

| Old Tool | New Template | Notes |
|----------|--------------|-------|
| `create_node` | `gns3://templates/{id}/create` | Declarative creation |
| `create_drawing` | `gns3://drawings/create/{type}` | Type-specific params |
| `export_topology_diagram` | `gns3://projects/{id}/export` | Export as template |

### Tools Renamed (Consistency)

| Old Name | New Name | Reason |
|----------|----------|--------|
| `send_console` | `console_send` | Prefix-based grouping |
| `read_console` | `console_read` | Prefix-based grouping |
| `disconnect_console` | `console_disconnect` | Prefix-based grouping |
| `configure_ssh` | `ssh_configure` | Prefix-based grouping |
| `ssh_send_command` + `ssh_send_config_set` | `ssh_command` | Auto-detection |

### Tools Removed

| Tool | Reason |
|------|--------|
| `send_and_wait_console` | Use prompt workflow or manual send+read |
| `ssh_cleanup_sessions` | Use explicit `ssh_disconnect` |
| `delete_drawing` | Low usage, use GNS3 GUI |

## Implementation Phases

### Phase 1: v0.13.0 - Resources (Non-breaking)

- [ ] Implement `@mcp.resource()` decorators
- [ ] Add URI routing helpers
- [ ] Create project resources (gns3://projects/...)
- [ ] Create node resources (gns3://projects/{id}/nodes/...)
- [ ] Create link resources (gns3://projects/{id}/links/...)
- [ ] Create template resources (gns3://templates/...)
- [ ] Create session resources (gns3://sessions/...)
- [ ] Update manifest.json
- [ ] Document resources in README.md and SKILL.md
- [ ] **Keep all existing tools unchanged**

**Duration**: 1-2 weeks
**Risk**: Low (additive only)

### Phase 2: v0.13.1 - Templates (Non-breaking)

- [ ] Implement `@mcp.resource_template()` decorators
- [ ] Create node creation template
- [ ] Create drawing creation template
- [ ] Create topology export template
- [ ] Add parameter validation
- [ ] Update manifest.json
- [ ] Add deprecation warnings to old tools
- [ ] Document templates in README.md

**Duration**: 1 week
**Risk**: Low (deprecated tools still work)

### Phase 3: v0.13.2 - Prompts (Non-breaking)

- [ ] Implement `@mcp.prompt()` decorators
- [ ] Create SSH setup prompt
- [ ] Create topology discovery prompt
- [ ] Create troubleshooting prompt
- [ ] Add device-specific instructions
- [ ] Update manifest.json
- [ ] Document prompts in SKILL.md

**Duration**: 1 week
**Risk**: Low (additive only)

### Phase 4: v0.14.0 - Consolidation (BREAKING)

- [ ] Remove deprecated tools (11 tools)
- [ ] Rename tools for consistency (6 renames)
- [ ] Consolidate SSH tools (merge command + config_set)
- [ ] Remove `delete_drawing`, `ssh_cleanup_sessions`
- [ ] Update manifest.json to v0.14.0
- [ ] Create MIGRATION_v0.14.md
- [ ] Update all documentation
- [ ] Test all workflows with new tool set
- [ ] Rebuild .mcpb extension
- [ ] Publish release notes

**Duration**: 1-2 weeks
**Risk**: Medium (breaking changes, migration required)

## File Structure Changes

```
mcp-server/server/
├── main.py                      # Resource/tool registration
├── gns3_client.py              # No changes
├── console_manager.py          # No changes
├── models.py                   # No changes
├── link_validator.py           # No changes
├── export_tools.py             # No changes
│
├── resources/                  # NEW
│   ├── __init__.py
│   ├── projects.py            # Project resources
│   ├── nodes.py               # Node resources
│   ├── links.py               # Link resources
│   ├── templates.py           # Template resources
│   ├── sessions.py            # Session resources
│   └── topology.py            # Topology resource
│
├── resource_templates/         # NEW
│   ├── __init__.py
│   ├── node_creation.py
│   ├── drawing_creation.py
│   └── topology_export.py
│
├── prompts/                    # NEW
│   ├── __init__.py
│   ├── ssh_setup.py
│   ├── topology_discovery.py
│   └── troubleshooting.py
│
└── tools/                      # EXISTING (simplified)
    ├── __init__.py
    ├── project_tools.py       # open_project only
    ├── node_tools.py          # set_node, delete_node
    ├── console_tools.py       # console_send, console_read, console_disconnect
    ├── ssh_tools.py           # ssh_configure, ssh_command, ssh_disconnect
    └── link_tools.py          # set_connection
```

## Benefits at a Glance

| Aspect | Before | After |
|--------|--------|-------|
| **Tool Count** | 30 | 10 |
| **State Queries** | 11 tools | 15+ resources |
| **Creation Ops** | 3 tools | 3 templates |
| **Workflows** | Documentation only | 3+ prompts |
| **Naming** | Mixed | Consistent prefix |
| **Discoverability** | Tool list | Resource hierarchy |
| **Complexity** | High | Low |

## Example Usage Comparison

### Before (v0.12.4)

```python
# List nodes (tool call)
nodes = list_nodes()

# Get node details (tool call)
details = get_node_details("Router1")

# Check console status (tool call)
status = get_console_status("Router1")

# Get SSH history (tool call)
history = ssh_get_history("Router1", limit=10)

# Create node (tool call)
node = create_node("cisco-iosv", x=100, y=200)
```

### After (v0.13+)

```python
# List nodes (resource)
nodes = read_resource("gns3://projects/{id}/nodes/")

# Get node details (resource)
details = read_resource("gns3://projects/{id}/nodes/{node_id}")

# Check console status (resource)
status = read_resource("gns3://sessions/console/Router1")

# Get SSH history (resource)
history = read_resource("gns3://sessions/ssh/Router1/history")

# Create node (resource template)
node = create_from_template("gns3://templates/{id}/create", {
    "x": 100,
    "y": 200
})
```

## Key Advantages

1. **Separation of Concerns**: Resources = read, Tools = write, Prompts = guide
2. **URI-based Navigation**: Browse state like a file system
3. **Declarative Creation**: Templates describe parameters upfront
4. **Workflow Guidance**: Prompts provide step-by-step instructions
5. **Reduced Complexity**: 66% fewer tools, clearer purpose
6. **Future-Proof**: Ready for subscriptions, caching, sampling

## Questions Resolved

**Q: How do users list nodes now?**
A: Resource `gns3://projects/{id}/nodes/` instead of `list_nodes()` tool

**Q: How do users create nodes now?**
A: Resource template `gns3://templates/{id}/create` instead of `create_node()` tool

**Q: How do users set up SSH?**
A: Prompt `setup_ssh` provides step-by-step workflow, then `ssh_configure()` tool

**Q: Are there breaking changes?**
A: Not until v0.14.0. v0.13.x maintains backward compatibility with deprecation warnings.

**Q: How do users migrate?**
A: Gradual adoption in v0.13.x, then MIGRATION_v0.14.md guide for breaking changes.

## Success Criteria

- [ ] Tool count reduced from 30 to 10
- [ ] 15+ resources implemented and documented
- [ ] 3+ resource templates working
- [ ] 3+ prompts available
- [ ] Migration guide published
- [ ] All existing workflows still work (v0.13.x)
- [ ] User feedback positive on discoverability
- [ ] Documentation comprehensive

## Timeline

```
Week 1-2:  Phase 1 (v0.13.0 - Resources)
Week 3:    Phase 2 (v0.13.1 - Templates)
Week 4:    Phase 3 (v0.13.2 - Prompts)
Week 5:    Testing and documentation
Week 6-7:  Phase 4 (v0.14.0 - Breaking changes)
Week 8:    Release and support
```

**Total Duration**: ~8 weeks
**Release Schedule**: v0.13.0, v0.13.1, v0.13.2, v0.14.0

---

**Next Steps**:
1. Review architecture proposal
2. Approve phased plan
3. Create GitHub issues for each phase
4. Begin Phase 1 implementation
5. Update project roadmap
