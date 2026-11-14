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


def test_runtime_data_files_are_package_data():
    """GM-94: setuptools ships only .py files unless package-data lists the rest"""
    with open(ROOT / "pyproject.toml", "rb") as f:
        package_data = tomllib.load(f)["tool"]["setuptools"].get("package-data", {})

    declared = {
        (ROOT / package.replace(".", "/") / pattern).resolve()
        for package, patterns in package_data.items()
        for pattern in patterns
    }
    data_files = {
        p.resolve()
        for p in (ROOT / "gns3_mcp").rglob("*")
        if p.is_file()
        and p.suffix not in {".py", ".pyc"}
        and p.name != "py.typed"  # shipped by setuptools automatically
        and "__pycache__" not in p.parts
    }
    assert data_files, "expected at least instructions.md"
    assert data_files <= declared, sorted(str(p) for p in data_files - declared)


def test_icons_exist_and_are_square():
    """plugin.json and the MCPB manifest point at PNGs rendered from plugin/assets/icon.svg"""
    from PIL import Image

    plugin = json.loads((ROOT / "plugin" / ".claude-plugin" / "plugin.json").read_text())
    manifest = json.loads((ROOT / "mcp-server" / "manifest.json").read_text(encoding="utf-8"))
    for path, min_size in (
        (ROOT / "plugin" / plugin["icon"], 512),  # Anthropic directory: 512-2048 px
        (ROOT / "mcp-server" / manifest["icon"], 256),  # MCPB: 256 px minimum
    ):
        with Image.open(path) as img:
            assert img.format == "PNG" and img.width == img.height >= min_size, path


def test_plugin_runs_matching_server_version():
    plugin = json.loads((ROOT / "plugin" / ".claude-plugin" / "plugin.json").read_text())
    mcp = (ROOT / "plugin" / ".mcp.json").read_text()

    # Cowork ignores a server whose referenced options have no default
    for name in re.findall(r"\$\{user_config\.(\w+)\}", mcp):
        assert "default" in plugin["userConfig"][name], name


def test_plugin_server_is_locked_for_the_directory():
    """GM-107: Anthropic's plugin directory accepts no PyPI version as a pin. The plugin is a
    uv project whose uv.lock pins gns3-mcp and every dependency by hash."""
    plugin_dir = ROOT / "plugin"
    plugin = json.loads((plugin_dir / ".claude-plugin" / "plugin.json").read_text())
    server = json.loads((plugin_dir / ".mcp.json").read_text())["mcpServers"]["gns3"]
    project = tomllib.loads((plugin_dir / "pyproject.toml").read_text(encoding="utf-8"))
    # Windows checkouts can turn the lock's line endings into CRLF
    lock = (plugin_dir / "uv.lock").read_text(encoding="utf-8").replace("\r\n", "\n")

    assert server["command"] == "uv"
    assert server["args"] == ["run", "--locked", "--project", "${CLAUDE_PLUGIN_ROOT}", "gns3-mcp"]
    version = plugin["version"]
    assert project["project"]["version"] == version
    assert project["project"]["dependencies"] == [f"gns3-mcp=={version}"]
    assert f'name = "gns3-mcp"\nversion = "{version}"' in lock
    # Over 256 KiB the directory holds the file for a reviewer; Python 3.10/3.11 double it
    assert (plugin_dir / "uv.lock").stat().st_size < 256 * 1024
    # CI locks the plugin after the PyPI upload, so it may trail the package, never lead it
    package = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    as_key = lambda v: tuple(int(p) for p in v.split("."))  # noqa: E731
    assert as_key(version) <= as_key(package["project"]["version"])
