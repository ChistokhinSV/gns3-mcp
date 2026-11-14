"""`gns3-mcp configure` (GM-102): agent configs, rules blocks, settings, end to end

Everything runs against a temporary home folder; nothing touches the real agent configs.
"""

import argparse
import json
from pathlib import Path

import pytest

from gns3_mcp import __version__, configure
from gns3_mcp.configure import (
    AGENTS,
    BACKUP_SUFFIX,
    MD_BEGIN,
    MD_END,
    ConfigureError,
    Env,
    Launch,
    plan_codex,
    plan_json,
    plan_rules,
    resolve_settings,
)

LAUNCH = Launch("uvx", (f"gns3-mcp@{__version__}",))


@pytest.fixture
def env(tmp_path):
    home, cwd = tmp_path / "home", tmp_path / "repo"
    home.mkdir()
    cwd.mkdir()
    return Env(home=home, cwd=cwd, platform="linux")


def _apply(step):
    assert step.apply, f"nothing to apply: {step.action} {step.note}"
    step.apply()


class TestJsonConfig:
    def test_adds_entry_and_keeps_everything_else(self, tmp_path):
        path = tmp_path / "mcp.json"
        path.write_text(
            json.dumps({"theme": "dark", "mcpServers": {"other": {"command": "x"}}}, indent=4)
        )

        step = plan_json(path, AGENTS["cursor"].mcp[-1], LAUNCH)
        _apply(step)

        data = json.loads(path.read_text())
        assert step.action == "create"
        assert data["theme"] == "dark"
        assert data["mcpServers"]["other"] == {"command": "x"}
        assert data["mcpServers"]["gns3"] == {"command": "uvx", "args": [f"gns3-mcp@{__version__}"]}
        assert '\n    "theme"' in path.read_text()  # the file's 4-space indent kept
        assert (tmp_path / ("mcp.json" + BACKUP_SUFFIX)).exists()

    def test_update_keeps_keys_the_user_added_and_is_idempotent(self, tmp_path):
        path = tmp_path / "mcp.json"
        old = {"command": "uvx", "args": ["gns3-mcp@0.1.0"], "autoApprove": ["project"]}
        path.write_text(json.dumps({"mcpServers": {"gns3": old}}))

        _apply(plan_json(path, AGENTS["kiro"].mcp[-1], LAUNCH))

        entry = json.loads(path.read_text())["mcpServers"]["gns3"]
        assert entry["args"] == [f"gns3-mcp@{__version__}"]
        assert entry["autoApprove"] == ["project"]
        assert plan_json(path, AGENTS["kiro"].mcp[-1], LAUNCH).action == "unchanged"

    def test_backup_is_taken_once(self, tmp_path):
        path = tmp_path / "mcp.json"
        path.write_text('{"mcpServers": {}}')
        _apply(plan_json(path, AGENTS["cursor"].mcp[-1], LAUNCH))
        _apply(plan_json(path, AGENTS["cursor"].mcp[-1], Launch("uvx", ("gns3-mcp@9.9.9",))))

        backup = tmp_path / ("mcp.json" + BACKUP_SUFFIX)
        assert backup.read_text() == '{"mcpServers": {}}'

    def test_file_with_comments_is_left_alone(self, tmp_path):
        path = tmp_path / "mcp.json"
        text = '{\n  // my servers\n  "servers": {}\n}\n'
        path.write_text(text)

        step = plan_json(path, AGENTS["vscode"].mcp[-1], LAUNCH)

        assert step.action == "skip"
        assert '"servers"' in step.note  # the entry to add by hand
        assert path.read_text() == text

    def test_trailing_commas_alone_are_fine(self, tmp_path):
        path = tmp_path / "opencode.jsonc"
        path.write_text('{\n  "theme": "x",\n  "mcp": {\n    "servers": {},\n  },\n}\n')

        _apply(plan_json(path, AGENTS["opencode"].mcp[0], LAUNCH))

        assert "gns3" in json.loads(path.read_text())["mcp"]["servers"]

    def test_commented_file_is_read_for_layout_and_unchanged_check(self, tmp_path):
        path = tmp_path / "opencode.jsonc"
        entry = {"type": "local", "command": ["uvx", *LAUNCH.args]}
        body = json.dumps({"mcp": {"servers": {"gns3": entry}}})
        path.write_text("/* mine */\n" + body)

        assert plan_json(path, AGENTS["opencode"].mcp[0], LAUNCH).action == "unchanged"
        path.write_text("// mine\n" + body.replace(LAUNCH.args[0], "gns3-mcp@0.1"))
        step = plan_json(path, AGENTS["opencode"].mcp[0], LAUNCH)
        assert step.action == "skip" and '"servers"' in step.note

    def test_strip_jsonc_keeps_slashes_in_strings(self):
        text, comments = configure.strip_jsonc('{"url": "http://x//y", "a": [1, 2,],} // c')
        assert json.loads(text) == {"url": "http://x//y", "a": [1, 2]}
        assert comments

    def test_entry_shapes(self):
        copilot, local_harness = AGENTS["vscode"].mcp
        assert copilot.entry(LAUNCH)["type"] == "local" and copilot.entry(LAUNCH)["tools"] == ["*"]
        assert local_harness.container == ("servers",)
        assert local_harness.entry(LAUNCH)["type"] == "stdio"

    def test_opencode_keeps_the_layout_the_file_uses(self, tmp_path):
        spec = AGENTS["opencode"].mcp[0]
        old, new = tmp_path / "old.json", tmp_path / "new.json"
        new.write_text(json.dumps({"mcp": {"servers": {"other": {"type": "local"}}}}))

        _apply(plan_json(old, spec, LAUNCH))
        _apply(plan_json(new, spec, LAUNCH))

        command = ["uvx", *LAUNCH.args]
        assert json.loads(old.read_text())["mcp"]["gns3"] == {
            "type": "local",
            "command": command,
            "enabled": True,
        }
        servers = json.loads(new.read_text())["mcp"]["servers"]
        assert servers["gns3"] == {"type": "local", "command": command}
        assert "other" in servers

    def test_warns_about_old_gns3_mcp_entry(self, tmp_path):
        path = tmp_path / "c.json"
        path.write_text(json.dumps({"mcpServers": {"gns3-mcp": {"command": "uvx"}}}))

        assert "gns3-mcp" in plan_json(path, AGENTS["claude-desktop"].mcp[-1], LAUNCH).note


