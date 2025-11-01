#!/usr/bin/env python3
"""Automated version bumping across all version files

Increments semantic version (MAJOR.MINOR.PATCH) and updates:
- gns3_mcp/__init__.py (source of truth)
- pyproject.toml
- mcp-server/manifest.json

Usage:
    python scripts/bump_version.py patch  # 0.43.0 -> 0.43.1
    python scripts/bump_version.py minor  # 0.43.0 -> 0.44.0
    python scripts/bump_version.py major  # 0.43.0 -> 1.0.0
"""

import argparse
import json
import re
import sys
from pathlib import Path


def parse_version(version_str: str) -> tuple[int, int, int]:
    """Parse semantic version string into (major, minor, patch)"""
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)$", version_str)
    if not match:
        raise ValueError(f"Invalid version format: {version_str}")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def bump_version(version: tuple[int, int, int], level: str) -> tuple[int, int, int]:
    """Bump version according to level (major/minor/patch)"""
    major, minor, patch = version

    if level == "major":
        return (major + 1, 0, 0)
    elif level == "minor":
        return (major, minor + 1, 0)
    elif level == "patch":
        return (major, minor, patch + 1)
    else:
        raise ValueError(f"Invalid bump level: {level} (must be major/minor/patch)")


def format_version(version: tuple[int, int, int]) -> str:
    """Format version tuple as string"""
    return f"{version[0]}.{version[1]}.{version[2]}"


def get_current_version() -> str:
    """Read current version from gns3_mcp/__init__.py (source of truth)"""
    init_file = Path("gns3_mcp/__init__.py")
    content = init_file.read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
    if not match:
        raise ValueError("Could not find __version__ in gns3_mcp/__init__.py")
    return match.group(1)


def update_init_py(new_version: str) -> None:
    """Update version in gns3_mcp/__init__.py"""
    init_file = Path("gns3_mcp/__init__.py")
    content = init_file.read_text(encoding="utf-8")

    # Replace version string
    new_content = re.sub(
        r'(__version__\s*=\s*["\'])([^"\']+)(["\'])',
        rf'\g<1>{new_version}\g<3>',
        content
    )

    init_file.write_text(new_content, encoding="utf-8")
    print(f"[OK] Updated gns3_mcp/__init__.py")


def update_pyproject_toml(new_version: str) -> None:
    """Update version in pyproject.toml (Managed by just bump)"""
    pyproject_file = Path("pyproject.toml")
    content = pyproject_file.read_text(encoding="utf-8")

    # Replace version line in [project] section only (not target-version or python_version)
    # Match: version = "X.Y.Z" (with optional whitespace)
    # Don't match: target-version, python_version, etc.
    new_content = re.sub(
        r'(^version\s*=\s*["\'])([^"\']+)(["\'])',
        rf'\g<1>{new_version}\g<3>',
        content,
        flags=re.MULTILINE
    )

    pyproject_file.write_text(new_content, encoding="utf-8")
    print(f"[OK] Updated pyproject.toml")


def update_manifest_json(new_version: str) -> None:
    """Update version in mcp-server/manifest.json (Managed by just bump)"""
    manifest_file = Path("mcp-server/manifest.json")

    with open(manifest_file, encoding="utf-8") as f:
        manifest = json.load(f)

    old_version = manifest.get("version", "unknown")
    manifest["version"] = new_version

    # Update long_description to mention new version (optional)
    if "long_description" in manifest:
        manifest["long_description"] = re.sub(
            r'v\d+\.\d+\.\d+',
            f'v{new_version}',
            manifest["long_description"],
            count=1
        )

    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")  # Add trailing newline

    print(f"[OK] Updated mcp-server/manifest.json")


def verify_consistency() -> bool:
    """Verify all version files are consistent"""
    from check_version import get_init_version, get_pyproject_version, get_manifest_version

    init_ver = get_init_version()
    pyproject_ver = get_pyproject_version()
    manifest_ver = get_manifest_version()

    if init_ver == pyproject_ver == manifest_ver:
        print(f"\n[OK] All versions consistent: {init_ver}")
        return True
    else:
        print(f"\n[ERROR] Version mismatch!")
        print(f"  gns3_mcp/__init__.py: {init_ver}")
        print(f"  pyproject.toml: {pyproject_ver}")
        print(f"  mcp-server/manifest.json: {manifest_ver}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Bump version across all version files",
        epilog="Example: python scripts/bump_version.py minor"
    )
    parser.add_argument(
        "level",
        choices=["major", "minor", "patch"],
        help="Version component to bump"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without modifying files"
    )

    args = parser.parse_args()

    print("=" * 70)
    print("Version Bump Utility")
    print("=" * 70)

    # Get current version
    current_version_str = get_current_version()
    current_version = parse_version(current_version_str)
    print(f"\nCurrent version: {current_version_str}")

    # Calculate new version
    new_version = bump_version(current_version, args.level)
    new_version_str = format_version(new_version)
    print(f"New version:     {new_version_str}")
    print(f"Bump level:      {args.level}")

    if args.dry_run:
        print("\n[DRY RUN] Would update:")
        print("  - gns3_mcp/__init__.py")
        print("  - pyproject.toml")
        print("  - mcp-server/manifest.json")
        print("\nRun without --dry-run to apply changes")
        return 0

    # Update all files
    print(f"\nUpdating version files...")
    try:
        update_init_py(new_version_str)
        update_pyproject_toml(new_version_str)
        update_manifest_json(new_version_str)
    except Exception as e:
        print(f"\n[ERROR] Failed to update files: {e}")
        return 1

    # Verify consistency
    if not verify_consistency():
        return 1

    print("\n" + "=" * 70)
    print(f"[SUCCESS] Bumped version: {current_version_str} -> {new_version_str}")
    print("=" * 70)
    print("\nNext steps:")
    print("  1. Update CHANGELOG.md with changes for this version")
    print("  2. Run 'just check' to verify everything works")
    print("  3. Commit: git add -A && git commit -m 'chore: bump version to {}'".format(new_version_str))

    return 0


if __name__ == "__main__":
    sys.exit(main())
