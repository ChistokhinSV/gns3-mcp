"""GNS3 MCP Server v0.19.0

Model Context Protocol server for GNS3 lab automation.
Provides console and SSH automation tools for network devices.

IMPORTANT: Tool Selection Guidelines
====================================
When automating network devices, ALWAYS prefer SSH tools over console tools!

SSH Tools (Preferred):
- ssh_command() - Auto-detects show vs config commands
- Better reliability with automatic prompt detection
- Structured output and error handling
- Supports 200+ device types via Netmiko

Console Tools (Use Only When Necessary):
- console_send(), console_read(), console_disconnect(), console_keystroke()
- For initial device configuration (enabling SSH, creating users)
- For troubleshooting when SSH is unavailable
- For devices without SSH support (VPCS, simple switches)

Typical Workflow:
1. Use console tools to configure SSH access on device
2. Establish SSH session with ssh_configure()
3. Switch to SSH tools for all automation tasks
4. Return to console only if SSH fails

Version 0.19.0 - UX & Advanced Features (FEATURE):
- NEW: MCP tool annotations for all 20 tools
  * destructive: delete_node, restore_snapshot, delete_drawing (3 tools)
  * idempotent: open_project, create_project, close_project, set_node, console_disconnect,
                ssh_configure, ssh_disconnect, update_drawing, export_topology_diagram (9 tools)
  * read_only: console_read (1 tool)
  * creates_resource: create_project, create_node, create_snapshot, export_topology_diagram,
                      create_drawing (5 tools)
  * modifies_topology: set_connection, create_node, delete_node (3 tools)
- DEFERRED: Autocomplete support for 7 parameter types via MCP completions (disabled - FastMCP API differs)
  * node_name: All console/SSH/node tools autocomplete from current project nodes
  * template_name: create_node autocompletes from available templates
  * action (set_node): start/stop/suspend/reload/restart
  * project_name: open_project autocompletes from all projects
  * snapshot_name: restore_snapshot autocompletes from project snapshots
  * drawing_type: create_drawing autocompletes rectangle/ellipse/line/text
  * topology_type: lab_setup autocompletes star/mesh/linear/ring/ospf/bgp
- NEW: 3 drawing tools for visual annotations (hybrid architecture)
  * create_drawing: Create rectangle, ellipse, line, or text annotations
  * update_drawing: Modify position, rotation, appearance, lock state
  * delete_drawing: Remove drawing objects
  * Follows hybrid pattern: Resources for READ, Tools for WRITE
- ARCHITECTURE: 20 tools + 17 resources + 4 prompts + 8 completions = Enhanced UX
- FILE CHANGES:
  * Modified: main.py (added annotations to 17 tools, 8 completion handlers, 3 drawing tools, +300 LOC)
  * Modified: drawing_tools.py (added update_drawing_impl, +65 LOC)
  * Modified: manifest.json (version 0.18.0→0.19.0, added 3 tools, updated descriptions)
- NO BREAKING CHANGES: All existing tools, resources, prompts unchanged
- RATIONALE: Tool annotations enable IDE warnings for destructive operations, autocomplete
  improves discoverability and reduces errors, drawing tools restore functionality removed
  in v0.15.0 with improved hybrid architecture

Version 0.18.0 - Core Lab Automation (FEATURE):
- NEW: 5 new tools for complete lab lifecycle management
  * create_project: Create new projects and auto-open
  * close_project: Close current project
  * create_node: Create nodes from templates at specified coordinates (restored from v0.15.0)
  * create_snapshot: Save project state with validation (warns on running nodes)
  * restore_snapshot: Restore to previous state (stops nodes, disconnects sessions)
- NEW: 2 new MCP resources for snapshot browsing
  * gns3://projects/{id}/snapshots/ - List all snapshots
  * gns3://projects/{id}/snapshots/{id} - Snapshot details
- NEW: lab_setup prompt - Automated topology creation with 6 types
  * Star: Hub-and-spoke topology (device_count = spokes)
  * Mesh: Full mesh topology (device_count = routers)
  * Linear: Chain topology (device_count = routers)
  * Ring: Circular topology (device_count = routers)
  * OSPF: Multi-area with backbone (device_count = areas, 3 routers per area)
  * BGP: Multiple AS topology (device_count = AS, 2 routers per AS)
  * Includes: Layout algorithms, link generation, IP addressing schemes
- ARCHITECTURE: 16 tools + 17 resources + 4 prompts = Complete lab automation
- FILE CHANGES:
  * Created: snapshot_tools.py (~200 LOC), prompts/lab_setup.py (~800 LOC)
  * Modified: gns3_client.py (+100 LOC), project_tools.py (+100 LOC),
              main.py (+100 LOC), models.py (+30 LOC),
              project_resources.py (+100 LOC), resource_manager.py (+20 LOC)
- NO BREAKING CHANGES: All existing tools, resources, and prompts unchanged
- RATIONALE: Enables complete lab automation from project creation through topology
  setup to snapshot management. Lab setup prompt reduces manual work for common topologies.

Version 0.17.0 - MCP Prompts (FEATURE):
- NEW: 3 guided workflow prompts for common GNS3 operations
  * ssh_setup: Device-specific SSH configuration (Cisco, MikroTik, Juniper, Arista, Linux)
  * topology_discovery: Discover and visualize network topology with resources
  * troubleshooting: OSI model-based troubleshooting methodology
- ARCHITECTURE: 11 tools + 15 resources + 3 prompts = Complete MCP server
- ENHANCED: Workflow guidance for complex multi-step operations
- DEVICE COVERAGE: 6 device types with specific configuration commands
- NO BREAKING CHANGES: All tools and resources unchanged, prompts additive
- RATIONALE: Prompts guide users through complex workflows, reducing errors and improving efficiency

Version 0.15.0 - Complete Tool Consolidation (BREAKING CHANGES):
- RENAMED: All tools now follow {category}_{action} pattern for consistency
  * send_console → console_send
  * read_console → console_read
  * disconnect_console → console_disconnect
  * send_keystroke → console_keystroke
  * configure_ssh → ssh_configure
- MERGED: SSH command tools with auto-detection
  * ssh_send_command + ssh_send_config_set → ssh_command (auto-detects show vs config)
- REMOVED: 7 deprecated/low-usage tools
  * send_and_wait_console → Use console_send + console_read workflow
  * create_node → Will be resource template in v0.16.0
  * create_drawing → Will be resource template in v0.16.0
  * delete_drawing → Use GNS3 GUI (low usage)
  * ssh_cleanup_sessions → Use explicit ssh_disconnect
  * ssh_get_job_status → Already available as resource gns3://sessions/ssh/{node}/jobs/{id}
- NEW: ssh_disconnect tool for explicit session cleanup
- FINAL ARCHITECTURE: 11 core tools + 15 browsable resources
  * Tools: open_project, set_node, delete_node, console_send, console_read, console_disconnect,
           console_keystroke, set_connection, ssh_configure, ssh_command, ssh_disconnect
  * Resources: 15 gns3:// URIs for browsing state
- RATIONALE: Consistent naming, simpler SSH interface, reduced tool count (17→11)

Version 0.14.0 - Tool Consolidation (BREAKING CHANGES - Phase 1):
- REMOVED: 11 deprecated query tools (replaced by MCP resources in v0.13.0)
  * list_projects → use resource gns3://projects
  * list_nodes → use resource gns3://projects/{id}/nodes
  * get_node_details → use resource gns3://projects/{id}/nodes/{id}
  * get_links → use resource gns3://projects/{id}/links
  * list_templates → use resource gns3://projects/{id}/templates
  * list_drawings → use resource gns3://projects/{id}/drawings
  * get_console_status → use resource gns3://sessions/console/{node}
  * ssh_get_status → use resource gns3://sessions/ssh/{node}
  * ssh_get_history → use resource gns3://sessions/ssh/{node}/history
  * ssh_get_command_output → query resource with filtering
  * ssh_read_buffer → use resource gns3://sessions/ssh/{node}/buffer
- FINAL ARCHITECTURE: 10 core tools + 15 browsable resources
  * Tools: Actions that modify state (create, delete, configure, execute)
  * Resources: Read-only browsable state (projects, nodes, sessions, status)
- RATIONALE: Clearer separation of concerns, reduced cognitive load, better IDE integration

Version 0.13.0 - MCP Resources (BREAKING CHANGES - Phase 1):
- NEW: 15 MCP resources for browsable state (gns3:// URI scheme)
  * gns3://projects/ - List all projects
  * gns3://projects/{id} - Project details
  * gns3://projects/{id}/nodes/ - List nodes in project
  * gns3://projects/{id}/nodes/{id} - Node details with full info
  * gns3://projects/{id}/links/ - List links in project
  * gns3://projects/{id}/templates/ - Available templates
  * gns3://projects/{id}/drawings/ - List drawings
  * gns3://sessions/console/ - All console sessions
  * gns3://sessions/console/{node} - Console session status
  * gns3://sessions/ssh/ - All SSH sessions
  * gns3://sessions/ssh/{node} - SSH session status
  * gns3://sessions/ssh/{node}/history - SSH command history
  * gns3://sessions/ssh/{node}/buffer - SSH continuous buffer
  * gns3://proxy/status - SSH proxy service status
  * gns3://proxy/sessions - All SSH proxy sessions
- REFACTORED: Resource architecture with 3 new modules
  * resources/resource_manager.py - URI routing (330 LOC)
  * resources/project_resources.py - Project/node/link resources (340 LOC)
  * resources/session_resources.py - Console/SSH session resources (230 LOC)
- DEPRECATED: 11 query tools (still available, will be removed in v0.14.0)
  * list_projects → gns3://projects/
  * list_nodes → gns3://projects/{id}/nodes/
  * get_node_details → gns3://projects/{id}/nodes/{id}
  * get_links → gns3://projects/{id}/links/
  * list_templates → gns3://projects/{id}/templates/
  * list_drawings → gns3://projects/{id}/drawings/
  * get_console_status → gns3://sessions/console/{node}
  * ssh_get_status → gns3://sessions/ssh/{node}
  * ssh_get_history → gns3://sessions/ssh/{node}/history
  * ssh_get_command_output → gns3://sessions/ssh/{node}/history (with filtering)
  * ssh_read_buffer → gns3://sessions/ssh/{node}/buffer
- ENHANCED: Better IDE integration with resource discovery
- NO BREAKING CHANGES: All existing tools still work (deprecated tools functional)

Version 0.12.4 - Error Handling Improvement (BUGFIX):
- FIXED: configure_ssh error messages now properly distinguish SSH connection
  errors (timeout, auth failure) from server errors
- Better error parsing from SSH proxy HTTP responses

Version 0.12.3 - Console Output Fix (BUGFIX):
- FIXED: send_and_wait_console now accumulates all output during polling

Version 0.12.2 - Lightweight Node Listing (BUGFIX):
- FIXED: list_nodes returns lightweight NodeSummary to prevent large output failures

Version 0.12.1 - Grep Filtering (FEATURE):
- ADDED: Grep-style pattern filtering for SSH and console buffers

Version 0.12.0 - SSH Proxy Service (FEATURE - Phase 1):
- NEW: SSH proxy service (FastAPI container on port 8022, Python 3.13-slim)
- NEW: 9 MCP tools for SSH automation via Netmiko (200+ device types)
  * configure_ssh, ssh_send_command, ssh_send_config_set
  * ssh_read_buffer, ssh_get_history, ssh_get_command_output
  * ssh_get_status, ssh_cleanup_sessions, ssh_get_job_status
- NEW: Dual storage - continuous buffer + per-command job history
- NEW: Adaptive async execution (poll wait_timeout, return job_id for long commands)
- NO BREAKING CHANGES: All existing tools unchanged, SSH tools additive

Version 0.11.0 - Code Organization Refactoring (REFACTOR):
- ADDED: Console manager unit tests (38 tests, 76% coverage)
- REFACTORED: Extracted 19 tools to 6 modules (tools/ directory)
- IMPROVED: Reduced main.py from 1,836 to 914 LOC (50% reduction)

Version 0.10.0 - Testing Infrastructure (FEATURE):
- ADDED: Comprehensive unit testing infrastructure (pytest 8.4.2, 134 tests total)
- REFACTORED: Extracted export functionality to export_tools.py module

Version 0.9.0 - Major Cleanup (BREAKING CHANGES):
- REMOVED: Caching infrastructure, detect_console_state() tool
- CHANGED: read_console() now uses mode parameter ("diff"/"last_page"/"all")
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
from pathlib import Path
from typing import Optional, List, Dict, Any

from mcp.server.fastmcp import FastMCP, Context
from mcp.types import Completion

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
from tools.project_tools import (
    list_projects_impl,
    open_project_impl,
    create_project_impl,
    close_project_impl
)
from tools.node_tools import (
    list_nodes_impl,
    get_node_details_impl,
    set_node_impl,
    create_node_impl,
    delete_node_impl,
    get_node_file_impl,
    write_node_file_impl,
    configure_node_network_impl
)
from tools.console_tools import (
    send_console_impl,
    read_console_impl,
    disconnect_console_impl,
    get_console_status_impl,
    send_and_wait_console_impl,
    send_keystroke_impl,
    console_batch_impl
)
from tools.link_tools import get_links_impl, set_connection_impl
from tools.drawing_tools import (
    list_drawings_impl,
    create_drawing_impl,
    update_drawing_impl,
    delete_drawing_impl
)
from tools.template_tools import list_templates_impl
from tools.snapshot_tools import create_snapshot_impl, restore_snapshot_impl
from resources import ResourceManager
from prompts import (
    render_ssh_setup_prompt,
    render_topology_discovery_prompt,
    render_troubleshooting_prompt,
    render_lab_setup_prompt,
    render_node_setup_prompt
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


# ============================================================================
# MCP Resources - Browsable State
# ============================================================================

# Project resources
@mcp.resource("gns3://projects")
async def resource_projects() -> str:
    """List all GNS3 projects"""
    return await _app.resource_manager.list_projects()

@mcp.resource("gns3://projects/{project_id}")
async def resource_project(ctx: Context, project_id: str) -> str:
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.get_project(project_id)

@mcp.resource("gns3://projects/{project_id}/nodes")
async def resource_nodes(ctx: Context, project_id: str) -> str:
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.list_nodes(project_id)

@mcp.resource("gns3://projects/{project_id}/nodes/{node_id}")
async def resource_node(ctx: Context, project_id: str, node_id: str) -> str:
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.get_node(project_id, node_id)

@mcp.resource("gns3://projects/{project_id}/links")
async def resource_links(ctx: Context, project_id: str) -> str:
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.list_links(project_id)

@mcp.resource("gns3://templates")
async def resource_templates() -> str:
    """List all available GNS3 templates"""
    return await _app.resource_manager.list_templates()

@mcp.resource("gns3://projects/{project_id}/drawings")
async def resource_drawings(ctx: Context, project_id: str) -> str:
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.list_drawings(project_id)

@mcp.resource("gns3://projects/{project_id}/snapshots")
async def resource_snapshots(ctx: Context, project_id: str) -> str:
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.list_snapshots(project_id)

@mcp.resource("gns3://projects/{project_id}/snapshots/{snapshot_id}")
async def resource_snapshot(ctx: Context, project_id: str, snapshot_id: str) -> str:
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.get_snapshot(project_id, snapshot_id)

@mcp.resource("gns3://projects/{project_id}/readme")
async def resource_project_readme(ctx: Context, project_id: str) -> str:
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.get_project_readme(project_id)

@mcp.resource("gns3://projects/{project_id}/sessions/console")
async def resource_console_sessions(ctx: Context, project_id: str) -> str:
    """List console sessions for project nodes"""
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.list_console_sessions(project_id)

@mcp.resource("gns3://projects/{project_id}/sessions/ssh")
async def resource_ssh_sessions(ctx: Context, project_id: str) -> str:
    """List SSH sessions for project nodes"""
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.list_ssh_sessions(project_id)

# Template resources
@mcp.resource("gns3://templates/{template_id}")
async def resource_template(ctx: Context, template_id: str) -> str:
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.get_template(template_id)

@mcp.resource("gns3://projects/{project_id}/nodes/{node_id}/template")
async def resource_node_template(ctx: Context, project_id: str, node_id: str) -> str:
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.get_node_template_usage(project_id, node_id)

# Console session resources (node-specific templates only)
@mcp.resource("gns3://sessions/console/{node_name}")
async def resource_console_session(ctx: Context, node_name: str) -> str:
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.get_console_session(node_name)

# SSH session resources (node-specific templates only)
@mcp.resource("gns3://sessions/ssh/{node_name}")
async def resource_ssh_session(ctx: Context, node_name: str) -> str:
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.get_ssh_session(node_name)

@mcp.resource("gns3://sessions/ssh/{node_name}/history")
async def resource_ssh_history(ctx: Context, node_name: str) -> str:
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.get_ssh_history(node_name)

@mcp.resource("gns3://sessions/ssh/{node_name}/buffer")
async def resource_ssh_buffer(ctx: Context, node_name: str) -> str:
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.get_ssh_buffer(node_name)

# SSH proxy resources
@mcp.resource("gns3://proxy/status")
async def resource_proxy_status() -> str:
    """Get SSH proxy service status"""
    return await _app.resource_manager.get_proxy_status()

@mcp.resource("gns3://proxy/registry")
async def resource_proxy_registry() -> str:
    """Get proxy registry (discovered lab proxies via Docker API)"""
    return await _app.resource_manager.get_proxy_registry()

# Proxy resource templates (project-scoped)
@mcp.resource("gns3://projects/{project_id}/proxies")
async def resource_project_proxies(ctx: Context, project_id: str) -> str:
    """List proxies for specific project"""
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.list_project_proxies(project_id)

@mcp.resource("gns3://proxy/{proxy_id}")
async def resource_proxy(ctx: Context, proxy_id: str) -> str:
    """Get specific proxy details by proxy_id (GNS3 node_id)"""
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.get_proxy(proxy_id)


# ============================================================================
# MCP Prompts - Guided Workflows
# ============================================================================

@mcp.prompt()
async def ssh_setup(
    node_name: str,
    device_type: str,
    username: str = "admin",
    password: str = "admin"
) -> str:
    """SSH Setup Workflow - Enable SSH access on network devices

    Provides device-specific step-by-step instructions for configuring SSH
    on network devices. Covers 6 device types: Cisco IOS, NX-OS, MikroTik
    RouterOS, Juniper Junos, Arista EOS, and Linux.

    Args:
        node_name: Target node name to configure
        device_type: Device type (cisco_ios, cisco_nxos, mikrotik_routeros,
                     juniper_junos, arista_eos, linux)
        username: SSH username to create (default: "admin")
        password: SSH password to set (default: "admin")

    Returns:
        Complete workflow with device-specific commands, verification steps,
        and troubleshooting guidance
    """
    return await render_ssh_setup_prompt(node_name, device_type, username, password)


@mcp.prompt()
async def topology_discovery(
    project_name: str = None,
    include_export: bool = True
) -> str:
    """Topology Discovery Workflow - Discover and visualize network topology

    Guides you through discovering nodes, links, and topology structure using
    MCP resources and tools. Includes visualization and analysis guidance.

    Args:
        project_name: Optional project name to focus on (default: guide user to select)
        include_export: Include export/visualization steps (default: True)

    Returns:
        Complete workflow for topology discovery, visualization, and analysis
    """
    return await render_topology_discovery_prompt(project_name, include_export)


@mcp.prompt()
async def troubleshooting(
    node_name: str = None,
    issue_type: str = None
) -> str:
    """Network Troubleshooting Workflow - Systematic network issue diagnosis

    Provides OSI model-based troubleshooting methodology for network labs.
    Covers connectivity, console access, SSH, and performance issues.

    Args:
        node_name: Optional node name to focus troubleshooting on
        issue_type: Optional issue category (connectivity, console, ssh, performance)

    Returns:
        Complete troubleshooting workflow with diagnostic steps, common issues,
        and resolution guidance
    """
    return await render_troubleshooting_prompt(node_name, issue_type)


@mcp.prompt()
async def lab_setup(
    topology_type: str,
    device_count: int,
    template_name: str = "Alpine Linux",
    project_name: str = "Lab Topology"
) -> str:
    """Lab Setup Workflow - Automated lab topology creation

    Generates complete lab topologies with automated node placement, link
    configuration, and IP addressing schemes. Supports 6 topology types.

    Args:
        topology_type: Topology type (star, mesh, linear, ring, ospf, bgp)
        device_count: Number of devices (spokes for star, areas for OSPF, AS for BGP)
        template_name: GNS3 template to use (default: "Alpine Linux")
        project_name: Name for the new project (default: "Lab Topology")

    Returns:
        Complete workflow with node creation, link setup, IP addressing,
        and topology-specific configuration guidance

    Topology Types:
        - star: Hub-and-spoke with central hub
        - mesh: Full mesh with all devices interconnected
        - linear: Chain of devices in a line
        - ring: Circular connection of devices
        - ospf: Multi-area OSPF with backbone and areas
        - bgp: Multiple AS with iBGP and eBGP peering
    """
    return render_lab_setup_prompt(topology_type, device_count, template_name, project_name)


@mcp.prompt()
async def node_setup(
    node_name: str,
    template_name: str,
    ip_address: str,
    subnet_mask: str = "255.255.255.0",
    device_type: str = "cisco_ios",
    username: str = "admin",
    password: str = "admin"
) -> str:
    """Node Setup Workflow - Complete workflow for adding a new node to a lab

    Guides through the entire process of:
    1. Creating a new node from template
    2. Starting the node and waiting for boot
    3. Configuring IP address via console
    4. Documenting IP/credentials in project README
    5. Establishing SSH session for automation

    Args:
        node_name: Name for the new node (e.g., "Router1")
        template_name: GNS3 template to use (e.g., "Cisco IOSv", "Alpine Linux")
        ip_address: Management IP to assign (e.g., "192.168.1.10")
        subnet_mask: Subnet mask (default: "255.255.255.0")
        device_type: Device type for SSH (cisco_ios, linux, mikrotik_routeros)
        username: SSH username to create (default: "admin")
        password: SSH password to set (default: "admin")

    Returns:
        Complete workflow with device-specific commands for IP configuration,
        README documentation template, SSH session setup, and verification steps
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

