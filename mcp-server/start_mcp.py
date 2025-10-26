#!/usr/bin/env python3
"""
Wrapper script to load .env file and start MCP server
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Get the project root directory (parent of mcp-server)
project_root = Path(__file__).parent.parent

# Load .env file from project root
env_file = project_root / '.env'
if env_file.exists():
    load_dotenv(env_file)

# Add lib and server to Python path
lib_path = str(project_root / 'mcp-server' / 'lib')
server_path = str(project_root / 'mcp-server' / 'server')
sys.path.insert(0, lib_path)
sys.path.insert(0, server_path)

# Import and run the MCP server
if __name__ == '__main__':
    import argparse
    from main import mcp

    # Parse command line arguments (supports both .env defaults and CLI overrides)
    parser = argparse.ArgumentParser(description="GNS3 MCP Server")

    # GNS3 connection arguments (with .env file defaults)
    parser.add_argument("--host", default=os.getenv('GNS3_HOST', 'localhost'), help="GNS3 server host")
    parser.add_argument("--port", type=int, default=int(os.getenv('GNS3_PORT', '80')), help="GNS3 server port")
    parser.add_argument("--username", default=os.getenv('GNS3_USER', 'admin'), help="GNS3 username")
    parser.add_argument("--password", default=os.getenv('GNS3_PASSWORD', ''), help="GNS3 password")

    # MCP transport mode arguments (NEW in v0.21.0)
    parser.add_argument(
        "--transport",
        choices=["stdio", "http", "sse"],
        default="stdio",
        help="MCP transport mode: stdio (process-based, default), http (Streamable HTTP, recommended for network), sse (legacy SSE, deprecated)"
    )
    parser.add_argument(
        "--http-host",
        default="127.0.0.1",
        help="HTTP server host (only for http/sse transport, default: 127.0.0.1)"
    )
    parser.add_argument(
        "--http-port",
        type=int,
        default=8000,
        help="HTTP server port (only for http/sse transport, default: 8000)"
    )

    args = parser.parse_args()

    # Store args in server for lifespan access
    mcp._args = args
    mcp.get_args = lambda: args

    # Run server with selected transport mode
    if args.transport == "stdio":
        # Process-based communication (default for Claude Desktop/Code)
        mcp.run()
    elif args.transport == "http":
        # Streamable HTTP transport (recommended for network access)
        import uvicorn
        print(f"Starting MCP server with HTTP transport at http://{args.http_host}:{args.http_port}/mcp/")

        # Create ASGI app for Streamable HTTP transport
        app = mcp.streamable_http_app()

        # Run with uvicorn
        uvicorn.run(
            app,
            host=args.http_host,
            port=args.http_port,
            log_level="info"
        )
    elif args.transport == "sse":
        # Legacy SSE transport (deprecated, use HTTP instead)
        import uvicorn
        print(f"WARNING: SSE transport is deprecated. Consider using --transport http instead.")
        print(f"Starting MCP server with SSE transport at http://{args.http_host}:{args.http_port}/sse")

        # Create ASGI app for SSE transport
        app = mcp.sse_app()

        # Run with uvicorn
        uvicorn.run(
            app,
            host=args.http_host,
            port=args.http_port,
            log_level="info"
        )
