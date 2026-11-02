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

    node_section = (
        f"**Troubleshooting Node: {node_name}** (use it in place of R1 in the examples)\n"
        if node_name
        else ""
    )

    issue_section = ""
    if issue_type:
        # (focus description, where to start in the workflow)
        issue_map = {
            "connectivity": ("network connectivity issues", "Steps 1, 3-5"),
            "console": ("console access problems", "Step 2"),
            "ssh": ("SSH connection failures", "Step 8"),
            "performance": ("performance degradation", "Step 7"),
        }
        focus, start = issue_map.get(issue_type, (issue_type, "Step 1"))
        issue_section = f"\n**Focus Area: {focus}** - start with {start}\n"

    workflow = f"""# Network Troubleshooting Workflow

{node_section}{issue_section}
Systematic troubleshooting of GNS3 labs with the gns3 MCP tools. Replace R1, SW1, Host1 (Linux)
and `<project_id>` with real names and IDs.

## Methodology

Work bottom-up through the OSI model:
1. **Layer 1 (Physical)**: node state, links, cabling
2. **Layer 2 (Data Link)**: interfaces, VLANs, MAC tables
3. **Layer 3 (Network)**: IP addressing, routing, reachability
4. **Layer 4+ (Transport/Application)**: services, firewalls, DNS

Prefer `ssh` once SSH works on a device. Use `console` before the device has an IP/SSH,
for devices without SSH, or when the network path itself is broken.

## Step 1: Verify Lab State

```python
project_docs(action="get")                                 # IP plan, credentials, known issues
project(action="list")                                     # find <project_id>; open it if needed
query_resource("projects://<project_id>/topology_report")  # nodes + links + status
node(action="list", project_id="<project_id>")             # status, console type and port
```

Key checks:
- Affected nodes are **started** (not stopped or suspended) and booted without errors
- Links exist between the intended ports and are not suspended
- Tools fail or sessions are stale after a GNS3 restart: `gns3_connection(action="reconnect")`

```python
node(action="set", node_name="R1", state_action="start")   # waits up to ~60 s for 'started'
node(action="set", node_name="*", state_action="start")    # all nodes, in parallel
node(action="set", node_name="R1", state_action="reload")  # reboot a hung node
notification(action="subscribe", project_id="<project_id>")
notification(action="read", filter_action="log.error")     # or "node.updated", "link."
```

## Step 2: Verify Console Access

```python
query_resource("sessions://console/")                      # active console sessions
# First batch for a never-accessed node may only contain 'read' ops
console(operations=[{{"type": "read", "node_name": "R1", "mode": "last_page"}}])
console(operations=[
    {{"type": "send", "node_name": "R1", "data": "\\n"}},    # wake the console
    {{"type": "read", "node_name": "R1", "mode": "last_page"}},
])
```

**Common console issues:**
- **Connection refused**: node not started or console port not open. Start it, wait 10-30 s, retry.
- **Timeout / no output**: node still booting, or console type is not `telnet` (see `node list`).
  Wait for the boot without sending anything (omit `command`):
```python
console(operations=[{{"type": "send_and_wait", "node_name": "R1",
                      "wait_pattern": "login:|[>#]", "timeout": 300}}])
```
- **Stuck CLI or garbled output**: break out and re-check the prompt. If it stays broken,
  `gns3_connection(action="reconnect")` clears all console sessions; they reopen on next use.
```python
console(operations=[
    {{"type": "keystroke", "node_name": "R1", "key": "ctrl_c"}},
    {{"type": "keystroke", "node_name": "R1", "key": "enter"}},
    {{"type": "read", "node_name": "R1", "mode": "last_page"}},
])
```
- **`wait_pattern` never matches**: it is a regex; confirm the real prompt with `read` `last_page`.

## Step 3: Layer 1 - Physical Connectivity

```python
link(action="list", project_id="<project_id>")     # port names and link ids
export_topology_diagram(output_path="C:/labs/troubleshooting", format="svg")
```

Diagram port colours: green = node started and link active; red = node stopped OR link suspended.

**Common Layer 1 issues:**
- **Red port / link**: start the stopped node(s). The tools cannot resume a suspended link -
  resume it in the GNS3 GUI, or disconnect and reconnect it in one `link` batch.
- **Missing or mis-cabled link**: compare ports with the device interfaces, then fix in one
  validated batch (nothing changes unless every operation passes):
```python
link(action="batch", connections=[
    {{"action": "disconnect", "link_id": "<link_id from link list>"}},
    {{"action": "connect", "node_a": "R1", "adapter_a": "GigabitEthernet0/0", "port_a": 0,
     "node_b": "R2", "adapter_b": "GigabitEthernet0/0", "port_b": 0}},
])
```

## Step 4: Layer 2 - Data Link

```python
ssh(operations=[
    {{"type": "command", "node_name": "R1", "command": "show interfaces"}},
    {{"type": "command", "node_name": "SW1", "command": "show interfaces status"}},
    {{"type": "command", "node_name": "SW1", "command": "show vlan brief"}},
    {{"type": "command", "node_name": "SW1", "command": "show mac address-table"}},
])
```
MikroTik: `/interface print`. Linux: `ip link show`.

**Common Layer 2 issues:**
- **Interface administratively down** - a command list is sent as config commands:
```python
ssh(operations=[{{"type": "command", "node_name": "R1",
                  "command": ["interface GigabitEthernet0/0", "no shutdown"]}}])
```
- **VLAN mismatch** (devices on the same link can't talk): access ports in the same VLAN,
  or the trunk allows the VLAN.
- **MAC flapping / duplicate MACs** (intermittent connectivity): the same MAC on several ports in
  `show mac address-table` - often a Layer 2 loop.

## Step 5: Layer 3 - Network

```python
ssh(operations=[
    {{"type": "command", "node_name": "R1", "command": "show ip interface brief"}},
    {{"type": "command", "node_name": "R1", "command": "show ip route"}},
    {{"type": "command", "node_name": "R1", "command": "show ip arp"}},
    {{"type": "command", "node_name": "R1", "command": "show ip ospf neighbor"}},
])
```
MikroTik: `/ip address print`, `/ip route print`. Linux: `ip addr show`, `ip route show`.

**Common Layer 3 issues:**
- **IP address missing** ("unassigned"): no IP means no SSH - configure over the console:
```python
console(operations=[
    {{"type": "send_and_wait", "node_name": "R1", "command": "configure terminal\\n", "wait_pattern": "#"}},
    {{"type": "send_and_wait", "node_name": "R1", "command": "interface GigabitEthernet0/0\\n", "wait_pattern": "#"}},
    {{"type": "send_and_wait", "node_name": "R1", "command": "ip address 192.168.1.1 255.255.255.0\\n", "wait_pattern": "#"}},
    {{"type": "send_and_wait", "node_name": "R1", "command": "no shutdown\\n", "wait_pattern": "#"}},
    {{"type": "send_and_wait", "node_name": "R1", "command": "end\\n", "wait_pattern": "R1#"}},
])
```
- **IP conflict** ("Duplicate address" warnings): check `show ip arp`; every device needs a unique IP.
- **Subnet mismatch** (link up, ping fails): both ends must share the subnet.
  192.168.1.1/24 <-> 192.168.1.2/24 works; 192.168.1.1/24 <-> 192.168.2.1/24 does not.
- **No route** ("Destination/Network unreachable"): add a static route or fix the routing
  protocol (`show ip protocols`, `show ip ospf neighbor`, `show ip bgp summary`):
```python
ssh(operations=[{{"type": "command", "node_name": "R1",
                  "command": ["ip route 10.0.0.0 255.0.0.0 192.168.1.254"]}}])
```

**Test reachability** from the device and from the SSH proxy (`"@"`):
```python
ssh(operations=[
    {{"type": "command", "node_name": "R1", "command": "ping 192.168.1.2"}},
    {{"type": "command", "node_name": "@", "command": "ping -c 2 192.168.1.2"}},
])
console(operations=[{{"type": "send_and_wait", "node_name": "R1",
                      "command": "ping 192.168.1.2 repeat 100\\n",
                      "wait_pattern": "Success rate", "timeout": 120}}])
```

## Step 6: Layer 4+ - Services and Applications

```python
ssh(operations=[
    {{"type": "command", "node_name": "Host1", "command": "systemctl status sshd"}},
    {{"type": "command", "node_name": "Host1", "command": "ss -tuln"}},    # listening ports
    {{"type": "command", "node_name": "Host1", "command": "iptables -L -n -v"}},
    {{"type": "command", "node_name": "R1", "command": "show ip sockets"}},
])
```

**Common service issues:**
- **Connection refused** to a service port: service not running - `systemctl start sshd`.
- **Connection timeout** (not refused): firewall dropping traffic - review `iptables -L -n -v`.
- **IP works, hostname fails**: DNS - test with `nslookup` / `dig`, check the resolver config.

## Step 7: Performance

```python
ssh(operations=[
    {{"type": "command", "node_name": "R1", "command": "show processes cpu sorted"}},
    {{"type": "command", "node_name": "R1", "command": "show memory statistics"}},
    {{"type": "command", "node_name": "R1", "command": "show interfaces | include rate"}},
    {{"type": "command", "node_name": "R1", "command": "show interfaces GigabitEthernet0/0 | include error"}},
])
```
Linux: `top -b -n 1 | head -20`, `free -h`, `ip -s link show`.

**Common performance issues:**
- **High CPU**: routing loops, broadcast storms (Layer 2 loop - check spanning-tree), software bugs.
- **Interface errors**: input - duplex mismatch or bad link; output - oversubscription, buffering.
- **Packet loss**: extended ping, then read "Success rate" (long commands need `read_timeout`).
  Intermittent loss: congestion or physical issue. Complete loss: Layer 1-3 configuration.
```python
ssh(operations=[{{"type": "command", "node_name": "R1",
                  "command": "ping 192.168.1.2 repeat 1000", "read_timeout": 120}}])
```

## Step 8: SSH Troubleshooting

```python
query_resource("sessions://ssh/R1")              # session state
query_resource("sessions://ssh/R1/history")      # recent commands and results
query_resource("proxies:///status")              # main SSH proxy health
query_resource("proxies://")                     # lab proxies for isolated networks
ssh(operations=[{{"type": "command", "node_name": "@", "command": "ping -c 2 192.168.1.1"}}])
```

**Common SSH issues:**
- **Connection refused**: SSH not enabled - enable it over the console ("SSH Setup Workflow" prompt).
- **Authentication failed**: check credentials in `project_docs`, then on the device:
```python
console(operations=[{{"type": "send_and_wait", "node_name": "R1",
                      "command": "show running-config | include username\\n", "wait_pattern": "R1#"}}])
```
- **Host unreachable**: Layer 1-3 problem between proxy and device - Steps 3-5. Devices on isolated
  networks need a lab proxy: set `"proxy"` in the `configure` op (ids from `proxies://`).
- **Timeout on slow commands**: raise `read_timeout` on the command op (see Step 7).
- **SSH_DISCONNECTED / stale session after a lab restart**: re-configure with `force`:
```python
ssh(operations=[
    {{"type": "configure", "node_name": "R1", "force": True, "device_dict": {{
        "device_type": "cisco_ios", "host": "192.168.1.1",
        "username": "admin", "password": "<from project_docs>"}}}},
    {{"type": "command", "node_name": "R1", "command": "show version"}},
])
```

## Step 9: Log Collection

```python
ssh(operations=[
    {{"type": "command", "node_name": "R1", "command": "show logging"}},
    {{"type": "command", "node_name": "Host1", "command": "journalctl -n 100 --no-pager"}},
])
query_resource("sessions://ssh/R1/buffer")       # full SSH output buffer
console(operations=[{{"type": "read", "node_name": "R1", "mode": "all",
                      "pattern": "error|down", "case_insensitive": True, "context": 2}}])
notification(action="read", filter_action="log.")  # GNS3 server log events
```

Once fixed, save the config: `ssh` command `write memory` (keep `show running-config` as a backup).

## Step 10: Baseline Comparison

- Compare the topology diagram and configs with the known-good design in the project docs
- What changed before the issue: new nodes, edited configs, different images or versions?
- Record root cause and fix: `project_docs(action="get")`, add notes, then
  `project_docs(action="update", content="<full README>")` (update replaces the whole README)

## Troubleshooting Decision Tree

```
Issue detected
  |- Tools fail / stale sessions? -> gns3_connection(action="reconnect")
  |- Nodes not started?           -> node set state_action="start", wait for boot
  |- Link red or missing?         -> start nodes, re-cable with link batch
  |- Console not accessible?      -> node started? console type telnet? read last_page
  |- Interface down?              -> "no shutdown", check cabling
  |- No IP address?               -> configure over console, verify subnet
  |- Can't ping?                  -> routes, ARP, ping from the proxy ("@")
  |- Service not working?         -> service status, listening ports, firewall
  |- Slow or lossy?               -> CPU/memory, interface errors, Layer 2 loops
```

## Quick Reference

- Resources via `query_resource(uri)`: `projects://<project_id>/topology_report`,
  `nodes://<project_id>/`, `nodes://<project_id>/<node_id>`, `links://<project_id>/`,
  `sessions://console/`, `sessions://ssh/<node_name>`, `sessions://ssh/<node_name>/history`,
  `proxies:///status`, `proxies://`
- Related prompts: "SSH Setup Workflow", "Topology Discovery Workflow"
- Prevention: save configs after changes, keep IP plan/VLANs/credentials in the project docs,
  export diagrams as a baseline, stop unused nodes and close unused projects
"""

    return workflow
