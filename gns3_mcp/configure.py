"""`gns3-mcp configure <agent>`: register the GNS3 MCP server with an AI agent (GM-102)

Modelled on `npx webiny-mcp configure <agent>`: asks for the GNS3 settings, checks the login,
saves them in ~/.gns3-mcp/.env (the server reads that file, so agent configs hold no secrets),
then adds the server to the agent's MCP config and a short instructions file or block to its
rules.

Where each agent reads its config: the agents' docs (checked 2026-11-14) and, where they
overlap, the table Ansible Flow Designer's "Set Up AI Assistants" tested on 2026-11-08.
- Only our entry changes: other servers and keys the user or the agent added stay.
- Every file gets a one-time *.gns3-mcp-backup before our first change.
- A file that is not plain JSON (comments) is left alone; the entry is printed instead.
"""

from __future__ import annotations

import argparse
import dataclasses
import getpass
import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from gns3_mcp import __version__

SERVER_NAME = "gns3"
PACKAGE = "gns3-mcp"
SITE_URL = "https://chistokhinsv.github.io/gns3-mcp"
BACKUP_SUFFIX = ".gns3-mcp-backup"

MANAGED_NOTE = "written by `gns3-mcp configure`; run it again to update"
MD_BEGIN = f"<!-- gns3-mcp:begin ({MANAGED_NOTE}) -->"
MD_END = "<!-- gns3-mcp:end -->"
TOML_BEGIN = f"# >>> gns3 ({MANAGED_NOTE})"
TOML_END = "# <<< gns3"

INSTRUCTIONS = """\
## GNS3 lab

A `gns3` MCP server controls the GNS3 network lab: projects, nodes, links, device consoles, SSH \
and drawings.

- Use the `gns3` tools for all lab work. Never call the GNS3 REST API directly; the server \
handles authentication.
- Start with `project(action="list")` and `project(action="open", name=...)`, then read \
`project_docs(action="get")` for the lab's IP plan and credentials.
- `node(action="delete")` with a pattern and `project(action="delete")` only preview until \
called again with `confirm=True`.
- GNS3 settings are in `~/.gns3-mcp/.env`; `uvx gns3-mcp configure <agent>` changes them.
"""


# ---------------------------------------------------------------------------------------------
# Environment: where things are on this machine (a parameter, so tests use a temporary home)
# ---------------------------------------------------------------------------------------------

ENV_VARS = (
    "APPDATA",
    "LOCALAPPDATA",
    "XDG_CONFIG_HOME",
    "CODEX_HOME",
    "COPILOT_HOME",
    "CLINE_MCP_SETTINGS_PATH",
    "CLINE_DATA_DIR",
    "CLINE_DIR",
)


@dataclass(frozen=True)
class Env:
    home: Path
    cwd: Path
    platform: str
    vars: Mapping[str, str] = field(default_factory=dict)

    @classmethod
    def current(cls) -> Env:
        return cls(
            home=Path.home(),
            cwd=Path.cwd(),
            platform=sys.platform,
            vars={k: v for k in ENV_VARS if (v := os.environ.get(k))},
        )

    def var(self, name: str) -> Path | None:
        value = self.vars.get(name)
        return Path(value) if value else None

    def app_config(self) -> Path:
        """The per-user settings folder of desktop apps (Claude Desktop, VS Code)"""
        if self.platform == "win32":
            return self.var("APPDATA") or self.home / "AppData" / "Roaming"
        if self.platform == "darwin":
            return self.home / "Library" / "Application Support"
        return self.xdg_config()

    def xdg_config(self) -> Path:
        return self.var("XDG_CONFIG_HOME") or self.home / ".config"


@dataclass(frozen=True)
class Launch:
    """How an agent starts the server"""

    command: str
    args: tuple[str, ...]


def launch_for(project: bool) -> Launch:
    """uvx with the version that ran configure.

    User-wide configs get uvx's full path: desktop apps started from a menu often have a
    shorter PATH than the terminal (no ~/.local/bin). Project files keep plain `uvx` so they
    work on other machines.
    """
    found = None if project else shutil.which("uvx")
    return Launch(found or "uvx", (f"{PACKAGE}@{__version__}",))


# ---------------------------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------------------------


def _std_entry(launch: Launch) -> dict:
    return {"command": launch.command, "args": list(launch.args)}


def _vscode_entry(launch: Launch) -> dict:
    return {"type": "stdio", **_std_entry(launch)}


def _copilot_entry(launch: Launch) -> dict:
    return {"type": "local", **_std_entry(launch), "tools": ["*"]}


