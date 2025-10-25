# GNS3 MCP Server Architecture Review v0.13

**Date**: 2025-10-25
**Current Version**: v0.12.4
**Reviewer**: Claude (MCP Architecture Specialist)
**Status**: Proposed Design

---

## Executive Summary

The current GNS3 MCP server (v0.12.4) has **30 tools** across multiple categories. While functional, this creates cognitive overload and misses opportunities to leverage MCP protocol features (resources, resource templates, prompts). This review proposes a redesign targeting **8-12 tools** plus **resources**, **templates**, and **prompts** for improved developer experience.

**Key Recommendations**:
1. **Convert state queries to Resources** (projects, nodes, links, sessions)
2. **Use Resource Templates** for creation operations
3. **Add Prompts** for multi-step workflows
4. **Consolidate tools** to reduce from 30 → 10 core tools
5. **Maintain backward compatibility** through deprecation strategy

---

## Current Architecture Analysis

### Tool Inventory (30 Tools)

**Project Management (2)**:
- `list_projects` → Should be Resource
- `open_project` → Keep as tool (state change)

**Node Management (5)**:
- `list_nodes` → Should be Resource
- `get_node_details` → Should be Resource (individual node)
- `set_node` → Keep (unified control/config)
- `create_node` → Convert to Resource Template
- `delete_node` → Keep

**Console Operations (6)**:
- `send_console` → Keep (core action)
- `read_console` → Keep (core action)
- `disconnect_console` → Could be automatic (resource cleanup)
- `get_console_status` → Should be Resource
- `send_and_wait_console` → Could be Prompt workflow
- `send_keystroke` → Keep (specialized action)

**SSH Operations (9)**:
- `configure_ssh` → Keep (session lifecycle)
- `ssh_send_command` → Keep (core action)
- `ssh_send_config_set` → Keep (core action)
- `ssh_read_buffer` → Keep (buffer access)
- `ssh_get_history` → Should be Resource
- `ssh_get_command_output` → Should be Resource (individual job)
- `ssh_get_status` → Should be Resource
- `ssh_cleanup_sessions` → Could be automatic
- `ssh_get_job_status` → Should be Resource

**Topology Management (5)**:
- `get_links` → Should be Resource
- `set_connection` → Keep (batch operations)
- `list_templates` → Should be Resource
- `list_drawings` → Should be Resource
- `create_drawing` → Convert to Resource Template
- `delete_drawing` → Keep
- `export_topology_diagram` → Convert to Resource Template

### Pain Points Identified

1. **Tool Proliferation**: 30 tools is overwhelming
2. **State vs Action Confusion**: Many tools are read-only queries (should be resources)
3. **Duplicate Functionality**: SSH vs Console tools overlap
4. **Manual Session Management**: Users track console/SSH sessions manually
5. **Complex Multi-Step Workflows**: No guided assistance (e.g., SSH setup)
6. **No Resource Subscriptions**: Can't watch for topology changes
7. **Template Discovery**: Templates listed as data, not as creatable resources

---

## Proposed Architecture v0.13

### 1. MCP Resources

Resources represent **browsable, read-only state** with optional subscriptions.

#### Resource URI Schemes

**Project Resources**:
```
gns3://projects/                          # List all projects
gns3://projects/{project_id}              # Project details
gns3://projects/{project_id}/nodes/       # List nodes in project
gns3://projects/{project_id}/nodes/{id}   # Node details (full NodeInfo)
gns3://projects/{project_id}/links/       # List links
gns3://projects/{project_id}/links/{id}   # Link details
gns3://projects/{project_id}/drawings/    # List drawings
gns3://projects/{project_id}/topology.svg # Topology diagram (dynamic)
```

**Template Resources**:
```
gns3://templates/                         # List all templates
gns3://templates/{template_id}            # Template details
gns3://templates/categories/{category}    # Templates by category
```

**Session Resources**:
```
gns3://sessions/console/                  # List active console sessions
gns3://sessions/console/{node_name}       # Console session status
gns3://sessions/ssh/                      # List active SSH sessions
gns3://sessions/ssh/{node_name}           # SSH session status
gns3://sessions/ssh/{node_name}/history   # SSH command history
gns3://sessions/ssh/{node_name}/jobs/{id} # Individual job output
```

