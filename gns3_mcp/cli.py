#!/usr/bin/env python3
"""Console script entry point for gns3-mcp package

This module provides the command-line interface for running the GNS3 MCP server.
It loads environment variables from .env files and starts the server with the
specified transport mode (stdio, http, or sse).
"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def main():
    """Main entry point for gns3-mcp CLI

    Loads configuration from .env file and command-line arguments,
    then starts the MCP server with the specified transport mode.
    """
    # Parse arguments first to get optional --env-file
    parser = argparse.ArgumentParser(
        description="GNS3 MCP Server - Network lab automation with AI agent integration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # STDIO mode (default, for Claude Desktop/Code)
  gns3-mcp

  # HTTP mode (for network access)
  gns3-mcp --transport http --http-port 8100

  # Custom .env file
  gns3-mcp --env-file /path/to/.env

  # Override .env settings
  gns3-mcp --host 10.0.0.1 --port 443 --username user --password pass

Environment variables (.env file):
  GNS3_HOST       GNS3 server hostname/IP (default: localhost)
  GNS3_PORT       GNS3 server API port (default: 80)
  GNS3_USER       GNS3 username (default: admin)
  GNS3_PASSWORD   GNS3 password (required)
  MCP_API_KEY     API key for HTTP mode authentication (auto-generated if missing)
        """,
    )

    # GNS3 connection arguments
    parser.add_argument(
        "--host", help="GNS3 server hostname or IP address (default: from .env or 'localhost')"
    )
    parser.add_argument("--port", type=int, help="GNS3 server API port (default: from .env or 80)")
    parser.add_argument("--username", help="GNS3 username (default: from .env or 'admin')")
    parser.add_argument("--password", help="GNS3 password (default: from .env)")
    parser.add_argument(
        "--use-https",
        action="store_true",
        help="Use HTTPS for GNS3 connection (or set GNS3_USE_HTTPS=true in .env)",
    )
    parser.add_argument(
        "--verify-ssl",
        default=True,
        type=lambda x: str(x).lower() != "false",
        help="Verify GNS3 SSL certificate (default: true, set to 'false' for self-signed certs)",
    )

    # MCP transport mode arguments
    parser.add_argument(
        "--transport",
        choices=["stdio", "http", "sse"],
        default="stdio",
        help="MCP transport mode (default: stdio). stdio=process-based, http=Streamable HTTP, sse=legacy SSE",
    )
    parser.add_argument(
        "--http-host",
        default="127.0.0.1",
        help="HTTP server host for http/sse transport (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--http-port",
        type=int,
        default=8000,
        help="HTTP server port for http/sse transport (default: 8000)",
    )

    # Environment file argument
    parser.add_argument(
        "--env-file", type=Path, help="Path to .env file (default: .env in current directory)"
    )

    # Version argument
    parser.add_argument("--version", action="version", version=f"%(prog)s {_get_version()}")

    args = parser.parse_args()

    # Load .env file
    if args.env_file:
        # Use specified .env file
        if args.env_file.exists():
            load_dotenv(args.env_file)
        else:
            print(f"Error: .env file not found: {args.env_file}", file=sys.stderr)
            sys.exit(1)
    else:
        # Try current directory
        env_file = Path.cwd() / ".env"
        if env_file.exists():
            load_dotenv(env_file)

    # Apply defaults from environment with fallback values
    if args.host is None:
        args.host = os.getenv("GNS3_HOST", "localhost")
    if args.port is None:
        args.port = int(os.getenv("GNS3_PORT", "80"))
    if args.username is None:
        args.username = os.getenv("GNS3_USER", "admin")
    if args.password is None:
        args.password = os.getenv("GNS3_PASSWORD", "")

    # Validate required parameters
    if not args.password:
        print(
            "Error: GNS3 password required (set GNS3_PASSWORD in .env or use --password)",
            file=sys.stderr,
        )
        sys.exit(1)

    # Import MCP server (after .env is loaded)
    try:
        from gns3_mcp.server.main import mcp
    except ImportError as e:
        print(f"Error: Failed to import MCP server: {e}", file=sys.stderr)
        print("\nThis usually means dependencies are not installed.", file=sys.stderr)
        print("Try: pip install gns3-mcp", file=sys.stderr)
        sys.exit(1)

    # Store args in server for lifespan access
    mcp._args = args
    mcp.get_args = lambda: args

    # Run server with selected transport mode
    if args.transport == "stdio":
        # Process-based communication (default for Claude Desktop/Code)
        mcp.run()

    elif args.transport == "http":
        # Streamable HTTP transport (recommended for network access)
        try:
            import uvicorn
        except ImportError:
            print("Error: uvicorn not installed (required for HTTP transport)", file=sys.stderr)
            print("Try: pip install 'gns3-mcp[http]'", file=sys.stderr)
            sys.exit(1)

        print(
            f"Starting MCP server with HTTP transport at http://{args.http_host}:{args.http_port}/mcp/"
        )

        # Create ASGI app for HTTP transport
        app = mcp.http_app()

        # Run with uvicorn
        uvicorn.run(app, host=args.http_host, port=args.http_port, log_level="info")

    elif args.transport == "sse":
        # Legacy SSE transport (deprecated, use HTTP instead)
        try:
            import uvicorn
        except ImportError:
            print("Error: uvicorn not installed (required for SSE transport)", file=sys.stderr)
            print("Try: pip install 'gns3-mcp[http]'", file=sys.stderr)
            sys.exit(1)

        print("WARNING: SSE transport is deprecated. Consider using --transport http instead.")
        print(
            f"Starting MCP server with SSE transport at http://{args.http_host}:{args.http_port}/sse"
        )

        # Create ASGI app for SSE transport
        app = mcp.sse_app()

        # Run with uvicorn
        uvicorn.run(app, host=args.http_host, port=args.http_port, log_level="info")


def _get_version() -> str:
    """Get package version from __init__.py"""
    try:
        from gns3_mcp import __version__

        return __version__
    except ImportError:
        return "unknown"


if __name__ == "__main__":
    main()
