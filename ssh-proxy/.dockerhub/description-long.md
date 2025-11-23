# GNS3 SSH Proxy - Network Automation Gateway

FastAPI-based proxy for SSH automation in GNS3 network labs with TFTP server and HTTP/HTTPS reverse proxy.

## 🚀 Features

### SSH Automation
- **Netmiko Integration**: 200+ device types (Cisco, Juniper, Arista, MikroTik, etc.)
- **Async Command Execution**: Non-blocking operations with job tracking
- **Dual Storage**: Continuous buffer (10MB) + command history with metadata
- **Session Management**: 4-hour TTL, health checks, automatic cleanup
- **Multi-Proxy Support**: Main proxy + lab-internal proxies for isolated networks

### TFTP Server
- **Read-Write Access**: Devices can upload/download files
- **Port**: 69/udp (standard TFTP)
- **Root Directory**: `/opt/gns3-ssh-proxy/tftp`
- **Use Cases**: Firmware updates, config backups, boot images

### HTTP/HTTPS Reverse Proxy
- **Nginx-Based**: Expose device web UIs externally
- **Self-Signed Certs**: HTTPS support for secure device connections
- **Single Entry Point**: Access multiple device ports through proxy port 8022
- **WebSocket Support**: Modern device management interfaces
- **URL Format**: `http://proxy:8022/http-proxy/{device_ip}:{port}/path`

### Network Diagnostics
- **Tools**: ping, traceroute, dig, nslookup, ss, netstat
- **Local Execution**: Run commands on proxy container
- **Automation**: Ansible-core for playbook execution

## 🔌 Ports

- **8022/tcp** - FastAPI management API
- **69/udp** - TFTP server
- **HTTP/HTTPS proxying** - Through port 8022 reverse proxy

## 📦 Quick Start

### Docker Compose

```yaml
services:
  gns3-ssh-proxy:
    image: chistokhinsv/gns3-ssh-proxy:{VERSION}
    container_name: gns3-ssh-proxy
    network_mode: host
    restart: unless-stopped
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - /opt/gns3-ssh-proxy:/opt/gns3-ssh-proxy
    environment:
      - GNS3_HOST=192.168.1.20
      - GNS3_PORT=80
      - GNS3_USER=admin
      - GNS3_PASSWORD=your_password
```

### Docker Run

```bash
docker run -d \
  --name gns3-ssh-proxy \
  --network host \
  --restart unless-stopped \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  -v /opt/gns3-ssh-proxy:/opt/gns3-ssh-proxy \
  -e GNS3_HOST=192.168.1.20 \
  -e GNS3_PORT=80 \
  -e GNS3_USER=admin \
  -e GNS3_PASSWORD=your_password \
  chistokhinsv/gns3-ssh-proxy:{VERSION}
```

## 🔧 API Endpoints

### Session Management
- `POST /ssh/configure` - Create/configure SSH session
- `GET /ssh/status/{node_name}` - Check session status
- `POST /ssh/cleanup` - Clean orphaned sessions

### Command Execution
- `POST /ssh/send_command` - Execute show command
- `POST /ssh/send_config_set` - Send configuration
- `POST /local/execute` - Execute command on proxy container

### TFTP Management
- `POST /tftp` (action: list, upload, download, delete, status)
- Manage files in TFTP directory
- Full read-write access for devices

### HTTP Reverse Proxy
- `POST /http-proxy` (action: register, unregister, list, reload)
- Dynamic device registration
- Nginx configuration management

### Data Retrieval
- `GET /ssh/buffer/{node_name}` - Read continuous buffer
- `GET /ssh/history/{node_name}` - Command history
- `GET /proxy/registry` - Discover lab proxies

### Health & Discovery
- `GET /health` - Health check endpoint
- `GET /version` - Service version
- `GET /proxy/registry` - Multi-proxy discovery

## 🐍 Python Client Example

```python
import httpx

# Configure SSH session
response = httpx.post("http://192.168.1.20:8022/ssh/configure", json={
    "node_name": "Router1",
    "device_dict": {
        "device_type": "cisco_ios",
        "host": "10.1.0.1",
        "username": "admin",
        "password": "cisco123"
    }
})

# Execute command
response = httpx.post("http://192.168.1.20:8022/ssh/send_command", json={
    "node_name": "Router1",
    "command": "show version"
})
print(response.json()["output"])

# Access device web UI through reverse proxy
ui_response = httpx.get("http://192.168.1.20:8022/http-proxy/10.1.0.1:80/")
```

## 🔐 Security Notes

- SSH credentials stored in session memory only
- No persistent credential storage
- Self-signed certs for HTTPS proxy (lab use)
- Network mode: host (requires GNS3 host access)

## 📊 Multi-Proxy Architecture

```
┌──────────────┐
│  MCP Server  │
└──────┬───────┘
       │
┌──────▼────────────┐
│   Main Proxy      │ (GNS3 Host)
│   192.168.1.20    │
└──────┬────────────┘
       │
  ┌────▼────┐   ┌─────────┐
  │ Lab     │   │  Lab    │
  │ Proxy 1 │   │ Proxy 2 │
  │ 10.1.0  │   │ 10.2.0  │
  └────┬────┘   └────┬────┘
       │             │
  ┌────▼────┐   ┌───▼─────┐
  │ Devices │   │ Devices │
  └─────────┘   └─────────┘
```

## 🧪 Testing

```bash
# Health check
curl http://localhost:8022/health

# Version check
curl http://localhost:8022/version

# TFTP file list
curl -X POST http://localhost:8022/tftp -H "Content-Type: application/json" \
  -d '{"action": "list"}'

# HTTP reverse proxy device list
curl -X POST http://localhost:8022/http-proxy -H "Content-Type: application/json" \
  -d '{"action": "list"}'
```

## 📚 Documentation

- [GitHub Repository](https://github.com/ChistokhinSV/gns3-mcp)
- [SSH Proxy README](https://github.com/ChistokhinSV/gns3-mcp/tree/master/ssh-proxy)
- [API Documentation](https://github.com/ChistokhinSV/gns3-mcp/tree/master/ssh-proxy#api-endpoints)

## 🏷️ Version

**{VERSION}** - Auto-updated by GitHub Actions

## 📝 License

MIT License - See [LICENSE](https://github.com/ChistokhinSV/gns3-mcp/blob/master/LICENSE) for details

## 🤝 Contributing

Contributions welcome! Please read the contributing guidelines before submitting PRs.

## 🐛 Issues & Support

Report issues at: https://github.com/ChistokhinSV/gns3-mcp/issues
