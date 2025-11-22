"""GNS3 MCP server

GNS3 lab automation with AI agent
"""

# Add lib directory to Python path for bundled dependencies (.mcpb package)
# ruff: noqa: E402 - Module imports must come after sys.path setup
import sys
from pathlib import Path

# Get the directory containing this script (server/)
server_dir = Path(__file__).parent.resolve()
# Get the parent directory (mcp-server/)
root_dir = server_dir.parent
# Add lib/ and server/ to path
lib_dir = root_dir / "lib"
if lib_dir.exists():
    sys.path.insert(0, str(lib_dir))
sys.path.insert(0, str(server_dir))

import argparse
import json
import logging
import os
from pathlib import Path
from typing import Annotated, Any, Dict, List, Literal

from app import AppContext, app_lifespan
from context import get_app, validate_current_project
from export_tools import (
    export_topology_diagram,
)
from fastapi import Request
from fastapi.responses import JSONResponse
from fastmcp import Context, FastMCP
from models import (
    ErrorResponse,
)
from prompts import (
    render_lab_setup_prompt,
    render_node_setup_prompt,
    render_ssh_setup_prompt,
    render_topology_discovery_prompt,
    render_troubleshooting_prompt,
)
from tools.console_tools import (
    console_batch_impl,
)
from tools.drawing_tools import (
    create_drawing_impl,
    create_drawings_batch_impl,
    delete_drawing_impl,
    update_drawing_impl,
)
from tools.link_tools import set_connection_impl
from tools.node_tools import (
    configure_node_network_impl,
    create_node_impl,
    delete_node_impl,
    get_node_file_impl,
    set_node_impl,
    write_node_file_impl,
)
from tools.project_tools import (
    close_project_impl,
    create_project_impl,
    open_project_impl,
)
from tools.resource_tools import (
    list_nodes as list_nodes_impl,
)
from tools.resource_tools import (
    list_projects as list_projects_impl,
)
from tools.resource_tools import (
    query_resource as query_resource_impl,
)

# Read version from package __init__.py (single source of truth for PyPI package)
try:
    from gns3_mcp import __version__

    VERSION = __version__
except ImportError:
    # Fallback version if import fails (e.g., running directly without package installation)
    VERSION = f"{0}.{42}.{0}"
    print("Warning: Could not import version from gns3_mcp package, using fallback")

# Read server instructions for AI guidance (v0.39.0)
INSTRUCTIONS_PATH = Path(__file__).parent / "instructions.md"
try:
    SERVER_INSTRUCTIONS = (
        INSTRUCTIONS_PATH.read_text(encoding="utf-8") if INSTRUCTIONS_PATH.exists() else None
    )
except Exception as e:
    SERVER_INSTRUCTIONS = None
    print(f"Warning: Could not read instructions.md: {e}")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S %d.%m.%Y",
)
logger = logging.getLogger(__name__)

# Note: SVG generation helpers moved to export_tools.py for better modularity
# Note: AppContext and lifecycle management moved to app.py (v0.49.0 - GM-45)
# Note: Global context helpers moved to context.py (v0.49.0 - GM-45)


# Create MCP server (v0.39.0: Added instructions for AI guidance)
mcp = FastMCP("GNS3 Lab Controller", lifespan=app_lifespan, instructions=SERVER_INSTRUCTIONS)


# ============================================================================
# MCP Resources - Browsable State
# ============================================================================


# Project resources
@mcp.resource(
    "projects://",
    name="Projects",
    title="GNS3 projects list",
    description="List all GNS3 projects with their statuses and IDs",
    mime_type="text/plain",
)
async def resource_projects() -> str:
    """List all GNS3 projects with their statuses and IDs"""
    return await get_app().resource_manager.list_projects()


@mcp.resource(
    "projects://{project_id}",
    name="Project details",  # human-readable name
    title="GNS3 project details",  # human-readable name
    description="Details for a specific GNS3 project",  # defaults to docsctring
    mime_type="text/plain",
)
async def resource_project(ctx: Context, project_id: str) -> str:
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.get_project(project_id)


@mcp.resource(
    "nodes://{project_id}/",
    name="Project nodes list",
    title="GNS3 project nodes list",
    description="List all nodes (devices) in a specific GNS3 project with status and basic info",
    mime_type="text/plain",
)
async def resource_nodes(ctx: Context, project_id: str) -> str:
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.list_nodes(project_id)


@mcp.resource(
    "nodes://{project_id}/{node_id}",
    name="Node details",
    title="GNS3 node details",
    description="Detailed information about a specific node including status, coordinates, console settings, and properties",
    mime_type="application/json",
)
async def resource_node(ctx: Context, project_id: str, node_id: str) -> str:
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.get_node(project_id, node_id)


@mcp.resource(
    "links://{project_id}/",
    name="Project links",
    title="GNS3 project network links",
    description="List all network links (connections) between nodes in a specific project",
    mime_type="text/plain",
)
async def resource_links(ctx: Context, project_id: str) -> str:
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.list_links(project_id)


@mcp.resource(
    "templates://",
    name="Templates",
    title="GNS3 templates list",
    description="List all available GNS3 device templates (routers, switches, Docker containers, VMs)",
    mime_type="text/plain",
)
async def resource_templates() -> str:
    """List all available GNS3 templates"""
    return await get_app().resource_manager.list_templates()


@mcp.resource(
    "drawings://{project_id}/",
    name="Project drawings",
    title="GNS3 project drawing objects",
    description="List all drawing objects (rectangles, ellipses, lines, text labels) in a specific project",
    mime_type="text/plain",
)
async def resource_drawings(ctx: Context, project_id: str) -> str:
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.list_drawings(project_id)


# REMOVED v0.29.0 - Snapshot resources removed (planned for future reimplementation)
# Snapshot functionality requires additional work to properly handle GNS3 v3 API snapshot operations


@mcp.resource(
    "projects://{project_id}/readme",
    name="Project README",
    title="GNS3 project README/notes",
    description="Project documentation in markdown - IP schemes, credentials, architecture notes, troubleshooting guides",
    mime_type="text/markdown",
)
async def resource_project_readme(ctx: Context, project_id: str) -> str:
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.get_project_readme(project_id)


@mcp.resource(
    "projects://{project_id}/topology_report",
    name="Topology Report",
    title="Unified topology report with nodes and links",
    description="v0.40.0: Comprehensive topology report showing nodes, links, statistics in table format with JSON data. Single call replaces multiple queries.",
    mime_type="text/plain",
)
async def resource_topology_report(ctx: Context, project_id: str) -> str:
    """Get unified topology report"""
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.get_topology_report(project_id)


@mcp.resource(
    "projects://{project_id}/sessions/console/",
    name="Project console sessions",
    title="Active console sessions for project",
    description="List all active console (telnet) sessions for nodes in a specific project",
    mime_type="text/plain",
)
async def resource_console_sessions(ctx: Context, project_id: str) -> str:
    """List console sessions for project nodes"""
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.list_console_sessions(project_id)


@mcp.resource(
    "projects://{project_id}/sessions/ssh/",
    name="Project SSH sessions",
    title="Active SSH sessions for project",
    description="List all active SSH sessions for nodes in a specific project",
    mime_type="text/plain",
)
async def resource_ssh_sessions(ctx: Context, project_id: str) -> str:
    """List SSH sessions for project nodes"""
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.list_ssh_sessions(project_id)


# Template resources
@mcp.resource(
    "templates://{template_id}",
    name="Template details",
    title="GNS3 template details",
    description="Detailed information about a specific template including properties, default settings, and usage notes",
    mime_type="application/json",
)
async def resource_template(ctx: Context, template_id: str) -> str:
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.get_template(template_id)


@mcp.resource(
    "nodes://{project_id}/{node_id}/template",
    name="Node template usage",
    title="Template usage notes for node",
    description="Template-specific configuration hints and usage notes for this node instance",
    mime_type="text/markdown",
)
async def resource_node_template(ctx: Context, project_id: str, node_id: str) -> str:
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.get_node_template_usage(project_id, node_id)


# Session list resources (support query param: ?project_id=xxx)
@mcp.resource(
    "sessions://console/",
    name="Console sessions",
    title="All console sessions",
    description="List all console sessions (optionally filtered by ?project_id=xxx query parameter)",
    mime_type="text/plain",
)
async def resource_console_sessions_all() -> str:
    return await get_app().resource_manager.list_console_sessions()


@mcp.resource(
    "sessions://ssh/",
    name="SSH sessions",
    title="All SSH sessions",
    description="List all SSH sessions (optionally filtered by ?project_id=xxx query parameter)",
    mime_type="text/plain",
)
async def resource_ssh_sessions_all() -> str:
    return await get_app().resource_manager.list_ssh_sessions()


