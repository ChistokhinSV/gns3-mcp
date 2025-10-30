# GNS3 MCP HTTP Server - Windows Service Setup

This guide explains how to run the GNS3 MCP server as a Windows service for continuous HTTP access.

## Why Use HTTP Service?

**Advantages:**
- Server runs continuously in background
- Can reload code without restarting Claude Code conversation
- Independent of Claude Code process lifecycle
- Global access from any project or conversation

**When to use:**
- Development workflow with frequent code changes
- Multiple conversations needing MCP access simultaneously
- Prefer HTTP debugging tools over stdio
- Want single server instance shared across sessions

**When stdio is better:**
- Single-user desktop usage
- Simple per-conversation lifecycle
- No background process management needed
- Credentials loaded from .env automatically

## Architecture

```
Windows Service (NSSM)
  └─ Python process
      └─ start_mcp_http.py
          ├─ Loads .env configuration
          ├─ Sets up logging to mcp-http-server.log
          └─ Executes main.py with HTTP transport

HTTP Server (127.0.0.1:8100)
  └─ FastMCP Streamable HTTP
      └─ MCP protocol over HTTP at /mcp/
```

## Prerequisites

- Windows 10/11
- Python 3.11+
- NSSM (Non-Sucking Service Manager)
- Administrator access

## Installation Steps

### 1. Install NSSM

```powershell
# Install via Chocolatey (run as Administrator)
choco install nssm -y

# Verify installation
nssm --version
```

### 2. Configure Environment

Edit `.env` file with GNS3 credentials:

```bash
# GNS3 Server Configuration
GNS3_USER=admin
GNS3_PASSWORD=your-password
GNS3_HOST=192.168.1.20
GNS3_PORT=80

# Compatibility aliases (for start_mcp.py)
USER=admin
PASSWORD=your-password

# HTTP Server Configuration (for start_mcp_http.py)
HTTP_HOST=127.0.0.1
HTTP_PORT=8100
LOG_LEVEL=INFO
```

### 3. Install Service

**Run as Administrator:**

```cmd
cd "C:\HOME\1. Scripts\008. GNS3 MCP"
server.cmd install
```

The unified `server.cmd` tool will:
- ✓ Auto-create/populate venv if needed
- ✓ Install Python dependencies
- ✓ Check prerequisites (NSSM, Python, .env file)
- ✓ Remove existing service if present
- ✓ Install service with proper NSSM configuration
- ✓ Configure auto-restart on failure (5-second delay)
- ✓ Set up log rotation (10MB max size)
- ✓ Start the service automatically

**Alternative Commands:**
```cmd
server.cmd uninstall   # Remove service
server.cmd reinstall   # Reinstall service
server.cmd status      # Check service status
server.cmd             # Start server directly (no service)

### 4. Verify Service

```powershell
# Check service status
nssm status GNS3-MCP-HTTP

# View service configuration
nssm status GNS3-MCP-HTTP

# Check logs
Get-Content "C:\HOME\1. Scripts\008. GNS3 MCP\mcp-http-server.log" -Tail 50 -Wait
```

### 5. Configure Claude Code

Update `.mcp.json` to use HTTP transport:

```json
{
  "mcpServers": {
    "gns3-lab": {
      "url": "http://127.0.0.1:8100/mcp/"
    }
  }
}
```

Or configure globally:

```bash
claude mcp add gns3-lab --url http://127.0.0.1:8100/mcp/ --scope user
```

### 6. Test Connection

Start a new Claude Code conversation:

```bash
# Check MCP server status
claude mcp get gns3-lab
# Should show: Status: ✓ Connected

# List available tools
# In conversation: "List all MCP tools"
```

## Service Management

### Start/Stop/Restart

```powershell
# Start service
nssm start GNS3-MCP-HTTP

# Stop service
nssm stop GNS3-MCP-HTTP

# Restart service (e.g., after code changes)
nssm restart GNS3-MCP-HTTP
```

### Check Status

```cmd
# Quick status check with server.cmd
server.cmd status
```

Or use NSSM directly:

```powershell
# Service status
nssm status GNS3-MCP-HTTP
# Output: SERVICE_RUNNING (if running)

# Windows Services GUI
services.msc
# Find: GNS3 MCP HTTP Server
```

### View Logs

```powershell
# Tail logs in real-time
Get-Content "C:\HOME\1. Scripts\008. GNS3 MCP\mcp-http-server.log" -Tail 50 -Wait

# Open log file
notepad "C:\HOME\1. Scripts\008. GNS3 MCP\mcp-http-server.log"
```

### Restart After Code Changes

**IMPORTANT:** After modifying server code, restart the service to load changes:

```powershell
# Quick restart
nssm restart GNS3-MCP-HTTP

