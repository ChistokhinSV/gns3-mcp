# GNS3 MCP Server

Model Context Protocol (MCP) server for GNS3 network lab automation. Control GNS3 projects, nodes, and device consoles through Claude Desktop or any MCP-compatible client. Includes SSH automation via Netmiko for advanced network device management.

**Current Version**: v0.38.0 (Non-Blocking Authentication)

## 📐 Architecture Documentation

Comprehensive architecture documentation is available in the [docs/architecture](docs/architecture/) directory:

- **[Architecture Overview](docs/architecture/README.md)** - Complete system architecture guide
- **[C4 Model Diagrams](docs/architecture/)** - Context, Container, Component, and Deployment diagrams
- **[Architecture Decision Records (ADRs)](docs/architecture/adr/)** - Key architectural decisions with rationale
- **[Data Flow Documentation](docs/architecture/05-tool-invocation-flow.md)** - Request/response flow through system layers

**Architecture Grade**: B+ (85/100) - Clean layered architecture with comprehensive type safety

## What's New in v0.38.0

Version 0.38.0 fixes critical startup delays and improves reliability with instant server startup:

### Instant Server Startup (3 Seconds)
- **No More Blocking**: Server starts immediately regardless of GNS3 availability (was 15-20 seconds)
- **Background Authentication**: Non-blocking auth with exponential backoff (5s → 10s → 30s → 60s → 300s max)
- **Always Available**: All 29 tools/resources available even when GNS3 disconnected
- **Fast Failure**: API operations fail quickly (6s max) with clear error messages

### 2 New Connection Management Tools
- **check_gns3_connection()** - Check connection status, error details, last attempt time
- **retry_gns3_connection()** - Force immediate reconnection (bypasses backoff timer)

### Unified Server Management (server.cmd)
Single command replaces 5+ installation scripts:
- `server.cmd` - Start server (auto-creates/populates venv)
- `server.cmd install` - Install Windows service via WinSW (auto-downloads if missing)
- `server.cmd uninstall` - Remove Windows service
- `server.cmd reinstall` - Reinstall service
- `server.cmd status` - Check service status

**WinSW Auto-Download**: The script automatically downloads WinSW from GitHub if not present. No manual installation required.

### Connection Status Tracking
- `is_connected` - Boolean connection state
- `connection_error` - Detailed error message (timeout, no route, etc.)
- `last_auth_attempt` - Timestamp of last attempt
- Auto-recovery when GNS3 becomes available

See [CLAUDE.md](CLAUDE.md) for complete v0.38.0 release notes.

## What's New in v0.12.0

Version 0.12.0 introduces SSH automation capabilities for advanced network device management:

### SSH Proxy Service
- **Separate Container**: FastAPI service on port 8022 (Python 3.13-slim)
- **Network Mode Host**: Direct access to GNS3 lab network
- **Netmiko Integration**: Support for 200+ device types (Cisco, Juniper, Arista, MikroTik, etc.)
- **Deployment**: Docker container deployed to GNS3 host via SSH

### 9 New SSH Automation Tools
- **configure_ssh()** - Establish SSH sessions to network devices
- **ssh_send_command()** - Execute show commands with adaptive async
- **ssh_send_config_set()** - Send configuration commands
- **ssh_read_buffer()** - Read continuous command output
- **ssh_get_history()** - Review command history with search
- **ssh_get_command_output()** - Get specific job output by ID
- **ssh_get_status()** - Check SSH session status
- **ssh_cleanup_sessions()** - Clean orphaned sessions
- **ssh_get_job_status()** - Poll async job completion

### Key Features
- **Dual Storage**: Continuous buffer + per-command job history
- **Adaptive Async**: Commands poll then return job_id for long operations
- **Error Detection**: Intelligent SSH error classification with helpful suggestions
- **Long Commands**: Support 15+ minute operations (firmware upgrades, backups)
- **Audit Trail**: Full command history with timestamps and execution times

See [DEPLOYMENT.md](DEPLOYMENT.md) for SSH proxy deployment instructions.

## What's New in v0.11.0

Version 0.11.0 is a major code organization refactoring with comprehensive testing:

### Code Organization
- **50% LOC Reduction**: main.py reduced from 1,836 to 914 LOC
- **Tool Extraction**: 19 tools extracted to 6 category modules (project, node, console, link, drawing, template)
- **Better Maintainability**: Clearer code organization with focused module responsibilities
- **No Breaking Changes**: All tool interfaces remain unchanged

