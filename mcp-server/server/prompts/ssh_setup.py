"""SSH Setup Workflow Prompt

Guides users through enabling SSH on network devices with device-specific instructions.
"""

# Device-specific SSH configuration commands
DEVICE_CONFIGS = {
    "cisco_ios": """
**Cisco IOS/IOS-XE SSH Setup:**

1. Enter configuration mode:
   ```
   console_send("{node_name}", "configure terminal\\n")
   ```

2. Create administrative user:
   ```
   console_send("{node_name}", "username {username} privilege 15 secret {password}\\n")
   ```

3. Generate RSA keys (required for SSH):
   ```
   console_send("{node_name}", "crypto key generate rsa modulus 2048\\n")
   ```
   Note: May prompt "Do you really want to replace them? [yes/no]:" - send "yes\\n" if needed

4. Enable SSH version 2:
   ```
   console_send("{node_name}", "ip ssh version 2\\n")
   ```

5. Configure VTY lines for SSH access:
   ```
   console_send("{node_name}", "line vty 0 4\\n")
   console_send("{node_name}", "login local\\n")
   console_send("{node_name}", "transport input ssh\\n")
   console_send("{node_name}", "end\\n")
   ```

6. Save configuration:
   ```
   console_send("{node_name}", "write memory\\n")
   ```
""",

    "cisco_nxos": """
**Cisco NX-OS SSH Setup:**

1. Enter configuration mode:
   ```
   console_send("{node_name}", "configure terminal\\n")
   ```

2. Enable SSH feature:
   ```
   console_send("{node_name}", "feature ssh\\n")
   ```

3. Create user:
   ```
   console_send("{node_name}", "username {username} password {password} role network-admin\\n")
   ```

4. Generate SSH keys:
   ```
   console_send("{node_name}", "ssh key rsa 2048\\n")
   ```

5. Exit and save:
   ```
   console_send("{node_name}", "end\\n")
   console_send("{node_name}", "copy running-config startup-config\\n")
   ```
""",

    "mikrotik_routeros": """
**MikroTik RouterOS SSH Setup:**

1. Create administrative user:
   ```
   console_send("{node_name}", "/user add name={username} password={password} group=full\\n")
   ```

2. Ensure SSH service is enabled (usually enabled by default):
   ```
   console_send("{node_name}", "/ip service enable ssh\\n")
   ```

3. Optional: Configure SSH port (default is 22):
   ```
   console_send("{node_name}", "/ip service set ssh port=22\\n")
   ```
""",

    "juniper_junos": """
**Juniper Junos SSH Setup:**

1. Enter configuration mode:
   ```
   console_send("{node_name}", "configure\\n")
   ```

2. Create user with SSH access:
   ```
   console_send("{node_name}", "set system login user {username} class super-user authentication plain-text-password\\n")
   ```
   Note: Will prompt for password - send "{password}\\n" twice

3. Enable SSH service:
   ```
   console_send("{node_name}", "set system services ssh\\n")
   ```

4. Commit and exit:
   ```
   console_send("{node_name}", "commit and-quit\\n")
   ```
""",

    "arista_eos": """
**Arista EOS SSH Setup:**

1. Enter configuration mode:
   ```
   console_send("{node_name}", "configure\\n")
   ```

2. Create user:
   ```
   console_send("{node_name}", "username {username} privilege 15 secret {password}\\n")
   ```

3. Enable SSH (usually enabled by default):
   ```
   console_send("{node_name}", "management ssh\\n")
   console_send("{node_name}", "idle-timeout 0\\n")
   console_send("{node_name}", "exit\\n")
   ```

4. Save configuration:
   ```
   console_send("{node_name}", "end\\n")
   console_send("{node_name}", "write memory\\n")
   ```
""",

    "linux": """
**Linux/Alpine SSH Setup:**

1. Install OpenSSH server (if not installed):
   ```
   console_send("{node_name}", "apk add openssh\\n")  # Alpine
   # OR
   console_send("{node_name}", "apt-get install openssh-server\\n")  # Debian/Ubuntu
   ```

2. Set root password or create user:
   ```
   console_send("{node_name}", "passwd\\n")  # Then send password twice
   # OR create user
   console_send("{node_name}", "adduser {username}\\n")  # Follow prompts
   ```

3. Start SSH service:
   ```
   console_send("{node_name}", "rc-service sshd start\\n")  # Alpine
   # OR
   console_send("{node_name}", "systemctl start ssh\\n")  # SystemD
   ```

4. Enable SSH on boot:
   ```
   console_send("{node_name}", "rc-update add sshd\\n")  # Alpine
   # OR
   console_send("{node_name}", "systemctl enable ssh\\n")  # SystemD
   ```
"""
}


