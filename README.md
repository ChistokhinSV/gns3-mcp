# GNS3 MCP Server

Model Context Protocol (MCP) server for GNS3 network lab automation. Control GNS3 projects, nodes, and device consoles through Claude Desktop or any MCP-compatible client.

**Version**: 0.49.0

## Features

- **15 Tools**: CRUD-style GNS3 automation (v0.47.0: 53% consolidation from 32 tools)
- **25 Resources**: Read-only data access (projects, nodes, links, sessions, topology reports)
- **CRUD Pattern**: Consolidated tools with `action` parameters (`project(action="open")`, `node(action="create")`, etc.)
- **Batch Operations**: Console and SSH operations use batch-only APIs for atomic execution
- **Wildcard Support**: Node operations support patterns (`*`, `Router*`, `R[123]`, JSON arrays)
- **Project Management**: Create, open, close GNS3 projects
- **Node Control**: Start/stop/restart nodes with wildcard patterns and parallel execution
- **Console Access**: Telnet console automation with pattern matching and grep filtering
- **SSH Automation**: Network device automation via Netmiko (200+ device types)
- **Network Topology**: Batch connect/disconnect links, create drawings, export diagrams
- **Docker Integration**: Configure container networks, read/write files
- **Tool Discovery**: `search_tools()` with category/capability/resource filtering
- **Claude Desktop Support**: All resources accessible via tools (`query_resource`, `list_projects`, `list_nodes`, `get_topology`)
- **Security**: API key authentication (HTTP mode), service privilege isolation, HTTPS support

## Installation

**Supported Platform:** Windows only

### Quick Start (Claude Code - Recommended)

**Prerequisites:**
- Windows 10/11
- GNS3 server running and accessible
- Claude Code installed
- **uv package manager** (for uvx): Install with `pip install uv` or download from https://github.com/astral-sh/uv

**Option 1: Using uvx (Recommended - Faster)**

```powershell
# Single command - no .env file needed!
claude mcp add --transport stdio gns3-mcp `
  --env GNS3_HOST=192.168.1.20 `
  --env GNS3_PORT=80 `
  --env GNS3_USER=admin `
  --env GNS3_PASSWORD=your-password `
  --scope user `
  -- uvx gns3-mcp@latest

# Verify installation
claude mcp get gns3-mcp
# Should show: Status: ✓ Connected
```

**Option 2: Using pip (Traditional)**

```powershell
# Step 1: Install package
pip install gns3-mcp

# Step 2: Add to Claude Code with credentials
claude mcp add --transport stdio gns3-mcp `
  --env GNS3_HOST=192.168.1.20 `
  --env GNS3_PORT=80 `
  --env GNS3_USER=admin `
  --env GNS3_PASSWORD=your-password `
  --scope user `
  -- gns3-mcp

# Step 3: Verify installation
claude mcp get gns3-mcp
# Should show: Status: ✓ Connected
```

> **Why uvx?** 10-100× faster than pip, automatic dependency isolation, no venv management needed.

---

### Installation by Editor

<details>
<summary><b>Claude Code (Detailed Setup)</b></summary>

### Claude Code Setup

**STDIO Mode (Recommended)**

STDIO mode is more secure - no HTTP service, no authentication needed, runs only when Claude Code is active.

**Using uvx (Recommended):**

```powershell
# 1. Install uv (one-time setup)
pip install uv

# 2. Create .env file
@"
GNS3_HOST=192.168.1.20
GNS3_PORT=80
GNS3_USER=admin
GNS3_PASSWORD=your-password
"@ | Out-File -FilePath .env -Encoding ASCII

# 3. Add to Claude Code
claude mcp add --transport stdio gns3-mcp --scope user -- uvx gns3-mcp@latest

# 4. Verify
claude mcp get gns3-mcp
```

**Using pip:**

```powershell
# 1. Install package globally
pip install gns3-mcp

# 2. Create .env file in project directory
@"
GNS3_HOST=192.168.1.20
GNS3_PORT=80
GNS3_USER=admin
GNS3_PASSWORD=your-password
"@ | Out-File -FilePath .env -Encoding ASCII

# 3. Add to Claude Code
claude mcp add --transport stdio gns3-mcp --scope user -- gns3-mcp

# 4. Verify
claude mcp get gns3-mcp
# Should show: Status: ✓ Connected
```

