"""GNS3 MCP Server

Model Context Protocol server for GNS3 lab automation.
Provides tools for managing projects, nodes, and console access.
"""

import argparse
import asyncio
import json
import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

from mcp.server.fastmcp import FastMCP, Context

from gns3_client import GNS3Client
from console_manager import ConsoleManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S %d.%m.%Y'
)
logger = logging.getLogger(__name__)


@dataclass
class AppContext:
    """Application context with GNS3 client and console manager"""
    gns3: GNS3Client
    console: ConsoleManager
    current_project_id: str | None = None


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Manage application lifecycle"""

    # Get server args
    args = server.get_args()

    # Initialize GNS3 client
    gns3 = GNS3Client(
        host=args.host,
        port=args.port,
        username=args.username,
        password=args.password
    )

    # Authenticate
    authenticated = await gns3.authenticate()
    if not authenticated:
        raise RuntimeError("Failed to authenticate to GNS3 server")

    # Initialize console manager
    console = ConsoleManager()

    # Auto-detect opened project
    projects = await gns3.get_projects()
    opened = [p for p in projects if p.get("status") == "opened"]
    current_project_id = opened[0]["project_id"] if opened else None

    if current_project_id:
        logger.info(f"Auto-detected opened project: {opened[0]['name']}")
    else:
        logger.warning("No opened project found - some tools require opening a project first")

    context = AppContext(
        gns3=gns3,
        console=console,
        current_project_id=current_project_id
    )

    try:
        yield context
    finally:
        # Cleanup
        await console.close_all()
        await gns3.close()
        logger.info("GNS3 MCP Server shutdown complete")


# Create MCP server
mcp = FastMCP(
    "GNS3 Lab Controller",
    lifespan=app_lifespan,
    dependencies=["mcp>=1.2.1", "httpx>=0.28.1", "telnetlib3>=2.0.4"]
)


@mcp.tool()
async def list_projects(ctx: Context) -> str:
    """List all GNS3 projects with their status"""
    gns3: GNS3Client = ctx.request_context.lifespan_context.gns3

    projects = await gns3.get_projects()

    result = []
    for p in projects:
        result.append(
            f"- {p['name']} ({p['status']}) [ID: {p['project_id']}]"
        )

    return "\n".join(result) if result else "No projects found"


@mcp.tool()
async def open_project(ctx: Context, project_name: str) -> str:
    """Open a GNS3 project by name

    Args:
        project_name: Name of the project to open
    """
    app: AppContext = ctx.request_context.lifespan_context

    # Find project by name
    projects = await app.gns3.get_projects()
    project = next((p for p in projects if p['name'] == project_name), None)

    if not project:
        return f"Project '{project_name}' not found"

    # Open it
    result = await app.gns3.open_project(project['project_id'])
    app.current_project_id = project['project_id']

    return f"Opened project: {result['name']} (status: {result['status']})"


@mcp.tool()
async def list_nodes(ctx: Context) -> str:
    """List all nodes in the current project with their status and console info"""
    app: AppContext = ctx.request_context.lifespan_context

    if not app.current_project_id:
        return "No project opened - use open_project() first"

    nodes = await app.gns3.get_nodes(app.current_project_id)

    result = []
    for node in nodes:
        console_info = f"{node['console_type']}:{node['console']}" if node['console'] else "none"
        result.append(
            f"- {node['name']} ({node['node_type']}) - {node['status']} [console: {console_info}] [ID: {node['node_id']}]"
        )

    return "\n".join(result) if result else "No nodes found"


@mcp.tool()
async def get_node_details(ctx: Context, node_name: str) -> str:
    """Get detailed information about a specific node

    Args:
        node_name: Name of the node
    """
    app: AppContext = ctx.request_context.lifespan_context

    if not app.current_project_id:
        return "No project opened"

    nodes = await app.gns3.get_nodes(app.current_project_id)
    node = next((n for n in nodes if n['name'] == node_name), None)

    if not node:
        return f"Node '{node_name}' not found"

    # Format key info
    info = [
        f"Name: {node['name']}",
        f"Type: {node['node_type']}",
        f"Status: {node['status']}",
        f"Console: {node['console_type']}:{node['console']} @ {node['console_host']}",
        f"ID: {node['node_id']}",
        f"Compute: {node['compute_id']}"
    ]

    if 'ports' in node:
        info.append(f"Ports: {len(node['ports'])}")

    return "\n".join(info)


@mcp.tool()
async def start_node(ctx: Context, node_name: str) -> str:
    """Start a node in the current project

    Args:
        node_name: Name of the node to start
    """
    app: AppContext = ctx.request_context.lifespan_context

    if not app.current_project_id:
        return "No project opened"

    # Find node
    nodes = await app.gns3.get_nodes(app.current_project_id)
    node = next((n for n in nodes if n['name'] == node_name), None)

    if not node:
        return f"Node '{node_name}' not found"

    if node['status'] == 'started':
        return f"Node '{node_name}' is already started"

    # Start it
    result = await app.gns3.start_node(app.current_project_id, node['node_id'])
    return f"Started {node_name} - status: {result.get('status', 'unknown')}"


@mcp.tool()
async def stop_node(ctx: Context, node_name: str) -> str:
    """Stop a node in the current project

    Args:
        node_name: Name of the node to stop
    """
    app: AppContext = ctx.request_context.lifespan_context

    if not app.current_project_id:
        return "No project opened"

    # Find node
    nodes = await app.gns3.get_nodes(app.current_project_id)
    node = next((n for n in nodes if n['name'] == node_name), None)

    if not node:
        return f"Node '{node_name}' not found"

    if node['status'] == 'stopped':
        return f"Node '{node_name}' is already stopped"

    # Stop it
    result = await app.gns3.stop_node(app.current_project_id, node['node_id'])
    return f"Stopped {node_name} - status: {result.get('status', 'unknown')}"


@mcp.tool()
async def connect_console(ctx: Context, node_name: str) -> str:
    """Connect to a node's console

    Args:
        node_name: Name of the node

    Returns:
        Session ID for subsequent console operations
    """
    app: AppContext = ctx.request_context.lifespan_context

    if not app.current_project_id:
        return "No project opened"

    # Find node
    nodes = await app.gns3.get_nodes(app.current_project_id)
    node = next((n for n in nodes if n['name'] == node_name), None)

    if not node:
        return f"Node '{node_name}' not found"

    # Check console type
    console_type = node['console_type']
    if console_type not in ['telnet']:
        return f"Console type '{console_type}' not supported (only 'telnet' currently supported)"

    if not node['console']:
        return f"Node '{node_name}' has no console configured"

    # Extract host from GNS3 client config
    host = app.gns3.base_url.split('//')[1].split(':')[0]
    port = node['console']

    # Connect
    try:
        session_id = await app.console.connect(host, port, node_name)
        return f"Connected to {node_name} console\nSession ID: {session_id}\nUse this session ID with send_console, read_console, and disconnect_console"
    except Exception as e:
        return f"Failed to connect: {str(e)}"


@mcp.tool()
async def send_console(ctx: Context, session_id: str, data: str) -> str:
    """Send data to console session

    Args:
        session_id: Console session ID from connect_console
        data: Data to send (commands or keystrokes)
    """
    app: AppContext = ctx.request_context.lifespan_context

    success = await app.console.send(session_id, data)
    return "Sent successfully" if success else "Failed to send"


@mcp.tool()
async def read_console(ctx: Context, session_id: str) -> str:
    """Read current console output

    Args:
        session_id: Console session ID

    Returns:
        Full console buffer
    """
    app: AppContext = ctx.request_context.lifespan_context

    output = app.console.get_output(session_id)
    return output if output is not None else f"Session '{session_id}' not found"


@mcp.tool()
async def read_console_diff(ctx: Context, session_id: str) -> str:
    """Read new console output since last read

    Args:
        session_id: Console session ID

    Returns:
        New output since last read
    """
    app: AppContext = ctx.request_context.lifespan_context

    diff = app.console.get_diff(session_id)
    return diff if diff is not None else f"Session '{session_id}' not found"


@mcp.tool()
async def disconnect_console(ctx: Context, session_id: str) -> str:
    """Disconnect console session

    Args:
        session_id: Console session ID to disconnect
    """
    app: AppContext = ctx.request_context.lifespan_context

    success = await app.console.disconnect(session_id)
    return "Disconnected successfully" if success else "Failed to disconnect or session not found"


@mcp.tool()
async def list_console_sessions(ctx: Context) -> str:
    """List all active console sessions"""
    app: AppContext = ctx.request_context.lifespan_context

    sessions = app.console.list_sessions()

    if not sessions:
        return "No active console sessions"

    result = []
    for sid, info in sessions.items():
        result.append(
            f"- {info['node_name']} @ {info['host']}:{info['port']} "
            f"[Session: {sid}, Buffer: {info['buffer_size']} bytes]"
        )

    return "\n".join(result)


if __name__ == "__main__":
    # Parse command line arguments
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
