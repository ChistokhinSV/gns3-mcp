#!/usr/bin/env python3
"""Validate that CHANGELOG.md contains entry for current version

Checks that the current version has a section in CHANGELOG.md with:
- Version header (## [X.Y.Z])
- Release date
- Changes documented
"""
import re
import sys
from pathlib import Path


def get_current_version():
    """Get current version from gns3_mcp/__init__.py"""
    init_file = Path("gns3_mcp/__init__.py")
    if not init_file.exists():
        print("[ERROR] gns3_mcp/__init__.py not found", file=sys.stderr)
        sys.exit(1)

    content = init_file.read_text(encoding='utf-8')
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
    if not match:
        print("[ERROR] Could not extract version from __init__.py", file=sys.stderr)
        sys.exit(1)

    return match.group(1)


def check_changelog(version):
    """Check if version exists in CHANGELOG.md"""
    changelog = Path("CHANGELOG.md")
    if not changelog.exists():
        print("[ERROR] CHANGELOG.md not found", file=sys.stderr)
        sys.exit(1)

    content = changelog.read_text(encoding='utf-8')

    # Look for version header patterns:
    # - ## [X.Y.Z] - YYYY-MM-DD
    # - ## [X.Y.Z]
    # - ## Version X.Y.Z
    patterns = [
        rf'##\s+\[{re.escape(version)}\]',  # ## [0.42.0]
        rf'##\s+{re.escape(version)}',      # ## 0.42.0
        rf'##\s+[vV]ersion\s+{re.escape(version)}',  # ## Version 0.42.0
    ]

    for pattern in patterns:
        if re.search(pattern, content, re.MULTILINE):
            return True

    return False


def extract_changelog_entry(version):
    """Extract changelog entry for version (for display)"""
    changelog = Path("CHANGELOG.md")
    content = changelog.read_text(encoding='utf-8')

    # Find version header
    pattern = rf'##\s+.*{re.escape(version)}.*$'
    match = re.search(pattern, content, re.MULTILINE)
    if not match:
        return None

    start_pos = match.start()

    # Find next version header or end of file
    next_pattern = r'##\s+\[?\d+\.\d+\.\d+.*$'
    next_match = re.search(next_pattern, content[match.end():], re.MULTILINE)

    if next_match:
        end_pos = match.end() + next_match.start()
    else:
        end_pos = len(content)

    entry = content[start_pos:end_pos].strip()

    # Limit to first 500 chars for display
    if len(entry) > 500:
        entry = entry[:500] + "\n..."

    return entry


def main():
    """Check changelog for current version"""
    print("=" * 70)
    print("Changelog Validation")
    print("=" * 70)
    print()

    version = get_current_version()
    print(f"Current version: {version}")
    print()

    if check_changelog(version):
        print(f"[OK] CHANGELOG.md contains entry for version {version}")
        print()

        # Show the entry
        entry = extract_changelog_entry(version)
        if entry:
            print("Entry preview:")
            print("-" * 70)
            print(entry)
            print("-" * 70)

        print()
        print("=" * 70)
        return 0
    else:
        print(f"[ERROR] CHANGELOG.md missing entry for version {version}")
        print()
        print("Please add a changelog entry with format:")
        print()
        print(f"## [{version}] - YYYY-MM-DD")
        print()
        print("### Added")
        print("- New feature description")
        print()
        print("### Changed")
        print("- Change description")
        print()
        print("### Fixed")
        print("- Bug fix description")
        print()
        print("=" * 70)
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())
