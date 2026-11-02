"""MCPB entry point (uv runtime).

Claude Desktop runs `uv run --directory <bundle> gns3_mcp_server.py`; uv installs
the dependencies from the bundle's pyproject.toml. Connection settings arrive as
GNS3_HOST / GNS3_PORT / GNS3_USER / GNS3_PASSWORD from the manifest's env, so the
password never appears on the command line.
"""

from gns3_mcp.cli import main

if __name__ == "__main__":
    main()