# Console session resources (node-specific templates only)
@mcp.resource(
    "sessions://console/{node_name}",
    name="Console session",
    title="Console session for node",
    description="Console session state and buffer for a specific node - connection status and recent output",
    mime_type="application/json",
)
async def resource_console_session(ctx: Context, node_name: str) -> str:
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.get_console_session(node_name)


# SSH session resources (node-specific templates only)
@mcp.resource(
    "sessions://ssh/{node_name}",
    name="SSH session",
    title="SSH session for node",
    description="SSH session state for a specific node - connection status, device type, and proxy routing",
    mime_type="application/json",
)
async def resource_ssh_session(ctx: Context, node_name: str) -> str:
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.get_ssh_session(node_name)


@mcp.resource(
    "sessions://ssh/{node_name}/history",
    name="SSH command history",
    title="SSH command history for node",
    description="Command history for a specific node's SSH session - chronological list of executed commands",
    mime_type="application/json",
)
async def resource_ssh_history(ctx: Context, node_name: str) -> str:
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.get_ssh_history(node_name)


@mcp.resource(
    "sessions://ssh/{node_name}/buffer",
    name="SSH output buffer",
    title="SSH output buffer for node",
    description="Accumulated SSH output buffer for a specific node - recent command outputs and console text",
    mime_type="text/plain",
)
async def resource_ssh_buffer(ctx: Context, node_name: str) -> str:
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.get_ssh_buffer(node_name)


# SSH proxy resources
@mcp.resource(
    "proxies:///status",
    name="Main proxy status",
    title="SSH proxy service status",
    description="Health status and version of the main SSH proxy on GNS3 host (default proxy for ssh_configure)",
    mime_type="application/json",
)
async def resource_proxy_status() -> str:
    """Get SSH proxy service status (main proxy on GNS3 host)

    Returns health status and version of the main SSH proxy running on the GNS3 host.
    This is the default proxy used when ssh_configure() is called without a proxy parameter.
    """
    return await get_app().resource_manager.get_proxy_status()


@mcp.resource(
    "proxies://",
    name="Lab proxy registry",
    title="Discovered lab SSH proxies",
    description="All discovered SSH proxy containers in GNS3 lab projects - use proxy_id for routing through isolated networks",
    mime_type="text/plain",
)
async def resource_proxy_registry() -> str:
    """Discover lab SSH proxies via Docker API (v0.26.0 Multi-Proxy Support)

    Returns all discovered SSH proxy containers running inside GNS3 lab projects.
    Use the proxy_id from this list to route SSH connections through lab proxies
    for accessing isolated networks not reachable from the GNS3 host.

    Example workflow:
    1. Check this resource to find available lab proxies
    2. Use proxy_id in ssh_configure(proxy=proxy_id) for isolated network access
    3. All subsequent ssh_command() calls will route through the selected proxy

    Returns: {available, proxies[], count} where each proxy has:
    - proxy_id: Use this with ssh_configure(proxy=...)
    - hostname: Node name in GNS3
    - project_id: Which project this proxy belongs to
    - url: Proxy API endpoint
    - console_port: Port mapped from GNS3 host
    """
    return await get_app().resource_manager.get_proxy_registry()


@mcp.resource(
    "proxies://sessions",
    name="All proxy sessions",
    title="SSH sessions across all proxies",
    description="Aggregated list of ALL active SSH sessions from main proxy and lab proxies - global lab infrastructure view",
    mime_type="text/plain",
)
async def resource_proxy_sessions() -> str:
    """List all SSH sessions across all proxies (v0.26.0 Multi-Proxy Aggregation)

    Queries the main SSH proxy on GNS3 host plus all discovered lab proxies,
    returning a combined list of ALL active SSH sessions regardless of project.

    Each session includes proxy attribution (proxy_id, proxy_url, proxy_hostname)
    so you can see which proxy manages each session.

    Use this for a global view of all SSH connectivity across the entire lab infrastructure.
    For project-specific sessions, use projects://{id}/sessions/ssh instead.
    """
    return await get_app().resource_manager.list_proxy_sessions()


# Proxy resource templates (project-scoped)
@mcp.resource(
    "proxies://project/{project_id}",
    name="Project proxies",
    title="Lab proxies for project",
    description="SSH proxy containers running in a specific GNS3 project - filtered view of proxy registry",
    mime_type="application/json",
)
async def resource_project_proxies(ctx: Context, project_id: str) -> str:
    """List lab proxies for specific project (filtered view of registry)

    Returns only the SSH proxy containers running in the specified GNS3 project.
    Useful for project-specific proxy discovery without seeing proxies from other projects.
    """
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.list_project_proxies(project_id)


@mcp.resource(
    "proxies://{proxy_id}",
    name="Proxy details",
    title="Lab proxy details",
    description="Detailed information about a specific lab proxy - container details, network config, connection info",
    mime_type="application/json",
)
async def resource_proxy(ctx: Context, proxy_id: str) -> str:
    """Get detailed information about a specific lab proxy

    Returns full details for a lab proxy identified by its proxy_id (GNS3 node_id).
    Includes container details, network configuration, and connection information.
    """
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.get_proxy(proxy_id)


# Diagram resources
@mcp.resource(
    "diagrams://{project_id}/topology",
    name="Topology diagram",
    title="Visual topology diagram (SVG/PNG)",
    description="Generated topology diagram as image - shows nodes, links, status indicators. Only access if agent can process visual information.",
    mime_type="image/svg+xml",
)
async def resource_topology_diagram(ctx: Context, project_id: str) -> str:
    """Generate topology diagram as SVG image (agent-friendly access)

    Returns visual topology diagram as SVG without saving to disk. Agents can
    access diagrams directly if they can process visual information.

    SVG format is preferred for agents (scalable, smaller, text-based).

    ⚠️ Visual Resource Warning:
    This resource returns image data. Only access if you can process visual
    information and need node physical locations. Text-based resources
    (nodes, links, drawings) provide same data in structured format.

    For humans: Use export_topology_diagram() tool to save SVG/PNG files to disk.
    """
    from export_tools import generate_topology_diagram_content

    app: AppContext = ctx.request_context.lifespan_context

    try:
        # Always return SVG format (most useful for agents)
        content, mime_type = await generate_topology_diagram_content(
            app, project_id, format="svg", dpi=150
        )
        return content

    except Exception as e:
        error_response = ErrorResponse(error="Failed to generate topology diagram", details=str(e))
        return json.dumps(error_response.model_dump(), indent=2)


# ============================================================================
# MCP Prompts - Guided Workflows
# ============================================================================


@mcp.prompt(
    name="SSH Setup Workflow",
    title="Enable SSH on network devices",
    description="Device-specific SSH configuration for 6 device types with multi-proxy support",
    tags={"workflow", "ssh", "setup", "device-access", "guided"},
)
async def ssh_setup(
    node_name: Annotated[str, "Target node name to configure"],
    device_type: Annotated[
        str,
        "Device type (cisco_ios, cisco_nxos, mikrotik_routeros, juniper_junos, arista_eos, linux)",
    ],
    username: Annotated[str, "SSH username to create"] = "admin",
    password: Annotated[str, "SSH password to set"] = "admin",
) -> str:
    """SSH Setup Workflow - Enable SSH access on network devices

    Provides device-specific step-by-step instructions for configuring SSH
    on network devices. Covers 6 device types: Cisco IOS, NX-OS, MikroTik
    RouterOS, Juniper Junos, Arista EOS, and Linux.

    Returns:
        Complete workflow with device-specific commands, verification steps,
        multi-proxy routing instructions, and troubleshooting guidance
    """
    return await render_ssh_setup_prompt(node_name, device_type, username, password)


@mcp.prompt(
    name="Topology Discovery Workflow",
    title="Discover and visualize network topology",
    description="Discover nodes, links, templates, drawings using resources - includes visual diagram guidance for agents",
    tags={"workflow", "discovery", "visualization", "read-only", "guided"},
)
async def topology_discovery(
    project_name: Annotated[
        str | None, "Optional project name to focus on (default: guide user to select)"
    ] = None,
    include_export: Annotated[bool, "Include export/visualization steps (default: True)"] = True,
) -> str:
    """Topology Discovery Workflow - Discover and visualize network topology

    Guides you through discovering nodes, links, and topology structure using
    MCP resources and tools. Includes visualization guidance with warnings
    about agent-appropriate access patterns.

    Returns:
        Complete workflow for topology discovery, visualization, and analysis
    """
    return await render_topology_discovery_prompt(project_name, include_export)


