# GNS3 MCP Server

Model Context Protocol (MCP) server for GNS3 network lab automation. Control GNS3 projects, nodes, and device consoles through Claude Desktop or any MCP-compatible client.

**Version**: 0.56.0 · Requires GNS3 server v3.x (v3 API) · See [CHANGELOG.md](CHANGELOG.md)

## Features

- **Claude plugin**: one install for Claude Code and Cowork - the server plus a skill with lab workflows
- **15 Tools**: CRUD-style tools with an `action` parameter (`project(action="open")`, `node(action="create")`, ...)
- **25 Resources**: Read-only data (projects, nodes, links, templates, sessions, proxies, topology report)
- **5 Prompts**: Guided workflows (SSH setup, topology discovery, troubleshooting, lab setup, node setup)
- **Node Control**: Create from templates, start/stop/restart with wildcards (`*`, `Router*`, `R[123]`, JSON arrays) and parallel execution
- **Node Hardware**: RAM, CPUs, adapters, QEMU disks (`hda`/`hdb`/`hdd`), CD-ROM image, QEMU options (e.g. `-cpu host`) on create and set; values GNS3 did not apply are reported back
- **Console Access**: Batch telnet automation with pattern waits, wait-only mode, pagination handling, grep filtering
- **SSH Automation**: Network device automation via Netmiko (200+ device types) through the SSH proxy
- **Network Topology**: Batch connect/disconnect links with two-phase validation, drawings, SVG/PNG export
- **Notifications**: Live GNS3 event stream (node/link/drawing changes, logs, compute events)
- **Docker Nodes**: Configure container networks, read/write files
- **Lab Services**: TFTP server and HTTP client/reverse proxy via the SSH proxy container
- **Tool Discovery**: `search_tools()` with category/capability/resource filtering; `query_resource()` reads any resource from clients without resource support
- **Security**: required API key on every HTTP/SSE entry point (`/health` open for probes), service privilege isolation, HTTPS to GNS3

### Tools

| Tool | Actions / purpose |
|------|-------------------|
| `gns3_connection` | `check`, `retry`, `reconnect` |
| `project` | `list`, `open`, `create`, `close` |
| `node` | `list`, `create`, `delete`, `set` (properties and start/stop/suspend/reload/restart) |
| `link` | `list`, `batch` (connect / disconnect) |
| `drawing` | `list`, `create`, `update`, `delete`, `batch` |
| `console` | batch of `send`, `send_and_wait`, `read`, `keystroke` |
| `ssh` | batch of `configure`, `command`, `read`, `disconnect` |
| `node_file` | `read`, `write`, `configure_network` (Docker nodes) |
| `project_docs` | `get`, `update` (per-project README / notes) |
| `notification` | `subscribe`, `read`, `unsubscribe`, `status` |
| `tftp`, `http_client` | SSH proxy lab services |
| `query_resource`, `search_tools`, `export_topology_diagram` | resource access, tool discovery, diagram export |

### Example

```python
# Ubuntu VM with a bigger boot disk, cloud-init ISO and host CPU model
node(action="create", template_name="Ubuntu Cloud Guest", node_name="ops1", x=0, y=0,
     ram=8192, cpus=4, adapters=2, hda_disk_image="ops1-60G.qcow2",
     cdrom_image="ops1-seed.iso", options="-cpu host")

# Wire it to switch port Ethernet2, start it, wait for the login prompt
link(action="batch", connections=[{"action": "connect", "node_a": "ops1", "adapter_a": "eth0",
     "port_a": 0, "node_b": "SW1", "adapter_b": "Ethernet2", "port_b": 0}])
node(action="set", node_name="ops1", state_action="start")
console(operations=[{"type": "read", "node_name": "ops1"}])  # first access: read only
console(operations=[{"type": "send_and_wait", "node_name": "ops1",
                     "wait_pattern": "login:", "timeout": 180}])  # wait-only, sends nothing
```

## Installation

