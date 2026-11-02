"""Node Setup Workflow Prompt

Complete workflow for adding a new node to a lab: create, configure IP, document in README, establish SSH.
"""

import ipaddress
import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class _Node:
    name: str
    ip: str
    netmask: str  # dotted, e.g. 255.255.255.0
    prefix: str  # prefix length, e.g. 24
    username: str
    password: str
    device_type: str


def _call(head: str, items: list[dict[str, Any]]) -> str:
    """Render `<head>[...])` with one dict per line.

    json.dumps (not f-string interpolation) keeps user values with quotes and regex
    backslashes valid in the rendered example.
    """
    if len(items) == 1:
        return f"{head}[{json.dumps(items[0])}])"
    lines = "\n".join(f"    {json.dumps(item)}," for item in items)
    return f"{head}[\n{lines}\n])"


def _console(*ops: dict[str, Any]) -> str:
    return _call("console(operations=", list(ops))


def _sw(node: str, command: str | None, pattern: str, timeout: int = 30) -> dict[str, Any]:
    """send_and_wait op. command=None is wait-only (nothing sent); "" sends just Enter."""
    op: dict[str, Any] = {"type": "send_and_wait", "node_name": node}
    if command is not None:
        op["command"] = command + "\n"
    op["wait_pattern"] = pattern
    op["timeout"] = timeout
    return op


def _cisco_ios(d: _Node) -> str:
    n = d.name
    # Unanchored: IOS log lines (%LINK-3-UPDOWN, %SSH-5-ENABLED) can arrive after the prompt
    ios = "#"
    boot = _console(_sw(n, "", r"\[yes/no\]:|RETURN to get started|[>#]\s*$", 180))
    dialog = _console(_sw(n, "no", r"RETURN to get started|[>#]\s*$", 120))
    iface = _console(
        _sw(n, "", r"[>#]\s*$"),
        _sw(n, "enable", ios),
        _sw(n, "configure terminal", ios),
        _sw(n, "interface GigabitEthernet0/0", ios),
        _sw(n, f"ip address {d.ip} {d.netmask}", ios),
        _sw(n, "no shutdown", ios),
        _sw(n, "end", ios),
        _sw(n, "show ip interface brief", ios),
    )
    ssh = _console(
        _sw(n, "configure terminal", ios),
        _sw(n, f"hostname {n}", ios),
        _sw(n, "ip domain-name lab.local", ios),
        _sw(n, f"username {d.username} privilege 15 secret {d.password}", ios),
        _sw(n, "crypto key generate rsa modulus 2048", ios, 120),
        _sw(n, "ip ssh version 2", ios),
        _sw(n, "line vty 0 4", ios),
        _sw(n, "login local", ios),
        _sw(n, "transport input ssh", ios),
        _sw(n, "end", ios),
        _sw(n, "write memory", ios, 60),
    )
    return f"""**Cisco IOS IP Configuration** (fresh IOSv prompts: `Router>`, `Router#`)

**1. Wait for boot** (30-60 s after `started`); Enter wakes the console:

```python
{boot}
```

If the output asks `initial configuration dialog? [yes/no]:`, answer `no`:

```python
{dialog}
```

**2. Configure the management interface and verify** (last result = `show ip interface brief`):

```python
{iface}
```

**3. Enable SSH and save** (RSA keys need a hostname other than `Router` and a domain name):

```python
{ssh}
```
"""


def _linux(d: _Node) -> str:
    n = d.name
    sh = r"[#$]\s*$"
    login = _console(
        _sw(n, "", r"login:|[#$]\s*$", 300),
        _sw(n, "root", r"[Pp]assword:|[#$]\s*$"),
    )
    temp_ip = _console(
        _sw(n, f"ip addr add {d.ip}/{d.prefix} dev eth0", sh),
        _sw(n, "ip link set eth0 up", sh),
        _sw(n, "ip addr show eth0", sh),
    )
    interfaces = (
        "cat > /etc/network/interfaces << 'EOF'\n"
        "auto lo\niface lo inet loopback\n\n"
        "auto eth0\niface eth0 inet static\n"
        f"    address {d.ip}\n    netmask {d.netmask}\nEOF"
    )
    persist = _console(
        _sw(n, interfaces, sh),
        _sw(n, "/etc/init.d/networking restart", sh, 60),
    )
    user = _console(
        _sw(n, "rc-update add sshd default", sh),
        _sw(n, "service sshd start", sh, 60),
        _sw(n, f"adduser {d.username}", r"[Pp]assword:"),
        _sw(n, d.password, "Retype"),
        _sw(n, d.password, sh),
        _sw(n, f"addgroup {d.username} wheel", sh),
    )
    return f"""**Linux IP Configuration** (Alpine example)

**1. Wait for boot (10-20 s) and log in as root:**

```python
{login}
```

If `Password:` appears, send the image's root password (template usage, Step 2.5).

**2. Configure IP address (temporary) and verify:**

```python
{temp_ip}
```

**3. Make it persistent** (Alpine `/etc/network/interfaces`):

```python
{persist}
```

**4. Enable SSH and create user {d.username}** (no `sshd` service? `apk add openssh` first, needs internet):

```python
{user}
```
"""