class TestCodex:
    def test_appends_marked_block_and_updates_it_in_place(self, tmp_path):
        path = tmp_path / "config.toml"
        path.write_text('model = "o3"\n')

        _apply(plan_codex(path, LAUNCH))
        _apply(plan_codex(path, Launch("uvx", ("gns3-mcp@9.9.9",))))

        text = path.read_text()
        assert text.startswith('model = "o3"\n')
        assert text.count("[mcp_servers.gns3]") == 1
        assert 'args = ["gns3-mcp@9.9.9"]' in text
        assert plan_codex(path, Launch("uvx", ("gns3-mcp@9.9.9",))).action == "unchanged"

    def test_hand_written_table_is_left_alone(self, tmp_path):
        path = tmp_path / "config.toml"
        path.write_text('[mcp_servers.gns3]\ncommand = "mine"\n')

        assert plan_codex(path, LAUNCH).action == "skip"

    def test_windows_path_is_escaped(self):
        block = configure.codex_block(Launch(r"C:\Users\a b\uvx.exe", ("gns3-mcp@1",)))
        assert r'command = "C:\\Users\\a b\\uvx.exe"' in block


class TestRules:
    def test_block_added_to_shared_file_once(self, tmp_path):
        path = tmp_path / "GEMINI.md"
        path.write_text("# My rules\n\nBe brief.\n")

        _apply(plan_rules(path, AGENTS["gemini"]))
        text = path.read_text()

        assert text.startswith("# My rules\n\nBe brief.\n")
        assert text.count(MD_BEGIN) == 1 and MD_END in text
        assert plan_rules(path, AGENTS["gemini"]).action == "unchanged"

    def test_block_update_replaces_only_the_block(self, tmp_path):
        path = tmp_path / "AGENTS.md"
        path.write_text(f"before\n{MD_BEGIN}\nold text\n{MD_END}\nafter\n")

        _apply(plan_rules(path, AGENTS["codex"]))
        text = path.read_text()

        assert text.startswith("before\n") and text.endswith(f"{MD_END}\nafter\n")
        assert "old text" not in text and "## GNS3 lab" in text

    def test_own_rules_file_gets_front_matter(self, tmp_path):
        path = tmp_path / "steering" / "gns3.md"

        _apply(plan_rules(path, AGENTS["kiro"]))

        text = path.read_text()
        assert text.startswith("---\ninclusion: always\n---\n\n<!-- written by")
        assert "## GNS3 lab" in text
        assert plan_rules(path, AGENTS["kiro"]).action == "unchanged"

    def test_claude_rules_are_a_file_of_their_own(self, env):
        assert AGENTS["claude"].user_rules(env) == env.home / ".claude" / "rules" / "gns3.md"
        assert AGENTS["claude"].rules_header == ""