**Implementation Example**:
```python
@mcp.resource("gns3://projects/")
async def list_projects_resource(ctx: Context) -> str:
    """List all GNS3 projects"""
    app: AppContext = ctx.request_context.lifespan_context
    projects = await app.gns3.get_projects()
    # Return JSON array of ProjectInfo
    return json.dumps([ProjectInfo(**p).model_dump() for p in projects], indent=2)

@mcp.resource("gns3://projects/{project_id}/nodes/")
async def list_nodes_resource(ctx: Context, uri: str) -> str:
    """List nodes in project"""
    project_id = extract_project_id(uri)
    app: AppContext = ctx.request_context.lifespan_context
    nodes = await app.gns3.get_nodes(project_id)
    return json.dumps([NodeSummary(**n).model_dump() for n in nodes], indent=2)

@mcp.resource("gns3://sessions/ssh/{node_name}/history")
async def ssh_history_resource(ctx: Context, uri: str) -> str:
    """SSH command history for node"""
    node_name = extract_node_name(uri)
    # Fetch from SSH proxy
    history = await fetch_ssh_history(node_name)
    return json.dumps(history, indent=2)
```

**Benefits**:
- **Browsable hierarchy**: Projects → Nodes → Links/Drawings
- **Dynamic topology**: `topology.svg` regenerates on access
- **Session visibility**: See all active console/SSH sessions
- **Command audit trail**: SSH history as resource
- **Subscription support**: Watch for topology changes (future)

### 2. Resource Templates

Templates represent **creatable resources** with parameters.

#### Template Definitions

**Create Node Template**:
```
gns3://templates/{template_id}/create
```

**Parameters**:
- `x` (int): X coordinate
- `y` (int): Y coordinate
- `node_name` (string, optional): Custom name
- `compute_id` (string, default="local"): Compute host

**Create Drawing Template**:
```
gns3://drawings/create/{type}
```

**Types**: `rectangle`, `ellipse`, `line`, `text`
**Parameters**: Vary by type (width, height, color, etc.)

**Export Topology Template**:
```
gns3://projects/{project_id}/export
```

**Parameters**:
- `output_path` (string): Export directory
- `format` (string): "svg", "png", or "both"
- `crop_x`, `crop_y`, `crop_width`, `crop_height` (optional): Crop region

**Implementation Example**:
```python
@mcp.resource_template("gns3://templates/{template_id}/create")
async def create_node_template(ctx: Context, uri: str, arguments: dict) -> str:
    """Create node from template"""
    template_id = extract_template_id(uri)
    app: AppContext = ctx.request_context.lifespan_context

    # Validate current project
    error = await validate_current_project(app)
    if error:
        return error

    # Create node
    node = await app.gns3.create_node(
        project_id=app.current_project_id,
        template_id=template_id,
        x=arguments['x'],
        y=arguments['y'],
        name=arguments.get('node_name'),
        compute_id=arguments.get('compute_id', 'local')
    )

    return json.dumps(NodeInfo(**node).model_dump(), indent=2)
```

**Benefits**:
- **Declarative creation**: Templates describe what can be created
- **Parameter discovery**: Clients see required/optional params
- **Type safety**: Parameter validation built-in
- **Reduces tool count**: No separate `create_*` tools

### 3. Prompts

Prompts represent **multi-step workflows** with embedded instructions.

#### Prompt Definitions

**SSH Setup Workflow**:
```
Name: setup_ssh
Description: Configure SSH access on network device
Arguments:
  - node_name (string): Target node
  - device_type (string): Device type (cisco_ios, mikrotik_routeros, etc.)
  - username (string): SSH username
  - password (string): SSH password
```

