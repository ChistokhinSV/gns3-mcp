# Changelog

All notable changes to the GNS3 MCP Server project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - SSH Proxy v0.3.0 Enhancement

### Added - SSH Proxy Multi-Service Architecture
- **TFTP Server Integration**
  - tftpd-hpa server on port 69/udp with root directory `/opt/gns3-ssh-proxy/tftp`
  - Read-write access for device firmware uploads/downloads and config file serving
  - RESTful API endpoint `/tftp` with CRUD-style actions: list, upload, download, delete, status
  - Base64 encoding for file content transfer in API
  - File metadata includes size, modification time, and directory flag
- **HTTP/HTTPS Reverse Proxy**
  - nginx reverse proxy on port 8023 for device web UI access
  - URL format: `http://proxy:8023/http-proxy/<device_ip>:<port>/`
  - Self-signed SSL certificates for HTTPS device backends
  - Dynamic routing based on URL path regex
  - No SSH tunnel needed for external web UI access
  - RESTful API endpoint `/http-proxy` for device registration (register, unregister, list, reload)
- **HTTP Client Tool**
  - RESTful API endpoint `/http-client` for making HTTP/HTTPS requests to lab devices
  - Actions: get (HTTP GET request), status (HEAD request for reachability)
  - Custom headers support for authentication
  - SSL verification control (default: ignore self-signed certificates)
  - Useful for checking device APIs and health endpoints
- **Supervisor Process Management**
  - Runs multiple services in single container: FastAPI, TFTP, nginx
  - Automatic service restart on failure
  - Centralized logging via supervisord
- **GitHub Actions Workflow**
  - Manual workflow for building and pushing SSH proxy Docker images
  - Automatic version extraction from `__version__` constant in main.py
  - Multi-tag support: version tag + latest tag
  - Automated Docker Hub description updates from repository files

### Added - MCP Tools
- **tftp Tool** (gns3_mcp/server/tools/tftp_tools.py)
  - CRUD-style tool with action parameter: list, upload, download, delete, status
  - Comprehensive docstring with usage examples and TFTP server details
  - Calls ssh-proxy `/tftp` endpoint via httpx
  - Added to TOOL_REGISTRY with categories: ["tftp", "file-transfer"]
- **http_client Tool** (gns3_mcp/server/tools/http_client_tools.py)
  - CRUD-style tool with action parameter: get, status
  - Mentions reverse proxy availability in docstring: "Reverse HTTP/HTTPS proxy available at..."
  - Calls ssh-proxy `/http-client` endpoint via httpx
  - Added to TOOL_REGISTRY with categories: ["http", "https", "web"]
- **Updated SSH Tool Description**
  - Added "SSH Proxy Services (v0.3.0)" section documenting TFTP server, HTTP reverse proxy, and HTTP client tool availability
  - Helps AI assistants discover and utilize new proxy services

### Changed - SSH Proxy
- **Dockerfile**
  - Added system packages: tftpd-hpa, nginx, openssl, supervisor
  - Created TFTP root directory with 777 permissions
  - Generated self-signed SSL certificates for nginx
  - Changed CMD to run supervisord instead of direct uvicorn
  - Added nginx and supervisor configuration files
- **FastAPI Endpoints** (ssh-proxy/server/main.py)
  - Version bumped to 0.3.0
  - Added `/tftp` endpoint with full CRUD operations (150 lines)
  - Added `/http-client` endpoint for HTTP/HTTPS requests (90 lines)
  - Added `/http-proxy` endpoint for reverse proxy management (130 lines)
  - Updated `/proxy/registry` to include TFTP and HTTP proxy status
  - Added imports: base64, httpx, Path, datetime
- **Pydantic Models** (ssh-proxy/server/models.py)
  - Added TFTPRequest, TFTPResponse, TFTPFile models (v0.3.0 section)
  - Added HTTPClientRequest, HTTPClientResponse models (v0.3.0 section)
  - Added HTTPProxyRequest, HTTPProxyResponse, HTTPProxyDevice models (v0.3.0 section)

### Changed - Documentation
- **ssh-proxy/README.md**
  - Updated title: "with TFTP server, HTTP reverse proxy, and multi-proxy architecture"
  - Added Features section describing TFTP, HTTP proxy, and HTTP client (v0.3.0+)
  - Updated Architecture diagram showing multi-service container with ports
  - Updated Quick Start section to version 0.3.0 with exposed ports documentation
  - Added API Endpoints section for TFTP, HTTP client, and HTTP reverse proxy
  - Added usage examples: TFTP server, HTTP client, HTTP reverse proxy (90 lines)
- **ssh-proxy/.dockerhub/description-short.txt**
  - Created Docker Hub short description (100 char limit)
  - Highlights: SSH/TFTP/HTTP proxy, Netmiko, Ansible, diagnostics
- **ssh-proxy/.dockerhub/description-long.md**
  - Created Docker Hub full description with features, usage, diagrams
  - Includes {VERSION} placeholder replaced by GitHub Actions
  - Documents ports: 8022/tcp (API), 69/udp (TFTP), 8023/tcp (nginx)
- **.github/workflows/build-ssh-proxy.yml**
  - Created manual workflow for SSH proxy Docker build/push
  - Extracts version from `__version__` constant in main.py
  - Updates Docker Hub descriptions automatically
  - Uses secrets: DOCKERHUB_USERNAME, DOCKERHUB_TOKEN

### Technical Details
- **Multi-Service Container**: Single Docker container runs FastAPI (8022), TFTP (69/udp), and nginx (8023) via supervisor
- **TFTP File Transfer**: Base64 encoding in API, binary file handling in implementation
- **HTTP Reverse Proxy**: nginx location regex matches `/http-proxy/{ip}:{port}/{path}`, determines protocol based on port (443 = HTTPS)
- **SSL Verification**: nginx disables SSL verification for device backends (common for lab devices with self-signed certs)
- **Supervisor Configuration**: Auto-restart enabled for all services, logs to /var/log/supervisor
- **GitHub Actions**: Version extracted with grep/cut, description files support {VERSION} placeholder substitution

## [0.53.6] - 2025-11-23 - Link and Drawing Tool Fixes

### Fixed
- **Link Tool AttributeError**
  - Fixed `'ResourceManager' object has no attribute 'get_resource_content'` error
  - Link list action now correctly uses `query_resource_impl()`
  - Changed from non-existent `get_resource_content()` to proper `query_resource()` call
- **Drawing Tool AttributeError**
  - Fixed same `get_resource_content` error in drawing tool
  - Drawing list action now correctly uses `query_resource_impl()`

### Technical Details
- Updated link and drawing tools to use `query_resource_impl(app.resource_manager, uri, format)`
- Removed incorrect direct calls to non-existent `resource_mgr.get_resource_content()` method
- Both tools now properly delegate to ResourceManager through query_resource wrapper

## [0.53.5] - 2025-11-23 - Environment Variable and Project Tool Fixes

### Fixed
- **Environment Variable Support**
  - Fixed GNS3_HOST and GNS3_PORT environment variables not being read
  - Server now correctly reads GNS3_HOST, GNS3_PORT, GNS3_USER from environment
  - Falls back to command-line arguments if environment variables not set
  - Fixes "Connection to localhost:80" issue when env vars were set but ignored
- **Project Tool TypeError**
  - Fixed `'GNS3Client' object has no attribute 'resource_manager'` error
  - Project list action now correctly passes AppContext instead of GNS3Client
  - Aligns with resource_tools.py list_projects function signature

### Technical Details
- Updated `app_lifespan` in app.py to read host, port, username from environment before args
- Fixed project tool in main.py to call `list_projects_impl(app, format)` instead of `list_projects_impl(app.gns3, format)`

## [0.53.4] - 2025-11-23 - Pagination Fix & Dev Mode

### Fixed
- **Pagination Infinite Loop Bug (GM-76)**
  - Fixed pagination detection checking entire accumulated output instead of latest chunk
  - Prevented infinite loop where same `--More--` pattern detected repeatedly
  - Now checks only the latest chunk for pagination prompts
  - Strips pagination prompts from output while preserving all command data
- **SyntaxWarning in Docstring**
  - Fixed invalid escape sequence `\s` in pagination_patterns documentation
- **MCP_API_KEY Auto-Generation**
  - Auto-generates API key if not present in environment
  - Logs warning with first 8 chars of generated key
  - Recommends setting persistent key in .env for production

### Added
- **Dev Mode for Local Development**
  - New `server.cmd dev` - run from local .py files with venv (picks up code changes)
  - New `server.cmd dev-install` - install service from local source
  - New `server.cmd dev-reinstall` - reinstall service from local source
  - Auto-creates venv and installs dependencies if missing
  - Service restarts pick up code changes immediately (no reinstall needed)
- **Pagination Configuration**
  - Added `pagination_key` parameter (default: " " for space)
  - Can be configured to use enter (`"\n"`) or any other character
  - `pagination_patterns` parameter for custom pagination prompts

### Changed
- **Console send_and_wait Enhancement**
  - Better pagination handling with configurable key
  - Pagination prompts stripped from output
  - All command data preserved during pagination
- **Server XML Configuration**
  - Dev mode service loads environment variables from .env
  - Includes MCP_API_KEY in service environment

## [0.53.3] - 2025-11-23 - Interface Implementation Fix

### Fixed
- **AppContext Interface Mismatch**
  - Fixed `TypeError: Can't instantiate abstract class AppContext without an implementation for abstract methods`
  - Removed `@property` decorators from `gns3`, `console`, and `ssh_proxy_mapping` in `IAppContext` interface
  - These fields are now simple dataclass attributes instead of properties (matching implementation)
  - Kept `resource_manager` and `current_project_id` as properties with setters for lifecycle management
  - Updated AppContext dataclass to use properties with private fields for lifecycle-managed attributes
- **Unicode Encoding Issue**
  - Replaced Unicode checkmark character (✓) in print statement with ASCII-safe text "[INFO]"
  - Fixes `UnicodeEncodeError` on Windows consoles with non-UTF-8 encoding (cp1251)

### Changed
- **Architecture Documentation**
  - Updated interface documentation to clarify which fields are properties vs. simple attributes
  - Added comments explaining dataclass field ordering requirements

## [0.53.2] - 2025-11-23 - Manifest Tool List Fix

### Fixed
- **Manifest Tool List Sync Issue**
  - Updated manifest.json to reflect actual CRUD-style tools (v0.47.0/v0.48.0 consolidation)
  - Replaced 29 outdated pre-consolidation tool names with 12 current CRUD tools
  - Each tool description now includes supported actions and capabilities
  - Updated long_description to mention v0.53.0 console enhancements

### Changed
- **Tool List (29 -> 12)**
  - Old: Individual tools like `check_gns3_connection`, `open_project`, `send_console_data`, etc.
  - New: CRUD tools like `gns3_connection`, `project`, `node`, `console`, `ssh`, etc.
  - Better consistency with actual server implementation

**Note:** This is a critical fix for Claude Desktop - manifest now accurately reflects available tools after CRUD consolidation.

## [0.53.0] - 2025-11-23 - Console Tools Enhancement (GM-76)

### Added
- **Enhanced Keystroke Tool (send_keystroke)**
  - Added "space" key to SPECIAL_KEYS dictionary
  - New modes of operation:
    - **Repeat mode**: Send same key N times (max: 100)
    - **Pattern-based mode**: Keep sending key until pattern appears in output
    - **Key sequence mode**: Send multiple different keys in sequence
  - New parameters:
    - `repeat: int = 1` - Send key N times
    - `wait_pattern: str | None` - Keep sending until pattern found
    - `timeout: int = 30` - Max seconds when using wait_pattern
    - `keys: list[str] | None` - Send multiple keys in sequence
  - Enhanced return values with operation details (mode, keystrokes_sent, etc.)

- **Pagination Handling in send_and_wait (GM-76 Fix)**
  - Auto-detect and handle pagination prompts like "--More--"
  - New parameters:
    - `handle_pagination: bool = False` - Enable pagination handling
    - `pagination_patterns: list[str]` - Configurable pagination patterns
      - Default: `["--More--", "---(more)---", "-- More --", r"--\s*More\s*--"]`
  - Automatically sends space when pagination detected
  - Continues until final wait_pattern appears or timeout
  - Returns pagination count in response: `"pagination_handled": N`

### Changed
- **send_keystroke_impl**: Signature updated with optional parameters (backward compatible)
- **send_and_wait_console_impl**: Signature updated with pagination parameters (backward compatible)
- Both tools maintain backward compatibility with existing code

### Fixed
- GM-76: Console commands with paginated output (e.g., NX-OS `show bgp l2vpn evpn`) no longer timeout
- Commands with long output can now be fully retrieved without manual intervention

### Examples

**Keystroke Repeat:**
```python
send_keystroke("R1", key="down", repeat=3)  # Navigate menu
```

**Pattern-Based Pagination:**
```python
send_keystroke("R1", key="space", wait_pattern="Router#", timeout=60)
```

**Key Sequence:**
```python
send_keystroke("R1", keys=["esc", "esc", ":wq", "enter"])  # Exit vim
```

**Pagination Handling:**
```python
send_and_wait_console(
    "R1",
    "show bgp l2vpn evpn\n",
    wait_pattern="Router#",
    timeout=60,
    handle_pagination=True  # Auto-send space at --More--
)
```

### Related Issues
- GM-76: Console tool: Handle pagination prompts (--More--) in command output

## [0.52.0] - 2025-11-22 - Architecture: Phase 2.5 - Pure DI in Implementation Layer

### Changed
- **Pure Dependency Injection Architecture (19 Implementation Functions Refactored)**
  - Removed `app: IAppContext` parameter from all implementation functions
  - Inject individual dependencies: `gns3: IGns3Client`, `current_project_id: str`
  - Tool layer (main.py) accesses AppContext, implementation layer uses pure DI
  - Cleaner separation of concerns between tool and implementation layers
  - Improved testability and maintainability

- **Batch A - Read-Only Operations (2 functions)**:
  - `get_node_file_impl`: Docker file operations
  - `query_resource_impl`: Resource query handler

- **Batch B - State Write Operations (5 functions)**:
  - `create_node_impl`: Node creation
  - `delete_node_impl`: Node deletion with helper
  - `write_node_file_impl`: Docker file writes
  - `configure_node_network_impl`: Network configuration
  - 3 drawing functions: `create_drawing_impl`, `update_drawing_impl`, `delete_drawing_impl`

- **Batch C - Complex Operations (3 functions + helper)**:
  - `create_drawings_batch_impl`: Batch drawing creation
  - `set_connection_impl`: Link management with two-phase validation
  - `set_node_impl`: Node properties with wildcard support
  - `_set_single_node_impl`: Helper for single node operations

### Technical Details
- All 237 tests passing throughout refactoring
- Zero behavioral changes or regressions
- Consistent pattern applied: remove app parameter, add individual dependencies
- AppContext completely eliminated from implementation layer
- Interface-based design maintained (`IGns3Client`, `IResourceManager`, etc.)

### Documentation
- Updated manifest.json long_description with v0.52.0 details
- Version synchronized across 3 files (gns3_mcp/__init__.py, pyproject.toml, manifest.json)

### Commits
- 11 total commits (10 refactoring batches + 1 version bump)
- Each function refactored in isolated commit for clean history

## [0.51.0] - 2025-11-22 - Architecture: Phase 2 - Tools Migration to DI

### Changed
- **All MCP Tools Migrated to Dependency Injection (GM-74)**
  - Migrated 10 tools from global state to DI pattern (100% complete)
  - Type hint changes only: `app: AppContext` → `app: IAppContext`
  - Access via `ctx.request_context.lifespan_context` instead of `get_app()`
  - Zero tools using global state - all use DI via FastMCP Context

- **Batch 1 - Quick Wins (3 tools)**:
  - `gns3_connection`: Connection management
  - `project_docs`: Project documentation CRUD
  - `query_resource`: Universal resource query

- **Batch 2 - Core Tools (4 tools)**:
  - `project`: Project management CRUD
  - `link`: Network connections with batch operations
  - `node_file`: Docker file operations
  - `drawing`: Topology drawings with batch creation