def _mikrotik_routeros(d: _Node) -> str:
    n = d.name
    ros = r"\] >"
    login = _console(
        _sw(n, "", r"Login:|\] >", 180),
        _sw(n, "admin", "Password:"),
        _sw(n, "", r"\[Y/n\]|password>|\] >"),
    )
    first_login = _console(
        _sw(n, "n", r"password>|\] >"),
        _sw(n, "<new admin password>", "password>"),
        _sw(n, "<new admin password>", ros),
    )
    ip = _console(
        _sw(n, f"/ip address add address={d.ip}/{d.prefix} interface=ether1", ros),
        _sw(n, "/ip address print", ros),
    )
    ssh = _console(
        _sw(n, f"/user add name={d.username} password={d.password} group=full", ros),
        _sw(n, "/ip service enable ssh", ros),
    )
    return f"""**MikroTik RouterOS IP Configuration** (prompt `[admin@MikroTik] >`)

**1. Wait for boot and log in** (admin / blank password):

```python
{login}
```

RouterOS 7 then asks to view the license (`[Y/n]`) and to set a new admin password; record it in the README:

```python
{first_login}
```

**2. Configure IP address and verify:**

```python
{ip}
```

**3. Create SSH user and enable SSH service:**

```python
{ssh}
```
"""


def _generic(d: _Node) -> str:
    example = _console(
        _sw(d.name, "", r"[Ll]ogin:|[>#$]\s*$", 180),
        _sw(d.name, "<CLI command>", "<prompt regex>"),
    )
    return f"""**Generic IP Configuration (device_type: {d.device_type}):**

1. Access device console and log in (credentials: template usage, Step 2.5)
2. Configure IP address {d.ip}/{d.prefix} on the management interface
3. Enable SSH service
4. Create user {d.username} with password
5. Verify configuration

Send each CLI line as a `send_and_wait` with the device prompt regex as `wait_pattern`
(check the real prompt with a `read` in `last_page` mode first):

```python
{example}
```

Refer to device documentation for specific commands.
"""


_IP_CONFIGS = {
    "cisco_ios": _cisco_ios,
    "linux": _linux,
    "mikrotik_routeros": _mikrotik_routeros,
}
_MGMT_INTERFACE = {
    "cisco_ios": "GigabitEthernet0/0",
    "linux": "eth0",
    "mikrotik_routeros": "ether1",
}
_VERIFY_COMMAND = {"linux": "uname -a", "mikrotik_routeros": "/system resource print"}


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
        subnet_mask: Subnet mask (default: "255.255.255.0"; a prefix length like "24" also works)
        device_type: Device type for SSH (cisco_ios, linux, etc.)
        username: SSH username to create (default: "admin")
        password: SSH password to set (default: "admin")

    Returns:
        Formatted workflow instructions as string
    """
    try:
        net = ipaddress.IPv4Network(f"0.0.0.0/{subnet_mask}")
        netmask, prefix = str(net.netmask), str(net.prefixlen)
    except ValueError:
        netmask = prefix = subnet_mask

    d = _Node(node_name, ip_address, netmask, prefix, username, password, device_type)
    ip_config = _IP_CONFIGS.get(device_type, _generic)(d)
    mgmt_if = _MGMT_INTERFACE.get(device_type, "<mgmt interface>")

    nq, tq = json.dumps(node_name), json.dumps(template_name)
    first_read = _console({"type": "read", "node_name": node_name, "mode": "last_page"})
    wait_only = _console(_sw(node_name, None, r"[Ll]ogin:|[>#$]\s*$", 300))
    device_dict = {
        "device_type": device_type,
        "host": ip_address,
        "username": username,
        "password": password,
        "port": 22,
    }
    configure_op = {"type": "configure", "node_name": node_name, "device_dict": device_dict}
    command_op = {
        "type": "command",
        "node_name": node_name,
        "command": _VERIFY_COMMAND.get(device_type, "show version"),
    }
    ssh_configure = _call("ssh(operations=", [configure_op])
    ssh_proxy = _call("ssh(operations=", [{**configure_op, "proxy": "<proxy_id>"}])
    ssh_verify = _call("ssh(operations=", [command_op])
    ssh_full = _call("ssh(operations=", [configure_op, command_op])
    ssh_ping = _call(
        "ssh(operations=",
        [{"type": "command", "node_name": "@", "command": f"ping -c 2 {ip_address}"}],
    )
    link_batch = _call(
        'link(action="batch", connections=',
        [
            {
                "action": "connect",
                "node_a": node_name,
                "adapter_a": 1,
                "port_a": 0,
                "node_b": "ExistingRouter",
                "adapter_b": 1,
                "port_b": 0,
            }
        ],
    )

    workflow = f"""# Complete Node Setup: {node_name}