async def render_ssh_setup_prompt(
    node_name: str,
    device_type: str,
    username: str = "admin",
    password: str = "admin"
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
    device_instructions = DEVICE_CONFIGS.get(device_type, f"""
**Generic SSH Setup (device_type: {device_type}):**

Device-specific instructions not available. General steps:
1. Use console_send() to access device configuration mode
2. Create a user account with administrative privileges
3. Enable SSH service
4. Generate SSH keys if required
5. Configure SSH access permissions
6. Save configuration

Refer to device documentation for specific commands.
""")

    # Format instructions with parameters
    device_instructions = device_instructions.format(
        node_name=node_name,
        username=username,
        password=password
    )

    workflow = f"""# SSH Setup Workflow for {node_name}

This guided workflow helps you enable SSH access on **{node_name}** ({device_type}).

## Prerequisites

- Node must be running (check with resource `gns3://projects/{{id}}/nodes/`)
- Console access available (check with resource `gns3://sessions/console/{node_name}`)
- Know the device's management IP address

## Step 1: Configure SSH on Device (via Console)

Use console tools to configure SSH access on the device:

{device_instructions}

## Step 2: Verify Device Configuration

Read console output to verify commands executed successfully:
```
console_read("{node_name}", mode="diff")
```

Look for success messages and note any errors.

## Step 3: Find Management IP Address

Get the device's management interface IP:
```
console_send("{node_name}", "show ip interface brief\\n")  # Cisco
# OR
console_send("{node_name}", "/ip address print\\n")  # MikroTik
# OR
console_send("{node_name}", "show interfaces terse\\n")  # Juniper
# OR
console_send("{node_name}", "ip addr\\n")  # Linux
```

Then read the output:
```
console_read("{node_name}", mode="last_page")
```

Identify the management IP (e.g., 192.168.1.10).

## Step 4: Establish SSH Session

### Option A: Direct Connection (Default)

For devices reachable from GNS3 host, use default proxy:
```
ssh_configure("{node_name}", {{
    "device_type": "{device_type}",
    "host": "192.168.1.10",  # Replace with actual IP
    "username": "{username}",
    "password": "{password}",
    "port": 22
}})
```

### Option B: Via Lab Proxy (Isolated Networks - v0.26.0)

**Use this when the device is on an isolated network unreachable from GNS3 host.**

1. Discover available lab proxies:
```
# Check resource: gns3://proxy/registry
```

2. Configure SSH through lab proxy:
```
ssh_configure("{node_name}", {{
    "device_type": "{device_type}",
    "host": "10.199.0.20",  # Device IP on isolated network
    "username": "{username}",
    "password": "{password}",
    "port": 22
}}, proxy="<proxy_id>")  # Use proxy_id from registry
```

Example for isolated network 10.199.0.0/24:
```
# 1. Find A-PROXY's proxy_id from gns3://proxy/registry
# Returns: proxy_id="3f3a56de-19d3-40c3-9806-76bee4fe96d4"

# 2. Configure SSH through A-PROXY
ssh_configure("A-CLIENT", {{
    "device_type": "linux",
    "host": "10.199.0.20",
    "username": "alpine",
    "password": "alpine"
}}, proxy="3f3a56de-19d3-40c3-9806-76bee4fe96d4")
```

**How Multi-Proxy Routing Works:**
- First call to ssh_configure() stores proxy mapping
- All subsequent ssh_command() calls automatically route through same proxy
- No need to specify proxy again for each command

## Step 5: Test SSH Connection

Verify SSH works by running a show command:
```
ssh_command("{node_name}", "show version")  # Or appropriate command for device
```

## Step 6: Verify Session Status

Check SSH session is active:
```
# Use resource: gns3://sessions/ssh/{node_name}
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
1. Use `ssh_command()` for all automation tasks
2. Review command history with resource `gns3://sessions/ssh/{node_name}/history`
3. Disconnect console session if no longer needed: `console_disconnect("{node_name}")`

SSH provides better reliability and automatic prompt detection compared to console.
"""

    return workflow
