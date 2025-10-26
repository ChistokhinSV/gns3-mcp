# Changelog

All notable changes to the GNS3 MCP Server project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.23.0] - Project Notes/Memory (FEATURE)

### Added
- **NEW**: Project README/notes functionality via GNS3 native README.txt storage
  - MCP Resource: `gns3://projects/{id}/readme` - browsable, read-only access to project notes
  - Tool: `get_project_readme()` - retrieve project documentation in markdown format
  - Tool: `update_project_readme()` - save project documentation (IP schemes, credentials, architecture)
  - **Storage**: Uses native GNS3 `/v3/projects/{id}/files/README.txt` API endpoints
  - **Format**: Markdown (human-readable, supports formatting)
  - **Scope**: Per-project (each lab has separate notes)
  - **Access**: Zero context cost - loaded only on explicit tool call

### Use Cases
- **IP Addressing**: Store IP schemes, VLANs, subnets per project
- **Credentials**: Document usernames, password vault keys, SSH access
- **Architecture**: Text-based diagrams, node relationships, HA configs
- **Configuration**: Templates, snippets, device-specific settings
- **Troubleshooting**: Runbooks, common issues, debugging notes

### Changed
- **UPDATED**: manifest.json version 0.22.3→0.23.0
  - Updated description: "24 tools + 18 resources" (was 22 tools + 17 resources)
  - Added 2 tool definitions for get_project_readme and update_project_readme

### Technical Details
- **NO BREAKING CHANGES**: Additive feature, all existing tools unchanged
- **FILES CHANGED**:
  - `mcp-server/server/gns3_client.py`: Added get_project_readme() and update_project_readme() methods (+54 LOC)
  - `mcp-server/server/resources/project_resources.py`: Added get_project_readme_impl() handler (+25 LOC)
  - `mcp-server/server/resources/resource_manager.py`: Added readme URI pattern and handler (+15 LOC)
  - `mcp-server/server/main.py`: Added resource and 2 tools (+102 LOC)
  - `mcp-server/manifest.json`: Version 0.22.3→0.23.0, added 2 tools, updated descriptions