This workflow guides you through setting up **{node_name}** from scratch.

**What This Does:**
1. Create node from template
2. Start node and wait for boot
3. Configure IP address via console
4. Document IP/credentials in project README
5. Establish SSH session for automation

Console ops in one `console(operations=[...])` batch run in order. Each `send_and_wait`
result carries `output` and `pattern_found` - check `pattern_found` before the next step.
`wait_pattern` is a regex.

## Prerequisites

- The right project is current: `project(action="list")`, then `project(action="open", name="<project>")` if needed
- Template "{template_name}" exists: `query_resource("templates://")`

## Step 1: Create Node

```python
node(action="create", template_name={tq}, node_name={nq}, x=100, y=100)
```

Note `node_id` from the result - resource URIs below need the ID, not the name.
`project_id`: `project(action="list")`.

## Step 2: Start Node

```python
node(action="set", node_name={nq}, state_action="start")  # waits up to ~60 s for 'started'
```

`started` means the VM runs; the OS keeps booting:
- Cisco routers: 30-60 seconds
- Linux nodes: 10-20 seconds
- MikroTik: 15-30 seconds

The first console batch for a node may contain only `read` ops (others are skipped), so open it with:

```python
{first_read}
```

## Step 2.5: Check Template Usage Field

```python
query_resource("nodes://<project_id>/<node_id>/template")
```

**The usage field may contain:**
- Default credentials for initial login
- Special boot procedures or timing requirements
- Device-specific configuration quirks and interface naming
- Management interface defaults

Review it before Step 3 to avoid common pitfalls.

## Step 3: Configure IP Address

{ip_config}
## Step 4: Document in Project README

`update` replaces the whole README, so read it first:

```python
project_docs(action="get")
```

Append this section to the returned markdown:

```markdown
## Node: {node_name}
- IP Address: {ip_address}/{prefix} ({mgmt_if})
- Template: {template_name}, device_type: {device_type}
- Credentials: {username} / {password} (SSH port 22)
- Purpose / connected to: <fill in>
```

```python
project_docs(action="update", content=readme)  # readme = existing README + section above
```

## Step 5: Establish SSH Session

Device reachable from the GNS3 host:

```python
{ssh_configure}
```

Isolated lab network: take a `proxy_id` from `query_resource("proxies://")` and add it:

```python
{ssh_proxy}
```

## Step 6: Verify SSH Connection

```python
{ssh_verify}
```

Session status: `query_resource("sessions://ssh/{node_name}")`

## Step 7: Connect to Network (Optional)

```python
{link_batch}
```

Numbers are (adapter, port): adapter 1 port 0 is the node's second interface. A port name in
`adapter_*` (case-sensitive, e.g. "Gi0/1", "eth1") fixes adapter and port; get names from
`link(action="list", project_id="<project_id>")` or `query_resource("nodes://<project_id>/<node_id>")`.
Then add the connection to the README (Step 4).

## Completion Checklist

- [ ] Node created and started
- [ ] IP address configured and verified
- [ ] Credentials documented in README
- [ ] SSH session established and tested
- [ ] Network connections made (if needed)
- [ ] Configuration saved on device

## Next Steps

1. **Configure routing protocols** (OSPF, BGP, etc.) over SSH
2. **Back up before major changes**: save the device config and keep key settings in the README (there is no snapshot tool)
3. **Update architecture notes** in the README with role and relationships
4. **Review the lab**: `query_resource("projects://<project_id>/topology_report")`

## Troubleshooting

**Node won't start:**
- Read the error `details` of the `node` result (missing image, not enough RAM/CPU)
- Check the template: `query_resource("templates://")`
- GNS3 errors: `notification(action="subscribe", project_id="<project_id>")`, then `notification(action="read", filter_action="log.error")`

**Can't access console:**
- Node `started`, console type `telnet`: `query_resource("nodes://<project_id>/<node_id>")`
- Sends skipped? The first batch for a node may only contain `read` ops
- Still booting: `{first_read}` shows the real prompt; wait without sending: `{wait_only}`
- Stale consoles after a GNS3 restart: `gns3_connection(action="reconnect")`

**SSH connection fails:**
- Ping from the SSH proxy: `{ssh_ping}`
- Confirm SSH service is running and the user exists (Step 3)
- Stale session (`SSH_DISCONNECTED`): re-run `configure` with `"force": True`

**IP not working:**
- Verify interface is up (`no shutdown` for Cisco)
- Check correct interface name used
- Confirm subnet doesn't conflict with existing network
- Verify physical connections if connecting to other nodes

## Example: Complete Workflow

```python
node(action="create", template_name={tq}, node_name={nq}, x=100, y=100)
node(action="set", node_name={nq}, state_action="start")
{first_read}
# Step 3 console batches - check pattern_found in each result
project_docs(action="get")
project_docs(action="update", content=readme)  # existing README + node section
{ssh_full}
```

**Success!** {node_name} is now ready for network automation.
"""

    return workflow