# Or stop → edit → start
nssm stop GNS3-MCP-HTTP
# ... edit code ...
nssm start GNS3-MCP-HTTP
```

**No need to restart Claude Code conversation** - the service runs independently!

## Troubleshooting

### Service Won't Start

**Check logs:**
```powershell
Get-Content "C:\HOME\1. Scripts\008. GNS3 MCP\mcp-http-server.log" -Tail 100
```

**Common issues:**
- ❌ `.env` file missing or incorrect credentials
  - Fix: Verify `.env` exists with USER/PASSWORD variables
- ❌ Port 8100 already in use
  - Fix: Change HTTP_PORT in `.env`, update service with `nssm edit GNS3-MCP-HTTP`
- ❌ Python not found
  - Fix: Update Python path in `install-service.ps1` and reinstall

### Service Crashes/Restarts

**Auto-restart configured:**
- Service automatically restarts after crash
- 5-second delay between restart attempts
- Check logs for error patterns

**Common crash causes:**
- Network issues connecting to GNS3 server
- Invalid GNS3 credentials
- Python dependency issues

### Can't Connect from Claude Code

**Verify service is running:**
```powershell
nssm status GNS3-MCP-HTTP
```

**Test endpoint manually:**
```powershell
# Note: /mcp/ is MCP protocol endpoint, not REST API
# Empty response is expected - it's waiting for MCP messages
curl http://127.0.0.1:8100/mcp/
```

**Check .mcp.json configuration:**
```json
{
  "mcpServers": {
    "gns3-lab": {
      "url": "http://127.0.0.1:8100/mcp/"
    }
  }
}
```

**Restart Claude Code:**
- MCP connections are established at conversation start
- Start new conversation after service restart

### Port Conflicts

**Change HTTP port:**

1. Edit `.env`:
   ```bash
   HTTP_PORT=8200  # New port
   ```

2. Restart service:
   ```powershell
   nssm restart GNS3-MCP-HTTP
   ```

3. Update `.mcp.json`:
   ```json
   {
     "mcpServers": {
       "gns3-lab": {
         "url": "http://127.0.0.1:8200/mcp/"
       }
     }
   }
   ```

## Uninstallation

**Easy uninstall with server.cmd:**

```cmd
cd "C:\HOME\1. Scripts\008. GNS3 MCP"
server.cmd uninstall
```

Or manually with NSSM:

```powershell
# Stop service
nssm stop GNS3-MCP-HTTP

# Remove service
nssm remove GNS3-MCP-HTTP confirm
```

## Files and Locations

```
C:\HOME\1. Scripts\008. GNS3 MCP\
├── mcp-server\
│   ├── start_mcp_http.py          # HTTP server wrapper (v0.38.0)
│   ├── start_mcp.py                # stdio wrapper (for Claude Code stdio mode)
│   └── server\
│       └── main.py                 # FastMCP server implementation
├── venv\                           # Virtual environment (auto-created)
├── .env                            # Configuration (gitignored)
├── .mcp.json                       # Claude Code MCP config
├── mcp-http-server.log            # Service logs
├── server.cmd                      # Unified server management tool (v0.38.0)
└── SERVICE_SETUP.md                # This file
```

## Comparison: stdio vs HTTP

| Feature | stdio (default) | HTTP Service |
|---------|----------------|--------------|
| **Lifecycle** | Per conversation | Continuous background |
| **Code reload** | Restart conversation | Restart service only |
| **Setup complexity** | Simple | Requires service setup |
| **Resource usage** | Per-conversation process | Single shared process |
| **Development** | Good for stable code | Best for active development |
| **Multi-project** | Each project spawns process | Single instance for all |
| **Debugging** | Logs in conversation | Logs in file |

## Development Workflow

**Typical development cycle with HTTP service:**

1. Edit server code in `mcp-server/server/*.py`
2. Save changes
3. Restart service: `nssm restart GNS3-MCP-HTTP`
4. Test in current Claude Code conversation (no restart needed!)
5. Check logs: `Get-Content mcp-http-server.log -Tail 50 -Wait`

**Benefits:**
- Fast iteration without restarting conversations
- Keep context and conversation history
- Test immediately after code changes
- Monitor logs in real-time

## Security Notes

- Service runs as Local System by default
- Credentials stored in `.env` (gitignored)
- HTTP endpoint bound to 127.0.0.1 (localhost only)
- No network exposure unless explicitly configured
- Logs may contain device output (review before sharing)

## Advanced Configuration

### Custom Service Account

Run service as specific user:

```powershell
nssm set GNS3-MCP-HTTP ObjectName "DOMAIN\Username" "password"
```

### Network Access

Allow network connections (use with caution):

1. Edit `.env`:
   ```bash
   HTTP_HOST=0.0.0.0  # Listen on all interfaces
   ```

2. Configure firewall:
   ```powershell
   New-NetFirewallRule -DisplayName "GNS3 MCP HTTP" -Direction Inbound -LocalPort 8100 -Protocol TCP -Action Allow
   ```

### Log Retention

Configure log rotation in `install-service.ps1`:

```powershell
# Rotate at 10MB (default)
nssm set GNS3-MCP-HTTP AppRotateBytes 10485760

# Rotate at 50MB
nssm set GNS3-MCP-HTTP AppRotateBytes 52428800
```

## Support

For issues with:
- **Service setup**: Check this document and logs
- **MCP server code**: See `CLAUDE.md` and `README.md`
- **GNS3 integration**: See `skill/SKILL.md`
- **Bug reports**: Open issue at project repository

## References

- NSSM Documentation: https://nssm.cc/usage
- FastMCP: https://github.com/anthropics/fastmcp
- MCP Protocol: https://modelcontextprotocol.io/
