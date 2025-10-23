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

# Get connection details from environment
host = os.getenv('GNS3_HOST', 'localhost')
port = int(os.getenv('GNS3_PORT', '80'))
username = os.getenv('GNS3_USER', 'admin')
password = os.getenv('GNS3_PASSWORD', '')

# Set sys.argv for the main script to parse
sys.argv = [
    'start_mcp.py',
    '--host', host,
    '--port', str(port),
    '--username', username,
    '--password', password
]

# Import and run the MCP server
if __name__ == '__main__':
    import argparse
    from main import mcp

    # Parse command line arguments (will use our modified sys.argv)
    parser = argparse.ArgumentParser(description="GNS3 MCP Server")
    parser.add_argument("--host", default="localhost", help="GNS3 server host")
    parser.add_argument("--port", type=int, default=80, help="GNS3 server port")
    parser.add_argument("--username", default="admin", help="GNS3 username")
    parser.add_argument("--password", default="", help="GNS3 password")

    args = parser.parse_args()

    # Store args in server for lifespan access
    mcp._args = args
    mcp.get_args = lambda: args

    # Run server
    mcp.run()
