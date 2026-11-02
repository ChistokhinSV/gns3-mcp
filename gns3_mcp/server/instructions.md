# GNS3 MCP Server

Automation for GNS3 v3 network labs: projects, nodes, links, device consoles (telnet), SSH through a proxy, drawings, notifications and topology export.

## Rules

- **Use these tools only.** The GNS3 API needs JWT auth that the server handles; never call it with curl or httpx.
- **Current project.** Node, link, console and drawing tools act on the server's current project. GNS3 can have several projects open; after a server restart the first opened one is picked. Call `project(action="open", name=...)` when in doubt.
- **Read before you change.** `project_docs(action="get")` keeps the lab's IP plan and credentials; `query_resource("projects://<id>/topology_report")` shows nodes, links and status in one call.
- **Nodes boot slowly.** `node(action="set", state_action="start")` waits up to ~60 s for `started`; the device OS needs more time before its console or SSH answers.
- **Console first access.** The first `console` batch for a node never accessed may contain only `read` operations; other operations are skipped. Read once, then send.
- **Trust what results say.** `unapplied_properties` (create) or `Warning: not applied by GNS3` (set) means GNS3 ignored those keys for that node type. Error `details` carry GNS3's reason (missing image, connected switch, node must be stopped).
- **Record what you build** with `project_docs(action="update", content=...)`.

## Tools

| Tool | Actions / operations |
|---|---|
| `project` | `list`, `open`, `create` (auto-opens), `close` |
| `node` | `list`, `create` (from template), `delete`, `set` (properties; `state_action` start/stop/suspend/reload/restart) |
| `link` | `list`, `batch` of `connect` / `disconnect` (all validated before any change) |
| `console` | batch of `send`, `send_and_wait`, `read`, `keystroke` |
| `ssh` | batch of `configure`, `command`, `read`, `disconnect` (Netmiko, via SSH proxy) |
| `node_file` | Docker nodes: `read`, `write`, `configure_network` |
| `project_docs` | `get`, `update` the project README |
| `drawing` | `list`, `create`, `update`, `delete`, `batch` |
| `export_topology_diagram` | SVG/PNG of the canvas |
| `notification` | `subscribe`, `read`, `unsubscribe`, `status` |
| `query_resource` | read any resource URI (list below) |
| `gns3_connection` | `check`, `retry`, `reconnect` |
| `tftp`, `http_client` | TFTP files and HTTP requests through the SSH proxy |
| `search_tools` | find tools by category or capability |

## Nodes

```python
node(action="create", template_name="Cisco IOSv", node_name="R1", x=0, y=0)
node(action="create", template_name="Ubuntu Cloud Guest", node_name="ops1", x=200, y=0,
     ram=8192, cpus=4, adapters=2, hda_disk_image="ops1-60G.qcow2",
     cdrom_image="seed.iso", options="-cpu host")
node(action="set", node_name="ops1", properties={"adapter_type": "virtio-net-pci"})
node(action="set", node_name="*", state_action="start")        # all nodes, in parallel
```

- Hardware params apply on `create` and `set` (most need the node stopped). Disk slots: `hda` boot, `hdb` second, `hdc` via `properties`, `hdd` fourth.
- Patterns for `set`/`delete`: `*`, `R*`, `*-Core`, `R[123]`, JSON array `'["R1","R2"]'`. Several nodes return a batch result with `succeeded_items` / `failed_items`.
- Switch `ports` can change only while no links are attached.

## Links

```python
link(action="batch", connections=[
    {"action": "connect", "node_a": "R1", "adapter_a": "GigabitEthernet0/0", "port_a": 0,
     "node_b": "SW1", "adapter_b": "Ethernet2", "port_b": 0},
    {"action": "disconnect", "link_id": "<id from link list>"},
])
```

A port name in `adapter_*` fixes adapter and port (`port_*` ignored); with numbers the link uses (`adapter_*`, `port_*`) - switches keep all ports on adapter 0. Names are case-sensitive.

## Console