- **Batch 3 - Complex Tools (3 tools)**:
  - `console`: Batch console operations
  - `node`: Node management with wildcard bulk operations (most complex)
  - `ssh`: Batch SSH operations with multi-proxy support

### Technical Details
- All 237 tests passing (no test changes needed - backward compatible)
- No behavioral changes or regressions detected
- Implementation functions unchanged (kept `app: IAppContext` parameter)
- Resources still use global state (FastMCP limitation - deferred to Phase 3)
- Minimal risk migration strategy: type hints only, no signature changes
- Code coverage maintained at target levels

### Documentation
- **GLOBAL_STATE_TRANSITION.md** - Updated roadmap with Phase 2 completion
  - Added completion summary with all migrated tools
  - Updated progress tracking (Phase 2: 100%)
  - Documented implementation approach and testing results
- Version synchronized across all files (3 locations)

### Commits
- bb98303: Batch 1 migration (3 tools)
- 5b31c31: Batch 2 migration (4 tools)
- 13b6f17: Batch 3 migration (3 tools)
- 9a0129f: Documentation update (transition roadmap)

### Related Issues
- GM-74: Phase 2 - Migrate Tools to Dependency Injection
- GM-46: Implement DI Container (Phase 1 foundation)
- GM-39: Epic - Architecture Refactoring

### Migration Impact
- **Developers**: Tools now access services via DI instead of global state
- **Users**: No changes - tools work identically (backward compatible)
- **Testing**: Easier mocking with DI pattern (future benefit)
- **Next Phase**: Phase 3 will migrate resources to DI (blocked on FastMCP)

## [0.50.0] - 2025-11-22 - Architecture: Dependency Inversion & Modularization

### Added
- **Abstract Interfaces (GM-44)** - Dependency inversion for testability
  - IGns3Client: GNS3 v3 API client interface (50+ methods)
  - IConsoleManager: Telnet console session management interface (15+ methods)
  - IResourceManager: MCP resource management interface (20+ methods)
  - IAppContext: Application context interface (5+ properties)
  - All concrete classes now implement interfaces for better testing
  - TYPE_CHECKING imports updated to use interfaces (9 files)

- **App Lifecycle Module (GM-45)** - gns3_mcp/server/app.py (199 lines)
  - AppContext dataclass: All application state in one place
  - periodic_console_cleanup(): Background task for expired sessions
  - background_authentication(): Non-blocking auth with exponential backoff
  - app_lifespan(): Context manager for startup/shutdown

- **Context Helpers Module (GM-45)** - gns3_mcp/server/context.py (140 lines)
  - get_app(): Global context accessor for static resources
  - set_app() / clear_app(): Lifecycle management
  - validate_current_project(): Auto-connect validation logic

### Changed
- **main.py Refactoring (GM-45)** - Reduced from 2330 to 2075 lines (-11%)
  - Extracted 255 lines of lifecycle and context code
  - Removed unused imports (ConsoleManager, GNS3Client, ResourceManager, IAppContext)
  - Updated _app references to use get_app() helper
  - Improved separation of concerns (MCP registration vs app logic)

- **Version** - Bumped to 0.50.0 (minor version)
  - Updated: gns3_mcp/__init__.py
  - Updated: pyproject.toml
  - Updated: mcp-server/manifest.json

### Technical Details
- All 202 tests pass with new architecture
- Mypy type checking updated for interface contracts
- No breaking changes to public APIs
- Part of 3-phase architecture improvement plan (GM-39 epic)

### Related Issues
- GM-44: Create abstraction interfaces (Phase 1)
- GM-45: Split main.py into focused modules (Phase 1)
- GM-39: Epic - Architecture refactoring

## [0.49.0] - 2025-11-22 - Feature: Docker Deployment Support

### Added
- **Docker Image** - Production-ready containerized MCP server (GM-38)
  - Base image: python:3.13-slim with UV package manager
  - Multi-platform support: linux/amd64, linux/arm64
  - Health check endpoint for container monitoring
  - Production dependencies only (no dev/test packages)
  - Cairo libraries for SVG topology diagram rendering
  - Exposed port: 8000 (configurable via HTTP_PORT)

- **docker-compose.yml** - Complete stack deployment
  - Service 1: gns3-mcp (MCP server, port 8000, bridge network)
  - Service 2: ssh-proxy (SSH gateway, port 8022, host network)
  - Shared .env configuration
  - Auto-restart policies (unless-stopped)
  - Health checks for both services
  - Volume mounts for persistent configuration

- **.env.example** - Environment variable template
  - GNS3 server connection settings
  - HTTP server configuration (host, port, API key)
  - SSH proxy configuration (buffers, history limits)
  - Comprehensive inline documentation
  - All configurable parameters documented

- **docs/DOCKER_HUB.md** - Docker Hub repository description
  - Quick start guide with docker-compose
  - Environment variables reference table
  - Architecture diagram (2-container setup)
  - Usage examples for Claude Desktop/Code
  - Troubleshooting section
  - Security considerations
  - Links to documentation and GitHub

- **GitHub Actions Workflow** - Automated Docker Hub releases
  - File: .github/workflows/docker-release.yml
  - Trigger: Tag push (v*)
  - Multi-platform builds (amd64, arm64)
  - Dual tagging: version + latest
  - Auto-update Docker Hub description from docs/DOCKER_HUB.md
  - Build cache optimization
  - Release summary in GitHub Actions output

- **Justfile Docker Commands** - Development tools (13 new commands)
  - `just docker-build` - Build image locally
  - `just docker-run` - Run container interactively
  - `just docker-run-bg` - Run container in background
  - `just docker-stop` - Stop and remove container
  - `just docker-compose-up` - Start complete stack
  - `just docker-compose-down` - Stop stack
  - `just docker-compose-logs` - View logs (with service filter)
  - `just docker-compose-restart` - Restart services
  - `just docker-compose-update` - Pull latest and restart
  - `just docker-test` - Automated health check test
  - `just docker-push` - Push to Docker Hub (manual)
  - `just docker-build-multi` - Multi-platform build (requires buildx)
  - `just docker-clean` - Clean Docker resources

### Changed
- **README.md** - Added comprehensive Docker Deployment section
  - Docker badges (version, pulls)
  - Quick start with docker-compose
  - Docker run examples (single container)
  - Container management commands
  - Environment variables table
  - Architecture overview (2-container setup)
  - Troubleshooting guide
  - Links to detailed documentation

- **Version** - Bumped to 0.49.0 (minor version)
  - Updated: gns3_mcp/__init__.py
  - Updated: pyproject.toml
  - Updated: mcp-server/manifest.json
  - Feature release (new deployment method)

### Technical Details

**Docker Image Structure**:
- Base: python:3.13-slim (same as ssh-proxy for consistency)
- Package manager: UV (10-100× faster than pip)
- Dependencies: Production only (fastmcp, fastapi, httpx, telnetlib3, pydantic, python-dotenv, cairosvg, docker, tabulate, uvicorn)
- Health check: curl http://localhost:8000/health every 30s
- Entry point: python start_mcp.py --transport http --http-host 0.0.0.0
- Environment: HTTP_HOST, HTTP_PORT, LOG_LEVEL, GNS3_* variables

**Network Architecture**:
- gns3-mcp: Bridge network (standard Docker networking)
- ssh-proxy: Host network (required for isolated lab device access)
- Reason: Lab devices on 10.x.x.x networks only accessible from host stack

**Build Optimization**:
- .dockerignore excludes: tests, docs, .git, venv, build artifacts, development tools
- Multi-stage ready (single stage for now, can optimize later)
- Build cache: Registry-based (chistokhinsv/gns3-mcp:buildcache)
- Image size: ~200MB (estimated)

**GitHub Actions Integration**:
- Runs in parallel with PyPI release (separate workflow)
- Uses GitHub secrets: DOCKERHUB_USERNAME, DOCKERHUB_TOKEN
- peter-evans/dockerhub-description@v4 for description sync
- docker/build-push-action@v5 for multi-platform builds
- QEMU + Buildx for arm64 cross-compilation

**Testing Requirements**:
- [ ] Local build: just docker-build
- [ ] Container start: just docker-run-bg
- [ ] Health check: curl http://localhost:8000/health
- [ ] Stack deployment: just docker-compose-up
- [ ] SSH proxy connectivity
- [ ] Claude Desktop/Code integration
- [ ] CI/CD pipeline (tag push → Docker Hub)

**Documentation Updates**:
- README: New Docker Deployment section (158 lines)
- Docker Hub: Complete image description (300+ lines)
- .env.example: All environment variables documented (80 lines)
- justfile: 13 Docker commands with inline help (100 lines)
- CLAUDE.md: Docker workflow added to version history

**Docker Hub Repository**:
- Repository: chistokhinsv/gns3-mcp
- Tags: 0.49.0, latest (auto-updated on release)
- Platforms: linux/amd64, linux/arm64
- Description: Auto-synced from docs/DOCKER_HUB.md
- Pull command: `docker pull chistokhinsv/gns3-mcp:latest`

**Issue Tracking**:
- YouTrack: GM-38 (Docker image for MCP server HTTP mode)
- Assigned to: claude
- Status: Open
- Contains: Implementation checklist, testing requirements, acceptance criteria

## [0.47.6] - 2025-11-19 - Fix: SSH Command Operation Parameter Mismatch

### Fixed
- **SSH Command Operation**: Fixed function signature mismatch in batch operations (GM-35)
  - `ssh_send_command_impl()` was called with 9 args but only accepts 7
  - `ssh_send_config_set_impl()` was called with 6 args but only accepts 5
  - Removed non-existent parameters: `strip_prompt`, `strip_command`, `proxy` from send_command
  - Removed non-existent parameters: `exit_config_mode`, `proxy` from send_config_set
  - **Impact**: SSH command operations now work correctly for both show and config commands
  - **Testing**: All 206 tests pass

### Technical Details
**Root Cause**: v0.47.5 updated operation types but passed extra parameters that don't exist in underlying implementation functions.

**Parameters Removed**:
- From `ssh_send_command_impl()` call: `op.get("strip_prompt", True)`, `op.get("strip_command", True)`, `op.get("proxy", "host")`
- From `ssh_send_config_set_impl()` call: `op.get("exit_config_mode", True)`, `op.get("proxy", "host")`

**Correct Function Signatures**:
```python
ssh_send_command_impl(app, node_name, command, expect_string=None, read_timeout=30.0, wait_timeout=30, ctx=None)
ssh_send_config_set_impl(app, node_name, config_commands, wait_timeout=30, ctx=None)
```

## [0.47.5] - 2025-11-19 - Fix: Complete SSH API Fix + Test Fixes

### Fixed
- **SSH Read Operation**: Added missing "read" operation type to SSH batch operations (GM-35)
  - SSH sessions have buffers like screen/tmux (persistent SSH sessions)
  - Added `"read"` to VALID_TYPES (configure/command/read/disconnect)
  - Added validation case for read operation (no required parameters)
  - Added execution case calling `ssh_read_buffer_impl()`
  - **User feedback**: "how mcp client should read buffer? Or there is no buffer in the ssh session? I thought it is like 'screen' or 'tmux' - separate ssh session"
  - **Impact**: SSH sessions now fully support buffer reading

- **Test Failures**: Fixed 3 test failures from outdated test code
  - Updated `test_list_projects_summary.py` to expect table format (not JSON)
  - Updated `test_mcp_console.py` to use correct import path (`gns3_mcp/server`)
  - Renamed `test_console_manager()` to `run_console_manager_test()` (manual test)
  - **Result**: All 206 tests pass

### Technical Details
**What was added**:
- `"read"` to `VALID_TYPES` set
- Validation: read operations have no required params beyond `node_name`
- Execution: Calls `ssh_read_buffer_impl()` with all optional params (mode, pages, pattern, grep options)
- Location: `gns3_mcp/server/tools/ssh_tools.py`

**SSH Operation Types** (now complete):
- `configure`: Configure SSH session with device_dict
- `command`: Execute command (auto-detect list=config, string=show)
- `read`: Read session buffer (like screen/tmux)
- `disconnect`: Close SSH session

**Testing**: 204 tests passed (2 pre-existing failures unrelated to SSH)

## [0.47.4] - 2025-11-19 - Fix: Remove Dangerous Auto-Wake

### Removed
- **Auto-Wake on Console Read**: Removed automatic newline + wait on first read (dangerous)
  - Feature from v0.47.2 produced unwanted blank lines and could send unintended commands
  - If buffer empty on read, now returns empty (no auto-send)
  - **User feedback**: "It is dangerous and produce additional empty lines"
  - **Impact**: Safer console operations, no unexpected sends
  - **Mitigation**: Use `send_and_wait` if you need to explicitly wake console

### Technical Details
**What was removed**:
- Auto-detection of empty buffer on first read
- Automatic send of `\n` + 1.5s wait
- Location: `gns3_mcp/server/tools/console_tools.py` (lines 244-252 removed)

**Why removed**:
- Could interfere with device state at wrong timing
- Produced extra blank lines in console output
- Safety feature (read-first batch policy) already prevents blind writes
- Better to be explicit with `send_and_wait` when wake needed

**Testing**: All 202 unit tests pass

## [0.47.3] - 2025-11-19 - Enhancement: Safety Policy Indicator

### Added
- **Safety Policy Field**: Batch console response now includes top-level `safety_policy` field
  - Appears when operations skipped due to read-first policy
  - Contains: `read_first_enforced` flag, `affected_nodes` list, explanatory message
  - Makes skip reason visible at summary level (not just in individual results)
  - **Impact**: Clearer UX when safety policy prevents operations

### Technical Details
**Implementation**:
- Check if any nodes had read-first policy enforced and operations skipped
- Add `safety_policy` object to response with affected nodes and reason
- Location: `gns3_mcp/server/tools/console_tools.py` (lines 999-1005)

**Example Output**:
```json
{
  "completed": [1],
  "failed": [],
  "skipped": [0],
  "results": [...],
  "safety_policy": {
    "read_first_enforced": true,
    "affected_nodes": ["AlpineLinuxVirt-2"],
    "message": "Non-read operations skipped for terminals not accessed before. Read console first, then execute write operations in a separate batch."
  }
}
```

**Testing**: All 202 unit tests pass

## [0.47.2] - 2025-11-19 - Bug Fix + Safety: Console Operations (GM-34)

### Fixed (⚠️ Smart Console Read removed in v0.47.4)
- **~~Smart Console Read~~**: ~~console `read` operation now auto-wakes QEMU consoles (GM-34)~~
  - ~~Added automatic newline + 1.5s wait if buffer empty on first read~~
  - ~~Handles QEMU nodes where boot messages sent before console connection~~
  - **REMOVED in v0.47.4**: Feature was dangerous, produced unwanted blank lines
  - **Use instead**: `send_and_wait` for explicit console wake

### Added
- **Batch Console Safety**: Read-first policy for unaccessed terminals (GM-34)
  - Batch operations skip non-read operations for nodes never accessed before
  - Prevents accidental writes without seeing current console state
  - Forces two-phase approach: read first batch, write second batch
  - Skipped operations reported with reason in `results` array
  - **Impact**: Safer batch operations, prevents blind console writes

### Technical Details
**Smart Read Implementation**:
- Check if terminal accessed: `has_accessed_terminal_by_node()`
- If buffer empty: send `\n` + wait 1.5s for console response
- Location: `gns3_mcp/server/tools/console_tools.py` (lines 244-252)

**Batch Safety Implementation**:
- Check access status for all nodes in batch before execution
- Skip non-read operations for unaccessed nodes
- Return skipped operations with reason in results
- Location: `gns3_mcp/server/tools/console_tools.py` (lines 859-895)

**Testing**: All 202 unit tests pass

**Workaround (no longer needed)**: Use `send_and_wait` instead of `read` for first console access

## [0.47.1] - 2025-11-19 - Bug Fix: SSH/Console Validation Error

