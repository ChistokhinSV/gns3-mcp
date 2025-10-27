# GNS3 SSH Proxy Service

FastAPI service for SSH automation using Netmiko with dual storage architecture and proxy discovery.

## Features

- **Dual Storage System**:
  - Continuous buffer (real-time stream of all output)
  - Command history (per-command audit trail with searchable jobs)
- **Proxy Discovery** (v0.2.0+):
  - Automatic discovery of lab proxies via Docker API
  - Main proxy can discover all lab proxies in GNS3 projects
  - Requires `/var/run/docker.sock` mount on main proxy
- **Diagnostic Tools** (v0.2.1+):
  - Network diagnostics: ping, traceroute, ip, ss, netstat
  - DNS tools: dig, nslookup
  - HTTP client: curl
  - Automation: ansible-core, python3, bash
  - Shared directory: `/opt/gns3-ssh-proxy/` for scripts/playbooks exchange
- **Adaptive Async Execution**: Commands return immediately or poll based on execution time
- **Netmiko Integration**: Full support for 200+ network device types
- **Interactive Prompts**: Handle Y/N confirmations, password prompts, etc.
- **Long-Running Commands**: Support for 15+ minute installations with proper timeout handling
- **Error Detection**: Intelligent SSH connection error classification with helpful suggestions

## Architecture

```
MCP Server (main.py)          SSH Proxy (FastAPI)          Network Devices
    |                              |                             |
    | HTTP requests (port 8022)    |                             |
    |----------------------------->|                             |
    |                              | SSH connections (Netmiko)   |
    |                              |---------------------------->|
    |                              |                             |
    |<-----------------------------|                             |
    | JSON responses               |                             |

Storage:
  - Buffer: Continuous stream (10MB max)
  - History: Job records with full output + metadata
```

## Quick Start

### 1. Build Docker Image

```bash
cd ssh-proxy
docker build -t chistokhinsv/gns3-ssh-proxy:v0.2.1 .
```

### 2. Deploy with Docker Compose (Recommended)

#### Main Proxy on GNS3 Host:
```bash
# Create .env file with GNS3 credentials
cp .env.example .env
# Edit .env and set GNS3_PASSWORD

# Start main proxy with discovery enabled
docker-compose up -d gns3-ssh-proxy-main
```

#### Or Use Docker Run:

**Lab Proxy (Inside GNS3):**
```bash
docker run -d \
  --name gns3-ssh-proxy \
  --network host \
  --restart unless-stopped \
  -v /opt/gns3-ssh-proxy:/opt/gns3-ssh-proxy \
  chistokhinsv/gns3-ssh-proxy:v0.2.1
```

**Main Proxy (On GNS3 Host, with Discovery):**
```bash
docker run -d \
  --name gns3-ssh-proxy-main \
  --network host \
  --restart unless-stopped \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  -v /opt/gns3-ssh-proxy:/opt/gns3-ssh-proxy \
  -e GNS3_HOST=localhost \
  -e GNS3_PORT=80 \
  -e GNS3_USERNAME=admin \
  -e GNS3_PASSWORD=yourpassword \
  chistokhinsv/gns3-ssh-proxy:v0.2.1
```

### 3. Verify

```bash
# Check health
curl http://localhost:8022/health

# Test proxy discovery (main proxy only)
curl http://localhost:8022/proxy/registry
```

## API Endpoints

### Session Management
- **POST /ssh/configure** - Create/recreate SSH session
- **GET /ssh/status/{node_name}** - Check session status
- **POST /ssh/cleanup** - Clean orphaned/all sessions

### Command Execution
- **POST /ssh/send_command** - Execute show command (adaptive async)
- **POST /ssh/send_config_set** - Send configuration commands

### Data Retrieval
- **GET /ssh/buffer/{node_name}** - Read continuous buffer (diff/last_page/num_pages/all)
- **GET /ssh/history/{node_name}** - List command history
- **GET /ssh/history/{node_name}/{job_id}** - Get specific command output
- **GET /ssh/job/{job_id}** - Poll job status (async commands)

