"""GNS3 MCP Server v0.14.0

Model Context Protocol server for GNS3 lab automation.
Provides console and SSH automation tools for network devices.

IMPORTANT: Tool Selection Guidelines
====================================
When automating network devices, ALWAYS prefer SSH tools over console tools!

SSH Tools (Preferred):
- ssh_send_command(), ssh_send_config_set()
- Better reliability with automatic prompt detection
- Structured output and error handling
- Supports 200+ device types via Netmiko

Console Tools (Use Only When Necessary):
- send_console(), read_console(), send_and_wait_console()
- For initial device configuration (enabling SSH, creating users)
- For troubleshooting when SSH is unavailable
- For devices without SSH support (VPCS, simple switches)

Typical Workflow:
1. Use console tools to configure SSH access on device
2. Establish SSH session with configure_ssh()
3. Switch to SSH tools for all automation tasks
4. Return to console only if SSH fails

Version 0.14.0 - Tool Consolidation (BREAKING CHANGES - Final Architecture):
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
from tools.project_tools import list_projects_impl, open_project_impl
from tools.node_tools import (
    list_nodes_impl,
    get_node_details_impl,
    set_node_impl,
    create_node_impl,
    delete_node_impl
)
from tools.console_tools import (
    send_console_impl,
    read_console_impl,
    disconnect_console_impl,
    get_console_status_impl,
    send_and_wait_console_impl,
    send_keystroke_impl
)
from tools.link_tools import get_links_impl, set_connection_impl
from tools.drawing_tools import (
    list_drawings_impl,
    create_drawing_impl,
    delete_drawing_impl
)
from tools.template_tools import list_templates_impl
from resources import ResourceManager

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


# ============================================================================
# MCP Resources - Browsable State
# ============================================================================

# Project resources
@mcp.resource("gns3://projects")
async def resource_projects(ctx: Context) -> str:
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.list_projects()

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

@mcp.resource("gns3://projects/{project_id}/templates")
async def resource_templates(ctx: Context, project_id: str) -> str:
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.list_templates(project_id)

@mcp.resource("gns3://projects/{project_id}/drawings")
async def resource_drawings(ctx: Context, project_id: str) -> str:
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.list_drawings(project_id)

# Console session resources
@mcp.resource("gns3://sessions/console")
async def resource_console_sessions(ctx: Context) -> str:
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.list_console_sessions()

@mcp.resource("gns3://sessions/console/{node_name}")
async def resource_console_session(ctx: Context, node_name: str) -> str:
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.get_console_session(node_name)

# SSH session resources
@mcp.resource("gns3://sessions/ssh")
async def resource_ssh_sessions(ctx: Context) -> str:
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.list_ssh_sessions()

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
async def resource_proxy_status(ctx: Context) -> str:
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.get_proxy_status()

@mcp.resource("gns3://proxy/sessions")
async def resource_proxy_sessions(ctx: Context) -> str:
    app: AppContext = ctx.request_context.lifespan_context
    return await app.resource_manager.list_proxy_sessions()


# ============================================================================
# MCP Tools - Actions That Modify State
# ============================================================================

@mcp.tool()
async def open_project(ctx: Context, project_name: str) -> str:
    """Open a GNS3 project by name

    Args:
        project_name: Name of the project to open

    Returns:
        JSON with ProjectInfo for opened project
    """
    app: AppContext = ctx.request_context.lifespan_context
    return await open_project_impl(app, project_name)


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
    return await set_node_impl(
        app, node_name, action, x, y, z, locked, ports,
        name, ram, cpus, hdd_disk_image, adapters, console_type
    )


@mcp.tool()
async def send_console(ctx: Context, node_name: str, data: str, raw: bool = False) -> str:
    """Send data to console (auto-connects if needed)

    IMPORTANT: Prefer SSH tools when available! Console tools are primarily for:
    - Initial device configuration (enabling SSH, creating users)
    - Troubleshooting when SSH is unavailable
    - Devices without SSH support (VPCS, simple switches)

    For automation workflows, use SSH tools (ssh_send_command, ssh_send_config_set)
    which provide better reliability, error handling, and prompt detection.

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
    return await send_console_impl(app, node_name, data, raw)


