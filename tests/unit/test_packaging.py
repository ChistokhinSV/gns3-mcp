"""Tests for plugin/MCPB packaging support (GM-91, GM-92)

- cli.load_config_env: settings fall back process env > ./.env > user-level .env, and empty
  values (what the Claude plugin passes when Cowork never prompted) count as unset
- scripts/prepare_mcpb.bundle_pyproject: bundle deps/version follow the root pyproject
"""

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest
import tomllib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gns3_mcp.cli import load_config_env  # noqa: E402

KEYS = ("GNS3_HOST", "GNS3_PORT", "GNS3_USER", "GNS3_PASSWORD")


@pytest.fixture
def clean_env(monkeypatch, tmp_path):
    for key in KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)
    user_env = tmp_path / "user" / ".env"
    user_env.parent.mkdir()
    monkeypatch.setenv("GNS3_MCP_ENV_FILE", str(user_env))
    return tmp_path, user_env


def test_empty_values_fall_back_to_user_env(clean_env, monkeypatch):
    _, user_env = clean_env
    user_env.write_text("GNS3_HOST=10.0.0.5\nGNS3_PASSWORD=from-file\n")
    for key in KEYS:
        monkeypatch.setenv(key, "")

    load_config_env()

    import os

    assert os.environ["GNS3_HOST"] == "10.0.0.5"
    assert os.environ["GNS3_PASSWORD"] == "from-file"
    # Keys nobody set stay unset, so the CLI defaults (port 80, admin) apply
    assert "GNS3_PORT" not in os.environ


def test_precedence_env_then_cwd_then_user(clean_env, monkeypatch):
    cwd, user_env = clean_env
    user_env.write_text("GNS3_HOST=user\nGNS3_USER=user\nGNS3_PASSWORD=user\n")
    (cwd / ".env").write_text("GNS3_HOST=cwd\nGNS3_USER=cwd\n")
    monkeypatch.setenv("GNS3_HOST", "process")

    load_config_env()

    import os

    assert os.environ["GNS3_HOST"] == "process"
    assert os.environ["GNS3_USER"] == "cwd"
    assert os.environ["GNS3_PASSWORD"] == "user"


def test_missing_explicit_env_file_exits(clean_env):
    cwd, _ = clean_env
    with pytest.raises(SystemExit):
        load_config_env(cwd / "nope.env")


def _load_prepare_mcpb():
    spec = importlib.util.spec_from_file_location(
        "prepare_mcpb", ROOT / "scripts" / "prepare_mcpb.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bundle_pyproject_follows_root():
    with open(ROOT / "pyproject.toml", "rb") as f:
        root = tomllib.load(f)

    rendered = tomllib.loads(_load_prepare_mcpb().bundle_pyproject(root))

    assert rendered["project"]["version"] == root["project"]["version"]
    assert rendered["project"]["dependencies"] == root["project"]["dependencies"]
    assert rendered["tool"]["uv"]["package"] is False


def test_manifest_uses_uv_runtime_and_env_credentials():
    manifest = json.loads((ROOT / "mcp-server" / "manifest.json").read_text(encoding="utf-8"))
    server = manifest["server"]

    assert server["type"] == "uv"
    assert (ROOT / "mcp-server" / server["entry_point"]).exists()
    # No secret on the command line (process listings)
    assert not any("password" in arg.lower() for arg in server["mcp_config"]["args"])
    assert server["mcp_config"]["env"]["GNS3_PASSWORD"] == "${user_config.password}"
    assert "linux" not in manifest["compatibility"]["platforms"]


def test_plugin_runs_matching_server_version():
    plugin = json.loads((ROOT / "plugin" / ".claude-plugin" / "plugin.json").read_text())
    mcp = (ROOT / "plugin" / ".mcp.json").read_text()

    assert re.search(r'"gns3-mcp@([^"]+)"', mcp).group(1) == plugin["version"]
    # Cowork ignores a server whose referenced options have no default
    for name in re.findall(r"\$\{user_config\.(\w+)\}", mcp):
        assert "default" in plugin["userConfig"][name], name
