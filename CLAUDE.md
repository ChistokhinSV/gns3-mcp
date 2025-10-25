# GNS3 MCP Server - Project Instructions

Project-specific instructions for working with the GNS3 MCP server codebase.

## Project Overview

MCP server providing programmatic access to GNS3 network simulation labs. Includes:
- Desktop extension (.mcpb) for Claude Desktop
- Agent skill with GNS3 procedural knowledge
- Console management for device interaction
- GNS3 v3 API client with JWT authentication

## Current Version: v0.20.0

**Latest Release:** v0.20.0 - Polish & Quality (Phase 1 - Foundation) (REFACTOR)
- **NEW**: Single source of truth for version - manifest.json
  - `main.py` reads VERSION from manifest.json at runtime (no hardcoded versions)
  - Falls back to "0.20.0" if manifest read fails
  - Pre-commit hook validates no hardcoded VERSION in code
  - Version synchronization tests ensure consistency
- **NEW**: Enhanced error handling infrastructure (foundation for Phase 2)
  - **ErrorCode enum** with 26 standardized error codes:
    - Resource Not Found (6 codes): PROJECT_NOT_FOUND, NODE_NOT_FOUND, LINK_NOT_FOUND, etc.
    - Validation Errors (8 codes): INVALID_PARAMETER, PORT_IN_USE, NODE_RUNNING, etc.
    - Connection Errors (6 codes): GNS3_UNREACHABLE, CONSOLE_CONNECTION_FAILED, etc.
    - Authentication Errors (3 codes): AUTH_FAILED, TOKEN_EXPIRED, INVALID_CREDENTIALS
    - Internal Errors (3 codes): INTERNAL_ERROR, TIMEOUT, OPERATION_FAILED
  - **Enhanced ErrorResponse model**:
    - Added `error_code` field (machine-readable, from ErrorCode enum)
    - Added `context` field (debugging information with structured data)
    - Added `server_version` field (tracks which version produced error)
    - Added `timestamp` field (auto-generated ISO 8601 UTC timestamp)
    - Kept legacy fields for backward compatibility
  - **15 error helper functions** in error_utils.py (~400 LOC):
    - `create_error_response()` - Generic error creation with version tracking
    - `node_not_found_error()` - Node errors with available nodes list
    - `project_not_found_error()` - Project errors with suggested action
    - `validation_error()` - Validation errors with valid values list
    - `gns3_api_error()` - API errors with status code and endpoint
    - And 10 more specialized helpers for common error scenarios
    - All helpers include suggested_action and context for debugging
- **FILES CHANGED** (Foundation Phase):
  - `mcp-server/server/main.py`: VERSION reading from manifest (+12 LOC)
  - `mcp-server/server/models.py`: ErrorCode enum, enhanced ErrorResponse (+48 LOC)
  - `mcp-server/server/error_utils.py`: NEW - 15 error helper functions (400 LOC)
  - `tests/unit/test_version.py`: NEW - Version synchronization tests (85 LOC)
  - `.git/hooks/pre-commit`: Version consistency validation (+11 LOC)
  - `mcp-server/manifest.json`: Version 0.19.0→0.20.0, updated descriptions
  - `CLAUDE.md`: This version entry
- **PHASE 1 STATUS**: Foundation complete, tools not yet updated
  - ✅ Version synchronization infrastructure
  - ✅ Error code taxonomy and response models
  - ✅ Error utility helper functions
  - ✅ Unit tests for version handling
  - ⏳ Pending: Update 20 tools to use standardized errors (Phase 2)
  - ⏳ Pending: Update gns3_client.py error handling (Phase 2)
  - ⏳ Pending: Create ERROR_CODES.md documentation (Phase 2)
  - ⏳ Pending: Write comprehensive error handling tests (Phase 2)
- **NO BREAKING CHANGES**: All tools still functional, error handling backward compatible
- **TESTING**: Server starts successfully, VERSION correctly read from manifest.json
- **RATIONALE**: Centralized version management prevents version mismatch errors. Standardized
  error handling foundation enables consistent error responses across all 20 tools with helpful
  suggested actions and debugging context. Phase 1 establishes infrastructure, Phase 2 will
  update all tools to use it.

**Previous:** v0.19.0 - UX & Advanced Features (FEATURE)
- **NEW**: MCP tool annotations for all 20 tools (visibility of tool behavior in IDE/MCP clients)
  - **destructive** (3 tools): delete_node, restore_snapshot, delete_drawing
    - Marks tools that delete data or make irreversible changes
    - IDE/MCP clients may show warnings or require confirmation
  - **idempotent** (9 tools): open_project, create_project, close_project, set_node, console_disconnect,
                               ssh_configure, ssh_disconnect, update_drawing, export_topology_diagram
    - Safe to retry - same operation multiple times produces same result
    - Example: opening already-opened project, stopping already-stopped node
  - **read_only** (1 tool): console_read
    - Tool only reads data, makes no state changes
    - May be cached by MCP clients
  - **creates_resource** (5 tools): create_project, create_node, create_snapshot, export_topology_diagram, create_drawing
    - Tool creates new resources in GNS3 or filesystem
  - **modifies_topology** (3 tools): set_connection, create_node, delete_node
    - Tool changes network topology structure
- **DEFERRED**: Autocomplete support via MCP completions for 7 parameter types (implementation prepared but disabled pending FastMCP API clarification)
  - **node_name** (9 tools): console_send, console_read, console_keystroke, console_disconnect,
                              ssh_configure, ssh_command, ssh_disconnect, set_node, delete_node
    - Autocompletes from current project's node names
    - Shows node type and status in description (e.g., "vpcs (started)")
    - Filters by prefix, limits to 10 results
  - **template_name** (create_node): Autocompletes from available GNS3 templates
    - Shows category and node_type in description
  - **action** (set_node): Enum autocomplete for start/stop/suspend/reload/restart
  - **project_name** (open_project): Autocompletes from all GNS3 projects
    - Shows project status in description
  - **snapshot_name** (restore_snapshot): Autocompletes from current project's snapshots
    - Shows created_at timestamp in description
  - **drawing_type** (create_drawing): Enum autocomplete for rectangle/ellipse/line/text
  - **topology_type** (lab_setup prompt): Enum autocomplete for star/mesh/linear/ring/ospf/bgp
