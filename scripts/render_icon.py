#!/usr/bin/env python3
"""Render plugin/assets/icon.svg to the PNG icons the packages use.

- plugin/assets/icon.png   1024 px  (Claude plugin, `icon` in plugin.json; directory needs 512-2048 px)
- mcp-server/icon.png       512 px  (MCPB `icon`, 512 px recommended by the spec)

The PNGs are committed (the plugin is installed straight from git), so run this after
editing the SVG. Run from the repository root; needs cairosvg (a runtime dependency).
"""

import sys
from pathlib import Path

import cairosvg

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "plugin" / "assets" / "icon.svg"
TARGETS = {
    ROOT / "plugin" / "assets" / "icon.png": 1024,
    ROOT / "mcp-server" / "icon.png": 512,
}


def main() -> int:
    svg = SOURCE.read_bytes()
    for target, size in TARGETS.items():
        cairosvg.svg2png(
            bytestring=svg, write_to=str(target), output_width=size, output_height=size
        )
        print(f"{target.relative_to(ROOT)}: {size}x{size}, {target.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