### Testing Infrastructure
- **Console Manager Tests**: 38 unit tests achieving 76% coverage on 374 LOC critical async code
- **Test Coverage**: 134 total tests with 30%+ overall coverage focused on critical paths
- **Quality Assurance**: All existing tests pass with zero regressions

See [CLAUDE.md](CLAUDE.md) for complete v0.11.0 release notes.

## What's New in v0.6.2

Version 0.6.2 fixes label rendering in topology exports to match the official GNS3 GUI.

### Improvements

- **Fixed Label Positioning**: `export_topology_diagram()` now renders labels exactly as GNS3 GUI does
- **Auto-Centering**: Labels with x=None properly center above nodes at y=-25
- **Dynamic Text Anchor**: Text alignment (start/middle/end) automatically set based on label position
- **Accurate Rendering**: No more incorrect offset additions - uses GNS3-stored positions directly

See [CLAUDE.md - Label Rendering Implementation](CLAUDE.md#label-rendering-implementation-v062) for technical details.

## Version History

### v0.6.1 - Newline Normalization & Special Keystrokes
- Console newlines auto-converted to \r\n (CR+LF) for device compatibility
- New `send_keystroke()` tool for TUI navigation and vim editing
- Fixed `detect_console_state()` to check only last non-empty line

### v0.6.0 - Interactive Console Tools
- New `send_and_wait_console()` - wait for prompt patterns with timeout
- New `detect_console_state()` - auto-detect device type and console state
- Added DEVICE_PATTERNS library for Cisco IOS, MikroTik, Juniper, Arista, Linux

### v0.5.0 - Topology Export
- New `export_topology_diagram()` - export as SVG/PNG with port status indicators
- Drawing object support: rectangles, ellipses, text labels

### v0.3.0 - Type Safety & Performance (Breaking Changes)

**IMPORTANT**: If upgrading from v0.2.x, see [MIGRATION_v0.3.md](MIGRATION_v0.3.md) for complete migration guide.

- **Type-Safe Operations**: Pydantic v2 models with validation for all inputs/outputs
- **Two-Phase Validation**: Prevents partial topology changes - validates ALL operations before executing ANY
- **10× Performance**: TTL-based caching eliminates N+1 queries in batch operations
- **Multi-Adapter Support**: Explicit `adapter_a`/`adapter_b` parameters for routers with multiple interface types
- **JSON Outputs**: All tools now return structured JSON instead of formatted strings
- **Better Error Messages**: Detailed validation errors with suggested fixes

**Breaking Changes:**
1. All tool outputs now return JSON - Update parsing code if calling from scripts
2. set_connection() requires adapters - Add `adapter_a` and `adapter_b` to connect operations
3. Error format changed - Errors now return JSON with `error` and `details` fields

## Features

- **SSH Automation** (v0.12.0): Network device automation via Netmiko (200+ device types), dual storage with job history
- **Topology Export** (v0.5.0): Export diagrams as SVG/PNG matching official GNS3 rendering (v0.6.2)
- **Interactive Console Tools** (v0.6.0): Auto-detect device types, wait for prompts, send special keystrokes
- **Project Management**: List, open GNS3 projects
- **Unified Node Control** (v0.2.0): Single tool for start/stop/restart/configure nodes
- **Auto-Connect Console** (v0.2.0): Automatic session management by node name
- **Console Access**: Telnet console with clean output (ANSI stripped, normalized line endings)
- **Output Diff Tracking**: Read full buffer or only new output since last check
- **Link Management** (v0.2.0): Batch connect/disconnect network connections with two-phase validation (v0.3.0)
- **Node Configuration** (v0.2.0): Position, lock, configure switch ports
- **Drawing Objects** (v0.5.0): Create rectangles, ellipses, text labels for documentation
- **Desktop Extension**: One-click installation in Claude Desktop
- **Multi-Session**: Support multiple concurrent console and SSH connections
- **Type Safety** (v0.3.0): Pydantic models ensure data integrity

## Architecture

- **MCP Server** (`mcp-server/`): FastMCP-based server with GNS3 v3 API client
- **SSH Proxy** (`ssh-proxy/`): FastAPI service for SSH automation (v0.12.0, deployed to GNS3 host)
- **Agent Skill** (`skill/`): Procedural knowledge for network automation workflows
- **Desktop Extension**: Packaged `.mcpb` bundle for Claude Desktop

## Requirements

- Python ≥ 3.10
- GNS3 Server v3.x running and accessible
- Network access to GNS3 server
- **SSH Automation (v0.12.0)**: Docker on GNS3 host for SSH proxy container
- Dependencies (see `requirements.txt`):
  - `mcp>=1.2.1` - MCP protocol support
  - `httpx>=0.28.1` - HTTP client for GNS3 API
  - `telnetlib3>=2.0.4` - Telnet console connections
  - `pydantic>=2.0.0` - Type-safe data models (v0.3.0)
  - `python-dotenv>=1.1.1` - Environment variable management

## Transport Modes

The MCP server supports three transport modes for different deployment scenarios:

### Transport Mode Comparison

| Transport | Use Case | Communication | Installation |
|-----------|----------|---------------|--------------|
| **stdio** | Claude Desktop, Claude Code | Process-based (stdin/stdout) | Default, packaged in .mcpb |
| **HTTP** | Network access, remote clients | Streamable HTTP (recommended) | Manual server deployment |
| **SSE** | Legacy compatibility | Server-Sent Events (deprecated) | Use HTTP instead |

### When to Use Each Transport

**stdio (Default)**:
- ✅ Claude Desktop with .mcpb extension
- ✅ Claude Code with project/global installation
- ✅ Local development and testing
- ✅ Simple single-user scenarios
- ❌ Not suitable for network access

**HTTP (Streamable)**:
- ✅ Multiple clients connecting over network
- ✅ Remote deployment (cloud servers, containers)
- ✅ Web service integrations
- ✅ Load balancing and scaling
- ✅ Modern bidirectional communication
- **Recommended** for production network deployments

**SSE (Deprecated)**:
- ⚠️ Legacy backward compatibility only
- ❌ Do NOT use for new projects
- ❌ Limited to server-to-client streaming
- Use HTTP transport instead

### Starting the Server

**stdio Mode (Default)**:
```bash
# Used by Claude Desktop/Code - automatically started
python mcp-server/server/main.py --host localhost --port 80 \
  --username admin --password YOUR_PASSWORD
```

**HTTP Mode (Streamable)**:
```bash
# Network-accessible server at http://localhost:8000/mcp/
python mcp-server/server/main.py --host localhost --port 80 \
  --username admin --password YOUR_PASSWORD \
  --transport http --http-host 0.0.0.0 --http-port 8000
```

**SSE Mode (Legacy)**:
```bash
# Only use for backward compatibility with old clients
python mcp-server/server/main.py --host localhost --port 80 \
  --username admin --password YOUR_PASSWORD \
  --transport sse --http-host 0.0.0.0 --http-port 8000
```

### HTTP Transport Endpoints

When running in HTTP mode, the server exposes:

- **Main endpoint**: `http://{http-host}:{http-port}/mcp/`
- **Protocol**: MCP Streamable HTTP
- **Methods**: POST (bidirectional communication)
- **Authentication**: GNS3 credentials in startup args

**Example HTTP Configuration**:
```bash
# Local network access
--transport http --http-host 192.168.1.100 --http-port 8000

# Docker container
--transport http --http-host 0.0.0.0 --http-port 8000

# Custom port
--transport http --http-host 127.0.0.1 --http-port 3000
```

### Security Considerations

**stdio Mode**:
- ✅ Process-level isolation
- ✅ No network exposure
- ✅ Credentials passed as command arguments

**HTTP Mode**:
- ⚠️ Network-exposed endpoints
- ⚠️ No built-in authentication on MCP endpoint (relies on GNS3 auth)
- ⚠️ Use firewall rules to restrict access
- ⚠️ Consider reverse proxy with TLS for production

## Installation

### Windows Service (Production Deployment)

Run the MCP HTTP server as a Windows service for production use:

```batch
REM Install and start service (requires admin privileges)
server.cmd install

REM Check service status
server.cmd status

REM Stop service
server.cmd stop

REM Restart service
server.cmd restart

REM Uninstall service
server.cmd uninstall
```

**Requirements**:
- **WinSW**: Windows Service Wrapper executable
  - Auto-downloads from https://github.com/winsw/winsw/releases on first run
  - For 32-bit systems, edit `server.cmd` and uncomment the x86 URL
- **GNS3-MCP-HTTP.xml**: Service configuration (included in project)
- **Administrator privileges**: Required for service installation

**Service Details**:
- Service Name: `GNS3-MCP-HTTP`
- Startup Type: Automatic
- Log Files:
  - Server log: `mcp-http-server.log`
  - Wrapper log: `GNS3-MCP-HTTP.wrapper.log`
  - Error log: `GNS3-MCP-HTTP.err.log`

**Manual WinSW Installation** (if auto-download fails):
1. Download WinSW from https://github.com/winsw/winsw/releases
2. Choose `WinSW-x64.exe` (or `WinSW-x86.exe` for 32-bit)
3. Rename to `GNS3-MCP-HTTP.exe`
4. Place in project root directory

### Claude Desktop (stdio mode)

1. **Package the extension**:
   ```bash
   cd mcp-server
   npx @anthropic-ai/mcpb pack
   ```

2. **Install in Claude Desktop**:
   - Double-click the generated `mcp-server.mcpb` file
   - Configure GNS3 connection details in the UI
   - Click Install

3. **Install the Agent Skill**:
   - Copy `skill/` folder to `~/.claude/skills/gns3-lab-automation/`
   - Restart Claude Desktop

### Claude Code

#### Option 1: Project-Scoped (Recommended)

This project includes a pre-configured setup that automatically loads credentials from `.env`.

1. **Configuration files** (already included):

   `.mcp.json`:
   ```json
   {
     "mcpServers": {
       "gns3-lab": {
         "command": "python",
         "args": ["./mcp-server/start_mcp.py"]
       }
     }
   }
   ```

   `.env` (create this file):
   ```bash
   GNS3_USER=admin
   GNS3_PASSWORD=your-password
   GNS3_HOST=192.168.1.20
   GNS3_PORT=80
   ```

2. **Wrapper script** (`mcp-server/start_mcp.py`):
   - Automatically loads credentials from `.env`
   - Sets up Python paths for dependencies
   - No manual PYTHONPATH configuration needed

3. **Start Claude Code** in project directory - Server auto-loads

4. **Verify installation**:
   ```bash
   claude mcp get gns3-lab
   ```
   Should show: `Status: ✓ Connected`

5. **Start new conversation** to access MCP tools (tools load at conversation start)

#### Option 2: Global Installation

Install server globally for use across all projects:

**Windows (PowerShell)**:
```powershell
claude mcp add --transport stdio gns3-lab --scope user -- `
  python "C:\path\to\project\mcp-server\start_mcp.py"
```

**Linux/Mac (Bash)**:
```bash
claude mcp add --transport stdio gns3-lab --scope user -- \
  python /path/to/project/mcp-server/start_mcp.py
```

**Note**: Global installation reads from the same `.env` file in the project directory.

#### Troubleshooting

**Server not connecting:**
1. Check `.env` file exists with correct credentials
2. Verify server: `python mcp-server/start_mcp.py` (should connect to GNS3)
3. Check status: `claude mcp get gns3-lab`

**Tools not available:**
- MCP tools load at conversation start
- Start a new conversation after configuring the server
- Old conversations won't have access to newly added servers

### Development Setup

1. **Create virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run server**:
   ```bash
   cd mcp-server/server
   python main.py --host localhost --port 80 --username admin --password YOUR_PASSWORD
   ```

4. **Test with MCP Inspector**:
   ```bash
   mcp dev main.py --host localhost --port 80 --username admin --password YOUR_PASSWORD
   ```

## Configuration

### GNS3 Server Settings

- **Host**: GNS3 server IP/hostname (default: `localhost`)
- **Port**: API port (default: `80`)
- **Username**: GNS3 username (default: `admin`)
- **Password**: GNS3 password (required)

### Default Configuration

Based on traffic analysis, typical setup:
- Local GNS3 VM: `localhost:80`
- Authentication: Required (JWT)
- Console encoding: UTF-8

## Available MCP Tools

**All tools return JSON** (v0.3.0) - Outputs are structured and parseable.

### Project Operations
- `list_projects(force_refresh=False)` - List all projects with status
  - Returns: JSON array of `ProjectInfo` objects
  - Caching: 60s TTL (use `force_refresh=True` to bypass)
- `open_project(project_name)` - Open a project by name
  - Returns: JSON `ProjectInfo` object

### Node Operations
- `list_nodes(force_refresh=False)` - List all nodes in current project
  - Returns: JSON array of `NodeInfo` objects
  - Caching: 30s TTL
- `get_node_details(node_name, force_refresh=False)` - Get node info (console, status, ports)
  - Returns: JSON `NodeInfo` object with ports, adapters, console info
  - Caching: 30s TTL
- `set_node(node_name, action, x, y, z, locked, ports)` - **[v0.2.0]** Unified node control
  - Actions: `start`, `stop`, `suspend`, `reload`, `restart`
  - Properties: position (x, y, z), locked, switch ports
  - Restart with automatic retry logic (3 attempts × 5 seconds)
  - Returns: JSON status message

### Console Operations (Auto-Connect)
- `send_console(node_name, data)` - **[v0.2.0]** Send commands (auto-connects)
  - Returns: JSON status message
- `read_console(node_name, diff)` - **[v0.2.0]** Read console output
  - `diff=False` (default): full buffer
  - `diff=True`: only new output since last read
  - Returns: JSON with console output
- `disconnect_console(node_name)` - **[v0.2.0]** Close console session
  - Returns: JSON status message
- `get_console_status(node_name)` - **[v0.3.0]** Check console connection status
  - Returns: JSON `ConsoleStatus` (connected, session_id, host, port, buffer_size)
  - Makes auto-connect behavior transparent

### Link Management
- `get_links(force_refresh=False)` - **[v0.2.1]** List all network links with IDs, nodes, and ports
  - Returns: JSON array of `LinkInfo` objects with adapter numbers
  - Shows link IDs needed for disconnection
  - Displays which ports are in use
  - Caching: 30s TTL
- `set_connection(connections)` - **[v0.2.0, v0.3.0 breaking]** Batch connect/disconnect links
  - **Two-phase validation** (v0.3.0): Validates ALL operations before executing ANY
  - **BREAKING**: Now requires `adapter_a` and `adapter_b` parameters
  - **Use get_links() first** to check topology
  - Returns: JSON `OperationResult` with completed and failed operations
  - Cache invalidation: Clears link/node cache after execution

## Usage Examples

### Start a Lab (v0.2.0)

```python
# List available projects
list_projects()

# Open your lab
open_project("My Network Lab")

# Check nodes
list_nodes()

# Start a router
set_node("Router1", action="start")

# Or restart with retry logic
set_node("Router1", action="restart")
```

### Configure Router via Console (v0.2.0)

```python
# Send commands (auto-connects on first use)
send_console("Router1", "\n")  # Wake up console
output = read_console("Router1", diff=True)  # Check prompt

# Send configuration command
send_console("Router1", "/ip address print\n")
output = read_console("Router1", diff=True)  # Read new output only

# Disconnect when done
disconnect_console("Router1")
```

### Multi-Device Automation (v0.2.0)

```python
# Start all routers
for router in ["R1", "R2", "R3"]:
    set_node(router, action="start")

# Configure each router
for router in ["R1", "R2", "R3"]:
    # Send configuration (auto-connects)
    send_console(router, "\n")
    read_console(router, diff=True)  # Check prompt

    send_console(router, "configure commands...\n")
    output = read_console(router, diff=True)
    # Process output...

    # Disconnect when done
    disconnect_console(router)
```

### Manage Network Topology (v0.3.0)

```python
# 1. Check current topology (returns JSON)
links_json = get_links()
# Output: JSON array with LinkInfo objects showing adapters and ports

# 2. Batch link operations (disconnect then connect)
# IMPORTANT: v0.3.0 requires adapter_a and adapter_b parameters
set_connection([
    # Disconnect old link (use link_id from get_links output)
    {"action": "disconnect", "link_id": "abc-123"},

    # Connect R1 to Switch1 (port 0 now free)
    {"action": "connect",
     "node_a": "R1", "adapter_a": 0, "port_a": 0,
     "node_b": "Switch1", "adapter_b": 0, "port_b": 3},

    # Connect R2 to Switch1
    {"action": "connect",
     "node_a": "R2", "adapter_a": 0, "port_a": 0,
     "node_b": "Switch1", "adapter_b": 0, "port_b": 4}
])
# Returns: JSON OperationResult with completed operations

# 3. Multi-adapter device example (router with GigE and Serial)
# Router has:
# - Adapter 0: GigabitEthernet 0/0-3
# - Adapter 1: Serial 1/0-1

set_connection([
    # Connect GigabitEthernet to switch
    {"action": "connect",
     "node_a": "Router1", "adapter_a": 0, "port_a": 0,
     "node_b": "Switch1", "adapter_b": 0, "port_b": 0},

    # Connect Serial to another router
    {"action": "connect",
     "node_a": "Router1", "adapter_a": 1, "port_a": 0,
     "node_b": "Router2", "adapter_b": 1, "port_b": 0}
])
```

### Configure Node Properties (v0.2.0)

```python
# Position and lock node
set_node("Router1", x=100, y=200, locked=True)

# Configure switch ports
set_node("Switch1", ports=16)

# Combined: start and position
set_node("Router1", action="start", x=150, y=300)
```

## Migration Guides

### v0.2.x → v0.3.0

**BREAKING CHANGES**: See [MIGRATION_v0.3.md](MIGRATION_v0.3.md) for complete migration guide.

Key changes:
- All tool outputs now return JSON
- `set_connection()` requires `adapter_a` and `adapter_b` parameters
- Error responses changed to JSON format
- New features: Two-phase validation, caching, multi-adapter support

### v0.1.x → v0.2.0

Version 0.2.0 introduces breaking changes to simplify the API and improve usability.

### Removed Tools

The following tools have been removed or consolidated:

| Removed Tool | Replacement | Notes |
|-------------|-------------|-------|
| `connect_console(node_name)` | *(auto-connect)* | No manual connect needed |
| `read_console_diff(session_id)` | `read_console(node_name, diff=True)` | Merged into single tool |
| `list_console_sessions()` | *(removed)* | Sessions managed automatically |
| `start_node(node_name)` | `set_node(node_name, action="start")` | Unified control |
| `stop_node(node_name)` | `set_node(node_name, action="stop")` | Unified control |

### Updated Tool Signatures

**Console Operations:**
```python
# OLD (v0.1.x)
session_id = connect_console("Router1")
send_console(session_id, "command\n")
output = read_console_diff(session_id)
disconnect_console(session_id)

# NEW (v0.2.0)
send_console("Router1", "command\n")  # Auto-connects
output = read_console("Router1", diff=True)
disconnect_console("Router1")
```

**Node Control:**
```python
# OLD (v0.1.x)
start_node("Router1")
stop_node("Router1")

# NEW (v0.2.0)
set_node("Router1", action="start")
set_node("Router1", action="stop")
set_node("Router1", action="restart")  # New: with retry logic
```

### New Features

**Link Management:**
```python
# Batch connect/disconnect operations
set_connection([
    {"action": "disconnect", "link_id": "abc123"},
    {"action": "connect", "node_a": "R1", "port_a": 0,
     "node_b": "R2", "port_b": 1}
])
```

**Node Configuration:**
```python
# Position, lock, and configure nodes
set_node("Router1", x=100, y=200, locked=True)
set_node("Switch1", ports=16)
```

### Benefits

- **Simpler API**: No session_id tracking needed
- **Auto-connect**: Console operations "just work"
- **Unified control**: Single tool for all node operations
- **Batch operations**: Change multiple links atomically
- **Retry logic**: Built-in restart with polling

## Agent Skill

The included Agent Skill teaches Claude about:
- GNS3 concepts (projects, nodes, console types)
- Common workflows (lab setup, device configuration, troubleshooting)
- Device-specific commands (RouterOS, Arista, Cisco)
- Best practices for console interaction
- Error handling strategies

### Global Installation (Recommended)

Install the skill globally to use it across all Claude Code projects:

**Quick Install (PowerShell)**:
```powershell
# Create directory and copy skill
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.claude\skills\gns3"
Copy-Item "C:\HOME\1. Scripts\008. GNS3 MCP\skill\SKILL.md" `
  -Destination "$env:USERPROFILE\.claude\skills\gns3\SKILL.md"
```

**Status**: ✓ Already installed globally at `C:\Users\mail4\.claude\skills\gns3\SKILL.md`

See [GLOBAL_SKILL_INSTALLATION.md](GLOBAL_SKILL_INSTALLATION.md) for complete installation instructions, troubleshooting, and best practices.

---

See `skill/SKILL.md` for complete documentation.

## API Reference

### GNS3 API v3 Endpoints (Confirmed)

Based on actual traffic analysis and implementation:

**Authentication:**
- `POST /v3/access/users/authenticate` - JWT authentication
- Header: `Authorization: Bearer <JWT_TOKEN>`

**Projects:**
- `GET /v3/projects` - List projects
- `POST /v3/projects/{id}/open` - Open project

**Nodes:**
- `GET /v3/projects/{id}/nodes` - List nodes
- `POST /v3/projects/{id}/nodes/{node_id}/start` - Start node
- `POST /v3/projects/{id}/nodes/{node_id}/stop` - Stop node
- `POST /v3/projects/{id}/nodes/{node_id}/suspend` - Suspend node *(v0.2.0)*
- `POST /v3/projects/{id}/nodes/{node_id}/reload` - Reload node *(v0.2.0)*
- `PUT /v3/projects/{id}/nodes/{node_id}` - Update node properties *(v0.2.0)*

**Links:**
- `GET /v3/projects/{id}/links` - List links
- `POST /v3/projects/{id}/links` - Create link *(v0.2.0)*
- `DELETE /v3/projects/{id}/links/{link_id}` - Delete link *(v0.2.0)*

### Console Access

- Console connection: Direct telnet to `{gns3_host}:{console_port}`
- Port numbers extracted from node data (`console` field)
- Supported console types: `telnet` (others return error)

## Development

### Project Structure

```
008. GNS3 MCP/
├── mcp-server/
│   ├── server/
│   │   ├── main.py              # MCP server with FastMCP
│   │   ├── gns3_client.py       # GNS3 API v3 client
│   │   ├── console_manager.py   # Telnet console manager
│   │   ├── models.py            # [v0.3.0] Pydantic data models
│   │   ├── link_validator.py    # [v0.3.0] Two-phase link validation
│   │   └── cache.py             # [v0.3.0] TTL-based data caching
│   ├── lib/                     # Bundled Python dependencies
│   ├── manifest.json            # Desktop extension manifest
│   └── start_mcp.py            # Wrapper script for .env loading
├── skill/
│   ├── SKILL.md                 # Agent skill documentation
│   └── examples/                # Workflow examples
├── tests/
│   ├── test_mcp_console.py      # Console manager tests
│   ├── interactive_console_test.py  # Direct console testing
│   ├── list_nodes_helper.py     # Node discovery helper
│   ├── ALPINE_SETUP_GUIDE.md    # Test device setup guide
│   └── TEST_RESULTS.md          # Latest test results
├── data/
│   ├── dump.pcapng             # Traffic analysis (reference)
│   └── SESSION.txt             # HTTP session analysis
├── MIGRATION_v0.3.md           # [v0.3.0] Migration guide
├── REFACTORING_STATUS_v0.3.md  # [v0.3.0] Refactoring documentation
├── requirements.txt
└── README.md
```

### Testing

#### Manual Testing

1. Start GNS3 server
2. Create/open a test project
3. Run MCP server in dev mode:
   ```bash
   mcp dev server/main.py --host YOUR_GNS3_IP --port 80 --username admin --password YOUR_PASSWORD
   ```
4. Test tools in MCP Inspector

#### Automated Testing

1. Setup test device (see `tests/ALPINE_SETUP_GUIDE.md`)
2. Run direct console test:
   ```bash
   python tests/simple_console_test.py --host YOUR_GNS3_IP --port CONSOLE_PORT
   ```
3. Run full MCP test suite:
   ```bash
   python tests/test_mcp_server.py --password YOUR_PASSWORD --test-node "Alpine-Test"
   ```

See `tests/README.md` for complete testing documentation.

### Adding New Tools

1. Add async function in `main.py` decorated with `@mcp.tool()`
2. Access context: `ctx.request_context.lifespan_context.gns3` or `.console`
3. Return string result
4. Update `manifest.json` tools list
5. Add to git and rebuild extension

## Troubleshooting

### Authentication Failed
- Verify GNS3 credentials
- Check GNS3 server is running: `http://{host}:{port}/v3/version`
- Ensure port 80 is accessible

### Console Not Connecting
- Verify node is started
- Check console type is `telnet`
- Confirm firewall allows access to console ports
- Some nodes take 30-60s after start before console is ready

### Session Timeout
- Console sessions expire after 30 minutes idle
- Always disconnect when done
- Use `list_console_sessions()` to check active sessions

## Contributing

1. Fork repository
2. Create feature branch
3. Test with real GNS3 server
4. Submit pull request

## License

MIT License - see LICENSE file

## Credits

Built with:
- [MCP Python SDK](https://github.com/anthropics/python-mcp)
- [httpx](https://www.python-httpx.org/)
- [telnetlib3](https://telnetlib3.readthedocs.io/)

GNS3 API analysis based on actual v3.0.5 traffic captures.