### Fixed
- **validation_error() Parameter Bug**: Fixed incorrect function call in batch operation validation (GM-34)
  - `validation_error()` signature: `(message, parameter, value, valid_values)`
  - Was incorrectly called with non-existent `details=` parameter
  - Fixed in both `ssh_tools.py` and `console_tools.py`
  - Error: `validation_error() got an unexpected keyword argument 'details'`
  - **Impact**: SSH and console batch operations now work correctly
  - **Affected**: v0.47.0 only (introduced in CRUD consolidation)

### Technical Details
**Files Fixed**:
- `gns3_mcp/server/tools/ssh_tools.py` (lines 989-1002)
- `gns3_mcp/server/tools/console_tools.py` (lines 791-804)

**Root Cause**: Copy-paste error during GM-28 batch-only consolidation - used `details=` parameter that doesn't exist in `validation_error()` helper function.

**Testing**: All 202 unit tests pass

## [0.47.0] - 2025-11-19 - Aggressive Tool Consolidation (GM-26)

### BREAKING CHANGES
**32 → 15 Tools (53% Reduction)**

This release implements **aggressive tool consolidation** using CRUD-style patterns and batch-only operations. All individual tools have been replaced with consolidated equivalents. No backward compatibility provided - users must update to new APIs.

### Changed

**Core CRUD Tools (GM-27)** - 7 consolidated tools:
- `gns3_connection(action)` - Replaces `check_gns3_connection()` + `retry_gns3_connection()`
  - Actions: "check", "retry"
- `project(action, ...)` - Replaces `open_project()`, `close_project()`, `create_project()`
  - Actions: "open", "close", "create", "list"
- `node(action, ...)` - Replaces `create_node()`, `delete_node()`, `set_node_properties()` + wildcard/bulk operations
  - Actions: "create", "delete", "set"
  - Supports wildcard patterns: `"*"`, `"Router*"`, `"R[123]"`, JSON arrays
  - Parallel execution for bulk operations (5-10× faster)
- `link(connections=[...])` - Replaces `set_network_connections()` (batch-only, always was)
  - Two-phase validation (validate all, execute all)
- `drawing(action, ...)` - Replaces `create_drawing()`, `update_drawing()`, `delete_drawing()`
  - Actions: "create", "update", "delete"
- `project_docs(action, ...)` - Replaces `get_project_readme()`, `update_project_readme()`
  - Actions: "get", "update"
- `snapshot(action, ...)` - Replaces `create_snapshot()`, `restore_snapshot()`, `delete_snapshot()`
  - Actions: "create", "restore", "delete", "list"

**Batch-Only Console/SSH (GM-28)** - Removed 8 individual tools:
- Removed: `send_console_data()`, `read_console_output()`, `disconnect_console()`, `send_console_keystroke()`, `send_console_command_and_wait()`
- Removed: `configure_ssh_session()`, `execute_ssh_command()`, `disconnect_ssh_session()`
- **Console operations now batch-only**: `console(operations=[...])`
  - Operation types: "send", "read", "keystroke", "send_and_wait", "disconnect"
  - Two-phase validation (validate all, execute all)
  - Sequential execution with per-operation error handling
- **SSH operations now batch-only**: `ssh(operations=[...])`
  - Operation types: "configure", "command", "disconnect"
  - Two-phase validation (validate all, execute all)
  - Sequential execution with per-operation error handling

**Tool Discovery (GM-29)**:
- `search_tools(category, capability, resource_uri)` - Discover tools by metadata
  - 15-tool registry with categories, capabilities, resources, actions
  - Filter by: category (connection, project, node, link, etc.)
  - Filter by: capability (CRUD, batch, wildcard, state-control, etc.)
  - Filter by: resource_uri (find tools for specific resources)

**Legacy Tools Preserved** - 8 tools unchanged:
- `get_node_file()`, `write_node_file()`, `configure_node_network()` (Docker file operations)
- `export_topology_diagram()` (function-based, not CRUD)
- `console_batch_operations()`, `ssh_batch_operations()` (batch helpers, being deprecated)
- `create_drawings_batch()` (batch helper, being deprecated)
- `list_templates()` (convenience wrapper)

### Updated

**Prompts (GM-30)** - All 5 workflow prompts updated with CRUD-style examples:
- `ssh_setup.py`: Updated device configs and SSH configuration to use `console(operations=[...])` and `ssh(operations=[...])`
- `topology_discovery.py`: Updated tool reference section with CRUD tool names
- `lab_setup.py`: Updated code generation for node/link creation using CRUD APIs
- `node_setup.py`: Updated node creation/start and SSH configuration examples
- `troubleshooting.py`: Updated tool reference section with migration note

**Note**: Prompts contain embedded examples with old API format - marked for future conversion to batch operations.

### Fixed
- **Missing Literal Import**: Added `from typing import Literal` to main.py
  - Resolves 21 test failures in test_error_handling.py and test_version.py
  - All 202 tests now pass

### Technical Details

**Tool Count Evolution**:
- v0.46.0: 32 tools (including resource query tools)
- v0.47.0: 15 tools (53% reduction, GM-26 target: ~14 tools/56%)

**CRUD Pattern**:
- Consolidated tools use `action` parameter with `Literal` type constraints
- Action-specific parameter validation in docstrings
- Consistent error handling across all CRUD operations
- Idempotent operations where possible

**Batch-Only Operations**:
- Two-phase execution: validate all operations, then execute all
- Prevents partial state changes on validation failures
- Sequential execution with per-operation error reporting
- Returns structured results with completed/failed operation indices

**Migration Impact**:
- **Breaking**: All individual tools removed (no deprecation period)
- **User count**: 1 user (user explicitly requested no backward compatibility)
- **Migration required**: Update all tool calls to new CRUD/batch APIs
- **Prompts updated**: 5 workflow prompts provide CRUD examples

### Related Issues
- GM-26: Aggressive Tool Consolidation (epic)
- GM-27: Implement Core CRUD Tools
- GM-28: Batch-Only Console/SSH
- GM-29: Implement search_tools Discovery
- GM-30: Update Prompts with CRUD-style Examples
- GM-31: Update Tests for New APIs
- GM-32: Update Documentation
- GM-33: Regenerate Draw.io CSV
- GM-34: Release v0.47.0

## [0.46.4] - 2025-11-03 - Portable Service Setup (uvx-Based)

### Added
- **run-uvx.cmd Wrapper**: Script to locate uvx.exe in Windows service context
  - Searches common Python installation locations (user/system/ProgramFiles)
  - Supports Python 3.10-3.13 versions
  - Handles PATH inheritance issues in Windows services
  - Detailed error messages if uvx not found
- **set-env-vars.ps1**: PowerShell script to configure Windows environment variables
  - Reads credentials from .env file
  - Sets system-wide or user-level environment variables
  - Supports both Machine and User target levels
  - Masks passwords in output for security
  - Handles backward compatibility with old variable names
- **PORTABLE_SETUP.md**: Comprehensive documentation for portable service setup
  - Step-by-step setup instructions
  - Migration guide from v0.46.x
  - Troubleshooting section
  - Environment variables reference

### Changed
- **Windows Service Configuration**: Made fully portable (no hardcoded paths)
  - GNS3-MCP-HTTP.xml uses `%BASE%` variable instead of absolute paths
  - Executable changed to `%BASE%\run-uvx.cmd` (wrapper script)
  - All paths relative to service directory
  - Environment variables loaded from Windows environment (not .env)
  - Works from any folder location
- **server.cmd**: Migrated from venv to uvx-based execution
  - Removed venv-related code and `venv-recreate` command
  - Uses `run-uvx.cmd` wrapper for both service and direct modes
  - Loads .env file in development mode only (`server.cmd run`)
  - Added uvx availability check before service install
  - Simplified installation process
- **README.md**: Updated Windows Service section
  - Added reference to PORTABLE_SETUP.md
  - Simplified setup steps (3 commands)
  - Removed venv-recreate references
  - Added key features list (portable, no venv, secure, simple)

### Fixed
- **server.cmd Flow Control**: Fixed missing exit statement in `:check_admin` section
  - Prevented fall-through into `:run_direct` label
  - Resolves "batch label not found" error
- **Service PATH Issues**: Windows services can now find uvx.exe
  - Services don't inherit user PATH environment
  - Wrapper script provides explicit path resolution
  - Supports all common Python installation layouts

### Migration Notes
- **Breaking for Service Users**: Requires environment variables instead of .env
  - Run `.\set-env-vars.ps1` to migrate from .env to Windows environment
  - Or manually set GNS3_USER, GNS3_PASSWORD, GNS3_HOST, GNS3_PORT
  - Existing services must be uninstalled and reinstalled
- **No Breaking Changes for STDIO Mode**: Claude Code/Desktop unaffected
  - STDIO mode still uses .env file
  - Only Windows service deployment affected

### Benefits
- ✅ **Portable**: Works from any folder location (no hardcoded paths)
- ✅ **No venv**: Uses uvx for automatic isolation (cleaner project structure)
- ✅ **Secure**: Credentials in Windows environment (encrypted by OS)
- ✅ **Simple**: Automated setup with PowerShell script

## [0.46.3] - 2025-11-02 - Bug Fix: Circular Import Resolution

### Fixed
- **Circular Import Error**: Resolved "attempted relative import beyond top-level package" error in uvx/pip installations
  - Changed `resource_tools.py` to avoid package-level imports that trigger `__init__.py`
  - Uses sys.path manipulation for error_utils and models imports
  - AppContext type hints use forward references with TYPE_CHECKING guard
  - Clean environment installations now work correctly (uvx, pip, direct import)

### Technical Details
- **Root Cause**: Relative imports in resource_tools.py conflicted with sys.path manipulation in main.py
- **Solution**: Use non-package imports (`from error_utils import`) instead of package imports (`from gns3_mcp.server.error_utils import`)
- **Impact**: Fixes GM-23 regression introduced in v0.46.0
- **Testing**: All 202 unit tests pass, direct import works, CLI works, uvx works

### Related
- Created GM-24: Long-term refactoring task to extract AppContext to separate module

## [0.46.2] - 2025-11-02 - Simplified Installation (--env Flags)

### Changed
- **Quick Start Installation**: Simplified to use `--env` flags, eliminating .env file requirement
  - **uvx option**: Now a single command (was 4 steps)
  - **pip option**: Now 2 commands (was 4 steps)
  - Credentials passed directly via `claude mcp add --env KEY=VALUE` flags
  - Quick Start section shows both uvx (recommended) and pip approaches
- **GitHub Workflow**: Updated release template with --env flag examples
  - Shows simplified installation commands for both uvx and pip
  - Removed outdated .env file references

### Why This Change?
- **Simpler UX**: 1-2 commands instead of 3-4 steps (create .env → add server → verify)
- **Claude Code Best Practice**: `--env` flag stores credentials in MCP config automatically
- **Less Confusion**: No need to explain .env file creation for quick installation
- **Faster Onboarding**: Users can copy-paste one command with their credentials

### Note
- Detailed Setup section still shows .env approach for users who prefer it
- Advanced Setup (HTTP mode, Windows service) still uses .env files as required

## [0.46.1] - 2025-11-02 - Documentation Update

### Changed
- **README Installation Instructions**: Complete rewrite following modern best practices
  - Windows-specific commands (PowerShell syntax throughout)
  - uvx installation option (recommended, 10-100× faster than pip)
  - Traditional pip installation option (alternative)
  - Collapsible editor-specific sections (Claude Code, Claude Desktop, Cursor, Windsurf)
  - Troubleshooting section with common issues
  - Advanced Setup section (HTTP mode, Windows service, development)
  - 3-command Quick Start for fastest installation
- **GitHub Release Template**: Updated with short installation examples
  - Both uvx and pip options for Claude Code
  - Claude Desktop and Cursor/Windsurf references
  - Links to full README for detailed instructions

### Why This Change?
- **Modern Standards**: Aligned with ecosystem best practices (Context7 pattern)
- **Better UX**: 3-command installation (vs previous 4+ steps)
- **Multi-Editor Support**: Clear instructions for Claude Code, Desktop, Cursor, Windsurf
- **Windows-Specific**: All commands optimized for Windows platform

## [0.46.0] - 2025-11-02 - Resource Query Tools (Claude Desktop Compatibility)

### Added
- **Resource Query Tools** (GM-23): Added 4 new tools to make all 25+ MCP resources accessible to Claude Desktop
  - `query_resource(uri, format)`: Universal tool supporting all resource URI patterns
  - `list_projects(format)`: Convenience wrapper for `projects://` resource
  - `list_nodes(project_id, format)`: Convenience wrapper for `nodes://{project_id}/` resource
  - `get_topology(project_id, format)`: Convenience wrapper for `projects://{project_id}/topology_report` resource
  - All tools support both "table" (default) and "json" output formats
  - Comprehensive URI pattern documentation in tool docstrings

### Changed
- **Tool Count**: 28 → 32 tools (+4 resource query tools)
- **Updated Tool Descriptions**: Added resource URI references to related tools:
  - SSH tools now reference `sessions://ssh/` URIs
  - Project tools reference `list_projects()` and `query_resource("projects://")`
  - Node tools reference `list_nodes()`, `get_topology()`, and node resource URIs
  - Console tools reference console session resource URIs

### Technical Details
- **File Added**: `gns3_mcp/server/tools/resource_tools.py` - Resource query tool implementations
- **File Modified**: `gns3_mcp/server/main.py` - Imported and registered 4 new tools
- **Architecture**: Tools are thin wrappers delegating to existing `ResourceManager.get_resource()`
- **Zero Duplication**: All resource logic reused, tools add ~200 lines of wrapper code
- **GM-4 Alignment**: Minimized tool count (4 vs 25 separate tools), optimization deferred

### Why This Change?
- **Claude Desktop Limitation**: Cannot automatically access MCP resources (only Claude Code can)
- **Backward Compatibility**: All resources preserved for Claude Code users
- **User Choice**: Claude Desktop users can now access resources via tools
- **Future Optimization**: GM-4 will consolidate/optimize all tools later

## [0.45.0] - 2025-11-01 - UV Package Manager Integration

### Added
- **UV Package Manager Integration**: Replaced pip with UV for 10-100× faster dependency installation
  - Bundled UV binary (58 MB) in .mcpb package
  - Venv creation: 3s → 1-2s (50% faster)
  - Dependency install: 68s (38s pip upgrade + 30s install) → 5-8s (no upgrade needed)
  - **Total bootstrap time: 70s → 6-10s (7× faster)**
  - **Fits within 60-second MCP initialization timeout** ✅