### Proxy Discovery (v0.2.0+)
- **GET /proxy/registry** - Get registry of all discovered lab proxies
  - Only works on main proxy (with Docker socket mounted)
  - Returns empty list on lab proxies

## Usage Example

### Via MCP Tools (Recommended)

```python
# 1. Use console to enable SSH
send_console('R1', 'configure terminal\n')
send_console('R1', 'username admin privilege 15 secret cisco123\n')
send_console('R1', 'crypto key generate rsa modulus 2048\n')
send_console('R1', 'ip ssh version 2\n')
send_console('R1', 'end\n')

# 2. Configure SSH session
configure_ssh('R1', {
    'device_type': 'cisco_ios',
    'host': '10.10.10.1',
    'username': 'admin',
    'password': 'cisco123'
})

# 3. Execute commands
ssh_send_command('R1', 'show version')

# 4. View history
ssh_get_history('R1', limit=10)
```

### Via Direct API

```bash
# Configure session
curl -X POST http://localhost:8022/ssh/configure \
  -H "Content-Type: application/json" \
  -d '{
    "node_name": "R1",
    "device": {
      "device_type": "cisco_ios",
      "host": "10.10.10.1",
      "username": "admin",
      "password": "cisco123"
    },
    "persist": true
  }'

# Send command
curl -X POST http://localhost:8022/ssh/send_command \
  -H "Content-Type: application/json" \
  -d '{
    "node_name": "R1",
    "command": "show ip interface brief",
    "wait_timeout": 30
  }'

# Get history
curl http://localhost:8022/ssh/history/R1?limit=10
```

## Session Management (v0.1.6)

### 30-Minute Session TTL

Sessions automatically expire after 30 minutes of inactivity to prevent stale connections:

- **Activity Tracking**: `last_activity` timestamp updated on every operation
  - SSH command execution (`send_command`, `send_config_set`)
  - Buffer reads (`read_buffer`)
  - Session configuration (`configure_ssh` with reuse)

- **Automatic Expiry**: Sessions exceeding 30-minute TTL are detected and removed
  - Happens during next `configure_ssh()` call
  - New connection automatically created
  - No manual intervention required

- **Manual Override**: Use `force_recreate: true` to force new session creation
  ```json
  {
    "node_name": "R1",
    "device": {...},
    "force_recreate": true  // Forces new session even if one exists
  }
  ```

### Session Health Checks

Before reusing existing sessions, health checks detect stale/closed connections:

1. **TTL Check**: Verify session not expired (30min)
2. **Connection Check**: Test if SSH socket still alive
   - Uses Netmiko `is_alive()` if available (Netmiko 4.0+)
   - Falls back to lightweight empty command test
3. **Auto-Recreation**: Stale sessions automatically replaced with fresh connections

### Stale Session Recovery

If commands fail with "Socket is closed" errors:

1. **Auto-Cleanup**: Stale session immediately removed from manager
2. **Error Response**: Clear error message with suggested action
   ```json
   {
     "completed": false,
     "error": "SSH session closed...",
     "error_code": "SSH_DISCONNECTED",
     "suggested_action": "Session was stale. Reconnect with ssh_configure()..."
   }
   ```
3. **Reconnect**: Simply call `configure_ssh()` again to create fresh session

## Error Handling

SSH connection failures provide detailed error classification:

- **authentication_failed**: Wrong password → Suggests using console to configure SSH
- **connection_refused**: SSH not enabled → Provides SSH enabling commands
- **timeout**: Connection timeout → Suggests checking IP/connectivity
- **host_unreachable**: Network issue → Recommends verifying GNS3 project/node status

Example error response:
```json
{
  "error": "SSH authentication failed",
  "ssh_connection_error": {
    "error_type": "authentication_failed",
    "error": "SSH authentication failed",
    "details": "Permission denied (publickey,password)",
    "suggestion": "Use console tools to configure SSH access first:\n1. send_console..."
  }
}
```