def _args(**kw):
    base = {"host": None, "port": None, "user": None, "https": False, "no_verify_ssl": False}
    return argparse.Namespace(**{**base, **kw})


class TestSettings:
    def test_flags_beat_environment_beat_saved_file(self):
        saved = {"GNS3_HOST": "saved", "GNS3_PORT": "8080", "GNS3_PASSWORD": "old"}
        environ = {"GNS3_HOST": "from-env", "GNS3_USER": "ops"}

        s = resolve_settings(_args(host="flag"), saved, environ, None, None)

        assert (s.host, s.port, s.user, s.password) == ("flag", 8080, "ops", "old")

    def test_password_comes_from_environment_before_prompt(self):
        asked = []
        s = resolve_settings(
            _args(host="h"),
            {},
            {"GNS3_PASSWORD": "env-pw"},
            None,
            lambda prompt: asked.append(prompt) or "typed",
        )
        assert s.password == "env-pw" and not asked

    def test_empty_prompt_keeps_saved_password(self):
        s = resolve_settings(
            _args(host="h"), {"GNS3_PASSWORD": "kept"}, {}, lambda label, d: "", lambda p: ""
        )
        assert s.password == "kept"

    def test_missing_host_or_password_is_an_error(self):
        with pytest.raises(ConfigureError, match="host"):
            resolve_settings(_args(), {}, {"GNS3_PASSWORD": "x"}, None, None)
        with pytest.raises(ConfigureError, match="password"):
            resolve_settings(_args(host="h"), {}, {}, None, None)

    def test_login_check_reports_rejected_password(self, monkeypatch):
        class Response:
            status_code, text = 401, '{"message": "Authentication was unsuccessful"}'

        monkeypatch.setattr("httpx.post", lambda *a, **kw: Response())
        s = configure.Settings("h", 80, "admin", "secret")

        problem = configure.check_login(s)

        assert "rejected" in problem and "secret" not in problem