@mcp.prompt(
    name="Troubleshooting Workflow",
    title="Systematic network troubleshooting",
    description="OSI model-based troubleshooting with README checks, diagnostic tools, log collection",
    tags={"workflow", "troubleshooting", "diagnostics", "guided"},
)
async def troubleshooting(
    node_name: Annotated[str | None, "Optional node name to focus troubleshooting on"] = None,
    issue_type: Annotated[
        str | None, "Optional issue category (connectivity, console, ssh, performance)"
    ] = None,
) -> str:
    """Network Troubleshooting Workflow - Systematic network issue diagnosis

    Provides OSI model-based troubleshooting methodology for network labs.
    Covers connectivity, console access, SSH, and performance issues.
    Includes README documentation checks for known configurations.

    Returns:
        Complete troubleshooting workflow with diagnostic steps, common issues,
        and resolution guidance
    """
    return await render_troubleshooting_prompt(node_name, issue_type)


@mcp.prompt(
    name="Lab Setup Workflow",
    title="Automated lab topology creation",
    description="Create complete topologies (star/mesh/linear/ring/ospf/bgp) with nodes, links, IPs, and README documentation",
    tags={"workflow", "topology", "automation", "creates-resource", "guided"},
)
async def lab_setup(
    topology_type: Annotated[str, "Topology type (star, mesh, linear, ring, ospf, bgp)"],
    device_count: Annotated[int, "Number of devices (spokes for star, areas for OSPF, AS for BGP)"],
    template_name: Annotated[str, "GNS3 template to use"] = "Alpine Linux",
    project_name: Annotated[str, "Name for the new project"] = "Lab Topology",
) -> str:
    """Lab Setup Workflow - Automated lab topology creation

    Generates complete lab topologies with automated node placement, link
    configuration, IP addressing schemes, and README documentation. Supports 6 topology types.

    Topology Types:
        - star: Hub-and-spoke with central hub
        - mesh: Full mesh with all devices interconnected
        - linear: Chain of devices in a line
        - ring: Circular connection of devices
        - ospf: Multi-area OSPF with backbone and areas
        - bgp: Multiple AS with iBGP and eBGP peering

    Returns:
        Complete workflow with node creation, link setup, IP addressing,
        README documentation, and topology-specific configuration guidance
    """
    return render_lab_setup_prompt(topology_type, device_count, template_name, project_name)


@mcp.prompt(
    name="Node Setup Workflow",
    title="Complete node addition workflow",
    description="End-to-end node setup: create, configure IP, document in README, establish SSH, connect to network",
    tags={"workflow", "setup", "node", "automation", "guided"},
)
async def node_setup(
    node_name: Annotated[str, "Name for the new node (e.g., 'Router1')"],
    template_name: Annotated[str, "GNS3 template to use (e.g., 'Cisco IOSv', 'Alpine Linux')"],
    ip_address: Annotated[str, "Management IP to assign (e.g., '192.168.1.10')"],
    subnet_mask: Annotated[str, "Subnet mask"] = "255.255.255.0",
    device_type: Annotated[str, "Device type for SSH"] = "cisco_ios",
    username: Annotated[str, "SSH username to create"] = "admin",
    password: Annotated[str, "SSH password to set"] = "admin",
) -> str:
    """Node Setup Workflow - Complete node addition workflow

    Guides you through adding a new node: creation, IP configuration via console,
    README documentation, SSH setup, and network connections. Includes template
    usage field guidance for device-specific instructions.

    Returns:
        Complete workflow covering node creation, boot, IP config, README documentation,
        template usage checks, SSH setup, and network connection guidance
    """
    return render_node_setup_prompt(
        node_name=node_name,
        template_name=template_name,
        ip_address=ip_address,
        subnet_mask=subnet_mask,
        device_type=device_type,
        username=username,
        password=password,
    )


# ============================================================================
# MCP Tools - Connection Management (v0.38.0)
# ============================================================================


@mcp.tool(
    name="gns3_connection",
    tags={"connection", "management", "diagnostics"},
)
async def gns3_connection(
    ctx: Context,
    action: Annotated[
        Literal["check", "retry"], "Action: 'check' (check status) or 'retry' (force reconnect)"
    ],
) -> str:
    """Manage GNS3 server connection

    CRUD-style connection management tool.

    Actions:
        - check: Check connection status (connection state, error details, last attempt time)
        - retry: Force immediate reconnection (bypasses exponential backoff)

    Args:
        action: Connection action to perform

    Returns:
        JSON with connection status or reconnection result

    Examples:
        # Check connection status
        >>> gns3_connection(action="check")
        {"connected": false, "server": "http://192.168.1.20:80",
         "error": "Connection timeout", "last_attempt": "08:15:42 30.10.2025"}

        # Force reconnection
        >>> gns3_connection(action="retry")
        {"success": true, "message": "Successfully reconnected to GNS3 server",
         "server": "http://192.168.1.20:80", "error": null}
    """
    app: IAppContext = ctx.request_context.lifespan_context
    gns3 = app.gns3

    if action == "check":
        # Check connection status
        status = {
            "connected": gns3.is_connected,
            "server": gns3.base_url,
            "error": gns3.connection_error,
            "last_attempt": (
                gns3.last_auth_attempt.strftime("%H:%M:%S %d.%m.%Y")
                if gns3.last_auth_attempt
                else None
            ),
        }
        return json.dumps(status, indent=2)

    elif action == "retry":
        # Force immediate reconnection
        logger.info("Manual reconnection attempt triggered")

        # Attempt authentication with 5-second timeout
        success = await gns3.authenticate(retry=False, retry_interval=5, max_retries=1)

        if success:
            # Try to detect opened project
            try:
                projects = await gns3.get_projects()
                opened = [p for p in projects if p.get("status") == "opened"]
                if opened:
                    app.current_project_id = opened[0]["project_id"]
                    logger.info(f"Auto-detected opened project: {opened[0]['name']}")
            except Exception as e:
                logger.warning(f"Failed to detect opened project: {e}")

            result = {
                "success": True,
                "message": "Successfully reconnected to GNS3 server",
                "server": gns3.base_url,
                "error": None,
            }
        else:
            result = {
                "success": False,
                "message": "Failed to reconnect to GNS3 server",
                "server": gns3.base_url,
                "error": gns3.connection_error,
            }

        return json.dumps(result, indent=2)


# ============================================================================
# MCP Tools - Actions That Modify State
# ============================================================================


@mcp.tool(
    name="project",
    tags={"project", "management", "idempotent"},
    annotations={"idempotent": True},
)
async def project(
    ctx: Context,
    action: Annotated[
        Literal["list", "open", "create", "close"], "Action: 'list', 'open', 'create', or 'close'"
    ],
    name: Annotated[str | None, "Project name (required for 'open' and 'create')"] = None,
    path: Annotated[str | None, "Optional project directory path (for 'create')"] = None,
    format: Annotated[
        str, "Output format: 'table' (default) or 'json' (for 'list' action)"
    ] = "table",
) -> str:
    """Manage GNS3 projects

    CRUD-style project management tool.

    Actions:
        - list: List all projects
        - open: Open a project by name
        - create: Create a new project and auto-open it
        - close: Close the currently opened project

    Args:
        action: Project action to perform
        name: Project name (required for open/create)
        path: Optional project directory path (create only)
        format: Output format for 'list' action

    Returns:
        JSON with ProjectInfo for created project, or list of projects

    Examples:
        # List all projects
        >>> project(action="list")
        >>> project(action="list", format="json")

        # Open existing project
        >>> project(action="open", name="My Lab")

        # Create new project
        >>> project(action="create", name="Production Lab")
        >>> project(action="create", name="Test Lab", path="/opt/gns3/projects")

        # Close current project
        >>> project(action="close")
    """
    app: IAppContext = ctx.request_context.lifespan_context

    if action == "list":
        return await list_projects_impl(app.gns3, format)

    elif action == "open":
        if not name:
            raise ValueError("name parameter is required for 'open' action")
        result, new_project_id = await open_project_impl(app.gns3, name)
        if new_project_id:  # Only update if successful (empty string means error)
            app.current_project_id = new_project_id
        return result

    elif action == "create":
        if not name:
            raise ValueError("name parameter is required for 'create' action")
        result, new_project_id = await create_project_impl(app.gns3, name, path)
        if new_project_id:  # Only update if successful
            app.current_project_id = new_project_id
        return result

    elif action == "close":
        result, _ = await close_project_impl(app.gns3, app.current_project_id)
        # Close always clears current_project_id (returns None)
        app.current_project_id = None
        return result


