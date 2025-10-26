# GNS3 SSH Proxy Service

FastAPI service for SSH automation using Netmiko with dual storage architecture.

## Features

- **Dual Storage System**:
  - Continuous buffer (real-time stream of all output)
  - Command history (per-command audit trail with searchable jobs)
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
docker build -t chistokhinsv/gns3-ssh-proxy:v0.1.1 .
```

### 2. Run Container

```bash
docker run -d \
  --name gns3-ssh-proxy \
  --network host \
  --restart unless-stopped \
  chistokhinsv/gns3-ssh-proxy:v0.1.1
```

### 3. Verify

```bash
curl http://localhost:8022/health
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

Current version: **0.1.6** (Feature - Session Management & Stale Session Recovery)

**v0.1.6 Changes:**
- **NEW**: 30-minute session TTL with automatic expiry detection
- **NEW**: Session health checks detect stale/closed connections before reuse
- **NEW**: Auto-cleanup on "Socket is closed" errors
- **NEW**: Structured error responses with `error_code` and `suggested_action` fields
- **ENHANCED**: `last_activity` timestamp updated on all operations
- **ENHANCED**: Better error messages for timeout and socket closure errors

**Previous:** v0.1.5 - Added `/version` endpoint for API monitoring

See [CLAUDE.md](../CLAUDE.md) for full version history and changelog.
