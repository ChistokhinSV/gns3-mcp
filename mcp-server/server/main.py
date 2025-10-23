"""GNS3 MCP Server v0.3.2

Model Context Protocol server for GNS3 lab automation.
Provides tools for managing projects, nodes, links, and console access.

Version 0.3.2 - Feature Enhancement:
- set_node() supports hardware configuration (rename, RAM, CPUs, HDD, adapters)
- Validation ensures node is stopped when renaming
- Cache invalidation after node property updates

Version 0.3.0 - Breaking Changes:
- All tools now return JSON (not formatted strings)
- set_connection() requires adapter_a and adapter_b parameters
- Two-phase validation prevents partial topology changes
- Data caching for improved performance
"""

import argparse
import asyncio
import json
import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from mcp.server.fastmcp import FastMCP, Context

from gns3_client import GNS3Client
from console_manager import ConsoleManager
from cache import DataCache
from link_validator import LinkValidator
from models import (
    ProjectInfo, NodeInfo, LinkInfo, LinkEndpoint,
    ConnectOperation, DisconnectOperation,
    CompletedOperation, FailedOperation, OperationResult,
    ConsoleStatus, ErrorResponse,
    validate_connection_operations
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S %d.%m.%Y'
)
logger = logging.getLogger(__name__)


@dataclass
class AppContext:
    """Application context with GNS3 client, console manager, and cache"""
    gns3: GNS3Client
    console: ConsoleManager
    cache: DataCache
    current_project_id: str | None = None
    cleanup_task: Optional[asyncio.Task] = field(default=None)


async def periodic_console_cleanup(console: ConsoleManager):
    """Periodically clean up expired console sessions"""
    while True:
        try:
            await asyncio.sleep(300)  # Every 5 minutes
            await console.cleanup_expired()
            logger.debug("Completed periodic console cleanup")
        except asyncio.CancelledError:
            logger.info("Console cleanup task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in cleanup task: {e}")


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

    # Initialize cache (30s TTL for nodes/links, 60s for projects)
    cache = DataCache(node_ttl=30, link_ttl=30, project_ttl=60)

    # Start periodic cleanup task
    cleanup_task = asyncio.create_task(periodic_console_cleanup(console))

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
        cache=cache,
        current_project_id=current_project_id,
        cleanup_task=cleanup_task
    )

    try:
        yield context
    finally:
        # Cleanup
        if cleanup_task:
            cleanup_task.cancel()
            try:
                await cleanup_task
            except asyncio.CancelledError:
                pass

        await console.close_all()
        await gns3.close()

        # Log cache statistics
        stats = cache.get_stats()
        logger.info(f"Cache statistics: {json.dumps(stats, indent=2)}")
        logger.info("GNS3 MCP Server shutdown complete")


# Helper Functions

async def validate_current_project(app: AppContext) -> Optional[str]:
    """Validate that current project is still open

    Args:
        app: Application context

    Returns:
        Error message if invalid, None if valid
    """
    if not app.current_project_id:
        return json.dumps(ErrorResponse(
            error="No project opened",
            details="Use open_project() to open a project first"
        ).model_dump(), indent=2)

    try:
        # Use cache for project list
        projects = await app.cache.get_projects(
            lambda: app.gns3.get_projects()
        )

        project = next((p for p in projects
                       if p['project_id'] == app.current_project_id), None)

        if not project:
            app.current_project_id = None
            return json.dumps(ErrorResponse(
                error="Project no longer exists",
                details=f"Project ID {app.current_project_id} not found. Use list_projects() and open_project()"
            ).model_dump(), indent=2)

        if project['status'] != 'opened':
            app.current_project_id = None
            return json.dumps(ErrorResponse(
                error=f"Project is {project['status']}",
                details=f"Project '{project['name']}' is not open. Use open_project() to reopen"
            ).model_dump(), indent=2)

        return None

    except Exception as e:
        return json.dumps(ErrorResponse(
            error="Failed to validate project",
            details=str(e)
        ).model_dump(), indent=2)


# Create MCP server
mcp = FastMCP(
    "GNS3 Lab Controller",
    lifespan=app_lifespan,
    dependencies=["mcp>=1.2.1", "httpx>=0.28.1", "telnetlib3>=2.0.4", "pydantic>=2.0.0"]
)


