# Installing the GNS3 Skill

The `gns3-lab-automation` skill teaches Claude how to use the gns3 MCP tools: which calls to make
for each lab task, the console first-access rule, timing, and troubleshooting. It lives in the
Claude plugin at `plugin/skills/gns3-lab-automation/` (`SKILL.md` plus `references/devices.md`).

## Recommended: install the plugin

The plugin installs the skill **and** the MCP server together and keeps both up to date:

```bash
# Claude Code
/plugin marketplace add ChistokhinSV/gns3-mcp
/plugin install gns3-lab@gns3-mcp
```

claude.ai / Cowork: **Customize > Plugins > Add > Add marketplace**, enter `ChistokhinSV/gns3-mcp`,
then add **GNS3 Lab**. Settings and requirements: [plugin/README.md](plugin/README.md).

## Alternative: copy the skill only

Use this when you already run the MCP server another way (`.mcpb`, uvx, Docker) and only want the
skill. Skills in `~/.claude/skills/` are available in every Claude Code project.

```powershell
# Windows (PowerShell), from the repository root
$dest = "$env:USERPROFILE\.claude\skills\gns3-lab-automation"
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Copy-Item -Path "plugin\skills\gns3-lab-automation\*" -Destination $dest -Recurse -Force
```

```bash
# macOS / Linux, from the repository root
mkdir -p ~/.claude/skills/gns3-lab-automation
cp -R plugin/skills/gns3-lab-automation/. ~/.claude/skills/gns3-lab-automation/
```

Copying again after `git pull` updates it. A copied skill does not update itself - the plugin does.

## Check that it loads

Start a new Claude Code session and ask "What skills do you have for GNS3?". Claude should list
`gns3-lab-automation`; describing a lab task (for example "start all routers and show their
interfaces") should load it automatically.

## Resources

- [Claude Code skills](https://code.claude.com/docs/en/skills)
- [Claude plugins](https://claude.com/docs/plugins/overview)
- [GNS3 documentation](https://docs.gns3.com/)
