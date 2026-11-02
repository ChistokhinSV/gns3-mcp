#!/usr/bin/env python3
"""Smoke test a built .mcpb the way Claude Desktop runs it (uv runtime).

Unpacks the bundle into a temp dir, starts `uv run --directory <dir> <entry_point>`
with dummy GNS3 settings, then checks the MCP handshake and the tool list. No GNS3
server is needed: authentication runs in the background and may fail.

Usage: python scripts/smoke_test_mcpb.py [mcp-server/mcp-server.mcpb]
Requires: uv on PATH, the `mcp` package.
"""

import asyncio
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

EXPECTED_TOOLS = 15


async def check(bundle_dir: Path, entry_point: str) -> int:
    env = dict(os.environ)
    # Unreachable port: the server must still start and list its tools
    env.update(GNS3_HOST="127.0.0.1", GNS3_PORT="9", GNS3_USER="ci", GNS3_PASSWORD="ci-dummy")
    params = StdioServerParameters(
        command="uv",
        args=["run", "--directory", str(bundle_dir), entry_point],
        env=env,
        cwd=str(bundle_dir),
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        init = await asyncio.wait_for(session.initialize(), timeout=300)
        tools = await session.list_tools()
        names = sorted(t.name for t in tools.tools)
        # `serverInfo` became `server_info` in newer mcp SDKs
        info = getattr(init, "server_info", None) or getattr(init, "serverInfo", None)
        print(f"initialize OK ({info.name}), {len(names)} tools: {', '.join(names)}")
        if len(names) != EXPECTED_TOOLS:
            print(f"ERROR: expected {EXPECTED_TOOLS} tools")
            return 1
    return 0


def main() -> int:
    bundle = Path(sys.argv[1] if len(sys.argv) > 1 else "mcp-server/mcp-server.mcpb")
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(bundle) as zf:
            zf.extractall(tmp)
        manifest = json.loads((Path(tmp) / "manifest.json").read_text(encoding="utf-8"))
        if manifest["server"]["type"] != "uv":
            print(f"ERROR: expected server.type 'uv', got {manifest['server']['type']!r}")
            return 1
        return asyncio.run(check(Path(tmp), manifest["server"]["entry_point"]))


if __name__ == "__main__":
    sys.exit(main())
