"""GNS3 MCP server

GNS3 lab automation with AI agent
"""

import argparse
import asyncio
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any, Dict, List, Optional

from console_manager import ConsoleManager
from export_tools import (
    export_topology_diagram,
)
from fastmcp import Context, FastMCP
from gns3_client import GNS3Client
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
from resources import ResourceManager
from tools.console_tools import (
    console_batch_impl,
    disconnect_console_impl,
    read_console_impl,
    send_and_wait_console_impl,
    send_console_impl,
    send_keystroke_impl,
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

# Read version from manifest.json (single source of truth)
MANIFEST_PATH = Path(__file__).parent.parent / "manifest.json"
try:
    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)
        VERSION = manifest["version"]
except Exception as e:
    # Fallback version if manifest read fails (not a string literal to avoid pre-commit hook detection)
    VERSION = f"{0}.{20}.{0}"
    print(f"Warning: Could not read version from manifest.json: {e}")

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
    """Application context with GNS3 client, console manager, and resource manager"""
    gns3: GNS3Client
    console: ConsoleManager
    resource_manager: Optional[ResourceManager] = None
    current_project_id: str | None = None
    cleanup_task: Optional[asyncio.Task] = field(default=None)
    # v0.26.0: Multi-proxy SSH support - maps node_name to proxy_url for routing
    ssh_proxy_mapping: Dict[str, str] = field(default_factory=dict)


# Global app context for static resources (set during lifespan)
_app: Optional[AppContext] = None


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

    # Initialize console manager first (no dependencies)
    console = ConsoleManager()

    # Start periodic cleanup task
    cleanup_task = asyncio.create_task(periodic_console_cleanup(console))

    # Try initial authentication (max 3 attempts)
    # If fails, continue initialization - auth will retry in background on first API call
    try:
        await gns3.authenticate(retry=True, retry_interval=5, max_retries=3)
        logger.info("Successfully authenticated with GNS3 server")

        # Auto-detect opened project
        projects = await gns3.get_projects()
        opened = [p for p in projects if p.get("status") == "opened"]
        current_project_id = opened[0]["project_id"] if opened else None

        if current_project_id:
            logger.info(f"Auto-detected opened project: {opened[0]['name']}")
        else:
            logger.warning("No opened project found - some tools require opening a project first")
    except Exception as e:
        logger.warning(f"Initial authentication failed: {e}")
        logger.warning("MCP server will continue starting - tools will retry authentication as needed")
        current_project_id = None

    # Create context (resource_manager needs context, so create first then update)
    context = AppContext(
        gns3=gns3,
        console=console,
        current_project_id=current_project_id,
        cleanup_task=cleanup_task
    )

    # Initialize resource manager (needs context for callbacks)
    context.resource_manager = ResourceManager(context)

    # Set global app for static resources
    global _app
    _app = context

    try:
        yield context
    finally:
        _app = None  # Clear global on shutdown
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
    """Validate that current project is still open, with auto-connect to opened projects

    If no project is connected but one is opened in GNS3, automatically connects to it.
    This provides seamless UX when projects are opened via GNS3 GUI.

    Args:
        app: Application context

    Returns:
        Error message if invalid, None if valid
    """
    try:
        # Get project list directly from API
        projects = await app.gns3.get_projects()

        # If no project connected, try to auto-connect to opened project
        if not app.current_project_id:
            opened = [p for p in projects if p.get("status") == "opened"]

            if not opened:
                return json.dumps(ErrorResponse(
                    error="No project opened in GNS3",
                    details="No projects are currently opened. Open a project in GNS3 or use open_project()",
                    suggested_action="Open a project in GNS3 GUI, or call list_projects() then open_project(project_name)"
                ).model_dump(), indent=2)

            # Auto-connect to the first opened project
            app.current_project_id = opened[0]["project_id"]
            logger.info(f"Auto-connected to opened project: {opened[0]['name']} ({opened[0]['project_id']})")

            if len(opened) > 1:
                logger.warning(f"Multiple projects opened ({len(opened)}), connected to: {opened[0]['name']}")

            return None  # Successfully auto-connected

        # Validate that connected project still exists and is opened
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
    lifespan=app_lifespan
)


# ============================================================================
# MCP Resources - Browsable State
# ============================================================================

# Project resources
@mcp.resource("projects://",
    name="Projects",
    title="GNS3 projects list",
    description="List all GNS3 projects with their statuses and IDs",
    mime_type="text/plain"
)
async def resource_projects() -> str:
    """List all GNS3 projects with their statuses and IDs"""
    return await _app.resource_manager.list_projects()

@mcp.resource("projects://{project_id}",
    name="Project details",  # human-readable name
    title="GNS3 project details", # human-readable name
    description="Details for a specific GNS3 project", # defaults to docsctring
    mime_type="text/plain",
)
async def resource_project(ctx: Context, project_id: str) -> str:
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.get_project(project_id)

@mcp.resource("nodes://{project_id}/",
    name="Project nodes",
    title="GNS3 project nodes list",
    description="List all nodes (devices) in a specific GNS3 project with status and basic info",
    mime_type="text/plain"
)
async def resource_nodes(ctx: Context, project_id: str) -> str:
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.list_nodes(project_id)

@mcp.resource("nodes://{project_id}/{node_id}",
    name="Node details",
    title="GNS3 node details",
    description="Detailed information about a specific node including status, coordinates, console settings, and properties",
    mime_type="application/json"
)
async def resource_node(ctx: Context, project_id: str, node_id: str) -> str:
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.get_node(project_id, node_id)

@mcp.resource("links://{project_id}/",
    name="Project links",
    title="GNS3 project network links",
    description="List all network links (connections) between nodes in a specific project",
    mime_type="text/plain"
)
async def resource_links(ctx: Context, project_id: str) -> str:
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.list_links(project_id)

@mcp.resource("templates://",
    name="Templates",
    title="GNS3 templates list",
    description="List all available GNS3 device templates (routers, switches, Docker containers, VMs)",
    mime_type="text/plain"
)
async def resource_templates() -> str:
    """List all available GNS3 templates"""
    return await _app.resource_manager.list_templates()

@mcp.resource("drawings://{project_id}/",
    name="Project drawings",
    title="GNS3 project drawing objects",
    description="List all drawing objects (rectangles, ellipses, lines, text labels) in a specific project",
    mime_type="text/plain"
)
async def resource_drawings(ctx: Context, project_id: str) -> str:
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.list_drawings(project_id)

# REMOVED v0.29.0 - Snapshot resources removed (planned for future reimplementation)
# Snapshot functionality requires additional work to properly handle GNS3 v3 API snapshot operations

@mcp.resource("projects://{project_id}/readme",
    name="Project README",
    title="GNS3 project README/notes",
    description="Project documentation in markdown - IP schemes, credentials, architecture notes, troubleshooting guides",
    mime_type="text/markdown"
)
async def resource_project_readme(ctx: Context, project_id: str) -> str:
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.get_project_readme(project_id)