@mcp.tool()
async def list_projects(ctx: Context, force_refresh: bool = False) -> str:
    """List all GNS3 projects with their status

    Args:
        force_refresh: Force cache refresh (default: False)

    Returns:
        JSON array of ProjectInfo objects
    """
    app: AppContext = ctx.request_context.lifespan_context

    try:
        # Get projects with caching
        projects = await app.cache.get_projects(
            lambda: app.gns3.get_projects(),
            force_refresh=force_refresh
        )

        # Convert to ProjectInfo models
        project_models = [
            ProjectInfo(
                project_id=p['project_id'],
                name=p['name'],
                status=p['status'],
                path=p.get('path'),
                filename=p.get('filename'),
                auto_start=p.get('auto_start', False),
                auto_close=p.get('auto_close', True),
                auto_open=p.get('auto_open', False)
            )
            for p in projects
        ]

        return json.dumps([p.model_dump() for p in project_models], indent=2)

    except Exception as e:
        return json.dumps(ErrorResponse(
            error="Failed to list projects",
            details=str(e)
        ).model_dump(), indent=2)


@mcp.tool()
async def open_project(ctx: Context, project_name: str) -> str:
    """Open a GNS3 project by name

    Args:
        project_name: Name of the project to open

    Returns:
        JSON with ProjectInfo for opened project
    """
    app: AppContext = ctx.request_context.lifespan_context

    try:
        # Find project by name (use cache)
        projects = await app.cache.get_projects(
            lambda: app.gns3.get_projects(),
            force_refresh=True  # Refresh to get latest status
        )

        project = next((p for p in projects if p['name'] == project_name), None)

        if not project:
            return json.dumps(ErrorResponse(
                error="Project not found",
                details=f"No project named '{project_name}' found. Use list_projects() to see available projects."
            ).model_dump(), indent=2)

        # Open it
        result = await app.gns3.open_project(project['project_id'])
        app.current_project_id = project['project_id']

        # Invalidate caches (project status changed)
        await app.cache.invalidate_projects()

        # Return ProjectInfo
        project_info = ProjectInfo(
            project_id=result['project_id'],
            name=result['name'],
            status=result['status'],
            path=result.get('path'),
            filename=result.get('filename')
        )

        return json.dumps(project_info.model_dump(), indent=2)

    except Exception as e:
        return json.dumps(ErrorResponse(
            error="Failed to open project",
            details=str(e)
        ).model_dump(), indent=2)


@mcp.tool()
async def list_nodes(ctx: Context, force_refresh: bool = False) -> str:
    """List all nodes in the current project with their status and console info

    Args:
        force_refresh: Force cache refresh (default: False)

    Returns:
        JSON array of NodeInfo objects
    """
    app: AppContext = ctx.request_context.lifespan_context

    # Validate project
    error = await validate_current_project(app)
    if error:
        return error

    try:
        # Get nodes with caching
        nodes = await app.cache.get_nodes(
            app.current_project_id,
            lambda pid: app.gns3.get_nodes(pid),
            force_refresh=force_refresh
        )

        # Convert to NodeInfo models
        node_models = []
        for n in nodes:
            props = n.get('properties', {})
            node_models.append(NodeInfo(
                node_id=n['node_id'],
                name=n['name'],
                node_type=n['node_type'],
                status=n['status'],
                console_type=n['console_type'],
                console=n.get('console'),
                console_host=n.get('console_host'),
                compute_id=n.get('compute_id', 'local'),
                x=n.get('x', 0),
                y=n.get('y', 0),
                z=n.get('z', 0),
                locked=n.get('locked', False),
                ports=n.get('ports'),
                label=n.get('label'),
                symbol=n.get('symbol'),
                # Hardware properties
                ram=props.get('ram'),
                cpus=props.get('cpus'),
                adapters=props.get('adapters'),
                hdd_disk_image=props.get('hdd_disk_image'),
                hda_disk_image=props.get('hda_disk_image')
            ))

        return json.dumps([n.model_dump() for n in node_models], indent=2)

    except Exception as e:
        return json.dumps(ErrorResponse(
            error="Failed to list nodes",
            details=str(e)
        ).model_dump(), indent=2)


