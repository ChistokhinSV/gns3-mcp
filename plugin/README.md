# GNS3 Lab plugin

Lets Claude build, wire, configure and troubleshoot GNS3 network labs. The plugin
bundles two things:

- **The `gns3` MCP server** ([gns3-mcp](https://pypi.org/project/gns3-mcp/)), started on
  your computer with `uvx`. It gives Claude 15 tools for projects, nodes, links, consoles,
  SSH, drawings, notifications and topology export.
- **The `gns3-lab-automation` skill**, which tells Claude how to use those tools: which
  calls to make for each step, the console first-access rule, timing, and troubleshooting.

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

Claude Code:

```bash
/plugin marketplace add ChistokhinSV/gns3-mcp
/plugin install gns3-lab@gns3-mcp
```

claude.ai / Cowork: **Customize > Plugins > Add > Add marketplace**, enter
`ChistokhinSV/gns3-mcp`, then add **GNS3 Lab**.

## Settings

Claude Code prompts for host, port, username and password (the password goes to the
system credential store). Empty fields fall back, in order, to:

1. environment variables `GNS3_HOST`, `GNS3_PORT`, `GNS3_USER`, `GNS3_PASSWORD`
2. a `.env` file in the working directory
3. `~/.gns3-mcp/.env` (or the file named by `GNS3_MCP_ENV_FILE`)

For Cowork, create `~/.gns3-mcp/.env`:

```bash
GNS3_HOST=192.168.1.20
GNS3_PORT=80
GNS3_USER=admin
GNS3_PASSWORD=your-password
```

## Data

The server talks only to your GNS3 server (and, for SSH/TFTP/HTTP tools, to the GNS3 SSH
proxy container in your lab). Tool results - node lists, console and command output -
go to Claude as conversation content. Nothing is sent anywhere else.