**Prompt Content**:
```markdown
# SSH Setup Workflow for {node_name}

This workflow enables SSH on {node_name} and establishes an SSH session.

## Step 1: Configure SSH on Device (Console)

Depending on device type, use console tools to enable SSH:

**For Cisco IOS** (device_type=cisco_ios):
1. Enter configuration mode: `send_console("{node_name}", "configure terminal\n")`
2. Create user: `send_console("{node_name}", "username {username} privilege 15 secret {password}\n")`
3. Generate RSA keys: `send_console("{node_name}", "crypto key generate rsa modulus 2048\n")`
4. Enable SSH v2: `send_console("{node_name}", "ip ssh version 2\n")`
5. Configure VTY: `send_console("{node_name}", "line vty 0 4\nlogin local\ntransport input ssh\n")`
6. Exit config: `send_console("{node_name}", "end\n")`

**For MikroTik RouterOS** (device_type=mikrotik_routeros):
1. Create user: `send_console("{node_name}", "/user add name={username} password={password} group=full\n")`
2. Enable SSH: `send_console("{node_name}", "/ip service enable ssh\n")`

## Step 2: Get Device IP Address

Read console to find management IP:
`read_console("{node_name}")`

Look for interface IP (e.g., 10.10.10.1)

## Step 3: Establish SSH Session

Use the IP from Step 2:
```python
configure_ssh("{node_name}", {
    "device_type": "{device_type}",
    "host": "10.10.10.1",  # Replace with actual IP
    "username": "{username}",
    "password": "{password}"
})
```

## Step 4: Verify SSH Access

Test SSH connection:
`ssh_send_command("{node_name}", "show version")`

## Completion

SSH is now configured! Use SSH tools for automation:
- `ssh_send_command()` - Execute show commands
- `ssh_send_config_set()` - Send configuration
- `ssh_get_history()` - Review command history
```

**Topology Discovery Workflow**:
```
Name: discover_topology
Description: Discover and visualize network topology
Arguments:
  - output_path (string, optional): Export directory
```

**Topology Troubleshooting Workflow**:
```
Name: troubleshoot_connectivity
Description: Diagnose connectivity issues between nodes
Arguments:
  - source_node (string): Source node name
  - dest_node (string): Destination node name
```

**Implementation**:
```python
@mcp.prompt()
async def setup_ssh(ctx: Context, node_name: str, device_type: str,
                   username: str, password: str) -> PromptMessage:
    """SSH setup workflow"""

    # Render template with arguments
    content = render_ssh_setup_prompt(node_name, device_type, username, password)

    return PromptMessage(
        role="user",
        content=TextContent(type="text", text=content)
    )
```

**Benefits**:
- **Guided workflows**: Step-by-step instructions for complex tasks
- **Device-specific**: Tailored to device type (Cisco, MikroTik, etc.)
- **Reduces errors**: Users follow proven procedures
- **Onboarding**: New users learn best practices
- **Contextual help**: Embedded in tool selection

### 4. Consolidated Tools

Reduced from 30 → **10 core tools** for actions only.

#### Tool List v0.13

**Project Control (1)**:
1. `open_project(project_name)` - Open/switch project

**Node Control (2)**:
2. `set_node(node_name, ...)` - Configure node properties and/or control state
3. `delete_node(node_name)` - Delete node

**Console Operations (3)**:
4. `console_send(node_name, data, raw=False)` - Send data to console (auto-connects)
5. `console_read(node_name, mode="diff", pattern=None, ...)` - Read console output with grep
6. `console_disconnect(node_name)` - Explicit disconnect (optional, auto-timeout exists)

**SSH Operations (3)**:
7. `ssh_configure(node_name, device_dict, persist=True)` - Configure SSH session
8. `ssh_command(node_name, command, ...)` - Execute command (show/config auto-detected)
9. `ssh_disconnect(node_name)` - Disconnect SSH session

**Topology Operations (1)**:
10. `set_connection(connections)` - Batch link operations (connect/disconnect)

**Note**: `delete_drawing` removed (use GNS3 GUI or future generic `delete_resource()`)

#### Tool Changes from v0.12.4