def _opencode_entry(launch: Launch) -> dict:
    return {"type": "local", "command": [launch.command, *launch.args], "enabled": True}


def _opencode_v2_entry(launch: Launch) -> dict:
    return {"type": "local", "command": [launch.command, *launch.args]}


@dataclass(frozen=True)
class McpFile:
    """One JSON file an agent reads servers from"""

    user: Callable[[Env], Path | None]
    project: Callable[[Env], Path | None] = lambda env: None
    container: tuple[str, ...] = ("mcpServers",)
    entry: Callable[[Launch], dict] = _std_entry
    # Keys of an existing entry that are ours; others (disabled, autoApprove, tools...) stay
    managed: tuple[str, ...] = ("command", "args")
    # Picks the layout from what the file already holds (OpenCode's two formats)
    adapt: Callable[[dict, McpFile], McpFile] | None = None


def _opencode_adapt(data: dict, spec: McpFile) -> McpFile:
    """OpenCode 1.19 reads mcp.servers.<name>; mcp.<name> + enabled is the older, still valid form"""
    mcp = data.get("mcp")
    if isinstance(mcp, dict) and isinstance(mcp.get("servers"), dict):
        return dataclasses.replace(spec, container=("mcp", "servers"), entry=_opencode_v2_entry)
    return spec


def _opencode_file(base: Path) -> Path:
    """OpenCode reads opencode.jsonc or opencode.json; ours goes in the one that exists"""
    jsonc = base / "opencode.jsonc"
    return jsonc if jsonc.exists() else base / "opencode.json"


def _claude_desktop_config(env: Env) -> Path:
    """%APPDATA%\\Claude, or the MSIX copy under LocalCache when that one exists"""
    if env.platform == "win32" and (local := env.var("LOCALAPPDATA")):
        pattern = "Claude_*/LocalCache/Roaming/Claude/claude_desktop_config.json"
        for found in sorted((local / "Packages").glob(pattern)):
            return found
    return env.app_config() / "Claude" / "claude_desktop_config.json"


def _cline_settings(env: Env) -> Path:
    """Cline's extension, CLI and JetBrains plugin share one file (moved to ~/.cline in 2026)"""
    if path := env.var("CLINE_MCP_SETTINGS_PATH"):
        return path
    data = env.var("CLINE_DATA_DIR") or (env.var("CLINE_DIR") or env.home / ".cline") / "data"
    return data / "settings" / "cline_mcp_settings.json"


def _copilot_home(env: Env) -> Path:
    return env.var("COPILOT_HOME") or env.home / ".copilot"


def _codex_home(env: Env) -> Path:
    return env.var("CODEX_HOME") or env.home / ".codex"


@dataclass(frozen=True)
class Agent:
    key: str
    title: str
    # "json": a key in JSON files; "codex": marked TOML block; "claude": the claude CLI
    kind: str
    mcp: tuple[McpFile, ...] = ()
    user_rules: Callable[[Env], Path | None] = lambda env: None
    project_rules: Callable[[Env], Path | None] = lambda env: None
    # Front matter of a rules file of our own; None = marked block in a shared file
    rules_header: str | None = None
    restart: str = "Restart the agent"
    notes: tuple[str, ...] = ()


