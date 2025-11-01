# GNS3 MCP Server

Model Context Protocol (MCP) server for GNS3 network lab automation. Control GNS3 projects, nodes, and device consoles through Claude Desktop or any MCP-compatible client.

**Version**: 0.41.0

## Features

- **Project Management**: Create, open, close GNS3 projects
- **Node Control**: Start/stop/restart nodes with wildcard patterns (`*`, `Router*`)
- **Console Access**: Telnet console automation with pattern matching and grep filtering
- **SSH Automation**: Network device automation via Netmiko (200+ device types)
- **Network Topology**: Batch connect/disconnect links, create drawings, export diagrams
- **Docker Integration**: Configure container networks, read/write files
- **Security**: API key authentication (HTTP mode), service privilege isolation, HTTPS support

## Installation

### Quick Start with pip (Recommended)

**Prerequisites:**
- Python 3.10+
- GNS3 server running and accessible

**Steps:**

1. Install package:
   ```bash
   pip install gns3-mcp
   ```

2. Create `.env` file in your working directory:
   ```bash
   GNS3_HOST=192.168.1.20
   GNS3_PORT=80
   GNS3_USER=admin
   GNS3_PASSWORD=your-password
   ```

3. Add to Claude Code (STDIO mode):
   ```bash
   claude mcp add --transport stdio gns3-lab -- gns3-mcp
   ```

4. Verify installation:
   ```bash
   claude mcp get gns3-lab
   # Should show: Status: ✓ Connected
   ```

**HTTP Mode (Advanced):**

For network access or always-running service:

```bash
# Add to .env
MCP_API_KEY=your-random-token-here

# Configure Claude Code
claude mcp add --transport http gns3-lab \
  http://127.0.0.1:8100/mcp/ \
  --header "MCP_API_KEY: your-token"

# Start server (in separate terminal)
gns3-mcp --transport http --http-port 8100
```

---

### Claude Code (Manual Installation - STDIO Mode)

**STDIO mode is more secure** - no HTTP service, no authentication needed, runs only when Claude Code is active.

1. Create `.env` file in project root:
   ```bash
   GNS3_HOST=192.168.1.20
   GNS3_PORT=80
   GNS3_USER=admin
   GNS3_PASSWORD=your-password
   ```

2. Install:
   ```powershell
   # Windows
   claude mcp add --transport stdio gns3-lab --scope user -- python "C:\HOME\1. Scripts\008. GNS3 MCP\mcp-server\start_mcp.py"

   # Linux/Mac
   claude mcp add --transport stdio gns3-lab --scope user -- python /path/to/project/mcp-server/start_mcp.py
   ```

3. Verify: `claude mcp get gns3-lab` (should show "✓ Connected")

### Claude Code (HTTP Mode - Advanced)

**HTTP mode** requires a persistent service and API key authentication. Only use if you need the service always running.

1. Add to `.env`:
   ```bash
   # Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
   MCP_API_KEY=your-random-token-here
   ```

2. Install:
   ```powershell
   claude mcp add --transport http gns3-lab `
     http://127.0.0.1:8100/mcp/ `
     --header "MCP_API_KEY: your-random-token-here"
   ```

**Note**: If `MCP_API_KEY` is missing from `.env`, it will be auto-generated on first start and automatically saved to `.env` for persistence. Check `.env` file or service logs for the generated key.

### Claude Desktop

**Desktop extension uses STDIO mode only** (simpler, more secure, no service needed):

1. Download latest `.mcpb` from [Releases](https://github.com/ChistokhinSV/gns3-mcp/releases)
2. Double-click to install
3. Configure GNS3 credentials in Claude Desktop settings

### Windows Service Deployment

Run MCP server as a Windows service with WinSW (for HTTP mode):

**Setup (one-time):**
```batch
# 1. Recreate venv with all dependencies (including FastAPI)
.\server.cmd venv-recreate

# 2. Create service user account (requires Administrator)
.\server.cmd create-user

# 3. Install and start service
.\server.cmd install
```

**Service Management:**
```batch
# Check status
.\server.cmd status

# Start/stop/restart
.\server.cmd start
.\server.cmd stop
.\server.cmd restart

# After code updates
.\server.cmd venv-recreate    # Rebuild dependencies
.\server.cmd reinstall        # Reinstall service

# Remove service
.\server.cmd uninstall
```

**Service Details:**
- **User**: GNS3MCPService (low privilege, not LocalSystem)
- **Startup**: Automatic
- **Logs**: `mcp-http-server.log` and `GNS3-MCP-HTTP.wrapper.log`
- **Commands**: All integrated into server.cmd

### Manual Installation

**Requirements:**
- Python ≥ 3.10
- GNS3 Server v3.x running and accessible

**Setup:**
```bash
# Install dependencies
pip install -r requirements.txt

# Run directly (STDIO mode - no authentication)
python mcp-server/server/main.py --host YOUR_GNS3_HOST --port 80 \
  --username admin --password YOUR_PASSWORD

# Or run HTTP mode (requires MCP_API_KEY in environment)
export MCP_API_KEY="your-api-key"
python mcp-server/start_mcp_http.py
```

## Documentation

- **[CHANGELOG.md](CHANGELOG.md)** - Version history and release notes
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - SSH proxy deployment instructions
- **[docs/architecture/](docs/architecture/)** - Architecture documentation and C4 diagrams

## License

MIT License

## Author

Sergei Chistokhin (Sergei@Chistokhin.com)