**Removed (converted to Resources)**:
- `list_projects` → Resource `gns3://projects/`
- `list_nodes` → Resource `gns3://projects/{id}/nodes/`
- `get_node_details` → Resource `gns3://projects/{id}/nodes/{node_id}`
- `get_links` → Resource `gns3://projects/{id}/links/`
- `get_console_status` → Resource `gns3://sessions/console/{node_name}`
- `list_templates` → Resource `gns3://templates/`
- `list_drawings` → Resource `gns3://projects/{id}/drawings/`
- `ssh_get_status` → Resource `gns3://sessions/ssh/{node_name}`
- `ssh_get_history` → Resource `gns3://sessions/ssh/{node_name}/history`
- `ssh_get_command_output` → Resource `gns3://sessions/ssh/{node_name}/jobs/{id}`
- `ssh_get_job_status` → Resource `gns3://sessions/ssh/{node_name}/jobs/{id}`

**Removed (converted to Resource Templates)**:
- `create_node` → Template `gns3://templates/{id}/create`
- `create_drawing` → Template `gns3://drawings/create/{type}`
- `export_topology_diagram` → Template `gns3://projects/{id}/export`

**Removed (converted to Prompts)**:
- `send_and_wait_console` → Use prompt workflow or `console_send` + `console_read`

**Consolidated**:
- `ssh_send_command` + `ssh_send_config_set` → `ssh_command` (auto-detects type)
- `send_console` → `console_send` (clearer naming)
- `read_console` → `console_read` (clearer naming)
- `disconnect_console` → `console_disconnect` (clearer naming)
- `configure_ssh` → `ssh_configure` (clearer naming)
- `ssh_cleanup_sessions` removed (use `ssh_disconnect` explicitly)
- `send_keystroke` kept but documented as console feature

**Removed Entirely**:
- `delete_drawing` - Low usage, use GNS3 GUI

#### Renamed Tools (Consistency)

| Old Name | New Name | Reason |
|----------|----------|--------|
| `send_console` | `console_send` | Prefix-based grouping |
| `read_console` | `console_read` | Prefix-based grouping |
| `disconnect_console` | `console_disconnect` | Prefix-based grouping |
| `configure_ssh` | `ssh_configure` | Prefix-based grouping |
| `ssh_send_command` | `ssh_command` | Consolidation |
| `ssh_send_config_set` | (merged into `ssh_command`) | Auto-detection |

**Rationale**: Tool names now follow `{category}_{action}` pattern for better discoverability and grouping in tool lists.

---

## Implementation Roadmap

### Phase 1: Resource Infrastructure (v0.13.0)

**Objective**: Add resources without breaking existing tools

**Tasks**:
1. Implement `@mcp.resource()` decorators for read-only state
2. Add resource URI routing and extraction helpers
3. Create resources for:
   - Projects: `gns3://projects/`, `gns3://projects/{id}`
   - Nodes: `gns3://projects/{id}/nodes/`, `gns3://projects/{id}/nodes/{node_id}`
   - Links: `gns3://projects/{id}/links/`
   - Templates: `gns3://templates/`
   - Sessions: `gns3://sessions/console/`, `gns3://sessions/ssh/`
4. Update manifest.json with resource definitions
5. Document resources in README.md and SKILL.md
6. **Keep all existing tools** (no breaking changes)

**Testing**:
- Verify resource URIs resolve correctly
- Test resource content matches tool output
- Validate JSON schema compliance

**Deliverables**:
- Resources implemented and documented
- No tool changes
- Backward compatible

### Phase 2: Resource Templates (v0.13.1)

**Objective**: Add creation via resource templates

**Tasks**:
1. Implement `@mcp.resource_template()` decorators
2. Create templates for:
   - Node creation: `gns3://templates/{id}/create`
   - Drawing creation: `gns3://drawings/create/{type}`
   - Topology export: `gns3://projects/{id}/export`
3. Add parameter validation and examples
4. Update manifest.json with template definitions
5. **Deprecate** (but keep) `create_node`, `create_drawing`, `export_topology_diagram`
6. Add deprecation warnings to tool docstrings

**Testing**:
- Verify template parameter validation
- Test creation via templates matches tool behavior
- Validate error handling

**Deliverables**:
- Templates working
- Deprecated tools still functional
- Migration guide in docs

### Phase 3: Prompts (v0.13.2)