AGENTS: dict[str, Agent] = {
    a.key: a
    for a in (
        Agent(
            key="claude",
            title="Claude Code",
            kind="claude",
            mcp=(McpFile(user=lambda env: None, project=lambda env: env.cwd / ".mcp.json"),),
            user_rules=lambda env: env.home / ".claude" / "rules" / "gns3.md",
            project_rules=lambda env: env.cwd / ".claude" / "rules" / "gns3.md",
            rules_header="",
            restart="Restart Claude Code; check with `claude mcp get gns3`",
        ),
        Agent(
            key="claude-desktop",
            title="Claude Desktop",
            kind="json",
            mcp=(McpFile(user=_claude_desktop_config),),
            restart="Quit Claude Desktop completely (tray icon) and start it again",
            notes=("Claude Desktop has no rules file; the server sends its own instructions.",),
        ),
        Agent(
            key="cursor",
            title="Cursor",
            kind="json",
            mcp=(
                McpFile(
                    user=lambda env: env.home / ".cursor" / "mcp.json",
                    project=lambda env: env.cwd / ".cursor" / "mcp.json",
                ),
            ),
            project_rules=lambda env: env.cwd / ".cursor" / "rules" / "gns3.mdc",
            rules_header="---\ndescription: GNS3 lab through the gns3 MCP server\nalwaysApply: true\n---\n",
            restart="Restart Cursor (or toggle the server in Settings > MCP)",
            notes=("Cursor keeps user rules in its settings; --project writes .cursor/rules.",),
        ),
        Agent(
            key="vscode",
            title="VS Code (GitHub Copilot)",
            kind="json",
            mcp=(
                # Copilot harness (VS Code's default since 2026) and Copilot CLI
                McpFile(
                    user=lambda env: _copilot_home(env) / "mcp-config.json",
                    entry=_copilot_entry,
                    managed=("type", "command", "args"),
                ),
                # VS Code's Local harness (deprecated, removed in Feb 2027)
                McpFile(
                    user=lambda env: env.app_config() / "Code" / "User" / "mcp.json",
                    project=lambda env: env.cwd / ".vscode" / "mcp.json",
                    container=("servers",),
                    entry=_vscode_entry,
                    managed=("type", "command", "args"),
                ),
            ),
            user_rules=lambda env: _copilot_home(env) / "instructions" / "gns3.instructions.md",
            project_rules=lambda env: env.cwd / ".github" / "instructions" / "gns3.instructions.md",
            rules_header="---\napplyTo: '**'\n---\n",
            restart="Reload VS Code; start the server from the MCP list if it does not start",
            notes=("Written for both Copilot harnesses; Copilot CLI reads the first file too.",),
        ),
        Agent(
            key="windsurf",
            title="Windsurf / Devin Desktop",
            kind="json",
            mcp=(
                # Devin Desktop still reads Windsurf's file, so one entry serves both
                McpFile(
                    user=lambda env: env.home / ".codeium" / "windsurf" / "mcp_config.json",
                    project=lambda env: env.cwd / ".devin" / "mcp_config.json",
                ),
            ),
            user_rules=lambda env: env.home / ".devin" / "rules" / "gns3.md",
            project_rules=lambda env: env.cwd / ".devin" / "rules" / "gns3.md",
            rules_header="---\ntrigger: always_on\n---\n",
            restart="Restart the app (or refresh the MCP servers panel)",
        ),
        Agent(
            key="cline",
            title="Cline",
            kind="json",
            mcp=(McpFile(user=_cline_settings),),
            user_rules=lambda env: env.home / ".cline" / "rules" / "gns3.md",
            project_rules=lambda env: env.cwd / ".clinerules" / "gns3.md",
            rules_header="",
            restart="Reload VS Code / restart Cline",
        ),
        Agent(
            key="kiro",
            title="Kiro",
            kind="json",
            mcp=(
                McpFile(
                    user=lambda env: env.home / ".kiro" / "settings" / "mcp.json",
                    project=lambda env: env.cwd / ".kiro" / "settings" / "mcp.json",
                ),
            ),
            user_rules=lambda env: env.home / ".kiro" / "steering" / "gns3.md",
            project_rules=lambda env: env.cwd / ".kiro" / "steering" / "gns3.md",
            rules_header="---\ninclusion: always\n---\n",
            restart="Restart Kiro (it asks before each tool call)",
        ),
        Agent(
            key="opencode",
            title="OpenCode",
            kind="json",
            mcp=(
                McpFile(
                    user=lambda env: _opencode_file(env.xdg_config() / "opencode"),
                    project=lambda env: _opencode_file(env.cwd),
                    container=("mcp",),
                    entry=_opencode_entry,
                    managed=("type", "command"),
                    adapt=_opencode_adapt,
                ),
            ),
            user_rules=lambda env: env.xdg_config() / "opencode" / "AGENTS.md",
            project_rules=lambda env: env.cwd / "AGENTS.md",
            restart="Restart OpenCode",
        ),
        Agent(
            key="codex",
            title="Codex",
            kind="codex",
            mcp=(
                McpFile(
                    user=lambda env: _codex_home(env) / "config.toml",
                    project=lambda env: env.cwd / ".codex" / "config.toml",
                ),
            ),
            user_rules=lambda env: _codex_home(env) / "AGENTS.md",
            project_rules=lambda env: env.cwd / "AGENTS.md",
            restart="Restart Codex; check with `codex mcp list`",
            notes=("Codex reads a project's .codex/config.toml only in trusted projects.",),
        ),
        Agent(
            key="gemini",
            title="Gemini CLI",
            kind="json",
            mcp=(
                McpFile(
                    user=lambda env: env.home / ".gemini" / "settings.json",
                    project=lambda env: env.cwd / ".gemini" / "settings.json",
                ),
            ),
            user_rules=lambda env: env.home / ".gemini" / "GEMINI.md",
            project_rules=lambda env: env.cwd / "GEMINI.md",
            restart="Restart Gemini CLI; check with /mcp",
        ),
    )
}