@mcp.tool(
    name="node",
    tags={"node", "topology", "modifies-state", "bulk", "idempotent"},
    annotations={"idempotent": True},
)
async def node(
    ctx: Context,
    action: Annotated[
        Literal["list", "create", "delete", "set"],
        "Action: 'list' (list nodes), 'create' (new node), 'delete' (remove node), or 'set' (configure/control node)",
    ],
    project_id: Annotated[str | None, "Project ID (required for 'list')"] = None,
    node_name: Annotated[
        str | None,
        "Node name, wildcard pattern ('*', 'Router*', 'R[123]'), or JSON array ('[\"R1\",\"R2\"]'). Required for 'delete' and 'set'",
    ] = None,
    template_name: Annotated[
        str | None, "Template name (required for 'create', e.g., 'Alpine Linux', 'Cisco IOSv')"
    ] = None,
    state_action: Annotated[
        str | None,
        "State control action for 'set': 'start' (boot), 'stop' (shutdown), 'suspend' (pause), 'reload' (reboot), 'restart' (stop then start)",
    ] = None,
    x: Annotated[int | None, "X coordinate (top-left corner of node icon)"] = None,
    y: Annotated[int | None, "Y coordinate (top-left corner of node icon)"] = None,
    z: Annotated[int | None, "Z-order layer for overlapping nodes"] = None,
    locked: Annotated[bool | None, "Lock position to prevent GUI moves"] = None,
    ports: Annotated[int | None, "Number of ports (ethernet_switch nodes only)"] = None,
    name: Annotated[str | None, "New name (REQUIRES node stopped)"] = None,
    ram: Annotated[int | None, "RAM in MB (QEMU nodes only)"] = None,
    cpus: Annotated[int | None, "Number of CPUs (QEMU nodes only)"] = None,
    hdd_disk_image: Annotated[str | None, "HDD disk image path (QEMU nodes only)"] = None,
    adapters: Annotated[int | None, "Network adapters count (QEMU nodes only)"] = None,
    console_type: Annotated[str | None, "Console type: telnet/vnc/spice"] = None,
    format: Annotated[
        str, "Output format: 'table' (default) or 'json' (for 'list' action)"
    ] = "table",
    compute_id: Annotated[str, "Compute server ID (for 'create')"] = "local",
    properties: Annotated[
        Dict[str, Any] | None, "Override template properties for 'create' (e.g., {'ram': 512})"
    ] = None,
    parallel: Annotated[
        bool, "Execute operations concurrently (default: True for start/stop/suspend)"
    ] = True,
) -> str:
    """Manage GNS3 nodes (CRUD operations)

    v0.47.0: CRUD-style consolidation of create_node, delete_node, and set_node.
    v0.40.0: Enhanced with wildcard and bulk operation support.

    Actions:
        - list: List nodes in a project
        - create: Create new node from template at specified coordinates
        - delete: Delete node from project (WARNING: destructive, cannot be undone)
        - set: Configure node properties and/or control state (supports wildcards/bulk)

    Wildcard Patterns (for 'set' and 'delete'):
        - Single node: "Router1"
        - All nodes: "*"
        - Prefix match: "Router*" (matches Router1, Router2, RouterCore)
        - Suffix match: "*-Core" (matches Router-Core, Switch-Core)
        - Character class: "R[123]" (matches R1, R2, R3)
        - JSON array: '["Router1", "Router2", "Switch1"]'

    Validation Rules:
        - name parameter requires node to be stopped
        - Hardware properties (ram, cpus, hdd_disk_image, adapters) apply to QEMU nodes only
        - ports parameter applies to ethernet_switch nodes only
        - state_action values: start, stop, suspend, reload, restart

    Returns:
        Single node: Status message
        Multiple nodes: BatchOperationResult JSON with per-node success/failure

    Examples:
        # List nodes in project
        >>> node(action="list", project_id="abc-123")
        >>> node(action="list", project_id="abc-123", format="json")

        # Create new node
        >>> node(action="create", template_name="Alpine Linux", x=100, y=200)
        >>> node(action="create", template_name="Cisco IOSv", x=300, y=400, node_name="R1", properties={"ram": 1024})

        # Delete node
        >>> node(action="delete", node_name="Router1")

        # Start all nodes
        >>> node(action="set", node_name="*", state_action="start")

        # Stop all routers
        >>> node(action="set", node_name="Router*", state_action="stop")

        # Configure node properties
        >>> node(action="set", node_name="R1", x=100, y=200, ram=2048)
    """
    app: IAppContext = ctx.request_context.lifespan_context

    if action == "list":
        if not project_id:
            raise ValueError("project_id is required for 'list' action")
        return await list_nodes_impl(app, project_id, format)

    elif action == "create":
        # Create new node from template
        if not template_name:
            raise ValueError("template_name is required for 'create' action")
        if x is None or y is None:
            raise ValueError("x and y coordinates are required for 'create' action")

        error = await validate_current_project(app)
        if error:
            return error

        return await create_node_impl(
            app.gns3, app.current_project_id, template_name, x, y, node_name, compute_id, properties
        )

    elif action == "delete":
        # Delete node
        if not node_name:
            raise ValueError("node_name is required for 'delete' action")

        error = await validate_current_project(app)
        if error:
            return error

        return await delete_node_impl(
            app.gns3, app.current_project_id, app.ssh_proxy_mapping, node_name
        )

    elif action == "set":
        # Configure node properties and/or control state
        if not node_name:
            raise ValueError("node_name is required for 'set' action")

        return await set_node_impl(
            app,
            node_name,
            state_action,  # Renamed from 'action' to 'state_action'
            x,
            y,
            z,
            locked,
            ports,
            name,
            ram,
            cpus,
            hdd_disk_image,
            adapters,
            console_type,
            ctx=ctx,
            parallel=parallel,
        )


@mcp.tool(name="console", tags={"console", "device-access", "bulk", "automation"})
async def console(
    ctx: Context,
    operations: Annotated[
        List[Dict[str, Any]], "List of console operations (send/send_and_wait/read/keystroke)"
    ],
) -> str:
    """Execute console operations (BATCH-ONLY)

    v0.47.0: Batch-only console tool. Individual console tools removed (aggressive consolidation).

    IMPORTANT: Prefer SSH tools when available! Console tools are primarily for:
    - Initial device configuration (enabling SSH, creating users)
    - Troubleshooting when SSH is unavailable
    - Devices without SSH support (VPCS, simple switches)

    Two-phase execution:
    1. VALIDATE ALL operations (check nodes exist, required params present)
    2. EXECUTE ALL operations (only if all valid, sequential execution)

    Each operation supports all parameters from the underlying console tool:

    - "send": Send data to console
        {
            "type": "send",
            "node_name": "R1",
            "data": "show version\\n",
            "raw": false  // optional
        }

    - "send_and_wait": Send command and wait for pattern
        {
            "type": "send_and_wait",
            "node_name": "R1",
            "command": "show ip interface brief\\n",
            "wait_pattern": "Router#",  // optional
            "timeout": 30,  // optional
            "raw": false  // optional
        }

    - "read": Read console output (NOTE: returns empty if nothing sent yet - this is normal)
        {
            "type": "read",
            "node_name": "R1",
            "mode": "diff",  // optional: diff/last_page/num_pages/all
            "pages": 1,  // optional, only with mode="num_pages"
            "pattern": "error",  // optional grep pattern
            "case_insensitive": true,  // optional
            "invert": false,  // optional
            "before": 0,  // optional context lines
            "after": 0,  // optional context lines
            "context": 0  // optional context lines (overrides before/after)
        }
        IMPORTANT: Console buffer may be empty on first read (QEMU nodes don't output until prompted).
        Use 'send_and_wait' to explicitly send a command and read the response, or send commands first with 'send'.

    - "keystroke": Send special keystroke
        {
            "type": "keystroke",
            "node_name": "R1",
            "key": "enter"  // up/down/enter/ctrl_c/etc
        }

    Args:
        operations: List of operation dictionaries (see examples above)

    Returns:
        JSON with execution results:
        {
            "completed": [0, 1, 2],  // Indices of successful operations
            "failed": [3],  // Indices of failed operations
            "results": [
                {
                    "operation_index": 0,
                    "success": true,
                    "operation_type": "send_and_wait",
                    "node_name": "R1",
                    "result": {...}  // Operation-specific result
                },
                ...
            ],
            "total_operations": 4,
            "execution_time": 5.3
        }

    Examples:
        # Multiple commands on one node:
        >>> console(operations=[
        ...     {"type": "send_and_wait", "node_name": "R1", "command": "show version\\n", "wait_pattern": "Router#"},
        ...     {"type": "send_and_wait", "node_name": "R1", "command": "show ip route\\n", "wait_pattern": "Router#"},
        ...     {"type": "read", "node_name": "R1", "mode": "diff"}
        ... ])

        # Same command on multiple nodes:
        >>> console(operations=[
        ...     {"type": "send_and_wait", "node_name": "R1", "command": "show ip int brief\\n", "wait_pattern": "#"},
        ...     {"type": "send_and_wait", "node_name": "R2", "command": "show ip int brief\\n", "wait_pattern": "#"},
        ...     {"type": "send_and_wait", "node_name": "R3", "command": "show ip int brief\\n", "wait_pattern": "#"}
        ... ])

        # Mixed operations:
        >>> console(operations=[
        ...     {"type": "send", "node_name": "R1", "data": "\\n"},  # Wake console
        ...     {"type": "read", "node_name": "R1", "mode": "last_page"},  # Check prompt
        ...     {"type": "send_and_wait", "node_name": "R1", "command": "show version\\n", "wait_pattern": "#"},
        ...     {"type": "keystroke", "node_name": "R1", "key": "ctrl_c"}  # Cancel if needed
        ... ])
    """
    app: IAppContext = ctx.request_context.lifespan_context
    return await console_batch_impl(app, operations)