@mcp.tool()
async def get_node_details(ctx: Context, node_name: str, force_refresh: bool = False) -> str:
    """Get detailed information about a specific node

    Args:
        node_name: Name of the node
        force_refresh: Force cache refresh (default: False)

    Returns:
        JSON with NodeInfo object
    """
    app: AppContext = ctx.request_context.lifespan_context

    # Validate project
    error = await validate_current_project(app)
    if error:
        return error

    try:
        # Get nodes with caching
        nodes = await app.cache.get_nodes(
            app.current_project_id,
            lambda pid: app.gns3.get_nodes(pid),
            force_refresh=force_refresh
        )

        node = next((n for n in nodes if n['name'] == node_name), None)

        if not node:
            return json.dumps(ErrorResponse(
                error="Node not found",
                details=f"No node named '{node_name}' in current project. Use list_nodes() to see available nodes."
            ).model_dump(), indent=2)

        # Extract hardware properties from nested 'properties' object
        props = node.get('properties', {})

        # Convert to NodeInfo model
        node_info = NodeInfo(
            node_id=node['node_id'],
            name=node['name'],
            node_type=node['node_type'],
            status=node['status'],
            console_type=node['console_type'],
            console=node.get('console'),
            console_host=node.get('console_host'),
            compute_id=node.get('compute_id', 'local'),
            x=node.get('x', 0),
            y=node.get('y', 0),
            z=node.get('z', 0),
            locked=node.get('locked', False),
            ports=node.get('ports'),
            label=node.get('label'),
            symbol=node.get('symbol'),
            # Hardware properties
            ram=props.get('ram'),
            cpus=props.get('cpus'),
            adapters=props.get('adapters'),
            hdd_disk_image=props.get('hdd_disk_image'),
            hda_disk_image=props.get('hda_disk_image')
        )

        return json.dumps(node_info.model_dump(), indent=2)

    except Exception as e:
        return json.dumps(ErrorResponse(
            error="Failed to get node details",
            details=str(e)
        ).model_dump(), indent=2)


@mcp.tool()
async def get_links(ctx: Context, force_refresh: bool = False) -> str:
    """List all network links in the current project

    Returns link details including link IDs (needed for disconnect),
    connected nodes, ports, adapters, and link type. Use this before
    set_connection() to check current topology and find link IDs.

    Args:
        force_refresh: Force cache refresh (default: False)

    Returns:
        JSON array of LinkInfo objects
    """
    app: AppContext = ctx.request_context.lifespan_context

    # Validate project
    error = await validate_current_project(app)
    if error:
        return error

    try:
        # Get links and nodes with caching
        links = await app.cache.get_links(
            app.current_project_id,
            lambda pid: app.gns3.get_links(pid),
            force_refresh=force_refresh
        )

        nodes = await app.cache.get_nodes(
            app.current_project_id,
            lambda pid: app.gns3.get_nodes(pid),
            force_refresh=force_refresh
        )

        # Create node ID to name mapping
        node_map = {n['node_id']: n['name'] for n in nodes}

        # Convert to LinkInfo models
        link_models = []
        warnings = []

        for link in links:
            link_id = link['link_id']
            link_type = link.get('link_type', 'ethernet')
            link_nodes = link.get('nodes', [])

            # Check for corrupted links
            if len(link_nodes) < 2:
                warnings.append(
                    f"Warning: Link {link_id} has only {len(link_nodes)} endpoint(s) - "
                    f"possibly corrupted. Consider deleting with set_connection()"
                )
                continue

            if len(link_nodes) > 2:
                warnings.append(
                    f"Warning: Link {link_id} has {len(link_nodes)} endpoints - "
                    f"unexpected topology (multi-point link?)"
                )

            # Build LinkInfo
            node_a = link_nodes[0]
            node_b = link_nodes[1]

            link_info = LinkInfo(
                link_id=link_id,
                link_type=link_type,
                node_a=LinkEndpoint(
                    node_id=node_a['node_id'],
                    node_name=node_map.get(node_a['node_id'], 'Unknown'),
                    adapter_number=node_a.get('adapter_number', 0),
                    port_number=node_a.get('port_number', 0),
                    adapter_type=node_a.get('adapter_type'),
                    port_name=node_a.get('name')
                ),
                node_b=LinkEndpoint(
                    node_id=node_b['node_id'],
                    node_name=node_map.get(node_b['node_id'], 'Unknown'),
                    adapter_number=node_b.get('adapter_number', 0),
                    port_number=node_b.get('port_number', 0),
                    adapter_type=node_b.get('adapter_type'),
                    port_name=node_b.get('name')
                ),
                capturing=link.get('capturing', False),
                capture_file_name=link.get('capture_file_name'),
                capture_file_path=link.get('capture_file_path'),
                capture_compute_id=link.get('capture_compute_id'),
                suspend=link.get('suspend', False)
            )

            link_models.append(link_info)

        # Build response
        response = {
            "links": [link.model_dump() for link in link_models],
            "warnings": warnings if warnings else None
        }

        return json.dumps(response, indent=2)

    except Exception as e:
        return json.dumps(ErrorResponse(
            error="Failed to get links",
            details=str(e)
        ).model_dump(), indent=2)


