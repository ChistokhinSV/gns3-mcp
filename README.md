# GNS3 MCP Server

Model Context Protocol (MCP) server for GNS3 network lab automation. Control GNS3 projects, nodes, and device consoles through Claude Desktop or any MCP-compatible client.

## Features

- **Project Management**: List, open GNS3 projects
- **Node Control**: Start, stop nodes; get detailed status
- **Console Access**: Connect to device consoles (telnet), send commands, read output
- **Output Diff Tracking**: Read only new console output since last check
- **Multi-Session**: Support multiple concurrent console connections
- **Desktop Extension**: One-click installation in Claude Desktop

## Architecture

- **MCP Server** (`mcp-server/`): FastMCP-based server with GNS3 v3 API client
- **Agent Skill** (`skill/`): Procedural knowledge for network automation workflows
- **Desktop Extension**: Packaged `.mcpb` bundle for Claude Desktop

## Requirements

- Python ≥ 3.10
- GNS3 Server v3.x running and accessible
- Network access to GNS3 server

## Installation

### Claude Desktop

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

### Project Operations
- `list_projects()` - List all projects with status
- `open_project(project_name)` - Open a project by name

### Node Operations
- `list_nodes()` - List all nodes in current project
- `get_node_details(node_name)` - Get node info (console, status, ports)
- `start_node(node_name)` - Start a node
- `stop_node(node_name)` - Stop a node

### Console Operations
- `connect_console(node_name)` - Connect to telnet console, returns session_id
- `send_console(session_id, data)` - Send commands/keystrokes
- `read_console(session_id)` - Read full console buffer
- `read_console_diff(session_id)` - Read only new output since last read
- `disconnect_console(session_id)` - Close console session
- `list_console_sessions()` - List active sessions

## Usage Examples

### Start a Lab

```python
# List available projects
list_projects()

# Open your lab
open_project("My Network Lab")

# Check nodes
list_nodes()

# Start a router
start_node("Router1")
```

### Configure Router via Console

```python
# Connect to console
session_id = connect_console("Router1")  # Returns: session_id

# Send commands
send_console(session_id, "\n")  # Wake up console
output = read_console_diff(session_id)  # Check prompt

send_console(session_id, "/ip address print\n")
output = read_console_diff(session_id)  # Read command output

# Disconnect when done
disconnect_console(session_id)
```

### Multi-Device Automation

```python
# Start all routers
for router in ["R1", "R2", "R3"]:
    start_node(router)

# Configure each
sessions = {}
for router in ["R1", "R2", "R3"]:
    sessions[router] = connect_console(router)
    send_console(sessions[router], "configure commands...\n")

# Read results
for router, sid in sessions.items():
    output = read_console_diff(sid)
    # Process output...

# Cleanup
for sid in sessions.values():
    disconnect_console(sid)
```

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

Based on actual traffic analysis:

- `POST /v3/access/users/authenticate` - JWT authentication
- `GET /v3/projects` - List projects
- `POST /v3/projects/{id}/open` - Open project
- `GET /v3/projects/{id}/nodes` - List nodes
- `GET /v3/projects/{id}/links` - List links
- `POST /v3/projects/{id}/nodes/{node_id}/start` - Start node
- `POST /v3/projects/{id}/nodes/{node_id}/stop` - Stop node

Authentication: `Authorization: Bearer <JWT_TOKEN>`

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
│   │   └── console_manager.py   # Telnet console manager
│   ├── manifest.json            # Desktop extension manifest
│   └── README.md
├── skill/
│   ├── SKILL.md                 # Agent skill documentation
│   └── examples/                # Workflow examples
├── tests/
│   ├── test_mcp_server.py       # Automated test suite
│   ├── simple_console_test.py   # Direct console testing
│   ├── ALPINE_SETUP_GUIDE.md    # Test device setup guide
│   └── README.md                # Testing documentation
├── data/
│   ├── dump.pcapng             # Traffic analysis (reference)
│   └── SESSION.txt             # HTTP session analysis
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