@mcp.tool()
async def read_console(
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

    For automation workflows, use ssh_send_command() and ssh_read_buffer()
    which provide better reliability and structured output.

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
        read_console("R1", mode="all", pattern="error", case_insensitive=True)

    Example - Find interface with context:
        read_console("R1", mode="diff", pattern="GigabitEthernet", context=2)
    """
    app: AppContext = ctx.request_context.lifespan_context
    return await read_console_impl(app, node_name, mode, pages, pattern, case_insensitive, invert, before, after, context)


@mcp.tool()
async def disconnect_console(ctx: Context, node_name: str) -> str:
    """Disconnect console session

    Args:
        node_name: Name of the node

    Returns:
        JSON with status
    """
    app: AppContext = ctx.request_context.lifespan_context
    return await disconnect_console_impl(app, node_name)


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

    IMPORTANT: Prefer SSH tools when available! Console tools are primarily for:
    - Initial device configuration (enabling SSH, creating users)
    - Troubleshooting when SSH is unavailable
    - Devices without SSH support

    For automation workflows, use ssh_send_command() which provides automatic
    prompt detection and better error handling.

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
    return await send_and_wait_console_impl(
        app, node_name, command, wait_pattern, timeout, raw
    )


@mcp.tool()
async def send_keystroke(ctx: Context, node_name: str, key: str) -> str:
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

    return await delete_node_impl(app, node_name)


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

    return await create_node_impl(app, template_name, x, y, node_name, compute_id)


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

    return await create_drawing_impl(
        app, drawing_type, x, y, z, width, height, rx, ry,
        fill_color, border_color, border_width,
        x2, y2, text, font_size, font_weight, font_family, color
    )


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

    return await delete_drawing_impl(app, drawing_id)


# export_topology_diagram tool now registered from export_tools module
# Register the imported tool with MCP
mcp.tool()(export_topology_diagram)


# ============================================================================
# SSH Proxy Tools
# ============================================================================

from tools.ssh_tools import (
    configure_ssh_impl,
    ssh_send_command_impl,
    ssh_send_config_set_impl,
    ssh_read_buffer_impl,
    ssh_get_history_impl,
    ssh_get_command_output_impl,
    ssh_get_status_impl,
    ssh_cleanup_sessions_impl,
    ssh_get_job_status_impl
)


@mcp.tool()
async def configure_ssh(
    ctx: Context,
    node_name: str,
    device_dict: dict,
    persist: bool = True
) -> str:
    """Configure SSH session for network device

    IMPORTANT: Enable SSH on device first using console tools.

    Args:
        node_name: Node identifier
        device_dict: Netmiko config dict (device_type, host, username, password, port, secret)
        persist: Store credentials for reconnection (default: True)

    Returns:
        JSON with session_id, connected, device_type
    """
    app: AppContext = ctx.request_context.lifespan_context
    return await configure_ssh_impl(app, node_name, device_dict, persist)


@mcp.tool()
async def ssh_send_command(
    ctx: Context,
    node_name: str,
    command: str,
    expect_string: str = None,
    read_timeout: float = 30.0,
    wait_timeout: int = 30
) -> str:
    """Execute show command via SSH with adaptive async

    Long commands: Set read_timeout high, wait_timeout=0 for job_id, poll with ssh_get_job_status().

    Args:
        node_name: Node identifier
        command: Command to execute
        expect_string: Regex pattern to wait for (overrides prompt detection, optional)
        read_timeout: Max seconds to wait for output (default: 30)
        wait_timeout: Seconds to poll before returning job_id (default: 30)

    Returns:
        JSON with completed, job_id, output, execution_time
    """
    app: AppContext = ctx.request_context.lifespan_context
    return await ssh_send_command_impl(app, node_name, command, expect_string, read_timeout, wait_timeout)


@mcp.tool()
async def ssh_send_config_set(
    ctx: Context,
    node_name: str,
    config_commands: list,
    wait_timeout: int = 30
) -> str:
    """Send configuration commands via SSH

    Args:
        node_name: Node identifier
        config_commands: List of configuration commands
        wait_timeout: Seconds to poll before returning job_id (default: 30)

    Returns:
        JSON with completed, job_id, output, execution_time
    """
    app: AppContext = ctx.request_context.lifespan_context
    return await ssh_send_config_set_impl(app, node_name, config_commands, wait_timeout)


@mcp.tool()
async def ssh_cleanup_sessions(
    ctx: Context,
    keep_nodes: list = None,
    clean_all: bool = False
) -> str:
    """Clean orphaned/all SSH sessions

    Useful when project changes (different IPs on same node names).

    Args:
        keep_nodes: Node names to preserve (default: [])
        clean_all: Clean all sessions, ignoring keep_nodes (default: False)

    Returns:
        JSON with cleaned and kept node lists
    """
    app: AppContext = ctx.request_context.lifespan_context
    return await ssh_cleanup_sessions_impl(app, keep_nodes, clean_all)


@mcp.tool()
async def ssh_get_job_status(
    ctx: Context,
    job_id: str
) -> str:
    """Check job status by job_id (for async polling)

    Poll long-running commands that returned job_id.

    Args:
        job_id: Job ID from ssh_send_command or ssh_send_config_set

    Returns:
        JSON with job status, output, execution_time
    """
    app: AppContext = ctx.request_context.lifespan_context
    return await ssh_get_job_status_impl(app, job_id)


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