@mcp.tool(annotations={
    "idempotent": True
})
async def open_project(ctx: Context, project_name: str) -> str:
    """Open a GNS3 project by name

    Args:
        project_name: Name of the project to open

    Returns:
        JSON with ProjectInfo for opened project
    """
    app: AppContext = ctx.request_context.lifespan_context
    return await open_project_impl(app, project_name)


@mcp.tool(annotations={
    "idempotent": True,
    "creates_resource": True
})
async def create_project(ctx: Context, name: str, path: Optional[str] = None) -> str:
    """Create a new GNS3 project and auto-open it

    Args:
        name: Project name
        path: Optional project directory path

    Returns:
        JSON with ProjectInfo for created project

    Example:
        >>> create_project("My Lab")
        >>> create_project("Production Lab", "/opt/gns3/projects")
    """
    app: AppContext = ctx.request_context.lifespan_context
    return await create_project_impl(app, name, path)


@mcp.tool(annotations={
    "idempotent": True
})
async def close_project(ctx: Context) -> str:
    """Close the currently opened project

    Returns:
        JSON with success message

    Example:
        >>> close_project()
    """
    app: AppContext = ctx.request_context.lifespan_context
    return await close_project_impl(app)


@mcp.tool(annotations={
    "idempotent": True
})
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
    return await set_node_impl(
        app, node_name, action, x, y, z, locked, ports,
        name, ram, cpus, hdd_disk_image, adapters, console_type
    )


