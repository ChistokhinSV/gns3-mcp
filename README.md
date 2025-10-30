# GNS3 MCP Server

Model Context Protocol (MCP) server for GNS3 network lab automation. Control GNS3 projects, nodes, and device consoles through Claude Desktop or any MCP-compatible client.

**Version**: 0.40.1

## Features

- **Project Management**: Create, open, close GNS3 projects
- **Node Control**: Start/stop/restart nodes with wildcard patterns (`*`, `Router*`)
- **Console Access**: Telnet console automation with pattern matching and grep filtering
- **SSH Automation**: Network device automation via Netmiko (200+ device types)
- **Network Topology**: Batch connect/disconnect links, create drawings, export diagrams
- **Docker Integration**: Configure container networks, read/write files

## Quick Start

### Claude Code

1. Create `.env` file in project root:
   ```bash
   GNS3_HOST=YOUR_GNS3_HOST_IP
   GNS3_PORT=80
   GNS3_USER=admin
   GNS3_PASSWORD=your-password
   ```

2. Install globally:
   ```bash
   # Windows (PowerShell)
   claude mcp add --transport stdio gns3-lab --scope user -- python "C:\path\to\project\mcp-server\start_mcp.py"
   
   # Linux/Mac
   claude mcp add --transport stdio gns3-lab --scope user -- python /path/to/project/mcp-server/start_mcp.py
   ```

3. Verify: `claude mcp get gns3-lab` (should show "✓ Connected")

### Claude Desktop

1. Download the latest release from [Releases](https://github.com/ChistokhinSV/gns3-mcp/releases)
2. Double-click `mcp-server.mcpb` to install
3. Configure GNS3 connection details (host, port, credentials)

### Manual Installation

**Requirements:**
- Python ≥ 3.10
- GNS3 Server v3.x running and accessible

**Install dependencies:**
```bash
pip install -r requirements.txt
```

**Run server:**
```bash
python mcp-server/server/main.py --host YOUR_GNS3_HOST --port 80 \
  --username admin --password YOUR_PASSWORD
```

### Windows Service

Run as a Windows service for production deployment:

```batch
REM Install service (auto-downloads WinSW if needed)
server.cmd install

REM Check status
server.cmd status

REM Uninstall
server.cmd uninstall
```

## Documentation

- **[CHANGELOG.md](CHANGELOG.md)** - Version history and release notes
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - SSH proxy deployment instructions
- **[docs/architecture/](docs/architecture/)** - Architecture documentation and C4 diagrams

## License

MIT License

## Author

Sergei Chistokhin (Sergei@Chistokhin.com)
