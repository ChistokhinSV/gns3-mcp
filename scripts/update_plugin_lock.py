#!/usr/bin/env python3
"""Point the Claude plugin at a published gns3-mcp release and re-lock it (GM-107)

Anthropic's plugin directory does not accept a PyPI version as a pin. The plugin is a uv
project (plugin/pyproject.toml) whose uv.lock pins gns3-mcp and every dependency by hash,
and plugin/.mcp.json starts the server with `uv run --locked`. The lock can only be made once
PyPI serves the release, so the release workflow runs this after publishing (and so can you).

Usage:
    python scripts/update_plugin_lock.py 0.59.2            # set version, lock
    python scripts/update_plugin_lock.py 0.59.2 --wait 600 # retry while PyPI catches up
"""

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugin"
# The directory holds any non-image file above this size for a reviewer
DIRECTORY_FILE_LIMIT = 256 * 1024
RETRY_SECONDS = 15


def set_version(version: str) -> None:
    project = PLUGIN / "pyproject.toml"
    text = project.read_text(encoding="utf-8")
    text = re.sub(r'(?m)^version = "[^"]+"', f'version = "{version}"', text, count=1)
    text = re.sub(r'"gns3-mcp==[^"]+"', f'"gns3-mcp=={version}"', text)
    project.write_text(text, encoding="utf-8")

    manifest = PLUGIN / ".claude-plugin" / "plugin.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["version"] = version
    manifest.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def lock(wait: float) -> None:
    """uv lock in plugin/, retrying while PyPI does not serve the new release yet"""
    # --refresh-package: a cached index page from before the upload would hide the release
    cmd = ["uv", "lock", "--directory", str(PLUGIN), "--refresh-package", "gns3-mcp"]
    deadline = time.monotonic() + wait
    while True:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            return
        if time.monotonic() >= deadline:
            sys.stderr.write(result.stdout + result.stderr)
            raise SystemExit("uv lock failed")
        print(f"uv lock failed (PyPI may not serve the release yet); retrying in {RETRY_SECONDS}s")
        time.sleep(RETRY_SECONDS)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("version", help="published gns3-mcp version, e.g. 0.59.2")
    parser.add_argument(
        "--wait", type=float, default=0, help="seconds to keep retrying the lock (default 0)"
    )
    args = parser.parse_args()
    if not re.fullmatch(r"\d+\.\d+\.\d+", args.version):
        parser.error(f"not a version: {args.version}")

    set_version(args.version)
    lock(args.wait)

    lock_file = PLUGIN / "uv.lock"
    lock_text = lock_file.read_text("utf-8").replace("\r\n", "\n")  # CRLF on Windows checkouts
    if f'name = "gns3-mcp"\nversion = "{args.version}"' not in lock_text:
        raise SystemExit(f"uv.lock does not lock gns3-mcp {args.version}")
    size = lock_file.stat().st_size
    print(f"[OK] plugin locked to gns3-mcp {args.version} (uv.lock {size // 1024} KiB)")
    if size > DIRECTORY_FILE_LIMIT:
        print(
            f"[WARN] uv.lock is over {DIRECTORY_FILE_LIMIT // 1024} KiB: the plugin directory "
            "holds it for a reviewer. Check requires-python in plugin/pyproject.toml."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
