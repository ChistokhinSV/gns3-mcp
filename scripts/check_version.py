#!/usr/bin/env python3
"""Validate version consistency across project files

Checks that version matches in:
- gns3_mcp/__init__.py
- pyproject.toml
- mcp-server/manifest.json

and that the Claude plugin is consistent in itself (plugin.json = plugin/pyproject.toml =
gns3-mcp locked in plugin/uv.lock) and not ahead of the package. The plugin may be one
release behind: CI locks it after the PyPI upload (scripts/update_plugin_lock.py, GM-107).
"""
import json
import re
import sys
from pathlib import Path


def get_init_version():
    """Get version from gns3_mcp/__init__.py"""
    init_file = Path("gns3_mcp/__init__.py")
    if not init_file.exists():
        return None

    content = init_file.read_text(encoding='utf-8')
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
    return match.group(1) if match else None


def get_pyproject_version():
    """Get version from pyproject.toml"""
    pyproject = Path("pyproject.toml")
    if not pyproject.exists():
        return None

    content = pyproject.read_text(encoding='utf-8')
    match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
    return match.group(1) if match else None


def get_manifest_version():
    """Get version from mcp-server/manifest.json"""
    manifest = Path("mcp-server/manifest.json")
    if not manifest.exists():
        return None

    data = json.loads(manifest.read_text(encoding='utf-8'))
    return data.get("version")


def get_plugin_version():
    """Get version from plugin/.claude-plugin/plugin.json"""
    plugin = Path("plugin/.claude-plugin/plugin.json")
    if not plugin.exists():
        return None

    data = json.loads(plugin.read_text(encoding='utf-8'))
    return data.get("version")


def get_plugin_server_pin():
    """The gns3-mcp version the plugin's uv project depends on (plugin/pyproject.toml)"""
    project = Path("plugin/pyproject.toml")
    if not project.exists():
        return None

    match = re.search(r'"gns3-mcp==([^"]+)"', project.read_text(encoding='utf-8'))
    return match.group(1) if match else None


def plugin_problems():
    """What is inconsistent inside the plugin (GM-107), as a list of messages.

    The plugin runs `uv run --locked` on its own uv project: plugin.json, the project's
    version, its gns3-mcp pin and the gns3-mcp locked in uv.lock must all agree.
    """
    problems = []
    version = get_plugin_version()
    project = Path("plugin/pyproject.toml")
    lock = Path("plugin/uv.lock")
    if not project.exists() or not lock.exists():
        return ["plugin/pyproject.toml or plugin/uv.lock missing"]
    text = project.read_text(encoding="utf-8")
    project_version = re.search(r'(?m)^version = "([^"]+)"', text)
    if not project_version or project_version.group(1) != version:
        problems.append("plugin/pyproject.toml version differs from plugin.json")
    if get_plugin_server_pin() != version:
        problems.append("plugin/pyproject.toml gns3-mcp pin differs from plugin.json")
    if f'name = "gns3-mcp"\nversion = "{version}"' not in lock.read_text(encoding="utf-8"):
        problems.append(f"plugin/uv.lock does not lock gns3-mcp {version}")
    mcp = Path("plugin/.mcp.json").read_text(encoding="utf-8")
    if '"--locked"' not in mcp or "${CLAUDE_PLUGIN_ROOT}" not in mcp:
        problems.append("plugin/.mcp.json does not start the server with uv run --locked")
    return problems


def _key(version):
    return tuple(int(part) for part in version.split("."))


def main():
    """Check version consistency across all files"""
    print("=" * 70)
    print("Version Consistency Check")
    print("=" * 70)
    print()

    versions = {
        "gns3_mcp/__init__.py": get_init_version(),
        "pyproject.toml": get_pyproject_version(),
        "mcp-server/manifest.json": get_manifest_version(),
    }

    # Display versions
    max_file_len = max(len(f) for f in versions.keys())
    for file, version in versions.items():
        if version:
            print(f"  {file:<{max_file_len}}  ->  {version}")
        else:
            print(f"  {file:<{max_file_len}}  ->  [NOT FOUND]")

    print()

    # Check for missing versions
    missing = [f for f, v in versions.items() if v is None]
    if missing:
        print("[ERROR] Missing version in files:")
        for f in missing:
            print(f"  - {f}")
        print()
        sys.exit(1)

    # Check for mismatches
    unique_versions = set(v for v in versions.values() if v)

    if len(unique_versions) != 1:
        print("[ERROR] Version mismatch detected!")
        print()
        print("All files must have the same version.")
        print("Please update version in all files:")
        for file, version in versions.items():
            print(f"  {file}: {version}")
        print()
        sys.exit(1)

    current_version = unique_versions.pop()
    print(f"[OK] All versions match: {current_version}")

    # The plugin is locked to a *published* release by CI after the PyPI upload, so between
    # `just bump` and that commit it is one release behind; ahead of the package is wrong.
    plugin_version = get_plugin_version()
    problems = plugin_problems()
    if plugin_version and _key(plugin_version) > _key(current_version):
        problems.append(f"plugin {plugin_version} is ahead of the package {current_version}")
    if problems:
        print("[ERROR] Plugin:")
        for problem in problems:
            print(f"  - {problem}")
        sys.exit(1)
    note = "" if plugin_version == current_version else " (CI locks the new release after publish)"
    print(f"[OK] Plugin locked to gns3-mcp {plugin_version}{note}")
    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