**Objective**: Add workflow guidance

**Tasks**:
1. Implement `@mcp.prompt()` decorators
2. Create prompts for:
   - SSH setup workflow
   - Topology discovery
   - Connectivity troubleshooting
3. Add prompt templates with argument substitution
4. Update manifest.json with prompt definitions
5. Document prompts in SKILL.md

**Testing**:
- Verify prompt rendering with arguments
- Test workflow instructions are accurate
- Validate device-specific instructions

**Deliverables**:
- 3+ prompts implemented
- Workflow documentation
- Examples in SKILL.md

### Phase 4: Tool Consolidation (v0.14.0 - BREAKING)

**Objective**: Remove deprecated tools, consolidate functionality

**Tasks**:
1. **Remove deprecated tools**:
   - `list_projects`, `list_nodes`, `get_node_details`, `get_links`
   - `get_console_status`, `ssh_get_status`, `ssh_get_history`
   - `list_templates`, `list_drawings`
   - `create_node`, `create_drawing`, `export_topology_diagram`
2. **Rename tools** for consistency:
   - `send_console` → `console_send`
   - `read_console` → `console_read`
   - `disconnect_console` → `console_disconnect`
   - `configure_ssh` → `ssh_configure`
3. **Consolidate SSH tools**:
   - Merge `ssh_send_command` + `ssh_send_config_set` → `ssh_command`
   - Auto-detect command type (show vs config)
4. **Remove low-usage tools**:
   - `ssh_cleanup_sessions` (use explicit disconnect)
   - `delete_drawing` (use GNS3 GUI)
5. Update manifest.json (version 0.14.0, remove deprecated tools)
6. Update all documentation
7. Create MIGRATION_v0.14.md guide

**Testing**:
- Verify all workflows work with new tool set
- Test resource → tool migration paths
- Validate no regressions in functionality

**Deliverables**:
- 10 core tools (from 30)
- Resources + Templates + Prompts
- Migration guide
- Updated documentation

### Phase 5: Advanced Features (v0.15.0+)

**Future enhancements**:
1. **Resource subscriptions**: Watch for topology changes
2. **Sampling support**: LLM-driven device configuration
3. **Enhanced prompts**: Interactive step-by-step wizards
4. **Resource caching**: Client-side caching with ETags
5. **Batch operations**: Generic batch resource operations

---

## Migration Strategy

### Backward Compatibility

**v0.13.x series (Non-breaking)**:
- All existing tools continue to work
- New resources/templates/prompts added
- Deprecation warnings in tool docstrings
- Migration guide published

**v0.14.0 (Breaking change)**:
- Deprecated tools removed
- Tool renames (console_*, ssh_*)
- Resources/templates/prompts fully functional
- MIGRATION_v0.14.md with upgrade steps

### User Migration Path

**For v0.13.x users**:
1. Start using resources for read-only queries
2. Switch to resource templates for creation
3. Try prompts for complex workflows
4. Update code to use new tool names (prefixed)
5. Prepare for v0.14.0 (remove deprecated tool usage)

**For v0.14.0 users**:
1. Resources are primary method for state queries
2. Tools only for actions (control, send, configure)
3. Prompts guide complex workflows
4. Cleaner tool list (10 vs 30)

### Desktop Extension Updates

**Claude Desktop (.mcpb)**:
- Version must increment to v0.13.0
- Pre-commit hook rebuilds extension
- Users reinstall by double-clicking .mcpb

**Claude Code (.mcp.json)**:
- Project-scoped config auto-updates
- Restart conversation to load new resources

---

## Code Structure Recommendations

### File Organization v0.13