## Environment Variables

See `.env.example` for configuration options:

- `API_PORT`: API port (default: 8022)
- `LOG_LEVEL`: Logging level (default: INFO)
- `MAX_BUFFER_SIZE`: Buffer size limit (default: 10MB)
- `TRIM_BUFFER_SIZE`: Buffer trim size (default: 5MB)
- `MAX_HISTORY_JOBS`: Max jobs per session (default: 1000)

## Diagnostic Tools (v0.2.1+)

The SSH proxy container includes diagnostic tools for network troubleshooting and automation:

### Network Diagnostics
- `ping` - Test network connectivity
- `traceroute` - Trace network path to destination
- `ip` - Advanced IP routing and interface management
- `ss` - Socket statistics
- `netstat` - Network statistics

### DNS Tools
- `dig` - DNS lookup utility
- `nslookup` - Query DNS servers

### HTTP Client
- `curl` - Transfer data with URLs (also used for healthchecks)

### Automation
- `ansible-core` - Network automation engine
- `python3` (3.13) - Python interpreter
- `bash` - Shell scripting

### Shared Directory

The `/opt/gns3-ssh-proxy/` directory is mounted from the host, allowing you to:
- Share ansible playbooks between host and container
- Exchange scripts and configuration files
- Store troubleshooting data persistently

**Example - Run ansible playbook from container:**
```bash
# On GNS3 host: place playbook in /opt/gns3-ssh-proxy/
sudo cp my-playbook.yml /opt/gns3-ssh-proxy/

# Inside container: run playbook
docker exec -it gns3-ssh-proxy-main bash
cd /opt/gns3-ssh-proxy
ansible-playbook my-playbook.yml -i inventory.ini
```

**Example - Network diagnostics:**
```bash
# Ping from container
docker exec gns3-ssh-proxy-main ping -c 3 10.10.10.1

# DNS lookup
docker exec gns3-ssh-proxy-main dig example.com

# Check interface configuration
docker exec gns3-ssh-proxy-main ip addr show
```

## Development

### Local Testing

```bash
# Install dependencies
pip install -r requirements.txt

# Run server
cd server
python main.py
```

### Testing with MCP

1. Ensure SSH proxy is running
2. Configure MCP server to use `SSH_PROXY_URL=http://localhost:8022`
3. Use MCP tools via Claude Desktop/Code

## Deployment

See [DEPLOYMENT.md](../DEPLOYMENT.md) for complete deployment instructions for GNS3 hosts.

## Version

Current version: **0.2.1** (Feature - Diagnostic Tools & Shared Directory)

**v0.2.1 Changes:**
- **NEW**: Network diagnostic tools (ping, traceroute, ip, ss, netstat)
- **NEW**: DNS tools (dig, nslookup)
- **NEW**: HTTP client (curl) - fixes healthcheck functionality
- **NEW**: ansible-core for network automation playbooks
- **NEW**: Shared directory `/opt/gns3-ssh-proxy/` for exchanging scripts/configs with host
- **ENHANCED**: Docker image now suitable for interactive troubleshooting and automation
- **SIZE**: Image increased by ~100-150MB to ~500-550MB total

**v0.2.0 Changes:**
- **NEW**: Proxy Discovery - Automatic discovery of lab proxies via Docker API
- **NEW**: Main proxy can discover all lab proxies in GNS3 projects
- **REQUIRES**: `/var/run/docker.sock` mount on main proxy for discovery

**v0.1.6 Changes:**
- **NEW**: 30-minute session TTL with automatic expiry detection
- **NEW**: Session health checks detect stale/closed connections before reuse
- **NEW**: Auto-cleanup on "Socket is closed" errors
- **NEW**: Structured error responses with `error_code` and `suggested_action` fields

See [CLAUDE.md](../CLAUDE.md) for full version history and changelog.