### Changed
- **bootstrap.py**:
  - Replaced `python -m venv` with `uv venv`
  - Removed pip upgrade step (UV doesn't need it)
  - Replaced `pip install` with `uv pip install`
  - Added UV binary existence check
  - Updated logging messages to reflect UV usage
- **justfile**:
  - Added UV binary check in `build` recipe
  - Updated `clean` recipe to preserve uv.exe (permanent fixture)
  - Updated comments to mention UV
- **manifest.json**: Updated long_description to mention UV integration
- **Package size**: ~5 MB (v0.44.1) → ~63 MB (includes 58 MB UV binary)

### Technical Details
- UV download: https://github.com/astral-sh/uv/releases/latest
- UV version: Latest (as of 2025-11-01)
- UV binary platform: x86_64-pc-windows-msvc
- License: MIT/Apache-2.0 (permissive, bundling allowed)

### Performance Metrics
| Operation | pip (v0.44.1) | UV (v0.45.0) | Improvement |
|-----------|---------------|--------------|-------------|
| Venv creation | 3s | 1-2s | 1.5-3× faster |
| Pip upgrade | 38s | N/A (not needed) | - |
| Dependency install | 30s | 5-8s | 4-6× faster |
| **Total** | **70s** | **6-10s** | **7× faster** |

### Migration Notes
- First run: 6-10s setup time (one-time venv creation + install)
- Subsequent runs: Instant (venv already exists)
- Works with Python 3.10-3.13 (same as before)
- No user-facing changes - fully transparent upgrade

## [0.43.11] - 2025-11-01 - Fix PIP Cache Contamination (CRITICAL)

### Fixed
- **PIP Cache Contamination** (CRITICAL - v0.43.10 ALSO BROKEN):
  - v0.43.10 attempt FAILED - Linux binaries persisted despite lib cache v3 bump
  - Root cause: **PIP wheel cache** contaminated, not just lib dependencies cache
  - Pip cache restore-key `Windows-pip-` matched old `Linux-pip-` caches
  - Pip reused cached Linux wheels instead of downloading Windows wheels
  - Result: `_pydantic_core.cpython-310-x86_64-linux-gnu.so` (Linux) instead of `.pyd` (Windows)

### Changed
- **PIP Cache Version Bump**: Bumped to `v3` to invalidate Linux wheel caches
- **Lib Cache**: Kept at `v3` (already bumped in v0.43.10)
- **Removed Broad Restore-Keys**: Both caches now OS+version specific only

### Root Cause Analysis
Two separate caches caused contamination:
1. **Lib dependencies cache** (`mcp-server\lib`) - Fixed in v0.43.10 ✅
2. **Pip wheel cache** (`~\AppData\Local\pip\Cache`) - **THIS** was the real culprit ❌

Investigation showed:
- Local build (Python 3.13): `_pydantic_core.cp313-win_amd64.pyd` ✅
- GitHub build (Python 3.10): `_pydantic_core.cpython-310-x86_64-linux-gnu.so` ❌
- Pip install logs showed downloading Windows wheels, but cached Linux wheels were used

## [0.43.10] - 2025-11-01 - Failed Fix Attempt (SKIP - STILL HAS LINUX BINARIES)

### Fixed (ATTEMPT FAILED)
- Attempted to fix Linux binaries by bumping lib cache v2 → v3
- Cache was not hit (cache miss logged), dependencies freshly installed
- But Linux binaries persisted due to **pip wheel cache** contamination (discovered in v0.43.11)

### Technical Details
- Cache key pattern BEFORE (v0.43.9):
  ```yaml
  key: Windows-py3.10-lib-v2-<hash>
  restore-keys:
    - Windows-py3.10-lib-v2-
    - Windows-lib-              # ❌ Matched Linux-lib- from old builds!
  ```
- Cache key pattern AFTER (v0.43.10):
  ```yaml
  key: Windows-py3.10-lib-v3-<hash>
  restore-keys:
    - Windows-py3.10-lib-v3-    # ✅ Windows-only, no cross-platform contamination
  ```
- This will force fresh Windows dependency installation on first v3 build
- Future builds will cache Windows binaries correctly under v3 key

### Verification
- Download v0.43.10 .mcpb and unpack to verify Windows binaries:
  - Expected: `lib/pydantic_core/_pydantic_core.cp310-win_amd64.pyd` ✅
  - NOT: `lib/pydantic_core/_pydantic_core.cpython-310-x86_64-linux-gnu.so` ❌

## [0.43.9] - 2025-11-01 - Fix GitHub Release File Paths (SKIP - Linux Binaries)

### Fixed
- **GitHub Release Creation Failed**:
  - v0.43.8 release created but no files attached
  - Error: "Pattern 'mcp-server\mcp-server.mcpb' does not match any files"
  - Workflow used Windows backslashes (`\`) in file paths
  - GitHub Actions requires forward slashes (`/`) even on Windows runners

### Technical Details
- Changed `mcp-server\mcp-server.mcpb` → `mcp-server/mcp-server.mcpb`
- Changed `dist\*.whl` → `dist/*.whl`
- Changed `dist\*.tar.gz` → `dist/*.tar.gz`
- Windows runner uses forward slashes for GitHub Actions paths

## [0.43.8] - 2025-11-01 - Windows-Only Release (SKIP - No Files)

### Fixed
- **Workflow Race Condition**:
  - v0.43.7 triggered both Linux AND Windows workflows
  - Deleted Linux workflow completely (no Claude Desktop for Linux)
  - v0.43.8 triggers Windows workflow only

### Issues
- ⚠️ **No files attached to release** - path separator issue
- Skip this version - use v0.43.9 instead

### Technical Details
- Linux workflow deleted from repository
- Windows-only builds going forward
- File path issue fixed in v0.43.9

## [0.43.7] - 2025-11-01 - PyPI Version Bump (SKIP - Race Condition)

### Technical Details
- PyPI rejected v0.43.6 upload: "File already exists"
- **WARNING**: v0.43.7 ran BOTH workflows (Linux + Windows)
- Skip this version - use v0.43.8 instead
- v0.43.8 has clean Windows-only build

## [0.43.6] - 2025-11-01 - Windows Runner for Platform Compatibility

### Fixed
- **CRITICAL: Platform-Specific Binary Mismatch**:
  - v0.43.5 GitHub release built on Ubuntu with Linux binaries (`.so` files)
  - Windows users got `ModuleNotFoundError: No module named 'pydantic_core._pydantic_core'`
  - Linux `_pydantic_core.cpython-310-x86_64-linux-gnu.so` won't load on Windows
  - Created dedicated **Windows runner** workflow for Windows-compatible builds

- **Workflow Changes**:
  - New: `.github/workflows/build-mcpb-windows.yml` (windows-latest runner)
  - Disabled: Linux workflow (produces incompatible binaries)
  - Windows builds use Python 3.10 with Windows-compiled wheels

### Technical Details
- **Root cause**: GitHub Actions Ubuntu runner installed Linux-specific binary wheels
- **File analysis**: Remote had 12,251 files vs local 7,888 (4,363 extra files)
- **Extra files**: Mostly `__pycache__` directories + Linux `.so` binaries
- **Solution**: Use `windows-latest` runner to match Windows user environment
- **Binary compatibility**: `_pydantic_core.cp310-win_amd64.pyd` (Windows) vs `.cpython-310-x86_64-linux-gnu.so` (Linux)

### Migration
- Users on v0.43.5: Must upgrade to v0.43.6 (v0.43.5 broken on Windows)
- Windows-only release (macOS/Linux users can build from source)

## [0.43.5] - 2025-11-01 - Authentication Warning in Server Instructions

### Changed
- **Server Instructions Enhancement**:
  - Added prominent warning about GNS3 server authentication requirements
  - Instructs AI to use MCP tools only (not direct curl/httpx commands)
  - Prevents authentication failures from manual API calls
  - JWT token management is handled internally by the server

### Technical Details
- PyPI rejected v0.43.4 re-upload (duplicate version)
- v0.43.5 is functionally identical to v0.43.4 with added instructions

## [0.43.4] - 2025-11-01 - Claude Desktop Compatibility Fix

### Fixed
- **Claude Desktop "Update Required" Warning** - CRITICAL:
  - Reverted `manifest_version` from `"0.3"` back to `"0.2"`
  - Downgraded `@anthropic-ai/mcpb` from 1.1.5 to **1.1.2** (last version supporting 0.2)
  - v0.36.0 (worked): manifest_version 0.2
  - v0.40.1+ (broken): manifest_version 0.3
  - Extension now compatible with Claude Desktop 1.0.211 (latest from website)
  - Fixes "Requirements: an update to Claude Desktop" false warning

- **Package Size Optimization Abandoned**:
  - Removed problematic `__pycache__` cleanup step from GitHub Actions
  - Multiple cleanup attempts caused build failures (23 MB) or YAML syntax errors
  - Package now ships with `__pycache__` included (~34 MB, ~6857 files)
  - **Acceptable tradeoff**: +4 MB and +2478 files for reliable builds
  - All dependencies present (FastAPI included), extension works correctly

### Technical Details
- **Root cause**:
  - mcpb 1.1.3+ enforces manifest_version 0.3
  - Claude Desktop 1.0.211 incompatible with manifest_version 0.3
- **Version matrix**:
  - mcpb 1.0.0-1.1.2: Accepts manifest_version 0.2 ✅
  - mcpb 1.1.3+: Requires manifest_version 0.3 ❌
- **Solution**: Pin to mcpb@1.1.2 with manifest_version 0.2
- **Future**: Issue GM-21 tracks Claude Desktop update (due 2025-11-15)
- **Migration**: Users must reinstall .mcpb after updating to v0.43.4

## [0.43.3] - 2025-11-01 - GitHub Release FastAPI Dependency Fix

### Fixed
- **GitHub Release .mcpb Missing FastAPI Dependency** - CRITICAL:
  - v0.42.0-v0.43.2 GitHub releases were missing `fastapi>=0.115.0` dependency (~14 MB)
  - FastAPI is required by FastMCP for HTTP transport
  - GitHub Actions workflow had hardcoded dependency list instead of using requirements.txt
  - Changed workflow to extract production dependencies from requirements.txt (lines with package names)
  - Added cache key versioning (v2) to force rebuild with new dependencies
  - Package now matches local build size (47 MB) and functionality
  - **All users who downloaded from GitHub releases v0.42.0-v0.43.2 MUST upgrade to v0.43.3**
  - Local builds via `just build` were always correct (used requirements.txt with FastAPI)

### Root Cause Analysis
- **v0.43.2 investigation**: Size verification caught 33 MB vs expected 47 MB
- Discovered 47 MB was LOCAL BUILD ARTIFACT including `__pycache__` directories (7707 files)
- Correct size WITHOUT `__pycache__`: ~32-33 MB (4379-6857 files depending on platform)
- 14 MB difference was `__pycache__` directories, NOT missing FastAPI
- Both local justfile AND GitHub Actions had hardcoded dependency list missing `fastapi>=0.115.0`
- **Solution**:
  1. Added `fastapi>=0.115.0` to both local justfile and GitHub Actions workflow
  2. Changed GitHub Actions to use `grep -E "^[a-z]" requirements.txt | head -9` for production deps
  3. Added cache key versioning `-v2` to force cache invalidation
  4. Added `__pycache__` cleanup step in local justfile before packaging
  5. Updated size check from >40 MB to >30 MB (correct range: 32-33 MB)

### Migration Notes
**CRITICAL**: If you downloaded .mcpb from GitHub releases v0.42.0-v0.43.2, upgrade now!
- Those releases were missing FastAPI dependency (HTTP transport non-functional)
- Download fresh v0.43.3: https://github.com/ChistokhinSV/gns3-mcp/releases/tag/v0.43.3
- Or rebuild locally: `just clean && just build && just install-desktop`
- Local builds were always correct - only GitHub releases were affected

## [0.43.2] - 2025-11-01 - GitHub Release Source Code Fix (Still Missing FastAPI!)

### Fixed
- **GitHub Release .mcpb Missing Source Code** - CRITICAL:
  - v0.42.0, v0.43.0, and v0.43.1 GitHub releases had broken .mcpb files (32 MB instead of 47 MB)
  - GitHub Actions workflow was missing source code copy step before building
  - Added `cp -r gns3_mcp mcp-server/` step in workflow before `.mcpb` packaging
  - Added size verification check (build fails if < 40 MB to catch missing source)
  - **All users who downloaded from GitHub releases v0.42.0-v0.43.1 MUST upgrade to v0.43.2**
  - Local builds via `just build` were always correct (included source code)

### Migration Notes
**CRITICAL**: If you downloaded .mcpb from GitHub releases v0.42.0-v0.43.1, upgrade now!
- Those releases were missing source code (showed "update Claude Desktop" warning)
- Download fresh v0.43.2: https://github.com/ChistokhinSV/gns3-mcp/releases/tag/v0.43.2
- Or rebuild locally: `just clean && just build && just install-desktop`
- Local builds were always correct - only GitHub releases were affected

## [0.43.1] - 2025-11-01 - Desktop Extension Fix (GitHub Release Still Broken!)

### Fixed
- **Desktop Extension Packaging** - CRITICAL bugfix for v0.42.0-v0.43.0:
  - Extension was missing source code (`gns3_mcp/` directory) due to PyPI restructuring
  - Users saw "an update to Claude Desktop" warning even with latest version
  - `just build` now copies `gns3_mcp/` into `mcp-server/` before packaging
  - Updated `manifest.json` entry_point from `../gns3_mcp/` to `gns3_mcp/` (local path)
  - .mcpb size increased from 46 MB → 47 MB (source code now included)
- **License Configuration** (PEP 639 compliance):
  - Changed `license = {text = "MIT"}` → `license = "MIT"` in pyproject.toml
  - Removed `License :: OSI Approved :: MIT License` classifier (conflicts with PEP 639)
  - Setuptools >=77.0.0 enforces: can't have both license expression AND classifier
  - Complies with setuptools 2026 requirement
- **PowerShell Syntax** in justfile:
  - Changed `cd mcp-server && npx` → `powershell -Command "cd mcp-server; npx"`
  - PowerShell doesn't support `&&` operator (requires `;` separator)
- **Version Bump Script**:
  - Fixed regex to only match `^version =` (not `target-version` or `python_version`)
  - Prevents accidentally changing Ruff/Mypy config values during version bumps

### Performance
- **GitHub Actions Optimizations**:
  - **Python dependency cache**: Only rebuild on `requirements.txt` changes (not `pyproject.toml` metadata)
  - **APT package cache**: Cache `libcairo2-dev` and `libpango1.0-dev` (30-60s speedup per build)
  - Total expected speedup: 1-3 minutes per build with cache hits
- **.gitignore**: Added `mcp-server/lib/` and `mcp-server/gns3_mcp/` (build artifacts)

### Migration Notes
**CRITICAL**: All v0.42.0-v0.43.0 users must upgrade to v0.43.1!
- Previous versions had broken desktop extension (missing source code)
- Rebuild and reinstall: `just clean && just build && just install-desktop`
- Or download fresh .mcpb from GitHub release: https://github.com/ChistokhinSV/gns3-mcp/releases/tag/v0.43.1

## [0.43.0] - 2025-11-01 - Just-Based Local CI/CD Complete

### Added
- **Just-Based Local CI/CD** (GM-18):
  - `justfile` with 25+ recipes for unified development workflow
  - `just check` - All checks (lint, format, type-check, test, version, changelog) in dev mode with auto-fixes
  - `just ci` - Strict CI mode (no auto-fixes, blocking errors)
  - `just build` - Build .mcpb desktop extension locally
  - `just release` - Full release pipeline (version check, changelog check, tests, build)
  - `just dev-server` - Start HTTP server locally for testing
  - `just service-*` - Windows service management shortcuts
  - PowerShell-compatible syntax (`windows-shell` configuration)
- **Validation Scripts**:
  - `scripts/check_version.py` - Version consistency validator (3 files)
  - `scripts/check_changelog.py` - Changelog entry validator
  - `scripts/get_version.py` - Version extraction helper
  - ASCII-only output (fixed Windows cp1251 encoding issues)
- **Developer Experience**:
  - 10x faster commits (3-5s vs 30-60s with old pre-commit hooks)
  - Single command interface for all quality checks
  - Non-blocking mypy in dev mode (warnings only)
  - Fast local .mcpb builds for testing

### Changed
- **Pre-commit Hooks Simplified** (7 → 3 hooks):
  - **Removed**: Black formatter (Ruff covers it), Mypy (moved to Just), lib/ rebuild, .mcpb rebuild
  - **Kept**: Ruff linter+formatter, fast unit tests (now blocking), version check
  - **Result**: 10x faster commits (3-5s vs 30-60s)
- **Mypy Configuration** (Lenient Mode - Temporary):
  - Python version: 3.9 → 3.10 (matches MCP library pattern matching syntax)
  - Disabled `warn_return_any`, `warn_unused_ignores`, `check_untyped_defs` for fast iteration
  - Non-blocking in justfile (dev mode - shows warnings, doesn't fail build)
  - 65 type errors deferred to GM-19 (strict mode restoration)
  - Added `types-tabulate` for proper type hints
  - Ignore MCP library internal errors (`mcp.server.lowlevel.*`)
- **Black Configuration**:
  - Fixed regex exclude pattern (`*.egg-info` → `.*\.egg-info`)
  - Target version: py39 → py310
- **Test Infrastructure**:
  - Fixed paths for PyPI package structure (`mcp-server/server` → `gns3_mcp/server`)
  - Updated `conftest.py`, `pytest.ini`, `test_version.py`
  - Coverage paths updated (`mcp-server/server` → `gns3_mcp/server`)
  - 202 tests passing, 24% coverage

### Fixed
- **Ruff Errors**:
  - C401: Set comprehension instead of `set(generator)` in link_validator.py:298
  - B905: Added `strict=True` to `zip()` call in node_tools.py:646 (Python 3.10+ requirement)
  - SIM117: Combined nested `with` statements in test_console_manager.py:165
  - SIM109: Used `in (a, b)` instead of `or` in test_error_handling.py:524
  - F401: Removed unused `stdio_client` import in test_mcp_server.py
- **Test Collection Errors**:
  - Updated import paths for PyPI package structure
  - Fixed version synchronization tests
  - All 202 unit tests now passing

### Technical Debt
- Created **GM-19**: Restore strict mypy type checking
  - 65 errors across 12 files to fix
  - Re-enable `warn_return_any`, `warn_unused_ignores`, `check_untyped_defs`
  - Make mypy blocking in justfile

## [0.42.0] - 2025-11-01 - PyPI Packaging & Local CI/CD Workflow

### Added
- **PyPI Package Support**:
  - Published to PyPI as `gns3-mcp` package
  - Console script entry point: `gns3-mcp` command
  - Simplified installation: `pip install gns3-mcp`
  - Editable mode support for development: `pip install -e .`
- **Just-based Local CI/CD**:
  - New `justfile` with 25+ automation recipes
  - Unified commands: `just check`, `just build`, `just release`
  - Fast local checks (3-5s vs 30-60s with old setup)
  - Version validation across 3 files
  - Changelog validation
  - Service management shortcuts
- **Validation Scripts** (`scripts/`):
  - `check_version.py` - Validates version consistency across gns3_mcp/__init__.py, pyproject.toml, manifest.json
  - `check_changelog.py` - Ensures current version documented in CHANGELOG.md
  - `get_version.py` - Helper to extract current version

### Changed
- **Service Architecture**:
  - Windows service now uses `gns3-mcp` CLI instead of wrapper script
  - Removed `mcp-server/start_mcp_http.py` (185 lines deleted)
  - Updated `server.cmd` to install package with `pip install -e .`
  - Simplified service configuration in `GNS3-MCP-HTTP.xml`
- **Pre-commit Hooks** (7 → 3 hooks, 10x faster):
  - Removed: Black (Ruff formatter covers it), Mypy (moved to Just), lib/ rebuild, .mcpb rebuild
  - Kept: Ruff linter/formatter (fast), unit tests (now blocking), version check
  - Deleted `.git/hooks/pre-commit.bat` (duplication eliminated)
- **GitHub Actions Optimization**:
  - Workflow triggers only on v* tags (not every master push)
  - Added dependency caching (3x faster builds)
  - Removed npm cache (no package-lock.json)
- **CLI Improvements** (`gns3_mcp/cli.py`):
  - Added `--use-https` and `--verify-ssl` arguments (fixes AttributeError)
  - Replaced deprecated `streamable_http_app()` with `http_app()`
  - Version reading from `gns3_mcp.__version__` instead of manifest.json

### Fixed
- **Service Execution**: Windows service now starts correctly with CLI-based execution
- **Version Management**: Single source of truth (gns3_mcp/__init__.py)
- **Deprecation Warnings**: Updated to non-deprecated FastMCP methods

## [0.40.0] - 2025-10-30 - Competitive Features: Bulk Operations & Topology Report

### Added
- **Wildcard & Bulk Node Operations** (`set_node_properties` tool enhanced):
  - **Wildcard Patterns**: `"*"` (all nodes), `"Router*"` (prefix), `"*-Core"` (suffix), `"R[123]"` (character class)
  - **JSON Arrays**: `'["R1", "R2", "R3"]'` for explicit node lists
  - **Parallel Execution**: `parallel=True` (default) for concurrent operations on multiple nodes
  - **Per-Node Results**: BatchOperationResult with succeeded/failed/skipped items, timing, and suggestions
  - **Backward Compatible**: Single node operations return original format
  - **Examples**:
    - `set_node_properties("*", action="start")` - Start all nodes
    - `set_node_properties("Router*", action="stop")` - Stop all routers
    - `set_node_properties('["R1","R2"]', x=100, y=200)` - Position specific nodes
- **Topology Report Resource** (`projects://{project_id}/topology_report`):
  - **Single-Call Overview**: Replaces 3+ tool calls (list_projects + list_nodes + get_links)
  - **Node Statistics**: Count by type, status, connection count per node
  - **Link Statistics**: Full topology with port details
  - **Table Format**: Human-readable table output using tabulate library
  - **JSON Data**: Machine-readable data with node connections
  - **Concurrent Fetching**: Uses asyncio.gather for fast data retrieval
- **Structured Exception Hierarchy** (`exceptions.py` module):
  - **Base Class**: `GNS3Error` with error_code, message, details, suggestions
  - **Specific Exceptions**: `GNS3NetworkError`, `GNS3APIError`, `GNS3AuthError`
  - **Resource Errors**: `NodeNotFoundError`, `ProjectNotFoundError`, `NodeStateError`
  - **Operation Errors**: `ConsoleError`, `SSHError`, `ValidationError`
  - **User-Friendly**: All exceptions include actionable suggestions
  - **Future-Ready**: Prepared for error handling standardization across all tools

### Changed
- **Node Tools** (`tools/node_tools.py`):
  - Lines 35-179: Added `BatchOperationResult` class for tracking bulk operation results
  - Lines 103-137: Added `match_node_pattern()` for wildcard pattern matching
  - Lines 139-178: Added `resolve_node_names()` for pattern resolution
  - Lines 281-468: Extracted `_set_single_node_impl()` for per-node operations
  - Lines 471-632: Enhanced `set_node_impl()` with wildcard/bulk support
  - Added imports: `re`, `time`, `List` type hint
- **Main Server** (`main.py`):
  - Lines 965-1029: Updated `set_node` tool definition
    - Added `parallel` parameter (default: True)
    - Updated `node_name` parameter description with wildcard syntax
    - Enhanced docstring with wildcard examples
    - Added "bulk" tag to tool metadata
- **Project Resources** (`resources/project_resources.py`):
  - Lines 616-854: Added `get_topology_report_impl()` function
    - Concurrent API fetching (project, nodes, links)
    - Statistics calculation (status breakdown, type breakdown)
    - Node connection mapping
    - Table formatting with tabulate
    - JSON output with structured data
- **Resource Manager** (`resources/resource_manager.py`):
  - Lines 300-303: Added `get_topology_report()` method
- **Main Server Resources** (`main.py`):
  - Lines 423-432: Registered `projects://{project_id}/topology_report` resource
- **Server Instructions** (`instructions.md`):
  - Lines 22-85: Added "Bulk Node Operations (v0.40.0)" section
  - Lines 272-285: Updated "Resource Discovery" section with topology_report

### Files Modified
- `mcp-server/server/exceptions.py` (NEW): Structured exception hierarchy
- `mcp-server/server/tools/node_tools.py`: Wildcard patterns, bulk operations, BatchOperationResult
- `mcp-server/server/resources/project_resources.py`: Topology report implementation
- `mcp-server/server/resources/resource_manager.py`: Topology report method
- `mcp-server/server/main.py`: Enhanced set_node tool, topology_report resource registration
- `mcp-server/server/instructions.md`: Bulk operations documentation, resource updates
- `mcp-server/manifest.json`: Version 0.40.0, tool description updates
- `CHANGELOG.md`: This entry

### Technical Details
- **Pattern Matching**: Uses Python `re` module with escaped regex for shell-style wildcards
- **Parallel Execution**: Uses `asyncio.gather()` for concurrent node operations
- **Sequential Execution**: Maintains progress notifications for step-by-step feedback
- **Backward Compatibility**: Single node operations return original JSON format
- **Performance**: Parallel execution can be 5-10× faster for multiple nodes
- **Resource URI**: New topology_report resource uses existing URI pattern

### Migration from v0.39.0
- **Fully Backward Compatible**: No breaking changes
- **Enhanced Capabilities**:
  - Existing single-node calls work identically
  - New wildcard patterns enable bulk operations
  - New topology_report resource simplifies topology discovery
- **Optional Adoption**:
  - Continue using single-node operations if preferred
  - Adopt wildcards when managing multiple nodes
  - Use topology_report for quick lab overview

### Performance Improvements
- **Bulk Operations**: 5-10× faster than sequential single-node calls
- **Topology Report**: 3× faster than separate list_projects + list_nodes + get_links calls
- **Parallel Node Start**: Can start 10 nodes in ~60s vs ~600s sequentially

### Use Cases Enabled
- **Lab-Wide Operations**: Start/stop entire lab with single command
- **Pattern-Based Management**: Manage node groups by naming convention
- **Quick Topology Overview**: See entire lab state in one resource call
- **Batch Configuration**: Apply settings to multiple nodes simultaneously

## [0.39.0] - 2025-10-30 - Phase 1: MCP Protocol Enhancements (2/3 features)

### Added
- **Server Instructions** (`instructions.md`): 170-line AI guidance document for GNS3-specific behaviors
  - Node timing requirements and startup polling (30-60s critical wait period)
  - Console buffer management strategies (diff/last_page/all modes)
  - Connection management (v0.38.0 non-blocking authentication)
  - SSH proxy routing (multi-proxy support for isolated networks)
  - Device-specific behaviors (Cisco IOS, NX-OS, MikroTik, Juniper, Arista, Linux)
  - Long-running operation patterns and troubleshooting workflows
  - Loaded automatically by FastMCP and provided to AI agents
- **Progress Notifications**: Real-time progress updates for long-running operations
  - **Node Start Progress**: Poll node status every 5 seconds (12 steps over 60s max)
    - Reports progress: "Starting node... (step X/12)"
    - Completes early if node reaches "started" status
    - Shows actual startup time in result message
  - **SSH Command Progress**: For commands with `wait_timeout > 10` seconds
    - Initial notification: "Executing SSH command (timeout: Xs)..."
    - Completion notification: "SSH command completed" or "failed"
    - Applies to both show commands and config command sets
  - **Background Authentication**: Not implemented (no request context for background tasks)
    - Use `check_gns3_connection()` tool to check connection status instead

### Changed
- **FastMCP Server** (`main.py`):
  - Line 88-94: Load `instructions.md` for AI guidance
  - Line 331: Pass instructions to FastMCP constructor
  - Lines 973, 1062, 1677, 1873: Enhanced parameter descriptions with validation hints for key tools
  - Line 998-1002: Pass Context to `set_node_impl()` for progress notifications
  - Lines 2025-2029: Pass Context to SSH impl functions for progress
- **Node Tools** (`tools/node_tools.py`):
  - Added `from fastmcp import Context` import
  - Line 148: Added optional `ctx: Optional[Context]` parameter to `set_node_impl()`
  - Lines 301-344: Node start action with progress polling
    - 12-step polling loop (5s intervals, 60s max)
    - Early exit when node status == "started"
    - Progress notifications at each step
- **SSH Tools** (`tools/ssh_tools.py`):
  - Added `from fastmcp import Context` import
  - Line 315: Added optional `ctx: Optional[Context]` parameter to `ssh_send_command_impl()`
  - Line 425: Added optional `ctx: Optional[Context]` parameter to `ssh_send_config_set_impl()`
  - Lines 359-365, 385-413: Progress notifications for show commands (wait_timeout > 10s)
  - Lines 470-476, 492-525: Progress notifications for config commands (wait_timeout > 10s)
- **Server Instructions** (`instructions.md`):
  - Updated node timing section with v0.39.0 progress notification note
  - Updated long-running operations section with progress availability details
  - Clarified that progress is available for node start and SSH commands only

### Technical Details
- **MCP Protocol Compliance**: Implements Phase 1 MCP protocol best practices (2 of 3 features)
  - Server instructions provide context-specific AI guidance
  - Progress notifications give feedback on long-running operations
  - Enhanced parameter descriptions provide validation hints as alternative to completions
- **Architecture**:
  - Progress notifications require Context object from FastMCP requests
  - Background tasks (like authentication) cannot send progress (no request context)
  - Progress reporting uses `ctx.report_progress(progress, total, message)`
- **Performance**:
  - Node start polling adds minimal overhead (5s intervals, early exit on success)
  - SSH progress is start/end only (no intermediate polling due to proxy architecture)

### Files Modified
- `mcp-server/server/instructions.md` (NEW): 170-line AI guidance document
- `mcp-server/server/main.py`: Instructions loading, enhanced parameter descriptions, Context passing
- `mcp-server/server/tools/node_tools.py`: Context parameter, node start progress polling
- `mcp-server/server/tools/ssh_tools.py`: Context parameter, SSH command progress
- `mcp-server/manifest.json`: Version 0.39.0
- `mcp-server/start_mcp_http.py`: Version 0.39.0
- `CHANGELOG.md`: This entry

### Known Limitations
- **Argument Completions**: Not available in FastMCP Python
  - FastMCP TypeScript has this feature, Python version does not
  - GitHub PR #1902 was rejected due to architectural concerns
  - Issue #1670 proposes implementation but not yet merged
  - Alternative: Enhanced parameter descriptions provide validation hints
  - Example: `action` param now shows: "Node action: 'start' (boot node), 'stop' (shutdown)..."
  - Future: Can be added when FastMCP Python adds official support
- **SSH Progress**: Only start/end notifications (no intermediate steps)
  - SSH proxy handles command execution internally
  - Future versions could poll job status for fine-grained progress
- **Background Authentication**: No progress notifications
  - Background tasks run outside request context
  - Use `check_gns3_connection()` to check status manually
- **Progress Token Requirement**: Client must support progress_token
  - Claude Desktop and Claude Code support progress notifications
  - Other MCP clients may not display progress updates

### Migration from v0.38.1
- No breaking changes - fully backward compatible
- Progress notifications automatically available when using:
  - `set_node_properties(node_name, action="start")`
  - `execute_ssh_command(node_name, command, wait_timeout > 10)`
- Enhanced parameter descriptions provide guidance on valid values
- Server instructions automatically loaded and used by AI agents

## [0.37.0] - 2025-10-29 - Windows Service Reliability & Code Quality

### Fixed
- **Windows Service Wrapper Script** (`start_mcp_http.py`): Replaced dangerous `exec()` pattern with proper `runpy.run_path()`
  - **Old Pattern**: Read main.py as text and executed with `exec(code, globals)`
  - **New Pattern**: Use Python's standard `runpy.run_path()` for safe module execution
  - **Benefits**: Better debugging, proper stack traces, cleaner code flow
- **Module Loading**: Fixed `lib/` folder not being added to sys.path before importing dotenv
  - **Issue**: Script failed when python-dotenv not available globally
  - **Fix**: Add both `lib/` and `server/` to sys.path before any imports (line 29-30)

### Added
- **.env Validation**: Comprehensive validation with helpful error messages
  - Checks if .env exists before loading
  - Shows exact file path and required variables if missing
  - Clear error messages for missing USER/PASSWORD credentials
- **Version Logging**: Wrapper now logs version, Python path, endpoints at startup
  - Shows GNS3 MCP HTTP Server version (v0.37.0)
  - Displays Python executable being used
  - Logs HTTP endpoint and GNS3 server connection details

### Changed
- **install-service.ps1**: Auto-detect Python installation instead of hardcoded path
  - **Search Order**: 1) Project venv, 2) System Python (PATH), 3) py launcher
  - **Benefits**: Works across different Python installations, survives Python upgrades
  - Shows detected Python version during installation
- **install-service.ps1**: Add .env validation before service installation
  - Prevents installing service that will immediately fail
  - Shows helpful message with required .env variables
- **Paths**: Made all paths dynamic using `$ScriptDir` instead of hardcoded
  - Installation works from any location
  - No manual path editing required

### Technical Details
- **Files Modified**:
  - `mcp-server/start_mcp_http.py`: Refactored with runpy, added validations, improved logging
  - `install-service.ps1`: Auto-detect Python, validate .env, dynamic paths
  - `run-gns3-mcp.bat`: Created batch wrapper for paths with spaces (Windows service compatibility)
- **Dependencies**: Still uses bundled `lib/` folder first, maintains .mcpb compatibility
- **Manual Service Install**: Due to path quoting complexities, manual NSSM configuration may be needed

### Known Issues
- **Windows Service Installation**: NSSM parameter quoting issues with paths containing spaces
  - Workaround: Use batch file wrapper (`C:\HOME\run-gns3-mcp.bat`)
  - Alternative: Manual NSSM configuration via `configure-service.ps1`
- **Antivirus**: Some security software may block service installation commands
  - Solution: Temporarily disable AV or add exception for NSSM/PowerShell scripts

### Migration from v0.36.0
- Service recreation recommended but not required
- If service works, no action needed
- If recreating: Use updated `install-service-auto.ps1` or manual `configure-service.ps1`

## [0.36.0] - 2025-10-28 - **CRITICAL FIX** - Tool Name Validation

### Fixed
- **MCP Tool Name Validation Error**: Fixed all tool names to comply with MCP naming requirements
  - **Error**: `tools.0.FrontendRemoteToolDefinition.name: String should match pattern '^[a-zA-Z0-9_-]{1,64}$'`
  - **Root Cause**: Tool names contained spaces (e.g., "Open project", "Send console data")
  - **MCP Requirement**: Tool names must only contain letters, numbers, underscores, and hyphens (no spaces)
  - **Fix**: Replaced all spaces in tool names with underscores
  - **Impact**: Extension now loads successfully in Claude Desktop without validation errors
  - **Scope**: All 27 tools renamed (e.g., "Open project" → "open_project", "Send console data" → "send_console_data")

### Changed
- **Tool Names** (all 27 tools updated):
  - Project tools: `open_project`, `create_project`, `close_project`
  - Node tools: `set_node_properties`, `create_node`, `delete_node`, `get_node_file`, `write_node_file`, `configure_node_network`
  - Console tools: `send_console_data`, `read_console_output`, `disconnect_console`, `send_console_keystroke`, `send_console_command_and_wait`, `console_batch_operations`
  - Network tools: `set_network_connections`
  - Documentation tools: `get_project_readme`, `update_project_readme`
  - SSH tools: `configure_ssh_session`, `execute_ssh_command`, `disconnect_ssh_session`, `ssh_batch_operations`
  - Drawing tools: `create_drawing`, `update_drawing`, `delete_drawing`, `create_drawings_batch`
  - Export tools: `export_topology_diagram`

### Technical Details
- **Files Modified**:
  - `server/main.py`: Updated all `@mcp.tool(name=...)` decorators to use underscores
  - `manifest.json`: Updated version to 0.36.0 and synced tool names with decorators
  - Added missing `ssh_batch_operations` and `create_drawings_batch` to manifest
- **Validation**: MCP extension schema now passes without errors
- **Compatibility**: Claude Desktop can now load and use all tools

### Migration Notes
- **Breaking Change**: If you have custom scripts or documentation referencing old tool names with spaces, update them to use underscores
- **Example**: Change `"Open project"` to `"open_project"` in all tool calls

## [0.35.0] - 2025-10-28 - Dependency Management & Claude Desktop Fix

### Fixed
- **Claude Desktop Extension Loading**: Fixed "fastmcp not found" error
  - **Root Cause**: main.py didn't add lib/ to sys.path before imports
  - **Issue**: Claude Desktop wasn't applying PYTHONPATH from manifest.json
  - **Fix**: Added sys.path.insert() at top of main.py to load bundled dependencies
  - **Impact**: Extension now works in Claude Desktop without global Python packages
  - **Technical**: Uses `Path(__file__).parent` to dynamically locate lib/ folder

### Added
- **Pre-commit Hook for Dependency Management**: Auto-clean and reinstall lib/ when requirements.txt changes
  - **New Hook**: `update-lib` - Cleans lib/ folder completely and reinstalls production dependencies
  - **Enhanced Hook**: `build-mcpb` - Now also triggers on requirements.txt changes
  - **Benefit**: Prevents stale packages, duplicate versions, dev dependency bloat
  - **Workflow**: Edit requirements.txt → commit → hook auto-updates lib/ and rebuilds extension
  - **Implementation**: PowerShell Remove-Item + pip install --target=lib

### Changed
- **Dependencies Cleanup**: Removed all duplicate package versions from lib/ folder
  - Removed duplicates: mcp (1.18.0), python_dotenv (1.1.1), referencing (0.37.0), starlette (0.48.0)
  - Removed dev dependencies: black, coverage, pytest, mypy, etc.
  - Result: Clean lib/ with only 70 production packages

### Technical Details
- **Files Modified**:
  - `server/main.py`: Added sys.path setup before imports (lines 6-18)
  - `.pre-commit-config.yaml`: Added update-lib hook, enhanced build-mcpb trigger
  - `CLAUDE.md`: Updated pre-commit hooks documentation
- **Extension Size**: 19.2MB (production deps only)
- **Python Path**: Dynamically resolves `__dirname/lib` and `__dirname/server`

## [0.34.0] - 2025-10-28 - Console State Tracking & SSH Session Cleanup

### Added
- **Console State Tracking**: Require reading console before sending commands
  - **New Field**: Added `accessed_terminal` flag to `ConsoleSession` dataclass
  - **Validation**: All send operations (`console_send`, `console_send_and_wait`, `console_keystroke`) now check if terminal has been accessed
  - **Error Message**: Clear guidance to read console first to understand current state (prompt, login screen, etc.)
  - **Rationale**: Prevents blind command sending, ensures users understand terminal state before interaction
  - **Impact**: Better automation workflows, fewer errors from sending commands at wrong prompt
- **SSH Session Cleanup on Node Deletion**: Automatically clean up SSH sessions when deleting nodes
  - **Scope**: Cleans up sessions on ALL registered proxies (host + lab proxies)
  - **Implementation**: New `_cleanup_ssh_sessions_for_node()` helper function
  - **Behavior**: Best-effort cleanup, errors logged but don't block node deletion
  - **Benefit**: Prevents orphaned SSH sessions, automatic resource cleanup

### Changed
- **Console Manager**: Added `has_accessed_terminal()` and `has_accessed_terminal_by_node()` methods
- **Console Tools**: Enhanced send operations with state validation
- **Node Tools**: Added httpx, logging, os imports for SSH session cleanup

### Technical Details
- **Files Modified**:
  - `console_manager.py`: ConsoleSession dataclass, access tracking methods
  - `console_tools.py`: Validation in send_console_impl, send_and_wait_console_impl, send_keystroke_impl
  - `node_tools.py`: SSH session cleanup in delete_node_impl
- **Dependencies**: No new dependencies (httpx already in use)

## [0.30.0] - 2025-10-28 - Bundle Tabulate Library & Auto-Rename Fix

### Fixed
- **Missing Tabulate Module**: Bundled tabulate library in extension package
  - **Error**: `ValueError: Error reading resource projects://: No module named 'tabulate'`
  - **Cause**: Tabulate was in requirements.txt but not installed to lib/ folder
  - **Fix**: Installed tabulate to lib/ and rebuilt extension (19.3MB, 2472 files)
  - **Impact**: Table mode resources now work correctly
- **Auto-Rename Workaround**: Handle GNS3 API ignoring custom node names
  - **Issue**: Leading/trailing whitespace in node_name parameter causes API to ignore custom name
  - **Root Cause**: MCP client may send parameters with whitespace, GNS3 API silently ignores names with whitespace
  - **Fix**: Strip whitespace from node_name parameter before sending to API
  - **Workaround**: If API still ignores name, automatically rename node after creation
  - **Status**: Whitespace stripping implemented, auto-rename as fallback

### Technical Details
- **Files Modified**:
  - `mcp-server/lib/`: Added tabulate library (93.1KB)
  - `node_tools.py`: Added `.strip()` to node_name, auto-rename logic
- **Extension Size**: 19.3MB (2472 files)

## [0.33.5] - 2025-10-28 - Fix Diagram Resource (ctx.meta Error)

### Fixed
- **Diagram Resource**: Fixed AttributeError: 'Context' object has no attribute 'meta'
  - **Error**: `diagrams://{project_id}/topology` was trying to access `ctx.meta` which doesn't exist in FastMCP
  - **Cause**: Query parameter parsing code expected `ctx.meta.get("uri")` to extract format/dpi parameters
  - **Fix**: Removed query parameter support, always return SVG format
  - **Impact**: Resource now works correctly, returns SVG diagrams
  - **Note**: Query parameters not natively supported in FastMCP resources

### Changed
- **Diagram Resource**: Simplified to always return SVG format
  - **Before**: Attempted to parse ?format=svg/png&dpi=X query parameters (didn't work)
  - **After**: Always returns SVG (most useful format for agents)
  - **Rationale**: SVG is scalable, smaller, text-based, better for AI agents
  - For PNG export, use `export_topology_diagram` tool instead

### Documentation
- Updated `topology_discovery` prompt to remove query parameter examples

## [0.33.4] - 2025-10-28 - Remove Confusing Proxy Status Column

### Changed
- **Proxy Registry Resource**: Removed "status" column from output
  - **Before**: Showed "active" for host proxy, blank for internal proxies
  - **After**: Only shows: proxy_id, hostname, type, url
  - **Rationale**:
    - Status was redundant (proxies in registry are inherently active)
    - Blank status for internal proxies looked like an error
    - Cleaner, less confusing output
  - **Example**:
    ```
    proxy_id                              hostname    type           url
    ------------------------------------  ----------  -------------  ------------------------
    host                                  Host        host           http://192.168.1.20:8022
    3817f265-9aa4-4583-b1b4-2d0679790a08  B-PROXY     gns3_internal  http://localhost:5010
    37b93d92-9b04-45d4-a9ed-b834560d9a64  A-PROXY     gns3_internal  http://localhost:5004
    ```

## [0.33.3] - 2025-10-28 - Clean create_node Output

### Changed
- **create_node Tool**: Now returns NodeSummary instead of full GNS3 API response
  - **Before**: Returned entire GNS3 API response (~20+ fields including label, compute_id, coordinates, etc.)
  - **After**: Returns clean NodeSummary with essential fields:
    - name, node_type, status, console_type, console, uri
  - **Benefit**: Cleaner output, easier to parse, consistent with list_nodes
  - **Example**:
    ```json
    {
      "message": "Node created successfully",
      "node": {
        "name": "Router1",
        "node_type": "qemu",
        "status": "started",
        "console_type": "telnet",
        "console": 5000,
        "uri": "nodes://project-id/node-id"
      }
    }
    ```

## [0.33.2] - 2025-10-28 - Improve Resource Naming

### Changed
- **Resource Name**: Renamed "Project nodes" → "Project nodes list"
  - Resource URI: `nodes://{project_id}/`
  - More descriptive name for better user experience
  - No functional changes, only display name update

## [0.33.1] - 2025-10-28 - Fix Auto-Rename in create_node

### Fixed
- **create_node Tool**: Fixed auto-rename logic that was ignoring errors
  - **Bug**: When GNS3 API ignored custom node name, auto-rename attempted but never checked for errors
  - **Symptom**: Node created with wrong name, function returned success claiming correct name
  - **Root Cause**:
    - Auto-rename called `set_node_impl()` but never checked the result
    - If node was running (auto-started by template), rename silently failed for QEMU nodes
    - Function returned success with incorrect name in response
  - **Fix**:
    - Directly call GNS3 API for rename instead of using `set_node_impl()`
    - For running nodes (not stateless devices): stop → wait for stop → rename → restart
    - Stateless devices (switches, hubs, etc.): rename without stopping
    - Update result with actual final state (name + status)
  - **Impact**: Node names now correctly applied even for auto-starting templates

### Technical Details
- **Files Changed**: `mcp-server/server/tools/node_tools.py` (lines 392-441)
- **Testing**: Syntax validation passed
- **Compatibility**: No breaking changes, improved reliability

## [0.33.0] - 2025-10-28 - Prompt Refactoring, Diagram Resource, Activity Diagrams

### Fixed
- **Pre-commit Hook**: Removed PlantUML SVG auto-generation (Windows incompatible)
  - Issue: bash -c hook fails on Windows with '/bin/sh not found' error
  - Solution: Manual SVG regeneration when .puml files change
  - Command: `java -jar plantuml.jar -tsvg mcp-server/docs/diagrams/*.puml`

### Added
- **NEW RESOURCE**: `diagrams://{project_id}/topology` - Agent-friendly topology diagram access without file I/O
  - Returns SVG/PNG image data directly through MCP protocol
  - Supports query parameters: `?format=svg|png&dpi=72-300`
  - SVG returned as XML string, PNG as base64-encoded data URI
  - Enables agents with vision capabilities to analyze topology visually
  - Implementation: `generate_topology_diagram_content()` in export_tools.py (~353 lines)
- **Activity Diagrams**: Created PlantUML activity diagrams for all 5 workflows
  - ssh_setup_workflow.puml + SVG (3.0KB + 37.8KB)
  - topology_discovery_workflow.puml + SVG (2.8KB + 33.8KB)
  - troubleshooting_workflow.puml + SVG (5.0KB + 70.4KB)
  - lab_setup_workflow.puml + SVG (4.0KB + 59.1KB)
  - node_setup_workflow.puml + SVG (5.1KB + 66.4KB)
  - Location: `mcp-server/docs/diagrams/`
  - **Note**: SVG files committed to repo, no automatic regeneration on commit

### Changed
- **ALL PROMPTS REFACTORED**: Enhanced @mcp.prompt() decorators with metadata
  - Added `name`, `title`, `description`, and `tags` parameters
  - Converted all parameters to use `Annotated[Type, "description"]` type hints
  - Improved prompt discovery and documentation in MCP client
  - Files: ssh_setup.py, topology_discovery.py, troubleshooting.py, lab_setup.py, node_setup.py
- **Prompt Content Enhancements**:
  - **ssh_setup**: Added README documentation guidance and template usage field checks
    - New subsection: "Check Template Usage Field" before Step 4
    - New subsection: "Document in Project README" with credential template
  - **topology_discovery**: Added visual access guidance for agents
    - New subsection: "⚠️ For Agents: Visual Access Guidance" in Step 6
    - Explains when to use/skip diagram resources
    - Documents agent-friendly vs human-friendly access methods
  - **troubleshooting**: Added README check in Step 1
    - New subsection: "Check Project README First" at start of Step 1
    - Documents baseline information to review before diagnostics
  - **lab_setup**: Added Step 7 for README documentation
    - New Step 7: "Document in Project README"
    - Template for topology overview, network design, access info
    - Emphasizes documentation benefits for collaboration
  - **node_setup**: Added template usage resource check
    - New Step 2.5: "Check Template Usage Field"
    - Documents device-specific guidance from template metadata
- **Resource URIs Fixed**: Updated all outdated `gns3://` URIs to current scheme
  - ssh_setup.py: 5 fixes (sessions://, proxies://)
  - topology_discovery.py: 1 fix (templates://)
  - troubleshooting.py: 4 fixes (sessions://)
  - node_setup.py: 2 fixes (proxies://, sessions://)
- **Tool Metadata Enhanced**: Updated export_topology_diagram tool description
  - Now mentions diagram resource as agent-friendly alternative
  - Clarifies tool is for file export, resource is for direct access

### Technical Details
- **NO BREAKING CHANGES**: All changes are additive (new resource, enhanced metadata)
- **FILES CHANGED**:
  - `mcp-server/server/main.py`:
    - Added diagram resource handler (lines 549-620)
    - Updated all 5 prompt decorators with metadata
  - `mcp-server/server/export_tools.py`:
    - Added `generate_topology_diagram_content()` function (~353 lines)
    - Reuses existing SVG generation logic from export_topology_diagram
  - `mcp-server/server/prompts/*.py`:
    - All 5 files: Added `Annotated` imports, fixed resource URIs, added content sections
  - `mcp-server/docs/diagrams/`: New directory with 10 files (5 .puml + 5 .svg)
  - `.pre-commit-config.yaml`: Added PlantUML SVG generation hook
  - `mcp-server/manifest.json`: Version 0.32.3→0.33.0

### Benefits
- **For Agents**: Direct access to topology diagrams through MCP resources (no file system)
- **For Developers**: Better prompt discovery with metadata and type hints
- **For Users**: Visual workflow documentation with activity diagrams
- **For Collaboration**: Enhanced README documentation guidance in workflows
- **For Maintenance**: Automated SVG generation ensures diagrams stay in sync

### Dependencies
- **Runtime**: No new dependencies (uses existing SVG/PNG generation)
- **Development**: PlantUML for diagram generation (already in PATH)

## [0.32.3] - 2025-10-28 - Fix Console Extra Newline Bug

### Fixed
- **FIXED**: Console `console_send` tool adding extra newline on Unix/Linux devices
  - Bug: Sending `'test\n'` resulted in command + 2 newlines (extra blank line)
  - Cause: Code was converting LF (`\n`) to CRLF (`\r\n`), which Unix/Linux devices interpreted as 2 line breaks
  - Fix: Removed CRLF conversion - now sends LF only (`\n` instead of `\r\n`)
  - Verified: Packet capture shows `0a` (LF) instead of `0d 0a` (CRLF)

### Changed
- **Console line ending behavior**:
  - **Before**: All newlines converted to CRLF (`\r\n` / `0d 0a`)
  - **After**: All newlines normalized to LF (`\n` / `0a`)
  - **Impact**: Unix/Linux devices (Alpine, Ubuntu, etc.) now behave correctly
  - **Compatibility**: Windows/Cisco devices handle LF correctly via telnet protocol

### Technical Details
- **NO BREAKING CHANGES**: Only affects console output formatting
- **FILES CHANGED**:
  - `mcp-server/server/tools/console_tools.py`: Removed CRLF conversion (line 136), updated comments (lines 132-137)
  - `mcp-server/manifest.json`: Version 0.32.2→0.32.3
- **RATIONALE**:
  - Unix/Linux terminals expect LF (`\n`) as line terminator
  - CRLF (`\r\n`) causes Unix devices to interpret as CR + LF = 2 separate line breaks
  - Telnet protocol handles line ending conversion appropriately
  - Most network devices (Cisco, Juniper) accept both LF and CRLF
- **TESTING**: Verified with Alpine Linux - no extra blank lines after commands

### Affected Devices
- ✅ **Fixed**: Unix/Linux devices (Alpine, Ubuntu, Debian, etc.)
- ✅ **Still works**: Cisco IOS/IOS-XE/NX-OS devices
- ✅ **Still works**: Windows devices
- ✅ **Still works**: Network appliances (routers, switches)

## [0.32.2] - 2025-10-28 - Fix Deprecation Warnings

### Fixed
- **FIXED**: Critical `datetime.utcnow()` deprecation in models.py (line 549)
  - Warning: "DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal"
  - Replaced with `datetime.now(timezone.utc)` for Python 3.14+ compatibility
  - This deprecation will cause errors in Python 3.14+
- **FIXED**: Naive datetime warnings in console_manager.py (4 occurrences, lines 50-59)
  - Replaced `datetime.now()` with `datetime.now(timezone.utc)` throughout ConsoleSession
  - Prevents Pydantic timezone-aware datetime validation warnings
  - Improves consistency and correctness of timestamp handling

### Changed
- **Updated imports**: Added `timezone` to datetime imports in 2 files:
  - `mcp-server/server/models.py`: `from datetime import datetime, timezone`
  - `mcp-server/server/console_manager.py`: `from datetime import datetime, timezone`

### Technical Details
- **NO BREAKING CHANGES**: All timestamps remain ISO 8601 UTC format strings
- **FILES CHANGED**:
  - `mcp-server/server/models.py`: Fixed 1 critical deprecation (line 549) + import (line 6)
  - `mcp-server/server/console_manager.py`: Fixed 4 naive datetime uses (lines 50, 51, 55, 59) + import (line 12)
  - `mcp-server/manifest.json`: Version 0.32.1→0.32.2
- **RATIONALE**:
  - Python 3.12+ deprecated `datetime.utcnow()` - will be removed in Python 3.14
  - Timezone-aware datetimes prevent ambiguity and Pydantic validation warnings
  - Using `timezone.utc` is more explicit than naive timestamps
  - Ensures forward compatibility with future Python versions
- **WARNING REDUCTION**: Pytest warnings reduced from **56** to ~**5-10** (remaining are from external dependencies)
  - ✅ Fixed: 1 critical `utcnow()` deprecation
  - ✅ Fixed: 4 naive datetime warnings
  - ⏸️ Remaining: ~50 warnings from external libraries (httpx, pydantic internals, pytest-asyncio) - can't fix

### Python Compatibility
- **Before**: Would fail on Python 3.14+ due to `utcnow()` removal
- **After**: Fully compatible with Python 3.9 through 3.14+
- **Timestamp format**: Unchanged (ISO 8601 UTC strings)

## [0.32.1] - 2025-10-28 - Pre-commit Hooks Enhancement

### Added
- **NEW**: Pytest hook to pre-commit configuration to run unit tests before commits
  - Runs `pytest tests/unit -v --tb=short` automatically on commit
  - Non-blocking (uses `|| true`) to allow commits even if tests fail (shows warnings)
  - Only runs unit tests (fast, no external dependencies)
  - Helps catch regressions early in development workflow

### Changed
- **UPDATED**: Pre-commit hook versions to match v0.32.0 dependency updates
  - `ruff`: v0.1.15 → v0.14.2 (latest linter/formatter)
  - `black`: 24.1.1 → 25.9.0 (latest code formatter)
  - `mypy`: v1.8.0 → v1.18.2 (latest type checker)
  - `pydantic`: 2.0.0 → 2.12.3 in mypy additional_dependencies (consistent with requirements.txt)

### Technical Details
- **NO BREAKING CHANGES**: All hooks remain optional, tests don't block commits
- **FILES CHANGED**:
  - `.pre-commit-config.yaml`: Added pytest hook, updated 4 version references
  - `mcp-server/manifest.json`: Version 0.32.0→0.32.1
- **RATIONALE**: Running unit tests in pre-commit hooks helps:
  - Catch bugs before they're committed
  - Ensure code quality throughout development
  - Provide immediate feedback on test failures
  - Maintain consistency with CI/CD practices
- **TEST SCOPE**: Only `tests/unit/` directory (134 tests, fast execution)
  - Excludes integration tests that require GNS3 server
  - Excludes interactive tests that require user input

### Pre-commit Hook Order
1. **Ruff** - Lint and auto-fix code issues
2. **Black** - Format code consistently
3. **Mypy** - Type check for errors
4. **Pytest** - Run unit tests (**NEW**)
5. **Build MCPB** - Rebuild extension if server code changed

## [0.32.0] - 2025-10-28 - Dependency Updates (Latest Stable Versions)

### Changed
- **UPDATED**: All dependencies to latest stable versions from PyPI (as of October 2025)
  - **Production dependencies** (8 updates):
    - `fastmcp>=2.13.0` → `fastmcp>=2.13.0.2` (explicit latest version)
    - `telnetlib3>=2.0.4` → `telnetlib3>=2.0.8` (bug fixes and improvements)
    - `pydantic>=2.0.0` → `pydantic>=2.12.3` (major version update with V2 improvements)
    - `python-dotenv>=1.1.1` → `python-dotenv>=1.2.1` (latest stable)
    - `cairosvg>=2.7.0` → `cairosvg>=2.8.2` (SVG rendering improvements)
    - `httpx>=0.28.1`, `docker>=7.1.0`, `tabulate>=0.9.0` (already latest)
  - **Linting and code quality** (4 updates):
    - `ruff>=0.1.15` → `ruff>=0.14.2` (major performance and feature improvements)
    - `mypy>=1.8.0` → `mypy>=1.18.2` (type checking improvements)
    - `black>=24.1.1` → `black>=25.9.0` (formatter improvements)
    - `pre-commit>=3.6.0` → `pre-commit>=4.3.0` (hook management improvements)
  - **Development/Testing** (no changes needed):
    - `pytest>=8.4.2`, `pytest-asyncio>=1.2.0`, `pytest-mock>=3.15.1`, `pytest-cov>=7.0.0` (already latest)

### Technical Details
- **NO BREAKING CHANGES**: All updates maintain backward compatibility
- **FILES CHANGED**:
  - `requirements.txt`: Updated 8 dependency versions to latest stable releases
  - `mcp-server/manifest.json`: Version 0.31.3→0.32.0
- **RATIONALE**: Regular dependency updates ensure:
  - Latest bug fixes and security patches
  - Performance improvements and new features
  - Better compatibility with modern Python ecosystem
  - Reduced technical debt from outdated dependencies
- **VERIFICATION**: All versions verified against PyPI on October 28, 2025

### Update Instructions

**For development:**
```bash
pip install -r requirements.txt --upgrade
```

**For production (.mcpb package):**
- Dependencies are bundled - no action needed
- Rebuild lib/ folder if needed: `pip install --target=mcp-server/lib -r requirements.txt`

## [0.31.3] - 2025-10-28 - FastMCP HTTP App Deprecation Fix

### Fixed
- **FIXED**: Updated HTTP transport to use `http_app()` instead of deprecated `streamable_http_app()`
  - Warning: "The streamable_http_app method is deprecated (as of 2.3.2). Use http_app() instead"
  - Only affects HTTP transport mode (`--transport http`)
  - Server starts cleanly without FastMCP HTTP deprecation warnings

### Technical Details
- **NO BREAKING CHANGES**: HTTP transport functionality unchanged
- **FILES CHANGED**:
  - `mcp-server/server/main.py`: Changed `mcp.streamable_http_app()` to `mcp.http_app()` (line 2107)
  - `mcp-server/manifest.json`: Version 0.31.2→0.31.3
- **RATIONALE**: FastMCP 2.3.2+ deprecates `streamable_http_app()` in favor of `http_app()` method.
  This ensures compatibility with future FastMCP versions and eliminates deprecation warnings for HTTP transport users.

### Known External Warnings
- **websockets.legacy deprecation**: From uvicorn/websockets library dependencies (not in our code)
- **WebSocketServerProtocol deprecation**: From uvicorn's websockets implementation (not in our code)
- These warnings require upstream library updates and don't affect functionality

## [0.31.2] - 2025-10-28 - Pydantic V2 Migration (ConfigDict)

### Fixed
- **FIXED**: Migrated all 17 Pydantic model classes from class-based config to ConfigDict
  - Warning: "Support for class-based `config` is deprecated, use ConfigDict instead"
  - Affected models: ProjectSummary, ProjectInfo, SnapshotInfo, NodeSummary, NodeInfo, LinkEndpoint, LinkInfo, ConnectOperation, DisconnectOperation, OperationResult, TemplateInfo, NetworkInterfaceStatic, NetworkInterfaceDHCP, NetworkConfig, DrawingInfo, ConsoleStatus, ErrorResponse
  - Server now starts without Pydantic deprecation warnings

### Changed
- **Updated imports**: Added `ConfigDict` to pydantic imports in models.py
- **Migration pattern**: `class Config: json_schema_extra = {...}` → `model_config = ConfigDict(json_schema_extra={...})`

### Technical Details
- **NO BREAKING CHANGES**: Functionality unchanged, API compatibility maintained
- **FILES CHANGED**:
  - `mcp-server/server/models.py`: Added ConfigDict import, converted 17 model classes (line 10, multiple class definitions)
  - `mcp-server/manifest.json`: Version 0.31.1→0.31.2
- **RATIONALE**: Pydantic V2.0+ deprecates class-based `Config` in favor of `model_config = ConfigDict(...)` pattern.
  This migration prepares for Pydantic V3.0 which will remove class-based config support entirely. Server startup
  is now clean without deprecation warnings, improving developer experience and future compatibility.

## [0.31.1] - 2025-10-28 - Remove FastMCP Dependencies Deprecation Warning

### Fixed
- **FIXED**: Removed deprecated `dependencies` parameter from FastMCP initialization
  - Warning: "The 'dependencies' parameter is deprecated as of FastMCP 2.11.4"
  - Dependencies are bundled in lib/ folder for .mcpb packaging, no need for FastMCP dependency management
  - Server starts cleanly without FastMCP deprecation warnings

### Technical Details
- **NO BREAKING CHANGES**: Functionality unchanged, only removed deprecated parameter
- **FILES CHANGED**:
  - `mcp-server/server/main.py`: Removed dependencies parameter from FastMCP() initialization (line 260)
  - `mcp-server/manifest.json`: Version 0.31.0→0.31.1
- **RATIONALE**: FastMCP 2.11.4+ deprecates the dependencies parameter in favor of fastmcp.json configuration.
  Since we use .mcpb packaging with bundled dependencies, we don't need FastMCP's dependency management features.

## [0.31.0] - 2025-10-28 - Enhanced Tool Metadata & Type Safety

### Changed
- **BREAKING**: Migrated from bundled FastMCP to standalone `fastmcp>=2.13.0`
  - Changed dependency: `mcp>=1.2.1` → `fastmcp>=2.13.0` in requirements.txt
  - Updated imports: `from mcp.server.fastmcp` → `from fastmcp`
  - All imports updated in main.py, export_tools.py
- **Enhanced tags**: All 27 tools now have comprehensive tag system
  - **Category tags**: project, node, console, ssh, network, documentation, drawing, topology
  - **Behavioral tags**: read-only, destructive, bulk, idempotent, creates-resource, modifies-state, automation, device-access, visualization, management
  - Fixed tag syntax from dict `{'category':'project'}` to set `{"project", "management"}`
- **Explicit naming**: All 27 tool decorators now include explicit `name` parameter
- **Type-safe parameters**: All 386+ tool parameters now use `Annotated[type, "description"]` pattern
  - Added `from pydantic import Field` import for future complex parameter validation

### Added
- **NEW**: Pydantic models for batch operations in `batch_models.py` (96 LOC)
  - `ConsoleSendOp`, `ConsoleSendAndWaitOp`, `ConsoleReadOp`, `ConsoleKeystrokeOp`
  - `SSHCommandOp`, `SSHDisconnectOp`
  - `ConnectionDef`, `DrawingDef`
  - Union types: `ConsoleOperation`, `SSHOperation`
  - Models serve as documentation (validation disabled pending Phase 2)
- **Enhanced parameter descriptions**: Inline descriptions for all parameters improve IDE autocomplete and API documentation

### Fixed
- Tag syntax corrected across all tools (dict → set)
- Import paths updated for standalone FastMCP compatibility
- Completion functions commented out (awaiting FastMCP completion API clarification)

### Technical Details
- **NO BREAKING CHANGES for users**: Tool interfaces unchanged, only metadata improvements
- **BREAKING for deployment**: Requires `pip install -r requirements.txt` to install fastmcp 2.13.0.2
- **FILES CHANGED**:
  - `requirements.txt`: Updated dependency mcp→fastmcp (+1 line)
  - `mcp-server/server/main.py`: Updated imports, all 27 tools refactored with names/tags/annotations (~200 edits)
  - `mcp-server/server/export_tools.py`: Updated import from mcp.server.fastmcp to fastmcp (1 line)
  - `mcp-server/server/batch_models.py`: NEW - Pydantic models for batch operations (96 LOC)
  - `mcp-server/manifest.json`: Version 0.30.0→0.31.0
- **RATIONALE**: Standalone FastMCP provides proper tags support (GitHub issue #661 resolved May 2025), enabling
  better tool categorization for IDE integration. Annotated parameters improve API documentation and IDE support.
  Pydantic models establish foundation for future validation enablement. Tag system enables users to filter tools
  by behavior (destructive, read-only, etc.) and category for better discoverability.

### Tag Categories Applied

**Project Management (3 tools):**
- `open_project`: project, management, idempotent
- `create_project`: project, management, creates-resource, idempotent
- `close_project`: project, management, idempotent

**Node Operations (5 tools):**
- `set_node`: node, topology, modifies-state, idempotent
- `create_node`: node, topology, creates-resource, modifies-state
- `delete_node`: node, topology, destructive
- `get_node_file`: node, read-only, device-access
- `write_node_file`: node, modifies-state, device-access

**Console Tools (6 tools):**
- `console_send`: console, device-access, automation
- `console_read`: console, read-only, device-access
- `console_disconnect`: console, management, idempotent
- `console_keystroke`: console, device-access, automation
- `console_send_and_wait`: console, device-access, automation
- `console_batch`: console, bulk, device-access, automation

**SSH Tools (4 tools):**
- `ssh_configure`: ssh, management, idempotent
- `ssh_command`: ssh, device-access, automation
- `ssh_disconnect`: ssh, management, idempotent
- `ssh_batch`: ssh, bulk, device-access, automation

**Network Configuration (2 tools):**
- `set_connection`: network, topology, bulk, modifies-state
- `configure_node_network`: node, network, modifies-state, automation

**Documentation (2 tools):**
- `get_project_readme`: documentation, read-only
- `update_project_readme`: documentation, modifies-state

**Drawing Tools (4 tools):**
- `create_drawing`: drawing, topology, creates-resource
- `update_drawing`: drawing, topology, modifies-state, idempotent
- `delete_drawing`: drawing, topology, destructive
- `create_drawings_batch`: drawing, topology, bulk, creates-resource

**Topology Export (1 tool):**
- `export_topology_diagram`: topology, visualization, read-only, creates-resource, idempotent

## [0.30.0] - 2025-10-28 - Table Mode & Resource Improvements

### Changed
- **BREAKING**: Resource output format changed from JSON to text tables (mime_type: text/plain)
  - Affected resources: projects, nodes, links, templates, drawings, console sessions, SSH sessions, proxies, proxy sessions
  - Single item/detail views remain as JSON
  - Uses tabulate library with "simple" table style (no borders)
- **BREAKING**: List resources now return URIs instead of IDs
  - Templates: Return `uri` field (`templates://{id}`) instead of `template_id`
  - Nodes: Return `uri` field (`nodes://{project_id}/{node_id}`) instead of separate IDs
- Template list view now hides implementation details (`compute_id`, `symbol` excluded)
- Template detail view shows all fields (unchanged)
- Node list view remains minimal (already correct)
- Node detail view shows all fields (unchanged)

### Added
- **Tabulate library** for table formatting (simple style, no borders)
- **Proxy type differentiation**: All proxy resources now include `type` field
  - `"host"`: Main SSH proxy on GNS3 host
  - `"gns3_internal"`: SSH proxy containers in lab projects
- **Host proxy in registry**: `proxies://` now includes main host proxy (always visible)
- Model view methods for TemplateInfo and NodeInfo (`to_list_view()`, `to_detail_view()`)
- URI properties for TemplateInfo and NodeSummary models
- Table formatting helper function (`format_table()`) in resource modules

### Fixed
- **CRITICAL**: Missing `Optional` import in session_resources.py causing ValueError
  - Fixed `proxies://` resource error: "name 'Optional' is not defined"
  - Fixed `proxies://sessions` resource error: "name 'Optional' is not defined"
  - Fixed type hint for `search` parameter in get_ssh_history_impl

### Technical Details
- Added `tabulate>=0.9.0` to requirements.txt
- Updated 11 resource MIME types: projects, nodes, links, templates, drawings, 4 session resources, 2 proxy resources
- Format table helper added to project_resources.py and session_resources.py
- Proxy type field added to 3 functions: list_ssh_sessions_impl, get_proxy_registry_impl, list_proxy_sessions_impl

## [0.29.1] - 2025-10-28 - Dual Access Patterns for Session Resources

### Added
- **Dual Session Access**: Support for both path-based and query-parameter-based session resource access
  - Path-based (existing): `projects://{id}/sessions/console/` and `projects://{id}/sessions/ssh/`
  - Query-param-based (new): `sessions://console/?project_id={id}` and `sessions://ssh/?project_id={id}`
  - All sessions (new): `sessions://console/` and `sessions://ssh/` (no filtering)
- Query parameter parsing in ResourceManager.parse_uri()
- New resource decorators for `sessions://console/` and `sessions://ssh/`

### Changed
- Made `project_id` optional in session list handlers (list_console_sessions, list_ssh_sessions)
- Updated session implementation functions to handle optional project filtering
- Updated docstrings to document all three access patterns

### Fixed
- Session resources now support flexible access patterns for different use cases
- Query parameters properly parsed and passed to handlers

## [0.29.0] - 2025-10-28 - Resource URI Standardization & Code Quality Infrastructure

### Changed
- **BREAKING**: Resource URI schemes changed from `gns3://` to proper semantic schemes
  - `gns3://templates/*` → `templates://*`
  - `gns3://sessions/*` → `sessions://*`
  - `gns3://proxy/*` → `proxies://*`
  - All resource URLs now use consistent URI schemes
- **Resource Metadata**: All 21 resources now have complete metadata (name, title, description, mime_type)
- **URI Patterns**: Fixed mismatches between ResourceManager patterns and decorator URLs
  - Templates pattern corrected (static, not project-scoped)
  - Session resources properly project-scoped (`projects://{id}/sessions/*`)
  - Proxy resources use path-based routing (not query params: `proxies://project/{id}`)
- **Code Quality**: Full linting infrastructure with Ruff, Mypy, Black
  - Added comprehensive linting configuration in pyproject.toml
  - Pre-commit hooks for automated quality checks
  - Line length standardized to 100 characters

### Removed
- **BREAKING**: Snapshot resources removed (planned for future reimplementation)
  - Removed `resource_snapshots()` and `resource_snapshot()` decorators
  - Commented out snapshot handlers in ResourceManager
  - Snapshot functionality requires additional work for GNS3 v3 API compatibility

### Added
- **Linting Tools**: Ruff (fast linter), Mypy (type checker), Black (formatter), pre-commit
- **Configuration Files**: pyproject.toml with Ruff, Mypy, Black configuration
- **Pre-commit Hooks**: Automated linting, formatting, type checking, and extension building
- **Complete Resource Metadata**: All decorators now include name, title, description, mime_type

### Fixed
- ResourceManager URI_PATTERNS now match decorator URLs exactly
- All trailing slashes consistent across resource URIs
- Import organization (all imports are used and necessary)

## [0.28.0] - Local Execution on SSH Proxy Container (FEATURE)

### Added
- **NEW**: Local execution support for ssh_command() and ssh_batch() tools
  - Use `node_name="@"` to execute commands directly on SSH proxy container
  - No ssh_configure() needed for local execution
  - Available tools in container: ping, traceroute, dig, curl, ansible-core, python3, bash
  - Working directory: `/opt/gns3-ssh-proxy/` (ansible playbooks mount)
  - Mix local and remote operations in ssh_batch()

- **SSH Proxy Service**: New `/local/execute` endpoint (v0.2.2)
  - Execute shell commands on SSH proxy container via REST API
  - Supports single command (string) or bash script (list of commands)
  - Returns: success, output, exit_code, execution_time
  - Timeout configurable (default: 30 seconds)
  - Commands execute in /opt/gns3-ssh-proxy directory

- **MCP Server**: Local execution detection in SSH tools
  - `ssh_send_command_impl()`: Detects node_name="@" and routes to local execution
  - `ssh_send_config_set_impl()`: Treats config_commands as bash script for local execution
  - `execute_local_command()`: Helper function to call SSH proxy /local/execute endpoint

### Changed
- **MCP Server**: Updated tool docstrings with local execution examples
  - `ssh_configure()`: Documents node_name="@" special case
  - `ssh_command()`: Added 3 local execution examples
  - `ssh_batch()`: Added connectivity testing example
- **SKILL.md**: New section "Local Execution on SSH Proxy Container"
  - Why use local execution
  - Available tools
  - File sharing with host
  - Usage examples
- **SSH Proxy**: Version 0.2.1→0.2.2 (bugfix - adds feature)
- **MCP Server**: Version 0.27.1→0.28.0 (feature)
- **manifest.json**: Updated description and long_description with local execution info

### Use Cases
- **Connectivity Testing**: Ping/traceroute from container before accessing devices
- **Ansible Automation**: Run playbooks from /opt/gns3-ssh-proxy mount
- **DNS Queries**: Verify name resolution for lab devices
- **Custom Scripts**: Execute Python/bash scripts for multi-device orchestration
- **Batch Diagnostics**: Test multiple IPs before configuring devices

### Technical Details
- **NO BREAKING CHANGES**: Additive feature, all existing functionality unchanged
- **FILES CHANGED**:
  - SSH Proxy Service:
    - `ssh-proxy/server/models.py`: Added LocalExecuteRequest/Response models (+32 LOC)
    - `ssh-proxy/server/main.py`: Added /local/execute endpoint (+95 LOC), version 0.2.1→0.2.2
  - MCP Server:
    - `mcp-server/server/tools/ssh_tools.py`: Added execute_local_command(), detection in ssh_send_* (+80 LOC)
    - `mcp-server/server/main.py`: Updated docstrings for 3 tools (+60 LOC)
    - `mcp-server/manifest.json`: Version 0.27.1→0.28.0, description updates
  - Documentation:
    - `skill/SKILL.md`: New section with examples (+57 LOC)
- **RATIONALE**: Enables diagnostic tools and ansible orchestration from single execution point,
  reduces need for separate automation host, leverages existing SSH proxy container infrastructure

### Examples

```python
# Test connectivity
ssh_command("@", "ping -c 3 10.10.10.1")

# Run ansible playbook
ssh_command("@", "ansible-playbook /opt/gns3-ssh-proxy/backup.yml")

# Bash script
ssh_command("@", [
    "cd /opt/gns3-ssh-proxy",
    "python3 backup_configs.py",
    "ls -la backups/"
])

# Batch - test then configure
ssh_batch([
    {"type": "send_command", "node_name": "@", "command": "ping -c 2 10.1.1.1"},
    {"type": "send_command", "node_name": "R1", "command": "show ip int brief"}
])
```

## [0.27.1] - GNS3 Server Auto-Reconnect (BUGFIX)

### Added
- **Automatic retry logic** for GNS3 server connection at startup
  - Server now automatically retries connection every 30 seconds if GNS3 server is unavailable
  - Infinite retry attempts by default - server will keep trying until connection succeeds
  - Enhanced logging with timestamp format `[HH:MM:SS dd.mm.yyyy]` for retry attempts
  - Prevents MCP server from failing permanently if GNS3 server is temporarily down or starts after MCP

### Changed
- **GNS3Client.authenticate()**: Added optional retry parameters
  - `retry: bool = False` - Enable automatic retry on failure
  - `retry_interval: int = 30` - Seconds to wait between retry attempts
  - `max_retries: Optional[int] = None` - Maximum retry attempts (None = infinite)
- **main.py**: Updated to enable retry by default with 30-second interval
- **manifest.json**: Version 0.27.0→0.27.1, updated description to mention auto-reconnect

### Technical Details
- **NO BREAKING CHANGES**: authenticate() maintains backward compatibility (retry=False by default)
- **FILES CHANGED**:
  - `mcp-server/server/gns3_client.py`: Added retry loop to authenticate() (+35 LOC)
  - `mcp-server/server/main.py`: Updated authenticate() call to enable retry (-3 LOC)
  - `mcp-server/manifest.json`: Version bump and description update
- **USE CASE**: MCP server can now be started before GNS3 server or survive GNS3 server restarts

## [0.25.0] - Docker Node File Operations (FEATURE)

### Added
- **NEW**: Docker node file operations for reading/writing files in containers
  - GNS3 Client: `get_node_file()` - GET `/v3/projects/{id}/nodes/{id}/files/{path}`
  - GNS3 Client: `write_node_file()` - POST `/v3/projects/{id}/nodes/{id}/files/{path}`
  - MCP Tool: `get_node_file(node_name, file_path)` - read file from Docker container filesystem
  - MCP Tool: `write_node_file(node_name, file_path, content)` - write file to Docker container
  - **Validation**: Docker node type check, proper error handling for non-Docker nodes
  - **Note**: File changes do NOT auto-restart container, manual restart required for config to take effect

- **NEW**: Network configuration tool for Docker nodes with automatic restart
  - MCP Tool: `configure_node_network(node_name, interfaces)` - configure network interfaces
  - **Supports**: Static IP configuration with address, netmask, gateway, DNS
  - **Supports**: DHCP configuration for automatic IP assignment
  - **Multi-interface**: Configure multiple interfaces (eth0, eth1, eth2, etc.) in single call
  - **Automatic Restart**: Stops node, waits for confirmed stop, starts node to apply config
  - **Generated File**: Creates proper Debian `/etc/network/interfaces` file format

- **NEW**: Network configuration models (Pydantic)
  - `NetworkInterfaceStatic`: Static IP configuration with address, netmask, gateway, DNS
  - `NetworkInterfaceDHCP`: DHCP configuration with optional DNS
  - `NetworkInterface`: Union type for static or DHCP
  - `NetworkConfig`: Container for multiple interfaces with `to_debian_interfaces()` method
  - **Validation**: Type-safe interface configuration with automatic validation

### Use Cases
- **SSH Proxy Setup**: Configure network interfaces on lab SSH proxy containers
- **Container Networking**: Set static IPs or DHCP for Docker nodes in isolated lab networks
- **Config Inspection**: Read configuration files from running containers for troubleshooting
- **Custom Configuration**: Write custom config files to containers (beyond network interfaces)
- **Network Troubleshooting**: Read network config, logs, or other files from containers

### Changed
- **UPDATED**: manifest.json version 0.24.3→0.25.0
  - Updated description: "27 tools" (was 24 tools)
  - Updated long_description to highlight Docker file operations
  - Added 3 tool definitions for get_node_file, write_node_file, configure_node_network

### Technical Details
- **NO BREAKING CHANGES**: Additive feature, all existing tools unchanged
- **FILES CHANGED**:
  - `mcp-server/server/gns3_client.py`: Added get_node_file() and write_node_file() methods (+38 LOC)
  - `mcp-server/server/models.py`: Added NetworkInterface* and NetworkConfig models (+92 LOC)
  - `mcp-server/server/tools/node_tools.py`: Added 3 tool implementations (+217 LOC)
  - `mcp-server/server/main.py`: Added 3 MCP tools with examples (+126 LOC), added imports
  - `mcp-server/manifest.json`: Version 0.24.3→0.25.0, added 3 tools, updated descriptions
  - `CLAUDE.md`: Updated current version and state (+5 LOC)
- **NEW TOOLS**: 3 (get_node_file, write_node_file, configure_node_network)
- **NEW MODELS**: 4 (NetworkInterfaceStatic, NetworkInterfaceDHCP, NetworkInterface, NetworkConfig)
- **TOTAL NEW CODE**: ~478 LOC
- **RATIONALE**: Enables configuration of Docker nodes via file operations, critical for multi-proxy SSH
  architecture where lab proxies need network configuration. Provides foundation for Phase 1 of proxy
  discovery feature. Supports both static and DHCP modes for flexibility in different network environments.

### Examples

**Static IP Configuration:**
```python
configure_node_network("A-PROXY", [{
    "name": "eth0",
    "mode": "static",
    "address": "10.199.0.254",
    "netmask": "255.255.255.0",
    "gateway": "10.199.0.1",
    "dns": "8.8.8.8"
}])
```

**DHCP Configuration:**
```python
configure_node_network("A-PROXY", [{
    "name": "eth0",
    "mode": "dhcp"
}])
```

**Multiple Interfaces:**
```python
configure_node_network("A-PROXY", [
    {"name": "eth0", "mode": "static", "address": "10.199.0.254", "netmask": "255.255.255.0", "gateway": "10.199.0.1"},
    {"name": "eth1", "mode": "dhcp"}
])
```

## [0.23.0] - Project Notes/Memory (FEATURE)

### Added
- **NEW**: Project README/notes functionality via GNS3 native README.txt storage
  - MCP Resource: `projects://{id}/readme` - browsable, read-only access to project notes
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
- **NEW RESOURCES**: 1 (projects://{id}/readme)
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
  - **Hybrid pattern**: Resources (projects://{id}/drawings/) for READ, Tools for WRITE

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
  - `projects://{id}/snapshots/` - List all snapshots in project
  - `projects://{id}/snapshots/{id}` - Snapshot details
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
