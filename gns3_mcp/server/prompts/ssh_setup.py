"""SSH Setup Workflow Prompt

Guides users through enabling SSH on network devices with device-specific instructions.
"""

# Device-specific SSH configuration commands
DEVICE_CONFIGS = {
    "cisco_ios": """
**Cisco IOS/IOS-XE SSH Setup:**

Use console batch operations to configure SSH:
```
console(operations=[
    {{"type": "send", "node_name": "{node_name}", "data": "configure terminal\\n"}},
    {{"type": "send", "node_name": "{node_name}", "data": "username {username} privilege 15 secret {password}\\n"}},
    {{"type": "send", "node_name": "{node_name}", "data": "crypto key generate rsa modulus 2048\\n"}},
    {{"type": "send", "node_name": "{node_name}", "data": "ip ssh version 2\\n"}},
    {{"type": "send", "node_name": "{node_name}", "data": "line vty 0 4\\n"}},
    {{"type": "send", "node_name": "{node_name}", "data": "login local\\n"}},
    {{"type": "send", "node_name": "{node_name}", "data": "transport input ssh\\n"}},
    {{"type": "send", "node_name": "{node_name}", "data": "end\\n"}},
    {{"type": "send", "node_name": "{node_name}", "data": "write memory\\n"}}
])
```
Note: If "crypto key generate rsa" prompts "Do you really want to replace them? [yes/no]:", send "yes\\n" in separate operation
""",
    "cisco_nxos": """
**Cisco NX-OS SSH Setup:**

Use console batch operations:
```
console(operations=[
    {{"type": "send", "node_name": "{node_name}", "data": "configure terminal\\n"}},
    {{"type": "send", "node_name": "{node_name}", "data": "feature ssh\\n"}},
    {{"type": "send", "node_name": "{node_name}", "data": "username {username} password {password} role network-admin\\n"}},
    {{"type": "send", "node_name": "{node_name}", "data": "ssh key rsa 2048\\n"}},
    {{"type": "send", "node_name": "{node_name}", "data": "end\\n"}},
    {{"type": "send", "node_name": "{node_name}", "data": "copy running-config startup-config\\n"}}
])
```
""",
    "mikrotik_routeros": """
**MikroTik RouterOS SSH Setup:**

Use console batch operations:
```
console(operations=[
    {{"type": "send", "node_name": "{node_name}", "data": "/user add name={username} password={password} group=full\\n"}},
    {{"type": "send", "node_name": "{node_name}", "data": "/ip service enable ssh\\n"}},
    {{"type": "send", "node_name": "{node_name}", "data": "/ip service set ssh port=22\\n"}}
])
```
""",
    "juniper_junos": """
**Juniper Junos SSH Setup:**

Use console batch operations:
```
console(operations=[
    {{"type": "send", "node_name": "{node_name}", "data": "configure\\n"}},
    {{"type": "send", "node_name": "{node_name}", "data": "set system login user {username} class super-user authentication plain-text-password\\n"}},
    # Wait for password prompt, then send password twice
    {{"type": "send", "node_name": "{node_name}", "data": "{password}\\n"}},
    {{"type": "send", "node_name": "{node_name}", "data": "{password}\\n"}},
    {{"type": "send", "node_name": "{node_name}", "data": "set system services ssh\\n"}},
    {{"type": "send", "node_name": "{node_name}", "data": "commit and-quit\\n"}}
])
```
""",
    "arista_eos": """
**Arista EOS SSH Setup:**

Use console batch operations:
```
console(operations=[
    {{"type": "send", "node_name": "{node_name}", "data": "configure\\n"}},
    {{"type": "send", "node_name": "{node_name}", "data": "username {username} privilege 15 secret {password}\\n"}},
    {{"type": "send", "node_name": "{node_name}", "data": "management ssh\\n"}},
    {{"type": "send", "node_name": "{node_name}", "data": "idle-timeout 0\\n"}},
    {{"type": "send", "node_name": "{node_name}", "data": "exit\\n"}},
    {{"type": "send", "node_name": "{node_name}", "data": "end\\n"}},
    {{"type": "send", "node_name": "{node_name}", "data": "write memory\\n"}}
])
```
""",
    "linux": """
**Linux/Alpine SSH Setup:**

Use console batch operations:
```
# Alpine
console(operations=[
    {{"type": "send", "node_name": "{node_name}", "data": "apk add openssh\\n"}},
    {{"type": "send", "node_name": "{node_name}", "data": "passwd\\n"}},
    {{"type": "send", "node_name": "{node_name}", "data": "{password}\\n"}},
    {{"type": "send", "node_name": "{node_name}", "data": "{password}\\n"}},
    {{"type": "send", "node_name": "{node_name}", "data": "rc-service sshd start\\n"}},
    {{"type": "send", "node_name": "{node_name}", "data": "rc-update add sshd\\n"}}
])

# OR Debian/Ubuntu
console(operations=[
    {{"type": "send", "node_name": "{node_name}", "data": "apt-get install -y openssh-server\\n"}},
    {{"type": "send", "node_name": "{node_name}", "data": "systemctl start ssh\\n"}},
    {{"type": "send", "node_name": "{node_name}", "data": "systemctl enable ssh\\n"}}
])
```
""",
}