@mcp.tool(
    name="link",
    tags={"network", "topology", "bulk", "modifies-state"},
    annotations={"modifies_topology": True},
)
async def link(
    ctx: Context,
    action: Annotated[
        Literal["list", "batch"], "Action: 'list' (list links) or 'batch' (batch operations)"
    ],
    project_id: Annotated[str | None, "Project ID (required for 'list')"] = None,
    connections: Annotated[
        List[Dict[str, Any]] | None, "List of connection operations (required for 'batch')"
    ] = None,
    format: Annotated[str, "Output format: 'table' (default) or 'json' (for 'list')"] = "table",
) -> str:
    """Manage network connections (links)

    v0.47.0: Renamed from set_network_connections to link (CRUD consolidation).

    Actions:
        - list: List all links in a project
        - batch: Execute multiple connect/disconnect operations with two-phase validation

    Two-phase execution for batch operations prevents partial topology changes:
    1. VALIDATE ALL operations (check nodes exist, ports free, adapters valid)
    2. EXECUTE ALL operations (only if all valid - atomic)

    Connection Operations (for 'batch' action):
        Connect: {action: "connect", node_a, node_b, port_a, port_b, adapter_a, adapter_b}
        Disconnect: {action: "disconnect", link_id}

    Examples:
        # List links
        >>> link(action="list", project_id="abc-123")
        >>> link(action="list", project_id="abc-123", format="json")

        # Connect two nodes (batch)
        >>> link(action="batch", connections=[{
        ...     "action": "connect",
        ...     "node_a": "Router1",
        ...     "node_b": "Router2",
        ...     "port_a": 0,
        ...     "port_b": 0,
        ...     "adapter_a": 0,
        ...     "adapter_b": 0
        ... }])

        # Disconnect link (batch)
        >>> link(action="batch", connections=[{"action": "disconnect", "link_id": "abc123"}])

    Returns: JSON with OperationResult (completed and failed operations) or list of links
    """
    app: IAppContext = ctx.request_context.lifespan_context

    if action == "list":
        if not project_id:
            raise ValueError("project_id is required for 'list' action")
        # Use query_resource to get links
        resource_mgr = app.resource_manager
        result = await resource_mgr.get_resource_content(f"links://{project_id}/", format)
        return result

    elif action == "batch":
        if not connections:
            raise ValueError("connections parameter is required for 'batch' action")

        error = await validate_current_project(app)
        if error:
            return error

        return await set_connection_impl(app, connections)


@mcp.tool(
    name="node_file",
    tags={"node", "docker", "modifies-state"},
)
async def node_file(
    ctx: Context,
    action: Annotated[
        Literal["read", "write", "configure_network"],
        "Action: 'read' (get file), 'write' (update file), or 'configure_network' (network config workflow)",
    ],
    node_name: Annotated[str, "Name of the Docker node"],
    file_path: Annotated[
        str | None, "Path relative to container root (required for 'read' and 'write')"
    ] = None,
    content: Annotated[str | None, "File contents (required for 'write')"] = None,
    interfaces: Annotated[
        list | None, "List of interface configs (required for 'configure_network')"
    ] = None,
) -> str:
    """Manage Docker node files (CRUD operations)

    v0.47.0: CRUD-style consolidation of get_node_file, write_node_file, and configure_node_network.

    Actions:
        - read: Read file from Docker node filesystem
        - write: Write file to Docker node filesystem (WARNING: does NOT restart node)
        - configure_network: Configure network interfaces (full workflow: write + restart)

    IMPORTANT: Use 'configure_network' for network configuration as it handles the complete
    workflow (write config → restart node → apply changes).

    Returns:
        JSON with file contents, confirmation message, or configured interfaces

    Examples:
        # Read file
        >>> node_file(action="read", node_name="A-PROXY", file_path="etc/network/interfaces")

        # Write file
        >>> node_file(action="write", node_name="A-PROXY",
        ...           file_path="etc/network/interfaces",
        ...           content="auto eth0\\niface eth0 inet dhcp")

        # Configure network (recommended)
        >>> node_file(action="configure_network", node_name="A-PROXY", interfaces=[{
        ...     "name": "eth0",
        ...     "mode": "static",
        ...     "address": "10.199.0.254",
        ...     "netmask": "255.255.255.0",
        ...     "gateway": "10.199.0.1"
        ... }])
    """
    app: IAppContext = ctx.request_context.lifespan_context

    error = await validate_current_project(app)
    if error:
        return error

    if action == "read":
        # Read file from Docker node
        if not file_path:
            raise ValueError("file_path is required for 'read' action")

        return await get_node_file_impl(app.gns3, app.current_project_id, node_name, file_path)

    elif action == "write":
        # Write file to Docker node
        if not file_path:
            raise ValueError("file_path is required for 'write' action")
        if not content:
            raise ValueError("content is required for 'write' action")

        return await write_node_file_impl(app, node_name, file_path, content)

    elif action == "configure_network":
        # Configure network interfaces (full workflow)
        if not interfaces:
            raise ValueError("interfaces list is required for 'configure_network' action")

        return await configure_node_network_impl(app, node_name, interfaces)


@mcp.tool(
    name="project_docs",
    tags={"documentation", "project", "modifies-state"},
)
async def project_docs(
    ctx: Context,
    action: Annotated[
        Literal["get", "update"], "Action: 'get' (read README) or 'update' (write README)"
    ],
    content: Annotated[str | None, "Markdown content (required for 'update')"] = None,
    project_id: Annotated[str | None, "Project ID (uses current project if not specified)"] = None,
) -> str:
    """Manage project documentation (CRUD operations)

    v0.47.0: CRUD-style consolidation of get_project_readme and update_project_readme.

    Actions:
        - get: Read project README/notes (markdown format)
        - update: Write project README/notes

    Project documentation typically includes:
        - IP addressing schemes and VLANs
        - Node credentials (usernames, password vault keys)
        - Architecture diagrams (text-based)
        - Configuration templates and snippets
        - Troubleshooting notes and runbooks

    Returns:
        JSON with project_id and markdown content or success confirmation

    Examples:
        # Get README
        >>> project_docs(action="get")
        >>> project_docs(action="get", project_id="a920c77d-6e9b-41b8-9311-b4b866a2fbb0")

        # Update README
        >>> project_docs(action="update", content=\"\"\"
        ... # HA PowerDNS
        ... ## IPs
        ... - B-Rec1: 10.2.0.1/24
        ... - B-Rec2: 10.2.0.2/24
        ... \"\"\")
    """
    app: IAppContext = ctx.request_context.lifespan_context

    if not project_id:
        error = await validate_current_project(app)
        if error:
            return error
        project_id = app.current_project_id

    if action == "get":
        # Get project README
        try:
            readme_content = await app.gns3.get_project_readme(project_id)
            return json.dumps(
                {
                    "project_id": project_id,
                    "content": (
                        readme_content if readme_content else "# Project Notes\n\n(No notes yet)"
                    ),
                    "format": "markdown",
                },
                indent=2,
            )
        except Exception as e:
            return json.dumps(
                {
                    "error": "Failed to get project README",
                    "project_id": project_id,
                    "details": str(e),
                },
                indent=2,
            )

    elif action == "update":
        # Update project README
        if not content:
            raise ValueError("content is required for 'update' action")

        try:
            success = await app.gns3.update_project_readme(project_id, content)
            if success:
                return json.dumps(
                    {
                        "success": True,
                        "project_id": project_id,
                        "message": "README updated successfully",
                        "content_length": len(content),
                    },
                    indent=2,
                )
            else:
                return json.dumps(
                    {"error": "Failed to update README", "project_id": project_id}, indent=2
                )
        except Exception as e:
            return json.dumps(
                {"error": "Failed to update README", "project_id": project_id, "details": str(e)},
                indent=2,
            )


