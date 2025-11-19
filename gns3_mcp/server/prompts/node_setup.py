"""Node Setup Workflow Prompt

Complete workflow for adding a new node to a lab: create, configure IP, document in README, establish SSH.
"""


def render_node_setup_prompt(
    node_name: str,
    template_name: str,
    ip_address: str,
    subnet_mask: str = "255.255.255.0",
    device_type: str = "cisco_ios",
    username: str = "admin",
    password: str = "admin",
) -> str:
    """Generate complete node setup workflow prompt

    This workflow covers the entire process of:
    1. Creating a new node from template
    2. Starting the node and waiting for boot
    3. Configuring IP address via console
    4. Documenting IP/credentials in project README
    5. Establishing SSH session for automation

    Args:
        node_name: Name for the new node (e.g., "Router1")
        template_name: GNS3 template to use (e.g., "Cisco IOSv", "Alpine Linux")
        ip_address: Management IP to assign (e.g., "192.168.1.10")
        subnet_mask: Subnet mask (default: "255.255.255.0")
        device_type: Device type for SSH (cisco_ios, linux, etc.)
        username: SSH username to create (default: "admin")
        password: SSH password to set (default: "admin")

    Returns:
        Formatted workflow instructions as string
    """

    # Device-specific IP configuration commands
    ip_configs = {
        "cisco_ios": f"""
**Cisco IOS IP Configuration:**

1. Wait for boot (30-60 seconds), then access console:
   ```
   console_send("{node_name}", "\\n")
   console_read("{node_name}", mode="last_page")
   ```

2. Enter privileged mode:
   ```
   console_send("{node_name}", "enable\\n")
   ```

3. Configure management interface:
   ```
   console_send("{node_name}", "configure terminal\\n")
   console_send("{node_name}", "interface GigabitEthernet0/0\\n")
   console_send("{node_name}", "ip address {ip_address} {subnet_mask}\\n")
   console_send("{node_name}", "no shutdown\\n")
   console_send("{node_name}", "end\\n")
   ```

4. Verify IP configuration:
   ```
   console_send("{node_name}", "show ip interface brief\\n")
   console_read("{node_name}", mode="last_page")
   ```

5. Save configuration:
   ```
   console_send("{node_name}", "write memory\\n")
   ```

6. Create SSH user:
   ```
   console_send("{node_name}", "configure terminal\\n")
   console_send("{node_name}", "username {username} privilege 15 secret {password}\\n")
   console_send("{node_name}", "crypto key generate rsa modulus 2048\\n")
   console_send("{node_name}", "ip ssh version 2\\n")
   console_send("{node_name}", "line vty 0 4\\n")
   console_send("{node_name}", "login local\\n")
   console_send("{node_name}", "transport input ssh\\n")
   console_send("{node_name}", "end\\n")
   console_send("{node_name}", "write memory\\n")
   ```
""",
        "linux": f"""
**Linux IP Configuration:**

1. Wait for boot (10-20 seconds), login via console:
   ```
   console_send("{node_name}", "\\n")
   console_read("{node_name}", mode="last_page")
   # Login with default credentials
   console_send("{node_name}", "root\\n")
   console_send("{node_name}", "password\\n")
   ```

2. Configure IP address (temporary):
   ```
   console_send("{node_name}", "ip addr add {ip_address}/{subnet_mask} dev eth0\\n")
   console_send("{node_name}", "ip link set eth0 up\\n")
   ```

3. Verify IP:
   ```
   console_send("{node_name}", "ip addr show eth0\\n")
   console_read("{node_name}", mode="last_page")
   ```

4. Configure persistent (Alpine Linux example):
   ```
   console_send("{node_name}", "cat > /etc/network/interfaces << 'EOF'\\n")
   console_send("{node_name}", "auto lo\\n")
   console_send("{node_name}", "iface lo inet loopback\\n")
   console_send("{node_name}", "\\n")
   console_send("{node_name}", "auto eth0\\n")
   console_send("{node_name}", "iface eth0 inet static\\n")
   console_send("{node_name}", "    address {ip_address}\\n")
   console_send("{node_name}", "    netmask {subnet_mask}\\n")
   console_send("{node_name}", "EOF\\n")
   console_send("{node_name}", "/etc/init.d/networking restart\\n")
   ```

5. Enable SSH (if not already enabled):
   ```
   console_send("{node_name}", "rc-update add sshd default\\n")
   console_send("{node_name}", "service sshd start\\n")
   ```

6. Set password for root or create user:
   ```
   console_send("{node_name}", "adduser {username}\\n")
   # Follow prompts to set password
   console_send("{node_name}", "{password}\\n")
   console_send("{node_name}", "{password}\\n")
   # Add to sudoers
   console_send("{node_name}", "addgroup {username} wheel\\n")
   ```
""",
        "mikrotik_routeros": f"""
**MikroTik RouterOS IP Configuration:**

1. Wait for boot, access console:
   ```
   console_send("{node_name}", "\\n")
   console_read("{node_name}", mode="last_page")
   ```

2. Login with default credentials (admin / blank password):
   ```
   console_send("{node_name}", "admin\\n")
   console_send("{node_name}", "\\n")
   ```

3. Configure IP address:
   ```
   console_send("{node_name}", "/ip address add address={ip_address}/24 interface=ether1\\n")
   ```

4. Verify IP:
   ```
   console_send("{node_name}", "/ip address print\\n")
   console_read("{node_name}", mode="last_page")
   ```

5. Create SSH user:
   ```
   console_send("{node_name}", "/user add name={username} password={password} group=full\\n")
   ```

6. Enable SSH service:
   ```
   console_send("{node_name}", "/ip service enable ssh\\n")
   ```
""",
    }

    # Get device-specific config or generic
    ip_config = ip_configs.get(
        device_type,
        f"""
**Generic IP Configuration (device_type: {device_type}):**

1. Access device console and login
2. Configure IP address {ip_address}/{subnet_mask} on management interface
3. Enable SSH service
4. Create user {username} with password
5. Verify configuration

Refer to device documentation for specific commands.
""",
    )

    # Format with parameters
    ip_config = ip_config.format(
        node_name=node_name,
        ip_address=ip_address,
        subnet_mask=subnet_mask,
        username=username,
        password=password,
    )

    # Build complete workflow
    workflow = f"""# Complete Node Setup: {node_name}

This workflow guides you through setting up **{node_name}** from scratch.

**What This Does:**
1. ✅ Create node from template
2. ✅ Start node and wait for boot
3. ✅ Configure IP address via console
4. ✅ Document IP/credentials in project README
5. ✅ Establish SSH session for automation

## Prerequisites

- Project must be opened
- Template "{template_name}" must exist (check resource `projects://{{id}}/templates/`)
- Console access available after node starts

## Step 1: Create Node

Create the node from template and position it on canvas:

```python
node(
    action="create",
    template_name="{template_name}",
    node_name="{node_name}",
    x=100,  # Adjust position as needed
    y=100
)
```

Note the returned node_id for reference.

## Step 2: Start Node

Start the node and wait for boot sequence:

```python
node(action="set", node_name="{node_name}", state_action="start")
```

**Wait time depends on device type:**
- Cisco routers: 30-60 seconds
- Linux nodes: 10-20 seconds
- MikroTik: 15-30 seconds

Monitor boot via console:
```python
# Check boot progress
console_read("{node_name}", mode="all")
```

## Step 2.5: Check Template Usage Field

Before configuring the device, check the template's usage field for device-specific guidance:

```python
# View node template usage information
Resource: nodes://{{project_id}}/{node_name}/template
```

**The usage field may contain:**
- Default credentials for initial login
- Special boot procedures or timing requirements
- Device-specific configuration quirks
- Recommended interface naming conventions
- Known limitations or compatibility notes
- Management interface defaults

**Example usage field content:**
```
Alpine Linux default login:
- Username: root
- Password: (blank - just press Enter)

After first login, set password with: passwd

For persistent network config, edit /etc/network/interfaces
```

Review this information before proceeding with configuration to avoid common pitfalls.

## Step 3: Configure IP Address

{ip_config}

## Step 4: Document in Project README

Update project README with node details for future reference:

```python
# First, get existing README (if any)
current_notes = get_project_readme()

# Append new node information
update_project_readme(f\"\"\"
{{current_notes}}

## Node: {node_name}

### Network Configuration
- **IP Address**: {ip_address}/{subnet_mask}
- **Interface**: GigabitEthernet0/0 (or eth0 for Linux)
- **Template**: {template_name}
- **Device Type**: {device_type}

### Credentials
- **Username**: {username}
- **Password**: {password}
- **SSH Access**: ssh://{username}@{ip_address}:22

### Notes
- Created: {{datetime.now().strftime("%Y-%m-%d %H:%M")}}
- Purpose: [Add purpose here]
- Connected to: [Add connections here]

### Configuration
```
[Paste key configuration here]
```

### Troubleshooting
- **Issue**: [Document common issues]
- **Fix**: [Document solutions]
\"\"\")
```

**Pro tip:** Keep README organized with clear sections for each node.

## Step 5: Establish SSH Session

Configure SSH session for automated management:

### Standard Connection (Devices Reachable from GNS3 Host):

```python
ssh(operations=[{{
    "type": "configure",
    "node_name": "{node_name}",
    "device_dict": {{
        "device_type": "{device_type}",
        "host": "{ip_address}",
        "username": "{username}",
        "password": "{password}",
        "port": 22
    }}
}}])
```

### Isolated Network Connection (v0.26.0 Multi-Proxy):

For devices on isolated networks, use lab proxy:

```python
# 1. Discover lab proxies: check proxies://
# 2. Configure SSH through lab proxy:
ssh(operations=[{{
    "type": "configure",
    "node_name": "{node_name}",
    "device_dict": {{
        "device_type": "{device_type}",
        "host": "{ip_address}",
        "username": "{username}",
        "password": "{password}",
        "port": 22
    }},
    "proxy": "<proxy_id>"  # proxy_id from registry
}}])
```

## Step 6: Verify SSH Connection

Test SSH access with a simple command:

```python
# Cisco
ssh(operations=[{{"type": "command", "node_name": "{node_name}", "command": "show version"}}])

# Linux
ssh(operations=[{{"type": "command", "node_name": "{node_name}", "command": "uname -a"}}])

# MikroTik
ssh(operations=[{{"type": "command", "node_name": "{node_name}", "command": "/system resource print"}}])
```

Check SSH session status:
```python
# Via resource
sessions://ssh/{node_name}
```

## Step 7: Connect to Network (Optional)

If this node needs to connect to other nodes:

```python
set_connection(connections=[
    {{
        "action": "connect",
        "node_a": "{node_name}",
        "node_b": "ExistingRouter",
        "port_a": 0,
        "port_b": 1,
        "adapter_a": "GigabitEthernet0/1",  # Or adapter number
        "adapter_b": "GigabitEthernet0/0"
    }}
])
```

Update README with connection info:
```python
update_project_readme(f\"\"\"
[previous content]

### Connections
- {node_name} Gi0/1 ← → ExistingRouter Gi0/0
\"\"\")
```

## Completion Checklist

- [ ] Node created and started
- [ ] IP address configured and verified
- [ ] Credentials documented in README
- [ ] SSH session established and tested
- [ ] Network connections made (if needed)
- [ ] Configuration saved on device

## Next Steps

Now that {node_name} is configured:

1. **Configure routing protocols** (OSPF, BGP, etc.)
2. **Add to monitoring** (document in README)
3. **Create snapshot** before major changes: `create_snapshot("Before {node_name} routing config")`
4. **Update architecture notes** in README with role and relationships

## Troubleshooting

**Node won't start:**
- Check template is valid: resource `projects://{{id}}/templates/`
- Verify enough resources (RAM, CPU) on GNS3 server
- Check GNS3 server logs

**Can't access console:**
- Wait for boot completion (check console output)
- Verify node is started: resource `projects://{{id}}/nodes/{node_name}`
- Check console type is telnet

**SSH connection fails:**
- Verify IP is pingable from GNS3 server
- Confirm SSH service is running on device
- Check credentials are correct
- Review SSH configuration commands executed successfully

**IP not working:**
- Verify interface is up (`no shutdown` for Cisco)
- Check correct interface name used
- Confirm subnet doesn't conflict with existing network
- Verify physical connections if connecting to other nodes

## Example: Complete Workflow Code

```python
# 1. Create and start node
create_node(template_name="{template_name}", node_name="{node_name}", x=100, y=100)
set_node(node_name="{node_name}", action="start")

# 2. Wait for boot
import time
time.sleep(45)  # Adjust based on device type

# 3. Configure via console (see device-specific commands above)
console_send("{node_name}", "\\n")
# [Execute IP configuration commands...]

# 4. Document in README
update_project_readme(f\"\"\"
# My Lab

## {node_name}
- IP: {ip_address}/{subnet_mask}
- User: {username}
- Pass: {password}
\"\"\")

# 5. Configure SSH
ssh_configure("{node_name}", {{
    "device_type": "{device_type}",
    "host": "{ip_address}",
    "username": "{username}",
    "password": "{password}"
}})

# 6. Verify
ssh_command("{node_name}", "show version")
```

**Success!** {node_name} is now ready for network automation.
"""

    return workflow
