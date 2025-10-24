"""GNS3 MCP Server v0.6.2

Model Context Protocol server for GNS3 lab automation.
Provides tools for managing projects, nodes, links, console access, and drawings.

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
from cache import DataCache
from link_validator import LinkValidator
from models import (
    ProjectInfo, NodeInfo, LinkInfo, LinkEndpoint,
    ConnectOperation, DisconnectOperation,
    CompletedOperation, FailedOperation, OperationResult,
    ConsoleStatus, ErrorResponse,
    TemplateInfo, DrawingInfo,
    validate_connection_operations
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S %d.%m.%Y'
)
logger = logging.getLogger(__name__)


# Device Pattern Library for Console State Detection
# Used by detect_console_state() and execute_console_sequence()
DEVICE_PATTERNS = {
    "cisco_ios": {
        "login": r"[Uu]sername:",
        "password": r"[Pp]assword:",
        "user_mode": r"[\w\-]+>",
        "privileged": r"[\w\-]+#",
        "config": r"\(config[^\)]*\)#",
        "errors": [r"% Invalid", r"% Unknown", r"% Incomplete"]
    },
    "mikrotik": {
        "login": r"Login:",
        "password": r"Password:",
        "new_password": r"[Nn]ew [Pp]assword\s*>",
        "repeat_password": r"[Rr]epeat.*[Pp]assword\s*>",
        "prompt": r"\[[\w\-]+@[\w\-]+\]\s*[>]",
        "errors": [r"failure", r"bad command", r"expected"]
    },
    "juniper": {
        "login": r"login:",
        "password": r"[Pp]assword:",
        "user_mode": r"[\w\-]+>",
        "privileged": r"[\w\-]+#",
        "config": r"\[edit[^\]]*\]",
        "errors": [r"error:", r"syntax error", r"unknown command"]
    },
    "arista": {
        "login": r"[Ll]ogin:",
        "password": r"[Pp]assword:",
        "user_mode": r"[\w\-]+>",
        "privileged": r"[\w\-]+#",
        "config": r"\(config[^\)]*\)#",
        "errors": [r"% Invalid", r"% Incomplete"]
    },
    "linux": {
        "login": r"login:",
        "password": r"[Pp]assword:",
        "prompt": r"[$#]",
        "root_prompt": r"#",
        "errors": [r"command not found", r"permission denied", r"No such file"]
    }
}

# Common error patterns across all devices
COMMON_ERROR_PATTERNS = [
    r"% Invalid",
    r"% Unknown",
    r"% Incomplete",
    r"^Error:",
    r"[Ff]ailed",
    r"[Ff]ailure",
    r"syntax error",
    r"bad command"
]


# SVG Generation Helpers

def create_rectangle_svg(width: int, height: int, fill: str = "#ffffff",
                        border: str = "#000000", border_width: int = 2) -> str:
    """Generate SVG for a rectangle"""
    return f'''<svg height="{height}" width="{width}">
  <rect fill="{fill}" fill-opacity="1.0" height="{height}" width="{width}"
        stroke="{border}" stroke-width="{border_width}" />
</svg>'''


def create_text_svg(text: str, font_size: int = 10, font_weight: str = "normal",
                   font_family: str = "TypeWriter", color: str = "#000000") -> str:
    """Generate SVG for text"""
    # Escape XML special characters
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    return f'''<svg height="{font_size + 2}" width="{len(text) * font_size}">
  <text fill="{color}" fill-opacity="1.0" font-family="{font_family}"
        font-size="{font_size}" font-weight="{font_weight}">
    {text}
  </text>
</svg>'''


def create_ellipse_svg(rx: int, ry: int, fill: str = "#ffffff",
                      border: str = "#000000", border_width: int = 2) -> str:
    """Generate SVG for an ellipse"""
    width = rx * 2
    height = ry * 2
    return f'''<svg height="{height}" width="{width}">
  <ellipse cx="{rx}" cy="{ry}" fill="{fill}" fill-opacity="1.0"
           rx="{rx}" ry="{ry}" stroke="{border}" stroke-width="{border_width}" />
</svg>'''


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
async def read_console(ctx: Context, node_name: str, diff: bool = False) -> str:
    """Read console output (auto-connects if needed)

    Reads accumulated output from background console buffer. Output accumulates
    while device runs - this function retrieves it without blocking.

    Buffer Behavior:
    - Background task continuously reads console into 10MB buffer
    - Full buffer (diff=False): Returns all console output since connection
    - Diff mode (diff=True): Returns only NEW output since last read
    - Read position advances with each diff=True read

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
        diff: If True, return only new output since last read (recommended for
              interactive sessions to avoid seeing old output)

    Returns:
        Console output (ANSI escape codes stripped, line endings normalized)
        or "No output available" if buffer empty

    Example - Check for specific prompt:
        output = read_console("R1", diff=True)
        if "Login:" in output:
            send_console("R1", "admin\\n")
        elif "Router>" in output:
            send_console("R1", "enable\\n")
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

    Workflow:
    1. Send command to console
    2. If wait_pattern provided: poll console until pattern appears or timeout
    3. Return all output accumulated during wait

    Args:
        node_name: Name of the node
        command: Command to send (include \n for newline)
        wait_pattern: Optional regex pattern to wait for (e.g., "Router[>#]", "Login:")
                      If None, waits 2 seconds and returns output
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

    Example - Wait for login prompt:
        result = send_and_wait_console(
            "R1",
            "\n",
            wait_pattern="Login:",
            timeout=10
        )
        # Returns when "Login:" appears or after 10 seconds

    Example - Send command and wait for prompt:
        result = send_and_wait_console(
            "R1",
            "show ip interface brief\n",
            wait_pattern="Router#",
            timeout=10
        )
        # Returns when "Router#" appears (command finished)

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
async def detect_console_state(ctx: Context, node_name: str) -> str:
    """Analyze console output to determine current device state

    Inspects recent console output to identify device state using pattern library
    for common devices (Cisco, MikroTik, Juniper, Arista, Linux). Auto-detects
    device type with fallback to generic patterns.

    Detected States:
    - "login_prompt": Device asking for username (patterns: "Login:", "login:")
    - "password_prompt": Device asking for password (patterns: "Password:", "password:")
    - "new_password_prompt": MikroTik asking to set new password
    - "repeat_password_prompt": MikroTik asking to repeat new password
    - "command_prompt_user": User mode CLI (patterns: ">", "$")
    - "command_prompt_privileged": Privileged mode CLI (patterns: "#")
    - "config_mode": Configuration mode (patterns: "(config)", "[edit]")
    - "booting": Device still booting (patterns: "Loading", "Booting")
    - "unknown": Cannot determine state

    Args:
        node_name: Name of the node

    Returns:
        JSON with:
        {
            "state": "command_prompt_privileged",
            "prompt_text": "Router#",
            "ready_for_commands": true,
            "detected_device": "cisco_ios",  # or null if generic
            "last_lines": "show ip int brief\\n...\\nRouter#",
            "confidence": "high"  # high/medium/low
        }

    Example Workflow:
        # Wake console
        send_console("R1", "\\n")
        await 2 seconds

        # Check state
        state = detect_console_state("R1")

        if state["state"] == "login_prompt":
            send_console("R1", "admin\\n")
        elif state["state"] == "password_prompt":
            send_console("R1", "\\n")  # Empty password
        elif state["ready_for_commands"]:
            send_console("R1", "show version\\n")
    """
    app: AppContext = ctx.request_context.lifespan_context

    # Auto-connect
    error = await _auto_connect_console(app, node_name)
    if error:
        return json.dumps({
            "state": "unknown",
            "error": error,
            "ready_for_commands": False
        }, indent=2)

    # Get recent output (last 1000 chars)
    full_output = app.console.get_output_by_node(node_name) or ""
    recent_output = full_output[-1000:] if len(full_output) > 1000 else full_output

    # Extract last few lines for analysis and debugging
    lines = recent_output.split('\n')
    last_lines = '\n'.join(lines[-5:]) if len(lines) >= 5 else recent_output

    # Get the last non-empty line (current prompt)
    current_line = ""
    for line in reversed(lines):
        if line.strip():
            current_line = line
            break

    # Pattern matching for state detection
    import re

    state = "unknown"
    prompt_text = ""
    confidence = "low"
    ready = False
    detected_device = None

    # Try device-specific patterns first (higher confidence)
    for device_name, patterns in DEVICE_PATTERNS.items():
        # Check for device-specific prompts on current line
        if device_name == "mikrotik":
            if re.search(patterns.get("new_password", ""), current_line, re.IGNORECASE):
                state = "new_password_prompt"
                prompt_text = "new password>"
                confidence = "high"
                ready = False
                detected_device = device_name
                break
            elif re.search(patterns.get("repeat_password", ""), current_line, re.IGNORECASE):
                state = "repeat_password_prompt"
                prompt_text = "repeat new password>"
                confidence = "high"
                ready = False
                detected_device = device_name
                break
            elif re.search(patterns.get("prompt", ""), current_line):
                state = "command_prompt_privileged"
                match = re.search(patterns.get("prompt", ""), current_line)
                prompt_text = match.group(0) if match else ""
                confidence = "high"
                ready = True
                detected_device = device_name
                break

    # Generic pattern matching (if no device-specific match)
    if state == "unknown":
        # Login prompt (high confidence)
        if re.search(r'[Ll]ogin\s*:', current_line):
            state = "login_prompt"
            match = re.search(r'[Ll]ogin\s*:', current_line)
            prompt_text = match.group(0) if match else "Login:"
            confidence = "high"
            ready = False

        # Password prompt (high confidence)
        elif re.search(r'[Pp]assword\s*[>:]', current_line):
            state = "password_prompt"
            match = re.search(r'[Pp]assword\s*[>:]', current_line)
            prompt_text = match.group(0) if match else "Password:"
            confidence = "high"
            ready = False

        # Privileged mode (high confidence)
        elif re.search(r'[\w\-]+#\s*$', current_line):
            state = "command_prompt_privileged"
            match = re.search(r'[\w\-]+#\s*$', last_lines)
            prompt_text = match.group(0).strip() if match else ""
            confidence = "high"
            ready = True

        # Config mode (high confidence)
        elif re.search(r'\(config[^\)]*\)[#>]', last_lines) or re.search(r'\[edit[^\]]*\]', last_lines):
            state = "config_mode"
            match = re.search(r'(\(config[^\)]*\)[#>]|\[edit[^\]]*\])', last_lines)
            prompt_text = match.group(0) if match else ""
            confidence = "high"
            ready = True

        # User mode (medium confidence)
        elif re.search(r'[\w\-]+>\s*$', last_lines):
            state = "command_prompt_user"
            match = re.search(r'[\w\-]+>\s*$', last_lines)
            prompt_text = match.group(0).strip() if match else ""
            confidence = "medium"
            ready = True

        # Booting indicators (medium confidence)
        elif re.search(r'(Loading|Booting|Initializing|Starting)', last_lines, re.IGNORECASE):
            state = "booting"
            confidence = "medium"
            ready = False

    return json.dumps({
        "state": state,
        "prompt_text": prompt_text,
        "ready_for_commands": ready,
        "detected_device": detected_device,
        "last_lines": last_lines,
        "confidence": confidence
    }, indent=2)


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
        await app.cache.invalidate_nodes(app.current_project_id)
        await app.cache.invalidate_links(app.current_project_id)

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

        await app.cache.invalidate_nodes(app.current_project_id)

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
async def create_rectangle(ctx: Context, x: int, y: int, width: int, height: int,
                          fill_color: str = "#ffffff", border_color: str = "#000000",
                          border_width: int = 2, z: int = 0) -> str:
    """Create a colored rectangle drawing

    Args:
        x: X coordinate (top-left corner)
        y: Y coordinate (top-left corner)
        width: Rectangle width
        height: Rectangle height
        fill_color: Fill color (hex or name, default: white)
        border_color: Border color (default: black)
        border_width: Border width in pixels (default: 2)
        z: Z-order/layer (default: 0 - behind nodes)

    Returns:
        JSON with created drawing info
    """
    app: AppContext = ctx.request_context.lifespan_context

    error = await validate_current_project(app)
    if error:
        return error

    try:
        svg = create_rectangle_svg(width, height, fill_color, border_color, border_width)

        drawing_data = {
            "x": x,
            "y": y,
            "z": z,
            "svg": svg,
            "rotation": 0
        }

        result = await app.gns3.create_drawing(app.current_project_id, drawing_data)

        return json.dumps({"message": "Rectangle created successfully", "drawing": result}, indent=2)

    except Exception as e:
        return json.dumps(ErrorResponse(
            error="Failed to create rectangle",
            details=str(e)
        ).model_dump(), indent=2)