# export_topology_diagram tool now registered from export_tools module
# Register the imported tool with MCP
mcp.tool(
    name="export_topology_diagram",
    description="Export topology diagram to SVG/PNG files on disk. For agents: use diagrams://{project_id}/topology resource for direct access without saving files.",
    tags={"topology", "visualization", "export", "file-io", "idempotent"},
    annotations={"idempotent": True, "read_only": True, "creates_resource": True},
)(export_topology_diagram)


# ============================================================================
# Drawing Tools
# ============================================================================


@mcp.tool(
    name="drawing",
    tags={"drawing", "topology", "visualization", "bulk"},
    annotations={"creates_resource": True},
)
async def drawing(
    ctx: Context,
    action: Annotated[
        Literal["list", "create", "update", "delete", "batch"],
        "Action: 'list' (list drawings), 'create' (new drawing), 'update' (modify), 'delete' (remove), or 'batch' (create multiple)",
    ],
    project_id: Annotated[str | None, "Project ID (required for 'list')"] = None,
    drawing_id: Annotated[str | None, "Drawing ID (required for 'update' and 'delete')"] = None,
    drawing_type: Annotated[
        str | None,
        "Shape type for 'create': 'rectangle' (box), 'ellipse' (circle/oval), 'line' (connector), 'text' (label)",
    ] = None,
    x: Annotated[int | None, "X coordinate (start point for line, top-left for others)"] = None,
    y: Annotated[int | None, "Y coordinate (start point for line, top-left for others)"] = None,
    z: Annotated[int | None, "Z-order/layer (default: 0 for shapes, 1 for text)"] = None,
    width: Annotated[int | None, "Width in pixels (rectangle/ellipse only)"] = None,
    height: Annotated[int | None, "Height in pixels (rectangle/ellipse only)"] = None,
    rx: Annotated[int | None, "Horizontal corner radius (rectangle only)"] = None,
    ry: Annotated[int | None, "Vertical corner radius (rectangle only)"] = None,
    fill_color: Annotated[str, "Fill color hex code"] = "#ffffff",
    border_color: Annotated[str, "Border color hex code"] = "#000000",
    border_width: Annotated[int, "Border width in pixels"] = 2,
    x2: Annotated[int | None, "End X coordinate (line only)"] = None,
    y2: Annotated[int | None, "End Y coordinate (line only)"] = None,
    text: Annotated[str | None, "Text content (text only)"] = None,
    font_size: Annotated[int, "Font size in points (text only)"] = 10,
    font_weight: Annotated[str, "Font weight: 'normal' or 'bold' (text only)"] = "normal",
    font_family: Annotated[str, "Font family name (text only)"] = "TypeWriter",
    color: Annotated[str, "Text color hex code (text only)"] = "#000000",
    rotation: Annotated[int | None, "Rotation angle in degrees (for 'update')"] = None,
    svg: Annotated[str | None, "SVG content (for 'update')"] = None,
    locked: Annotated[bool | None, "Lock/unlock drawing (for 'update')"] = None,
    format: Annotated[str, "Output format: 'table' (default) or 'json' (for 'list')"] = "table",
    drawings: Annotated[
        list[dict] | None, "List of drawing definitions (required for 'batch')"
    ] = None,
) -> str:
    """Manage drawings (CRUD operations)

    v0.47.0: CRUD-style consolidation of create_drawing, update_drawing, delete_drawing, and create_drawings_batch.

    Actions:
        - list: List all drawings in a project
        - create: Create new drawing (rectangle, ellipse, line, text)
        - update: Update existing drawing properties
        - delete: Delete drawing (WARNING: destructive, cannot be undone)
        - batch: Create multiple drawings with two-phase validation

    Returns:
        JSON with drawing info or batch operation results

    Examples:
        # List drawings
        >>> drawing(action="list", project_id="abc-123")
        >>> drawing(action="list", project_id="abc-123", format="json")

        # Create rectangle
        >>> drawing(action="create", drawing_type="rectangle", x=100, y=100, width=200, height=100)

        # Create text label
        >>> drawing(action="create", drawing_type="text", x=175, y=140, text="Router1", z=1)

        # Update drawing position
        >>> drawing(action="update", drawing_id="abc123", x=200, y=200)

        # Delete drawing
        >>> drawing(action="delete", drawing_id="abc123")

        # Create multiple drawings
        >>> drawing(action="batch", drawings=[
        ...     {"drawing_type": "rectangle", "x": 100, "y": 100, "width": 200, "height": 100},
        ...     {"drawing_type": "text", "x": 175, "y": 140, "text": "Router1", "z": 1}
        ... ])
    """
    app: IAppContext = ctx.request_context.lifespan_context

    if action == "list":
        if not project_id:
            raise ValueError("project_id is required for 'list' action")
        # Use query_resource to get drawings
        resource_mgr = app.resource_manager
        result = await resource_mgr.get_resource_content(f"drawings://{project_id}/", format)
        return result

    error = await validate_current_project(app)
    if error:
        return error

    if action == "create":
        # Create single drawing
        if not drawing_type:
            raise ValueError("drawing_type is required for 'create' action")
        if x is None or y is None:
            raise ValueError("x and y coordinates are required for 'create' action")

        return await create_drawing_impl(
            app,
            drawing_type,
            x,
            y,
            z if z is not None else 0,
            width,
            height,
            rx,
            ry,
            fill_color,
            border_color,
            border_width,
            x2,
            y2,
            text,
            font_size,
            font_weight,
            font_family,
            color,
        )

    elif action == "update":
        # Update existing drawing
        if not drawing_id:
            raise ValueError("drawing_id is required for 'update' action")

        return await update_drawing_impl(app, drawing_id, x, y, z, rotation, svg, locked)

    elif action == "delete":
        # Delete drawing
        if not drawing_id:
            raise ValueError("drawing_id is required for 'delete' action")

        return await delete_drawing_impl(app, drawing_id)

    elif action == "batch":
        # Create multiple drawings
        if not drawings:
            raise ValueError("drawings list is required for 'batch' action")

        return await create_drawings_batch_impl(app, drawings)


# ============================================================================
# SSH Proxy Tools
# ============================================================================

from tools.ssh_tools import (
    ssh_batch_impl,
)


@mcp.tool(name="ssh", tags={"ssh", "device-access", "bulk", "automation"})
async def ssh(
    ctx: Context, operations: Annotated[list[dict], "List of SSH operations (command/disconnect)"]
) -> str:
    """Execute SSH operations (BATCH-ONLY)

    v0.47.0: Batch-only SSH tool. Individual SSH tools removed (aggressive consolidation).
    v0.28.0: Local execution support with node_name="@"

    Local Execution Support:
    - Use node_name="@" in any operation for local execution on SSH proxy container
    - Mix local and remote operations in same batch
    - Useful for: connectivity tests before device access, ansible playbooks

    Two-phase execution prevents partial failures:
    1. VALIDATE ALL operations (check required params, valid types)
    2. EXECUTE ALL operations (only if all valid, sequential execution)

    Supported operation types:
    - "configure": Configure SSH session (equivalent to old ssh_configure)
    - "command": Execute command (equivalent to old ssh_command, supports local with "@")
    - "disconnect": Disconnect SSH session

    Args:
        operations: List of operation dicts, each with:
            - type (str): Operation type (required)
            - node_name (str): Node name (or "@" for local execution) (required)
            - Additional params specific to operation type

    Returns:
        JSON with execution results including completed/failed indices

    Examples:
        # Configure session + run commands:
        >>> ssh(operations=[
        ...     {"type": "configure", "node_name": "R1", "device_dict": {
        ...         "device_type": "cisco_ios", "host": "10.1.0.1",
        ...         "username": "admin", "password": "cisco123"
        ...     }},
        ...     {"type": "command", "node_name": "R1", "command": "show version"},
        ...     {"type": "command", "node_name": "R1", "command": "show ip route"}
        ... ])

        # Same command on multiple nodes:
        >>> ssh(operations=[
        ...     {"type": "command", "node_name": "R1", "command": "show ip int brief"},
        ...     {"type": "command", "node_name": "R2", "command": "show ip int brief"}
        ... ])

        # Configuration commands:
        >>> ssh(operations=[{
        ...     "type": "command",
        ...     "node_name": "R1",
        ...     "command": [
        ...         "interface GigabitEthernet0/0",
        ...         "ip address 10.1.1.1 255.255.255.0",
        ...         "no shutdown"
        ...     ]
        ... }])

        # Local execution - test connectivity before device access:
        >>> ssh(operations=[
        ...     {"type": "command", "node_name": "@", "command": "ping -c 2 10.1.1.1"},
        ...     {"type": "command", "node_name": "@", "command": "ping -c 2 10.1.1.2"},
        ...     {"type": "command", "node_name": "R1", "command": "show ip int brief"},
        ...     {"type": "command", "node_name": "R2", "command": "show ip int brief"}
        ... ])
    """
    app: IAppContext = ctx.request_context.lifespan_context
    return await ssh_batch_impl(app, operations)


