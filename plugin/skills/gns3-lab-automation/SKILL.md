---
name: gns3-lab-automation
description: Build, wire, configure and troubleshoot GNS3 network labs through the gns3 MCP tools - projects, nodes (RAM, CPUs, QEMU disks, CD-ROM, options), links, device consoles, SSH, drawings and topology export. Use when the user mentions GNS3, a network lab or topology, lab routers/switches/firewalls/VMs, or asks to create, start, cable, configure or debug lab devices.
---

# GNS3 Lab Automation

The `gns3` MCP server drives a GNS3 v3 server. Every call goes through its tools; never call the GNS3 REST API with curl - the server handles JWT auth.

## Tools at a glance

| Tool | Use it for |
|---|---|
| `project` | `list`, `open` (by name), `create` (auto-opens), `close` |
| `node` | `list`, `create` from a template, `delete`, `set` (properties and start/stop/suspend/reload/restart; wildcards) |
| `link` | `list`, `batch` connect/disconnect (validated before anything changes) |
| `console` | batch of `send`, `send_and_wait`, `read`, `keystroke` on telnet consoles |
| `ssh` | batch of `configure`, `command`, `read`, `disconnect` through the SSH proxy (Netmiko) |
| `node_file` | Docker nodes: `read`, `write`, `configure_network` |
| `project_docs` | `get` / `update` the project README (IPs, credentials, notes) |
| `drawing` | `list`, `create`, `update`, `delete`, `batch` (rectangles, ellipses, lines, text) |
| `export_topology_diagram` | SVG/PNG of the canvas |
| `notification` | live GNS3 events: `subscribe`, `read`, `unsubscribe`, `status` |
| `query_resource` | read any resource URI (see below) |
| `gns3_connection` | `check`, `retry`, `reconnect` (after a GNS3 restart) |
| `tftp`, `http_client` | lab services on the SSH proxy |
| `search_tools` | find a tool by category or capability |

## Ground rules

1. **Know the current project.** Node, link, console and drawing tools act on the server's current project. After a server restart it picks the first *opened* project - with several open, call `project(action="open", name=...)` first.
2. **Read before you write.** `project_docs(action="get")` holds IP plans and credentials. `query_resource("projects://<id>/topology_report")` gives nodes, links and status in one call.
3. **Nodes boot slowly.** `node(action="set", state_action="start")` waits up to ~60 s for `started`; consoles and SSH need the OS to finish booting after that.
4. **Console first-access rule.** The first batch for a node that was never accessed may only contain `read` ops; other ops are skipped. Read once, then send.
5. **Trust the reports.** A `node` result with `unapplied_properties` or `Warning: not applied by GNS3` means GNS3 ignored those keys - fix the key name for that node type instead of retrying. Error `details` carry GNS3's reason (missing image, connected switch, node must be stopped).
6. **Record what you build** (IPs, logins, purpose) with `project_docs(action="update")`.

## Find things

```python
project(action="list")
project(action="open", name="Lab1")
node(action="list", project_id="<id>")                    # table; format="json" for details
query_resource("projects://<id>/topology_report")         # nodes + links + status
query_resource("nodes://<project_id>/<node_id>")         # ports, ram, cpus, disks, options
query_resource("templates://")                           # template names for node create
link(action="list", project_id="<id>")                   # port names and link ids
```

Other URIs: `links://<pid>/`, `drawings://<pid>/`, `projects://<pid>/readme`, `templates://<tid>`, `nodes://<pid>/<nid>/template`, `sessions://console/`, `sessions://ssh/<node>/history`, `proxies:///status`, `diagrams://<pid>/topology`.

## Build a topology

```python
# Nodes - hardware applies on create and set (set needs the node stopped for most changes)
node(action="create", template_name="Cisco IOSv", node_name="R1", x=0, y=0)
node(action="create", template_name="Ethernet switch", node_name="SW1", x=200, y=0)
node(action="create", template_name="Ubuntu Cloud Guest", node_name="ops1", x=400, y=0,
     ram=8192, cpus=4, adapters=2,
     hda_disk_image="ops1-60G.qcow2",       # boot disk (image must exist on the GNS3 server)
     cdrom_image="ops1-seed.iso",           # e.g. cloud-init seed
     options="-cpu host")                   # x86-64-v2 guests (glibc 2.34+) need this

# Anything else GNS3 knows for the node type goes through properties
node(action="set", node_name="ops1", properties={"adapter_type": "virtio-net-pci"})
```

Disk slots: `hda` = boot, `hdb` = second, `hdc` via `properties`, `hdd` = fourth (not the boot disk). Switch `ports` can change only while no links are attached.

### Cabling

```python
link(action="batch", connections=[
    # Port names are clearest: the name fixes adapter AND port
    {"action": "connect", "node_a": "R1", "adapter_a": "GigabitEthernet0/0", "port_a": 0,
     "node_b": "SW1", "adapter_b": "Ethernet1", "port_b": 0},
    # Numbers: (adapter, port). Switches keep every port on adapter 0, so port_b=2 is Ethernet2
    {"action": "connect", "node_a": "ops1", "adapter_a": 0, "port_a": 0,
     "node_b": "SW1", "adapter_b": 0, "port_b": 2},
])
link(action="batch", connections=[{"action": "disconnect", "link_id": "<id from link list>"}])
```