```python
console(operations=[{"type": "read", "node_name": "R1", "mode": "last_page"}])        # first access
console(operations=[
    {"type": "send", "node_name": "R1", "data": "\n"},
    {"type": "send_and_wait", "node_name": "R1", "command": "show ip route\n",
     "wait_pattern": "R1#", "timeout": 30, "handle_pagination": True},
])
console(operations=[{"type": "send_and_wait", "node_name": "R1",
                     "wait_pattern": "login:", "timeout": 180}])   # no command = wait only
```

- `read` modes: `diff` (new output, default), `last_page` (25 lines), `num_pages` + `pages`, `all` (whole buffer - use rarely). Grep with `pattern`, `case_insensitive`, `before` / `after` / `context`.
- Check the real prompt with `last_page` before choosing a `wait_pattern` (regex).
- `keystroke` keys: `enter`, `ctrl_c`, `ctrl_z`, `ctrl_d`, `esc`, `tab`, `space`, `up`, `down`, `backspace`.
- `raw: True` on `send` skips escape processing (e.g. MikroTik). Keep pasted lines short on FortiOS and older IOS.
- Sessions close after 30 min idle; buffers keep all output (10 MB cap).

## SSH

Enable SSH on the device through the console first, then:

```python
ssh(operations=[
    {"type": "configure", "node_name": "R1", "device_dict": {
        "device_type": "cisco_ios", "host": "10.1.0.1", "username": "admin", "password": "..."}},
    {"type": "command", "node_name": "R1", "command": "show version"},
    {"type": "command", "node_name": "R1", "command": ["interface Gi0/1", "no shutdown"]},
])
ssh(operations=[{"type": "command", "node_name": "@", "command": "ping -c 2 10.1.0.1"}])  # on the proxy
```

- `host` is the device's lab IP. `proxy` (default `host`) picks a lab proxy for isolated networks: `query_resource("proxies://")`.
- Options: `force: True` for a fresh session (after a lab restart), `session_timeout`; per command `expect_string`, `read_timeout`, `wait_timeout` (long jobs report progress).
- Sessions expire after 30 min idle and are recreated on the next `configure`.

## Notifications

```python
notification(action="subscribe", project_id="<id>")          # omit project_id for controller events
notification(action="read", filter_action="node.updated")    # modes: diff (default), all, last + limit
```

Project events: `node.*`, `link.*`, `drawing.*`, `snapshot.restored`, `ping`. Controller events: `compute.*`, `project.*`, `template.*`, `log.error|warning|info`, `ping` (CPU/memory). One subscription at a time; buffer keeps 5000 events.

## Resources (`query_resource`)

`projects://`, `projects://<id>`, `projects://<id>/readme`, `projects://<id>/topology_report`, `nodes://<pid>/`, `nodes://<pid>/<nid>`, `nodes://<pid>/<nid>/template`, `links://<pid>/`, `drawings://<pid>/`, `templates://`, `templates://<tid>`, `sessions://console/`, `sessions://ssh/`, `sessions://ssh/<node>/history`, `sessions://ssh/<node>/buffer`, `proxies:///status`, `proxies://`, `diagrams://<pid>/topology`.

## Connection

The server starts without waiting for GNS3 and authenticates in the background (retry 5 s -> 300 s). `gns3_connection(action="check")` shows the state and last error, `retry` re-authenticates now, `reconnect` also clears console/SSH/notification sessions (use after a GNS3 restart).

## Troubleshooting

| Symptom | Do this |
|---|---|
| "No project opened" / wrong project | `project(action="list")`, then `project(action="open", name=...)` |
| Console times out or is silent | node `started`? `read` with `last_page`; boot may still run - wait-only `send_and_wait` |
| Console type is vnc/spice | only telnet consoles are supported; change with `node(action="set", console_type="telnet")` (node stopped) |
| SSH `SSH_DISCONNECTED` | `configure` again with `force: True` |
| `unapplied_properties` | key unknown for that node type - check `nodes://<pid>/<nid>` |
| `The image '<x>' is missing` | upload the image to the GNS3 server first |
| Link "port in use" | `link(action="list")`, disconnect the old link in the same batch |
| Tools fail after GNS3 restart | `gns3_connection(action="reconnect")` |

Guided workflows are available as prompts: "Node Setup Workflow", "Lab Setup Workflow", "SSH Setup Workflow", "Topology Discovery Workflow", "Troubleshooting Workflow".