- **NEW RESOURCES**: 1 (gns3://projects/{id}/readme)
- **NEW TOOLS**: 2 (get_project_readme, update_project_readme)
- **TOTAL NEW CODE**: ~196 LOC
- **RATIONALE**: Enables AI agent to maintain project-specific context without consuming main conversation
  context. Agent can store discovered information (IPs, credentials, architecture notes) persistently per
  project. Uses native GNS3 README.txt storage for portability and version control compatibility.

## [0.22.3] - Documentation Cleanup (REFACTOR)

### Removed
- **REMOVED**: Label Rendering Implementation (v0.6.2) section from CLAUDE.md
  - Deleted 175 lines of detailed SVG rendering documentation
  - CLAUDE.md reduced from 660 to 485 lines (26.5% reduction)
  - Technical details included: coordinate system, positioning algorithm, rendering mistakes, CSS styles, font formats, rotation, testing checklist
  - Information was implementation-specific for v0.6.2 and not essential for current development

### Changed
- **UPDATED**: manifest.json version 0.22.2→0.22.3
  - Updated long_description to mention SVG rendering details removal

### Technical Details
- **NO BREAKING CHANGES**: Documentation-only cleanup, no code changes
- **FILES CHANGED**:
  - `CLAUDE.md`: Removed Label Rendering Implementation section (175 lines)
  - `mcp-server/manifest.json`: Version 0.22.2→0.22.3, updated description
- **RATIONALE**: Label rendering implementation details were highly specific to v0.6.2 bugfix and contained
  extensive technical documentation about SVG coordinate systems, positioning algorithms, and rendering
  mistakes. This level of detail is better suited for code comments or a separate ARCHITECTURE.md file.
  Removing it keeps CLAUDE.md focused on current development workflows.

## [0.22.2] - Documentation Cleanup (REFACTOR)

### Removed
- **REMOVED**: Outdated v0.3.0 Architecture section from CLAUDE.md
  - Deleted 104 lines of old architecture documentation (Pydantic models, two-phase validation, TTL caching)
  - CLAUDE.md reduced from 764 to 660 lines (13.6% reduction)
  - Information was specific to v0.3.0 and no longer relevant to current architecture

### Changed
- **UPDATED**: manifest.json version 0.22.1→0.22.2
  - Updated long_description to mention removal of outdated architecture docs

### Technical Details
- **NO BREAKING CHANGES**: Documentation-only cleanup, no code changes
- **FILES CHANGED**:
  - `CLAUDE.md`: Removed v0.3.0 Architecture section (104 lines)
  - `mcp-server/manifest.json`: Version 0.22.1→0.22.2, updated description
- **RATIONALE**: v0.3.0 Architecture section described implementation details from early 2024 that are
  no longer the primary focus. Removing outdated technical details keeps CLAUDE.md focused on current
  development workflows and reduces maintenance burden.

## [0.22.1] - Documentation Refactoring (REFACTOR)

### Changed
- **REFACTORED**: Extracted complete version history from CLAUDE.md to CHANGELOG.md
  - CLAUDE.md reduced from 1779 to 764 lines (57.1% reduction, 1015 lines saved)
  - Created CHANGELOG.md with full version history (593 lines)
  - CLAUDE.md now contains only current version (v0.22.0) with summary
  - All historical versions documented in standard CHANGELOG.md format
- **UPDATED**: manifest.json version 0.22.0→0.22.1
  - Updated long_description to reference CHANGELOG.md for complete version history
- **IMPROVED**: Better documentation organization
  - Current version and key features in CLAUDE.md for quick reference
  - Complete historical record in CHANGELOG.md for detailed research
  - Follows industry-standard Keep a Changelog format

### Technical Details
- **NO BREAKING CHANGES**: Documentation-only refactor, no code changes
- **FILES CHANGED**:
  - `CLAUDE.md`: Replaced 1038 lines of version history with concise current version summary
  - `CHANGELOG.md`: NEW - Complete version history in standard format (593 lines)
  - `mcp-server/manifest.json`: Version 0.22.0→0.22.1, updated description
- **RATIONALE**: CLAUDE.md was too large (1779 lines) with 58% being version history. Extracting to
  CHANGELOG.md improves maintainability, follows industry standards, and makes current version info
  more accessible. Total documentation size reduced from 1779 to 1357 lines (764+593).

## [0.22.0] - Batch Console Operations (FEATURE)

### Added
- **NEW**: `console_batch` tool for executing multiple console operations with two-phase validation
  - Aggregates any console tool (send, send_and_wait, read, keystroke) with full parameter support
  - **Two-phase execution**: Validate ALL → Execute ALL (prevents partial failures)
  - **Sequential execution**: Operations run in order, results collected with success/failure status
  - **Full parameter support**: Each operation supports all parameters from underlying tool
- **FUNCTIONALITY**: Batch execution with structured results
  - Supports 4 operation types: "send", "send_and_wait", "read", "keystroke"
  - Each operation specifies: `{"type": "...", "node_name": "...", ...tool_params}`
  - Returns JSON: `{completed: [indices], failed: [indices], results: [...], total_operations, execution_time}`
  - Failed operations don't stop batch - all results returned with error details
- **USE CASES**:
  - **Multiple commands on one node**: Diagnostic sequence on single router
  - **Same command on multiple nodes**: "show ip int brief" on R1, R2, R3 for comparison
  - **Mixed operations**: Wake console + read prompt + send command + validate output
  - **Interactive workflows**: Multi-step sequences with validation between steps
- **OPERATION TYPES** with full parameter support:
  - `send`: `{type, node_name, data, raw}`
  - `send_and_wait`: `{type, node_name, command, wait_pattern, timeout, raw}`
  - `read`: `{type, node_name, mode, pages, pattern, case_insensitive, invert, before, after, context}`
  - `keystroke`: `{type, node_name, key}`
- **ADVANTAGES**:
  - **Validation**: All operations validated before execution (no partial failures)
  - **Structured Results**: Clear success/failure status per operation with error details
  - **Timing**: Execution time tracking for performance analysis
  - **Flexibility**: Mix different operation types in one batch
  - **Error Isolation**: Failed operations don't stop batch, all results returned

### Changed
- `mcp-server/server/tools/console_tools.py`: Added console_batch_impl() (+239 LOC)
  - Two-phase validation (check types, required params)
  - Sequential execution with error handling
  - Structured result collection
- `mcp-server/server/main.py`: Added console_batch tool registration (+104 LOC), imported console_batch_impl
- `mcp-server/manifest.json`: Added tool definition, version 0.21.1→0.22.0, updated descriptions (22 tools)
- `skill/SKILL.md`: Added "Batch Console Operations (v0.22.0)" section with comprehensive examples (+134 LOC)

### Technical Details
- **TOOL COUNT**: 21 → 22 tools
- **NO BREAKING CHANGES**: Additive feature, all existing tools unchanged
- **IMPLEMENTATION PATTERN**: Follows set_connection() batch pattern (two-phase validation, atomic execution)
- **RATIONALE**: User requested batch console tool that "automatically supports all parameters of the tools".
  Enables efficient multi-node analysis (run same command on multiple routers), multi-step workflows (diagnostic
  sequences), and mixed operations (interactive workflows). Two-phase validation prevents partial failures.
  Each operation type supports full parameter set from underlying tool for maximum flexibility.

## [0.21.1] - Console Send-and-Wait Tool Restoration (FEATURE)

### Added
- **RESTORED**: `console_send_and_wait` tool for interactive console automation
  - Removed in v0.15.0 as "low usage", now restored by user request
  - **Naming fix**: Uses correct v0.15.0+ naming convention (`console_` prefix, not `send_and_wait_console`)
  - **Why it was removed**: Deemed replaceable with two-step `console_send()` + `console_read()` workflow
  - **Why restored**: Essential for interactive workflows requiring pattern matching and synchronization
- **FUNCTIONALITY**: Send command + wait for prompt pattern + return output
  - Pattern matching with regex support (e.g., `wait_pattern="Router[>#]"`)
  - Auto-polling every 0.5 seconds until pattern found or timeout
  - Returns JSON: `{output, pattern_found, timeout_occurred, wait_time}`
  - Timeout support (default: 30s, configurable)
  - No-pattern mode: waits 2 seconds and returns output
- **USE CASES**:
  - Interactive logins (wait for "Login:" prompt)
  - Command completion verification (wait for prompt return)
  - Configuration mode transitions (wait for "(config)#")
  - Boot sequences with specific prompts
- **BEST PRACTICE WORKFLOW** (documented in tool + SKILL.md):
  1. Check prompt first: `console_send("\n")` + `console_read()` → see "Router#"
  2. Use that pattern: `console_send_and_wait(..., wait_pattern="Router#")`
  3. Ensures correct pattern and prevents missed output
- **ERROR HANDLING**: Standardized error responses
  - Invalid regex: `error_code="INVALID_PARAMETER"` with syntax help
  - Console disconnected: `error_code="CONSOLE_DISCONNECTED"` with recovery steps
  - Timeout without pattern: `timeout_occurred=true`, returns accumulated output

### Changed
- `mcp-server/server/main.py`: Added console_send_and_wait tool registration (+66 LOC)
- `mcp-server/server/tools/console_tools.py`: Implementation already existed from v0.14.0, uses standardized error handling
- `mcp-server/manifest.json`: Added tool definition, version 0.21.0→0.21.1, updated descriptions (21 tools)
- `skill/SKILL.md`: Added "Interactive Console Automation (v0.21.1)" section with workflow guide (+71 LOC)

### Technical Details
- **TOOL COUNT**: 20 → 21 tools
- **NO BREAKING CHANGES**: Additive feature, all existing tools unchanged
- **RATIONALE**: User-requested feature for interactive console automation. Two-step workflow (send+read) doesn't
  support pattern matching or timeout, requiring manual sleep() calls and polling logic. Single tool simplifies
  interactive workflows while maintaining clean API with proper naming convention.

## [0.21.0] - HTTP/SSE Transport Modes (FEATURE)

### Added
- **NEW**: HTTP and SSE transport modes for network deployment
  - **stdio mode** (default): Process-based communication for Claude Desktop/Code
  - **HTTP mode** (recommended): Streamable HTTP transport for network access, remote deployment
  - **SSE mode** (deprecated): Server-Sent Events for backward compatibility only
- **NEW**: Command-line arguments for transport configuration
  - `--transport {stdio|http|sse}` - Select transport mode (default: stdio)
  - `--http-host` - HTTP server bind address (default: 127.0.0.1)
  - `--http-port` - HTTP server port (default: 8000)
- **NEW**: Server endpoint information printed on HTTP/SSE startup
  - HTTP: `http://{host}:{port}/mcp/`
  - SSE: `http://{host}:{port}/sse` (with deprecation warning)
- **ENHANCED**: README.md documentation with comprehensive transport mode guide
  - Transport comparison table (stdio vs HTTP vs SSE)
  - When to use each transport mode
  - Starting server examples for all modes
  - HTTP endpoint configuration examples
  - Security considerations for network-exposed deployments

### Changed
- `mcp-server/server/main.py`: Added transport mode arguments and conditional execution (lines 1614-1651, +38 LOC)
- `README.md`: Added "Transport Modes" section with complete documentation (lines 147-239, +93 LOC)
- `mcp-server/manifest.json`: Version 0.20.0→0.21.0, updated descriptions

### Technical Details
- **NO BREAKING CHANGES**: Default stdio mode unchanged, HTTP/SSE modes are opt-in
- **USE CASES**:
  - stdio: Claude Desktop, Claude Code, local development (existing workflows unchanged)
  - HTTP: Multiple remote clients, cloud deployment, web service integration, container orchestration
  - SSE: Legacy client compatibility (migrate to HTTP when possible)
- **TESTING**: ✅ HTTP mode tested successfully - server starts on http://127.0.0.1:8000, StreamableHTTP session manager initializes correctly
- **RATIONALE**: Enables network deployment scenarios (remote access, multiple clients, cloud hosting)
  while maintaining backward compatibility with existing stdio-based installations. HTTP transport
  provides modern bidirectional communication for production use.

## [0.20.0] - Polish & Quality (Phase 1 - Foundation) (REFACTOR)

### Added
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

### Changed
- `mcp-server/server/main.py`: VERSION reading from manifest (+12 LOC)
- `mcp-server/server/models.py`: ErrorCode enum, enhanced ErrorResponse (+48 LOC)
- `mcp-server/server/error_utils.py`: NEW - 15 error helper functions (400 LOC)
- `tests/unit/test_version.py`: NEW - Version synchronization tests (85 LOC)
- `.git/hooks/pre-commit`: Version consistency validation (+11 LOC)
- `mcp-server/manifest.json`: Version 0.19.0→0.20.0, updated descriptions

### Technical Details
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

## [0.19.0] - UX & Advanced Features (FEATURE)

### Added
- **NEW**: MCP tool annotations for all 20 tools (visibility of tool behavior in IDE/MCP clients)
  - **destructive** (3 tools): delete_node, restore_snapshot, delete_drawing
  - **idempotent** (9 tools): open_project, create_project, close_project, set_node, console_disconnect, ssh_configure, ssh_disconnect, update_drawing, export_topology_diagram
  - **read_only** (1 tool): console_read
  - **creates_resource** (5 tools): create_project, create_node, create_snapshot, export_topology_diagram, create_drawing
  - **modifies_topology** (3 tools): set_connection, create_node, delete_node
- **DEFERRED**: Autocomplete support via MCP completions for 7 parameter types (implementation prepared but disabled pending FastMCP API clarification)
- **NEW**: 3 drawing tools for visual annotations (hybrid architecture)
  - `create_drawing`: Create rectangle, ellipse, line, or text annotations
  - `update_drawing`: Modify position (x/y/z), rotation, svg content, locked state
  - `delete_drawing`: Remove drawing object by ID
  - **Hybrid pattern**: Resources (gns3://projects/{id}/drawings/) for READ, Tools for WRITE

### Changed
- `mcp-server/server/main.py`: Added annotations to 17 tools, 8 completion handlers, 3 drawing tools (+300 LOC)
- `mcp-server/server/tools/drawing_tools.py`: Added update_drawing_impl() (+65 LOC)
- `mcp-server/manifest.json`: Version 0.18.0→0.19.0, added 3 tools, updated descriptions

### Technical Details
- **ARCHITECTURE**: 20 tools + 17 resources + 4 prompts + (8 completions deferred) = Enhanced UX
- **NO BREAKING CHANGES**: All existing tools, resources, prompts unchanged
- **KNOWN ISSUES**: Completions disabled - FastMCP API for completions is different from MCP spec
- **Rationale**: Tool annotations enable IDE warnings for destructive operations, improving safety. Drawing tools restore functionality removed in v0.15.0 with improved hybrid architecture.

## [0.18.0] - Core Lab Automation (FEATURE)

### Added
- **NEW**: 5 new tools for complete lab lifecycle management
  - `create_project`: Create new GNS3 projects and auto-open
  - `close_project`: Close currently opened project
  - `create_node`: Create nodes from templates at specified coordinates (RESTORED from v0.15.0)
  - `create_snapshot`: Save project state with validation
  - `restore_snapshot`: Restore to previous snapshot state
- **NEW**: 2 new MCP resources for snapshot browsing
  - `gns3://projects/{id}/snapshots/` - List all snapshots in project
  - `gns3://projects/{id}/snapshots/{id}` - Snapshot details
- **NEW**: lab_setup prompt - Automated topology creation with 6 topology types
  - `star`, `mesh`, `linear`, `ring`, `ospf`, `bgp`

### Changed
- Multiple files updated for snapshot management and lab setup
- Version 0.17.0→0.18.0

### Technical Details
- **ARCHITECTURE**: 16 tools + 17 resources + 4 prompts = Complete lab automation
- **WORKFLOW ENABLEMENT**: Complete lab lifecycle now automated
- **NO BREAKING CHANGES**: All existing tools, resources, and prompts unchanged

## [0.17.0] - MCP Prompts (FEATURE)

### Added
- **NEW**: 3 guided workflow prompts for common GNS3 operations
  - `ssh_setup`: Device-specific SSH configuration workflow (6 device types)
  - `topology_discovery`: Network topology discovery and visualization
  - `troubleshooting`: OSI model-based systematic troubleshooting

### Changed
- Multiple prompt files added
- Version 0.15.0→0.17.0

### Technical Details
- **ARCHITECTURE**: Complete MCP server = 11 tools + 15 resources + 3 prompts
- **DEVICE COVERAGE**: 6 device types with specific configuration commands
- **NO BREAKING CHANGES**: All tools and resources unchanged, prompts additive

## [0.15.0] - Complete Tool Consolidation (BREAKING CHANGES)

### Changed
- **RENAMED**: All tools now follow `{category}_{action}` naming pattern
  - `send_console` → `console_send`
  - `read_console` → `console_read`
  - `disconnect_console` → `console_disconnect`
  - `send_keystroke` → `console_keystroke`
  - `configure_ssh` → `ssh_configure`
- **MERGED**: SSH command tools with auto-detection
  - `ssh_send_command` + `ssh_send_config_set` → `ssh_command()`

### Removed
- **REMOVED**: 7 deprecated/low-usage tools
  - `send_and_wait_console`, `create_node`, `create_drawing`, `delete_drawing`, `ssh_cleanup_sessions`, `ssh_get_job_status`

### Added
- **NEW**: `ssh_disconnect` tool for explicit SSH session cleanup

### Technical Details
- **FINAL ARCHITECTURE**: 11 core tools + 15 browsable resources
- **Tool count reduction**: 17 → 11 (-35% reduction from v0.14.0)
- **NO BREAKING CHANGES for resources**: All 15 MCP resources unchanged

## [0.14.0] - Tool Consolidation (BREAKING CHANGES - Phase 1)

### Removed
- **REMOVED**: 11 deprecated query tools (replaced by MCP resources in v0.13.0)
  - All list/get tools replaced by MCP resources

### Changed
- Version 0.13.0→0.14.0

### Technical Details
- **FINAL ARCHITECTURE**: 17 core tools + 15 browsable resources
- **Tool count reduction**: 30 → 17 (-43% reduction in cognitive load)
- **NO BREAKING CHANGES for v0.13.0 users**: Resources already available

## [0.13.0] - MCP Resources (Breaking Changes - Phase 1)

### Added
- **NEW**: 15 MCP resources for browsable state via `gns3://` URI scheme
  - Project resources, Session resources, SSH proxy resources
- **REFACTORED**: Resource architecture with 3 new modules
  - `resources/resource_manager.py`, `resources/project_resources.py`, `resources/session_resources.py`

### Deprecated
- **DEPRECATED**: 11 query tools (still functional, will be removed in v0.14.0)

### Changed
- Version 0.12.4→0.13.0

### Technical Details
- **NO BREAKING CHANGES**: All existing tools still functional (deprecated but working)
- **Rationale**: MCP resources provide better IDE integration and clearer separation

## [0.12.4] - Documentation and Error Handling (Patch - UX)

### Added
- **ENHANCED**: Added comprehensive SSH vs Console tool selection guidelines
- **IMPROVED**: configure_ssh error response handling

### Changed
- Version 0.12.3→0.12.4

### Technical Details
- **NO BREAKING CHANGES**: All functionality unchanged, documentation improvements only

## [0.12.3] - send_and_wait_console Output Fix (Bugfix - Critical)

### Fixed
- **FIXED**: `send_and_wait_console()` now correctly accumulates all output during polling
  - Previous bug: Output was lost when pattern matched quickly

### Changed
- Version 0.12.2→0.12.3

### Technical Details
- **NO BREAKING CHANGES**: API unchanged, bug fix only

## [0.12.2] - Lightweight list_nodes Output (Bugfix - Performance)

### Fixed
- **FIXED**: `list_nodes()` now returns lightweight NodeSummary instead of full NodeInfo
  - Reduces output size by ~80-90%

### Added
- **NEW**: Created NodeSummary model for minimal node information

### Changed
- Version 0.12.1→0.12.2

### Technical Details
- **NO BREAKING CHANGES**: API remains the same, just returns less data per node

## [0.12.1] - Grep Filtering for Buffers (Feature - Enhancement)

### Added
- **NEW**: Grep-style pattern filtering for both SSH and console buffer output
  - Optional `pattern` parameter with full regex support
  - Grep feature set: case insensitive (-i), invert match (-v), context lines (-B/-A/-C)
- **SSH Proxy v0.1.4 Changes**: Added grep filtering to SSH proxy

### Changed
- Version 0.12.0→0.12.1

### Technical Details
- **NO BREAKING CHANGES**: All new parameters are optional
- **Deployment**: SSH proxy v0.1.4, MCP server v0.12.1

## SSH Proxy [0.1.6] - Session Management & Stale Session Recovery (FEATURE)

### Added
- **NEW**: 30-minute session TTL with automatic expiry detection
- **NEW**: Session health checks detect stale/closed connections
- **NEW**: Auto-cleanup on "Socket is closed" errors
- **NEW**: Structured error responses with error_code and suggested_action fields
- **NEW**: Force recreation parameter for ssh_configure

### Changed
- Version 0.1.5→0.1.6

### Technical Details
- **Deployment**: Built and deployed as `chistokhinsv/gns3-ssh-proxy:v0.1.6` and `latest` tags

## SSH Proxy [0.1.5] - API Monitoring Endpoints (PATCH)

### Added
- **NEW**: Added `/version` endpoint for version tracking
- **ENHANCED**: Improved `/health` endpoint documentation

### Changed
- Version 0.1.4→0.1.5

### Technical Details
- **Deployment**: Built and deployed as `chistokhinsv/gns3-ssh-proxy:v0.1.5` and `latest` tags

## [0.12.0] - SSH Proxy Service (Feature - Phase 1)

### Added
- **NEW**: SSH proxy service (FastAPI container, Python 3.13-slim)
  - Separate Docker container with network mode=host
  - Port 8022, Docker Hub: `chistokhinsv/gns3-ssh-proxy:v0.1.3`
- **NEW**: Dual storage architecture (continuous buffer + command history)
- **NEW**: Adaptive async command execution
- **NEW**: 9 MCP tools for SSH automation
- **NEW**: SSH connection error detection
- **NEW**: Netmiko integration (200+ device types)

### Changed
- Version to v0.12.0

### Technical Details
- **NO BREAKING CHANGES**: All existing tools unchanged, SSH tools additive

## SSH Proxy [0.1.3] - Version Tracking (FEATURE)

### Added
- **NEW**: Added version field to configure_ssh response

### Changed
- Version 0.1.2→0.1.3

## SSH Proxy [0.1.2] - Netmiko Fixes (PATCH)

### Fixed
- **FIXED**: Netmiko prompt detection timeout on Alpine Linux
- **FIXED**: Exception handlers masking errors

### Changed
- Version 0.1.1→0.1.2

## [0.11.1] - Console Output Pagination (Patch)

### Added
- **NEW**: Added `num_pages` mode to `read_console()` tool
- **ENHANCED**: Parameter validation and documentation

### Changed
- Version to v0.11.1

### Technical Details
- **NO BREAKING CHANGES**: All existing modes work unchanged

## [0.11.0] - Code Organization Refactoring (Refactor)

### Added
- **NEW**: Console manager unit tests (38 tests, 76% coverage)
- **REFACTORED**: Extracted 19 tool implementations to 6 category modules

### Changed
- **IMPROVED**: Reduced main.py from 1,836 to 914 LOC (50% reduction)
- Version to v0.11.0

### Technical Details
- **NO BREAKING CHANGES**: All tool interfaces remain unchanged

## [0.10.0] - Testing Infrastructure (Feature)

### Added
- **NEW**: Comprehensive unit testing infrastructure with pytest
  - 134 unit tests covering critical modules
  - pytest 8.4.2 with plugins
- **NEW**: Extracted export functionality to separate module

### Changed
- Version to v0.10.0

### Technical Details
- **Test Coverage**: models.py (100%), link_validator.py (96%), gns3_client.py (75%)

## [0.9.0] - Major Refactoring (Breaking Changes)

### Removed
- **REMOVED**: Caching infrastructure completely
- **REMOVED**: `detect_console_state()` tool and DEVICE_PATTERNS

### Changed
- **BREAKING**: `read_console()` API redesigned
  - Previous: `read_console(node, diff: bool, last_page: bool)`
  - Now: `read_console(node, mode: str = "diff")`
- **ENHANCED**: ErrorResponse model now includes `suggested_action` field

### Technical Details
- **Rationale**: Caching added unnecessary complexity for local labs

## [0.8.1] - Documentation Enhancement (Patch)

### Added
- **ENHANCED**: Added best practice guidance for `send_and_wait_console()`
- **SKILL.md**: New section "Using send_and_wait_console for Automation"

### Changed
- Version to v0.8.1

## [0.8.0] - Tool Redesign (Breaking Changes)

### Changed
- **BREAKING**: `read_console()` now defaults to `diff=True`
- **NEW**: `read_console()` added `last_page=True` parameter
- **BREAKING**: Removed individual drawing tools
- **NEW**: Unified `create_drawing(drawing_type, ...)` tool

### Technical Details
- **Rationale**: Diff mode is most common use case

## [0.7.0] - Adapter Name Support (Feature)

### Added
- **NEW**: `set_connection()` now accepts adapter names in addition to numeric indexes
- **Backward compatible**: Numeric adapter indexes still work

### Changed
- Version to v0.7.0

## [0.6.5] - Empty Response Handling (Bugfix)

### Fixed
- **Fixed node actions**: Handle empty API responses (HTTP 204)

## [0.6.4] - Z-order Rendering Fix (Bugfix)

### Fixed
- **Fixed z-order**: Links render below nodes, correct layering

## [0.6.3] - Font Fallback Chain (Bugfix)

### Fixed
- **Fixed font rendering**: Added CSS-style font fallback chains

## [0.6.2] - Label Rendering Fix (Bugfix)

### Fixed
- **Fixed label positioning**: Matches official GNS3 GUI rendering
- **Auto-centering**: Labels with x=None properly center above nodes

## [0.6.1] - Newline Normalization & Special Keystrokes

### Fixed
- **FIXED**: All newlines automatically converted to \r\n

### Added
- **NEW**: `send_keystroke()` - Send special keys for TUI navigation

## [0.6.0] - Interactive Console Tools

### Added
- **NEW**: `send_and_wait_console()` - Send command and wait for pattern
- **NEW**: `detect_console_state()` - Auto-detect device type
- **ENHANCED**: Console tool docstrings with timing guidance

## [0.5.1] - Label Alignment

### Fixed
- Fixed node label alignment - right-aligned and vertically centered

## [0.5.0] - Port Status Indicators

### Added
- Topology export shows port status indicators (green/red)

## [0.4.2] - Topology Export

### Added
- **NEW**: `export_topology_diagram()` - Export topology as SVG/PNG

## [0.4.0] - Node Creation & Drawing Objects

### Added
- **NEW**: Multiple tools for node and drawing management
  - `delete_node`, `list_templates`, `create_node`
  - `list_drawings`, `create_rectangle`, `create_text`, `create_ellipse`

## [0.3.0] - Major Refactoring (Breaking Changes)

### Added
- **Type-safe operations**: Pydantic v2 models
- **Two-phase validation**: Prevents partial topology changes
- **Performance caching**: 10× faster with TTL-based cache
- **New tool**: `get_console_status()`

### Changed
- **Multi-adapter support**: `set_connection()` now requires `adapter_a`/`adapter_b` parameters
- **JSON outputs**: All tools return structured JSON

## [0.2.1] - Link Discovery

### Added
- Added `get_links()` tool for topology discovery
- Enhanced `set_connection()` with workflow guidance

## [0.2.0] - Auto-Connect & Unified Control

### Changed
- Console tools now use `node_name` instead of `session_id` (auto-connect)
- `start_node` + `stop_node` → unified `set_node` tool
- Added `set_connection` tool for link management
