#!/usr/bin/env python3
"""Copy the shared files from the full plugin into the skill-only plugin (GM-107)

Anthropic's plugin directory refuses plugins with a local MCP server or files other than
Markdown, text, JSON, YAML and images from organisations that are not Verified. The
directory therefore lists skill-plugin/ (gns3-lab-guide): the same gns3-lab-automation
skill and icon as plugin/, no server. Its plugin.json and README are its own.

Usage: python scripts/sync_skill_plugin.py          # copy
       python scripts/sync_skill_plugin.py --check  # exit 1 if anything differs
"""

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "plugin"
TARGET = ROOT / "skill-plugin"
# Paths relative to the plugin root; the SVG stays out (not an allowed file type)
SHARED = ("skills", "assets/icon.png")


def shared_files(base: Path) -> dict[str, Path]:
    files: dict[str, Path] = {}
    for entry in SHARED:
        path = base / entry
        candidates = sorted(p for p in path.rglob("*") if p.is_file()) if path.is_dir() else [path]
        for file in candidates:
            if file.exists():
                files[file.relative_to(base).as_posix()] = file
    return files


def differences() -> list[str]:
    source, target = shared_files(SOURCE), shared_files(TARGET)
    problems = [f"missing in skill-plugin: {name}" for name in source if name not in target]
    problems += [f"not in plugin/: {name}" for name in target if name not in source]
    problems += [
        f"differs: {name}"
        for name in source
        if name in target and source[name].read_bytes() != target[name].read_bytes()
    ]
    return problems


def sync() -> None:
    for name in shared_files(TARGET):
        if name not in shared_files(SOURCE):
            (TARGET / name).unlink()
    for name, file in shared_files(SOURCE).items():
        destination = TARGET / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(file, destination)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="report differences, copy nothing")
    args = parser.parse_args()
    if args.check:
        problems = differences()
        for problem in problems:
            print(problem)
        return 1 if problems else 0
    sync()
    print(f"[OK] skill-plugin/ has the same {', '.join(SHARED)} as plugin/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