```
mcp-server/
├── server/
│   ├── main.py                  # FastMCP app, resource/tool registration
│   ├── gns3_client.py           # GNS3 API client
│   ├── console_manager.py       # Telnet console manager
│   ├── models.py                # Pydantic models
│   ├── link_validator.py        # Two-phase link validation
│   ├── export_tools.py          # SVG/PNG export helpers
│   │
│   ├── resources/               # NEW: Resource implementations
│   │   ├── __init__.py
│   │   ├── projects.py          # Project resources
│   │   ├── nodes.py             # Node resources
│   │   ├── links.py             # Link resources
│   │   ├── templates.py         # Template resources
│   │   ├── sessions.py          # Console/SSH session resources
│   │   └── topology.py          # Topology export resource
│   │
│   ├── resource_templates/      # NEW: Resource template implementations
│   │   ├── __init__.py
│   │   ├── node_creation.py     # Node creation templates
│   │   ├── drawing_creation.py  # Drawing creation templates
│   │   └── topology_export.py   # Topology export templates
│   │
│   ├── prompts/                 # NEW: Prompt implementations
│   │   ├── __init__.py
│   │   ├── ssh_setup.py         # SSH setup workflow
│   │   ├── topology_discovery.py # Topology discovery
│   │   └── troubleshooting.py   # Connectivity troubleshooting
│   │
│   └── tools/                   # EXISTING: Tool implementations
│       ├── __init__.py
│       ├── project_tools.py     # Project control (open_project)
│       ├── node_tools.py        # Node control (set_node, delete_node)
│       ├── console_tools.py     # Console ops (send, read, disconnect)
│       ├── ssh_tools.py         # SSH ops (configure, command, disconnect)
│       └── link_tools.py        # Link ops (set_connection)
│
├── ssh-proxy/                   # EXISTING: SSH proxy service
│   └── ...
│
├── tests/
│   ├── unit/
│   │   ├── test_resources.py    # NEW: Resource tests
│   │   ├── test_templates.py    # NEW: Template tests
│   │   └── ...
│   └── ...
│
├── manifest.json                # MCP package metadata
├── MIGRATION_v0.14.md          # NEW: Migration guide
└── ARCHITECTURE_REVIEW_v0.13.md # This document
```

### Resource Implementation Pattern

**File**: `mcp-server/server/resources/projects.py`

```python
"""Project Resources

Browsable project state via MCP resources.
"""

import json
from mcp.server.fastmcp import Context
from models import ProjectInfo

async def list_projects_resource(ctx: Context, uri: str) -> str:
    """Resource: gns3://projects/

    Lists all GNS3 projects with status.

    Returns:
        JSON array of ProjectInfo objects
    """
    app = ctx.request_context.lifespan_context
    projects = await app.gns3.get_projects()

    return json.dumps(
        [ProjectInfo(**p).model_dump() for p in projects],
        indent=2
    )

async def get_project_resource(ctx: Context, uri: str) -> str:
    """Resource: gns3://projects/{project_id}

    Get detailed project information.

    Args:
        uri: Resource URI with project_id

    Returns:
        JSON ProjectInfo object
    """
    project_id = uri.split("/")[-1]
    app = ctx.request_context.lifespan_context

    projects = await app.gns3.get_projects()
    project = next((p for p in projects if p["project_id"] == project_id), None)

    if not project:
        return json.dumps({"error": f"Project {project_id} not found"}, indent=2)

    return json.dumps(ProjectInfo(**project).model_dump(), indent=2)
```

**Registration in main.py**:

```python
from resources.projects import list_projects_resource, get_project_resource

# Register resources
mcp.resource("gns3://projects/")(list_projects_resource)
mcp.resource("gns3://projects/{project_id}")(get_project_resource)
```

### Resource Template Implementation Pattern

**File**: `mcp-server/server/resource_templates/node_creation.py`