@mcp.tool()
async def console_send(ctx: Context, node_name: str, data: str, raw: bool = False) -> str:
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

    Args:
        node_name: Name of the node (e.g., "Router1")
        data: Data to send - include newline for commands (e.g., "enable\n")
              Send just "\n" to wake console and check for prompts
        raw: If True, send data without escape sequence processing (default: False)

    Returns:
        "Sent successfully" or error message

    Example - Wake console and check state:
        console_send("R1", "\n")
        await 1 second
        console_read("R1", mode="diff")  # See what prompt appeared
    """
    app: AppContext = ctx.request_context.lifespan_context
    return await send_console_impl(app, node_name, data, raw)


@mcp.tool(annotations={
    "read_only": True
})
async def console_read(
    ctx: Context,
    node_name: str,
    mode: str = "diff",
    pages: int = 1,
    pattern: str | None = None,
    case_insensitive: bool = False,
    invert: bool = False,
    before: int = 0,
    after: int = 0,
    context: int = 0
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

    Args:
        node_name: Name of the node
        mode: Output mode (default: "diff")
        pages: Number of pages (only with mode="num_pages")
        pattern: Regex to filter output
        case_insensitive: Case-insensitive matching
        invert: Invert match
        before/after/context: Context lines

    Returns:
        Console output (filtered if pattern provided)

    Example - Grep for errors:
        console_read("R1", mode="all", pattern="error", case_insensitive=True)

    Example - Find interface with context:
        console_read("R1", mode="diff", pattern="GigabitEthernet", context=2)
    """
    app: AppContext = ctx.request_context.lifespan_context
    return await read_console_impl(app, node_name, mode, pages, pattern, case_insensitive, invert, before, after, context)


