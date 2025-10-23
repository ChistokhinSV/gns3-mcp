# Alpine Linux Test Device Setup for GNS3

Complete guide to setting up Alpine Linux as a test device for GNS3 MCP server testing.

## Why Alpine Linux?

- **Lightweight**: 130 MB ISO, 256 MB RAM
- **Fast**: 5-second boot time
- **Simple**: Single root login, no password by default
- **Stable**: Perfect for automated console testing
- **No cruft**: No license prompts or setup wizards

## Download Alpine Linux

1. Visit: https://alpinelinux.org/downloads/
2. Download: **VIRTUAL** → **x86_64** → **STANDARD** ISO
3. Current version: alpine-virt-3.20.3-x86_64.iso (~50 MB)
4. Save to: `C:\DOWNLOAD_TEMP\alpine-virt-3.20.3-x86_64.iso`

## Create GNS3 Template

### Step 1: Add QEMU VM

1. Open GNS3
2. **Edit** → **Preferences**
3. **QEMU** → **QEMU VMs** → **New**

### Step 2: Configure VM

**VM Name**: `Alpine Linux Test`

**RAM**: `256 MB`

**Disk image**:
- Click **New Image**
- Name: `alpine-test.qcow2`
- Size: `512 MB`
- Format: `qcow2`

**CD/DVD**:
- Enable: ✓
- Image: Browse to downloaded `alpine-virt-3.20.3-x86_64.iso`

**Network**:
- Adapters: `1`
- Type: `e1000`

**Advanced**:
- Console type: `telnet`
- Options: `-nographic -serial mon:stdio`

### Step 3: Finish Template

Click **Finish** to create template.

## First Boot Setup

### Start the Node

1. Drag "Alpine Linux Test" to GNS3 workspace
2. Right-click → **Start**
3. Right-click → **Console**

### Login

```
localhost login: root
(no password - just press Enter)
```

### Optional: Setup System

If you want persistent storage (optional for testing):

```sh
# Run Alpine setup
setup-alpine

# Answer prompts:
# Keyboard: us
# Hostname: alpine-test
# Network: dhcp
# Password: test123
# Timezone: UTC
# Proxy: none
# NTP: chrony
# Mirror: 1 (or closest to you)
# User: none
# SSH: openssh
# Disk: sda
# Mode: sys
```

### For Quick Testing (No Installation)

Just use live boot - no setup needed:

```sh
# Already at shell prompt
# Test with:
hostname
ip addr
echo "Hello from Alpine"
```

## Testing Console Operations

### Manual Test from GNS3 Console

```sh
# Login
root

# See prompt
alpine-test:~#

# Test commands
whoami
date
uptime
```

### Test with MCP Server

From Claude Desktop or test script:

```python
# Connect
connect_console("Alpine Linux Test")
# Returns: session_id

# Send wake-up
send_console(session_id, "\n")

# Read prompt
read_console(session_id)
# Should show: "alpine-test:~#"

# Send command
send_console(session_id, "hostname\n")

# Read output
read_console_diff(session_id)
# Should show: "alpine-test"
```

### Test Script

```bash
cd "C:\HOME\1. Scripts\008. GNS3 MCP\tests"

# Direct console test
python simple_console_test.py --host 192.168.1.20 --port 5000 --duration 5

# Full MCP test (once MCP client implemented)
python test_mcp_server.py --password admin --test-node "Alpine Linux Test"
```

## Device States

### Fresh Boot (Live Mode)

- Boot time: ~5 seconds
- Login: `root` (no password)
- Prompt: `localhost:~#`
- RAM: ~30 MB used

### After Installation

- Boot time: ~3 seconds
- Login: `root` with password `test123`
- Prompt: `alpine-test:~#`
- Persistent storage

## Test Scenarios

### Scenario 1: Basic Console

1. Connect to console
2. Wait for login prompt
3. Send: `root\n`
4. Read prompt: `localhost:~#`

### Scenario 2: Command Execution

1. Connect
2. Login
3. Send: `echo "Test successful"\n`
4. Read diff: Should contain "Test successful"

### Scenario 3: Multi-line Output

1. Send: `ip addr\n`
2. Read: Multiple lines of network config

### Scenario 4: Session Persistence

1. Connect → session_id_1
2. Send commands
3. Disconnect
4. Connect → session_id_2 (new session)
5. Console state reset (new login prompt)

## Troubleshooting

### Node Won't Start

- Check QEMU settings
- Verify ISO path is correct
- Check available RAM

### Console Shows Nothing

- Wait 5 seconds after boot
- Send: `\n` (newline) to wake up console
- Check console type is `telnet`

### Boot Hangs

- Press Enter at boot menu
- Or wait 5 seconds for auto-boot

## Alternative: Pre-configured Appliance

GNS3 has pre-configured Alpine appliance:

1. **GNS3** → **File** → **Import appliance**
2. Search: "Alpine Linux"
3. Download and import
4. Already configured correctly

## Comparison with Other Test Devices

| Device | Boot Time | RAM | Complexity | Good for Testing |
|--------|-----------|-----|------------|------------------|
| Alpine Linux | 5s | 256 MB | Low | ✓ Excellent |
| MikroTik CHR | 15s | 256 MB | Medium | ✓ Good (after setup) |
| Tiny Core | 3s | 128 MB | Low | ✓ Excellent |
| Ubuntu Server | 30s | 1024 MB | High | ✗ Too heavy |
| Cisco IOL | 20s | 512 MB | Medium | ✓ Good (if available) |

## Next Steps

1. Create Alpine test device in GNS3
2. Verify console works manually
3. Note the console port (check node properties)
4. Test with `simple_console_test.py`
5. Integrate into automated test suite

## Advanced: Automation Scripts

### Auto-login Script (Optional)

Create wrapper script that handles login automatically:

```python
async def auto_login_alpine(session_id):
    """Auto-login to Alpine test device"""

    # Wait for login prompt
    await asyncio.sleep(2)
    output = read_console(session_id)

    if "login:" in output:
        send_console(session_id, "root\n")
        await asyncio.sleep(1)

    # Now at shell prompt
    return read_console_diff(session_id)
```

This makes test scripts simpler and more reliable.