@mcp.resource("projects://{project_id}/sessions/console/",
    name="Project console sessions",
    title="Active console sessions for project",
    description="List all active console (telnet) sessions for nodes in a specific project",
    mime_type="text/plain"
)
async def resource_console_sessions(ctx: Context, project_id: str) -> str:
    """List console sessions for project nodes"""
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.list_console_sessions(project_id)

@mcp.resource("projects://{project_id}/sessions/ssh/",
    name="Project SSH sessions",
    title="Active SSH sessions for project",
    description="List all active SSH sessions for nodes in a specific project",
    mime_type="text/plain"
)
async def resource_ssh_sessions(ctx: Context, project_id: str) -> str:
    """List SSH sessions for project nodes"""
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.list_ssh_sessions(project_id)

# Template resources
@mcp.resource("templates://{template_id}",
    name="Template details",
    title="GNS3 template details",
    description="Detailed information about a specific template including properties, default settings, and usage notes",
    mime_type="application/json"
)
async def resource_template(ctx: Context, template_id: str) -> str:
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.get_template(template_id)

@mcp.resource("nodes://{project_id}/{node_id}/template",
    name="Node template usage",
    title="Template usage notes for node",
    description="Template-specific configuration hints and usage notes for this node instance",
    mime_type="text/markdown"
)
async def resource_node_template(ctx: Context, project_id: str, node_id: str) -> str:
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.get_node_template_usage(project_id, node_id)

# Session list resources (support query param: ?project_id=xxx)
@mcp.resource("sessions://console/",
    name="Console sessions",
    title="All console sessions",
    description="List all console sessions (optionally filtered by ?project_id=xxx query parameter)",
    mime_type="text/plain"
)
async def resource_console_sessions_all() -> str:
    return await _app.resource_manager.list_console_sessions()

@mcp.resource("sessions://ssh/",
    name="SSH sessions",
    title="All SSH sessions",
    description="List all SSH sessions (optionally filtered by ?project_id=xxx query parameter)",
    mime_type="text/plain"
)
async def resource_ssh_sessions_all() -> str:
    return await _app.resource_manager.list_ssh_sessions()

# Console session resources (node-specific templates only)
@mcp.resource("sessions://console/{node_name}",
    name="Console session",
    title="Console session for node",
    description="Console session state and buffer for a specific node - connection status and recent output",
    mime_type="application/json"
)
async def resource_console_session(ctx: Context, node_name: str) -> str:
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.get_console_session(node_name)

# SSH session resources (node-specific templates only)
@mcp.resource("sessions://ssh/{node_name}",
    name="SSH session",
    title="SSH session for node",
    description="SSH session state for a specific node - connection status, device type, and proxy routing",
    mime_type="application/json"
)
async def resource_ssh_session(ctx: Context, node_name: str) -> str:
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.get_ssh_session(node_name)

@mcp.resource("sessions://ssh/{node_name}/history",
    name="SSH command history",
    title="SSH command history for node",
    description="Command history for a specific node's SSH session - chronological list of executed commands",
    mime_type="application/json"
)
async def resource_ssh_history(ctx: Context, node_name: str) -> str:
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.get_ssh_history(node_name)

@mcp.resource("sessions://ssh/{node_name}/buffer",
    name="SSH output buffer",
    title="SSH output buffer for node",
    description="Accumulated SSH output buffer for a specific node - recent command outputs and console text",
    mime_type="text/plain"
)
async def resource_ssh_buffer(ctx: Context, node_name: str) -> str:
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.get_ssh_buffer(node_name)

# SSH proxy resources
@mcp.resource("proxies:///status",
    name="Main proxy status",
    title="SSH proxy service status",
    description="Health status and version of the main SSH proxy on GNS3 host (default proxy for ssh_configure)",
    mime_type="application/json"
)
async def resource_proxy_status() -> str:
    """Get SSH proxy service status (main proxy on GNS3 host)

    Returns health status and version of the main SSH proxy running on the GNS3 host.
    This is the default proxy used when ssh_configure() is called without a proxy parameter.
    """
    return await _app.resource_manager.get_proxy_status()

