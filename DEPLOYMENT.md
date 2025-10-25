# SSH Proxy Deployment Guide

Deployment instructions for GNS3 SSH Proxy service.

## Prerequisites

- Docker Desktop (for building)
- Docker Hub account (chistokhinsv)
- SSH access to GNS3 host(s)
- GNS3 server running on target host

## Build & Deploy Workflow

### 1. Build Docker Image

```bash
cd ssh-proxy
docker build -t chistokhinsv/gns3-ssh-proxy:v0.1.0 .
```

### 2. Push to Docker Hub

```bash
# Login (already done for chistokhinsv)
docker login -u chistokhinsv

# Push image
docker push chistokhinsv/gns3-ssh-proxy:v0.1.0
```

### 3. Deploy to GNS3 Host

**Option A: Pull from Docker Hub**
```bash
# SSH to GNS3 server
ssh gns3

# Pull image
docker pull chistokhinsv/gns3-ssh-proxy:v0.1.0

# Run container with --network host
docker run -d \
  --name gns3-ssh-proxy \
  --network host \
  --restart unless-stopped \
  -e API_PORT=8022 \
  -e LOG_LEVEL=INFO \
  chistokhinsv/gns3-ssh-proxy:v0.1.0

# Verify
curl http://localhost:8022/health
docker logs -f gns3-ssh-proxy
```

**Option B: Build Directly on GNS3 Host** (faster, recommended)
```bash
# On local machine - create tarball
cd ssh-proxy
tar czf /tmp/ssh-proxy.tar.gz Dockerfile requirements.txt server/

# Copy to GNS3 host
scp /tmp/ssh-proxy.tar.gz gns3:/tmp/

# On GNS3 host - extract and build
ssh gns3
cd /tmp && tar xzf ssh-proxy.tar.gz
docker build -t chistokhinsv/gns3-ssh-proxy:v0.1.0 .

# Run container
docker run -d \
  --name gns3-ssh-proxy \
  --network host \
  --restart unless-stopped \
  -e API_PORT=8022 \
  -e LOG_LEVEL=INFO \
  chistokhinsv/gns3-ssh-proxy:v0.1.0

# Verify
curl http://localhost:8022/health
```

## Network Mode: host

**CRITICAL**: The container MUST use `--network host` to access GNS3 lab devices.

- Lab devices have isolated network addresses (e.g., 10.10.10.0/24)
- Only accessible from GNS3 host's network stack
- Bridge/NAT modes won't work

## Deploy to Multiple GNS3 Servers

```bash
# Server 1
ssh gns3-server1
docker pull chistokhinsv/gns3-ssh-proxy:v0.1.0
docker run -d --name gns3-ssh-proxy --network host --restart unless-stopped chistokhinsv/gns3-ssh-proxy:v0.1.0

# Server 2
ssh gns3-server2
docker pull chistokhinsv/gns3-ssh-proxy:v0.1.0
docker run -d --name gns3-ssh-proxy --network host --restart unless-stopped chistokhinsv/gns3-ssh-proxy:v0.1.0
```

## Container Management

```bash
# Check status
docker ps | grep gns3-ssh-proxy

# View logs
docker logs -f gns3-ssh-proxy

# Stop container
docker stop gns3-ssh-proxy

# Restart container
docker restart gns3-ssh-proxy

# Remove container
docker rm -f gns3-ssh-proxy
```

## Updating to New Version

```bash
# 1. Build new version locally
cd ssh-proxy
docker build -t chistokhinsv/gns3-ssh-proxy:v0.2.0 .

# 2. Push to Docker Hub
docker push chistokhinsv/gns3-ssh-proxy:v0.2.0

# 3. Update on GNS3 host
ssh gns3
docker stop gns3-ssh-proxy
docker rm gns3-ssh-proxy
docker pull chistokhinsv/gns3-ssh-proxy:v0.2.0
docker run -d --name gns3-ssh-proxy --network host --restart unless-stopped chistokhinsv/gns3-ssh-proxy:v0.2.0
```

## Troubleshooting

### Container Won't Start

```bash
# Check Docker logs
docker logs gns3-ssh-proxy

# Check if port 8022 is available
netstat -tuln | grep 8022

# Kill process using port 8022
lsof -i:8022
kill <PID>
```

### SSH Connection Fails

1. **Verify GNS3 lab is running**:
   ```bash
   # From GNS3 host
   ping 10.10.10.1
   ```

2. **Check device SSH config** (use console tools):
   ```
   send_console('R1', 'show ip ssh\n')
   send_console('R1', 'show running-config | include username\n')
   ```

3. **Test SSH directly**:
   ```bash
   # From GNS3 host
   ssh admin@10.10.10.1
   ```

### API Not Responding

```bash
# Check container is running
docker ps | grep gns3-ssh-proxy

# Check health endpoint
curl http://localhost:8022/health

# Check API from MCP server
curl http://<GNS3_HOST>:8022/health
```

## MCP Server Configuration

Update MCP server to point to SSH proxy:

```bash
# In .env or environment
export SSH_PROXY_URL=http://192.168.1.20:8022

# Or in code
SSH_PROXY_URL = os.getenv("SSH_PROXY_URL", "http://localhost:8022")
```

## Security Considerations

- SSH proxy has **no authentication** (intended for internal GNS3 network)
- Runs on port 8022 (not exposed externally)
- Credentials stored in memory only (not persisted to disk)
- Use GNS3 host firewall to restrict access

## Port Reference

- **8022**: SSH proxy API (FastAPI)
- **80/3080**: GNS3 server API
- **22**: SSH to devices (from proxy)
- **5000+**: Telnet consoles (for console tools)

## Version Management

Tag images with version numbers:

```bash
# Build with version
docker build -t chistokhinsv/gns3-ssh-proxy:v0.1.0 .
docker build -t chistokhinsv/gns3-ssh-proxy:latest .

# Push both tags
docker push chistokhinsv/gns3-ssh-proxy:v0.1.0
docker push chistokhinsv/gns3-ssh-proxy:latest
```

## Complete Example

```bash
# ========================================
# On Development Machine
# ========================================

# 1. Build image
cd "C:\HOME\1. Scripts\008. GNS3 MCP\ssh-proxy"
docker build -t chistokhinsv/gns3-ssh-proxy:v0.1.0 .

# 2. Push to Docker Hub
docker push chistokhinsv/gns3-ssh-proxy:v0.1.0

# ========================================
# On GNS3 Host
# ========================================

# 3. SSH to GNS3
ssh gns3

# 4. Pull and run
docker pull chistokhinsv/gns3-ssh-proxy:v0.1.0
docker run -d \
  --name gns3-ssh-proxy \
  --network host \
  --restart unless-stopped \
  chistokhinsv/gns3-ssh-proxy:v0.1.0

# 5. Verify
curl http://localhost:8022/health
docker logs gns3-ssh-proxy

# ========================================
# On MCP Client (Claude Desktop/Code)
# ========================================

# 6. Test with MCP tools
configure_ssh('R1', {
    'device_type': 'cisco_ios',
    'host': '10.10.10.1',
    'username': 'admin',
    'password': 'cisco123'
})

ssh_send_command('R1', 'show version')
```

## Success Criteria

- [ ] Container runs without errors
- [ ] Health check returns `{"status": "healthy"}`
- [ ] Can configure SSH session via MCP tools
- [ ] Can execute commands and retrieve output
- [ ] Command history tracked correctly
- [ ] Sessions persist across MCP server restarts (container restart loses sessions)