```python
"""Node Creation Resource Template

Create nodes from GNS3 templates via resource templates.
"""

import json
from mcp.server.fastmcp import Context
from models import NodeInfo, ErrorResponse

async def create_node_template(ctx: Context, uri: str, arguments: dict) -> str:
    """Resource Template: gns3://templates/{template_id}/create

    Create a node from a GNS3 template.

    Args:
        uri: Resource URI with template_id
        arguments: Creation parameters
            - x (int): X coordinate
            - y (int): Y coordinate
            - node_name (str, optional): Custom node name
            - compute_id (str, optional): Compute host (default: "local")

    Returns:
        JSON NodeInfo for created node or ErrorResponse
    """
    template_id = uri.split("/")[-2]  # Extract from URI
    app = ctx.request_context.lifespan_context

    # Validate current project
    if not app.current_project_id:
        return json.dumps(ErrorResponse(
            error="No project opened",
            suggested_action="Open a project first"
        ).model_dump(), indent=2)

    # Validate required arguments
    if "x" not in arguments or "y" not in arguments:
        return json.dumps(ErrorResponse(
            error="Missing required arguments",
            details="x and y coordinates are required"
        ).model_dump(), indent=2)

    # Create node
    try:
        node = await app.gns3.create_node(
            project_id=app.current_project_id,
            template_id=template_id,
            x=arguments["x"],
            y=arguments["y"],
            name=arguments.get("node_name"),
            compute_id=arguments.get("compute_id", "local")
        )

        return json.dumps(NodeInfo(**node).model_dump(), indent=2)

    except Exception as e:
        return json.dumps(ErrorResponse(
            error="Node creation failed",
            details=str(e)
        ).model_dump(), indent=2)
```

**Registration in main.py**:

```python
from resource_templates.node_creation import create_node_template

# Register resource template
mcp.resource_template("gns3://templates/{template_id}/create")(create_node_template)
```

### Prompt Implementation Pattern

**File**: `mcp-server/server/prompts/ssh_setup.py`

