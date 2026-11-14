# GNS3 Lab plugin

Lets Claude build, wire, configure and troubleshoot GNS3 network labs. The plugin
bundles two things:

- **The `gns3` MCP server** ([gns3-mcp](https://pypi.org/project/gns3-mcp/)), started on
  your computer with `uvx`. It gives Claude 15 tools for projects, nodes, links, consoles,
  SSH, drawings, notifications and topology export.
- **The `gns3-lab-automation` skill**, which tells Claude how to use those tools: which
  calls to make for each step, the console first-access rule, timing, and troubleshooting.

GNS3 Lab is a community plugin. It is not made or endorsed by the GNS3 project or GNS3
Technologies; GNS3 is a trademark of its owners.

## Where it works

| App | Works? |
|---|---|
| Claude Code (terminal, IDE, desktop Code tab) | Yes. Asks for the GNS3 settings when you enable the plugin |
| Cowork in the desktop app (session on your computer) | Yes. Cowork does not ask for settings - put them in `~/.gns3-mcp/.env` |
| Chat on claude.ai / desktop / mobile | Skill only. Chat does not start local servers; on Claude Desktop use the `.mcpb` extension instead |

## Requirements

- [uv](https://docs.astral.sh/uv/getting-started/installation/) on your `PATH` (`uvx` downloads
  the server and a matching Python on first start).
- A GNS3 server v3.x that your computer can reach.

## Install

Claude Code in a terminal:

```bash
/plugin marketplace add ChistokhinSV/gns3-mcp
/plugin install gns3-lab@gns3-mcp
```

Claude Code in the desktop app: typing `/plugin ...` there only opens the plugin browser,
which lists plugins from the marketplaces you have already added. Add this one from a
terminal once - the desktop app reads the same settings - with one command that adds the
marketplace and installs the plugin:

```bash
claude plugin install gns3-lab --marketplace ChistokhinSV/gns3-mcp
```

claude.ai / Cowork: **Customize > Plugins > Add > Add marketplace**, enter
`ChistokhinSV/gns3-mcp`, then add **GNS3 Lab**.

## Settings

Claude Code prompts for host, port, username and password (the password goes to the
system credential store). After a shell install, set them in a terminal session with
`/plugin configure gns3-lab@gns3-mcp`, or leave them empty. Empty fields fall back, in
order, to:

1. environment variables `GNS3_HOST`, `GNS3_PORT`, `GNS3_USER`, `GNS3_PASSWORD`
2. a `.env` file in the working directory
3. `~/.gns3-mcp/.env` (or the file named by `GNS3_MCP_ENV_FILE`)

For Cowork, create `~/.gns3-mcp/.env`, or let `uvx gns3-mcp configure manual` ask for the
values, check the login and write the file:

```bash
GNS3_HOST=192.168.1.20
GNS3_PORT=80
GNS3_USER=admin
GNS3_PASSWORD=your-password
```

## What it runs and contacts

- **On start**: `uvx` downloads the pinned `gns3-mcp` package and its dependencies from
  PyPI (and a matching Python if needed), then runs the server locally over stdio.
- **Your GNS3 server**: the GNS3 v3 REST API (login, projects, nodes, links, drawings,
  notifications) and the telnet consoles of your lab devices, at the host and port you set.
- **Your lab's SSH proxy**: only for the SSH, TFTP and HTTP tools - the gns3-ssh-proxy
  container on the GNS3 host (port 8022), which reaches devices inside the lab.
- **Claude**: tool results - node lists, console and command output - go to Claude as
  conversation content.

Nothing is sent anywhere else: no telemetry, no other hosts. The source is at
https://github.com/ChistokhinSV/gns3-mcp.