@mcp.tool()
async def create_text(ctx: Context, text: str, x: int, y: int,
                     font_size: int = 10, font_weight: str = "normal",
                     font_family: str = "TypeWriter", color: str = "#000000",
                     z: int = 1) -> str:
    """Create a text label with formatting

    Args:
        text: Text content
        x: X coordinate (top-left corner of text)
        y: Y coordinate (top-left corner of text)
        font_size: Font size in points (default: 10)
        font_weight: Font weight - "normal" or "bold" (default: normal)
        font_family: Font family (default: "TypeWriter")
        color: Text color (hex or name, default: black)
        z: Z-order/layer (default: 1 - in front of shapes)

    Returns:
        JSON with created drawing info
    """
    app: AppContext = ctx.request_context.lifespan_context

    error = await validate_current_project(app)
    if error:
        return error

    try:
        svg = create_text_svg(text, font_size, font_weight, font_family, color)

        drawing_data = {
            "x": x,
            "y": y,
            "z": z,
            "svg": svg,
            "rotation": 0
        }

        result = await app.gns3.create_drawing(app.current_project_id, drawing_data)

        return json.dumps({"message": "Text created successfully", "drawing": result}, indent=2)

    except Exception as e:
        return json.dumps(ErrorResponse(
            error="Failed to create text",
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


@mcp.tool()
async def create_ellipse(ctx: Context, x: int, y: int, rx: int, ry: int,
                        fill_color: str = "#ffffff", border_color: str = "#000000",
                        border_width: int = 2, z: int = 0) -> str:
    """Create an ellipse/circle drawing

    Args:
        x: X coordinate (top-left corner of bounding box)
        y: Y coordinate (top-left corner of bounding box)
        rx: Horizontal radius
        ry: Vertical radius (use same as rx for a circle)
        fill_color: Fill color (hex or name, default: white)
        border_color: Border color (default: black)
        border_width: Border width in pixels (default: 2)
        z: Z-order/layer (default: 0 - behind nodes)

    Note: The ellipse center will be at (x + rx, y + ry). For a circle
    with radius 50 at position (100, 100), the center is at (150, 150).

    Returns:
        JSON with created drawing info
    """
    app: AppContext = ctx.request_context.lifespan_context

    error = await validate_current_project(app)
    if error:
        return error

    try:
        svg = create_ellipse_svg(rx, ry, fill_color, border_color, border_width)

        drawing_data = {
            "x": x,
            "y": y,
            "z": z,
            "svg": svg,
            "rotation": 0
        }

        result = await app.gns3.create_drawing(app.current_project_id, drawing_data)

        return json.dumps({"message": "Ellipse created successfully", "drawing": result}, indent=2)

    except Exception as e:
        return json.dumps(ErrorResponse(
            error="Failed to create ellipse",
            details=str(e)
        ).model_dump(), indent=2)


@mcp.tool()
async def export_topology_diagram(ctx: Context, output_path: str,
                                  format: str = "both",
                                  crop_x: Optional[int] = None,
                                  crop_y: Optional[int] = None,
                                  crop_width: Optional[int] = None,
                                  crop_height: Optional[int] = None) -> str:
    """Export topology as SVG and/or PNG diagram

    Creates a visual diagram of the current topology including nodes, links,
    and drawings with status indicators.

    GNS3 Coordinate System:
    - Node positions (x, y): Top-left corner of icon
    - Node icon sizes: PNG images = 78×78, SVG/internal icons = 58×58
    - Label positions: Stored as offsets from node center in GNS3
    - Link connections: Connect to node centers (x + icon_size/2, y + icon_size/2)
    - Drawing positions (x, y): Top-left corner

    Args:
        output_path: Base path for output files (without extension)
        format: Output format - "svg", "png", or "both" (default: "both")
        crop_x: Optional crop X coordinate (default: auto-fit to content)
        crop_y: Optional crop Y coordinate (default: auto-fit to content)
        crop_width: Optional crop width (default: auto-fit to content)
        crop_height: Optional crop height (default: auto-fit to content)

    Returns:
        JSON with created file paths and diagram info
    """
    app: AppContext = ctx.request_context.lifespan_context

    error = await validate_current_project(app)
    if error:
        return error

    try:
        # Get all topology data
        nodes = await app.cache.get_nodes(
            app.current_project_id,
            lambda pid: app.gns3.get_nodes(pid)
        )
        links = await app.cache.get_links(
            app.current_project_id,
            lambda pid: app.gns3.get_links(pid)
        )
        drawings = await app.gns3.get_drawings(app.current_project_id)

        # Calculate bounds
        if crop_x is None or crop_y is None or crop_width is None or crop_height is None:
            # Auto-calculate bounds
            min_x = min_y = float('inf')
            max_x = max_y = float('-inf')

            for node in nodes:
                x, y = node['x'], node['y']
                symbol = node.get('symbol', '')

                # Determine icon size: PNG = 78×78, SVG = 58×58
                if symbol and symbol.lower().endswith('.png'):
                    icon_size = 78
                else:
                    icon_size = 58

                # Get label position to account for it in bounds
                label_info = node.get('label', {})
                label_x = label_info.get('x', 0)
                label_y = label_info.get('y', icon_size // 2 + 20)

                # Account for node icon (top-left at x,y)
                min_x = min(min_x, x)
                max_x = max(max_x, x + icon_size)
                min_y = min(min_y, y)
                max_y = max(max_y, y + icon_size)

                # Account for label position (relative to node top-left)
                label_abs_x = x + label_x
                label_abs_y = y + label_y
                min_x = min(min_x, label_abs_x - 50)  # Approximate text width
                max_x = max(max_x, label_abs_x + 50)
                min_y = min(min_y, label_abs_y - 10)  # Approximate text height
                max_y = max(max_y, label_abs_y + 10)

            for drawing in drawings:
                # Parse SVG to get dimensions (basic parsing)
                svg = drawing['svg']
                if 'width=' in svg and 'height=' in svg:
                    import re
                    w_match = re.search(r'width="(\d+)"', svg)
                    h_match = re.search(r'height="(\d+)"', svg)
                    if w_match and h_match:
                        w, h = int(w_match.group(1)), int(h_match.group(1))
                        min_x = min(min_x, drawing['x'])
                        max_x = max(max_x, drawing['x'] + w)
                        min_y = min(min_y, drawing['y'])
                        max_y = max(max_y, drawing['y'] + h)

            # Add padding
            padding = 50
            crop_x = int(min_x - padding)
            crop_y = int(min_y - padding)
            crop_width = int(max_x - min_x + padding * 2)
            crop_height = int(max_y - min_y + padding * 2)

        # Generate SVG
        svg_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
     width="{crop_width}" height="{crop_height}"
     viewBox="{crop_x} {crop_y} {crop_width} {crop_height}">
  <defs>
    <style>
      .node {{ stroke: #333; stroke-width: 2; }}
      .node-stopped {{ fill: #ff9999; }}
      .node-started {{ fill: #99ff99; }}
      .node-suspended {{ fill: #ffff99; }}
      .node-label {{ dominant-baseline: text-before-edge; }}
      .link {{ stroke: #666; stroke-width: 2; fill: none; }}
    </style>
  </defs>

  <!-- Drawings (background) -->
'''

        # Add drawings sorted by z-order
        for drawing in sorted(drawings, key=lambda d: d.get('z', 0)):
            # Extract SVG content (remove outer svg tags)
            svg = drawing['svg']
            import re

            # Extract SVG dimensions
            width_match = re.search(r'width="(\d+)"', svg)
            height_match = re.search(r'height="(\d+)"', svg)
            svg_width = int(width_match.group(1)) if width_match else 100
            svg_height = int(height_match.group(1)) if height_match else 100

            svg_inner = re.sub(r'<svg[^>]*>', '', svg)
            svg_inner = re.sub(r'</svg>', '', svg_inner)

            # Fix text elements without positioning attributes
            # Add x, y, text-anchor, and dominant-baseline for proper centering
            # While preserving existing font attributes
            if '<text' in svg_inner and 'x="' not in svg_inner:
                # Extract existing font attributes
                font_family_match = re.search(r'font-family="([^"]*)"', svg_inner)
                font_size_match = re.search(r'font-size="([^"]*)"', svg_inner)
                font_weight_match = re.search(r'font-weight="([^"]*)"', svg_inner)
                fill_match = re.search(r'fill="([^"]*)"', svg_inner)

                # Build attributes string preserving existing font settings
                attrs = []
                if font_family_match:
                    attrs.append(f'font-family="{font_family_match.group(1)}"')
                if font_size_match:
                    attrs.append(f'font-size="{font_size_match.group(1)}"')
                if font_weight_match:
                    attrs.append(f'font-weight="{font_weight_match.group(1)}"')
                if fill_match:
                    attrs.append(f'fill="{fill_match.group(1)}"')

                # Add positioning for vertical centering and right alignment
                padding = 10
                attrs.append(f'x="{svg_width - padding}"')
                attrs.append(f'y="{svg_height // 2}"')
                attrs.append('text-anchor="end"')
                attrs.append('dominant-baseline="central"')

                # Replace text tag with preserved and new attributes
                svg_inner = re.sub(
                    r'<text[^>]*>',
                    f'<text {" ".join(attrs)}>',
                    svg_inner,
                    count=1
                )

            svg_content += f'''  <g transform="translate({drawing['x']}, {drawing['y']})">
    {svg_inner}
  </g>
'''

        # Pre-calculate icon sizes for all nodes
        # PNG images: 78×78, SVG/internal icons: 58×58
        node_icon_sizes = {}
        for node in nodes:
            symbol = node.get('symbol', '')
            if symbol and symbol.lower().endswith('.png'):
                node_icon_sizes[node['node_id']] = 78
            else:
                node_icon_sizes[node['node_id']] = 58

        # Add links
        svg_content += '\n  <!-- Links -->\n'
        node_map = {n['node_id']: n for n in nodes}

        for link in links:
            node_a_id = link['nodes'][0]['node_id']
            node_b_id = link['nodes'][1]['node_id']

            if node_a_id in node_map and node_b_id in node_map:
                node_a = node_map[node_a_id]
                node_b = node_map[node_b_id]

                # Links connect to center of nodes (offset from top-left by icon_size/2)
                icon_size_a = node_icon_sizes.get(node_a_id, 58)
                icon_size_b = node_icon_sizes.get(node_b_id, 58)

                x1 = node_a['x'] + icon_size_a // 2
                y1 = node_a['y'] + icon_size_a // 2
                x2 = node_b['x'] + icon_size_b // 2
                y2 = node_b['y'] + icon_size_b // 2

                svg_content += f'  <line class="link" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}"/>\n'

        # Add port status indicators
        svg_content += '\n  <!-- Port Status Indicators -->\n'
        import math

        for link in links:
            node_a_id = link['nodes'][0]['node_id']
            node_b_id = link['nodes'][1]['node_id']
            link_suspended = link.get('suspend', False)

            if node_a_id in node_map and node_b_id in node_map:
                node_a = node_map[node_a_id]
                node_b = node_map[node_b_id]

                # Get node statuses
                status_a = node_a['status']
                status_b = node_b['status']

                # Calculate indicator colors
                # Green if node started and link not suspended, else red
                color_a = "#00cc00" if (status_a == "started" and not link_suspended) else "#cc0000"
                color_b = "#00cc00" if (status_b == "started" and not link_suspended) else "#cc0000"

                # Get icon sizes
                icon_size_a = node_icon_sizes.get(node_a_id, 58)
                icon_size_b = node_icon_sizes.get(node_b_id, 58)

                # Node centers
                cx_a = node_a['x'] + icon_size_a // 2
                cy_a = node_a['y'] + icon_size_a // 2
                cx_b = node_b['x'] + icon_size_b // 2
                cy_b = node_b['y'] + icon_size_b // 2

                # Calculate indicator positions on link line
                # Distance from center: icon_size/2 + 15px
                dx = cx_b - cx_a
                dy = cy_b - cy_a
                length = math.sqrt(dx*dx + dy*dy)

                if length > 0:
                    unit_x = dx / length
                    unit_y = dy / length

                    # Indicator for node A side
                    offset_a = icon_size_a // 2 + 15
                    ind_ax = cx_a + unit_x * offset_a
                    ind_ay = cy_a + unit_y * offset_a

                    # Indicator for node B side
                    offset_b = icon_size_b // 2 + 15
                    ind_bx = cx_b - unit_x * offset_b  # Negative because going from B toward A
                    ind_by = cy_b - unit_y * offset_b

                    # Render indicators (4px radius, no border)
                    svg_content += f'  <circle cx="{ind_ax}" cy="{ind_ay}" r="4" fill="{color_a}"/>\n'
                    svg_content += f'  <circle cx="{ind_bx}" cy="{ind_by}" r="4" fill="{color_b}"/>\n'

        # Add nodes with actual icons
        svg_content += '\n  <!-- Nodes -->\n'
        import base64

        for node in nodes:
            x, y = node['x'], node['y']
            status = node['status']
            name = node['name']
            symbol = node.get('symbol', '')

            # Determine icon size based on symbol type
            # PNG images: 78×78, SVG/internal icons: 58×58
            if symbol and symbol.lower().endswith('.png'):
                icon_size = 78
            else:
                icon_size = 58

            # Fetch actual icon if available
            icon_data = None
            if symbol:
                try:
                    # Get raw symbol data from GNS3
                    raw_bytes = await app.gns3.get_symbol_raw(symbol)

                    # Determine MIME type
                    if symbol.lower().endswith('.png'):
                        mime_type = 'image/png'
                    elif symbol.lower().endswith('.svg'):
                        mime_type = 'image/svg+xml'
                    elif symbol.lower().endswith('.jpg') or symbol.lower().endswith('.jpeg'):
                        mime_type = 'image/jpeg'
                    else:
                        mime_type = 'image/png'  # Default

                    # Encode as base64 data URI
                    b64_data = base64.b64encode(raw_bytes).decode('utf-8')
                    icon_data = f"data:{mime_type};base64,{b64_data}"

                except Exception as e:
                    logger.warning(f"Failed to fetch icon for {symbol}: {e}")
                    icon_data = None

            # Try category-based fallback if primary icon failed
            if not icon_data:
                # Map node_type to category fallback icons
                node_type = node.get('node_type', '')
                fallback_symbol = None

                if node_type == 'qemu':
                    # Most QEMU nodes are routers
                    fallback_symbol = ':/symbols/affinity/circle/blue/router.svg'
                elif node_type in ['ethernet_switch', 'ethernet_hub', 'atm_switch', 'frame_relay_switch']:
                    fallback_symbol = ':/symbols/affinity/square/blue/switch_multilayer.svg'
                elif node_type in ['nat', 'vpcs', 'cloud', 'docker']:
                    fallback_symbol = ':/symbols/classic/computer.svg'
                else:
                    fallback_symbol = ':/symbols/affinity/circle/blue/router.svg'  # Default

                # Try to fetch category fallback icon
                if fallback_symbol:
                    try:
                        raw_bytes = await app.gns3.get_symbol_raw(fallback_symbol)
                        b64_data = base64.b64encode(raw_bytes).decode('utf-8')
                        icon_data = f"data:image/svg+xml;base64,{b64_data}"
                    except Exception as e:
                        logger.warning(f"Failed to fetch fallback icon {fallback_symbol}: {e}")
                        icon_data = None

            # Extract label information from GNS3 data
            # GNS3 stores label offset from node top-left to label box top-left
            label_info = node.get('label', {})
            label_text = label_info.get('text', name)
            label_x_offset = label_info.get('x', 0)
            label_y_offset = label_info.get('y', icon_size//2 + 20)
            label_rotation = label_info.get('rotation', 0)
            label_style = label_info.get('style', '')

            # Extract font size from style, default to 10
            import re
            font_size = 10.0
            if label_style:
                font_match = re.search(r'font-size:\s*(\d+\.?\d*)', label_style)
                if font_match:
                    font_size = float(font_match.group(1))

            # GNS3 Label Positioning:
            # - When x is None, GNS3 auto-centers the label above the node
            # - When x/y are set, they represent the label position directly (not bounding box)
            # - Official GNS3 uses text position, not bounding box corner
            if label_x_offset is None:
                # Auto-center label above node (mimic official GNS3 behavior)
                estimated_width = len(label_text) * font_size * 0.6
                label_x = icon_size / 2  # Center of node
                label_y = -25  # Standard position above node
                text_anchor = "middle"
            else:
                # Use GNS3-stored position directly (no offset additions)
                label_x = label_x_offset
                label_y = label_y_offset
                # Determine text anchor based on position relative to node center
                if abs(label_x_offset - icon_size / 2) < 5:
                    text_anchor = "middle"  # Centered
                elif label_x_offset > icon_size / 2:
                    text_anchor = "end"  # Right of center
                else:
                    text_anchor = "start"  # Left of center

            # Parse style string into SVG attributes
            style_attrs = ''
            if label_style:
                style_attrs = f' style="{label_style}"'

            # Build label transform (rotation around label origin)
            label_transform = ''
            if label_rotation != 0:
                label_transform = f' transform="rotate({label_rotation} {label_x} {label_y})"'

            # Render node with icon or final fallback
            # Note: GNS3 coordinates are top-left corner of icon
            if icon_data:
                # Use actual or fallback icon
                svg_content += f'''  <g transform="translate({x}, {y})">
    <image href="{icon_data}" x="0" y="0" width="{icon_size}" height="{icon_size}"/>
    <text class="node-label" x="{label_x}" y="{label_y}" text-anchor="{text_anchor}"{label_transform}{style_attrs}>{label_text}</text>
  </g>
'''
            else:
                # Final fallback: colored rectangle with status
                status_class = f"node-{status}"
                svg_content += f'''  <g transform="translate({x}, {y})">
    <rect class="node {status_class}" x="0" y="0" width="80" height="80" rx="5"/>
    <text class="node-label" x="{label_x}" y="{label_y}" text-anchor="{text_anchor}"{label_transform}{style_attrs}>{label_text}</text>
  </g>
'''

        svg_content += '</svg>\n'

        # Save SVG
        files_created = []
        if format in ["svg", "both"]:
            svg_path = f"{output_path}.svg"
            with open(svg_path, 'w', encoding='utf-8') as f:
                f.write(svg_content)
            files_created.append(svg_path)

        # Save PNG (if requested and cairosvg available)
        if format in ["png", "both"]:
            try:
                import cairosvg
                png_path = f"{output_path}.png"
                cairosvg.svg2png(bytestring=svg_content.encode('utf-8'),
                               write_to=png_path)
                files_created.append(png_path)
            except ImportError:
                return json.dumps({
                    "warning": "PNG export requires cairosvg library",
                    "files_created": files_created,
                    "bounds": {"x": crop_x, "y": crop_y, "width": crop_width, "height": crop_height},
                    "note": "Install with: pip install cairosvg"
                }, indent=2)

        return json.dumps({
            "message": "Topology diagram exported successfully",
            "files_created": files_created,
            "bounds": {"x": crop_x, "y": crop_y, "width": crop_width, "height": crop_height},
            "nodes_count": len(nodes),
            "links_count": len(links),
            "drawings_count": len(drawings)
        }, indent=2)

    except Exception as e:
        return json.dumps(ErrorResponse(
            error="Failed to export topology diagram",
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