```python
"""SSH Setup Workflow Prompt

Guides users through enabling SSH on network devices.
"""

from mcp.types import PromptMessage, TextContent

# Device-specific instructions
CISCO_IOS_STEPS = """
1. Enter configuration mode:
   send_console("{node_name}", "configure terminal\\n")

2. Create administrative user:
   send_console("{node_name}", "username {username} privilege 15 secret {password}\\n")

3. Generate RSA keys:
   send_console("{node_name}", "crypto key generate rsa modulus 2048\\n")

4. Enable SSH version 2:
   send_console("{node_name}", "ip ssh version 2\\n")

5. Configure VTY lines:
   send_console("{node_name}", "line vty 0 4\\nlogin local\\ntransport input ssh\\nend\\n")
"""

MIKROTIK_STEPS = """
1. Create administrative user:
   send_console("{node_name}", "/user add name={username} password={password} group=full\\n")

2. Enable SSH service:
   send_console("{node_name}", "/ip service enable ssh\\n")
"""

DEVICE_STEPS = {
    "cisco_ios": CISCO_IOS_STEPS,
    "mikrotik_routeros": MIKROTIK_STEPS,
    # Add more device types
}

async def ssh_setup_prompt(node_name: str, device_type: str,
                           username: str, password: str) -> PromptMessage:
    """Generate SSH setup workflow prompt

    Args:
        node_name: Target node name
        device_type: Device type (cisco_ios, mikrotik_routeros, etc.)
        username: SSH username
        password: SSH password

    Returns:
        PromptMessage with workflow instructions
    """

    device_steps = DEVICE_STEPS.get(device_type, "# Unknown device type")

    content = f"""# SSH Setup Workflow for {node_name}

This workflow enables SSH on {node_name} ({device_type}) and establishes an SSH session.

## Step 1: Configure SSH on Device (via Console)

{device_steps.format(node_name=node_name, username=username, password=password)}

## Step 2: Get Device IP Address

Read console output to find management IP:
```
read_console("{node_name}")
```

Look for interface IP address (e.g., 10.10.10.1)

## Step 3: Establish SSH Session

Use the IP address from Step 2:
```
ssh_configure("{node_name}", {{
    "device_type": "{device_type}",
    "host": "10.10.10.1",  # Replace with actual IP
    "username": "{username}",
    "password": "{password}"
}})
```

## Step 4: Verify SSH Access

Test SSH connection:
```
ssh_command("{node_name}", "show version")
```

## Completion

SSH is now configured! Use SSH tools for automation:
- `ssh_command()` - Execute commands
- Review history: `gns3://sessions/ssh/{node_name}/history`
"""

    return PromptMessage(
        role="user",
        content=TextContent(type="text", text=content)
    )
```

**Registration in main.py**:

```python
from prompts.ssh_setup import ssh_setup_prompt

@mcp.prompt()
async def setup_ssh(ctx: Context, node_name: str, device_type: str,
                   username: str, password: str) -> PromptMessage:
    """SSH setup workflow

    Guides through enabling SSH on network device.

    Args:
        node_name: Target node name
        device_type: Device type (cisco_ios, mikrotik_routeros, juniper, etc.)
        username: SSH username to create
        password: SSH password to set
    """
    return await ssh_setup_prompt(node_name, device_type, username, password)
```

---

## Benefits Summary

### Developer Experience Improvements

**Before v0.13 (30 tools)**:
- Overwhelming tool list
- Unclear when to use which tool
- Manual session tracking
- No workflow guidance
- State queries mixed with actions

**After v0.13 (10 tools + resources + templates + prompts)**:
- **10 focused action tools** (send, configure, control)
- **Resources for state** (browse projects, nodes, sessions)
- **Templates for creation** (create nodes, drawings, export)
- **Prompts for workflows** (SSH setup, troubleshooting)
- **Clear separation**: Resources = read, Tools = write, Prompts = guide

### Specific Improvements

1. **Reduced Cognitive Load**: 10 tools vs 30 (66% reduction)
2. **Better Discoverability**: Resources browsable by URI hierarchy
3. **Workflow Guidance**: Prompts provide step-by-step instructions
4. **Consistent Naming**: Tool names follow `{category}_{action}` pattern
5. **Fewer Tool Calls**: Resources fetch state without tool invocation
6. **Audit Trails**: SSH history as resource (persistent, browsable)
7. **Dynamic Content**: Topology diagrams regenerate on access
8. **Future-Proof**: Resource subscriptions enable topology watching

---

## Risk Assessment

### Risks and Mitigations

**Risk: Breaking existing workflows**
**Mitigation**: Phase 1-3 are non-breaking (v0.13.x). Breaking changes in v0.14.0 with migration guide.

**Risk: Resource implementation complexity**
**Mitigation**: Resources reuse existing tool logic. Gradual rollout by category.

**Risk: User confusion during migration**
**Mitigation**: Deprecation warnings, dual support in v0.13.x, clear documentation.

**Risk: Resource performance (large topologies)**
**Mitigation**: Lightweight NodeSummary for lists, full NodeInfo for individual resources.

**Risk: Tool consolidation loses functionality**
**Mitigation**: Merged tools preserve all parameters (e.g., `ssh_command` detects show vs config).

---

## Success Metrics

### Quantitative Goals

- **Tool count**: 30 → 10 (66% reduction)
- **Resource count**: 0 → 15+ URIs
- **Prompt count**: 0 → 3+ workflows
- **Documentation**: All resources/templates/prompts documented
- **Migration**: <5% user issues during v0.14.0 upgrade

### Qualitative Goals

- **Improved discoverability**: Users find state via resources
- **Faster onboarding**: Prompts guide new users
- **Clearer tool purpose**: Tools are actions, resources are state
- **Better UX**: Reduced cognitive load, clearer organization

---

## Conclusion

The proposed v0.13 architecture leverages MCP protocol features (resources, templates, prompts) to significantly improve the GNS3 MCP server developer experience. By converting state queries to resources, creation operations to templates, and complex workflows to prompts, we reduce tool count from 30 to 10 while adding powerful new capabilities.

The phased rollout (v0.13.0 → v0.13.2 → v0.14.0) ensures backward compatibility during migration, with clear deprecation warnings and comprehensive documentation. The result is a more intuitive, maintainable, and powerful MCP server that scales to future enhancements like resource subscriptions and LLM sampling.

**Recommended Next Steps**:
1. Review this proposal with stakeholders
2. Approve phased implementation plan
3. Begin Phase 1: Resource infrastructure (v0.13.0)
4. Publish migration guide and updated documentation
5. Gather user feedback during v0.13.x series
6. Execute Phase 4: Breaking changes (v0.14.0)

---

**Document Version**: 1.0
**Last Updated**: 2025-10-25
**Author**: Claude (MCP Architecture Specialist)
**Status**: Proposed Design - Awaiting Approval