async def render_ssh_setup_prompt(
    node_name: str, device_type: str, username: str = "admin", password: str = "admin"
) -> str:
    """Generate SSH setup workflow prompt with device-specific instructions

    Args:
        node_name: Target node name
        device_type: Device type (cisco_ios, mikrotik_routeros, juniper_junos, arista_eos, linux, etc.)
        username: SSH username to create (default: "admin")
        password: SSH password to set (default: "admin")

    Returns:
        Formatted workflow instructions as string
    """

    # Get device-specific instructions or provide generic guidance
    device_instructions = DEVICE_CONFIGS.get(
        device_type,
        f"""
**Generic SSH Setup (device_type: {device_type}):**

Device-specific instructions not available. General steps:
1. Use console_send() to access device configuration mode
2. Create a user account with administrative privileges
3. Enable SSH service
4. Generate SSH keys if required
5. Configure SSH access permissions
6. Save configuration

Refer to device documentation for specific commands.
""",
    )

    # Format instructions with parameters
    device_instructions = device_instructions.format(
        node_name=node_name, username=username, password=password
    )

    workflow = f"""# SSH Setup Workflow for {node_name}

This guided workflow helps you enable SSH access on **{node_name}** ({device_type}).

## Prerequisites

- Node must be running (check with resource `projects://{{id}}/nodes/`)
- Console access available (check with resource `sessions://console/{node_name}`)
- Know the device's management IP address

## Step 1: Configure SSH on Device (via Console)

Use console tools to configure SSH access on the device:

{device_instructions}

## Step 2: Verify Device Configuration

Read console output to verify commands executed successfully:
```
console(operations=[
    {{"type": "read", "node_name": "{node_name}", "mode": "diff"}}
])
```

Look for success messages and note any errors.

## Step 3: Find Management IP Address

Get the device's management interface IP:
```
# Cisco
console(operations=[
    {{"type": "send", "node_name": "{node_name}", "data": "show ip interface brief\\n"}},
    {{"type": "read", "node_name": "{node_name}", "mode": "last_page"}}
])

# OR MikroTik
console(operations=[
    {{"type": "send", "node_name": "{node_name}", "data": "/ip address print\\n"}},
    {{"type": "read", "node_name": "{node_name}", "mode": "last_page"}}
])

# OR Juniper
console(operations=[
    {{"type": "send", "node_name": "{node_name}", "data": "show interfaces terse\\n"}},
    {{"type": "read", "node_name": "{node_name}", "mode": "last_page"}}
])

# OR Linux
console(operations=[
    {{"type": "send", "node_name": "{node_name}", "data": "ip addr\\n"}},
    {{"type": "read", "node_name": "{node_name}", "mode": "last_page"}}
])
```

Identify the management IP (e.g., 192.168.1.10).

### Check Template Usage Field

Before proceeding, check the node's template for device-specific guidance:
```
# View node template usage field
Resource: nodes://{{project_id}}/{node_name}/template
```

The **usage** field may contain important information about:
- Default credentials or special SSH setup requirements
- Device-specific configuration quirks
- Console access procedures
- Management interface naming conventions

### Document in Project README

**IMPORTANT**: Document the management IP and credentials in the project README for future reference:

```
project_docs(action="update", content=f\"\"\"
[existing README content]

## {node_name} - SSH Access

- **Management IP**: 192.168.1.10  # Replace with actual IP
- **SSH Username**: {username}
- **SSH Password**: {password}
- **SSH Port**: 22
- **Device Type**: {device_type}
- **Console Type**: telnet (port {{console_port}})

### SSH Access
```bash
ssh {username}@192.168.1.10
```

### Notes
- Configured: {{current_date}}
- SSH enabled via console commands
- See template usage field for device-specific guidance
\"\"\")
```

Keeping credentials documented in the README ensures team members can access devices and helps with troubleshooting connectivity issues.

## Step 4: Establish SSH Session

### Option A: Direct Connection (Default)

For devices reachable from GNS3 host, use default proxy:
```
ssh(operations=[{{
    "type": "configure",
    "node_name": "{node_name}",
    "device_dict": {{
        "device_type": "{device_type}",
        "host": "192.168.1.10",  # Replace with actual IP
        "username": "{username}",
        "password": "{password}",
        "port": 22
    }}
}}])
```

### Option B: Via Lab Proxy (Isolated Networks - v0.26.0)

**Use this when the device is on an isolated network unreachable from GNS3 host.**

1. Discover available lab proxies:
```
# Check resource: proxies://
```

2. Configure SSH through lab proxy:
```
ssh(operations=[{{
    "type": "configure",
    "node_name": "{node_name}",
    "device_dict": {{
        "device_type": "{device_type}",
        "host": "10.199.0.20",  # Device IP on isolated network
        "username": "{username}",
        "password": "{password}",
        "port": 22
    }},
    "proxy": "<proxy_id>"  # Use proxy_id from registry
}}])
```

Example for isolated network 10.199.0.0/24:
```
# 1. Find A-PROXY's proxy_id from proxies://
# Returns: proxy_id="3f3a56de-19d3-40c3-9806-76bee4fe96d4"

# 2. Configure SSH through A-PROXY
ssh(operations=[{{
    "type": "configure",
    "node_name": "A-CLIENT",
    "device_dict": {{
        "device_type": "linux",
        "host": "10.199.0.20",
        "username": "alpine",
        "password": "alpine"
    }},
    "proxy": "3f3a56de-19d3-40c3-9806-76bee4fe96d4"
}}])
```

**How Multi-Proxy Routing Works:**
- First configure operation stores proxy mapping
- All subsequent ssh command operations automatically route through same proxy
- No need to specify proxy again for each command

## Step 5: Test SSH Connection

Verify SSH works by running a show command:
```
ssh(operations=[{{
    "type": "command",
    "node_name": "{node_name}",
    "command": "show version"  # Or appropriate command for device
}}])
```

## Step 6: Verify Session Status

Check SSH session is active:
```
# Use resource: sessions://ssh/{node_name}
```

## Troubleshooting

**Connection Refused:**
- Verify SSH service is running on device
- Check firewall rules allow SSH (port 22)
- Confirm management IP is correct

**Authentication Failed:**
- Verify username/password are correct
- Check user has appropriate privileges
- For Cisco: Ensure "login local" is configured on VTY lines

**Timeout:**
- Verify network connectivity to device
- Check device IP is reachable
- Ensure correct interface has IP address configured

**SSH Keys Error (Cisco):**
- If "crypto key generate rsa" fails, device may need more RAM
- Try smaller key size: "crypto key generate rsa modulus 1024"

## Next Steps

Once SSH is working:
1. Use `ssh()` batch operations for all automation tasks
2. Review command history with resource `sessions://ssh/{node_name}/history`
3. Disconnect console session if no longer needed:
   ```
   console(operations=[{{"type": "disconnect", "node_name": "{node_name}"}}])
   ```

SSH provides better reliability and automatic prompt detection compared to console.
"""

    return workflow