class TestRun:
    @pytest.fixture
    def setup(self, env, monkeypatch, tmp_path):
        env_file = tmp_path / "gns3.env"
        monkeypatch.setenv("GNS3_MCP_ENV_FILE", str(env_file))
        monkeypatch.setenv("GNS3_PASSWORD", "pw")
        monkeypatch.setattr(configure.shutil, "which", lambda name: None)
        return env, env_file

    def test_non_interactive_writes_settings_config_and_rules(self, setup):
        env, env_file = setup
        argv = ["cursor", "--project", "--host", "10.0.0.5", "--yes", "--skip-check"]

        assert configure.run(argv, env) == 0

        assert "GNS3_HOST='10.0.0.5'" in env_file.read_text()
        entry = json.loads((env.cwd / ".cursor" / "mcp.json").read_text())["mcpServers"]["gns3"]
        assert entry["command"] == "uvx"  # project files stay portable
        assert (env.cwd / ".cursor" / "rules" / "gns3.mdc").exists()

    def test_dry_run_writes_nothing(self, setup):
        env, env_file = setup

        assert (
            configure.run(["gemini", "--host", "h", "--yes", "--skip-check", "--dry-run"], env) == 0
        )

        assert not env_file.exists()
        assert not (env.home / ".gemini").exists()

    def test_failed_login_writes_nothing(self, setup, monkeypatch):
        env, env_file = setup
        monkeypatch.setattr(configure, "check_login", lambda s: "cannot reach GNS3")

        assert configure.run(["gemini", "--host", "h", "--yes"], env) == 1
        assert not env_file.exists()

    def test_claude_without_cli_prints_the_command(self, setup, capsys):
        env, _ = setup

        configure.run(["claude", "--host", "h", "--yes", "--skip-check", "--no-instructions"], env)

        out = capsys.readouterr().out
        assert "claude mcp add --scope user gns3 -- uvx gns3-mcp@" in out
        assert "claude is not on PATH" in out

    def test_unknown_agent(self, setup):
        env, _ = setup
        assert configure.run(["notepad", "--yes"], env) == 2

    def test_manual_guide_covers_every_agent(self, env):
        guide = configure.manual_guide(env)
        for agent in AGENTS.values():
            assert f"(`{agent.key}`)" in guide
        assert "[mcp_servers.gns3]" in guide


def test_cli_dispatches_configure(monkeypatch):
    called = []
    monkeypatch.setattr("sys.argv", ["gns3-mcp", "configure", "--instructions"])
    monkeypatch.setattr(configure, "main", lambda argv: called.append(argv))

    from gns3_mcp import cli

    cli.main()

    assert called == [["--instructions"]]


class TestPaths:
    def test_claude_desktop_prefers_msix_copy_when_present(self, tmp_path):
        local = tmp_path / "local"
        env = Env(
            tmp_path,
            tmp_path,
            "win32",
            {"APPDATA": str(tmp_path / "roaming"), "LOCALAPPDATA": str(local)},
        )
        spec = AGENTS["claude-desktop"].mcp[0]
        assert spec.user(env) == tmp_path / "roaming" / "Claude" / "claude_desktop_config.json"

        msix = local / "Packages" / "Claude_abc" / "LocalCache" / "Roaming" / "Claude"
        msix.mkdir(parents=True)
        (msix / "claude_desktop_config.json").write_text("{}")
        assert spec.user(env) == msix / "claude_desktop_config.json"

    def test_cline_honours_its_overrides(self, tmp_path):
        spec = AGENTS["cline"].mcp[0]
        plain = Env(tmp_path, tmp_path, "linux")
        assert (
            spec.user(plain)
            == tmp_path / ".cline" / "data" / "settings" / "cline_mcp_settings.json"
        )
        custom = Env(
            tmp_path, tmp_path, "linux", {"CLINE_MCP_SETTINGS_PATH": str(tmp_path / "x.json")}
        )
        assert spec.user(custom) == tmp_path / "x.json"

    def test_aliases(self, monkeypatch, env, tmp_path):
        monkeypatch.setenv("GNS3_MCP_ENV_FILE", str(tmp_path / "e.env"))
        monkeypatch.setenv("GNS3_PASSWORD", "pw")
        argv = ["devin", "copilot", "--host", "h", "--yes", "--skip-check", "--dry-run"]
        assert configure.run(argv, env) == 0


def test_user_scope_uses_full_uvx_path(monkeypatch):
    monkeypatch.setattr(configure.shutil, "which", lambda name: str(Path("/opt/uv/uvx")))
    assert configure.launch_for(project=False).command == str(Path("/opt/uv/uvx"))
    assert configure.launch_for(project=True).command == "uvx"