@mcp.resource("proxies://",
    name="Lab proxy registry",
    title="Discovered lab SSH proxies",
    description="All discovered SSH proxy containers in GNS3 lab projects - use proxy_id for routing through isolated networks",
    mime_type="text/plain"
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
    return await _app.resource_manager.get_proxy_registry()

@mcp.resource("proxies://sessions",
    name="All proxy sessions",
    title="SSH sessions across all proxies",
    description="Aggregated list of ALL active SSH sessions from main proxy and lab proxies - global lab infrastructure view",
    mime_type="text/plain"
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
    return await _app.resource_manager.list_proxy_sessions()

# Proxy resource templates (project-scoped)
@mcp.resource("proxies://project/{project_id}",
    name="Project proxies",
    title="Lab proxies for project",
    description="SSH proxy containers running in a specific GNS3 project - filtered view of proxy registry",
    mime_type="application/json"
)
async def resource_project_proxies(ctx: Context, project_id: str) -> str:
    """List lab proxies for specific project (filtered view of registry)

    Returns only the SSH proxy containers running in the specified GNS3 project.
    Useful for project-specific proxy discovery without seeing proxies from other projects.
    """
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.list_project_proxies(project_id)

@mcp.resource("proxies://{proxy_id}",
    name="Proxy details",
    title="Lab proxy details",
    description="Detailed information about a specific lab proxy - container details, network config, connection info",
    mime_type="application/json"
)
async def resource_proxy(ctx: Context, proxy_id: str) -> str:
    """Get detailed information about a specific lab proxy

    Returns full details for a lab proxy identified by its proxy_id (GNS3 node_id).
    Includes container details, network configuration, and connection information.
    """
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.get_proxy(proxy_id)


# Diagram resources
@mcp.resource("diagrams://{project_id}/topology",
    name="Topology diagram",
    title="Visual topology diagram (SVG/PNG)",
    description="Generated topology diagram as image - shows nodes, links, status indicators. Only access if agent can process visual information.",
    mime_type="image/svg+xml"
)
async def resource_topology_diagram(ctx: Context, project_id: str) -> str:
    """Generate topology diagram as SVG/PNG image (agent-friendly access)

    Returns visual topology diagram without saving to disk. Agents can access
    diagrams directly if they can process visual information (SVG/PNG formats).

    Query parameters:
    - format: "svg" (default) or "png" - output format
    - dpi: DPI for PNG rendering (default: 150, range: 72-300)

    SVG format is preferred for agents (scalable, smaller, faster).
    PNG format is rasterized at specified DPI.

    ⚠️ Visual Resource Warning:
    This resource returns image data. Only access if you can process visual
    information and need node physical locations. Text-based resources
    (nodes, links, drawings) provide same data in structured format.

    Example URIs:
    - diagrams://abc123/topology - SVG diagram (default)
    - diagrams://abc123/topology?format=png&dpi=300 - High-res PNG

    For humans: Use export_topology_diagram() tool to save files to disk.
    """
    from export_tools import generate_topology_diagram_content

    app: AppContext = ctx.request_context.lifespan_context

    # Parse query parameters from URI
    uri = ctx.meta.get("uri", "")
    format_param = "svg"  # default
    dpi = 150  # default

    if "?" in uri:
        query_str = uri.split("?")[1]
        for param in query_str.split("&"):
            if "=" in param:
                key, value = param.split("=", 1)
                if key == "format":
                    format_param = value.lower()
                elif key == "dpi":
                    try:
                        dpi = int(value)
                        dpi = max(72, min(300, dpi))  # Clamp to 72-300
                    except ValueError:
                        pass

    try:
        # Generate diagram content (SVG string or PNG bytes)
        content, mime_type = await generate_topology_diagram_content(
            app, project_id, format_param, dpi
        )

        # Return content with appropriate MIME type
        # Note: MCP resource returns string, so PNG will be base64-encoded
        return content

    except Exception as e:
        error_response = ErrorResponse(
            error="Failed to generate topology diagram",
            details=str(e)
        )
        return json.dumps(error_response.model_dump(), indent=2)


# ============================================================================
# MCP Prompts - Guided Workflows
# ============================================================================

@mcp.prompt(
    name="SSH Setup Workflow",
    title="Enable SSH on network devices",
    description="Device-specific SSH configuration for 6 device types with multi-proxy support",
    tags={"workflow", "ssh", "setup", "device-access", "guided"}
)
async def ssh_setup(
    node_name: Annotated[str, "Target node name to configure"],
    device_type: Annotated[str, "Device type (cisco_ios, cisco_nxos, mikrotik_routeros, juniper_junos, arista_eos, linux)"],
    username: Annotated[str, "SSH username to create"] = "admin",
    password: Annotated[str, "SSH password to set"] = "admin"
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
    tags={"workflow", "discovery", "visualization", "read-only", "guided"}
)
async def topology_discovery(
    project_name: Annotated[Optional[str], "Optional project name to focus on (default: guide user to select)"] = None,
    include_export: Annotated[bool, "Include export/visualization steps (default: True)"] = True
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
    tags={"workflow", "troubleshooting", "diagnostics", "guided"}
)
async def troubleshooting(
    node_name: Annotated[Optional[str], "Optional node name to focus troubleshooting on"] = None,
    issue_type: Annotated[Optional[str], "Optional issue category (connectivity, console, ssh, performance)"] = None
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
    tags={"workflow", "topology", "automation", "creates-resource", "guided"}
)
async def lab_setup(
    topology_type: Annotated[str, "Topology type (star, mesh, linear, ring, ospf, bgp)"],
    device_count: Annotated[int, "Number of devices (spokes for star, areas for OSPF, AS for BGP)"],
    template_name: Annotated[str, "GNS3 template to use"] = "Alpine Linux",
    project_name: Annotated[str, "Name for the new project"] = "Lab Topology"
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
    tags={"workflow", "setup", "node", "automation", "guided"}
)
async def node_setup(
    node_name: Annotated[str, "Name for the new node (e.g., 'Router1')"],
    template_name: Annotated[str, "GNS3 template to use (e.g., 'Cisco IOSv', 'Alpine Linux')"],
    ip_address: Annotated[str, "Management IP to assign (e.g., '192.168.1.10')"],
    subnet_mask: Annotated[str, "Subnet mask"] = "255.255.255.0",
    device_type: Annotated[str, "Device type for SSH"] = "cisco_ios",
    username: Annotated[str, "SSH username to create"] = "admin",
    password: Annotated[str, "SSH password to set"] = "admin"
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
        password=password
    )


# ============================================================================
# MCP Tools - Actions That Modify State
# ============================================================================

@mcp.tool(
    name="Open project",
    tags={"project", "management", "idempotent"},
    annotations={"idempotent": True}
)
async def open_project(
    ctx: Context,
    project_name: Annotated[str, "Name of the project to open"],
) -> str:
    """Open a GNS3 project by name

    Returns: JSON with ProjectInfo for opened project
    """
    app: AppContext = ctx.request_context.lifespan_context
    return await open_project_impl(app, project_name)


@mcp.tool(
    name="Create project",
    tags={"project", "management", "creates-resource", "idempotent"},
    annotations={"idempotent": True, "creates_resource": True}
)
async def create_project(
    ctx: Context,
    name: Annotated[str, "Project name"],
    path: Annotated[str | None, "Optional project directory path"] = None
) -> str:
    """Create a new GNS3 project and auto-open it

    Returns: JSON with ProjectInfo for created project

    Example:
        >>> create_project("My Lab")
        >>> create_project("Production Lab", "/opt/gns3/projects")
    """
    app: AppContext = ctx.request_context.lifespan_context
    return await create_project_impl(app, name, path)


@mcp.tool(
    name="Close project",
    tags={"project", "management", "idempotent"},
    annotations={"idempotent": True}
)
async def close_project(ctx: Context) -> str:
    """Close the currently opened project

    Returns: JSON with success message

    Example:
        >>> close_project()
    """
    app: AppContext = ctx.request_context.lifespan_context
    return await close_project_impl(app)


@mcp.tool(
    name="Set node properties",
    tags={"node", "topology", "modifies-state", "idempotent"},
    annotations={"idempotent": True}
)
async def set_node(
    ctx: Context,
    node_name: Annotated[str, "Name of the node to modify"],
    action: Annotated[str | None, "Action: start/stop/suspend/reload/restart"] = None,
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
    console_type: Annotated[str | None, "Console type: telnet/vnc/spice"] = None
) -> str:
    """Configure node properties and/or control node state

    Validation Rules:
    - name parameter requires node to be stopped
    - Hardware properties (ram, cpus, hdd_disk_image, adapters) apply to QEMU nodes only
    - ports parameter applies to ethernet_switch nodes only
    - action values: start, stop, suspend, reload, restart
    - restart action: stops node (with retry logic), waits for confirmed stop, then starts

    Returns: Status message describing what was done
    """
    app: AppContext = ctx.request_context.lifespan_context
    return await set_node_impl(
        app, node_name, action, x, y, z, locked, ports,
        name, ram, cpus, hdd_disk_image, adapters, console_type
    )


@mcp.tool(
    name="Send console data",
    tags={"console", "device-access", "modifies-state"}
)
async def console_send(
    ctx: Context,
    node_name: Annotated[str, "Name of the node (e.g., 'Router1')"],
    data: Annotated[str, "Data to send - include newline for commands (e.g., 'enable\\n')"],
    raw: Annotated[bool, "Send data without escape sequence processing"] = False
) -> str:
    """Send data to console (auto-connects if needed)

    IMPORTANT: Prefer SSH tools when available! Console tools are primarily for:
    - Initial device configuration (enabling SSH, creating users)
    - Troubleshooting when SSH is unavailable
    - Devices without SSH support (VPCS, simple switches)

    For automation workflows, use ssh_command() which provides better
    reliability, error handling, and automatic prompt detection.

    Sends data immediately to console without waiting for response.
    For interactive workflows, use console_read() after sending to verify output.

    Timing Considerations:
    - Console output appears in background buffer (read via console_read)
    - Allow 0.5-2 seconds after send before reading for command processing
    - Interactive prompts (login, password) may need 1-3 seconds to appear
    - Boot/initialization sequences may take 30-60 seconds

    Auto-connect Behavior:
    - First send/read automatically connects to console (no manual connect needed)
    - Connection persists until console_disconnect() or 30-minute timeout
    - Check connection state with resource gns3://sessions/console/{node}

    Escape Sequence Processing:
    - By default, processes common escape sequences (\n, \r, \t, \x1b)
    - Use raw=True to send data without processing (for binary data)

    Returns: "Sent successfully" or error message

    Example - Wake console and check state:
        console_send("R1", "\n")
        await 1 second
        console_read("R1", mode="diff")  # See what prompt appeared
    """
    app: AppContext = ctx.request_context.lifespan_context
    return await send_console_impl(app, node_name, data, raw)


@mcp.tool(
    name="Read console output",
    tags={"console", "device-access", "read-only"},
    annotations={"read_only": True}
)
async def console_read(
    ctx: Context,
    node_name: Annotated[str, "Name of the node"],
    mode: Annotated[str, "Output mode: diff/last_page/num_pages/all"] = "diff",
    pages: Annotated[int, "Number of pages (only with mode='num_pages')"] = 1,
    pattern: Annotated[str | None, "Regex pattern to filter output"] = None,
    case_insensitive: Annotated[bool, "Case-insensitive matching (grep -i)"] = False,
    invert: Annotated[bool, "Invert match (grep -v)"] = False,
    before: Annotated[int, "Context lines before match (grep -B)"] = 0,
    after: Annotated[int, "Context lines after match (grep -A)"] = 0,
    context: Annotated[int, "Context lines around match (grep -C)"] = 0
) -> str:
    """Read console output with optional grep filtering (auto-connects if needed)

    IMPORTANT: Prefer SSH tools when available! Console tools are primarily for:
    - Initial device configuration (enabling SSH, creating users)
    - Troubleshooting when SSH is unavailable
    - Devices without SSH support

    For automation workflows, use ssh_command() which provides better
    reliability and structured output.

    Reads accumulated output from background console buffer. Output accumulates
    while device runs - this function retrieves it without blocking.

    Buffer Behavior:
    - Background task continuously reads console into 10MB buffer
    - Diff mode (DEFAULT): Returns only NEW output since last read
    - Last page mode: Returns last ~25 lines of buffer
    - Num pages mode: Returns last N pages (~25 lines per page)
    - All mode: Returns ALL console output since connection (WARNING: May produce >25000 tokens!)
    - Read position advances with each diff mode read

    Grep Parameters (optional):
    - pattern: Regex pattern to filter output (returns matching lines with line numbers)
    - case_insensitive: Ignore case when matching (grep -i)
    - invert: Return non-matching lines (grep -v)
    - before/after/context: Context lines around matches (grep -B/-A/-C)

    Returns: Console output (filtered if pattern provided)

    Example - Grep for errors:
        console_read("R1", mode="all", pattern="error", case_insensitive=True)

    Example - Find interface with context:
        console_read("R1", mode="diff", pattern="GigabitEthernet", context=2)
    """
    app: AppContext = ctx.request_context.lifespan_context
    return await read_console_impl(app, node_name, mode, pages, pattern, case_insensitive, invert, before, after, context)


@mcp.tool(
    name="Disconnect console",
    tags={"console", "device-access", "idempotent"},
    annotations={"idempotent": True}
)
async def console_disconnect(
    ctx: Context,
    node_name: Annotated[str, "Name of the node"]
) -> str:
    """Disconnect console session

    Returns: JSON with status
    """
    app: AppContext = ctx.request_context.lifespan_context
    return await disconnect_console_impl(app, node_name)


@mcp.tool(
    name="Send console keystroke",
    tags={"console", "device-access", "modifies-state"}
)
async def console_keystroke(
    ctx: Context,
    node_name: Annotated[str, "Name of the node"],
    key: Annotated[str, "Special key to send (e.g., 'up', 'enter', 'ctrl_c')"]
) -> str:
    """Send special keystroke to console (auto-connects if needed)

    IMPORTANT: Prefer SSH tools when available! Console tools are primarily for:
    - Initial device configuration (enabling SSH, creating users)
    - Troubleshooting when SSH is unavailable
    - Devices without SSH support (VPCS, simple switches)

    Sends special keys like arrows, function keys, control sequences for
    navigating menus, editing in vim, or TUI applications.

    Supported Keys:
    - Navigation: "up", "down", "left", "right", "home", "end", "pageup", "pagedown"
    - Editing: "enter", "backspace", "delete", "tab", "esc"
    - Control: "ctrl_c", "ctrl_d", "ctrl_z", "ctrl_a", "ctrl_e"
    - Function: "f1" through "f12"

    Returns: "Sent successfully" or error message

    Example - Navigate menu:
        send_keystroke("R1", "down")
        send_keystroke("R1", "down")
        send_keystroke("R1", "enter")

    Example - Exit vim:
        send_keystroke("R1", "esc")
        send_console("R1", ":wq\n")
    """
    app: AppContext = ctx.request_context.lifespan_context
    return await send_keystroke_impl(app, node_name, key)


@mcp.tool(
    name="Send console command and wait",
    tags={"console", "device-access", "automation"}
)
async def console_send_and_wait(
    ctx: Context,
    node_name: Annotated[str, "Name of the node"],
    command: Annotated[str, "Command to send (include \\n for newline)"],
    wait_pattern: Annotated[str | None, "Regex pattern to wait for (e.g., 'Router#')"] = None,
    timeout: Annotated[int, "Maximum seconds to wait for pattern"] = 30,
    raw: Annotated[bool, "Send command without escape sequence processing"] = False
) -> str:
    """Send command and wait for prompt pattern with timeout

    IMPORTANT: Prefer SSH tools when available! Console tools are primarily for:
    - Initial device configuration (enabling SSH, creating users)
    - Troubleshooting when SSH is unavailable
    - Devices without SSH support (VPCS, simple switches)

    Combines send + wait + read into single operation. Useful for interactive
    workflows where you need to verify prompt before proceeding.

    BEST PRACTICE: Check the prompt first!
    1. Send "\\n" with console_send() to wake the console
    2. Use console_read() to see the current prompt (e.g., "Router#", "[admin@MikroTik] >")
    3. Use that exact prompt pattern in wait_pattern parameter
    4. This ensures you wait for the right prompt and don't miss command output

    Returns:
        JSON with output, pattern_found, timeout_occurred, wait_time

    Examples:
        # Step 1: Check the prompt first
        console_send("R1", "\\n")
        output = console_read("R1")  # Shows "Router#"

        # Step 2: Use that prompt pattern
        result = console_send_and_wait(
            "R1",
            "show ip interface brief\\n",
            wait_pattern="Router#",  # Wait for exact prompt
            timeout=10
        )
        # Returns when "Router#" appears - command is complete

        # Wait for login prompt:
        console_send_and_wait("R1", "\\n", wait_pattern="Login:", timeout=10)

        # No pattern (just wait 2s):
        console_send_and_wait("R1", "enable\\n")
    """
    app: AppContext = ctx.request_context.lifespan_context
    return await send_and_wait_console_impl(app, node_name, command, wait_pattern, timeout, raw)


@mcp.tool(
    name="Console batch operations",
    tags={"console", "device-access", "bulk", "automation"}
)
async def console_batch(
    ctx: Context,
    operations: Annotated[List[Dict[str, Any]], "List of console operations (send/send_and_wait/read/keystroke)"]
) -> str:
    """Execute multiple console operations in batch with validation

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

    - "read": Read console output
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
        console_batch([
            {"type": "send_and_wait", "node_name": "R1", "command": "show version\\n", "wait_pattern": "Router#"},
            {"type": "send_and_wait", "node_name": "R1", "command": "show ip route\\n", "wait_pattern": "Router#"},
            {"type": "read", "node_name": "R1", "mode": "diff"}
        ])

        # Same command on multiple nodes:
        console_batch([
            {"type": "send_and_wait", "node_name": "R1", "command": "show ip int brief\\n", "wait_pattern": "#"},
            {"type": "send_and_wait", "node_name": "R2", "command": "show ip int brief\\n", "wait_pattern": "#"},
            {"type": "send_and_wait", "node_name": "R3", "command": "show ip int brief\\n", "wait_pattern": "#"}
        ])

        # Mixed operations:
        console_batch([
            {"type": "send", "node_name": "R1", "data": "\\n"},  // Wake console
            {"type": "read", "node_name": "R1", "mode": "last_page"},  // Check prompt
            {"type": "send_and_wait", "node_name": "R1", "command": "show version\\n", "wait_pattern": "#"},
            {"type": "keystroke", "node_name": "R1", "key": "ctrl_c"}  // Cancel if needed
        ])
    """
    app: AppContext = ctx.request_context.lifespan_context
    return await console_batch_impl(app, operations)


@mcp.tool(
    name="Set network connections",
    tags={"network", "topology", "bulk", "modifies-state"},
    annotations={"modifies_topology": True}
)
async def set_connection(
    ctx: Context,
    connections: Annotated[List[Dict[str, Any]], "List of connection operations (connect/disconnect)"]
) -> str:
    """Manage network connections (links) in batch with two-phase validation

    Two-phase execution prevents partial topology changes:
    1. VALIDATE ALL operations (check nodes exist, ports free, adapters valid)
    2. EXECUTE ALL operations (only if all valid - atomic)

    Workflow:
        1. Call get_links() to see current topology
        2. Identify link IDs to disconnect (if needed)
        3. Call set_connection() with disconnect + connect operations

    Connection Operations:
        Connect: {action: "connect", node_a, node_b, port_a, port_b, adapter_a, adapter_b}
        Disconnect: {action: "disconnect", link_id}

    Returns: JSON with OperationResult (completed and failed operations)
    """
    app: AppContext = ctx.request_context.lifespan_context

    error = await validate_current_project(app)
    if error:
        return error

    return await set_connection_impl(app, connections)


@mcp.tool(
    name="Create node",
    tags={"node", "topology", "creates-resource"},
    annotations={"creates_resource": True, "modifies_topology": True}
)
async def create_node(
    ctx: Context,
    template_name: Annotated[str, "Template name (e.g., 'Alpine Linux', 'Cisco IOSv')"],
    x: Annotated[int, "X coordinate (horizontal position, left edge of icon)"],
    y: Annotated[int, "Y coordinate (vertical position, top edge of icon)"],
    node_name: Annotated[str | None, "Custom name (defaults to template name with auto-number)"] = None,
    compute_id: Annotated[str, "Compute server ID"] = "local",
    properties: Annotated[Dict[str, Any] | None, "Override template properties (e.g., {'ram': 512})"] = None
) -> str:
    """Create a new node from template at specified coordinates

    Creates a node from a GNS3 template and places it at the given x/y position.
    Optional properties can override template defaults.

    Returns: JSON with created NodeInfo

    Example:
        >>> create_node("Alpine Linux", 100, 200)
        >>> create_node("Cisco IOSv", 300, 400, node_name="R1", properties={"ram": 1024})
        >>> create_node("Ethernet switch", 500, 600, node_name="SW1")
    """
    app: AppContext = ctx.request_context.lifespan_context

    error = await validate_current_project(app)
    if error:
        return error

    return await create_node_impl(app, template_name, x, y, node_name, compute_id, properties)


@mcp.tool(
    name="Delete node",
    tags={"node", "topology", "destructive", "idempotent"},
    annotations={"destructive": True, "idempotent": True, "modifies_topology": True}
)
async def delete_node(
    ctx: Context,
    node_name: Annotated[str, "Name of the node to delete"]
) -> str:
    """Delete a node from the current project

    WARNING: This operation is destructive and cannot be undone.

    Returns: JSON confirmation message
    """
    app: AppContext = ctx.request_context.lifespan_context

    error = await validate_current_project(app)
    if error:
        return error

    return await delete_node_impl(app, node_name)


@mcp.tool(
    name="Get node file",
    tags={"node", "read-only"}
)
async def get_node_file(
    ctx: Context,
    node_name: Annotated[str, "Name of the Docker node"],
    file_path: Annotated[str, "Path relative to container root (e.g., 'etc/network/interfaces')"]
) -> str:
    """Read file from Docker node filesystem

    Allows reading files from Docker node containers. Useful for inspecting
    configuration files, logs, or other data inside containers.

    Returns: JSON with file contents

    Example:
        get_node_file("A-PROXY", "etc/network/interfaces")
    """
    app: AppContext = ctx.request_context.lifespan_context

    error = await validate_current_project(app)
    if error:
        return error

    return await get_node_file_impl(app, node_name, file_path)


@mcp.tool(
    name="Write node file",
    tags={"node", "modifies-state"}
)
async def write_node_file(
    ctx: Context,
    node_name: Annotated[str, "Name of the Docker node"],
    file_path: Annotated[str, "Path relative to container root (e.g., 'etc/network/interfaces')"],
    content: Annotated[str, "File contents to write"]
) -> str:
    """Write file to Docker node filesystem

    Allows writing configuration files or other data to Docker node containers.

    IMPORTANT: File changes do NOT automatically restart the node or apply configuration.
    For network configuration, use configure_node_network() which handles the full workflow.

    Returns: JSON confirmation message

    Example:
        write_node_file("A-PROXY", "etc/network/interfaces", "auto eth0\\niface eth0 inet dhcp")
    """
    app: AppContext = ctx.request_context.lifespan_context

    error = await validate_current_project(app)
    if error:
        return error

    return await write_node_file_impl(app, node_name, file_path, content)


@mcp.tool(
    name="Configure node network",
    tags={"network", "node", "modifies-state"},
    annotations={"modifies_topology": True}
)
async def configure_node_network(
    ctx: Context,
    node_name: Annotated[str, "Name of the Docker node"],
    interfaces: Annotated[list, "List of interface configs (static/DHCP)"]
) -> str:
    """Configure network interfaces on Docker node

    Generates /etc/network/interfaces file and restarts the node to apply configuration.
    Supports both static IP and DHCP configuration for multiple interfaces (eth0, eth1, etc.).

    This is the recommended way to configure network settings on Docker nodes, as it handles
    the complete workflow: write config file → restart node → apply configuration.

    Interface Configuration:
        Static mode: {name, mode: "static", address, netmask, gateway?, dns?}
        DHCP mode: {name, mode: "dhcp", dns?}

    Returns: JSON confirmation with configured interfaces

    Examples:
        # Static IP configuration
        configure_node_network("A-PROXY", [{
            "name": "eth0",
            "mode": "static",
            "address": "10.199.0.254",
            "netmask": "255.255.255.0",
            "gateway": "10.199.0.1"
        }])

        # DHCP configuration
        configure_node_network("A-PROXY", [{
            "name": "eth0",
            "mode": "dhcp"
        }])

        # Multiple interfaces
        configure_node_network("A-PROXY", [
            {
                "name": "eth0",
                "mode": "static",
                "address": "10.199.0.254",
                "netmask": "255.255.255.0",
                "gateway": "10.199.0.1"
            },
            {
                "name": "eth1",
                "mode": "dhcp"
            }
        ])
    """
    app: AppContext = ctx.request_context.lifespan_context

    error = await validate_current_project(app)
    if error:
        return error

    return await configure_node_network_impl(app, node_name, interfaces)

@mcp.tool(
    name="Get project README",
    tags={"documentation", "project", "read-only"}
)
async def get_project_readme(
    ctx: Context,
    project_id: Annotated[str | None, "Project ID (uses current project if not specified)"] = None
) -> str:
    """Get project README/notes

    Returns project documentation in markdown format including:
    - IP addressing schemes and VLANs
    - Node credentials and details
    - Architecture notes and diagrams
    - Configuration snippets
    - Troubleshooting notes

    Returns: JSON with project_id and markdown content

    Example:
        >>> get_project_readme()
        >>> get_project_readme("a920c77d-6e9b-41b8-9311-b4b866a2fbb0")
    """
    app: AppContext = ctx.request_context.lifespan_context

    if not project_id:
        error = await validate_current_project(app)
        if error:
            return error
        project_id = app.current_project_id

    try:
        content = await app.gns3.get_project_readme(project_id)
        return json.dumps({
            "project_id": project_id,
            "content": content if content else "# Project Notes\n\n(No notes yet)",
            "format": "markdown"
        }, indent=2)
    except Exception as e:
        return json.dumps({
            "error": "Failed to get project README",
            "project_id": project_id,
            "details": str(e)
        }, indent=2)


@mcp.tool(
    name="Update project README",
    tags={"documentation", "project", "modifies-state"}
)
async def update_project_readme(
    ctx: Context,
    content: Annotated[str, "Markdown content to save"],
    project_id: Annotated[str | None, "Project ID (uses current project if not specified)"] = None
) -> str:
    """Update project README/notes

    Saves project documentation in markdown format. Agent can store:
    - IP addressing schemes and VLANs
    - Node credentials (usernames, password vault keys)
    - Architecture diagrams (text-based)
    - Configuration templates and snippets
    - Troubleshooting notes and runbooks

    Args:
        content: Markdown content to save
        project_id: Project ID (uses current project if not specified)

    Returns:
        JSON with success confirmation

    Example:
        >>> update_project_readme(\"\"\"
        ... # HA PowerDNS
        ... ## IPs
        ... - B-Rec1: 10.2.0.1/24
        ... - B-Rec2: 10.2.0.2/24
        ... \"\"\")
    """
    app: AppContext = ctx.request_context.lifespan_context

    if not project_id:
        error = await validate_current_project(app)
        if error:
            return error
        project_id = app.current_project_id

    try:
        success = await app.gns3.update_project_readme(project_id, content)
        if success:
            return json.dumps({
                "success": True,
                "project_id": project_id,
                "message": "README updated successfully",
                "content_length": len(content)
            }, indent=2)
        else:
            return json.dumps({
                "error": "Failed to update README",
                "project_id": project_id
            }, indent=2)
    except Exception as e:
        return json.dumps({
            "error": "Failed to update README",
            "project_id": project_id,
            "details": str(e)
        }, indent=2)


# export_topology_diagram tool now registered from export_tools module
# Register the imported tool with MCP
mcp.tool(
    name="Export topology diagram",
    description="Export topology diagram to SVG/PNG files on disk. For agents: use diagrams://{project_id}/topology resource for direct access without saving files.",
    tags={"topology", "visualization", "export", "file-io", "idempotent"},
    annotations={"idempotent": True, "read_only": True, "creates_resource": True}
)(export_topology_diagram)


# ============================================================================
# Drawing Tools
# ============================================================================

@mcp.tool(
    name="Create drawing",
    tags={"drawing", "topology", "visualization", "creates-resource"},
    annotations={"creates_resource": True}
)
async def create_drawing(
    ctx: Context,
    drawing_type: Annotated[str, "Type: 'rectangle', 'ellipse', 'line', or 'text'"],
    x: Annotated[int, "X coordinate (start point for line, top-left for others)"],
    y: Annotated[int, "Y coordinate (start point for line, top-left for others)"],
    z: Annotated[int, "Z-order/layer (default: 0 for shapes, 1 for text)"] = 0,
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
    color: Annotated[str, "Text color hex code (text only)"] = "#000000"
) -> str:
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

        Line parameters (drawing_type="line"):
            x2: X offset from start point (required, can be negative)
            y2: Y offset from start point (required, can be negative)
            color: Line color (hex or name, default: black)
            border_width: Line width in pixels (default: 2)

        Text parameters (drawing_type="text"):
            text: Text content (required)
            font_size: Font size in points (default: 10)
            font_weight: Font weight - "normal" or "bold" (default: normal)
            font_family: Font family (default: "TypeWriter")
            color: Text color (hex or name, default: black)

    Returns:
        JSON with created drawing info
    """
    app: AppContext = ctx.request_context.lifespan_context

    error = await validate_current_project(app)
    if error:
        return error

    return await create_drawing_impl(
        app, drawing_type, x, y, z,
        width, height, rx, ry, fill_color, border_color, border_width,
        x2, y2, text, font_size, font_weight, font_family, color
    )


@mcp.tool(
    name="Update drawing",
    tags={"drawing", "topology", "visualization", "modifies-state"},
    annotations={"idempotent": True}
)
async def update_drawing(
    ctx: Context,
    drawing_id: Annotated[str, "ID of the drawing to update"],
    x: Annotated[int | None, "New X coordinate"] = None,
    y: Annotated[int | None, "New Y coordinate"] = None,
    z: Annotated[int | None, "New Z-order/layer"] = None,
    rotation: Annotated[int | None, "New rotation angle in degrees"] = None,
    svg: Annotated[str | None, "New SVG content (for changing appearance)"] = None,
    locked: Annotated[bool | None, "Lock/unlock drawing"] = None
) -> str:
    """Update properties of an existing drawing object

    Returns: JSON with updated drawing info
    """
    app: AppContext = ctx.request_context.lifespan_context

    error = await validate_current_project(app)
    if error:
        return error

    return await update_drawing_impl(app, drawing_id, x, y, z, rotation, svg, locked)


@mcp.tool(
    name="Delete drawing",
    tags={"drawing", "topology", "visualization", "destructive", "idempotent"},
    annotations={"destructive": True, "idempotent": True}
)
async def delete_drawing(
    ctx: Context,
    drawing_id: Annotated[str, "ID of the drawing to delete"]
) -> str:
    """Delete a drawing object from the current project

    WARNING: This operation is destructive and cannot be undone.

    Returns: JSON confirmation message
    """
    app: AppContext = ctx.request_context.lifespan_context

    error = await validate_current_project(app)
    if error:
        return error

    return await delete_drawing_impl(app, drawing_id)


@mcp.tool(
    name="Create drawings batch",
    tags={"drawing", "topology", "visualization", "bulk", "creates-resource"},
)
async def create_drawings_batch(
    ctx: Context,
    drawings: Annotated[list[dict], "List of drawing definitions to create"]
) -> str:
    """Create multiple drawing objects in batch with validation

    Two-phase execution prevents partial failures:
    1. VALIDATE ALL drawings (check required params, valid types)
    2. CREATE ALL drawings (only if all valid, sequential execution)

    Supported drawing types:
    - "rectangle": Rectangle with width, height
    - "ellipse": Ellipse/circle with rx, ry (radii)
    - "line": Line with x2, y2 (offsets)
    - "text": Text label with text content

    Args:
        drawings: List of drawing dicts, each with:
            - drawing_type (str): Drawing type (required)
            - x (int): X coordinate (required)
            - y (int): Y coordinate (required)
            - z (int): Z-order/layer (optional, default: 0)
            - Additional params specific to drawing type

    Returns:
        JSON with execution results including completed/failed indices

    Examples:
        # Create multiple shapes:
        create_drawings_batch([
            {"drawing_type": "rectangle", "x": 100, "y": 100, "width": 200, "height": 100},
            {"drawing_type": "ellipse", "x": 400, "y": 100, "rx": 50, "ry": 50}
        ])

        # Create labeled diagram:
        create_drawings_batch([
            {"drawing_type": "rectangle", "x": 100, "y": 100, "width": 150, "height": 80, "z": 0},
            {"drawing_type": "text", "x": 175, "y": 140, "text": "Router1", "z": 1}
        ])
    """
    app: AppContext = ctx.request_context.lifespan_context

    error = await validate_current_project(app)
    if error:
        return error

    return await create_drawings_batch_impl(app, drawings)


# ============================================================================
# SSH Proxy Tools
# ============================================================================

from tools.ssh_tools import (
    configure_ssh_impl,
    ssh_batch_impl,
    ssh_disconnect_impl,
    ssh_send_command_impl,
    ssh_send_config_set_impl,
)


@mcp.tool(
    name="Configure SSH session",
    tags={"ssh", "device-access", "automation", "idempotent"},
    annotations={"idempotent": True}
)
async def ssh_configure(
    ctx: Context,
    node_name: Annotated[str, "GNS3 node name (e.g., 'Router1') OR '@' for local execution"],
    device_dict: Annotated[dict, "Netmiko config: device_type, host, username, password"],
    persist: Annotated[bool, "Store credentials for reconnection"] = True,
    force: Annotated[bool, "Force recreation even if healthy session exists"] = False,
    proxy: Annotated[str, "Proxy to route through: 'host' (default) or proxy_id"] = "host",
    session_timeout: Annotated[int, "Session timeout in seconds (default: 4 hours)"] = 14400
) -> str:
    """Configure SSH session to a network device in GNS3 lab

    IMPORTANT: This configures SSH to the NETWORK DEVICE (router/switch/host),
    NOT to the proxy. Enable SSH on the target device first using console tools.

    PARAMETERS EXPLAINED:
    - node_name: The GNS3 node name (e.g., "Router1", "Switch-Core")
    - device_dict['host']: IP address of the NETWORK DEVICE you want to SSH to
    - device_dict['username']: Login username for the NETWORK DEVICE
    - device_dict['password']: Login password for the NETWORK DEVICE
    - proxy parameter: Which proxy to route SSH through (NOT the target)

    Special Node Names (v0.28.0):
    - node_name="@": Local execution (no SSH session needed)
      Execute commands directly on SSH proxy container with diagnostic tools
      (ping, traceroute, dig, curl, ansible). Working dir: /opt/gns3-ssh-proxy

    Multi-Proxy Support (v0.26.0):
    - Use 'proxy' parameter to route through specific proxy
    - proxy="host" (default): Use main proxy on GNS3 host
    - proxy="<proxy_id>": Use discovered lab proxy for isolated networks
    - Discovery: Check gns3://proxy/registry resource for available proxies

    Session Management (v0.1.6) - AUTOMATIC RECOVERY:
    - Reuses existing healthy sessions automatically
    - Detects expired sessions (default 4hr TTL) and recreates automatically (v0.27.0)
    - Detects stale/closed connections via health check and recreates automatically
    - On "Socket is closed" errors: Just call ssh_configure() again (no force needed)

    When ssh_command() fails with "Socket is closed":
    1. Session is auto-removed from memory
    2. Simply call ssh_configure() again with same parameters
    3. Fresh session will be created automatically
    4. Retry your ssh_command() - it will work

    Args:
        node_name: GNS3 node name of target device (e.g., "Router1") OR "@" for local execution
        device_dict: Netmiko config for TARGET DEVICE (not proxy):
                     - device_type: "cisco_ios", "linux", "mikrotik_routeros", etc.
                     - host: IP address of the TARGET DEVICE (e.g., "10.1.0.1")
                     - username: Login username for TARGET DEVICE
                     - password: Login password for TARGET DEVICE
                     - port: SSH port (optional, default 22)
                     - secret: Enable password for Cisco (optional)
        persist: Store credentials for reconnection (default: True)
        force: Force recreation even if healthy session exists (default: False)
               Only needed for: manual credential refresh, troubleshooting
        proxy: Which proxy to route through - "host" (default) or proxy_id from registry
        session_timeout: Session timeout in seconds (default: 4 hours = 14400s) (v0.27.0)

    Returns:
        JSON with session_id, connected, device_type, proxy_url, proxy

    Examples:
        # Connect to Router1 at 10.1.0.1 (use default proxy on GNS3 host)
        ssh_configure("Router1", {"device_type": "cisco_ios", "host": "10.1.0.1",
                                  "username": "admin", "password": "cisco123"})

        # Isolated network - use lab proxy
        # Step 1: Discover lab proxies
        proxies = get_proxy_registry()  # gns3://proxy/registry

        # Step 2: Configure SSH through lab proxy
        ssh_configure("A-CLIENT", {
            "device_type": "linux",
            "host": "10.199.0.20",
            "username": "alpine",
            "password": "alpine"
        }, proxy="3f3a56de-19d3-40c3-9806-76bee4fe96d4")  # A-PROXY proxy_id

        # After "Socket is closed" error - just retry (auto-recovery)
        # NO force parameter needed - stale session already cleaned up
        ssh_configure("R1", device_dict)

        # Force recreation (rarely needed)
        ssh_configure("R1", device_dict, force=True)
    """
    app: AppContext = ctx.request_context.lifespan_context
    return await configure_ssh_impl(app, node_name, device_dict, persist, force, proxy, session_timeout)


@mcp.tool(
    name="Execute SSH command",
    tags={"ssh", "device-access", "automation"}
)
async def ssh_command(
    ctx: Context,
    node_name: Annotated[str, "Node identifier (or '@' for local execution)"],
    command: Annotated[str | list, "Command(s) - string for show, list for config/bash script"],
    expect_string: Annotated[str | None, "Regex pattern to wait for (overrides prompt detection)"] = None,
    read_timeout: Annotated[float, "Max seconds to wait for output"] = 30.0,
    wait_timeout: Annotated[int, "Max wait for long commands (0 for async job_id)"] = 30
) -> str:
    """Execute command(s) via SSH with auto-detection (show vs config)

    Local Execution (v0.28.0):
    - Use node_name="@" to execute commands on SSH proxy container
    - No ssh_configure() needed for local execution
    - Access to: ping, traceroute, dig, curl, ansible, python3, bash
    - Working directory: /opt/gns3-ssh-proxy (ansible playbooks mount)

    Auto-detects command type:
    - String: Single show command (uses ssh_send_command)
    - List: Configuration commands or bash script (uses ssh_send_config_set)

    Long commands: Set read_timeout high, wait_timeout=0 for job_id,
    poll with resource gns3://sessions/ssh/{node}/jobs/{id}

    Args:
        node_name: Node identifier (or "@" for local execution)
        command: Command(s) - string for show/single command, list for config/bash script
        expect_string: Regex pattern to wait for (overrides prompt detection, optional)
        read_timeout: Max seconds to wait for output (default: 30)
        wait_timeout: Seconds to poll before returning job_id (default: 30)

    Returns:
        JSON with completed, job_id, output, execution_time (or success, output, exit_code for local)

    Examples:
        # Show command (string)
        ssh_command("R1", "show ip interface brief")

        # Config commands (list)
        ssh_command("R1", [
            "interface GigabitEthernet0/0",
            "ip address 192.168.1.1 255.255.255.0",
            "no shutdown"
        ])

        # Local execution - single command
        ssh_command("@", "ping -c 3 10.10.10.1")

        # Local execution - ansible playbook
        ssh_command("@", "ansible-playbook /opt/gns3-ssh-proxy/backup.yml")

        # Local execution - bash script (list)
        ssh_command("@", [
            "cd /opt/gns3-ssh-proxy",
            "python3 backup_configs.py",
            "ls -la backups/"
        ])
    """
    app: AppContext = ctx.request_context.lifespan_context

    # Auto-detect command type
    if isinstance(command, list):
        # Config mode: list of commands
        return await ssh_send_config_set_impl(app, node_name, command, wait_timeout)
    else:
        # Show mode: single command
        return await ssh_send_command_impl(app, node_name, command, expect_string, read_timeout, wait_timeout)


@mcp.tool(
    name="Disconnect SSH session",
    tags={"ssh", "device-access", "idempotent"},
    annotations={"idempotent": True}
)
async def ssh_disconnect(
    ctx: Context,
    node_name: Annotated[str, "Node identifier"]
) -> str:
    """Disconnect SSH session

    Returns: JSON with status
    """
    app: AppContext = ctx.request_context.lifespan_context
    return await ssh_disconnect_impl(app, node_name)


@mcp.tool(
    name="SSH batch operations",
    tags={"ssh", "device-access", "bulk", "automation"}
)
async def ssh_batch(
    ctx: Context,
    operations: Annotated[list[dict], "List of SSH operations (command/disconnect)"]
) -> str:
    """Execute multiple SSH operations in batch with validation

    Local Execution Support (v0.28.0):
    - Use node_name="@" in any operation for local execution on SSH proxy container
    - Mix local and remote operations in same batch
    - Useful for: connectivity tests before device access, ansible playbooks

    Two-phase execution prevents partial failures:
    1. VALIDATE ALL operations (check required params, valid types)
    2. EXECUTE ALL operations (only if all valid, sequential execution)

    Supported operation types:
    - "send_command": Execute show command (or local command with node_name="@")
    - "send_config_set": Send configuration commands (or bash script with node_name="@")
    - "read_buffer": Read SSH buffer with optional grep

    Args:
        operations: List of operation dicts, each with:
            - type (str): Operation type (required)
            - node_name (str): Node name (or "@" for local execution) (required)
            - Additional params specific to operation type

    Returns:
        JSON with execution results including completed/failed indices

    Examples:
        # Multiple commands on one node:
        ssh_batch([
            {"type": "send_command", "node_name": "R1", "command": "show version"},
            {"type": "send_command", "node_name": "R1", "command": "show ip route"}
        ])

        # Same command on multiple nodes:
        ssh_batch([
            {"type": "send_command", "node_name": "R1", "command": "show ip int brief"},
            {"type": "send_command", "node_name": "R2", "command": "show ip int brief"}
        ])

        # Configuration commands:
        ssh_batch([{
            "type": "send_config_set",
            "node_name": "R1",
            "config_commands": [
                "interface GigabitEthernet0/0",
                "ip address 10.1.1.1 255.255.255.0",
                "no shutdown"
            ]
        }])

        # Local execution - test connectivity before device access:
        ssh_batch([
            {"type": "send_command", "node_name": "@", "command": "ping -c 2 10.1.1.1"},
            {"type": "send_command", "node_name": "@", "command": "ping -c 2 10.1.1.2"},
            {"type": "send_command", "node_name": "R1", "command": "show ip int brief"},
            {"type": "send_command", "node_name": "R2", "command": "show ip int brief"}
        ])
    """
    app: AppContext = ctx.request_context.lifespan_context
    return await ssh_batch_impl(app, operations)


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
    parser.add_argument("--password", default="", help="GNS3 password")

    # MCP transport mode arguments
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

        # Create ASGI app for HTTP transport
        app = mcp.http_app()

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
        print("WARNING: SSE transport is deprecated. Consider using --transport http instead.")
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