# ============================================================================
# MCP Tools - Resource Query (v0.46.0 - Claude Desktop Compatibility)
# ============================================================================


@mcp.tool(
    name="query_resource",
    tags={"resource", "query", "read-only", "claude-desktop"},
)
async def query_resource(
    ctx: Context,
    uri: Annotated[str, "Resource URI to query (see tool description for supported patterns)"],
    format: Annotated[
        str, "Output format: 'table' (default, human-readable) or 'json' (structured)"
    ] = "table",
) -> str:
    """Universal resource query tool - access any GNS3 MCP resource.

    See tool implementation docstring for comprehensive URI pattern documentation.
    """
    app: IAppContext = ctx.request_context.lifespan_context
    return await query_resource_impl(app.resource_manager, uri, format)


# ============================================================================
# MCP Tools - Tool Discovery (v0.47.0 - Aggressive Consolidation)
# ============================================================================


# Tool metadata registry for search_tools
TOOL_REGISTRY = {
    "gns3_connection": {
        "categories": ["connection", "management"],
        "capabilities": ["CRUD"],
        "resources": [],
        "description": "Manage GNS3 server connection (check status, retry connection)",
        "actions": ["check", "retry"],
    },
    "project": {
        "categories": ["project", "management"],
        "capabilities": ["CRUD", "idempotent"],
        "resources": ["projects://"],
        "description": "Manage GNS3 projects (list, open, create, close)",
        "actions": ["list", "open", "create", "close"],
    },
    "node": {
        "categories": ["node", "topology"],
        "capabilities": ["CRUD", "bulk", "wildcard", "parallel"],
        "resources": ["nodes://{project_id}/"],
        "description": "Manage GNS3 nodes (list, create, delete, configure/control)",
        "actions": ["list", "create", "delete", "set"],
    },
    "link": {
        "categories": ["connection", "topology"],
        "capabilities": ["CRUD", "batch", "parallel"],
        "resources": ["links://{project_id}/"],
        "description": "Manage network connections/links (list, batch operations)",
        "actions": ["list", "batch"],
    },
    "drawing": {
        "categories": ["drawing", "visualization"],
        "capabilities": ["CRUD", "batch"],
        "resources": ["drawings://{project_id}/"],
        "description": "Manage topology drawings (list, create, update, delete, batch)",
        "actions": ["list", "create", "update", "delete", "batch"],
    },
    "node_file": {
        "categories": ["docker", "node"],
        "capabilities": ["CRUD"],
        "resources": [],
        "description": "Manage Docker node files (read, write, configure network)",
        "actions": ["read", "write", "configure_network"],
    },
    "project_docs": {
        "categories": ["docs", "project"],
        "capabilities": ["CRUD"],
        "resources": ["projects://{id}/readme"],
        "description": "Manage project documentation/README (get, update)",
        "actions": ["get", "update"],
    },
    "console": {
        "categories": ["console", "device-access"],
        "capabilities": ["batch"],
        "resources": ["sessions://console/"],
        "description": "Execute console operations in batch (send, read, keystroke, send_and_wait)",
        "actions": ["batch"],
    },
    "ssh": {
        "categories": ["ssh", "device-access"],
        "capabilities": ["batch"],
        "resources": ["sessions://ssh/"],
        "description": "Execute SSH operations in batch (configure, command, disconnect)",
        "actions": ["batch"],
    },
    "query_resource": {
        "categories": ["resource", "query"],
        "capabilities": [],
        "resources": ["*"],
        "description": "Universal resource query tool - access any GNS3 MCP resource by URI",
        "actions": [],
    },
    "export_topology_diagram": {
        "categories": ["topology", "visualization", "export"],
        "capabilities": ["idempotent"],
        "resources": ["diagrams://{project_id}/topology"],
        "description": "Export topology diagram to SVG/PNG files on disk",
        "actions": [],
    },
}


@mcp.tool(
    name="search_tools",
    tags={"discovery", "search", "read-only"},
)
async def search_tools(
    ctx: Context,
    category: Annotated[
        str | None,
        "Filter by category: project, node, console, ssh, drawing, resource, docker, connection, docs, management, device-access, topology, visualization, discovery",
    ] = None,
    capability: Annotated[
        str | None, "Filter by capability: CRUD, batch, wildcard, parallel, idempotent"
    ] = None,
    resource_uri: Annotated[
        str | None,
        "Find tools applicable to resource URI (e.g., 'projects://', 'nodes://{project_id}/')",
    ] = None,
) -> str:
    """Discover GNS3 MCP tools (v0.47.0 - Tool Discovery)

    Search and filter available tools by category, capability, or resource URI.
    Returns tool metadata including description, actions, and applicable resources.

    **Categories:**
    - **project**: Project management (open, create, close)
    - **node**: Node management (create, delete, configure)
    - **connection**: Network connections and GNS3 server
    - **console**: Console access to devices
    - **ssh**: SSH access to devices
    - **drawing**: Topology visualization
    - **resource**: Resource query tools
    - **docker**: Docker-specific operations
    - **docs**: Documentation management
    - **topology**: Topology operations
    - **management**: Management operations
    - **device-access**: Device access (console/SSH)
    - **visualization**: Visual elements
    - **discovery**: Tool discovery

    **Capabilities:**
    - **CRUD**: Supports create/read/update/delete operations via action parameter
    - **batch**: Supports batch operations (multiple operations in one call)
    - **wildcard**: Supports wildcard patterns (*, Router*, R[123])
    - **parallel**: Supports parallel execution
    - **idempotent**: Multiple executions produce same result

    **Resource Mapping:**
    - **projects://**: project, list_projects, query_resource
    - **nodes://{project_id}/**: node, list_nodes, query_resource
    - **links://{project_id}/**: link, query_resource
    - **drawings://{project_id}/**: drawing, query_resource
    - **sessions://console/**: console, query_resource
    - **sessions://ssh/**: ssh, query_resource
    - **topology://{project_id}**: get_topology, query_resource

    Returns:
        JSON with matching tools and their metadata

    Examples:
        # Find all CRUD tools
        >>> search_tools(capability="CRUD")

        # Find tools for working with nodes
        >>> search_tools(category="node")

        # Find tools that work with projects:// resources
        >>> search_tools(resource_uri="projects://")

        # Find batch operation tools
        >>> search_tools(capability="batch")

        # Find tools with wildcard support
        >>> search_tools(capability="wildcard")
    """
    results = []

    for tool_name, metadata in TOOL_REGISTRY.items():
        # Filter by category
        if category and category.lower() not in metadata["categories"]:
            continue

        # Filter by capability
        if capability and capability.upper() not in metadata["capabilities"]:
            continue

        # Filter by resource URI
        if resource_uri:
            # Match resource URI patterns
            if "*" not in metadata["resources"]:  # "*" means matches all resources
                matched = False
                for resource_pattern in metadata["resources"]:
                    # Simple pattern matching (can be enhanced)
                    if resource_uri.startswith(resource_pattern.split("{")[0]):
                        matched = True
                        break
                if not matched:
                    continue

        # Add to results
        results.append(
            {
                "tool": tool_name,
                "description": metadata["description"],
                "categories": metadata["categories"],
                "capabilities": metadata["capabilities"],
                "actions": metadata["actions"],
                "resources": metadata["resources"],
            }
        )

    return json.dumps(
        {
            "query": {
                "category": category,
                "capability": capability,
                "resource_uri": resource_uri,
            },
            "total_results": len(results),
            "tools": results,
        },
        indent=2,
    )