@mcp.tool(annotations={
    "idempotent": True
})
async def console_disconnect(ctx: Context, node_name: str) -> str:
    """Disconnect console session

    Args:
        node_name: Name of the node

    Returns:
        JSON with status
    """
    app: AppContext = ctx.request_context.lifespan_context
    return await disconnect_console_impl(app, node_name)


@mcp.tool()
async def console_keystroke(ctx: Context, node_name: str, key: str) -> str:
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
    return await send_keystroke_impl(app, node_name, key)


@mcp.tool()
async def console_send_and_wait(
    ctx: Context,
    node_name: str,
    command: str,
    wait_pattern: Optional[str] = None,
    timeout: int = 30,
    raw: bool = False
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

    Args:
        node_name: Name of the node
        command: Command to send (include \\n for newline)
        wait_pattern: Optional regex pattern to wait for (e.g., "Router[>#]", "Login:")
                      If None, waits 2 seconds and returns output
                      TIP: Check prompt first with console_read() to get exact pattern
        timeout: Maximum seconds to wait for pattern (default: 30)
        raw: If True, send command without escape sequence processing (default: False)

    Returns:
        JSON with:
        {
            "output": "console output",
            "pattern_found": true/false,
            "timeout_occurred": true/false,
            "wait_time": 2.5  // seconds actually waited
        }

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


@mcp.tool()
async def console_batch(ctx: Context, operations: List[Dict[str, Any]]) -> str:
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


@mcp.tool(annotations={
    "modifies_topology": True
})
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

    error = await validate_current_project(app)
    if error:
        return error

    return await set_connection_impl(app, connections)


@mcp.tool(annotations={
    "creates_resource": True,
    "modifies_topology": True
})
async def create_node(
    ctx: Context,
    template_name: str,
    x: int,
    y: int,
    node_name: Optional[str] = None,
    compute_id: str = "local",
    properties: Optional[Dict[str, Any]] = None
) -> str:
    """Create a new node from template at specified coordinates

    Creates a node from a GNS3 template and places it at the given x/y position.
    Optional properties can override template defaults.

    Args:
        template_name: Name of the template to use (e.g., "Alpine Linux", "Cisco IOSv")
        x: X coordinate (horizontal position, left edge of icon)
        y: Y coordinate (vertical position, top edge of icon)
        node_name: Optional custom name (defaults to template name with auto-number)
        compute_id: Compute server ID (default: "local")
        properties: Optional dict to override template properties (e.g., {"ram": 512, "cpus": 2})

    Returns:
        JSON with created NodeInfo

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


@mcp.tool(annotations={
    "destructive": True,
    "idempotent": True,
    "modifies_topology": True
})
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

    return await delete_node_impl(app, node_name)


@mcp.tool()
async def get_node_file(ctx: Context, node_name: str, file_path: str) -> str:
    """Read file from Docker node filesystem

    Allows reading files from Docker node containers. Useful for inspecting
    configuration files, logs, or other data inside containers.

    Args:
        node_name: Name of the Docker node
        file_path: Path relative to container root (e.g., 'etc/network/interfaces')

    Returns:
        JSON with file contents

    Example:
        get_node_file("A-PROXY", "etc/network/interfaces")
    """
    app: AppContext = ctx.request_context.lifespan_context

    error = await validate_current_project(app)
    if error:
        return error

    return await get_node_file_impl(app, node_name, file_path)


@mcp.tool()
async def write_node_file(ctx: Context, node_name: str, file_path: str, content: str) -> str:
    """Write file to Docker node filesystem

    Allows writing configuration files or other data to Docker node containers.

    IMPORTANT: File changes do NOT automatically restart the node or apply configuration.
    For network configuration, use configure_node_network() which handles the full workflow.

    Args:
        node_name: Name of the Docker node
        file_path: Path relative to container root (e.g., 'etc/network/interfaces')
        content: File contents to write

    Returns:
        JSON confirmation message

    Example:
        write_node_file("A-PROXY", "etc/network/interfaces", "auto eth0\\niface eth0 inet dhcp")
    """
    app: AppContext = ctx.request_context.lifespan_context

    error = await validate_current_project(app)
    if error:
        return error

    return await write_node_file_impl(app, node_name, file_path, content)


@mcp.tool(annotations={
    "modifies_topology": True
})
async def configure_node_network(ctx: Context, node_name: str, interfaces: list) -> str:
    """Configure network interfaces on Docker node

    Generates /etc/network/interfaces file and restarts the node to apply configuration.
    Supports both static IP and DHCP configuration for multiple interfaces (eth0, eth1, etc.).

    This is the recommended way to configure network settings on Docker nodes, as it handles
    the complete workflow: write config file → restart node → apply configuration.

    Args:
        node_name: Name of the Docker node
        interfaces: List of interface configurations, each with:
            Static mode:
                - name: Interface name (eth0, eth1, etc.)
                - mode: "static"
                - address: IP address
                - netmask: Network mask
                - gateway: Default gateway (optional)
                - dns: DNS server (optional, default: 8.8.8.8)
            DHCP mode:
                - name: Interface name (eth0, eth1, etc.)
                - mode: "dhcp"
                - dns: DNS server (optional, default: 8.8.8.8)

    Returns:
        JSON confirmation with configured interfaces

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


@mcp.tool(annotations={
    "creates_resource": True
})
async def create_snapshot(ctx: Context, name: str, description: str = "") -> str:
    """Create a snapshot of the current project state

    Snapshots capture the entire project state including:
    - All node configurations and positions
    - All link connections
    - Drawing objects
    - Project settings

    Warning is issued (but not blocking) if nodes are running. For consistent snapshots,
    stop all nodes before creating a snapshot.

    Args:
        name: Snapshot name (must be unique within project)
        description: Optional snapshot description

    Returns:
        JSON with SnapshotInfo for created snapshot

    Example:
        >>> create_snapshot("Before Config Change")
        >>> create_snapshot("Working Configuration", "Config before OSPF changes")
    """
    app: AppContext = ctx.request_context.lifespan_context

    error = await validate_current_project(app)
    if error:
        return error

    return await create_snapshot_impl(app, name, description)


@mcp.tool(annotations={
    "destructive": True
})
async def restore_snapshot(ctx: Context, snapshot_name: str) -> str:
    """Restore project to a previous snapshot state

    This operation:
    1. Stops all running nodes
    2. Disconnects all console sessions
    3. Restores project to snapshot state

    All current changes since the snapshot will be lost.

    Args:
        snapshot_name: Name of the snapshot to restore

    Returns:
        JSON with success message and restore details

    Example:
        >>> restore_snapshot("Before Config Change")
    """
    app: AppContext = ctx.request_context.lifespan_context

    error = await validate_current_project(app)
    if error:
        return error

    return await restore_snapshot_impl(app, snapshot_name)


@mcp.tool()
async def get_project_readme(ctx: Context, project_id: Optional[str] = None) -> str:
    """Get project README/notes

    Returns project documentation in markdown format including:
    - IP addressing schemes and VLANs
    - Node credentials and details
    - Architecture notes and diagrams
    - Configuration snippets
    - Troubleshooting notes

    Args:
        project_id: Project ID (uses current project if not specified)

    Returns:
        JSON with project_id and markdown content

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


@mcp.tool()
async def update_project_readme(ctx: Context, content: str, project_id: Optional[str] = None) -> str:
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
mcp.tool(annotations={
    "idempotent": True,
    "read_only": True,
    "creates_resource": True
})(export_topology_diagram)


# ============================================================================
# Drawing Tools
# ============================================================================

@mcp.tool(annotations={
    "creates_resource": True
})
async def create_drawing(
    ctx: Context,
    drawing_type: str,
    x: int,
    y: int,
    z: int = 0,
    width: Optional[int] = None,
    height: Optional[int] = None,
    rx: Optional[int] = None,
    ry: Optional[int] = None,
    fill_color: str = "#ffffff",
    border_color: str = "#000000",
    border_width: int = 2,
    x2: Optional[int] = None,
    y2: Optional[int] = None,
    text: Optional[str] = None,
    font_size: int = 10,
    font_weight: str = "normal",
    font_family: str = "TypeWriter",
    color: str = "#000000"
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


@mcp.tool(annotations={
    "idempotent": True
})
async def update_drawing(
    ctx: Context,
    drawing_id: str,
    x: Optional[int] = None,
    y: Optional[int] = None,
    z: Optional[int] = None,
    rotation: Optional[int] = None,
    svg: Optional[str] = None,
    locked: Optional[bool] = None
) -> str:
    """Update properties of an existing drawing object

    Args:
        drawing_id: ID of the drawing to update
        x: New X coordinate (optional)
        y: New Y coordinate (optional)
        z: New Z-order/layer (optional)
        rotation: New rotation angle in degrees (optional)
        svg: New SVG content (optional, for changing appearance)
        locked: Lock/unlock drawing (optional)

    Returns:
        JSON with updated drawing info
    """
    app: AppContext = ctx.request_context.lifespan_context

    error = await validate_current_project(app)
    if error:
        return error

    return await update_drawing_impl(app, drawing_id, x, y, z, rotation, svg, locked)


@mcp.tool(annotations={
    "destructive": True,
    "idempotent": True
})
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

    return await delete_drawing_impl(app, drawing_id)


# ============================================================================
# SSH Proxy Tools
# ============================================================================

from tools.ssh_tools import (
    configure_ssh_impl,
    ssh_send_command_impl,
    ssh_send_config_set_impl,
    ssh_disconnect_impl
)


@mcp.tool(annotations={
    "idempotent": True
})
async def ssh_configure(
    ctx: Context,
    node_name: str,
    device_dict: dict,
    persist: bool = True,
    force: bool = False
) -> str:
    """Configure SSH session for network device

    IMPORTANT: Enable SSH on device first using console tools.

    Session Management (v0.1.6) - AUTOMATIC RECOVERY:
    - Reuses existing healthy sessions automatically
    - Detects expired sessions (30min TTL) and recreates automatically
    - Detects stale/closed connections via health check and recreates automatically
    - On "Socket is closed" errors: Just call ssh_configure() again (no force needed)

    When ssh_command() fails with "Socket is closed":
    1. Session is auto-removed from memory
    2. Simply call ssh_configure() again with same parameters
    3. Fresh session will be created automatically
    4. Retry your ssh_command() - it will work

    Args:
        node_name: Node identifier
        device_dict: Netmiko config dict (device_type, host, username, password, port, secret)
        persist: Store credentials for reconnection (default: True)
        force: Force recreation even if healthy session exists (default: False)
               Only needed for: manual credential refresh, troubleshooting

    Returns:
        JSON with session_id, connected, device_type

    Examples:
        # Normal usage - creates session or reuses healthy one
        ssh_configure("R1", {"device_type": "cisco_ios", "host": "10.1.0.1",
                             "username": "admin", "password": "cisco123"})

        # After "Socket is closed" error - just retry (auto-recovery)
        # NO force parameter needed - stale session already cleaned up
        ssh_configure("R1", device_dict)

        # Force recreation (rarely needed)
        ssh_configure("R1", device_dict, force=True)
    """
    app: AppContext = ctx.request_context.lifespan_context
    return await configure_ssh_impl(app, node_name, device_dict, persist, force)


@mcp.tool()
async def ssh_command(
    ctx: Context,
    node_name: str,
    command: str | list,
    expect_string: str = None,
    read_timeout: float = 30.0,
    wait_timeout: int = 30
) -> str:
    """Execute command(s) via SSH with auto-detection (show vs config)

    Auto-detects command type:
    - String: Single show command (uses ssh_send_command)
    - List: Configuration commands (uses ssh_send_config_set)

    Long commands: Set read_timeout high, wait_timeout=0 for job_id,
    poll with resource gns3://sessions/ssh/{node}/jobs/{id}

    Args:
        node_name: Node identifier
        command: Command(s) - string for show, list for config
        expect_string: Regex pattern to wait for (overrides prompt detection, optional)
        read_timeout: Max seconds to wait for output (default: 30)
        wait_timeout: Seconds to poll before returning job_id (default: 30)

    Returns:
        JSON with completed, job_id, output, execution_time

    Examples:
        # Show command (string)
        ssh_command("R1", "show ip interface brief")

        # Config commands (list)
        ssh_command("R1", [
            "interface GigabitEthernet0/0",
            "ip address 192.168.1.1 255.255.255.0",
            "no shutdown"
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


@mcp.tool(annotations={
    "idempotent": True
})
async def ssh_disconnect(ctx: Context, node_name: str) -> str:
    """Disconnect SSH session

    Args:
        node_name: Node identifier

    Returns:
        JSON with status
    """
    app: AppContext = ctx.request_context.lifespan_context
    return await ssh_disconnect_impl(app, node_name)


# ============================================================================
# MCP Completions - Autocomplete Support
# ============================================================================
# NOTE: Completions currently disabled - FastMCP API for completions is different
# from standard MCP spec. Will be re-enabled once correct API is determined.
# See: https://github.com/anthropics/fastmcp/issues

# # Completion for node names
# @mcp.completion("console_send", "node_name")
# @mcp.completion("console_read", "node_name")
# @mcp.completion("console_keystroke", "node_name")
# @mcp.completion("console_disconnect", "node_name")
# @mcp.completion("ssh_configure", "node_name")
# @mcp.completion("ssh_command", "node_name")
# @mcp.completion("ssh_disconnect", "node_name")
# @mcp.completion("set_node", "node_name")
# @mcp.completion("delete_node", "node_name")
async def complete_node_names_DISABLED(ctx: Context, prefix: str) -> list[Completion]:
    """Autocomplete node names from current project"""
    app: AppContext = ctx.request_context.lifespan_context

    if not app.current_project_id:
        return []

    try:
        nodes = await app.gns3.get_nodes(app.current_project_id)

        # Filter by prefix
        matching = [n for n in nodes if n["name"].lower().startswith(prefix.lower())]

        # Return completions
        return [
            Completion(
                value=node["name"],
                label=node["name"],
                description=f"{node['node_type']} ({node['status']})"
            )
            for node in matching[:10]  # Limit to 10 results
        ]

    except Exception as e:
        logger.warning(f"Failed to fetch nodes for completion: {e}")
        return []


# # Completion for template names
# @mcp.completion("create_node", "template_name")
async def complete_template_names_DISABLED(ctx: Context, prefix: str) -> list[Completion]:
    """Autocomplete template names"""
    app: AppContext = ctx.request_context.lifespan_context

    try:
        templates = await app.gns3.get_templates()

        matching = [t for t in templates if t["name"].lower().startswith(prefix.lower())]

        return [
            Completion(
                value=template["name"],
                label=template["name"],
                description=f"{template.get('category', 'Unknown')} - {template.get('node_type', '')}"
            )
            for template in matching[:10]
        ]

    except Exception as e:
        logger.warning(f"Failed to fetch templates for completion: {e}")
        return []


# # Completion for node actions (enum)
# @mcp.completion("set_node", "action")
async def complete_node_actions_DISABLED(ctx: Context, prefix: str) -> list[Completion]:
    """Autocomplete node actions"""
    actions = [
        ("start", "Start the node"),
        ("stop", "Stop the node"),
        ("suspend", "Suspend the node"),
        ("reload", "Reload the node"),
        ("restart", "Restart the node (stop + start)")
    ]

    matching = [(a, desc) for a, desc in actions if a.startswith(prefix.lower())]

    return [
        Completion(value=action, label=action, description=desc)
        for action, desc in matching
    ]


# # Completion for project names
# @mcp.completion("open_project", "project_name")
async def complete_project_names_DISABLED(ctx: Context, prefix: str) -> list[Completion]:
    """Autocomplete project names"""
    app: AppContext = ctx.request_context.lifespan_context

    try:
        projects = await app.gns3.get_projects()

        matching = [p for p in projects if p["name"].lower().startswith(prefix.lower())]

        return [
            Completion(
                value=project["name"],
                label=project["name"],
                description=f"Status: {project['status']}"
            )
            for project in matching[:10]
        ]

    except Exception as e:
        logger.warning(f"Failed to fetch projects for completion: {e}")
        return []


# # Completion for snapshot names
# @mcp.completion("restore_snapshot", "snapshot_name")
async def complete_snapshot_names_DISABLED(ctx: Context, prefix: str) -> list[Completion]:
    """Autocomplete snapshot names"""
    app: AppContext = ctx.request_context.lifespan_context

    if not app.current_project_id:
        return []

    try:
        snapshots = await app.gns3.get_snapshots(app.current_project_id)

        matching = [s for s in snapshots if s["name"].lower().startswith(prefix.lower())]

        return [
            Completion(
                value=snapshot["name"],
                label=snapshot["name"],
                description=f"Created: {snapshot.get('created_at', 'Unknown')}"
            )
            for snapshot in matching[:10]
        ]

    except Exception as e:
        logger.warning(f"Failed to fetch snapshots for completion: {e}")
        return []


# # Completion for drawing types (enum)
# @mcp.completion("create_drawing", "drawing_type")
async def complete_drawing_types_DISABLED(ctx: Context, prefix: str) -> list[Completion]:
    """Autocomplete drawing types"""
    drawing_types = [
        ("rectangle", "Create a rectangle shape"),
        ("ellipse", "Create an ellipse/circle shape"),
        ("line", "Create a line"),
        ("text", "Create a text label")
    ]

    matching = [(dt, desc) for dt, desc in drawing_types if dt.startswith(prefix.lower())]

    return [
        Completion(value=dtype, label=dtype, description=desc)
        for dtype, desc in matching
    ]


# # Completion for topology types (enum)
# @mcp.completion("lab_setup", "topology_type")
async def complete_topology_types_DISABLED(ctx: Context, prefix: str) -> list[Completion]:
    """Autocomplete topology types"""
    topology_types = [
        ("star", "Hub-and-spoke topology (device_count = spokes)"),
        ("mesh", "Full mesh topology (all routers interconnected)"),
        ("linear", "Chain topology (routers in series)"),
        ("ring", "Circular topology (closes the loop)"),
        ("ospf", "Multi-area OSPF topology (device_count = areas)"),
        ("bgp", "Multiple AS topology (device_count = AS, 2 routers per AS)")
    ]

    matching = [(tt, desc) for tt, desc in topology_types if tt.startswith(prefix.lower())]

    return [
        Completion(value=ttype, label=ttype, description=desc)
        for ttype, desc in matching
    ]


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
