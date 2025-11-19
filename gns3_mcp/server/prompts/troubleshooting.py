"""Troubleshooting Workflow Prompt

Guides users through systematic troubleshooting of network issues in GNS3 labs.
"""


async def render_troubleshooting_prompt(node_name: str = None, issue_type: str = None) -> str:
    """Generate troubleshooting workflow prompt

    Args:
        node_name: Optional node name to focus troubleshooting on
        issue_type: Optional issue category (connectivity, console, ssh, performance)

    Returns:
        Formatted workflow instructions as string
    """

    node_section = f"**Troubleshooting Node: {node_name}**\n" if node_name else ""

    issue_section = ""
    if issue_type:
        issue_map = {
            "connectivity": "network connectivity issues",
            "console": "console access problems",
            "ssh": "SSH connection failures",
            "performance": "performance degradation",
        }
        issue_section = f"\n**Focus Area: {issue_map.get(issue_type, issue_type)}**\n"

    workflow = f"""# Network Troubleshooting Workflow

{node_section}{issue_section}
This guided workflow helps you systematically troubleshoot issues in GNS3 network labs.

## Troubleshooting Methodology

Follow the OSI model bottom-up approach:
1. **Layer 1 (Physical)**: Links, node state, connections
2. **Layer 2 (Data Link)**: Switching, VLANs, MAC addresses
3. **Layer 3 (Network)**: IP addressing, routing, reachability
4. **Layer 4+ (Transport/Application)**: Services, protocols, applications

## Step 1: Verify Lab State

**Check Project README First:**

Before diving into diagnostics, review the project README for documented information:
```
# View project documentation
Resource: projects://{{project_id}}/readme
```

**Look for:**
- Node IP addresses and credentials
- Known issues or troubleshooting notes
- Network topology design (subnets, VLANs, routing)
- Configuration dependencies
- Recent changes or maintenance notes

Having this baseline information helps identify configuration mismatches and expected behavior.

**Check Node Status:**
```
# View all nodes and their states
Resource: projects://{{project_id}}/nodes/
```

**Key Checks:**
- ✅ Are affected nodes **started**? (not stopped or suspended)
- ✅ Did nodes boot successfully? (no boot errors)
- ✅ Are nodes consuming resources? (CPU, memory within limits)

**Start Stopped Nodes:**
```
set_node(node_name="NodeName", action="start")
```

**Check Link Status:**
```
# View all links
Resource: projects://{{project_id}}/links/
```

**Key Checks:**
- ✅ Are links **active**? (not suspended)
- ✅ Are ports connected to correct adapters?
- ✅ Do link types match device capabilities?

**Activate Suspended Links:**
```
set_connection(operations=[
    {
        "action": "unsuspend",
        "link_id": "link-uuid-here"
    }
])
```

## Step 2: Verify Console Access

**Check Console Sessions:**
```
# View active console sessions
Resource: sessions://console/{{node_name}}
```

**Test Console Access:**
```
# Send command to console
console_send("NodeName", "\\n")

# Read response
console_read("NodeName", mode="last_page")
```

**Common Console Issues:**

**Issue: "Connection refused"**
- **Cause**: Node not started or console port not open
- **Fix**: Start node, wait 10-30 seconds, retry

**Issue: "Timeout connecting"**
- **Cause**: Node still booting or console type unsupported
- **Fix**: Wait longer, check console_type is "telnet"

**Issue: "No output from console"**
- **Cause**: Device prompt not sending data, terminal settings
- **Fix**: Send keystroke to trigger prompt:
```
console_keystroke("NodeName", "enter")
console_read("NodeName", mode="last_page")
```

**Issue: "Garbled output"**
- **Cause**: Terminal encoding mismatch
- **Fix**: Disconnect and reconnect console:
```
console_disconnect("NodeName")
# Wait 2 seconds, then reconnect automatically on next send
console_send("NodeName", "\\n")
```

## Step 3: Layer 1 - Physical Connectivity

**Verify Physical Topology:**
```
# Export topology diagram to visualize connections
export_topology_diagram(
    output_path="C:/path/to/troubleshooting",
    format="svg"
)
```

**Check Port Status Indicators:**
- 🟢 **Green**: Port active (node started, link not suspended)
- 🔴 **Red**: Port stopped (node stopped OR link suspended)

**Common Layer 1 Issues:**

**Issue: Link shows red indicator**
- Check node status: `Resource: projects://{id}/nodes/{id}`
- Check link status: `Resource: projects://{id}/links/`
- Start nodes if stopped
- Unsuspend links if suspended

**Issue: Nodes not physically connected**
- Verify link exists between nodes
- Check adapter/port numbers match device interfaces
- Create missing links:
```
set_connection(operations=[
    {
        "action": "connect",
        "node_a": "R1",
        "node_b": "R2",
        "adapter_a": "GigabitEthernet0/0",  # Or adapter number
        "adapter_b": "GigabitEthernet0/0",
        "port_a": 0,
        "port_b": 0
    }
])
```

## Step 4: Layer 2 - Data Link Issues

**Check Interface Status:**
```
# Cisco
ssh_command("R1", "show interfaces status")
ssh_command("R1", "show interfaces")

# MikroTik
ssh_command("R1", "/interface print")

# Linux
ssh_command("Host1", "ip link show")
```

**Common Layer 2 Issues:**

**Issue: Interface administratively down**
- **Symptom**: "administratively down" in show interfaces
- **Fix (Cisco)**:
```
ssh_command("R1", [
    "interface GigabitEthernet0/0",
    "no shutdown"
])
```

**Issue: VLAN mismatch**
- **Symptom**: Devices on same link can't communicate
- **Check VLANs**:
```
ssh_command("SW1", "show vlan brief")
```
- Verify access ports on same VLAN or trunk allows VLAN

**Issue: MAC address conflicts**
- **Symptom**: Intermittent connectivity, flapping
- **Check MAC table**:
```
ssh_command("SW1", "show mac address-table")
```
- Look for duplicate MACs

## Step 5: Layer 3 - Network Layer Issues

**Check IP Addressing:**
```
# Cisco
ssh_command("R1", "show ip interface brief")

# MikroTik
ssh_command("R1", "/ip address print")

# Linux
ssh_command("Host1", "ip addr show")
```

**Common Layer 3 Issues:**

**Issue: IP address not configured**
- **Symptom**: Interface shows "unassigned" or no IP
- **Fix (Cisco)**:
```
ssh_command("R1", [
    "interface GigabitEthernet0/0",
    "ip address 192.168.1.1 255.255.255.0",
    "no shutdown"
])
```

**Issue: IP address conflict**
- **Symptom**: "Duplicate IP address" warnings
- **Check ARP cache**:
```
ssh_command("R1", "show ip arp")
```
- Verify each device has unique IP

**Issue: Subnet mismatch**
- **Symptom**: Devices can't ping despite being "connected"
- **Verify**: Both ends of link in same subnet
- Example: 192.168.1.1/24 ↔ 192.168.1.2/24 ✅
- Example: 192.168.1.1/24 ↔ 192.168.2.1/24 ❌

**Check Routing:**
```
# Cisco
ssh_command("R1", "show ip route")

# MikroTik
ssh_command("R1", "/ip route print")

# Linux
ssh_command("Host1", "ip route show")
```

**Issue: No route to destination**
- **Symptom**: "Destination unreachable" or "Network unreachable"
- **Fix**: Add static route or enable routing protocol
```
# Cisco static route
ssh_command("R1", [
    "ip route 10.0.0.0 255.0.0.0 192.168.1.254"
])
```

**Test Reachability:**
```
# ICMP ping test
ssh_command("R1", "ping 192.168.1.2")

# Continuous ping (Ctrl+C to stop in console)
console_send("R1", "ping 192.168.1.2 repeat 100\\n")
# Wait, then read output
console_read("R1", mode="last_page")
```

## Step 6: Layer 4+ - Services and Applications

**Check Service Status:**
```
# Linux services
ssh_command("Host1", "systemctl status sshd")
ssh_command("Host1", "netstat -tuln")  # Listening ports

# Cisco services
ssh_command("R1", "show ip sockets")
```

**Common Service Issues:**

**Issue: Service not running**
- **Symptom**: Connection refused to service port
- **Fix**: Start service
```
ssh_command("Host1", "systemctl start sshd")
```

**Issue: Firewall blocking**
- **Symptom**: Connection timeout (not refused)
- **Check firewall rules**:
```
ssh_command("Host1", "iptables -L -n -v")
```

**Issue: DNS resolution failing**
- **Symptom**: Can ping IP but not hostname
- **Test DNS**:
```
ssh_command("Host1", "nslookup example.com")
ssh_command("Host1", "dig example.com")
```

## Step 7: Performance Troubleshooting

**Check Resource Utilization:**

**CPU Usage:**
```
# Cisco
ssh_command("R1", "show processes cpu sorted")

# Linux
ssh_command("Host1", "top -b -n 1 | head -20")
```

**Memory Usage:**
```
# Cisco
ssh_command("R1", "show memory statistics")

# Linux
ssh_command("Host1", "free -h")
```

**Interface Utilization:**
```
# Cisco
ssh_command("R1", "show interfaces | include rate")

# Linux
ssh_command("Host1", "ip -s link show")
```

**Common Performance Issues:**

**Issue: High CPU usage**
- **Cause**: Routing loops, broadcast storms, software bugs
- **Check for loops**: Verify no Layer 2 loops (use spanning-tree)
- **Check routing**: Look for routing loops in "show ip route"

**Issue: High interface errors**
```
ssh_command("R1", "show interfaces GigabitEthernet0/0 | include error")
```
- **Input errors**: Bad cables, duplex mismatch
- **Output errors**: Oversubscription, buffering issues

**Issue: Packet loss**
```
# Extended ping with statistics
console_send("R1", "ping 192.168.1.2 repeat 1000\\n")
# Wait for completion
console_read("R1", mode="last_page")
```
- Check "Success rate" percentage
- Intermittent loss: Physical issue, congestion
- Complete loss: Configuration issue (Layer 1-3)

## Step 8: SSH Troubleshooting

**Check SSH Session Status:**
```
Resource: sessions://ssh/{{node_name}}
```

**Common SSH Issues:**

**Issue: "Connection refused"**
- **Cause**: SSH not enabled on device
- **Fix**: Use console to enable SSH (see "SSH Setup Workflow" prompt)

**Issue: "Authentication failed"**
- **Cause**: Wrong username/password, user not configured
- **Check configuration (Cisco)**:
```
console_send("R1", "show running-config | include username\\n")
console_read("R1", mode="last_page")
```

**Issue: "Host unreachable"**
- **Cause**: Network connectivity issue (Layer 1-3)
- **Fix**: Follow Layer 1-3 troubleshooting first

**Issue: "Timeout"**
- **Cause**: Slow device, high latency, firewall
- **Fix**: Increase read_timeout in ssh_command:
```
ssh_command("R1", "show version", read_timeout=60.0)
```

**Disconnect and Retry:**
```
ssh_disconnect("R1")
# Wait 2 seconds
ssh_configure("R1", {
        "device_type": "cisco_ios",
    "host": "192.168.1.1",
    "username": "admin",
    "password": "password"
})
```

## Step 9: Log Collection

**Collect Device Logs:**
```
# Cisco
ssh_command("R1", "show logging")
ssh_command("R1", "show logging last 50")

# Linux
ssh_command("Host1", "journalctl -n 100")
ssh_command("Host1", "dmesg | tail -50")
```

**Check Console History:**
```
# View command history
Resource: sessions://ssh/{{node_name}}/history

# View SSH buffer
Resource: sessions://ssh/{{node_name}}/buffer
```

**Save Configurations:**
```
# Cisco
ssh_command("R1", "show running-config")
ssh_command("R1", "show startup-config")

# Save to startup
ssh_command("R1", "write memory")
```

## Step 10: Baseline Comparison

**Compare with Working Topology:**
- Export current topology diagram
- Compare with known-good state
- Identify configuration differences

**Document Changes:**
- What changed before issue started?
- Were new devices added?
- Were configurations modified?
- Did software/IOS versions change?

## Troubleshooting Decision Tree

```
Issue Detected
    │
    ├─ Nodes not started? → Start nodes, wait for boot
    │
    ├─ Links suspended/red? → Check connections, unsuspend links
    │
    ├─ Console not accessible? → Verify node started, check console type
    │
    ├─ Interface down? → Check config, "no shutdown", verify cable
    │
    ├─ No IP address? → Configure IP, verify subnet
    │
    ├─ Can't ping? → Check routing, verify reachability
    │
    ├─ Service not working? → Check service status, firewall rules
    │
    └─ Performance issues? → Check CPU/memory, look for loops
```

## Related Prompts and Tools

**Prompts:**
- **SSH Setup Workflow**: Enable SSH on devices for automation
- **Topology Discovery Workflow**: Understand network structure

**Resources (viewing state):**
- `projects://{id}/nodes/` - Node status
- `projects://{id}/links/` - Link status
- `sessions://console/{node_name}` - Console session state
- `sessions://ssh/{node_name}` - SSH session state

**Tools (actions):**
- `node(action="set", state_action="start|stop|reload", ...)` - Start/stop/reload nodes
- `link(connections=[...])` - Manage links (batch)
- `console(operations=[{"type": "send|read|keystroke", ...}])` - Console interaction (batch)
- `ssh(operations=[{"type": "command", ...}])` - Execute commands via SSH (batch)
- `export_topology_diagram(...)` - Visualize topology

**Note**: v0.47.0 uses CRUD-style APIs. Individual tool examples in this guide use old API format and should be converted to batch operations.

## Prevention and Best Practices

**Configuration Management:**
- Save configurations regularly (`write memory`)
- Document changes before making them
- Use version control for configuration files

**Topology Documentation:**
- Export topology diagrams
- Maintain IP address spreadsheets
- Document VLAN assignments

**Regular Health Checks:**
- Verify all nodes started
- Check interface status
- Review routing tables
- Monitor resource utilization

**Lab Hygiene:**
- Close unused projects to free resources
- Stop nodes when not in use
- Clean up old console/SSH sessions
- Remove unused links and devices
"""

    return workflow