# ============================================================================
# MCP Completions - Autocomplete Support
# ============================================================================
# NOTE: Completions currently disabled - FastMCP API for completions is different
# from standard MCP spec. Will be re-enabled once correct API is determined.
# See: https://github.com/anthropics/fastmcp/issues

# # Completion for node names
# # @mcp.completion("console_send", "node_name")
# # @mcp.completion("console_read", "node_name")
# # @mcp.completion("console_keystroke", "node_name")
# # @mcp.completion("console_disconnect", "node_name")
# # @mcp.completion("ssh_configure", "node_name")
# # @mcp.completion("ssh_command", "node_name")
# # @mcp.completion("ssh_disconnect", "node_name")
# # @mcp.completion("set_node", "node_name")
# # @mcp.completion("delete_node", "node_name")
# # async def complete_node_names_DISABLED(ctx: Context, prefix: str) -> list[Completion]:
# #     """Autocomplete node names from current project"""
# #     app: AppContext = ctx.request_context.lifespan_context
# #
# #     if not app.current_project_id:
# #         return []
# #
# #     try:
# #         nodes = await app.gns3.get_nodes(app.current_project_id)
# #
# #         # Filter by prefix
# #         matching = [n for n in nodes if n["name"].lower().startswith(prefix.lower())]
# #
# #         # Return completions
# #         return [
# #             Completion(
# #                 value=node["name"],
# #                 label=node["name"],
# #                 description=f"{node['node_type']} ({node['status']})"
# #             )
# #             for node in matching[:10]  # Limit to 10 results
# #         ]
# #
# #     except Exception as e:
# #         logger.warning(f"Failed to fetch nodes for completion: {e}")
# #         return []
# #
# #
# # # Completion for template names
# # @mcp.completion("create_node", "template_name")
# # async def complete_template_names_DISABLED(ctx: Context, prefix: str) -> list[Completion]:
# #     """Autocomplete template names"""
# #     app: AppContext = ctx.request_context.lifespan_context
# #
# #     try:
# #         templates = await app.gns3.get_templates()
# #
# #         matching = [t for t in templates if t["name"].lower().startswith(prefix.lower())]
# #
# #         return [
# #             Completion(
# #                 value=template["name"],
# #                 label=template["name"],
# #                 description=f"{template.get('category', 'Unknown')} - {template.get('node_type', '')}"
# #             )
# #             for template in matching[:10]
# #         ]
# #
# #     except Exception as e:
# #         logger.warning(f"Failed to fetch templates for completion: {e}")
# #         return []
# #
# #
# # # Completion for node actions (enum)
# # @mcp.completion("set_node", "action")
# # async def complete_node_actions_DISABLED(ctx: Context, prefix: str) -> list[Completion]:
# #     """Autocomplete node actions"""
# #     actions = [
# #         ("start", "Start the node"),
# #         ("stop", "Stop the node"),
# #         ("suspend", "Suspend the node"),
# #         ("reload", "Reload the node"),
# #         ("restart", "Restart the node (stop + start)")
# #     ]
# #
# #     matching = [(a, desc) for a, desc in actions if a.startswith(prefix.lower())]
# #
# #     return [
# #         Completion(value=action, label=action, description=desc)
# #         for action, desc in matching
# #     ]
# #
# #
# # # Completion for project names
# # @mcp.completion("open_project", "project_name")
# # async def complete_project_names_DISABLED(ctx: Context, prefix: str) -> list[Completion]:
# #     """Autocomplete project names"""
# #     app: AppContext = ctx.request_context.lifespan_context
# #
# #     try:
# #         projects = await app.gns3.get_projects()
# #
# #         matching = [p for p in projects if p["name"].lower().startswith(prefix.lower())]
# #
# #         return [
# #             Completion(
# #                 value=project["name"],
# #                 label=project["name"],
# #                 description=f"Status: {project['status']}"
# #             )
# #             for project in matching[:10]
# #         ]
# #
# #     except Exception as e:
# #         logger.warning(f"Failed to fetch projects for completion: {e}")
# #         return []
# #
# # # Completion for drawing types (enum)
# # @mcp.completion("create_drawing", "drawing_type")
# # async def complete_drawing_types_DISABLED(ctx: Context, prefix: str) -> list[Completion]:
# #     """Autocomplete drawing types"""
# #     drawing_types = [
# #         ("rectangle", "Create a rectangle shape"),
# #         ("ellipse", "Create an ellipse/circle shape"),
# #         ("line", "Create a line"),
# #         ("text", "Create a text label")
# #     ]
# #
# #     matching = [(dt, desc) for dt, desc in drawing_types if dt.startswith(prefix.lower())]
# #
# #     return [
# #         Completion(value=dtype, label=dtype, description=desc)
# #         for dtype, desc in matching
# #     ]
# #
# #
# # # Completion for topology types (enum)
# # @mcp.completion("lab_setup", "topology_type")
# # async def complete_topology_types_DISABLED(ctx: Context, prefix: str) -> list[Completion]:
# #     """Autocomplete topology types"""
# #     topology_types = [
# #         ("star", "Hub-and-spoke topology (device_count = spokes)"),
# #         ("mesh", "Full mesh topology (all routers interconnected)"),
# #         ("linear", "Chain topology (routers in series)"),
# #         ("ring", "Circular topology (closes the loop)"),
# #         ("ospf", "Multi-area OSPF topology (device_count = areas)"),
# #         ("bgp", "Multiple AS topology (device_count = AS, 2 routers per AS)")
# #     ]
# #
# #     matching = [(tt, desc) for tt, desc in topology_types if tt.startswith(prefix.lower())]
# #
# #     return [
# #         Completion(value=ttype, label=ttype, description=desc)
# #         for ttype, desc in matching
# #     ]


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="GNS3 MCP Server")

    # GNS3 connection arguments
    parser.add_argument("--host", default="localhost", help="GNS3 server host")
    parser.add_argument("--port", type=int, default=80, help="GNS3 server port")
    parser.add_argument("--username", default="admin", help="GNS3 username")
    parser.add_argument(
        "--password", default="", help="GNS3 password (or use PASSWORD/GNS3_PASSWORD env var)"
    )
    parser.add_argument(
        "--use-https",
        action="store_true",
        help="Use HTTPS for GNS3 connection (or set GNS3_USE_HTTPS=true)",
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
        help="MCP transport mode: stdio (process-based, default), http (Streamable HTTP, recommended for network), sse (legacy SSE, deprecated)",
    )
    parser.add_argument(
        "--http-host",
        default="127.0.0.1",
        help="HTTP server host (only for http/sse transport, default: 127.0.0.1)",
    )
    parser.add_argument(
        "--http-port",
        type=int,
        default=8000,
        help="HTTP server port (only for http/sse transport, default: 8000)",
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

        print(
            f"Starting MCP server with HTTP transport at http://{args.http_host}:{args.http_port}/mcp/"
        )

        # Create ASGI app for HTTP transport
        app = mcp.http_app()

        # Add API key authentication middleware (CWE-306 fix)
        api_key = os.getenv("MCP_API_KEY")
        if not api_key:
            raise ValueError(
                "MCP_API_KEY required for HTTP transport (set in .env). "
                'Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"'
            )

        @app.middleware("http")
        async def verify_api_key(request: Request, call_next):
            """Verify MCP_API_KEY header for all HTTP requests (except health/status)"""
            # Skip auth for health/status endpoints (if any)
            if request.url.path in ["/health", "/status"]:
                return await call_next(request)

            # Check API key header (case-insensitive)
            client_key = request.headers.get("MCP_API_KEY") or request.headers.get("mcp_api_key")
            if client_key != api_key:
                return JSONResponse(
                    status_code=401,
                    content={
                        "error": "Unauthorized",
                        "detail": "Invalid or missing MCP_API_KEY header. "
                        "Add header: 'MCP_API_KEY: <your-key-from-env>'",
                    },
                )
            return await call_next(request)

        print("✓ API key authentication enabled (MCP_API_KEY required)")

        # Run with uvicorn
        uvicorn.run(app, host=args.http_host, port=args.http_port, log_level="info")
    elif args.transport == "sse":
        # Legacy SSE transport (deprecated, use HTTP instead)
        import uvicorn

        print("WARNING: SSE transport is deprecated. Consider using --transport http instead.")
        print(
            f"Starting MCP server with SSE transport at http://{args.http_host}:{args.http_port}/sse"
        )

        # Create ASGI app for SSE transport
        app = mcp.sse_app()

        # Run with uvicorn
        uvicorn.run(app, host=args.http_host, port=args.http_port, log_level="info")
