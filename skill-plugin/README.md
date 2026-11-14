# GNS3 Lab Guide

Teaches Claude how to build, wire, configure and troubleshoot GNS3 network labs with the
`gns3` MCP server: which tool calls to make for each step, the console first-access rule,
boot timing, device-specific prompts and login sequences, and how to diagnose links and
consoles.

This plugin contains one skill, `gns3-lab-automation`, and nothing that runs on its own.
The tools it uses come from the open-source `gns3-mcp` server, which runs on your computer
and talks to your GNS3 3.x server. Set it up once in a terminal:

```bash
uvx gns3-mcp configure claude
```

It asks for the GNS3 host, port, user and password, checks the login, saves the settings in
`~/.gns3-mcp/.env` and registers the server with Claude Code. Use another agent's name
instead of `claude` for Cursor, VS Code, Codex and others. It needs
[uv](https://docs.astral.sh/uv/getting-started/installation/). Step-by-step guide:
https://chistokhinsv.github.io/gns3-mcp

Install this plugin from the project's marketplace (in a terminal; the Claude desktop app reads
the same settings):

```bash
claude plugin install gns3-lab-guide --marketplace ChistokhinSV/gns3-mcp
```

If you want the server and the skill in one install for Claude Code and Cowork, use the full
**GNS3 Lab** plugin from the project's own marketplace instead of this one (installing both
loads the skill twice):

```bash
claude plugin install gns3-lab --marketplace ChistokhinSV/gns3-mcp
```

## What it runs and contacts

The skill itself runs nothing and sends nothing. When the user asks for lab work and the
`gns3` tools are missing, it tells Claude to ask the user to run the setup command above.
The `gns3-mcp` server, once set up, talks only to the GNS3 server you configure (its REST API
and device consoles) and, for SSH, TFTP and HTTP tools, to the lab's SSH proxy container.

GNS3 Lab Guide is a community plugin. It is not made or endorsed by the GNS3 project or GNS3
Technologies; GNS3 is a trademark of its owners. Source and issues:
https://github.com/ChistokhinSV/gns3-mcp
