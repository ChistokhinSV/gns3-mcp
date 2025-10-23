# GNS3 MCP Server Testing

Test infrastructure for the GNS3 MCP server.

## Test Script

`test_mcp_server.py` - Comprehensive test suite for all MCP tools

### Usage

```bash
python test_mcp_server.py --password YOUR_PASSWORD --test-node "Alpine-Test"
```

### Options

- `--host` - GNS3 server host (default: localhost)
- `--port` - GNS3 server port (default: 80)
- `--username` - GNS3 username (default: admin)
- `--password` - GNS3 password (required)
- `--test-node` - Node name to test console operations (required)

### What It Tests

1. **Project Operations**
   - List projects

2. **Node Operations**
   - List nodes
   - Get node details

3. **Console Operations**
   - Connect to console
   - Read console output
   - Send data to console
   - Read console diff
   - List active sessions
   - Disconnect console

## Test Device Setup

### Option 1: Alpine Linux (Recommended)

Alpine Linux is lightweight and perfect for testing console operations.

1. **Download Alpine virt image**:
   - Download from: https://alpinelinux.org/downloads/
   - Get "VIRTUAL" x86_64 ISO

2. **Create GNS3 template**:
   - In GNS3: Edit → Preferences → QEMU → QEMU VMs → New
   - Name: "Alpine-Test"
   - RAM: 256 MB
   - Disk: 512 MB
   - Add CDROM: Select downloaded Alpine ISO

3. **Configure for testing**:
   - Start node in GNS3
   - Login: root (no password)
   - Run: `setup-alpine` (minimal setup)
   - Enable console: Already enabled by default

4. **Test characteristics**:
   - Boot time: ~5 seconds
   - Login prompt: `localhost login:`
   - Shell prompt: `localhost:~#`
   - Perfect for automated testing

### Option 2: MikroTik CHR (Current)

Your existing MikroTik CHR node works but has complexity:
- First-time password setup required
- License prompt on first login
- ASCII art banner (slows display)

**Simplify for testing**:
1. Complete initial setup manually
2. Set password to known value
3. Disable license prompt: Configure → System → Set `show-license` to `no`

### Option 3: Tiny Core Linux

Extremely lightweight alternative:
- Download: http://tinycorelinux.net/downloads.html
- CorePlus ISO recommended
- RAM: 128 MB
- Very fast boot

### Test Device Requirements

Good test device should have:
- Fast boot time (<10 seconds)
- Simple login (single username, known password)
- No interactive prompts on first login
- Stable console output
- UTF-8 support

## Automated Testing Workflow

### Manual Testing via Claude Desktop

1. Open project: "list_projects" → "open_project"
2. Find test node: "list_nodes"
3. Connect: "connect_console(Alpine-Test)"
4. Test read: "read_console"
5. Test send: "send_console(session_id, '\\n')"
6. Test diff: "read_console_diff"
7. Cleanup: "disconnect_console"

### Scripted Testing

```bash
# Run full test suite
python tests/test_mcp_server.py \
  --password admin \
  --test-node "Alpine-Test"

# Test against remote GNS3
python tests/test_mcp_server.py \
  --host 192.168.1.20 \
  --password admin \
  --test-node "Alpine-Test"
```

## Troubleshooting

### Console Not Responding

1. Check node is started: "list_nodes"
2. Verify console type: "get_node_details(node_name)"
3. Wait 5-10 seconds after node start
4. Try reconnecting

### Empty Console Output

- Some devices need a keystroke to show prompt
- Send newline: "send_console(session_id, '\\n')"
- Wait 1 second, then read_console_diff

### Session Timeout

- Sessions expire after 30 minutes
- Always disconnect when done
- Check active sessions: "list_console_sessions"

## CI/CD Integration

Future enhancement: Run tests automatically on commits

```yaml
# Example GitHub Actions workflow
name: Test GNS3 MCP
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run MCP tests
        run: |
          python -m venv venv
          source venv/bin/activate
          pip install -r requirements.txt
          python tests/test_mcp_server.py \
            --host ${{ secrets.GNS3_HOST }} \
            --password ${{ secrets.GNS3_PASSWORD }} \
            --test-node "Alpine-Test"
```
