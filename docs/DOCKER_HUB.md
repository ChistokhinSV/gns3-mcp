# GNS3 MCP Server

[![Docker Image Version](https://img.shields.io/docker/v/chistokhinsv/gns3-mcp)](https://hub.docker.com/r/chistokhinsv/gns3-mcp)
[![Docker Image Size](https://img.shields.io/docker/image-size/chistokhinsv/gns3-mcp)](https://hub.docker.com/r/chistokhinsv/gns3-mcp)
[![Docker Pulls](https://img.shields.io/docker/pulls/chistokhinsv/gns3-mcp)](https://hub.docker.com/r/chistokhinsv/gns3-mcp)

MCP (Model Context Protocol) server providing programmatic access to GNS3 network simulation labs. Enables AI assistants like Claude to interact with GNS3 projects, manage nodes, configure devices via console/SSH, and automate network topology operations.

## Features

- **12 CRUD-style MCP tools** for GNS3 lab management
- **25+ resources** for project/node/link/session data
- **Console access** - Telnet to device consoles for configuration
- **SSH access** - Execute commands on network devices (via companion ssh-proxy)
- **Topology management** - Create, modify, and visualize network diagrams
- **Project documentation** - Integrated README notes for IP schemes and credentials
- **Multi-proxy support** - Isolated network access for complex topologies

## Quick Start

### Using Docker Compose (Recommended)

```bash
# 1. Clone or download docker-compose.yml
curl -O https://raw.githubusercontent.com/chistokhinsv/gns3-mcp/master/docker-compose.yml

# 2. Create .env file with your GNS3 credentials
cat > .env <<EOF
GNS3_HOST=192.168.1.20
GNS3_PORT=80
GNS3_USER=admin
GNS3_PASSWORD=your-password
HTTP_PORT=8000
LOG_LEVEL=INFO
EOF

# 3. Start both MCP server and SSH proxy
docker-compose up -d

# 4. Verify services are running
curl http://localhost:8000/health
curl http://localhost:8022/health

# 5. View logs
docker-compose logs -f
```

### Using Docker Run

```bash
docker run -d \
  --name gns3-mcp-server \
  -p 8000:8000 \
  -e GNS3_HOST=192.168.1.20 \
  -e GNS3_PORT=80 \
  -e GNS3_USER=admin \
  -e GNS3_PASSWORD=your-password \
  -e HTTP_HOST=0.0.0.0 \
  -e HTTP_PORT=8000 \
  -e LOG_LEVEL=INFO \
  --restart unless-stopped \
  chistokhinsv/gns3-mcp:latest
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GNS3_HOST` | Yes | - | GNS3 server IP address or hostname |
| `GNS3_PORT` | No | `80` | GNS3 API port (use 443 for HTTPS) |
| `GNS3_USER` | Yes | - | GNS3 username |
| `GNS3_PASSWORD` | Yes | - | GNS3 password |
| `GNS3_USE_HTTPS` | No | `false` | Use HTTPS for GNS3 API |
| `GNS3_VERIFY_SSL` | No | `true` | Verify SSL certificates |
| `HTTP_HOST` | No | `0.0.0.0` | MCP server listen address |
| `HTTP_PORT` | No | `8000` | MCP server port |
| `LOG_LEVEL` | No | `INFO` | Logging level (DEBUG/INFO/WARNING/ERROR) |
| `MCP_API_KEY` | No | auto | API key for MCP authentication |

## Architecture

The GNS3 MCP ecosystem consists of two containers:

1. **gns3-mcp** (this image) - Main MCP server providing GNS3 API access
   - Port: 8000 (HTTP/SSE transport)
   - Network: Bridge mode
   - Protocols: MCP over HTTP

2. **gns3-ssh-proxy** (companion image) - SSH gateway for lab devices
   - Port: 8022 (FastAPI)
   - Network: Host mode (required for isolated lab networks)
   - Protocols: Netmiko SSH automation

## Usage with Claude Desktop

Add to Claude Desktop MCP configuration:

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

## Available Tools

### Project Management
- `project()` - List, open, create, close projects
- `project_docs()` - Get/update project README notes

### Node Operations
- `node()` - List, create, delete, configure nodes (CRUD + wildcards)
- `node_file()` - Read/write files in Docker nodes

### Network Connections
- `link()` - List, connect, disconnect links (batch operations)

### Device Access
- `console()` - Send commands, read output via telnet console
- `ssh()` - Execute commands via SSH (requires ssh-proxy)

### Topology & Visualization
- `drawing()` - Create/update/delete topology drawings
- `export_topology_diagram()` - Export topology to SVG/PNG

### Utilities
- `gns3_connection()` - Check/retry GNS3 server connection
- `search_tools()` - Discover tools by category/capability
- `query_resource()` - Universal resource access

## Resources

Access GNS3 data via MCP resources:
- `projects://` - All projects
- `nodes://{project_id}/` - Nodes in project
- `links://{project_id}/` - Network links
- `sessions://console/` - Active console sessions
- `sessions://ssh/` - Active SSH sessions
- `topology://{project_id}` - Topology diagram

## Health Checks

The container includes built-in health checks:

```bash
# Check MCP server health
curl http://localhost:8000/health

# Check container status
docker ps --filter name=gns3-mcp-server
```

## Logging

View logs for troubleshooting:

```bash
# Follow logs in real-time
docker logs -f gns3-mcp-server

# Last 100 lines
docker logs --tail 100 gns3-mcp-server

# With timestamps
docker logs -t gns3-mcp-server
```

## Networking Notes

### MCP Server (Bridge Mode)
- Uses standard Docker bridge networking
- Accessible on host via port mapping (8000:8000)
- Can communicate with GNS3 server on LAN

### SSH Proxy (Host Mode Required)
- **MUST** use `network_mode: host` to access lab devices
- Lab devices use isolated network addresses (10.x.x.x/24)
- Only accessible from GNS3 host's network stack
- Bridge/NAT modes will NOT work

## Security Considerations

- Container has **no built-in authentication** (use firewalls/VPNs)
- GNS3 credentials stored as environment variables
- MCP_API_KEY can be set for basic authentication
- Recommended for internal/lab networks only
- Do not expose port 8000 to public internet

## Troubleshooting

### Container Won't Start
```bash
# Check logs for errors
docker logs gns3-mcp-server

# Verify environment variables
docker inspect gns3-mcp-server | grep -A 20 Env
```

### Cannot Connect to GNS3
```bash
# Test GNS3 API from container
docker exec gns3-mcp-server curl -v http://${GNS3_HOST}:${GNS3_PORT}/v3/version

# Check network connectivity
docker exec gns3-mcp-server ping -c 3 ${GNS3_HOST}
```

### Health Check Failing
```bash
# Manual health check
curl -v http://localhost:8000/health

# Check if FastMCP provides health endpoint
docker exec gns3-mcp-server curl -v http://localhost:8000/
```

## Version History

- **v0.49.0** - Docker support, multi-platform builds
- **v0.48.0** - List action integration in CRUD tools
- **v0.47.0** - Aggressive tool consolidation (32→15 tools)
- **v0.46.0** - Resource query tools for Claude Desktop
- **v0.40.0** - Wildcard bulk operations, topology report

## Links

- **GitHub**: https://github.com/chistokhinsv/gns3-mcp
- **Documentation**: https://github.com/chistokhinsv/gns3-mcp/blob/master/README.md
- **Issues**: https://github.com/chistokhinsv/gns3-mcp/issues
- **GNS3 Docs**: https://docs.gns3.com/

## License

MIT License - see repository for full details

## Support

For issues, questions, or contributions:
- GitHub Issues: https://github.com/chistokhinsv/gns3-mcp/issues
- GNS3 Community: https://gns3.com/community