| You use | Install | Platforms |
|---|---|---|
| Claude Code or Cowork | [Claude plugin](#claude-plugin-claude-code-and-cowork) - server + skill, one install | Windows, macOS, Linux (needs uv) |
| Claude Desktop chat | [`.mcpb` extension](#claude-desktop-mcpb) - double-click | Windows, macOS |
| Claude Code without the plugin, Cursor, Windsurf | `uvx gns3-mcp` / `pip install gns3-mcp` (below) | Windows, macOS, Linux |
| A shared HTTP server | [Docker](#docker-deployment) or the [Windows service](#advanced-setup) | any |

### Claude plugin (Claude Code and Cowork)

The plugin installs the `gns3` MCP server (started locally with `uvx`) together with the `gns3-lab-automation` skill, which teaches Claude the lab workflows. Requires [uv](https://docs.astral.sh/uv/getting-started/installation/) on `PATH`.

```bash
# In Claude Code
/plugin marketplace add ChistokhinSV/gns3-mcp
/plugin install gns3-lab@gns3-mcp
```

- **Claude Code** asks for GNS3 host, port, username and password when the plugin is enabled (the password goes to the system credential store).
- **Cowork** (desktop app): **Customize > Plugins > Add > Add marketplace** → `ChistokhinSV/gns3-mcp`, add **GNS3 Lab**. Cowork does not ask for settings, so put them in `~/.gns3-mcp/.env`:
  ```bash
  GNS3_HOST=192.168.1.20
  GNS3_PORT=80
  GNS3_USER=admin
  GNS3_PASSWORD=your-password
  ```
- Chat on claude.ai doesn't start local servers - on Claude Desktop use the `.mcpb` below.

Empty plugin settings fall back to environment variables, then `./.env`, then `~/.gns3-mcp/.env` (or `GNS3_MCP_ENV_FILE`). Details: [plugin/README.md](plugin/README.md).

### Quick Start (Claude Code without the plugin)

**Prerequisites:**
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

### Claude Desktop (.mcpb)

The `.mcpb` is an [MCP Bundle](https://github.com/modelcontextprotocol/mcpb) (manifest 0.4, uv runtime): it holds only the source, and Claude Desktop installs the Python dependencies with its own uv on first start (allow ~30 s). Windows and macOS.

1. Download `mcp-server.mcpb` from [Releases](https://github.com/ChistokhinSV/gns3-mcp/releases), or build it: `just build` (creates `mcp-server\mcp-server.mcpb`)
2. **Install**: double-click it, drag it into Claude Desktop, or **Settings > Extensions > Advanced settings > Install Extension…**
3. **Enter credentials** when the installer asks: GNS3 host, GNS3 port, username, password.
   Change them later in Settings > Extensions > GNS3 Lab Controller. The password is passed to the server as an environment variable, never on the command line.
4. **Check logs** if issues occur:
   ```
   Windows: %APPDATA%\Claude\logs\mcp-server-GNS3 Lab Controller.log
   macOS:   ~/Library/Logs/Claude/mcp-server-GNS3 Lab Controller.log
   ```

> The Claude directory no longer lists `.mcpb` extensions; install from the file. For Claude Code and Cowork use the plugin instead.

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
# Test GNS3 server connectivity (no auth needed for this endpoint)
curl http://192.168.1.20:80/v3/version

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
- **Stale console sessions after a GNS3 restart**: `gns3_connection(action="reconnect")`
- **Node change "not applied by GNS3"**: the key is wrong for that node type or misplaced - check `query_resource("nodes://<project_id>/<node_id>")`

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
   claude mcp add --transport http gns3-mcp http://127.0.0.1:8100/mcp --scope user `
     --header "MCP_API_KEY: your-random-token-here"
   ```

3. Start server (in separate terminal):
   ```powershell
   gns3-mcp --transport http --http-port 8100
   ```

**Note**: `MCP_API_KEY` is required for HTTP/SSE transport - the server refuses to start without it. Every HTTP entry point checks it (`gns3-mcp`, Docker, `server.cmd install`, `python -m gns3_mcp.server.main`). `GET /health` needs no key.

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

# Service from the local checkout (.venv, picks up code changes on restart)
.\server.cmd dev-install
.\server.cmd dev-reinstall

# Remove service
.\server.cmd uninstall

# Development mode (direct run, no service)
.\server.cmd run
```

After restarting the service, reconnect the MCP client (Claude Code: `/mcp` > gns3-mcp > Reconnect).

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

# Run directly (STDIO mode, reads .env from the current directory)
python gns3_mcp\cli.py

# Or add to Claude Code (project-scoped)
claude mcp add --transport stdio gns3-mcp --scope project -- python "C:\full\path\to\gns3_mcp\cli.py"
```

> Keep the password in `.env` rather than `--password`: command-line arguments are visible to other processes.

**Quality checks and tests:**
```powershell
just check                                  # lint, format, type check, tests, version + changelog
python -m pytest tests\unit -q              # unit tests only
just bump minor                             # bump version in all three version files
```

**Build .mcpb package:**
```powershell
just build
# Creates: mcp-server\mcp-server.mcpb
```

**Release:** push a `vX.Y.Z` tag - GitHub Actions publish PyPI, the `.mcpb` GitHub release and the Docker Hub image.

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
MCP_API_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
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

For **Claude Code** (HTTP mode, key from `.env`):
```powershell
claude mcp add --transport http gns3-mcp http://localhost:8000/mcp --scope user `
  --header "MCP_API_KEY: your-random-token-here"
```

For **Claude Desktop**, use the `.mcpb` package (STDIO) instead - see Installation.

### Using Docker Run (without compose)

```bash
docker run -d \
  --name gns3-mcp-server \
  -p 8000:8000 \
  -e GNS3_HOST=192.168.1.20 \
  -e GNS3_PORT=80 \
  -e GNS3_USER=admin \
  -e GNS3_PASSWORD=your-password \
  -e MCP_API_KEY=your-random-token-here \
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
| `MCP_API_KEY` | Yes | - | Key clients send in the `MCP_API_KEY` header; container exits without it |
| `HTTP_PORT` | No | `8000` | MCP server port |
| `LOG_LEVEL` | No | `INFO` | Logging level |
| `GNS3_USE_HTTPS` | No | `false` | Use HTTPS for GNS3 |
| `GNS3_VERIFY_SSL` | No | `true` | Verify SSL certs |

See [.env.example](.env.example) for complete list.

### Architecture

The Docker deployment includes two containers:

1. **gns3-mcp** - Main MCP server (port 8000, endpoint `/mcp`)
   - Provides MCP protocol access to GNS3
   - Streamable HTTP transport, `MCP_API_KEY` header auth; `GET /health` open for the healthcheck
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
- **[plugin/](plugin/README.md)** - Claude plugin for Claude Code and Cowork: server + `gns3-lab-automation` skill
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - SSH proxy deployment instructions
- **[PORTABLE_SETUP.md](PORTABLE_SETUP.md)** - Windows service setup
- **[ERROR_CODES.md](ERROR_CODES.md)** - Error codes returned by tools
- **[docs/architecture/](docs/architecture/)** - Architecture documentation and C4 diagrams

## License

MIT License

## Author

Sergei Chistokhin (Sergei@Chistokhin.com)
