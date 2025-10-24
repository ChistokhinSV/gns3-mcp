"""GNS3 MCP Server v0.9.1

Model Context Protocol server for GNS3 lab automation.
Provides tools for managing projects, nodes, links, console access, and drawings.

Version 0.9.1 - Error Message Improvements (PATCH):
- IMPROVED: Added suggested_action to 15 critical error messages for better user guidance
- IMPROVED: Standardized all 20 tool descriptions in manifest with return types
- IMPROVED: Better adapter error messages (shows 15 ports, notes case-sensitivity, suggests get_links())
- FIXED: read_console() mode validation now returns plain string (not JSON), consistent with other console tools

Version 0.9.0 - Major Refactoring (BREAKING CHANGES):
- REMOVED: Caching infrastructure (cache.py, all cache usage, force_refresh parameters)
- REMOVED: detect_console_state() tool and DEVICE_PATTERNS dictionary
- CHANGED: read_console() now uses mode parameter ("diff"/"last_page"/"all") instead of bool flags
- SIMPLIFIED: Direct API calls instead of cache layer, better for local/close labs

Version 0.6.4 - Z-Order Rendering Fix:
- FIXED: Z-order rendering in topology export now matches GNS3 GUI painter's algorithm
  * Links render at z=min(connected_nodes)-0.5 (always below nodes)
  * Drawings and nodes intermixed by z-value (sorted rendering)
  * Port indicators integrated into link rendering
  * Ensures correct layering: links → nodes/drawings (by z) → high-z elements

Version 0.6.3 - Font Fallback Chain:
- FIXED: Font fallback for consistent cross-platform rendering in SVG/PNG exports
  * TypeWriter → Courier New → Courier → Liberation Mono → Consolas → monospace
  * Other fonts get appropriate fallback chains (serif, sans-serif)
  * Ensures consistent appearance regardless of system font availability

Version 0.6.2 - Label Rendering Fix:
- FIXED: Node label positioning in export_topology_diagram() now matches official GNS3
  * Labels use GNS3-stored positions directly (no incorrect offset additions)
  * Dynamic text-anchor based on label position (start/middle/end)
  * Auto-centering when x is None (matches GNS3 behavior)
  * Removes dominant-baseline from CSS, applies text-before-edge

Version 0.6.1 - Newline Normalization & Special Keystrokes:
- FIXED: All newlines automatically converted to \r\n (CR+LF) for console compatibility
  * Copy-paste multi-line text directly - newlines just work
  * send_console() and send_and_wait_console() normalize all line endings
  * Handles \n, \r, \r\n uniformly → all become \r\n
  * Add raw=True parameter to disable processing
- NEW: send_keystroke() - Send special keys for TUI navigation and vim editing
  * Navigation: up, down, left, right, home, end, pageup, pagedown
  * Editing: enter (sends \r\n), backspace, delete, tab, esc
  * Control: ctrl_c, ctrl_d, ctrl_z, ctrl_a, ctrl_e
  * Function keys: f1-f12
- FIXED: detect_console_state() now checks only last non-empty line (not 5 lines)
  * Prevents detecting old prompts instead of current state
  * Fixed MikroTik password patterns: "new password>" not "new password:"

Version 0.6.0 - Interactive Console Tools:
- NEW: send_and_wait_console() - Send command and wait for prompt pattern
- NEW: detect_console_state() - Auto-detect device type and console state
- ENHANCED: Console tool docstrings with timing guidance
- Added DEVICE_PATTERNS library for auto-detection

Version 0.5.1 - Label Alignment:
- Fixed node label alignment - right-aligned and vertically centered

Version 0.5.0 - Port Status Indicators:
- Topology export shows port status (green=active, red=stopped)

Version 0.4.2 - Topology Export:
- NEW: export_topology_diagram() - Export topology as SVG/PNG

Version 0.4.0 - Node Creation & Drawing Objects:
- NEW: delete_node, list_templates, create_node
- NEW: list_drawings, create_rectangle, create_text, create_ellipse

Version 0.3.0 - Type Safety & Caching:
- Type-safe Pydantic models, two-phase validation, performance caching
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
from link_validator import LinkValidator
from models import (
    ProjectInfo, NodeInfo, LinkInfo, LinkEndpoint,
    ConnectOperation, DisconnectOperation,
    CompletedOperation, FailedOperation, OperationResult,
    ConsoleStatus, ErrorResponse,
    TemplateInfo, DrawingInfo,
    validate_connection_operations
)
from export_tools import (
    export_topology_diagram,
    create_rectangle_svg,
    create_text_svg,
    create_ellipse_svg,
    create_line_svg
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S %d.%m.%Y'
)
logger = logging.getLogger(__name__)

# Note: SVG generation helpers moved to export_tools.py for better modularity


@dataclass
class AppContext:
    """Application context with GNS3 client and console manager"""
    gns3: GNS3Client
    console: ConsoleManager
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
            details="Use open_project() to open a project first",
            suggested_action="Call list_projects() to see available projects, then open_project(project_name)"
        ).model_dump(), indent=2)

    try:
        # Get project list directly from API
        projects = await app.gns3.get_projects()

        project = next((p for p in projects
                       if p['project_id'] == app.current_project_id), None)

        if not project:
            app.current_project_id = None
            return json.dumps(ErrorResponse(
                error="Project no longer exists",
                details=f"Project ID {app.current_project_id} not found. Use list_projects() and open_project()",
                suggested_action="Call list_projects() to see current projects, then open_project(project_name)"
            ).model_dump(), indent=2)

        if project['status'] != 'opened':
            app.current_project_id = None
            return json.dumps(ErrorResponse(
                error=f"Project is {project['status']}",
                details=f"Project '{project['name']}' is not open. Use open_project() to reopen",
                suggested_action=f"Call open_project('{project['name']}') to reopen this project"
            ).model_dump(), indent=2)

        return None

    except Exception as e:
        return json.dumps(ErrorResponse(
            error="Failed to validate project",
            details=str(e),
            suggested_action="Check GNS3 server connection and project state"
        ).model_dump(), indent=2)


# Create MCP server
mcp = FastMCP(
    "GNS3 Lab Controller",
    lifespan=app_lifespan,
    dependencies=["mcp>=1.2.1", "httpx>=0.28.1", "telnetlib3>=2.0.4", "pydantic>=2.0.0"]
)


@mcp.tool()
async def list_projects(ctx: Context) -> str:
    """List all GNS3 projects with their status

    Returns:
        JSON array of ProjectInfo objects
    """
    app: AppContext = ctx.request_context.lifespan_context

    try:
        # Get projects directly from API
        projects = await app.gns3.get_projects()

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
        # Find project by name
        projects = await app.gns3.get_projects()

        project = next((p for p in projects if p['name'] == project_name), None)

        if not project:
            return json.dumps(ErrorResponse(
                error="Project not found",
                details=f"No project named '{project_name}' found. Use list_projects() to see available projects.",
                suggested_action="Call list_projects() to see exact project names (case-sensitive)"
            ).model_dump(), indent=2)

        # Open it
        result = await app.gns3.open_project(project['project_id'])
        app.current_project_id = project['project_id']

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
            details=str(e),
            suggested_action="Verify project exists in GNS3 and is not corrupted"
        ).model_dump(), indent=2)


@mcp.tool()
async def list_nodes(ctx: Context) -> str:
    """List all nodes in the current project with their status and console info

    Returns:
        JSON array of NodeInfo objects
    """
    app: AppContext = ctx.request_context.lifespan_context

    # Validate project
    error = await validate_current_project(app)
    if error:
        return error

    try:
        # Get nodes directly from API
        nodes = await app.gns3.get_nodes(app.current_project_id)

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
async def get_node_details(ctx: Context, node_name: str) -> str:
    """Get detailed information about a specific node

    Args:
        node_name: Name of the node

    Returns:
        JSON with NodeInfo object
    """
    app: AppContext = ctx.request_context.lifespan_context

    # Validate project
    error = await validate_current_project(app)
    if error:
        return error

    try:
        # Get nodes directly from API
        nodes = await app.gns3.get_nodes(app.current_project_id)

        node = next((n for n in nodes if n['name'] == node_name), None)

        if not node:
            return json.dumps(ErrorResponse(
                error="Node not found",
                details=f"No node named '{node_name}' in current project. Use list_nodes() to see available nodes.",
                suggested_action="Call list_nodes() to see exact node names (case-sensitive)"
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
async def get_links(ctx: Context) -> str:
    """List all network links in the current project

    Returns link details including link IDs (needed for disconnect),
    connected nodes, ports, adapters, and link type. Use this before
    set_connection() to check current topology and find link IDs.

    Returns:
        JSON array of LinkInfo objects
    """
    app: AppContext = ctx.request_context.lifespan_context

    # Validate project
    error = await validate_current_project(app)
    if error:
        return error

    try:
        # Get links and nodes directly from API
        links = await app.gns3.get_links(app.current_project_id)
        nodes = await app.gns3.get_nodes(app.current_project_id)

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

    Validation Rules:
    - name parameter requires node to be stopped
    - Hardware properties (ram, cpus, hdd_disk_image, adapters) apply to QEMU nodes only
    - ports parameter applies to ethernet_switch nodes only
    - action values: start, stop, suspend, reload, restart
    - restart action: stops node (with retry logic), waits for confirmed stop, then starts

    Args:
        node_name: Name of the node to modify
        action: Action to perform (start/stop/suspend/reload/restart)
        x: X coordinate (top-left corner of node icon)
        y: Y coordinate (top-left corner of node icon)
        z: Z-order (layer) for overlapping nodes
        locked: Lock node position (prevents accidental moves in GUI)
        ports: Number of ports (ethernet_switch nodes only)
        name: New name for the node (REQUIRES node to be stopped)
        ram: RAM in MB (QEMU nodes only)
        cpus: Number of CPUs (QEMU nodes only)
        hdd_disk_image: Path to HDD disk image (QEMU nodes only)
        adapters: Number of network adapters (QEMU nodes only)
        console_type: Console type - telnet, vnc, spice, etc.

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
            details=f"Node '{node_name}' does not exist in current project",
            suggested_action="Call list_nodes() to see exact node names (case-sensitive)"
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
        return "No project opened. Use open_project() first."

    # Find node
    nodes = await app.gns3.get_nodes(app.current_project_id)
    node = next((n for n in nodes if n['name'] == node_name), None)

    if not node:
        return f"Node '{node_name}' not found. Use list_nodes() to see available nodes (case-sensitive)."

    # Check console type
    console_type = node['console_type']
    if console_type not in ['telnet']:
        return f"Console type '{console_type}' not supported (only 'telnet' currently supported). Check node configuration."

    if not node['console']:
        return f"Node '{node_name}' has no console configured. Verify node is started with list_nodes()."

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
async def send_console(ctx: Context, node_name: str, data: str, raw: bool = False) -> str:
    """Send data to console (auto-connects if needed)

    Sends data immediately to console without waiting for response.
    For interactive workflows, use read_console() after sending to verify output.

    Timing Considerations:
    - Console output appears in background buffer (read via read_console)
    - Allow 0.5-2 seconds after send before reading for command processing
    - Interactive prompts (login, password) may need 1-3 seconds to appear
    - Boot/initialization sequences may take 30-60 seconds

    Auto-connect Behavior:
    - First send/read automatically connects to console (no manual connect needed)
    - Connection persists until disconnect_console() or 30-minute timeout
    - Check connection state with get_console_status()

    Escape Sequence Processing:
    - By default, processes common escape sequences (\n, \r, \t, \x1b)
    - Use raw=True to send data without processing (for binary data)

    Args:
        node_name: Name of the node (e.g., "Router1")
        data: Data to send - include newline for commands (e.g., "enable\n")
              Send just "\n" to wake console and check for prompts
        raw: If True, send data without escape sequence processing (default: False)

    Returns:
        "Sent successfully" or error message

    Example - Wake console and check state:
        send_console("R1", "\n")
        await 1 second
        read_console("R1", diff=True)  # See what prompt appeared
    """
    app: AppContext = ctx.request_context.lifespan_context

    # Auto-connect if needed
    error = await _auto_connect_console(app, node_name)
    if error:
        return error

    # Process escape sequences unless raw mode
    if not raw:
        # First handle escape sequences (backslash-escaped strings)
        data = data.replace('\\r\\n', '\r\n')  # \r\n → CR+LF
        data = data.replace('\\n', '\n')       # \n → LF
        data = data.replace('\\r', '\r')       # \r → CR
        data = data.replace('\\t', '\t')       # \t → tab
        data = data.replace('\\x1b', '\x1b')   # \x1b → ESC

        # Then normalize all newlines to \r\n for console compatibility
        # This handles copy-pasted multi-line text
        data = data.replace('\r\n', '\n')      # Normalize CRLF to LF first
        data = data.replace('\r', '\n')        # Normalize CR to LF
        data = data.replace('\n', '\r\n')      # Convert all LF to CRLF

    success = await app.console.send_by_node(node_name, data)
    return "Sent successfully" if success else "Failed to send"


@mcp.tool()
async def read_console(ctx: Context, node_name: str, mode: str = "diff") -> str:
    """Read console output (auto-connects if needed)

    Reads accumulated output from background console buffer. Output accumulates
    while device runs - this function retrieves it without blocking.

    Buffer Behavior:
    - Background task continuously reads console into 10MB buffer
    - Diff mode (DEFAULT): Returns only NEW output since last read
    - Last page mode: Returns last ~25 lines of buffer
    - All mode: Returns ALL console output since connection
    - Read position advances with each diff mode read

    Timing Recommendations:
    - After send_console(): Wait 0.5-2s before reading for command output
    - After node start: Wait 30-60s for boot messages
    - Interactive prompts: Wait 1-3s for prompt to appear

    State Detection Tips:
    - Look for prompt patterns: "Router>", "Login:", "Password:", "#"
    - Check for "% " at start of line (IOS error messages)
    - Look for "[OK]" or "failed" for command results
    - MikroTik prompts: "[admin@RouterOS] > " or similar

    Args:
        node_name: Name of the node
        mode: Output mode (default: "diff")
            - "diff": Return only new output since last read (DEFAULT)
            - "last_page": Return last ~25 lines of buffer
            - "all": Return entire buffer since connection

    Returns:
        Console output (ANSI escape codes stripped, line endings normalized)
        or "No output available" if buffer empty

    Example - Interactive session (default):
        output = read_console("R1")  # mode="diff" by default
        if "Login:" in output:
            send_console("R1", "admin\\n")

    Example - Check recent output:
        output = read_console("R1", mode="last_page")  # Last 25 lines

    Example - Get everything:
        output = read_console("R1", mode="all")  # Entire buffer
    """
    app: AppContext = ctx.request_context.lifespan_context

    # Validate mode parameter
    if mode not in ("diff", "last_page", "all"):
        return (f"Invalid mode '{mode}'. Valid modes:\n"
                f"  'diff' - New output since last read (default)\n"
                f"  'last_page' - Last ~25 lines\n"
                f"  'all' - Entire buffer")

    # Auto-connect if needed
    error = await _auto_connect_console(app, node_name)
    if error:
        return error

    if mode == "diff":
        # Return only new output since last read
        output = app.console.get_diff_by_node(node_name)
    elif mode == "last_page":
        # Return last ~25 lines
        full_output = app.console.get_output_by_node(node_name)
        if full_output:
            lines = full_output.splitlines()
            output = '\n'.join(lines[-25:]) if len(lines) > 25 else full_output
        else:
            output = None
    else:  # mode == "all"
        # Return entire buffer
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

    Shows connection state and buffer size. Does NOT show current prompt or
    device readiness - use read_console(diff=True) to check current state.

    Returns:
        JSON with ConsoleStatus:
        {
            "connected": true/false,
            "node_name": "Router1",
            "session_id": "uuid",  # null if not connected
            "host": "192.168.1.20",  # null if not connected
            "port": 5000,  # null if not connected
            "buffer_size": 1024,  # bytes accumulated
            "created_at": "2025-10-23T10:30:00"  # null if not connected
        }

    Use Cases:
    - Check if already connected before manual operations
    - Verify auto-connect succeeded
    - Monitor buffer size (>10MB triggers trim to 5MB)

    Note: Connection state does NOT indicate device readiness. A connected
    console may still be at login prompt, booting, or waiting for input.
    Use read_console() to check current prompt state.

    Args:
        node_name: Name of the node

    Example:
        status = get_console_status("R1")
        if status["connected"]:
            print(f"Buffer size: {status['buffer_size']} bytes")
        else:
            print("Not connected - next send/read will auto-connect")
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
async def send_and_wait_console(
    ctx: Context,
    node_name: str,
    command: str,
    wait_pattern: Optional[str] = None,
    timeout: int = 30,
    raw: bool = False
) -> str:
    """Send command and wait for specific prompt pattern

    Combines send + wait + read into single operation. Useful for interactive
    workflows where you need to verify prompt before proceeding.

    BEST PRACTICE: Before using this tool, first check what the prompt looks like:
    1. Send "\n" with send_console() to wake the console
    2. Use read_console() to see the current prompt (e.g., "Router#", "[admin@MikroTik] >")
    3. Use that exact prompt pattern in wait_pattern parameter
    4. This ensures you wait for the right prompt and don't miss command output

    Workflow:
    1. Send command to console
    2. If wait_pattern provided: poll console until pattern appears or timeout
    3. Return all output accumulated during wait

    Args:
        node_name: Name of the node
        command: Command to send (include \n for newline)
        wait_pattern: Optional regex pattern to wait for (e.g., "Router[>#]", "Login:")
                      If None, waits 2 seconds and returns output
                      TIP: Check prompt first with read_console() to get exact pattern
        timeout: Maximum seconds to wait for pattern (default: 30)
        raw: If True, send command without escape sequence processing (default: False)

    Returns:
        JSON with:
        {
            "output": "console output",
            "pattern_found": true/false,
            "timeout_occurred": true/false,
            "wait_time": 2.5  # seconds actually waited
        }

    Example - Best practice workflow:
        # Step 1: Check the prompt first
        send_console("R1", "\n")
        output = read_console("R1")  # Shows "Router#"

        # Step 2: Use that prompt pattern
        result = send_and_wait_console(
            "R1",
            "show ip interface brief\n",
            wait_pattern="Router#",  # Wait for exact prompt
            timeout=10
        )
        # Returns when "Router#" appears - command is complete

    Example - Wait for login prompt:
        result = send_and_wait_console(
            "R1",
            "\n",
            wait_pattern="Login:",
            timeout=10
        )
        # Returns when "Login:" appears or after 10 seconds

    Example - No pattern (just wait 2s):
        result = send_and_wait_console("R1", "enable\n")
        # Sends command, waits 2s, returns output
    """
    app: AppContext = ctx.request_context.lifespan_context

    # Auto-connect
    error = await _auto_connect_console(app, node_name)
    if error:
        return json.dumps({
            "error": error,
            "output": "",
            "pattern_found": False,
            "timeout_occurred": False
        }, indent=2)

    # Process escape sequences unless raw mode
    if not raw:
        # First handle escape sequences (backslash-escaped strings)
        command = command.replace('\\r\\n', '\r\n')  # \r\n → CR+LF
        command = command.replace('\\n', '\n')       # \n → LF
        command = command.replace('\\r', '\r')       # \r → CR
        command = command.replace('\\t', '\t')       # \t → tab
        command = command.replace('\\x1b', '\x1b')   # \x1b → ESC

        # Then normalize all newlines to \r\n for console compatibility
        command = command.replace('\r\n', '\n')      # Normalize CRLF to LF first
        command = command.replace('\r', '\n')        # Normalize CR to LF
        command = command.replace('\n', '\r\n')      # Convert all LF to CRLF

    # Send command
    success = await app.console.send_by_node(node_name, command)
    if not success:
        return json.dumps({
            "error": "Failed to send command",
            "output": "",
            "pattern_found": False,
            "timeout_occurred": False
        }, indent=2)

    # Wait for pattern or timeout
    import time
    start_time = time.time()
    pattern_found = False
    timeout_occurred = False

    if wait_pattern:
        import re
        try:
            pattern_re = re.compile(wait_pattern)
        except re.error as e:
            return json.dumps({
                "error": f"Invalid regex pattern: {str(e)}",
                "output": "",
                "pattern_found": False,
                "timeout_occurred": False
            }, indent=2)

        # Poll console every 0.5s
        while (time.time() - start_time) < timeout:
            await asyncio.sleep(0.5)
            output = app.console.get_diff_by_node(node_name) or ""

            if pattern_re.search(output):
                pattern_found = True
                break

        if not pattern_found:
            timeout_occurred = True
    else:
        # No pattern - just wait 2 seconds
        await asyncio.sleep(2)

    wait_time = time.time() - start_time

    # Get all output since command was sent
    output = app.console.get_diff_by_node(node_name) or ""

    return json.dumps({
        "output": output,
        "pattern_found": pattern_found,
        "timeout_occurred": timeout_occurred,
        "wait_time": round(wait_time, 2)
    }, indent=2)


@mcp.tool()
async def send_keystroke(ctx: Context, node_name: str, key: str) -> str:
    """Send special keystroke to console (auto-connects if needed)

    Sends special keys like arrows, function keys, control sequences for
    navigating menus, editing in vim, or TUI applications.

    Supported Keys:
    - Navigation: "up", "down", "left", "right", "home", "end", "pageup", "pagedown"
    - Editing: "enter", "backspace", "delete", "tab", "esc"
    - Control: "ctrl_c", "ctrl_d", "ctrl_z", "ctrl_a", "ctrl_e"
    - Function: "f1" through "f12"

    Args:
        node_name: Name of the node
        key: Special key to send (e.g., "up", "enter", "ctrl_c")

    Returns:
        "Sent successfully" or error message

    Example - Navigate menu:
        send_keystroke("R1", "down")
        send_keystroke("R1", "down")
        send_keystroke("R1", "enter")

    Example - Exit vim:
        send_keystroke("R1", "esc")
        send_console("R1", ":wq\n")
    """
    app: AppContext = ctx.request_context.lifespan_context

    # Auto-connect if needed
    error = await _auto_connect_console(app, node_name)
    if error:
        return error

    # Map key names to escape sequences
    SPECIAL_KEYS = {
        # Navigation
        'up': '\x1b[A',
        'down': '\x1b[B',
        'right': '\x1b[C',
        'left': '\x1b[D',
        'home': '\x1b[H',
        'end': '\x1b[F',
        'pageup': '\x1b[5~',
        'pagedown': '\x1b[6~',

        # Editing
        'enter': '\r\n',
        'backspace': '\x7f',
        'delete': '\x1b[3~',
        'tab': '\t',
        'esc': '\x1b',

        # Control sequences
        'ctrl_c': '\x03',
        'ctrl_d': '\x04',
        'ctrl_z': '\x1a',
        'ctrl_a': '\x01',
        'ctrl_e': '\x05',

        # Function keys
        'f1': '\x1bOP',
        'f2': '\x1bOQ',
        'f3': '\x1bOR',
        'f4': '\x1bOS',
        'f5': '\x1b[15~',
        'f6': '\x1b[17~',
        'f7': '\x1b[18~',
        'f8': '\x1b[19~',
        'f9': '\x1b[20~',
        'f10': '\x1b[21~',
        'f11': '\x1b[23~',
        'f12': '\x1b[24~',
    }

    key_lower = key.lower()
    if key_lower not in SPECIAL_KEYS:
        return f"Unknown key: {key}. Supported keys: {', '.join(sorted(SPECIAL_KEYS.keys()))}"

    keystroke = SPECIAL_KEYS[key_lower]
    success = await app.console.send_by_node(node_name, keystroke)
    return "Sent successfully" if success else "Failed to send"


@mcp.tool()
async def set_connection(ctx: Context, connections: List[Dict[str, Any]]) -> str:
    """Manage network connections (links) in batch with two-phase validation

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
                "adapter_a": "eth0",  # Port name OR adapter number (int)
                "adapter_b": "GigabitEthernet0/0"  # Port name OR adapter number
            }
            Disconnect: {
                "action": "disconnect",
                "link_id": "abc123"
            }

    Returns:
        JSON with OperationResult (completed and failed operations)
        Includes both port names and adapter/port numbers in confirmation
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
        nodes = await app.gns3.get_nodes(app.current_project_id)
        links = await app.gns3.get_links(app.current_project_id)

        # PHASE 1: VALIDATE ALL operations (no state changes)
        validator = LinkValidator(nodes, links)

        # Resolve adapter names to numbers and validate
        resolved_ops = []
        for idx, op in enumerate(parsed_ops):
            if isinstance(op, ConnectOperation):
                # Resolve adapter_a
                adapter_a_num, port_a_num, port_a_name, error = validator.resolve_adapter_identifier(
                    op.node_a, op.adapter_a
                )
                if error:
                    return json.dumps(ErrorResponse(
                        error=f"Failed to resolve adapter for {op.node_a}",
                        details=error,
                        operation_index=idx
                    ).model_dump(), indent=2)

                # Resolve adapter_b
                adapter_b_num, port_b_num, port_b_name, error = validator.resolve_adapter_identifier(
                    op.node_b, op.adapter_b
                )
                if error:
                    return json.dumps(ErrorResponse(
                        error=f"Failed to resolve adapter for {op.node_b}",
                        details=error,
                        operation_index=idx
                    ).model_dump(), indent=2)

                # Store resolved values
                resolved_ops.append({
                    'op': op,
                    'adapter_a_num': adapter_a_num,
                    'port_a_num': port_a_num,
                    'port_a_name': port_a_name,
                    'adapter_b_num': adapter_b_num,
                    'port_b_num': port_b_num,
                    'port_b_name': port_b_name
                })

                # Validate with resolved numbers
                validation_error = validator.validate_connect(
                    op.node_a, op.node_b,
                    op.port_a, op.port_b,
                    adapter_a_num, adapter_b_num
                )
            else:  # DisconnectOperation
                resolved_ops.append({'op': op})
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

        for idx, resolved in enumerate(resolved_ops):
            op = resolved['op']
            try:
                if isinstance(op, ConnectOperation):
                    # Build link spec with resolved adapter numbers
                    node_a = node_map[op.node_a]
                    node_b = node_map[op.node_b]

                    link_spec = {
                        "nodes": [
                            {
                                "node_id": node_a["node_id"],
                                "adapter_number": resolved['adapter_a_num'],
                                "port_number": op.port_a
                            },
                            {
                                "node_id": node_b["node_id"],
                                "adapter_number": resolved['adapter_b_num'],
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
                        adapter_a=resolved['adapter_a_num'],
                        adapter_b=resolved['adapter_b_num'],
                        port_a_name=resolved['port_a_name'],
                        port_b_name=resolved['port_b_name']
                    ))

                    logger.info(f"Connected {op.node_a} {resolved['port_a_name']} (adapter {resolved['adapter_a_num']}) <-> "
                              f"{op.node_b} {resolved['port_b_name']} (adapter {resolved['adapter_b_num']})")

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

        # Build result
        result = OperationResult(completed=completed, failed=failed)
        return json.dumps(result.model_dump(), indent=2)

    except Exception as e:
        return json.dumps(ErrorResponse(
            error="Failed to manage connections",
            details=str(e)
        ).model_dump(), indent=2)


@mcp.tool()
async def delete_node(ctx: Context, node_name: str) -> str:
    """Delete a node from the current project

    Args:
        node_name: Name of the node to delete

    Returns:
        JSON confirmation message
    """
    app: AppContext = ctx.request_context.lifespan_context

    error = await validate_current_project(app)
    if error:
        return error

    try:
        nodes = await app.gns3.get_nodes(app.current_project_id)
        node = next((n for n in nodes if n['name'] == node_name), None)

        if not node:
            return json.dumps(ErrorResponse(
                error="Node not found",
                details=f"Node '{node_name}' does not exist"
            ).model_dump(), indent=2)

        await app.gns3.delete_node(app.current_project_id, node['node_id'])

        return json.dumps({"message": f"Node '{node_name}' deleted successfully"}, indent=2)

    except Exception as e:
        return json.dumps(ErrorResponse(
            error="Failed to delete node",
            details=str(e)
        ).model_dump(), indent=2)


@mcp.tool()
async def list_templates(ctx: Context) -> str:
    """List all available GNS3 templates

    Returns:
        JSON array of TemplateInfo objects
    """
    app: AppContext = ctx.request_context.lifespan_context

    try:
        templates = await app.gns3.get_templates()

        template_models = [
            TemplateInfo(
                template_id=t['template_id'],
                name=t['name'],
                category=t.get('category', 'default'),
                node_type=t.get('template_type'),
                compute_id=t.get('compute_id') or 'local',
                builtin=t.get('builtin', False),
                symbol=t.get('symbol')
            )
            for t in templates
        ]

        return json.dumps([t.model_dump() for t in template_models], indent=2)

    except Exception as e:
        return json.dumps(ErrorResponse(
            error="Failed to list templates",
            details=str(e)
        ).model_dump(), indent=2)


@mcp.tool()
async def create_node(ctx: Context, template_name: str, x: int, y: int,
                     node_name: Optional[str] = None, compute_id: str = "local") -> str:
    """Create a new node from a template

    Args:
        template_name: Name of the template to use
        x: X coordinate position (top-left corner of node icon)
        y: Y coordinate position (top-left corner of node icon)
        node_name: Optional custom name for the node
        compute_id: Compute ID (default: "local")

    Note: Coordinates represent the top-left corner of the node icon.
    Icon sizes are PNG: 78×78, SVG/internal: 58×58.

    Returns:
        JSON with created NodeInfo
    """
    app: AppContext = ctx.request_context.lifespan_context

    error = await validate_current_project(app)
    if error:
        return error

    try:
        templates = await app.gns3.get_templates()
        template = next((t for t in templates if t['name'] == template_name), None)

        if not template:
            return json.dumps(ErrorResponse(
                error="Template not found",
                details=f"Template '{template_name}' not found. Use list_templates() to see available templates."
            ).model_dump(), indent=2)

        payload = {"x": x, "y": y, "compute_id": compute_id}
        if node_name:
            payload["name"] = node_name

        result = await app.gns3.create_node_from_template(
            app.current_project_id, template['template_id'], payload
        )

        return json.dumps({"message": "Node created successfully", "node": result}, indent=2)

    except Exception as e:
        return json.dumps(ErrorResponse(
            error="Failed to create node",
            details=str(e)
        ).model_dump(), indent=2)


@mcp.tool()
async def list_drawings(ctx: Context) -> str:
    """List all drawing objects in the current project

    Returns:
        JSON array of DrawingInfo objects
    """
    app: AppContext = ctx.request_context.lifespan_context

    error = await validate_current_project(app)
    if error:
        return error

    try:
        drawings = await app.gns3.get_drawings(app.current_project_id)

        drawing_models = [
            DrawingInfo(
                drawing_id=d['drawing_id'],
                project_id=d['project_id'],
                x=d['x'],
                y=d['y'],
                z=d.get('z', 0),
                rotation=d.get('rotation', 0),
                svg=d['svg'],
                locked=d.get('locked', False)
            )
            for d in drawings
        ]

        return json.dumps([d.model_dump() for d in drawing_models], indent=2)

    except Exception as e:
        return json.dumps(ErrorResponse(
            error="Failed to list drawings",
            details=str(e)
        ).model_dump(), indent=2)


@mcp.tool()
async def create_drawing(ctx: Context,
                        drawing_type: str,
                        x: int,
                        y: int,
                        z: int = 0,
                        # Rectangle/Ellipse parameters
                        width: Optional[int] = None,
                        height: Optional[int] = None,
                        rx: Optional[int] = None,
                        ry: Optional[int] = None,
                        fill_color: str = "#ffffff",
                        border_color: str = "#000000",
                        border_width: int = 2,
                        # Line parameters
                        x2: Optional[int] = None,
                        y2: Optional[int] = None,
                        # Text parameters
                        text: Optional[str] = None,
                        font_size: int = 10,
                        font_weight: str = "normal",
                        font_family: str = "TypeWriter",
                        color: str = "#000000") -> str:
    """Create a drawing object (rectangle, ellipse, line, or text)

    Args:
        drawing_type: Type of drawing - "rectangle", "ellipse", "line", or "text"
        x: X coordinate (start point for line, top-left for others)
        y: Y coordinate (start point for line, top-left for others)
        z: Z-order/layer (default: 0 for shapes, 1 for text)

        Rectangle parameters (drawing_type="rectangle"):
            width: Rectangle width (required)
            height: Rectangle height (required)
            fill_color: Fill color (hex or name, default: white)
            border_color: Border color (default: black)
            border_width: Border width in pixels (default: 2)

        Ellipse parameters (drawing_type="ellipse"):
            rx: Horizontal radius (required)
            ry: Vertical radius (required, use same as rx for circle)
            fill_color: Fill color (hex or name, default: white)
            border_color: Border color (default: black)
            border_width: Border width in pixels (default: 2)
            Note: Ellipse center will be at (x + rx, y + ry)

        Line parameters (drawing_type="line"):
            x2: X offset from start point (required, can be negative)
            y2: Y offset from start point (required, can be negative)
            color: Line color (hex or name, default: black)
            border_width: Line width in pixels (default: 2)
            Note: Line goes from (x, y) to (x+x2, y+y2)

        Text parameters (drawing_type="text"):
            text: Text content (required)
            font_size: Font size in points (default: 10)
            font_weight: Font weight - "normal" or "bold" (default: normal)
            font_family: Font family (default: "TypeWriter")
            color: Text color (hex or name, default: black)

    Returns:
        JSON with created drawing info

    Examples:
        # Create rectangle
        create_drawing("rectangle", x=100, y=100, width=200, height=150,
                      fill_color="#ff0000", z=0)

        # Create circle
        create_drawing("ellipse", x=100, y=100, rx=50, ry=50,
                      fill_color="#00ff00", z=0)

        # Create line from (100,100) to (300,200)
        create_drawing("line", x=100, y=100, x2=200, y2=100,
                      color="#0000ff", border_width=3, z=0)

        # Create text label
        create_drawing("text", x=100, y=100, text="Router1",
                      font_size=12, font_weight="bold", z=1)
    """
    app: AppContext = ctx.request_context.lifespan_context

    error = await validate_current_project(app)
    if error:
        return error

    try:
        drawing_type = drawing_type.lower()

        # Generate appropriate SVG based on type
        if drawing_type == "rectangle":
            if width is None or height is None:
                return json.dumps(ErrorResponse(
                    error="Missing required parameters",
                    details="Rectangle requires 'width' and 'height' parameters"
                ).model_dump(), indent=2)

            svg = create_rectangle_svg(width, height, fill_color, border_color, border_width)
            message = "Rectangle created successfully"

        elif drawing_type == "ellipse":
            if rx is None or ry is None:
                return json.dumps(ErrorResponse(
                    error="Missing required parameters",
                    details="Ellipse requires 'rx' and 'ry' parameters"
                ).model_dump(), indent=2)

            svg = create_ellipse_svg(rx, ry, fill_color, border_color, border_width)
            message = "Ellipse created successfully"

        elif drawing_type == "line":
            if x2 is None or y2 is None:
                return json.dumps(ErrorResponse(
                    error="Missing required parameters",
                    details="Line requires 'x2' and 'y2' parameters (offset from start point)"
                ).model_dump(), indent=2)

            svg = create_line_svg(x2, y2, color, border_width)
            message = "Line created successfully"

        elif drawing_type == "text":
            if text is None:
                return json.dumps(ErrorResponse(
                    error="Missing required parameters",
                    details="Text drawing requires 'text' parameter"
                ).model_dump(), indent=2)

            svg = create_text_svg(text, font_size, font_weight, font_family, color)
            message = "Text created successfully"

        else:
            return json.dumps(ErrorResponse(
                error="Invalid drawing type",
                details=f"drawing_type must be 'rectangle', 'ellipse', 'line', or 'text', got '{drawing_type}'"
            ).model_dump(), indent=2)

        # Create drawing in GNS3
        drawing_data = {
            "x": x,
            "y": y,
            "z": z,
            "svg": svg,
            "rotation": 0
        }

        result = await app.gns3.create_drawing(app.current_project_id, drawing_data)

        return json.dumps({"message": message, "drawing": result}, indent=2)

    except Exception as e:
        return json.dumps(ErrorResponse(
            error="Failed to create drawing",
            details=str(e)
        ).model_dump(), indent=2)


@mcp.tool()
async def delete_drawing(ctx: Context, drawing_id: str) -> str:
    """Delete a drawing object from the current project

    Args:
        drawing_id: ID of the drawing to delete

    Returns:
        JSON confirmation message
    """
    app: AppContext = ctx.request_context.lifespan_context

    error = await validate_current_project(app)
    if error:
        return error

    try:
        await app.gns3.delete_drawing(app.current_project_id, drawing_id)
        return json.dumps({"message": f"Drawing {drawing_id} deleted successfully"}, indent=2)

    except Exception as e:
        return json.dumps(ErrorResponse(
            error="Failed to delete drawing",
            details=str(e)
        ).model_dump(), indent=2)


# export_topology_diagram tool now registered from export_tools module
# Register the imported tool with MCP
mcp.tool()(export_topology_diagram)


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