All operations are validated first (nodes exist, ports free, names resolve); nothing changes unless all pass. Names are case-sensitive - take them from `link list` or the node's `ports`.

### Power

```python
node(action="set", node_name="*", state_action="start")          # all, in parallel
node(action="set", node_name="R*", state_action="stop")
node(action="set", node_name='["R1","R2"]', state_action="restart", parallel=False)
```

Patterns: `*`, `Prefix*`, `*-Suffix`, `R[123]`, JSON array.

## Configure devices over the console

```python
console(operations=[{"type": "read", "node_name": "R1", "mode": "last_page"}])   # first access
console(operations=[
    {"type": "send", "node_name": "R1", "data": "\n"},
    {"type": "send_and_wait", "node_name": "R1", "command": "show ip interface brief\n",
     "wait_pattern": "R1#", "timeout": 30, "handle_pagination": True},
])
# Wait-only (boot, login prompt): omit "command" - nothing is sent
console(operations=[{"type": "send_and_wait", "node_name": "ops1",
                     "wait_pattern": "login:", "timeout": 300}])
```

- Check the real prompt with `read mode="last_page"` before choosing `wait_pattern` (a regex).
- `read` modes: `diff` (new output, default), `last_page`, `num_pages` + `pages`, `all`; grep with `pattern`, `case_insensitive`, `before`/`after`/`context`.
- `keystroke` keys: `enter`, `ctrl_c`, `ctrl_z`, `up`, `down`, `tab`, `space`, ...
- Keep each CLI line short; some consoles (FortiOS, older IOS) drop long pasted lines.
- Device-specific prompts, enable/config modes and first-boot steps: `references/devices.md`.

## Automate over SSH

Enable SSH on the device via the console first, then:

```python
ssh(operations=[
    {"type": "configure", "node_name": "R1", "device_dict": {
        "device_type": "cisco_ios", "host": "10.1.0.1", "username": "admin", "password": "<from project_docs>"}},
    {"type": "command", "node_name": "R1", "command": "show version"},
    {"type": "command", "node_name": "R1", "command": ["interface Gi0/1", "ip address 10.1.2.1 255.255.255.0", "no shutdown"]},
])
ssh(operations=[{"type": "command", "node_name": "@", "command": "ping -c 2 10.1.0.1"}])  # "@" = on the proxy
```

- `host` is the device's lab IP, not the proxy. `proxy` (default `host`) picks a lab proxy for isolated networks: see `query_resource("proxies://")`.
- Session options: `force` (fresh session), `session_timeout`, `persist`; command options: `expect_string`, `read_timeout`, `wait_timeout`.
- Sessions expire after 30 min idle and are recreated automatically; after a lab restart use `force: True`.
- Netmiko `device_type` values for common images: `references/devices.md`.

## Docker nodes

```python
node_file(action="configure_network", node_name="client1", interfaces=[
    {"name": "eth0", "mode": "static", "address": "10.0.0.10", "netmask": "255.255.255.0", "gateway": "10.0.0.1"}])
node_file(action="read", node_name="client1", file_path="etc/hosts")
node_file(action="write", node_name="client1", file_path="etc/motd", content="lab client\n")
```

`configure_network` restarts the container. QEMU nodes don't support `node_file` - use the console.

## Document and visualise

```python
project_docs(action="update", content="# Lab1\n\n| Node | Mgmt IP | Login |\n|---|---|---|\n| R1 | 10.1.0.1 | admin |\n")
drawing(action="create", drawing_type="rectangle", x=-50, y=-50, width=500, height=200,
        fill_color="#e8f4ff", border_color="#3366cc")
drawing(action="create", drawing_type="text", x=-40, y=-80, text="Site A", font_size=14, font_weight="bold")
export_topology_diagram(output_path="C:/labs/lab1", format="both")   # writes .svg and .png
```

## Watch events

```python
notification(action="subscribe", project_id="<id>")
notification(action="read", mode="diff", filter_action="node.updated")   # or 'log.error', 'link.'
```

## Troubleshoot

| Symptom | Do this |
|---|---|
| Tools fail after GNS3 restart, stale consoles | `gns3_connection(action="reconnect")` |
| "No project opened" / wrong project | `project(action="list")`, then `open` |
| Console times out | node `started`? read `last_page` to see the real prompt; boot may still run - wait-only `send_and_wait` |
| `unapplied_properties` / "not applied by GNS3" | key unknown for that node type; check `nodes://<pid>/<nid>` |
| `The image '<x>' is missing` | upload the image to the GNS3 server first |
| `Cannot change ports on a switch that is already connected` | disconnect its links, resize, reconnect |
| SSH `SSH_DISCONNECTED` | re-run `configure` with `force: True` |
| Link "port in use" | `link list`, disconnect the old link in the same batch |

Lab-wide troubleshooting by OSI layer is available as the server prompt "Troubleshooting Workflow"; other prompts: "Lab Setup Workflow", "Node Setup Workflow", "SSH Setup Workflow", "Topology Discovery Workflow".