**Environment Variables:**

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `GNS3_HOST` | Yes | GNS3 server IP/hostname | `192.168.1.20` |
| `GNS3_PORT` | Yes | GNS3 server port | `80` or `3080` |
| `GNS3_USER` | Yes | GNS3 username | `admin` |
| `GNS3_PASSWORD` | Yes | GNS3 password | `your-password` |

</details>

<details>
<summary><b>Claude Desktop (.mcpb Package)</b></summary>

### Claude Desktop Setup

**Installation:**

1. Download the latest `.mcpb` package:
   - From [Releases](https://github.com/ChistokhinSV/gns3-mcp/releases)
   - Or build locally: `just build` (creates `mcp-server\mcp-server.mcpb`)

2. **Install by double-clicking** the `.mcpb` file

3. **Configure credentials** in Claude Desktop:
   - Open Claude Desktop
   - Go to Settings > Developer > Edit Config
   - Find `gns3-mcp` server
   - Add environment variables:
     ```json
     {
       "GNS3_HOST": "192.168.1.20",
       "GNS3_PORT": "80",
       "GNS3_USER": "admin",
       "GNS3_PASSWORD": "your-password"
     }
     ```

4. **Restart Claude Desktop**

5. **Check logs** if issues occur:
   ```
   C:\Users\<username>\AppData\Roaming\Claude\logs\mcp-server-GNS3 Lab Controller.log
   ```

</details>

<details>
<summary><b>Cursor & Windsurf (JSON Configuration)</b></summary>

### Cursor Setup

**Configuration File Location:**
- **Project-specific:** `.cursor\mcp.json` (in project directory)
- **Global:** `%USERPROFILE%\.cursor\mcp.json`

**Using uvx (Recommended):**

1. Install uv: `pip install uv`

2. Create/edit `.cursor\mcp.json`:

```json
{
  "mcpServers": {
    "gns3-mcp": {
      "command": "uvx",
      "args": ["gns3-mcp@latest"],
      "env": {
        "GNS3_HOST": "192.168.1.20",
        "GNS3_PORT": "80",
        "GNS3_USER": "admin",
        "GNS3_PASSWORD": "your-password"
      }
    }
  }
}
```

**Using pip:**

1. Install package: `pip install gns3-mcp`

2. Create/edit `.cursor\mcp.json`:

```json
{
  "mcpServers": {
    "gns3-mcp": {
      "command": "gns3-mcp",
      "args": [],
      "env": {
        "GNS3_HOST": "192.168.1.20",
        "GNS3_PORT": "80",
        "GNS3_USER": "admin",
        "GNS3_PASSWORD": "your-password"
      }
    }
  }
}
```

3. Restart Cursor

---

### Windsurf Setup

**Configuration File Location:** `%USERPROFILE%\.codeium\windsurf\mcp_config.json`

**Using uvx (Recommended):**

1. Install uv: `pip install uv`

2. Create/edit `mcp_config.json`:

```json
{
  "mcpServers": {
    "gns3-mcp": {
      "command": "uvx",
      "args": ["gns3-mcp@latest"],
      "env": {
        "GNS3_HOST": "192.168.1.20",
        "GNS3_PORT": "80",
        "GNS3_USER": "admin",
        "GNS3_PASSWORD": "your-password"
      }
    }
  }
}
```

**Using pip:**

1. Install package: `pip install gns3-mcp`

2. Create/edit `mcp_config.json`:

```json
{
  "mcpServers": {
    "gns3-mcp": {
      "command": "gns3-mcp",
      "args": [],
      "env": {
        "GNS3_HOST": "192.168.1.20",
        "GNS3_PORT": "80",
        "GNS3_USER": "admin",
        "GNS3_PASSWORD": "your-password"
      }
    }
  }
}
```

3. Restart Windsurf

> **Note:** Cursor and Windsurf use identical configuration formats.

</details>

---

### Troubleshooting

**Connection Issues:**
```powershell
# Test GNS3 server connectivity
curl http://192.168.1.20:80/v3/projects

# Check Claude Code MCP status
claude mcp get gns3-mcp

# View detailed logs (Claude Code)
# Check console output when running commands
```

**Common Issues:**
- **"gns3-mcp not found"**: Ensure package is installed (`pip list | findstr gns3-mcp`)
- **"Connection refused"**: Verify GNS3 server is running and accessible
- **"Authentication failed"**: Check credentials in `.env` file
- **"Socket is closed"**: SSH session expired, reconnect automatically on next command

**For Claude Desktop issues:**
Check logs at:
```
C:\Users\<username>\AppData\Roaming\Claude\logs\mcp-server-GNS3 Lab Controller.log
```

---

### Advanced Setup

<details>
<summary><b>HTTP Mode (Always-Running Service)</b></summary>

### HTTP Mode Configuration

**HTTP mode** requires a persistent service and API key authentication. Only use if you need the service always running or network access from other machines.

**Prerequisites:**
- `.env` file with GNS3 credentials
- API key for authentication

**Setup:**

1. Add to `.env`:
   ```powershell
   # Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
   MCP_API_KEY=your-random-token-here
   ```

2. Configure Claude Code:
   ```powershell
   claude mcp add --transport http gns3-mcp http://127.0.0.1:8100/mcp/ --scope user`
     --header "MCP_API_KEY: your-random-token-here"
   ```

3. Start server (in separate terminal):
   ```powershell
   gns3-mcp --transport http --http-port 8100
   ```

**Note**: If `MCP_API_KEY` is missing from `.env`, it will be auto-generated on first start and automatically saved to `.env` for persistence.

</details>

<details>
<summary><b>Windows Service (Production Deployment)</b></summary>

### Windows Service Deployment

Run MCP server as a Windows service with WinSW and uvx (for HTTP mode).

**📖 See [PORTABLE_SETUP.md](PORTABLE_SETUP.md) for detailed instructions.**

**Quick Setup:**
```batch
# 1. Install uv (if not already installed)
pip install uv

# 2. Set environment variables from .env (requires Administrator)
.\set-env-vars.ps1

# 3. Install and start service (requires Administrator)
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
.\server.cmd reinstall        # Reinstall service

# Remove service
.\server.cmd uninstall

# Development mode (direct run, no service)
.\server.cmd run
```

**Key Features:**
- ✅ **Portable**: Works from any folder location (no hardcoded paths)
- ✅ **No venv**: Uses uvx for automatic isolation
- ✅ **Secure**: Credentials in Windows environment variables
- ✅ **Simple**: Automated setup with PowerShell script
- **User**: GNS3MCPService (low privilege, optional)
- **Startup**: Automatic
- **Logs**: `mcp-http-server.log` and `GNS3-MCP-HTTP.wrapper.log`

</details>

<details>
<summary><b>Development Setup (Contributors)</b></summary>

### Manual Installation from Source

**Requirements:**
- Python ≥ 3.10
- GNS3 Server v3.x running and accessible

**Setup:**
```powershell
# Install dependencies
pip install -r requirements.txt

# Create .env file
@"
GNS3_HOST=192.168.1.20
GNS3_PORT=80
GNS3_USER=admin
GNS3_PASSWORD=your-password
"@ | Out-File -FilePath .env -Encoding ASCII

# Run directly (STDIO mode - no authentication)
python gns3_mcp\cli.py --host 192.168.1.20 --port 80 --username admin --password your-password

# Or add to Claude Code (project-scoped)
claude mcp add --transport stdio gns3-mcp --scope project -- python "C:\full\path\to\gns3_mcp\cli.py"
```

**Build .mcpb package:**
```powershell
just build
# Creates: mcp-server\mcp-server.mcpb
```

</details>

---

## Docker Deployment

[![Docker Image Version](https://img.shields.io/docker/v/chistokhinsv/gns3-mcp)](https://hub.docker.com/r/chistokhinsv/gns3-mcp)
[![Docker Pulls](https://img.shields.io/docker/pulls/chistokhinsv/gns3-mcp)](https://hub.docker.com/r/chistokhinsv/gns3-mcp)

Run GNS3 MCP Server in Docker for isolated deployment, easier management, and multi-platform support.

### Quick Start with Docker Compose

**Prerequisites:**
- Docker Desktop installed
- GNS3 server running and accessible
- Network access to GNS3 server

**Step 1: Download docker-compose.yml**

```bash
curl -O https://raw.githubusercontent.com/ChistokhinSV/gns3-mcp/master/docker-compose.yml
```

**Step 2: Create .env file**

```bash
cat > .env <<EOF
GNS3_HOST=192.168.1.20
GNS3_PORT=80
GNS3_USER=admin
GNS3_PASSWORD=your-password
HTTP_PORT=8000
LOG_LEVEL=INFO
EOF
```

Or copy from template:
```bash
curl -O https://raw.githubusercontent.com/ChistokhinSV/gns3-mcp/master/.env.example
mv .env.example .env
# Edit .env with your credentials
```

**Step 3: Start services**

```bash
# Start MCP server and SSH proxy
docker-compose up -d

# View logs
docker-compose logs -f

# Check health
curl http://localhost:8000/health
curl http://localhost:8022/health
```

**Step 4: Configure Claude Desktop/Code**

For **Claude Code** (HTTP mode):
```powershell
claude mcp add --transport http gns3-mcp --url http://localhost:8000
```

For **Claude Desktop**, add to MCP configuration:
```json
{
  "mcpServers": {
    "gns3-mcp": {
      "transport": {
        "type": "http",
        "url": "http://localhost:8000"
      }
    }
  }
}
```

### Using Docker Run (without compose)

```bash
docker run -d \
  --name gns3-mcp-server \
  -p 8000:8000 \
  -e GNS3_HOST=192.168.1.20 \
  -e GNS3_PORT=80 \
  -e GNS3_USER=admin \
  -e GNS3_PASSWORD=your-password \
  --restart unless-stopped \
  chistokhinsv/gns3-mcp:latest
```

### Container Management

```bash
# View logs
docker-compose logs -f gns3-mcp
docker-compose logs -f ssh-proxy

# Restart services
docker-compose restart

# Stop services
docker-compose down

# Update to latest version
docker-compose pull
docker-compose up -d
```

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GNS3_HOST` | Yes | - | GNS3 server IP/hostname |
| `GNS3_PORT` | No | `80` | GNS3 API port |
| `GNS3_USER` | Yes | - | GNS3 username |
| `GNS3_PASSWORD` | Yes | - | GNS3 password |
| `HTTP_PORT` | No | `8000` | MCP server port |
| `LOG_LEVEL` | No | `INFO` | Logging level |
| `GNS3_USE_HTTPS` | No | `false` | Use HTTPS for GNS3 |
| `GNS3_VERIFY_SSL` | No | `true` | Verify SSL certs |

See [.env.example](.env.example) for complete list.

### Architecture

The Docker deployment includes two containers:

1. **gns3-mcp** - Main MCP server (port 8000)
   - Provides MCP protocol access to GNS3
   - HTTP/SSE transport modes
   - Bridge network mode

2. **gns3-ssh-proxy** - SSH gateway (port 8022)
   - Enables SSH access to lab devices
   - Host network mode (required for isolated lab networks)
   - Netmiko-based automation

### Troubleshooting

**Container won't start:**
```bash
docker-compose logs gns3-mcp
docker-compose logs ssh-proxy
```

**Cannot connect to GNS3:**
```bash
# Test from container
docker exec gns3-mcp-server curl -v http://192.168.1.20/v3/version

# Check connectivity
docker exec gns3-mcp-server ping -c 3 192.168.1.20
```

**Health check failing:**
```bash
# Manual health check
curl -v http://localhost:8000/health

# Check container status
docker ps --filter name=gns3-mcp
```

For more details, see [docs/DOCKER_HUB.md](docs/DOCKER_HUB.md).

---

## Documentation

- **[CHANGELOG.md](CHANGELOG.md)** - Version history and release notes
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - SSH proxy deployment instructions
- **[docs/architecture/](docs/architecture/)** - Architecture documentation and C4 diagrams

## License

MIT License

## Author

Sergei Chistokhin (Sergei@Chistokhin.com)