@mcp.tool()
async def set_node(ctx: Context,
                   node_name: str,
                   action: Optional[str] = None,
                   x: Optional[int] = None,
                   y: Optional[int] = None,
                   z: Optional[int] = None,
                   locked: Optional[bool] = None,
                   ports: Optional[int] = None,
                   name: Optional[str] = None,
                   ram: Optional[int] = None,
                   cpus: Optional[int] = None,
                   hdd_disk_image: Optional[str] = None,
                   adapters: Optional[int] = None,
                   console_type: Optional[str] = None) -> str:
    """Configure node properties and/or control node state

    Args:
        node_name: Name of the node to modify
        action: Action to perform (start/stop/suspend/reload/restart)
        x: X coordinate
        y: Y coordinate
        z: Z-order (layer)
        locked: Lock node position
        ports: Number of ports (for ethernet switches)
        name: New name for the node (requires node to be stopped)
        ram: RAM in MB (QEMU nodes)
        cpus: Number of CPUs (QEMU nodes)
        hdd_disk_image: Path to HDD disk image (QEMU nodes)
        adapters: Number of network adapters (QEMU nodes)
        console_type: Console type (telnet, vnc, spice, etc.)

    Returns:
        Status message describing what was done
    """
    app: AppContext = ctx.request_context.lifespan_context

    if not app.current_project_id:
        return json.dumps(ErrorResponse(
            error="No project opened",
            details="Use open_project() to open a project first"
        ).model_dump(), indent=2)

    # Find node
    nodes = await app.gns3.get_nodes(app.current_project_id)
    node = next((n for n in nodes if n['name'] == node_name), None)

    if not node:
        return json.dumps(ErrorResponse(
            error="Node not found",
            details=f"Node '{node_name}' does not exist in current project"
        ).model_dump(), indent=2)

    node_id = node['node_id']
    node_status = node.get('status', 'unknown')
    results = []

    # Validate stopped state for properties that require it
    requires_stopped = []
    if name is not None:
        requires_stopped.append('name')

    if requires_stopped and node_status != 'stopped':
        return json.dumps(ErrorResponse(
            error="Node must be stopped",
            details=f"Properties {requires_stopped} can only be changed when node is stopped. Current status: {node_status}. Use set_node(node_name='{node_name}', action='stop') first."
        ).model_dump(), indent=2)

    # Handle property updates
    # Separate top-level properties from hardware properties
    update_payload = {}
    hardware_props = {}

    # Top-level properties
    if x is not None:
        update_payload['x'] = x
    if y is not None:
        update_payload['y'] = y
    if z is not None:
        update_payload['z'] = z
    if locked is not None:
        update_payload['locked'] = locked
    if name is not None:
        update_payload['name'] = name

    # Hardware properties (nested in 'properties' object for QEMU nodes)
    if ram is not None:
        hardware_props['ram'] = ram
    if cpus is not None:
        hardware_props['cpus'] = cpus
    if hdd_disk_image is not None:
        hardware_props['hdd_disk_image'] = hdd_disk_image
    if adapters is not None:
        hardware_props['adapters'] = adapters
    if console_type is not None:
        hardware_props['console_type'] = console_type

    # Special handling for ethernet switches
    if ports is not None:
        if node['node_type'] == 'ethernet_switch':
            ports_mapping = [
                {"name": f"Ethernet{i}", "port_number": i, "type": "access", "vlan": 1}
                for i in range(ports)
            ]
            hardware_props['ports_mapping'] = ports_mapping
        else:
            results.append(f"Warning: Port configuration only supported for ethernet switches")

    # Wrap hardware properties in 'properties' object for QEMU nodes
    if hardware_props and node['node_type'] == 'qemu':
        update_payload['properties'] = hardware_props
    elif hardware_props:
        # For non-QEMU nodes, merge directly
        update_payload.update(hardware_props)

    if update_payload:
        try:
            await app.gns3.update_node(app.current_project_id, node_id, update_payload)

            # Invalidate cache after node modification
            await app.cache.invalidate_nodes(app.current_project_id)

            # Build change summary
            changes = []
            if name is not None:
                changes.append(f"name={name}")
            if x is not None or y is not None or z is not None:
                pos_parts = []
                if x is not None: pos_parts.append(f"x={x}")
                if y is not None: pos_parts.append(f"y={y}")
                if z is not None: pos_parts.append(f"z={z}")
                changes.append(", ".join(pos_parts))
            if locked is not None:
                changes.append(f"locked={locked}")
            for k, v in hardware_props.items():
                if k != 'ports_mapping':
                    changes.append(f"{k}={v}")
            if 'ports_mapping' in hardware_props:
                changes.append(f"ports={ports}")

            results.append(f"Updated: {', '.join(changes)}")
        except Exception as e:
            return json.dumps(ErrorResponse(
                error="Failed to update properties",
                details=str(e)
            ).model_dump(), indent=2)

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
                return json.dumps(ErrorResponse(
                    error="Unknown action",
                    details=f"Action '{action}' not recognized. Valid actions: start, stop, suspend, reload, restart"
                ).model_dump(), indent=2)

        except Exception as e:
            return json.dumps(ErrorResponse(
                error="Action failed",
                details=str(e)
            ).model_dump(), indent=2)

    if not results:
        return json.dumps({"message": f"No changes made to {node_name}"}, indent=2)

    # Return success with list of changes
    return json.dumps({"message": "Node updated successfully", "changes": results}, indent=2)


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

    Returns:
        JSON with status
    """
    app: AppContext = ctx.request_context.lifespan_context

    success = await app.console.disconnect_by_node(node_name)

    return json.dumps({
        "success": success,
        "node_name": node_name,
        "message": "Disconnected successfully" if success else "No active session for this node"
    }, indent=2)


@mcp.tool()
async def get_console_status(ctx: Context, node_name: str) -> str:
    """Check console connection status for a node

    Makes auto-connect behavior transparent by showing connection state.

    Args:
        node_name: Name of the node

    Returns:
        JSON with ConsoleStatus object
    """
    app: AppContext = ctx.request_context.lifespan_context

    if app.console.has_session(node_name):
        session_id = app.console.get_session_id(node_name)
        sessions = app.console.list_sessions()
        session_info = sessions.get(session_id, {})

        status = ConsoleStatus(
            connected=True,
            node_name=node_name,
            session_id=session_id,
            host=session_info.get("host"),
            port=session_info.get("port"),
            buffer_size=session_info.get("buffer_size"),
            created_at=session_info.get("created_at")
        )
    else:
        status = ConsoleStatus(
            connected=False,
            node_name=node_name
        )

    return json.dumps(status.model_dump(), indent=2)


@mcp.tool()
async def set_connection(ctx: Context, connections: List[Dict[str, Any]]) -> str:
    """Manage network connections (links) in batch with two-phase validation

    BREAKING CHANGE v0.3.0: Now requires adapter_a and adapter_b parameters.

    Two-phase execution prevents partial topology changes:
    1. VALIDATE ALL operations (check nodes exist, ports free, adapters valid)
    2. EXECUTE ALL operations (only if all valid - atomic)

    Workflow:
        1. Call get_links() to see current topology
        2. Identify link IDs to disconnect (if needed)
        3. Call set_connection() with disconnect + connect operations

    Args:
        connections: List of connection operations:
            Connect: {
                "action": "connect",
                "node_a": "Router1",
                "node_b": "Router2",
                "port_a": 0,
                "port_b": 1,
                "adapter_a": 0,  # REQUIRED in v0.3.0 (default 0 if omitted)
                "adapter_b": 0   # REQUIRED in v0.3.0 (default 0 if omitted)
            }
            Disconnect: {
                "action": "disconnect",
                "link_id": "abc123"
            }

    Returns:
        JSON with OperationResult (completed and failed operations)
    """
    app: AppContext = ctx.request_context.lifespan_context

    # Validate project
    error = await validate_current_project(app)
    if error:
        return error

    try:
        # Validate operation structure with Pydantic
        parsed_ops, validation_error = validate_connection_operations(connections)
        if validation_error:
            return json.dumps(ErrorResponse(
                error="Invalid operation structure",
                details=validation_error
            ).model_dump(), indent=2)

        # Fetch topology data ONCE (not in loop - fixes N+1 issue)
        nodes = await app.cache.get_nodes(
            app.current_project_id,
            lambda pid: app.gns3.get_nodes(pid),
            force_refresh=True  # Ensure fresh data for validation
        )

        links = await app.cache.get_links(
            app.current_project_id,
            lambda pid: app.gns3.get_links(pid),
            force_refresh=True
        )

        # PHASE 1: VALIDATE ALL operations (no state changes)
        validator = LinkValidator(nodes, links)

        for idx, op in enumerate(parsed_ops):
            if isinstance(op, ConnectOperation):
                validation_error = validator.validate_connect(
                    op.node_a, op.node_b,
                    op.port_a, op.port_b,
                    op.adapter_a, op.adapter_b
                )
            else:  # DisconnectOperation
                validation_error = validator.validate_disconnect(op.link_id)

            if validation_error:
                return json.dumps(ErrorResponse(
                    error=f"Validation failed at operation {idx}",
                    details=validation_error,
                    operation_index=idx
                ).model_dump(), indent=2)

        logger.info(f"All {len(parsed_ops)} operations validated successfully")

        # PHASE 2: EXECUTE ALL operations (all validated - safe to proceed)
        completed = []
        failed = None
        node_map = {n['name']: n for n in nodes}

        for idx, op in enumerate(parsed_ops):
            try:
                if isinstance(op, ConnectOperation):
                    # Build link spec with adapter support (FIXES hardcoded adapter_number=0)
                    node_a = node_map[op.node_a]
                    node_b = node_map[op.node_b]

                    link_spec = {
                        "nodes": [
                            {
                                "node_id": node_a["node_id"],
                                "adapter_number": op.adapter_a,
                                "port_number": op.port_a
                            },
                            {
                                "node_id": node_b["node_id"],
                                "adapter_number": op.adapter_b,
                                "port_number": op.port_b
                            }
                        ]
                    }

                    result = await app.gns3.create_link(app.current_project_id, link_spec)

                    completed.append(CompletedOperation(
                        index=idx,
                        action="connect",
                        link_id=result.get("link_id"),
                        node_a=op.node_a,
                        node_b=op.node_b,
                        port_a=op.port_a,
                        port_b=op.port_b,
                        adapter_a=op.adapter_a,
                        adapter_b=op.adapter_b
                    ))

                    logger.info(f"Connected {op.node_a} adapter {op.adapter_a} port {op.port_a} <-> "
                              f"{op.node_b} adapter {op.adapter_b} port {op.port_b}")

                else:  # Disconnect
                    await app.gns3.delete_link(app.current_project_id, op.link_id)

                    completed.append(CompletedOperation(
                        index=idx,
                        action="disconnect",
                        link_id=op.link_id
                    ))

                    logger.info(f"Disconnected link {op.link_id}")

            except Exception as e:
                # Execution failed (should be rare after validation)
                failed = FailedOperation(
                    index=idx,
                    action=op.action,
                    operation=op.model_dump(),
                    reason=str(e)
                )
                logger.error(f"Operation {idx} failed during execution: {str(e)}")
                break

        # Invalidate cache after topology changes
        await app.cache.invalidate_links(app.current_project_id)
        await app.cache.invalidate_nodes(app.current_project_id)  # Port status changed

        # Build result
        result = OperationResult(completed=completed, failed=failed)
        return json.dumps(result.model_dump(), indent=2)

    except Exception as e:
        return json.dumps(ErrorResponse(
            error="Failed to manage connections",
            details=str(e)
        ).model_dump(), indent=2)


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
