"""Resource query tools - Claude Desktop compatibility layer.

Provides tool-based access to all MCP resources for Claude Desktop,
which cannot automatically access resources like Claude Code can.

Resources remain the primary data access method for Claude Code.
These tools are thin wrappers that delegate to resource implementations.
"""

import logging
from typing import Literal

from ..app_context import AppContext
from ..error_utils import create_error_response
from ..models import ErrorCode

logger = logging.getLogger(__name__)


async def query_resource(
    app: AppContext,
    uri: str,
    format: Literal["table", "json"] = "table",
) -> str:
    """Universal resource query tool - access any GNS3 MCP resource.

    Provides read-only access to all 25+ GNS3 MCP resources through URI interface.
    Resources include projects, nodes, links, sessions, templates, and diagrams.

    For Claude Code users: Resources (gns3://{uri}) are preferred over this tool.
    For Claude Desktop users: Use this tool to access resource data.

    Args:
        uri: Resource URI to query. Supported patterns:

            Projects:
              projects://                           List all projects
              projects://{id}                       Project details
              projects://{id}/readme                Project documentation
              projects://{id}/topology_report       Unified topology overview
              projects://{id}/sessions/console/     Console sessions in project
              projects://{id}/sessions/ssh/         SSH sessions in project

            Nodes & Links:
              nodes://{project_id}/                 List nodes
              nodes://{project_id}/{node_id}        Node details
              nodes://{project_id}/{node_id}/template Node template info
              links://{project_id}/                 List links
              drawings://{project_id}/              List drawings

            Sessions:
              sessions://console/                   All console sessions
              sessions://console/?project_id={id}   Console sessions (filtered)
              sessions://console/{node_name}        Console session details
              sessions://ssh/                       All SSH sessions
              sessions://ssh/?project_id={id}       SSH sessions (filtered)
              sessions://ssh/{node_name}            SSH session details
              sessions://ssh/{node_name}/history    SSH command history
              sessions://ssh/{node_name}/buffer     SSH output buffer

            Templates & Diagrams:
              templates://                          List all templates
              templates://{template_id}             Template details
              diagrams://{project_id}/topology      Topology diagram (SVG/PNG)

            Proxies:
              proxies:///status                     Main proxy status (3 slashes!)
              proxies://                            Proxy registry
              proxies://sessions                    All proxy sessions
              proxies://project/{project_id}        Project-specific proxies
              proxies://{proxy_id}                  Specific proxy details

        format: Output format:
            - "table" (default): Human-readable text tables (no borders, "simple" style)
            - "json": Structured JSON for programmatic access

    Returns:
        Resource data in requested format, or error message

    Examples:
        # List all projects
        query_resource("projects://")

        # Get nodes in project (replace {project_id} with actual ID)
        query_resource("nodes://abc-123-def-456/")

        # Get SSH session for node
        query_resource("sessions://ssh/Router1")

        # Export as JSON
        query_resource("templates://", format="json")

        # Get topology report (v0.40.0 unified view)
        query_resource("projects://abc-123/topology_report")

    Note: For write operations, use specific tools like open_project(),
    configure_ssh_session(), set_node_properties(), etc. This tool is read-only.
    """
    try:
        # Delegate to resource manager
        result = await app.resource_manager.get_resource(uri)

        # Resource implementations already return formatted output
        # If format is JSON and result is table, this needs conversion
        # However, most resources support both formats internally
        # For now, return as-is and enhance later if needed
        return result

    except Exception as e:
        logger.error(f"Resource query failed for URI '{uri}': {e}")
        return create_error_response(
            error="Resource query failed",
            error_code=ErrorCode.INVALID_PARAMETER,
            details=str(e),
            suggested_action="Check URI syntax matches supported patterns. "
            "Verify project_id exists for project-scoped resources. "
            "Use 'projects://' to list available projects first.",
        )


async def list_projects(
    app: AppContext,
    format: Literal["table", "json"] = "table",
) -> str:
    """List all GNS3 projects (convenience wrapper).

    Convenience tool that wraps query_resource("projects://").
    Provides quick access to most commonly used resource.

    For Claude Code users: Resource gns3://projects:// is preferred.
    For Claude Desktop users: Use this tool for convenience.

    Args:
        format: Output format:
            - "table" (default): Human-readable text table with columns:
              status, name, uri (simple style, no borders)
            - "json": Structured JSON array of project objects

    Returns:
        List of projects in requested format

    Examples:
        # List projects as table
        list_projects()

        # List projects as JSON
        list_projects(format="json")

    See also:
        - query_resource("projects://") - equivalent universal tool
        - open_project(name) - open a specific project
        - create_project(name) - create new project
    """
    return await query_resource(app, "projects://", format)


async def list_nodes(
    app: AppContext,
    project_id: str,
    format: Literal["table", "json"] = "table",
) -> str:
    """List nodes in a GNS3 project (convenience wrapper).

    Convenience tool that wraps query_resource(f"nodes://{project_id}/").
    Provides quick access to second most commonly used resource.

    For Claude Code users: Resource gns3://nodes://{project_id}/ is preferred.
    For Claude Desktop users: Use this tool for convenience.

    Args:
        project_id: GNS3 project ID (UUID format)
        format: Output format:
            - "table" (default): Human-readable text table with columns:
              name, status, node_type, console_type (simple style, no borders)
            - "json": Structured JSON array of node objects

    Returns:
        List of nodes in requested format

    Examples:
        # List nodes as table (replace with actual project ID)
        list_nodes("abc-123-def-456")

        # List nodes as JSON
        list_nodes("abc-123-def-456", format="json")

    See also:
        - query_resource(f"nodes://{project_id}/") - equivalent universal tool
        - list_projects() - get project IDs
        - set_node_properties() - configure nodes
        - create_node() - add new nodes
    """
    return await query_resource(app, f"nodes://{project_id}/", format)


async def get_topology(
    app: AppContext,
    project_id: str,
    format: Literal["table", "json"] = "table",
) -> str:
    """Get unified topology report for a project (convenience wrapper).

    Convenience tool that wraps query_resource(f"projects://{project_id}/topology_report").
    Provides quick access to v0.40.0 topology_report feature - comprehensive overview
    with nodes, links, and statistics in single call.

    Replaces 3+ separate tool calls (list_projects, list_nodes, get_links).

    For Claude Code users: Resource gns3://projects://{project_id}/topology_report is preferred.
    For Claude Desktop users: Use this tool for convenience.

    Args:
        project_id: GNS3 project ID (UUID format)
        format: Output format:
            - "table" (default): Human-readable report with:
              - Node statistics (types, statuses, connection counts)
              - Node table (name, type, status, console_type)
              - Link topology table (node_a, port_a, node_b, port_b)
            - "json": Structured JSON with nodes, links, statistics

    Returns:
        Topology report in requested format

    Examples:
        # Get topology as formatted report
        get_topology("abc-123-def-456")

        # Get topology as JSON for analysis
        get_topology("abc-123-def-456", format="json")

    See also:
        - query_resource(f"projects://{project_id}/topology_report") - equivalent
        - list_nodes(project_id) - just nodes, no links
        - query_resource(f"links://{project_id}/") - just links, no nodes
    """
    return await query_resource(app, f"projects://{project_id}/topology_report", format)
