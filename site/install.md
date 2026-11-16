# Install the GNS3 MCP server (steps for AI agents)

You are an AI agent and the user asked you to install the GNS3 MCP server from
https://chistokhinsv.github.io/gns3-mcp. Follow these steps. They need a terminal; if you
cannot run commands, show the user step 4 and let them run it.

## 1. Know which agent you are

`gns3-mcp configure` takes one of these names:

| Name | Agent |
|---|---|
| `claude` | Claude Code |
| `claude-desktop` | Claude Desktop |
| `cursor` | Cursor |
| `vscode` | GitHub Copilot in VS Code |
| `windsurf` | Windsurf (Devin Desktop) |
| `cline` | Cline |
| `kiro` | Kiro |
| `opencode` | OpenCode |
| `codex` | OpenAI Codex |
| `gemini` | Gemini CLI |

If you are not sure, ask the user. If your agent is not listed, run
`uvx gns3-mcp@latest configure --instructions` and follow the manual guide it prints.

## 2. Check uv

Run `uvx --version`. If it is missing, ask the user before installing uv:

- Windows (PowerShell): `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
- macOS / Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`

Open a new terminal afterwards so `uvx` is on `PATH`.

## 3. Get the GNS3 settings

Ask the user for:

- GNS3 server host or IP (for example `192.168.1.20`)
- API port: `80` on the GNS3 VM, `3080` for a gns3server installed directly
- Username (often `admin`)
- Whether the server uses HTTPS (rare)

If `~/.gns3-mcp/.env` already exists, its saved settings are the defaults; the user may only need
to confirm them.

## 4. Run configure

**Preferred:** ask the user to run this in their own terminal. It asks for the password without
showing it:

```bash
uvx gns3-mcp@latest configure <agent>
```

**If the user wants you to run it** and gives you the password: pass the password only through
the `GNS3_PASSWORD` environment variable, never as a command-line argument, never repeat it in
your messages and never write it to a file yourself.

bash / zsh:

```bash
GNS3_PASSWORD='<password>' uvx gns3-mcp@latest configure <agent> --host <host> --port <port> --user <user> --yes
```

PowerShell:

```powershell
$env:GNS3_PASSWORD = '<password>'; uvx gns3-mcp@latest configure <agent> --host <host> --port <port> --user <user> --yes; Remove-Item Env:GNS3_PASSWORD
```

Add `--https` for HTTPS, `--no-verify-ssl` for a self-signed certificate, `--project` to write
the project's config files in the current folder instead of the user-wide config, and
`--dry-run` to see what would change.

**Updates.** Interactively, the last question is whether to update automatically (default yes).
With `--yes` auto-update is on unless you add `--no-auto-update`. Auto-update makes the agent run
`uvx gns3-mcp@latest`, which needs internet at each start: ask the user whether the machine
always has internet, and pass `--no-auto-update` (pin this version) if it does not.

## 5. Check the result

The output shows `login check: OK`, the saved settings file and each file written. If the
login check fails, tell the user the reason it prints (it never contains the password) and
fix the host, port or user. Nothing is written when the check fails.

## 6. Finish

Tell the user to restart the agent (the `next:` line of the output says how), then ask:
"List my GNS3 projects". The answer should come from the `gns3` tools.

## What configure changes

- `~/.gns3-mcp/.env`: the GNS3 settings, read by the server. Agent configs hold no secrets.
- The agent's MCP config: one server entry `gns3` that runs `uvx gns3-mcp@latest` (auto-update)
  or `uvx gns3-mcp@<version>` (pinned). Other
  servers and settings stay; a backup `*.gns3-mcp-backup` is kept of each file before the first
  change.
- The agent's rules file: a short block between `<!-- gns3-mcp:begin -->` and
  `<!-- gns3-mcp:end -->` telling the agent to use the `gns3` tools (`--no-instructions` skips it).

Running configure again updates the same entries; it never adds duplicates.

## Updating

Auto-update: restart the agent. Pinned: `uvx gns3-mcp@latest configure <agent> --yes` (keeps the
saved settings and the pin choice, writes the new version), then restart the agent. Always run
configure as `gns3-mcp@latest`: a plain `uvx gns3-mcp` keeps using the version uvx cached first.
`gns3_connection(action="check")` reports `update_available` when PyPI has a newer release.
