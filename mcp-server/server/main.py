"""GNS3 MCP Server

Model Context Protocol server for GNS3 lab automation.
Provides tools for managing projects, nodes, links, and console access.
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
async def get_links(ctx: Context) -> str:
    """List all network links in the current project

    Returns link details including link IDs (needed for disconnect),
    connected nodes, ports, and link type. Use this before set_connection()
    to check current topology and find link IDs for disconnection.

    Output format: Link [ID]: NodeA port X <-> NodeB port Y (type)
    """
    app: AppContext = ctx.request_context.lifespan_context

    if not app.current_project_id:
        return "No project opened"

    # Get links and nodes
    links = await app.gns3.get_links(app.current_project_id)
    nodes = await app.gns3.get_nodes(app.current_project_id)

    # Create node ID to name mapping
    node_map = {n['node_id']: n['name'] for n in nodes}

    if not links:
        return "No links in project"

    # Format each link
    result = []
    for link in links:
        link_id = link['link_id']
        link_type = link.get('link_type', 'unknown')

        # Get node endpoints
        link_nodes = link.get('nodes', [])
        if len(link_nodes) >= 2:
            node_a = link_nodes[0]
            node_b = link_nodes[1]

            node_a_name = node_map.get(node_a['node_id'], 'Unknown')
            node_b_name = node_map.get(node_b['node_id'], 'Unknown')

            port_a = node_a.get('port_number', '?')
            port_b = node_b.get('port_number', '?')

            result.append(
                f"Link [{link_id}]: {node_a_name} port {port_a} <-> "
                f"{node_b_name} port {port_b} ({link_type})"
            )

    return "\n".join(result) if result else "No valid links found"


@mcp.tool()
async def set_node(ctx: Context,
                   node_name: str,
                   action: Optional[str] = None,
                   x: Optional[int] = None,
                   y: Optional[int] = None,
                   z: Optional[int] = None,
                   locked: Optional[bool] = None,
                   ports: Optional[int] = None) -> str:
    """Configure node properties and/or control node state

    Args:
        node_name: Name of the node
        action: Action to perform (start/stop/suspend/reload/restart)
        x: X coordinate
        y: Y coordinate
        z: Z-order (layer)
        locked: Lock node position
        ports: Number of ports (for ethernet switches)

    Returns:
        Status message describing what was done
    """
    app: AppContext = ctx.request_context.lifespan_context

    if not app.current_project_id:
        return "No project opened"

    # Find node
    nodes = await app.gns3.get_nodes(app.current_project_id)
    node = next((n for n in nodes if n['name'] == node_name), None)

    if not node:
        return f"Node '{node_name}' not found"

    node_id = node['node_id']
    results = []

    # Handle property updates
    properties = {}
    if x is not None:
        properties['x'] = x
    if y is not None:
        properties['y'] = y
    if z is not None:
        properties['z'] = z
    if locked is not None:
        properties['locked'] = locked
    if ports is not None:
        # For ethernet switches, update ports_mapping
        if node['node_type'] == 'ethernet_switch':
            ports_mapping = [
                {"name": f"Ethernet{i}", "port_number": i, "type": "access", "vlan": 1}
                for i in range(ports)
            ]
            properties['ports_mapping'] = ports_mapping
        else:
            results.append(f"Warning: Port configuration only supported for ethernet switches")

    if properties:
        try:
            await app.gns3.update_node(app.current_project_id, node_id, properties)
            prop_list = ", ".join(f"{k}={v}" for k, v in properties.items() if k != 'ports_mapping')
            if 'ports_mapping' in properties:
                prop_list += f", ports={ports}"
            results.append(f"Updated properties: {prop_list}")
        except Exception as e:
            return f"Failed to update properties: {str(e)}"

    # Handle action
    if action:
        action = action.lower()
        try:
            if action == 'start':
                await app.gns3.start_node(app.current_project_id, node_id)
                results.append(f"Started {node_name}")

            elif action == 'stop':
                await app.gns3.stop_node(app.current_project_id, node_id)
                results.append(f"Stopped {node_name}")

            elif action == 'suspend':
                await app.gns3.suspend_node(app.current_project_id, node_id)
                results.append(f"Suspended {node_name}")

            elif action == 'reload':
                await app.gns3.reload_node(app.current_project_id, node_id)
                results.append(f"Reloaded {node_name}")

            elif action == 'restart':
                # Stop node
                await app.gns3.stop_node(app.current_project_id, node_id)
                results.append(f"Stopped {node_name}")

                # Wait for node to stop with retries
                stopped = False
                for attempt in range(3):
                    await asyncio.sleep(5)
                    nodes = await app.gns3.get_nodes(app.current_project_id)
                    current_node = next((n for n in nodes if n['node_id'] == node_id), None)
                    if current_node and current_node['status'] == 'stopped':
                        stopped = True
                        break
                    results.append(f"Retry {attempt + 1}/3: Waiting for stop...")

                if not stopped:
                    results.append(f"Warning: Node may not have stopped completely")

                # Start node
                await app.gns3.start_node(app.current_project_id, node_id)
                results.append(f"Started {node_name}")

            else:
                return f"Unknown action: {action}. Valid: start, stop, suspend, reload, restart"

        except Exception as e:
            results.append(f"Action failed: {str(e)}")

    if not results:
        return f"No changes made to {node_name}"

    return "\n".join(results)


# Console helper function
async def _auto_connect_console(app: AppContext, node_name: str) -> Optional[str]:
    """Auto-connect to console if not already connected

    Returns:
        Error message if connection fails, None if successful
    """
    # Check if already connected
    if app.console.has_session(node_name):
        return None

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
        await app.console.connect(host, port, node_name)
        return None
    except Exception as e:
        return f"Failed to connect: {str(e)}"


@mcp.tool()
async def send_console(ctx: Context, node_name: str, data: str) -> str:
    """Send data to console (auto-connects if needed)

    Args:
        node_name: Name of the node
        data: Data to send (commands or keystrokes)
    """
    app: AppContext = ctx.request_context.lifespan_context

    # Auto-connect if needed
    error = await _auto_connect_console(app, node_name)
    if error:
        return error

    success = await app.console.send_by_node(node_name, data)
    return "Sent successfully" if success else "Failed to send"


@mcp.tool()
async def read_console(ctx: Context, node_name: str, diff: bool = False) -> str:
    """Read console output (auto-connects if needed)

    Args:
        node_name: Name of the node
        diff: If True, return only new output since last read

    Returns:
        Console output
    """
    app: AppContext = ctx.request_context.lifespan_context

    # Auto-connect if needed
    error = await _auto_connect_console(app, node_name)
    if error:
        return error

    if diff:
        output = app.console.get_diff_by_node(node_name)
    else:
        output = app.console.get_output_by_node(node_name)

    return output if output is not None else "No output available"


@mcp.tool()
async def disconnect_console(ctx: Context, node_name: str) -> str:
    """Disconnect console session

    Args:
        node_name: Name of the node
    """
    app: AppContext = ctx.request_context.lifespan_context

    success = await app.console.disconnect_by_node(node_name)
    return "Disconnected successfully" if success else "No active session for this node"


@mcp.tool()
async def set_connection(ctx: Context, connections: List[Dict[str, Any]]) -> str:
    """Manage network connections (links) in batch

    IMPORTANT: Call get_links() first to check current topology and find link IDs.
    Ports must be free before connecting - disconnect existing links first if needed.

    Executes connection operations sequentially. If an operation fails,
    returns status showing what completed and what failed.

    Workflow:
        1. Call get_links() to see current topology
        2. Identify link IDs to disconnect (if needed)
        3. Call set_connection() with disconnect + connect operations

    Args:
        connections: List of connection operations to perform.
            Each operation is a dict with:
            - action: "connect" or "disconnect"
            - For disconnect: {"action": "disconnect", "link_id": "abc123"}
            - For connect: {"action": "connect", "node_a": "R1", "port_a": 0,
                           "node_b": "R2", "port_b": 1}

    Returns:
        JSON string with completed and failed operations
    """
    app: AppContext = ctx.request_context.lifespan_context

    if not app.current_project_id:
        return json.dumps({"error": "No project opened"})

    completed = []
    failed = None

    # Execute operations sequentially
    for idx, conn in enumerate(connections):
        action = conn.get("action", "").lower()

        try:
            if action == "disconnect":
                # Disconnect operation
                link_id = conn.get("link_id")
                if not link_id:
                    raise ValueError("Missing link_id for disconnect operation")

                await app.gns3.delete_link(app.current_project_id, link_id)
                completed.append({
                    "index": idx,
                    "action": "disconnect",
                    "link_id": link_id
                })

            elif action == "connect":
                # Connect operation
                node_a_name = conn.get("node_a")
                node_b_name = conn.get("node_b")
                port_a = conn.get("port_a")
                port_b = conn.get("port_b")

                if not all([node_a_name, node_b_name, port_a is not None, port_b is not None]):
                    raise ValueError("Missing required fields for connect operation (node_a, node_b, port_a, port_b)")

                # Find nodes
                nodes = await app.gns3.get_nodes(app.current_project_id)
                node_a = next((n for n in nodes if n['name'] == node_a_name), None)
                node_b = next((n for n in nodes if n['name'] == node_b_name), None)

                if not node_a:
                    raise ValueError(f"Node '{node_a_name}' not found")
                if not node_b:
                    raise ValueError(f"Node '{node_b_name}' not found")

                # Create link specification
                # Using port_number as per API research (will verify in Phase 4)
                link_spec = {
                    "nodes": [
                        {
                            "node_id": node_a["node_id"],
                            "adapter_number": 0,  # Default adapter
                            "port_number": port_a
                        },
                        {
                            "node_id": node_b["node_id"],
                            "adapter_number": 0,  # Default adapter
                            "port_number": port_b
                        }
                    ]
                }

                result = await app.gns3.create_link(app.current_project_id, link_spec)
                completed.append({
                    "index": idx,
                    "action": "connect",
                    "link_id": result.get("link_id"),
                    "node_a": node_a_name,
                    "port_a": port_a,
                    "node_b": node_b_name,
                    "port_b": port_b
                })

            else:
                raise ValueError(f"Unknown action: {action}. Valid actions: connect, disconnect")

        except Exception as e:
            # Operation failed - record it and stop
            failed = {
                "index": idx,
                "action": action,
                "operation": conn,
                "reason": str(e)
            }
            break

    # Build result
    result = {"completed": completed}
    if failed:
        result["failed"] = failed

    return json.dumps(result, indent=2)


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
