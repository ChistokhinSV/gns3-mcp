#!/usr/bin/env python3
"""Validate version consistency across project files

Checks that version matches in:
- gns3_mcp/__init__.py
- pyproject.toml
- mcp-server/manifest.json
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
    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