- **NEW**: 3 drawing tools for visual annotations (hybrid architecture)
  - `create_drawing`: Create rectangle, ellipse, line, or text annotations
    - **Rectangle**: width/height, fill_color, border_color, border_width
    - **Ellipse**: rx/ry (radii), fill_color, border_color, border_width
    - **Line**: x2/y2 (offset from start), color, border_width
    - **Text**: text content, font_size, font_weight, font_family, color
    - All: x/y position, z-order/layer
  - `update_drawing`: Modify position (x/y/z), rotation, svg content, locked state
    - Partial updates supported - provide only changed properties
  - `delete_drawing`: Remove drawing object by ID
  - **Hybrid pattern**: Resources (gns3://projects/{id}/drawings/) for READ, Tools for WRITE
    - Follows MCP protocol semantics (Resources = browsable read-only, Tools = actions)
    - Drawing resources already existed from v0.13.0
    - Tools added in v0.19.0 to enable modifications
- **ARCHITECTURE**: 20 tools + 17 resources + 4 prompts + (8 completions deferred) = Enhanced UX
  - **Tools (20)**: Added export_topology_diagram, create_drawing, update_drawing, delete_drawing
  - **Resources (17)**: Unchanged from v0.18.0
  - **Prompts (4)**: Unchanged from v0.18.0
  - **Completions (8)**: Implementation prepared but disabled - FastMCP completion API differs from MCP spec
                          Functions: complete_node_names, complete_template_names, complete_node_actions,
                          complete_project_names, complete_snapshot_names, complete_drawing_types,
                          complete_topology_types, complete_connection_actions (all suffixed with _DISABLED)
- **Files changed**:
  - `mcp-server/server/main.py`: Added annotations to 17 tools, 8 completion handlers, 3 drawing tools,
                                   imported Completion type, version 0.18.0→0.19.0 (+300 LOC)
  - `mcp-server/server/tools/drawing_tools.py`: Added update_drawing_impl() (+65 LOC)
  - `mcp-server/manifest.json`: Version 0.18.0→0.19.0, added 3 tools (create/update/delete_drawing),
                                  updated descriptions to reflect 20 tools + annotations
  - `CLAUDE.md`: This version entry
  - `mcp-server/mcp-server.mcpb`: Rebuilt desktop extension
- **NO BREAKING CHANGES**: All existing tools, resources, prompts unchanged
- **KNOWN ISSUES**: Completions disabled - FastMCP API for completions is different from MCP spec.
  Code is ready but disabled pending API clarification. Will be re-enabled in future version once
  correct FastMCP completion decorator syntax is determined.
- **Rationale**: Tool annotations enable IDE warnings for destructive operations, improving safety.
  Completions would reduce typing and discovery friction (deferred). Drawing tools restore functionality
  removed in v0.15.0 with improved hybrid architecture that separates READ (resources) from WRITE (tools).

**Previous:** v0.18.0 - Core Lab Automation (FEATURE)
- **NEW**: 5 new tools for complete lab lifecycle management
  - `create_project`: Create new GNS3 projects and auto-open
    - Validates no duplicate project names
    - Auto-opens after creation
    - Stores project in GNS3 configured directory or custom path
  - `close_project`: Close currently opened project
    - Clears current_project_id from app context
    - Returns project name in confirmation
  - `create_node`: Create nodes from templates at specified coordinates (RESTORED from v0.15.0)
    - Uses template name (e.g., "Alpine Linux", "Cisco IOSv")
    - Positions nodes with x/y coordinates
    - Optional custom node name and property overrides
  - `create_snapshot`: Save project state with validation
    - Checks for duplicate snapshot names
    - Warns (non-blocking) if nodes are running
    - Captures all project state: nodes, links, drawings, settings
  - `restore_snapshot`: Restore to previous snapshot state
    - Stops all running nodes first
    - Disconnects all console sessions
    - Restores complete project state
- **NEW**: 2 new MCP resources for snapshot browsing
  - `gns3://projects/{id}/snapshots/` - List all snapshots in project
  - `gns3://projects/{id}/snapshots/{id}` - Snapshot details (name, created_at, snapshot_id)
- **NEW**: lab_setup prompt - Automated topology creation with 6 topology types
  - `star`: Hub-and-spoke topology (parameter: spoke count)
    - Hub at center, spokes radiate outward
    - IP scheme: 10.0.{spoke}.0/24 per link
  - `mesh`: Full mesh topology (parameter: router count)
    - All routers interconnected
    - IP scheme: 10.0.{subnet}.0/30 point-to-point links
  - `linear`: Chain topology (parameter: router count)
    - Routers connected in series
    - IP scheme: 10.0.{link}.0/30
  - `ring`: Circular topology (parameter: router count)
    - Each router connects to two neighbors
    - Closes the loop
  - `ospf`: Multi-area OSPF topology (parameter: area count)
    - Area 0 backbone with ABRs in center
    - Additional areas radiate outward
    - 3 routers per area
    - IP scheme: 10.{area}.0.{router}/32 loopbacks
  - `bgp`: Multiple AS topology (parameter: AS count)
    - 2 routers per AS (iBGP peering)
    - eBGP between adjacent AS
    - IP scheme: 10.{AS}.1.0/30 (iBGP), 172.16.{link}.0/30 (eBGP)
  - **Includes**: Layout algorithms for node positioning, link generation functions, IP addressing schemes
- **ARCHITECTURE**: 16 tools + 17 resources + 4 prompts = Complete lab automation
  - **Tools (16)**: open_project, create_project, close_project, set_node, create_node, delete_node,
                    create_snapshot, restore_snapshot, console_send, console_read, console_disconnect,
                    console_keystroke, set_connection, ssh_configure, ssh_command, ssh_disconnect
  - **Resources (17)**: 17 `gns3://` URIs (added 2 snapshot resources)
  - **Prompts (4)**: ssh_setup, topology_discovery, troubleshooting, lab_setup
- **WORKFLOW ENABLEMENT**: Complete lab lifecycle now automated
  - Create project → Add nodes → Create links → Create snapshot → Test → Restore if needed
  - Lab setup prompt generates complete topologies with single command
- **Files added**:
  - `mcp-server/server/tools/snapshot_tools.py`: Snapshot management (~200 LOC)
  - `mcp-server/server/prompts/lab_setup.py`: Lab setup workflow with layout algorithms (~800 LOC)
- **Files changed**:
  - `mcp-server/server/gns3_client.py`: Added create_project(), close_project(), get_snapshots(),
                                         create_snapshot(), restore_snapshot() (+100 LOC)
  - `mcp-server/server/tools/project_tools.py`: Added create_project_impl(), close_project_impl() (+100 LOC)
  - `mcp-server/server/main.py`: Registered 5 tools + 1 prompt, version 0.17.0→0.18.0 (+100 LOC)
  - `mcp-server/server/models.py`: Added SnapshotInfo model (+30 LOC)
  - `mcp-server/server/resources/project_resources.py`: Added list_snapshots_impl(), get_snapshot_impl() (+100 LOC)
  - `mcp-server/server/resources/resource_manager.py`: Added snapshot URI patterns (+20 LOC)
  - `mcp-server/server/prompts/__init__.py`: Exported render_lab_setup_prompt
  - `mcp-server/manifest.json`: Version 0.17.0→0.18.0, added 5 tools + 1 prompt to definitions
  - `CLAUDE.md`: This version entry
  - `mcp-server/mcp-server.mcpb`: Rebuilt desktop extension
- **NO BREAKING CHANGES**: All existing tools, resources, and prompts unchanged
- **Rationale**: Enables complete lab automation from project creation through topology setup to snapshot
  management. Lab setup prompt with layout algorithms reduces manual work for common topologies. Snapshot
  management provides version control for lab configurations.

**Previous:** v0.17.0 - MCP Prompts (FEATURE)
- **NEW**: 3 guided workflow prompts for common GNS3 operations
  - `ssh_setup`: Device-specific SSH configuration workflow
    - Covers 6 device types: Cisco IOS, NX-OS, MikroTik RouterOS, Juniper Junos, Arista EOS, Linux
    - Step-by-step instructions from console configuration to SSH session establishment
    - Device-specific commands with parameter placeholders
    - Troubleshooting guidance for common SSH issues
  - `topology_discovery`: Network topology discovery and visualization
    - Guides through using MCP resources to browse projects/nodes/links
    - Instructions for export_topology_diagram tool usage
    - Topology pattern analysis (hub-and-spoke, mesh, tiered, etc.)
    - Common topology questions to answer during discovery
  - `troubleshooting`: OSI model-based systematic troubleshooting
    - Layer 1-7 troubleshooting methodology
    - Common issues and resolutions for each layer
    - Console and SSH troubleshooting workflows
    - Performance analysis and log collection
- **ARCHITECTURE**: Complete MCP server = 11 tools + 15 resources + 3 prompts
  - **Tools (11)**: Actions that modify state
  - **Resources (15)**: Browsable read-only state
  - **Prompts (3)**: Guided workflows for complex operations
- **DEVICE COVERAGE**: 6 device types with specific configuration commands
  - Cisco IOS/IOS-XE: Full enterprise router/switch setup
  - Cisco NX-OS: Data center switch configuration
  - MikroTik RouterOS: SOHO/branch router setup
  - Juniper Junos: Enterprise networking equipment
  - Arista EOS: Cloud/data center switching
  - Linux: Alpine/Debian/Ubuntu server configuration
- **WORKFLOW GUIDANCE**: Step-by-step instructions reduce errors
  - Prerequisites check before starting workflows
  - Verification steps after each action
  - Troubleshooting sections for common problems
  - Next steps guidance after workflow completion
- **Files added**:
  - `mcp-server/server/prompts/__init__.py`: Module initialization (17 LOC)
  - `mcp-server/server/prompts/ssh_setup.py`: SSH setup workflow (~280 LOC)
  - `mcp-server/server/prompts/topology_discovery.py`: Topology discovery workflow (~320 LOC)
  - `mcp-server/server/prompts/troubleshooting.py`: Troubleshooting workflow (~440 LOC)
- **Files changed**:
  - `mcp-server/server/main.py`: Added prompt imports, registered 3 prompts, version 0.15.0→0.17.0
  - `mcp-server/manifest.json`: Added prompts section, version 0.15.0→0.17.0
  - `CLAUDE.md`: This version entry
  - `mcp-server/mcp-server.mcpb`: Rebuilt desktop extension
- **NO BREAKING CHANGES**: All tools and resources unchanged, prompts additive
- **Rationale**: Prompts guide users through complex multi-step workflows, reducing errors and improving efficiency. Device-specific instructions ensure correct configuration for different platforms.

**Previous:** v0.15.0 - Complete Tool Consolidation (BREAKING CHANGES)
- **RENAMED**: All tools now follow `{category}_{action}` naming pattern for consistency
  - `send_console` → `console_send`
  - `read_console` → `console_read`
  - `disconnect_console` → `console_disconnect`
  - `send_keystroke` → `console_keystroke`
  - `configure_ssh` → `ssh_configure`
- **MERGED**: SSH command tools with auto-detection
  - `ssh_send_command` + `ssh_send_config_set` → `ssh_command()`
  - Auto-detects command type: string = show command, list = config commands
  - Simpler API: one tool for all SSH operations
- **REMOVED**: 7 deprecated/low-usage tools
  - `send_and_wait_console` → Use `console_send` + `console_read` workflow
  - `create_node` → Will be resource template in v0.16.0
  - `create_drawing` → Will be resource template in v0.16.0
  - `delete_drawing` → Use GNS3 GUI (low usage)
  - `ssh_cleanup_sessions` → Use explicit `ssh_disconnect`
  - `ssh_get_job_status` → Already available as resource `gns3://sessions/ssh/{node}/jobs/{id}`
- **NEW**: `ssh_disconnect` tool for explicit SSH session cleanup
- **FINAL ARCHITECTURE**: 11 core tools + 15 browsable resources
  - **Tools (11)**: open_project, set_node, delete_node, console_send, console_read, console_disconnect, console_keystroke, set_connection, ssh_configure, ssh_command, ssh_disconnect
  - **Resources (15)**: 15 `gns3://` URIs for browsing state
  - **Clear patterns**: Console tools prefixed with `console_`, SSH tools prefixed with `ssh_`
- **Tool count reduction**: 17 → 11 (-35% reduction from v0.14.0, -63% total from v0.12.4's 30 tools)
- **Files changed**:
  - `mcp-server/server/main.py`: Renamed 5 tools, merged 2 SSH tools, removed 7 tools, version 0.14.0→0.15.0
  - `mcp-server/server/tools/ssh_tools.py`: Added `ssh_disconnect_impl()` function (48 LOC)
  - `mcp-server/manifest.json`: Updated tool definitions, version 0.14.0→0.15.0
  - `CLAUDE.md`: This version entry
  - `mcp-server/mcp-server.mcpb`: Rebuilt desktop extension
- **Migration Guide**:
  - **Console tools**: Add `console_` prefix (e.g., `send_console` → `console_send`)
  - **SSH configuration**: `configure_ssh` → `ssh_configure`
  - **SSH commands**: Use `ssh_command()` for both show and config
    - Show: `ssh_command("R1", "show ip route")` (string)
    - Config: `ssh_command("R1", ["interface Gi0/0", "ip address..."])` (list)
  - **Interactive workflows**: Replace `send_and_wait_console()` with `console_send()` + `console_read()`
  - **Node/drawing creation**: Use GNS3 GUI until v0.16.0 resource templates available
- **NO BREAKING CHANGES for resources**: All 15 MCP resources unchanged
- **Rationale**: Consistent tool naming improves discoverability, merged SSH command simplifies API, reduced tool count lowers cognitive load

**Previous:** v0.14.0 - Tool Consolidation (BREAKING CHANGES - Phase 1)
- **REMOVED**: 11 deprecated query tools (replaced by MCP resources in v0.13.0)
  - `list_projects()` → resource `gns3://projects`
  - `list_nodes()` → resource `gns3://projects/{id}/nodes`
  - `get_node_details()` → resource `gns3://projects/{id}/nodes/{id}`
  - `get_links()` → resource `gns3://projects/{id}/links`
  - `list_templates()` → resource `gns3://projects/{id}/templates`
  - `list_drawings()` → resource `gns3://projects/{id}/drawings`
  - `get_console_status()` → resource `gns3://sessions/console/{node}`
  - `ssh_get_status()` → resource `gns3://sessions/ssh/{node}`
  - `ssh_get_history()` → resource `gns3://sessions/ssh/{node}/history`
  - `ssh_get_command_output()` → query resource with filtering
  - `ssh_read_buffer()` → resource `gns3://sessions/ssh/{node}/buffer`
- **FINAL ARCHITECTURE**: 17 core tools + 15 browsable resources
  - **Tools (17)**: Actions that modify state - create, delete, configure, execute
  - **Resources (15)**: Read-only browsable state - projects, nodes, sessions, status
  - **Clear separation**: Tools change things, Resources view things
- **Tool count reduction**: 30 → 17 (-43% reduction in cognitive load)
- **Files changed**:
  - `mcp-server/server/main.py`: Removed 11 tool definitions, updated version 0.13.0→0.14.0
  - `mcp-server/manifest.json`: Removed 11 tool definitions, version 0.13.0→0.14.0
  - `skill/SKILL.md`: Updated deprecated tools section to "Removed in v0.14.0"
  - `CLAUDE.md`: This version entry
- **NO BREAKING CHANGES for v0.13.0 users**: Resources already available, tools simply removed
- **Rationale**: Clearer separation of concerns (read vs write), reduced cognitive load, better IDE integration with resources

**Previous:** v0.13.0 - MCP Resources (Breaking Changes - Phase 1)
- **NEW**: 15 MCP resources for browsable state via `gns3://` URI scheme
  - Project resources: `gns3://projects/`, `gns3://projects/{id}`, `gns3://projects/{id}/nodes/`, etc.
  - Session resources: `gns3://sessions/console/{node}`, `gns3://sessions/ssh/{node}`, etc.
  - SSH proxy resources: `gns3://proxy/status`, `gns3://proxy/sessions`
  - Provides browsable state in MCP-aware tools (inspectors, IDEs)
  - Better IDE integration with automatic discovery and autocomplete
- **REFACTORED**: Resource architecture with 3 new modules
  - `resources/resource_manager.py` - URI routing and resource dispatch (330 LOC)
  - `resources/project_resources.py` - Project/node/link/template/drawing resources (340 LOC)
  - `resources/session_resources.py` - Console/SSH session resources (230 LOC)
  - Total: 900 LOC for resource infrastructure
- **DEPRECATED**: 11 query tools (still functional, will be removed in v0.14.0)
  - `list_projects()` → `gns3://projects/`
  - `list_nodes()` → `gns3://projects/{id}/nodes/`
  - `get_node_details()` → `gns3://projects/{id}/nodes/{id}`
  - `get_links()` → `gns3://projects/{id}/links/`
  - `list_templates()` → `gns3://projects/{id}/templates/`
  - `list_drawings()` → `gns3://projects/{id}/drawings/`
  - `get_console_status()` → `gns3://sessions/console/{node}`
  - `ssh_get_status()` → `gns3://sessions/ssh/{node}`
  - `ssh_get_history()` → `gns3://sessions/ssh/{node}/history`
  - `ssh_get_command_output()` → Query resource with filtering
  - `ssh_read_buffer()` → `gns3://sessions/ssh/{node}/buffer`
- **ENHANCED**: Updated server architecture
  - Added `ResourceManager` to AppContext for centralized resource management
  - Added `@mcp.list_resources()` handler for resource discovery
  - Added `@mcp.resource("gns3://{+path}")` handler for URI-based resource access
  - Main.py version header updated to v0.13.0 with full resource documentation
- **DOCUMENTATION**: Updated SKILL.md and manifest.json
  - SKILL.md: New "MCP Resources" section with complete URI reference (66 lines)
  - Manifest.json: Updated description to emphasize MCP resources
  - Clear migration guidance from deprecated tools to resources
- **Files added**:
  - `mcp-server/server/resources/__init__.py` - Resource module initialization
  - `mcp-server/server/resources/resource_manager.py` - URI routing (330 LOC)
  - `mcp-server/server/resources/project_resources.py` - Project resources (340 LOC)
  - `mcp-server/server/resources/session_resources.py` - Session resources (230 LOC)
- **Files changed**:
  - `mcp-server/server/main.py`: Added ResourceManager import, AppContext field, lifespan initialization, 2 resource handlers, version 0.12.4→0.13.0
  - `mcp-server/manifest.json`: Version 0.12.4→0.13.0, updated descriptions
  - `skill/SKILL.md`: Added "MCP Resources" section with complete documentation
  - `CLAUDE.md`: This version entry
- **NO BREAKING CHANGES**: All existing tools still functional (deprecated but working)
  - Query tools will continue working until v0.14.0
  - Migration period allows gradual transition to resources
  - All action tools (modify state) unchanged
- **Rationale**: MCP resources provide better IDE integration, automatic discovery, and clearer separation between read (resources) and write (tools) operations. Reduces cognitive load from 30 tools to 10 core tools + 15 browsable resources.

**Previous:** v0.12.4 - Documentation and Error Handling (Patch - UX)
- **ENHANCED**: Added comprehensive SSH vs Console tool selection guidelines
  - Server-level instruction in main.py module docstring (visible on server load)
  - Individual tool docstrings updated with preference notes
  - Skill file updated with "Choosing Between SSH and Console Tools" section
- **IMPROVED**: configure_ssh error response handling
  - Better parsing of HTTP 400 (connection errors) vs HTTP 500 (server errors)
  - Graceful handling of JSON parsing failures in error responses
  - Clearer error messages distinguishing connection failures from other issues
- **GUIDANCE**: When automating network devices, always prefer SSH tools
  - SSH tools: Better reliability, automatic prompt detection, structured output
  - Console tools: Only for initial SSH configuration, troubleshooting, or devices without SSH
  - Typical workflow: Console → configure SSH → Switch to SSH tools
- **Files changed**:
  - `mcp-server/server/main.py`: Added server-level tool selection guidance (lines 6-26), updated 4 console tool docstrings
  - `mcp-server/server/tools/ssh_tools.py`: Improved error handling in configure_ssh_impl (lines 82-128)
  - `skill/SKILL.md`: Added "Choosing Between SSH and Console Tools" section (lines 26-48)
  - `mcp-server/manifest.json`: Version 0.12.3→0.12.4
  - `mcp-server/mcp-server.mcpb`: Rebuilt desktop extension (19.1MB, 2435 files)
  - `CLAUDE.md`: This version entry
- **NO BREAKING CHANGES**: All functionality unchanged, documentation and UX improvements only
- **Rationale**: Users may not realize SSH tools are preferred. Clear guidance prevents inefficient console-based automation.

**Previous:** v0.12.3 - send_and_wait_console Output Fix (Bugfix - Critical)
- **FIXED**: `send_and_wait_console()` now correctly accumulates all output during polling
  - Previous bug: Output was lost when pattern matched quickly
  - Pattern would match on first poll (0.5s), but final output was empty
  - Root cause: `get_diff_by_node()` called multiple times without accumulation
- **Implementation**: Added output accumulation pattern
  - Created `accumulated_output = []` list to collect all chunks
  - Each poll iteration appends chunk to list
  - Pattern search performed on complete accumulated output
  - Timeout case collects remaining output after timeout
  - No-pattern case collects output after 2-second wait
  - Final output is `''.join(accumulated_output)`
- **Files changed**:
  - `mcp-server/server/tools/console_tools.py`: Fixed send_and_wait_console_impl (lines 494-549)
  - `mcp-server/manifest.json`: Version 0.12.2→0.12.3
  - `mcp-server/mcp-server.mcpb`: Rebuilt desktop extension (19.1MB, 2435 files)
  - `CLAUDE.md`: This version entry
- **Testing**: User-reported example now works correctly (command output returned with pattern_found=true)
- **NO BREAKING CHANGES**: API unchanged, bug fix only
- **Rationale**: Critical fix for interactive console workflows where command output was being silently lost

**Previous:** v0.12.2 - Lightweight list_nodes Output (Bugfix - Performance)
- **FIXED**: `list_nodes()` now returns lightweight NodeSummary instead of full NodeInfo
  - Prevents large output failures with projects containing many nodes
  - Reduces output size by ~80-90% (removes ports, hardware properties, position, label data)
  - NodeSummary includes only essential fields: node_id, name, node_type, status, console_type, console
- **NEW**: Created NodeSummary model for minimal node information
  - Designed for list operations where full details aren't needed
  - Use `get_node_details()` to retrieve complete node information (ports, hardware, position, etc.)
- **ENHANCED**: Updated tool documentation to clarify lightweight output
  - list_nodes: Returns NodeSummary array (basic info)
  - get_node_details: Returns full NodeInfo (detailed info)
- **Files changed**:
  - `mcp-server/server/models.py`: Added NodeSummary model (lines 44-63)
  - `mcp-server/server/tools/node_tools.py`: Updated list_nodes_impl to use NodeSummary (lines 15-46)
  - `mcp-server/server/main.py`: Updated list_nodes() tool docstring with example output (lines 314-348)
  - `mcp-server/manifest.json`: Version 0.12.1→0.12.2, updated tool descriptions (lines 5, 7, 70, 74)
  - `mcp-server/mcp-server.mcpb`: Rebuilt desktop extension (19.1MB, 2435 files)
- **NO BREAKING CHANGES**: API remains the same, just returns less data per node
- **Rationale**: Large projects (10+ nodes with many ports) were causing token limit issues. Lightweight output fixes this while maintaining usability. Full details still available via get_node_details().

**Previous:** v0.12.1 - Grep Filtering for Buffers (Feature - Enhancement)
- **NEW**: Grep-style pattern filtering for both SSH and console buffer output
  - Optional `pattern` parameter added to `ssh_read_buffer()` and `read_console()` tools
  - Full regex support with Python `re` module
  - Grep feature set: case insensitive (-i), invert match (-v), context lines (-B/-A/-C)
  - Output format: line numbers with content (grep -n style: "LINE_NUM: line content")
- **NEW**: Pattern searches respect current mode (diff/last_page/num_pages/all)
  - Pattern filters the output AFTER mode-based retrieval
  - Example: `mode="diff", pattern="error"` searches only new output since last read
  - Example: `mode="all", pattern="interface"` searches entire buffer
- **NEW**: Context line support with overlap prevention
  - `before` parameter: Lines of context before match (grep -B)
  - `after` parameter: Lines of context after match (grep -A)
  - `context` parameter: Lines before AND after (grep -C, overrides before/after)
  - Uses set-based deduplication to prevent duplicate context lines
- **SSH Proxy v0.1.4 Changes**:
  - Added `_grep_filter()` method to SSHSessionManager (73 LOC)
  - Updated `get_buffer()` signature with 6 new grep parameters
  - Added `ReadBufferRequest` Pydantic model with grep fields
  - Changed `/ssh/read_buffer` endpoint from GET to POST (to support request body)
  - Updated version from 0.1.3 to 0.1.4
- **MCP Server v0.12.1 Changes**:
  - Added `_grep_filter()` helper function to console_tools.py (72 LOC)
  - Updated `read_console_impl()` signature with 6 new grep parameters
  - Updated `read_console()` tool registration with grep parameters and examples
  - Updated manifest.json version from 0.12.0 to 0.12.1
- **Files added**:
  - None (all changes to existing files)
- **Files changed**:
  - `ssh-proxy/server/session_manager.py`: Added _grep_filter() method (lines 585-657), updated get_buffer() signature (lines 547-616)
  - `ssh-proxy/server/models.py`: Added ReadBufferRequest model with grep parameters (lines 132-167)
  - `ssh-proxy/server/main.py`: Changed endpoint GET→POST (line 244), updated version to 0.1.4 (lines 81, 96)
  - `mcp-server/server/tools/console_tools.py`: Added _grep_filter() function (lines 216-287), updated read_console_impl() (lines 116-127)
  - `mcp-server/server/main.py`: Updated read_console() tool with grep parameters (lines 458-509)
  - `mcp-server/manifest.json`: Updated version to 0.12.1 (line 5)
  - `mcp-server/mcp-server.mcpb`: Rebuilt by pre-commit hook
- **Usage Examples**:
  ```python
  # Find errors in new output (case insensitive)
  read_console("R1", mode="diff", pattern="error", case_insensitive=True)

  # Find interfaces with 2 lines of context
  read_console("R1", mode="all", pattern="GigabitEthernet", context=2)

  # Find non-matching lines (invert)
  ssh_read_buffer("R1", mode="last_page", pattern="success", invert=True)
  ```
- **NO BREAKING CHANGES**: All new parameters are optional with backward-compatible defaults
- **Deployment**:
  - SSH proxy: Built and deployed as `chistokhinsv/gns3-ssh-proxy:v0.1.4`
  - MCP server: Packaged as gns3-mcp@0.12.1 desktop extension
- **Rationale**: Enables efficient log analysis and troubleshooting by filtering large console/SSH buffers. Grep-style interface familiar to network engineers. Maintains full backward compatibility.

**SSH Proxy v0.1.5** (Patch - API monitoring endpoints)
- **NEW**: Added `/version` endpoint for version tracking
  - GET `/version` - Returns service version and name
  - Useful for compatibility checking and deployment tracking
  - Example response: `{"version": "0.1.5", "service": "gns3-ssh-proxy"}`
- **ENHANCED**: Improved `/health` endpoint documentation
  - GET `/health` - Returns service health status, name, and version
  - Example response: `{"status": "healthy", "service": "gns3-ssh-proxy", "version": "0.1.5"}`
- **Files changed**:
  - `ssh-proxy/server/main.py`: Added /version endpoint (lines 104-118), updated health endpoint docs (lines 90-101), version 0.1.4→0.1.5 (lines 81, 100, 117)
- **Testing**: Verified both endpoints on deployed container
  - `/health`: ✅ Returns healthy status with version
  - `/version`: ✅ Returns version 0.1.5
- **Deployment**: Built and deployed as `chistokhinsv/gns3-ssh-proxy:v0.1.5` and `latest` tags
- **Rationale**: Standard REST API practice to provide health/version endpoints for monitoring, logging, and troubleshooting

**Previous:** v0.12.0 - SSH Proxy Service (Feature - Phase 1)
- **NEW**: SSH proxy service (FastAPI container, Python 3.13-slim)
  - Separate Docker container with network mode=host for GNS3 lab access
  - Port 8022 (SSH-like mnemonic)
  - Docker Hub: `chistokhinsv/gns3-ssh-proxy:v0.1.3`
  - Deployment via SSH to GNS3 host
- **NEW**: Dual storage architecture
  - **Storage System 1**: Continuous buffer (10MB max, like console manager)
  - **Storage System 2**: Command history with per-command jobs
  - Every command creates Job record (even synchronous executions)
  - Jobs include: job_id, command, output, timestamps, execution_time, sequence_number
  - Searchable history with execution order tracking
- **NEW**: Adaptive async command execution
  - Commands poll for wait_timeout seconds
  - Return output if completes quickly (<wait_timeout)
  - Return job_id for polling if still running (>wait_timeout)
  - Supports 15+ minute long-running commands (read_timeout=900)
- **NEW**: 9 MCP tools for SSH automation
  - `configure_ssh()` - Create/recreate SSH session (auto-drops on IP change)
  - `ssh_send_command()` - Execute show commands with adaptive async
  - `ssh_send_config_set()` - Send configuration commands
  - `ssh_read_buffer()` - Read continuous buffer (modes: diff/last_page/num_pages/all)
  - `ssh_get_history()` - List command history (limit, search filter)
  - `ssh_get_command_output()` - Get specific job's full output
  - `ssh_get_status()` - Check session status
  - `ssh_cleanup_sessions()` - Clean orphaned/all sessions
  - `ssh_get_job_status()` - Poll async job status
- **NEW**: SSH connection error detection
  - Intelligent error classification (authentication_failed, connection_refused, timeout, host_unreachable)
  - Helpful suggestions for each error type
  - Emphasizes using console tools to configure SSH access first
- **NEW**: Netmiko integration
  - Supports 200+ device types (cisco_ios, juniper, arista_eos, etc.)
  - Interactive prompt handling with expect_string parameter
  - Long-running command support with read_timeout=0 (no timeout)
  - Timing-based detection for Y/N confirmations
- **Files added**:
  - `ssh-proxy/` directory: FastAPI service
    - `server/models.py` (380 LOC): Pydantic models with error classification
    - `server/session_manager.py` (560 LOC): Dual storage + SSH lifecycle
    - `server/main.py` (450 LOC): FastAPI app with 10 endpoints
  - `ssh-proxy/Dockerfile`: Python 3.13-slim, network mode=host
  - `ssh-proxy/requirements.txt`: fastapi, uvicorn, netmiko, pydantic, httpx
  - `ssh-proxy/README.md`: Service documentation
  - `mcp-server/server/tools/ssh_tools.py` (370 LOC): 9 MCP tool implementations
  - `DEPLOYMENT.md`: Docker deployment guide for GNS3 hosts
- **Files changed**:
  - `mcp-server/server/main.py`: Added 9 SSH tool registrations, updated version header to v0.12.0
  - `mcp-server/server/tools/ssh_tools.py`: Fixed SSH_PROXY_URL to use GNS3_HOST from environment
  - `mcp-server/manifest.json`: Updated to v0.12.0, added 9 SSH tool definitions
  - `CLAUDE.md`: This version entry
- **Workflow Integration**:
  1. Use console tools to enable SSH on device (send_console)
  2. Call configure_ssh() to establish SSH session
  3. Use SSH tools for automation (send_command, send_config_set)
  4. Review history with ssh_get_history() and ssh_get_command_output()
- **NO BREAKING CHANGES**: All existing tools unchanged, SSH tools additive
- **Rationale**: Enables SSH automation for devices without telnet console, handles interactive prompts and long-running installations, maintains searchable command history with audit trail

**SSH Proxy v0.1.3** (Feature - Version tracking)
- **NEW**: Added version field to configure_ssh response
  - Returns SSH proxy service version from container
  - Helps track deployed version when troubleshooting
  - Example: `{"version": "0.1.3", ...}`
- **Files changed**:
  - `ssh-proxy/server/models.py`: Added version field to ConfigureSSHResponse
  - `ssh-proxy/server/main.py`: Version 0.1.2→0.1.3, configure_ssh returns app.version
- **Testing**: Verified version field present in configure_ssh response
- **Deployment**: Built and deployed as `chistokhinsv/gns3-ssh-proxy:v0.1.3` and `latest` tags
- **Rationale**: Version visibility improves debugging and deployment tracking

**SSH Proxy v0.1.2** (Patch - Netmiko timeout and error handling fixes)
- **FIXED**: Netmiko prompt detection timeout on Alpine Linux
  - Increased delay_factor from 2 to 4 (provides 20s read window with read_timeout=5)
  - Commands now complete in ~0.1s instead of timing out after 11s
  - Empty output bug resolved - commands now capture actual output
- **FIXED**: Exception handlers masking errors
  - Changed to return `completed: False` for failures (was incorrectly True)
  - Now includes error messages, execution_time calculation, and partial output
  - Provides actionable error details instead of silent failures
- **Files changed**:
  - `ssh-proxy/server/session_manager.py`: delay_factor 2→4 (line 364), exception handlers rewritten (lines 323-339, 467-482)
  - `ssh-proxy/server/main.py`: Version 0.1.1→0.1.2
  - `.gitignore`: Added .coverage
- **Testing**: Verified on B-Rec1 (Alpine Linux):
  - `doas rc-service pdns-recursor status`: ✅ 0.107s, output: " * status: started"
  - `echo "test" && pwd && whoami`: ✅ 0.107s, complete output captured
  - Container logs: No "Pattern not detected" errors
- **Deployment**: Built and deployed as `chistokhinsv/gns3-ssh-proxy:v0.1.2` and `latest` tags
- **Rationale**: Resolves critical bugs where SSH commands returned empty output with 11-second timeouts due to Netmiko prompt detection issues

**Previous:** v0.11.1 - Console Output Pagination (Patch)
- **NEW**: Added `num_pages` mode to `read_console()` tool
  - Retrieve multiple pages of console output (~25 lines per page)
  - New parameter: `pages` (integer, default: 1, only valid with mode="num_pages")
  - Usage: `read_console("R1", mode="num_pages", pages=3)` returns last 75 lines
- **ENHANCED**: Parameter validation
  - Using `pages` parameter with other modes returns clear error message
  - Error example: "Error: 'pages' parameter can only be used with mode='num_pages'"
- **ENHANCED**: Documentation improvements
  - Added warning to `all` mode about potential >25000 token output
  - Recommends using `num_pages` mode instead of `all` for large buffers
  - Added examples for num_pages mode usage
- **Files changed**:
  - `mcp-server/server/tools/console_tools.py`: Updated read_console_impl() (lines 116-213)
  - `mcp-server/server/main.py`: Updated read_console() tool definition (lines 453-508)
  - `manifest.json`: Updated to v0.11.1, updated tool description
  - `CLAUDE.md`: This version entry
- **NO BREAKING CHANGES**: All existing modes ('diff', 'last_page', 'all') work unchanged
- **Testing**: 5 unit tests passed (default pages, multiple pages, overflow, error handling, backward compatibility)
- **Rationale**: Provides flexible console buffer retrieval without overwhelming token limits. Alternative to 'all' mode for large outputs.

**Previous:** v0.11.0 - Code Organization Refactoring (Refactor)
- **NEW**: Console manager unit tests for critical async code
  - 38 unit tests covering ConsoleManager class (560 LOC test file)
  - 76% coverage on console_manager.py (374 LOC, critical async telnet session handling)
  - Mocked telnetlib3 connections for isolated unit testing
  - Test categories: connection management (8), session lifecycle (6), buffer management (5), data processing (4), convenience methods (6), concurrent access (2), helper functions (5), dataclass (4)
- **REFACTORED**: Extracted 19 tool implementations to 6 category modules
  - Created `mcp-server/server/tools/` directory structure
  - `project_tools.py` (95 LOC): list_projects, open_project
  - `node_tools.py` (460 LOC): list_nodes, get_node_details, set_node, create_node, delete_node
  - `console_tools.py` (485 LOC): send_console, read_console, disconnect_console, get_console_status, send_and_wait_console, send_keystroke
  - `link_tools.py` (290 LOC): get_links, set_connection
  - `drawing_tools.py` (230 LOC): list_drawings, create_drawing, delete_drawing
  - `template_tools.py` (45 LOC): list_templates
- **IMPROVED**: Main.py delegation pattern for maintainability
  - All `@mcp.tool()` decorators remain in main.py (centralized tool registration)
  - Tool functions delegate to `{name}_impl(app, ...)` in category modules
  - Shared `_auto_connect_console()` helper extracted to console_tools.py
- **IMPROVED**: Reduced main.py from 1,836 to 914 LOC (50% reduction, 922 lines saved)
  - Better code organization and discoverability
  - Easier to maintain and test individual tool categories
  - No changes to tool interfaces or behavior
- **Files added**:
  - `tests/unit/test_console_manager.py`: 38 tests for console manager (560 LOC)
  - `mcp-server/server/tools/__init__.py`: tools directory marker
  - `mcp-server/server/tools/project_tools.py`: project management tools
  - `mcp-server/server/tools/node_tools.py`: node management tools
  - `mcp-server/server/tools/console_tools.py`: console interaction tools
  - `mcp-server/server/tools/link_tools.py`: link/connection tools
  - `mcp-server/server/tools/drawing_tools.py`: drawing object tools
  - `mcp-server/server/tools/template_tools.py`: template tools
- **Files changed**:
  - `main.py`: Import tool implementations, delegate to _impl() functions (1,836 → 914 LOC)
  - `manifest.json`: Updated to v0.11.0
  - `CLAUDE.md`: This version entry
- **NO BREAKING CHANGES**: All tool interfaces remain unchanged
- **Rationale**: Console manager tests address P0 priority gap (0% coverage on 374 LOC critical code). Tool extraction improves maintainability without changing functionality. Addresses architecture review recommendations.

**Previous:** v0.10.0 - Testing Infrastructure (Feature)
- **NEW**: Comprehensive unit testing infrastructure with pytest
  - pytest 8.4.2 with plugins (pytest-asyncio, pytest-mock, pytest-cov)
  - 134 unit tests covering critical modules
  - pytest.ini with coverage settings and test markers
  - tests/conftest.py with shared fixtures
- **Test Coverage Achieved**:
  - models.py: 100% coverage (41 tests)
  - link_validator.py: 96% coverage (37 tests)
  - gns3_client.py: 75% coverage (30 tests)
  - export_tools.py: 19% coverage (26 tests, helper functions fully tested)
  - Overall: 30% total coverage (focused on critical paths)
- **NEW**: Extracted export functionality to separate module
  - `mcp-server/server/export_tools.py` (547 lines)
  - Reduced `main.py` from 2,410 to 1,836 LOC
  - Functions: add_font_fallbacks(), create_*_svg(), export_topology_diagram()
- **Files added**:
  - `pytest.ini`: pytest configuration with coverage settings
  - `tests/conftest.py`: shared test fixtures
  - `tests/unit/test_models.py`: 41 tests for Pydantic models
  - `tests/unit/test_link_validator.py`: 37 tests for two-phase validation
  - `tests/unit/test_gns3_client.py`: 30 tests for API client
  - `tests/unit/test_export_tools.py`: 26 tests for SVG generation
  - `mcp-server/server/export_tools.py`: extracted export module
- **Files changed**:
  - `requirements.txt`: Added pytest dependencies
  - `mcp-server/server/main.py`: Import export functions from export_tools.py
- **Rationale**: Testing infrastructure ensures code quality and prevents regressions. Export extraction improves maintainability.

**Previous:** v0.9.0 - Major Refactoring (Breaking Changes)
- **REMOVED**: Caching infrastructure completely
  - Deleted `cache.py` (274 lines)
  - Removed all cache usage from `main.py` (17 locations)
  - Removed `force_refresh` parameter from 4 tools (list_projects, list_nodes, get_node_details, get_links)
  - Direct API calls throughout - simpler, faster for local/close labs
- **REMOVED**: `detect_console_state()` tool and DEVICE_PATTERNS
  - Deleted 165 lines of console state detection code
  - Removed DEVICE_PATTERNS dictionary (41 lines) and COMMON_ERROR_PATTERNS (10 lines)
  - Pattern matching was unreliable (80% dead code per architecture review)
- **BREAKING**: `read_console()` API redesigned
  - Previous: `read_console(node, diff: bool, last_page: bool)`
  - Now: `read_console(node, mode: str = "diff")`
  - Mode values: `"diff"` (default), `"last_page"`, `"all"`
  - Added parameter validation with clear error messages
- **ENHANCED**: ErrorResponse model now includes `suggested_action` field
  - Critical errors now provide actionable guidance
  - 8 key validation errors updated with suggested_action
- **ENHANCED**: `set_node()` docstring now documents validation rules
  - Clarifies which parameters require stopped nodes
  - Documents node-type-specific parameters (QEMU, ethernet_switch)
- **FIXED**: Version mismatch in main.py header (v0.6.4 → v0.9.0)
- **Files changed**:
  - `cache.py`: DELETED
  - `main.py`: Cache removed, read_console() redesigned, detect_console_state() removed, version updated, docstrings enhanced
  - `models.py`: Added `suggested_action` to ErrorResponse
  - `manifest.json`: Version 0.9.0, removed detect_console_state tool, updated descriptions
  - `CLAUDE.md`: This version entry
- **Migration Guide**:
  - Remove `force_refresh` parameters from tool calls
  - Update `read_console()` calls: `diff=True` → `mode="diff"`, `diff=False, last_page=True` → `mode="last_page"`, `diff=False, last_page=False` → `mode="all"`
  - Replace `detect_console_state()` with manual prompt checking via `read_console()`
- **Rationale**: Caching added unnecessary complexity for local labs. State detection was unreliable. New API is clearer and more maintainable.

**Previous:** v0.8.1 - Documentation Enhancement (Patch)
- **ENHANCED**: Added best practice guidance for `send_and_wait_console()`
  - Tool docstring now includes prominent "BEST PRACTICE" section
  - Recommends checking prompt first with `read_console()` before using wait patterns
  - Added example showing recommended workflow: check prompt → use in automation
  - TIP added to `wait_pattern` parameter documentation
- **SKILL.md**: New section "Using send_and_wait_console for Automation"
  - 3-step workflow guide with examples
  - Comparison: when to use send_and_wait vs send+read
  - Best practices for avoiding common issues (wrong prompts, timeouts, missed output)
- **Files changed**:
  - `main.py`: Enhanced `send_and_wait_console()` docstring (lines 1247-1307)
  - `SKILL.md`: Added automation section and best practices (lines 139-184)
  - `manifest.json`: Updated to v0.8.1
- **Rationale**: Prevents common user errors from incorrect prompt patterns

**Previous:** v0.8.0 - Tool Redesign (Breaking Changes)
- **BREAKING**: `read_console()` now defaults to `diff=True` (was `diff=False`)
  - Previous: `read_console(node)` returned full buffer
  - Now: `read_console(node)` returns only new output since last read
  - Migration: Use `read_console(node, diff=False, last_page=False)` for old behavior
- **NEW**: `read_console()` added `last_page=True` parameter for last ~25 lines
  - `read_console(node)` - new output only (diff mode, default)
  - `read_console(node, diff=False, last_page=True)` - last ~25 lines
  - `read_console(node, diff=False, last_page=False)` - full buffer
- **BREAKING**: Removed individual drawing tools: `create_rectangle()`, `create_text()`, `create_ellipse()`
- **NEW**: Unified `create_drawing(drawing_type, ...)` tool
  - Supports `drawing_type`: "rectangle", "ellipse", "line", "text"
  - **Rectangle**: `create_drawing("rectangle", x, y, width=W, height=H, fill_color, border_color)`
  - **Ellipse**: `create_drawing("ellipse", x, y, rx=R1, ry=R2, fill_color, border_color)`
  - **Line**: `create_drawing("line", x, y, x2=X, y2=Y, border_color, border_width)` - NEW type
  - **Text**: `create_drawing("text", x, y, text=T, font_size, color, font_weight)`
- **Files changed**:
  - `main.py`: Modified `read_console()` defaults (line 1055), added unified `create_drawing()` (lines 2003-2136)
  - `main.py`: Added `create_line_svg()` helper function (lines 258-283)
  - `main.py`: Removed `create_rectangle()`, `create_text()`, `create_ellipse()` tools
  - `manifest.json`: Updated tool definitions for v0.8.0
  - `SKILL.md`: Updated documentation with new tool interfaces
- **Rationale**: Diff mode is most common use case for interactive sessions; unified drawing tool reduces API surface

**Previous:** v0.7.0 - Adapter Name Support (Feature)
- **NEW**: `set_connection()` now accepts adapter names in addition to numeric indexes
- **Adapter names**: Use port names like "eth0", "GigabitEthernet0/0", "Ethernet0" for better readability
- **Backward compatible**: Numeric adapter indexes still work (0, 1, 2, ...)
- **Enhanced responses**: Include both human-readable port names AND adapter/port numbers
- **Example**: `"adapter_a": 0, "port_a_name": "eth0"` in confirmation
- **Files changed**:
  - `link_validator.py`: Added `resolve_adapter_identifier()` method with port name mapping
  - `models.py`: Updated `ConnectOperation` to accept `Union[str, int]` for adapters
  - `main.py`: Resolution and validation logic for adapter names
  - `SKILL.md`: Updated documentation with adapter name examples
- **Use case**: More intuitive link creation - `adapter_a: "eth0"` instead of `adapter_a: 0`

**Previous:** v0.6.5 - Empty Response Handling (Bugfix)
- **Fixed node actions**: `start_node()`, `stop_node()`, `suspend_node()`, `reload_node()` now handle empty API responses
- **Issue**: GNS3 API returns HTTP 204 No Content (empty body) for these actions
- **Error**: Previously failed with "Expecting value: line 1 column 1 (char 0)" JSON parse error
- **Fix**: Check response status code and content before parsing JSON, return empty dict for 204/empty responses
- **Impact**: All node control actions now work correctly
- **Files changed**: `mcp-server/server/gns3_client.py` lines 112-162

**Previous:** v0.6.4 - Z-order Rendering Fix (Bugfix)
- **Fixed z-order**: Links render below nodes (z=min(nodes)-0.5), drawings/nodes intermixed by z-value
- **Painter's algorithm**: Ensures correct layering for overlapping elements

**Previous:** v0.6.3 - Font Fallback Chain (Bugfix)
- **Fixed font rendering**: Added CSS-style font fallback chains for consistent cross-platform SVG/PNG export
- **TypeWriter fallback**: TypeWriter → Courier New → Courier → Liberation Mono → Consolas → monospace
- **Display font fallback**: Gerbera Black/decorative → Georgia → Times New Roman → serif
- **Implementation**: `add_font_fallbacks()` helper function processes SVG style strings
- **Applied to**: Node labels and drawing text elements
- **Why needed**: Qt (GNS3 GUI) auto-resolves "TypeWriter" to system monospace, but SVG renderers need explicit fallbacks

**Previous:** v0.6.2 - Label Rendering Fix (Bugfix)
- **Fixed label positioning**: `export_topology_diagram()` now matches official GNS3 GUI rendering
- **Auto-centering**: Labels with x=None properly center above nodes (y=-25)
- **Dynamic text-anchor**: Text alignment (start/middle/end) based on label position
- **No offset additions**: Uses GNS3-stored positions directly, no incorrect calculations
- See [Label Rendering Implementation](#label-rendering-implementation-v062) section for details

**Previous:** v0.6.1 - Newline Normalization & Special Keystrokes
- **FIXED**: All newlines automatically converted to \r\n (CR+LF) for console compatibility
  - Copy-paste multi-line text directly - newlines just work
  - `send_console()` and `send_and_wait_console()` normalize all line endings (\n, \r, \r\n → \r\n)
  - Add `raw=True` parameter to disable processing
- **NEW**: `send_keystroke()` - Send special keys for TUI navigation and vim editing
  - Navigation: up, down, left, right, home, end, pageup, pagedown
  - Editing: enter (sends \r\n), backspace, delete, tab, esc
  - Control: ctrl_c, ctrl_d, ctrl_z, ctrl_a, ctrl_e
  - Function keys: f1-f12
- **FIXED**: `detect_console_state()` now checks only last non-empty line (not 5 lines)
  - Prevents detecting old prompts instead of current state
  - Fixed MikroTik password patterns: "new password>" not "new password:"

**Previous:** v0.6.0 - Interactive Console Tools
- **NEW**: `send_and_wait_console()` - Send command and wait for prompt pattern
  - Regex pattern matching with 0.5s polling interval
  - Timeout support for reliable automation
- **NEW**: `detect_console_state()` - Auto-detect device type and console state
  - Detects: Cisco IOS, MikroTik, Juniper, Arista, Linux
  - Identifies 9 console states with confidence scoring
- **ENHANCED**: Console tool docstrings with timing guidance
- Added DEVICE_PATTERNS library for auto-detection

**Previous:** v0.5.1 - Label Alignment
- Fixed node label alignment - right-aligned and vertically centered
- Note: v0.6.2 supersedes this with accurate GNS3-matching positioning

**Previous:** v0.5.0 - Port Status Indicators
- Topology export shows port status indicators
  - Green = port active (node started, link not suspended)
  - Red = port stopped (node stopped or link suspended)
- Enhanced `export_topology_diagram()` with visual status

**Previous:** v0.4.2 - Topology Export
- **NEW**: `export_topology_diagram()` - Export topology as SVG/PNG
- Renders nodes, links, and drawings
- Auto-fits to content with padding
- Supports custom crop regions

**Previous:** v0.4.0 - Node Creation & Drawing Objects
- **NEW**: `delete_node` - Remove nodes from projects
- **NEW**: `list_templates` - List available GNS3 templates
- **NEW**: `create_node` - Create nodes from templates at specified coordinates
- **NEW**: `list_drawings` - List drawing objects in project
- **NEW**: `create_rectangle` - Create colored rectangle drawings
- **NEW**: `create_text` - Create text labels with formatting
- **NEW**: `create_ellipse` - Create ellipse/circle drawings

**Previous:** v0.3.0 - Major Refactoring (Breaking Changes)
- **Type-safe operations**: Pydantic v2 models for all data structures
- **Two-phase validation**: Prevents partial topology changes in `set_connection()`
- **Performance caching**: 10× faster with TTL-based cache (30s for nodes/links, 60s for projects)
- **Multi-adapter support**: `set_connection()` now requires `adapter_a`/`adapter_b` parameters
- **JSON outputs**: All tools return structured JSON instead of formatted strings
- **New tool**: `get_console_status()` for checking console connection state
- **Better errors**: Detailed validation messages with suggested fixes
- See [MIGRATION_v0.3.md](MIGRATION_v0.3.md) for complete migration guide

**Previous:** v0.2.1 - Link Discovery
- Added `get_links()` tool for topology discovery
- Enhanced `set_connection()` with workflow guidance

**Previous:** v0.2.0 - Auto-Connect & Unified Control
- Console tools now use `node_name` instead of `session_id` (auto-connect)
- `start_node` + `stop_node` → unified `set_node` tool
- Added `set_connection` tool for link management

## Version Management

**CRITICAL**: Update extension version every time a change is made.

- **Bugfix**: Increment patch version (0.1.1 → 0.1.2)
- **New feature**: Increment minor version (0.1.2 → 0.2.0)
- **Breaking change**: Increment major version (0.2.0 → 1.0.0)

**Version Synchronization:**
- Server code and desktop extension (.mcpb) must have the **same version**
- Desktop extension is **automatically rebuilt** by git pre-commit hook
- If versions mismatch, Claude Desktop may use outdated code

**Steps to update version:**
1. Edit `mcp-server/manifest.json` - update `"version"` field
2. Commit your changes - pre-commit hook automatically rebuilds .mcpb
3. Verify version in build output: `gns3-mcp@X.Y.Z`
4. Reinstall in Claude Desktop (double-click .mcpb)

**Pre-commit Hook:**
- Located at `.git/hooks/pre-commit` (and `.bat` for Windows)
- Automatically detects changes to `mcp-server/server/` or `manifest.json`
- Rebuilds desktop extension and adds to commit
- Aborts commit if build fails

## File Structure

```
008. GNS3 MCP/
├── mcp-server/
│   ├── server/
│   │   ├── main.py              # FastMCP server (11 tools)
│   │   ├── gns3_client.py       # GNS3 v3 API client
│   │   ├── console_manager.py   # Telnet console manager
│   │   ├── models.py            # [v0.3.0] Pydantic data models
│   │   ├── link_validator.py    # [v0.3.0] Two-phase link validation
│   │   └── cache.py             # [v0.3.0] TTL-based data caching
│   ├── lib/                     # Bundled Python dependencies
│   ├── manifest.json            # Desktop extension manifest
│   ├── start_mcp.py            # Wrapper script for .env loading
│   └── mcp-server.mcpb          # Packaged extension
├── skill/
│   ├── SKILL.md                 # Agent skill documentation
│   └── examples/                # GNS3 workflow examples
├── tests/
│   ├── test_mcp_console.py      # Console manager tests
│   ├── interactive_console_test.py
│   ├── list_nodes_helper.py     # Node discovery helper
│   └── TEST_RESULTS.md          # Latest test results
├── .env                         # GNS3 credentials (gitignored)
├── .mcp.json                    # MCP server config (Claude Code)
├── requirements.txt             # Python dependencies
├── MIGRATION_v0.3.md           # [v0.3.0] Migration guide
├── REFACTORING_STATUS_v0.3.md  # [v0.3.0] Refactoring documentation
└── README.md                    # User documentation
```

## Development Workflow

### 1. Making Code Changes

**Before editing server code:**
```bash
# Read the current implementation
cat mcp-server/server/main.py
cat mcp-server/server/gns3_client.py
cat mcp-server/server/console_manager.py

# [v0.3.0] Architecture files
cat mcp-server/server/models.py        # Pydantic data models
cat mcp-server/server/link_validator.py  # Two-phase validation
cat mcp-server/server/cache.py         # TTL-based caching
```

**After editing:**
1. Test locally first (see Testing section)
2. Update version in manifest.json (increment appropriately)
3. Commit changes - pre-commit hook automatically rebuilds extension
4. Verify version in hook output: `gns3-mcp@X.Y.Z`
5. Reinstall and test in Claude Desktop (double-click .mcpb)

### 2. Testing

**Always test changes before packaging:**

```bash
# Test node discovery
python tests/list_nodes_helper.py

# Test console directly (verify telnet works)
python tests/interactive_console_test.py --port <PORT>

# Test ConsoleManager
python tests/test_mcp_console.py --port <PORT>

# Manual MCP server test
cd mcp-server
mcp dev server/main.py --host 192.168.1.20 --port 80 --username admin --password <PASS>
```

**Test device:** AlpineLinuxTest-1 (port 5014)
- Fast boot, simple login
- Good for automated testing
- See `tests/ALPINE_SETUP_GUIDE.md`

### 3. Packaging

**After any server code change:**

```bash
cd mcp-server
npx @anthropic-ai/mcpb pack

# Output: mcp-server.mcpb (~19MB)
```

**Validate manifest before packaging:**
```bash
npx @anthropic-ai/mcpb validate manifest.json
```

### 4. Installation

#### Claude Desktop

**To install/update in Claude Desktop:**
1. Close Claude Desktop completely
2. Double-click `mcp-server.mcpb`
3. Restart Claude Desktop
4. Check logs: `C:\Users\mail4\AppData\Roaming\Claude\logs\mcp-server-GNS3 Lab Controller.log`

#### Claude Code

**Project-scoped installation (recommended):**

Configuration files:
- `.mcp.json` - MCP server configuration (committed to git)
- `.env` - Credentials (gitignored)
- `mcp-server/start_mcp.py` - Wrapper script that loads .env

The wrapper script automatically:
1. Loads environment variables from `.env`
2. Adds `mcp-server/lib` and `mcp-server/server` to Python path
3. Starts the MCP server with credentials from environment

**Verify installation:**
```bash
claude mcp get gns3-lab
# Should show: Status: ✓ Connected
```

**Important:** MCP tools load at conversation start. After configuring the server, start a new conversation to access the tools.

**Global installation (optional):**
```powershell
claude mcp add --transport stdio gns3-lab --scope user -- `
  python "C:\HOME\1. Scripts\008. GNS3 MCP\mcp-server\start_mcp.py"
```

**Key differences:**
- Claude Desktop: `.mcpb` package (user-wide), manual credential config
- Claude Code: `.mcp.json` + wrapper script (project-scoped), auto-loads .env
- Both use same Python server code

## Common Tasks

### Add New MCP Tool

1. Edit `mcp-server/server/main.py`
2. Add function decorated with `@mcp.tool()`:
   ```python
   @mcp.tool()
   async def new_tool(ctx: Context, param: str) -> str:
       """Tool description"""
       # Implementation
       return "result"
   ```
3. Update version in manifest.json
4. Test with `mcp dev`
5. Package and install

### Modify GNS3 API Client

1. Edit `mcp-server/server/gns3_client.py`
2. Refer to `data/SESSION.txt` for API endpoints
3. Use `httpx` async client
4. Return parsed JSON, not raw responses
5. Test changes before packaging

### Update Console Manager

1. Edit `mcp-server/server/console_manager.py`
2. Use telnetlib3 for connections
3. Keep background reader async task pattern
4. Test with `tests/test_mcp_console.py`
5. Verify buffer management and timeouts

### Update Agent Skill

1. Edit `skill/SKILL.md`
2. Follow progressive disclosure structure
3. Add device-specific commands if needed
4. Include examples for common workflows
5. No packaging needed (skill is separate)

## Dependency Management

**Python dependencies** (requirements.txt):
- `mcp>=1.2.1` - MCP protocol
- `httpx>=0.28.1` - HTTP client
- `telnetlib3>=2.0.4` - Telnet client
- `pydantic>=2.0.0` - Type-safe data models [v0.3.0]
- `python-dotenv>=1.1.1` - Environment variables

**Bundled dependencies** (mcp-server/lib/):
- Automatically bundled during packaging
- Do NOT commit lib/ folder to git
- Generated by: `pip install --target=lib -r requirements.txt`

**Update dependencies:**
```bash
# Update requirements.txt with new versions
pip install <package>==<version>

# Rebuild lib folder (if needed)
cd mcp-server
pip install --target=lib mcp httpx telnetlib3 pydantic python-dotenv
```

## Environment Variables

**Development** (.env file):
```
USER=admin
PASSWORD=<your-gns3-password>
GNS3_HOST=192.168.1.20
GNS3_PORT=80
```

**Production** (Claude Desktop):
- Configured via extension manifest
- User provides in Claude Desktop settings
- See manifest.json `user_config` section

## Troubleshooting

### Extension Won't Load in Claude Desktop

1. Check logs: `C:\Users\mail4\AppData\Roaming\Claude\logs\`
2. Validate manifest: `npx @anthropic-ai/mcpb validate manifest.json`
3. Verify PYTHONPATH in manifest includes lib/ and server/
4. Check Python dependencies are bundled in lib/

### Console Connection Fails

1. Test direct telnet: `python tests/interactive_console_test.py --port <PORT>`
2. Verify node is started in GNS3
3. Check console type is `telnet` (not vnc, spice, etc.)
4. Wait 5-10 seconds after node start before connecting
5. Review console_manager.py logs

### Authentication Fails

1. Verify credentials in .env
2. Test with curl:
   ```bash
   curl -X POST http://192.168.1.20/v3/access/users/authenticate \
     -H "Content-Type: application/json" \
     -d '{"username":"admin","password":"YOUR_PASSWORD"}'
   ```
3. Check GNS3 server is running
4. Verify GNS3 v3 API is enabled

### ModuleNotFoundError

1. Check lib/ folder exists and contains dependencies
2. Verify PYTHONPATH in manifest.json
3. Repackage extension: `npx @anthropic-ai/mcpb pack`
4. Use semicolon (;) separator on Windows, not colon (:)

## Code Conventions

### Logging

Use Python logging module with timestamp format:
```python
import logging

logger = logging.getLogger(__name__)
# Format: [HH:MM:SS DD.MM.YYYY] message
```

### Error Handling

- Always catch and log exceptions
- Return descriptive error messages to user
- Don't expose sensitive data in errors
- Use try/except in all async functions

### Async Patterns

- Use `async def` for I/O operations
- Use `await` for async calls
- Use `asyncio.create_task()` for background tasks
- Clean up tasks on disconnect

### Type Hints

Use type hints for function parameters and returns:
```python
async def connect(self, host: str, port: int) -> str:
    """Type hints help with IDE support"""
    pass
```

## v0.3.0 Architecture

### Pydantic Models (models.py)

All data structures use Pydantic v2 BaseModel for:
- Type validation at runtime
- JSON schema generation
- Clear error messages
- IDE autocomplete support

Example:
```python
from models import ConnectOperation, LinkInfo

# Validate connection operation
op = ConnectOperation(
    action="connect",
    node_a="R1",
    node_b="R2",
    port_a=0,
    port_b=0,
    adapter_a=0,  # Required in v0.3.0
    adapter_b=0
)

# Access validated fields
print(op.node_a)  # Type-safe
```

### Two-Phase Validation (link_validator.py)

LinkValidator prevents partial topology changes:

**Phase 1: Validation**
- Check all nodes exist
- Verify ports are available
- Validate adapters exist on devices
- Build simulated state (no API calls)

**Phase 2: Execution**
- Only execute if ALL operations valid
- Cache invalidation after success
- Atomic topology changes

Example workflow:
```python
validator = LinkValidator(nodes, links)

# Validate ALL operations first
for op in operations:
    error = validator.validate_connect(...)
    if error:
        return error_response  # STOP - no changes made

# All valid - execute ALL operations
for op in operations:
    await gns3.create_link(...)  # Safe - validated
```

### TTL-Based Caching (cache.py)

DataCache reduces API calls:
- 30s TTL for nodes and links
- 60s TTL for projects
- Automatic invalidation after mutations
- 10× performance improvement for batch operations

Example:
```python
# First call - cache miss (API call)
nodes = await cache.get_nodes(project_id, fetch_fn)

# Second call within 30s - cache hit (instant)
nodes = await cache.get_nodes(project_id, fetch_fn)

# Force refresh (bypass cache)
nodes = await cache.get_nodes(project_id, fetch_fn, force_refresh=True)

# Invalidate after mutations
await cache.invalidate_nodes(project_id)
```

### JSON Output Format

All tools return JSON for structured parsing:

```python
# Tool returns JSON string
result = await list_nodes()

# Parse in Python
import json
nodes = json.loads(result)
for node in nodes:
    print(node['name'], node['status'])

# Error responses are also JSON
{
    "error": "Validation failed at operation 0",
    "details": "Port R1 adapter 0 port 0 already connected...",
    "operation_index": 0
}
```

## Label Rendering Implementation (v0.6.2)

### Overview

The `export_topology_diagram()` tool creates SVG/PNG diagrams that visually match the official GNS3 GUI rendering. Version 0.6.2 fixed label positioning to accurately replicate GNS3's label behavior.

### GNS3 Label Coordinate System

**Official GNS3 Behavior** (from `gns3-gui/gns3/items/node_item.py`):

```python
# GNS3 stores labels with these properties:
label = {
    "text": "NodeName",           # Label text
    "x": 10,                      # X offset from node top-left (or None for auto-center)
    "y": -25,                     # Y offset from node top-left (typically -25 for above node)
    "rotation": 0,                # Rotation angle in degrees
    "style": "font-family: TypeWriter;font-size: 10.0;font-weight: bold;fill: #000000;fill-opacity: 1.0;"
}
```

**Key Concepts:**
1. **Node coordinates**: Top-left corner of icon (x, y)
2. **Icon sizes**: PNG images = 78×78, SVG icons = 58×58
3. **Label position**: Offset from node top-left corner
4. **Auto-centering**: When `x` is `None`, GNS3 centers label above node

### Label Positioning Algorithm

**Auto-Centered Labels** (x is None):
```python
if label_x_offset is None:
    # Calculate text width estimate
    estimated_width = len(label_text) * font_size * 0.6

    # Center horizontally on node
    label_x = icon_size / 2  # Center of node
    label_y = -25            # Standard above-node position
    text_anchor = "middle"   # SVG text anchor
```

**Manual-Positioned Labels** (x/y are set):
```python
else:
    # Use GNS3 position directly - NO additional calculations
    label_x = label_x_offset
    label_y = label_y_offset

    # Determine text anchor based on position relative to node center
    if abs(label_x_offset - icon_size / 2) < 5:
        text_anchor = "middle"  # Centered
    elif label_x_offset > icon_size / 2:
        text_anchor = "end"     # Right of center (right-aligned)
    else:
        text_anchor = "start"   # Left of center (left-aligned)
```

### Common Label Rendering Mistakes

**❌ WRONG - v0.6.1 and earlier:**
```python
# DON'T add estimated dimensions to stored position!
estimated_width = len(label_text) * font_size * 0.6
estimated_height = font_size * 1.5
label_x = label_x_offset + estimated_width  # ❌ Adds offset incorrectly
label_y = label_y_offset + estimated_height / 2  # ❌ Vertical misalignment
```

**✅ CORRECT - v0.6.2:**
```python
# Use stored position directly
label_x = label_x_offset  # ✅ GNS3 position is already correct
label_y = label_y_offset  # ✅ No additional calculations needed
```

### SVG Rendering Details

**CSS Styles:**
```css
.node-label {
    /* NO fixed text-anchor here - applied per-label dynamically */
    dominant-baseline: text-before-edge;  /* Vertical alignment */
}
```

**SVG Text Element:**
```svg
<text class="node-label"
      x="{label_x}"
      y="{label_y}"
      text-anchor="{text_anchor}"  <!-- Dynamic: start/middle/end -->
      transform="rotate({rotation} {label_x} {label_y})"
      style="{label_style}">
    {label_text}
</text>
```

### Font Style Formats

GNS3 uses two font format representations:

**Qt Font String** (internal GNS3 settings):
```python
"TypeWriter,10,-1,5,75,0,0,0,0,0"
# Format: Family,Size,Weight,Style,Weight2,...
```

**SVG Style String** (stored in .gns3 project file):
```python
"font-family: TypeWriter;font-size: 10.0;font-weight: bold;fill: #000000;fill-opacity: 1.0;"
```

The MCP server preserves the SVG style string from GNS3 data, ensuring visual consistency.

### Label Rotation

Labels support rotation around their anchor point:

```python
# Rotation transform applied to text element
if label_rotation != 0:
    label_transform = f'transform="rotate({label_rotation} {label_x} {label_y})"'
```

**Rotation is around**: The label's actual position (label_x, label_y), NOT the node center.

### Comparison: Official GNS3 vs MCP Export

**Before v0.6.2 (Incorrect):**
- Labels offset too far to the right (added estimated_width)
- Labels positioned too low (added half estimated_height)
- All labels right-aligned (fixed text-anchor: end)

**After v0.6.2 (Correct):**
- ✅ Labels match GNS3 GUI positions exactly
- ✅ Auto-centered labels work correctly
- ✅ Dynamic text-anchor based on position
- ✅ Rotation works as expected

### Testing Label Rendering

**Export from GNS3 GUI:**
```
File → Export portable picture → Save as PNG
```

**Export from MCP Server:**
```python
export_topology_diagram(
    output_path="C:/path/to/output",
    format="both"  # Creates .svg and .png
)
```

**Visual Comparison Checklist:**
- [ ] Node labels in identical positions
- [ ] Label text not offset to the right
- [ ] Auto-centered labels (x=None) above nodes at y=-25
- [ ] Font matches: TypeWriter, 10pt, bold, black
- [ ] Rotated labels render correctly
- [ ] Left/center/right aligned labels match position

### Implementation Files

**Label rendering logic:**
- `mcp-server/server/main.py` lines 2338-2403
  - Label position calculation (2355-2375)
  - SVG text generation (2377-2403)
  - CSS styles (2117)

**Reference implementation:**
- `gns3-gui/gns3/items/node_item.py` lines 343-393
  - Official GNS3 label centering logic (_centerLabel)
  - Label update and positioning (_updateLabel)

## Git Workflow

### Commit Messages

Follow conventional commits format:
```
feat: add new console filtering tool
fix: resolve telnet timeout issue
docs: update testing guide
test: add console reconnection tests
```

### Files to Commit

**Always commit:**
- Source code (server/*.py)
- manifest.json
- requirements.txt
- Documentation (*.md)
- Tests (tests/*.py)

**Never commit:**
- .env (contains passwords)
- lib/ folder (generated)
- *.mcpb files (generated)
- __pycache__/
- *.pyc

### Before Committing

1. Run tests
2. Update version if needed
3. Update documentation if needed
4. Stage only relevant files
5. Write descriptive commit message

## Testing Checklist

Before considering a change complete:

- [ ] Code changes tested locally
- [ ] Unit tests pass (`python tests/test_mcp_console.py`)
- [ ] Version updated in manifest.json
- [ ] Extension repackaged: `npx @anthropic-ai/mcpb pack`
- [ ] Version in build output matches manifest
- [ ] Extension reinstalled in Claude Desktop
- [ ] Integration test passes (manual test in Claude Desktop)
- [ ] No errors in Claude Desktop logs
- [ ] Documentation updated if needed
- [ ] Changes committed to git

## Performance Considerations

### Console Buffer Management

- Default: 10MB per session
- Trim at 5MB when exceeded
- Adjust `MAX_BUFFER_SIZE` in console_manager.py if needed

### Session Timeouts

- Default: 30 minutes (1800 seconds)
- Cleanup task runs periodically
- Adjust `SESSION_TIMEOUT` if needed

### Concurrent Connections

- Multiple console sessions supported
- Each session has independent buffer
- Background reader tasks run concurrently
- Test with multiple devices if adding concurrency features

## Security Notes

- Never log passwords or tokens
- GNS3 password stored in .env (gitignored)
- JWT tokens not logged
- Console output may contain sensitive info (sanitize if needed)
- Use `sensitive: true` for password fields in manifest

## API Reference

### GNS3 v3 API Endpoints

See `data/SESSION.txt` for complete traffic analysis.

Key endpoints:
- POST `/v3/access/users/authenticate` - Get JWT token
- GET `/v3/projects` - List projects
- GET `/v3/projects/{id}/nodes` - List nodes
- POST `/v3/projects/{id}/nodes/{node_id}/start` - Start node
- POST `/v3/projects/{id}/nodes/{node_id}/stop` - Stop node

### Console Ports

- Extracted from node data: `node["console"]`
- Console type: `node["console_type"]` (telnet, vnc, spice+agent, none)
- Only telnet consoles supported currently

## Resources

- MCP Docs: https://modelcontextprotocol.io/
- GNS3 Docs: https://docs.gns3.com/
- FastMCP: https://github.com/anthropics/fastmcp
- telnetlib3: https://telnetlib3.readthedocs.io/

## Quick Reference

```bash
# Common commands
cd "C:\HOME\1. Scripts\008. GNS3 MCP"

# List nodes
python tests/list_nodes_helper.py

# Test console
python tests/test_mcp_console.py --port 5014

# Package extension
cd mcp-server && npx @anthropic-ai/mcpb pack

# View logs
notepad "C:\Users\mail4\AppData\Roaming\Claude\logs\mcp-server-GNS3 Lab Controller.log"

# Git status
git status

# Commit
git add . && git commit -m "feat: description"
```
- use https://apiv3.gns3.net/ as a source of documentation for GNS3 v3 api
- rebuild desktop extensions after finishing modifications of the tools and skills
- remember to restart chat when need to update mcp server
- keep version history in CLAUDE.md
- Remember that you need to update the version and set the 'latest' tag to the container