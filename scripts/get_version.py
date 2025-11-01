#!/usr/bin/env python3
"""Get current version from package __init__.py"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from gns3_mcp import __version__
    print(__version__)
except ImportError as e:
    print(f"Error: Could not import version: {e}", file=sys.stderr)
    sys.exit(1)