ALIASES = {"devin": "windsurf", "copilot": "vscode", "claude-code": "claude"}


# ---------------------------------------------------------------------------------------------
# Steps: what configure does to one file, planned first so --dry-run can show it
# ---------------------------------------------------------------------------------------------


@dataclass
class Step:
    what: str  # "MCP" or "instructions"
    target: str  # file, or the command for Claude Code
    action: str  # create / update / unchanged / skip / failed
    note: str = ""
    apply: Callable[[], None] | None = None


class ConfigureError(Exception):
    """A problem the user must fix; the message says how"""


def _backup(path: Path) -> None:
    """Keep the file as it was before our first change (never overwritten later)"""
    copy = path.with_name(path.name + BACKUP_SUFFIX)
    if path.exists() and not copy.exists():
        shutil.copy2(path, copy)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _backup(path)
    tmp = path.with_name(path.name + ".gns3-mcp-tmp")
    tmp.write_text(text, encoding="utf-8", newline="")
    os.replace(tmp, path)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        return ""


def _eol(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def _indent(text: str) -> int | str:
    match = re.search(r"\n([ \t]+)\"", text)
    if not match:
        return 2
    return "\t" if "\t" in match.group(1) else len(match.group(1))


def strip_jsonc(text: str) -> tuple[str, bool]:
    """JSON text without // and /* */ comments and trailing commas; True if it had comments.

    Many agents read JSONC (OpenCode, Gemini, VS Code). Without comments the file can be
    rewritten as plain JSON; with them it is only read, since a rewrite would drop them.
    """
    out: list[str] = []
    i, n, comments = 0, len(text), False
    while i < n:
        c = text[i]
        if c == '"':
            j = i + 1
            while j < n and text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            out.append(text[i : j + 1])
            i = j + 1
        elif text.startswith("//", i):
            comments = True
            while i < n and text[i] not in "\r\n":
                i += 1
        elif text.startswith("/*", i):
            comments = True
            end = text.find("*/", i + 2)
            i = n if end < 0 else end + 2
        elif c == ",":
            rest = re.match(r"\s*", text[i + 1 :])
            nxt = i + 1 + (rest.end() if rest else 0)
            if nxt < n and text[nxt] in "}]":
                i += 1  # trailing comma
            else:
                out.append(c)
                i += 1
        else:
            out.append(c)
            i += 1
    return "".join(out), comments


def _nest(container: tuple[str, ...], value: dict) -> dict:
    for key in reversed(container):
        value = {key: value}
    return value


def plan_json(path: Path, spec: McpFile, launch: Launch) -> Step:
    """Our entry as one key of the agent's JSON config; everything else stays"""
    text = _read_text(path)
    plain, comments = strip_jsonc(text)
    try:
        data = json.loads(plain) if plain.strip() else {}
    except json.JSONDecodeError:
        data = None
    if spec.adapt and isinstance(data, dict):
        spec = spec.adapt(data, spec)
    want = spec.entry(launch)
    snippet = json.dumps(_nest(spec.container, {SERVER_NAME: want}), indent=2)
    if data is None:
        note = f"not valid JSON; left as it is - add this by hand:\n{snippet}"
        return Step("MCP", str(path), "skip", note)

    servers: object = data
    for key in spec.container:
        servers = servers.get(key, {}) if isinstance(servers, dict) else None
    if not isinstance(servers, dict):
        return Step("MCP", str(path), "skip", f"unexpected layout; add this by hand:\n{snippet}")

    have = servers.get(SERVER_NAME)
    if isinstance(have, dict):
        new = {**have, **{k: want[k] for k in spec.managed if k in want}}
        action = "unchanged" if new == have else "update"
    else:
        new, action = want, "create"
    note = ""
    if "gns3-mcp" in servers:
        note = "an older entry 'gns3-mcp' is there too - remove it to avoid two servers"
    if action == "unchanged":
        return Step("MCP", str(path), action, note)
    if comments:
        note = (
            "has comments, which a rewrite would drop; left as it is - "
            f"add this by hand:\n{json.dumps(_nest(spec.container, {SERVER_NAME: new}), indent=2)}"
        )
        return Step("MCP", str(path), "skip", note)

    def apply() -> None:
        level = data
        for key in spec.container:
            level = level.setdefault(key, {})
        level[SERVER_NAME] = new
        eol = _eol(text)
        body = json.dumps(data, indent=_indent(text), ensure_ascii=False)
        _write_text(path, body.replace("\n", eol) + eol)

    return Step("MCP", str(path), action, note, apply)


def _split_block(text: str, begin: str, end: str) -> tuple[str, str | None, str]:
    start = text.find(begin)
    stop = text.find(end, start) if start >= 0 else -1
    if start < 0 or stop < 0:
        return text, None, ""
    return text[:start], text[start : stop + len(end)], text[stop + len(end) :]


def _replace_block(text: str, block: str, begin: str, end: str) -> str:
    eol = _eol(text) if text else "\n"
    block = block.replace("\n", eol)
    before, old, after = _split_block(text, begin, end)
    if old is not None:
        return before + block + after
    if not text:
        return block + eol
    sep = "" if text.endswith(eol) else eol
    return text + sep + eol + block + eol


def codex_block(launch: Launch) -> str:
    # TOML basic strings take JSON's escapes for the characters paths and names use
    args = ", ".join(json.dumps(a) for a in launch.args)
    return "\n".join(
        [
            TOML_BEGIN,
            f"[mcp_servers.{SERVER_NAME}]",
            f"command = {json.dumps(launch.command)}",
            f"args = [{args}]",
            TOML_END,
        ]
    )


def plan_codex(path: Path, launch: Launch) -> Step:
    text = _read_text(path)
    before, old, after = _split_block(text, TOML_BEGIN, TOML_END)
    by_hand = re.compile(rf'^\s*\[mcp_servers\.("?){SERVER_NAME}\1\]', re.MULTILINE)
    if by_hand.search(before + after):
        return Step("MCP", str(path), "skip", "[mcp_servers.gns3] was written by hand; left as is")
    block = codex_block(launch)
    if old is not None and old.replace("\r\n", "\n") == block:
        return Step("MCP", str(path), "unchanged")
    action = "create" if old is None else "update"
    new = _replace_block(text, block, TOML_BEGIN, TOML_END)
    return Step("MCP", str(path), action, apply=lambda: _write_text(path, new))


def _claude_args(launch: Launch) -> list[str]:
    return ["mcp", "add", "--scope", "user", SERVER_NAME, "--", launch.command, *launch.args]


def _quote(arg: str) -> str:
    return f'"{arg}"' if re.search(r"\s", arg) else arg


def _run(cli: str, args: list[str]) -> subprocess.CompletedProcess:
    """Runs a CLI; a Windows .cmd shim needs the shell, with every argument quoted"""
    if re.search(r"\.(cmd|bat)$", cli, re.IGNORECASE):
        line = " ".join('"' + a.replace('"', '""') + '"' for a in [cli, *args])
        return subprocess.run(
            line, shell=True, capture_output=True, text=True, timeout=60, check=False
        )
    return subprocess.run([cli, *args], capture_output=True, text=True, timeout=60, check=False)


def plan_claude_user(env: Env, launch: Launch) -> Step:
    """Claude Code's user scope goes through its CLI: ~/.claude.json is its busy state file"""
    cli = shutil.which("claude")
    shown = " ".join(_quote(a) for a in ["claude", *_claude_args(launch)])
    if not cli:
        return Step("MCP", shown, "skip", "claude is not on PATH: run this command once it is")

    have = None
    try:
        data = json.loads(_read_text(env.home / ".claude.json") or "{}")
        have = (data.get("mcpServers") or {}).get(SERVER_NAME)
    except (json.JSONDecodeError, AttributeError):
        pass
    want = _std_entry(launch)
    if isinstance(have, dict) and all(have.get(k) == v for k, v in want.items()):
        return Step("MCP", shown, "unchanged")

    def apply() -> None:
        if have is not None:
            _run(cli, ["mcp", "remove", SERVER_NAME, "--scope", "user"])
        result = _run(cli, _claude_args(launch))
        if result.returncode != 0:
            output = (result.stdout + result.stderr).strip()
            raise ConfigureError(f"claude mcp add failed: {output}")

    return Step("MCP", shown, "create" if have is None else "update", apply=apply)


def _own_rules_text(header: str) -> str:
    comment = f"<!-- {MANAGED_NOTE} -->\n"
    return (header + "\n" if header else "") + comment + "\n" + INSTRUCTIONS


def plan_rules(path: Path, agent: Agent) -> Step:
    text = _read_text(path)
    if agent.rules_header is not None:
        want = _own_rules_text(agent.rules_header)
        if text.replace("\r\n", "\n") == want:
            return Step("instructions", str(path), "unchanged")
        action = "update" if text else "create"
        return Step("instructions", str(path), action, apply=lambda: _write_text(path, want))

    block = f"{MD_BEGIN}\n{INSTRUCTIONS}{MD_END}"
    _, old, _ = _split_block(text, MD_BEGIN, MD_END)
    if old is not None and old.replace("\r\n", "\n") == block:
        return Step("instructions", str(path), "unchanged")
    action = "create" if old is None else "update"
    new = _replace_block(text, block, MD_BEGIN, MD_END)
    return Step("instructions", str(path), action, apply=lambda: _write_text(path, new))


def plan_agent(agent: Agent, env: Env, project: bool, instructions: bool) -> list[Step]:
    launch = launch_for(project)
    steps: list[Step] = []
    if agent.kind == "claude" and not project:
        steps.append(plan_claude_user(env, launch))
    else:
        files: list[tuple[McpFile, Path]] = []
        for spec in agent.mcp:
            path = spec.project(env) if project else spec.user(env)
            if path is not None:
                files.append((spec, path))
        if not files:
            note = f"{agent.title} has no project MCP config; run without --project"
            steps.append(Step("MCP", "-", "skip", note))
        for spec, path in files:
            if agent.kind == "codex":
                steps.append(plan_codex(path, launch))
            else:
                steps.append(plan_json(path, spec, launch))

    if instructions:
        rules = agent.project_rules(env) if project else agent.user_rules(env)
        if rules is not None:
            steps.append(plan_rules(rules, agent))
    return steps


# ---------------------------------------------------------------------------------------------
# GNS3 settings: ~/.gns3-mcp/.env
# ---------------------------------------------------------------------------------------------


def _truthy(value: str | None) -> bool:
    return str(value).strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Settings:
    host: str
    port: int
    user: str
    password: str = field(repr=False)
    https: bool = False
    verify_ssl: bool = True

    @property
    def url(self) -> str:
        return f"{'https' if self.https else 'http'}://{self.host}:{self.port}"

    def env_values(self) -> dict[str, str]:
        return {
            "GNS3_HOST": self.host,
            "GNS3_PORT": str(self.port),
            "GNS3_USER": self.user,
            "GNS3_PASSWORD": self.password,
            "GNS3_USE_HTTPS": "true" if self.https else "false",
            "GNS3_VERIFY_SSL": "true" if self.verify_ssl else "false",
        }


def resolve_settings(
    args: argparse.Namespace,
    saved: Mapping[str, str | None],
    environ: Mapping[str, str],
    ask: Callable[[str, str], str] | None,
    ask_secret: Callable[[str], str] | None,
) -> Settings:
    """Flags > GNS3_* environment > saved ~/.gns3-mcp/.env > built-in defaults.

    With `ask` (interactive), each value not given as a flag is asked, the found value being
    the default. The password is never a flag: it comes from GNS3_PASSWORD, a hidden prompt,
    or the saved file.
    """

    def found(flag: object, key: str, default: str) -> tuple[str, bool]:
        if flag not in (None, ""):
            return str(flag), True
        return str(environ.get(key) or saved.get(key) or default), False

    values = {}
    for name, flag, key, default in (
        ("host", args.host, "GNS3_HOST", ""),
        ("port", args.port, "GNS3_PORT", "80"),
        ("user", args.user, "GNS3_USER", "admin"),
    ):
        value, fixed = found(flag, key, default)
        if ask and not fixed:
            value = ask(f"GNS3 {name}", value) or value
        values[name] = value.strip()

    if not values["host"]:
        raise ConfigureError("GNS3 host is not set: pass --host or set GNS3_HOST")
    try:
        port = int(values["port"])
    except ValueError as e:
        raise ConfigureError(f"GNS3 port must be a number, got {values['port']!r}") from e

    password = environ.get("GNS3_PASSWORD") or ""
    if not password and ask_secret:
        keep = " (Enter keeps the saved one)" if saved.get("GNS3_PASSWORD") else ""
        password = ask_secret(f"GNS3 password{keep}: ")
    password = password or saved.get("GNS3_PASSWORD") or ""
    if not password:
        raise ConfigureError("GNS3 password is not set: set GNS3_PASSWORD or run interactively")

    https = args.https or _truthy(environ.get("GNS3_USE_HTTPS") or saved.get("GNS3_USE_HTTPS"))
    verify = environ.get("GNS3_VERIFY_SSL") or saved.get("GNS3_VERIFY_SSL") or "true"
    return Settings(
        host=values["host"],
        port=port,
        user=values["user"],
        password=password,
        https=https,
        verify_ssl=not args.no_verify_ssl and _truthy(verify),
    )


def check_login(settings: Settings, timeout: float = 10.0) -> str | None:
    """None when GNS3 accepts the login, else what went wrong (never the password)"""
    import httpx

    url = f"{settings.url}/v3/access/users/authenticate"
    try:
        response = httpx.post(
            url,
            json={"username": settings.user, "password": settings.password},
            timeout=timeout,
            verify=settings.verify_ssl,
        )
    except httpx.HTTPError as e:
        return f"cannot reach GNS3 at {settings.url}: {e or type(e).__name__}"
    if response.status_code == 200 and "access_token" in response.text:
        return None
    if response.status_code in (401, 403):
        return f"GNS3 at {settings.url} rejected user '{settings.user}' or the password"
    return f"GNS3 at {settings.url} answered HTTP {response.status_code} (a GNS3 3.x server?)"


def save_settings(path: Path, settings: Settings) -> None:
    """Update the GNS3 keys of the user .env; other keys (MCP_API_KEY, ...) stay"""
    from dotenv import set_key

    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch(mode=0o600)
    for key, value in settings.env_values().items():
        set_key(str(path), key, value)
    if os.name == "posix":
        path.chmod(0o600)


# ---------------------------------------------------------------------------------------------
# --instructions: a manual guide for every agent
# ---------------------------------------------------------------------------------------------


def manual_guide(env: Env) -> str:
    launch = Launch("uvx", (f"{PACKAGE}@{__version__}",))
    fence = "```"

    def rel(path: Path) -> str:
        return path.relative_to(env.cwd).as_posix()

    lines = [
        "# GNS3 MCP server: manual setup",
        "",
        f"Automatic: `uvx gns3-mcp configure <agent>` with one of: {', '.join(AGENTS)}.",
        f"Guide for people and agents: {SITE_URL}",
        "",
        "## 1. GNS3 settings",
        "",
        "Put them in `~/.gns3-mcp/.env`; the server reads it, so agent configs need no secrets:",
        "",
        f"{fence}ini",
        "GNS3_HOST=192.168.1.20",
        "GNS3_PORT=80",
        "GNS3_USER=admin",
        "GNS3_PASSWORD=your-password",
        fence,
        "",
        "## 2. Register the server",
        "",
        "A stdio MCP server named `gns3` started with `uvx gns3-mcp@<version>`. Most agents take:",
        "",
        f"{fence}json",
        json.dumps({"mcpServers": {SERVER_NAME: _std_entry(launch)}}, indent=2),
        fence,
        "",
        "Per agent (paths for this computer):",
        "",
    ]
    for agent in AGENTS.values():
        lines += [f"### {agent.title} (`{agent.key}`)", ""]
        if agent.kind == "claude":
            lines.append(f"- User-wide: `{' '.join(['claude', *_claude_args(launch)])}`")
        snippets = []
        for spec in agent.mcp:
            user, project = spec.user(env), spec.project(env)
            if user:
                lines.append(f"- User-wide config: `{user}`")
            if project:
                lines.append(f"- Project config: `{rel(project)}`")
            if agent.kind != "codex" and (
                spec.container != ("mcpServers",) or spec.entry is not _std_entry
            ):
                snippets.append(
                    json.dumps(_nest(spec.container, {SERVER_NAME: spec.entry(launch)}), indent=2)
                )
        user_rules, project_rules = agent.user_rules(env), agent.project_rules(env)
        where = [f"`{user_rules}`" if user_rules else ""]
        where.append(f"`{rel(project_rules)}` (project)" if project_rules else "")
        if any(where):
            lines.append("- Instructions: " + ", ".join(w for w in where if w))
        lines += [f"- {note}" for note in agent.notes]
        if agent.kind == "codex":
            lines += ["", f"{fence}toml", codex_block(launch), fence]
        for snippet in snippets:
            lines += ["", f"{fence}json", snippet, fence]
        lines.append("")
    lines += [
        "## 3. Agent instructions",
        "",
        "Add this to the agent's rules or instructions file:",
        "",
        f"{fence}markdown",
        INSTRUCTIONS.rstrip(),
        fence,
        "",
        "## 4. Restart the agent",
        "",
        'Then ask it: "List my GNS3 projects".',
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gns3-mcp configure",
        description="Register the GNS3 MCP server with an AI agent and save the GNS3 settings.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Agents: {", ".join(AGENTS)}

Examples:
  uvx gns3-mcp configure claude                 # asks for host, port, user, password
  uvx gns3-mcp configure cursor codex --project # project files in the current folder
  uvx gns3-mcp configure --instructions         # manual setup guide for every agent
  GNS3_PASSWORD=... uvx gns3-mcp configure claude --host 192.168.1.20 --yes

Settings go to ~/.gns3-mcp/.env (GNS3_MCP_ENV_FILE to change); agent configs hold no secrets.
Guide: {SITE_URL}
""",
    )
    parser.add_argument("agents", nargs="*", metavar="agent", help="agent(s) to configure")
    parser.add_argument(
        "--project", action="store_true", help="write project files in the current folder"
    )
    parser.add_argument("--host", help="GNS3 server host or IP")
    parser.add_argument("--port", type=int, help="GNS3 API port (default 80)")
    parser.add_argument("--user", help="GNS3 username (default admin)")
    parser.add_argument("--https", action="store_true", help="connect to GNS3 over HTTPS")
    parser.add_argument(
        "--no-verify-ssl", action="store_true", help="accept a self-signed GNS3 certificate"
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="no prompts: values from flags, GNS3_* variables and the saved .env",
    )
    parser.add_argument(
        "--skip-check", action="store_true", help="save the settings without testing the login"
    )
    parser.add_argument(
        "--no-instructions", action="store_true", help="do not write the agent instructions"
    )
    parser.add_argument(
        "--instructions", action="store_true", help="print a manual setup guide and exit"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="show what would change; write nothing"
    )
    return parser


def _ask(label: str, default: str) -> str:
    shown = f" [{default}]" if default else ""
    return input(f"{label}{shown}: ").strip()


def _pick_agent() -> list[str]:
    keys = list(AGENTS)
    print("Which agent?")
    for i, key in enumerate(keys, 1):
        print(f"  {i:2}. {key:15} {AGENTS[key].title}")
    answer = input("Number or name: ").strip()
    if answer.isdigit() and 1 <= int(answer) <= len(keys):
        return [keys[int(answer) - 1]]
    return [answer]


def _print_step(step: Step) -> None:
    print(f"  {step.what}: {step.action:9} {step.target}")
    for line in step.note.splitlines():
        print(f"    {line}")


def run(argv: list[str], env: Env | None = None) -> int:
    args = build_parser().parse_args(argv)
    env = env or Env.current()

    if args.instructions:
        print(manual_guide(env))
        return 0

    interactive = not args.yes and sys.stdin.isatty()
    agents = args.agents or (_pick_agent() if interactive else [])
    agents = [ALIASES.get(a, a) for a in agents]
    if not agents:
        print(f"Name an agent: {', '.join(AGENTS)} (or --instructions)", file=sys.stderr)
        return 2
    unknown = [a for a in agents if a not in AGENTS]
    if unknown:
        print(f"Unknown agent {', '.join(unknown)}; known: {', '.join(AGENTS)}", file=sys.stderr)
        return 2

    from dotenv import dotenv_values

    from gns3_mcp.cli import user_env_file

    env_file = user_env_file()
    try:
        saved = dotenv_values(env_file) if env_file.exists() else {}
        settings = resolve_settings(
            args,
            saved,
            os.environ,
            _ask if interactive else None,
            getpass.getpass if interactive else None,
        )
    except ConfigureError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    print(f"GNS3 {settings.url}, user {settings.user}")
    if not args.skip_check:
        problem = check_login(settings)
        if problem:
            print(f"  login check: FAILED - {problem}", file=sys.stderr)
            if not (interactive and _ask("Save these settings anyway? (y/N)", "n").lower() == "y"):
                print("Nothing written. Fix the settings, or pass --skip-check.", file=sys.stderr)
                return 1
        else:
            print("  login check: OK")
    if args.dry_run:
        print(f"  settings: would save {env_file}")
    else:
        save_settings(env_file, settings)
        print(f"  settings: saved {env_file}")

    failed = False
    for key in agents:
        agent = AGENTS[key]
        print(f"{agent.title} ({'project ' + str(env.cwd) if args.project else 'user-wide'})")
        for step in plan_agent(agent, env, args.project, not args.no_instructions):
            if step.apply and not args.dry_run:
                try:
                    step.apply()
                except (OSError, ConfigureError, subprocess.SubprocessError) as e:
                    step.action, step.note = "failed", str(e)
                    failed = True
            _print_step(step)
        for note in agent.notes:
            print(f"  note: {note}")
        print(f"  next: {agent.restart}")
    if args.dry_run:
        print("Dry run: nothing was written.")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> None:
    sys.exit(run(sys.argv[1:] if argv is None else argv))
